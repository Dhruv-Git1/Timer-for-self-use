"""
Live timer business logic.

This is what makes "press Start, do the activity, press Stop" work. The running
timer's state — which category, and since when — is kept in the same key/value
settings table the app already uses for things like the theme choice, via
:class:`SettingsRepository`. That means it survives closing and reopening the
app with no extra database table: elapsed time is always just "now minus the
stored start time", so reopening the app naturally shows the timer still
counting, caught up to the real elapsed time.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Tuple

from app.database.repositories.settings_repo import SettingsRepository
from app.services.entry_service import EntryService
from app.utils import time_utils
from app.utils.event_bus import bus, TIMER_STATE_CHANGED
from config import TIMESTAMP_FMT

# The three app_meta keys that together describe "is a timer running, and for
# what". Kept together here so the storage format has one home.
_KEY_ACTIVE = "timer_active"
_KEY_CATEGORY_ID = "timer_category_id"
_KEY_START_TS = "timer_start_ts"

Outcome = Tuple[bool, str, Optional[int]]


@dataclass
class TimerState:
    """A snapshot of the timer right now."""

    is_active: bool
    category_id: Optional[int] = None
    start_ts: Optional[str] = None
    elapsed_seconds: int = 0


class TimerService:
    """Starts, stops, switches and discards the one live timer."""

    def __init__(self, settings_repo: SettingsRepository, entry_service: EntryService) -> None:
        self.settings = settings_repo
        self.entries = entry_service

    # ------------------------------------------------------------------ #
    # Reading the current state
    # ------------------------------------------------------------------ #
    def current_state(self) -> TimerState:
        """The live state of the timer, computed fresh against the real clock."""
        if self.settings.get(_KEY_ACTIVE) != "1":
            return TimerState(is_active=False)

        category_id = int(self.settings.get(_KEY_CATEGORY_ID, "0") or "0")
        start_ts = self.settings.get(_KEY_START_TS)
        if not start_ts:
            # Defensive: corrupt/partial state should read as "not running"
            # rather than crash the UI.
            return TimerState(is_active=False)

        elapsed = int((datetime.now() - time_utils.parse_live_ts(start_ts)).total_seconds())
        return TimerState(
            is_active=True, category_id=category_id,
            start_ts=start_ts, elapsed_seconds=max(0, elapsed),
        )

    # ------------------------------------------------------------------ #
    # Starting, stopping, switching, discarding
    # ------------------------------------------------------------------ #
    def start(self, category_id: int) -> None:
        """Start the timer for ``category_id``.

        If a different category is already running, the current session is
        stopped and saved first, then the new one begins (a one-click "switch
        activity"). Starting the category that is already running is a no-op.
        """
        state = self.current_state()
        if state.is_active:
            if state.category_id == category_id:
                return
            self.stop()  # auto-switch: save the old session before starting the new one

        now_ts = time_utils.now_live_ts()
        self.settings.set(_KEY_ACTIVE, "1")
        self.settings.set(_KEY_CATEGORY_ID, str(category_id))
        self.settings.set(_KEY_START_TS, now_ts)
        bus.publish(TIMER_STATE_CHANGED)

    def stop(self, notes: str = "") -> Outcome:
        """Stop the running timer and save it as a real time entry.

        The timer state is always cleared, whether or not an entry ends up
        being saved (a sub-minute session is discarded, not left "stuck
        running"). Returns the same ``(ok, message, entry_id)`` shape the rest
        of the entry-writing methods use.
        """
        state = self.current_state()
        if not state.is_active:
            return (False, "No timer is running.", None)

        end_ts = datetime.now().strftime(TIMESTAMP_FMT)
        # Saved entries are minute-precision; the live start_ts may carry
        # seconds (see now_live_ts), so truncate before it reaches storage.
        # The first 16 characters are "YYYY-MM-DD HH:MM" either way.
        minute_start_ts = state.start_ts[:16]
        ok, msg, entry_id = self.entries.add_completed_session(
            state.category_id, minute_start_ts, end_ts, notes
        )
        if not ok and state.elapsed_seconds > time_utils.MINUTES_PER_DAY * 60:
            # A timer left running for more than 24h (forgotten overnight, say)
            # cannot be stored as one entry — the schema caps a session at a
            # day. Rather than silently losing the whole thing, save the first
            # 23h59m and tell the user to log the rest by hand.
            clipped_end = time_utils.parse_ts(minute_start_ts) + timedelta(
                minutes=time_utils.MINUTES_PER_DAY - 1
            )
            ok, _msg, entry_id = self.entries.add_completed_session(
                state.category_id, minute_start_ts, clipped_end.strftime(TIMESTAMP_FMT), notes
            )
            if ok:
                msg = ("Timer had been running over 24h — logged the first "
                       "23h 59m. Please add the rest manually if needed.")
        self._clear()
        bus.publish(TIMER_STATE_CHANGED)
        return (ok, msg, entry_id)

    def discard(self) -> None:
        """Abandon the running timer without saving anything."""
        self._clear()
        bus.publish(TIMER_STATE_CHANGED)

    def _clear(self) -> None:
        self.settings.set(_KEY_ACTIVE, "0")
