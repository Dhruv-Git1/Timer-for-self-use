"""
Search business logic.

A thin layer over the entry repository's combined search. It exists mainly to
give the UI one clear place to call, and to normalise empty filters (a blank box
means "don't filter on that").
"""

from __future__ import annotations

from typing import List, Optional

from app.database.repositories.entry_repo import EntryRepository
from app.models.time_entry import TimeEntry
from app.utils import time_utils


class SearchService:
    """Finds entries by keyword, category and/or date."""

    def __init__(self, entry_repo: EntryRepository) -> None:
        self.entries = entry_repo

    def search(
        self,
        keyword: str = "",
        category_id: Optional[int] = None,
        date_str: Optional[str] = None,
    ) -> List[TimeEntry]:
        """Return entries matching every filter that is provided.

        A blank keyword, ``None`` category, or blank/invalid date are simply
        ignored, so an empty search returns your whole history (newest first).
        """
        # Guard the date filter: only pass a genuine YYYY-MM-DD through.
        clean_date = date_str if (date_str and time_utils.is_valid_date(date_str)) else None
        return self.entries.search(
            keyword=keyword or "",
            category_id=category_id,
            date_str=clean_date,
        )
