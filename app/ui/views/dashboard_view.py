"""
The daily dashboard.

Shows one day at a glance: a headline status (Complete / Partial / Failed), a row
of summary cards (productive time, recorded time, completion, streak, longest
session, sessions), and a per-category table comparing what you did against your
goals. A small ‹ Today › navigator moves between days.
"""

from __future__ import annotations

import customtkinter as ctk

from app.ui import theme
from app.ui.views.base_view import BaseView
from app.ui.widgets.stat_card import StatCard
from app.utils import time_utils


class DashboardView(BaseView):
    title = "Dashboard"

    def __init__(self, master, context) -> None:
        super().__init__(master, context)
        self.current_date = time_utils.today_str()
        self._cards: dict[str, StatCard] = {}
        self._build()

    # ------------------------------------------------------------------ #
    # Static layout (built once)
    # ------------------------------------------------------------------ #
    def _build(self) -> None:
        # Header row: title on the left, date navigator on the right.
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(20, 8))

        ctk.CTkLabel(header, text="Dashboard",
                     font=ctk.CTkFont(size=26, weight="bold")).pack(side="left")

        nav = ctk.CTkFrame(header, fg_color="transparent")
        nav.pack(side="right")
        ctk.CTkButton(nav, text="‹", width=36, command=self._prev_day).pack(side="left")
        self.date_label = ctk.CTkLabel(nav, text="", width=220,
                                       font=ctk.CTkFont(size=15, weight="bold"))
        self.date_label.pack(side="left", padx=6)
        ctk.CTkButton(nav, text="›", width=36, command=self._next_day).pack(side="left")
        ctk.CTkButton(nav, text="Today", width=64, fg_color=theme.NEUTRAL_BTN,
                      hover_color=theme.NEUTRAL_BTN_HOVER, text_color=("gray10", "gray90"),
                      command=self._go_today).pack(side="left", padx=(8, 0))

        # A big banner that turns green/amber/red with the day's status.
        self.status_banner = ctk.CTkFrame(self, height=64, corner_radius=12)
        self.status_banner.pack(fill="x", padx=24, pady=(8, 12))
        self.status_banner.pack_propagate(False)
        self.status_text = ctk.CTkLabel(self.status_banner, text="",
                                        font=ctk.CTkFont(size=20, weight="bold"),
                                        text_color="white")
        self.status_text.pack(side="left", padx=20)
        self.completion_text = ctk.CTkLabel(self.status_banner, text="",
                                            font=ctk.CTkFont(size=15),
                                            text_color="white")
        self.completion_text.pack(side="right", padx=20)

        # Summary cards in a responsive grid (4 across).
        cards = ctk.CTkFrame(self, fg_color="transparent")
        cards.pack(fill="x", padx=24, pady=4)
        for col in range(4):
            cards.grid_columnconfigure(col, weight=1, uniform="cards")

        specs = [
            ("productive", "Productive Time", "#2E9E5B"),
            ("recorded", "Recorded Time", "#3B82F6"),
            ("streak", "Current Streak", "#E0A100"),
            ("longest", "Longest Session", "#8B5CF6"),
            ("sessions", "Sessions", "#EC4899"),
            ("completion", "Completion", "#14B8A6"),
        ]
        for index, (key, label, color) in enumerate(specs):
            card = StatCard(cards, title=label, accent=color)
            card.grid(row=index // 4, column=index % 4, padx=6, pady=6, sticky="ew")
            self._cards[key] = card

        # Per-category target-vs-actual table.
        ctk.CTkLabel(self, text="Goals for the day",
                     font=ctk.CTkFont(size=17, weight="bold")).pack(
            anchor="w", padx=24, pady=(14, 4))
        self.table = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.table.pack(fill="both", expand=True, padx=24, pady=(0, 20))

    # ------------------------------------------------------------------ #
    # Date navigation
    # ------------------------------------------------------------------ #
    def _prev_day(self) -> None:
        self.current_date = time_utils.add_days(self.current_date, -1)
        self.refresh()

    def _next_day(self) -> None:
        self.current_date = time_utils.add_days(self.current_date, 1)
        self.refresh()

    def _go_today(self) -> None:
        self.current_date = time_utils.today_str()
        self.refresh()

    # ------------------------------------------------------------------ #
    # Refresh (rebuild dynamic parts from current data)
    # ------------------------------------------------------------------ #
    def refresh(self) -> None:
        summary = self.ctx.dashboard_service.build_summary(self.current_date)

        # Date label, with a friendly "Today" hint.
        weekday = time_utils.weekday_name(self.current_date)
        suffix = "  (Today)" if self.current_date == time_utils.today_str() else ""
        self.date_label.configure(text=f"{weekday}, {self.current_date}{suffix}")

        # Status banner.
        status = summary.status
        banner_text = {
            "Complete": "✅  Day Complete",
            "Partial": "🟡  Partially Complete",
            "Failed": "❌  Day Failed",
            "Neutral": "•  No goal set for this day",
        }[status.label]
        self.status_banner.configure(fg_color=status.color)
        self.status_text.configure(text=banner_text)
        if summary.total_target_minutes > 0:
            self.completion_text.configure(
                text=f"{summary.completion_pct:.0f}% of "
                     f"{time_utils.fmt_duration(summary.total_target_minutes)} goal")
        else:
            self.completion_text.configure(text="")

        # Summary cards.
        self._cards["productive"].update_values(
            summary.productive_label, subtitle="counts toward goals")
        self._cards["recorded"].update_values(
            summary.recorded_label, subtitle="all activity")
        self._cards["streak"].update_values(
            str(summary.current_streak),
            subtitle="day" if summary.current_streak == 1 else "days")
        self._cards["longest"].update_values(
            summary.longest_session_label, subtitle="single session")
        self._cards["sessions"].update_values(
            str(summary.session_count), subtitle="logged today")
        self._cards["completion"].update_values(
            f"{summary.completion_pct:.0f}%", subtitle="of daily goal")

        self._rebuild_table(summary)

    def _rebuild_table(self, summary) -> None:
        # Clear any previous rows.
        for child in self.table.winfo_children():
            child.destroy()

        headers = ["Category", "Target", "Actual", "Difference", "Progress", "Status"]
        widths = [200, 90, 90, 110, 160, 90]
        head = ctk.CTkFrame(self.table, fg_color="transparent")
        head.pack(fill="x", pady=(0, 4))
        for text, width in zip(headers, widths):
            ctk.CTkLabel(head, text=text, width=width, anchor="w",
                         font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=theme.MUTED_TEXT).pack(side="left")

        if not summary.progress:
            ctk.CTkLabel(self.table, text="No goals or activity for this day yet.",
                         text_color=theme.MUTED_TEXT).pack(anchor="w", pady=10)
            return

        for prog in summary.progress:
            row = ctk.CTkFrame(self.table, fg_color=theme.CARD_COLOR, corner_radius=8)
            row.pack(fill="x", pady=3)

            # Category name with its color dot.
            name_cell = ctk.CTkFrame(row, fg_color="transparent", width=200)
            name_cell.pack(side="left", padx=(10, 0), pady=8)
            name_cell.pack_propagate(False)
            ctk.CTkLabel(name_cell, text="●", text_color=prog.color,
                         font=ctk.CTkFont(size=16)).pack(side="left")
            ctk.CTkLabel(name_cell, text=f" {prog.name}", anchor="w").pack(side="left")

            ctk.CTkLabel(row, text=prog.target_label, width=90, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=prog.actual_label, width=90, anchor="w").pack(side="left")

            diff_color = "#2E9E5B" if prog.difference_minutes >= 0 else "#D0463B"
            ctk.CTkLabel(row, text=prog.difference_label if prog.target_minutes else "—",
                         width=110, anchor="w", text_color=diff_color).pack(side="left")

            # A little progress bar toward the goal.
            bar_cell = ctk.CTkFrame(row, fg_color="transparent", width=160)
            bar_cell.pack(side="left")
            bar_cell.pack_propagate(False)
            bar = ctk.CTkProgressBar(bar_cell, width=130)
            bar.set(prog.completion_pct / 100)
            bar.pack(side="left", pady=8)

            if prog.target_minutes == 0:
                status_txt, status_col = "—", theme.MUTED_TEXT
            elif prog.is_met:
                status_txt, status_col = "✓ Met", "#2E9E5B"
            else:
                status_txt, status_col = "✗ Short", "#D0463B"
            ctk.CTkLabel(row, text=status_txt, width=90, anchor="w",
                         text_color=status_col).pack(side="left")
