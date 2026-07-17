"""
The app shell: one persistent bottom NavigationBar + swappable body content.

Tabs are peers, not a navigation stack — switching tabs just rebuilds the
body's content and calls page.update(), mirroring how the desktop AppWindow
swaps CTkFrame content in its own content area (app/ui/app_window.py).
"""

from __future__ import annotations

from urllib.parse import urlparse

import flet as ft

from app.services.timer_service import MODE_COUNTDOWN, MODE_STOPWATCH
from app.utils import time_utils
from app.utils.event_bus import DATA_CHANGED, TIMER_STATE_CHANGED, bus
from mobile import theme
from mobile.services.android_timer_bridge import (
    AndroidTimerBridge,
    state_payload,
    task_reminder_payload,
    target_status_payload,
)
from mobile.screens import (
    ai_coach_screen,
    calendar_screen, categories_screen, dashboard_screen, entries_screen,
    goals_screen, graphs_screen, help_screen, home_screen, insights_screen, placeholder_screen,
    search_screen, settings_screen, statistics_screen, timer_screen,
)
from mobile.storage import get_context
from mobile.widgets.fury import screen_enter

_TABS = [
    ("timer", "Timer", ft.Icons.TIMER),
    ("home", "Home", ft.Icons.LOCAL_FIRE_DEPARTMENT),
    ("goals", "Goals", ft.Icons.FLAG),
    ("insights", "Insights", ft.Icons.SCIENCE),
    ("more", "More", ft.Icons.MORE_HORIZ),
]

# (label, icon, screen-builder). Every screen is now built — Milestone 3 complete.
_MORE_ITEMS = [
    ("Calendar", ft.Icons.CALENDAR_MONTH, calendar_screen.build),
    ("AI Coach", ft.Icons.AUTO_AWESOME, ai_coach_screen.build),
    ("Dashboard", ft.Icons.DASHBOARD, dashboard_screen.build),
    ("Today's Entries", ft.Icons.LIST_ALT, entries_screen.build),
    ("Statistics", ft.Icons.BAR_CHART, statistics_screen.build),
    ("Graphs", ft.Icons.INSIGHTS, graphs_screen.build),
    ("Categories", ft.Icons.CATEGORY, categories_screen.build),
    ("Search", ft.Icons.SEARCH, search_screen.build),
    ("Settings", ft.Icons.SETTINGS, settings_screen.build),
    ("How to use", ft.Icons.HELP_OUTLINE, help_screen.build),
]

_MORE_GROUPS = [
    ("Review", _MORE_ITEMS[:6]),
    ("Organize", _MORE_ITEMS[6:8]),
    ("App", _MORE_ITEMS[8:]),
]


def timer_mode_from_route(route: str | None) -> str | None:
    """Normalize cold/warm Flet deep-link route shapes to a timer mode."""
    if not route:
        return None
    parsed = urlparse(str(route))
    parts = [part.casefold() for part in ([parsed.netloc] + parsed.path.split("/")) if part]
    if not parts:
        parts = [part.casefold() for part in str(route).split("?")[0].split("/") if part]
    if parts and parts[-1] in {MODE_COUNTDOWN, MODE_STOPWATCH}:
        if "timer" in parts or len(parts) == 1:
            return parts[-1]
    return None


def goal_task_id_from_route(route: str | None) -> int | None:
    """Extract a task ID from a cold or warm notification deep link."""
    if not route:
        return None
    parsed = urlparse(str(route))
    parts = [part.casefold() for part in ([parsed.netloc] + parsed.path.split("/")) if part]
    try:
        task_index = parts.index("task")
        if "goals" in parts and task_index + 1 < len(parts):
            return int(parts[task_index + 1])
    except (ValueError, TypeError):
        return None
    return None


