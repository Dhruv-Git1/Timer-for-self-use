"""
Time and date helpers.

Everything the app knows about turning the text you type ("09:30") into real
timestamps, working out how long a session lasted, and splitting an overnight
session across two calendar days lives here. Keeping it in one module means the
midnight-crossing rule is defined exactly once, so it can never disagree with
itself in different corners of the code.

Vocabulary used below:
  * "time string"  -> "HH:MM" in 24-hour form, e.g. "23:05".
  * "date string"  -> "YYYY-MM-DD", e.g. "2026-07-15".
  * "timestamp"    -> a full "YYYY-MM-DD HH:MM", e.g. "2026-07-15 23:05".
"""

from __future__ import annotations

import re
from datetime import datetime, date, timedelta
from typing import List, Tuple, Optional

from config import DATE_FMT, LIVE_TIMESTAMP_FMT, TIME_FMT, TIMESTAMP_FMT

# A "time of day" is one or two digits for the hour (0-23) then ":" then exactly
# two digits for the minute (00-59). We deliberately reject 24:00 — midnight is
# 00:00 of the next day, never 24:00.
_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):[0-5]\d$")

MINUTES_PER_DAY = 24 * 60  # 1440


# --------------------------------------------------------------------------- #
# Parsing and validation
# --------------------------------------------------------------------------- #
def is_valid_time(text: str) -> bool:
    """Return True if ``text`` looks like a 24-hour HH:MM time."""
    return bool(_TIME_RE.match(text.strip())) if text else False


def normalize_time(text: str) -> Optional[str]:
    """Tidy a user-typed time into canonical "HH:MM", or return None if invalid.

    Accepts sloppy input like "9:5" is NOT allowed (minutes must be two digits),
    but "9:05" becomes "09:05". Returning None (rather than raising) lets the
    form show a gentle inline error instead of crashing.
    """
    if not text:
        return None
    text = text.strip()
    if not _TIME_RE.match(text):
        return None
    hh, mm = text.split(":")
    return f"{int(hh):02d}:{mm}"


def is_valid_date(text: str) -> bool:
    """Return True if ``text`` is a real YYYY-MM-DD calendar date."""
    try:
        datetime.strptime(text.strip(), DATE_FMT)
        return True
    except (ValueError, AttributeError):
        return False


