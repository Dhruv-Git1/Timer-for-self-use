from __future__ import annotations

import os
import tempfile
import unittest

import flet as ft

from app.services.context import AppContext
from mobile.screens import timer_screen


class _FocusPage:
    def __init__(self) -> None:
        self.services: list[ft.Service] = []
        self.dialogs: list[ft.BottomSheet] = []

    def update(self) -> None:
        pass

    def run_task(self, *_args, **_kwargs) -> None:
        pass

    def show_dialog(self, dialog: ft.BottomSheet) -> None:
        dialog.open = True
        self.dialogs.append(dialog)

    def pop_dialog(self) -> None:
        if self.dialogs:
            dialog = self.dialogs.pop()
            dialog.open = False
            if dialog.on_dismiss is not None:
                dialog.on_dismiss(None)


def _walk(control):
    yield control
    for child in getattr(control, "controls", []):
        yield from _walk(child)
    content = getattr(control, "content", None)
    if content is not None:
        yield from _walk(content)


def _has_text(control, value: str) -> bool:
    return any(getattr(child, "value", None) == value for child in _walk(control))


class FocusModeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.ctx = AppContext(os.path.join(self.temp.name, "focus.db"))

    def tearDown(self) -> None:
        self.ctx.close()
        self.temp.cleanup()

    def test_start_opens_a_clock_only_fullscreen_focus_mode(self) -> None:
        page = _FocusPage()
        screen = timer_screen.build(page, self.ctx)
        start = next(
            control
            for control in _walk(screen)
            if callable(getattr(control, "on_click", None)) and _has_text(control, "START")
        )

        start.on_click(None)

        self.assertEqual(len(page.dialogs), 1)
        focus = page.dialogs[0]
        self.assertIsInstance(focus, ft.BottomSheet)
        self.assertTrue(focus.fullscreen)
        self.assertFalse(focus.dismissible)
        self.assertFalse(focus.draggable)
        self.assertTrue(any(isinstance(service, ft.Wakelock) for service in page.services))
        clocks = [
            control for control in _walk(focus)
            if isinstance(control, ft.Text) and control.size == timer_screen._FOCUS_CLOCK_SIZE
        ]
        self.assertEqual(len(clocks), 1)
        self.assertEqual(clocks[0].value, "0:00:00")
        self.assertEqual(
            len(
                [
                    control for control in _walk(focus)
                    if isinstance(control, ft.IconButton)
                    and control.tooltip == "Exit focus mode"
                ]
            ),
            1,
        )


if __name__ == "__main__":
    unittest.main()
