"""Server selection component - Following official Reflex dashboard template patterns."""

import reflex as rx

from salsa.frontend.state import PlexServerInfo, ServerConnection, State


def server_select_card() -> rx.Component:
    """Server selection UI shown after Plex login."""
    return rx.box(
        rx.card(
            rx.vstack(
                rx.hstack(
                    rx.avatar(
                        src=State.thumb,
                        fallback=rx.cond(
                            State.username != "",
                            State.username[:2].upper(),
                            "?",
                        ),
                        size="3",
                    ),
                    rx.vstack(
                        rx.text(State.username, weight="bold", size="3"),
                        rx.text("Select a Plex server", size="2", color=rx.color("gray", 11)),
                        spacing="1",
                        align="start",
                    ),
                    spacing="3",
                    align="center",
                    width="100%",
                ),
                rx.box(height="4px"),
                rx.cond(
                    State.server_selection_error != "",
                    rx.callout(
                        State.server_selection_error,
                        icon="circle-alert",
                        color="red",
                        size="1",
                    ),
                ),
                rx.cond(
                    State.is_loading_servers,
                    rx.hstack(
                        rx.spinner(size="2"),
                        rx.text("Loading servers...", size="2"),
                        spacing="2",
                        justify="center",
                        width="100%",
                    ),
                    _server_selection_content(),
                ),
                rx.button(
                    rx.icon("log-out", size=14),
                    "Sign out",
                    size="2",
                    variant="ghost",
                    color_scheme="gray",
                    on_click=State.logout,
                ),
                spacing="4",
                align="center",
                width="100%",
            ),
            size="3",
            style={
                "width": "100%",
                "max_width": "480px",
            },
        ),
        on_mount=State.test_all_connections,
    )


def _server_selection_content() -> rx.Component:
    """Server list and custom URL input."""
    return rx.vstack(
        rx.cond(
            State.available_servers.length() > 0,
            rx.vstack(
                rx.text("Your Plex Servers", weight="medium", size="2"),
                rx.foreach(State.available_servers, _server_item),
                spacing="2",
                width="100%",
            ),
            rx.text(
                "No servers found. Enter a server URL below.",
                size="2",
                color=rx.color("gray", 11),
            ),
        ),
        rx.separator(size="4"),
        rx.vstack(
            rx.text("Or enter server URL manually", size="2", color=rx.color("gray", 11)),
            rx.hstack(
                rx.input(
                    placeholder="http://192.168.1.100:32400",
                    value=State.custom_server_url,
                    on_change=State.set_custom_server_url,
                    size="2",
                    style={"flex": "1"},
                ),
                rx.match(
                    State.custom_server_status,
                    ("testing", rx.spinner(size="2")),
                    (
                        "valid",
                        rx.tooltip(
                            rx.icon("circle-check", size=20, color=rx.color("teal", 9)),
                            content=f"Server reachable ({State.custom_server_latency}ms)",
                        ),
                    ),
                    (
                        "invalid",
                        rx.tooltip(
                            rx.icon("circle-x", size=20, color=rx.color("red", 9)),
                            content=State.custom_server_error,
                        ),
                    ),
                    rx.box(width="20px"),
                ),
                rx.button(
                    "Connect",
                    size="2",
                    on_click=State.select_custom_server,
                    loading=State.is_loading_servers,
                    disabled=(State.custom_server_status != "valid"),
                ),
                spacing="2",
                align="center",
                width="100%",
            ),
            rx.cond(
                State.custom_server_error != "",
                rx.text(State.custom_server_error, size="1", color=rx.color("red", 9)),
            ),
            rx.cond(
                State.custom_server_status == "valid",
                rx.text(
                    f"Server reachable ({State.custom_server_latency}ms)",
                    size="1",
                    color=rx.color("teal", 9),
                ),
            ),
            rx.text(
                "Tip: Use host.docker.internal:32400 for Plex on this machine",
                size="1",
                color=rx.color("gray", 10),
            ),
            spacing="2",
            width="100%",
        ),
        spacing="4",
        width="100%",
    )


def _server_item(server: PlexServerInfo) -> rx.Component:
    """Individual server item with connection options."""
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.icon("server", size=18),
                rx.vstack(
                    rx.text(server.name, weight="medium", size="2"),
                    rx.text("v" + server.version, size="1", color=rx.color("gray", 10)),
                    spacing="0",
                    align="start",
                ),
                rx.spacer(),
                rx.cond(
                    server.owned,
                    rx.badge("Owner", color_scheme="teal", size="1", variant="soft"),
                    rx.badge("Shared", color_scheme="blue", size="1", variant="soft"),
                ),
                width="100%",
                align="center",
            ),
            rx.hstack(
                rx.foreach(server.connections, _connection_button),
                spacing="2",
                wrap="wrap",
            ),
            spacing="3",
            width="100%",
        ),
        size="2",
    )


def _connection_button(conn: ServerConnection) -> rx.Component:
    """Button to connect using a specific connection URI."""
    status = State.connection_status.get(conn.uri, "testing")

    button = rx.button(
        rx.hstack(
            rx.match(
                status,
                ("testing", rx.spinner(size="1")),
                ("ok", rx.icon("circle-check", size=12, color=rx.color("teal", 9))),
                ("error", rx.icon("circle-x", size=12, color=rx.color("red", 9))),
                rx.spinner(size="1"),
            ),
            rx.cond(
                conn.local,
                rx.icon("wifi", size=12),
                rx.cond(
                    conn.relay,
                    rx.icon("cloud", size=12),
                    rx.icon("globe", size=12),
                ),
            ),
            rx.text(conn.uri, size="1"),
            spacing="1",
            align="center",
        ),
        size="1",
        variant="soft",
        on_click=State.select_server(conn.uri),
    )

    return rx.tooltip(
        button,
        content=rx.cond(
            conn.local,
            "Local network connection",
            rx.cond(
                conn.relay,
                "Plex relay connection (slower)",
                "Remote connection",
            ),
        ),
    )
