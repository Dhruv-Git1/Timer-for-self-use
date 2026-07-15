"""
The left navigation sidebar.

A fixed-width column with the app name at the top, one button per screen, and a
light/dark switch at the bottom. Clicking a button asks the main window to swap
the content area to that screen and highlights the button so you always know
where you are.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Tuple

import customtkinter as ctk

from app.ui import theme
from app.utils.event_bus import bus, TIMER_STATE_CHANGED

# The navigation items, in the order they appear. Each is (key, label, icon).
# The "icons" are plain emoji so we need no image files and they render on
# Windows 11 out of the box. Home is first: it's the app's landing screen.
NAV_ITEMS: List[Tuple[str, str, str]] = [
    ("home", "Home", "🔥"),
    ("timer", "Timer", "⏱️"),
    ("dashboard", "Dashboard", "🏠"),
    ("entries", "Today's Entries", "📝"),
    ("calendar", "Calendar", "📅"),
    ("statistics", "Statistics", "📊"),
    ("graphs", "Graphs", "📈"),
    ("insights", "Insights", "🔬"),
    ("categories", "Categories", "🏷️"),
    ("search", "Search", "🔍"),
    ("settings", "Settings", "⚙️"),
]


class Sidebar(ctk.CTkFrame):
    """The vertical navigation bar on the left of the window."""

    def __init__(
        self,
        master,
        on_navigate: Callable[[str], None],
        on_theme_change: Callable[[str], None],
        initial_theme: str = "dark",
        timer_service=None,
    ) -> None:
        super().__init__(master, width=210, corner_radius=0, fg_color=theme.SIDEBAR_COLOR)
        self.grid_propagate(False)   # keep the fixed width regardless of content
        self.on_navigate = on_navigate
        self.on_theme_change = on_theme_change
        self.timer_service = timer_service
        self._buttons: Dict[str, ctk.CTkButton] = {}
        self._active_key: str | None = None

        # App title / brand, with a crimson divider beneath it.
        ctk.CTkLabel(
            self, text="⏱  TIME TRACKER", anchor="w",
            font=ctk.CTkFont(family=theme.DISPLAY_FAMILY, size=16, weight="bold"),
        ).pack(anchor="w", padx=20, pady=(24, 6))
        ctk.CTkFrame(self, height=2, corner_radius=0, fg_color=theme.ACCENT).pack(
            fill="x", padx=20, pady=(0, 16))

        # One button per screen (mono labels, red-tinted hover).
        for key, label, icon in NAV_ITEMS:
            btn = ctk.CTkButton(
                self, text=f"  {icon}   {label}", anchor="w", height=42,
                corner_radius=8, fg_color="transparent",
                text_color=("gray10", "#C7CCD1"), hover_color=("#EDECEC", "#1A0E10"),
                font=ctk.CTkFont(family=theme.MONO_FAMILY, size=13),
                command=lambda k=key: self.on_navigate(k),
            )
            btn.pack(fill="x", padx=12, pady=2)
            self._buttons[key] = btn

            # A tiny "recording" indicator directly under the Timer button,
            # visible from any screen, so you always know time is being
            # tracked even while looking at a different part of the app.
            if key == "timer":
                self._recording_dot = ctk.CTkLabel(
                    self, text="● Recording", text_color="#D0463B",
                    font=ctk.CTkFont(size=11, weight="bold"),
                )

        if timer_service is not None:
            bus.subscribe(TIMER_STATE_CHANGED, self._refresh_recording_dot)
            self._refresh_recording_dot()

        # Appearance switch pinned to the bottom.
        ctk.CTkLabel(
            self, text=theme.spaced("APPEARANCE"),
            font=ctk.CTkFont(family=theme.MONO_FAMILY, size=11, weight="bold"),
            text_color=theme.MONO_LABEL,
        ).pack(anchor="w", padx=20, pady=(20, 4), side="bottom")
        self.theme_menu = ctk.CTkOptionMenu(
            self, values=["Dark", "Light", "System"],
            command=lambda choice: self.on_theme_change(choice.lower()),
        )
        self.theme_menu.set(initial_theme.capitalize())
        self.theme_menu.pack(fill="x", padx=12, pady=(0, 20), side="bottom")

    def _refresh_recording_dot(self, **_payload) -> None:
        """Show or hide the small "Recording" hint under the Timer button."""
        if self.timer_service is not None and self.timer_service.current_state().is_active:
            self._recording_dot.pack(anchor="w", padx=24, pady=(0, 4),
                                     after=self._buttons["timer"])
        else:
            self._recording_dot.pack_forget()

    def set_active(self, key: str) -> None:
        """Highlight the button for the current screen, un-highlight the rest."""
        for k, btn in self._buttons.items():
            if k == key:
                btn.configure(fg_color=theme.ACCENT, text_color="white")
            else:
                btn.configure(fg_color="transparent",
                              text_color=("gray10", "#C7CCD1"))
        self._active_key = key
