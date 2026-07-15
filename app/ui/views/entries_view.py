"""
The entries screen.

Lists everything you logged on a chosen day and lets you add, edit or delete
entries. A ‹ Today › navigator moves between days, "Add entry" opens the form,
and "Duplicate previous day" clones yesterday's log onto the day you are viewing.
Entries that overlap another session on the same day get a small ⚠ so you can
spot an accidental double-log.
"""

from __future__ import annotations

import customtkinter as ctk

from app.ui import theme
from app.ui.views.base_view import BaseView
from app.ui.widgets.confirm_dialog import ask_confirm
from app.ui.widgets.time_entry_form import TimeEntryForm
from app.utils import time_utils


class EntriesView(BaseView):
    title = "Today's Entries"

    def __init__(self, master, context) -> None:
        super().__init__(master, context)
        self.current_date = time_utils.today_str()
        self._build()

    def _build(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(20, 8))
        ctk.CTkLabel(header, text="Entries",
                     font=ctk.CTkFont(size=26, weight="bold")).pack(side="left")

        nav = ctk.CTkFrame(header, fg_color="transparent")
        nav.pack(side="right")
        ctk.CTkButton(nav, text="‹", width=36, command=self._prev_day).pack(side="left")
        self.date_label = ctk.CTkLabel(nav, text="", width=210,
                                       font=ctk.CTkFont(size=15, weight="bold"))
        self.date_label.pack(side="left", padx=6)
        ctk.CTkButton(nav, text="›", width=36, command=self._next_day).pack(side="left")
        ctk.CTkButton(nav, text="Today", width=60, fg_color=theme.NEUTRAL_BTN,
                      hover_color=theme.NEUTRAL_BTN_HOVER, text_color=("gray10", "gray90"),
                      command=self._go_today).pack(side="left", padx=(8, 0))

        # Action buttons.
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", padx=24, pady=(0, 8))
        ctk.CTkButton(actions, text="➕  Add entry", command=self._add_entry).pack(side="left")
        ctk.CTkButton(actions, text="📋  Duplicate previous day", fg_color=theme.NEUTRAL_BTN,
                      hover_color=theme.NEUTRAL_BTN_HOVER, text_color=("gray10", "gray90"),
                      command=self._duplicate_prev).pack(side="left", padx=8)
        self.day_total = ctk.CTkLabel(actions, text="", text_color=theme.MUTED_TEXT,
                                      font=ctk.CTkFont(size=13))
        self.day_total.pack(side="right")

        # The list of entries.
        self.list_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.list_frame.pack(fill="both", expand=True, padx=24, pady=(0, 20))

    # -- Navigation ----------------------------------------------------- #
    def _prev_day(self) -> None:
        self.current_date = time_utils.add_days(self.current_date, -1)
        self.refresh()

    def _next_day(self) -> None:
        self.current_date = time_utils.add_days(self.current_date, 1)
        self.refresh()

    def _go_today(self) -> None:
        self.current_date = time_utils.today_str()
        self.refresh()

    # -- Actions -------------------------------------------------------- #
    def _add_entry(self) -> None:
        TimeEntryForm(self, self.ctx, on_saved=self.refresh,
                      default_date=self.current_date)

    def _edit_entry(self, entry) -> None:
        TimeEntryForm(self, self.ctx, on_saved=self.refresh, entry=entry)

    def _delete_entry(self, entry) -> None:
        if ask_confirm(self, "Delete entry",
                       f"Delete the {entry.category_name} entry "
                       f"{entry.start_time}–{entry.end_time}? This cannot be undone."):
            self.ctx.entry_service.delete_entry(entry.id)
            self.refresh()

    def _duplicate_prev(self) -> None:
        prev = time_utils.add_days(self.current_date, -1)
        ok, msg, _ = self.ctx.entry_service.duplicate_day(prev, self.current_date)
        # Show the outcome briefly in the day-total label as lightweight feedback.
        if ok:
            self.refresh()
        else:
            self.day_total.configure(text=msg)

    # -- Refresh -------------------------------------------------------- #
    def refresh(self) -> None:
        weekday = time_utils.weekday_name(self.current_date)
        suffix = "  (Today)" if self.current_date == time_utils.today_str() else ""
        self.date_label.configure(text=f"{weekday}, {self.current_date}{suffix}")

        for child in self.list_frame.winfo_children():
            child.destroy()

        entries = self.ctx.entry_service.entries_for_date(self.current_date)
        overlaps = self.ctx.entry_service.overlapping_ids(self.current_date)

        total = sum(e.duration_minutes for e in entries)
        self.day_total.configure(
            text=f"{len(entries)} entr{'y' if len(entries) == 1 else 'ies'} • "
                 f"{time_utils.fmt_duration(total)} recorded"
            if entries else "No entries yet")

        if not entries:
            ctk.CTkLabel(self.list_frame,
                         text="Nothing logged for this day.\nClick “Add entry” to start.",
                         text_color=theme.MUTED_TEXT, justify="left").pack(anchor="w", pady=20)
            return

        for entry in entries:
            self._entry_row(entry, entry.id in overlaps)

    def _entry_row(self, entry, is_overlap: bool) -> None:
        row = ctk.CTkFrame(self.list_frame, fg_color=theme.CARD_COLOR, corner_radius=8)
        row.pack(fill="x", pady=3)

        # Time span + duration.
        time_cell = ctk.CTkFrame(row, fg_color="transparent", width=150)
        time_cell.pack(side="left", padx=(12, 0), pady=10)
        time_cell.pack_propagate(False)
        span = f"{entry.start_time} – {entry.end_time}"
        if entry.crosses_midnight:
            span += " ⏭"
        ctk.CTkLabel(time_cell, text=span, anchor="w",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(time_cell, text=entry.duration_label, anchor="w",
                     text_color=theme.MUTED_TEXT, font=ctk.CTkFont(size=12)).pack(anchor="w")

        # Category chip.
        cat_cell = ctk.CTkFrame(row, fg_color="transparent", width=140)
        cat_cell.pack(side="left", pady=10)
        cat_cell.pack_propagate(False)
        ctk.CTkLabel(cat_cell, text="●", text_color=entry.category_color,
                     font=ctk.CTkFont(size=16)).pack(side="left")
        ctk.CTkLabel(cat_cell, text=f" {entry.category_name}", anchor="w").pack(side="left")

        # Notes (and overlap warning).
        note_text = entry.notes or ""
        if is_overlap:
            note_text = "⚠ overlaps another entry   " + note_text
        ctk.CTkLabel(row, text=note_text, anchor="w", justify="left",
                     text_color=("#B25A00" if is_overlap else theme.MUTED_TEXT),
                     wraplength=320).pack(side="left", fill="x", expand=True, padx=8)

        # Edit / delete.
        ctk.CTkButton(row, text="🗑", width=36, fg_color="transparent",
                      hover_color=("gray80", "gray25"), text_color=("gray10", "gray90"),
                      command=lambda e=entry: self._delete_entry(e)).pack(side="right", padx=(0, 10))
        ctk.CTkButton(row, text="✎", width=36, fg_color="transparent",
                      hover_color=("gray80", "gray25"), text_color=("gray10", "gray90"),
                      command=lambda e=entry: self._edit_entry(e)).pack(side="right")
