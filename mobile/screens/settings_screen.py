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


def build(page: ft.Page, ctx) -> ft.Control:
    status_text = ft.Text("", size=12, color=theme.MUTED_TEXT)
    score_column = ft.Column(spacing=8)

    def _toggle_score_inclusion(category, included: bool) -> None:
        category.include_in_daily_score = included
        ctx.category_service.update(category)
        _refresh_score_section()
        page.update()

    def _set_score_weight(category, value: str | None) -> None:
        if value is None:
            return
        previous_weight = category.score_weight
        category.score_weight = int(value)
        ok, _message, _ = ctx.category_service.update(category)
        if not ok:
            category.score_weight = previous_weight
        _refresh_score_section()
        page.update()

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
                theme.card(
                    ft.Column(
                        spacing=6,
                        controls=[
                            ft.Row(
                                controls=[
                                    ft.Icon(
                                        ft.Icons.CIRCLE,
                                        size=11,
                                        color=category.color,
                                    ),
                                    ft.Column(
                                        expand=True,
                                        spacing=1,
                                        controls=[
                                            ft.Text(
                                                category.name,
                                                size=13,
                                                color=theme.HEADLINE,
                                            ),
                                            ft.Text(
                                                f"Weight {category.score_weight}\u00d7 \u2014 counts "
                                                f"{category.score_weight} share"
                                                f"{'s' if category.score_weight != 1 else ''} "
                                                "in today's score",
                                                size=11,
                                                color=theme.MUTED_TEXT,
                                            ),
                                        ],
                                    ),
                                    ft.Switch(
                                        value=category.include_in_daily_score,
                                        active_color=theme.ACCENT,
                                        on_change=lambda e, c=category: _toggle_score_inclusion(
                                            c, e.control.value
                                        ),
                                    ),
                                ]
                            ),
                            ft.Row(
                                alignment=ft.MainAxisAlignment.END,
                                controls=[
                                    ft.Dropdown(
                                        label="Score weight",
                                        value=str(category.score_weight),
                                        width=145,
                                        options=[
                                            ft.DropdownOption(
                                                key=str(weight), text=f"{weight}\u00d7"
                                            )
                                            for weight in range(1, 6)
                                        ],
                                        on_select=lambda e, c=category: _set_score_weight(
                                            c, e.control.value
                                        ),
                                    ),
                                ],
                            ),
                        ],
                    ),
                    padding=12,
                    radius=10,
                )
            )

    _refresh_score_section()

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
            theme.card(
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.NIGHTLIGHT_ROUND, color=theme.KICKER_RED, size=22),
                        ft.Column(
                            spacing=2,
                            controls=[
                                theme.tracked(
                                    "FOCUS DARK",
                                    size=12,
                                    color=theme.HEADLINE,
                                    family=theme.MONO_FAMILY_SEMIBOLD,
                                    spacing=0.8,
                                ),
                                ft.Text(
                                    "The high-contrast study theme is active everywhere.",
                                    size=11,
                                    color=theme.MUTED_TEXT,
                                ),
                            ],
                        ),
                    ]
                ),
                padding=14,
            ),

            theme.section_label("Today's Score"),
            ft.Text(
                "Today's score is a weighted average. Each included category is "
                "0-100% complete toward its own daily goal (time, check-off, or "
                "counter); a weight of 2\u00d7 counts twice as much as a weight of 1\u00d7. "
                "Turn a category off to leave it out of the score.",
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
