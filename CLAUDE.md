# Personal Time Tracker & Productivity Dashboard

Offline Windows 11 desktop app for tracking time and seeing productivity stats,
styled as a dark cinematic "REVENGE" theme. Built with Python 3.13, CustomTkinter
(UI), SQLite (storage), matplotlib (charts), pandas + openpyxl (export), Pillow
(hero banner image compositing, app icon). Everything runs locally — no network
calls anywhere in the app.

**Status: fully built and working.** Every feature below exists, has been
exercised with headless tests, and the app has been launched and visually
verified. This file is the map for picking the project back up in a new session.

## Running the app

```
python main.py
```

**Environment gotcha (important):** this machine has TWO Python installs —
`miniconda3` and `miniforge3`. All the packages (customtkinter, matplotlib, …)
are installed under **miniconda3**. Use:

- `C:\Users\nisha\miniconda3\python.exe` (or `pythonw.exe` to launch with no console window)

A desktop shortcut ("Time Tracker") points at miniconda3's `pythonw.exe` and uses
`assets/icon.ico`. If a plain terminal picks up miniforge3 instead, imports like
`customtkinter` will report "not found" — point at the miniconda3 interpreter
explicitly (`/c/Users/nisha/miniconda3/python.exe` in Git Bash).

To relaunch after code changes: kill any running `pythonw` process first
(`Get-Process pythonw | Stop-Process -Force` in PowerShell), then start it again
— otherwise you're looking at a stale process still running the old code.

## How the project evolved (context for *why* things look this way)

1. Built from a full spec as a **manual-entry** tracker (type start/end `HH:MM`,
   pick a category) with dashboard/calendar/stats/graphs/export/backup.
2. User rejected manual typing — replaced with a **live Start/Stop timer** as the
   primary way to log time (manual add/edit kept as a secondary/backfill tool on
   the Entries screen). Went through one real bug fix: tapping a category
   originally started tracking immediately, which felt like the timer "was
   already running" — now tapping only *selects* a category and a separate
   **Start** button begins it (switching categories *while already running*
   is still one click, no confirmation, since something is already being
   tracked either way).
3. Full **"REVENGE" cinematic re-theme**: dark near-black + crimson-red
   everywhere, a Pillow-composited hero banner (user's own image + generated
   gradient fallback), a new Home landing screen, Windows-safe mono/display
   fonts. This is the current visual identity — not a WIP, it's done and live.

## Architecture — strict layering (dependencies point downward)

```
UI (app/ui/…)  →  Services (app/services/…)  →  Repositories (app/database/…)  →  SQLite
Models (app/models/) + Utils (app/utils/) are shared across layers.
Charts (app/charts/) and Export (app/export/) read Services only.
```

Two rules that keep it clean — **do not break these**:
1. **The UI never runs SQL** (repositories are the only place with SQL).
2. **The UI never does time arithmetic** (all of that lives in `app/utils/time_utils.py`
   and the services).

**Refresh-on-change:** a tiny pub/sub bus in `app/utils/event_bus.py` (singleton
`bus`, events `DATA_CHANGED` / `TIMER_STATE_CHANGED`). Services publish after
mutations; every screen (`BaseView`) auto-subscribes and re-`refresh()`s itself
only while it's the visible one.

**Wiring:** `app/services/context.py` (`AppContext`) builds the whole object
graph once — db → repositories → services — in dependency order, and is passed
into every view. There is exactly one `AppContext` per running app.

## File map

