"""
Backup and restore business logic.

Makes safe copies of the SQLite database and restores them on request. Because
the app runs the database in "write-ahead logging" mode (where recent changes
can live in a side file for a moment before being folded into the main file), we
never just copy the ``.db`` file by hand — we use SQLite's own online-backup
feature, which produces a complete, consistent snapshot even while the app is
running.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
from datetime import datetime
from typing import List, Tuple

import config
from app.database.connection import DatabaseManager
from app.database.repositories.settings_repo import SettingsRepository


class BackupService:
    """Creates timestamped database backups and restores from them."""

    def __init__(self, db: DatabaseManager, settings_repo: SettingsRepository) -> None:
        self.db = db
        self.settings = settings_repo

    def create_backup(self) -> Tuple[bool, str, str]:
        """Write a fresh backup and return ``(ok, message, path)``.

        The backup file is named with the current date and time so backups sort
        naturally and never overwrite each other.
        """
        config.ensure_directories()
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest_path = os.path.join(config.BACKUP_DIR, f"timetracker_{stamp}.db")

        # sqlite3's backup() copies a live database into another connection,
        # producing a consistent snapshot without stopping the app.
        dest_conn = sqlite3.connect(dest_path)
        try:
            self.db.conn.backup(dest_conn)
        finally:
            dest_conn.close()

        self.settings.set("last_backup_at", datetime.now().strftime("%Y-%m-%d %H:%M"))
        return (True, f"Backup saved to {dest_path}", dest_path)

    def list_backups(self) -> List[str]:
        """Paths of existing backup files, newest first."""
        config.ensure_directories()
        files = [
            os.path.join(config.BACKUP_DIR, f)
            for f in os.listdir(config.BACKUP_DIR)
            if f.endswith(".db")
        ]
        return sorted(files, reverse=True)

    def restore_backup(self, backup_path: str) -> Tuple[bool, str]:
        """Replace the current database with a chosen backup file.

        Steps: close the live connection, drop the current database file (and its
        temporary write-ahead files), copy the backup into place, then reconnect.
        Because every repository asks the manager for the connection fresh each
        time, they all transparently start using the restored database.
        """
        if not os.path.exists(backup_path):
            return (False, "That backup file no longer exists.")

        self.db.close()
        try:
            # Remove the current database and any leftover WAL side files so no
            # stale data survives the restore.
            for suffix in ("", "-wal", "-shm"):
                path = config.DB_PATH + suffix
                if os.path.exists(path):
                    os.remove(path)
            shutil.copy(backup_path, config.DB_PATH)
        except OSError as exc:
            self.db.connect()  # make sure the app still has a working connection
            return (False, f"Restore failed: {exc}")

        self.db.connect()
        return (True, "Backup restored successfully.")
