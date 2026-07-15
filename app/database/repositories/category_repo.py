"""Reads and writes for the ``categories`` table."""

from __future__ import annotations

from typing import List, Optional

from app.database.repositories.base_repo import BaseRepository
from app.models.category import Category


class CategoryRepository(BaseRepository):
    """All database operations for activity categories."""

    # ------------------------------------------------------------------ #
    # Reads
    # ------------------------------------------------------------------ #
    def list_all(self, include_archived: bool = False) -> List[Category]:
        """Return categories in display order.

        By default archived (soft-deleted) categories are hidden, which is what
        pickers and the dashboard want. Pass ``include_archived=True`` for the
        management screen that lets you un-archive them.
        """
        sql = "SELECT * FROM categories"
        if not include_archived:
            sql += " WHERE is_archived = 0"
        sql += " ORDER BY sort_order, name COLLATE NOCASE"
        rows = self.conn.execute(sql).fetchall()
        return [Category.from_row(r) for r in rows]

    def get(self, category_id: int) -> Optional[Category]:
        """Fetch one category by id, or None if it does not exist."""
        row = self.conn.execute(
            "SELECT * FROM categories WHERE id = ?", (category_id,)
        ).fetchone()
        return Category.from_row(row) if row else None

    def count_entries(self, category_id: int) -> int:
        """How many time entries reference this category.

        Used to decide whether a category can be deleted outright or must be
        archived to preserve its history.
        """
        row = self.conn.execute(
            "SELECT COUNT(*) AS n FROM time_entries WHERE category_id = ?",
            (category_id,),
        ).fetchone()
        return row["n"]

    # ------------------------------------------------------------------ #
    # Writes
    # ------------------------------------------------------------------ #
    def create(
        self,
        name: str,
        color: str,
        is_productive: bool,
        daily_target_minutes: int,
        sort_order: int = 0,
    ) -> int:
        """Insert a new category and return its new id."""
        cur = self.conn.execute(
            """
            INSERT INTO categories
                (name, color, is_productive, daily_target_minutes, sort_order)
            VALUES (?, ?, ?, ?, ?)
            """,
            (name.strip(), color, 1 if is_productive else 0,
             daily_target_minutes, sort_order),
        )
        self.conn.commit()
        return cur.lastrowid

    def update(self, category: Category) -> None:
        """Save all editable fields of an existing category."""
        self.conn.execute(
            """
            UPDATE categories
               SET name = ?,
                   color = ?,
                   is_productive = ?,
                   daily_target_minutes = ?,
                   sort_order = ?,
                   is_archived = ?,
                   updated_at = datetime('now')
             WHERE id = ?
            """,
            (
                category.name.strip(),
                category.color,
                1 if category.is_productive else 0,
                category.daily_target_minutes,
                category.sort_order,
                1 if category.is_archived else 0,
                category.id,
            ),
        )
        self.conn.commit()

    def set_archived(self, category_id: int, archived: bool) -> None:
        """Archive or un-archive a category (soft delete / restore)."""
        self.conn.execute(
            "UPDATE categories SET is_archived = ?, updated_at = datetime('now') WHERE id = ?",
            (1 if archived else 0, category_id),
        )
        self.conn.commit()

    def delete(self, category_id: int) -> None:
        """Hard-delete a category.

        Only safe when the category has no entries; the ON DELETE RESTRICT rule
        in the schema will raise an IntegrityError otherwise, which the service
        layer turns into a friendly "archive instead" message.
        """
        self.conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        self.conn.commit()