```
main.py                  Entry point: folders → AppContext → load revenge.json
                          theme → apply saved dark/light mode → AppWindow → mainloop
config.py                 Paths, date/time formats, day-status thresholds + colors,
                          chart palette, default seed categories
requirements.txt          Pinned dependency versions
CLAUDE.md                 This file
README.md                 User-facing docs — NOTE: written for the original
                          manual-entry design, now stale re: the timer + REVENGE
                          theme (not yet updated to match; see below)

data/timetracker.db       SQLite database (WAL mode) — created at first run
backups/, exports/        Created at runtime by Settings actions
assets/icon.ico           App/window/shortcut icon (generated, blue stopwatch)
assets/hero.png           The Home screen's hero background image (user-supplied)
assets/theme/revenge.json Custom CustomTkinter color theme (see Theming below)

app/database/
  connection.py            DatabaseManager: opens the connection, runs schema.sql,
                            seeds default categories + settings on first run only
  schema.sql               Source of truth for the schema (categories, time_entries,
                            app_meta key/value settings table)
  repositories/
    base_repo.py            Shared cursor/connection access
    category_repo.py        CRUD for categories
    entry_repo.py            CRUD + date-range/keyword queries for time entries
    settings_repo.py         get/set over the app_meta key/value table (also
                            backs the live timer's persisted state and the hero
                            banner's configurable text)

app/models/                Plain dataclasses — Category, TimeEntry, DailySummary,
                          CategoryProgress, PeriodStats, DayStatus enum

app/services/
  aggregation.py            THE core calculation engine: split_by_day() (midnight
                            split), productive_recorded(), classify_day()/
                            classify_range() (day status green/amber/red/grey).
                            Everything else funnels through this.
  entry_service.py          Add/edit/delete/duplicate-day entries, overlap
                            detection, add_completed_session() (used by the timer)
  timer_service.py          The live timer: start/stop/discard/current_state(),
                            persisted via SettingsRepository (no schema change),
                            auto-switch, sub-minute discard, >24h clip-and-save
  category_service.py       CRUD + validation; delete blocked if entries exist
                            (archive instead) to protect history
  dashboard_service.py      Builds one day's DailySummary (targets vs actual)
  stats_service.py          Daily/weekly/monthly/yearly aggregates (pandas)
  streak_service.py         Current + longest streak (grey-day-skipping, today-
                            grace logic)
  calendar_service.py       Month → {date: DayStatus} for the calendar grid
  search_service.py         Keyword/category/date search over entries
  backup_service.py         Backup/restore via SQLite's online-backup API
  context.py                AppContext — builds and wires every repo + service

app/charts/
  chart_data.py             Turns service data into plottable Series (daily/
                            weekly/monthly hours, category pie, trend, streak
                            history)
  chart_factory.py          Draws matplotlib Figures (line/bar/pie/trend) with a
                            ChartStyle (colors); ChartStyle.dark() matches the
                            REVENGE near-black/crimson palette
  chart_frame.py            CTk widget hosting one reusable Figure+Canvas
                            (never recreated — avoids Tk/matplotlib leaks)

app/export/exporter.py     Excel (multi-sheet)/CSV/JSON export from services

app/utils/
  time_utils.py              All time math: HH:MM parsing/validation,
                            build_timestamps() (manual-entry midnight guessing),
                            entry_fields_from_timestamps() (timer's real-clock
                            path, no guessing needed), split_by_day(),
                            fmt_duration()/fmt_clock(), date helpers
  validators.py              Input validation → (ok, message) pairs
  event_bus.py               Pub/sub bus + DATA_CHANGED/TIMER_STATE_CHANGED

app/ui/
  app_window.py              AppWindow (CTk root): resolves fonts (theme.init_fonts),
                            builds sidebar + content area, view registry
                            (_VIEW_CLASSES), lands on "home", Ctrl+1..9 shortcuts,
                            Ctrl+N quick-add, Ctrl+F search
  sidebar.py                 Left nav: NAV_ITEMS list (home, timer, dashboard,
                            entries, calendar, statistics, graphs, categories,
                            search, settings), live "● Recording" indicator when
                            the timer is active, dark/light mode switch
  theme.py                   ALL color tokens (ACCENT crimson, CARD_COLOR,
                            MUTED_TEXT, …) + MONO_FAMILY/DISPLAY_FAMILY (resolved
                            per-machine by init_fonts()) + spaced() letter-
                            spacing helper. Change tokens here to re-theme the
                            whole app at once.

  views/  (each is a BaseView subclass implementing refresh(); auto-refreshes
           on DATA_CHANGED while visible)
    base_view.py               Common on_show/on_hide/refresh contract
    home_view.py                THE landing screen: hero banner + stat cards
                            (Today/Streak/Sessions/This Week) + "MISSION
                            TARGETS" goal-progress panel + launch buttons
    timer_view.py               Select-a-category → Start → live H:MM:SS clock
                            → Stop/Discard. Auto-switch while running.
    dashboard_view.py           One day's detail: status banner + stat cards +
                            per-category target-vs-actual table
    entries_view.py             Manual add/edit/delete list for a chosen day
                            (secondary tool — see history above), overlap
                            warnings, duplicate-previous-day
    calendar_view.py            Month grid colored by day status, click a day
                            for its entries
    statistics_view.py          Daily/weekly/monthly/yearly stat cards +
                            category breakdown
    graphs_view.py               The 6 matplotlib charts
    categories_view.py          Manage categories (add/edit/archive/delete)
    search_view.py               Keyword/category/date search
    settings_view.py            Theme toggle, export, backup/restore

  widgets/
    hero_banner.py              Pillow-composited cinematic header: darkened
                            image + red gradient/vignette/speckle + tracked
                            kicker/headline/subtitle + live clock, redrawn on
                            debounced resize; text is baked into one image
                            (CTk "transparent" labels paint the parent's color,
                            not sibling pixels, so stacking labels over an
                            image does not work — this is why it's one bitmap)
    stat_card.py                 Reusable stat tile: big centered number (display
                            font), thin accent underline, tiny tracked mono label
    time_entry_form.py          Modal add/edit form for manual entries
    category_form.py            Modal add/edit form for categories
    confirm_dialog.py           ask_confirm() blocking Yes/No modal
```

## Key domain rules (the tricky logic — all verified with headless tests)

- **Overnight sessions split at midnight.** An entry from 23:00→07:00 is stored
  as one editable row, but its minutes are split across the two days when
  totalling (60 min to day 1, 420 to day 2). The single source of truth is
  `time_utils.split_by_day()`; every aggregation (dashboard, stats, calendar,
  streaks, charts) funnels through it.
- **Productive vs recorded time.** Each category has an `is_productive` flag.
  Recorded = all entries; productive = only productive categories. Seed
  defaults not-productive: Sleep, Entertainment, Travel, Busy Work.
