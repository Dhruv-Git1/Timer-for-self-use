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
    if series.is_empty:
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
    for values, extra_color in (extra_lines or []):
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
    """Bars use a subtle top-to-bottom shade when they all share one accent
    color (a single flat gradient reads as premium); per-category colors
    (``series.colors``) stay flat, since a gradient on every one of several
    hues at once would look busy rather than classic."""
    if series.is_empty:
        return _empty()

    max_value = max(series.values) or 1
    if series.colors:
        rods = [fc.BarChartRod(to_y=v, color=series.colors[i], width=18,
                               border_radius=ft.BorderRadius.all(4))
                for i, v in enumerate(series.values)]
    else:
        gradient = ft.LinearGradient(
            begin=ft.Alignment.BOTTOM_CENTER, end=ft.Alignment.TOP_CENTER,
            colors=[theme.ACCENT_DEEP, color],
        )
        rods = [fc.BarChartRod(to_y=v, gradient=gradient, width=18,
                               border_radius=ft.BorderRadius.all(4))
                for v in series.values]
    groups = [fc.BarChartGroup(x=i, rods=[rod]) for i, rod in enumerate(rods)]
    bottom_axis = fc.ChartAxis(
        labels=[fc.ChartAxisLabel(value=i, label=label)
                for i, label in _thinned_labels(series.labels).items()],
        label_size=20,
    )
    return ft.Container(
        height=height, padding=10,
        content=fc.BarChart(groups=groups, min_y=0, max_y=max_value * 1.2,
                            bottom_axis=bottom_axis, interactive=True),
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
