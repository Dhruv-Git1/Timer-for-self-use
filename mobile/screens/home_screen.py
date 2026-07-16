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
from mobile.widgets.fury import animate_fill_in, fury_button, fury_progress
from mobile.widgets.hero import hero_banner
from mobile.widgets.sheets import dismiss_sheet, form_sheet, show_sheet
from mobile.widgets.stat_card import stat_card


def build(page: ft.Page, ctx) -> ft.Control:
    today = time_utils.today_str()
    summary = ctx.dashboard_service.build_summary(today)
    week = ctx.stats_service.weekly(today)
    saved_reflection = ctx.daily_reflection_service.get_text(today)

    streak_word = "day" if summary.current_streak == 1 else "days"
    hero_subtitle = (
        f"{summary.current_streak} {streak_word} streak  ·  "
        f"{summary.productive_label} logged today"
    )

    cards = ft.ResponsiveRow(
        controls=[
            stat_card("Today", summary.productive_label, "productive", theme.ACCENT),
            stat_card("Streak", str(summary.current_streak), streak_word, theme.GOLD),
            stat_card("Sessions", str(summary.session_count), "logged today", theme.KICKER_RED),
            stat_card("This Week", time_utils.fmt_duration(week.total_productive_minutes),
                      "productive", theme.FLAME),
        ],
    )

    reflection_copy = ft.Text(
        saved_reflection or "Write a few words about what helped or got in the way today.",
        size=12,
        color=theme.HEADLINE if saved_reflection else theme.MUTED_TEXT,
        max_lines=3,
        overflow=ft.TextOverflow.ELLIPSIS,
    )
    reflection_label = ft.Text(
        "Saved today" if saved_reflection else "Not written yet",
        size=11,
        color=theme.STATUS_COMPLETE if saved_reflection else theme.MUTED_TEXT,
    )

    def _open_daily_review(_event) -> None:
        note_field = ft.TextField(
            label="What helped or got in the way today?",
            value=ctx.daily_reflection_service.get_text(today),
            hint_text=(
                "Example: I slept well and started early, but my phone distracted "
                "me after lunch."
            ),
            min_lines=5,
            max_lines=9,
            multiline=True,
        )
        error_text = ft.Text("", size=12, color=theme.KICKER_RED)
        holder: dict[str, ft.BottomSheet] = {}

        def _close(_event=None) -> None:
            dismiss_sheet(page, holder["sheet"])

        def _save(_event=None) -> None:
            try:
                saved = ctx.daily_reflection_service.save(today, note_field.value or "")
            except ValueError as exc:
                error_text.value = str(exc)
                page.update()
                return
            reflection_copy.value = saved or "Write a few words about what helped or got in the way today."
            reflection_copy.color = theme.HEADLINE if saved else theme.MUTED_TEXT
            reflection_label.value = "Saved today" if saved else "Not written yet"
            reflection_label.color = theme.STATUS_COMPLETE if saved else theme.MUTED_TEXT
            _close()
            page.update()

        sheet = form_sheet(
            "Daily review",
            ft.Column(
                spacing=8,
                controls=[
                    ft.Text(
                        "Write naturally. This stays on your device unless you later "
                        "choose an AI Coach review.",
                        size=12,
                        color=theme.MUTED_TEXT,
                    ),
                    note_field,
                    error_text,
                ],
            ),
            actions=[
                ft.TextButton("Cancel", on_click=_close),
                fury_button("Save review", kind="primary", on_click=_save),
            ],
            on_close=_close,
            body_height=380,
        )
        holder["sheet"] = sheet
        show_sheet(page, sheet)

    daily_review_card = theme.card(
        ft.Column(
            spacing=8,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Column(
                            expand=True,
                            spacing=2,
                            controls=[
                                theme.section_label("Daily reflection"),
                                reflection_label,
                            ],
                        ),
                        fury_button(
                            "Edit" if saved_reflection else "Write review",
                            kind="secondary",
                            icon=ft.Icons.EDIT_NOTE,
                            on_click=_open_daily_review,
                        ),
                    ],
                ),
                reflection_copy,
            ],
        ),
        padding=16,
        radius=12,
    )

    goals = [p for p in summary.progress if p.target_minutes > 0]
    goal_rows: list[ft.Control] = []
    progress_bars: list[ft.ProgressBar] = []
    if not goals:
        goal_rows.append(
            ft.Container(
                padding=12,
                border_radius=10,
                bgcolor=theme.NEUTRAL_BTN,
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.FLAG_OUTLINED, color=theme.FLAME, size=20),
                        ft.Column(
                            expand=True,
                            spacing=2,
                            controls=[
                                ft.Text("Set your first target", size=13, color=theme.HEADLINE),
                                ft.Text(
                                    "Open Timer and set a daily goal to start building momentum.",
                                    size=11,
                                    color=theme.MUTED_TEXT,
                                ),
                            ],
                        ),
                    ],
                ),
            )
        )
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
            daily_review_card,
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
