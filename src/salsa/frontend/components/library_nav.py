"""Library navigation - Following official Reflex dashboard template patterns."""

import reflex as rx

from salsa.frontend import styles
from salsa.frontend.state import State

# =============================================================================
# LIBRARY SELECTOR - Simple tab-like pills
# =============================================================================


def _library_pill(lib: dict) -> rx.Component:
    """Library selection pill - matches template sidebar_item pattern."""
    is_selected = State.selected_library_key == lib["key"]
    return rx.box(
        rx.hstack(
            rx.cond(
                lib["type"] == "movie",
                rx.icon("film", size=14),
                rx.icon("tv", size=14),
            ),
            rx.text(lib["title"], size="2", weight="medium"),
            spacing="2",
            align="center",
            justify="center",
        ),
        padding_x="3",
        padding_y="2",
        border_radius=styles.border_radius,
        cursor="pointer",
        flex="1",
        display="flex",
        align_items="center",
        justify_content="center",
        color=rx.cond(is_selected, styles.accent_text_color, styles.text_color),
        background=rx.cond(is_selected, styles.accent_bg_color, "transparent"),
        style={
            "_hover": {
                "background_color": rx.cond(
                    is_selected, styles.accent_bg_color, styles.gray_bg_color
                ),
            },
        },
        on_click=lambda: State.select_library(lib["key"]),
    )


# =============================================================================
# BREADCRUMB HEADER - Shows current selection with back
# =============================================================================


def _breadcrumb_header(
    title: rx.Var,
    subtitle: str,
    on_back: callable,
) -> rx.Component:
    """Clickable breadcrumb bar - entire bar is the back button.

    Hover reveals chevron sliding in from left while text shifts right.
    Click anywhere on the bar to go back. Smooth, professional animation.
    """
    return rx.box(
        rx.hstack(
            rx.box(
                rx.icon("chevron-left", size=16, color=styles.accent_text_color),
                display="flex",
                align_items="center",
                justify_content="center",
                width="0px",
                opacity="0",
                overflow="hidden",
                style={
                    "transition": "all 0.2s cubic-bezier(0.4, 0, 0.2, 1)",
                },
                class_name="breadcrumb-chevron",
            ),
            rx.vstack(
                rx.text(
                    title,
                    size="2",
                    weight="medium",
                    color=styles.text_color,
                    truncate=True,
                ),
                rx.text(subtitle, size="1", color=rx.color("gray", 9)),
                spacing="0",
                align="start",
                flex="1",
                min_width="0",
                overflow="hidden",
            ),
            spacing="2",
            align="center",
            width="100%",
        ),
        padding="3",
        padding_x="4",
        background=styles.gray_bg_color,
        border_radius=styles.border_radius,
        border="1px solid transparent",
        cursor="pointer",
        width="100%",
        min_height="44px",
        display="flex",
        align_items="center",
        style={
            "border_color": rx.color("gray", 6),
            "transition": "all 0.2s cubic-bezier(0.4, 0, 0.2, 1)",
            "_hover": {
                "background": rx.color("gray", 4),
                "border_color": "var(--orange-9)",
                "& .breadcrumb-chevron": {
                    "width": "24px",
                    "opacity": "1",
                },
            },
            "_active": {
                "transform": "scale(0.98)",
                "background": rx.color("gray", 5),
            },
        },
        on_click=on_back,
    )


# =============================================================================
# SEARCH INPUT - Simple ghost style
# =============================================================================


def _search_input(placeholder: str, value: rx.Var, on_change: callable) -> rx.Component:
    """Simple search input - no clear button, user can select all and delete."""
    return rx.hstack(
        rx.icon("search", size=14, color=rx.color("gray", 9)),
        rx.input(
            placeholder=placeholder,
            value=value,
            on_change=on_change,
            size="2",
            variant="soft",
            style={
                "flex": "1",
                "background": "transparent",
                "border": "none",
                "box_shadow": "none",
            },
        ),
        spacing="2",
        align="center",
        width="100%",
        padding="2",
        padding_x="3",
        background=rx.color("gray", 2),
        border=styles.border,
        border_radius=styles.border_radius,
    )


# =============================================================================
# LIST ITEMS - Matching template sidebar_item exactly
# =============================================================================


def _list_item(
    title: rx.Var,
    is_selected: rx.Var,
    on_click: callable,
    suffix: rx.Component | None = None,
) -> rx.Component:
    """Generic list item - template sidebar_item pattern."""
    return rx.box(
        rx.hstack(
            rx.text(
                title,
                size="2",
                weight=rx.cond(is_selected, "medium", "regular"),
                truncate=True,
                flex="1",
            ),
            suffix if suffix else rx.fragment(),
            spacing="2",
            align="center",
            width="100%",
        ),
        padding="0.35em",
        padding_x="0.5em",
        border_radius=styles.border_radius,
        cursor="pointer",
        width="100%",
        color=rx.cond(is_selected, styles.accent_text_color, styles.text_color),
        background=rx.cond(is_selected, styles.accent_bg_color, "transparent"),
        style={
            "_hover": {
                "background_color": rx.cond(
                    is_selected, styles.accent_bg_color, styles.gray_bg_color
                ),
                "color": rx.cond(is_selected, styles.accent_text_color, styles.text_color),
            },
        },
        on_click=on_click,
    )


