"""
The statistics screen.

Pick a period — a single day, a week, a month or a year — and see the aggregate
numbers for it: totals, averages, your longest session, streaks, the most and
least productive weekday, and a breakdown of time by category. ‹ › move between
periods of the chosen kind.
"""

from __future__ import annotations

from datetime import date

import customtkinter as ctk

from app.ui import theme
from app.ui.views.base_view import BaseView
from app.ui.widgets.stat_card import StatCard
from app.utils import time_utils


class StatisticsView(BaseView):
    title = "Statistics"

    def __init__(self, master, context) -> None:
        super().__init__(master, context)
        self.period = "Weekly"
        self.anchor = time_utils.today_str()
        self._build()

    def _build(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(20, 8))
        ctk.CTkLabel(header, text="Statistics",
                     font=ctk.CTkFont(size=26, weight="bold")).pack(side="left")

        self.period_selector = ctk.CTkSegmentedButton(
            header, values=["Daily", "Weekly", "Monthly", "Yearly"],
            command=self._change_period)
        self.period_selector.set(self.period)
        self.period_selector.pack(side="right")

        nav = ctk.CTkFrame(self, fg_color="transparent")
        nav.pack(fill="x", padx=24, pady=(0, 8))
        ctk.CTkButton(nav, text="‹", width=36, command=self._prev).pack(side="left")
        self.period_label = ctk.CTkLabel(nav, text="", width=240,
                                         font=ctk.CTkFont(size=15, weight="bold"))
        self.period_label.pack(side="left", padx=6)
        ctk.CTkButton(nav, text="›", width=36, command=self._next).pack(side="left")

        # A scrollable body holds the cards and the breakdown so nothing gets cut
        # off on smaller windows.
        self.body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=24, pady=(0, 20))

    # -- Period control ------------------------------------------------- #
    def _change_period(self, value: str) -> None:
        self.period = value
        self.refresh()

    def _shift_month(self, months: int) -> None:
        d = time_utils.to_date(self.anchor)
        month_index = d.year * 12 + (d.month - 1) + months
        year, month = divmod(month_index, 12)
        # Clamp the day so shifting from the 31st into a short month is safe.
        import calendar as _cal
        day = min(d.day, _cal.monthrange(year, month + 1)[1])
        self.anchor = date(year, month + 1, day).strftime("%Y-%m-%d")

    def _prev(self) -> None:
        self._step(-1)

    def _next(self) -> None:
        self._step(1)

    def _step(self, direction: int) -> None:
        if self.period == "Daily":
            self.anchor = time_utils.add_days(self.anchor, direction)
        elif self.period == "Weekly":
            self.anchor = time_utils.add_days(self.anchor, 7 * direction)
        elif self.period == "Monthly":
            self._shift_month(direction)
        else:  # Yearly
            self._shift_month(12 * direction)
        self.refresh()

    # -- Refresh -------------------------------------------------------- #
    def _current_stats(self):
        d = time_utils.to_date(self.anchor)
        if self.period == "Daily":
            return self.ctx.stats_service.daily(self.anchor)
        if self.period == "Weekly":
            return self.ctx.stats_service.weekly(self.anchor)
        if self.period == "Monthly":
            return self.ctx.stats_service.monthly(d.year, d.month)
        return self.ctx.stats_service.yearly(d.year)

    def refresh(self) -> None:
        stats = self._current_stats()
        self.period_label.configure(text=stats.label)

        for child in self.body.winfo_children():
            child.destroy()

        # Summary cards.
        cards = ctk.CTkFrame(self.body, fg_color="transparent")
        cards.pack(fill="x")
        for col in range(4):
            cards.grid_columnconfigure(col, weight=1, uniform="stat")

        def hours(minutes) -> str:
            return time_utils.fmt_duration(int(round(minutes)))

        specs = [
            ("Productive Total", hours(stats.total_productive_minutes), "#2E9E5B"),
            ("Recorded Total", hours(stats.total_recorded_minutes), "#3B82F6"),
            ("Active Days", str(stats.active_days), "#14B8A6"),
            ("Sessions", str(stats.session_count), "#EC4899"),
            ("Avg Session", hours(stats.avg_session_minutes) if stats.session_count else "—", "#8B5CF6"),
            ("Avg Start Time", stats.avg_start_time, "#F59E0B"),
            ("Longest Session", hours(stats.longest_session_minutes) if stats.longest_session_minutes else "—", "#EF4444"),
            ("Avg / Active Day", hours(stats.avg_productive_minutes_per_active_day) if stats.active_days else "—", "#2E9E5B"),
        ]
        for i, (label, value, color) in enumerate(specs):
            card = StatCard(cards, title=label, value=value, accent=color)
            card.grid(row=i // 4, column=i % 4, padx=6, pady=6, sticky="ew")

        # Streaks + weekday highlights as a small info strip.
        info = ctk.CTkFrame(self.body, fg_color=theme.CARD_COLOR, corner_radius=10)
        info.pack(fill="x", pady=(10, 4))
        info_text = (f"🔥 Current streak: {stats.current_streak} days      "
                     f"🏆 Longest streak: {stats.longest_streak} days      "
                     f"📈 Most productive: {stats.most_productive_weekday}      "
                     f"📉 Least productive: {stats.least_productive_weekday}")
        ctk.CTkLabel(info, text=info_text, anchor="w").pack(anchor="w", padx=16, pady=12)

        # Category breakdown table.
        ctk.CTkLabel(self.body, text="Time by category",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(
            anchor="w", pady=(14, 4))
        self._category_table(stats)

    def _category_table(self, stats) -> None:
        if not stats.minutes_by_category:
            ctk.CTkLabel(self.body, text="No activity recorded in this period.",
                         text_color=theme.MUTED_TEXT).pack(anchor="w", pady=8)
            return

        total = sum(stats.minutes_by_category.values()) or 1
        ordered = sorted(stats.minutes_by_category.items(),
                         key=lambda kv: kv[1], reverse=True)
        # Look up each category's color for the dot.
        colors = {c.name: c.color for c in
                  self.ctx.category_service.list_categories(include_archived=True)}

        for name, minutes in ordered:
            row = ctk.CTkFrame(self.body, fg_color=theme.CARD_COLOR, corner_radius=8)
            row.pack(fill="x", pady=3)
            ctk.CTkLabel(row, text="●", text_color=colors.get(name, "#888888"),
                         font=ctk.CTkFont(size=16)).pack(side="left", padx=(12, 4), pady=8)
            ctk.CTkLabel(row, text=name, width=160, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=time_utils.fmt_duration(minutes), width=100,
                         anchor="w").pack(side="left")
            share = minutes / total
            bar = ctk.CTkProgressBar(row, width=200)
            bar.set(share)
            bar.pack(side="left", padx=8)
            ctk.CTkLabel(row, text=f"{share * 100:.0f}%", width=50,
                         text_color=theme.MUTED_TEXT).pack(side="left")