class AppShell:
    """Owns the one View, the NavigationBar, and the swappable body."""

    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.ctx = get_context()
        self.body = ft.Container(expand=True, padding=16)
        self.safe_body = ft.SafeArea(
            content=self.body,
            expand=True,
            avoid_intrusions_left=False,
            avoid_intrusions_top=True,
            avoid_intrusions_right=False,
            avoid_intrusions_bottom=False,
        )
        self._current_tab = "timer"
        self._more_detail_open = False
        self._detail_view: ft.View | None = None
        self.android_timer_bridge: AndroidTimerBridge | None = None

        if getattr(page, "platform", None) == ft.PagePlatform.ANDROID:
            self.android_timer_bridge = AndroidTimerBridge()
            page.services.append(self.android_timer_bridge)
            # The Timer screen needs this only to send the foreground completion
            # notification with its original token; desktop never sees it.
            page._timetracker_android_bridge = self.android_timer_bridge
            bus.subscribe(TIMER_STATE_CHANGED, self._on_timer_state_changed)
            bus.subscribe(DATA_CHANGED, self._on_android_data_changed)
            page.on_app_lifecycle_state_change = self._on_lifecycle_state_change
            page.run_task(self._initialize_android_timer)

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
            controls=[self.safe_body],
        )

        page.views.append(self.view)
        page.on_view_pop = self._on_view_pop
        page.on_route_change = self._on_route_change
        self._show_tab("timer")
        self._apply_timer_deep_link(getattr(page, "route", ""))
        self._apply_goal_deep_link(getattr(page, "route", ""))

    async def _initialize_android_timer(self) -> None:
        if self.android_timer_bridge is None:
            return
        try:
            await self._sync_android_data()
        except Exception as exc:  # native permissions are best-effort
            print(f"[Android timer] bridge initialization failed: {exc}")

    def _on_timer_state_changed(self, **_payload) -> None:
        if self.android_timer_bridge is not None:
            self.page.run_task(self._sync_android_widgets)

    def _on_android_data_changed(self, **_payload) -> None:
        if self.android_timer_bridge is not None:
            self.page.run_task(self._sync_android_data)

    def _on_lifecycle_state_change(self, event: ft.AppLifecycleStateChangeEvent) -> None:
        if event.state != ft.AppLifecycleState.RESUME:
            return
        before = self.ctx.timer_service.current_state()
        completed = self.ctx.timer_service.reconcile_expired()
        if completed[0] and before.token and self.android_timer_bridge is not None:
            self.page.run_task(self.android_timer_bridge.notify_finished, before.token)
        if self.android_timer_bridge is not None:
            self.page.run_task(self._sync_android_data)

    async def _sync_android_widgets(self) -> None:
        if self.android_timer_bridge is None:
            return
        state = self.ctx.timer_service.current_state()
        category = (
            self.ctx.category_service.get(state.category_id)
            if state.is_active and state.category_id is not None
            else None
        )
        await self.android_timer_bridge.sync_state(state_payload(state, category))
        score = self.ctx.daily_progress_service.score(time_utils.today_str())
        await self.android_timer_bridge.sync_target_status(target_status_payload(score))

    async def _sync_android_data(self) -> None:
        """Refresh widgets and reconcile every pending task alarm."""
        if self.android_timer_bridge is None:
            return
        await self._sync_android_widgets()
        tasks = self.ctx.goal_service.pending_task_reminders()
        await self.android_timer_bridge.sync_task_reminders(
            [task_reminder_payload(task) for task in tasks]
        )

    def _on_nav_change(self, e: ft.ControlEvent) -> None:
        key = _TABS[self.nav_bar.selected_index][0]
        self._show_tab(key)

    def _on_route_change(self, event: ft.RouteChangeEvent) -> None:
        self._apply_timer_deep_link(event.route)
        self._apply_goal_deep_link(event.route)

    def _apply_timer_deep_link(self, route: str | None) -> None:
        mode = timer_mode_from_route(route)
        if mode is None:
            return
        state = self.ctx.timer_service.current_state()
        if not state.is_active:
            self.ctx.timer_service.set_preferred_mode(mode)
        # An active timer is authoritative: opening a shortcut never mutates
        # its mode/category, but it still takes the user to the Timer tab.
        self._show_tab("timer")

    def _apply_goal_deep_link(self, route: str | None) -> None:
        task_id = goal_task_id_from_route(route)
        if task_id is None:
            return
        self._show_tab("goals")
        opener = getattr(self.page, "_timetracker_open_goal_task", None)
        if callable(opener):
            opener(task_id)

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
        elif key == "goals":
            content = goals_screen.build(self.page, self.ctx)
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
