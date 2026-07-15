# Personal Time Tracker & Productivity Dashboard

A lightweight, **offline** desktop app for Windows 11 that turns manually logged
time entries into a productivity dashboard, calendar, statistics and graphs.
There is no live stopwatch — you type the start and end time of each activity,
and the app does the rest: calculates durations, compares them against your daily
goals, saves everything in a local database, and draws the charts.

Your data never leaves your computer.

---

## Quick start

```bash
# 1. Install the dependencies (one time)
python -m pip install -r requirements.txt

# 2. Run the app
python main.py
```

The first launch creates a local database at `data/timetracker.db` and fills it
with ten starter categories (Study, Research, Reading, …). Nothing else is
needed — no accounts, no setup, no internet.

Requires **Python 3.10+** (built and tested on 3.13). `tkinter` and `sqlite3`
come with Python; the other packages are in `requirements.txt`.

---

## What it does

| Screen | What you get |
| --- | --- |
| **Dashboard** | One day at a glance: a green/amber/red status banner, cards for productive time, recorded time, streak, longest session and sessions, plus a per-category target-vs-actual table. |
| **Today's Entries** | Add, edit and delete time entries for any day. Overlapping sessions are flagged. "Duplicate previous day" clones yesterday's log. |
| **Calendar** | A colored month grid — green = every goal met, amber = some met, red = none met, grey = no goal / no data / future. Click a day to see its entries. |
| **Statistics** | Daily / weekly / monthly / yearly totals, averages, longest session, streaks, most & least productive weekday, and a time-by-category breakdown. |
| **Graphs** | Six charts (daily hours, weekly, monthly, category pie, productivity trend, streak history) that redraw when data or theme changes. |
| **Categories** | Create, edit, archive or delete categories; set each one's color, daily goal, and whether it counts as "productive". |
| **Search** | Find entries by keyword (in notes), category and/or date. |
| **Settings** | Dark/light theme, export to Excel/CSV/JSON, and back up / restore the database. |

### Keyboard shortcuts
- `Ctrl+1` … `Ctrl+8` — jump to a screen (in sidebar order)
- `Ctrl+N` — add an entry from anywhere
- `Ctrl+F` — open Search

---

## A few rules worth knowing

These are the decisions that shape the numbers, so they are spelled out here:

- **Overnight sessions split at midnight.** If you log Sleep from `23:00` to
  `07:00`, the app understands the end time is the next morning. One hour counts
  toward the first day and seven toward the next, so each day's totals are
  accurate. You still edit or delete it as a single entry.
- **Productive vs recorded time.** Every category has a "Productive" switch.
  *Recorded* time is everything you logged; *productive* time counts only
  productive categories. By default Sleep, Entertainment, Travel and Busy Work
  are **not** productive.
- **When a day is "Complete".** A day is **green** only when *every* category
  that has a daily goal met it. If some but not all goals are met it is
  **amber**; a past day with goals where none are met is **red**; days with no
  goals, no data, or in the future are **grey**.
- **Streaks.** A streak is a run of consecutive green days. Grey days are
  skipped, and today is given grace — an unfinished today never breaks your
  streak.

---

## Project structure

The code is organised in clean layers so it is easy to extend. Each layer only
talks to the one below it; the user interface never runs SQL and never does time
arithmetic.

```
main.py                     Entry point
config.py                   Paths, colors, thresholds, default categories
app/
├── database/               SQLite: connection, schema.sql, repositories (the only SQL)
├── models/                 Plain data objects (Category, TimeEntry, DailySummary, …)
├── services/               All business logic and rules
│   ├── aggregation.py        The shared engine: split-at-midnight + day status
│   ├── entry_service.py      Add/edit/delete/duplicate + overlap detection
│   ├── dashboard_service.py  Builds a day's summary
│   ├── stats_service.py      Daily/weekly/monthly/yearly statistics
│   ├── streak_service.py     Current & longest streak
│   ├── calendar_service.py   Month status colors
│   ├── category_service.py   Category rules (archive-don't-destroy)
│   ├── search_service.py     Search
│   ├── backup_service.py     Backup & restore
│   └── context.py            Wires everything together (AppContext)
├── charts/                 Prepare series (chart_data) + draw them (chart_factory)
├── export/                 Excel / CSV / JSON exporters
└── ui/                     CustomTkinter: app window, sidebar, widgets, views
```

Data folders are created next to the app at runtime: `data/` (the database),
`backups/`, and `exports/`.

---

## Backups & exports

- **SQLite is always the source of truth.** Exports are snapshots for backup or
  for opening in a spreadsheet — the app keeps working from the database.
- **Backups** use SQLite's safe online-backup mechanism and are timestamped in
  `backups/`. Restoring replaces your current data and asks for confirmation
  first.

---

## Design principles

Fast, offline, minimal clicks, easy editing, and — above all — **your data is
never lost**: deleting a category that has entries is blocked in favor of
archiving, deletes ask for confirmation, and backups are one click away.
