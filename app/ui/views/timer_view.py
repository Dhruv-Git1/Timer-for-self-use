"""
The Timer screen — the app's home screen.

A big live-updating clock, and below it a grid of your categories.

Starting a session is a deliberate two-step action, so a stray click can never
begin real tracking by accident: tapping a category while idle only *selects*
it (a highlighted border) — pressing the Start button then begins the timer.
Once a timer is running, tapping a *different* category is a fast one-click
"switch activity" (it saves the current session and immediately starts the new
one) — no confirmation needed there, since a session is already being tracked
either way. Stop saves the current session; Discard throws it away.
"""

from __future__ import annotations

import customtkinter as ctk

from app.ui import theme
from app.ui.views.base_view import BaseView
from app.ui.widgets.confirm_dialog import ask_confirm
from app.ui.widgets.goals_form import GoalsForm
from app.utils import time_utils
from app.utils.event_bus import bus, TIMER_STATE_CHANGED

_STOP_RED = "#D0463B"


class _CategoryTile(ctk.CTkFrame):
    """A clickable card for one category.

    Three looks, depending on ``mode``:
      * ``"tracking"``  — this category's timer is actively running (filled
        with the category's own color, a "tracking" badge).
      * ``"selected"``  — idle, but this is the category chosen to start next
        (a colored border, waiting on the Start button).
      * ``"idle"``      — the plain, unselected look.
    """

    def __init__(self, master, category, mode: str, on_click) -> None:
        is_tracking = mode == "tracking"
        is_selected = mode == "selected"

        super().__init__(
            master, corner_radius=10, cursor="hand2",
            fg_color=(category.color if is_tracking else theme.CARD_COLOR),
            border_width=3 if is_selected else (2 if is_tracking else 1),
            border_color=(category.color if is_selected else
                         ("white" if is_tracking else theme.CARD_BORDER)),
        )
        text_color = "white" if is_tracking else ("gray10", "gray90")
        dot_color = "white" if is_tracking else category.color

        dot = ctk.CTkLabel(self, text="●", text_color=dot_color, font=ctk.CTkFont(size=18))
        dot.pack(side="left", padx=(14, 4), pady=14)
        name = ctk.CTkLabel(
            self, text=category.name, anchor="w", text_color=text_color,
            font=ctk.CTkFont(size=14, weight="bold" if (is_tracking or is_selected) else "normal"),
        )
        name.pack(side="left", fill="x", expand=True, padx=(0, 10), pady=14)

        clickables = [self, dot, name]
        if is_tracking:
            badge = ctk.CTkLabel(self, text="● tracking", text_color="white",
                                 font=ctk.CTkFont(size=10, weight="bold"))
            badge.pack(side="right", padx=(0, 14))
            clickables.append(badge)
        elif is_selected:
            badge = ctk.CTkLabel(self, text="✓ selected", text_color=category.color,
                                 font=ctk.CTkFont(size=10, weight="bold"))
            badge.pack(side="right", padx=(0, 14))
            clickables.append(badge)

        for widget in clickables:
            widget.bind("<Button-1>", lambda _e, cid=category.id: on_click(cid))


