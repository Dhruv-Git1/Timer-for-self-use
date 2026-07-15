"""
The search screen.

Find past sessions by any mix of a keyword (matched inside the notes), a
category, and a date. Leave a filter blank to ignore it — an empty search lists
your whole history, newest first. Click a result to open it for editing.
"""

from __future__ import annotations

import customtkinter as ctk

from app.ui import theme
from app.ui.views.base_view import BaseView
from app.ui.widgets.time_entry_form import TimeEntryForm
from app.utils import time_utils

_ALL = "All categories"


class SearchView(BaseView):
    title = "Search"

    def __init__(self, master, context) -> None:
        super().__init__(master, context)
        self._build()

    def _build(self) -> None:
        ctk.CTkLabel(self, text="Search",
                     font=ctk.CTkFont(size=26, weight="bold")).pack(
            anchor="w", padx=24, pady=(20, 8))

        # Filter bar.
        filters = ctk.CTkFrame(self, fg_color=theme.CARD_COLOR, corner_radius=10)
        filters.pack(fill="x", padx=24, pady=(0, 8))

        inner = ctk.CTkFrame(filters, fg_color="transparent")
        inner.pack(fill="x", padx=12, pady=12)

        self.keyword_var = ctk.StringVar()
        kw = ctk.CTkEntry(inner, textvariable=self.keyword_var,
                          placeholder_text="Keyword in notes (e.g. Cache)", width=240)
        kw.pack(side="left")
        kw.bind("<Return>", lambda _e: self.refresh())

        self.category_var = ctk.StringVar(value=_ALL)
        self._names = [_ALL] + [c.name for c in
                                self.ctx.category_service.list_categories(include_archived=True)]
        ctk.CTkOptionMenu(inner, values=self._names,
                          variable=self.category_var).pack(side="left", padx=8)

        self.date_var = ctk.StringVar()
        ctk.CTkEntry(inner, textvariable=self.date_var,
                     placeholder_text="Date YYYY-MM-DD", width=140).pack(side="left")

        ctk.CTkButton(inner, text="Search", width=90,
                      command=self.refresh).pack(side="left", padx=8)
        ctk.CTkButton(inner, text="Clear", width=70, fg_color=theme.NEUTRAL_BTN,
                      hover_color=theme.NEUTRAL_BTN_HOVER, text_color=("gray10", "gray90"),
                      command=self._clear).pack(side="left")

        self.count_label = ctk.CTkLabel(self, text="", text_color=theme.MUTED_TEXT)
        self.count_label.pack(anchor="w", padx=24)

        self.results = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.results.pack(fill="both", expand=True, padx=24, pady=(4, 20))

    def _clear(self) -> None:
        self.keyword_var.set("")
        self.category_var.set(_ALL)
        self.date_var.set("")
        self.refresh()

    def _category_id(self):
        name = self.category_var.get()
        if name == _ALL:
            return None
        for c in self.ctx.category_service.list_categories(include_archived=True):
            if c.name == name:
                return c.id
        return None

    def refresh(self) -> None:
        # Keep the category dropdown current in case categories changed.
        results = self.ctx.search_service.search(
            keyword=self.keyword_var.get(),
            category_id=self._category_id(),
            date_str=self.date_var.get().strip() or None,
        )

        for child in self.results.winfo_children():
            child.destroy()

        self.count_label.configure(
            text=f"{len(results)} result{'' if len(results) == 1 else 's'}")

        if not results:
            ctk.CTkLabel(self.results, text="No matching entries.",
                         text_color=theme.MUTED_TEXT).pack(anchor="w", pady=16)
            return

        for entry in results:
            row = ctk.CTkFrame(self.results, fg_color=theme.CARD_COLOR, corner_radius=8)
            row.pack(fill="x", pady=3)

            left = ctk.CTkFrame(row, fg_color="transparent")
            left.pack(side="left", fill="x", expand=True, padx=12, pady=8)
            weekday = time_utils.weekday_name(entry.log_date)
            ctk.CTkLabel(left,
                         text=f"{entry.log_date} ({weekday})  •  "
                              f"{entry.start_time}–{entry.end_time}  •  {entry.duration_label}",
                         anchor="w", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w")
            meta = ctk.CTkFrame(left, fg_color="transparent")
            meta.pack(anchor="w", fill="x")
            ctk.CTkLabel(meta, text="●", text_color=entry.category_color,
                         font=ctk.CTkFont(size=13)).pack(side="left")
            ctk.CTkLabel(meta, text=f" {entry.category_name}   {entry.notes}",
                         anchor="w", text_color=theme.MUTED_TEXT).pack(side="left")

            ctk.CTkButton(row, text="✎  Edit", width=70, fg_color=theme.NEUTRAL_BTN,
                          hover_color=theme.NEUTRAL_BTN_HOVER, text_color=("gray10", "gray90"),
                          command=lambda e=entry: self._edit(e)).pack(side="right", padx=10)

    def _edit(self, entry) -> None:
        TimeEntryForm(self, self.ctx, on_saved=self.refresh, entry=entry)
