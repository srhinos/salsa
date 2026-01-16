"""Track table components - Following official Reflex dashboard template patterns."""

import reflex as rx

from salsa.frontend import styles
from salsa.frontend.state import State
from salsa.frontend.state.browser import StreamItem


# =============================================================================
# MAIN TRACK PANEL
# =============================================================================

def track_panel() -> rx.Component:
    """Main panel showing audio and subtitle tracks."""
    return rx.cond(
        State.is_loading_streams,
        rx.center(
            rx.vstack(
                rx.spinner(size="3"),
                rx.text("Loading streams...", size="2", color=rx.color("gray", 9)),
                spacing="3",
            ),
            padding="8",
            height="100%",
        ),
        rx.cond(
            State.has_streams,
            _episode_track_panel(),
            rx.cond(
                (State.selected_item_type == "show") | (State.selected_season_key != ""),
                _show_season_summary_panel(),
                _empty_state(),
            ),
        ),
    )


def _empty_state() -> rx.Component:
    """Empty state when nothing selected."""
    return rx.center(
        rx.vstack(
            rx.icon("clapperboard", size=48, color=styles.accent_text_color),
            rx.heading("Select Media", size="5", weight="medium"),
            rx.text(
                "Choose a show, season, or episode from the sidebar",
                size="2",
                color=rx.color("gray", 9),
                text_align="center",
            ),
            spacing="4",
            align="center",
        ),
        padding="8",
        height="100%",
    )


# =============================================================================
# EPISODE TRACK PANEL
# =============================================================================

def _episode_track_panel() -> rx.Component:
    """Track panel for individual episode/movie."""
    return rx.vstack(
        rx.hstack(
            rx.foreach(
                State.breadcrumbs,
                lambda crumb, idx: rx.hstack(
                    rx.cond(
                        idx > 0,
                        rx.icon("chevron-right", size=12, color=rx.color("gray", 9)),
                    ),
                    rx.text(crumb["title"], size="2", color=styles.text_color),
                    spacing="2",
                    align="center",
                ),
            ),
            spacing="2",
            align="center",
            wrap="wrap",
            padding="3",
            background=styles.gray_bg_color,
            border_radius=styles.border_radius,
            width="100%",
        ),

        audio_track_section(),

        subtitle_track_section(),

        spacing="4",
        width="100%",
    )


# =============================================================================
# SHOW/SEASON SUMMARY PANEL
# =============================================================================

def _show_season_summary_panel() -> rx.Component:
    """Summary panel for show or season level with batch selectors."""
    return rx.vstack(
        rx.card(
            rx.hstack(
                rx.icon("tv", size=24, color=styles.accent_text_color),
                rx.vstack(
                    rx.heading(
                        rx.cond(
                            State.selected_season_key != "",
                            State.selected_season_title,
                            State.selected_item_title,
                        ),
                        size="5",
                        weight="bold",
                    ),
                    rx.text(
                        "Manage audio & subtitles for all episodes",
                        size="2",
                        color=rx.color("gray", 9),
                    ),
                    spacing="1",
                    align="start",
                ),
                spacing="4",
                align="center",
            ),
            size="3",
            width="100%",
        ),

        rx.cond(
            State.is_batch_running,
            rx.card(
                rx.vstack(
                    rx.hstack(
                        rx.spinner(size="2"),
                        rx.text(
                            rx.cond(
                                State.batch_current_item is not None,
                                f"Processing: {State.batch_current_item}",
                                "Starting batch operation...",
                            ),
                            size="2",
                            weight="medium",
                        ),
                        spacing="2",
                        align="center",
                    ),
                    rx.progress(
                        value=State.batch_progress_percent,
                        width="100%",
                        color_scheme="orange",
                    ),
                    rx.text(
                        f"{State.batch_processed}/{State.batch_total} items",
                        size="1",
                        color=rx.color("gray", 9),
                    ),
                    spacing="3",
                    width="100%",
                ),
                size="2",
            ),
        ),

        rx.cond(
            State.is_loading_summary,
            rx.center(
                rx.vstack(
                    rx.spinner(size="3"),
                    rx.text("Analyzing streams...", size="2", color=rx.color("gray", 9)),
                    spacing="3",
                ),
                padding="6",
            ),
            rx.cond(
                State.stream_summary is not None,
                rx.vstack(
                    rx.hstack(
                        rx.badge(
                            State.stream_summary["total_items"].to(str) + " episodes",
                            size="1",
                            variant="soft",
                        ),
                        spacing="2",
                    ),

                    _audio_selector_card(),

                    _subtitle_selector_card(),

                    spacing="4",
                    width="100%",
                ),
                rx.center(
                    rx.text("Select a show or season", size="2", color=rx.color("gray", 9)),
                    padding="8",
                ),
            ),
        ),

        spacing="5",
        width="100%",
    )


