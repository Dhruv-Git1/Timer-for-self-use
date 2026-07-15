# Personal Time Tracker & Productivity Dashboard

Offline time-tracking app, styled as a dark cinematic "REVENGE" theme, now in
**two forms that share one brain**:
- **Desktop** (Windows 11): Python 3.13, CustomTkinter (UI), matplotlib (charts),
  Pillow (hero banner compositing, icon).
- **Mobile** (Android, via Flet): same Python 3.13, Flet 0.86 (UI, renders through
  Flutter), `flet-charts` (native charts). Lives at `mobile/`.

Both import the exact same `app/services/`, `app/models/`, `app/utils/`,
`app/database/` (SQLite) — that shared layer has zero UI-toolkit dependency and
is the reason the mobile port was fast. Only the *views* (`app/ui/` vs.
`mobile/screens/`) and the *chart drawing* (`app/charts/chart_factory.py`
matplotlib vs. `mobile/widgets/charts.py` Flet-native) are duplicated, one per
platform. pandas+openpyxl (Excel export) stay desktop-only; CSV/JSON export is
pandas-free and shared. Everything runs locally — no network calls anywhere in
either app.

**Status:** desktop is fully built, working, and has been launched and visually
verified. Mobile has all the same screens built and verified (headless
construction/interaction tests + a real `flet run` launch + screenshots) but
**has not yet been packaged as an actual Android APK** — that's the next step
(see "Mobile app" below). Treat any "fully built and working" claim in this file
as "verified as of its own section" rather than a blanket guarantee — this repo
has been caught with stale docs before (a screen once silently unwired despite
this file saying otherwise); re-check a claim against the actual code before
relying on it for anything consequential.

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
4. **Mobile port to Android via Flet** (2026-07-15): user wants "same UI" on a
   phone. Decided to keep the desktop app untouched and add a *separate* Flet
   app (`mobile/`) that imports the same services/database layer rather than
   duplicating logic or rewriting the desktop app in place. Screens were
   rebuilt one-for-one for a phone-sized, bottom-nav layout; charts rebuilt
   native (matplotlib doesn't run on Android). See "Mobile app" below.

## Architecture — strict layering (dependencies point downward)

```
                    ┌─ UI: app/ui/ (CustomTkinter, desktop)
Services ──────────┤
(app/services/)     └─ UI: mobile/screens/ (Flet, Android) ── mobile/widgets/charts.py (native charts)
    │                                                          mobile/widgets/heatmap.py (hand-built)
    ▼
Repositories (app/database/) → SQLite
Models (app/models/) + Utils (app/utils/) are shared across everything above.
app/charts/chart_data.py (pure data-shaping) is ALSO shared by both UIs;
app/charts/chart_factory.py + chart_frame.py (matplotlib) are desktop-only.
Export (app/export/) is read by both — pandas only in to_excel() (desktop-only).
```

Two rules that keep it clean — **do not break these**:
1. **No UI layer runs SQL** (repositories are the only place with SQL) — applies
   to `app/ui/` and `mobile/screens/` alike.
2. **No UI layer does time arithmetic** (all of that lives in `app/utils/time_utils.py`
   and the services) — same rule, both platforms.

**When adding a feature that should exist on both platforms:** put the
calculation/data-shaping in `app/services/` or `app/charts/chart_data.py` first
(both already have zero UI dependency), then build the desktop view and the
Flet screen as thin, mostly-independent consumers of that same function. This
is the whole reason the mobile port went fast — don't let new logic leak into
`app/ui/views/*` or `mobile/screens/*` where it can't be shared.

**Refresh-on-change:** a tiny pub/sub bus in `app/utils/event_bus.py` (singleton
`bus`, events `DATA_CHANGED` / `TIMER_STATE_CHANGED`). Services publish after
mutations; every screen (`BaseView`) auto-subscribes and re-`refresh()`s itself
only while it's the visible one.

**Wiring:** `app/services/context.py` (`AppContext`) builds the whole object
graph once — db → repositories → services — in dependency order, and is passed
into every view. There is exactly one `AppContext` per running app.
`export_service` is built lazily (a property, not a constructor-time field) so
just importing/constructing `AppContext` never requires pandas — only actually
calling `ctx.export_service` does. This matters on mobile, which has no pandas.

**Desktop vs. mobile refresh model:** desktop uses the `event_bus` above so a
visible screen repaints itself live when data changes elsewhere. Mobile does
not use the event bus at all — each `mobile/screens/*.build()` call is a fresh,
self-contained closure that reads current data once and rebuilds its own
controls on every internal state change (tap, save, nav step); switching tabs
in `mobile/app_shell.py` just calls `build()` again. Simpler, no subscription
lifecycle to manage, at the cost of no cross-screen live-refresh (acceptable
for a phone UI where you're only ever looking at one screen at a time).

## File map

```
main.py                  Desktop entry point: folders → AppContext → load
                          revenge.json theme → apply saved dark/light mode →
                          AppWindow → mainloop
config.py                 Paths, date/time formats, day-status thresholds + colors,
                          chart palette, default seed categories. Data/backup/
                          export dirs resolve from FLET_APP_STORAGE_DATA when set
                          (mobile), else fall back to BASE_DIR (desktop, unchanged)
pyproject.toml            Flet build config for the MOBILE app only — [tool.flet.app]
                          module = "mobile.main", org/bundle_id, Android min_sdk_version.
                          Desktop (main.py) does not use this file at all.
requirements.txt          Pinned dependency versions (desktop). Mobile's deps
                          (flet, flet-charts) are declared in pyproject.toml instead.
CLAUDE.md                 This file
README.md                 User-facing docs — NOTE: written for the original
                          manual-entry design, now stale re: the timer + REVENGE
                          theme + mobile app (not yet updated to match; see below)

data/timetracker.db       SQLite database (WAL mode) — created at first run
backups/, exports/        Created at runtime by Settings actions
assets/icon.ico           App/window/shortcut icon (generated, blue stopwatch)
assets/hero.png           The Home screen's hero background image (user-supplied)
assets/theme/revenge.json Custom CustomTkinter color theme (see Theming below)

app/database/
  connection.py            DatabaseManager: opens the connection, runs schema.sql
                            (loaded via importlib.resources, not a raw file path —
                            works the same run from source or bundled in a package),
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
  stats_service.py          Daily/weekly/monthly/yearly aggregates (pure Python
                            — no pandas, despite what an earlier version of this
                            file claimed; verified by reading the actual imports)
  streak_service.py         Current + longest streak (grey-day-skipping, today-
                            grace logic)
  calendar_service.py       Month → {date: DayStatus} for the calendar grid
  search_service.py         Keyword/category/date search over entries
  backup_service.py         Backup/restore via SQLite's online-backup API (desktop-only UI so far)
  context.py                AppContext — builds and wires every repo + service.
                            export_service is a lazy property (see Wiring above)

app/charts/
  chart_data.py             Turns service data into plottable Series (daily/
                            weekly/monthly hours, category pie, trend, streak
                            history)
  chart_factory.py          Draws matplotlib Figures (line/bar/pie/trend) with a
                            ChartStyle (colors); ChartStyle.dark() matches the
                            REVENGE near-black/crimson palette
  chart_frame.py            CTk widget hosting one reusable Figure+Canvas
                            (never recreated — avoids Tk/matplotlib leaks)

app/export/exporter.py     Excel (multi-sheet, pandas+openpyxl, desktop-only)/
                          CSV (stdlib csv, no pandas)/JSON (stdlib json) export

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
                            entries, calendar, statistics, graphs, insights,
                            categories, search, settings), live "● Recording"
                            indicator when the timer is active, dark/light mode switch
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
    insights_view.py            Per-category deep dive: pick one category, see its
                            own year heat-map (GitHub-style), streak/best-day/
                            total stat cards, and its weekday pattern
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
    goals_form.py                Edit every category's daily goal (minutes) in one
                            dialog — also reachable inline from Timer/Home
    time_entry_form.py          Modal add/edit form for manual entries
    category_form.py            Modal add/edit form for categories
    confirm_dialog.py           ask_confirm() blocking Yes/No modal

mobile/                    THE FLET APP (Android + desktop preview). Imports
                          app/services, app/models, app/utils, app/database,
                          and app/charts/chart_data.py UNCHANGED — see Architecture
                          above. Nothing here touches CustomTkinter or matplotlib.
  main.py                   Entry point: sys.path shim (so app.* and mobile.*
                            both import regardless of how this file is launched)
                            → ft.run(main) → builds AppShell. Run via:
                            `flet run mobile/main.py` (desktop preview) or
                            `flet build apk` (real Android build, see below)
  storage.py                get_context(): builds ONE AppContext, cached at module
                            level, shared by every screen (mirrors AppWindow.ctx)
  theme.py                  Same crimson/near-black tokens as app/ui/theme.py, as
                            plain hex strings (Flet takes a hex string directly —
                            no ColorScheme object needed). Dark only for now.
  app_shell.py               The whole nav model: ONE ft.View holding a
                            NavigationBar (Timer/Home/Calendar/Insights/More) +
                            a Container whose .content gets swapped per tab.
                            Tabs are peers (rebuild + page.update()), NOT a
                            page.views push/pop stack — simpler, and enough for
                            a 5-destination bottom bar. "More" is a plain
                            tappable list (not a NavigationDrawer — opening a
                            drawer imperatively wasn't confirmed as available
                            in this Flet version, so a pushed-list screen was
                            used instead; functionally the same for the user).

  screens/  (each is a plain `build(page, ctx) -> ft.Control` function — no
             class, no BaseView, no event-bus subscription; see "Desktop vs.
             mobile refresh model" above for why)
    timer_screen.py            Live clock (page.run_task async tick loop, NOT
                            page.after — that's a CTk-ism), 2-col category grid
                            (3-col on desktop), inline goal edit (tap pencil —
                            no modal, simpler than desktop's dialog)
    home_screen.py             Stat cards + Mission Targets. No hero banner yet
                            (Pillow compositing is desktop-only; a plain header
                            stands in for now)
    calendar_screen.py         Month grid; tap a day → BottomSheet (page.overlay
                            .append(sheet); sheet.open = True; page.update())
    insights_screen.py         Category dropdown + year nav + the heatmap widget
                            + stat cards + weekday bar chart — same
                            ChartDataProvider calls as desktop's insights_view.py
    dashboard_screen.py         One day's detail, same shape as desktop
    entries_screen.py           Day's entries + add/edit via AlertDialog
                            (page.show_dialog(dialog) / page.pop_dialog())
    statistics_screen.py        Daily/Weekly/Monthly/Yearly toggle (plain
                            Container buttons, not ft.SegmentedButton) + cards
    graphs_screen.py             The same 6 charts as desktop's graphs_view.py,
                            via mobile/widgets/charts.py (Flet-native, NOT
                            matplotlib — matplotlib does not run on Android)
    categories_screen.py        Add/edit/archive/delete; color picked from a
                            row of config.CHART_PALETTE swatches (no system
                            color picker on Flet/Android the way desktop's
                            tkinter.colorchooser has)
    search_screen.py            Keyword/category/date filter, tap to edit
    settings_screen.py          Theme switch + CSV/JSON export (no Excel — see
                            app/export/exporter.py note above; no backup/
                            restore yet — assumes a desktop-style file browser)
    placeholder_screen.py       "Coming soon" filler — kept for any future More
                            item added before its real screen exists (currently
                            unused: every item is a real screen)

  widgets/
    charts.py                  General line_chart()/bar_chart()/pie_chart() over
                            a chart_data.Series, using flet_charts (a SEPARATE
                            pip package from core `flet` in this version —
                            `pip install flet flet-charts`, matching versions).
                            The mobile equivalent of app/charts/chart_factory.py.
    heatmap.py                  The GitHub-style year heat-map, hand-built from
                            Container grids (no Flet chart type does this) —
                            horizontally scrollable, reads left(Jan)→right(Dec)
                            same direction as desktop, since a full year can't
                            fit a phone's width at once
    stat_card.py                 Flet version of the desktop stat tile
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
- **Mobile calls the exact same `TimerService`** (`mobile/screens/timer_screen.py`)
  — same start/stop/discard/current_state(), same rules above. The only
  difference is *how the second-by-second tick is driven*: desktop uses CTk's
  `self.after(1000, ...)`; mobile uses `page.run_task(async_tick_loop)` (an
  `async def` with `await asyncio.sleep(1)` in a loop) — that's the Flet-native
  equivalent, confirmed via `hasattr(ft.Page, "run_task")` before use.

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

**Mobile's theme is much simpler:** `mobile/theme.py` is just the same crimson/
near-black hex values as plain module-level string constants (no light/dark
tuple, no font resolution — Flet handles fonts itself). Flet controls accept a
hex string directly wherever they want a color, so there's no CTk-theme-JSON
equivalent to keep in sync — one file, no `KeyError`-on-missing-key trap. Only
dark mode is implemented on mobile so far (Settings has a Dark/Light/System
switch that updates `page.theme_mode`, but no light-mode token set exists yet
— picking Light currently just flips Flet's own default light colors, not the
REVENGE palette).

The hero banner's text is configurable via `app_meta` settings (`hero_kicker`,
`hero_headline`, `hero_subtitle`, `hero_image_path`) with sensible defaults —
not yet exposed as UI controls in Settings (a natural next step if wanted).

## Database

SQLite at `data/timetracker.db` (WAL mode). Schema is `app/database/schema.sql`
(the source of truth, loaded via `importlib.resources` — see File map). Tables:
`categories`, `time_entries`, `app_meta` (key/value settings — also used for
theme choice, first-run flag, last-backup time, and the live timer's persisted
state). Deleting a category with entries is blocked → archive instead
(`ON DELETE RESTRICT`), so history is never lost.

On a real installed Android build, the database (and backups/exports) will
live under whatever `os.environ["FLET_APP_STORAGE_DATA"]` points to (a
writable, per-app, update-persistent directory the Android runtime provides)
instead of next to the source — `config.py` picks this up automatically.

**Verified directly (2026-07-15), and worth knowing:** `flet run mobile/main.py`
(the desktop preview) does **NOT** set `FLET_APP_STORAGE_DATA` — only a real
packaged/installed build does. So right now, previewing the mobile app on this
desktop reads and writes the exact same `data/timetracker.db` as the
CustomTkinter app — confirmed by querying the real db and finding entries/goal
edits made through the mobile preview sitting right next to the desktop app's
data. This is harmless (it's still just the one real local database, nothing
sent anywhere), but it means: once a real APK is installed on a phone, THAT
copy starts from an empty database in its own sandboxed storage — it will
*not* already contain what you see in the desktop-preview testing right now.
There is no sync between desktop and a real phone install; they are two
independent SQLite files from that point on.

## Conventions

Desktop:
- Colors are centralized in `app/ui/theme.py` as (light, dark) tuples; status/
  chart colors in `config.py`. Prefer theme tokens over hardcoded hex in new code.
- Charts use matplotlib's `Figure` + `FigureCanvasTkAgg` directly — never
  `pyplot` (it leaks in a long-running GUI). See `app/charts/`.
- Every screen subclasses `BaseView` and implements `refresh()`.

Mobile:
- Every screen is a plain `build(page: ft.Page, ctx: AppContext) -> ft.Control`
  function (see `mobile/screens/`) — no base class, no lifecycle hooks. Read
  `mobile/theme.py` for colors (plain hex strings), not `app/ui/theme.py`
  (light/dark tuples — a CTk-ism that doesn't apply here).
- **Verify the Flet API before writing code, don't rely on training-data
  memory of older Flet versions.** This framework's control names and event
  patterns have changed release to release, and the current install here is
  0.86. Concretely hit and fixed once already: `ft.ElevatedButton` /
  `ft.TextButton` (old) → `ft.Button` is the current one for a filled button
  (`ElevatedButton` still works but is deprecated, warns at runtime, and is
  slated for removal in 1.0); `ft.Dropdown`'s change event is `on_select`, not
  `on_change`; showing a modal is `page.show_dialog(dialog)` /
  `page.pop_dialog()`, not a `dialog.open = True` flag (that pattern IS still
  used for `ft.BottomSheet`, via `page.overlay.append(sheet); sheet.open =
  True; page.update()` — the two dialog-ish controls are NOT symmetric in this
  version); geometry helpers are `ft.Border.all(width, color)` /
  `ft.Padding.symmetric(vertical=, horizontal=)` / `ft.BorderRadius.all(radius)`
  / `ft.Alignment.CENTER` (classmethod-style constructors / class constants —
  not the old lowercase `ft.border.all()` / `ft.alignment.center` module
  style). Quick way to check anything: `python -c "import flet as ft, inspect;
  print(inspect.signature(ft.Whatever.__init__))"` against the real installed
  package — faster and more reliable than guessing.
- `flet-charts` is a SEPARATE pip package from core `flet` in this version —
  install both, matching versions (`pip install flet==X flet-charts==X`).
  matplotlib does not run on Android at all; don't reach for it on the mobile
  side even for a "quick" chart.

## Testing / verification

No formal test suite; verification is done with headless scripts (written to the
session's scratchpad, not checked into the repo).

**Desktop:**
(a) build an `AppContext` against a **temp** DB (never the real one), seed data,
    and assert on service outputs — e.g. back-dating `timer_start_ts` directly to
    simulate elapsed time without sleeping, to test midnight-split, streaks, the
    24h-clip, and restart-persistence deterministically;
(b) construct the real `AppWindow` and cycle through every view (`win.show_view(key)`
    for each nav key) to catch UI build errors before launching for real.

Always run `python -m compileall -q app main.py config.py` after edits, and prefer
a temp-database `AppContext(db_path=...)` over the real one for any exploratory
script — the real db lives at `data/timetracker.db` and should stay clean.

Screen-grab screenshots of a plain Tk window are unreliable (a Tk window won't
come to the front without its event loop, so a grab can capture whatever else
is on screen instead — this happened once and grabbed the browser). For
desktop, prefer rendering matplotlib figures / PIL images (like the hero
composite) directly to PNG and reading those.

**Mobile:** `python -m compileall -q mobile` first. Then a fake-`Page` smoke
test — a tiny stand-in object with `update()`/`run_task()`/`show_dialog()`/
`pop_dialog()`/`overlay`/`views` — lets every `screens/*.build(page, ctx)` run
and even lets you *call the real button callbacks* (`control.controls[i]
.on_click(None)`) to exercise add/edit/delete/save flows end-to-end against a
temp db, without a live Flet server. Then for real: `flet run mobile/main.py`
launches an actual window (a real Flet/Flutter render, not headless), and —
unlike plain Tk — **a targeted screenshot of it works reliably** here: find its
`MainWindowHandle` via `Get-Process flet | Where MainWindowTitle -eq "..."`,
then P/Invoke `PrintWindow(hwnd, hdc, 2)` (flag `2` = `PW_RENDERFULLCONTENT`)
into a `Bitmap` sized from `GetWindowRect` — call `SetProcessDPIAware()` first
or the capture comes out cropped on a scaled display. The same handle can also
be driven with `SetCursorPos` + `mouse_event` (compute screen coords as
`rect.Left/Top + image-relative x/y`) to actually click a control and
screenshot the result — useful for showing the user a specific screen without
them navigating there themselves. A throwaway single-screen preview (build one
`ft.View` around just the screen you want to check, `ft.run` it, screenshot,
`TaskStop` it) is a fast way to visually check one screen/chart in isolation.

## Known gaps / possible next steps

Desktop:
- `README.md` still describes the original manual-entry-only design and doesn't
  mention the timer, REVENGE theme, or the mobile app — stale, not yet updated.
- Hero banner text (`hero_kicker`/`hero_headline`/`hero_subtitle`/`hero_image_path`)
  is settable via `app_meta` but has no Settings-screen UI yet.
- Light mode still works but is a lesser variant — the cinematic identity is dark.

Mobile (in priority order for "make this a real installable app"):
- **The actual Android build hasn't been run yet.** Everything so far is
  verified via `flet run` (desktop preview) + headless tests. `flet build apk`
  (or `flet build aab` for Play Store) still needs to happen — first run
  downloads JDK/Android SDK/Flutter (multi-GB, one-time) and takes real build
  time; the resulting file then needs installing on an actual device/emulator
  to confirm it truly works on Android, which can't be done from a dev session.
  User explicitly deferred this ("make apk some time later") as of 2026-07-15.
- No hero banner (Pillow compositing is desktop-only; `home_screen.py` uses a
  plain text header instead).
- No light-mode token set (`mobile/theme.py` is dark-only; the Settings
  Dark/Light/System switch changes `page.theme_mode` but Light doesn't yet
  apply REVENGE colors).
- No backup/restore on mobile (assumes a desktop-style file browser today).
- Export is CSV/JSON only (no Excel — needs pandas+openpyxl, deliberately kept
  desktop-only); nothing writes through Android's share sheet yet, so exported
  files land in the app's own storage folder with no built-in way to get them
  out to Drive/email from the phone itself.
- "Insights" (per-category charts) vs. "Graphs" (combined charts) as separate
  destinations confused a user in testing (asked twice where the per-category
  graph was before finding the Insights tab) — worth considering a rename or
  merging a category filter into Graphs too if this comes up again.
- No automated tests are checked into the repo for either platform — same
  "headless scratchpad scripts" approach as desktop (see Testing above).
