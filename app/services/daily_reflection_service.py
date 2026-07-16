"""Business rules for the user's daily productivity reflection."""

from __future__ import annotations

from app.database.repositories.daily_reflection_repo import DailyReflectionRepository
from app.utils.event_bus import DATA_CHANGED, bus


class DailyReflectionService:
    """Keep daily reflections small, editable, and entirely local by default."""

    MAX_NOTES_CHARS = 4_000

    def __init__(self, reflections: DailyReflectionRepository) -> None:
        self.reflections = reflections

    def get_text(self, log_date: str) -> str:
        reflection = self.reflections.get(log_date)
        return reflection.notes if reflection else ""

    def list_by_date_range(self, start_date: str, end_date: str):
        return self.reflections.list_by_date_range(start_date, end_date)

    def save(self, log_date: str, notes: str) -> str:
        notes = notes.strip()
        if len(notes) > self.MAX_NOTES_CHARS:
            raise ValueError(f"Keep the reflection under {self.MAX_NOTES_CHARS:,} characters.")
        self.reflections.set(log_date, notes)
        bus.publish(DATA_CHANGED, date=log_date)
        return notes
