"""
The graphs screen.

Six charts that redraw themselves whenever the data (or the light/dark theme)
changes: daily productive hours, weekly productivity, monthly totals, the split
of time by category, a smoothed productivity trend, and the history of your
streak. Charts are embedded matplotlib figures; each one reuses a single figure
for its whole life so switching screens never leaks memory.
"""

from __future__ import annotations

import customtkinter as ctk

from app.charts import chart_factory
from app.charts.chart_data import ChartDataProvider
from app.ui import theme
from app.ui.views.base_view import BaseView


class GraphsView(BaseView):
    title = "Graphs"

    def __init__(self, master, context) -> None:
        super().__init__(master, context)
        self.data = ChartDataProvider(context)
        self._frames = {}
        self._build()

    def _build(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(20, 8))
        ctk.CTkLabel(header, text="Graphs",
                     font=ctk.CTkFont(size=26, weight="bold")).pack(side="left")
        ctk.CTkButton(header, text="⟳  Refresh", width=100,
                      command=self.refresh).pack(side="right")

        grid = ctk.CTkScrollableFrame(self, fg_color="transparent")
        grid.pack(fill="both", expand=True, padx=24, pady=(0, 20))
        grid.grid_columnconfigure((0, 1), weight=1, uniform="charts")

        # Import here to keep the widget list tidy; each key maps to a chart.
        from app.charts.chart_frame import ChartFrame
        keys = ["daily", "weekly", "monthly", "pie", "trend", "streak"]
        for index, key in enumerate(keys):
            frame = ChartFrame(grid, width_inches=4.8, height_inches=3.0,
                               corner_radius=12, fg_color=theme.CARD_COLOR)
            frame.grid(row=index // 2, column=index % 2, padx=8, pady=8, sticky="nsew")
            grid.grid_rowconfigure(index // 2, weight=1)
            self._frames[key] = frame

    def refresh(self) -> None:
        style = theme.chart_style()

        # 1. Daily productive hours (line).
        daily = self.data.daily_productive_hours(14)
        self._frames["daily"].draw(
            lambda fig: chart_factory.line_chart(
                fig, daily, style, "Daily Productive Hours (14 days)"))

        # 2. Weekly productivity (bar).
        weekly = self.data.weekly_productive_hours(8)
        self._frames["weekly"].draw(
            lambda fig: chart_factory.bar_chart(
                fig, weekly, style, "Weekly Productivity (8 weeks)"))

        # 3. Monthly totals (bar).
        monthly = self.data.monthly_productive_hours(6)
        self._frames["monthly"].draw(
            lambda fig: chart_factory.bar_chart(
                fig, monthly, style, "Monthly Totals (6 months)"))

        # 4. Category distribution (pie).
        pie = self.data.category_distribution(30)
        self._frames["pie"].draw(
            lambda fig: chart_factory.pie_chart(
                fig, pie, style, "Category Distribution (30 days)"))

        # 5. Productivity trend (line + moving average).
        trend, moving = self.data.productivity_trend(30)
        self._frames["trend"].draw(
            lambda fig: chart_factory.trend_chart(
                fig, trend, moving, style, "Productivity Trend (30 days)"))

        # 6. Streak history (line).
        streak = self.data.streak_history(60)
        self._frames["streak"].draw(
            lambda fig: chart_factory.line_chart(
                fig, streak, style, "Streak History (60 days)", ylabel="Streak (days)"))
