"""SALSA Reflex application entry point."""

import reflex as rx

from salsa.frontend.pages import index_page

app = rx.App(
    theme=rx.theme(
        appearance="dark",
        accent_color="orange",
        gray_color="slate",
        radius="medium",
        panel_background="translucent",
    ),
    stylesheets=[
        "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap",
        "/styles/global.css",
    ],
    head_components=[
        rx.el.link(rel="icon", href="/icons/favicon.svg", type="image/svg+xml"),
    ],
)

app.add_page(index_page, route="/", title="SALSA - Plex Stream Manager")
