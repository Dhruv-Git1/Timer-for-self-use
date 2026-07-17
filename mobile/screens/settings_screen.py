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
from mobile.widgets.sheets import dismiss_sheet, form_sheet, show_sheet


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
    import_picker = next(
        (
            service
            for service in page.services
            if isinstance(service, ft.FilePicker)
            and service.data == "timetracker-import-picker"
        ),
        None,
    )
    if import_picker is None:
        import_picker = ft.FilePicker(data="timetracker-import-picker")
        page.services.append(import_picker)

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

    async def _import_csv(_event) -> None:
        try:
            files = await import_picker.pick_files(
                dialog_title="Choose Time Tracker CSV",
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=["csv"],
                allow_multiple=False,
                with_data=True,
            )
            if not files:
                status_text.value = "Import canceled."
                page.update()
                return
            selected_file = files[0]
            source = selected_file.bytes if selected_file.bytes is not None else selected_file.path
            if source is None:
                status_text.value = "The selected CSV could not be read by the app."
                page.update()
                return
            preview = ctx.csv_import_service.preview(source, source_name=selected_file.name)
            _show_import_preview(preview)
        except Exception as exc:  # noqa: BLE001 - retain the Settings screen on failures
            status_text.value = f"Import preview failed: {exc}"
            page.update()

    def _show_import_preview(preview) -> None:
        importing = {"value": False}
        details: list[ft.Control] = [
            ft.Text(preview.source_name, size=13, color=theme.HEADLINE),
            ft.Text(
                f"{preview.valid_rows} valid entr{'y' if preview.valid_rows == 1 else 'ies'} · "
                f"{preview.duplicate_rows} duplicate{'s' if preview.duplicate_rows != 1 else ''}",
                size=12,
                color=theme.MUTED_TEXT,
            ),
        ]
        if preview.new_category_names:
            details.append(
                ft.Text(
                    "New categories: " + ", ".join(preview.new_category_names),
                    size=12,
                    color=theme.MUTED_TEXT,
                )
            )
        if preview.existing_category_conflicts:
            details.append(theme.section_label("Existing category settings kept"))
            details.extend(
                ft.Text(
                    f"{conflict.category}: productive stays "
                    f"{'yes' if conflict.existing_productive else 'no'}.",
                    size=12,
                    color=theme.MUTED_TEXT,
                )
                for conflict in preview.existing_category_conflicts
            )
        if preview.issues:
            details.append(theme.section_label("Validation errors"))
            details.extend(
                ft.Text(
                    f"Row {issue.row_number}: {issue.message}" if issue.row_number else issue.message,
                    size=12,
                    color=theme.STOP_RED,
                )
                for issue in preview.issues
            )
        elif preview.total_rows == 0:
            details.append(
                ft.Text("This export is valid but has no entries to import.",
                        size=12, color=theme.MUTED_TEXT)
            )

        def _cancel(_event=None) -> None:
            dismiss_sheet(page, sheet)

        async def _confirm(_event=None) -> None:
            if importing["value"]:
                return
            importing["value"] = True
            try:
                result = ctx.csv_import_service.import_preview(preview)
            except Exception as exc:  # keep the preview open for a useful retry/error
                importing["value"] = False
                preview_body.controls.append(
                    ft.Text(f"Import failed: {exc}", size=12, color=theme.STOP_RED)
                )
                page.update()
                return
            _cancel()
            status_text.value = (
                f"Imported {result.imported_entries}; skipped {result.skipped_duplicates} duplicates; "
                f"created {result.created_categories} categories."
            )
            page.update()

        preview_body = ft.Column(spacing=8, controls=details)
        sheet = form_sheet(
            "Import CSV",
            preview_body,
            [
                ft.TextButton("Cancel", on_click=_cancel),
                fury_button(
                    "Import",
                    kind="primary",
                    disabled=not preview.import_allowed,
                    on_click=_confirm,
                ),
            ],
            _cancel,
            body_height=430,
        )
        show_sheet(page, sheet)

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

            theme.section_label("Data"),
            ft.Row(controls=[
                fury_button("Import CSV", kind="secondary", on_click=_import_csv),
                fury_button("Export CSV", kind="secondary", on_click=_export_csv),
                fury_button("Export JSON", kind="secondary", on_click=_export_json),
            ]),
            status_text,

            theme.section_label("About"),
            ft.Text("Personal Time Tracker & Productivity Dashboard\n"
                    "Offline by default. Gemini receives data only when you request an AI review.",
                    size=12, color=theme.MUTED_TEXT),
        ],
    )
