"""Login component - Following official Reflex dashboard template patterns."""

import reflex as rx

from salsa.frontend.state import State


def login_card() -> rx.Component:
    """Login card with PIN and token authentication options."""
    return rx.card(
        rx.vstack(
            rx.image(
                src="/icons/salsa_merged.svg",
                width="64px",
                height="64px",
            ),

            rx.heading("SALSA", size="7", weight="bold"),
            rx.text(
                "Subtitle And Language Stream Automation",
                size="2",
                color=rx.color("gray", 11),
            ),

            rx.box(height="8px"),

            rx.cond(
                State.error_message != "",
                rx.callout(
                    State.error_message,
                    icon="circle-alert",
                    color="red",
                    size="1",
                ),
            ),

            rx.cond(
                State.auth_url != "",
                _pin_auth_section(),
                _login_options(),
            ),

            spacing="4",
            align="center",
            width="100%",
        ),
        size="3",
        style={
            "width": "100%",
            "max_width": "380px",
        },
    )


def _login_options() -> rx.Component:
    """Login options when not in PIN auth flow."""
    return rx.vstack(
        rx.button(
            "Sign in with Plex",
            size="3",
            width="100%",
            on_click=State.create_pin,
            loading=State.is_loading,
        ),

        rx.hstack(
            rx.separator(size="4"),
            rx.text("or", size="1", color=rx.color("gray", 10)),
            rx.separator(size="4"),
            align="center",
            width="100%",
        ),

        _token_login_form(),

        spacing="4",
        width="100%",
    )


def _pin_auth_section() -> rx.Component:
    """PIN authentication in progress."""
    return rx.vstack(
        rx.hstack(
            rx.spinner(size="2"),
            rx.text("Completing Plex sign in...", size="3", weight="medium"),
            spacing="2",
            align="center",
        ),

        rx.text(
            "A popup window should have opened. Complete sign in there.",
            size="2",
            color=rx.color("gray", 11),
            text_align="center",
        ),

        rx.hstack(
            rx.text("Popup blocked?", size="2", color=rx.color("gray", 11)),
            rx.link(
                "Click here to open manually",
                href=State.auth_url,
                is_external=True,
                size="2",
            ),
            spacing="1",
            align="center",
        ),

        rx.badge(
            f"PIN: {State.pin_code}",
            size="1",
            variant="soft",
        ),

        rx.button(
            "Cancel",
            size="2",
            variant="ghost",
            color_scheme="gray",
            on_click=State.cancel_pin_auth,
        ),

        spacing="4",
        align="center",
    )


def _token_login_form() -> rx.Component:
    """Manual token login form."""
    return rx.form(
        rx.vstack(
            rx.input(
                placeholder="Enter Plex Token",
                name="token",
                type="password",
                size="2",
                width="100%",
            ),
            rx.button(
                "Login with Token",
                type="submit",
                size="2",
                variant="soft",
                width="100%",
            ),
            spacing="2",
            width="100%",
        ),
        on_submit=lambda form_data: State.login_with_token(form_data.to(dict[str, str])["token"]),
        width="100%",
    )


def user_menu() -> rx.Component:
    """User menu when logged in."""
    return rx.menu.root(
        rx.menu.trigger(
            rx.button(
                rx.avatar(
                    src=State.thumb,
                    fallback=rx.cond(
                        State.username != "",
                        State.username[:2].upper(),
                        "?",
                    ),
                    size="2",
                ),
                rx.text(
                    State.username,
                    size="2",
                    weight="medium",
                    display=["none", "none", "block"],
                ),
                rx.icon(
                    "chevron-down",
                    size=12,
                    color=rx.color("gray", 10),
                    display=["none", "none", "block"],
                ),
                variant="ghost",
                size="2",
            ),
        ),
        rx.menu.content(
            rx.menu.item(
                rx.icon("user", size=14),
                State.email,
                disabled=True,
            ),
            rx.menu.separator(),
            rx.menu.item(
                rx.icon("users", size=14),
                "Switch User",
                on_click=State.load_home_users,
            ),
            rx.menu.separator(),
            rx.menu.item(
                rx.icon("log-out", size=14),
                "Logout",
                color="red",
                on_click=State.logout,
            ),
        ),
    )
