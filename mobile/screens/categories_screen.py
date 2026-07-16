"""Android category management shared by More and the Timer screen.

Categories can be timers, once-per-day check-offs, or whole-number counters.
The full screen under More and the modal manager opened from Timer intentionally
reuse the same controls so creating and editing behaves identically in both.
"""

from __future__ import annotations

from typing import Callable, Optional

import flet as ft

import config
from app.models.category import TRACKING_CHECKOFF, TRACKING_COUNTER, TRACKING_TIMER
from app.utils import validators
from mobile import theme
from mobile.widgets.fury import fury_button
from mobile.widgets.sheets import dismiss_sheet, form_sheet, show_sheet

ChangedCallback = Optional[Callable[[], None]]


def _mode_label(mode: str) -> str:
    return {
        TRACKING_TIMER: "Timer",
        TRACKING_CHECKOFF: "Check-off",
        TRACKING_COUNTER: "Counter",
    }.get(mode, "Timer")


def _mode_icon(mode: str) -> str:
    return {
        TRACKING_TIMER: ft.Icons.TIMER,
        TRACKING_CHECKOFF: ft.Icons.CHECK,
        TRACKING_COUNTER: ft.Icons.ADD,
    }.get(mode, ft.Icons.TIMER)


def _goal_label(category) -> str:
    if category.is_timer:
        return (
            f"{category.daily_target_minutes} min/day"
            if category.daily_target_minutes > 0 else "no daily goal"
        )
    if category.is_checkoff:
        return "once per day"
    return f"{category.daily_target_count} {category.unit_label}/day"


