"""
The "Edit daily goals" dialog.

Lists every active category with its daily goal (in minutes) in one editable
field, so a goal can be set or changed in one place instead of opening each
category's own edit form individually.
"""

from __future__ import annotations

from typing import Callable, Dict

import customtkinter as ctk

from app.services.context import AppContext
from app.ui import theme
from app.utils import validators


class GoalsForm(ctk.CTkToplevel):
    """Edit every category's daily goal (minutes) in one place."""

    def __init__(self, parent, context: AppContext, on_saved: Callable[[], None]) -> None:
        super().__init__(parent)
        self.ctx = context
        self.on_saved = on_saved
        self._categories = context.category_service.list_categories()
        self._vars: Dict[int, ctk.StringVar] = {}

        self.title("Edit daily goals")
        self.geometry("420x480")
        self.resizable(False, False)
        self.transient(parent)
        self.lift()
        self.after(10, self.grab_set)
        self.after(20, self.focus_force)

        self._build()

    def _build(self) -> None:
        ctk.CTkLabel(self, text="Daily goal per category", anchor="w",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(
            fill="x", padx=20, pady=(16, 2))
        ctk.CTkLabel(self, text="Minutes per day — 0 means no goal.",
                     text_color=theme.MUTED_TEXT, anchor="w",
                     font=ctk.CTkFont(size=12)).pack(fill="x", padx=20, pady=(0, 10))

        if not self._categories:
            ctk.CTkLabel(self, text="No categories yet — add one on the Categories screen.",
                         text_color=theme.MUTED_TEXT, wraplength=360).pack(
                fill="x", padx=20, pady=20)
        else:
            rows = ctk.CTkScrollableFrame(self, fg_color="transparent")
            rows.pack(fill="both", expand=True, padx=20)
            for category in self._categories:
                row = ctk.CTkFrame(rows, fg_color="transparent")
                row.pack(fill="x", pady=4)
                ctk.CTkLabel(row, text="●", text_color=category.color,
                             font=ctk.CTkFont(size=14)).pack(side="left", padx=(0, 6))
                ctk.CTkLabel(row, text=category.name, anchor="w", width=140).pack(side="left")
                var = ctk.StringVar(value=str(category.daily_target_minutes))
                self._vars[category.id] = var
                ctk.CTkEntry(row, textvariable=var, width=80).pack(
                    side="left", padx=(8, 4))
                ctk.CTkLabel(row, text="min/day", text_color=theme.MUTED_TEXT,
                             font=ctk.CTkFont(size=11)).pack(side="left")

        self.error_label = ctk.CTkLabel(self, text="", text_color="#D0463B", anchor="w",
                                        wraplength=380, justify="left",
                                        font=ctk.CTkFont(size=12))
        self.error_label.pack(fill="x", padx=20, pady=(6, 0))

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(fill="x", padx=20, pady=(10, 16), side="bottom")
        ctk.CTkButton(buttons, text="Cancel", width=100, fg_color=theme.NEUTRAL_BTN,
                      hover_color=theme.NEUTRAL_BTN_HOVER, text_color=("gray10", "gray90"),
                      command=self.destroy).pack(side="right", padx=(8, 0))
        if self._categories:
            ctk.CTkButton(buttons, text="Save", width=100, command=self._save).pack(side="right")
        self.bind("<Escape>", lambda _e: self.destroy())

    def _save(self) -> None:
        # Validate every field before saving any of them, so one bad value
        # can't leave the goals half-updated.
        parsed: Dict[int, int] = {}
        for category in self._categories:
            text = self._vars[category.id].get()
            ok, msg = validators.validate_target_minutes(text)
            if not ok:
                self.error_label.configure(text=f"{category.name}: {msg}")
                return
            parsed[category.id] = int(text or 0)

        for category in self._categories:
            new_target = parsed[category.id]
            if new_target != category.daily_target_minutes:
                category.daily_target_minutes = new_target
                ok, msg, _ = self.ctx.category_service.update(category)
                if not ok:
                    self.error_label.configure(text=f"{category.name}: {msg}")
                    return

        self.on_saved()
        self.destroy()
