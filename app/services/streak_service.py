"""
Streak business logic.

A "streak" is a run of consecutive Complete (green) days. Two numbers matter:
the current streak (how many green days lead up to today) and the longest streak
you have ever achieved. Grey "not applicable" days are skipped rather than
counted as breaks, and today gets a grace period so an unfinished day can never
retroactively kill a streak.
"""

from __future__ import annotations

from typing import Dict, Optional

from app.database.repositories.category_repo import CategoryRepository
from app.database.repositories.entry_repo import EntryRepository
from app.models.stats import DayStatus
from app.services import aggregation
from app.utils import time_utils


class StreakService:
    """Computes current and longest streaks from the day-status history."""

    def __init__(
        self, category_repo: CategoryRepository, entry_repo: EntryRepository
    ) -> None:
        self.categories = category_repo
        self.entries = entry_repo

    def _statuses(self) -> tuple[Dict[str, DayStatus], Optional[str], str]:
        """Classify every day from the first entry up to today.

        Returns ``(statuses, first_date, today)``. When there is no data yet the
        status map is empty and ``first_date`` is None.
        """
        today = time_utils.today_str()
        bounds = self.entries.date_bounds()
        if bounds is None:
            return ({}, None, today)

        first_date = bounds[0]
        # Look at everything from the first logged day through today (today may
        # be later than the last entry, which is fine — those days classify as
        # Failed/Neutral as appropriate).
        end_date = max(bounds[1], today)
        prev_day = time_utils.add_days(first_date, -1)
        entries = self.entries.list_by_date_range(prev_day, end_date)
        categories = self.categories.list_all(include_archived=True)

        statuses = aggregation.classify_range(
            entries, categories, first_date, end_date, first_date, today
        )
        return (statuses, first_date, today)

    def current_streak(self) -> int:
        """Number of consecutive green days ending at today (with grace).

        If today is already green we count it; if today is not yet green we look
        at the streak ending yesterday instead, so a day still in progress does
        not appear to break the streak.
        """
        statuses, first_date, today = self._statuses()
        if first_date is None:
            return 0

        def count_back(from_day: str) -> int:
            streak = 0
            day = from_day
            while day >= first_date:
                status = statuses.get(day, DayStatus.NEUTRAL)
                if status == DayStatus.COMPLETE:
                    streak += 1
                elif status == DayStatus.NEUTRAL:
                    pass  # "not applicable" day: neither extends nor breaks
                else:
                    break  # a real Partial/Failed day ends the streak
                day = time_utils.add_days(day, -1)
            return streak

        if statuses.get(today) == DayStatus.COMPLETE:
            return count_back(today)
        # Grace: evaluate the streak as of yesterday.
        return count_back(time_utils.add_days(today, -1))

    def longest_streak(self) -> int:
        """The longest run of consecutive green days anywhere in the history."""
        statuses, first_date, today = self._statuses()
        if first_date is None:
            return 0

        longest = 0
        current = 0
        day = first_date
        while day <= today:
            status = statuses.get(day, DayStatus.NEUTRAL)
            if status == DayStatus.COMPLETE:
                current += 1
                longest = max(longest, current)
            elif status == DayStatus.NEUTRAL:
                pass  # skip without resetting
            else:
                current = 0
            day = time_utils.add_days(day, 1)
        return longest
