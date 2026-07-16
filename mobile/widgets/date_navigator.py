"""A consistent, thumb-friendly period navigator for mobile screens."""

from __future__ import annotations

from typing import Callable

import flet as ft

from mobile import theme


def date_navigator(
    label: ft.Text,
    on_previous: Callable,
    on_next: Callable,
    on_today: Callable | None = None,
) -> ft.Control:
    """Return the shared previous/current/next control used outside Calendar.

    The buttons deliberately have a 44px hit target, rather than the smaller
    default icon/text controls, so changing dates is comfortable one-handed.
    """
    controls: list[ft.Control] = [
        ft.IconButton(
            icon=ft.Icons.CHEVRON_LEFT,
            icon_color=theme.HEADLINE,
            bgcolor=theme.NEUTRAL_BTN,
            width=44,
            height=44,
            on_click=on_previous,
        ),
        ft.Container(
            height=44,
            alignment=ft.Alignment.CENTER,
            padding=ft.Padding.symmetric(horizontal=12),
            border_radius=10,
            bgcolor=theme.CARD,
            border=ft.Border.all(1, theme.CARD_BORDER),
            content=label,
        ),
        ft.IconButton(
            icon=ft.Icons.CHEVRON_RIGHT,
            icon_color=theme.HEADLINE,
            bgcolor=theme.NEUTRAL_BTN,
            width=44,
            height=44,
            on_click=on_next,
        ),
    ]
    if on_today:
        controls.append(
            ft.Container(
                height=44,
                alignment=ft.Alignment.CENTER,
                padding=ft.Padding.symmetric(horizontal=12),
                border_radius=10,
                bgcolor=theme.NEUTRAL_BTN,
                content=theme.tracked(
                    "TODAY",
                    size=11,
                    color=theme.HEADLINE,
                    family=theme.MONO_FAMILY_SEMIBOLD,
                    spacing=0.7,
                ),
                ink=True,
                on_click=on_today,
            )
        )
    return ft.Row(
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=8,
        controls=controls,
    )
