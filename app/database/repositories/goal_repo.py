"""Reads and writes for longer-horizon goals."""

from __future__ import annotations

from typing import Optional

from app.database.repositories.base_repo import BaseRepository
from app.models.goal import Goal, GoalRoutine, GoalTask


class GoalRepository(BaseRepository):
    """Persist goal definitions; progress remains derived from tracked data."""

    def list_all(self, include_archived: bool = False) -> list[Goal]:
        sql = "SELECT * FROM goals"
        if not include_archived:
            sql += " WHERE is_archived = 0"
        sql += " ORDER BY is_archived, start_date, id"
        rows = self.conn.execute(sql).fetchall()
        return [Goal.from_row(row) for row in rows]

    def get(self, goal_id: int) -> Optional[Goal]:
        row = self.conn.execute("SELECT * FROM goals WHERE id = ?", (goal_id,)).fetchone()
        return Goal.from_row(row) if row else None

    def create(
        self,
        title: str,
        category_id: int,
        target_value: int,
        period: str,
        start_date: str,
        end_date: str | None,
        interval_count: int | None = None,
        interval_unit: str | None = None,
    ) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO goals (
                title, category_id, target_value, period, start_date, end_date,
                interval_count, interval_unit
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                title.strip(), category_id, target_value, period, start_date,
                end_date, interval_count, interval_unit,
            ),
        )
        self.conn.commit()
        return cur.lastrowid

    def update(self, goal: Goal) -> None:
        self.conn.execute(
            """
            UPDATE goals
               SET title = ?, category_id = ?, target_value = ?, period = ?,
                   start_date = ?, end_date = ?, interval_count = ?,
                   interval_unit = ?, is_archived = ?,
                   updated_at = datetime('now')
             WHERE id = ?
            """,
            (
                goal.title.strip(), goal.category_id, goal.target_value, goal.period,
                goal.start_date, goal.end_date, goal.interval_count,
                goal.interval_unit, 1 if goal.is_archived else 0, goal.id,
            ),
        )
        self.conn.commit()

    def delete(self, goal_id: int) -> None:
        self.conn.execute("DELETE FROM goals WHERE id = ?", (goal_id,))
        self.conn.commit()

    # ------------------------------------------------------------------
    # Independent one-off tasks
    # ------------------------------------------------------------------
    def list_tasks(self) -> list[GoalTask]:
        rows = self.conn.execute(
            """
            SELECT * FROM goal_tasks
            ORDER BY
                CASE WHEN completed_at IS NULL THEN 0 ELSE 1 END,
                CASE WHEN due_at IS NULL THEN 1 ELSE 0 END,
                due_at,
                id
            """
        ).fetchall()
        return [GoalTask.from_row(row) for row in rows]

    def get_task(self, task_id: int) -> Optional[GoalTask]:
        row = self.conn.execute(
            "SELECT * FROM goal_tasks WHERE id = ?", (task_id,)
        ).fetchone()
        return GoalTask.from_row(row) if row else None

    def create_task(
        self,
        title: str,
        due_at: str | None,
        reminder_offset_minutes: int | None,
    ) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO goal_tasks (title, due_at, reminder_offset_minutes)
            VALUES (?, ?, ?)
            """,
            (title.strip(), due_at, reminder_offset_minutes),
        )
        self.conn.commit()
        return cur.lastrowid

    def update_task(self, task: GoalTask) -> None:
        self.conn.execute(
            """
            UPDATE goal_tasks
               SET title = ?, due_at = ?, reminder_offset_minutes = ?,
                   completed_at = ?, updated_at = datetime('now')
             WHERE id = ?
            """,
            (
                task.title.strip(), task.due_at, task.reminder_offset_minutes,
                task.completed_at, task.id,
            ),
        )
        self.conn.commit()

    def delete_task(self, task_id: int) -> None:
        self.conn.execute("DELETE FROM goal_tasks WHERE id = ?", (task_id,))
        self.conn.commit()

    # ------------------------------------------------------------------
    # Permanent routines and independent check-ins
    # ------------------------------------------------------------------
    def list_routines(self, include_archived: bool = False) -> list[GoalRoutine]:
        sql = "SELECT * FROM goal_routines"
        if not include_archived:
            sql += " WHERE is_archived = 0"
        sql += " ORDER BY is_archived, category_id IS NULL, category_id, id"
        rows = self.conn.execute(sql).fetchall()
        return [GoalRoutine.from_row(row) for row in rows]

    def get_routine(self, routine_id: int) -> Optional[GoalRoutine]:
        row = self.conn.execute(
            "SELECT * FROM goal_routines WHERE id = ?", (routine_id,)
        ).fetchone()
        return GoalRoutine.from_row(row) if row else None

    def create_routine(
        self,
        title: str,
        category_id: int | None,
        weekdays_mask: int,
        start_date: str,
    ) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO goal_routines (title, category_id, weekdays_mask, start_date)
            VALUES (?, ?, ?, ?)
            """,
            (title.strip(), category_id, weekdays_mask, start_date),
        )
        self.conn.commit()
        return cur.lastrowid

    def update_routine(self, routine: GoalRoutine) -> None:
        self.conn.execute(
            """
            UPDATE goal_routines
               SET title = ?, category_id = ?, weekdays_mask = ?, start_date = ?,
                   is_archived = ?, updated_at = datetime('now')
             WHERE id = ?
            """,
            (
                routine.title.strip(), routine.category_id, routine.weekdays_mask,
                routine.start_date, 1 if routine.is_archived else 0, routine.id,
            ),
        )
        self.conn.commit()

    def delete_routine(self, routine_id: int) -> None:
        self.conn.execute("DELETE FROM goal_routines WHERE id = ?", (routine_id,))
        self.conn.commit()

    def routine_checkins(
        self, routine_id: int, start_date: str | None = None, end_date: str | None = None
    ) -> set[str]:
        sql = "SELECT log_date FROM goal_routine_checkins WHERE routine_id = ?"
        params: list[object] = [routine_id]
        if start_date is not None:
            sql += " AND log_date >= ?"
            params.append(start_date)
        if end_date is not None:
            sql += " AND log_date <= ?"
            params.append(end_date)
        rows = self.conn.execute(sql, tuple(params)).fetchall()
        return {row["log_date"] for row in rows}

    def set_routine_checkin(self, routine_id: int, log_date: str, completed: bool) -> None:
        if completed:
            self.conn.execute(
                """
                INSERT INTO goal_routine_checkins (routine_id, log_date)
                VALUES (?, ?)
                ON CONFLICT(routine_id, log_date) DO UPDATE SET
                    completed_at = datetime('now')
                """,
                (routine_id, log_date),
            )
        else:
            self.conn.execute(
                "DELETE FROM goal_routine_checkins WHERE routine_id = ? AND log_date = ?",
                (routine_id, log_date),
            )
        self.conn.commit()
