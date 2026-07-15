"""
A "stat card": a small tile showing one headline number.

Used all over the dashboard and statistics screens — "Productive time: 6h 30m",
"Current streak: 5", and so on. In the cinematic look each card is a near-black
tile with a thin red-tinted border, a big centered number in the heavy display
font, a short red accent underline, and a tiny uppercase tracked-out mono label.
An optional subtitle sits underneath.
"""

from __future__ import annotations

import customtkinter as ctk

from app.ui import theme


class StatCard(ctk.CTkFrame):
    """A tile displaying a title, a large centered value and an optional note."""

    def __init__(
        self,
        master,
        title: str,
        value: str = "—",
        subtitle: str = "",
        accent: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(
            master,
            corner_radius=12,
            fg_color=theme.CARD_COLOR,
            border_width=1,
            border_color=theme.CARD_BORDER,
            **kwargs,
        )
        # One centered column.
        self.grid_columnconfigure(0, weight=1)

        # Big number in the heavy display face.
        self._value = ctk.CTkLabel(
            self, text=value, anchor="center",
            font=ctk.CTkFont(family=theme.DISPLAY_FAMILY,
                             size=theme.STAT_NUMBER_SIZE, weight="bold"),
            text_color=theme.HEADLINE_WHITE,
        )
        self._value.grid(row=0, column=0, sticky="ew", padx=12, pady=(16, 2))

        # A short red accent underline. Kept as ``_accent_strip`` so the existing
        # update_values(accent=...) call keeps working; per-card colors (green,
        # amber, …) survive here as a subtle tick instead of a loud strip.
        self._accent_strip = ctk.CTkFrame(
            self, width=32, height=3, corner_radius=2,
            fg_color=accent or theme.ACCENT,
        )
        self._accent_strip.grid(row=1, column=0, pady=(0, 8))

        # Tiny uppercase tracked mono label.
        self._title = ctk.CTkLabel(
            self, text=theme.spaced(title.upper()), anchor="center",
            font=ctk.CTkFont(family=theme.MONO_FAMILY, size=theme.STAT_LABEL_SIZE),
            text_color=theme.MONO_LABEL,
        )
        self._title.grid(row=2, column=0, sticky="ew", padx=8)

        self._subtitle = ctk.CTkLabel(
            self, text=subtitle, anchor="center",
            font=ctk.CTkFont(family=theme.MONO_FAMILY, size=11),
            text_color=theme.MUTED_TEXT,
        )
        self._subtitle.grid(row=3, column=0, sticky="ew", padx=8, pady=(2, 14))

    def update_values(
        self, value: str, subtitle: str | None = None, accent: str | None = None
    ) -> None:
        """Change what the card shows without rebuilding it."""
        self._value.configure(text=value)
        if subtitle is not None:
            self._subtitle.configure(text=subtitle)
        if accent is not None:
            self._accent_strip.configure(fg_color=accent)
