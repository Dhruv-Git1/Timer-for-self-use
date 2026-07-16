"""
Category business logic.

Wraps the category repository with the rules the UI should not have to know
about: name validation, duplicate checking, and the "never destroy logged
history" policy that turns a risky delete into a safe archive when a category
already has entries.
"""

from __future__ import annotations

import sqlite3
from typing import List, Optional, Tuple

from app.database.repositories.category_repo import CategoryRepository
from app.models.category import (
    Category,
    TRACKING_CHECKOFF,
    TRACKING_COUNTER,
    TRACKING_MODES,
    TRACKING_TIMER,
)
from app.utils import validators
from app.utils.event_bus import bus, DATA_CHANGED

# A "(ok, message, value)" result: did it work, what to tell the user, and the
# new id when relevant.
Outcome = Tuple[bool, str, Optional[int]]


class CategoryService:
    """Create, edit, archive and delete activity categories."""

    def __init__(self, category_repo: CategoryRepository) -> None:
        self.repo = category_repo

    # ------------------------------------------------------------------ #
    # Reads
    # ------------------------------------------------------------------ #
    def list_categories(self, include_archived: bool = False) -> List[Category]:
        return self.repo.list_all(include_archived=include_archived)

    def get(self, category_id: int) -> Optional[Category]:
        return self.repo.get(category_id)

    def has_history(self, category_id: int) -> bool:
        return self.repo.has_history(category_id)

    def _existing_names(self, exclude_id: Optional[int] = None) -> set[str]:
        """Lower-cased set of category names, optionally excluding one id.

        Excluding the category being edited lets a user save it without renaming
        (so its own name does not count as a duplicate of itself).
        """
        return {
            c.name.lower()
            for c in self.repo.list_all(include_archived=True)
            if c.id != exclude_id
        }

    # ------------------------------------------------------------------ #
    # Writes
    # ------------------------------------------------------------------ #
    def create(
        self,
        name: str,
        color: str,
        is_productive: bool,
        target_minutes: int,
        tracking_mode: str = TRACKING_TIMER,
        target_count: int = 1,
        unit_label: str = "times",
        include_in_daily_score: bool = True,
    ) -> Outcome:
        """Validate and create a category. Returns (ok, message, new_id)."""
        ok, msg = validators.validate_category_name(name, self._existing_names())
        if not ok:
            return (False, msg, None)

        ok, msg = self._validate_tracking_fields(
            tracking_mode, target_minutes, target_count, unit_label
        )
        if not ok:
            return (False, msg, None)

        if tracking_mode != TRACKING_TIMER:
            is_productive = False
            target_minutes = 0
        if tracking_mode == TRACKING_CHECKOFF:
            target_count = 1

        # New categories go to the end of the current order.
        sort_order = len(self.repo.list_all(include_archived=True))
        new_id = self.repo.create(
            name,
            color,
            is_productive,
            target_minutes,
            sort_order,
            tracking_mode,
            target_count,
            unit_label,
            include_in_daily_score,
        )
        bus.publish(DATA_CHANGED)
        return (True, "", new_id)

    def update(self, category: Category) -> Outcome:
        """Validate and save an edited category."""
        ok, msg = validators.validate_category_name(
            category.name, self._existing_names(exclude_id=category.id)
        )
        if not ok:
            return (False, msg, None)
        if not isinstance(category.score_weight, int) or category.score_weight < 1:
            return (False, "Score weight must be a whole number of at least 1.", None)

        existing = self.repo.get(category.id)
        if existing is None:
            return (False, "Category no longer exists.", None)
        if (
            existing.tracking_mode != category.tracking_mode
            and self.repo.has_history(category.id)
        ):
            return (
                False,
                "Tracking mode cannot change after progress has been recorded. "
                "Archive this category and create a new one instead.",
                None,
            )
        ok, msg = self._validate_tracking_fields(
            category.tracking_mode,
            category.daily_target_minutes,
            category.daily_target_count,
            category.unit_label,
        )
        if not ok:
            return (False, msg, None)
        if category.tracking_mode != TRACKING_TIMER:
            category.is_productive = False
            category.daily_target_minutes = 0
        if category.tracking_mode == TRACKING_CHECKOFF:
            category.daily_target_count = 1
        self.repo.update(category)
        bus.publish(DATA_CHANGED)
        return (True, "", category.id)

    def set_archived(self, category_id: int, archived: bool) -> Outcome:
        """Archive (hide) or restore a category."""
        self.repo.set_archived(category_id, archived)
        bus.publish(DATA_CHANGED)
        return (True, "", category_id)

    def delete(self, category_id: int) -> Outcome:
        """Delete a category, protecting logged history.

        If the category has entries we refuse to delete it and suggest archiving
        instead — otherwise those entries would be orphaned or lost. The database
        also enforces this (ON DELETE RESTRICT); we check first so we can give a
        clear message, and still catch the database error as a safety net.
        """
        entry_count = self.repo.count_entries(category_id)
        progress_count = self.repo.count_progress_rows(category_id)
        if entry_count > 0 or progress_count > 0:
            parts = []
            if entry_count:
                parts.append(f"{entry_count} time entr{'y' if entry_count == 1 else 'ies'}")
            if progress_count:
                parts.append(
                    f"{progress_count} progress day{'s' if progress_count != 1 else ''}"
                )
            return (
                False,
                f"This category has {' and '.join(parts)}. "
                "Archive it instead to keep your history.",
                None,
            )
        try:
            self.repo.delete(category_id)
        except sqlite3.IntegrityError:
            return (
                False,
                "This category is still in use and cannot be deleted. "
                "Archive it instead.",
                None,
            )
        bus.publish(DATA_CHANGED)
        return (True, "", category_id)

    @staticmethod
    def _validate_tracking_fields(
        tracking_mode: str,
        target_minutes: int,
        target_count: int,
        unit_label: str,
    ) -> Tuple[bool, str]:
        if tracking_mode not in TRACKING_MODES:
            return (False, "Choose Timer, Check-off, or Counter.")
        if tracking_mode == TRACKING_TIMER:
            ok, msg = validators.validate_target_minutes(str(target_minutes))
            return (ok, msg)
        if tracking_mode == TRACKING_COUNTER:
            ok, msg = validators.validate_target_count(str(target_count))
            if not ok:
                return (ok, msg)
            return validators.validate_unit_label(unit_label)
        return (True, "")
