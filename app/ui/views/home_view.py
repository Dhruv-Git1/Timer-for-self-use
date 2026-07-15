"""
The Home screen — the cinematic landing page.

The hero banner up top, then a row of headline stats, a "MISSION TARGETS" panel
showing today's progress toward each daily goal, and big launch buttons into the
rest of the app. This is what greets you when the app opens: a motivating,
at-a-glance picture of the day plus one-tap jumps to where the work happens.
"""

from __future__ import annotations

import customtkinter as ctk

from app.ui import theme
from app.ui.views.base_view import BaseView
from app.ui.widgets.goals_form import GoalsForm
from app.ui.widgets.hero_banner import HeroBanner
from app.ui.widgets.stat_card import StatCard
from app.utils import time_utils


class HomeView(BaseView):
    title = "Home"

    def __init__(self, master, context) -> None:
        super().__init__(master, context)
        self._cards: dict[str, StatCard] = {}
        self._build()

    # ------------------------------------------------------------------ #
    # Static layout
    # ------------------------------------------------------------------ #
    def _build(self) -> None:
        self.hero = HeroBanner(self, self.ctx)
        self.hero.pack(fill="x", side="top")

        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=24, pady=(14, 20))

        # Headline stat cards.
        cards = ctk.CTkFrame(body, fg_color="transparent")
        cards.pack(fill="x")
        for col in range(4):
            cards.grid_columnconfigure(col, weight=1, uniform="homecards")
        specs = [
            ("today", "Today", "#E11D2A"),
            ("streak", "Streak", "#E0A100"),
            ("sessions", "Sessions", "#3B82F6"),
            ("week", "This Week", "#2E9E5B"),
        ]
        for i, (key, label, accent) in enumerate(specs):
            card = StatCard(cards, title=label, accent=accent)
            card.grid(row=0, column=i, padx=6, pady=6, sticky="ew")
            self._cards[key] = card

        # Two columns: mission targets (left), actions (right).
        panel = ctk.CTkFrame(body, fg_color="transparent")
        panel.pack(fill="both", expand=True, pady=(8, 0))
        panel.grid_columnconfigure(0, weight=3, uniform="homepanel")
        panel.grid_columnconfigure(1, weight=2, uniform="homepanel")

        # -- Mission targets card -------------------------------------- #
        targets_card = ctk.CTkFrame(panel, corner_radius=12, fg_color=theme.CARD_COLOR,
                                    border_width=1, border_color=theme.CARD_BORDER)
        targets_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        targets_header = ctk.CTkFrame(targets_card, fg_color="transparent")
        targets_header.pack(fill="x", padx=18, pady=(16, 8))
        ctk.CTkLabel(targets_header, text=theme.spaced("MISSION TARGETS"),
                     font=ctk.CTkFont(family=theme.MONO_FAMILY,
                                      size=theme.SECTION_LABEL_SIZE, weight="bold"),
                     text_color=theme.MONO_LABEL).pack(side="left")
        ctk.CTkButton(targets_header, text="✎  Edit goals", width=100, height=24,
                      fg_color=theme.NEUTRAL_BTN, hover_color=theme.NEUTRAL_BTN_HOVER,
                      text_color=("gray10", "gray90"), font=ctk.CTkFont(size=11),
                      command=self._on_edit_goals).pack(side="right")
        self.targets_body = ctk.CTkFrame(targets_card, fg_color="transparent")
        self.targets_body.pack(fill="both", expand=True, padx=18, pady=(0, 16))

        # -- Actions column -------------------------------------------- #
        actions = ctk.CTkFrame(panel, fg_color="transparent")
        actions.grid(row=0, column=1, sticky="nsew")

        ctk.CTkButton(
            actions, text="▶   LAUNCH DASHBOARD", height=64, corner_radius=12,
            font=ctk.CTkFont(family=theme.DISPLAY_FAMILY, size=17, weight="bold"),
            command=lambda: self._go("dashboard"),
        ).pack(fill="x", pady=(0, 10))

        self._quick_card(actions, "📈  Graphs", "Trends, streaks & totals", "graphs")
        self._quick_card(actions, "🗂  Today's Entries", "Review & fix your log", "entries")

    def _quick_card(self, parent, title: str, subtitle: str, view_key: str) -> None:
        card = ctk.CTkFrame(parent, corner_radius=12, fg_color=theme.CARD_COLOR,
                            border_width=1, border_color=theme.CARD_BORDER,
                            cursor="hand2")
        card.pack(fill="x", pady=(0, 10))
        title_lbl = ctk.CTkLabel(card, text=title, anchor="w",
                                 font=ctk.CTkFont(size=15, weight="bold"))
        title_lbl.pack(anchor="w", padx=16, pady=(12, 0))
        sub_lbl = ctk.CTkLabel(card, text=subtitle, anchor="w", text_color=theme.MUTED_TEXT,
                               font=ctk.CTkFont(family=theme.MONO_FAMILY, size=11))
        sub_lbl.pack(anchor="w", padx=16, pady=(0, 12))
        for widget in (card, title_lbl, sub_lbl):
            widget.bind("<Button-1>", lambda _e, k=view_key: self._go(k))

    def _go(self, view_key: str) -> None:
        if self.app_window is not None:
            self.app_window.show_view(view_key)

    def _on_edit_goals(self) -> None:
        GoalsForm(self, self.ctx, on_saved=self.refresh)

    # ------------------------------------------------------------------ #
    # Lifecycle: the hero ticks only while this screen is visible
    # ------------------------------------------------------------------ #
    def on_show(self) -> None:
        super().on_show()      # calls refresh()
        self.hero.start()

    def on_hide(self) -> None:
        super().on_hide()
        self.hero.stop()

    # ------------------------------------------------------------------ #
    # Refresh
    # ------------------------------------------------------------------ #
    def refresh(self) -> None:
        today = time_utils.today_str()
        summary = self.ctx.dashboard_service.build_summary(today)
        week = self.ctx.stats_service.weekly(today)

        self._cards["today"].update_values(
            summary.productive_label, subtitle="productive")
        self._cards["streak"].update_values(
            str(summary.current_streak),
            subtitle="day" if summary.current_streak == 1 else "days")
        self._cards["sessions"].update_values(
            str(summary.session_count), subtitle="logged today")
        self._cards["week"].update_values(
            time_utils.fmt_duration(week.total_productive_minutes), subtitle="this week")

        # Mission targets: today's progress toward each category goal.
        for child in self.targets_body.winfo_children():
            child.destroy()

        goals = [p for p in summary.progress if p.target_minutes > 0]
        if not goals:
            ctk.CTkLabel(self.targets_body,
                         text="No daily goals set yet. Add targets on the Categories screen.",
                         text_color=theme.MUTED_TEXT,
                         font=ctk.CTkFont(family=theme.MONO_FAMILY, size=11)).pack(
                anchor="w", pady=8)
            return

        for prog in goals:
            row = ctk.CTkFrame(self.targets_body, fg_color="transparent")
            row.pack(fill="x", pady=5)
            top = ctk.CTkFrame(row, fg_color="transparent")
            top.pack(fill="x")
            ctk.CTkLabel(top, text=prog.name, anchor="w",
                         font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")
            pct = prog.completion_pct
            ctk.CTkLabel(top, text=f"{pct:.0f}%", anchor="e",
                         text_color=(theme.KICKER_RED if pct < 100 else ("#2E9E5B", "#35C46A")),
                         font=ctk.CTkFont(family=theme.MONO_FAMILY, size=12, weight="bold")
                         ).pack(side="right")
            bar = ctk.CTkProgressBar(row, height=8, corner_radius=8,
                                     progress_color=theme.ACCENT)
            bar.set(pct / 100)
            bar.pack(fill="x", pady=(4, 0))
