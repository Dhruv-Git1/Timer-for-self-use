"""
Mobile entry point.

Desktop preview:  flet run mobile/main.py
Android build:    flet build apk   (see pyproject.toml, [tool.flet.app] module)

Reuses the exact same AppContext/services/database the desktop app uses (see
mobile/storage.py) — only the screens are Flet-native; nothing here touches
CustomTkinter or matplotlib.
"""

from __future__ import annotations

import os
import sys

# Make sure the project root (parent of this mobile/ package) is importable,
# regardless of whether this file is launched as a script or as a module —
# both "app.*" (shared logic) and "mobile.*" (this package) need it on sys.path.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import flet as ft

from mobile import theme
from mobile.app_shell import AppShell


def main(page: ft.Page) -> None:
    page.title = "Time Tracker"
    page.bgcolor = theme.BG
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 0

    AppShell(page)


if __name__ == "__main__":
    ft.run(main)
