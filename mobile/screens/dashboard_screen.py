"""
The mobile Dashboard screen — one day's detail: a status banner, stat cards,
and the full per-category target-vs-actual table. Same data as the desktop
Dashboard screen, via DashboardService.build_summary().
"""

from __future__ import annotations

import flet as ft

from app.utils import time_utils
from mobile import theme
from mobile.widgets.stat_card import stat_card


def build(page: ft.Page, ctx) -> ft.Control:
    state = {"date": time_utils.today_str()}

    date_label = ft.Text("", size=15, weight=ft.FontWeight.BOLD, color=theme.HEADLINE)
    banner_text = ft.Text("", size=13, weight=ft.FontWeight.BOLD, color="#FFFFFF")
    banner = ft.Container(padding=12, border_radius=10, content=banner_text)
    cards_row = ft.ResponsiveRow()
    table_column = ft.Column(spacing=10)

    def _prev(e=None) -> None:
        state["date"] = time_utils.add_days(state["date"], -1)
        _refresh()

    def _next(e=None) -> None:
        state["date"] = time_utils.add_days(state["date"], 1)
        _refresh()

    def _today(e=None) -> None:
        state["date"] = time_utils.today_str()
        _refresh()

    def _refresh() -> None:
        summary = ctx.dashboard_service.build_summary(state["date"])
        weekday = time_utils.weekday_name(state["date"])
        date_label.value = f"{weekday}, {state['date']}"

        banner.bgcolor = summary.status.color
        banner_text.value = (f"{summary.status.label}  •  {summary.productive_label} productive  "
                             f"•  {summary.session_count} sessions")

        cards_row.controls = [
            stat_card("Productive", summary.productive_label, accent=theme.ACCENT),
            stat_card("Recorded", summary.recorded_label, accent="#3B82F6"),
            stat_card("Sessions", str(summary.session_count), accent="#EC4899"),
            stat_card("Longest", summary.longest_session_label, accent="#8B5CF6"),
        ]

        table_column.controls.clear()
        if not summary.progress:
            table_column.controls.append(
                ft.Text("No activity recorded on this day.", size=12, color=theme.MUTED_TEXT)
            )
        for prog in summary.progress:
            label = f"{prog.actual_label} / {prog.target_label}" if prog.target_minutes else prog.actual_label
            table_column.controls.append(
                ft.Column(spacing=2, controls=[
                    ft.Row(controls=[
                        ft.Icon(ft.Icons.CIRCLE, size=11, color=prog.color),
                        ft.Text(prog.name, size=13, color=theme.HEADLINE, expand=True),
                        ft.Text(label, size=12, color=theme.MUTED_TEXT),
                    ]),
                    ft.ProgressBar(value=prog.completion_pct / 100, color=prog.color,
                                  bgcolor=theme.NEUTRAL_BTN, border_radius=8),
                ])
            )
        page.update()

    _refresh()

    nav = ft.Row(
        alignment=ft.MainAxisAlignment.CENTER, spacing=6,
        controls=[
            ft.IconButton(icon=ft.Icons.CHEVRON_LEFT, on_click=_prev),
            date_label,
            ft.IconButton(icon=ft.Icons.CHEVRON_RIGHT, on_click=_next),
            ft.TextButton("Today", on_click=_today),
        ],
    )

    return ft.Column(
        expand=True, scroll=ft.ScrollMode.AUTO, spacing=14,
        controls=[
            ft.Text("Dashboard", size=22, weight=ft.FontWeight.BOLD, color=theme.HEADLINE),
            nav, banner, cards_row,
            ft.Text("Time by category", size=15, weight=ft.FontWeight.BOLD, color=theme.HEADLINE),
            table_column,
        ],
    )
