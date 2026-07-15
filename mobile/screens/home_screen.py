"""
The mobile Home screen — headline stats + "Mission Targets" goal progress.

The desktop version's Pillow-composited hero banner image is skipped for this
first milestone (a plain styled header stands in for it); the stat cards and
goal panel underneath use the same data, via the same services
(DashboardService/StatsService) the desktop Home screen calls.
"""

from __future__ import annotations

import flet as ft

from app.utils import time_utils
from mobile import theme
from mobile.widgets.stat_card import stat_card


def build(page: ft.Page, ctx) -> ft.Control:
    today = time_utils.today_str()
    summary = ctx.dashboard_service.build_summary(today)
    week = ctx.stats_service.weekly(today)

    cards = ft.ResponsiveRow(
        controls=[
            stat_card("Today", summary.productive_label, "productive", theme.ACCENT),
            stat_card("Streak", str(summary.current_streak),
                     "day" if summary.current_streak == 1 else "days", "#E0A100"),
            stat_card("Sessions", str(summary.session_count), "logged today", "#3B82F6"),
            stat_card("This Week", time_utils.fmt_duration(week.total_productive_minutes),
                     "productive", "#2E9E5B"),
        ],
    )

    goals = [p for p in summary.progress if p.target_minutes > 0]
    goal_rows: list[ft.Control] = []
    if not goals:
        goal_rows.append(ft.Text("No daily goals set yet — set them on the Timer screen.",
                                 size=12, color=theme.MUTED_TEXT))
    for prog in goals:
        goal_rows.append(
            ft.Column(spacing=3, controls=[
                ft.Row(controls=[
                    ft.Text(prog.name, size=13, color=theme.HEADLINE, expand=True),
                    ft.Text(f"{prog.completion_pct:.0f}%", size=12,
                            color="#35C46A" if prog.completion_pct >= 100 else theme.ACCENT),
                ]),
                ft.ProgressBar(value=prog.completion_pct / 100, color=theme.ACCENT,
                              bgcolor=theme.NEUTRAL_BTN, border_radius=8),
            ])
        )

    return ft.Column(
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        spacing=16,
        controls=[
            ft.Text("Time Tracker", size=24, weight=ft.FontWeight.BOLD, color=theme.HEADLINE),
            ft.Text("The comeback starts now.", size=13, color=theme.MUTED_TEXT),
            cards,
            ft.Container(
                bgcolor=theme.CARD, border_radius=12, padding=16,
                content=ft.Column(spacing=10, controls=[
                    ft.Text("MISSION TARGETS", size=12, weight=ft.FontWeight.BOLD,
                            color=theme.MONO_LABEL),
                    *goal_rows,
                ]),
            ),
        ],
    )