def build_manager(
    page: ft.Page,
    ctx,
    *,
    on_changed: ChangedCallback = None,
    include_title: bool = True,
) -> ft.Control:
    """Build the reusable category list and editor entry points."""
    list_column = ft.Column(spacing=8)

    def _changed() -> None:
        _refresh()
        if on_changed:
            on_changed()

    def _refresh() -> None:
        list_column.controls.clear()
        categories = ctx.category_service.list_categories(include_archived=True)
        if not categories:
            list_column.controls.append(
                ft.Text(
                    "No categories yet. Add a Timer, Check-off, or Counter category.",
                    size=12,
                    color=theme.MUTED_TEXT,
                )
            )
        for category in categories:
            name = category.name + ("  (archived)" if category.is_archived else "")
            score_text = (
                " • score"
                if category.has_target and category.include_in_daily_score else ""
            )
            list_column.controls.append(
                ft.Container(
                    padding=14,
                    border_radius=10,
                    bgcolor=theme.CARD,
                    border=ft.Border.all(1, theme.CARD_BORDER),
                    on_click=lambda e, c=category: _open_form(c),
                    content=ft.Row(
                        controls=[
                            ft.Icon(_mode_icon(category.tracking_mode), size=18, color=category.color),
                            ft.Column(
                                expand=True,
                                spacing=2,
                                controls=[
                                    ft.Text(name, size=14, color=theme.HEADLINE),
                                    ft.Text(
                                        f"{_mode_label(category.tracking_mode)} • "
                                        f"{_goal_label(category)}{score_text}",
                                        size=11,
                                        color=theme.MUTED_TEXT,
                                    ),
                                ],
                            ),
                            ft.Icon(ft.Icons.CHEVRON_RIGHT, size=18, color=theme.MONO_LABEL),
                        ]
                    ),
                )
            )
        page.update()

    def _open_form(category=None) -> None:
        current_mode = category.tracking_mode if category else TRACKING_TIMER
        active = ctx.timer_service.current_state()
        is_active_category = bool(
            category and active.is_active and active.category_id == category.id
        )
        mode_locked = bool(
            category
            and (is_active_category or ctx.category_service.has_history(category.id))
        )

        name_field = ft.TextField(label="Name", value=category.name if category else "")
        chosen_color = {"value": category.color if category else config.CHART_PALETTE[0]}
        swatch_row = ft.Row(wrap=True, spacing=6)

        def _pick_color(color: str) -> None:
            chosen_color["value"] = color
            for swatch in swatch_row.controls:
                swatch.border = ft.Border.all(3, "#FFFFFF") if swatch.data == color else None
            page.update()

        for color in config.CHART_PALETTE:
            swatch_row.controls.append(
                ft.Container(
                    data=color,
                    width=32,
                    height=32,
                    border_radius=16,
                    bgcolor=color,
                    border=(
                        ft.Border.all(3, "#FFFFFF")
                        if color == chosen_color["value"] else None
                    ),
                    on_click=lambda e, c=color: _pick_color(c),
                )
            )

        mode_dropdown = ft.Dropdown(
            label="Tracking mode",
            value=current_mode,
            disabled=mode_locked,
            options=[
                ft.DropdownOption(key=TRACKING_TIMER, text="Timer"),
                ft.DropdownOption(key=TRACKING_CHECKOFF, text="Check-off"),
                ft.DropdownOption(key=TRACKING_COUNTER, text="Counter"),
            ],
        )
        lock_text = ft.Text(
            (
                "Stop the running timer before changing its mode."
                if is_active_category
                else "Tracking mode is locked because this category has history."
            ),
            size=11,
            color=theme.MUTED_TEXT,
            visible=mode_locked,
        )
        productive_switch = ft.Switch(
            label="Counts as productive time",
            value=category.is_productive if category else True,
        )
        minute_goal_field = ft.TextField(
            label="Daily goal (minutes, 0 = none)",
            value=str(category.daily_target_minutes) if category else "0",
            keyboard_type=ft.KeyboardType.NUMBER,
        )
        count_goal_field = ft.TextField(
            label="Daily counter target",
            value=str(category.daily_target_count) if category else "1",
            keyboard_type=ft.KeyboardType.NUMBER,
        )
        unit_field = ft.TextField(
            label="Unit (glasses, pages, fruits…)",
            value=category.unit_label if category else "times",
        )
        score_switch = ft.Switch(
            label="Include in Today's score",
            value=category.include_in_daily_score if category else True,
        )
        mode_help = ft.Text("", size=11, color=theme.MUTED_TEXT)
        error_text = ft.Text("", color=theme.STOP_RED, size=12)

        def _refresh_mode(e=None) -> None:
            mode = mode_dropdown.value or TRACKING_TIMER
            productive_switch.visible = mode == TRACKING_TIMER
            minute_goal_field.visible = mode == TRACKING_TIMER
            count_goal_field.visible = mode == TRACKING_COUNTER
            unit_field.visible = mode == TRACKING_COUNTER
            mode_help.value = {
                TRACKING_TIMER: "Start and stop a clock; progress is measured in minutes.",
                TRACKING_CHECKOFF: "Complete this once each day with a checkbox.",
                TRACKING_COUNTER: "Record a whole-number amount throughout the day.",
            }[mode]
            page.update()

        mode_dropdown.on_select = _refresh_mode
        _refresh_mode()

        def _save(e=None) -> None:
            mode = mode_dropdown.value or TRACKING_TIMER
            target_minutes = 0
            target_count = 1
            unit_label = "times"

            if mode == TRACKING_TIMER:
                ok, msg = validators.validate_target_minutes(minute_goal_field.value)
                if not ok:
                    error_text.value = msg
                    page.update()
                    return
                target_minutes = int(minute_goal_field.value or 0)
            elif mode == TRACKING_COUNTER:
                ok, msg = validators.validate_target_count(count_goal_field.value)
                if not ok:
                    error_text.value = msg
                    page.update()
                    return
                ok, msg = validators.validate_unit_label(unit_field.value)
                if not ok:
                    error_text.value = msg
                    page.update()
                    return
                target_count = int(count_goal_field.value)
                unit_label = unit_field.value.strip()

            if category:
                category.name = name_field.value
                category.color = chosen_color["value"]
                category.tracking_mode = mode
                category.is_productive = (
                    bool(productive_switch.value) if mode == TRACKING_TIMER else False
                )
                category.daily_target_minutes = target_minutes
                category.daily_target_count = target_count
                category.unit_label = unit_label
                category.include_in_daily_score = bool(score_switch.value)
                ok, msg, _ = ctx.category_service.update(category)
            else:
                ok, msg, _ = ctx.category_service.create(
                    name_field.value,
                    chosen_color["value"],
                    bool(productive_switch.value),
                    target_minutes,
                    tracking_mode=mode,
                    target_count=target_count,
                    unit_label=unit_label,
                    include_in_daily_score=bool(score_switch.value),
                )
            if not ok:
                error_text.value = msg
                page.update()
                return
            dismiss_sheet(page, sheet)
            _changed()

        def _archive(e=None) -> None:
            if is_active_category:
                error_text.value = "Stop the running timer before archiving this category."
                page.update()
                return
            ctx.category_service.set_archived(category.id, not category.is_archived)
            dismiss_sheet(page, sheet)
            _changed()

        def _confirm_delete(e=None) -> None:
            if is_active_category:
                error_text.value = "Stop the running timer before deleting this category."
                page.update()
                return
            dismiss_sheet(page, sheet)

            def _do_delete(e2=None) -> None:
                ok, msg, _ = ctx.category_service.delete(category.id)
                page.pop_dialog()
                if ok:
                    _changed()
                else:
                    page.show_dialog(
                        ft.AlertDialog(
                            modal=True,
                            title=ft.Text("Can't delete"),
                            content=ft.Text(msg),
                            actions=[
                                ft.TextButton("OK", on_click=lambda e: page.pop_dialog())
                            ],
                        )
                    )

            page.show_dialog(
                ft.AlertDialog(
                    modal=True,
                    title=ft.Text("Delete category?"),
                    content=ft.Text(f'Delete "{category.name}"? This cannot be undone.'),
                    actions=[
                        ft.TextButton("Cancel", on_click=lambda e: page.pop_dialog()),
                        ft.TextButton("Delete", on_click=_do_delete),
                    ],
                )
            )

        actions = [
            ft.TextButton("Cancel", on_click=lambda e: dismiss_sheet(page, sheet)),
            fury_button("Save", kind="primary", on_click=_save),
        ]
        if category:
            actions.insert(
                0,
                ft.TextButton(
                    "Unarchive" if category.is_archived else "Archive",
                    on_click=_archive,
                ),
            )
            actions.insert(0, ft.TextButton("Delete", on_click=_confirm_delete))

        sheet = form_sheet(
            "Edit category" if category else "Add category",
            ft.Column(
                spacing=10,
                scroll=ft.ScrollMode.AUTO,
                controls=[
                    name_field,
                    ft.Text("Color", size=12, color=theme.MUTED_TEXT),
                    swatch_row,
                    mode_dropdown,
                    lock_text,
                    mode_help,
                    productive_switch,
                    minute_goal_field,
                    count_goal_field,
                    unit_field,
                    score_switch,
                    error_text,
                ],
            ),
            actions,
            lambda e: dismiss_sheet(page, sheet),
            body_height=280,
        )
        show_sheet(page, sheet)

    _refresh()

    header = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        controls=[
            theme.display("Categories", size=28) if include_title else theme.section_label("Categories"),
            ft.TextButton("Add category", icon=ft.Icons.ADD, on_click=lambda e: _open_form()),
        ],
    )
    return ft.Column(
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        spacing=12,
        controls=[header, list_column],
    )


def show_manager(page: ft.Page, ctx, on_changed: ChangedCallback = None) -> None:
    """Open category management over Timer without changing app navigation."""
    manager = build_manager(page, ctx, on_changed=on_changed, include_title=False)
    page.show_dialog(
        ft.AlertDialog(
            modal=True,
            title=ft.Text("Manage categories"),
            content=ft.Container(width=340, height=500, content=manager),
            actions=[ft.TextButton("Close", on_click=lambda e: page.pop_dialog())],
        )
    )


def build(page: ft.Page, ctx) -> ft.Control:
    return build_manager(page, ctx, include_title=True)
