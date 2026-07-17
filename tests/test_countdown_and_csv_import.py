from __future__ import annotations

import csv
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import config
from app.services.context import AppContext
from app.services.timer_service import (
    MAX_COUNTDOWN_SECONDS,
    MIN_COUNTDOWN_SECONDS,
    MODE_COUNTDOWN,
    MODE_STOPWATCH,
    TimerService,
)
from mobile.app_shell import timer_mode_from_route
from mobile.services.android_timer_bridge import target_status_payload


class MutableClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def __call__(self) -> datetime:
        return self.value

    def advance(self, seconds: int) -> None:
        self.value += timedelta(seconds=seconds)


class CountdownTimerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.ctx = AppContext(os.path.join(self.temp.name, "timer.db"))
        self.clock = MutableClock(datetime(2026, 7, 16, 9, 0, 30))
        self.ctx.timer_service = TimerService(
            self.ctx.settings_repo, self.ctx.entry_service, now_provider=self.clock
        )
        categories = self.ctx.category_service.list_categories()
        self.category_id = categories[0].id
        self.second_category_id = categories[1].id

    def tearDown(self) -> None:
        self.ctx.close()
        self.temp.cleanup()

    def test_legacy_active_state_loads_as_stopwatch(self) -> None:
        self.ctx.set_setting("timer_active", "1")
        self.ctx.set_setting("timer_category_id", str(self.category_id))
        self.ctx.set_setting("timer_start_ts", "2026-07-16 09:00:00")

        state = self.ctx.timer_service.current_state()

        self.assertTrue(state.is_active)
        self.assertEqual(state.mode, MODE_STOPWATCH)
        self.assertEqual(state.elapsed_seconds, 30)

    def test_countdown_remaining_and_restart_recovery(self) -> None:
        self.ctx.timer_service.start(self.category_id, MODE_COUNTDOWN, 25 * 60)
        self.clock.advance(7 * 60 + 12)
        self.assertEqual(self.ctx.timer_service.current_state().remaining_seconds, 17 * 60 + 48)

        recovered = TimerService(
            self.ctx.settings_repo, self.ctx.entry_service, now_provider=self.clock
        )
        self.assertEqual(recovered.current_state().remaining_seconds, 17 * 60 + 48)

    def test_natural_completion_records_intended_duration_once(self) -> None:
        self.ctx.timer_service.start(self.category_id, MODE_COUNTDOWN, 25 * 60)
        self.clock.advance(25 * 60 + 4)

        first = self.ctx.timer_service.reconcile_expired()
        second = self.ctx.timer_service.reconcile_expired()

        self.assertTrue(first[0])
        self.assertFalse(second[0])
        entries = self.ctx.entry_repo.list_all()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].duration_minutes, 25)
        self.assertFalse(self.ctx.timer_service.current_state().is_active)

    def test_early_stop_logs_actual_elapsed_and_discard_logs_nothing(self) -> None:
        self.ctx.timer_service.start(self.category_id, MODE_COUNTDOWN, 60 * 60)
        self.clock.advance(5 * 60 + 45)
        ok, message, _ = self.ctx.timer_service.stop()
        self.assertTrue(ok, message)
        self.assertEqual(self.ctx.entry_repo.list_all()[0].duration_minutes, 5)

        self.ctx.timer_service.start(self.category_id, MODE_COUNTDOWN, 60 * 60)
        self.ctx.timer_service.discard()
        self.assertEqual(len(self.ctx.entry_repo.list_all()), 1)

    def test_duration_bounds_invalid_calls_and_sub_minute_stop(self) -> None:
        self.ctx.timer_service.start(self.category_id, MODE_COUNTDOWN, MIN_COUNTDOWN_SECONDS)
        self.ctx.timer_service.discard()
        self.ctx.timer_service.start(self.category_id, MODE_COUNTDOWN, MAX_COUNTDOWN_SECONDS)
        self.ctx.timer_service.discard()
        for invalid in (0, 59, MAX_COUNTDOWN_SECONDS + 1, "60"):
            with self.assertRaises(ValueError):
                self.ctx.timer_service.start(self.category_id, MODE_COUNTDOWN, invalid)  # type: ignore[arg-type]
            self.assertFalse(self.ctx.timer_service.current_state().is_active)

        self.ctx.timer_service.start(self.category_id)
        self.clock.advance(45)
        ok, message, _ = self.ctx.timer_service.stop()
        self.assertFalse(ok)
        self.assertIn("short", message)
        self.assertFalse(self.ctx.timer_service.current_state().is_active)

    def test_stopwatch_switching_is_preserved_and_countdown_switching_is_blocked(self) -> None:
        self.ctx.timer_service.start(self.category_id)
        self.clock.advance(60)
        self.ctx.timer_service.start(self.second_category_id)
        self.assertEqual(self.ctx.timer_service.current_state().category_id, self.second_category_id)
        self.assertEqual(len(self.ctx.entry_repo.list_all()), 1)
        self.ctx.timer_service.discard()

        self.ctx.timer_service.start(self.category_id, MODE_COUNTDOWN, 25 * 60)
        with self.assertRaises(ValueError):
            self.ctx.timer_service.start(self.second_category_id, MODE_COUNTDOWN, 25 * 60)


class CsvImportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.ctx = AppContext(os.path.join(self.temp.name, "import.db"))
        self.category_id = self.ctx.category_service.list_categories()[0].id

    def tearDown(self) -> None:
        self.ctx.close()
        self.temp.cleanup()

    def _csv(self, rows: list[dict], headers: list[str] | None = None, bom: bool = False) -> Path:
        path = Path(self.temp.name) / "selected.csv"
        fields = headers or [
            "date", "start_time", "end_time", "duration_minutes", "category", "productive", "notes"
        ]
        with path.open("w", newline="", encoding="utf-8-sig" if bom else "utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        return path

    @staticmethod
    def _row(**values) -> dict:
        row = {
            "date": "2026-07-15",
            "start_time": "09:00",
            "end_time": "10:00",
            "duration_minutes": "60",
            "category": "Imported focus",
            "productive": "yes",
            "notes": "careful notes",
        }
        row.update(values)
        return row

    def test_import_export_reimport_and_case_insensitive_reuse(self) -> None:
        source = AppContext(os.path.join(self.temp.name, "source.db"))
        original_export_dir = config.EXPORT_DIR
        config.EXPORT_DIR = os.path.join(self.temp.name, "source-exports")
        try:
            category = source.category_service.list_categories()[0]
            ok, message, _ = source.entry_service.add_entry(category.id, "2026-07-15", "09:00", "10:00", "note")
            self.assertTrue(ok, message)
            _, exported = source.export_service.to_csv()
            preview = self.ctx.csv_import_service.preview(exported)
            result = self.ctx.csv_import_service.import_preview(preview)
            self.assertEqual(result.imported_entries, 1)
            self.assertEqual(self.ctx.csv_import_service.import_preview(self.ctx.csv_import_service.preview(exported)).imported_entries, 0)
        finally:
            source.close()
            config.EXPORT_DIR = original_export_dir

        path = self._csv([self._row(category="study", notes="case reuse")])
        result = self.ctx.csv_import_service.import_preview(self.ctx.csv_import_service.preview(path))
        self.assertEqual(result.created_categories, 0)
        self.assertEqual(len([c for c in self.ctx.category_repo.list_all(True) if c.name.casefold() == "study"]), 1)

    def test_archived_category_conflicts_overnight_bom_and_reordered_headers(self) -> None:
        archived = self.ctx.category_service.list_categories()[1]
        self.ctx.category_service.set_archived(archived.id, True)
        path = self._csv(
            [self._row(
                category=archived.name.lower(), productive="false", start_time="23:00", end_time="01:00",
                duration_minutes="120", notes="  overnight note  ",
            )],
            headers=["notes", "productive", "category", "duration_minutes", "end_time", "date", "start_time"],
            bom=True,
        )
        preview = self.ctx.csv_import_service.preview(path)
        self.assertTrue(preview.import_allowed)
        self.assertEqual(len(preview.existing_category_conflicts), 1)
        result = self.ctx.csv_import_service.import_preview(preview)
        self.assertEqual(result.created_categories, 0)
        self.assertTrue(self.ctx.category_repo.get(archived.id).is_archived)
        entry = self.ctx.entry_repo.list_all()[0]
        self.assertTrue(entry.crosses_midnight)
        self.assertEqual(entry.notes, "overnight note")

    def test_rejects_ambiguous_missing_category_invalid_rows_duplicates_and_changed_file(self) -> None:
        path = self._csv([self._row(productive="true"), self._row(productive="false", start_time="10:00", end_time="11:00")])
        preview = self.ctx.csv_import_service.preview(path)
        self.assertFalse(preview.import_allowed)
        self.assertIn("conflicting", preview.issues[0].message)

        bad = self._csv([
            self._row(),
            self._row(),
            self._row(start_time="10:00", end_time="11:00", duration_minutes="59"),
        ])
        bad_preview = self.ctx.csv_import_service.preview(bad)
        self.assertFalse(bad_preview.import_allowed)
        self.assertGreaterEqual(bad_preview.duplicate_rows, 1)

        valid = self._csv([self._row()])
        valid_preview = self.ctx.csv_import_service.preview(valid)
        valid.write_text("date,start_time\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "changed"):
            self.ctx.csv_import_service.import_preview(valid_preview)

    def test_empty_missing_columns_and_rollback(self) -> None:
        empty = self._csv([])
        empty_preview = self.ctx.csv_import_service.preview(empty)
        self.assertFalse(empty_preview.import_allowed)
        self.assertFalse(empty_preview.issues)

        missing = Path(self.temp.name) / "missing.csv"
        missing.write_text("date,start_time\n2026-07-15,09:00\n", encoding="utf-8")
        self.assertFalse(self.ctx.csv_import_service.preview(missing).import_allowed)

        path = self._csv([self._row(category="Rollback category")])
        preview = self.ctx.csv_import_service.preview(path)
        original_create = self.ctx.entry_repo.create
        self.ctx.entry_repo.create = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("forced"))
        try:
            with self.assertRaisesRegex(RuntimeError, "forced"):
                self.ctx.csv_import_service.import_preview(preview)
        finally:
            self.ctx.entry_repo.create = original_create
        self.assertIsNone(next((c for c in self.ctx.category_repo.list_all(True) if c.name == "Rollback category"), None))


class TimerRouteAndSourceTests(unittest.TestCase):
    def test_deep_link_route_mapping_and_timer_ui_controls(self) -> None:
        self.assertEqual(timer_mode_from_route("timetracker://timer/countdown"), MODE_COUNTDOWN)
        self.assertEqual(timer_mode_from_route("/timer/stopwatch"), MODE_STOPWATCH)
        self.assertEqual(timer_mode_from_route("/more/settings"), None)
        source = Path("mobile/screens/timer_screen.py").read_text(encoding="utf-8")
        self.assertIn("STOPWATCH", source)
        self.assertIn("COUNTDOWN", source)
        self.assertIn("25m", source)
        self.assertIn("Custom countdown", source)
        self.assertNotIn("Discipline", source)
        self.assertIn("hero_banner(", source)
        self.assertIn('kicker="Timer / Live Session"', source)
        self.assertIn('headline="REVENGE"', source)

    def test_target_widget_payload_and_native_widgets_are_distinct(self) -> None:
        score = SimpleNamespace(
            items=[
                SimpleNamespace(actual=60, target=60),
                SimpleNamespace(actual=15, target=30),
            ],
        )
        payload = target_status_payload(score)
        self.assertEqual(payload.completed_goals, 1)
        self.assertEqual(payload.total_goals, 2)
        self.assertFalse(payload.is_reached)
        self.assertEqual(payload.progress_percent, 75)

        extension = Path("extensions/timetracker_android_widget/flutter/timetracker_android_widget/android")
        manifest = (extension / "src/main/AndroidManifest.xml").read_text(encoding="utf-8")
        timer_provider = (extension / "src/main/kotlin/com/timetracker/widget/TimerWidgetProvider.kt").read_text(encoding="utf-8")
        target_provider = (extension / "src/main/kotlin/com/timetracker/widget/TargetWidgetProvider.kt").read_text(encoding="utf-8")
        self.assertIn("TimerWidgetProvider", manifest)
        self.assertIn("TargetWidgetProvider", manifest)
        self.assertIn("TARGET REACHED", target_provider)
        self.assertNotIn("setOnClickPendingIntent", timer_provider)
        dart_bridge = (extension.parent / "lib/src/timer_bridge_service.dart").read_text(encoding="utf-8")
        self.assertIn("sync_target_status", dart_bridge)


if __name__ == "__main__":
    unittest.main()
