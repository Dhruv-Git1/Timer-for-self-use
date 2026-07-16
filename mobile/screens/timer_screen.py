"""Android Timer plus daily Check-off/Counter tracking and Today score.

The existing stopwatch and time-goal behavior stays intact. Non-timer progress
is stored separately by date, and its equal-weight score is intentionally local
to this screen: Calendar, streaks, dashboards, statistics, and Insights continue
to use their existing time-only services.
"""

from __future__ import annotations

import asyncio
import math
import os
import time

import flet as ft
import flet_video as ftv

import config
from app.utils import time_utils, validators
from mobile import theme
from mobile.screens import categories_screen
from mobile.widgets.fury import fury_button, fury_progress
from mobile.widgets.hero import COMPACT_HEIGHT, hero_banner
from mobile.widgets.sheets import dismiss_sheet, form_sheet, show_sheet

_PULSE_PERIOD = 2.6
_TICK_INTERVAL = 0.2


def _pulse_shadow(color: str) -> ft.BoxShadow:
    phase = (time.time() % _PULSE_PERIOD) / _PULSE_PERIOD
    blur = 14 + 10 * (0.5 + 0.5 * math.sin(phase * 2 * math.pi))
    return theme.glow(color, blur=blur)


def _score_label(value: float) -> str:
    return f"{value:.1f}".rstrip("0").rstrip(".") + "%"


