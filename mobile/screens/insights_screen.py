"""
The mobile Insights screen — pick a category, see its year heatmap, summary
stats, and weekday pattern. Same data as the desktop Insights screen (via
ChartDataProvider); only the widgets are mobile-native — a horizontally-
scrollable heatmap instead of a wide matplotlib figure, a Flet-native bar
chart instead of a matplotlib one.
"""

from __future__ import annotations

import flet as ft

from app.charts.chart_data import ChartDataProvider
from app.utils import time_utils
from mobile import theme
from mobile.widgets import charts, heatmap
from mobile.widgets.stat_card import stat_card


def build(page: ft.Page, ctx) -> ft.Control:
    data = ChartDataProvider(ctx)
    categories = ctx.category_service.list_categories()

    if not categories:
        return ft.Column(
            expand=True, alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[ft.Text("No categories yet.", color=theme.MUTED_TEXT)],
        )

    state = {
        "category_id": categories[0].id,
        "year": time_utils.to_date(time_utils.today_str()).year,
    }

    body = ft.Column(spacing=16)
    year_label = ft.Text("", size=15, weight=ft.FontWeight.BOLD, color=theme.HEADLINE)

    category_dropdown = ft.Dropdown(
        value=str(state["category_id"]),
        options=[ft.DropdownOption(key=str(c.id), text=c.name) for c in categories],
        width=160,
        on_select=lambda e: _on_category_change(),
    )

    def _on_category_change() -> None:
        state["category_id"] = int(category_dropdown.value)
        _refresh()

    def _prev_year(e=None) -> None:
        state["year"] -= 1
        _refresh()

    def _next_year(e=None) -> None:
        state["year"] += 1
        _refresh()

    def _refresh() -> None:
        category = next(c for c in categories if c.id == state["category_id"])
        year = state["year"]
        year_label.value = str(year)

        y0, y1 = f"{year:04d}-01-01", f"{year:04d}-12-31"
        day_minutes = data.category_year_heatmap(category.id, year)
        stats = data.category_summary_stats(category.id, y0, y1)
        daily_series = data.category_daily_hours(category.id, n_days=30)
        monthly_series = data.category_monthly_hours(category.id, year)
        cumulative_series = data.category_cumulative_hours(category.id, year)
        weekday_series = data.category_weekday_pattern(category.id, n_weeks=12)
        time_of_day_series = data.category_time_of_day(category.id, n_days=90)
        best_subtitle = time_utils.fmt_short_date(stats.best_day_date) if stats.best_day_date else ""

        def chart_card(chart: ft.Control) -> ft.Container:
            return ft.Container(
                bgcolor=theme.CARD, border_radius=12,
                border=ft.Border.all(1, theme.CARD_BORDER), content=chart,
            )

        body.controls = [
            ft.Container(
                bgcolor=theme.CARD, border_radius=12, padding=12,
                border=ft.Border.all(1, theme.CARD_BORDER),
                content=heatmap.build(day_minutes, year, category.color),
            ),
            ft.ResponsiveRow(controls=[
                stat_card("Total", stats.total_label, accent=category.color),
                stat_card("Active Days", str(stats.active_days), accent=category.color),
                stat_card("Streak", str(stats.current_streak_days),
                         "day" if stats.current_streak_days == 1 else "days", accent=category.color),
                stat_card("Best Day", stats.best_day_label, best_subtitle, accent=category.color),
            ]),
            theme.section_label("Daily hours (last 30 days)"),
            chart_card(charts.line_chart(daily_series, category.color, height=190)),
            theme.section_label(f"Monthly hours ({year})"),
            chart_card(charts.line_chart(monthly_series, category.color, height=190)),
            theme.section_label(f"Cumulative hours ({year})"),
            chart_card(charts.line_chart(cumulative_series, category.color, height=190)),
            theme.section_label("Weekday pattern (last 12 weeks)"),
            chart_card(charts.bar_chart(weekday_series, category.color)),
            theme.section_label("Time of day (last 90 days)"),
            chart_card(charts.bar_chart(time_of_day_series, category.color)),
        ]
        page.update()

    _refresh()

    header = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        controls=[
            theme.display("Insights", size=28),
            category_dropdown,
        ],
    )
    year_nav = ft.Row(
        alignment=ft.MainAxisAlignment.CENTER, spacing=10,
        controls=[
            ft.IconButton(icon=ft.Icons.CHEVRON_LEFT, on_click=_prev_year),
            year_label,
            ft.IconButton(icon=ft.Icons.CHEVRON_RIGHT, on_click=_next_year),
        ],
    )

    return ft.Column(
        expand=True, scroll=ft.ScrollMode.AUTO, spacing=12,
        controls=[header, year_nav, body],
    )
