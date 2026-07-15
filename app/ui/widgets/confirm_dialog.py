"""
A small yes/no confirmation dialog.

Used before anything destructive — deleting an entry, deleting a category,
restoring a backup over your current data. It pops up a modal window (one you
must answer before doing anything else) and returns True only if the user
clicks the confirm button.
"""

from __future__ import annotations

import customtkinter as ctk

from app.ui import theme


class ConfirmDialog(ctk.CTkToplevel):
    """A modal dialog asking the user to confirm or cancel an action."""

    def __init__(
        self,
        parent,
        title: str,
        message: str,
        confirm_text: str = "Delete",
        confirm_color: str = "#D0463B",
    ) -> None:
        super().__init__(parent)
        self.result = False

        self.title(title)
        self.geometry("400x180")
        self.resizable(False, False)

        # These four lines are the standard recipe that keeps a CustomTkinter
        # popup on Windows in front of its parent and holding keyboard focus,
        # instead of hiding behind the main window.
        self.transient(parent)
        self.lift()
        self.after(10, self.grab_set)      # grab after the window is realised
        self.after(20, self.focus_force)

        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(
            container, text=message, wraplength=340, justify="left",
            font=ctk.CTkFont(size=14),
        ).pack(anchor="w", pady=(0, 20))

        buttons = ctk.CTkFrame(container, fg_color="transparent")
        buttons.pack(fill="x", side="bottom")

        ctk.CTkButton(
            buttons, text="Cancel", width=100, fg_color=theme.NEUTRAL_BTN,
            hover_color=theme.NEUTRAL_BTN_HOVER, text_color=("gray10", "gray90"),
            command=self._cancel,
        ).pack(side="right", padx=(8, 0))
        ctk.CTkButton(
            buttons, text=confirm_text, width=100, fg_color=confirm_color,
            hover_color=confirm_color, command=self._confirm,
        ).pack(side="right")

        # Enter confirms, Escape cancels — small keyboard niceties.
        self.bind("<Return>", lambda _e: self._confirm())
        self.bind("<Escape>", lambda _e: self._cancel())

    def _confirm(self) -> None:
        self.result = True
        self.destroy()

    def _cancel(self) -> None:
        self.result = False
        self.destroy()


def ask_confirm(
    parent,
    title: str,
    message: str,
    confirm_text: str = "Delete",
    confirm_color: str = "#D0463B",
) -> bool:
    """Show a confirmation dialog and block until the user answers.

    Returns True if they confirmed. ``wait_window`` pauses here until the dialog
    closes, so the calling code can simply write ``if ask_confirm(...):``.
    """
    dialog = ConfirmDialog(parent, title, message, confirm_text, confirm_color)
    dialog.wait_window()
    return dialog.result
