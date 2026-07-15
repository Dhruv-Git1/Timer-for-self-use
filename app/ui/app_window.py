"""
The main application window.

This is the shell that holds everything together: the navigation sidebar on the
left and a content area on the right that swaps between screens. It creates each
screen the first time you visit it (so startup stays quick), remembers your
theme, wires up keyboard shortcuts, and provides the "quick add entry" action.
"""

from __future__ import annotations

import os

import customtkinter as ctk

import config
from app.services.context import AppContext
from app.ui import theme
from app.ui.sidebar import Sidebar, NAV_ITEMS
from app.ui.widgets.time_entry_form import TimeEntryForm
from app.utils import time_utils

# Which class renders each navigation key. Imported here (rather than at module
# top with everything else) purely for grouping/readability.
from app.ui.views.home_view import HomeView
from app.ui.views.timer_view import TimerView
from app.ui.views.dashboard_view import DashboardView
from app.ui.views.entries_view import EntriesView
from app.ui.views.calendar_view import CalendarView
from app.ui.views.statistics_view import StatisticsView
from app.ui.views.graphs_view import GraphsView
from app.ui.views.insights_view import InsightsView
from app.ui.views.categories_view import CategoriesView
from app.ui.views.search_view import SearchView
from app.ui.views.settings_view import SettingsView

_VIEW_CLASSES = {
    "home": HomeView,
    "timer": TimerView,
    "dashboard": DashboardView,
    "entries": EntriesView,
    "calendar": CalendarView,
    "statistics": StatisticsView,
    "graphs": GraphsView,
    "insights": InsightsView,
    "categories": CategoriesView,
    "search": SearchView,
    "settings": SettingsView,
}


class AppWindow(ctk.CTk):
    """The top-level window: sidebar + swappable content area."""

    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.ctx = context

        # Resolve the mono/display font families now — before the sidebar or any
        # view builds a font — since font lookup needs a live Tk root.
        theme.init_fonts(self)

        self.title("Personal Time Tracker & Productivity Dashboard")
        self.geometry("1240x780")
        self.minsize(1040, 680)

        # CustomTkinter overrides the window icon during its own init, so the
        # real icon has to be set slightly after startup, on a short delay.
        if os.path.exists(config.ICON_PATH):
            self.after(250, self._set_icon)

        # Two columns: fixed sidebar, stretchy content.
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        saved_theme = self.ctx.get_setting("theme", "dark")
        self.sidebar = Sidebar(
            self, on_navigate=self.show_view, on_theme_change=self.set_theme,
            initial_theme=saved_theme, timer_service=self.ctx.timer_service,
        )
        self.sidebar.grid(row=0, column=0, sticky="nsw")

        self.content = ctk.CTkFrame(self, fg_color=theme.BG)
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

        self._views: dict[str, object] = {}
        self._current_key: str | None = None
        self._current_view = None

        self._bind_shortcuts()
        self.show_view("home")

    def _set_icon(self) -> None:
        """Apply the taskbar/titlebar icon, ignoring platforms that reject .ico."""
        try:
            self.iconbitmap(config.ICON_PATH)
        except Exception:  # noqa: BLE001 - icon is cosmetic, never fatal
            pass

    # ------------------------------------------------------------------ #
    # Navigation
    # ------------------------------------------------------------------ #
    def _get_view(self, key: str):
        """Return the view for ``key``, creating it the first time it is needed."""
        if key not in self._views:
            view = _VIEW_CLASSES[key](self.content, self.ctx)
            view.app_window = self          # let the view reach the shell
            view.grid(row=0, column=0, sticky="nsew")
            self._views[key] = view
        return self._views[key]

    def show_view(self, key: str) -> None:
        """Switch the content area to the screen named ``key``."""
        if key == self._current_key:
            return
        if self._current_view is not None:
            self._current_view.on_hide()
            self._current_view.grid_remove()

        view = self._get_view(key)
        view.grid()
        view.on_show()

        self._current_key = key
        self._current_view = view
        self.sidebar.set_active(key)

    # ------------------------------------------------------------------ #
    # Theme
    # ------------------------------------------------------------------ #
    def set_theme(self, mode: str) -> None:
        """Apply and persist a light/dark/system theme, then redraw."""
        theme.apply_saved_mode(mode)
        self.ctx.set_setting("theme", mode)

        # Keep both theme selectors (sidebar and settings) in sync.
        self.sidebar.theme_menu.set(mode.capitalize())
        settings = self._views.get("settings")
        if settings is not None:
            settings.theme_menu.set(mode.capitalize())

        # Redraw the visible screen so charts pick up the new colors.
        if self._current_view is not None:
            self._current_view.refresh()

    # ------------------------------------------------------------------ #
    # Keyboard shortcuts
    # ------------------------------------------------------------------ #
    def _bind_shortcuts(self) -> None:
        # Ctrl+1..9 jump straight to a screen, in sidebar order. Only the digit
        # keys 1-9 are valid keysyms, so any 10th+ nav item simply has no
        # numeric shortcut (it is still reachable by clicking).
        for index, (key, _label, _icon) in enumerate(NAV_ITEMS, start=1):
            if index > 9:
                break
            self.bind(f"<Control-Key-{index}>", lambda _e, k=key: self.show_view(k))
        # Ctrl+N adds an entry from anywhere; Ctrl+F opens search.
        self.bind("<Control-n>", lambda _e: self._quick_add_entry())
        self.bind("<Control-f>", lambda _e: self.show_view("search"))

    def _quick_add_entry(self) -> None:
        """Open the add-entry form for today from any screen."""
        def after_save() -> None:
            if self._current_view is not None:
                self._current_view.refresh()
        TimeEntryForm(self, self.ctx, on_saved=after_save,
                      default_date=time_utils.today_str())
