"""Focused regression tests for Android multi-mode category tracking."""

from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest

import config
from app.database.connection import DatabaseManager
from app.models.category import TRACKING_COUNTER
from app.services.context import AppContext


class DefaultCategorySeedTests(unittest.TestCase):
    def test_new_database_seeds_only_the_three_requested_categories(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            ctx = AppContext(os.path.join(folder, "fresh.db"))
            try:
                self.assertEqual(
                    [category.name for category in ctx.category_service.list_categories()],
                    ["Study", "Writing", "Coding"],
                )
            finally:
                ctx.close()


class MigrationTests(unittest.TestCase):
    def test_v1_database_is_upgraded_without_losing_categories(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            db_path = os.path.join(folder, "legacy.db")
            conn = sqlite3.connect(db_path)
            conn.executescript(
                """
                CREATE TABLE categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    color TEXT NOT NULL DEFAULT '#3B82F6',
                    is_productive INTEGER NOT NULL DEFAULT 1,
                    daily_target_minutes INTEGER NOT NULL DEFAULT 0,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    is_archived INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
                CREATE TABLE app_meta (key TEXT PRIMARY KEY, value TEXT);
                INSERT INTO categories
                    (name, color, is_productive, daily_target_minutes, sort_order)
                VALUES ('Legacy Study', '#123456', 1, 90, 0);
                INSERT INTO app_meta (key, value) VALUES ('first_run', 'done');
                INSERT INTO app_meta (key, value) VALUES ('schema_version', '1');
                """
            )
            conn.commit()
            conn.close()

            db = DatabaseManager(db_path)
            db.initialize()
            row = db.conn.execute(
                "SELECT * FROM categories WHERE name = 'Legacy Study'"
            ).fetchone()
            version = db.conn.execute(
                "SELECT value FROM app_meta WHERE key = 'schema_version'"
            ).fetchone()["value"]
            table = db.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='daily_progress'"
            ).fetchone()
            reflections = db.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='daily_reflections'"
            ).fetchone()
            goals = db.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='goals'"
            ).fetchone()

            self.assertEqual(row["daily_target_minutes"], 90)
            self.assertEqual(row["tracking_mode"], "timer")
            self.assertEqual(row["daily_target_count"], 1)
            self.assertEqual(row["include_in_daily_score"], 1)
            self.assertEqual(version, config.SCHEMA_VERSION)
            self.assertIsNotNone(table)
            self.assertIsNotNone(reflections)
            self.assertIsNotNone(goals)
            db.close()


class MultiModeServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.ctx = AppContext(os.path.join(self.temp.name, "test.db"))
        for category in self.ctx.category_service.list_categories():
            self.ctx.category_service.set_archived(category.id, True)

    def tearDown(self) -> None:
        self.ctx.close()
        self.temp.cleanup()

    def _create_checkoff(self, name: str = "Eat fruit") -> int:
        ok, message, category_id = self.ctx.category_service.create(
            name,
            "#10B981",
            False,
            0,
            tracking_mode="checkoff",
            include_in_daily_score=True,
        )
        self.assertTrue(ok, message)
        return category_id

    def _create_counter(self, name: str = "Drink water") -> int:
        ok, message, category_id = self.ctx.category_service.create(
            name,
            "#3B82F6",
            False,
            0,
            tracking_mode="counter",
            target_count=10,
            unit_label="glasses",
            include_in_daily_score=True,
        )
        self.assertTrue(ok, message)
        return category_id

    def test_checkoff_and_counter_are_date_keyed_and_non_negative(self) -> None:
        checkoff_id = self._create_checkoff()
        counter_id = self._create_counter()
        first_day = "2026-07-15"
        second_day = "2026-07-16"

        self.assertEqual(self.ctx.daily_progress_service.get(checkoff_id, first_day), 0)
        self.assertEqual(self.ctx.daily_progress_service.toggle(checkoff_id, first_day), 1)
        self.assertEqual(self.ctx.daily_progress_service.toggle(checkoff_id, first_day), 0)
        self.assertEqual(self.ctx.daily_progress_service.get(checkoff_id, second_day), 0)

        self.assertEqual(self.ctx.daily_progress_service.increment(counter_id, first_day, 5), 5)
        self.assertEqual(self.ctx.daily_progress_service.increment(counter_id, first_day, -9), 0)
        self.assertEqual(self.ctx.daily_progress_service.set_amount(counter_id, first_day, 12), 12)
        self.assertEqual(self.ctx.daily_progress_service.get(counter_id, second_day), 0)
        with self.assertRaises(ValueError):
            self.ctx.daily_progress_service.set_amount(counter_id, first_day, -1)

    def test_today_score_is_equal_average_and_honors_opt_out(self) -> None:
        date = "2026-07-15"
        ok, message, timer_id = self.ctx.category_service.create(
            "Focused work", "#EF4444", True, 120,
            tracking_mode="timer", include_in_daily_score=True,
        )
        self.assertTrue(ok, message)
        checkoff_id = self._create_checkoff()
        counter_id = self._create_counter()

        ok, message, _ = self.ctx.entry_service.add_entry(
            timer_id, date, "09:00", "10:00"
        )
        self.assertTrue(ok, message)
        self.ctx.daily_progress_service.toggle(checkoff_id, date)
        self.ctx.daily_progress_service.set_amount(counter_id, date, 5)

        score = self.ctx.daily_progress_service.score(date)
        self.assertEqual(len(score.scored_items), 3)
        self.assertAlmostEqual(score.average_pct, (50 + 100 + 50) / 3)

        counter = self.ctx.category_service.get(counter_id)
        counter.include_in_daily_score = False
        ok, message, _ = self.ctx.category_service.update(counter)
        self.assertTrue(ok, message)
        score = self.ctx.daily_progress_service.score(date)
        self.assertEqual(len(score.scored_items), 2)
        self.assertAlmostEqual(score.average_pct, 75.0)

    def test_today_score_uses_category_weights(self) -> None:
        date = "2026-07-15"
        checkoff_id = self._create_checkoff()
        counter_id = self._create_counter()
        self.ctx.daily_progress_service.toggle(checkoff_id, date)
        self.ctx.daily_progress_service.set_amount(counter_id, date, 5)

        counter = self.ctx.category_service.get(counter_id)
        counter.score_weight = 3
        ok, message, _ = self.ctx.category_service.update(counter)
        self.assertTrue(ok, message)

        score = self.ctx.daily_progress_service.score(date)
        self.assertAlmostEqual(score.average_pct, (100 + 50 * 3) / 4)

    def test_history_locks_mode_and_blocks_deletion(self) -> None:
        category_id = self._create_checkoff()
        self.ctx.daily_progress_service.toggle(category_id, "2026-07-15")

        category = self.ctx.category_service.get(category_id)
        category.tracking_mode = TRACKING_COUNTER
        category.daily_target_count = 5
        ok, message, _ = self.ctx.category_service.update(category)
        self.assertFalse(ok)
        self.assertIn("cannot change", message)

        ok, message, _ = self.ctx.category_service.delete(category_id)
        self.assertFalse(ok)
        self.assertIn("Archive", message)
        ok, message, _ = self.ctx.category_service.set_archived(category_id, True)
        self.assertTrue(ok, message)

    def test_empty_category_deletes_successfully(self) -> None:
        category_id = self._create_checkoff("Temporary task")

        ok, message, deleted_id = self.ctx.category_service.delete(category_id)

        self.assertTrue(ok, message)
        self.assertEqual(deleted_id, category_id)
        self.assertIsNone(self.ctx.category_service.get(category_id))

    def test_time_entry_history_requires_archiving(self) -> None:
        ok, message, category_id = self.ctx.category_service.create(
            "Logged work", "#EF4444", True, 60
        )
        self.assertTrue(ok, message)
        ok, message, _ = self.ctx.entry_service.add_entry(
            category_id, "2026-07-15", "09:00", "10:00"
        )
        self.assertTrue(ok, message)

        ok, message, _ = self.ctx.category_service.delete(category_id)

        self.assertFalse(ok)
        self.assertIn("Archive", message)
        self.assertIsNotNone(self.ctx.category_service.get(category_id))

    def test_daily_progress_history_requires_archiving(self) -> None:
        category_id = self._create_counter("Progress task")
        self.ctx.daily_progress_service.set_amount(category_id, "2026-07-15", 3)

        ok, message, _ = self.ctx.category_service.delete(category_id)

        self.assertFalse(ok)
        self.assertIn("progress", message)
        self.assertIn("Archive", message)

    def test_running_timer_category_cannot_be_deleted(self) -> None:
        ok, message, category_id = self.ctx.category_service.create(
            "Live timer", "#3B82F6", True, 60
        )
        self.assertTrue(ok, message)
        self.ctx.timer_service.start(category_id)
        try:
            ok, message, _ = self.ctx.category_service.delete(category_id)
        finally:
            self.ctx.timer_service.discard()

        self.assertFalse(ok)
        self.assertIn("running timer", message)
        self.assertIsNotNone(self.ctx.category_service.get(category_id))

    def test_time_entries_reject_non_timer_categories(self) -> None:
        counter_id = self._create_counter()
        ok, message, entry_id = self.ctx.entry_service.add_entry(
            counter_id, "2026-07-15", "09:00", "10:00"
        )
        self.assertFalse(ok)
        self.assertIsNone(entry_id)
        self.assertIn("Timer categories", message)


if __name__ == "__main__":
    unittest.main()
