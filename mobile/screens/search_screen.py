"""
The mobile Search screen — filter past sessions by keyword, category and/or
date; tap a result to edit or delete it. Same SearchService as desktop.
"""

from __future__ import annotations

import flet as ft

from app.utils import validators
from mobile import theme
from mobile.widgets.fury import fury_button


def build(page: ft.Page, ctx) -> ft.Control:
    categories = ctx.category_service.list_categories(include_archived=True)
    results_column = ft.Column(spacing=8)

    keyword_field = ft.TextField(label="Keyword", width=180)
    category_dropdown = ft.Dropdown(
        label="Category", width=150,
        options=[ft.DropdownOption(key="", text="Any")]
                + [ft.DropdownOption(key=str(c.id), text=c.name) for c in categories],
        value="",
    )
    date_field = ft.TextField(label="Date (YYYY-MM-DD)", width=160)

    def _search(e=None) -> None:
        category_id = int(category_dropdown.value) if category_dropdown.value else None
        date_str = date_field.value.strip() or None
        results = ctx.search_service.search(keyword_field.value, category_id, date_str)

        results_column.controls.clear()
        if not results:
            results_column.controls.append(
                ft.Text("No matching entries.", size=12, color=theme.MUTED_TEXT)
            )
        for entry in results:
            subtitle = f"{entry.log_date}  {entry.start_time}–{entry.end_time}"
            if entry.notes:
                subtitle += f"  — {entry.notes}"
            results_column.controls.append(
                ft.Container(
                    padding=12, border_radius=10, bgcolor=theme.CARD,
                    border=ft.Border.all(1, theme.CARD_BORDER),
                    on_click=lambda ev, en=entry: _open_edit(en),
                    content=ft.Row(controls=[
                        ft.Icon(ft.Icons.CIRCLE, size=11, color=entry.category_color),
                        ft.Column(expand=True, spacing=0, controls=[
                            ft.Text(f"{entry.category_name}  ({entry.duration_label})",
                                    size=13, color=theme.HEADLINE),
                            ft.Text(subtitle, size=11, color=theme.MUTED_TEXT),
                        ]),
                    ]),
                )
            )
        page.update()

    def _open_edit(entry) -> None:
        cats = ctx.category_service.list_categories(include_archived=True)
        cat_dropdown = ft.Dropdown(
            value=str(entry.category_id),
            options=[ft.DropdownOption(key=str(c.id), text=c.name) for c in cats],
        )
        start_field = ft.TextField(label="Start (HH:MM)", value=entry.start_time)
        end_field = ft.TextField(label="End (HH:MM)", value=entry.end_time)
        notes_field = ft.TextField(label="Notes", value=entry.notes)
        error_text = ft.Text("", color=theme.STOP_RED, size=12)

        def _save(e=None) -> None:
            ok, msg = validators.validate_entry(entry.log_date, start_field.value, end_field.value)
            if not ok:
                error_text.value = msg
                page.update()
                return
            ctx.entry_service.update_entry(entry.id, int(cat_dropdown.value), entry.log_date,
                                           start_field.value, end_field.value, notes_field.value)
            page.pop_dialog()
            _search()

        def _delete(e=None) -> None:
            ctx.entry_service.delete_entry(entry.id)
            page.pop_dialog()
            _search()

        dialog = ft.AlertDialog(
            modal=True, title=ft.Text("Edit entry"),
            content=ft.Column(tight=True, spacing=10, width=320,
                              controls=[cat_dropdown, start_field, end_field, notes_field, error_text]),
            actions=[
                ft.TextButton("Delete", on_click=_delete),
                ft.TextButton("Cancel", on_click=lambda e: page.pop_dialog()),
                ft.Button("Save", on_click=_save),
            ],
        )
        page.show_dialog(dialog)

    def _clear(e=None) -> None:
        keyword_field.value = ""
        category_dropdown.value = ""
        date_field.value = ""
        _search()

    filters = ft.Column(spacing=10, controls=[
        keyword_field,
        ft.Row(wrap=True, controls=[category_dropdown, date_field]),
        ft.Row(controls=[
            fury_button("Search", icon=ft.Icons.SEARCH, kind="primary", on_click=_search),
            ft.TextButton("Clear", on_click=_clear),
        ]),
    ])

    _search()

    return ft.Column(
        expand=True, scroll=ft.ScrollMode.AUTO, spacing=14,
        controls=[
            theme.display("Search", size=28),
            filters,
            results_column,
        ],
    )