# =============================================================================
# AUDIO SELECTOR CARD
# =============================================================================

def _current_audio_indicator() -> rx.Component:
    """Current audio selection badge."""
    return rx.cond(
        State.has_current_audio,
        rx.hstack(
            rx.badge("Current", size="1", variant="soft"),
            rx.text(State.current_audio_text, size="2", weight="medium"),
            spacing="2",
            align="center",
            padding="2",
            background=styles.accent_bg_color,
            border_radius=styles.border_radius,
            width="100%",
        ),
    )


def _audio_selector_card() -> rx.Component:
    """Audio language selector card."""
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.icon("volume-2", size=16, color=styles.accent_text_color),
                rx.text("Audio Track", size="3", weight="bold"),
                spacing="2",
                align="center",
            ),

            rx.separator(size="4"),

            _current_audio_indicator(),

            rx.box(
                rx.foreach(
                    State.stream_summary["audio_summary"],
                    _audio_language_button,
                ),
                display="grid",
                grid_template_columns="repeat(auto-fill, minmax(140px, 1fr))",
                gap="3",
                width="100%",
            ),

            spacing="4",
            width="100%",
        ),
        size="3",
        width="100%",
    )


def _audio_language_button(item: dict) -> rx.Component:
    """Language button in grid."""
    total = State.stream_summary["total_items"]
    count = item["count"]
    is_complete = count == total
    is_current = State.current_audio_language == item["language"]

    return rx.box(
        rx.vstack(
            rx.text(
                item["language"],
                size="2",
                weight=rx.cond(is_current, "medium", "regular"),
            ),
            rx.badge(
                f"{count}/{total}",
                size="1",
                variant="soft",
                color_scheme=rx.cond(is_complete, "teal", "gray"),
            ),
            spacing="2",
            align="center",
        ),
        padding="3",
        border_radius=styles.border_radius,
        cursor=rx.cond(State.is_batch_running, "not-allowed", "pointer"),
        opacity=rx.cond(State.is_batch_running, "0.5", "1"),
        color=rx.cond(is_current, styles.accent_text_color, styles.text_color),
        background=rx.cond(is_current, styles.accent_bg_color, "transparent"),
        border=rx.cond(is_current, f"1px solid {styles.accent_text_color}", styles.border),
        style={
            "_hover": {
                "background_color": rx.cond(is_current, styles.accent_bg_color, styles.gray_bg_color),
            },
        },
        pointer_events=rx.cond(State.is_batch_running, "none", "auto"),
        on_click=State.apply_audio_to_scope(
            item["language"],
            item["sample_stream_id"],
            item["sample_rating_key"],
        ),
    )


# =============================================================================
# SUBTITLE SELECTOR CARD
# =============================================================================

def _current_subtitle_indicator() -> rx.Component:
    """Current subtitle selection badge."""
    return rx.cond(
        State.has_current_subtitle,
        rx.hstack(
            rx.badge(
                "Current",
                size="1",
                variant="soft",
                color_scheme=rx.cond(State.current_subtitle_is_disabled, "gray", "orange"),
            ),
            rx.text(State.current_subtitle_text, size="2", weight="medium"),
            spacing="2",
            align="center",
            padding="2",
            background=rx.cond(
                State.current_subtitle_is_disabled,
                styles.gray_bg_color,
                styles.accent_bg_color,
            ),
            border_radius=styles.border_radius,
            width="100%",
        ),
    )


