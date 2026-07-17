"""A practical in-app guide to the Android timer's features."""

from __future__ import annotations

import flet as ft

from mobile import theme


def _guide_card(icon: str, title: str, copy: str) -> ft.Control:
    return theme.card(
        ft.Row(
            vertical_alignment=ft.CrossAxisAlignment.START,
            spacing=12,
            controls=[
                ft.Container(
                    width=36,
                    height=36,
                    border_radius=18,
                    bgcolor=theme.NEUTRAL_BTN,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(icon, size=19, color=theme.FLAME),
                ),
                ft.Column(
                    expand=True,
                    spacing=4,
                    controls=[
                        ft.Text(title, size=14, color=theme.HEADLINE,
                                weight=ft.FontWeight.BOLD),
                        ft.Text(copy, size=12, color=theme.MUTED_TEXT),
                    ],
                ),
            ],
        ),
        padding=14,
        radius=12,
    )


def _section(title: str, cards: list[ft.Control]) -> list[ft.Control]:
    return [theme.section_label(title), *cards]


def build(page: ft.Page, ctx) -> ft.Control:
    """Build a readable, task-ordered guide instead of a feature dump."""
    controls: list[ft.Control] = [
        theme.display("How to use", size=28),
        ft.Text(
            "Start with one category and one session. Everything else builds from "
            "the activity you record there.",
            size=13,
            color=theme.MUTED_TEXT,
        ),
    ]
    controls += _section("1 · Track today", [
        _guide_card(
            ft.Icons.TIMER,
            "Timer and countdown",
            "On Timer, choose a timer category, then use Stopwatch or Countdown. "
            "Stop saves the session; Discard removes a session you do not want to log.",
        ),
        _guide_card(
            ft.Icons.CATEGORY,
            "Categories and daily wins",
            "In More → Categories, create Timer, Check-off, or Counter categories. "
            "Check-offs mark one win; counters record amounts such as pages or glasses.",
        ),
        _guide_card(
            ft.Icons.SCORE,
            "Today's score",
            "The Timer tab combines the categories included in your daily score. "
            "Use the category editor to include, exclude, or change each daily target.",
        ),
    ])
    controls += _section("2 · Plan with goals", [
        _guide_card(
            ft.Icons.FLAG,
            "Create a goal",
            "Open Goals and tap + Add. Choose Task for a one-off checkbox, Routine for "
            "a permanent scheduled habit, or Target for progress measured from a category. "
            "Use All, Tasks, Routines, and Targets to filter the list.",
        ),
        _guide_card(
            ft.Icons.CHECK_BOX,
            "Tasks, deadlines, and reminders",
            "Tasks can have no deadline or an exact date and time, including any year. "
            "Choose a preset reminder or a custom number of minutes, hours, or days before. "
            "An overdue task stays visible. A completed task remains checked today, then "
            "moves to Completed tomorrow, where you can restore or delete it.",
        ),
        _guide_card(
            ft.Icons.EVENT_REPEAT,
            "Permanent routines",
            "Choose a start date and any weekdays. A checkbox appears only on scheduled "
            "dates; category activity never checks it automatically. Open a routine to "
            "correct past dates and see its streak, completion rate, total, and year heatmap. "
            "Without a category, the routine is grouped under Personal.",
        ),
        _guide_card(
            ft.Icons.DATE_RANGE,
            "Target schedules and custom cycles",
            "Weekly resets on Monday. Biweekly uses 14-day blocks, and Monthly uses calendar "
            "months. You can also choose a one-time date range, No deadline, or Repeat every "
            "custom number of days, weeks, or months; the selected start date anchors each cycle.",
        ),
        _guide_card(
            ft.Icons.QUERY_STATS,
            "Targets and their own graphs",
            "Choose a category and target amount. Timer categories accept hours and minutes; "
            "check-off and counter targets use their natural units. Logged category activity "
            "updates the target automatically. Open it to compare actual progress with its "
            "target across recent cycles in a graph separate from general analytics.",
        ),
        _guide_card(
            ft.Icons.GRID_ON,
            "Reading routine heatmaps",
            "Completed and missed scheduled days use distinct colors; pending means today is "
            "still open. Unscheduled and future days are also marked separately, so the map "
            "does not treat days you never planned as failures.",
        ),
    ])
    controls += _section("3 · Review and improve", [
        _guide_card(
            ft.Icons.LOCAL_FIRE_DEPARTMENT,
            "Home and daily reflection",
            "Home shows today's productive time, streak, sessions, weekly total, and "
            "daily targets. Add a reflection to remember what helped or got in the way.",
        ),
        _guide_card(
            ft.Icons.CALENDAR_MONTH,
            "Calendar, dashboard, and stats",
            "Find Calendar in More → Review. Use it to inspect daily status, Dashboard "
            "for category detail, Statistics for time periods, and Graphs for trends.",
        ),
        _guide_card(
            ft.Icons.AUTO_AWESOME,
            "Insights and AI Coach",
            "Insights surfaces patterns in your recorded activity. AI Coach uses your "
            "history and optional reflections to suggest a practical next step.",
        ),
    ])
    controls += _section("4 · Manage your history", [
        _guide_card(
            ft.Icons.LIST_ALT,
            "Entries and search",
            "Use Today's Entries to check logged sessions. Search finds older entries by "
            "text, category, or date so you can review where your time went.",
        ),
        _guide_card(
            ft.Icons.SETTINGS,
            "Settings, data, and widgets",
            "In Settings, adjust appearance and daily-score targets, add your personal "
            "Gemini API key for AI Coach, import a Time Tracker CSV, or export CSV/JSON. "
            "On Android, countdowns can continue in the background; add the app widget "
            "for a quick timer/status view.",
        ),
        _guide_card(
            ft.Icons.ARCHIVE,
            "Archive instead of losing history",
            "Archive a category you no longer use. Its past entries and goals stay readable, "
            "while it disappears from everyday pickers.",
        ),
    ])
    return ft.Column(
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        spacing=12,
        controls=controls,
    )
