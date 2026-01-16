"""Server status and header components - Following official Reflex dashboard template patterns."""

import reflex as rx

from salsa.frontend import styles
from salsa.frontend.state import State


def server_status_badge() -> rx.Component:
    """Server connection status badge."""
    return rx.cond(
        State.server_connected,
        rx.badge(
            rx.icon("circle-check", size=12),
            "Connected",
            color_scheme="teal",
            size="1",
            variant="soft",
        ),
        rx.badge(
            rx.icon("circle-x", size=12),
            "Disconnected",
            color_scheme="red",
            size="1",
            variant="soft",
        ),
    )


def server_dropdown() -> rx.Component:
    """Server information dropdown - template pattern."""
    return rx.menu.root(
        rx.menu.trigger(
            rx.button(
                rx.hstack(
                    rx.icon("server", size=14, color=styles.accent_text_color),
                    rx.text(
                        rx.cond(
                            State.server_name != "",
                            State.server_name,
                            "Plex Server",
                        ),
                        size="2",
                        weight="medium",
                    ),
                    server_status_badge(),
                    rx.icon("chevron-down", size=12, color=rx.color("gray", 9)),
                    spacing="2",
                    align="center",
                ),
                variant="ghost",
                size="2",
            ),
        ),
        rx.menu.content(
            rx.menu.item(
                rx.icon("globe", size=14),
                State.server_url,
                disabled=True,
            ),
            rx.cond(
                State.server_version != "",
                rx.menu.item(
                    rx.icon("info", size=14),
                    "Version " + State.server_version,
                    disabled=True,
                ),
            ),
            rx.menu.separator(),
            rx.menu.item(
                rx.icon("refresh-cw", size=14),
                "Change Server",
                on_click=State.logout,
            ),
        ),
    )


def header_bar() -> rx.Component:
    """Simple header bar - template navbar pattern."""
    from salsa.frontend.components.library_nav import mobile_sidebar_drawer
    from salsa.frontend.components.login import user_menu

    return rx.hstack(
        rx.hstack(
            mobile_sidebar_drawer(),
            rx.hstack(
                rx.image(
                    src="/icons/salsa_merged.svg",
                    width="28px",
                    height="28px",
                ),
                rx.text(
                    "SALSA",
                    size="4",
                    weight="bold",
                    display=["none", "none", "flex"],
                ),
                rx.badge(
                    "Beta",
                    color_scheme="orange",
                    variant="soft",
                    size="1",
                    display=["none", "none", "flex"],
                ),
                spacing="2",
                align="center",
            ),
            spacing="2",
            align="center",
        ),
        rx.spacer(),
        rx.hstack(
            rx.box(
                rx.cond(State.server_connected, server_dropdown()),
                display=["none", "none", "flex"],
            ),
            user_menu(),
            spacing="3",
            align="center",
        ),
        width="100%",
        padding="1em",
        align="center",
        border_bottom=styles.border,
        bg=rx.color("gray", 1),
    )
