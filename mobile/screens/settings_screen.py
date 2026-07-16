"""
The mobile Settings screen — appearance (theme) and export as CSV/JSON (no
pandas — see app/export/exporter.py's to_csv). Desktop's Excel export and
backup/restore stay desktop-only for this milestone: Excel needs
pandas+openpyxl, and backup/restore assumes a desktop filesystem you browse
with a file manager, neither of which fits a first mobile pass.
"""

from __future__ import annotations

import os

import flet as ft

from app.services.gemini_service import DEFAULT_GEMINI_MODEL, normalize_gemini_model
from mobile import theme
from mobile.widgets.fury import fury_button


def build(page: ft.Page, ctx) -> ft.Control:
    status_text = ft.Text("", size=12, color=theme.MUTED_TEXT)
    gemini_status = ft.Text("", size=12, color=theme.MUTED_TEXT)
    score_column = ft.Column(spacing=8)
    gemini_key_field = ft.TextField(
        label="Personal Gemini API key",
        value=ctx.get_setting("gemini_api_key"),
        password=True,
        can_reveal_password=True,
        hint_text="Paste a replacement key from Google AI Studio",
    )
    gemini_model_field = ft.TextField(
        label="Model",
        value=normalize_gemini_model(ctx.get_setting("gemini_model")),
        hint_text=DEFAULT_GEMINI_MODEL,
    )

    def _save_gemini(_event) -> None:
        key = (gemini_key_field.value or "").strip()
        model = normalize_gemini_model(gemini_model_field.value)
        ctx.set_setting("gemini_api_key", key)
        ctx.set_setting("gemini_model", model)
        gemini_status.value = (
            "Gemini is disconnected."
            if not key else "Saved locally. Gemini is used only from AI Coach."
        )
        page.update()
    # FilePicker is a Flet service, not a visible control. It must be attached
    # to the page before save_file() can invoke Android's system Save dialog.
    # Reuse it when Settings is reopened so services do not accumulate.
    file_picker = next(
        (
            service
            for service in page.services
            if isinstance(service, ft.FilePicker)
            and service.data == "timetracker-export-picker"
        ),
        None,
    )
    if file_picker is None:
        file_picker = ft.FilePicker(data="timetracker-export-picker")
        page.services.append(file_picker)

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

    async def _export(fmt: str) -> None:
        try:
            ok, path = (
                ctx.export_service.to_csv()
                if fmt == "csv" else ctx.export_service.to_json()
            )
            if not ok:
                status_text.value = "Export failed."
                page.update()
                return

            with open(path, "rb") as export_file:
                saved_path = await file_picker.save_file(
                    dialog_title=f"Save {fmt.upper()} export",
                    file_name=os.path.basename(path),
                    file_type=ft.FilePickerFileType.CUSTOM,
                    allowed_extensions=[fmt],
                    src_bytes=export_file.read(),
                )
            status_text.value = (
                f"Saved {os.path.basename(saved_path)}"
                if saved_path else "Export canceled."
            )
        except Exception as exc:  # noqa: BLE001 - surface any export problem
            status_text.value = f"Export failed: {exc}"
        page.update()

    async def _export_csv(_event) -> None:
        await _export("csv")

    async def _export_json(_event) -> None:
        await _export("json")

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

            theme.section_label("Gemini AI Coach (optional)"),
            ft.Text(
                "For this personal APK only: add your own Google AI Studio key to use the "
                "free tier when available. The key is stored in this app's local database. "
                "Do not share the APK or your key; remove the key here to disconnect Gemini.",
                size=12,
                color=theme.MUTED_TEXT,
            ),
            gemini_key_field,
            gemini_model_field,
            fury_button("Save Gemini settings", kind="secondary", on_click=_save_gemini),
            gemini_status,

            theme.section_label("Export data"),
            ft.Row(controls=[
                fury_button("CSV", kind="secondary", on_click=_export_csv),
                fury_button("JSON", kind="secondary", on_click=_export_json),
            ]),
            status_text,

            theme.section_label("About"),
            ft.Text("Personal Time Tracker & Productivity Dashboard\n"
                    "Offline by default. Gemini receives data only when you request an AI review.",
                    size=12, color=theme.MUTED_TEXT),
        ],
    )
