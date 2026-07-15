"""
The settings screen.

Four small sections: choose the light/dark appearance, export your data to
Excel / CSV / JSON, back up or restore the database, and a short "about" panel
with where your data lives. Restoring a backup replaces your current data, so it
asks for confirmation first.
"""

from __future__ import annotations

import os

import customtkinter as ctk

import config
from app.ui import theme
from app.ui.views.base_view import BaseView
from app.ui.widgets.confirm_dialog import ask_confirm
from app.utils.event_bus import bus, DATA_CHANGED


class SettingsView(BaseView):
    title = "Settings"

    def __init__(self, master, context) -> None:
        super().__init__(master, context)
        self._build()

    # ------------------------------------------------------------------ #
    # Layout
    # ------------------------------------------------------------------ #
    def _build(self) -> None:
        ctk.CTkLabel(self, text="Settings",
                     font=ctk.CTkFont(size=26, weight="bold")).pack(
            anchor="w", padx=24, pady=(20, 8))

        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=24, pady=(0, 20))

        # --- Appearance -------------------------------------------------
        appearance = self._section(body, "Appearance")
        ctk.CTkLabel(appearance, text="Theme").pack(side="left", padx=(0, 12))
        self.theme_menu = ctk.CTkOptionMenu(
            appearance, values=["Dark", "Light", "System"],
            command=self._change_theme)
        self.theme_menu.set(self.ctx.get_setting("theme", "dark").capitalize())
        self.theme_menu.pack(side="left")

        # --- Export -----------------------------------------------------
        export = self._section(body, "Export data")
        ctk.CTkButton(export, text="Excel (.xlsx)",
                      command=lambda: self._export("excel")).pack(side="left", padx=(0, 8))
        ctk.CTkButton(export, text="CSV",
                      command=lambda: self._export("csv")).pack(side="left", padx=8)
        ctk.CTkButton(export, text="JSON",
                      command=lambda: self._export("json")).pack(side="left", padx=8)
        ctk.CTkButton(export, text="📂 Open folder", fg_color=theme.NEUTRAL_BTN,
                      hover_color=theme.NEUTRAL_BTN_HOVER, text_color=("gray10", "gray90"),
                      command=lambda: self._open_folder(config.EXPORT_DIR)).pack(side="left", padx=8)
        self.export_status = ctk.CTkLabel(body, text="", text_color=theme.MUTED_TEXT,
                                          anchor="w", wraplength=600, justify="left")
        self.export_status.pack(anchor="w", pady=(0, 6))

        # --- Backup & restore ------------------------------------------
        backup = self._section(body, "Backup & restore")
        ctk.CTkButton(backup, text="💾 Create backup now",
                      command=self._create_backup).pack(side="left")
        ctk.CTkButton(backup, text="📂 Open backups folder", fg_color=theme.NEUTRAL_BTN,
                      hover_color=theme.NEUTRAL_BTN_HOVER, text_color=("gray10", "gray90"),
                      command=lambda: self._open_folder(config.BACKUP_DIR)).pack(side="left", padx=8)
        self.backup_status = ctk.CTkLabel(body, text="", text_color=theme.MUTED_TEXT,
                                          anchor="w")
        self.backup_status.pack(anchor="w", pady=(2, 6))

        ctk.CTkLabel(body, text="Restore from a backup (replaces current data):",
                     anchor="w").pack(anchor="w", pady=(4, 2))
        self.backup_list = ctk.CTkFrame(body, fg_color="transparent")
        self.backup_list.pack(fill="x")

        # --- About ------------------------------------------------------
        about = self._section(body, "About")
        ctk.CTkLabel(
            about,
            text="Personal Time Tracker & Productivity Dashboard\n"
                 f"Data file: {config.DB_PATH}\n"
                 "Offline • your data never leaves this computer.",
            justify="left", anchor="w", text_color=theme.MUTED_TEXT,
        ).pack(anchor="w")

    def _section(self, parent, title: str) -> ctk.CTkFrame:
        """Create a titled card and return an inner row frame for its controls."""
        ctk.CTkLabel(parent, text=title,
                     font=ctk.CTkFont(size=16, weight="bold")).pack(
            anchor="w", pady=(14, 4))
        card = ctk.CTkFrame(parent, fg_color=theme.CARD_COLOR, corner_radius=10)
        card.pack(fill="x")
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=12)
        return row

    # ------------------------------------------------------------------ #
    # Actions
    # ------------------------------------------------------------------ #
    def _change_theme(self, choice: str) -> None:
        if self.app_window is not None:
            self.app_window.set_theme(choice.lower())

    def _export(self, fmt: str) -> None:
        try:
            if fmt == "excel":
                _ok, path = self.ctx.export_service.to_excel()
            elif fmt == "csv":
                _ok, path = self.ctx.export_service.to_csv()
            else:
                _ok, path = self.ctx.export_service.to_json()
            self.export_status.configure(text=f"✓ Exported to {path}")
        except Exception as exc:  # noqa: BLE001 - surface any export problem
            self.export_status.configure(text=f"✗ Export failed: {exc}")

    def _create_backup(self) -> None:
        ok, msg, _path = self.ctx.backup_service.create_backup()
        self.backup_status.configure(text=("✓ " if ok else "✗ ") + msg)
        self._refresh_backup_list()

    def _refresh_backup_list(self) -> None:
        for child in self.backup_list.winfo_children():
            child.destroy()
        backups = self.ctx.backup_service.list_backups()
        if not backups:
            ctk.CTkLabel(self.backup_list, text="No backups yet.",
                         text_color=theme.MUTED_TEXT).pack(anchor="w", pady=4)
            return
        for path in backups[:12]:   # show the twelve most recent
            row = ctk.CTkFrame(self.backup_list, fg_color=theme.CARD_COLOR, corner_radius=8)
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=os.path.basename(path), anchor="w").pack(
                side="left", padx=12, pady=6)
            ctk.CTkButton(row, text="Restore", width=80, fg_color=theme.NEUTRAL_BTN,
                          hover_color=theme.NEUTRAL_BTN_HOVER, text_color=("gray10", "gray90"),
                          command=lambda p=path: self._restore(p)).pack(side="right", padx=10)

    def _restore(self, path: str) -> None:
        if not ask_confirm(
            self, "Restore backup",
            f"Replace ALL current data with the backup\n{os.path.basename(path)}?\n\n"
            "Your current data will be overwritten.",
            confirm_text="Restore", confirm_color="#D0463B",
        ):
            return
        ok, msg = self.ctx.backup_service.restore_backup(path)
        self.backup_status.configure(text=("✓ " if ok else "✗ ") + msg)
        if ok:
            # Tell every screen to reload from the freshly restored database.
            bus.publish(DATA_CHANGED)

    def _open_folder(self, path: str) -> None:
        config.ensure_directories()
        try:
            os.startfile(path)   # Windows: opens the folder in File Explorer
        except Exception:  # noqa: BLE001 - non-critical convenience
            pass

    # ------------------------------------------------------------------ #
    # Refresh
    # ------------------------------------------------------------------ #
    def refresh(self) -> None:
        last = self.ctx.get_setting("last_backup_at", "")
        self.backup_status.configure(
            text=f"Last backup: {last}" if last else "No backups yet.")
        self._refresh_backup_list()
