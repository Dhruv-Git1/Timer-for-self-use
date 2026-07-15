"""
The app shell: one persistent bottom NavigationBar + swappable body content.

Tabs are peers, not a navigation stack — switching tabs just rebuilds the
body's content and calls page.update(), mirroring how the desktop AppWindow
swaps CTkFrame content in its own content area (app/ui/app_window.py).
"""

from __future__ import annotations

import flet as ft

from mobile import theme
from mobile.screens import (
    calendar_screen, categories_screen, dashboard_screen, entries_screen,
    graphs_screen, home_screen, insights_screen, placeholder_screen,
    search_screen, settings_screen, statistics_screen, timer_screen,
)
from mobile.storage import get_context
from mobile.widgets.fury import screen_enter

_TABS = [
    ("timer", "Timer", ft.Icons.TIMER),
    ("home", "Home", ft.Icons.LOCAL_FIRE_DEPARTMENT),
    ("calendar", "Calendar", ft.Icons.CALENDAR_MONTH),
    ("insights", "Insights", ft.Icons.SCIENCE),
    ("more", "More", ft.Icons.MORE_HORIZ),
]

# (label, icon, screen-builder). Every screen is now built — Milestone 3 complete.
_MORE_ITEMS = [
    ("Dashboard", ft.Icons.DASHBOARD, dashboard_screen.build),
    ("Today's Entries", ft.Icons.LIST_ALT, entries_screen.build),
    ("Statistics", ft.Icons.BAR_CHART, statistics_screen.build),
    ("Graphs", ft.Icons.INSIGHTS, graphs_screen.build),
    ("Categories", ft.Icons.CATEGORY, categories_screen.build),
    ("Search", ft.Icons.SEARCH, search_screen.build),
    ("Settings", ft.Icons.SETTINGS, settings_screen.build),
]


class AppShell:
    """Owns the one View, the NavigationBar, and the swappable body."""

    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.ctx = get_context()
        self.body = ft.Container(expand=True, padding=16)

        self.nav_bar = ft.NavigationBar(
            selected_index=0,
            bgcolor=theme.SIDEBAR,
            indicator_color=theme.ACCENT,
            indicator_shape=ft.RoundedRectangleBorder(radius=8),
            elevation=8,
            shadow_color=theme.ACCENT_GLOW,
            on_change=self._on_nav_change,
            destinations=[
                ft.NavigationBarDestination(icon=icon, label=label)
                for _key, label, icon in _TABS
            ],
        )

        self.view = ft.View(
            route="/",
            bgcolor=theme.BG,
            padding=0,
            spacing=0,
            navigation_bar=self.nav_bar,
            controls=[self.body],
        )

        page.views.append(self.view)
        self._show_tab("timer")

    def _on_nav_change(self, e: ft.ControlEvent) -> None:
        key = _TABS[self.nav_bar.selected_index][0]
        self._show_tab(key)

    def _show_tab(self, key: str) -> None:
        if key == "timer":
            content = timer_screen.build(self.page, self.ctx)
        elif key == "home":
            content = home_screen.build(self.page, self.ctx)
        elif key == "insights":
            content = insights_screen.build(self.page, self.ctx)
        elif key == "calendar":
            content = calendar_screen.build(self.page, self.ctx)
        else:  # more
            content = self._build_more_list()

        self.body.content = screen_enter(content, self.page)
        self.page.update()

    def _build_more_list(self) -> ft.Control:
        rows = []
        for label, icon, builder in _MORE_ITEMS:
            rows.append(
                ft.Container(
                    padding=16, border_radius=12, bgcolor=theme.CARD,
                    border=ft.Border.all(1, theme.CARD_BORDER),
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Row(controls=[
                                ft.Icon(icon, color=theme.MUTED_TEXT, size=20),
                                ft.Text(label, size=15, color=theme.HEADLINE),
                            ]),
                            ft.Icon(ft.Icons.CHEVRON_RIGHT, color=theme.MONO_LABEL, size=18),
                        ],
                    ),
                    on_click=lambda e, l=label, b=builder: self._open_more_item(l, b),
                )
            )
        return ft.Column(expand=True, scroll=ft.ScrollMode.AUTO, spacing=8, controls=rows)

    def _open_more_item(self, label: str, builder) -> None:
        if builder is not None:
            content = builder(self.page, self.ctx)
        else:
            content = placeholder_screen.build(label, "Coming in a future milestone.")
        self.body.content = screen_enter(content, self.page)
        self.page.update()
