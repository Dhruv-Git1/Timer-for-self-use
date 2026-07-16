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
    ai_coach_screen,
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
    ("AI Coach", ft.Icons.AUTO_AWESOME, ai_coach_screen.build),
    ("Dashboard", ft.Icons.DASHBOARD, dashboard_screen.build),
    ("Today's Entries", ft.Icons.LIST_ALT, entries_screen.build),
    ("Statistics", ft.Icons.BAR_CHART, statistics_screen.build),
    ("Graphs", ft.Icons.INSIGHTS, graphs_screen.build),
    ("Categories", ft.Icons.CATEGORY, categories_screen.build),
    ("Search", ft.Icons.SEARCH, search_screen.build),
    ("Settings", ft.Icons.SETTINGS, settings_screen.build),
]

_MORE_GROUPS = [
    ("Review", _MORE_ITEMS[:5]),
    ("Organize", _MORE_ITEMS[5:7]),
    ("App", _MORE_ITEMS[7:]),
]


class AppShell:
    """Owns the one View, the NavigationBar, and the swappable body."""

    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.ctx = get_context()
        self.body = ft.Container(expand=True, padding=16)
        self._current_tab = "timer"
        self._more_detail_open = False
        self._detail_view: ft.View | None = None

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
            can_pop=False,
            navigation_bar=self.nav_bar,
            controls=[self.body],
        )

        page.views.append(self.view)
        page.on_view_pop = self._on_view_pop
        self._show_tab("timer")

    def _on_nav_change(self, e: ft.ControlEvent) -> None:
        key = _TABS[self.nav_bar.selected_index][0]
        self._show_tab(key)

    def _show_tab(self, key: str) -> None:
        self._current_tab = key
        self._more_detail_open = False
        self.nav_bar.selected_index = next(
            index for index, (tab_key, _label, _icon) in enumerate(_TABS)
            if tab_key == key
        )
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
        rows: list[ft.Control] = [theme.display("More", size=28)]
        for group_label, items in _MORE_GROUPS:
            rows.append(theme.section_label(group_label))
            for label, icon, builder in items:
                rows.append(
                    ft.Container(
                        padding=16, border_radius=12, bgcolor=theme.CARD,
                        border=ft.Border.all(1, theme.CARD_BORDER),
                        ink=True,
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Row(controls=[
                                    ft.Icon(icon, color=theme.KICKER_RED, size=20),
                                    ft.Text(label, size=15, color=theme.HEADLINE),
                                ]),
                                ft.Icon(ft.Icons.CHEVRON_RIGHT, color=theme.MONO_LABEL, size=18),
                            ],
                        ),
                        on_click=lambda e, l=label, b=builder: self._open_more_item(l, b),
                    )
                )
        return ft.Column(expand=True, scroll=ft.ScrollMode.AUTO, spacing=10, controls=rows)

    def _open_more_item(self, label: str, builder) -> None:
        self._current_tab = "more"
        self._more_detail_open = True
        self.nav_bar.selected_index = next(
            index for index, (tab_key, _label, _icon) in enumerate(_TABS)
            if tab_key == "more"
        )
        if builder is not None:
            content = builder(self.page, self.ctx)
        else:
            content = placeholder_screen.build(label, "Coming in a future milestone.")

        self._detail_view = ft.View(
            route=f"/more/{label.lower().replace(' ', '-')}",
            bgcolor=theme.BG,
            padding=0,
            spacing=0,
            appbar=ft.AppBar(
                title=ft.Text(label, color=theme.HEADLINE),
                bgcolor=theme.SIDEBAR,
            ),
            controls=[
                ft.Container(
                    expand=True,
                    padding=16,
                    content=screen_enter(content, self.page),
                )
            ],
        )
        self.page.views.append(self._detail_view)
        self.page.update()

    def _on_view_pop(self, event: ft.ViewPopEvent) -> None:
        """Remove only a detail View; the root View is intentionally permanent."""
        if self._detail_view is None:
            return
        detail_view = event.view or self._detail_view
        if detail_view in self.page.views:
            self.page.views.remove(detail_view)
        elif self._detail_view in self.page.views:
            self.page.views.remove(self._detail_view)
        self._detail_view = None
        self._more_detail_open = False
        self.page.update()
