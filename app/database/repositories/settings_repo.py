"""Reads and writes for the ``app_meta`` key/value settings table."""

from __future__ import annotations

from typing import Optional

from app.database.repositories.base_repo import BaseRepository


class SettingsRepository(BaseRepository):
    """A thin wrapper over the app_meta table for storing small settings.

    Anything that is really just "one value the app should remember" — the
    chosen theme, when the last backup ran — lives here as a string keyed by a
    short name, instead of earning its own table.
    """

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Return the stored value for ``key``, or ``default`` if unset."""
        row = self.conn.execute(
            "SELECT value FROM app_meta WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default

    def set(self, key: str, value: str, *, commit: bool = True) -> None:
        """Store ``value`` under ``key`` (inserting or overwriting)."""
        self.conn.execute(
            "INSERT OR REPLACE INTO app_meta (key, value) VALUES (?, ?)",
            (key, value),
        )
        if commit:
            self.conn.commit()
