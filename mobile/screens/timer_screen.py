"""
The mobile Timer screen: live clock + category tap-grid + today's goal
progress. Same logic as the desktop app/ui/views/timer_view.py (same
TimerService, same select-then-Start flow), rebuilt for a narrow screen:
a 2-column category grid instead of 3, full-width Start/Stop, and goal
editing done inline (tap the pencil) instead of in a popup dialog.
"""

from __future__ import annotations

import asyncio

import flet as ft

from app.utils import time_utils, validators
from mobile import theme


def build(page: ft.Page, ctx) -> ft.Control:
    state = ctx.timer_service.current_state()
    categories = ctx.category_service.list_categories()
    cats_by_id = {c.id: c for c in categories}

    selected = {
        "id": state.category_id if state.is_active
        else (categories[0].id if categories else None)
    }
    editing_goals = {"on": False}
    goal_inputs: dict[int, ft.TextField] = {}

    clock_text = ft.Text("0:00:00", size=48, weight=ft.FontWeight.BOLD,
                        color=theme.HEADLINE, text_align=ft.TextAlign.CENTER)
    subtitle_text = ft.Text("", size=13, color=theme.MUTED_TEXT, text_align=ft.TextAlign.CENTER)
    controls_row = ft.Row(alignment=ft.MainAxisAlignment.CENTER, spacing=10)
    goals_column = ft.Column(spacing=8)
    grid_column = ft.Column(spacing=8)
    goals_header = ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

    async def _tick_loop() -> None:
        while True:
            await asyncio.sleep(1)
            live = ctx.timer_service.current_state()
            if not live.is_active:
                break
            clock_text.value = time_utils.fmt_clock(live.elapsed_seconds)
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

    def _toggle_edit_goals(e=None) -> None:
        editing_goals["on"] = not editing_goals["on"]
        _refresh_all()

    def _save_goals(e=None) -> None:
        error = None
        parsed: dict[int, int] = {}
        for cat in ctx.category_service.list_categories():
            text = goal_inputs[cat.id].value
            ok, msg = validators.validate_target_minutes(text)
            if not ok:
                error = f"{cat.name}: {msg}"
                break
            parsed[cat.id] = int(text or 0)
        if error is None:
            for cat in ctx.category_service.list_categories():
                if parsed[cat.id] != cat.daily_target_minutes:
                    cat.daily_target_minutes = parsed[cat.id]
                    ctx.category_service.update(cat)
            editing_goals["on"] = False
        _refresh_all()

    def _refresh_goals() -> None:
        goals_column.controls.clear()
        goal_inputs.clear()
        goals_header.controls = [
            ft.Text("Today's Goals", size=15, weight=ft.FontWeight.BOLD, color=theme.HEADLINE),
            ft.IconButton(
                icon=ft.Icons.CHECK if editing_goals["on"] else ft.Icons.EDIT,
                icon_color=theme.ACCENT,
                on_click=_save_goals if editing_goals["on"] else _toggle_edit_goals,
            ),
        ]

        cats = ctx.category_service.list_categories()
        if editing_goals["on"]:
            for cat in cats:
                field = ft.TextField(
                    value=str(cat.daily_target_minutes), width=70, height=42,
                    text_align=ft.TextAlign.CENTER, dense=True,
                )
                goal_inputs[cat.id] = field
                goals_column.controls.append(
                    ft.Row(controls=[
                        ft.Icon(ft.Icons.CIRCLE, size=12, color=cat.color),
                        ft.Text(cat.name, size=13, color=theme.HEADLINE, expand=True),
                        field,
                        ft.Text("min/day", size=11, color=theme.MUTED_TEXT),
                    ])
                )
            return

        summary = ctx.dashboard_service.build_summary(time_utils.today_str())
        goals = [p for p in summary.progress if p.target_minutes > 0]
        if not goals:
            goals_column.controls.append(
                ft.Text("No daily goals set yet — tap the pencil to add one.",
                        size=12, color=theme.MUTED_TEXT)
            )
        for prog in goals:
            goals_column.controls.append(
                ft.Column(spacing=2, controls=[
                    ft.Row(controls=[
                        ft.Text(prog.name, size=13, color=theme.HEADLINE, expand=True),
                        ft.Text(f"{prog.actual_label} / {prog.target_label}",
                                size=12, color=theme.MUTED_TEXT),
                    ]),
                    ft.ProgressBar(value=prog.completion_pct / 100, color=prog.color,
                                  bgcolor=theme.NEUTRAL_BTN, border_radius=8),
                ])
            )

    def _refresh_grid() -> None:
        grid_column.controls.clear()
        cats = ctx.category_service.list_categories()
        live = ctx.timer_service.current_state()

        row = None
        for i, cat in enumerate(cats):
            if i % 2 == 0:
                row = ft.Row(spacing=8)
                grid_column.controls.append(row)
            is_tracking = live.is_active and live.category_id == cat.id
            is_selected = not live.is_active and selected["id"] == cat.id
            border_color = cat.color if is_selected else ("#FFFFFF" if is_tracking else theme.CARD_BORDER)
            tile = ft.Container(
                expand=True, padding=14, border_radius=10,
                bgcolor=cat.color if is_tracking else theme.CARD,
                border=ft.Border.all(2 if (is_selected or is_tracking) else 1, border_color),
                content=ft.Row(spacing=6, controls=[
                    ft.Icon(ft.Icons.CIRCLE, size=13,
                            color="#FFFFFF" if is_tracking else cat.color),
                    ft.Text(cat.name, size=13,
                            color="#FFFFFF" if is_tracking else theme.HEADLINE,
                            weight=ft.FontWeight.BOLD if (is_tracking or is_selected) else ft.FontWeight.NORMAL),
                ]),
                on_click=lambda e, cid=cat.id: _on_category_tap(cid),
            )
            row.controls.append(tile)

    def _refresh_all() -> None:
        live = ctx.timer_service.current_state()
        cats = {c.id: c for c in ctx.category_service.list_categories()}

        if live.is_active and live.category_id in cats:
            cat = cats[live.category_id]
            clock_text.value = time_utils.fmt_clock(live.elapsed_seconds)
            clock_text.color = cat.color
            subtitle_text.value = f"Tracking: {cat.name}"
            subtitle_text.color = cat.color
        else:
            clock_text.value = time_utils.fmt_clock(0)
            clock_text.color = theme.HEADLINE
            if selected["id"] in cats:
                subtitle_text.value = f"Ready to start: {cats[selected['id']].name}"
                subtitle_text.color = cats[selected["id"]].color
            else:
                subtitle_text.value = "Choose a category below, then press Start"
                subtitle_text.color = theme.MUTED_TEXT

        controls_row.controls.clear()
        if live.is_active:
            controls_row.controls.append(
                ft.Button("Stop", icon=ft.Icons.STOP, bgcolor=theme.STOP_RED,
                         color="#FFFFFF", on_click=_on_stop)
            )
            controls_row.controls.append(ft.TextButton("Discard", on_click=_on_discard))
        else:
            controls_row.controls.append(
                ft.Button("Start", icon=ft.Icons.PLAY_ARROW, bgcolor=theme.ACCENT,
                         color="#FFFFFF", on_click=_on_start,
                         disabled=selected["id"] is None)
            )

        _refresh_goals()
        _refresh_grid()
        page.update()

    _refresh_all()
    if state.is_active:
        _start_ticking()

    return ft.Column(
        expand=True, scroll=ft.ScrollMode.AUTO, spacing=14,
        controls=[
            ft.Container(
                padding=20, border_radius=16, bgcolor=theme.CARD,
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6,
                    controls=[clock_text, subtitle_text, controls_row],
                ),
            ),
            goals_header,
            goals_column,
            ft.Text("Categories", size=15, weight=ft.FontWeight.BOLD, color=theme.HEADLINE),
            grid_column,
        ],
    )