def _show_item(item: dict) -> rx.Component:
    """Show/movie list item."""
    is_selected = State.selected_item_key == item["rating_key"]
    suffix = rx.cond(
        item["year"],
        rx.text(item["year"].to(str), size="1", color=rx.color("gray", 9)),
        rx.fragment(),
    )
    return _list_item(
        item["title"],
        is_selected,
        lambda: State.select_item(item["rating_key"]),
        suffix,
    )


def _season_item(season: dict) -> rx.Component:
    """Season list item with badge."""
    is_selected = State.selected_season_key == season["rating_key"]
    return rx.box(
        rx.hstack(
            rx.badge(
                rx.cond(
                    season["index"] > 0,
                    "S" + season["index"].to(str),
                    "S?",
                ),
                size="1",
                variant=rx.cond(is_selected, "solid", "soft"),
                color_scheme=rx.cond(is_selected, "orange", "gray"),
            ),
            rx.text(
                season["title"],
                size="2",
                weight=rx.cond(is_selected, "medium", "regular"),
                truncate=True,
                flex="1",
            ),
            spacing="2",
            align="center",
            width="100%",
        ),
        padding="0.35em",
        padding_x="0.5em",
        border_radius=styles.border_radius,
        cursor="pointer",
        width="100%",
        color=rx.cond(is_selected, styles.accent_text_color, styles.text_color),
        background=rx.cond(is_selected, styles.accent_bg_color, "transparent"),
        style={
            "_hover": {
                "background_color": rx.cond(
                    is_selected, styles.accent_bg_color, styles.gray_bg_color
                ),
            },
        },
        on_click=lambda: State.select_season(season["rating_key"]),
    )


def _episode_item(episode: dict) -> rx.Component:
    """Episode list item with number badge."""
    is_selected = State.selected_episode_key == episode["rating_key"]
    return rx.box(
        rx.hstack(
            rx.badge(
                rx.cond(episode["index"] > 0, episode["index"].to(str), "?"),
                size="1",
                variant=rx.cond(is_selected, "solid", "soft"),
                color_scheme=rx.cond(is_selected, "orange", "gray"),
            ),
            rx.text(
                episode["title"],
                size="2",
                weight=rx.cond(is_selected, "medium", "regular"),
                truncate=True,
                flex="1",
            ),
            spacing="2",
            align="center",
            width="100%",
        ),
        padding="0.35em",
        padding_x="0.5em",
        border_radius=styles.border_radius,
        cursor="pointer",
        width="100%",
        color=rx.cond(is_selected, styles.accent_text_color, styles.text_color),
        background=rx.cond(is_selected, styles.accent_bg_color, "transparent"),
        style={
            "_hover": {
                "background_color": rx.cond(
                    is_selected, styles.accent_bg_color, styles.gray_bg_color
                ),
            },
        },
        on_click=lambda: State.select_episode(episode["rating_key"]),
    )


# =============================================================================
# SECTION LABEL - Simple with count badge
# =============================================================================


def _section_label(text: str, count: rx.Var | None = None) -> rx.Component:
    """Section label matching template pattern."""
    return rx.hstack(
        rx.text(
            text,
            size="1",
            weight="bold",
            color=rx.color("gray", 9),
            style={"text_transform": "uppercase", "letter_spacing": "0.05em"},
        ),
        rx.cond(
            count is not None,
            rx.badge(count.to(str), size="1", variant="soft"),
            rx.fragment(),
        ),
        spacing="2",
        align="center",
        padding_bottom="2",
        margin_bottom="2",
        border_bottom=styles.border,
        width="100%",
    )


# =============================================================================
# MAIN NAVIGATION SIDEBAR
# =============================================================================


