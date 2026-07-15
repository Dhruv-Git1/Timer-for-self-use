"""
The shared calculation engine.

Three small, pure functions that every higher-level service leans on:

  * :func:`build_day_category_minutes` — turn a pile of raw entries into a tidy
    "how many minutes of each category happened on each day" table, correctly
    splitting overnight sessions across the midnight boundary.
  * :func:`productive_recorded` — from one day's per-category minutes, work out
    the productive total and the recorded total.
  * :func:`classify_day` — decide whether a day is Complete / Partial / Failed /
    Neutral using the rule we agreed on (green only when every targeted category
    is met).

"Pure" means these functions only read their inputs and return a value — they
touch no database and keep no state — which makes the tricky rules easy to test
in isolation.
"""

from __future__ import annotations

from typing import Dict, List, Iterable, Tuple

from app.models.category import Category
from app.models.time_entry import TimeEntry
from app.models.stats import DayStatus
from app.utils import time_utils

# A day -> {category_id -> minutes} table. For example:
#   {"2026-07-15": {1: 240, 10: 60}}  means 240 min of category 1 and 60 of 10.
DayCatMinutes = Dict[str, Dict[int, int]]


def build_day_category_minutes(
    entries: Iterable[TimeEntry], start_date: str, end_date: str
) -> DayCatMinutes:
    """Bucket entry minutes by calendar day and category, splitting at midnight.

    Pass in every entry that could touch the ``[start_date, end_date]`` window —
    that means entries starting as early as the day *before* ``start_date``,
    because an overnight session begun the previous night spills a few minutes
    into ``start_date``. Chunks that fall outside the window are ignored, so it
    is safe to over-fetch.
    """
    table: DayCatMinutes = {}
    for entry in entries:
        for day, minutes in time_utils.split_by_day(entry.start_ts, entry.end_ts):
            if start_date <= day <= end_date:
                per_cat = table.setdefault(day, {})
                per_cat[entry.category_id] = per_cat.get(entry.category_id, 0) + minutes
    return table


def productive_recorded(
    cat_minutes: Dict[int, int], categories_by_id: Dict[int, Category]
) -> Tuple[int, int]:
    """Return ``(productive_minutes, recorded_minutes)`` for one day.

    Recorded time counts every category; productive time counts only categories
    whose "productive" flag is on. We look categories up in a map that includes
    archived ones, because an old entry can still point at a category you have
    since archived.
    """
    recorded = sum(cat_minutes.values())
    productive = 0
    for cat_id, minutes in cat_minutes.items():
        category = categories_by_id.get(cat_id)
        if category is not None and category.is_productive:
            productive += minutes
    return productive, recorded


def classify_day(
    day: str,
    cat_minutes: Dict[int, int],
    targeted_categories: List[Category],
    first_date: str | None,
    today: str,
) -> DayStatus:
    """Decide a day's status from its per-category minutes.

    The rule (the one you chose):
      * GREEN / Complete  — every targeted category met its goal that day.
      * YELLOW / Partial  — at least one targeted category met, but not all.
      * RED / Failed      — a real past/today with targets where none were met
                            (including a day with no entries at all).
      * GREY / Neutral    — the day is in the future, there are no targets set,
                            or the day is before your very first logged entry
                            (so it is "not applicable" rather than a failure).

    ``targeted_categories`` should already be filtered to non-archived
    categories that have a target above zero.
    """
    # Future days and days before any data are simply "not applicable".
    if day > today:
        return DayStatus.NEUTRAL
    if first_date is None or day < first_date:
        return DayStatus.NEUTRAL
    if not targeted_categories:
        return DayStatus.NEUTRAL

    met = sum(
        1
        for c in targeted_categories
        if cat_minutes.get(c.id, 0) >= c.daily_target_minutes
    )
    total = len(targeted_categories)

    if met == total:
        return DayStatus.COMPLETE
    if met >= 1:
        return DayStatus.PARTIAL
    return DayStatus.FAILED


def classify_range(
    entries: Iterable[TimeEntry],
    categories: List[Category],
    start_date: str,
    end_date: str,
    first_date: str | None,
    today: str,
) -> Dict[str, DayStatus]:
    """Classify every day from ``start_date`` to ``end_date`` (inclusive).

    Returns a ``{date: DayStatus}`` map. Both the calendar (a month at a time)
    and the streak counter (the whole history) use this, so a day is always
    colored the same way no matter which screen asks. Pass entries covering one
    day earlier than ``start_date`` so overnight spillover is counted.
    """
    targeted = [
        c for c in categories if not c.is_archived and c.daily_target_minutes > 0
    ]
    table = build_day_category_minutes(entries, start_date, end_date)

    statuses: Dict[str, DayStatus] = {}
    day = start_date
    while day <= end_date:
        statuses[day] = classify_day(
            day, table.get(day, {}), targeted, first_date, today
        )
        day = time_utils.add_days(day, 1)
    return statuses
