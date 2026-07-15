"""
The base class every screen inherits from.

It gives each view three things for free:
  * a reference to the shared :class:`AppContext` (so it can reach the services),
  * automatic refreshing — when data changes anywhere, a visible view rebuilds
    itself, and a hidden one waits until it is shown again (so we never waste
    effort redrawing screens nobody is looking at), and
  * ``on_show`` / ``on_hide`` hooks the window calls as you navigate.
"""

from __future__ import annotations

import customtkinter as ctk

from app.services.context import AppContext
from app.utils.event_bus import bus, DATA_CHANGED


class BaseView(ctk.CTkFrame):
    """Common behaviour for all main screens."""

    #: Shown at the top of the screen. Subclasses override this.
    title = "Screen"

    def __init__(self, master, context: AppContext) -> None:
        super().__init__(master, fg_color="transparent")
        self.ctx = context
        # Set by the main window after construction, so a view can ask the shell
        # to do window-level things (like changing the theme). May stay None.
        self.app_window = None
        self._is_active = False
        # Listen for data changes for this view's whole life. We only actually
        # redraw when the view is the one on screen (see the handler below).
        bus.subscribe(DATA_CHANGED, self._on_data_changed)

    # -- Navigation hooks the window calls ------------------------------ #
    def on_show(self) -> None:
        """Called when this view becomes the visible one."""
        self._is_active = True
        self.refresh()

    def on_hide(self) -> None:
        """Called when the user navigates away from this view."""
        self._is_active = False

    # -- Auto-refresh --------------------------------------------------- #
    def _on_data_changed(self, **_payload) -> None:
        if self._is_active:
            self.refresh()

    def refresh(self) -> None:
        """Rebuild the screen's contents from the latest data.

        Subclasses override this. The default does nothing so a view that has no
        dynamic content still works.
        """
