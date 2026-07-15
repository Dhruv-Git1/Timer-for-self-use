"""
Color tokens for the mobile app — the same crimson/near-black "REVENGE"
identity as the desktop app's ``app/ui/theme.py``, expressed as plain hex
strings (Flet accepts a hex string directly wherever it wants a color, so
there is no need for a custom ColorScheme object).

Only the dark palette is ported for this first milestone — the cinematic
identity is dark on desktop too; light mode can follow later.
"""

from __future__ import annotations

ACCENT = "#E11D2A"
ACCENT_HOVER = "#B3141D"

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
