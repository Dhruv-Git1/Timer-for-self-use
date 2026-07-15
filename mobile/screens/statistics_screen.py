"""
The mobile Statistics screen — Daily/Weekly/Monthly/Yearly aggregates with
‹ › period navigation, stat cards, streak/weekday info, and a category
breakdown. Same data as the desktop Statistics screen, via StatsService.
"""

from __future__ import annotations

import calendar as _calendar
from datetime import date

import flet as ft

from app.utils import time_utils
from mobile import theme
from mobile.widgets.stat_card import stat_card

_PERIODS = ["Daily", "Weekly", "Monthly", "Yearly"]


def build(page: ft.Page, ctx) -> ft.Control:
    state = {"period": "Weekly", "anchor": time_utils.today_str()}

    period_row = ft.Row(spacing=6)
    period_label = ft.Text("", size=15, weight=ft.FontWeight.BOLD, color=theme.HEADLINE)
    cards_row = ft.ResponsiveRow()
    info_text = ft.Text("", size=12, color=theme.MUTED_TEXT)
    table_column = ft.Column(spacing=8)

    def _shift_month(months: int) -> None:
        d = time_utils.to_date(state["anchor"])
        month_index = d.year * 12 + (d.month - 1) + months
        year, month = divmod(month_index, 12)
        day = min(d.day, _calendar.monthrange(year, month + 1)[1])
        state["anchor"] = date(year, month + 1, day).strftime("%Y-%m-%d")

    def _step(direction: int) -> None:
        period = state["period"]
        if period == "Daily":
            state["anchor"] = time_utils.add_days(state["anchor"], direction)
        elif period == "Weekly":
            state["anchor"] = time_utils.add_days(state["anchor"], 7 * direction)
        elif period == "Monthly":
            _shift_month(direction)
        else:
            _shift_month(12 * direction)
        _refresh()

    def _set_period(period: str) -> None:
        state["period"] = period
        for btn in period_row.controls:
            btn.bgcolor = theme.ACCENT if btn.data == period else theme.NEUTRAL_BTN
        _refresh()

    def _current_stats():
        d = time_utils.to_date(state["anchor"])
        period = state["period"]
        if period == "Daily":
            return ctx.stats_service.daily(state["anchor"])
        if period == "Weekly":
            return ctx.stats_service.weekly(state["anchor"])
        if period == "Monthly":
            return ctx.stats_service.monthly(d.year, d.month)
        return ctx.stats_service.yearly(d.year)

    def _refresh() -> None:
        stats = _current_stats()
        period_label.value = stats.label

        def hours(minutes) -> str:
            return time_utils.fmt_duration(int(round(minutes)))

        cards_row.controls = [
            stat_card("Productive", hours(stats.total_productive_minutes), accent=theme.ACCENT),
            stat_card("Recorded", hours(stats.total_recorded_minutes), accent="#3B82F6"),
            stat_card("Active Days", str(stats.active_days), accent="#14B8A6"),
            stat_card("Sessions", str(stats.session_count), accent="#EC4899"),
            stat_card("Avg Session", hours(stats.avg_session_minutes) if stats.session_count else "—",
                     accent="#8B5CF6"),
            stat_card("Avg Start", stats.avg_start_time, accent="#F59E0B"),
            stat_card("Longest", hours(stats.longest_session_minutes) if stats.longest_session_minutes else "—",
                     accent="#EF4444"),
            stat_card("Avg/Active Day",
                     hours(stats.avg_productive_minutes_per_active_day) if stats.active_days else "—",
                     accent="#2E9E5B"),
        ]

        info_text.value = (f"🔥 Streak: {stats.current_streak}d   🏆 Longest: {stats.longest_streak}d   "
                           f"📈 Best: {stats.most_productive_weekday}   📉 Worst: {stats.least_productive_weekday}")

        table_column.controls.clear()
        if not stats.minutes_by_category:
            table_column.controls.append(
                ft.Text("No activity recorded in this period.", size=12, color=theme.MUTED_TEXT)
            )
        else:
            total = sum(stats.minutes_by_category.values()) or 1
            colors = {c.name: c.color for c in ctx.category_service.list_categories(include_archived=True)}
            ordered = sorted(stats.minutes_by_category.items(), key=lambda kv: kv[1], reverse=True)
            for name, minutes in ordered:
                share = minutes / total
                color = colors.get(name, theme.MUTED_TEXT)
                table_column.controls.append(
                    ft.Column(spacing=2, controls=[
                        ft.Row(controls=[
                            ft.Icon(ft.Icons.CIRCLE, size=11, color=color),
                            ft.Text(name, size=13, color=theme.HEADLINE, expand=True),
                            ft.Text(f"{time_utils.fmt_duration(minutes)} ({share * 100:.0f}%)",
                                    size=12, color=theme.MUTED_TEXT),
                        ]),
                        ft.ProgressBar(value=share, color=color, bgcolor=theme.NEUTRAL_BTN, border_radius=8),
                    ])
                )
        page.update()

    for period in _PERIODS:
        period_row.controls.append(
            ft.Container(
                data=period, padding=ft.Padding.symmetric(vertical=6, horizontal=12),
                border_radius=8, bgcolor=theme.ACCENT if period == state["period"] else theme.NEUTRAL_BTN,
                content=ft.Text(period, size=12, color="#FFFFFF"),
                on_click=lambda e, p=period: _set_period(p),
            )
        )

    _refresh()

    nav = ft.Row(
        alignment=ft.MainAxisAlignment.CENTER, spacing=6,
        controls=[
            ft.IconButton(icon=ft.Icons.CHEVRON_LEFT, on_click=lambda e: _step(-1)),
            period_label,
            ft.IconButton(icon=ft.Icons.CHEVRON_RIGHT, on_click=lambda e: _step(1)),
        ],
    )

    return ft.Column(
        expand=True, scroll=ft.ScrollMode.AUTO, spacing=14,
        controls=[
            ft.Text("Statistics", size=22, weight=ft.FontWeight.BOLD, color=theme.HEADLINE),
            period_row, nav, cards_row, info_text,
            ft.Text("Time by category", size=15, weight=ft.FontWeight.BOLD, color=theme.HEADLINE),
            table_column,
        ],
    )
