"""
Input validation helpers.

Each function checks one kind of user input and returns a simple
``(ok, message)`` pair: ``ok`` is True/False, and ``message`` is a short,
plain-English explanation to show when something is wrong (empty string when
everything is fine).

Returning a message instead of raising an exception lets the forms display a
gentle red hint under the field rather than crashing the app.
"""

from __future__ import annotations

from typing import Tuple

from app.utils import time_utils

# A validation result is just "did it pass?" plus "what to tell the user".
Result = Tuple[bool, str]

OK: Result = (True, "")


def validate_category_name(name: str, existing_names: set[str]) -> Result:
    """Check a new/edited category name.

    ``existing_names`` is the set of names already in use (lower-cased by the
    caller) so we can catch duplicates. It should exclude the category being
    edited so renaming to the same name is allowed.
    """
    name = (name or "").strip()
    if not name:
        return (False, "Category name cannot be empty.")
    if len(name) > 40:
        return (False, "Category name is too long (max 40 characters).")
    if name.lower() in existing_names:
        return (False, f'A category named "{name}" already exists.')
    return OK


def validate_target_minutes(text: str) -> Result:
    """Check a daily-target value typed as text (minutes)."""
    text = (text or "").strip()
    if text == "":
        return OK  # blank means "no target", which is allowed
    if not text.isdigit():
        return (False, "Daily target must be a whole number of minutes.")
    if int(text) > time_utils.MINUTES_PER_DAY:
        return (False, "Daily target cannot exceed 24 hours (1440 minutes).")
    return OK


def validate_entry(log_date: str, start: str, end: str) -> Result:
    """Check a full time entry before it is saved.

    Delegates the hard part — the midnight-crossing and duration rules — to
    :func:`time_utils.build_timestamps`, and turns any complaint it raises into
    a friendly ``(False, message)`` result.
    """
    if not time_utils.is_valid_date(log_date):
        return (False, "Please choose a valid date.")
    if not time_utils.is_valid_time(start):
        return (False, "Start time must be in HH:MM 24-hour format.")
    if not time_utils.is_valid_time(end):
        return (False, "End time must be in HH:MM 24-hour format.")
    try:
        time_utils.build_timestamps(log_date, start, end)
    except ValueError as exc:
        return (False, str(exc))
    return OK
