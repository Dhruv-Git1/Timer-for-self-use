"""
Export the tracked data to Excel, CSV or JSON.

The SQLite database always stays the real, authoritative copy of your data.
These exports are just convenient snapshots for backup or for poking at the
numbers in another tool (a spreadsheet, say). Every export writes a fresh,
timestamped file so you never clobber an older one.
"""

from __future__ import annotations

import csv
import json
import os
from datetime import datetime
from typing import Dict, List, Tuple

import config
from app.database.repositories.category_repo import CategoryRepository
from app.database.repositories.entry_repo import EntryRepository

_ENTRY_FIELDNAMES = [
    "id",
    "date",
    "start_time",
    "end_time",
    "duration_minutes",
    "duration",
    "category",
    "productive",
    "crosses_midnight",
    "notes",
]


class ExportService:
    """Turns the current database contents into Excel/CSV/JSON files."""

    def __init__(
        self, entry_repo: EntryRepository, category_repo: CategoryRepository
    ) -> None:
        self.entries = entry_repo
        self.categories = category_repo

    # ------------------------------------------------------------------ #
    # Gathering the data into plain rows
    # ------------------------------------------------------------------ #
    def _entry_rows(self) -> List[Dict]:
        """Every entry as a flat dictionary, ready for a table or JSON."""
        rows = []
        for e in self.entries.list_all():
            rows.append({
                "id": e.id,
                "date": e.log_date,
                "start_time": e.start_time,
                "end_time": e.end_time,
                "duration_minutes": e.duration_minutes,
                "duration": e.duration_label,
                "category": e.category_name,
                "productive": bool(e.is_productive),
                "crosses_midnight": e.crosses_midnight,
                "notes": e.notes,
            })
        return rows

    def _category_rows(self) -> List[Dict]:
        """Every category as a flat dictionary."""
        rows = []
        for c in self.categories.list_all(include_archived=True):
            rows.append({
                "id": c.id,
                "name": c.name,
                "productive": c.is_productive,
                "daily_target_minutes": c.daily_target_minutes,
                "color": c.color,
                "archived": c.is_archived,
            })
        return rows

    def _timestamped_path(self, extension: str) -> str:
        """Build an export file path like ``exports/timetracker_2026....xlsx``."""
        config.ensure_directories()
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return os.path.join(config.EXPORT_DIR, f"timetracker_{stamp}.{extension}")

    # ------------------------------------------------------------------ #
    # The three export formats
    # ------------------------------------------------------------------ #
    def to_excel(self) -> Tuple[bool, str]:
        """Write an .xlsx workbook with an Entries sheet and a Categories sheet."""
        # pandas is desktop-only. Keep this import local so CSV and JSON work
        # in the smaller Android package, which intentionally omits pandas.
        import pandas as pd

        path = self._timestamped_path("xlsx")
        entries_df = pd.DataFrame(self._entry_rows())
        categories_df = pd.DataFrame(self._category_rows())
        # openpyxl is the engine that actually writes the modern .xlsx format.
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            entries_df.to_excel(writer, sheet_name="Entries", index=False)
            categories_df.to_excel(writer, sheet_name="Categories", index=False)
        return (True, path)

    def to_csv(self) -> Tuple[bool, str]:
        """Write the entries to a single .csv file (the most portable format).

        Plain stdlib csv — a flat list of dict rows needs nothing heavier, and
        staying off pandas here means this path also works on a packaged
        mobile build, which does not carry pandas.
        """
        path = self._timestamped_path("csv")
        rows = self._entry_rows()
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=_ENTRY_FIELDNAMES)
            writer.writeheader()
            writer.writerows(rows)
        return (True, path)

    def to_json(self) -> Tuple[bool, str]:
        """Write categories and entries together into one .json file."""
        path = self._timestamped_path("json")
        payload = {
            "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "categories": self._category_rows(),
            "entries": self._entry_rows(),
        }
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
        return (True, path)
