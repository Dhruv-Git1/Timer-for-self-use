"""Android Timer plus daily Check-off/Counter tracking and Today score.

The existing stopwatch and time-goal behavior stays intact. Non-timer progress
is stored separately by date, and its equal-weight score is intentionally local
to this screen: Calendar, streaks, dashboards, statistics, and Insights continue
to use their existing time-only services.
"""

from __future__ import annotations

import asyncio
import math
import os
import shutil
import time
from pathlib import Path

import flet as ft
import flet_video as ftv

import config
from app.utils import time_utils, validators
from mobile import theme
from mobile.screens import categories_screen
from app.services.timer_service import MODE_COUNTDOWN, MODE_STOPWATCH
from mobile.widgets.fury import chip, fury_button, fury_progress
from mobile.widgets.hero import COMPACT_HEIGHT, hero_banner
from mobile.widgets.sheets import dismiss_sheet, form_sheet, show_sheet

_PULSE_PERIOD = 2.6
_TICK_INTERVAL = 0.2
_FOCUS_CLOCK_SIZE = 104
GOAL_CELEBRATION_SETTING = "last_goal_celebration_date"
GOAL_COMPLETION_VIDEO = "goal-complete.mp4"
GOAL_COMPLETION_CACHE_DIR = "timetracker-celebration"
GOAL_COMPLETION_VIDEO_CONFIGURATION = ftv.VideoConfiguration(
    # Direct MediaCodec output avoids the emulator's failing EGL texture path
    # while still using Android's native H.264 decoder on real phones.
    output_driver="mediacodec_embed",
    hardware_decoding_api="mediacodec",
)


def _pulse_shadow(color: str) -> ft.BoxShadow:
    phase = (time.time() % _PULSE_PERIOD) / _PULSE_PERIOD
    blur = 14 + 10 * (0.5 + 0.5 * math.sin(phase * 2 * math.pi))
    return theme.glow(color, blur=blur)


def _score_label(value: float) -> str:
    return f"{value:.1f}".rstrip("0").rstrip(".") + "%"


def should_show_goal_celebration(
    *,
    initialized: bool,
    was_complete: bool,
    is_complete: bool,
    last_celebration_date: str,
    today: str,
) -> bool:
    """Return whether an incomplete-to-complete transition may celebrate."""
    return (
        initialized
        and is_complete
        and not was_complete
        and last_celebration_date != today
    )


def reset_goal_celebration_state(ctx) -> None:
    """Clear the one-per-day latch for isolated automated tests only.

    This helper is deliberately not connected to the production UI.
    """
    ctx.set_setting(GOAL_CELEBRATION_SETTING, "")


def is_video_completion_event(event) -> bool:
    """Return whether flet-video has actually reached the end of a video.

    The component reports its initial ``completed=false`` state through the
    same callback as the final ``completed=true`` event.  Closing on either
    state tears down the full-screen player as soon as it is created.
    """
    return str(getattr(event, "data", "")).strip().lower() in {"true", "1"}


def goal_completion_video_resource() -> str:
    """Return a file URI that Android's native player can read.

    Flet bundles app assets separately from Flutter's own asset resolver, while
    ``flet_video`` passes its resource straight to media_kit. A bare relative
    filename therefore creates a player surface but does not give media_kit a
    readable Android file. Copy this immutable bundled clip to the app-private
    cache when possible and play the resulting file URI instead.
    """
    asset_dirs = [os.environ.get("FLET_ASSETS_DIR"), config.ASSETS_DIR]
    source = next(
        (
            Path(directory) / GOAL_COMPLETION_VIDEO
            for directory in asset_dirs
            if directory and (Path(directory) / GOAL_COMPLETION_VIDEO).is_file()
        ),
        Path(config.ASSETS_DIR) / GOAL_COMPLETION_VIDEO,
    )

    cache_root = os.environ.get("FLET_APP_STORAGE_CACHE")
    if cache_root and source.is_file():
        try:
            cached = Path(cache_root) / GOAL_COMPLETION_CACHE_DIR / GOAL_COMPLETION_VIDEO
            cached.parent.mkdir(parents=True, exist_ok=True)
            if not cached.is_file() or cached.stat().st_size != source.stat().st_size:
                shutil.copyfile(source, cached)
            return cached.resolve().as_uri()
        except OSError:
            # A cache failure must not prevent a completed goal from being
            # recorded; the bundled physical file remains a valid fallback.
            pass

    return source.resolve().as_uri()


