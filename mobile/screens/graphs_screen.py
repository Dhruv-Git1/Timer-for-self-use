"""
The mobile Graphs screen — the same six charts as the desktop Graphs screen
(daily/weekly/monthly totals, category split, trend, streak history), pulled
from the exact same ChartDataProvider, drawn with Flet-native charts
(Flutter-rendered, interactive) instead of matplotlib images.
"""

from __future__ import annotations

import flet as ft

from app.charts.chart_data import ChartDataProvider
from mobile import theme
from mobile.widgets import charts


def _section(title: str, chart: ft.Control) -> ft.Control:
    return ft.Column(spacing=6, controls=[
        theme.section_label(title),
        ft.Container(bgcolor=theme.CARD, border_radius=12,
                     border=ft.Border.all(1, theme.CARD_BORDER), content=chart),
    ])


def build(page: ft.Page, ctx) -> ft.Control:
    data = ChartDataProvider(ctx)

    daily = data.daily_productive_hours(14)
    weekly = data.weekly_productive_hours(8)
    monthly = data.monthly_productive_hours(6)
    pie = data.category_distribution(30)
    trend, moving_avg = data.productivity_trend(30)
    streak = data.streak_history(60)

    return ft.Column(
        expand=True, scroll=ft.ScrollMode.AUTO, spacing=18,
        controls=[
            theme.display("Graphs", size=28),
            _section("Daily Productive Hours (14 days)", charts.line_chart(daily, theme.KICKER_RED)),
            _section("Weekly Productivity (8 weeks)", charts.bar_chart(weekly, theme.ACCENT)),
            _section("Monthly Totals (6 months)", charts.bar_chart(monthly, "#10B981")),
            _section("Category Distribution (30 days)", charts.pie_chart(pie)),
            _section("Productivity Trend (30 days)",
                    charts.line_chart(trend, theme.ACCENT, extra_lines=[(moving_avg, theme.FLAME)])),
            _section("Streak History (60 days)", charts.line_chart(streak, theme.GOLD)),
        ],
    )
