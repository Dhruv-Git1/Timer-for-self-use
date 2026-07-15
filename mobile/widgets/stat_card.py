"""A small tile showing one headline number — the mobile equivalent of app/ui/widgets/stat_card.py."""

from __future__ import annotations

import flet as ft

from mobile import theme


def stat_card(title: str, value: str, subtitle: str = "", accent: str = theme.ACCENT) -> ft.Container:
    column_controls = [
        theme.number(value, size=theme.STAT_NUMBER_SIZE),
        ft.Container(width=28, height=3, bgcolor=accent, border_radius=2),
        theme.tracked(title.upper(), size=theme.STAT_LABEL_SIZE, color=theme.MONO_LABEL,
                      family=theme.MONO_FAMILY_SEMIBOLD, spacing=theme.TRACK_TIGHT,
                      text_align=ft.TextAlign.CENTER),
    ]
    if subtitle:
        column_controls.append(
            ft.Text(subtitle, size=10, color=theme.MUTED_TEXT, text_align=ft.TextAlign.CENTER)
        )
    return ft.Container(
        col=6,
        bgcolor=theme.CARD,
        border=ft.Border.all(1, theme.CARD_BORDER),
        border_radius=12,
        padding=14,
        content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=4,
            controls=column_controls,
        ),
    )
