"""
The categories screen.

Manage your activity categories: add new ones, edit their name/color/goal, mark
them productive or not, and archive or delete them. Deleting is blocked when a
category already has entries (to protect your history) — the app suggests
archiving instead, which just hides it from the pickers.
"""

from __future__ import annotations

import customtkinter as ctk

from app.ui import theme
from app.ui.views.base_view import BaseView
from app.ui.widgets.category_form import CategoryForm
from app.ui.widgets.confirm_dialog import ask_confirm
from app.utils import time_utils


class CategoriesView(BaseView):
    title = "Categories"

    def __init__(self, master, context) -> None:
        super().__init__(master, context)
        self.show_archived = ctk.BooleanVar(value=False)
        self._build()

    def _build(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(20, 8))
        ctk.CTkLabel(header, text="Categories",
                     font=ctk.CTkFont(size=26, weight="bold")).pack(side="left")
        ctk.CTkButton(header, text="➕  Add category",
                      command=self._add_category).pack(side="right")
        ctk.CTkCheckBox(header, text="Show archived", variable=self.show_archived,
                        command=self.refresh).pack(side="right", padx=16)

        self.list_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.list_frame.pack(fill="both", expand=True, padx=24, pady=(4, 20))

    def _add_category(self) -> None:
        CategoryForm(self, self.ctx, on_saved=self.refresh)

    def _edit_category(self, category) -> None:
        CategoryForm(self, self.ctx, on_saved=self.refresh, category=category)

    def _delete_category(self, category) -> None:
        # Try the delete; the service refuses (and explains) if it has entries.
        ok, msg, _ = self.ctx.category_service.delete(category.id)
        if ok:
            self.refresh()
            return
        # Offer archiving as the safe alternative.
        if ask_confirm(self, "Cannot delete", msg + "\n\nArchive it instead?",
                       confirm_text="Archive", confirm_color=theme.ACCENT[1]):
            self.ctx.category_service.set_archived(category.id, True)
            self.refresh()

    def _toggle_archive(self, category) -> None:
        self.ctx.category_service.set_archived(category.id, not category.is_archived)
        self.refresh()

    def refresh(self) -> None:
        for child in self.list_frame.winfo_children():
            child.destroy()

        categories = self.ctx.category_service.list_categories(
            include_archived=self.show_archived.get())

        for category in categories:
            self._category_row(category)

    def _category_row(self, category) -> None:
        count = self.ctx.category_repo.count_entries(category.id)
        row = ctk.CTkFrame(self.list_frame, fg_color=theme.CARD_COLOR, corner_radius=8)
        row.pack(fill="x", pady=3)

        ctk.CTkLabel(row, text="●", text_color=category.color,
                     font=ctk.CTkFont(size=20)).pack(side="left", padx=(12, 4), pady=10)

        name_text = category.name + ("  (archived)" if category.is_archived else "")
        info = ctk.CTkFrame(row, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(info, text=name_text, anchor="w",
                     font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w")

        target = (time_utils.fmt_duration(category.daily_target_minutes)
                  if category.daily_target_minutes else "no goal")
        kind = "productive" if category.is_productive else "recorded only"
        ctk.CTkLabel(info, text=f"{kind}  •  goal: {target}  •  {count} entries",
                     anchor="w", text_color=theme.MUTED_TEXT,
                     font=ctk.CTkFont(size=12)).pack(anchor="w")

        # Actions on the right.
        ctk.CTkButton(row, text="🗑", width=36, fg_color="transparent",
                      hover_color=("gray80", "gray25"), text_color=("gray10", "gray90"),
                      command=lambda c=category: self._delete_category(c)).pack(side="right", padx=(0, 10))
        archive_label = "Unarchive" if category.is_archived else "Archive"
        ctk.CTkButton(row, text=archive_label, width=90, fg_color=theme.NEUTRAL_BTN,
                      hover_color=theme.NEUTRAL_BTN_HOVER, text_color=("gray10", "gray90"),
                      command=lambda c=category: self._toggle_archive(c)).pack(side="right", padx=4)
        ctk.CTkButton(row, text="✎", width=36, fg_color="transparent",
                      hover_color=("gray80", "gray25"), text_color=("gray10", "gray90"),
                      command=lambda c=category: self._edit_category(c)).pack(side="right")