def navigation_sidebar() -> rx.Component:
    """Drill-down navigation sidebar - template pattern."""
    return rx.vstack(
        rx.box(
            rx.cond(
                State.is_loading_libraries,
                rx.center(rx.spinner(size="2"), padding="4"),
                rx.hstack(
                    rx.foreach(State.libraries, _library_pill),
                    spacing="2",
                    width="100%",
                ),
            ),
            width="100%",
            padding="1em",
        ),
        rx.cond(
            State.selected_library_key != "",
            rx.separator(size="4"),
        ),
        rx.cond(
            State.selected_library_key != "",
            rx.cond(
                State.selected_item_key != "",
                rx.box(
                    _breadcrumb_header(
                        State.selected_item_title,
                        rx.cond(State.selected_item_type == "movie", "Movie", "TV Show"),
                        State.clear_item_selection,
                    ),
                    padding="1em",
                    padding_top="0.5em",
                    width="100%",
                ),
                rx.box(
                    rx.vstack(
                        _section_label(State.selected_library_title, State.items.length()),
                        rx.cond(
                            State.is_loading_items,
                            rx.center(rx.spinner(size="2"), padding="4"),
                            rx.fragment(
                                _search_input(
                                    "Search...", State.item_filter, State.set_item_filter
                                ),
                                rx.scroll_area(
                                    rx.vstack(
                                        rx.foreach(State.filtered_items, _show_item),
                                        spacing="1",
                                        width="100%",
                                    ),
                                    type="hover",
                                    scrollbars="vertical",
                                    flex="1",
                                ),
                            ),
                        ),
                        spacing="3",
                        width="100%",
                        height="100%",
                    ),
                    flex="1",
                    width="100%",
                    padding="1em",
                    padding_top="0.5em",
                    display="flex",
                    flex_direction="column",
                    min_height="0",
                ),
            ),
        ),
        rx.cond(
            (State.selected_item_type == "show") & (State.selected_item_key != ""),
            rx.cond(
                State.selected_season_key != "",
                rx.box(
                    _breadcrumb_header(
                        State.selected_season_title,
                        "Season",
                        State.clear_season_selection,
                    ),
                    padding="1em",
                    padding_top="0",
                    width="100%",
                ),
                rx.vstack(
                    _section_label("Seasons", State.seasons.length()),
                    rx.cond(
                        State.is_loading_seasons,
                        rx.center(rx.spinner(size="2"), padding="3"),
                        rx.vstack(
                            rx.foreach(State.filtered_seasons, _season_item),
                            spacing="1",
                            width="100%",
                        ),
                    ),
                    spacing="3",
                    width="100%",
                    padding="1em",
                    padding_top="0",
                ),
            ),
        ),
        rx.cond(
            State.selected_season_key != "",
            rx.box(
                rx.vstack(
                    _section_label("Episodes", State.episodes.length()),
                    rx.cond(
                        State.is_loading_episodes,
                        rx.center(rx.spinner(size="2"), padding="3"),
                        rx.fragment(
                            _search_input(
                                "Search...", State.episode_filter, State.set_episode_filter
                            ),
                            rx.scroll_area(
                                rx.vstack(
                                    rx.foreach(State.filtered_episodes, _episode_item),
                                    spacing="1",
                                    width="100%",
                                ),
                                type="hover",
                                scrollbars="vertical",
                                flex="1",
                            ),
                        ),
                    ),
                    spacing="3",
                    width="100%",
                    height="100%",
                ),
                flex="1",
                width="100%",
                padding="1em",
                padding_top="0",
                display="flex",
                flex_direction="column",
                min_height="0",
            ),
        ),
        rx.cond(
            State.browser_error != "",
            rx.box(
                rx.callout(
                    State.browser_error,
                    icon="circle-alert",
                    color="red",
                    size="1",
                ),
                padding="1em",
            ),
        ),
        spacing="0",
        width="100%",
        height="100%",
        bg=rx.color("gray", 2),
    )


# =============================================================================
# MOBILE DRAWER - Using rx.drawer (template pattern)
# =============================================================================


def mobile_sidebar_drawer() -> rx.Component:
    """Mobile drawer using rx.drawer - template pattern."""
    return rx.drawer.root(
        rx.drawer.trigger(
            rx.icon_button(
                rx.icon("menu", size=20),
                size="2",
                variant="ghost",
                display=["flex", "flex", "none"],
            ),
        ),
        rx.drawer.overlay(z_index="5"),
        rx.drawer.portal(
            rx.drawer.content(
                rx.vstack(
                    rx.hstack(
                        rx.icon("library", size=16, color=styles.accent_text_color),
                        rx.text("Library", size="3", weight="bold"),
                        rx.spacer(),
                        rx.drawer.close(
                            rx.icon_button(
                                rx.icon("x", size=18),
                                size="2",
                                variant="ghost",
                            ),
                        ),
                        width="100%",
                        align="center",
                        padding="1em",
                        border_bottom=styles.border,
                    ),
                    rx.box(
                        navigation_sidebar(),
                        flex="1",
                        overflow_y="auto",
                        overflow_x="hidden",
                        width="100%",
                    ),
                    spacing="0",
                    height="100dvh",
                    width="100%",
                    overflow="hidden",
                ),
                width=styles.sidebar_width,
                max_width="85vw",
                padding="0",
                bg=rx.color("gray", 1),
                overflow="hidden",
            ),
        ),
        direction="left",
    )


def library_list() -> rx.Component:
    """Exported for compatibility."""
    return rx.fragment()
