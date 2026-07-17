"""
Time-entry business logic — the most important service in the app.

Every add, edit or delete of a logged session goes through here so that:
  * the input is validated before it ever reaches the database,
  * the stored ``start_ts`` / ``end_ts`` / ``duration_minutes`` /
    ``crosses_midnight`` fields are always computed the same way (via
    :mod:`time_utils`), and
  * a "data changed" signal is broadcast afterward so every open screen
    refreshes itself automatically.
"""

from __future__ import annotations

from typing import List, Optional, Set, Tuple

from app.database.repositories.category_repo import CategoryRepository
from app.database.repositories.entry_repo import EntryRepository
from app.models.time_entry import TimeEntry
from app.utils import time_utils, validators
from app.utils.event_bus import bus, DATA_CHANGED

# "(ok, message, entry_id)" — same shape the category service uses.
Outcome = Tuple[bool, str, Optional[int]]


class EntryService:
    """Create, edit, delete, duplicate and analyse logged time entries."""

    def __init__(
        self, entry_repo: EntryRepository, category_repo: Optional[CategoryRepository] = None
    ) -> None:
        self.repo = entry_repo
        self.categories = category_repo

    def _validate_timer_category(self, category_id: int) -> Tuple[bool, str]:
        if self.categories is None:
            return (True, "")
        category = self.categories.get(category_id)
        if category is None or category.is_archived:
            return (False, "Choose an active Timer category.")
        if not category.is_timer:
            return (False, "Time entries can only use Timer categories.")
        return (True, "")

    # ------------------------------------------------------------------ #
    # Reads
    # ------------------------------------------------------------------ #
    def entries_for_date(self, date_str: str) -> List[TimeEntry]:
        return self.repo.list_by_date(date_str)

    def get(self, entry_id: int) -> Optional[TimeEntry]:
        return self.repo.get(entry_id)

    # ------------------------------------------------------------------ #
    # Writes
    # ------------------------------------------------------------------ #
    def add_entry(
        self,
        category_id: int,
        log_date: str,
        start_time: str,
        end_time: str,
        notes: str = "",
    ) -> Outcome:
        """Validate and store a new entry.

        Returns ``(ok, message, new_id)``. On any validation problem it returns
        ``(False, reason, None)`` and writes nothing.
        """
        ok, msg = validators.validate_entry(log_date, start_time, end_time)
        if not ok:
            return (False, msg, None)
        ok, msg = self._validate_timer_category(category_id)
        if not ok:
            return (False, msg, None)

        start_ts, end_ts, duration, crosses = time_utils.build_timestamps(
            log_date, start_time, end_time
        )
        new_id = self.repo.create(
            category_id, log_date, start_ts, end_ts, duration, crosses, notes.strip()
        )
        bus.publish(DATA_CHANGED, date=log_date)
        return (True, "", new_id)

    def add_completed_session(
        self,
        category_id: int,
        start_ts: str,
        end_ts: str,
        notes: str = "",
        *,
        commit: bool = True,
        publish: bool = True,
    ) -> Outcome:
        """Store an entry from two real timestamps already captured by the timer.

        Unlike :meth:`add_entry`, this skips the ``HH:MM``-string validation
        (there is nothing to parse — the timer already captured two valid clock
        readings), but still enforces the same duration bounds so a bad session
        can never reach the database.
        """
        log_date, duration, crosses = time_utils.entry_fields_from_timestamps(
            start_ts, end_ts
        )
        ok, msg = self._validate_timer_category(category_id)
        if not ok:
            return (False, msg, None)
        if duration <= 0:
            return (False, "Session too short to log.", None)
        if duration > time_utils.MINUTES_PER_DAY:
            return (False, "Session exceeds 24 hours.", None)

        new_id = self.repo.create(
            category_id,
            log_date,
            start_ts,
            end_ts,
            duration,
            crosses,
            notes.strip(),
            commit=commit,
        )
        if publish:
            bus.publish(DATA_CHANGED, date=log_date)
        return (True, "", new_id)

    def update_entry(
        self,
        entry_id: int,
        category_id: int,
        log_date: str,
        start_time: str,
        end_time: str,
        notes: str = "",
    ) -> Outcome:
        """Validate and overwrite an existing entry, recomputing derived fields."""
        ok, msg = validators.validate_entry(log_date, start_time, end_time)
        if not ok:
            return (False, msg, None)
        ok, msg = self._validate_timer_category(category_id)
        if not ok:
            return (False, msg, None)

        start_ts, end_ts, duration, crosses = time_utils.build_timestamps(
            log_date, start_time, end_time
        )
        self.repo.update(
            entry_id, category_id, log_date, start_ts, end_ts,
            duration, crosses, notes.strip(),
        )
        bus.publish(DATA_CHANGED, date=log_date)
        return (True, "", entry_id)

    def delete_entry(self, entry_id: int) -> Outcome:
        """Permanently remove one entry."""
        entry = self.repo.get(entry_id)
        self.repo.delete(entry_id)
        bus.publish(DATA_CHANGED, date=entry.log_date if entry else None)
        return (True, "", entry_id)

    def duplicate_day(self, source_date: str, target_date: str) -> Tuple[bool, str, int]:
        """Copy every entry from ``source_date`` onto ``target_date``.

        This powers the "duplicate previous day" shortcut: if most days look
        alike, you can clone yesterday and then tweak. The clock times are kept;
        only the date shifts. Returns ``(ok, message, number_copied)``.
        """
        source_entries = self.repo.list_by_date(source_date)
        if not source_entries:
            return (False, f"No entries found on {source_date} to copy.", 0)

        copied = 0
        for entry in source_entries:
            # Rebuild timestamps against the target date so an overnight session
            # keeps its overnight shape on the new day.
            start_ts, end_ts, duration, crosses = time_utils.build_timestamps(
                target_date, entry.start_time, entry.end_time
            )
            self.repo.create(
                entry.category_id, target_date, start_ts, end_ts,
                duration, crosses, entry.notes,
            )
            copied += 1

        bus.publish(DATA_CHANGED, date=target_date)
        return (True, f"Copied {copied} entr{'y' if copied == 1 else 'ies'}.", copied)

    # ------------------------------------------------------------------ #
    # Analysis
    # ------------------------------------------------------------------ #
    def overlapping_ids(self, date_str: str) -> Set[int]:
        """Return the ids of entries on a day that overlap another entry.

        Overlaps are allowed (you might listen to a podcast while exercising),
        but the Entries screen flags them with a small warning so you can spot an
        accidental double-log. Two sessions overlap when each starts before the
        other ends.
        """
        entries = self.repo.list_by_date(date_str)
        overlapping: Set[int] = set()
        # Convert to (start, end, id) once so we are not re-parsing in the loop.
        spans = [
            (time_utils.parse_ts(e.start_ts), time_utils.parse_ts(e.end_ts), e.id)
            for e in entries
        ]
        for i in range(len(spans)):
            a_start, a_end, a_id = spans[i]
            for j in range(i + 1, len(spans)):
                b_start, b_end, b_id = spans[j]
                if a_start < b_end and b_start < a_end:
                    overlapping.add(a_id)
                    overlapping.add(b_id)
        return overlapping
