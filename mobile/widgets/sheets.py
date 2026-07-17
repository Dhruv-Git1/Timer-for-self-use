"""Reusable bottom-sheet scaffolding for mobile editing flows."""

from __future__ import annotations

from typing import Callable, Sequence

import flet as ft

from mobile import theme


def form_sheet(
    title: str,
    body: ft.Control,
    actions: Sequence[ft.Control],
    on_close: Callable,
    *,
    body_height: float | None = None,
    leading_actions: Sequence[ft.Control] = (),
    on_dismiss: Callable | None = None,
) -> ft.BottomSheet:
    """Create a scroll-friendly form sheet with a persistent action row.

    ``leading_actions`` holds destructive or secondary controls on the left;
    Cancel and the primary Save action remain grouped on the right.
    """
    body_control: ft.Control = body
    if body_height is not None:
        body_control = ft.Container(height=body_height, content=body)

    return ft.BottomSheet(
        bgcolor=theme.CARD,
        dismissible=True,
        draggable=True,
        show_drag_handle=True,
        scrollable=True,
        on_dismiss=on_dismiss,
        content=ft.Container(
            padding=ft.Padding.only(left=20, top=4, right=20, bottom=20),
            content=ft.Column(
                tight=True,
                spacing=12,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            theme.display(title.upper(), size=26),
                            ft.IconButton(
                                icon=ft.Icons.CLOSE,
                                icon_color=theme.MUTED_TEXT,
                                on_click=on_close,
                            ),
                        ],
                    ),
                    body_control,
                    ft.Divider(color=theme.CARD_BORDER, height=1),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Row(spacing=4, controls=list(leading_actions)),
                            ft.Row(spacing=8, controls=list(actions)),
                        ],
                    ),
                ],
            ),
        ),
    )


def show_sheet(page: ft.Page, sheet: ft.BottomSheet) -> None:
    """Show a managed modal sheet using Flet's dialog stack.

    BottomSheet inherits DialogControl. Keeping it out of ``page.overlay`` is
    important: managed dialogs remove their modal barrier after Flutter's
    dismissal animation, including when an AlertDialog was stacked above it.
    """
    page.show_dialog(sheet)


def dismiss_sheet(page: ft.Page, sheet: ft.BottomSheet) -> None:
    if sheet.open:
        page.pop_dialog()
