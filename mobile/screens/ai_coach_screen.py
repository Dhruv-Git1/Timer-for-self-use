"""Explicitly opt-in Gemini coaching for the user's recent tracker data."""

from __future__ import annotations

import asyncio
import os

import flet as ft

import config
from app.services.csv_insights_service import CsvInsightsError, CsvInsightsService
from app.services.gemini_service import (
    DEFAULT_GEMINI_MODEL,
    GeminiError,
    GeminiService,
)
from app.utils import time_utils
from mobile import theme
from mobile.widgets.fury import fury_button


def build(page: ft.Page, ctx) -> ft.Control:
    """Build the screen without making a network request on entry."""
    today = time_utils.today_str()
    todays_reflection = ctx.daily_reflection_service.get_text(today)
    source = {"path": None, "name": None}
    result_text = ft.Text("", size=13, color=theme.HEADLINE)
    status_text = ft.Text("", size=12, color=theme.MUTED_TEXT)
    source_text = ft.Text(
        "Source: this app's recent 14 days and saved reflections.",
        size=12,
        color=theme.MUTED_TEXT,
    )
    result_card = ft.Container(visible=False)
    analyze_button = fury_button(
        "Analyze last 14 days",
        kind="primary",
        icon=ft.Icons.AUTO_AWESOME,
        on_click=None,
    )

    # FilePicker is a page service. Keep one stable instance when the screen
    # is revisited; with_data=False is intentional so large CSV files are not
    # loaded into memory or uploaded to the app.
    file_picker = next(
        (
            service
            for service in page.services
            if isinstance(service, ft.FilePicker)
            and service.data == "timetracker-ai-csv-picker"
        ),
        None,
    )
    if file_picker is None:
        file_picker = ft.FilePicker(data="timetracker-ai-csv-picker")
        page.services.append(file_picker)

    def _show_result(text: str, *, error: bool = False) -> None:
        result_text.value = text
        result_text.color = theme.KICKER_RED if error else theme.HEADLINE
        result_card.visible = True

    def _set_csv_source(path: str, name: str) -> None:
        source["path"] = path
        source["name"] = name
        source_text.value = (
            f"Source: CSV export — {name}. It will replace the recent-app-data source."
        )

    async def _choose_csv(_event) -> None:
        files = await file_picker.pick_files(
            dialog_title="Choose a Time Tracker CSV export",
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["csv"],
            allow_multiple=False,
            with_data=False,
        )
        if not files:
            return

        selected = files[0]
        if not selected.path:
            status_text.value = (
                "This file location cannot be streamed by the app. Export a CSV from "
                "Settings, then use Latest CSV export instead."
            )
            page.update()
            return

        _set_csv_source(selected.path, selected.name or "selected CSV")
        status_text.value = "CSV selected. It has not been uploaded or analyzed yet."
        page.update()

    async def _use_latest_export(_event) -> None:
        try:
            candidates = [
                os.path.join(config.EXPORT_DIR, filename)
                for filename in os.listdir(config.EXPORT_DIR)
                if filename.lower().endswith(".csv")
                and filename.startswith("timetracker_")
            ]
            latest_path = max(candidates, key=os.path.getmtime)
        except (OSError, ValueError):
            status_text.value = "No Time Tracker CSV export found. Create one in Settings first."
            page.update()
            return

        _set_csv_source(latest_path, os.path.basename(latest_path))
        status_text.value = "Latest CSV selected. It has not been uploaded or analyzed yet."
        page.update()

    async def _analyze(_event) -> None:
        api_key = ctx.get_setting("gemini_api_key")
        if not api_key:
            _show_result("Add your Gemini API key in More > Settings first.", error=True)
            page.update()
            return

        analyze_button.opacity = 0.5
        analyze_button.on_click = None
        status_text.value = "Preparing your local summary..."
        result_card.visible = False
        page.update()
        try:
            if source["path"]:
                status_text.value = "Summarizing the CSV locally..."
                page.update()
                report = await asyncio.to_thread(
                    CsvInsightsService().report_from_path,
                    source["path"],
                )
                sent_description = (
                    "The CSV stayed on device; Gemini received only its compact aggregate "
                    "(recent days/months, yearly totals, and top categories). Entry notes "
                    "were excluded."
                )
            else:
                report = ctx.ai_insights_service.recent_report(days=14)
                sent_description = (
                    "Only this 14-day aggregate and saved daily reflections were sent."
                )
            model = ctx.get_setting("gemini_model", DEFAULT_GEMINI_MODEL)
            service = GeminiService(api_key, model)
            status_text.value = "Asking Gemini..."
            page.update()
            answer = await asyncio.to_thread(
                service.generate_productivity_report,
                report,
            )
            _show_result(answer)
            status_text.value = sent_description
        except CsvInsightsError as exc:
            _show_result(str(exc), error=True)
            status_text.value = "No tracker data was changed."
        except GeminiError as exc:
            _show_result(str(exc), error=True)
            status_text.value = "No tracker data was changed."
        except Exception:  # noqa: BLE001 - avoid exposing internal details in the app
            _show_result("The AI review failed unexpectedly. Please try again.", error=True)
            status_text.value = "No tracker data was changed."
        finally:
            analyze_button.opacity = 1
            analyze_button.on_click = _analyze
            page.update()

    analyze_button.on_click = _analyze
    result_card.content = ft.Container(
        padding=16,
        border_radius=12,
        bgcolor=theme.CARD,
        border=ft.Border.all(1, theme.CARD_BORDER),
        content=result_text,
    )

    return ft.Column(
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        spacing=14,
        controls=[
            theme.display("AI Coach", size=28),
            theme.card(
                ft.Column(
                    spacing=6,
                    controls=[
                        theme.section_label("Private by default"),
                        ft.Text(
                            "Your tracker stays local. Gemini is contacted only when you tap "
                            "Analyze. A selected CSV is summarized row by row on your device; "
                            "the file and entry notes are never sent.",
                            size=12,
                            color=theme.MUTED_TEXT,
                        ),
                    ],
                ),
                padding=14,
            ),
            theme.card(
                ft.Column(
                    spacing=5,
                    controls=[
                        theme.section_label("Today's reflection"),
                        ft.Text(
                            todays_reflection or "No reflection saved yet. Write one on Home first.",
                            size=12,
                            color=theme.HEADLINE if todays_reflection else theme.MUTED_TEXT,
                            max_lines=4,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                    ],
                ),
                padding=14,
            ),
            theme.card(
                ft.Column(
                    spacing=7,
                    controls=[
                        theme.section_label("Analyze a longer CSV history"),
                        ft.Text(
                            "Optional: choose a Time Tracker CSV export for multi-year trends. "
                            "It replaces the 14-day app-data source for this analysis.",
                            size=12,
                            color=theme.MUTED_TEXT,
                        ),
                        ft.Row(
                            spacing=8,
                            controls=[
                                fury_button(
                                    "Choose CSV",
                                    kind="secondary",
                                    icon=ft.Icons.UPLOAD_FILE,
                                    on_click=_choose_csv,
                                ),
                                fury_button(
                                    "Latest CSV export",
                                    kind="secondary",
                                    icon=ft.Icons.FOLDER_OPEN,
                                    on_click=_use_latest_export,
                                ),
                            ],
                        ),
                        source_text,
                    ],
                ),
                padding=14,
            ),
            analyze_button,
            status_text,
            result_card,
        ],
    )
