"""
Chart drawing.

Pure matplotlib drawing helpers: each one takes a ``Figure``, a data
:class:`~app.charts.chart_data.Series`, and a :class:`ChartStyle` describing the
current colors, then draws onto the figure. They never create their own figure
(the embedding frame owns and reuses one) and never import ``pyplot`` (its
hidden global state leaks memory inside a long-running GUI).

When a series has no data every function draws a friendly "no data yet" message
instead of an empty set of axes.
"""

from __future__ import annotations

import calendar as _calendar
from dataclasses import dataclass
from datetime import date
from typing import Dict

from matplotlib.colors import to_rgb
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle

from app.charts.chart_data import Series


@dataclass
class ChartStyle:
    """The handful of colors a chart needs to match the app's current theme."""

    background: str      # figure background
    axes: str            # plot area background
    text: str            # titles, labels, tick numbers
    grid: str            # gridlines
    accent: str          # default line/bar color

    @classmethod
    def dark(cls) -> "ChartStyle":
        # Near-black to match the cinematic app background, with the crimson
        # brand accent as the default line/bar color.
        return cls(background="#0A0A0C", axes="#141418", text="#C7CCD1",
                   grid="#26262B", accent="#E11D2A")

    @classmethod
    def light(cls) -> "ChartStyle":
        # Same crimson brand accent as dark mode (theme.ACCENT is identical in
        # both appearance modes) — only the surfaces lighten.
        return cls(background="#F7F8FA", axes="#FFFFFF", text="#22272E",
                   grid="#DCE1E6", accent="#E11D2A")


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #
def _prepare_axes(fig: Figure, style: ChartStyle):
    """Clear the figure and return a single, freshly styled axes.

    Clearing and redrawing onto one long-lived figure (rather than making a new
    one each refresh) is what keeps memory flat as the data changes.
    """
    fig.clf()
    fig.patch.set_facecolor(style.background)
    ax = fig.add_subplot(111)
    ax.set_facecolor(style.axes)
    for spine in ax.spines.values():
        spine.set_color(style.grid)
    ax.tick_params(colors=style.text, labelsize=8)
    ax.xaxis.label.set_color(style.text)
    ax.yaxis.label.set_color(style.text)
    return ax


def _empty_message(fig: Figure, style: ChartStyle, message: str) -> None:
    """Draw a centered placeholder when there is nothing to plot."""
    fig.clf()
    fig.patch.set_facecolor(style.background)
    ax = fig.add_subplot(111)
    ax.set_facecolor(style.axes)
    ax.axis("off")
    ax.text(0.5, 0.5, message, ha="center", va="center",
            color=style.text, fontsize=11, wrap=True)


def _title(ax, text: str, style: ChartStyle) -> None:
    ax.set_title(text, color=style.text, fontsize=11, fontweight="bold", pad=10)


# --------------------------------------------------------------------------- #
# The individual charts
# --------------------------------------------------------------------------- #
def line_chart(fig: Figure, series: Series, style: ChartStyle,
               title: str, ylabel: str = "Hours") -> None:
    """A single line, e.g. daily productive hours."""
    if series.is_empty:
        _empty_message(fig, style, "No data yet — add entries to see this chart.")
        return
    ax = _prepare_axes(fig, style)
    ax.plot(series.labels, series.values, color=style.accent,
            marker="o", markersize=4, linewidth=2)
    ax.grid(True, color=style.grid, linewidth=0.5, alpha=0.6)
    ax.set_ylabel(ylabel)
    _title(ax, title, style)
    _rotate_xticks(ax)
    fig.tight_layout()


def bar_chart(fig: Figure, series: Series, style: ChartStyle,
              title: str, ylabel: str = "Hours") -> None:
    """A simple vertical bar chart with value labels on top of each bar."""
    if series.is_empty:
        _empty_message(fig, style, "No data yet — add entries to see this chart.")
        return
    ax = _prepare_axes(fig, style)
    colors = series.colors if series.colors else [style.accent] * len(series.values)
    bars = ax.bar(series.labels, series.values, color=colors)
    ax.grid(True, axis="y", color=style.grid, linewidth=0.5, alpha=0.6)
    ax.set_ylabel(ylabel)
    _title(ax, title, style)
    # Put the number above each bar so the exact value is readable.
    for bar, value in zip(bars, series.values):
        if value > 0:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                    f"{value:g}", ha="center", va="bottom",
                    color=style.text, fontsize=7)
    _rotate_xticks(ax)
    fig.tight_layout()