- **Day status → calendar color → streaks.** A day is GREEN only when *every*
  category with a daily target met it; YELLOW if some but not all; RED if a past
  day with targets met none; GREY for future / no-targets / before first entry.
  A streak = consecutive green days (grey skipped; today gets grace so an
  unfinished day never breaks it). Rules live in `app/services/aggregation.py`.

## The live timer

- Home screen is the landing page; **Timer** is its own tab (`app/ui/views/timer_view.py`).
- **Select-then-Start:** tapping a category only *selects* it (a stray click can't
  start real tracking); a separate **Start** button begins it. While a timer is
  already running, tapping a *different* category is a one-click auto-switch
  (saves the old session, starts the new one — no confirmation needed there).
- **Silent resume:** running state lives in the `app_meta` key/value table
  (`timer_active`, `timer_category_id`, `timer_start_ts`) via SettingsRepository —
  no schema change. Elapsed = now − stored start, so closing/reopening the app
  just keeps counting. Logic in `app/services/timer_service.py`.
- Sessions under a minute are discarded (not saved as 0/1-minute noise); a timer
  left running >24h is clipped to 23h59m and saved rather than lost entirely.

## Theming ("REVENGE") — how to change the look

Three independent levers, all needed together for a full re-theme:
1. **`app/ui/theme.py` tokens** — anything built *with* an explicit `theme.X`
   color/font picks this up automatically (StatCard, hero banner, sidebar, most
   view code).
2. **`assets/theme/revenge.json`** — a full CustomTkinter color-theme file (a
   copy of the bundled `blue.json` with red overrides for every widget type:
   CTkButton, CTkProgressBar, CTkSwitch, CTkOptionMenu, etc.). Loaded in
   `main.py` via `ctk.set_default_color_theme(...)` before the window is built.
   Any CTk widget created *without* an explicit color inherits from this file.
   **If you add new theme keys, copy the full key set from `blue.json` first**
   — CTk raises `KeyError` on a missing top-level key.
3. **`config.STATUS_COLORS`/`CHART_PALETTE`** — deliberately left semantic
   (green=complete, amber=partial, red=failed, grey=neutral; per-category chart
   colors). These encode *meaning*, not brand — don't recolor them to red.

`theme.init_fonts(root)` resolves `MONO_FAMILY`/`DISPLAY_FAMILY` to whatever's
actually installed (Cascadia Mono/Consolas for mono, Arial Black/Bahnschrift/
Impact for display) — must run once, right after the Tk root exists, before any
widget builds a font (`AppWindow.__init__` does this first thing).

The hero banner's text is configurable via `app_meta` settings (`hero_kicker`,
`hero_headline`, `hero_subtitle`, `hero_image_path`) with sensible defaults —
not yet exposed as UI controls in Settings (a natural next step if wanted).

## Database

SQLite at `data/timetracker.db` (WAL mode). Schema is `app/database/schema.sql`
(the source of truth). Tables: `categories`, `time_entries`, `app_meta` (key/value
settings — also used for theme choice, first-run flag, last-backup time, and the
live timer's persisted state). Deleting a category with entries is blocked →
archive instead (`ON DELETE RESTRICT`), so history is never lost.

## Conventions

- Colors are centralized in `app/ui/theme.py` as (light, dark) tuples; status/
  chart colors in `config.py`. Prefer theme tokens over hardcoded hex in new code.
- Charts use matplotlib's `Figure` + `FigureCanvasTkAgg` directly — never
  `pyplot` (it leaks in a long-running GUI). See `app/charts/`.
- Every screen subclasses `BaseView` and implements `refresh()`.

## Testing / verification

No formal test suite; verification is done with headless scripts (written to the
session's scratchpad, not checked into the repo) that:
(a) build an `AppContext` against a **temp** DB (never the real one), seed data,
    and assert on service outputs — e.g. back-dating `timer_start_ts` directly to
    simulate elapsed time without sleeping, to test midnight-split, streaks, the
    24h-clip, and restart-persistence deterministically;
(b) construct the real `AppWindow` and cycle through every view (`win.show_view(key)`
    for each nav key) to catch UI build errors before launching for real.

Always run `python -m compileall -q app main.py config.py` after edits, and prefer
a temp-database `AppContext(db_path=...)` over the real one for any exploratory
script — the real db lives at `data/timetracker.db` and should stay clean.

Note: screen-grab screenshots of the running Tk window are unreliable here (a Tk
window won't come to the front without its event loop, so a grab can capture
whatever else is on screen instead — this happened once and grabbed the browser).
Prefer rendering matplotlib figures / PIL images (like the hero composite)
directly to PNG and reading those for visual checks.

## Known gaps / possible next steps

- `README.md` still describes the original manual-entry-only design and doesn't
  mention the timer or REVENGE theme — stale, not yet updated.
- Hero banner text (`hero_kicker`/`hero_headline`/`hero_subtitle`/`hero_image_path`)
  is settable via `app_meta` but has no Settings-screen UI yet.
- Light mode still works but is a lesser variant — the cinematic identity is dark.