def _subtitle_selector_card() -> rx.Component:
    """Subtitle language selector card."""
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.icon("captions", size=16, color=styles.accent_text_color),
                rx.text("Subtitle Track", size="3", weight="bold"),
                rx.spacer(),
                rx.button(
                    "Disable All",
                    size="1",
                    variant="soft",
                    color_scheme="gray",
                    on_click=State.apply_subtitle_to_scope("none", None, None),
                    disabled=State.is_batch_running,
                ),
                spacing="2",
                align="center",
                width="100%",
            ),

            rx.separator(size="4"),

            _current_subtitle_indicator(),

            rx.box(
                rx.foreach(
                    State.stream_summary["subtitle_summary"],
                    _subtitle_language_button,
                ),
                display="grid",
                grid_template_columns="repeat(auto-fill, minmax(140px, 1fr))",
                gap="3",
                width="100%",
            ),

            spacing="4",
            width="100%",
        ),
        size="3",
        width="100%",
    )


def _subtitle_language_button(item: dict) -> rx.Component:
    """Language button in grid."""
    total = State.stream_summary["total_items"]
    count = item["count"]
    is_complete = count == total
    is_current = State.current_subtitle_language == item["language"]

    return rx.box(
        rx.vstack(
            rx.text(
                item["language"],
                size="2",
                weight=rx.cond(is_current, "medium", "regular"),
            ),
            rx.badge(
                f"{count}/{total}",
                size="1",
                variant="soft",
                color_scheme=rx.cond(is_complete, "teal", "gray"),
            ),
            spacing="2",
            align="center",
        ),
        padding="3",
        border_radius=styles.border_radius,
        cursor=rx.cond(State.is_batch_running, "not-allowed", "pointer"),
        opacity=rx.cond(State.is_batch_running, "0.5", "1"),
        color=rx.cond(is_current, styles.accent_text_color, styles.text_color),
        background=rx.cond(is_current, styles.accent_bg_color, "transparent"),
        border=rx.cond(is_current, f"1px solid {styles.accent_text_color}", styles.border),
        style={
            "_hover": {
                "background_color": rx.cond(is_current, styles.accent_bg_color, styles.gray_bg_color),
            },
        },
        pointer_events=rx.cond(State.is_batch_running, "none", "auto"),
        on_click=State.apply_subtitle_to_scope(
            item["language"],
            item["sample_stream_id"],
            item["sample_rating_key"],
        ),
    )


# =============================================================================
# AUDIO TRACK SECTION (TABLE)
# =============================================================================

def audio_track_section() -> rx.Component:
    """Audio tracks table section."""
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.icon("volume-2", size=16, color=styles.accent_text_color),
                rx.text("Audio Tracks", size="3", weight="bold"),
                spacing="2",
                align="center",
            ),
            rx.separator(size="4"),
            rx.cond(
                State.audio_streams.length() > 0,
                rx.box(
                    rx.table.root(
                        rx.table.header(
                            rx.table.row(
                                rx.table.column_header_cell(""),
                                rx.table.column_header_cell("Language"),
                                rx.table.column_header_cell("Title"),
                                rx.table.column_header_cell("Codec"),
                                rx.table.column_header_cell("Channels"),
                            ),
                        ),
                        rx.table.body(
                            rx.foreach(State.audio_streams, _audio_row),
                        ),
                        width="100%",
                        size="2",
                    ),
                    overflow_x="auto",
                    width="100%",
                ),
                rx.center(
                    rx.text("No audio tracks", size="2", color=rx.color("gray", 9)),
                    padding="4",
                ),
            ),
            spacing="3",
            width="100%",
        ),
        size="2",
    )


