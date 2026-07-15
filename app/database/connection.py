"""
Database connection management.

``DatabaseManager`` owns the one SQLite connection the whole app shares. It is
responsible for opening the database file, switching on the safety settings we
want (foreign keys, write-ahead logging), creating the tables from schema.sql
the first time, and planting the default categories so a brand-new user has
something to work with.
"""

from __future__ import annotations

import os
import sqlite3
from typing import Optional

import config


class DatabaseManager:
    """Opens and configures the SQLite database, and seeds first-run data."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        # Allow an override (used by tests) but default to the configured file.
        self.db_path = db_path or config.DB_PATH
        self._conn: Optional[sqlite3.Connection] = None

    # ------------------------------------------------------------------ #
    # Connection lifecycle
    # ------------------------------------------------------------------ #
    def connect(self) -> sqlite3.Connection:
        """Open the connection (if not already open) and return it.

        We ask SQLite for a few things up front:
          * ``row_factory = sqlite3.Row`` so query results behave like
            dictionaries (``row["name"]``) instead of bare tuples.
          * ``PRAGMA foreign_keys = ON`` so the ON DELETE RESTRICT rule that
            protects logged history is actually enforced (SQLite leaves it off
            by default for historical reasons).
          * ``PRAGMA journal_mode = WAL`` (write-ahead logging) for smoother
            concurrent reads/writes and safer crashes.
        """
        if self._conn is not None:
            return self._conn

        # Make sure the folder for the database file exists first.
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        self._conn = conn
        return conn

    @property
    def conn(self) -> sqlite3.Connection:
        """The live connection, opening it on first use."""
        return self.connect()

    def close(self) -> None:
        """Close the connection (used before restoring from a backup)."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # ------------------------------------------------------------------ #
    # Schema creation and first-run seeding
    # ------------------------------------------------------------------ #
    def initialize(self) -> None:
        """Create the tables (if needed) and seed defaults on first run."""
        self._create_schema()
        self._seed_defaults()

    def _create_schema(self) -> None:
        """Run schema.sql to create tables and indexes."""
        with open(config.SCHEMA_PATH, "r", encoding="utf-8") as fh:
            script = fh.read()
        # executescript runs many statements separated by ';' in one go.
        self.conn.executescript(script)
        self.conn.commit()

    def _seed_defaults(self) -> None:
        """Insert starter categories and settings, but only once.

        We guard on a ``first_run`` flag in app_meta so that if you later delete
        all the categories on purpose, we do not helpfully recreate them behind
        your back on the next launch.
        """
        cur = self.conn.cursor()
        already = cur.execute(
            "SELECT value FROM app_meta WHERE key = 'first_run'"
        ).fetchone()
        if already is not None:
            return  # we have seeded before; leave everything as the user left it

        # Insert the default categories from config, giving each a color from
        # the shared palette and a sort order matching its position in the list.
        for index, (name, is_productive, target) in enumerate(config.DEFAULT_CATEGORIES):
            color = config.CHART_PALETTE[index % len(config.CHART_PALETTE)]
            cur.execute(
                """
                INSERT INTO categories
                    (name, color, is_productive, daily_target_minutes, sort_order)
                VALUES (?, ?, ?, ?, ?)
                """,
                (name, color, 1 if is_productive else 0, target, index),
            )

        # Record the settings that mark this database as initialized.
        cur.executemany(
            "INSERT OR REPLACE INTO app_meta (key, value) VALUES (?, ?)",
            [
                ("first_run", "done"),
                ("schema_version", config.SCHEMA_VERSION),
                ("theme", config.DEFAULT_THEME),
            ],
        )
        self.conn.commit()
