"""
Central configuration for the Personal Time Tracker.

This module holds every "magic value" the rest of the app needs: where files
live on disk, the colors used across the UI and charts, the rules that decide
whether a day counts as complete, and the list of categories we create the very
first time the app runs.

Keeping all of this in one place means you can retune the app's behavior (say,
change what counts as a "partial" day) without hunting through the codebase.
"""

from __future__ import annotations

import os

# --------------------------------------------------------------------------- #
# File-system paths
# --------------------------------------------------------------------------- #
# BASE_DIR is the folder this file lives in (the project root). Everything else
# is expressed relative to it, so the app works no matter where it is copied.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# On Android (via Flet), BASE_DIR sits inside the read-only app bundle, so user
# data must live somewhere writable instead. Flet pre-creates a writable,
# per-app directory and exposes it through this environment variable; when set
# (running as a packaged Flet app) data/backups/exports go there. The desktop
# CustomTkinter app never sets this variable, so its behavior is unchanged.
_STORAGE_ROOT = os.environ.get("FLET_APP_STORAGE_DATA") or BASE_DIR

DATA_DIR = os.path.join(_STORAGE_ROOT, "data")
BACKUP_DIR = os.path.join(_STORAGE_ROOT, "backups")
EXPORT_DIR = os.path.join(_STORAGE_ROOT, "exports")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

DB_PATH = os.path.join(DATA_DIR, "timetracker.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "app", "database", "schema.sql")
ICON_PATH = os.path.join(ASSETS_DIR, "icon.ico")


def ensure_directories() -> None:
    """Create the runtime folders if they do not already exist.

    Called once at startup. It is safe to call repeatedly because
    ``exist_ok=True`` turns "already there" into a no-op instead of an error.
    """
    for path in (DATA_DIR, BACKUP_DIR, EXPORT_DIR, ASSETS_DIR):
        os.makedirs(path, exist_ok=True)


# --------------------------------------------------------------------------- #
# Date / time formats
# --------------------------------------------------------------------------- #
# We store timestamps as plain text in these exact shapes. Because ISO-8601
# text sorts the same way alphabetically as it does chronologically, we can
# ORDER BY these columns directly in SQL.
DATE_FMT = "%Y-%m-%d"          # e.g. 2026-07-15
TIME_FMT = "%H:%M"            # e.g. 09:30  (24-hour)
TIMESTAMP_FMT = "%Y-%m-%d %H:%M"  # e.g. 2026-07-15 09:30
# The live timer's start baseline needs seconds — otherwise elapsed time jumps
# ahead by however many seconds had already passed in the current minute the
# instant you press Start. Saved entries stay minute-precision (TIMESTAMP_FMT).
LIVE_TIMESTAMP_FMT = "%Y-%m-%d %H:%M:%S"  # e.g. 2026-07-15 09:30:35

# Human-friendly weekday names, Monday first (matches Python's weekday() where
# Monday == 0). Used in statistics ("most productive weekday").
WEEKDAY_NAMES = [
    "Monday", "Tuesday", "Wednesday", "Thursday",
    "Friday", "Saturday", "Sunday",
]

# --------------------------------------------------------------------------- #
# Day-status thresholds
# --------------------------------------------------------------------------- #
# A day is GREEN only when *every* category that has a target is met. When some
# but not all targets are met the day is YELLOW. These labels are the single
# source of truth for the calendar colors, the dashboard badge, and streaks.
STATUS_COMPLETE = "complete"   # green  – all targeted categories met
STATUS_PARTIAL = "partial"    # yellow – at least one, but not all, met
STATUS_FAILED = "failed"     # red    – past day with targets, none met
STATUS_NEUTRAL = "neutral"    # grey   – future / no targets / before first entry

# The color each status paints on the calendar and status chips. Two shades per
# status (normal + a slightly different tone) keep things readable in both the
# light and dark themes.
STATUS_COLORS = {
    STATUS_COMPLETE: "#2E9E5B",  # green
    STATUS_PARTIAL: "#E0A100",  # amber
    STATUS_FAILED: "#D0463B",   # red
    STATUS_NEUTRAL: "#6B7280",  # grey
}

# --------------------------------------------------------------------------- #
# Chart palette
# --------------------------------------------------------------------------- #
# A calm, colorblind-friendly set of colors handed out to categories that do
# not have an explicit color yet. Reused for every chart so a category keeps a
# consistent color everywhere.
CHART_PALETTE = [
    "#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6",
    "#EC4899", "#14B8A6", "#F97316", "#6366F1", "#84CC16",
]

# --------------------------------------------------------------------------- #
# Default categories created on first run
# --------------------------------------------------------------------------- #
# Each tuple is (name, is_productive, daily_target_minutes). The productive flag
# follows the rule we agreed on: Sleep, Entertainment, Travel and Busy Work are
# recorded but do NOT count toward productive time or the daily goal.
DEFAULT_CATEGORIES = [
    # name,          productive?, daily target (minutes)
    ("Study",         True,  480),   # 8 h
    ("Research",      True,  120),   # 2 h
    ("Reading",       True,   60),   # 1 h
    ("Writing",       True,   60),
    ("Coding",        True,  120),
    ("Exercise",      True,   45),
    ("Entertainment", False,   0),
    ("Travel",        False,   0),
    ("Busy Work",     False,   0),
    ("Sleep",         False,   0),
]

# Default value stored in app_meta the first time the app starts.
DEFAULT_THEME = "dark"          # "dark", "light", or "system"
SCHEMA_VERSION = "1"            # bumped when the schema changes, for migrations
