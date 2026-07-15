"""
The add / edit category dialog.

A small modal form for creating a category or changing an existing one: its name,
its color (via the system color picker), whether it counts as productive time,
and its optional daily goal in minutes.
"""

from __future__ import annotations

from tkinter import colorchooser
from typing import Callable, Optional

import customtkinter as ctk

from app.models.category import Category
from app.services.context import AppContext
from app.ui import theme
from app.utils import validators


class CategoryForm(ctk.CTkToplevel):
    """Create or edit one activity category."""

    def __init__(
        self,
        parent,
        context: AppContext,
        on_saved: Callable[[], None],
        category: Optional[Category] = None,
    ) -> None:
        super().__init__(parent)
        self.ctx = context
        self.on_saved = on_saved
        self.category = category
        self.is_edit = category is not None
        self._color = category.color if self.is_edit else "#3B82F6"

        self.title("Edit category" if self.is_edit else "Add category")
        self.geometry("400x440")
        self.resizable(False, False)
        self.transient(parent)
        self.lift()
        self.after(10, self.grab_set)
        self.after(20, self.focus_force)

        self._build()

    def _build(self) -> None:
        pad = {"padx": 20}
        wrap = ctk.CTkFrame(self, fg_color="transparent")
        wrap.pack(fill="both", expand=True, pady=16)

        ctk.CTkLabel(wrap, text="Name", anchor="w",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(fill="x", pady=(6, 2), **pad)
        self.name_var = ctk.StringVar(value=self.category.name if self.is_edit else "")
        ctk.CTkEntry(wrap, textvariable=self.name_var).pack(fill="x", **pad)

        # Color picker: a button whose own color previews the choice.
        ctk.CTkLabel(wrap, text="Color", anchor="w",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(fill="x", pady=(12, 2), **pad)
        self.color_btn = ctk.CTkButton(wrap, text="Pick color…", fg_color=self._color,
                                       hover_color=self._color, command=self._pick_color)
        self.color_btn.pack(fill="x", **pad)

        # Productive switch.
        self.productive_var = ctk.BooleanVar(
            value=self.category.is_productive if self.is_edit else True)
        switch = ctk.CTkSwitch(wrap, text="Counts as productive time",
                               variable=self.productive_var)
        switch.pack(anchor="w", pady=(16, 4), **pad)
        ctk.CTkLabel(wrap, text="Turn off for things like Sleep, Travel or "
                     "Entertainment that you record but don't count toward goals.",
                     text_color="gray", wraplength=340, justify="left",
                     font=ctk.CTkFont(size=11)).pack(anchor="w", **pad)

        ctk.CTkLabel(wrap, text="Daily goal (minutes, 0 = none)", anchor="w",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(fill="x", pady=(14, 2), **pad)
        self.target_var = ctk.StringVar(
            value=str(self.category.daily_target_minutes) if self.is_edit else "0")
        ctk.CTkEntry(wrap, textvariable=self.target_var).pack(fill="x", **pad)

        self.error_label = ctk.CTkLabel(wrap, text="", text_color="#D0463B", anchor="w",
                                        wraplength=340, justify="left",
                                        font=ctk.CTkFont(size=12))
        self.error_label.pack(fill="x", pady=(8, 0), **pad)

        buttons = ctk.CTkFrame(wrap, fg_color="transparent")
        buttons.pack(fill="x", side="bottom", pady=(10, 0), **pad)
        ctk.CTkButton(buttons, text="Cancel", width=100, fg_color=theme.NEUTRAL_BTN,
                      hover_color=theme.NEUTRAL_BTN_HOVER, text_color=("gray10", "gray90"),
                      command=self.destroy).pack(side="right", padx=(8, 0))
        ctk.CTkButton(buttons, text="Save", width=100, command=self._save).pack(side="right")
        self.bind("<Escape>", lambda _e: self.destroy())

    def _pick_color(self) -> None:
        """Open the OS color picker; keep the current color if cancelled."""
        chosen = colorchooser.askcolor(color=self._color, parent=self)
        if chosen and chosen[1]:
            self._color = chosen[1]
            self.color_btn.configure(fg_color=self._color, hover_color=self._color)

    def _save(self) -> None:
        # Validate the target field first (name is validated by the service).
        ok, msg = validators.validate_target_minutes(self.target_var.get())
        if not ok:
            self.error_label.configure(text=msg)
            return
        target = int(self.target_var.get() or 0)

        if self.is_edit:
            self.category.name = self.name_var.get()
            self.category.color = self._color
            self.category.is_productive = self.productive_var.get()
            self.category.daily_target_minutes = target
            ok, msg, _ = self.ctx.category_service.update(self.category)
        else:
            ok, msg, _ = self.ctx.category_service.create(
                self.name_var.get(), self._color, self.productive_var.get(), target)

        if not ok:
            self.error_label.configure(text=msg)
            return
        self.on_saved()
        self.destroy()
