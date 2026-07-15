"""
Theme helpers and the app-wide color/font palette.

This is the single place the "REVENGE" cinematic look is defined: a dark,
near-black background with an aggressive crimson-red accent, cool-grey text, and
tech-y monospace labels over a heavy display face for big numbers/headlines.

Two things beyond CustomTkinter's own theming live here:
  * the semantic color tokens (ACCENT, CARD_COLOR, …) every screen reads, so a
    color change here re-themes the whole app at once, and
  * font-family resolution (``init_fonts``) that picks the best monospace and
    heavy-display fonts actually installed on this Windows machine, with safe
    fallbacks.

Colors are kept as (light, dark) pairs — CustomTkinter picks the right one for
the current appearance mode — but the *dark* entry is the real identity; light
mode is a supported-but-lesser variant.
"""

from __future__ import annotations

import customtkinter as ctk

from app.charts.chart_factory import ChartStyle

# --------------------------------------------------------------------------- #
# Brand / accent — crimson red
# --------------------------------------------------------------------------- #
# Vivid and saturated so it reads as aggressive on near-black, and clearly
# distinct from the muted "failure" brick-red used for missed goals.
ACCENT = ("#E11D2A", "#E11D2A")        # buttons, progress fill, active nav item
ACCENT_HOVER = ("#B3141D", "#B3141D")  # ~15% darker for hover
ACCENT_GLOW = ("#5A1A1F", "#5A1A1F")   # faint red used for card-border tint
# A brighter red for small text (a tiny red label on near-black needs more
# luminance to stay legible than a big red fill does).
KICKER_RED = ("#FF4655", "#FF4655")

# --------------------------------------------------------------------------- #
# Surfaces
# --------------------------------------------------------------------------- #
BG = ("#F4F5F7", "#0A0A0C")            # window / content background (near-black)
CARD_COLOR = ("#FFFFFF", "#141418")    # a card, slightly lifted from the bg
CARD_BORDER = ("#E2E6EA", "#2A1A1D")   # subtle red-tinted hairline border
SIDEBAR_COLOR = ("#F0F1F4", "#0E0E12")  # sidebar, a hair different from content

# --------------------------------------------------------------------------- #
# Text
# --------------------------------------------------------------------------- #
HEADLINE_WHITE = ("#111114", "#FFFFFF")
MUTED_TEXT = ("#6B7280", "#8B9099")    # secondary labels (cool grey)
MONO_LABEL = ("#7A828C", "#7A828C")    # tiny uppercase mono stat labels

# Neutral secondary button (replaces every old hardcoded "gray40"/"gray30").
NEUTRAL_BTN = ("#E4E6EA", "#26262B")
NEUTRAL_BTN_HOVER = ("#D4D8DD", "#33333A")

# --------------------------------------------------------------------------- #
# Fonts — resolved for real at startup by init_fonts()
# --------------------------------------------------------------------------- #
# These defaults are overwritten by init_fonts() with whatever is actually
# installed. Consolas and Arial Black both ship with Windows 11, so these are
# safe even if resolution somehow does not run.
MONO_FAMILY = "Consolas"
DISPLAY_FAMILY = "Arial Black"

# Font-size constants used across the hero, cards and section headers.
HERO_HEADLINE_SIZE = 56
HERO_KICKER_SIZE = 12
HERO_SUBTITLE_SIZE = 15
CLOCK_SIZE = 40
DATE_SIZE = 12
STAT_NUMBER_SIZE = 34
STAT_LABEL_SIZE = 10
SECTION_LABEL_SIZE = 13


def init_fonts(root) -> None:
    """Pick the best installed monospace and display fonts, with fallbacks.

    ``tkinter.font.families()`` needs a live Tk root, so this must be called
    once right after the main window exists and *before* any view or the sidebar
    builds its fonts. It rewrites the module-level ``MONO_FAMILY`` /
    ``DISPLAY_FAMILY`` so every widget built afterwards uses the resolved names.
    """
    global MONO_FAMILY, DISPLAY_FAMILY
    import tkinter.font as tkfont

    available = {f.lower() for f in tkfont.families(root)}

    def pick(candidates, fallback):
        for name in candidates:
            if name.lower() in available:
                return name
        return fallback

    # Both Cascadia Mono and Consolas ship with Windows 11; Consolas is the floor.
    MONO_FAMILY = pick(["Cascadia Mono", "Consolas", "Courier New"], "TkFixedFont")
    # All three ship with Windows 11; Arial Black best matches the wide, heavy
    # "REVENGE" weight.
    DISPLAY_FAMILY = pick(["Arial Black", "Bahnschrift SemiBold", "Impact"], "Segoe UI")


def spaced(text: str) -> str:
    """Add letter-spacing to a short display string.

    Tk fonts cannot do real tracking, so for a handful of short UPPERCASE labels
    (section headers, stat labels) we insert a thin space between characters to
    fake that wide, tracked-out look. Use only for short display strings — never
    body text, since it breaks copy/paste and kerning.
    """
    return " ".join(text)


# --------------------------------------------------------------------------- #
# Appearance mode + chart styling (unchanged behaviour)
# --------------------------------------------------------------------------- #
def apply_saved_mode(mode: str) -> None:
    """Set the global appearance mode from a stored setting.

    ``mode`` is one of "dark", "light" or "system"; anything unexpected falls
    back to dark. CustomTkinter wants the capitalised spelling. The cinematic
    identity is the dark theme; light is supported but lesser.
    """
    mode = (mode or "dark").lower()
    ctk.set_appearance_mode({"dark": "Dark", "light": "Light"}.get(mode, "System"))


def current_mode() -> str:
    """The resolved mode actually on screen: "Dark" or "Light"."""
    return ctk.get_appearance_mode()


def chart_style() -> ChartStyle:
    """The ChartStyle matching what is currently on screen."""
    return ChartStyle.dark() if current_mode() == "Dark" else ChartStyle.light()
