"""
General-purpose Flet-native charts (line/bar/pie) over a chart_data.Series —
the mobile equivalent of app/charts/chart_factory.py, rendered by Flutter
instead of matplotlib. Every function takes the exact same Series shape the
desktop charts already consume, so numbers can never disagree between them.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import flet as ft
import flet_charts as fc

from app.charts.chart_data import Series
from mobile import theme


# A warm-only palette keeps every bar chart visually tied to the app's
# crimson "get moving" identity.  The small tip variations distinguish
# adjacent categories without falling back to unrelated blues and greens.
_FIRE_TIPS = ("#FF4655", "#FF641F", "#FF7A1A", "#FFB020")
_EMBER = "#5F0D14"
_FLAME_EDGE = "#FFC06A"


def _fire_gradient(index: int = 0) -> ft.LinearGradient:
    return ft.LinearGradient(
        begin=ft.Alignment.BOTTOM_CENTER,
        end=ft.Alignment.TOP_CENTER,
        colors=[_EMBER, theme.ACCENT_DEEP, theme.ACCENT, _FIRE_TIPS[index % len(_FIRE_TIPS)]],
        stops=[0.0, 0.28, 0.72, 1.0],
    )


def _bar_width(item_count: int) -> int:
    """Keep weekly bars bold while preventing dense monthly charts colliding."""
    if item_count <= 7:
        return 26
    if item_count <= 12:
        return 20
    if item_count <= 20:
        return 13
    return 8


def _thinned_labels(labels: List[str], max_shown: int = 8) -> Dict[int, str]:
    """Map label-index -> text, showing at most ``max_shown`` evenly spaced —
    the mobile equivalent of chart_factory._rotate_xticks's thinning."""
    if len(labels) <= max_shown:
        return dict(enumerate(labels))
    step = max(1, len(labels) // max_shown)
    return {i: label for i, label in enumerate(labels) if i % step == 0}


def _empty(message: str = "No data yet — add entries to see this chart.") -> ft.Control:
    return ft.Container(padding=20, content=ft.Text(message, color=theme.MUTED_TEXT, size=12))


def line_chart(series: Series, color: str = theme.ACCENT, height: int = 220,
               extra_lines: Optional[List[Tuple[List[float], str]]] = None) -> ft.Control:
    """A line chart. ``extra_lines`` is an optional list of (values, color)
    pairs plotted on the same axes — e.g. a moving-average overlay.

    Curved with a faint gradient fade beneath the primary line (restrained —
    a premium-dashboard touch, not a saturated glow) — the mobile equivalent
    of a matplotlib fill_between with low alpha."""
    extra_lines = extra_lines or []
    has_extra_data = any(values and any(value != 0 for value in values) for values, _ in extra_lines)
    if not series.values or (series.is_empty and not has_extra_data):
        return _empty()

    data_series = [fc.LineChartData(
        points=[fc.LineChartDataPoint(x=i, y=v) for i, v in enumerate(series.values)],
        color=color, stroke_width=2.5, curved=True, rounded_stroke_cap=True,
        below_line_gradient=ft.LinearGradient(
            begin=ft.Alignment.TOP_CENTER, end=ft.Alignment.BOTTOM_CENTER,
            colors=[ft.Colors.with_opacity(0.22, color), ft.Colors.with_opacity(0.0, color)],
        ),
    )]
    all_values = list(series.values)
    for values, extra_color in extra_lines:
        data_series.append(fc.LineChartData(
            points=[fc.LineChartDataPoint(x=i, y=v) for i, v in enumerate(values)],
            color=extra_color, stroke_width=2, curved=True,
        ))
        all_values += list(values)

    bottom_axis = fc.ChartAxis(
        labels=[fc.ChartAxisLabel(value=i, label=label)
                for i, label in _thinned_labels(series.labels).items()],
        label_size=20,
    )
    return ft.Container(
        height=height, padding=10,
        content=fc.LineChart(
            data_series=data_series,
            min_y=min(0, min(all_values)) if all_values else 0,
            max_y=(max(all_values) * 1.15) if all_values else 1,
            bottom_axis=bottom_axis,
            interactive=True,
        ),
    )


def bar_chart(series: Series, color: str = theme.ACCENT, height: int = 200) -> ft.Control:
    """Render bold, fire-themed achievement bars.

    ``color`` remains in the public signature for compatibility with existing
    callers.  Bar charts intentionally use the shared crimson/fire palette so
    category colors cannot make the graph feel disconnected from the app.
    """
    if series.is_empty:
        return _empty()

    max_value = max(series.values) or 1
    chart_max = max(1, max_value * 1.18)
    width = _bar_width(len(series.values))
    bar_radius = ft.BorderRadius.only(
        top_left=7, top_right=7, bottom_left=2, bottom_right=2,
    )
    rods = [
        fc.BarChartRod(
            to_y=value,
            width=width,
            gradient=_fire_gradient(index if series.colors else 1),
            border_radius=bar_radius,
            border_side=ft.BorderSide(
                width=0.8,
                color=ft.Colors.with_opacity(0.38, _FLAME_EDGE),
            ),
            # The dim full-height rail makes each rod feel like a goal meter
            # and keeps zero/low-value days legible on the black canvas.
            bg_from_y=0,
            bg_to_y=chart_max,
            bgcolor=ft.Colors.with_opacity(0.08, _FLAME_EDGE),
        )
        for index, value in enumerate(series.values)
    ]
    groups = [fc.BarChartGroup(x=i, rods=[rod]) for i, rod in enumerate(rods)]
    bottom_axis = fc.ChartAxis(
        labels=[fc.ChartAxisLabel(value=i, label=label)
                for i, label in _thinned_labels(series.labels).items()],
        label_size=20,
    )
    return ft.Container(
        height=height, padding=10,
        content=fc.BarChart(
            groups=groups,
            min_y=0,
            max_y=chart_max,
            bottom_axis=bottom_axis,
            group_spacing=10,
            horizontal_grid_lines=fc.ChartGridLines(
                color=ft.Colors.with_opacity(0.09, _FLAME_EDGE),
                width=1,
                dash_pattern=[3, 6],
            ),
            animation=ft.Animation(480, ft.AnimationCurve.EASE_OUT),
            interactive=True,
        ),
    )


def pie_chart(series: Series, height: int = 240) -> ft.Control:
    if series.is_empty:
        return _empty()

    palette = series.colors if series.colors else [theme.ACCENT] * len(series.values)
    total = sum(series.values) or 1
    # A thin near-black border between wedges reads as clean/classic (Apple
    # Health-style ring separation) rather than slices bleeding together.
    border = ft.BorderSide(width=2, color=theme.BG)
    title_style = ft.TextStyle(size=11, weight=ft.FontWeight.BOLD, color=theme.HEADLINE)
    sections = [
        fc.PieChartSection(
            value=v, color=palette[i], radius=70, border_side=border,
            title=f"{series.labels[i]}\n{v / total * 100:.0f}%",
            title_style=title_style,
        )
        for i, v in enumerate(series.values)
    ]
    return ft.Container(
        height=height,
        content=fc.PieChart(sections=sections, sections_space=2, center_space_radius=30),
    )
