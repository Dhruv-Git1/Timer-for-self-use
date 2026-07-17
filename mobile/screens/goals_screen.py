"""The mobile Goals hub: tasks, permanent routines, and measured targets."""

from __future__ import annotations

from datetime import date, datetime, time

import flet as ft

from app.charts.chart_data import Series
from app.models.goal import (
    PERIOD_BIWEEKLY,
    PERIOD_CUSTOM,
    PERIOD_MONTHLY,
    PERIOD_TIMELESS,
    PERIOD_WEEKLY,
    Goal,
    GoalRoutine,
    GoalTask,
)
from app.utils import time_utils
from mobile import theme
from mobile.widgets import charts, heatmap
from mobile.widgets.fury import chip, fury_button, fury_progress
from mobile.widgets.sheets import dismiss_sheet, form_sheet, show_sheet


_FILTERS = ("All", "Tasks", "Routines", "Targets")
_WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_TARGET_SCHEDULES = (
    (PERIOD_WEEKLY, "Weekly"),
    (PERIOD_BIWEEKLY, "Biweekly"),
    (PERIOD_MONTHLY, "Monthly"),
    ("custom_range", "Custom range"),
    ("custom_interval", "Custom interval"),
    (PERIOD_TIMELESS, "No deadline"),
)
_REMINDER_PRESETS = (
    ("none", "No reminder"),
    ("0", "At deadline"),
    ("30", "30 minutes before"),
    ("60", "1 hour before"),
    ("120", "2 hours before"),
    ("180", "3 hours before"),
    ("360", "6 hours before"),
    ("720", "12 hours before"),
    ("1440", "1 day before"),
    ("custom", "Custom reminder"),
)


def _goal_schedule_key(goal: Goal) -> str:
    if goal.period == PERIOD_CUSTOM and goal.is_custom_interval:
        return "custom_interval"
    if goal.period == PERIOD_CUSTOM:
        return "custom_range"
    return goal.period


def _period_name(goal: Goal) -> str:
    if goal.is_custom_interval:
        return f"Every {goal.interval_count} {goal.interval_unit}"
    return dict(_TARGET_SCHEDULES).get(_goal_schedule_key(goal), goal.period.title())


def _value_label(value: int, tracking_mode: str, unit_label: str) -> str:
    return time_utils.fmt_duration(value) if tracking_mode == "timer" else f"{value} {unit_label}"


def _task_due_label(task: GoalTask, now: datetime | None = None) -> tuple[str, str]:
    if not task.due_at:
        return "No deadline", theme.MUTED_TEXT
    due = datetime.strptime(task.due_at, "%Y-%m-%d %H:%M")
    now = now or datetime.now()
    label = due.strftime("%d %b %Y · %I:%M %p").replace(" 0", " ")
    if not task.is_completed and due < now:
        return f"Overdue · {label}", theme.STOP_RED
    return label, theme.MUTED_TEXT


