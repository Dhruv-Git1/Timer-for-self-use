"""
A tiny publish/subscribe ("pub/sub") message bus.

The problem it solves: when you add, edit, or delete an entry, several parts of
the screen need to refresh — the dashboard totals, the calendar colors, the
graphs. Rather than wiring every screen directly to every other screen (which
gets tangled fast), each screen simply *subscribes* to an event, and the
services *publish* that event after they change data. Nobody needs to know who
is listening.

Think of it like a notice board: services pin up a note that says "the data
changed"; anyone who cares reads the board and reacts.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Any

# Event names used across the app. Using constants (instead of loose strings)
# means a typo becomes an import error instead of a silent no-op.
DATA_CHANGED = "data_changed"          # entries or categories were modified
THEME_CHANGED = "theme_changed"        # user toggled dark/light mode
TIMER_STATE_CHANGED = "timer_state_changed"  # the live timer started/stopped/switched


class EventBus:
    """Keeps lists of callback functions grouped by event name."""

    def __init__(self) -> None:
        # Maps an event name to the list of functions to call when it fires.
        self._subscribers: Dict[str, List[Callable[..., None]]] = {}

    def subscribe(self, event: str, callback: Callable[..., None]) -> None:
        """Register ``callback`` to run whenever ``event`` is published."""
        self._subscribers.setdefault(event, []).append(callback)

    def unsubscribe(self, event: str, callback: Callable[..., None]) -> None:
        """Stop calling ``callback`` for ``event`` (safe if not subscribed)."""
        if event in self._subscribers and callback in self._subscribers[event]:
            self._subscribers[event].remove(callback)

    def publish(self, event: str, **payload: Any) -> None:
        """Fire ``event``, calling every subscriber with the given payload.

        One misbehaving subscriber should not stop the others from updating, so
        each callback is wrapped in its own try/except. We deliberately print
        the problem rather than swallow it silently, so bugs stay visible during
        development without taking the whole app down.
        """
        for callback in list(self._subscribers.get(event, [])):
            try:
                callback(**payload)
            except Exception as exc:  # noqa: BLE001 - keep other listeners alive
                print(f"[EventBus] subscriber for '{event}' failed: {exc}")


# A single shared bus the whole app uses. Import this instance everywhere rather
# than creating new buses, so publishers and subscribers meet on common ground.
bus = EventBus()
