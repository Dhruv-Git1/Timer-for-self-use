"""Reads and writes for saved daily reflections."""

from __future__ import annotations

from typing import Optional

from app.database.repositories.base_repo import BaseRepository
from app.models.daily_reflection import DailyReflection


class DailyReflectionRepository(BaseRepository):
    """Persist at most one free-text reflection for each calendar date."""

    def get(self, log_date: str) -> Optional[DailyReflection]:
        row = self.conn.execute(
            "SELECT log_date, notes FROM daily_reflections WHERE log_date = ?",
            (log_date,),
        ).fetchone()
        return DailyReflection.from_row(row) if row else None

    def list_by_date_range(self, start_date: str, end_date: str) -> list[DailyReflection]:
        rows = self.conn.execute(
            """
            SELECT log_date, notes
              FROM daily_reflections
             WHERE log_date BETWEEN ? AND ?
             ORDER BY log_date
            """,
            (start_date, end_date),
        ).fetchall()
        return [DailyReflection.from_row(row) for row in rows]

    def set(self, log_date: str, notes: str) -> None:
        if not notes:
            self.conn.execute("DELETE FROM daily_reflections WHERE log_date = ?", (log_date,))
        else:
            self.conn.execute(
                """
                INSERT INTO daily_reflections (log_date, notes)
                VALUES (?, ?)
                ON CONFLICT(log_date) DO UPDATE SET
                    notes = excluded.notes,
                    updated_at = datetime('now')
                """,
                (log_date, notes),
            )
        self.conn.commit()
