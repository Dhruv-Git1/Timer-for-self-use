"""
The calendar screen.

A month-at-a-glance grid where each day is colored by how it went: green for
Complete (every goal met), amber for Partial, red for Failed, and grey for days
with no goals, no data, or still in the future. Click any day to see the entries
you logged that day in the panel on the right.
"""

from __future__ import annotations

import calendar as _calendar

import customtkinter as ctk

from app.models.stats import DayStatus
from app.ui import theme
from app.ui.views.base_view import BaseView
from app.utils import time_utils

_WEEKDAY_HEADERS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


class CalendarView(BaseView):
    title = "Calendar"

    def __init__(self, master, context) -> None:
        super().__init__(master, context)
        today = time_utils.to_date(time_utils.today_str())
        self.year, self.month = today.year, today.month
        self.selected_date: str | None = None
        self._build()

    def _build(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(20, 8))
        ctk.CTkLabel(header, text="Calendar",
                     font=ctk.CTkFont(size=26, weight="bold")).pack(side="left")

        nav = ctk.CTkFrame(header, fg_color="transparent")
        nav.pack(side="right")
        ctk.CTkButton(nav, text="‹", width=36, command=self._prev_month).pack(side="left")
        self.month_label = ctk.CTkLabel(nav, text="", width=180,
                                        font=ctk.CTkFont(size=16, weight="bold"))
        self.month_label.pack(side="left", padx=6)
        ctk.CTkButton(nav, text="›", width=36, command=self._next_month).pack(side="left")
        ctk.CTkButton(nav, text="This month", width=90, fg_color=theme.NEUTRAL_BTN,
                      hover_color=theme.NEUTRAL_BTN_HOVER, text_color=("gray10", "gray90"),
                      command=self._go_today).pack(side="left", padx=(8, 0))

        # Legend.
        legend = ctk.CTkFrame(self, fg_color="transparent")
        legend.pack(fill="x", padx=24, pady=(0, 8))
        for status in (DayStatus.COMPLETE, DayStatus.PARTIAL,
                       DayStatus.FAILED, DayStatus.NEUTRAL):
            chip = ctk.CTkFrame(legend, fg_color="transparent")
            chip.pack(side="left", padx=(0, 16))
            ctk.CTkLabel(chip, text="■", text_color=status.color,
                         font=ctk.CTkFont(size=16)).pack(side="left")
            meaning = {"Complete": "Complete", "Partial": "Partial",
                       "Failed": "Failed", "Neutral": "No goal / no data"}[status.label]
            ctk.CTkLabel(chip, text=f" {meaning}",
                         text_color=theme.MUTED_TEXT).pack(side="left")

        # Body: calendar grid on the left, day detail on the right.
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=24, pady=(0, 20))
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=2)
        body.grid_rowconfigure(0, weight=1)

        self.grid_frame = ctk.CTkFrame(body, fg_color="transparent")
        self.grid_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 12))

        self.detail = ctk.CTkScrollableFrame(body, fg_color=theme.CARD_COLOR,
                                             corner_radius=12)
        self.detail.grid(row=0, column=1, sticky="nsew")

    # -- Navigation ----------------------------------------------------- #
    def _prev_month(self) -> None:
        self.month -= 1
        if self.month == 0:
            self.month, self.year = 12, self.year - 1
        self.refresh()

    def _next_month(self) -> None:
        self.month += 1
        if self.month == 13:
            self.month, self.year = 1, self.year + 1
        self.refresh()

    def _go_today(self) -> None:
        today = time_utils.to_date(time_utils.today_str())
        self.year, self.month = today.year, today.month
        self.refresh()

    # -- Refresh -------------------------------------------------------- #
    def refresh(self) -> None:
        self.month_label.configure(
            text=f"{_calendar.month_name[self.month]} {self.year}")

        for child in self.grid_frame.winfo_children():
            child.destroy()

        # Weekday header row.
        for col in range(7):
            self.grid_frame.grid_columnconfigure(col, weight=1, uniform="cal")
            ctk.CTkLabel(self.grid_frame, text=_WEEKDAY_HEADERS[col],
                         text_color=theme.MUTED_TEXT,
                         font=ctk.CTkFont(size=12, weight="bold")).grid(
                row=0, column=col, pady=(0, 4))

        status_map = self.ctx.calendar_service.month_status(self.year, self.month)
        matrix = self.ctx.calendar_service.month_matrix(self.year, self.month)
        today = time_utils.today_str()

        for r, week in enumerate(matrix, start=1):
            self.grid_frame.grid_rowconfigure(r, weight=1, uniform="calrow")
            for c, day in enumerate(week):
                if day == 0:
                    continue  # padding day from a neighbouring month
                date_str = f"{self.year:04d}-{self.month:02d}-{day:02d}"
                status = status_map.get(date_str, DayStatus.NEUTRAL)
                # Highlight today with a visible border.
                border = 2 if date_str == today else 0
                cell = ctk.CTkButton(
                    self.grid_frame, text=str(day), fg_color=status.color,
                    hover_color=status.color, text_color="white",
                    border_width=border, border_color=theme.ACCENT,
                    font=ctk.CTkFont(size=14, weight="bold"), height=46,
                    command=lambda d=date_str: self._select_day(d),
                )
                cell.grid(row=r, column=c, padx=2, pady=2, sticky="nsew")

        # Keep any previously selected day shown, else prompt.
        if self.selected_date and self.selected_date.startswith(
                f"{self.year:04d}-{self.month:02d}"):
            self._select_day(self.selected_date)
        else:
            self._show_detail_placeholder()

    # -- Day detail ----------------------------------------------------- #
    def _show_detail_placeholder(self) -> None:
        for child in self.detail.winfo_children():
            child.destroy()
        ctk.CTkLabel(self.detail, text="Click a day to see its entries.",
                     text_color=theme.MUTED_TEXT).pack(anchor="w", padx=16, pady=16)

    def _select_day(self, date_str: str) -> None:
        self.selected_date = date_str
        for child in self.detail.winfo_children():
            child.destroy()

        weekday = time_utils.weekday_name(date_str)
        ctk.CTkLabel(self.detail, text=f"{weekday}, {date_str}",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(
            anchor="w", padx=16, pady=(16, 8))

        summary = self.ctx.dashboard_service.build_summary(date_str)
        ctk.CTkLabel(self.detail,
                     text=f"{summary.status.label}  •  "
                          f"{summary.productive_label} productive  •  "
                          f"{summary.session_count} sessions",
                     text_color=summary.status.color).pack(anchor="w", padx=16, pady=(0, 8))

        entries = self.ctx.calendar_service.day_entries(date_str)
        if not entries:
            ctk.CTkLabel(self.detail, text="No entries logged.",
                         text_color=theme.MUTED_TEXT).pack(anchor="w", padx=16, pady=8)
            return

        for entry in entries:
            item = ctk.CTkFrame(self.detail, fg_color="transparent")
            item.pack(fill="x", padx=12, pady=3)
            ctk.CTkLabel(item, text="●", text_color=entry.category_color,
                         font=ctk.CTkFont(size=14)).pack(side="left")
            ctk.CTkLabel(item,
                         text=f" {entry.start_time}–{entry.end_time}  "
                              f"{entry.category_name}  ({entry.duration_label})",
                         anchor="w", font=ctk.CTkFont(size=12)).pack(side="left")
