"""
Cinematic hero banner — the mobile equivalent of the desktop's Pillow-
composited app/ui/widgets/hero_banner.py. Built natively from Flet's Stack +
gradient Containers instead of a baked bitmap, since Flet supports real
gradients and letter-spacing directly (no need to pre-render an image).

Restrained per the "classic, not cheap" rule: the wash/scrim gradients are
understated (a hint of red, not a saturated blast), and there is no glow on
the banner itself — the fury comes from the photo + heavy tracked type.
"""

from __future__ import annotations

import asyncio
import datetime

import flet as ft

from mobile import theme

DEFAULT_HEIGHT = 270
# The Timer is the primary live-work screen, so its hero needs enough vertical
# room to retain the character's shoulders instead of reading as a thin crop.
COMPACT_HEIGHT = 220


def hero_banner(
    page: ft.Page,
    kicker: str = "OPERATION : DISCIPLINE",
    headline: str = "REVENGE",
    subtitle: str = "",
    height: float = DEFAULT_HEIGHT,
    with_clock: bool = False,
    image_align: ft.Alignment = ft.Alignment.CENTER,
) -> ft.Control:
    text_column_controls: list[ft.Control] = [
        theme.tracked(kicker.upper(), size=theme.HERO_KICKER_SIZE,
                      color=theme.KICKER_RED, spacing=theme.TRACK_WIDE),
        theme.display(headline.upper(), size=theme.HERO_HEADLINE_SIZE),
    ]
    if subtitle:
        text_column_controls.append(
            theme.tracked(subtitle, size=theme.HERO_SUBTITLE_SIZE,
                          color="#C7CBD1", spacing=0.4)
        )

    overlay_children: list[ft.Control] = [
        # Photo, filling the stack at full brightness — this is the prominent
        # element now, not something to dim behind overlays.
        ft.Image(
            src="hero.jpg",
            fit=ft.BoxFit.COVER,
            align=image_align,
            expand=True,
        ),
        # Understated left-to-right crimson wash (darkest where the text sits).
        ft.Container(
            expand=True,
            gradient=ft.LinearGradient(
                begin=ft.Alignment.CENTER_LEFT, end=ft.Alignment.CENTER_RIGHT,
                colors=[ft.Colors.with_opacity(0.45, "#3D0B10"),
                        ft.Colors.with_opacity(0.0, "#3D0B10")],
            ),
        ),
        # Bottom-to-top dark scrim, only as tall as the text needs for contrast
        # — kept shallow so a taller banner still shows most of the image clean.
        ft.Container(
            expand=True,
            gradient=ft.LinearGradient(
                begin=ft.Alignment.BOTTOM_CENTER, end=ft.Alignment.TOP_CENTER,
                colors=[ft.Colors.with_opacity(0.7, "#050506"),
                        ft.Colors.with_opacity(0.0, "#050506")],
                stops=[0.0, 0.55],
            ),
        ),
        ft.Container(
            left=18, right=18, bottom=16,
            content=ft.Column(spacing=4, tight=True, controls=text_column_controls),
        ),
    ]

    clock_text: ft.Text | None = None
    if with_clock:
        clock_text = theme.tracked(
            _now_hhmm(), size=22, color=theme.HEADLINE,
            family=theme.MONO_FAMILY_SEMIBOLD, spacing=1,
        )
        overlay_children.append(
            ft.Container(top=16, right=18, content=clock_text)
        )

    banner = ft.Container(
        height=height,
        border_radius=16,
        content=ft.Stack(controls=overlay_children, fit=ft.StackFit.EXPAND),
    )

    if clock_text is not None:
        page.run_task(_tick_clock, clock_text, page)

    return banner


def _now_hhmm() -> str:
    return datetime.datetime.now().strftime("%H:%M")


async def _tick_clock(clock_text: ft.Text, page: ft.Page) -> None:
    # Checking clock_text.page to detect "removed from the page" doesn't work
    # here — touching .page raises RuntimeError rather than returning None,
    # both before the control is first attached and after it's detached. Sleep
    # first (so we never touch it before the caller's page.update() has run),
    # then just stop on the first failure — that covers "screen changed away"
    # without needing to tell the two cases apart.
    while True:
        await asyncio.sleep(15)
        try:
            clock_text.value = _now_hhmm()
            page.update()
        except Exception:
            break
