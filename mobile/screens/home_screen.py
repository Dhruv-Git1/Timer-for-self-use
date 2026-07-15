"""
The mobile Home screen — cinematic hero banner + headline stats + "Mission
Targets" goal progress. The hero reuses the same crimson-aura reference image
as the desktop app's app/ui/widgets/hero_banner.py (assets/hero.png), built
natively here via mobile/widgets/hero.py instead of Pillow compositing.
"""

from __future__ import annotations

import flet as ft

from app.utils import time_utils
from mobile import theme
from mobile.widgets.fury import animate_fill_in, fury_progress
from mobile.widgets.hero import hero_banner
from mobile.widgets.stat_card import stat_card


def build(page: ft.Page, ctx) -> ft.Control:
    today = time_utils.today_str()
    summary = ctx.dashboard_service.build_summary(today)
    week = ctx.stats_service.weekly(today)

    streak_word = "day" if summary.current_streak == 1 else "days"
    hero_subtitle = (
        f"{summary.current_streak} {streak_word} streak  ·  "
        f"{summary.productive_label} logged today"
    )

    cards = ft.ResponsiveRow(
        controls=[
            stat_card("Today", summary.productive_label, "productive", theme.ACCENT),
            stat_card("Streak", str(summary.current_streak), streak_word, "#E0A100"),
            stat_card("Sessions", str(summary.session_count), "logged today", "#3B82F6"),
            stat_card("This Week", time_utils.fmt_duration(week.total_productive_minutes),
                      "productive", "#2E9E5B"),
        ],
    )

    goals = [p for p in summary.progress if p.target_minutes > 0]
    goal_rows: list[ft.Control] = []
    progress_bars: list[ft.ProgressBar] = []
    if not goals:
        goal_rows.append(ft.Text("No daily goals set yet — set them on the Timer screen.",
                                  size=12, color=theme.MUTED_TEXT))
    for prog in goals:
        bar = fury_progress(prog.completion_pct / 100, color=theme.ACCENT)
        progress_bars.append(bar)
        goal_rows.append(
            ft.Column(spacing=3, controls=[
                ft.Row(controls=[
                    ft.Text(prog.name, size=13, color=theme.HEADLINE, expand=True),
                    ft.Text(f"{prog.completion_pct:.0f}%", size=12,
                            color="#35C46A" if prog.completion_pct >= 100 else theme.ACCENT),
                ]),
                bar,
            ])
        )

    root = ft.Column(
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        spacing=16,
        controls=[
            hero_banner(page, kicker="Operation : Discipline", headline="REVENGE",
                        subtitle=hero_subtitle, with_clock=True),
            cards,
            theme.card(
                ft.Column(spacing=10, controls=[
                    theme.section_label("Mission Targets"),
                    *goal_rows,
                ]),
                padding=16, radius=12,
            ),
        ],
    )
    if progress_bars:
        page.run_task(animate_fill_in, page, progress_bars)
    return root
