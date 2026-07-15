"""
The Insights screen.

Pick one category — Study, Coding, whatever you track — and see it on its own:
a GitHub-style year heatmap in that category's own color, a handful of summary
numbers (total time, active days, current streak, best day, average), and a
weekday pattern so you can spot which days you actually show up.

Unlike Statistics/Graphs (which total every category together), everything on
this screen is scoped to the one category picked at the top.
"""

from __future__ import annotations

from typing import Dict, Optional

import customtkinter as ctk

from app.charts import chart_factory
from app.charts.chart_data import ChartDataProvider, Series
from app.charts.chart_frame import ChartFrame
from app.ui import theme
from app.ui.views.base_view import BaseView
from app.ui.widgets.stat_card import StatCard
from app.utils import time_utils


class InsightsView(BaseView):
    title = "Insights"

    def __init__(self, master, context) -> None:
        super().__init__(master, context)
        self.data = ChartDataProvider(context)
        self.year = time_utils.to_date(time_utils.today_str()).year
        self._categories = []
        self._selected_category_id: Optional[int] = None
        self._cards: Dict[str, StatCard] = {}
        self._build()

    # ------------------------------------------------------------------ #
    # Static layout
    # ------------------------------------------------------------------ #
    def _build(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(20, 8))
        ctk.CTkLabel(header, text="Insights",
                     font=ctk.CTkFont(size=26, weight="bold")).pack(side="left")
        self.category_menu = ctk.CTkOptionMenu(
            header, values=["—"], width=180, command=self._on_category_change)
        self.category_menu.pack(side="right")

        nav = ctk.CTkFrame(self, fg_color="transparent")
        nav.pack(fill="x", padx=24, pady=(0, 8))
        ctk.CTkButton(nav, text="‹", width=36, command=self._prev_year).pack(side="left")
        self.year_label = ctk.CTkLabel(nav, text="", width=80,
                                       font=ctk.CTkFont(size=15, weight="bold"))
        self.year_label.pack(side="left", padx=6)
        ctk.CTkButton(nav, text="›", width=36, command=self._next_year).pack(side="left")
        ctk.CTkButton(nav, text="This year", width=90, fg_color=theme.NEUTRAL_BTN,
                      hover_color=theme.NEUTRAL_BTN_HOVER, text_color=("gray10", "gray90"),
                      command=self._go_this_year).pack(side="left", padx=(8, 0))

        self.body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=24, pady=(0, 20))

        self.heatmap_frame = ChartFrame(self.body, width_inches=7.6, height_inches=2.4,
                                        corner_radius=12, fg_color=theme.CARD_COLOR)
        self.heatmap_frame.pack(fill="x", pady=(0, 12))

        self.cards_row = ctk.CTkFrame(self.body, fg_color="transparent")
        self.cards_row.pack(fill="x", pady=(0, 12))
        for col in range(5):
            self.cards_row.grid_columnconfigure(col, weight=1, uniform="insight_cards")
        specs = [("total", "Total Time"), ("active", "Active Days"),
                 ("streak", "Current Streak"), ("best", "Best Day"),
                 ("avg", "Avg / Active Day")]
        for i, (key, label) in enumerate(specs):
            card = StatCard(self.cards_row, title=label)
            card.grid(row=0, column=i, padx=6, pady=6, sticky="ew")
            self._cards[key] = card

        ctk.CTkLabel(self.body, text="Weekday pattern (last 12 weeks)",
                     font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", pady=(6, 4))
        self.weekday_frame = ChartFrame(self.body, width_inches=7.6, height_inches=2.8,
                                        corner_radius=12, fg_color=theme.CARD_COLOR)
        self.weekday_frame.pack(fill="x")

    # ------------------------------------------------------------------ #
    # Category + year controls
    # ------------------------------------------------------------------ #
    def _on_category_change(self, name: str) -> None:
        category = next((c for c in self._categories if c.name == name), None)
        if category is not None:
            self._selected_category_id = category.id
        self.refresh()

    def _prev_year(self) -> None:
        self.year -= 1
        self.refresh()

    def _next_year(self) -> None:
        self.year += 1
        self.refresh()

    def _go_this_year(self) -> None:
        self.year = time_utils.to_date(time_utils.today_str()).year
        self.refresh()

    # ------------------------------------------------------------------ #
    # Refresh
    # ------------------------------------------------------------------ #
    def refresh(self) -> None:
        self._categories = self.ctx.category_service.list_categories()
        self.year_label.configure(text=str(self.year))

        if not self._categories:
            self.category_menu.configure(values=["No categories"])
            self.category_menu.set("No categories")
            self._show_empty()
            return

        names = [c.name for c in self._categories]
        self.category_menu.configure(values=names)

        valid_ids = {c.id for c in self._categories}
        if self._selected_category_id not in valid_ids:
            self._selected_category_id = self._categories[0].id
        category = next(c for c in self._categories if c.id == self._selected_category_id)
        self.category_menu.set(category.name)

        style = theme.chart_style()

        # The year heatmap.
        day_minutes = self.data.category_year_heatmap(category.id, self.year)
        self.heatmap_frame.draw(
            lambda fig: chart_factory.heatmap_calendar(
                fig, day_minutes, self.year, category.color, style,
                f"{category.name} — {self.year}"))

        # Summary cards, scoped to the same year as the heatmap.
        stats = self.data.category_summary_stats(
            category.id, f"{self.year:04d}-01-01", f"{self.year:04d}-12-31")
        self._cards["total"].update_values(stats.total_label, accent=category.color)
        self._cards["active"].update_values(str(stats.active_days), accent=category.color)
        self._cards["streak"].update_values(
            str(stats.current_streak_days),
            subtitle="day" if stats.current_streak_days == 1 else "days",
            accent=category.color)
        best_subtitle = (time_utils.fmt_short_date(stats.best_day_date)
                         if stats.best_day_date else "")
        self._cards["best"].update_values(stats.best_day_label, subtitle=best_subtitle,
                                          accent=category.color)
        self._cards["avg"].update_values(stats.avg_label, accent=category.color)

        # Weekday pattern, tinted with the category's own color.
        weekday = self.data.category_weekday_pattern(category.id, n_weeks=12)
        weekday.colors = [category.color] * len(weekday.values)
        self.weekday_frame.draw(
            lambda fig: chart_factory.bar_chart(
                fig, weekday, style, f"{category.name} by weekday (avg hours)"))

    def _show_empty(self) -> None:
        style = theme.chart_style()
        self.heatmap_frame.draw(
            lambda fig: chart_factory.heatmap_calendar(fig, {}, self.year, theme.ACCENT[1], style, ""))
        for card in self._cards.values():
            card.update_values("—")
        self.weekday_frame.draw(lambda fig: chart_factory.bar_chart(fig, Series(), style, ""))
