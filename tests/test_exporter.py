from __future__ import annotations

import csv
import os
import tempfile
import unittest
from types import SimpleNamespace

import flet as ft

import config
from app.services.context import AppContext
from mobile.screens import settings_screen


class ExportServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.original_export_dir = config.EXPORT_DIR
        config.EXPORT_DIR = os.path.join(self.temp.name, "exports")
        self.ctx = AppContext(os.path.join(self.temp.name, "test.db"))

    def tearDown(self) -> None:
        self.ctx.close()
        config.EXPORT_DIR = self.original_export_dir
        self.temp.cleanup()

    def test_csv_export_is_valid_even_without_entries(self) -> None:
        ok, path = self.ctx.export_service.to_csv()

        self.assertTrue(ok)
        self.assertTrue(os.path.isfile(path))
        with open(path, newline="", encoding="utf-8") as csv_file:
            reader = csv.DictReader(csv_file)
            self.assertEqual(
                reader.fieldnames,
                [
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
                ],
            )
            self.assertEqual(list(reader), [])

    def test_settings_attaches_one_export_file_picker_service(self) -> None:
        page = SimpleNamespace(services=[], update=lambda: None)

        settings_screen.build(page, self.ctx)
        settings_screen.build(page, self.ctx)

        pickers = [service for service in page.services if isinstance(service, ft.FilePicker)]
        self.assertEqual(len(pickers), 1)
        self.assertEqual(pickers[0].data, "timetracker-export-picker")