def build(page: ft.Page, ctx) -> ft.Control:
    """Build a stateful in-tab hub; detail views retain the bottom navigation."""
    root = ft.Container(expand=True)
    state = {"filter": "All", "completed_open": False, "year": date.today().year}

    def _update() -> None:
        try:
            page.update()
        except Exception:
            pass

    def _category_meta(category_id: int | None) -> tuple[str, str]:
        if category_id is None:
            return "Personal", theme.ACCENT
        category = ctx.category_service.get(category_id)
        if category is None:
            return "Personal", theme.ACCENT
        return category.name, category.color

    def _open_date_picker(field: ft.TextField, label: str) -> None:
        try:
            selected = time_utils.to_date(field.value or "")
        except ValueError:
            selected = date.today()

        def _picked(event) -> None:
            if event.control.value:
                value = event.control.value
                field.value = value.strftime("%Y-%m-%d")
                _update()

        page.show_dialog(
            ft.DatePicker(
                value=selected,
                first_date=date(1900, 1, 1),
                last_date=date(9999, 12, 31),
                help_text=label,
                on_change=_picked,
            )
        )

    def _open_time_picker(field: ft.TextField) -> None:
        parsed = time(17, 0)
        if time_utils.is_valid_time(field.value or ""):
            parsed = datetime.strptime(field.value or "", "%H:%M").time()

        def _picked(event) -> None:
            if event.control.value:
                field.value = event.control.value.strftime("%H:%M")
                _update()

        page.show_dialog(ft.TimePicker(value=parsed, help_text="Choose deadline time", on_change=_picked))

    def _date_row(field: ft.TextField, label: str) -> ft.Row:
        return ft.Row(
            controls=[
                field,
                ft.IconButton(
                    icon=ft.Icons.CALENDAR_MONTH,
                    icon_color=theme.ACCENT,
                    tooltip=label,
                    on_click=lambda e: _open_date_picker(field, label),
                ),
            ]
        )

    def _section_header(title: str, subtitle: str, on_add=None) -> ft.Control:
        controls: list[ft.Control] = [
            ft.Column(
                expand=True,
                spacing=1,
                controls=[
                    theme.section_label(title),
                    ft.Text(subtitle, size=10, color=theme.MUTED_TEXT),
                ],
            )
        ]
        if on_add:
            controls.append(ft.TextButton("Add", icon=ft.Icons.ADD, on_click=on_add))
        return ft.Row(controls=controls)

    def _empty(message: str, action: str, on_click) -> ft.Control:
        return theme.card(
            ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=7,
                controls=[
                    ft.Text(message, size=12, color=theme.MUTED_TEXT, text_align=ft.TextAlign.CENTER),
                    ft.TextButton(action, icon=ft.Icons.ADD, on_click=on_click),
                ],
            ),
            padding=18,
            radius=12,
        )

    # ------------------------------------------------------------------
    # One-off task editor and cards
    # ------------------------------------------------------------------
    def _open_task_editor(task: GoalTask | None = None) -> None:
        title_field = ft.TextField(label="Task", value=task.title if task else "", autofocus=True)
        due_date = task.due_at[:10] if task and task.due_at else ""
        due_time = task.due_at[11:16] if task and task.due_at else ""
        date_field = ft.TextField(label="Deadline date (YYYY-MM-DD)", value=due_date, expand=True)
        time_field = ft.TextField(label="Time (HH:MM)", value=due_time, width=150)

        preset_values = {int(key) for key, _label in _REMINDER_PRESETS if key.isdigit()}
        existing_offset = task.reminder_offset_minutes if task else None
        reminder_key = (
            "none" if existing_offset is None
            else str(existing_offset) if existing_offset in preset_values
            else "custom"
        )
        custom_number = ""
        custom_unit = "minutes"
        if existing_offset is not None and reminder_key == "custom":
            if existing_offset % 1440 == 0:
                custom_number, custom_unit = str(existing_offset // 1440), "days"
            elif existing_offset % 60 == 0:
                custom_number, custom_unit = str(existing_offset // 60), "hours"
            else:
                custom_number = str(existing_offset)
        reminder_field = ft.Dropdown(
            label="Notify me",
            value=reminder_key,
            options=[ft.DropdownOption(key=key, text=label) for key, label in _REMINDER_PRESETS],
        )
        custom_field = ft.TextField(
            label="Amount before",
            value=custom_number,
            keyboard_type=ft.KeyboardType.NUMBER,
            visible=reminder_key == "custom",
            expand=True,
        )
        custom_unit_field = ft.Dropdown(
            label="Unit",
            value=custom_unit,
            options=[ft.DropdownOption(key=value, text=value.title()) for value in ("minutes", "hours", "days")],
            visible=reminder_key == "custom",
            width=140,
        )
        error_text = ft.Text("", size=12, color=theme.STOP_RED)
        sheet_result = {"changed": False}

        def _refresh_reminder(_event=None) -> None:
            custom = reminder_field.value == "custom"
            custom_field.visible = custom
            custom_unit_field.visible = custom
            _update()

        reminder_field.on_select = _refresh_reminder

        def _close(_event=None) -> None:
            dismiss_sheet(page, sheet)

        def _after_sheet(_event=None) -> None:
            if sheet_result["changed"]:
                _show_main()

        def _save(_event=None) -> None:
            date_text = (date_field.value or "").strip()
            time_text = (time_field.value or "").strip()
            if bool(date_text) != bool(time_text):
                error_text.value = "Choose both a deadline date and time, or leave both empty."
                _update()
                return
            due_at = None
            if date_text:
                if not time_utils.is_valid_date(date_text) or not time_utils.is_valid_time(time_text):
                    error_text.value = "Enter a real date and HH:MM time."
                    _update()
                    return
                due_at = f"{date_text} {time_utils.normalize_time(time_text)}"

            reminder_value = reminder_field.value or "none"
            offset: int | None
            if reminder_value == "none":
                offset = None
            elif reminder_value == "custom":
                amount = (custom_field.value or "").strip()
                if not amount.isdigit():
                    error_text.value = "Custom reminder must be a whole number."
                    _update()
                    return
                multiplier = {"minutes": 1, "hours": 60, "days": 1440}[custom_unit_field.value or "minutes"]
                offset = int(amount) * multiplier
            else:
                offset = int(reminder_value)

            if task is None:
                ok, message, _task_id = ctx.goal_service.create_task(
                    title_field.value or "", due_at, offset
                )
            else:
                task.title = title_field.value or ""
                task.due_at = due_at
                task.reminder_offset_minutes = offset
                ok, message, _task_id = ctx.goal_service.update_task(task)
            if not ok:
                error_text.value = message
                _update()
                return
            if offset is not None:
                bridge = getattr(page, "_timetracker_android_bridge", None)
                if bridge is not None:
                    page.run_task(bridge.request_permissions)
            sheet_result["changed"] = True
            _close()

        def _confirm_delete(_event=None) -> None:
            if task is None:
                return
            deleted = {"value": False}
            confirmation_error = ft.Text("", size=12, color=theme.STOP_RED)

            def _delete(_event=None) -> None:
                try:
                    ok, message, _ = ctx.goal_service.delete_task(task.id)
                except Exception:  # keep both modal layers recoverable on service failure
                    ok, message = False, "Couldn't delete this task. Please try again."
                if not ok:
                    error_text.value = message
                    confirmation_error.value = message
                    _update()
                    return
                deleted["value"] = True
                sheet_result["changed"] = True
                page.pop_dialog()

            def _after_confirm(_event=None) -> None:
                if deleted["value"]:
                    _close()

            page.show_dialog(
                ft.AlertDialog(
                    modal=True,
                    title=ft.Text("Delete task?"),
                    content=ft.Column(
                        tight=True,
                        controls=[
                            ft.Text(f'Delete "{task.title}" and its completion record?'),
                            confirmation_error,
                        ],
                    ),
                    on_dismiss=_after_confirm,
                    actions=[
                        ft.TextButton("Cancel", on_click=lambda e: page.pop_dialog()),
                        ft.TextButton("Delete", on_click=_delete),
                    ],
                )
            )

        sheet = form_sheet(
            "Edit task" if task else "New task",
            ft.Column(
                spacing=10,
                scroll=ft.ScrollMode.AUTO,
                controls=[
                    ft.Text("A one-off checkbox. It does not need a category.", size=12, color=theme.MUTED_TEXT),
                    title_field,
                    _date_row(date_field, "Choose deadline date"),
                    ft.Row(
                        controls=[
                            time_field,
                            ft.IconButton(
                                icon=ft.Icons.SCHEDULE,
                                icon_color=theme.ACCENT,
                                tooltip="Choose deadline time",
                                on_click=lambda e: _open_time_picker(time_field),
                            ),
                        ]
                    ),
                    reminder_field,
                    ft.Row(controls=[custom_field, custom_unit_field]),
                    error_text,
                ],
            ),
            [ft.TextButton("Cancel", on_click=_close), fury_button("Save task", _save)],
            _close,
            body_height=390,
            leading_actions=[ft.TextButton("Delete", on_click=_confirm_delete)] if task else [],
            on_dismiss=_after_sheet,
        )
        show_sheet(page, sheet)

    def _task_card(task: GoalTask) -> ft.Control:
        due_label, due_color = _task_due_label(task)

        def _toggle(event) -> None:
            ctx.goal_service.set_task_completed(task.id, bool(event.control.value))
            _show_main()

        return ft.Container(
            padding=ft.Padding.symmetric(vertical=8, horizontal=10),
            border_radius=12,
            bgcolor=theme.CARD,
            border=ft.Border.all(1, theme.CARD_BORDER),
            content=ft.Row(
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Checkbox(
                        value=task.is_completed,
                        active_color=theme.STATUS_COMPLETE,
                        semantics_label=f"{task.title}, {'completed' if task.is_completed else 'not completed'}",
                        on_change=_toggle,
                    ),
                    ft.Column(
                        expand=True,
                        spacing=2,
                        controls=[
                            ft.Text(
                                task.title,
                                size=14,
                                color=theme.MUTED_TEXT if task.is_completed else theme.HEADLINE,
                                style=ft.TextStyle(
                                    decoration=ft.TextDecoration.LINE_THROUGH if task.is_completed else None
                                ),
                            ),
                            ft.Text(due_label, size=10, color=due_color),
                        ],
                    ),
                    ft.IconButton(
                        icon=ft.Icons.EDIT_OUTLINED,
                        icon_color=theme.MUTED_TEXT,
                        tooltip="Edit task",
                        on_click=lambda e: _open_task_editor(task),
                    ),
                ],
            ),
        )

    # ------------------------------------------------------------------
    # Permanent routine editor, cards, and detail
    # ------------------------------------------------------------------
    def _open_routine_editor(routine: GoalRoutine | None = None) -> None:
        categories = ctx.category_service.list_categories()
        title_field = ft.TextField(label="Routine name", value=routine.title if routine else "")
        category_value = str(routine.category_id) if routine and routine.category_id else "personal"
        category_field = ft.Dropdown(
            label="Group (optional)",
            value=category_value,
            options=[ft.DropdownOption(key="personal", text="Personal")]
            + [ft.DropdownOption(key=str(item.id), text=item.name) for item in categories],
        )
        weekday_checks = [
            ft.Checkbox(
                label=label,
                value=bool(routine.weekdays_mask & (1 << index)) if routine else index < 5,
                active_color=theme.ACCENT,
            )
            for index, label in enumerate(_WEEKDAYS)
        ]
        start_field = ft.TextField(
            label="Start date (YYYY-MM-DD)",
            value=routine.start_date if routine else time_utils.today_str(),
            expand=True,
        )
        error_text = ft.Text("", size=12, color=theme.STOP_RED)
        sheet_result = {"changed": False}

        def _close(_event=None) -> None:
            dismiss_sheet(page, sheet)

        def _after_sheet(_event=None) -> None:
            if sheet_result["changed"]:
                _show_main()

        def _save(_event=None) -> None:
            mask = sum(1 << index for index, control in enumerate(weekday_checks) if control.value)
            selected = category_field.value or "personal"
            category_id = None if selected == "personal" else int(selected)
            if routine is None:
                ok, message, _ = ctx.goal_service.create_routine(
                    title_field.value or "", category_id, mask, start_field.value or ""
                )
            else:
                routine.title = title_field.value or ""
                routine.category_id = category_id
                routine.weekdays_mask = mask
                routine.start_date = start_field.value or ""
                ok, message, _ = ctx.goal_service.update_routine(routine)
            if not ok:
                error_text.value = message
                _update()
                return
            sheet_result["changed"] = True
            _close()

        def _confirm_delete(_event=None) -> None:
            if routine is None:
                return
            deleted = {"value": False}
            confirmation_error = ft.Text("", size=12, color=theme.STOP_RED)

            def _delete(_event=None) -> None:
                try:
                    ok, message, _ = ctx.goal_service.delete_routine(routine.id)
                except Exception:  # keep both modal layers recoverable on service failure
                    ok, message = False, "Couldn't delete this routine. Please try again."
                if not ok:
                    error_text.value = message
                    confirmation_error.value = message
                    _update()
                    return
                deleted["value"] = True
                sheet_result["changed"] = True
                page.pop_dialog()

            page.show_dialog(
                ft.AlertDialog(
                    modal=True,
                    title=ft.Text("Delete routine?"),
                    content=ft.Column(
                        tight=True,
                        controls=[
                            ft.Text("Its independent checkbox history will also be deleted."),
                            confirmation_error,
                        ],
                    ),
                    on_dismiss=lambda e: _close() if deleted["value"] else None,
                    actions=[
                        ft.TextButton("Cancel", on_click=lambda e: page.pop_dialog()),
                        ft.TextButton("Delete", on_click=_delete),
                    ],
                )
            )

        sheet = form_sheet(
            "Edit routine" if routine else "New routine",
            ft.Column(
                spacing=10,
                scroll=ft.ScrollMode.AUTO,
                controls=[
                    ft.Text(
                        "A permanent checkbox with its own history. Category time never checks it off.",
                        size=12,
                        color=theme.MUTED_TEXT,
                    ),
                    title_field,
                    category_field,
                    ft.Text("Scheduled days", size=12, color=theme.MUTED_TEXT),
                    ft.Row(wrap=True, spacing=3, controls=weekday_checks),
                    _date_row(start_field, "Choose routine start date"),
                    error_text,
                ],
            ),
            [ft.TextButton("Cancel", on_click=_close), fury_button("Save routine", _save)],
            _close,
            body_height=350,
            leading_actions=[ft.TextButton("Delete", on_click=_confirm_delete)] if routine else [],
            on_dismiss=_after_sheet,
        )
        show_sheet(page, sheet)

    def _routine_card(routine: GoalRoutine) -> ft.Control:
        category_name, color = _category_meta(routine.category_id)
        today = time_utils.today_str()
        scheduled = ctx.goal_service.is_routine_scheduled(routine, today)
        completed = scheduled and ctx.goal_service.routine_is_complete(routine.id, today)
        stats = ctx.goal_service.routine_stats(routine.id)

        def _toggle(event) -> None:
            ctx.goal_service.set_routine_completed(routine.id, today, bool(event.control.value))
            _show_main()

        occurrence_control: ft.Control = (
            ft.Checkbox(
                value=completed,
                active_color=color,
                tooltip="Scheduled today",
                semantics_label=f"{routine.title}, scheduled today",
                on_change=_toggle,
            )
            if scheduled
            else ft.Icon(
                ft.Icons.EVENT_AVAILABLE,
                size=22,
                color=theme.MONO_LABEL,
                tooltip="No occurrence scheduled today",
            )
        )
        return ft.Container(
            padding=12,
            border_radius=12,
            bgcolor=theme.CARD,
            border=ft.Border.all(1, theme.CARD_BORDER),
            content=ft.Column(
                spacing=7,
                controls=[
                    ft.Row(
                        controls=[
                            occurrence_control,
                            ft.Column(
                                expand=True,
                                spacing=1,
                                controls=[
                                    ft.Text(routine.title, size=14, color=theme.HEADLINE, weight=ft.FontWeight.BOLD),
                                    ft.Text(
                                        f"{category_name} · {ctx.goal_service.routine_schedule_label(routine)}",
                                        size=10,
                                        color=theme.MUTED_TEXT,
                                    ),
                                ],
                            ),
                            ft.IconButton(
                                icon=ft.Icons.EDIT_OUTLINED,
                                icon_color=theme.MUTED_TEXT,
                                tooltip="Edit routine",
                                on_click=lambda e: _open_routine_editor(routine),
                            ),
                            ft.IconButton(
                                icon=ft.Icons.INSIGHTS,
                                icon_color=color,
                                tooltip="Routine progress",
                                on_click=lambda e: _show_routine_detail(routine.id),
                            ),
                        ]
                    ),
                    ft.Text(
                        f"{(stats.completion_pct if stats else 0):.0f}% completion · "
                        f"{(stats.current_streak if stats else 0)} scheduled streak",
                        size=10,
                        color=color,
                    ),
                ],
            ),
        )

    def _show_routine_detail(routine_id: int, update_page: bool = True) -> None:
        routine = ctx.goal_service.get_routine(routine_id)
        if routine is None:
            _show_main(update_page)
            return
        category_name, color = _category_meta(routine.category_id)
        stats = ctx.goal_service.routine_stats(routine.id)
        year = state["year"]
        states = ctx.goal_service.routine_heatmap(routine.id, year)
        recent = ctx.goal_service.routine_recent_occurrences(routine.id)
        correction_field = ft.TextField(
            label="Past scheduled date (YYYY-MM-DD)",
            value=time_utils.today_str(),
            expand=True,
        )
        correction_error = ft.Text("", size=11, color=theme.STOP_RED)

        def _change_year(delta: int) -> None:
            state["year"] += delta
            _show_routine_detail(routine_id)

        def _toggle_date(day: str, value: bool) -> None:
            ctx.goal_service.set_routine_completed(routine.id, day, value)
            _show_routine_detail(routine_id)

        def _correct_date(completed: bool) -> None:
            ok, message, _ = ctx.goal_service.set_routine_completed(
                routine.id,
                (correction_field.value or "").strip(),
                completed,
            )
            if not ok:
                correction_error.value = message
                _update()
                return
            _show_routine_detail(routine_id)

        recent_controls: list[ft.Control] = []
        for day, completed in recent:
            recent_controls.append(
                ft.Container(
                    height=48,
                    padding=ft.Padding.symmetric(horizontal=8),
                    border_radius=8,
                    bgcolor=theme.CARD,
                    content=ft.Row(
                        controls=[
                            ft.Checkbox(
                                value=completed,
                                active_color=color,
                                semantics_label=f"{routine.title} on {day}",
                                on_change=lambda e, d=day: _toggle_date(d, bool(e.control.value)),
                            ),
                            ft.Text(
                                f"{time_utils.weekday_name(day)} · {time_utils.fmt_short_date(day)}",
                                size=12,
                                color=theme.HEADLINE,
                            ),
                        ]
                    ),
                )
            )

        def _stat(label: str, value: str) -> ft.Control:
            return theme.card(
                ft.Column(
                    spacing=1,
                    controls=[
                        ft.Text(value, size=20, color=color, weight=ft.FontWeight.BOLD),
                        ft.Text(label, size=9, color=theme.MUTED_TEXT),
                    ],
                ),
                padding=10,
                radius=10,
            )

        root.content = ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            spacing=12,
            controls=[
                ft.Row(
                    controls=[
                        ft.IconButton(icon=ft.Icons.ARROW_BACK, tooltip="Back to goals", on_click=lambda e: _show_main()),
                        ft.Column(
                            expand=True,
                            spacing=1,
                            controls=[theme.display(routine.title, size=24), ft.Text(category_name, size=11, color=color)],
                        ),
                        ft.IconButton(
                            icon=ft.Icons.EDIT_OUTLINED,
                            tooltip="Edit routine",
                            on_click=lambda e: _open_routine_editor(routine),
                        ),
                    ]
                ),
                ft.Text(ctx.goal_service.routine_schedule_label(routine), size=12, color=theme.MUTED_TEXT),
                ft.Row(
                    controls=[
                        _stat("Completion", f"{(stats.completion_pct if stats else 0):.0f}%"),
                        _stat("Streak", str(stats.current_streak if stats else 0)),
                        _stat("Done", str(stats.completed if stats else 0)),
                    ]
                ),
                ft.Row(
                    alignment=ft.MainAxisAlignment.CENTER,
                    controls=[
                        ft.IconButton(icon=ft.Icons.CHEVRON_LEFT, width=48, height=48, on_click=lambda e: _change_year(-1)),
                        ft.Text(str(year), size=15, color=theme.HEADLINE, weight=ft.FontWeight.BOLD),
                        ft.IconButton(icon=ft.Icons.CHEVRON_RIGHT, width=48, height=48, on_click=lambda e: _change_year(1)),
                    ],
                ),
                theme.card(heatmap.build_states(states, year, color), padding=12, radius=12),
                theme.section_label("Correct an occurrence"),
                _date_row(correction_field, "Choose a past scheduled date"),
                correction_error,
                ft.Row(
                    controls=[
                        ft.TextButton(
                            "Clear",
                            icon=ft.Icons.CHECK_BOX_OUTLINE_BLANK,
                            on_click=lambda e: _correct_date(False),
                        ),
                        ft.TextButton(
                            "Mark complete",
                            icon=ft.Icons.CHECK_BOX,
                            on_click=lambda e: _correct_date(True),
                        ),
                    ]
                ),
                theme.section_label("Recent scheduled days"),
                ft.Text("Correct any past checkbox here.", size=10, color=theme.MUTED_TEXT),
                *recent_controls,
            ],
        )
        if update_page:
            _update()

    # ------------------------------------------------------------------
    # Measured target editor, cards, and detail
    # ------------------------------------------------------------------
    def _open_target_editor(goal: Goal | None = None) -> None:
        categories = ctx.category_service.list_categories()
        if not categories:
            page.show_dialog(
                ft.AlertDialog(
                    title=ft.Text("Create a category first"),
                    content=ft.Text("Targets measure one category. Add a category, then return here."),
                    actions=[ft.TextButton("Close", on_click=lambda e: page.pop_dialog())],
                )
            )
            return
        ids = {item.id for item in categories}
        selected_id = goal.category_id if goal and goal.category_id in ids else categories[0].id
        title_field = ft.TextField(label="Target name", value=goal.title if goal else "")
        category_field = ft.Dropdown(
            label="Measure progress from",
            value=str(selected_id),
            options=[ft.DropdownOption(key=str(item.id), text=item.name) for item in categories],
        )
        selected_category = next(item for item in categories if item.id == selected_id)
        goal_minutes = goal.target_value if goal and selected_category.is_timer else 0
        hours, minutes = divmod(goal_minutes, 60)
        hours_field = ft.TextField(label="Hours", value=str(hours) if goal and selected_category.is_timer else "", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
        minutes_field = ft.TextField(label="Minutes", value=str(minutes) if goal and selected_category.is_timer else "0", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
        count_field = ft.TextField(
            label="Target amount",
            value=str(goal.target_value) if goal and not selected_category.is_timer else "",
            keyboard_type=ft.KeyboardType.NUMBER,
        )
        schedule_field = ft.Dropdown(
            label="Schedule",
            value=_goal_schedule_key(goal) if goal else PERIOD_WEEKLY,
            options=[ft.DropdownOption(key=key, text=label) for key, label in _TARGET_SCHEDULES],
        )
        start_field = ft.TextField(label="Start date (YYYY-MM-DD)", value=goal.start_date if goal else time_utils.today_str(), expand=True)
        end_field = ft.TextField(label="End date (YYYY-MM-DD)", value=(goal.end_date or "") if goal else "", expand=True)
        interval_field = ft.TextField(
            label="Repeat every",
            value=str(goal.interval_count) if goal and goal.interval_count else "",
            keyboard_type=ft.KeyboardType.NUMBER,
            expand=True,
        )
        interval_unit_field = ft.Dropdown(
            label="Unit",
            value=goal.interval_unit if goal and goal.interval_unit else "days",
            options=[ft.DropdownOption(key=value, text=value.title()) for value in ("days", "weeks", "months")],
            width=150,
        )
        schedule_help = ft.Text("", size=11, color=theme.MUTED_TEXT)
        target_help = ft.Text("", size=11, color=theme.MUTED_TEXT)
        error_text = ft.Text("", size=12, color=theme.STOP_RED)
        sheet_result = {"changed": False}

        def _selected_category():
            try:
                category_id = int(category_field.value or "")
            except ValueError:
                return None
            return next((item for item in categories if item.id == category_id), None)

        def _refresh_fields(_event=None) -> None:
            selected = _selected_category()
            timer_mode = bool(selected and selected.is_timer)
            hours_field.visible = timer_mode
            minutes_field.visible = timer_mode
            count_field.visible = not timer_mode
            target_help.value = (
                f"Tracked as hours and minutes from {selected.name}."
                if timer_mode and selected else
                f"Tracked as {selected.unit_label} from {selected.name}." if selected else ""
            )
            schedule = schedule_field.value or PERIOD_WEEKLY
            end_field.visible = schedule == "custom_range"
            interval_field.visible = schedule == "custom_interval"
            interval_unit_field.visible = schedule == "custom_interval"
            schedule_help.value = {
                PERIOD_WEEKLY: "Calendar week, Monday through Sunday.",
                PERIOD_BIWEEKLY: "Repeating 14-day blocks from the start date.",
                PERIOD_MONTHLY: "Resets on the first of each calendar month.",
                "custom_range": "One target between a start and end date.",
                "custom_interval": "Your own repeating number of days, weeks, or months.",
                PERIOD_TIMELESS: "Accumulates until the target is reached.",
            }[schedule]
            _update()

        category_field.on_select = _refresh_fields
        schedule_field.on_select = _refresh_fields

        def _close(_event=None) -> None:
            dismiss_sheet(page, sheet)

        def _after_sheet(_event=None) -> None:
            if sheet_result["changed"]:
                _show_main()

        def _save(_event=None) -> None:
            selected = _selected_category()
            if selected is None:
                error_text.value = "Choose a category."
                _update()
                return
            if selected.is_timer:
                hour_text = (hours_field.value or "0").strip()
                minute_text = (minutes_field.value or "0").strip()
                if not hour_text.isdigit() or not minute_text.isdigit() or int(minute_text) > 59:
                    error_text.value = "Hours and minutes must be valid whole numbers."
                    _update()
                    return
                target_value = int(hour_text) * 60 + int(minute_text)
            else:
                count_text = (count_field.value or "").strip()
                if not count_text.isdigit():
                    error_text.value = "Target amount must be a whole number."
                    _update()
                    return
                target_value = int(count_text)

            schedule = schedule_field.value or PERIOD_WEEKLY
            period = PERIOD_CUSTOM if schedule in {"custom_range", "custom_interval"} else schedule
            end_date = (end_field.value or "").strip() or None if schedule == "custom_range" else None
            interval_count = None
            interval_unit = None
            if schedule == "custom_interval":
                interval_text = (interval_field.value or "").strip()
                if not interval_text.isdigit():
                    error_text.value = "Custom interval must be a whole number."
                    _update()
                    return
                interval_count = int(interval_text)
                interval_unit = interval_unit_field.value or "days"

            if goal is None:
                ok, message, _ = ctx.goal_service.create(
                    title_field.value or "", selected.id, target_value, period,
                    start_field.value or "", end_date, interval_count, interval_unit,
                )
            else:
                goal.title = title_field.value or ""
                goal.category_id = selected.id
                goal.target_value = target_value
                goal.period = period
                goal.start_date = start_field.value or ""
                goal.end_date = end_date
                goal.interval_count = interval_count
                goal.interval_unit = interval_unit
                ok, message, _ = ctx.goal_service.update(goal)
            if not ok:
                error_text.value = message
                _update()
                return
            sheet_result["changed"] = True
            _close()

        def _confirm_delete(_event=None) -> None:
            if goal is None:
                return
            deleted = {"value": False}
            confirmation_error = ft.Text("", size=12, color=theme.STOP_RED)

            def _delete(_event=None) -> None:
                try:
                    ok, message, _ = ctx.goal_service.delete(goal.id)
                except Exception:  # keep both modal layers recoverable on service failure
                    ok, message = False, "Couldn't delete this target. Please try again."
                if not ok:
                    error_text.value = message
                    confirmation_error.value = message
                    _update()
                    return
                deleted["value"] = True
                sheet_result["changed"] = True
                page.pop_dialog()

            page.show_dialog(
                ft.AlertDialog(
                    modal=True,
                    title=ft.Text("Delete target?"),
                    content=ft.Column(
                        tight=True,
                        controls=[
                            ft.Text("Tracked category activity will remain intact."),
                            confirmation_error,
                        ],
                    ),
                    on_dismiss=lambda e: _close() if deleted["value"] else None,
                    actions=[
                        ft.TextButton("Cancel", on_click=lambda e: page.pop_dialog()),
                        ft.TextButton("Delete", on_click=_delete),
                    ],
                )
            )

        target_row = ft.Row(controls=[hours_field, minutes_field])
        interval_row = ft.Row(controls=[interval_field, interval_unit_field])
        _refresh_fields()
        sheet = form_sheet(
            "Edit target" if goal else "New target",
            ft.Column(
                spacing=10,
                scroll=ft.ScrollMode.AUTO,
                controls=[
                    ft.Text("Targets update automatically from category activity.", size=12, color=theme.MUTED_TEXT),
                    title_field,
                    category_field,
                    target_row,
                    count_field,
                    target_help,
                    schedule_field,
                    schedule_help,
                    _date_row(start_field, "Choose target start date"),
                    _date_row(end_field, "Choose target end date"),
                    interval_row,
                    error_text,
                ],
            ),
            [ft.TextButton("Cancel", on_click=_close), fury_button("Save target", _save)],
            _close,
            body_height=440,
            leading_actions=[ft.TextButton("Delete", on_click=_confirm_delete)] if goal else [],
            on_dismiss=_after_sheet,
        )
        show_sheet(page, sheet)

    def _target_card(progress) -> ft.Control:
        target = _value_label(progress.goal.target_value, progress.tracking_mode, progress.unit_label)
        actual = _value_label(progress.actual, progress.tracking_mode, progress.unit_label)
        ratio = min(1.0, progress.completion_pct / 100)
        return ft.Container(
            padding=14,
            border_radius=12,
            bgcolor=theme.CARD,
            border=ft.Border.all(1, theme.CARD_BORDER),
            content=ft.Column(
                spacing=7,
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.CIRCLE, size=11, color=progress.category_color),
                            ft.Text(progress.goal.title, size=15, color=theme.HEADLINE, expand=True, weight=ft.FontWeight.BOLD),
                            ft.Text(
                                "Complete" if progress.is_complete else f"{progress.completion_pct:.0f}%",
                                size=11,
                                color=theme.STATUS_COMPLETE if progress.is_complete else theme.ACCENT,
                            ),
                        ]
                    ),
                    ft.Row(
                        controls=[
                            ft.Text(progress.category_name, size=10, color=theme.MUTED_TEXT, expand=True),
                            ft.Text(_period_name(progress.goal), size=10, color=theme.MONO_LABEL),
                        ]
                    ),
                    fury_progress(ratio, progress.category_color, animate_in=False),
                    ft.Row(
                        controls=[
                            ft.Text(f"{actual} / {target}", size=12, color=theme.HEADLINE, expand=True),
                            ft.IconButton(
                                icon=ft.Icons.EDIT_OUTLINED,
                                icon_color=theme.MUTED_TEXT,
                                tooltip="Edit target",
                                on_click=lambda e: _open_target_editor(progress.goal),
                            ),
                            ft.IconButton(
                                icon=ft.Icons.INSIGHTS,
                                icon_color=progress.category_color,
                                tooltip="Target graph",
                                on_click=lambda e: _show_target_detail(progress.goal.id),
                            ),
                        ]
                    ),
                ],
            ),
        )

    def _show_target_detail(goal_id: int, update_page: bool = True) -> None:
        progress = ctx.goal_service.progress_for_goal(goal_id)
        history = ctx.goal_service.target_history(goal_id)
        if progress is None or history is None:
            _show_main(update_page)
            return
        goal = progress.goal
        actual = _value_label(progress.actual, progress.tracking_mode, progress.unit_label)
        target = _value_label(goal.target_value, progress.tracking_mode, progress.unit_label)
        chart = charts.line_chart(
            Series(labels=history.labels, values=history.actual_values),
            progress.category_color,
            height=220,
            extra_lines=[(history.target_values, theme.GOLD)],
        )
        root.content = ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            spacing=12,
            controls=[
                ft.Row(
                    controls=[
                        ft.IconButton(icon=ft.Icons.ARROW_BACK, tooltip="Back to goals", on_click=lambda e: _show_main()),
                        ft.Column(
                            expand=True,
                            spacing=1,
                            controls=[theme.display(goal.title, size=24), ft.Text(progress.category_name, size=11, color=progress.category_color)],
                        ),
                        ft.IconButton(icon=ft.Icons.EDIT_OUTLINED, tooltip="Edit target", on_click=lambda e: _open_target_editor(goal)),
                    ]
                ),
                theme.card(
                    ft.Column(
                        spacing=7,
                        controls=[
                            ft.Text(_period_name(goal), size=11, color=theme.MUTED_TEXT),
                            ft.Text(f"{actual} / {target}", size=22, color=theme.HEADLINE, weight=ft.FontWeight.BOLD),
                            fury_progress(min(1.0, progress.completion_pct / 100), progress.category_color, animate_in=False),
                            ft.Text(progress.window_label, size=10, color=theme.MUTED_TEXT),
                        ],
                    ),
                    padding=14,
                    radius=12,
                ),
                theme.section_label(f"This target · {history.unit_label}"),
                ft.Text("Actual progress", size=10, color=progress.category_color),
                ft.Text("Target line", size=10, color=theme.GOLD),
                theme.card(chart, padding=4, radius=12),
            ],
        )
        if update_page:
            _update()

    # ------------------------------------------------------------------
    # Hub composition and add-type picker
    # ------------------------------------------------------------------
    def _open_type_picker(_event=None) -> None:
        choice = {"value": None}

        def _choose(value: str) -> None:
            choice["value"] = value
            dismiss_sheet(page, sheet)

        def _after(_event=None) -> None:
            if choice["value"] == "task":
                _open_task_editor()
            elif choice["value"] == "routine":
                _open_routine_editor()
            elif choice["value"] == "target":
                _open_target_editor()

        def _option(icon, title, subtitle, value) -> ft.Control:
            return ft.Container(
                padding=14,
                border_radius=12,
                bgcolor=theme.NEUTRAL_BTN,
                ink=True,
                on_click=lambda e: _choose(value),
                content=ft.Row(
                    controls=[
                        ft.Icon(icon, color=theme.ACCENT),
                        ft.Column(
                            expand=True,
                            spacing=1,
                            controls=[
                                ft.Text(title, size=14, color=theme.HEADLINE, weight=ft.FontWeight.BOLD),
                                ft.Text(subtitle, size=10, color=theme.MUTED_TEXT),
                            ],
                        ),
                        ft.Icon(ft.Icons.CHEVRON_RIGHT, color=theme.MUTED_TEXT),
                    ]
                ),
            )

        sheet = form_sheet(
            "Add goal",
            ft.Column(
                spacing=8,
                controls=[
                    _option(ft.Icons.CHECK_BOX_OUTLINED, "Task", "One-off independent checkbox", "task"),
                    _option(ft.Icons.EVENT_REPEAT, "Routine", "Permanent scheduled checkbox + heatmap", "routine"),
                    _option(ft.Icons.TRACK_CHANGES, "Target", "Measured automatically from a category", "target"),
                ],
            ),
            [ft.TextButton("Cancel", on_click=lambda e: dismiss_sheet(page, sheet))],
            lambda e: dismiss_sheet(page, sheet),
            body_height=250,
            on_dismiss=_after,
        )
        show_sheet(page, sheet)

    def _show_main(update_page: bool = True) -> None:
        active_tasks = ctx.goal_service.list_tasks()
        old_completed = [
            item for item in ctx.goal_service.list_tasks(include_history=True)
            if item.completed_date != time_utils.today_str()
        ]
        routines = ctx.goal_service.list_routines()
        targets = ctx.goal_service.progress_for()
        pending_count = sum(not item.is_completed for item in active_tasks)
        total = pending_count + len(routines) + len(targets)

        def _select_filter(value: str) -> None:
            state["filter"] = value
            _show_main()

        controls: list[ft.Control] = [
            ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Column(
                        spacing=1,
                        controls=[
                            theme.display("Goals", size=28),
                            ft.Text(f"{total} active across tasks, routines, and targets", size=11, color=theme.MUTED_TEXT),
                        ],
                    ),
                    fury_button("Add", _open_type_picker, icon=ft.Icons.ADD),
                ],
            ),
            ft.Row(
                scroll=ft.ScrollMode.AUTO,
                spacing=6,
                controls=[
                    chip(label, state["filter"] == label, lambda e, value=label: _select_filter(value))
                    for label in _FILTERS
                ],
            ),
        ]

        if state["filter"] in {"All", "Tasks"}:
            controls.append(_section_header("Tasks", "Independent deadlines and checkboxes", lambda e: _open_task_editor()))
            if active_tasks:
                controls.extend(_task_card(item) for item in active_tasks)
            else:
                controls.append(_empty("No active one-off tasks.", "Add task", lambda e: _open_task_editor()))
            if state["filter"] == "Tasks" and old_completed:
                controls.append(
                    ft.TextButton(
                        f"{'Hide' if state['completed_open'] else 'Show'} Completed ({len(old_completed)})",
                        icon=ft.Icons.HISTORY,
                        on_click=lambda e: (
                            state.__setitem__("completed_open", not state["completed_open"]),
                            _show_main(),
                        ),
                    )
                )
                if state["completed_open"]:
                    controls.extend(_task_card(item) for item in old_completed)

        if state["filter"] in {"All", "Routines"}:
            controls.append(_section_header("Routines", "Permanent checkbox goals with their own heatmaps", lambda e: _open_routine_editor()))
            if routines:
                today = time_utils.today_str()
                ordered = sorted(
                    routines,
                    key=lambda item: (
                        _category_meta(item.category_id)[0].casefold(),
                        not ctx.goal_service.is_routine_scheduled(item, today),
                        item.id,
                    ),
                )
                previous_group = None
                for item in ordered:
                    group_name, group_color = _category_meta(item.category_id)
                    if group_name != previous_group:
                        controls.append(
                            ft.Text(
                                group_name.upper(),
                                size=10,
                                color=group_color,
                                weight=ft.FontWeight.BOLD,
                            )
                        )
                        previous_group = group_name
                    controls.append(_routine_card(item))
            else:
                controls.append(_empty("No permanent routines yet.", "Add routine", lambda e: _open_routine_editor()))

        if state["filter"] in {"All", "Targets"}:
            controls.append(_section_header("Targets", "Measured automatically from category activity", lambda e: _open_target_editor()))
            if targets:
                controls.extend(_target_card(item) for item in targets)
            else:
                controls.append(_empty("No measured targets yet.", "Add target", lambda e: _open_target_editor()))

        root.content = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO, spacing=10, controls=controls)
        page._timetracker_open_goal_task = lambda task_id: _open_task_editor(ctx.goal_service.get_task(task_id)) if ctx.goal_service.get_task(task_id) else None
        if update_page:
            _update()

    _show_main(update_page=False)
    return root
