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
from mobile.widgets.fury import fury_button

_THEMES = ["Dark", "Light", "System"]
_THEME_MODES = {"Dark": ft.ThemeMode.DARK, "Light": ft.ThemeMode.LIGHT, "System": ft.ThemeMode.SYSTEM}


def build(page: ft.Page, ctx) -> ft.Control:
    status_text = ft.Text("", size=12, color=theme.MUTED_TEXT)
    theme_row = ft.Row(spacing=6)
    score_column = ft.Column(spacing=8)

    def _toggle_score_inclusion(category, included: bool) -> None:
        category.include_in_daily_score = included
        ctx.category_service.update(category)

    def _set_score_weight(category, weight_str: str) -> None:
        category.score_weight = int(weight_str)
        ctx.category_service.update(category)

    def _refresh_score_section() -> None:
        score_column.controls.clear()
        scoreable = [c for c in ctx.category_service.list_categories() if c.has_target]
        if not scoreable:
            score_column.controls.append(
                ft.Text("Give a category a daily goal to include it in Today's score.",
                        size=12, color=theme.MUTED_TEXT)
            )
            return
        for category in scoreable:
            score_column.controls.append(
                ft.Row(controls=[
                    ft.Icon(ft.Icons.CIRCLE, size=11, color=category.color),
                    ft.Text(category.name, size=13, color=theme.HEADLINE, expand=True),
                    ft.Dropdown(
                        value=str(category.score_weight),
                        options=[ft.DropdownOption(key=str(w), text=f"{w}x") for w in range(1, 6)],
                        width=68,
                        on_select=lambda e, c=category: _set_score_weight(c, e.control.value),
                    ),
                    ft.Switch(
                        value=category.include_in_daily_score,
                        active_color=theme.ACCENT,
                        on_change=lambda e, c=category: _toggle_score_inclusion(c, e.control.value),
                    ),
                ])
            )

    _refresh_score_section()

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
                content=theme.tracked(mode.upper(), size=12, color=theme.HEADLINE,
                                       family=theme.MONO_FAMILY_SEMIBOLD, spacing=0.6),
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
            theme.display("Settings", size=28),

            theme.section_label("Appearance"),
            theme_row,

            theme.section_label("Today's Score"),
            ft.Text(
                "Today's score is a weighted average: each category below is "
                "0-100% complete toward its own daily goal (time, check-off, or "
                "counter), then combined using the weight next to it — a 3x "
                "category counts 3 times as much as a 1x one. Turn a category "
                "off to leave it out of the score entirely; nothing else about "
                "it changes.",
                size=12, color=theme.MUTED_TEXT,
            ),
            score_column,

            theme.section_label("Export data"),
            ft.Row(controls=[
                fury_button("CSV", kind="secondary", on_click=lambda e: _export("csv")),
                fury_button("JSON", kind="secondary", on_click=lambda e: _export("json")),
            ]),
            status_text,

            theme.section_label("About"),
            ft.Text("Personal Time Tracker & Productivity Dashboard\n"
                    "Offline — your data never leaves this device.",
                    size=12, color=theme.MUTED_TEXT),
        ],
    )
