"""Login page."""

import reflex as rx

from salsa.frontend.components import login_card, server_select_card
from salsa.frontend.state import State


def login_page() -> rx.Component:
    """Login page with centered card."""
    return rx.box(
        rx.center(
            rx.cond(
                State.is_selecting_server,
                server_select_card(),
                login_card(),
            ),
            width="100%",
            height="100vh",
        ),
        background="var(--gray-2)",
    )
