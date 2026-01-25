import flet as ft


def feather_icon(name: str, size: int = 16, color: str = "#f8d7da") -> ft.Image:
    return ft.Image(
        src=f"assets/icons/feather/{name}.svg",
        width=size,
        height=size,
        color=color,
    )


def icon_label(
    name: str,
    text: str,
    size: int = 16,
    color: str = "#f8d7da",
    text_size: int | None = None,
    text_weight: str | None = None,
    spacing: int = 6,
) -> ft.Row:
    return ft.Row(
        [
            feather_icon(name, size=size, color=color),
            ft.Text(text, size=text_size or size + 2, color=color, weight=text_weight),
        ],
        spacing=spacing,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )
