"""Shared base class for all repositories."""

from __future__ import annotations

import sqlite3

from app.database.connection import DatabaseManager


class BaseRepository:
    """Common plumbing every repository needs.

    A repository is a small object whose only job is to read and write one kind
    of thing (categories, entries, ...) in the database. They all share the same
    connection through the ``DatabaseManager`` passed in here, so the whole app
    talks to a single database file.
    """

    def __init__(self, db: DatabaseManager) -> None:
        self.db = db

    @property
    def conn(self) -> sqlite3.Connection:
        """The shared live database connection."""
        return self.db.conn