def _audio_row(stream: StreamItem) -> rx.Component:
    """Audio track table row."""
    return rx.table.row(
        rx.table.cell(
            rx.cond(
                stream["selected"],
                rx.icon("circle-check", size=16, color=styles.accent_text_color),
                rx.icon("circle", size=16, color=rx.color("gray", 6)),
            ),
        ),
        rx.table.cell(
            rx.hstack(
                rx.text(rx.cond(stream["language"], stream["language"], "Unknown"), size="2"),
                rx.cond(
                    stream["default"],
                    rx.badge("Default", size="1", variant="soft", color_scheme="blue"),
                ),
                spacing="2",
            ),
        ),
        rx.table.cell(
            rx.text(rx.cond(stream["title"], stream["title"], "-"), size="2", truncate=True),
        ),
        rx.table.cell(
            rx.badge(rx.cond(stream["codec"], stream["codec"], "?"), size="1", variant="soft"),
        ),
        rx.table.cell(
            rx.text(
                rx.match(
                    stream["channels"],
                    (2, "Stereo"),
                    (6, "5.1"),
                    (8, "7.1"),
                    stream["channels"].to(str),
                ),
                size="2",
            ),
        ),
        style={
            "background": rx.cond(stream["selected"], styles.accent_bg_color, "transparent"),
        },
        cursor="pointer",
        on_click=lambda: State.set_audio_stream(stream["id"]),
    )


# =============================================================================
# SUBTITLE TRACK SECTION (TABLE)
# =============================================================================

def subtitle_track_section() -> rx.Component:
    """Subtitle tracks table section."""
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.icon("captions", size=16, color=styles.accent_text_color),
                rx.text("Subtitle Tracks", size="3", weight="bold"),
                rx.spacer(),
                rx.button(
                    rx.icon("x", size=14),
                    "None",
                    size="1",
                    variant="soft",
                    color_scheme="gray",
                    on_click=lambda: State.set_subtitle_stream(0),
                ),
                width="100%",
                align="center",
                spacing="2",
            ),
            rx.separator(size="4"),
            rx.cond(
                State.subtitle_streams.length() > 0,
                rx.box(
                    rx.table.root(
                        rx.table.header(
                            rx.table.row(
                                rx.table.column_header_cell(""),
                                rx.table.column_header_cell("Language"),
                                rx.table.column_header_cell("Title"),
                                rx.table.column_header_cell("Codec"),
                                rx.table.column_header_cell("Flags"),
                            ),
                        ),
                        rx.table.body(
                            rx.foreach(State.subtitle_streams, _subtitle_row),
                        ),
                        width="100%",
                        size="2",
                    ),
                    overflow_x="auto",
                    width="100%",
                ),
                rx.center(
                    rx.text("No subtitle tracks", size="2", color=rx.color("gray", 9)),
                    padding="4",
                ),
            ),
            spacing="3",
            width="100%",
        ),
        size="2",
    )


def _subtitle_row(stream: dict) -> rx.Component:
    """Subtitle track table row."""
    return rx.table.row(
        rx.table.cell(
            rx.cond(
                stream["selected"],
                rx.icon("circle-check", size=16, color=styles.accent_text_color),
                rx.icon("circle", size=16, color=rx.color("gray", 6)),
            ),
        ),
        rx.table.cell(
            rx.hstack(
                rx.text(rx.cond(stream["language"], stream["language"], "Unknown"), size="2"),
                rx.cond(
                    stream["default"],
                    rx.badge("Default", size="1", variant="soft", color_scheme="blue"),
                ),
                spacing="2",
            ),
        ),
        rx.table.cell(
            rx.text(rx.cond(stream["title"], stream["title"], "-"), size="2", truncate=True),
        ),
        rx.table.cell(
            rx.badge(rx.cond(stream["codec"], stream["codec"], "?"), size="1", variant="soft"),
        ),
        rx.table.cell(
            rx.cond(
                stream["forced"],
                rx.badge("Forced", size="1", variant="soft", color_scheme="orange"),
                rx.fragment(),
            ),
        ),
        style={
            "background": rx.cond(stream["selected"], styles.accent_bg_color, "transparent"),
        },
        cursor="pointer",
        on_click=lambda: State.set_subtitle_stream(stream["id"]),
    )
