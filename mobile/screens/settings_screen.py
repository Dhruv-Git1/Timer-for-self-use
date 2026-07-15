"""
The mobile Settings screen — appearance (theme) and export as CSV/JSON (no
pandas — see app/export/exporter.py's to_csv). Desktop's Excel export and
backup/restore stay desktop-only for this milestone: Excel needs
pandas+openpyxl, and backup/restore assumes a desktop filesystem you browse
with a file manager, neither of which fits a first mobile pass.
"""

from __future__ import annotations

import flet as ft

from mobile import theme

_THEMES = ["Dark", "Light", "System"]
_THEME_MODES = {"Dark": ft.ThemeMode.DARK, "Light": ft.ThemeMode.LIGHT, "System": ft.ThemeMode.SYSTEM}


def build(page: ft.Page, ctx) -> ft.Control:
    status_text = ft.Text("", size=12, color=theme.MUTED_TEXT)
    theme_row = ft.Row(spacing=6)

    def _set_theme(mode: str) -> None:
        ctx.set_setting("theme", mode.lower())
        for btn in theme_row.controls:
            btn.bgcolor = theme.ACCENT if btn.data == mode else theme.NEUTRAL_BTN
        page.theme_mode = _THEME_MODES[mode]
        page.update()

    current_theme = ctx.get_setting("theme", "dark").capitalize()
    for mode in _THEMES:
        theme_row.controls.append(
            ft.Container(
                data=mode, padding=ft.Padding.symmetric(vertical=8, horizontal=16),
                border_radius=8, bgcolor=theme.ACCENT if mode == current_theme else theme.NEUTRAL_BTN,
                content=ft.Text(mode, size=13, color="#FFFFFF"),
                on_click=lambda e, m=mode: _set_theme(m),
            )
        )

    def _export(fmt: str) -> None:
        try:
            ok, path = ctx.export_service.to_csv() if fmt == "csv" else ctx.export_service.to_json()
            status_text.value = f"✓ Exported to {path}" if ok else "✗ Export failed."
        except Exception as exc:  # noqa: BLE001 - surface any export problem
            status_text.value = f"✗ Export failed: {exc}"
        page.update()

    return ft.Column(
        expand=True, scroll=ft.ScrollMode.AUTO, spacing=20,
        controls=[
            ft.Text("Settings", size=22, weight=ft.FontWeight.BOLD, color=theme.HEADLINE),

            ft.Text("Appearance", size=14, weight=ft.FontWeight.BOLD, color=theme.HEADLINE),
            theme_row,

            ft.Text("Export data", size=14, weight=ft.FontWeight.BOLD, color=theme.HEADLINE),
            ft.Row(controls=[
                ft.Button("CSV", on_click=lambda e: _export("csv")),
                ft.Button("JSON", on_click=lambda e: _export("json")),
            ]),
            status_text,

            ft.Text("About", size=14, weight=ft.FontWeight.BOLD, color=theme.HEADLINE),
            ft.Text("Personal Time Tracker & Productivity Dashboard\n"
                    "Offline — your data never leaves this device.",
                    size=12, color=theme.MUTED_TEXT),
        ],
    )
