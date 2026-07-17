"""Reads and writes for per-day checkbox and counter progress."""

from __future__ import annotations

from typing import Optional

from app.database.repositories.base_repo import BaseRepository
from app.models.daily_progress import DailyProgress


class DailyProgressRepository(BaseRepository):
    """Store at most one non-negative value per category and local date."""

    def get(self, category_id: int, log_date: str) -> Optional[DailyProgress]:
        row = self.conn.execute(
            "SELECT category_id, log_date, value FROM daily_progress "
            "WHERE category_id = ? AND log_date = ?",
            (category_id, log_date),
        ).fetchone()
        return DailyProgress.from_row(row) if row else None

    def get_value(self, category_id: int, log_date: str) -> int:
        progress = self.get(category_id, log_date)
        return progress.value if progress else 0

    def total_for_range(self, category_id: int, start_date: str, end_date: str) -> int:
        """Return the category's saved counter/check-off total in a date range."""
        row = self.conn.execute(
            "SELECT COALESCE(SUM(value), 0) AS total FROM daily_progress "
            "WHERE category_id = ? AND log_date BETWEEN ? AND ?",
            (category_id, start_date, end_date),
        ).fetchone()
        return int(row["total"])

    def values_for_range(
        self, category_id: int, start_date: str, end_date: str
    ) -> dict[str, int]:
        rows = self.conn.execute(
            "SELECT log_date, value FROM daily_progress "
            "WHERE category_id = ? AND log_date BETWEEN ? AND ?",
            (category_id, start_date, end_date),
        ).fetchall()
        return {row["log_date"]: int(row["value"]) for row in rows}

    def set_value(self, category_id: int, log_date: str, value: int) -> int:
        value = max(0, int(value))
        if value == 0:
            self.conn.execute(
                "DELETE FROM daily_progress WHERE category_id = ? AND log_date = ?",
                (category_id, log_date),
            )
        else:
            self.conn.execute(
                """
                INSERT INTO daily_progress (category_id, log_date, value)
                VALUES (?, ?, ?)
                ON CONFLICT(category_id, log_date) DO UPDATE SET
                    value = excluded.value,
                    updated_at = datetime('now')
                """,
                (category_id, log_date, value),
            )
        self.conn.commit()
        return value
