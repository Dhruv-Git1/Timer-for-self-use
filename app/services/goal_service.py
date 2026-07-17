"""Goal targets, one-off tasks, permanent routines, and their analytics."""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from typing import Optional

from app.database.repositories.category_repo import CategoryRepository
from app.database.repositories.daily_progress_repo import DailyProgressRepository
from app.database.repositories.entry_repo import EntryRepository
from app.database.repositories.goal_repo import GoalRepository
from app.models.goal import (
    GOAL_PERIODS,
    INTERVAL_UNITS,
    PERIOD_BIWEEKLY,
    PERIOD_CUSTOM,
    PERIOD_MONTHLY,
    PERIOD_TIMELESS,
    PERIOD_WEEKLY,
    Goal,
    GoalHistory,
    GoalProgress,
    GoalRoutine,
    GoalTask,
    RoutineStats,
)
from app.services import aggregation
from app.utils import time_utils
from app.utils.event_bus import DATA_CHANGED, bus


_TASK_TS_FORMAT = "%Y-%m-%d %H:%M"
_COMPLETE_TS_FORMAT = "%Y-%m-%d %H:%M:%S"


class GoalService:
    """Own every goal type while deriving progress from authoritative activity."""

    def __init__(
        self,
        goal_repo: GoalRepository,
        category_repo: CategoryRepository,
        entry_repo: EntryRepository,
        progress_repo: DailyProgressRepository,
    ) -> None:
        self.repo = goal_repo
        self.categories = category_repo
        self.entries = entry_repo
        self.progress = progress_repo

    # ------------------------------------------------------------------
    # Category-measured targets (the original Goals feature)
    # ------------------------------------------------------------------
    def list_goals(self, include_archived: bool = False) -> list[Goal]:
        return self.repo.list_all(include_archived=include_archived)

    def get(self, goal_id: int) -> Optional[Goal]:
        return self.repo.get(goal_id)

    def create(
        self,
        title: str,
        category_id: int,
        target_value: int,
        period: str,
        start_date: str,
        end_date: str | None = None,
        interval_count: int | None = None,
        interval_unit: str | None = None,
    ) -> tuple[bool, str, Optional[int]]:
        goal = Goal(
            id=0,
            title=title,
            category_id=category_id,
            target_value=target_value,
            period=period,
            start_date=start_date,
            end_date=end_date,
            interval_count=interval_count,
            interval_unit=interval_unit,
        )
        ok, message = self._validate_goal(goal)
        if not ok:
            return False, message, None
        self._normalize_goal_window(goal)
        goal_id = self.repo.create(
            goal.title,
            goal.category_id,
            goal.target_value,
            goal.period,
            goal.start_date,
            goal.end_date,
            goal.interval_count,
            goal.interval_unit,
        )
        bus.publish(DATA_CHANGED)
        return True, "", goal_id

    def update(self, goal: Goal) -> tuple[bool, str, Optional[int]]:
        if self.repo.get(goal.id) is None:
            return False, "Goal no longer exists.", None
        ok, message = self._validate_goal(goal)
        if not ok:
            return False, message, None
        self._normalize_goal_window(goal)
        self.repo.update(goal)
        bus.publish(DATA_CHANGED)
        return True, "", goal.id

    def delete(self, goal_id: int) -> tuple[bool, str, Optional[int]]:
        if self.repo.get(goal_id) is None:
            return False, "Goal no longer exists.", None
        self.repo.delete(goal_id)
        bus.publish(DATA_CHANGED)
        return True, "", goal_id

    def progress_for(self, as_of: str | None = None) -> list[GoalProgress]:
        as_of = as_of or time_utils.today_str()
        result: list[GoalProgress] = []
        for goal in self.repo.list_all():
            category = self.categories.get(goal.category_id)
            if category is None:
                continue
            window_start, window_end, window_label = self._window_for(goal, as_of)
            actual = self._actual(category, window_start, window_end)
            result.append(
                GoalProgress(
                    goal=goal,
                    category_name=category.name,
                    category_color=category.color,
                    tracking_mode=category.tracking_mode,
                    unit_label=category.unit_label,
                    window_start=window_start,
                    window_end=window_end,
                    window_label=window_label,
                    actual=actual,
                )
            )
        return result

    def progress_for_goal(self, goal_id: int, as_of: str | None = None) -> GoalProgress | None:
        return next(
            (item for item in self.progress_for(as_of) if item.goal.id == goal_id),
            None,
        )

    def target_history(self, goal_id: int, as_of: str | None = None) -> GoalHistory | None:
        """Return a goal-specific actual/target history suitable for a chart."""
        goal = self.repo.get(goal_id)
        if goal is None:
            return None
        category = self.categories.get(goal.category_id)
        if category is None:
            return None
        as_of = as_of or time_utils.today_str()
        if goal.period in {PERIOD_CUSTOM, PERIOD_TIMELESS} and not goal.is_custom_interval:
            return self._cumulative_history(goal, category, as_of)

        max_periods = 8 if goal.period == PERIOD_BIWEEKLY else 12
        windows: list[tuple[str, str, str]] = []
        cursor = max(as_of, goal.start_date)
        for _ in range(max_periods):
            start, end, _label = self._window_for(goal, cursor)
            windows.append((start, end, time_utils.to_date(start).strftime("%d %b")))
            if start <= goal.start_date:
                break
            cursor = time_utils.add_days(start, -1)
        windows.reverse()

        actuals = [float(self._actual(category, start, end)) for start, end, _ in windows]
        targets = [float(goal.target_value)] * len(windows)
        if category.is_timer:
            actuals = [value / 60 for value in actuals]
            targets = [value / 60 for value in targets]
            unit = "hours"
        else:
            unit = category.unit_label
        return GoalHistory(
            labels=[label for _start, _end, label in windows],
            actual_values=actuals,
            target_values=targets,
            unit_label=unit,
        )

    def _validate_goal(self, goal: Goal) -> tuple[bool, str]:
        title = (goal.title or "").strip()
        if not title:
            return False, "Goal name cannot be empty."
        if len(title) > 80:
            return False, "Goal name is too long (max 80 characters)."
        if goal.period not in GOAL_PERIODS:
            return False, "Choose a goal period."
        if not isinstance(goal.target_value, int) or not 1 <= goal.target_value <= 999_999:
            return False, "Target must be a whole number from 1 to 999999."
        category = self.categories.get(goal.category_id)
        if category is None or category.is_archived:
            return False, "Choose an active category to measure this goal."
        if not time_utils.is_valid_date(goal.start_date):
            return False, "Start date must be a real YYYY-MM-DD date."

        if goal.period == PERIOD_CUSTOM and goal.interval_count is not None:
            if not 1 <= goal.interval_count <= 999:
                return False, "Custom interval must be from 1 to 999."
            if goal.interval_unit not in INTERVAL_UNITS:
                return False, "Choose days, weeks, or months for the custom interval."
            if goal.end_date:
                return False, "A repeating custom goal does not use an end date."
        elif goal.period == PERIOD_CUSTOM:
            if goal.interval_unit is not None:
                return False, "Enter a number for the custom interval."
            if not goal.end_date or not time_utils.is_valid_date(goal.end_date):
                return False, "A custom range needs an end date (YYYY-MM-DD)."
            if goal.end_date < goal.start_date:
                return False, "The end date must be on or after the start date."
        elif goal.end_date or goal.interval_count is not None or goal.interval_unit is not None:
            return False, "Only a custom schedule can use an end date or interval."
        return True, ""

    @staticmethod
    def _normalize_goal_window(goal: Goal) -> None:
        if goal.period != PERIOD_CUSTOM:
            goal.end_date = None
            goal.interval_count = None
            goal.interval_unit = None
        elif goal.interval_count is not None:
            goal.end_date = None

    def _window_for(self, goal: Goal, as_of: str) -> tuple[str, str, str]:
        current = max(as_of, goal.start_date)
        current_date = time_utils.to_date(current)
        start_date = time_utils.to_date(goal.start_date)

        if goal.period == PERIOD_WEEKLY:
            period_start = current_date - timedelta(days=current_date.weekday())
            period_start = max(period_start, start_date)
            period_end = period_start + timedelta(days=6 - period_start.weekday())
            return self._range(period_start, period_end, "This week")

        if goal.period == PERIOD_BIWEEKLY:
            days_since_start = max(0, (current_date - start_date).days)
            period_start = start_date + timedelta(days=(days_since_start // 14) * 14)
            return self._range(period_start, period_start + timedelta(days=13), "2-week cycle")

        if goal.period == PERIOD_MONTHLY:
            period_start = max(current_date.replace(day=1), start_date)
            last_day = calendar.monthrange(current_date.year, current_date.month)[1]
            period_end = current_date.replace(day=last_day)
            return self._range(period_start, period_end, current_date.strftime("%B %Y"))

        if goal.period == PERIOD_CUSTOM and goal.is_custom_interval:
            period_start, period_end = self._custom_interval_window(goal, current_date)
            count = goal.interval_count or 1
            unit = goal.interval_unit or "days"
            return self._range(period_start, period_end, f"Every {count} {unit}")

        if goal.period == PERIOD_CUSTOM:
            end = time_utils.to_date(goal.end_date or goal.start_date)
            return self._range(start_date, end, "Custom window")

        return self._range(start_date, current_date, "No deadline")

    def _custom_interval_window(self, goal: Goal, current_date: date) -> tuple[date, date]:
        start = time_utils.to_date(goal.start_date)
        count = goal.interval_count or 1
        unit = goal.interval_unit or "days"
        if unit in {"days", "weeks"}:
            cycle_days = count * (7 if unit == "weeks" else 1)
            cycle_index = max(0, (current_date - start).days // cycle_days)
            period_start = start + timedelta(days=cycle_index * cycle_days)
            return period_start, period_start + timedelta(days=cycle_days - 1)

        month_delta = (current_date.year - start.year) * 12 + current_date.month - start.month
        cycle_index = max(0, month_delta // count)
        period_start = self._add_months_clipped(start, cycle_index * count)
        while period_start > current_date and cycle_index > 0:
            cycle_index -= 1
            period_start = self._add_months_clipped(start, cycle_index * count)
        next_start = self._add_months_clipped(start, (cycle_index + 1) * count)
        return period_start, next_start - timedelta(days=1)

    @staticmethod
    def _add_months_clipped(source: date, months: int) -> date:
        month_index = source.year * 12 + (source.month - 1) + months
        year, zero_month = divmod(month_index, 12)
        month = zero_month + 1
        day = min(source.day, calendar.monthrange(year, month)[1])
        return date(year, month, day)

    @staticmethod
    def _range(start: date, end: date, prefix: str) -> tuple[str, str, str]:
        start_str = start.strftime("%Y-%m-%d")
        end_str = end.strftime("%Y-%m-%d")
        if start_str == end_str:
            label = f"{prefix} · {start.strftime('%d %b')}"
        else:
            label = f"{prefix} · {start.strftime('%d %b')}–{end.strftime('%d %b')}"
        return start_str, end_str, label

    def _actual(self, category, start_date: str, end_date: str) -> int:
        if category.is_timer:
            entries = self.entries.list_by_date_range(time_utils.add_days(start_date, -1), end_date)
            per_day = aggregation.build_day_category_minutes(entries, start_date, end_date)
            return sum(day.get(category.id, 0) for day in per_day.values())
        return self.progress.total_for_range(category.id, start_date, end_date)

    def _daily_actuals(self, category, start_date: str, end_date: str) -> dict[str, int]:
        if category.is_timer:
            entries = self.entries.list_by_date_range(time_utils.add_days(start_date, -1), end_date)
            table = aggregation.build_day_category_minutes(entries, start_date, end_date)
            return {day: values.get(category.id, 0) for day, values in table.items()}
        return self.progress.values_for_range(category.id, start_date, end_date)

    def _cumulative_history(self, goal: Goal, category, as_of: str) -> GoalHistory:
        start = goal.start_date
        end = min(as_of, goal.end_date) if goal.end_date else as_of
        end = max(start, end)
        daily = self._daily_actuals(category, start, end)
        labels: list[str] = []
        values: list[float] = []
        total = 0
        cursor = start
        while cursor <= end:
            total += daily.get(cursor, 0)
            labels.append(time_utils.to_date(cursor).strftime("%d %b"))
            values.append(float(total))
            cursor = time_utils.add_days(cursor, 1)

        # Keep multi-year open goals light enough for an interactive mobile chart.
        if len(values) > 120:
            step = (len(values) + 119) // 120
            indexes = list(range(0, len(values), step))
            if indexes[-1] != len(values) - 1:
                indexes.append(len(values) - 1)
            labels = [labels[index] for index in indexes]
            values = [values[index] for index in indexes]
        targets = [float(goal.target_value)] * len(values)
        if category.is_timer:
            values = [value / 60 for value in values]
            targets = [value / 60 for value in targets]
            unit = "hours"
        else:
            unit = category.unit_label
        return GoalHistory(labels, values, targets, unit)

    # ------------------------------------------------------------------
    # One-off tasks
    # ------------------------------------------------------------------
    def list_tasks(self, include_history: bool = False, as_of: str | None = None) -> list[GoalTask]:
        tasks = self.repo.list_tasks()
        if include_history:
            return sorted(
                (task for task in tasks if task.is_completed),
                key=lambda item: item.completed_at or "",
                reverse=True,
            )
        today = as_of or time_utils.today_str()
        return [
            task for task in tasks
            if not task.is_completed or task.completed_date == today
        ]

    def get_task(self, task_id: int) -> GoalTask | None:
        return self.repo.get_task(task_id)

    def create_task(
        self,
        title: str,
        due_at: str | None = None,
        reminder_offset_minutes: int | None = None,
        *,
        now: datetime | None = None,
    ) -> tuple[bool, str, Optional[int]]:
        task = GoalTask(0, title, due_at, reminder_offset_minutes)
        ok, message = self._validate_task(task, now=now)
        if not ok:
            return False, message, None
        task_id = self.repo.create_task(task.title, task.due_at, task.reminder_offset_minutes)
        bus.publish(DATA_CHANGED)
        return True, "", task_id

    def update_task(
        self, task: GoalTask, *, now: datetime | None = None
    ) -> tuple[bool, str, Optional[int]]:
        if self.repo.get_task(task.id) is None:
            return False, "Task no longer exists.", None
        ok, message = self._validate_task(task, now=now)
        if not ok:
            return False, message, None
        self.repo.update_task(task)
        bus.publish(DATA_CHANGED)
        return True, "", task.id

    def set_task_completed(
        self, task_id: int, completed: bool, *, now: datetime | None = None
    ) -> tuple[bool, str, Optional[int]]:
        task = self.repo.get_task(task_id)
        if task is None:
            return False, "Task no longer exists.", None
        now = now or datetime.now()
        task.completed_at = now.strftime(_COMPLETE_TS_FORMAT) if completed else None
        self.repo.update_task(task)
        bus.publish(DATA_CHANGED)
        return True, "", task.id

    def delete_task(self, task_id: int) -> tuple[bool, str, Optional[int]]:
        if self.repo.get_task(task_id) is None:
            return False, "Task no longer exists.", None
        self.repo.delete_task(task_id)
        bus.publish(DATA_CHANGED)
        return True, "", task_id

    def pending_task_reminders(self, now: datetime | None = None) -> list[GoalTask]:
        now = now or datetime.now()
        return [
            task for task in self.repo.list_tasks()
            if not task.is_completed and task.reminder_at is not None and task.reminder_at > now
        ]

    @staticmethod
    def _validate_task(task: GoalTask, *, now: datetime | None = None) -> tuple[bool, str]:
        title = (task.title or "").strip()
        if not title:
            return False, "Task name cannot be empty."
        if len(title) > 120:
            return False, "Task name is too long (max 120 characters)."
        if task.due_at:
            try:
                datetime.strptime(task.due_at, _TASK_TS_FORMAT)
            except ValueError:
                return False, "Deadline must be a real date and time."
        if task.reminder_offset_minutes is not None:
            if task.due_at is None:
                return False, "Choose a deadline before adding a reminder."
            if not isinstance(task.reminder_offset_minutes, int) or task.reminder_offset_minutes < 0:
                return False, "Reminder offset must be a non-negative whole number."
            now = now or datetime.now()
            if task.reminder_at is None or task.reminder_at <= now:
                return False, "Reminder time must be in the future."
        return True, ""

    # ------------------------------------------------------------------
    # Permanent routines
    # ------------------------------------------------------------------
    def list_routines(self, include_archived: bool = False) -> list[GoalRoutine]:
        return self.repo.list_routines(include_archived=include_archived)

    def get_routine(self, routine_id: int) -> GoalRoutine | None:
        return self.repo.get_routine(routine_id)

    def create_routine(
        self,
        title: str,
        category_id: int | None,
        weekdays_mask: int,
        start_date: str,
    ) -> tuple[bool, str, Optional[int]]:
        routine = GoalRoutine(0, title, category_id, weekdays_mask, start_date)
        ok, message = self._validate_routine(routine)
        if not ok:
            return False, message, None
        routine_id = self.repo.create_routine(
            routine.title, routine.category_id, routine.weekdays_mask, routine.start_date
        )
        bus.publish(DATA_CHANGED)
        return True, "", routine_id

    def update_routine(self, routine: GoalRoutine) -> tuple[bool, str, Optional[int]]:
        if self.repo.get_routine(routine.id) is None:
            return False, "Routine no longer exists.", None
        ok, message = self._validate_routine(routine)
        if not ok:
            return False, message, None
        self.repo.update_routine(routine)
        bus.publish(DATA_CHANGED)
        return True, "", routine.id

    def delete_routine(self, routine_id: int) -> tuple[bool, str, Optional[int]]:
        if self.repo.get_routine(routine_id) is None:
            return False, "Routine no longer exists.", None
        self.repo.delete_routine(routine_id)
        bus.publish(DATA_CHANGED)
        return True, "", routine_id

    def is_routine_scheduled(self, routine: GoalRoutine, log_date: str) -> bool:
        if not time_utils.is_valid_date(log_date) or log_date < routine.start_date:
            return False
        weekday = time_utils.to_date(log_date).weekday()
        return bool(routine.weekdays_mask & (1 << weekday))

    def routine_is_complete(self, routine_id: int, log_date: str) -> bool:
        return log_date in self.repo.routine_checkins(routine_id, log_date, log_date)

    def set_routine_completed(
        self, routine_id: int, log_date: str, completed: bool, as_of: str | None = None
    ) -> tuple[bool, str, Optional[int]]:
        routine = self.repo.get_routine(routine_id)
        if routine is None:
            return False, "Routine no longer exists.", None
        today = as_of or time_utils.today_str()
        if not time_utils.is_valid_date(log_date) or log_date > today:
            return False, "Only today or a past scheduled date can be changed.", None
        if not self.is_routine_scheduled(routine, log_date):
            return False, "This routine is not scheduled for that date.", None
        self.repo.set_routine_checkin(routine_id, log_date, completed)
        bus.publish(DATA_CHANGED)
        return True, "", routine_id

    def routine_stats(self, routine_id: int, as_of: str | None = None) -> RoutineStats | None:
        routine = self.repo.get_routine(routine_id)
        if routine is None:
            return None
        today = as_of or time_utils.today_str()
        if today < routine.start_date:
            return RoutineStats(0, 0, 0.0, 0)
        checkins = self.repo.routine_checkins(routine_id, routine.start_date, today)
        scheduled_dates = self._scheduled_dates(routine, routine.start_date, today)
        completed = sum(day in checkins for day in scheduled_dates)

        # Today's scheduled checkbox is pending until the local day ends, so it
        # must not break a streak or lower the completion rate while still open.
        elapsed_dates = scheduled_dates
        if elapsed_dates and elapsed_dates[-1] == today and today not in checkins:
            elapsed_dates = elapsed_dates[:-1]
        streak = 0
        for day in reversed(elapsed_dates):
            if day not in checkins:
                break
            streak += 1
        percentage = completed / len(elapsed_dates) * 100 if elapsed_dates else 0.0
        return RoutineStats(completed, len(elapsed_dates), percentage, streak)

    def routine_recent_occurrences(
        self, routine_id: int, limit: int = 12, as_of: str | None = None
    ) -> list[tuple[str, bool]]:
        routine = self.repo.get_routine(routine_id)
        if routine is None:
            return []
        today = as_of or time_utils.today_str()
        if today < routine.start_date:
            return []
        scheduled = self._scheduled_dates(routine, routine.start_date, today)[-limit:]
        checkins = self.repo.routine_checkins(routine_id, scheduled[0], today) if scheduled else set()
        return [(day, day in checkins) for day in reversed(scheduled)]

    def routine_heatmap(self, routine_id: int, year: int, as_of: str | None = None) -> dict[str, str]:
        routine = self.repo.get_routine(routine_id)
        if routine is None:
            return {}
        today = as_of or time_utils.today_str()
        start = f"{year:04d}-01-01"
        end = f"{year:04d}-12-31"
        checkins = self.repo.routine_checkins(routine_id, start, end)
        states: dict[str, str] = {}
        cursor = start
        while cursor <= end:
            if cursor < routine.start_date or not self.is_routine_scheduled(routine, cursor):
                state = "unscheduled"
            elif cursor > today:
                state = "future"
            elif cursor in checkins:
                state = "completed"
            elif cursor == today:
                state = "pending"
            else:
                state = "missed"
            states[cursor] = state
            cursor = time_utils.add_days(cursor, 1)
        return states

    def routine_schedule_label(self, routine: GoalRoutine) -> str:
        initials = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        selected = [label for index, label in enumerate(initials) if routine.weekdays_mask & (1 << index)]
        if len(selected) == 7:
            return "Every day"
        if selected == initials[:5]:
            return "Weekdays"
        if selected == initials[5:]:
            return "Weekends"
        return ", ".join(selected)

    def _validate_routine(self, routine: GoalRoutine) -> tuple[bool, str]:
        title = (routine.title or "").strip()
        if not title:
            return False, "Routine name cannot be empty."
        if len(title) > 80:
            return False, "Routine name is too long (max 80 characters)."
        if not isinstance(routine.weekdays_mask, int) or not 1 <= routine.weekdays_mask <= 127:
            return False, "Choose at least one weekday."
        if not time_utils.is_valid_date(routine.start_date):
            return False, "Start date must be a real YYYY-MM-DD date."
        if routine.category_id is not None:
            category = self.categories.get(routine.category_id)
            if category is None or category.is_archived:
                return False, "Choose an active category or Personal."
        return True, ""

    def _scheduled_dates(self, routine: GoalRoutine, start_date: str, end_date: str) -> list[str]:
        result: list[str] = []
        cursor = max(start_date, routine.start_date)
        while cursor <= end_date:
            if self.is_routine_scheduled(routine, cursor):
                result.append(cursor)
            cursor = time_utils.add_days(cursor, 1)
        return result
