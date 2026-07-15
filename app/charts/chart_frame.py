"""
A CustomTkinter widget that hosts a matplotlib chart.

It owns exactly one matplotlib Figure and one canvas for its whole life and
reuses them on every redraw. That reuse matters: repeatedly creating new figures
or canvases inside a running Tkinter app slowly leaks memory and widgets, so
instead we hand a drawing function the same figure each time and just redraw.
"""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


class ChartFrame(ctk.CTkFrame):
    """Embeds one matplotlib figure inside the CustomTkinter layout."""

    def __init__(
        self,
        master,
        width_inches: float = 5.0,
        height_inches: float = 3.2,
        **kwargs,
    ) -> None:
        super().__init__(master, **kwargs)

        # A fixed dpi of 100 plus a size given in inches keeps charts crisp and
        # correctly sized on Windows high-DPI displays (where CustomTkinter and
        # matplotlib would otherwise fight over scaling and blur the image).
        self.figure = Figure(figsize=(width_inches, height_inches), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.figure, master=self)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    def draw(self, plot_fn: Callable[[Figure], None]) -> None:
        """Redraw the chart.

        ``plot_fn`` receives this frame's figure, clears it, and draws the new
        chart onto it. ``draw_idle`` then schedules an efficient repaint.
        """
        plot_fn(self.figure)
        self.canvas.draw_idle()

    def save_png(self, path: str) -> None:
        """Save the current chart to a PNG file (used by a 'Save image' button)."""
        self.figure.savefig(path, facecolor=self.figure.get_facecolor(), dpi=150)