def build(page: ft.Page, ctx) -> ft.Control:
    state = ctx.timer_service.current_state()
    timer_categories = [
        category for category in ctx.category_service.list_categories() if category.is_timer
    ]
    selected = {
        "id": state.category_id if state.is_active
        else (timer_categories[0].id if timer_categories else None)
    }
    preferred_mode = {"value": ctx.timer_service.preferred_mode()}
    editing_goals = {"on": False}
    goal_inputs: dict[int, ft.TextField] = {}
    celebration_state = {"initialized": False, "was_complete": False}
    focus_state: dict[str, object] = {"sheet": None, "clock": None, "open": False}

    clock_text = ft.Text(
        "0:00:00",
        size=theme.TIMER_CLOCK_SIZE,
        weight=ft.FontWeight.BOLD,
        font_family=theme.MONO_FAMILY_SEMIBOLD,
        color=theme.HEADLINE,
        text_align=ft.TextAlign.CENTER,
    )
    subtitle_text = ft.Text(
        "", size=13, color=theme.MUTED_TEXT, text_align=ft.TextAlign.CENTER
    )
    controls_row = ft.Row(alignment=ft.MainAxisAlignment.CENTER, spacing=10)
    mode_selector = ft.Row(alignment=ft.MainAxisAlignment.CENTER, spacing=8)
    duration_controls = ft.Row(alignment=ft.MainAxisAlignment.CENTER, spacing=6)
    clock_card = ft.Container(
        padding=22,
        border_radius=16,
        bgcolor=theme.CARD,
        border=ft.Border.all(1, theme.CARD_BORDER),
        content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=6,
            controls=[clock_text, subtitle_text, mode_selector, duration_controls, controls_row],
        ),
    )

    score_value = theme.number("—", size=42, color=theme.ACCENT)
    score_subtitle = ft.Text("", size=11, color=theme.MUTED_TEXT)
    score_bar = fury_progress(0, color=theme.ACCENT, animate_in=False)
    score_card = theme.card(
        ft.Row(
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Column(
                    tight=True,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        score_value,
                        theme.section_label("Score"),
                    ],
                ),
                ft.Container(width=1, height=48, bgcolor=theme.CARD_BORDER),
                ft.Column(
                    expand=True,
                    spacing=5,
                    controls=[
                        theme.section_label("Today's mission"),
                        score_subtitle,
                        score_bar,
                    ],
                ),
            ],
        ),
        padding=14,
        radius=12,
    )

    goals_column = ft.Column(spacing=8)
    checkins_column = ft.Column(spacing=8)
    grid_column = ft.Column(spacing=8)
    goals_header = ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
    categories_header = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        controls=[
            theme.section_label("Timer categories"),
            ft.TextButton(
                "Manage categories",
                icon=ft.Icons.EDIT,
                on_click=lambda e: categories_screen.show_manager(
                    page, ctx, on_changed=_on_categories_changed
                ),
            ),
        ],
    )

    def _focus_wakelock() -> ft.Wakelock | None:
        """Attach one wake lock so a deliberate focus session stays visible."""
        services = getattr(page, "services", None)
        if services is None:
            return None
        wakelock = getattr(page, "_timetracker_focus_wakelock", None)
        if wakelock is None:
            wakelock = ft.Wakelock()
            services.append(wakelock)
            page._timetracker_focus_wakelock = wakelock
        return wakelock

    def _keep_focus_screen_awake(enabled: bool) -> None:
        wakelock = _focus_wakelock()
        if wakelock is not None:
            page.run_task(wakelock.enable if enabled else wakelock.disable)

    def _close_focus_mode(e=None) -> None:
        """Return to the normal Timer view without changing the live session."""
        sheet = focus_state.get("sheet")
        focus_state["sheet"] = None
        focus_state["clock"] = None
        focus_state["open"] = False
        _keep_focus_screen_awake(False)
        if isinstance(sheet, ft.BottomSheet) and sheet.open:
            dismiss_sheet(page, sheet)

    def _show_focus_mode() -> None:
        """Put the active session in a clock-only, distraction-free display."""
        if focus_state["open"]:
            return
        live = ctx.timer_service.current_state()
        if not live.is_active:
            return
        category = ctx.category_service.get(live.category_id)
        shown_seconds = (
            live.remaining_seconds if live.mode == MODE_COUNTDOWN else live.elapsed_seconds
        )
        focus_clock = ft.Text(
            time_utils.fmt_clock(shown_seconds),
            size=_FOCUS_CLOCK_SIZE,
            weight=ft.FontWeight.BOLD,
            font_family=theme.MONO_FAMILY_SEMIBOLD,
            color=getattr(category, "color", theme.HEADLINE),
            text_align=ft.TextAlign.CENTER,
        )

        def _on_dismiss(_event=None) -> None:
            focus_state["sheet"] = None
            focus_state["clock"] = None
            focus_state["open"] = False
            _keep_focus_screen_awake(False)

        sheet = ft.BottomSheet(
            bgcolor="#000000",
            barrier_color="#000000",
            dismissible=False,
            draggable=False,
            fullscreen=True,
            use_safe_area=False,
            maintain_bottom_view_insets_padding=False,
            on_dismiss=_on_dismiss,
            content=ft.Container(
                expand=True,
                bgcolor="#000000",
                content=ft.Stack(
                    fit=ft.StackFit.EXPAND,
                    controls=[
                        ft.Container(
                            expand=True,
                            alignment=ft.Alignment.CENTER,
                            content=focus_clock,
                        ),
                        ft.Container(
                            top=16,
                            right=12,
                            content=ft.IconButton(
                                icon=ft.Icons.CLOSE,
                                icon_color="#555861",
                                icon_size=22,
                                tooltip="Exit focus mode",
                                on_click=_close_focus_mode,
                            ),
                        ),
                    ],
                ),
            ),
        )
        focus_state["sheet"] = sheet
        focus_state["clock"] = focus_clock
        focus_state["open"] = True
        _keep_focus_screen_awake(True)
        show_sheet(page, sheet)

    async def _tick_loop() -> None:
        last_shown_second = None
        while True:
            await asyncio.sleep(_TICK_INTERVAL)
            live = ctx.timer_service.current_state()
            if live.is_active and live.mode == MODE_COUNTDOWN and live.is_expired:
                completion_token = live.token or ""
                ok, _message, _entry_id = ctx.timer_service.reconcile_expired()
                if ok and completion_token:
                    bridge = getattr(page, "_timetracker_android_bridge", None)
                    if bridge is not None:
                        await bridge.notify_finished(completion_token)
                _close_focus_mode()
                _refresh_all()
                break
            if not live.is_active:
                break
            shown_seconds = (
                live.remaining_seconds if live.mode == MODE_COUNTDOWN else live.elapsed_seconds
            )
            if shown_seconds != last_shown_second:
                clock_text.value = time_utils.fmt_clock(shown_seconds)
                focus_clock = focus_state.get("clock")
                if isinstance(focus_clock, ft.Text):
                    focus_clock.value = clock_text.value
                last_shown_second = shown_seconds
            clock_card.shadow = _pulse_shadow(clock_text.color)
            page.update()

    def _start_ticking() -> None:
        page.run_task(_tick_loop)

    def _on_category_tap(category_id: int) -> None:
        live = ctx.timer_service.current_state()
        if live.is_active:
            if live.mode == MODE_COUNTDOWN:
                return
            if category_id != live.category_id:
                ctx.timer_service.start(category_id)
                _refresh_all()
                _start_ticking()
        else:
            selected["id"] = category_id
            _refresh_all()

    def _on_start(e=None) -> None:
        if selected["id"] is None:
            return
        mode = preferred_mode["value"]
        try:
            if mode == MODE_COUNTDOWN:
                ctx.timer_service.start(
                    selected["id"],
                    mode=MODE_COUNTDOWN,
                    duration_seconds=ctx.timer_service.last_countdown_seconds(),
                )
            else:
                ctx.timer_service.start(selected["id"])
        except ValueError:
            return
        if mode == MODE_COUNTDOWN:
            bridge = getattr(page, "_timetracker_android_bridge", None)
            if bridge is not None:
                # Ask for notification access at the moment the user starts a
                # countdown, never on app launch. Android's inexact-alarm
                # fallback keeps the timer useful if this prompt is declined.
                page.run_task(bridge.request_permissions)
        _refresh_all()
        _show_focus_mode()
        _start_ticking()

    def _on_stop(e=None) -> None:
        live = ctx.timer_service.current_state()
        ctx.timer_service.stop()
        _close_focus_mode()
        if live.is_expired and live.token:
            bridge = getattr(page, "_timetracker_android_bridge", None)
            if bridge is not None:
                page.run_task(bridge.notify_finished, live.token)
        _refresh_all()

    def _on_discard(e=None) -> None:
        ctx.timer_service.discard()
        _close_focus_mode()
        _refresh_all()

    def _select_mode(mode: str) -> None:
        if ctx.timer_service.current_state().is_active:
            return
        ctx.timer_service.set_preferred_mode(mode)
        preferred_mode["value"] = mode
        _refresh_all()

    def _set_duration(minutes: int) -> None:
        seconds = minutes * 60
        ctx.timer_service.set_last_countdown_seconds(seconds)
        _refresh_all()

    def _open_custom_duration(e=None) -> None:
        seconds = ctx.timer_service.last_countdown_seconds()
        hours, minutes = divmod(seconds // 60, 60)
        hours_field = ft.TextField(
            label="Hours", value=str(hours), keyboard_type=ft.KeyboardType.NUMBER
        )
        minutes_field = ft.TextField(
            label="Minutes", value=str(minutes), keyboard_type=ft.KeyboardType.NUMBER
        )
        error_text = ft.Text("", size=12, color=theme.STOP_RED)

        def _cancel(_event=None) -> None:
            dismiss_sheet(page, sheet)

        def _save(_event=None) -> None:
            hours_text = (hours_field.value or "").strip()
            minutes_text = (minutes_field.value or "").strip()
            if not hours_text.isdigit() or not minutes_text.isdigit():
                error_text.value = "Hours and minutes must be whole numbers."
            else:
                custom_hours = int(hours_text)
                custom_minutes = int(minutes_text)
                total_minutes = custom_hours * 60 + custom_minutes
                if not 0 <= custom_hours <= 23 or not 0 <= custom_minutes <= 59:
                    error_text.value = "Hours must be 0–23 and minutes must be 0–59."
                elif not 1 <= total_minutes <= 1439:
                    error_text.value = "Choose a duration between 1 minute and 23h 59m."
                else:
                    _set_duration(total_minutes)
                    _cancel()
                    return
            page.update()

        sheet = form_sheet(
            "Custom countdown",
            ft.Column(
                spacing=10,
                controls=[
                    ft.Text(
                        "Set a whole-minute duration. The timer keeps running even "
                        "when the app is in the background.",
                        size=12,
                        color=theme.MUTED_TEXT,
                    ),
                    ft.Row(controls=[hours_field, minutes_field]),
                    error_text,
                ],
            ),
            [
                ft.TextButton("Cancel", on_click=_cancel),
                fury_button("Save", kind="primary", on_click=_save),
            ],
            _cancel,
        )
        show_sheet(page, sheet)

    def _on_categories_changed() -> None:
        available = [
            category for category in ctx.category_service.list_categories() if category.is_timer
        ]
        available_ids = {category.id for category in available}
        if not ctx.timer_service.current_state().is_active and selected["id"] not in available_ids:
            selected["id"] = available[0].id if available else None
        _refresh_all()

    def _toggle_edit_goals(e=None) -> None:
        editing_goals["on"] = not editing_goals["on"]
        _refresh_all()

    def _save_goals(e=None) -> None:
        timer_cats = [
            category for category in ctx.category_service.list_categories() if category.is_timer
        ]
        parsed: dict[int, int] = {}
        for category in timer_cats:
            text = goal_inputs[category.id].value
            ok, _msg = validators.validate_target_minutes(text)
            if not ok:
                _refresh_all()
                return
            parsed[category.id] = int(text or 0)
        for category in timer_cats:
            if parsed[category.id] != category.daily_target_minutes:
                category.daily_target_minutes = parsed[category.id]
                ctx.category_service.update(category)
        editing_goals["on"] = False
        _refresh_all()

    def _refresh_goals() -> None:
        goals_column.controls.clear()
        goal_inputs.clear()
        goals_header.controls = [
            theme.section_label("Today's time goals"),
            ft.IconButton(
                icon=ft.Icons.CHECK if editing_goals["on"] else ft.Icons.EDIT,
                icon_color=theme.ACCENT,
                on_click=_save_goals if editing_goals["on"] else _toggle_edit_goals,
            ),
        ]

        timer_cats = [
            category for category in ctx.category_service.list_categories() if category.is_timer
        ]
        if editing_goals["on"]:
            for category in timer_cats:
                field = ft.TextField(
                    value=str(category.daily_target_minutes),
                    width=70,
                    height=42,
                    text_align=ft.TextAlign.CENTER,
                    dense=True,
                    keyboard_type=ft.KeyboardType.NUMBER,
                )
                goal_inputs[category.id] = field
                goals_column.controls.append(
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.CIRCLE, size=12, color=category.color),
                            ft.Text(category.name, size=13, color=theme.HEADLINE, expand=True),
                            field,
                            ft.Text("min/day", size=11, color=theme.MUTED_TEXT),
                        ]
                    )
                )
            if not timer_cats:
                goals_column.controls.append(
                    ft.Text("Add a Timer category first.", size=12, color=theme.MUTED_TEXT)
                )
            return

        summary = ctx.dashboard_service.build_summary(time_utils.today_str())
        goals = [progress for progress in summary.progress if progress.target_minutes > 0]
        if not goals:
            goals_column.controls.append(
                ft.Text(
                    "No time goals set yet — tap the pencil to add one.",
                    size=12,
                    color=theme.MUTED_TEXT,
                )
            )
        for progress in goals:
            goals_column.controls.append(
                ft.Column(
                    spacing=2,
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Text(progress.name, size=13, color=theme.HEADLINE, expand=True),
                                ft.Text(
                                    f"{progress.actual_label} / {progress.target_label}",
                                    size=12,
                                    color=theme.MUTED_TEXT,
                                ),
                            ]
                        ),
                        fury_progress(
                            progress.completion_pct / 100,
                            color=progress.color,
                            animate_in=False,
                        ),
                    ],
                )
            )

    def _toggle_checkoff(category_id: int) -> None:
        ctx.daily_progress_service.toggle(category_id, time_utils.today_str())
        _refresh_all()

    def _adjust_counter(category_id: int, delta: int) -> None:
        ctx.daily_progress_service.increment(category_id, time_utils.today_str(), delta)
        _refresh_all()

    def _open_amount_editor(category) -> None:
        today = time_utils.today_str()
        current = ctx.daily_progress_service.get(category.id, today)
        amount_field = ft.TextField(
            label=f"Amount ({category.unit_label})",
            value=str(current),
            keyboard_type=ft.KeyboardType.NUMBER,
            autofocus=True,
        )
        error_text = ft.Text("", size=12, color=theme.STOP_RED)

        def _save_amount(e=None) -> None:
            text = (amount_field.value or "").strip()
            if not text.isdigit():
                error_text.value = "Amount must be a non-negative whole number."
                page.update()
                return
            ctx.daily_progress_service.set_amount(category.id, today, int(text))
            dismiss_sheet(page, sheet)
            _refresh_all()

        def _cancel_amount(e=None) -> None:
            dismiss_sheet(page, sheet)

        sheet = form_sheet(
            f"Set {category.name}",
            ft.Column(spacing=10, controls=[amount_field, error_text]),
            [
                ft.TextButton("Cancel", on_click=_cancel_amount),
                fury_button("Save", kind="primary", on_click=_save_amount),
            ],
            _cancel_amount,
        )
        show_sheet(page, sheet)

    def _all_daily_goals_complete() -> bool:
        score = ctx.daily_progress_service.score(time_utils.today_str())
        return bool(score.items) and all(
            item.completion_pct >= 100 for item in score.items
        )

    def _show_goal_celebration(today: str) -> None:
        """Play the supplied celebration clip over the Timer screen once."""
        playback_started = {"value": False}
        playback_error = ft.Text("", size=12, color=theme.STOP_RED)
        video = ftv.Video(
            expand=True,
            autoplay=True,
            controls=None,
            configuration=GOAL_COMPLETION_VIDEO_CONFIGURATION,
                    # Fill the entire phone display; the source video is
                    # landscape, so its outer edges may be cropped on portrait
                    # devices rather than leaving letterbox bars.
            fit=ft.BoxFit.COVER,
            playlist=[
                ftv.VideoMedia(goal_completion_video_resource())
            ],
        )

        async def _stop_and_dismiss() -> None:
            try:
                await video.stop()
            except Exception:  # noqa: BLE001 - the player may already be closed
                pass
            dismiss_sheet(page, sheet)

        def _dismiss(e=None) -> None:
            page.run_task(_stop_and_dismiss)

        def _on_video_complete(event) -> None:
            if is_video_completion_event(event):
                _dismiss(event)

        def _on_video_load(event) -> None:
            # Do not consume today's one celebration until the native player has
            # actually initialized. Previously the latch was written before the
            # player was visible, so a transient Android player failure resulted
            # in a silent, non-retryable celebration.
            if not playback_started["value"]:
                playback_started["value"] = True
                ctx.set_setting(GOAL_CELEBRATION_SETTING, today)

        def _on_video_error(event) -> None:
            playback_error.value = "The celebration video could not start. Your goal is still complete."
            page.update()

        video.on_complete = _on_video_complete
        video.on_load = _on_video_load
        video.on_error = _on_video_error
        sheet = ft.BottomSheet(
            bgcolor="#000000",
            dismissible=False,
            draggable=False,
            fullscreen=True,
            content=ft.Container(
                expand=True,
                bgcolor="#000000",
                content=ft.Stack(
                    fit=ft.StackFit.EXPAND,
                    controls=[
                        video,
                        ft.Container(
                            top=20,
                            right=16,
                            content=ft.IconButton(
                                icon=ft.Icons.CLOSE,
                                icon_color=theme.HEADLINE,
                                tooltip="Close celebration",
                                on_click=_dismiss,
                            ),
                        ),
                        ft.Container(
                            left=20,
                            right=20,
                            bottom=28,
                            padding=14,
                            border_radius=12,
                            bgcolor=ft.Colors.with_opacity(0.76, "#08080A"),
                            content=ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Column(
                                        tight=True,
                                        spacing=2,
                                        controls=[
                                            theme.section_label("Daily goal complete"),
                                            ft.Text(
                                                "You completed every goal for today.",
                                                size=12,
                                                color=theme.HEADLINE,
                                            ),
                                            playback_error,
                                        ],
                                    ),
                                    fury_button(
                                        "Continue", kind="primary", on_click=_dismiss
                                    ),
                                ],
                            ),
                        ),
                    ],
                ),
            ),
        )
        show_sheet(page, sheet)

    def _maybe_show_goal_celebration() -> None:
        today = time_utils.today_str()
        is_complete = _all_daily_goals_complete()
        last_celebration_date = ctx.get_setting(GOAL_CELEBRATION_SETTING)
        if not celebration_state["initialized"]:
            celebration_state["initialized"] = True
            # Completion can happen from another screen or while Android has
            # the app in the background. In that case this Timer view sees an
            # already-complete day on its first refresh; celebrate it once
            # instead of silently treating it as stale state.
            if is_complete and last_celebration_date != today:
                _show_goal_celebration(today)
        elif should_show_goal_celebration(
            initialized=celebration_state["initialized"],
            was_complete=celebration_state["was_complete"],
            is_complete=is_complete,
            last_celebration_date=last_celebration_date,
            today=today,
        ):
            _show_goal_celebration(today)
        celebration_state["was_complete"] = is_complete

    def _refresh_score_and_checkins() -> None:
        today = time_utils.today_str()
        score = ctx.daily_progress_service.score(today)
        if score.has_scored_categories:
            score_value.value = _score_label(score.average_pct)
            count = len(score.scored_items)
            total_weight = sum(item.weight for item in score.scored_items)
            score_subtitle.value = (
                f"{count} goal{'s' if count != 1 else ''} \u00b7 "
                f"{total_weight}\u00d7 total weight"
            )
            score_bar.value = score.average_pct / 100
            score_bar.data = score_bar.value
        else:
            score_value.value = "—"
            score_subtitle.value = "Include a goal category to calculate today's score."
            score_bar.value = 0
            score_bar.data = 0

        checkins_column.controls.clear()
        categories = [
            category for category in ctx.category_service.list_categories()
            if not category.is_timer
        ]
        if not categories:
            checkins_column.controls.append(
                theme.card(
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE, color=theme.FLAME, size=22),
                            ft.Column(
                                expand=True,
                                spacing=2,
                                controls=[
                                    ft.Text("Add a daily win", size=13, color=theme.HEADLINE),
                                    ft.Text(
                                        "Track habits such as water, fruit, or a daily check-off.",
                                        size=11,
                                        color=theme.MUTED_TEXT,
                                    ),
                                ],
                            ),
                            ft.TextButton(
                                "Add",
                                on_click=lambda e: categories_screen.show_manager(
                                    page, ctx, on_changed=_on_categories_changed
                                ),
                            ),
                        ]
                    ),
                    padding=14,
                    radius=10,
                )
            )
            return

        for category in categories:
            amount = ctx.daily_progress_service.get(category.id, today)
            target = category.target_value
            progress = min(1.0, amount / target) if target else 0.0
            if category.is_checkoff:
                action = ft.Checkbox(
                    value=amount >= 1,
                    active_color=category.color,
                    on_change=lambda e, cid=category.id: _toggle_checkoff(cid),
                )
                detail = "Done" if amount else "Tap to complete"
            else:
                action = ft.Row(
                    tight=True,
                    spacing=2,
                    controls=[
                        ft.IconButton(
                            icon=ft.Icons.REMOVE,
                            icon_color=theme.MUTED_TEXT,
                            disabled=amount <= 0,
                            on_click=lambda e, cid=category.id: _adjust_counter(cid, -1),
                        ),
                        ft.TextButton(
                            f"{amount} / {target}",
                            on_click=lambda e, c=category: _open_amount_editor(c),
                        ),
                        ft.IconButton(
                            icon=ft.Icons.ADD,
                            icon_color=category.color,
                            on_click=lambda e, cid=category.id: _adjust_counter(cid, 1),
                        ),
                    ],
                )
                detail = category.unit_label

            checkins_column.controls.append(
                theme.card(
                    ft.Column(
                        spacing=5,
                        controls=[
                            ft.Row(
                                controls=[
                                    ft.Icon(ft.Icons.CIRCLE, size=11, color=category.color),
                                    ft.Column(
                                        expand=True,
                                        spacing=1,
                                        controls=[
                                            ft.Text(category.name, size=13, color=theme.HEADLINE),
                                            ft.Text(detail, size=10, color=theme.MUTED_TEXT),
                                        ],
                                    ),
                                    action,
                                ]
                            ),
                            fury_progress(progress, color=category.color, animate_in=False),
                        ],
                    ),
                    padding=12,
                    radius=10,
                )
            )

    def _refresh_grid() -> None:
        grid_column.controls.clear()
        categories = [
            category for category in ctx.category_service.list_categories() if category.is_timer
        ]
        live = ctx.timer_service.current_state()
        if not categories:
            grid_column.controls.append(
                theme.card(
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.TIMER_OUTLINED, color=theme.ACCENT, size=22),
                            ft.Column(
                                expand=True,
                                spacing=2,
                                controls=[
                                    ft.Text("Create your first timer", size=13, color=theme.HEADLINE),
                                    ft.Text(
                                        "Choose a focus category, set a target, then start your streak.",
                                        size=11,
                                        color=theme.MUTED_TEXT,
                                    ),
                                ],
                            ),
                            ft.TextButton(
                                "Create",
                                on_click=lambda e: categories_screen.show_manager(
                                    page, ctx, on_changed=_on_categories_changed
                                ),
                            ),
                        ]
                    ),
                    padding=14,
                    radius=10,
                )
            )
            return

        row = None
        for index, category in enumerate(categories):
            if index % 2 == 0:
                row = ft.Row(spacing=8)
                grid_column.controls.append(row)
            is_tracking = live.is_active and live.category_id == category.id
            is_selected = not live.is_active and selected["id"] == category.id
            is_locked = (
                live.is_active
                and live.mode == MODE_COUNTDOWN
                and category.id != live.category_id
            )
            border_color = (
                category.color if is_selected
                else ("#FFFFFF" if is_tracking else theme.CARD_BORDER)
            )
            row.controls.append(
                ft.Container(
                    expand=True,
                    padding=14,
                    border_radius=10,
                    bgcolor=category.color if is_tracking else theme.CARD,
                    border=ft.Border.all(
                        2 if (is_selected or is_tracking) else 1, border_color
                    ),
                    animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
                    opacity=0.42 if is_locked else 1.0,
                    content=ft.Row(
                        spacing=6,
                        controls=[
                            ft.Icon(
                                ft.Icons.CIRCLE,
                                size=13,
                                color="#FFFFFF" if is_tracking else category.color,
                            ),
                            ft.Text(
                                category.name,
                                size=13,
                                color="#FFFFFF" if is_tracking else theme.HEADLINE,
                                weight=(
                                    ft.FontWeight.BOLD
                                    if (is_tracking or is_selected) else ft.FontWeight.NORMAL
                                ),
                            ),
                        ],
                    ),
                    on_click=(
                        None if is_locked
                        else lambda e, cid=category.id: _on_category_tap(cid)
                    ),
                )
            )

    def _refresh_all() -> None:
        live = ctx.timer_service.current_state()
        categories = {
            category.id: category
            for category in ctx.category_service.list_categories()
            if category.is_timer
        }
        if not live.is_active and selected["id"] not in categories:
            selected["id"] = next(iter(categories), None)

        active_mode = live.mode if live.is_active else preferred_mode["value"]
        if live.is_active and live.category_id in categories:
            category = categories[live.category_id]
            shown_seconds = (
                live.remaining_seconds if live.mode == MODE_COUNTDOWN else live.elapsed_seconds
            )
            clock_text.value = time_utils.fmt_clock(shown_seconds)
            clock_text.color = category.color
            subtitle_text.value = (
                f"{'COUNTDOWN' if live.mode == MODE_COUNTDOWN else 'STOPWATCH'}: "
                f"{category.name.upper()}"
            )
            subtitle_text.color = category.color
            clock_card.shadow = _pulse_shadow(category.color)
        else:
            idle_seconds = (
                ctx.timer_service.last_countdown_seconds()
                if active_mode == MODE_COUNTDOWN else 0
            )
            clock_text.value = time_utils.fmt_clock(idle_seconds)
            clock_text.color = theme.HEADLINE
            clock_card.shadow = None
            if selected["id"] in categories:
                category = categories[selected["id"]]
                subtitle_text.value = (
                    f"Ready for {'a countdown' if active_mode == MODE_COUNTDOWN else 'a stopwatch'}: "
                    f"{category.name}"
                )
                subtitle_text.color = category.color
            else:
                subtitle_text.value = "Add a Timer category, then press Start"
                subtitle_text.color = theme.MUTED_TEXT

        mode_selector.controls = [
            ft.Container(
                padding=ft.Padding.symmetric(vertical=8, horizontal=14),
                border_radius=8,
                bgcolor=theme.ACCENT if active_mode == MODE_STOPWATCH else theme.NEUTRAL_BTN,
                opacity=0.55 if live.is_active else 1.0,
                ink=not live.is_active,
                content=theme.tracked("STOPWATCH", size=11, color=theme.HEADLINE,
                                     family=theme.MONO_FAMILY_SEMIBOLD, spacing=0.5),
                on_click=(None if live.is_active else lambda e: _select_mode(MODE_STOPWATCH)),
            ),
            ft.Container(
                padding=ft.Padding.symmetric(vertical=8, horizontal=14),
                border_radius=8,
                bgcolor=theme.ACCENT if active_mode == MODE_COUNTDOWN else theme.NEUTRAL_BTN,
                opacity=0.55 if live.is_active else 1.0,
                ink=not live.is_active,
                content=theme.tracked("COUNTDOWN", size=11, color=theme.HEADLINE,
                                     family=theme.MONO_FAMILY_SEMIBOLD, spacing=0.5),
                on_click=(None if live.is_active else lambda e: _select_mode(MODE_COUNTDOWN)),
            ),
        ]
        duration_controls.controls.clear()
        if not live.is_active and active_mode == MODE_COUNTDOWN:
            current_minutes = ctx.timer_service.last_countdown_seconds() // 60
            for label, minutes in (("25m", 25), ("1h", 60), ("2h", 120)):
                duration_controls.controls.append(
                    chip(label, current_minutes == minutes, lambda e, m=minutes: _set_duration(m))
                )
            duration_controls.controls.append(
                chip("Custom", current_minutes not in {25, 60, 120}, _open_custom_duration)
            )

        controls_row.controls.clear()
        if live.is_active:
            controls_row.controls.append(
                fury_button("Stop", icon=ft.Icons.STOP, kind="danger", on_click=_on_stop)
            )
            controls_row.controls.append(ft.TextButton("Discard", on_click=_on_discard))
        else:
            controls_row.controls.append(
                fury_button(
                    "Start countdown" if active_mode == MODE_COUNTDOWN else "Start",
                    icon=ft.Icons.PLAY_ARROW,
                    kind="primary",
                    on_click=_on_start,
                    disabled=selected["id"] is None,
                )
            )

        _refresh_score_and_checkins()
        _refresh_goals()
        _refresh_grid()
        _maybe_show_goal_celebration()
        page.update()

    _refresh_all()
    if state.is_active:
        _start_ticking()

    return ft.Column(
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        spacing=14,
        controls=[
            hero_banner(
                page,
                kicker="Timer / Live Session",
                headline="REVENGE",
                height=COMPACT_HEIGHT,
                # Keep the character's shoulders in frame rather than cropping
                # the hero down to a pale text-only header.
                image_align=ft.Alignment(0, 0.34),
            ),
            clock_card,
            categories_header,
            grid_column,
            score_card,
            theme.section_label("Today's check-ins"),
            checkins_column,
            goals_header,
            goals_column,
        ],
    )