# --------------------------------------------------------------------------- #
# Building and reading timestamps
# --------------------------------------------------------------------------- #
def build_timestamps(
    log_date: str, start_time: str, end_time: str
) -> Tuple[str, str, int, bool]:
    """Turn a date + start/end time into stored timestamp fields.

    This is the one and only place the "crosses midnight" rule is applied:
    if the end time is not strictly after the start time, we assume the session
    ran into the next calendar day (the classic Sleep 23:00 -> 07:00 case).

    Returns a 4-tuple:
        (start_ts, end_ts, duration_minutes, crosses_midnight)

    Raises ValueError with a friendly message when the input cannot form a valid
    session (bad format, identical start/end, or a span longer than 24 hours).
    """
    s = normalize_time(start_time)
    e = normalize_time(end_time)
    if s is None:
        raise ValueError("Start time must be in HH:MM 24-hour format.")
    if e is None:
        raise ValueError("End time must be in HH:MM 24-hour format.")
    if not is_valid_date(log_date):
        raise ValueError("Date must be a real calendar date (YYYY-MM-DD).")

    if s == e:
        # Identical times are ambiguous — is it a zero-length session or a full
        # 24 hours? Rather than guess, we refuse it. This check must come before
        # the midnight logic below, which would otherwise read "equal" as
        # "crosses midnight" and silently invent a 24-hour session.
        raise ValueError("Start and end time cannot be identical.")

    start_dt = datetime.strptime(f"{log_date} {s}", TIMESTAMP_FMT)
    end_dt = datetime.strptime(f"{log_date} {e}", TIMESTAMP_FMT)

    crosses_midnight = end_dt < start_dt
    if crosses_midnight:
        # End time is earlier in the day than the start, so it belongs to the
        # next calendar day (the classic overnight session).
        end_dt += timedelta(days=1)

    duration_minutes = int((end_dt - start_dt).total_seconds() // 60)
    if duration_minutes > MINUTES_PER_DAY:
        raise ValueError("A single session cannot be longer than 24 hours.")

    return (
        start_dt.strftime(TIMESTAMP_FMT),
        end_dt.strftime(TIMESTAMP_FMT),
        duration_minutes,
        crosses_midnight,
    )


def parse_ts(ts: str) -> datetime:
    """Parse a stored "YYYY-MM-DD HH:MM" timestamp back into a datetime."""
    return datetime.strptime(ts, TIMESTAMP_FMT)


def now_live_ts() -> str:
    """The current moment as a seconds-precision timestamp.

    Used only as the live timer's start baseline, so elapsed time (measured
    against the equally precise ``datetime.now()``) starts at 0 instead of
    inheriting whatever seconds had already ticked by in the current minute.
    """
    return datetime.now().strftime(LIVE_TIMESTAMP_FMT)


def parse_live_ts(ts: str) -> datetime:
    """Parse a live-timer start timestamp.

    Accepts the seconds-precision format written by :func:`now_live_ts`, and
    falls back to the plain minute format so a timer already running from
    before this format existed still reads back correctly.
    """
    try:
        return datetime.strptime(ts, LIVE_TIMESTAMP_FMT)
    except ValueError:
        return parse_ts(ts)


def ts_to_time(ts: str) -> str:
    """Pull just the "HH:MM" part out of a stored timestamp (for display)."""
    return parse_ts(ts).strftime(TIME_FMT)


def ts_to_date(ts: str) -> str:
    """Pull just the "YYYY-MM-DD" part out of a stored timestamp."""
    return parse_ts(ts).strftime(DATE_FMT)


# --------------------------------------------------------------------------- #
# Deriving fields from two already-real timestamps (the live timer)
# --------------------------------------------------------------------------- #
def entry_fields_from_timestamps(start_ts: str, end_ts: str) -> Tuple[str, int, bool]:
    """Derive (log_date, duration_minutes, crosses_midnight) from two real timestamps.

    Unlike :func:`build_timestamps`, this does not need to *guess* whether a
    session crosses midnight — both ``start_ts`` and ``end_ts`` were already
    captured from the real clock (by the live timer), so their calendar dates
    are simply whatever they are. ``log_date`` is the day the session started.
    """
    start_dt = parse_ts(start_ts)
    end_dt = parse_ts(end_ts)
    duration_minutes = int((end_dt - start_dt).total_seconds() // 60)
    crosses_midnight = start_dt.date() != end_dt.date()
    return start_dt.strftime(DATE_FMT), duration_minutes, crosses_midnight


# --------------------------------------------------------------------------- #
# The midnight split
# --------------------------------------------------------------------------- #
def split_by_day(start_ts: str, end_ts: str) -> List[Tuple[str, int]]:
    """Break a session into per-calendar-day chunks of minutes.

    Almost every session sits inside one day and comes back as a single chunk,
    e.g. ``[("2026-07-15", 150)]``. An overnight session is divided at midnight,
    e.g. a Sleep from 23:00 to 07:00 returns
    ``[("2026-07-15", 60), ("2026-07-16", 420)]`` — one hour credited to the
    first day and seven to the next.

    Every "how much happened on this day" calculation in the app funnels through
    here, which is what makes the split-at-midnight rule consistent everywhere.
    """
    start_dt = parse_ts(start_ts)
    end_dt = parse_ts(end_ts)
    chunks: List[Tuple[str, int]] = []

    cursor = start_dt
    while cursor < end_dt:
        # Midnight that begins the day *after* the cursor's day.
        next_midnight = datetime.combine(
            cursor.date() + timedelta(days=1), datetime.min.time()
        )
        # The chunk ends either at that midnight or at the real end, whichever
        # comes first.
        chunk_end = min(next_midnight, end_dt)
        minutes = int((chunk_end - cursor).total_seconds() // 60)
        if minutes > 0:
            chunks.append((cursor.strftime(DATE_FMT), minutes))
        cursor = chunk_end

    return chunks


# --------------------------------------------------------------------------- #
# Formatting and small date helpers
# --------------------------------------------------------------------------- #
def fmt_duration(minutes: int) -> str:
    """Turn a minute count into a compact "Hh Mm" label.

    Examples: 150 -> "2h 30m", 45 -> "45m", 480 -> "8h", 0 -> "0m".
    """
    minutes = int(round(minutes))
    hours, mins = divmod(minutes, 60)
    if hours and mins:
        return f"{hours}h {mins}m"
    if hours:
        return f"{hours}h"
    return f"{mins}m"


def fmt_hours(minutes: int) -> str:
    """Turn minutes into a decimal-hours label, e.g. 150 -> "2.5 h"."""
    return f"{minutes / 60:.1f} h"


def fmt_clock(total_seconds: int) -> str:
    """Turn a second count into a ticking-clock label "H:MM:SS" (or "HH:MM:SS").

    Used for the live timer display, where whole seconds matter — unlike
    :func:`fmt_duration`, which rounds finished sessions to the minute.
    """
    total_seconds = max(0, int(total_seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}"


def today_str() -> str:
    """Today's date as a "YYYY-MM-DD" string."""
    return date.today().strftime(DATE_FMT)


def add_days(date_str: str, delta: int) -> str:
    """Return the date ``delta`` days away from ``date_str`` (delta may be < 0)."""
    d = datetime.strptime(date_str, DATE_FMT).date()
    return (d + timedelta(days=delta)).strftime(DATE_FMT)


def to_date(date_str: str) -> date:
    """Convert a "YYYY-MM-DD" string into a real ``date`` object."""
    return datetime.strptime(date_str, DATE_FMT).date()


def weekday_name(date_str: str) -> str:
    """Return the weekday name ("Monday", ...) for a date string."""
    from config import WEEKDAY_NAMES
    return WEEKDAY_NAMES[to_date(date_str).weekday()]


def fmt_short_date(date_str: str) -> str:
    """Turn a "YYYY-MM-DD" date into a short display label, e.g. "Jul 15"."""
    return to_date(date_str).strftime("%b %d")
