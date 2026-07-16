from __future__ import annotations

import os
import tempfile
import unittest
from types import SimpleNamespace

import flet as ft
import flet_video as ftv

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
        video = next(control for control in _walk(celebration) if isinstance(control, ftv.Video))
        self.assertTrue(video.autoplay)
        self.assertTrue(video.playlist[0].resource.startswith("file:///"))
        self.assertTrue(video.playlist[0].resource.endswith("goal-complete.mp4"))
        self.assertEqual(video.configuration.output_driver, "mediacodec_embed")
        self.assertEqual(video.configuration.hardware_decoding_api, "mediacodec")
        self.assertEqual(
            self.ctx.get_setting(timer_screen.GOAL_CELEBRATION_SETTING),
            timer_screen.time_utils.today_str(),
        )

        # Completing the same goals again today must not retrigger the clip.
        checkoff.value = False
        checkoff.on_change(SimpleNamespace(control=checkoff))
        checkoff.value = True
        checkoff.on_change(SimpleNamespace(control=checkoff))
        self.assertEqual(len(page.overlay), 1)

    def test_completion_still_celebrates_when_a_goal_is_excluded_from_score(self) -> None:
        category = next(iter(self.ctx.category_service.list_categories()))
        category.include_in_daily_score = False
        ok, message, _ = self.ctx.category_service.update(category)
        self.assertTrue(ok, message)

        page = _PageStub()
        screen = timer_screen.build(page, self.ctx)
        checkoff = next(control for control in _walk(screen) if isinstance(control, ft.Checkbox))
        checkoff.value = True
        checkoff.on_change(SimpleNamespace(control=checkoff))

        self.assertEqual(len(page.overlay), 1)

    def test_celebration_transition_and_reset_helper_are_testable(self) -> None:
        today = "2026-07-16"
        self.assertFalse(
            timer_screen.should_show_goal_celebration(
                initialized=False,
                was_complete=False,
                is_complete=True,
                last_celebration_date="",
                today=today,
            )
        )
        self.assertTrue(
            timer_screen.should_show_goal_celebration(
                initialized=True,
                was_complete=False,
                is_complete=True,
                last_celebration_date="",
                today=today,
            )
        )
        self.assertFalse(
            timer_screen.should_show_goal_celebration(
                initialized=True,
                was_complete=False,
                is_complete=True,
                last_celebration_date=today,
                today=today,
            )
        )

        self.ctx.set_setting(timer_screen.GOAL_CELEBRATION_SETTING, today)
        timer_screen.reset_goal_celebration_state(self.ctx)
        self.assertEqual(self.ctx.get_setting(timer_screen.GOAL_CELEBRATION_SETTING), "")

    def test_video_completion_only_accepts_a_true_completed_state(self):
        self.assertFalse(
            timer_screen.is_video_completion_event(SimpleNamespace(data="false"))
        )
        self.assertFalse(
            timer_screen.is_video_completion_event(SimpleNamespace(data=""))
        )
        self.assertTrue(
            timer_screen.is_video_completion_event(SimpleNamespace(data="true"))
        )

    def test_video_resource_is_a_readable_file_uri(self):
        resource = timer_screen.goal_completion_video_resource()
        self.assertTrue(resource.startswith("file:///"))
        self.assertTrue(resource.endswith("goal-complete.mp4"))
