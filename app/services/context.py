"""
The application wiring.

``AppContext`` builds the whole object graph once — the database manager, every
repository, and every service — and hands them out through simple attributes.
Creating one ``AppContext`` at startup and passing it around means no other part
of the code has to know how the pieces are constructed or connected.
"""

from __future__ import annotations

from typing import Optional

import config
from app.database.connection import DatabaseManager
from app.database.repositories.category_repo import CategoryRepository
from app.database.repositories.entry_repo import EntryRepository
from app.database.repositories.settings_repo import SettingsRepository
from app.services.backup_service import BackupService
from app.services.calendar_service import CalendarService
from app.services.category_service import CategoryService
from app.services.dashboard_service import DashboardService
from app.services.entry_service import EntryService
from app.services.search_service import SearchService
from app.services.stats_service import StatsService
from app.services.streak_service import StreakService
from app.services.timer_service import TimerService


class AppContext:
    """Owns and connects every long-lived object in the application."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        # Make sure runtime folders exist, then open and initialise the database.
        config.ensure_directories()
        self.db = DatabaseManager(db_path)
        self.db.initialize()

        # Repositories (the only classes that run SQL).
        self.category_repo = CategoryRepository(self.db)
        self.entry_repo = EntryRepository(self.db)
        self.settings_repo = SettingsRepository(self.db)

        # Services (all business logic). Order matters where one depends on
        # another: the streak service is built first because the dashboard and
        # statistics services use it.
        self.streak_service = StreakService(self.category_repo, self.entry_repo)
        self.category_service = CategoryService(self.category_repo)
        self.entry_service = EntryService(self.entry_repo)
        self.timer_service = TimerService(self.settings_repo, self.entry_service)
        self.dashboard_service = DashboardService(
            self.category_repo, self.entry_repo, self.streak_service
        )
        self.stats_service = StatsService(
            self.category_repo, self.entry_repo, self.streak_service
        )
        self.calendar_service = CalendarService(self.category_repo, self.entry_repo)
        self.search_service = SearchService(self.entry_repo)
        self.backup_service = BackupService(self.db, self.settings_repo)
        # Built lazily (see the export_service property below) — it pulls in
        # pandas, which desktop has but a packaged mobile build may not.
        self._export_service = None

    @property
    def export_service(self):
        if self._export_service is None:
            from app.export.exporter import ExportService
            self._export_service = ExportService(self.entry_repo, self.category_repo)
        return self._export_service

    # ------------------------------------------------------------------ #
    # Small convenience pass-throughs for settings
    # ------------------------------------------------------------------ #
    def get_setting(self, key: str, default: str = "") -> str:
        return self.settings_repo.get(key, default) or default

    def set_setting(self, key: str, value: str) -> None:
        self.settings_repo.set(key, value)

    def close(self) -> None:
        self.db.close()
