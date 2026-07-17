"""
The GitHub-style year heatmap for one category, adapted for a narrow phone
screen: instead of shrinking a whole year to fit, it scrolls horizontally —
the standard pattern for calendar heatmaps on small screens — reading left
(January) to right (December), same direction as the desktop version.
"""

from __future__ import annotations

import datetime as _dt
from typing import Dict

import flet as ft

from mobile import theme

_CELL = 14
_GAP = 3
_WEEKDAY_INITIALS = ["M", "T", "W", "T", "F", "S", "S"]


def _hex_to_rgb(value: str):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def _cell_color(minutes: int, max_minutes: int, base_color: str) -> str:
    if minutes <= 0:
        return theme.CARD_BORDER
    t = 0.15 + 0.85 * min(1.0, minutes / max_minutes) if max_minutes else 0.15
    bg = _hex_to_rgb(theme.CARD_BORDER)
    fg = _hex_to_rgb(base_color)
    mixed = tuple(round(bg[i] + (fg[i] - bg[i]) * t) for i in range(3))
    return "#%02X%02X%02X" % mixed


def build(day_minutes: Dict[str, int], year: int, base_color: str = theme.ACCENT) -> ft.Control:
    """A horizontally-scrollable week-by-week heatmap for one category's year."""
    if not any(day_minutes.values()):
        return ft.Container(
            padding=20,
            content=ft.Text("No data yet for this category — start tracking it to see this fill in.",
                            color=theme.MUTED_TEXT, size=12),
        )

    jan1 = _dt.date(year, 1, 1)
    first_weekday = jan1.weekday()
    max_minutes = max(day_minutes.values())

    columns: Dict[int, Dict[int, int]] = {}
    month_label_at: Dict[int, str] = {}
    for date_str in sorted(day_minutes):
        d = _dt.date.fromisoformat(date_str)
        col = ((d - jan1).days + first_weekday) // 7
        columns.setdefault(col, {})[d.weekday()] = day_minutes[date_str]
        if d.day <= 7:
            month_label_at.setdefault(col, d.strftime("%b"))

    week_columns = []
    for col in range(max(columns) + 1):
        cells = []
        for row in range(7):
            minutes = columns.get(col, {}).get(row)
            if minutes is None:
                cells.append(ft.Container(width=_CELL, height=_CELL))
            else:
                cells.append(
                    ft.Container(
                        width=_CELL, height=_CELL, border_radius=3,
                        bgcolor=_cell_color(minutes, max_minutes, base_color),
                        tooltip=f"{minutes} min",
                    )
                )
        week_columns.append(
            ft.Column(spacing=_GAP, controls=[
                ft.Container(
                    height=14,
                    content=ft.Text(month_label_at.get(col, ""), size=9, color=theme.MUTED_TEXT),
                ),
                *cells,
            ])
        )

    weekday_labels = ft.Column(
        spacing=_GAP,
        controls=[ft.Container(height=14)] + [
            ft.Container(width=_CELL, height=_CELL,
                        content=ft.Text(name, size=9, color=theme.MUTED_TEXT))
            for name in _WEEKDAY_INITIALS
        ],
    )

    scroller = ft.Row(spacing=_GAP, scroll=ft.ScrollMode.AUTO, controls=week_columns)

    return ft.Row(
        vertical_alignment=ft.CrossAxisAlignment.START,
        controls=[weekday_labels, ft.Container(content=scroller, expand=True)],
    )


def build_states(day_states: Dict[str, str], year: int, base_color: str = theme.ACCENT) -> ft.Control:
    """Display a scheduled-routine heatmap with explicit completion states."""
    colors = {
        "completed": base_color,
        "missed": ft.Colors.with_opacity(0.65, theme.STOP_RED),
        "pending": theme.GOLD,
        "future": ft.Colors.with_opacity(0.18, theme.MUTED_TEXT),
        "unscheduled": ft.Colors.with_opacity(0.08, theme.MUTED_TEXT),
    }
    labels = {
        "completed": "Completed",
        "missed": "Missed",
        "pending": "Due today",
        "future": "Future",
        "unscheduled": "Not scheduled",
    }
    jan1 = _dt.date(year, 1, 1)
    first_weekday = jan1.weekday()
    columns: Dict[int, Dict[int, tuple[str, str]]] = {}
    month_label_at: Dict[int, str] = {}
    for date_str, state in sorted(day_states.items()):
        day = _dt.date.fromisoformat(date_str)
        col = ((day - jan1).days + first_weekday) // 7
        columns.setdefault(col, {})[day.weekday()] = (date_str, state)
        if day.day <= 7:
            month_label_at.setdefault(col, day.strftime("%b"))

    week_columns: list[ft.Control] = []
    for col in range(max(columns, default=-1) + 1):
        cells: list[ft.Control] = []
        for row in range(7):
            item = columns.get(col, {}).get(row)
            if item is None:
                cells.append(ft.Container(width=_CELL, height=_CELL))
                continue
            date_str, state = item
            cells.append(
                ft.Container(
                    width=_CELL,
                    height=_CELL,
                    border_radius=3,
                    bgcolor=colors.get(state, theme.CARD_BORDER),
                    tooltip=f"{date_str} · {labels.get(state, state.title())}",
                )
            )
        week_columns.append(
            ft.Column(
                spacing=_GAP,
                controls=[
                    ft.Container(
                        height=14,
                        content=ft.Text(
                            month_label_at.get(col, ""), size=9, color=theme.MUTED_TEXT
                        ),
                    ),
                    *cells,
                ],
            )
        )

    weekday_labels = ft.Column(
        spacing=_GAP,
        controls=[ft.Container(height=14)]
        + [
            ft.Container(
                width=_CELL,
                height=_CELL,
                content=ft.Text(name, size=9, color=theme.MUTED_TEXT),
            )
            for name in _WEEKDAY_INITIALS
        ],
    )
    scroller = ft.Row(spacing=_GAP, scroll=ft.ScrollMode.AUTO, controls=week_columns)
    legend = ft.Row(
        wrap=True,
        spacing=12,
        controls=[
            ft.Row(
                spacing=4,
                tight=True,
                controls=[
                    ft.Container(width=10, height=10, border_radius=2, bgcolor=colors[state]),
                    ft.Text(label, size=9, color=theme.MUTED_TEXT),
                ],
            )
            for state, label in (
                ("completed", "Done"),
                ("missed", "Missed"),
                ("pending", "Today"),
                ("unscheduled", "Off"),
                ("future", "Future"),
            )
        ],
    )
    return ft.Column(
        spacing=8,
        controls=[
            ft.Row(
                vertical_alignment=ft.CrossAxisAlignment.START,
                controls=[weekday_labels, ft.Container(content=scroller, expand=True)],
            ),
            legend,
        ],
    )
