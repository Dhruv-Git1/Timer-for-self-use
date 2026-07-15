"""
The add / edit time-entry dialog.

A modal form for logging a session or editing one you already logged. As you
type the start and end times it shows the calculated duration live (and quietly
understands an overnight session, where the end time is earlier than the start).
Saving runs the entry through the same validation the rest of the app uses, so a
bad time can never reach the database — you just get a gentle red hint instead.
"""

from __future__ import annotations

from typing import Callable, Optional

import customtkinter as ctk

from app.models.time_entry import TimeEntry
from app.services.context import AppContext
from app.ui import theme
from app.utils import time_utils


class TimeEntryForm(ctk.CTkToplevel):
    """Create a new entry, or edit an existing one, in a modal window."""

    def __init__(
        self,
        parent,
        context: AppContext,
        on_saved: Callable[[], None],
        entry: Optional[TimeEntry] = None,
        default_date: Optional[str] = None,
    ) -> None:
        super().__init__(parent)
        self.ctx = context
        self.on_saved = on_saved
        self.entry = entry              # None => add mode
        self.is_edit = entry is not None

        self.title("Edit entry" if self.is_edit else "Add entry")
        self.geometry("420x520")
        self.resizable(False, False)

        # Keep the popup in front and focused on Windows (see confirm_dialog).
        self.transient(parent)
        self.lift()
        self.after(10, self.grab_set)
        self.after(20, self.focus_force)

        # Build the category name -> id lookup for the dropdown. In edit mode we
        # make sure the entry's own category is present even if it was archived.
        self._categories = self.ctx.category_service.list_categories()
        self._name_to_id = {c.name: c.id for c in self._categories}
        if self.is_edit and entry.category_name not in self._name_to_id:
            self._name_to_id[entry.category_name] = entry.category_id

        self._build_form(default_date)

    # ------------------------------------------------------------------ #
    # Layout
    # ------------------------------------------------------------------ #
    def _build_form(self, default_date: Optional[str]) -> None:
        pad = {"padx": 20}
        wrap = ctk.CTkFrame(self, fg_color="transparent")
        wrap.pack(fill="both", expand=True, pady=16)

        def label(text: str) -> None:
            ctk.CTkLabel(wrap, text=text, anchor="w",
                         font=ctk.CTkFont(size=13, weight="bold")).pack(
                fill="x", pady=(10, 2), **pad)

        # Date
        label("Date  (YYYY-MM-DD)")
        self.date_var = ctk.StringVar(
            value=(self.entry.log_date if self.is_edit
                   else (default_date or time_utils.today_str()))
        )
        ctk.CTkEntry(wrap, textvariable=self.date_var).pack(fill="x", **pad)

        # Start / end times sit side by side.
        times = ctk.CTkFrame(wrap, fg_color="transparent")
        times.pack(fill="x", pady=(10, 0), **pad)
        times.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(times, text="Start  (HH:MM)", anchor="w",
                     font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 2))
        ctk.CTkLabel(times, text="End  (HH:MM)", anchor="w",
                     font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=0, column=1, sticky="w", padx=(10, 0), pady=(0, 2))

        self.start_var = ctk.StringVar(value=self.entry.start_time if self.is_edit else "")
        self.end_var = ctk.StringVar(value=self.entry.end_time if self.is_edit else "")
        start_entry = ctk.CTkEntry(times, textvariable=self.start_var, placeholder_text="09:00")
        start_entry.grid(row=1, column=0, sticky="ew")
        end_entry = ctk.CTkEntry(times, textvariable=self.end_var, placeholder_text="11:30")
        end_entry.grid(row=1, column=1, sticky="ew", padx=(10, 0))

        # Recompute the live duration whenever a time changes.
        for var in (self.start_var, self.end_var, self.date_var):
            var.trace_add("write", lambda *_: self._update_duration())

        self.duration_label = ctk.CTkLabel(
            wrap, text="Duration: —", anchor="w",
            font=ctk.CTkFont(size=13), text_color="#3B82F6",
        )
        self.duration_label.pack(fill="x", pady=(6, 0), **pad)

        # Category
        label("Category")
        names = list(self._name_to_id.keys())
        self.category_var = ctk.StringVar(
            value=(self.entry.category_name if self.is_edit
                   else (names[0] if names else ""))
        )
        ctk.CTkOptionMenu(wrap, values=names, variable=self.category_var).pack(
            fill="x", **pad)

        # Notes
        label("Notes  (optional)")
        self.notes_box = ctk.CTkTextbox(wrap, height=90)
        self.notes_box.pack(fill="x", **pad)
        if self.is_edit and self.entry.notes:
            self.notes_box.insert("1.0", self.entry.notes)

        # Inline error message (hidden until needed).
        self.error_label = ctk.CTkLabel(
            wrap, text="", text_color="#D0463B", anchor="w",
            font=ctk.CTkFont(size=12), wraplength=360, justify="left",
        )
        self.error_label.pack(fill="x", pady=(8, 0), **pad)

        # Buttons
        buttons = ctk.CTkFrame(wrap, fg_color="transparent")
        buttons.pack(fill="x", side="bottom", pady=(10, 0), **pad)
        ctk.CTkButton(buttons, text="Cancel", width=100, fg_color=theme.NEUTRAL_BTN,
                      hover_color=theme.NEUTRAL_BTN_HOVER, text_color=("gray10", "gray90"),
                      command=self.destroy).pack(side="right", padx=(8, 0))
        ctk.CTkButton(buttons, text="Save", width=100, command=self._save).pack(side="right")

        self.bind("<Return>", lambda _e: self._save())
        self.bind("<Escape>", lambda _e: self.destroy())
        self._update_duration()

    # ------------------------------------------------------------------ #
    # Behaviour
    # ------------------------------------------------------------------ #
    def _update_duration(self) -> None:
        """Show the live duration, or a hint, as the times are typed."""
        try:
            _s, _e, minutes, crosses = time_utils.build_timestamps(
                self.date_var.get(), self.start_var.get(), self.end_var.get()
            )
            text = f"Duration: {time_utils.fmt_duration(minutes)}"
            if crosses:
                text += "  (crosses midnight → next day)"
            self.duration_label.configure(text=text, text_color="#3B82F6")
        except ValueError:
            self.duration_label.configure(text="Duration: —", text_color="gray")

    def _save(self) -> None:
        """Validate and persist, then close on success or show the problem."""
        category_name = self.category_var.get()
        category_id = self._name_to_id.get(category_name)
        if category_id is None:
            self.error_label.configure(text="Please choose a category.")
            return

        notes = self.notes_box.get("1.0", "end").strip()
        if self.is_edit:
            ok, msg, _ = self.ctx.entry_service.update_entry(
                self.entry.id, category_id, self.date_var.get(),
                self.start_var.get(), self.end_var.get(), notes,
            )
        else:
            ok, msg, _ = self.ctx.entry_service.add_entry(
                category_id, self.date_var.get(),
                self.start_var.get(), self.end_var.get(), notes,
            )

        if not ok:
            self.error_label.configure(text=msg)
            return
        self.on_saved()
        self.destroy()
