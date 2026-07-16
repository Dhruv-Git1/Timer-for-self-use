-- ==========================================================================
-- Personal Time Tracker — database schema
--
-- This file is the single source of truth for the shape of the database. The
-- app runs it once, the first time it starts, to create the tables. "IF NOT
-- EXISTS" makes it safe to run again without wiping anything.
--
-- Storage choices worth knowing:
--   * Times are kept as full text timestamps "YYYY-MM-DD HH:MM". ISO-8601 text
--     sorts the same alphabetically as chronologically, so ORDER BY just works.
--   * The columns log_date, duration_minutes and crosses_midnight are DERIVED
--     from start_ts/end_ts. The app recomputes them on every save so they can
--     never drift out of agreement with the timestamps.
-- ==========================================================================

PRAGMA foreign_keys = ON;

-- --------------------------------------------------------------------------
-- Categories: the kinds of activity you track (Study, Sleep, Exercise, ...).
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS categories (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    -- COLLATE NOCASE makes the UNIQUE check case-insensitive, so "Study" and
    -- "study" are treated as the same name.
    name                 TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    -- Hex color used for this category everywhere (charts, calendar legend).
    color                TEXT    NOT NULL DEFAULT '#3B82F6',
    -- 1 = counts toward "productive time" and the daily goal; 0 = merely
    -- recorded (Sleep, Entertainment, Travel, Busy Work default to 0).
    is_productive        INTEGER NOT NULL DEFAULT 1 CHECK (is_productive IN (0, 1)),
    -- Daily goal in minutes. 0 means "no goal set for this category".
    daily_target_minutes INTEGER NOT NULL DEFAULT 0 CHECK (daily_target_minutes >= 0),
    -- How this category is recorded on Android: stopwatch, daily check-off,
    -- or a whole-number counter. Existing/desktop categories remain timers.
    tracking_mode        TEXT    NOT NULL DEFAULT 'timer'
                                 CHECK (tracking_mode IN ('timer', 'checkoff', 'counter')),
    -- Counter/check-off goal. Check-off always uses 1; timer categories ignore it.
    daily_target_count   INTEGER NOT NULL DEFAULT 1 CHECK (daily_target_count >= 1),
    -- Short label shown beside counter values, e.g. glasses, pages, fruits.
    unit_label           TEXT    NOT NULL DEFAULT 'times',
    -- Whether this goal contributes to Today's score at all.
    include_in_daily_score INTEGER NOT NULL DEFAULT 1
                                   CHECK (include_in_daily_score IN (0, 1)),
    -- How much this category counts in Today's score relative to the others
    -- (a weighted average, not a plain one). 1 = the original equal weighting.
    score_weight         INTEGER NOT NULL DEFAULT 1 CHECK (score_weight >= 1),
    -- Controls display order in lists.
    sort_order           INTEGER NOT NULL DEFAULT 0,
    -- Soft delete: archived categories vanish from pickers but keep their
    -- history so past statistics stay intact.
    is_archived          INTEGER NOT NULL DEFAULT 0 CHECK (is_archived IN (0, 1)),
    created_at           TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at           TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- --------------------------------------------------------------------------
-- Time entries: one row per logged activity session.
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS time_entries (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    -- ON DELETE RESTRICT: SQLite refuses to delete a category that still has
    -- entries. The app catches this and offers to archive instead, so logged
    -- history is never silently destroyed.
    category_id      INTEGER NOT NULL REFERENCES categories(id) ON DELETE RESTRICT,
    -- The calendar day the session STARTED on (= date part of start_ts). Note
    -- that an overnight session is split across days at calculation time, not
    -- here; this column is just the "home" day for quick lookups.
    log_date         TEXT    NOT NULL,
    start_ts         TEXT    NOT NULL,   -- canonical "YYYY-MM-DD HH:MM"
    end_ts           TEXT    NOT NULL,   -- canonical; may fall on the next day
    duration_minutes INTEGER NOT NULL CHECK (duration_minutes > 0 AND duration_minutes <= 1440),
    crosses_midnight INTEGER NOT NULL DEFAULT 0 CHECK (crosses_midnight IN (0, 1)),
    notes            TEXT    NOT NULL DEFAULT '',
    created_at       TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at       TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Indexes for the lookups the app does constantly: "entries on this day",
-- "entries in this category", and range scans ordered by start time.
CREATE INDEX IF NOT EXISTS idx_entries_log_date ON time_entries(log_date);
CREATE INDEX IF NOT EXISTS idx_entries_category ON time_entries(category_id);
CREATE INDEX IF NOT EXISTS idx_entries_start_ts ON time_entries(start_ts);

-- --------------------------------------------------------------------------
-- Daily progress: one current check-off/counter value per category and date.
-- Timer progress remains derived from time_entries and is never duplicated here.
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS daily_progress (
    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE RESTRICT,
    log_date    TEXT    NOT NULL,
    value       INTEGER NOT NULL DEFAULT 0 CHECK (value >= 0),
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (category_id, log_date)
);

CREATE INDEX IF NOT EXISTS idx_daily_progress_date ON daily_progress(log_date);

-- --------------------------------------------------------------------------
-- Daily reflections: the user's own explanation of what helped or hindered
-- productivity. This is intentionally separate from time-entry notes so one
-- reflection represents the whole day and remains easy to edit later.
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS daily_reflections (
    log_date   TEXT PRIMARY KEY,
    notes      TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- --------------------------------------------------------------------------
-- App metadata: a simple key/value store for settings that do not deserve
-- their own table (theme choice, schema version, last-backup time, ...).
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS app_meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
