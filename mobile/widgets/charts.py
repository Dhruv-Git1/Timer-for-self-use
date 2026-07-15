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
    pairs plotted on the same axes — e.g. a moving-average overlay."""
    if series.is_empty:
        return _empty()

    data_series = [fc.LineChartData(
        points=[fc.LineChartDataPoint(x=i, y=v) for i, v in enumerate(series.values)],
        color=color, stroke_width=2.5,
    )]
    all_values = list(series.values)
    for values, extra_color in (extra_lines or []):
        data_series.append(fc.LineChartData(
            points=[fc.LineChartDataPoint(x=i, y=v) for i, v in enumerate(values)],
            color=extra_color, stroke_width=2.5,
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
    if series.is_empty:
        return _empty()

    colors = series.colors if series.colors else [color] * len(series.values)
    max_value = max(series.values) or 1
    groups = [
        fc.BarChartGroup(x=i, rods=[fc.BarChartRod(to_y=v, color=colors[i], width=18,
                                                   border_radius=ft.BorderRadius.all(4))])
        for i, v in enumerate(series.values)
    ]
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
    sections = [
        fc.PieChartSection(
            value=v, color=palette[i], radius=70,
            title=f"{series.labels[i]}\n{v / total * 100:.0f}%",
        )
        for i, v in enumerate(series.values)
    ]
    return ft.Container(
        height=height,
        content=fc.PieChart(sections=sections, sections_space=2, center_space_radius=30),
    )
