"""Explicitly opt-in Gemini coaching for the user's tracker history."""

from __future__ import annotations

import asyncio

import flet as ft

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
        "Source: all time-tracking history saved in this app (automatic).",
        size=12,
        color=theme.MUTED_TEXT,
    )
    result_card = ft.Container(visible=False)
    analyze_button = fury_button(
        "Analyze my history",
        kind="primary",
        icon=ft.Icons.AUTO_AWESOME,
        on_click=None,
    )

    # FilePicker is only for an optional external/old CSV. Normal coaching
    # reads SQLite automatically and never requires an export.
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
        source_text.value = f"Source: optional external CSV - {name}."

    def _use_app_history(_event) -> None:
        source["path"] = None
        source["name"] = None
        source_text.value = (
            "Source: all time-tracking history saved in this app (automatic)."
        )
        status_text.value = "Using the app database. No export or file selection is needed."
        page.update()

    async def _choose_csv(_event) -> None:
        files = await file_picker.pick_files(
            dialog_title="Choose an optional external Time Tracker CSV",
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
                "This optional CSV location cannot be read. Your automatic app-history "
                "source is still available."
            )
            page.update()
            return

        _set_csv_source(selected.path, selected.name or "selected CSV")
        status_text.value = (
            "External CSV selected for the next analysis. It has not been uploaded."
        )
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
                status_text.value = "Summarizing the external CSV locally..."
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
                report = ctx.ai_insights_service.all_history_report()
                sent_description = (
                    "Your complete app history was summarized automatically. Gemini received "
                    "all-time/yearly totals, recent day/month detail, weekday/category patterns, "
                    "and up to 60 recent daily reflections - not raw session rows."
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
                            "AI Coach reads the history already stored inside this app - no "
                            "CSV download is needed. Gemini is contacted only when you tap "
                            "Analyze, and receives a compact summary instead of raw session rows.",
                            size=12,
                            color=theme.MUTED_TEXT,
                        ),
                    ],
                ),
                padding=14,
            ),
            theme.card(
                ft.Column(
                    spacing=7,
                    controls=[
                        theme.section_label("Data source"),
                        ft.Text(
                            "By default, all saved time entries are summarized on your phone. "
                            "Older years are compressed into monthly/yearly totals so the request "
                            "stays small.",
                            size=12,
                            color=theme.MUTED_TEXT,
                        ),
                        source_text,
                    ],
                ),
                padding=14,
            ),
            analyze_button,
            status_text,
            result_card,
            theme.card(
                ft.Column(
                    spacing=5,
                    controls=[
                        theme.section_label("Today's reflection"),
                        ft.Text(
                            todays_reflection
                            or "No reflection saved yet. Write one on Home first.",
                            size=12,
                            color=(
                                theme.HEADLINE if todays_reflection else theme.MUTED_TEXT
                            ),
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
                        theme.section_label("Optional external CSV"),
                        ft.Text(
                            "Only use this for old or external data that is not stored in this "
                            "app. Normal AI coaching does not require a CSV.",
                            size=12,
                            color=theme.MUTED_TEXT,
                        ),
                        ft.Row(
                            spacing=8,
                            wrap=True,
                            controls=[
                                fury_button(
                                    "Choose external CSV",
                                    kind="secondary",
                                    icon=ft.Icons.UPLOAD_FILE,
                                    on_click=_choose_csv,
                                ),
                                fury_button(
                                    "Use app history",
                                    kind="secondary",
                                    icon=ft.Icons.STORAGE,
                                    on_click=_use_app_history,
                                ),
                            ],
                        ),
                    ],
                ),
                padding=14,
            ),
        ],
    )
