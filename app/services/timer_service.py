"""Persistent stopwatch and countdown timer business logic.

The clock is deliberately derived from a stored wall-clock timestamp.  Neither
the Flet screen nor the Android widget owns a decrementing counter, so a timer
keeps the correct time through process death, screen-off, and an app restart.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Optional, Tuple
from uuid import uuid4

from app.database.repositories.settings_repo import SettingsRepository
from app.services.entry_service import EntryService
from app.utils import time_utils
from app.utils.event_bus import DATA_CHANGED, TIMER_STATE_CHANGED, bus
from config import TIMESTAMP_FMT

MODE_STOPWATCH = "stopwatch"
MODE_COUNTDOWN = "countdown"
TIMER_MODES = {MODE_STOPWATCH, MODE_COUNTDOWN}
MIN_COUNTDOWN_SECONDS = 60
MAX_COUNTDOWN_SECONDS = 23 * 60 * 60 + 59 * 60

_KEY_ACTIVE = "timer_active"
_KEY_CATEGORY_ID = "timer_category_id"
_KEY_START_TS = "timer_start_ts"
_KEY_MODE = "timer_mode"
_KEY_TARGET_SECONDS = "timer_target_seconds"
_KEY_PREFERRED_MODE = "timer_preferred_mode"
_KEY_LAST_COUNTDOWN_SECONDS = "timer_last_countdown_seconds"
_KEY_TOKEN = "timer_token"
_KEY_COMPLETED_TOKEN = "timer_completed_token"

Outcome = Tuple[bool, str, Optional[int]]


@dataclass(frozen=True)
class TimerState:
    """A complete, current snapshot of the single live timer."""

    is_active: bool
    category_id: Optional[int] = None
    start_ts: Optional[str] = None
    elapsed_seconds: int = 0
    mode: str = MODE_STOPWATCH
    target_seconds: int = 0
    remaining_seconds: int = 0
    is_expired: bool = False
    token: Optional[str] = None


class TimerService:
    """Starts, stops, switches, discards, and reconciles one timer."""

    def __init__(
        self,
        settings_repo: SettingsRepository,
        entry_service: EntryService,
        *,
        now_provider: Callable[[], datetime] = datetime.now,
    ) -> None:
        self.settings = settings_repo
        self.entries = entry_service
        self._now = now_provider

    # ------------------------------------------------------------------ #
    # Reading and preferences
    # ------------------------------------------------------------------ #
    def preferred_mode(self) -> str:
        mode = self.settings.get(_KEY_PREFERRED_MODE, MODE_STOPWATCH)
        return mode if mode in TIMER_MODES else MODE_STOPWATCH

    def last_countdown_seconds(self) -> int:
        value = self._parse_int(self.settings.get(_KEY_LAST_COUNTDOWN_SECONDS, ""))
        return value if self._valid_duration(value) else 25 * 60

    def set_preferred_mode(self, mode: str) -> None:
        self._validate_mode(mode)
        if self.current_state().is_active:
            raise ValueError("Timer mode cannot change while a timer is running.")
        self.settings.set(_KEY_PREFERRED_MODE, mode)
        bus.publish(TIMER_STATE_CHANGED)

    def set_last_countdown_seconds(self, duration_seconds: int) -> None:
        self._validate_duration(duration_seconds)
        self.settings.set(_KEY_LAST_COUNTDOWN_SECONDS, str(duration_seconds))
        bus.publish(TIMER_STATE_CHANGED)

    def current_state(self) -> TimerState:
        """Read the live state, calculating all time from ``now`` fresh."""
        if self.settings.get(_KEY_ACTIVE) != "1":
            return TimerState(is_active=False, mode=self.preferred_mode())

        category_id = self._parse_int(self.settings.get(_KEY_CATEGORY_ID, ""))
        start_ts = self.settings.get(_KEY_START_TS)
        if not category_id or not start_ts:
            return TimerState(is_active=False, mode=self.preferred_mode())

        try:
            start = time_utils.parse_live_ts(start_ts)
        except ValueError:
            return TimerState(is_active=False, mode=self.preferred_mode())

        mode = self.settings.get(_KEY_MODE, MODE_STOPWATCH)
        mode = mode if mode in TIMER_MODES else MODE_STOPWATCH
        target = self._parse_int(self.settings.get(_KEY_TARGET_SECONDS, ""))
        if mode == MODE_COUNTDOWN and not self._valid_duration(target):
            # A partially-written legacy/corrupt countdown must not run forever.
            return TimerState(is_active=False, mode=self.preferred_mode())

        elapsed = max(0, int((self._now() - start).total_seconds()))
        remaining = max(0, target - elapsed) if mode == MODE_COUNTDOWN else 0
        return TimerState(
            is_active=True,
            category_id=category_id,
            start_ts=start_ts,
            elapsed_seconds=elapsed,
            mode=mode,
            target_seconds=target if mode == MODE_COUNTDOWN else 0,
            remaining_seconds=remaining,
            is_expired=mode == MODE_COUNTDOWN and elapsed >= target,
            token=self.settings.get(_KEY_TOKEN) or None,
        )

    # ------------------------------------------------------------------ #
    # Starting, stopping and discarding
    # ------------------------------------------------------------------ #
    def start(
        self,
        category_id: int,
        mode: str = MODE_STOPWATCH,
        duration_seconds: Optional[int] = None,
    ) -> None:
        """Start a stopwatch or countdown for ``category_id``.

        Calling ``start(category_id)`` remains the original stopwatch API.
        A countdown accepts only whole-second values in the documented range;
        UI callers use whole minutes, while the service validates every caller.
        """
        self._validate_mode(mode)
        if mode == MODE_COUNTDOWN:
            if duration_seconds is None:
                raise ValueError("Countdown duration is required.")
            self._validate_duration(duration_seconds)
        elif duration_seconds is not None:
            # Stopwatch intentionally ignores an omitted duration, but a caller
            # supplying one is harmless and preserves the legacy API.
            duration_seconds = None

        state = self.current_state()
        if state.is_active:
            if state.category_id == category_id and state.mode == mode:
                return
            if state.mode == MODE_COUNTDOWN:
                raise ValueError("Cannot switch category while a countdown is running.")
            # Preserve the existing one-tap stopwatch category-switch behavior.
            self.stop()

        now_ts = self._now().strftime("%Y-%m-%d %H:%M:%S")
        token = uuid4().hex
        self.settings.set(_KEY_ACTIVE, "1", commit=False)
        self.settings.set(_KEY_CATEGORY_ID, str(category_id), commit=False)
        self.settings.set(_KEY_START_TS, now_ts, commit=False)
        self.settings.set(_KEY_MODE, mode, commit=False)
        self.settings.set(_KEY_TARGET_SECONDS, str(duration_seconds or 0), commit=False)
        self.settings.set(_KEY_TOKEN, token, commit=False)
        self.settings.set(_KEY_PREFERRED_MODE, mode, commit=False)
        if mode == MODE_COUNTDOWN:
            self.settings.set(_KEY_LAST_COUNTDOWN_SECONDS, str(duration_seconds), commit=False)
        self.settings.conn.commit()
        bus.publish(TIMER_STATE_CHANGED)

    def stop(self, notes: str = "") -> Outcome:
        """Stop and record actual elapsed time, clearing even short sessions."""
        state = self.current_state()
        if not state.is_active:
            return (False, "No timer is running.", None)
        if state.is_expired:
            return self.reconcile_expired()

        start = time_utils.parse_live_ts(state.start_ts)
        end = self._now()
        result = self._save_session(
            state.category_id,
            start,
            end,
            notes,
            token=state.token,
            natural_completion=False,
        )
        return result

    def discard(self) -> None:
        """Abandon a timer without writing a time entry."""
        self._clear()
        bus.publish(TIMER_STATE_CHANGED)

    def reconcile_expired(self) -> Outcome:
        """Idempotently commit an expired countdown at its intended finish time."""
        state = self.current_state()
        if not state.is_active or state.mode != MODE_COUNTDOWN or not state.is_expired:
            return (False, "No expired countdown to reconcile.", None)

        token = state.token or ""
        if token and self.settings.get(_KEY_COMPLETED_TOKEN) == token:
            self._clear()
            bus.publish(TIMER_STATE_CHANGED)
            return (True, "Countdown already completed.", None)

        start = time_utils.parse_live_ts(state.start_ts)
        end = start + timedelta(seconds=state.target_seconds)
        return self._save_session(
            state.category_id,
            start,
            end,
            "",
            token=token,
            natural_completion=True,
        )

    # ------------------------------------------------------------------ #
    # Storage helpers
    # ------------------------------------------------------------------ #
    def _save_session(
        self,
        category_id: int,
        start: datetime,
        end: datetime,
        notes: str,
        *,
        token: Optional[str],
        natural_completion: bool,
    ) -> Outcome:
        """Write the entry and clear live state in one SQLite transaction."""
        # Entries are minute-precision. Anchor the stored start to its minute
        # and add the *actual whole elapsed minutes*, rather than flooring the
        # two wall-clock timestamps independently (which can accidentally log
        # almost one extra minute when a session begins late in a minute).
        elapsed_minutes = max(0, int((end - start).total_seconds() // 60))
        stored_start = start.replace(second=0, microsecond=0)
        start_ts = stored_start.strftime(TIMESTAMP_FMT)
        end_ts = (stored_start + timedelta(minutes=elapsed_minutes)).strftime(TIMESTAMP_FMT)
        conn = self.settings.conn
        try:
            conn.execute("BEGIN")
            ok, message, entry_id = self.entries.add_completed_session(
                category_id,
                start_ts,
                end_ts,
                notes,
                commit=False,
                publish=False,
            )
            if not ok and int((end - start).total_seconds()) > time_utils.MINUTES_PER_DAY * 60:
                clipped = start + timedelta(minutes=time_utils.MINUTES_PER_DAY - 1)
                ok, _message, entry_id = self.entries.add_completed_session(
                    category_id,
                    start_ts,
                    clipped.replace(second=0, microsecond=0).strftime(TIMESTAMP_FMT),
                    notes,
                    commit=False,
                    publish=False,
                )
                if ok:
                    message = (
                        "Timer had been running over 24h — logged the first "
                        "23h 59m. Please add the rest manually if needed."
                    )
            self._clear(commit=False)
            if natural_completion and token:
                self.settings.set(_KEY_COMPLETED_TOKEN, token, commit=False)
            conn.commit()
        except Exception:
            conn.rollback()
            raise

        if entry_id is not None:
            bus.publish(DATA_CHANGED, date=start_ts[:10])
        bus.publish(TIMER_STATE_CHANGED)
        return (ok, message, entry_id)

    def _clear(self, *, commit: bool = True) -> None:
        # Preferences are deliberately not reset: after stopping/discarding a
        # countdown the next idle screen still offers the last chosen duration.
        self.settings.set(_KEY_ACTIVE, "0", commit=False)
        self.settings.set(_KEY_CATEGORY_ID, "", commit=False)
        self.settings.set(_KEY_START_TS, "", commit=False)
        self.settings.set(_KEY_MODE, "", commit=False)
        self.settings.set(_KEY_TARGET_SECONDS, "", commit=False)
        self.settings.set(_KEY_TOKEN, "", commit=False)
        if commit:
            self.settings.conn.commit()

    @staticmethod
    def _parse_int(value: Optional[str]) -> int:
        try:
            return int(value or "0")
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _valid_duration(value: int) -> bool:
        return isinstance(value, int) and MIN_COUNTDOWN_SECONDS <= value <= MAX_COUNTDOWN_SECONDS

    @classmethod
    def _validate_duration(cls, value: int) -> None:
        if not cls._valid_duration(value):
            raise ValueError(
                "Countdown duration must be an integer between 60 and 86,340 seconds."
            )

    @staticmethod
    def _validate_mode(mode: str) -> None:
        if mode not in TIMER_MODES:
            raise ValueError("Timer mode must be stopwatch or countdown.")
