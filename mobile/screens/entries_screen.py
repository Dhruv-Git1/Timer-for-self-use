"""
The mobile Today's Entries screen — day nav + a list of that day's logged
sessions, add/edit via a modal dialog, delete with a confirm step. Same
validation and services as the desktop Entries screen (EntryService),
including overlap warnings and "duplicate previous day".
"""

from __future__ import annotations

import flet as ft

from app.utils import time_utils, validators
from mobile import theme
from mobile.widgets.fury import fury_button


def build(page: ft.Page, ctx) -> ft.Control:
    state = {"date": time_utils.today_str()}

    date_label = ft.Text("", size=15, weight=ft.FontWeight.BOLD, color=theme.HEADLINE)
    list_column = ft.Column(spacing=8)

    def _prev(e=None) -> None:
        state["date"] = time_utils.add_days(state["date"], -1)
        _refresh()

    def _next(e=None) -> None:
        state["date"] = time_utils.add_days(state["date"], 1)
        _refresh()

    def _today(e=None) -> None:
        state["date"] = time_utils.today_str()
        _refresh()

    def _duplicate_prev(e=None) -> None:
        prev_day = time_utils.add_days(state["date"], -1)
        ctx.entry_service.duplicate_day(prev_day, state["date"])
        _refresh()

    def _open_form(entry=None) -> None:
        cats = [
            category for category in ctx.category_service.list_categories()
            if category.is_timer
        ]
        if not cats:
            page.show_dialog(ft.AlertDialog(
                modal=True,
                title=ft.Text("No Timer category"),
                content=ft.Text("Create a Timer category before adding a time entry."),
                actions=[ft.TextButton("OK", on_click=lambda e: page.pop_dialog())],
            ))
            return
        cat_dropdown = ft.Dropdown(
            value=str(entry.category_id if entry else cats[0].id),
            options=[ft.DropdownOption(key=str(c.id), text=c.name) for c in cats],
        )
        start_field = ft.TextField(label="Start (HH:MM)",
                                   value=entry.start_time if entry else "09:00")
        end_field = ft.TextField(label="End (HH:MM)",
                                 value=entry.end_time if entry else "10:00")
        notes_field = ft.TextField(label="Notes", value=entry.notes if entry else "")
        error_text = ft.Text("", color=theme.STOP_RED, size=12)

        def _save(e=None) -> None:
            category_id = int(cat_dropdown.value)
            ok, msg = validators.validate_entry(state["date"], start_field.value, end_field.value)
            if not ok:
                error_text.value = msg
                page.update()
                return
            if entry:
                ok, msg, _ = ctx.entry_service.update_entry(
                    entry.id, category_id, state["date"], start_field.value,
                    end_field.value, notes_field.value,
                )
            else:
                ok, msg, _ = ctx.entry_service.add_entry(
                    category_id, state["date"], start_field.value,
                    end_field.value, notes_field.value,
                )
            if not ok:
                error_text.value = msg
                page.update()
                return
            page.pop_dialog()
            _refresh()

        def _cancel(e=None) -> None:
            page.pop_dialog()

        def _delete(e=None) -> None:
            ctx.entry_service.delete_entry(entry.id)
            page.pop_dialog()
            _refresh()

        actions = [ft.TextButton("Cancel", on_click=_cancel), ft.Button("Save", on_click=_save)]
        if entry:
            actions.insert(0, ft.TextButton("Delete", on_click=_delete))

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Edit entry" if entry else "Add entry"),
            content=ft.Column(tight=True, spacing=10, width=320,
                              controls=[cat_dropdown, start_field, end_field, notes_field, error_text]),
            actions=actions,
        )
        page.show_dialog(dialog)

    def _refresh() -> None:
        weekday = time_utils.weekday_name(state["date"])
        date_label.value = f"{weekday}, {state['date']}"

        entries = ctx.entry_service.entries_for_date(state["date"])
        overlapping = ctx.entry_service.overlapping_ids(state["date"])

        list_column.controls.clear()
        if not entries:
            list_column.controls.append(
                ft.Text("No entries logged for this day.", size=12, color=theme.MUTED_TEXT)
            )
        for entry in entries:
            warn = "  ⚠" if entry.id in overlapping else ""
            list_column.controls.append(
                ft.Container(
                    padding=12, border_radius=10, bgcolor=theme.CARD,
                    border=ft.Border.all(1, theme.CARD_BORDER),
                    on_click=lambda e, en=entry: _open_form(en),
                    content=ft.Row(controls=[
                        ft.Icon(ft.Icons.CIRCLE, size=12, color=entry.category_color),
                        ft.Text(f"{entry.start_time}–{entry.end_time}  {entry.category_name}{warn}",
                                size=13, color=theme.HEADLINE, expand=True),
                        ft.Text(entry.duration_label, size=12, color=theme.MUTED_TEXT),
                    ]),
                )
            )
        page.update()

    _refresh()

    nav = ft.Row(
        alignment=ft.MainAxisAlignment.CENTER, spacing=6,
        controls=[
            ft.IconButton(icon=ft.Icons.CHEVRON_LEFT, on_click=_prev),
            date_label,
            ft.IconButton(icon=ft.Icons.CHEVRON_RIGHT, on_click=_next),
            ft.TextButton("Today", on_click=_today),
        ],
    )
    actions_row = ft.Row(controls=[
        fury_button("Add entry", icon=ft.Icons.ADD, kind="primary", on_click=lambda e: _open_form()),
        ft.TextButton("Duplicate previous day", on_click=_duplicate_prev),
    ])

    return ft.Column(
        expand=True, scroll=ft.ScrollMode.AUTO, spacing=14,
        controls=[
            theme.display("Today's Entries", size=26),
            nav, actions_row, list_column,
        ],
    )