def build(page: ft.Page, ctx) -> ft.Control:
    state = ctx.timer_service.current_state()
    timer_categories = [
        category for category in ctx.category_service.list_categories() if category.is_timer
    ]
    selected = {
        "id": state.category_id if state.is_active
        else (timer_categories[0].id if timer_categories else None)
    }
    editing_goals = {"on": False}
    goal_inputs: dict[int, ft.TextField] = {}
    celebration_state = {"initialized": False, "was_complete": False}

    clock_text = ft.Text(
        "0:00:00",
        size=theme.TIMER_CLOCK_SIZE,
        weight=ft.FontWeight.BOLD,
        font_family=theme.MONO_FAMILY_SEMIBOLD,
        color=theme.HEADLINE,
        text_align=ft.TextAlign.CENTER,
    )
    subtitle_text = ft.Text(
        "", size=13, color=theme.MUTED_TEXT, text_align=ft.TextAlign.CENTER
    )
    controls_row = ft.Row(alignment=ft.MainAxisAlignment.CENTER, spacing=10)
    clock_card = ft.Container(
        padding=22,
        border_radius=16,
        bgcolor=theme.CARD,
        border=ft.Border.all(1, theme.CARD_BORDER),
        content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=6,
            controls=[clock_text, subtitle_text, controls_row],
        ),
    )

    score_value = theme.number("—", size=42, color=theme.ACCENT)
    score_subtitle = ft.Text("", size=11, color=theme.MUTED_TEXT)
    score_bar = fury_progress(0, color=theme.ACCENT, animate_in=False)
    score_card = theme.card(
        ft.Row(
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Column(
                    tight=True,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        score_value,
                        theme.section_label("Score"),
                    ],
                ),
                ft.Container(width=1, height=48, bgcolor=theme.CARD_BORDER),
                ft.Column(
                    expand=True,
                    spacing=5,
                    controls=[
                        theme.section_label("Today's mission"),
                        score_subtitle,
                        score_bar,
                    ],
                ),
            ],
        ),
        padding=14,
        radius=12,
    )

    goals_column = ft.Column(spacing=8)
    checkins_column = ft.Column(spacing=8)
    grid_column = ft.Column(spacing=8)
    goals_header = ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
    categories_header = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        controls=[
            theme.section_label("Timer categories"),
            ft.TextButton(
                "Manage categories",
                icon=ft.Icons.EDIT,
                on_click=lambda e: categories_screen.show_manager(
                    page, ctx, on_changed=_on_categories_changed
                ),
            ),
        ],
    )

    async def _tick_loop() -> None:
        last_shown_second = None
        while True:
            await asyncio.sleep(_TICK_INTERVAL)
            live = ctx.timer_service.current_state()
            if not live.is_active:
                break
            if live.elapsed_seconds != last_shown_second:
                clock_text.value = time_utils.fmt_clock(live.elapsed_seconds)
                last_shown_second = live.elapsed_seconds
            clock_card.shadow = _pulse_shadow(clock_text.color)
            page.update()

    def _start_ticking() -> None:
        page.run_task(_tick_loop)

    def _on_category_tap(category_id: int) -> None:
        live = ctx.timer_service.current_state()
        if live.is_active:
            if category_id != live.category_id:
                ctx.timer_service.start(category_id)
                _refresh_all()
                _start_ticking()
        else:
            selected["id"] = category_id
            _refresh_all()

    def _on_start(e=None) -> None:
        if selected["id"] is None:
            return
        ctx.timer_service.start(selected["id"])
        _refresh_all()
        _start_ticking()

    def _on_stop(e=None) -> None:
        ctx.timer_service.stop()
        _refresh_all()

    def _on_discard(e=None) -> None:
        ctx.timer_service.discard()
        _refresh_all()

    def _on_categories_changed() -> None:
        available = [
            category for category in ctx.category_service.list_categories() if category.is_timer
        ]
        available_ids = {category.id for category in available}
        if not ctx.timer_service.current_state().is_active and selected["id"] not in available_ids:
            selected["id"] = available[0].id if available else None
        _refresh_all()

    def _toggle_edit_goals(e=None) -> None:
        editing_goals["on"] = not editing_goals["on"]
        _refresh_all()

    def _save_goals(e=None) -> None:
        timer_cats = [
            category for category in ctx.category_service.list_categories() if category.is_timer
        ]
        parsed: dict[int, int] = {}
        for category in timer_cats:
            text = goal_inputs[category.id].value
            ok, _msg = validators.validate_target_minutes(text)
            if not ok:
                _refresh_all()
                return
            parsed[category.id] = int(text or 0)
        for category in timer_cats:
            if parsed[category.id] != category.daily_target_minutes:
                category.daily_target_minutes = parsed[category.id]
                ctx.category_service.update(category)
        editing_goals["on"] = False
        _refresh_all()

    def _refresh_goals() -> None:
        goals_column.controls.clear()
        goal_inputs.clear()
        goals_header.controls = [
            theme.section_label("Today's time goals"),
            ft.IconButton(
                icon=ft.Icons.CHECK if editing_goals["on"] else ft.Icons.EDIT,
                icon_color=theme.ACCENT,
                on_click=_save_goals if editing_goals["on"] else _toggle_edit_goals,
            ),
        ]

        timer_cats = [
            category for category in ctx.category_service.list_categories() if category.is_timer
        ]
        if editing_goals["on"]:
            for category in timer_cats:
                field = ft.TextField(
                    value=str(category.daily_target_minutes),
                    width=70,
                    height=42,
                    text_align=ft.TextAlign.CENTER,
                    dense=True,
                    keyboard_type=ft.KeyboardType.NUMBER,
                )
                goal_inputs[category.id] = field
                goals_column.controls.append(
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.CIRCLE, size=12, color=category.color),
                            ft.Text(category.name, size=13, color=theme.HEADLINE, expand=True),
                            field,
                            ft.Text("min/day", size=11, color=theme.MUTED_TEXT),
                        ]
                    )
                )
            if not timer_cats:
                goals_column.controls.append(
                    ft.Text("Add a Timer category first.", size=12, color=theme.MUTED_TEXT)
                )
            return

        summary = ctx.dashboard_service.build_summary(time_utils.today_str())
        goals = [progress for progress in summary.progress if progress.target_minutes > 0]
        if not goals:
            goals_column.controls.append(
                ft.Text(
                    "No time goals set yet — tap the pencil to add one.",
                    size=12,
                    color=theme.MUTED_TEXT,
                )
            )
        for progress in goals:
            goals_column.controls.append(
                ft.Column(
                    spacing=2,
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Text(progress.name, size=13, color=theme.HEADLINE, expand=True),
                                ft.Text(
                                    f"{progress.actual_label} / {progress.target_label}",
                                    size=12,
                                    color=theme.MUTED_TEXT,
                                ),
                            ]
                        ),
                        fury_progress(
                            progress.completion_pct / 100,
                            color=progress.color,
                            animate_in=False,
                        ),
                    ],
                )
            )

    def _toggle_checkoff(category_id: int) -> None:
        ctx.daily_progress_service.toggle(category_id, time_utils.today_str())
        _refresh_all()

    def _adjust_counter(category_id: int, delta: int) -> None:
        ctx.daily_progress_service.increment(category_id, time_utils.today_str(), delta)
        _refresh_all()

    def _open_amount_editor(category) -> None:
        today = time_utils.today_str()
        current = ctx.daily_progress_service.get(category.id, today)
        amount_field = ft.TextField(
            label=f"Amount ({category.unit_label})",
            value=str(current),
            keyboard_type=ft.KeyboardType.NUMBER,
            autofocus=True,
        )
        error_text = ft.Text("", size=12, color=theme.STOP_RED)

        def _save_amount(e=None) -> None:
            text = (amount_field.value or "").strip()
            if not text.isdigit():
                error_text.value = "Amount must be a non-negative whole number."
                page.update()
                return
            ctx.daily_progress_service.set_amount(category.id, today, int(text))
            dismiss_sheet(page, sheet)
            _refresh_all()

        def _cancel_amount(e=None) -> None:
            dismiss_sheet(page, sheet)

        sheet = form_sheet(
            f"Set {category.name}",
            ft.Column(spacing=10, controls=[amount_field, error_text]),
            [
                ft.TextButton("Cancel", on_click=_cancel_amount),
                fury_button("Save", kind="primary", on_click=_save_amount),
            ],
            _cancel_amount,
        )
        show_sheet(page, sheet)

    def _all_daily_goals_complete() -> bool:
        score = ctx.daily_progress_service.score(time_utils.today_str())
        return bool(score.items) and all(
            item.completion_pct >= 100 for item in score.items
        )

    def _show_goal_celebration() -> None:
        """Play the supplied celebration clip over the Timer screen once."""
        video = ftv.Video(
            expand=True,
            autoplay=True,
            controls=None,
                    # Fill the entire phone display; the source video is
                    # landscape, so its outer edges may be cropped on portrait
                    # devices rather than leaving letterbox bars.
                    fit=ft.BoxFit.COVER,
            playlist=[
                ftv.VideoMedia(
                    os.path.join(config.ASSETS_DIR, "goal-complete.mp4")
                )
            ],
        )

        async def _stop_and_dismiss() -> None:
            try:
                await video.stop()
            except Exception:  # noqa: BLE001 - the player may already be closed
                pass
            dismiss_sheet(page, sheet)

        def _dismiss(e=None) -> None:
            page.run_task(_stop_and_dismiss)

        video.on_complete = _dismiss
        sheet = ft.BottomSheet(
            bgcolor="#000000",
            dismissible=False,
            draggable=False,
            fullscreen=True,
            content=ft.Container(
                expand=True,
                bgcolor="#000000",
                content=ft.Stack(
                    fit=ft.StackFit.EXPAND,
                    controls=[
                        video,
                        ft.Container(
                            top=20,
                            right=16,
                            content=ft.IconButton(
                                icon=ft.Icons.CLOSE,
                                icon_color=theme.HEADLINE,
                                tooltip="Close celebration",
                                on_click=_dismiss,
                            ),
                        ),
                        ft.Container(
                            left=20,
                            right=20,
                            bottom=28,
                            padding=14,
                            border_radius=12,
                            bgcolor=ft.Colors.with_opacity(0.76, "#08080A"),
                            content=ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Column(
                                        tight=True,
                                        spacing=2,
                                        controls=[
                                            theme.section_label("Daily goal complete"),
                                            ft.Text(
                                                "You completed every goal for today.",
                                                size=12,
                                                color=theme.HEADLINE,
                                            ),
                                        ],
                                    ),
                                    fury_button(
                                        "Continue", kind="primary", on_click=_dismiss
                                    ),
                                ],
                            ),
                        ),
                    ],
                ),
            ),
        )
        show_sheet(page, sheet)

    def _maybe_show_goal_celebration() -> None:
        today = time_utils.today_str()
        is_complete = _all_daily_goals_complete()
        if not celebration_state["initialized"]:
            celebration_state["initialized"] = True
        elif (
            is_complete
            and not celebration_state["was_complete"]
            and ctx.get_setting("last_goal_celebration_date") != today
        ):
            ctx.set_setting("last_goal_celebration_date", today)
            _show_goal_celebration()
        celebration_state["was_complete"] = is_complete

    def _refresh_score_and_checkins() -> None:
        today = time_utils.today_str()
        score = ctx.daily_progress_service.score(today)
        if score.has_scored_categories:
            score_value.value = _score_label(score.average_pct)
            count = len(score.scored_items)
            total_weight = sum(item.weight for item in score.scored_items)
            score_subtitle.value = (
                f"{count} goal{'s' if count != 1 else ''} \u00b7 "
                f"{total_weight}\u00d7 total weight"
            )
            score_bar.value = score.average_pct / 100
            score_bar.data = score_bar.value
        else:
            score_value.value = "—"
            score_subtitle.value = "Include a goal category to calculate today's score."
            score_bar.value = 0
            score_bar.data = 0

        checkins_column.controls.clear()
        categories = [
            category for category in ctx.category_service.list_categories()
            if not category.is_timer
        ]
        if not categories:
            checkins_column.controls.append(
                theme.card(
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE, color=theme.FLAME, size=22),
                            ft.Column(
                                expand=True,
                                spacing=2,
                                controls=[
                                    ft.Text("Add a daily win", size=13, color=theme.HEADLINE),
                                    ft.Text(
                                        "Track habits such as water, fruit, or a daily check-off.",
                                        size=11,
                                        color=theme.MUTED_TEXT,
                                    ),
                                ],
                            ),
                            ft.TextButton(
                                "Add",
                                on_click=lambda e: categories_screen.show_manager(
                                    page, ctx, on_changed=_on_categories_changed
                                ),
                            ),
                        ]
                    ),
                    padding=14,
                    radius=10,
                )
            )
            return

        for category in categories:
            amount = ctx.daily_progress_service.get(category.id, today)
            target = category.target_value
            progress = min(1.0, amount / target) if target else 0.0
            if category.is_checkoff:
                action = ft.Checkbox(
                    value=amount >= 1,
                    active_color=category.color,
                    on_change=lambda e, cid=category.id: _toggle_checkoff(cid),
                )
                detail = "Done" if amount else "Tap to complete"
            else:
                action = ft.Row(
                    tight=True,
                    spacing=2,
                    controls=[
                        ft.IconButton(
                            icon=ft.Icons.REMOVE,
                            icon_color=theme.MUTED_TEXT,
                            disabled=amount <= 0,
                            on_click=lambda e, cid=category.id: _adjust_counter(cid, -1),
                        ),
                        ft.TextButton(
                            f"{amount} / {target}",
                            on_click=lambda e, c=category: _open_amount_editor(c),
                        ),
                        ft.IconButton(
                            icon=ft.Icons.ADD,
                            icon_color=category.color,
                            on_click=lambda e, cid=category.id: _adjust_counter(cid, 1),
                        ),
                    ],
                )
                detail = category.unit_label

            checkins_column.controls.append(
                theme.card(
                    ft.Column(
                        spacing=5,
                        controls=[
                            ft.Row(
                                controls=[
                                    ft.Icon(ft.Icons.CIRCLE, size=11, color=category.color),
                                    ft.Column(
                                        expand=True,
                                        spacing=1,
                                        controls=[
                                            ft.Text(category.name, size=13, color=theme.HEADLINE),
                                            ft.Text(detail, size=10, color=theme.MUTED_TEXT),
                                        ],
                                    ),
                                    action,
                                ]
                            ),
                            fury_progress(progress, color=category.color, animate_in=False),
                        ],
                    ),
                    padding=12,
                    radius=10,
                )
            )

    def _refresh_grid() -> None:
        grid_column.controls.clear()
        categories = [
            category for category in ctx.category_service.list_categories() if category.is_timer
        ]
        live = ctx.timer_service.current_state()
        if not categories:
            grid_column.controls.append(
                theme.card(
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.TIMER_OUTLINED, color=theme.ACCENT, size=22),
                            ft.Column(
                                expand=True,
                                spacing=2,
                                controls=[
                                    ft.Text("Create your first timer", size=13, color=theme.HEADLINE),
                                    ft.Text(
                                        "Choose a focus category, set a target, then start your streak.",
                                        size=11,
                                        color=theme.MUTED_TEXT,
                                    ),
                                ],
                            ),
                            ft.TextButton(
                                "Create",
                                on_click=lambda e: categories_screen.show_manager(
                                    page, ctx, on_changed=_on_categories_changed
                                ),
                            ),
                        ]
                    ),
                    padding=14,
                    radius=10,
                )
            )
            return

        row = None
        for index, category in enumerate(categories):
            if index % 2 == 0:
                row = ft.Row(spacing=8)
                grid_column.controls.append(row)
            is_tracking = live.is_active and live.category_id == category.id
            is_selected = not live.is_active and selected["id"] == category.id
            border_color = (
                category.color if is_selected
                else ("#FFFFFF" if is_tracking else theme.CARD_BORDER)
            )
            row.controls.append(
                ft.Container(
                    expand=True,
                    padding=14,
                    border_radius=10,
                    bgcolor=category.color if is_tracking else theme.CARD,
                    border=ft.Border.all(
                        2 if (is_selected or is_tracking) else 1, border_color
                    ),
                    animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
                    content=ft.Row(
                        spacing=6,
                        controls=[
                            ft.Icon(
                                ft.Icons.CIRCLE,
                                size=13,
                                color="#FFFFFF" if is_tracking else category.color,
                            ),
                            ft.Text(
                                category.name,
                                size=13,
                                color="#FFFFFF" if is_tracking else theme.HEADLINE,
                                weight=(
                                    ft.FontWeight.BOLD
                                    if (is_tracking or is_selected) else ft.FontWeight.NORMAL
                                ),
                            ),
                        ],
                    ),
                    on_click=lambda e, cid=category.id: _on_category_tap(cid),
                )
            )

    def _refresh_all() -> None:
        live = ctx.timer_service.current_state()
        categories = {
            category.id: category
            for category in ctx.category_service.list_categories()
            if category.is_timer
        }
        if not live.is_active and selected["id"] not in categories:
            selected["id"] = next(iter(categories), None)

        if live.is_active and live.category_id in categories:
            category = categories[live.category_id]
            clock_text.value = time_utils.fmt_clock(live.elapsed_seconds)
            clock_text.color = category.color
            subtitle_text.value = f"TRACKING: {category.name.upper()}"
            subtitle_text.color = category.color
            clock_card.shadow = _pulse_shadow(category.color)
        else:
            clock_text.value = time_utils.fmt_clock(0)
            clock_text.color = theme.HEADLINE
            clock_card.shadow = None
            if selected["id"] in categories:
                category = categories[selected["id"]]
                subtitle_text.value = f"Ready to start: {category.name}"
                subtitle_text.color = category.color
            else:
                subtitle_text.value = "Add a Timer category, then press Start"
                subtitle_text.color = theme.MUTED_TEXT

        controls_row.controls.clear()
        if live.is_active:
            controls_row.controls.append(
                fury_button("Stop", icon=ft.Icons.STOP, kind="danger", on_click=_on_stop)
            )
            controls_row.controls.append(ft.TextButton("Discard", on_click=_on_discard))
        else:
            controls_row.controls.append(
                fury_button(
                    "Start",
                    icon=ft.Icons.PLAY_ARROW,
                    kind="primary",
                    on_click=_on_start,
                    disabled=selected["id"] is None,
                )
            )

        _refresh_score_and_checkins()
        _refresh_goals()
        _refresh_grid()
        _maybe_show_goal_celebration()
        page.update()

    _refresh_all()
    if state.is_active:
        _start_ticking()

    return ft.Column(
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        spacing=14,
        controls=[
            hero_banner(
                page,
                kicker="Timer / Live Session",
                headline="REVENGE",
                height=COMPACT_HEIGHT,
                # Nudge the cover crop down so the hero shows the character's
                # shoulders/chest as well as the face.
                image_align=ft.Alignment(0, 0.34),
            ),
            clock_card,
            categories_header,
            grid_column,
            score_card,
            theme.section_label("Today's check-ins"),
            checkins_column,
            goals_header,
            goals_column,
        ],
    )
