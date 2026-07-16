from __future__ import annotations

import os
import tempfile
import unittest
from types import SimpleNamespace

import flet as ft

from app.services.context import AppContext
from mobile.screens import timer_screen


class _PageStub:
    def __init__(self) -> None:
        self.overlay = []
        self.views = []

    def update(self) -> None:
        pass

    def run_task(self, *args, **kwargs) -> None:
        pass

    def show_dialog(self, *args, **kwargs) -> None:
        pass

    def pop_dialog(self, *args, **kwargs) -> None:
        pass


def _walk(control):
    yield control
    for child in getattr(control, "controls", []):
        yield from _walk(child)
    content = getattr(control, "content", None)
    if content is not None:
        yield from _walk(content)


class TimerCelebrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.ctx = AppContext(os.path.join(self.temp.name, "test.db"))
        for category in self.ctx.category_service.list_categories():
            self.ctx.category_service.set_archived(category.id, True)
        ok, message, _ = self.ctx.category_service.create(
            "Daily check-in",
            "#10B981",
            False,
            0,
            tracking_mode="checkoff",
        )
        self.assertTrue(ok, message)

    def tearDown(self) -> None:
        self.ctx.close()
        self.temp.cleanup()

    def test_completion_shows_the_goal_video_once(self) -> None:
        page = _PageStub()
        screen = timer_screen.build(page, self.ctx)
        self.assertEqual(page.overlay, [])

        checkoff = next(control for control in _walk(screen) if isinstance(control, ft.Checkbox))
        checkoff.value = True
        checkoff.on_change(SimpleNamespace(control=checkoff))

        self.assertEqual(len(page.overlay), 1)
        celebration = page.overlay[0]
        self.assertIsInstance(celebration, ft.BottomSheet)
        self.assertTrue(celebration.fullscreen)

