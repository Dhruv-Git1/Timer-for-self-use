"""
Dashboard business logic.

Builds the :class:`DailySummary` for a single day — the productive vs recorded
totals, the per-category target-vs-actual table, the day's status, session
count, longest session, and the current streak. The UI just reads the finished
object; all the counting happens here.
"""

from __future__ import annotations

from typing import Dict, List

from app.database.repositories.category_repo import CategoryRepository
from app.database.repositories.entry_repo import EntryRepository
from app.models.category import Category
from app.models.stats import CategoryProgress, DailySummary
from app.services import aggregation
from app.services.streak_service import StreakService
from app.utils import time_utils


class DashboardService:
    """Assembles the numbers shown on the daily dashboard."""

    def __init__(
        self,
        category_repo: CategoryRepository,
        entry_repo: EntryRepository,
        streak_service: StreakService,
    ) -> None:
        self.categories = category_repo
        self.entries = entry_repo
        self.streaks = streak_service

    def _categories_by_id(self) -> Dict[int, Category]:
        """Every category (including archived) keyed by id.

        Archived categories are included because an old entry may still point at
        one, and we need its productive flag to total the day correctly.
        """
        return {c.id: c for c in self.categories.list_all(include_archived=True)}

    def build_summary(self, date_str: str) -> DailySummary:
        """Compute the full summary for ``date_str``."""
        cats_by_id = self._categories_by_id()
        active_categories = self.categories.list_all(include_archived=False)

        # Categories that carry a daily goal drive the day's status; productive
        # goal-carrying categories drive the "combined target" progress bar.
        targeted = [c for c in active_categories if c.daily_target_minutes > 0]
        total_target = sum(
            c.daily_target_minutes
            for c in active_categories
            if c.is_productive and c.daily_target_minutes > 0
        )

        # Fetch entries starting from the day before, so an overnight session
        # begun last night correctly contributes its early-morning minutes today.
        prev_day = time_utils.add_days(date_str, -1)
        span_entries = self.entries.list_by_date_range(prev_day, date_str)
        table = aggregation.build_day_category_minutes(span_entries, date_str, date_str)
        cat_minutes = table.get(date_str, {})

        productive, recorded = aggregation.productive_recorded(cat_minutes, cats_by_id)

        # Sessions and longest session are counted on the day they were logged.
        todays_entries = self.entries.list_by_date(date_str)
        session_count = len(todays_entries)
        longest = max((e.duration_minutes for e in todays_entries), default=0)

        # Status uses the shared classifier so calendar/streak/dashboard agree.
        bounds = self.entries.date_bounds()
        first_date = bounds[0] if bounds else None
        status = aggregation.classify_day(
            date_str, cat_minutes, targeted, first_date, time_utils.today_str()
        )

        # Build the target-vs-actual table: show every goal, plus any category
        # you actually spent time on today even if it has no goal.
        progress: List[CategoryProgress] = []
        for c in active_categories:
            actual = cat_minutes.get(c.id, 0)
            if c.daily_target_minutes > 0 or actual > 0:
                progress.append(
                    CategoryProgress(
                        category_id=c.id,
                        name=c.name,
                        color=c.color,
                        target_minutes=c.daily_target_minutes,
                        actual_minutes=actual,
                    )
                )

        return DailySummary(
            date=date_str,
            status=status,
            productive_minutes=productive,
            recorded_minutes=recorded,
            total_target_minutes=total_target,
            session_count=session_count,
            longest_session_minutes=longest,
            current_streak=self.streaks.current_streak(),
            progress=progress,
        )
