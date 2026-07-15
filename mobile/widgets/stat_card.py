"""A small tile showing one headline number — the mobile equivalent of app/ui/widgets/stat_card.py."""

from __future__ import annotations

import flet as ft

from mobile import theme


def stat_card(title: str, value: str, subtitle: str = "", accent: str = theme.ACCENT) -> ft.Container:
    column_controls = [
        ft.Text(value, size=24, weight=ft.FontWeight.BOLD, color=theme.HEADLINE,
                text_align=ft.TextAlign.CENTER),
        ft.Container(width=28, height=3, bgcolor=accent, border_radius=2),
        ft.Text(title.upper(), size=10, color=theme.MONO_LABEL, text_align=ft.TextAlign.CENTER),
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
