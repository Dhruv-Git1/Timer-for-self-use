"""Python side of the Android timer widget/alarm extension.

This module intentionally stays in the main app package.  Desktop tests can
import it without needing the Android extension wheel installed; the service is
only attached to an Android page by :mod:`mobile.app_shell`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import flet as ft

from app.services.timer_service import MODE_COUNTDOWN, TimerState
from app.utils import time_utils


@dataclass(frozen=True)
class AndroidTimerPayload:
    active: bool
    mode: str
    start_epoch_ms: int
    target_seconds: int
    category_label: str
    category_color: str
    token: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "active": self.active,
            "mode": self.mode,
            "start_epoch_ms": self.start_epoch_ms,
            "target_seconds": self.target_seconds,
            "category_label": self.category_label,
            "category_color": self.category_color,
            "token": self.token,
        }


@dataclass(frozen=True)
class AndroidTargetPayload:
    """Small native mirror of today's authoritative target score."""

    has_target: bool
    is_reached: bool
    completed_goals: int
    total_goals: int
    progress_percent: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "has_target": self.has_target,
            "is_reached": self.is_reached,
            "completed_goals": self.completed_goals,
            "total_goals": self.total_goals,
            "progress_percent": self.progress_percent,
        }


@dataclass(frozen=True)
class AndroidTaskReminderPayload:
    """A reminder specification persisted and scheduled by Android."""

    task_id: int
    title: str
    due_epoch_ms: int
    reminder_epoch_ms: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "due_epoch_ms": self.due_epoch_ms,
            "reminder_epoch_ms": self.reminder_epoch_ms,
        }


def state_payload(state: TimerState, category=None) -> AndroidTimerPayload:
    """Make the native mirror payload from the authoritative service state."""
    start_epoch_ms = 0
    if state.is_active and state.start_ts:
        start_epoch_ms = int(time_utils.parse_live_ts(state.start_ts).timestamp() * 1000)
    return AndroidTimerPayload(
        active=state.is_active,
        mode=state.mode,
        start_epoch_ms=start_epoch_ms,
        target_seconds=state.target_seconds if state.mode == MODE_COUNTDOWN else 0,
        category_label=getattr(category, "name", "") if category else "",
        category_color=getattr(category, "color", "#B91C1C") if category else "#B91C1C",
        token=state.token or "",
    )


def target_status_payload(score) -> AndroidTargetPayload:
    """Summarize all of today's configured targets for the target widget."""
    items = score.items
    total = len(items)
    completed = sum(item.actual >= item.target for item in items)
    average = (
        sum(min(100.0, item.actual / item.target * 100.0) for item in items) / total
        if total
        else 0.0
    )
    return AndroidTargetPayload(
        has_target=bool(total),
        is_reached=bool(total) and completed == total,
        completed_goals=completed,
        total_goals=total,
        progress_percent=round(average),
    )


def task_reminder_payload(task) -> AndroidTaskReminderPayload:
    """Convert a dated task with a reminder to the native bridge format."""
    reminder_at = task.reminder_at
    if not task.due_at or reminder_at is None or task.id is None:
        raise ValueError("Task must be saved and have a due date and reminder")
    return AndroidTaskReminderPayload(
        task_id=task.id,
        title=task.title,
        due_epoch_ms=int(time_utils.parse_ts(task.due_at).timestamp() * 1000),
        reminder_epoch_ms=int(reminder_at.timestamp() * 1000),
    )


@ft.control("AndroidTimerBridge")
class AndroidTimerBridge(ft.Service):
    """Methods implemented by ``timetracker_android_widget`` on Android."""

    async def request_permissions(self) -> Any:
        return await self._invoke_method("request_permissions")

    async def sync_state(self, payload: AndroidTimerPayload) -> Any:
        return await self._invoke_method("sync_state", payload.to_dict())

    async def sync_target_status(self, payload: AndroidTargetPayload) -> Any:
        return await self._invoke_method("sync_target_status", payload.to_dict())

    async def sync_task_reminders(
        self, payloads: list[AndroidTaskReminderPayload]
    ) -> Any:
        return await self._invoke_method(
            "sync_task_reminders", [payload.to_dict() for payload in payloads]
        )

    async def schedule_task_reminder(self, payload: AndroidTaskReminderPayload) -> Any:
        return await self._invoke_method("schedule_task_reminder", payload.to_dict())

    async def cancel_task_reminder(self, task_id: int) -> Any:
        return await self._invoke_method("cancel_task_reminder", {"task_id": task_id})

    async def notify_finished(self, token: str) -> Any:
        return await self._invoke_method("notify_finished", {"token": token})

    async def refresh_widgets(self) -> Any:
        return await self._invoke_method("refresh_widgets")
