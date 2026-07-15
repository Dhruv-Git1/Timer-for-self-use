"""A plain "coming soon" screen for tabs/destinations not yet built in this milestone."""

from __future__ import annotations

import flet as ft

from mobile import theme


def build(title: str, message: str) -> ft.Control:
    return ft.Column(
        expand=True,
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Icon(ft.Icons.CONSTRUCTION, size=40, color=theme.MUTED_TEXT),
            ft.Text(title, size=18, weight=ft.FontWeight.BOLD, color=theme.HEADLINE),
            ft.Text(message, size=13, color=theme.MUTED_TEXT, text_align=ft.TextAlign.CENTER),
        ],
    )