def pie_chart(fig: Figure, series: Series, style: ChartStyle, title: str) -> None:
    """A category-distribution pie using each category's own color."""
    if series.is_empty:
        _empty_message(fig, style, "No data yet — add entries to see this chart.")
        return
    fig.clf()
    fig.patch.set_facecolor(style.background)
    ax = fig.add_subplot(111)
    ax.set_facecolor(style.background)
    colors = series.colors if series.colors else None
    wedges, texts, autotexts = ax.pie(
        series.values, labels=series.labels, colors=colors,
        autopct="%1.0f%%", startangle=90,
        textprops={"color": style.text, "fontsize": 8},
    )
    for autotext in autotexts:
        autotext.set_color("#FFFFFF")
        autotext.set_fontsize(7)
    ax.axis("equal")
    _title(ax, title, style)
    fig.tight_layout()


def trend_chart(fig: Figure, series: Series, moving_avg, style: ChartStyle,
                title: str) -> None:
    """Daily values as faint dots plus a bold 7-day moving-average line."""
    if series.is_empty:
        _empty_message(fig, style, "No data yet — add entries to see this chart.")
        return
    ax = _prepare_axes(fig, style)
    ax.plot(series.labels, series.values, color=style.accent, alpha=0.35,
            marker="o", markersize=3, linewidth=1, label="Daily")
    ax.plot(series.labels, moving_avg, color="#F59E0B", linewidth=2.2,
            label="7-day average")
    ax.grid(True, color=style.grid, linewidth=0.5, alpha=0.6)
    ax.set_ylabel("Hours")
    ax.legend(facecolor=style.axes, edgecolor=style.grid, labelcolor=style.text,
              fontsize=8)
    _title(ax, title, style)
    _rotate_xticks(ax)
    fig.tight_layout()


def heatmap_calendar(fig: Figure, day_minutes: Dict[str, int], year: int,
                      base_color: str, style: ChartStyle, title: str) -> None:
    """A GitHub-contributions-style year grid: one small square per day.

    Rows are weekdays (Monday at the top, matching the rest of the app's
    calendar), columns are weeks of ``year``. Each square is shaded from the
    empty background up to ``base_color`` at full strength, scaled by that
    day's minutes against the busiest day found in the data.
    """
    if not any(day_minutes.values()):
        _empty_message(fig, style, "No data yet for this category — start tracking it to see this heatmap fill in.")
        return

    jan1 = date(year, 1, 1)
    first_weekday = jan1.weekday()  # 0=Mon .. 6=Sun
    max_minutes = max(day_minutes.values()) or 1
    base_rgb = to_rgb(base_color)
    bg_rgb = to_rgb(style.axes)

    def cell_color(minutes: int) -> tuple:
        if minutes <= 0:
            return style.axes
        # A floor keeps even a short session visibly distinct from "empty".
        t = 0.15 + 0.85 * min(1.0, minutes / max_minutes)
        return tuple(bg + (base - bg) * t for bg, base in zip(bg_rgb, base_rgb))

    fig.clf()
    fig.patch.set_facecolor(style.background)
    ax = fig.add_subplot(111)
    ax.set_facecolor(style.background)

    max_col = 0
    month_first_col: Dict[int, int] = {}
    for date_str, minutes in day_minutes.items():
        day = date.fromisoformat(date_str)
        col = ((day - jan1).days + first_weekday) // 7
        row = day.weekday()
        max_col = max(max_col, col)
        month_first_col.setdefault(day.month, col)
        ax.add_patch(Rectangle((col, 6 - row), 0.86, 0.86,
                                facecolor=cell_color(minutes),
                                edgecolor=style.grid, linewidth=0.4))

    ax.set_xlim(-0.6, max_col + 1.4)
    ax.set_ylim(-0.5, 7.5)
    ax.set_aspect("equal")

    ax.set_yticks([6 - r + 0.43 for r in range(7)])
    ax.set_yticklabels(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
                       fontsize=7, color=style.text)
    ax.set_xticks([c + 0.43 for c in month_first_col.values()])
    ax.set_xticklabels([_calendar.month_abbr[m] for m in month_first_col.keys()],
                       fontsize=7, color=style.text)
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    _title(ax, title, style)
    fig.tight_layout()


def _rotate_xticks(ax) -> None:
    """Thin out and tilt x labels so they never overlap on a crowded axis."""
    labels = ax.get_xticklabels()
    # If there are many labels, show roughly ten evenly spaced ones.
    if len(labels) > 12:
        step = max(1, len(labels) // 10)
        for i, label in enumerate(labels):
            label.set_visible(i % step == 0)
    for label in labels:
        label.set_rotation(45)
        label.set_horizontalalignment("right")
