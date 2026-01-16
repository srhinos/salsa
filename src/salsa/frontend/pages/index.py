"""Main application page - Following official Reflex dashboard template patterns."""

import reflex as rx

from salsa.frontend import styles
from salsa.frontend.components import (
    batch_modal,
    header_bar,
    login_card,
    navigation_sidebar,
    server_select_card,
    track_panel,
)
from salsa.frontend.state import State


def index_page() -> rx.Component:
    """Main application page with sidebar and content."""
    return rx.cond(
        State.is_authenticated,
        _main_layout(),
        rx.cond(
            State.is_selecting_server,
            _server_select_layout(),
            _login_layout(),
        ),
    )


def _login_layout() -> rx.Component:
    """Layout for unauthenticated users - simple centered card."""
    return rx.center(
        login_card(),
        width="100%",
        height="100dvh",
        padding="1em",
        bg=rx.color("gray", 2),
    )


def _server_select_layout() -> rx.Component:
    """Layout for server selection after login."""
    return rx.center(
        server_select_card(),
        width="100%",
        height="100dvh",
        padding="1em",
        bg=rx.color("gray", 2),
    )


def _main_layout() -> rx.Component:
    """Layout for authenticated users - template pattern."""
    return rx.flex(
        header_bar(),

        rx.flex(
            rx.box(
                navigation_sidebar(),
                width=styles.sidebar_width,
                min_width=styles.sidebar_width,
                height="calc(100dvh - 60px)",
                overflow_y="auto",
                border_right=styles.border,
                display=["none", "none", "flex"],
            ),

            rx.box(
                track_panel(),
                flex="1",
                padding=["1em", "1.5em", "2em", "3em"],
                overflow_y="auto",
                height="calc(100dvh - 60px)",
            ),

            width="100%",
            flex="1",
        ),

        batch_modal(),

        direction="column",
        width="100%",
        height="100dvh",
        on_mount=State.load_libraries,
    )
