"""Reads and writes for the ``time_entries`` table."""

from __future__ import annotations

from typing import List, Optional, Tuple

from app.database.repositories.base_repo import BaseRepository
from app.models.time_entry import TimeEntry

# Every read joins the category so each entry arrives already labelled with its
# category name, color and productive flag — no second lookup needed.
_SELECT = """
    SELECT e.*,
           c.name          AS category_name,
           c.color         AS category_color,
           c.is_productive AS is_productive
      FROM time_entries e
      JOIN categories c ON c.id = e.category_id
"""


class EntryRepository(BaseRepository):
    """All database operations for logged time entries."""

    # ------------------------------------------------------------------ #
    # Reads
    # ------------------------------------------------------------------ #
    def get(self, entry_id: int) -> Optional[TimeEntry]:
        """Fetch one entry by id, or None."""
        row = self.conn.execute(
            _SELECT + " WHERE e.id = ?", (entry_id,)
        ).fetchone()
        return TimeEntry.from_row(row) if row else None

    def list_by_date(self, date_str: str) -> List[TimeEntry]:
        """All entries whose session *started* on ``date_str``, earliest first.

        This is what the Entries screen shows for a chosen day. Note it lists an
        overnight session on its start day only (where you logged it); the split
        across midnight matters for totals, not for which day the row appears on.
        """
        rows = self.conn.execute(
            _SELECT + " WHERE e.log_date = ? ORDER BY e.start_ts",
            (date_str,),
        ).fetchall()
        return [TimeEntry.from_row(r) for r in rows]

    def list_by_date_range(self, start_date: str, end_date: str) -> List[TimeEntry]:
        """All entries with a start day between two dates (inclusive)."""
        rows = self.conn.execute(
            _SELECT + " WHERE e.log_date BETWEEN ? AND ? ORDER BY e.start_ts",
            (start_date, end_date),
        ).fetchall()
        return [TimeEntry.from_row(r) for r in rows]

    def list_all(self) -> List[TimeEntry]:
        """Every entry ever logged, earliest first (used by export)."""
        rows = self.conn.execute(_SELECT + " ORDER BY e.start_ts").fetchall()
        return [TimeEntry.from_row(r) for r in rows]

    def date_bounds(self) -> Optional[Tuple[str, str]]:
        """The first and last log dates in the database, or None if empty.

        The streak and calendar code walks day-by-day between these bounds, so
        it needs to know how far back the data goes.
        """
        row = self.conn.execute(
            "SELECT MIN(log_date) AS lo, MAX(log_date) AS hi FROM time_entries"
        ).fetchone()
        if row is None or row["lo"] is None:
            return None
        return (row["lo"], row["hi"])

    def search(
        self,
        keyword: str = "",
        category_id: Optional[int] = None,
        date_str: Optional[str] = None,
    ) -> List[TimeEntry]:
        """Find entries matching any combination of keyword, category and date.

        ``keyword`` matches anywhere inside the notes (case-insensitive). Empty
        filters are ignored, so passing nothing returns everything. The pieces
        are combined with AND — a keyword *and* a category means both must hold.
        """
        clauses = []
        params: list = []
        if keyword.strip():
            clauses.append("e.notes LIKE ?")
            params.append(f"%{keyword.strip()}%")
        if category_id is not None:
            clauses.append("e.category_id = ?")
            params.append(category_id)
        if date_str:
            clauses.append("e.log_date = ?")
            params.append(date_str)

        sql = _SELECT
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY e.start_ts DESC"
        rows = self.conn.execute(sql, params).fetchall()
        return [TimeEntry.from_row(r) for r in rows]

    # ------------------------------------------------------------------ #
    # Writes
    # ------------------------------------------------------------------ #
    def create(
        self,
        category_id: int,
        log_date: str,
        start_ts: str,
        end_ts: str,
        duration_minutes: int,
        crosses_midnight: bool,
        notes: str,
    ) -> int:
        """Insert a new entry and return its new id."""
        cur = self.conn.execute(
            """
            INSERT INTO time_entries
                (category_id, log_date, start_ts, end_ts,
                 duration_minutes, crosses_midnight, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (category_id, log_date, start_ts, end_ts,
             duration_minutes, 1 if crosses_midnight else 0, notes),
        )
        self.conn.commit()
        return cur.lastrowid

    def update(
        self,
        entry_id: int,
        category_id: int,
        log_date: str,
        start_ts: str,
        end_ts: str,
        duration_minutes: int,
        crosses_midnight: bool,
        notes: str,
    ) -> None:
        """Overwrite an existing entry with recomputed fields."""
        self.conn.execute(
            """
            UPDATE time_entries
               SET category_id = ?,
                   log_date = ?,
                   start_ts = ?,
                   end_ts = ?,
                   duration_minutes = ?,
                   crosses_midnight = ?,
                   notes = ?,
                   updated_at = datetime('now')
             WHERE id = ?
            """,
            (category_id, log_date, start_ts, end_ts, duration_minutes,
             1 if crosses_midnight else 0, notes, entry_id),
        )
        self.conn.commit()

    def delete(self, entry_id: int) -> None:
        """Permanently remove one entry."""
        self.conn.execute("DELETE FROM time_entries WHERE id = ?", (entry_id,))
        self.conn.commit()
