"""
Personal Time Tracker & Productivity Dashboard — application entry point.

Run this file to start the app:

    python main.py

It wires up the data layer (creating the database on first run), reads your
saved theme, and opens the main window. Everything runs locally; no internet
connection is used at any point.
"""

from __future__ import annotations

import os

import customtkinter as ctk

import config
from app.services.context import AppContext
from app.ui import theme
from app.ui.app_window import AppWindow


def main() -> None:
    # 1. Make sure the data/backup/export folders exist.
    config.ensure_directories()

    # 2. Build the whole object graph and initialise the database (first run
    #    creates the tables and seeds the default categories).
    context = AppContext()

    # 3. Apply the saved appearance before the window is drawn, so there is no
    #    flash of the wrong theme, and load the custom crimson "REVENGE" color
    #    theme (falling back to CustomTkinter's built-in blue if the file is
    #    somehow missing, so the app always starts).
    revenge_theme = os.path.join(config.ASSETS_DIR, "theme", "revenge.json")
    try:
        ctk.set_default_color_theme(revenge_theme if os.path.exists(revenge_theme) else "blue")
    except Exception:  # noqa: BLE001 - a bad theme file must never block startup
        ctk.set_default_color_theme("blue")
    theme.apply_saved_mode(context.get_setting("theme", config.DEFAULT_THEME))

    # 4. Open the main window and hand control to the UI event loop.
    window = AppWindow(context)
    window.mainloop()

    # 5. Close the database cleanly when the window is closed.
    context.close()


if __name__ == "__main__":
    main()
