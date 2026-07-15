"""
Small style-kit widgets for the fierce-but-classic mobile UI: a custom
gradient/glow CTA button, a crimson progress bar with a fill-in-on-mount
helper, tactical segmented-control chips, and a fade+rise screen-entrance
wrapper.

Kept restrained per the design principle in mobile/theme.py: gradient+glow is
reserved for the ONE primary action per screen, chips/cards stay flat and
bordered, and the only motion is a single smooth fade/rise — no bounce, no
multiple things animating loudly at once.
"""

from __future__ import annotations

import asyncio

import flet as ft

from mobile import theme


def fury_button(
    text: str,
    on_click,
    icon: str | None = None,
    kind: str = "primary",
    disabled: bool = False,
    expand: bool | int = False,
) -> ft.Container:
    """A custom CTA (Flet's native Button can't take a gradient fill).
    kind="primary" is the one gradient+glow surface on a screen — reserve it
    for the single most important action. "danger" (Stop) and "secondary"
    stay flat."""
    gradient = None
    shadow = None
    if kind == "primary":
        bgcolor = None
        gradient = ft.LinearGradient(
            begin=ft.Alignment.CENTER_LEFT, end=ft.Alignment.CENTER_RIGHT,
            colors=[theme.ACCENT, theme.ACCENT_DEEP],
        )
        shadow = theme.glow(theme.ACCENT, blur=16)
    elif kind == "danger":
        bgcolor = theme.STOP_RED
    else:
        bgcolor = theme.NEUTRAL_BTN

    row: list[ft.Control] = []
    if icon:
        row.append(ft.Icon(icon, color=theme.HEADLINE, size=17))
    row.append(theme.tracked(text.upper(), size=13, color=theme.HEADLINE,
                              family=theme.MONO_FAMILY_SEMIBOLD, spacing=1.0))

    return ft.Container(
        bgcolor=bgcolor,
        gradient=None if disabled else gradient,
        shadow=None if disabled else shadow,
        border_radius=10,
        padding=ft.Padding.symmetric(vertical=13, horizontal=22),
        opacity=0.4 if disabled else 1.0,
        ink=not disabled,
        expand=expand,
        content=ft.Row(row, alignment=ft.MainAxisAlignment.CENTER, spacing=8, tight=True),
        on_click=None if disabled else on_click,
    )


def fury_progress(
    value: float, color: str = theme.ACCENT, height: float = 8, animate_in: bool = True,
) -> ft.ProgressBar:
    """A crimson progress bar. Flat fill by design — a gradient here reads as
    a loud game health-bar, not classic.

    `animate_in=True` (the default) starts at 0 so it can be paired with
    `animate_fill_in` right after a screen's first update, for a one-time
    fill-in-on-mount. Set `animate_in=False` on sections that rebuild often
    from user interaction (e.g. the Timer screen's goal bars, which refresh
    on nearly every tap) — replaying a fill-from-zero on every refresh would
    read as noisy, not fierce."""
    return ft.ProgressBar(
        value=0 if animate_in else value, color=color, bgcolor=theme.NEUTRAL_BTN,
        border_radius=height / 2, height=height, data=value,
    )


async def animate_fill_in(page: ft.Page, bars: list[ft.ProgressBar], delay: float = 0.15) -> None:
    """Call once per screen, right after its first page.update(), so every
    fury_progress bar on it fills in together instead of snapping full.

    Touching a control's `.page` raises rather than returning None if it
    hasn't been attached yet (this runs before the caller's own first
    page.update()) — so just attempt the update and swallow failure instead
    of trying to detect "not attached yet" beforehand."""
    await asyncio.sleep(delay)
    try:
        for bar in bars:
            bar.value = bar.data
        page.update()
    except Exception:
        pass


def chip(label: str, active: bool, on_click) -> ft.Container:
    """A tactical segmented-control pill — crimson when active, flat dark
    otherwise. Replaces the old bare ACCENT/NEUTRAL_BTN chip pattern."""
    return ft.Container(
        padding=ft.Padding.symmetric(vertical=8, horizontal=16),
        border_radius=8,
        bgcolor=theme.ACCENT if active else theme.NEUTRAL_BTN,
        content=theme.tracked(label.upper(), size=12, color=theme.HEADLINE,
                               family=theme.MONO_FAMILY_SEMIBOLD, spacing=0.6),
        on_click=on_click,
        ink=True,
        animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
    )


def screen_enter(control: ft.Control, page: ft.Page) -> ft.Control:
    """Wrap a screen's root control so it fades + rises in on mount. ONE
    smooth transition only — no bounce/elastic, nothing else animating at
    the same time."""
    control.opacity = 0
    control.offset = ft.Offset(0, 0.04)
    control.animate_opacity = ft.Animation(320, ft.AnimationCurve.EASE_OUT)
    control.animate_offset = ft.Animation(320, ft.AnimationCurve.EASE_OUT)
    page.run_task(_reveal, control, page)
    return control


async def _reveal(control: ft.Control, page: ft.Page) -> None:
    # Same reasoning as animate_fill_in above: touching .page raises rather
    # than returning None when the control isn't attached yet (this fires
    # before the caller's own page.update()), so just attempt it and swallow
    # failure rather than checking first.
    await asyncio.sleep(0.05)
    try:
        control.opacity = 1
        control.offset = ft.Offset(0, 0)
        page.update()
    except Exception:
        pass
