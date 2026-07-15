"""
Color tokens + style helpers for the mobile app — the same crimson/near-black
"REVENGE" identity as the desktop app's ``app/ui/theme.py``, expressed as
plain hex strings (Flet accepts a hex string directly wherever it wants a
color, so there is no need for a custom ColorScheme object).

Only the dark palette is ported for this first milestone — the cinematic
identity is dark on desktop too; light mode can follow later.

Design principle for this file — "fierce but classic, not cheap": one accent
color used deliberately, glow reserved for a couple of focal moments (not a
default on every card), gradients kept subtle, corners kept modest. See the
helpers below (`glow`, `subtle_gradient`, `card`) for where that restraint is
encoded so screens get it for free instead of re-deciding it per screen.
"""

from __future__ import annotations

import flet as ft

# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------

ACCENT = "#E11D2A"
ACCENT_HOVER = "#B3141D"
ACCENT_DEEP = "#8A1219"  # dark end of accent gradients / pressed states
ACCENT_GLOW = "#5A1A1F"  # base color for the (sparing) glow shadows
KICKER_RED = "#FF4655"  # brighter red for small tracked labels over imagery

BG = "#0A0A0C"
CARD = "#141418"
CARD_BORDER = "#2A1A1D"
SIDEBAR = "#0E0E12"

HEADLINE = "#FFFFFF"
MUTED_TEXT = "#8B9099"
MONO_LABEL = "#7A828C"

NEUTRAL_BTN = "#26262B"
NEUTRAL_BTN_HOVER = "#33333A"

STOP_RED = "#D0463B"

STATUS_COMPLETE = "#2E9E5B"
STATUS_PARTIAL = "#E0A100"
STATUS_FAILED = "#D0463B"
STATUS_NEUTRAL = "#6B7280"

# ---------------------------------------------------------------------------
# Typography
# ---------------------------------------------------------------------------
# Two bundled families only (see mobile/assets/fonts) — fewer typefaces reads
# more disciplined than mixing three. Bebas Neue does double duty for
# headlines and big stat numbers; Plex Mono carries tracked labels and clocks.

DISPLAY_FAMILY = "Bebas Neue"
NUMBER_FAMILY = "Bebas Neue"
MONO_FAMILY = "IBM Plex Mono"
MONO_FAMILY_SEMIBOLD = "IBM Plex Mono SemiBold"

HERO_HEADLINE_SIZE = 40
HERO_KICKER_SIZE = 11
HERO_SUBTITLE_SIZE = 13
STAT_NUMBER_SIZE = 30
STAT_LABEL_SIZE = 10
SECTION_LABEL_SIZE = 12
TIMER_CLOCK_SIZE = 52

TRACK_TIGHT = 1.0
TRACK_WIDE = 3.0

# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------


def tracked(
    text: str,
    size: float = SECTION_LABEL_SIZE,
    color: str = MONO_LABEL,
    family: str = MONO_FAMILY,
    weight: ft.FontWeight | None = None,
    spacing: float = TRACK_WIDE,
    text_align: ft.TextAlign | None = None,
) -> ft.Text:
    """Mono/tracked text — the "tactical readout" voice (kickers, labels, clock)."""
    return ft.Text(
        text,
        text_align=text_align,
        style=ft.TextStyle(
            size=size,
            weight=weight,
            font_family=family,
            color=color,
            letter_spacing=spacing,
        ),
    )


def section_label(text: str, color: str = MONO_LABEL) -> ft.Text:
    """A small uppercase tracked header, e.g. "MISSION TARGETS"."""
    return tracked(
        text.upper(), size=SECTION_LABEL_SIZE, color=color,
        family=MONO_FAMILY_SEMIBOLD, spacing=TRACK_TIGHT,
    )


def display(
    text: str,
    size: float = HERO_HEADLINE_SIZE,
    color: str = HEADLINE,
    spacing: float = TRACK_WIDE,
) -> ft.Text:
    """The fierce voice — Bebas Neue, for hero headlines and screen titles."""
    return ft.Text(
        text,
        style=ft.TextStyle(
            size=size, font_family=DISPLAY_FAMILY, color=color, letter_spacing=spacing,
        ),
    )


def number(text: str, size: float = STAT_NUMBER_SIZE, color: str = HEADLINE) -> ft.Text:
    """A big stat number — Bebas Neue at stat-card scale (scoreboard digits)."""
    return ft.Text(
        text, text_align=ft.TextAlign.CENTER,
        style=ft.TextStyle(size=size, font_family=NUMBER_FAMILY, color=color),
    )


# ---------------------------------------------------------------------------
# Shape / effect helpers — restraint lives here, not per-screen
# ---------------------------------------------------------------------------


def glow(color: str = ACCENT, blur: float = 20, spread: float = 0) -> ft.BoxShadow:
    """A soft, low-opacity glow. Reserved for ONE focal element at a time —
    the primary CTA button or the timer card while actively tracking — never
    a default on generic cards (that reads as gaudy, not fierce)."""
    return ft.BoxShadow(
        blur_radius=blur, spread_radius=spread,
        color=ft.Colors.with_opacity(0.35, color),
        offset=ft.Offset(0, 0),
    )


def subtle_gradient(
    top: str = "#151013", bottom: str = BG,
) -> ft.LinearGradient:
    """A barely-there vertical wash with a hint of red — not a saturated blast."""
    return ft.LinearGradient(
        begin=ft.Alignment.TOP_CENTER, end=ft.Alignment.BOTTOM_CENTER,
        colors=[top, bottom],
    )


def card(
    content: ft.Control,
    padding: float = 14,
    radius: float = 12,
    glow_effect: bool = False,
    border_color: str = CARD_BORDER,
) -> ft.Container:
    """The standard card: crisp 1px crimson-tinted border, modest radius.
    `glow_effect=True` is the rare exception (see `glow()`), not the norm."""
    return ft.Container(
        content=content,
        bgcolor=CARD,
        border=ft.Border.all(1, border_color),
        border_radius=radius,
        padding=padding,
        shadow=glow() if glow_effect else None,
    )
