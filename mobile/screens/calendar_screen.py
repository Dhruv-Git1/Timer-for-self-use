"""
The mobile Calendar screen — a month grid colored by day status (reusing
the same green/amber/red/grey classifier as the dashboard and streaks); tap
a day to see its entries in a bottom sheet instead of a side panel.
"""

from __future__ import annotations

import calendar as _calendar

import flet as ft

from app.utils import time_utils
from mobile import theme

_WEEKDAY_HEADERS = ["M", "T", "W", "T", "F", "S", "S"]


def build(page: ft.Page, ctx) -> ft.Control:
    today_str = time_utils.today_str()
    today = time_utils.to_date(today_str)
    state = {"year": today.year, "month": today.month}

    month_label = ft.Text("", size=16, weight=ft.FontWeight.BOLD, color=theme.HEADLINE)
    grid_column = ft.Column(spacing=3)

    def _prev(e=None) -> None:
        state["month"] -= 1
        if state["month"] == 0:
            state["month"], state["year"] = 12, state["year"] - 1
        _refresh()

    def _next(e=None) -> None:
        state["month"] += 1
        if state["month"] == 13:
            state["month"], state["year"] = 1, state["year"] + 1
        _refresh()

    def _go_today(e=None) -> None:
        state["year"], state["month"] = today.year, today.month
        _refresh()

    def _show_day(date_str: str) -> None:
        weekday = time_utils.weekday_name(date_str)
        summary = ctx.dashboard_service.build_summary(date_str)
        entries = ctx.calendar_service.day_entries(date_str)

        rows = [
            ft.Text(f"{weekday}, {date_str}", size=16, weight=ft.FontWeight.BOLD, color=theme.HEADLINE),
            ft.Text(f"{summary.status.label}  •  {summary.productive_label} productive  "
                    f"•  {summary.session_count} sessions", size=13, color=summary.status.color),
        ]
        if not entries:
            rows.append(ft.Text("No entries logged.", size=12, color=theme.MUTED_TEXT))
        for entry in entries:
            rows.append(
                ft.Row(controls=[
                    ft.Icon(ft.Icons.CIRCLE, size=11, color=entry.category_color),
                    ft.Text(f"{entry.start_time}–{entry.end_time}  {entry.category_name}  "
                            f"({entry.duration_label})", size=13, color=theme.HEADLINE),
                ])
            )

        sheet = ft.BottomSheet(
            content=ft.Container(
                padding=20, bgcolor=theme.CARD,
                content=ft.Column(tight=True, spacing=8, scroll=ft.ScrollMode.AUTO, controls=rows),
            ),
        )
        page.show_dialog(sheet)

    def _refresh() -> None:
        month_label.value = f"{_calendar.month_name[state['month']]} {state['year']}"
        status_map = ctx.calendar_service.month_status(state["year"], state["month"])
        matrix = ctx.calendar_service.month_matrix(state["year"], state["month"])

        grid_column.controls.clear()
        header_row = ft.Row(spacing=3, controls=[
            ft.Container(expand=True, aspect_ratio=2.4, alignment=ft.Alignment.CENTER,
                        content=ft.Text(h, size=11, color=theme.MUTED_TEXT))
            for h in _WEEKDAY_HEADERS
        ])
        grid_column.controls.append(header_row)

        for week in matrix:
            row = ft.Row(spacing=3, controls=[])
            for day in week:
                if day == 0:
                    row.controls.append(ft.Container(expand=True, aspect_ratio=1))
                    continue
                date_str = f"{state['year']:04d}-{state['month']:02d}-{day:02d}"
                status = status_map.get(date_str)
                color = status.color if status else theme.STATUS_NEUTRAL
                is_today = date_str == today_str
                row.controls.append(
                    ft.Container(
                        expand=True, aspect_ratio=1, border_radius=8, bgcolor=color,
                        border=ft.Border.all(3, theme.ACCENT) if is_today else None,
                        alignment=ft.Alignment.CENTER,
                        content=ft.Text(str(day), size=13, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
                        on_click=lambda e, d=date_str: _show_day(d),
                    )
                )
            grid_column.controls.append(row)
        page.update()

    _refresh()

    nav = ft.Row(
        alignment=ft.MainAxisAlignment.CENTER, spacing=6,
        controls=[
            ft.IconButton(icon=ft.Icons.CHEVRON_LEFT, on_click=_prev),
            month_label,
            ft.IconButton(icon=ft.Icons.CHEVRON_RIGHT, on_click=_next),
            ft.TextButton("Today", on_click=_go_today),
        ],
    )

    return ft.Column(
        expand=True, scroll=ft.ScrollMode.AUTO, spacing=8,
        controls=[
            theme.display("Calendar", size=28),
            nav, grid_column,
        ],
    )