class TimerView(BaseView):
    title = "Timer"

    def __init__(self, master, context) -> None:
        super().__init__(master, context)
        self._tick_job: str | None = None
        self._status_job: str | None = None
        # Only meaningful while idle: the category tapped, waiting for Start.
        # Cleared whenever a timer actually starts, stops, or is discarded.
        self._selected_category_id: int | None = None
        bus.subscribe(TIMER_STATE_CHANGED, self._on_timer_state_changed)
        self._build()

    # ------------------------------------------------------------------ #
    # Static layout
    # ------------------------------------------------------------------ #
    def _build(self) -> None:
        ctk.CTkLabel(self, text="Timer",
                     font=ctk.CTkFont(size=26, weight="bold")).pack(
            anchor="w", padx=24, pady=(20, 8))

        # The big clock card.
        card = ctk.CTkFrame(self, corner_radius=16, fg_color=theme.CARD_COLOR,
                            border_width=1, border_color=theme.CARD_BORDER)
        card.pack(fill="x", padx=24, pady=(0, 10))

        self.elapsed_label = ctk.CTkLabel(
            card, text="0:00:00", font=ctk.CTkFont(size=64, weight="bold"))
        self.elapsed_label.pack(pady=(28, 4))

        self.subtitle_label = ctk.CTkLabel(
            card, text="Choose a category below, then press Start",
            font=ctk.CTkFont(size=15), text_color=theme.MUTED_TEXT)
        self.subtitle_label.pack(pady=(0, 6))

        # Idle controls: a Start button, enabled only once a category is
        # selected. Shown only while idle.
        self.idle_controls = ctk.CTkFrame(card, fg_color="transparent")
        self.start_btn = ctk.CTkButton(
            self.idle_controls, text="▶  Start", width=160, height=42,
            fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
            font=ctk.CTkFont(size=15, weight="bold"), command=self._on_start,
            state="disabled",
        )
        self.start_btn.pack(padx=6)

        # Running controls: Stop + a de-emphasized Discard. Shown only while
        # a timer is actually running.
        self.running_controls = ctk.CTkFrame(card, fg_color="transparent")
        self.stop_btn = ctk.CTkButton(
            self.running_controls, text="■  Stop", width=160, height=42,
            fg_color=_STOP_RED, hover_color="#B23B31",
            font=ctk.CTkFont(size=15, weight="bold"), command=self._on_stop)
        self.stop_btn.pack(side="left", padx=6)
        self.discard_btn = ctk.CTkButton(
            self.running_controls, text="Discard this session", width=160, height=24,
            fg_color="transparent", hover_color=("gray80", "gray25"),
            text_color=theme.MUTED_TEXT, font=ctk.CTkFont(size=11),
            command=self._on_discard)
        self.discard_btn.pack(side="left", padx=6)

        self.status_label = ctk.CTkLabel(card, text="", text_color=theme.MUTED_TEXT,
                                         font=ctk.CTkFont(size=12))
        self.status_label.pack(pady=(0, 14))

        # Today's goal progress, one row per category with a daily target.
        goals_header = ctk.CTkFrame(self, fg_color="transparent")
        goals_header.pack(fill="x", padx=24, pady=(6, 0))
        ctk.CTkLabel(goals_header, text="Today's Goals",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(side="left")
        ctk.CTkButton(goals_header, text="✎  Edit goals", width=110, height=26,
                      fg_color=theme.NEUTRAL_BTN, hover_color=theme.NEUTRAL_BTN_HOVER,
                      text_color=("gray10", "gray90"), font=ctk.CTkFont(size=11),
                      command=self._on_edit_goals).pack(side="right")
        self.goals_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.goals_frame.pack(fill="x", padx=24, pady=(4, 6))

        # Category grid.
        ctk.CTkLabel(self, text="Categories",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(
            anchor="w", padx=24, pady=(10, 4))
        self.grid_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.grid_frame.pack(fill="both", expand=True, padx=24, pady=(0, 20))
        for col in range(3):
            self.grid_frame.grid_columnconfigure(col, weight=1, uniform="timer_cats")

    # ------------------------------------------------------------------ #
    # Lifecycle: tick only while this screen is actually on-screen
    # ------------------------------------------------------------------ #
    def on_show(self) -> None:
        super().on_show()          # calls refresh()
        self._schedule_tick()

    def on_hide(self) -> None:
        super().on_hide()
        if self._tick_job is not None:
            self.after_cancel(self._tick_job)
            self._tick_job = None

    def _schedule_tick(self) -> None:
        self._tick_job = self.after(1000, self._tick)

    def _tick(self) -> None:
        if not self._is_active:
            return  # view was hidden between scheduling and firing
        self._update_elapsed_label()
        self._schedule_tick()

    def _on_timer_state_changed(self, **_payload) -> None:
        if self._is_active:
            self.refresh()

    # ------------------------------------------------------------------ #
    # Actions
    # ------------------------------------------------------------------ #
    def _on_category_click(self, category_id: int) -> None:
        state = self.ctx.timer_service.current_state()
        if state.is_active:
            # Running: a different category is a fast, deliberate one-click
            # switch (already tracking something, no extra confirmation
            # needed). The already-tracked tile is a no-op.
            if category_id != state.category_id:
                self.ctx.timer_service.start(category_id)
        else:
            # Idle: a tap only selects — it never starts real tracking by
            # itself. You have to press Start.
            self._selected_category_id = category_id
        self.refresh()

    def _on_start(self) -> None:
        if self._selected_category_id is None:
            return
        self.ctx.timer_service.start(self._selected_category_id)
        self._selected_category_id = None
        self.refresh()

    def _on_stop(self) -> None:
        ok, msg, _entry_id = self.ctx.timer_service.stop()
        self._show_status(msg or "Session saved.")
        self.refresh()

    def _on_discard(self) -> None:
        state = self.ctx.timer_service.current_state()
        if not state.is_active:
            return
        elapsed = time_utils.fmt_clock(state.elapsed_seconds)
        if ask_confirm(self, "Discard session?",
                       f"Discard the last {elapsed}? This cannot be undone.",
                       confirm_text="Discard", confirm_color=_STOP_RED):
            self.ctx.timer_service.discard()
            self._show_status("Session discarded.")
            self.refresh()

    def _on_edit_goals(self) -> None:
        GoalsForm(self, self.ctx, on_saved=self.refresh)

    def _show_status(self, message: str) -> None:
        self.status_label.configure(text=message)
        if self._status_job is not None:
            self.after_cancel(self._status_job)
        self._status_job = self.after(5000, lambda: self.status_label.configure(text=""))

    # ------------------------------------------------------------------ #
    # Refresh (structural: idle/selected/running chrome + category grid)
    # ------------------------------------------------------------------ #
    def refresh(self) -> None:
        state = self.ctx.timer_service.current_state()
        categories = self.ctx.category_service.list_categories()
        category_ids = {c.id for c in categories}

        # A selected category that no longer exists (e.g. archived from
        # another screen while idle) can't stay selected.
        if self._selected_category_id not in category_ids:
            self._selected_category_id = None

        active_category = next((c for c in categories if c.id == state.category_id), None)
        selected_category = next(
            (c for c in categories if c.id == self._selected_category_id), None)

        self._update_elapsed_label(state)
        self._refresh_goals()

        if state.is_active and active_category is not None:
            self.subtitle_label.configure(
                text=f"Tracking: {active_category.name}", text_color=active_category.color)
            self.elapsed_label.configure(text_color=active_category.color)
            self.idle_controls.pack_forget()
            self.running_controls.pack(pady=(0, 10))
        else:
            self.elapsed_label.configure(text_color=("gray10", "gray90"))
            self.running_controls.pack_forget()
            self.idle_controls.pack(pady=(0, 10))
            if selected_category is not None:
                self.subtitle_label.configure(
                    text=f"Ready to start: {selected_category.name}",
                    text_color=selected_category.color)
                self.start_btn.configure(state="normal", fg_color=selected_category.color,
                                         hover_color=selected_category.color)
            else:
                self.subtitle_label.configure(
                    text="Choose a category below, then press Start",
                    text_color=theme.MUTED_TEXT)
                self.start_btn.configure(state="disabled", fg_color=theme.ACCENT,
                                         hover_color=theme.ACCENT_HOVER)

        for child in self.grid_frame.winfo_children():
            child.destroy()

        if not categories:
            ctk.CTkLabel(self.grid_frame,
                         text="No categories yet — add one on the Categories screen.",
                         text_color=theme.MUTED_TEXT).grid(row=0, column=0, columnspan=3,
                                                            sticky="w", pady=10)
            return

        for index, category in enumerate(categories):
            if state.is_active:
                mode = "tracking" if category.id == state.category_id else "idle"
            else:
                mode = "selected" if category.id == self._selected_category_id else "idle"
            tile = _CategoryTile(self.grid_frame, category, mode, on_click=self._on_category_click)
            tile.grid(row=index // 3, column=index % 3, padx=6, pady=6, sticky="ew")

    def _refresh_goals(self) -> None:
        """Redraw today's per-category goal progress rows."""
        for child in self.goals_frame.winfo_children():
            child.destroy()

        summary = self.ctx.dashboard_service.build_summary(time_utils.today_str())
        goals = [p for p in summary.progress if p.target_minutes > 0]
        if not goals:
            ctk.CTkLabel(self.goals_frame,
                         text="No daily goals set yet — click Edit goals to add one.",
                         text_color=theme.MUTED_TEXT, font=ctk.CTkFont(size=12)).pack(
                anchor="w", pady=4)
            return

        for prog in goals:
            row = ctk.CTkFrame(self.goals_frame, fg_color=theme.CARD_COLOR, corner_radius=8)
            row.pack(fill="x", pady=3)
            ctk.CTkLabel(row, text="●", text_color=prog.color,
                         font=ctk.CTkFont(size=14)).pack(side="left", padx=(12, 4), pady=8)
            ctk.CTkLabel(row, text=prog.name, width=120, anchor="w").pack(side="left")
            bar = ctk.CTkProgressBar(row, progress_color=prog.color)
            bar.set(prog.completion_pct / 100)
            bar.pack(side="left", fill="x", expand=True, padx=8)
            ctk.CTkLabel(row, text=f"{prog.actual_label} / {prog.target_label}",
                         width=110, text_color=theme.MUTED_TEXT,
                         font=ctk.CTkFont(size=11)).pack(side="left", padx=(0, 12))

    def _update_elapsed_label(self, state=None) -> None:
        """Cheap per-second update: just the clock text, no widget rebuilding."""
        if state is None:
            state = self.ctx.timer_service.current_state()
        self.elapsed_label.configure(text=time_utils.fmt_clock(state.elapsed_seconds))
