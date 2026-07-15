"""
The mobile Categories screen — manage your activity categories: add/edit
name, color (tap a swatch), productive flag and daily goal; archive or
delete. Same protection as desktop: CategoryService blocks deleting a
category that still has logged entries (archive instead), so history is
never lost.
"""

from __future__ import annotations

import flet as ft

import config
from app.utils import validators
from mobile import theme


def build(page: ft.Page, ctx) -> ft.Control:
    list_column = ft.Column(spacing=8)

    def _refresh() -> None:
        list_column.controls.clear()
        cats = ctx.category_service.list_categories(include_archived=True)
        for cat in cats:
            goal_text = f"goal: {cat.daily_target_minutes}m" if cat.has_target else "no goal"
            name_text = f"{cat.name}  (archived)" if cat.is_archived else cat.name
            list_column.controls.append(
                ft.Container(
                    padding=14, border_radius=10, bgcolor=theme.CARD,
                    border=ft.Border.all(1, theme.CARD_BORDER),
                    on_click=lambda e, c=cat: _open_form(c),
                    content=ft.Row(controls=[
                        ft.Icon(ft.Icons.CIRCLE, size=14, color=cat.color),
                        ft.Text(name_text, size=14, color=theme.HEADLINE, expand=True),
                        ft.Text(goal_text, size=11, color=theme.MUTED_TEXT),
                    ]),
                )
            )
        page.update()

    def _open_form(category=None) -> None:
        name_field = ft.TextField(label="Name", value=category.name if category else "")
        chosen_color = {"value": category.color if category else config.CHART_PALETTE[0]}
        swatch_row = ft.Row(wrap=True, spacing=6)

        def _pick_color(color: str) -> None:
            chosen_color["value"] = color
            for sw in swatch_row.controls:
                sw.border = ft.Border.all(3, "#FFFFFF") if sw.data == color else None
            page.update()

        for color in config.CHART_PALETTE:
            swatch_row.controls.append(
                ft.Container(
                    data=color, width=32, height=32, border_radius=16, bgcolor=color,
                    border=ft.Border.all(3, "#FFFFFF") if color == chosen_color["value"] else None,
                    on_click=lambda e, c=color: _pick_color(c),
                )
            )

        productive_switch = ft.Switch(label="Counts as productive time",
                                      value=category.is_productive if category else True)
        goal_field = ft.TextField(label="Daily goal (minutes, 0 = none)",
                                  value=str(category.daily_target_minutes) if category else "0")
        error_text = ft.Text("", color=theme.STOP_RED, size=12)

        def _save(e=None) -> None:
            ok, msg = validators.validate_target_minutes(goal_field.value)
            if not ok:
                error_text.value = msg
                page.update()
                return
            target = int(goal_field.value or 0)
            if category:
                category.name = name_field.value
                category.color = chosen_color["value"]
                category.is_productive = productive_switch.value
                category.daily_target_minutes = target
                ok, msg, _ = ctx.category_service.update(category)
            else:
                ok, msg, _ = ctx.category_service.create(
                    name_field.value, chosen_color["value"], productive_switch.value, target)
            if not ok:
                error_text.value = msg
                page.update()
                return
            page.pop_dialog()
            _refresh()

        def _archive(e=None) -> None:
            ctx.category_service.set_archived(category.id, not category.is_archived)
            page.pop_dialog()
            _refresh()

        def _confirm_delete(e=None) -> None:
            page.pop_dialog()

            def _do_delete(e2=None) -> None:
                ok, msg, _ = ctx.category_service.delete(category.id)
                page.pop_dialog()
                if ok:
                    _refresh()
                else:
                    page.show_dialog(ft.AlertDialog(
                        modal=True, title=ft.Text("Can't delete"), content=ft.Text(msg),
                        actions=[ft.TextButton("OK", on_click=lambda e: page.pop_dialog())],
                    ))

            page.show_dialog(ft.AlertDialog(
                modal=True, title=ft.Text("Delete category?"),
                content=ft.Text(f'Delete "{category.name}"? This cannot be undone.'),
                actions=[
                    ft.TextButton("Cancel", on_click=lambda e: page.pop_dialog()),
                    ft.TextButton("Delete", on_click=_do_delete),
                ],
            ))

        actions = [ft.TextButton("Cancel", on_click=lambda e: page.pop_dialog()),
                  ft.Button("Save", on_click=_save)]
        if category:
            actions.insert(0, ft.TextButton(
                "Unarchive" if category.is_archived else "Archive", on_click=_archive))
            actions.insert(0, ft.TextButton("Delete", on_click=_confirm_delete))

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Edit category" if category else "Add category"),
            content=ft.Column(tight=True, spacing=12, width=320, scroll=ft.ScrollMode.AUTO, controls=[
                name_field,
                ft.Text("Color", size=12, color=theme.MUTED_TEXT),
                swatch_row,
                productive_switch,
                goal_field,
                error_text,
            ]),
            actions=actions,
        )
        page.show_dialog(dialog)

    _refresh()

    return ft.Column(
        expand=True, scroll=ft.ScrollMode.AUTO, spacing=14,
        controls=[
            ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                theme.display("Categories", size=28),
                ft.IconButton(icon=ft.Icons.ADD, icon_color=theme.ACCENT,
                             on_click=lambda e: _open_form()),
            ]),
            list_column,
        ],
    )
