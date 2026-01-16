"""Batch operation modal component."""

import reflex as rx

from salsa.frontend.state import State


def batch_modal() -> rx.Component:
    """Modal for batch update operations."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title(
                rx.hstack(
                    rx.cond(
                        State.batch_stream_type == "audio",
                        rx.icon("volume-2", size=20),
                        rx.icon("captions", size=20),
                    ),
                    rx.text(f"Batch Update {State.batch_stream_type.capitalize()} Tracks"),
                    spacing="2",
                ),
            ),
            rx.dialog.description(
                "Apply the current track selection to multiple items.",
                size="2",
            ),

            rx.cond(
                State.is_batch_running,
                _batch_progress(),
                rx.cond(
                    State.batch_status == "completed",
                    _batch_results(),
                    _batch_form(),
                ),
            ),

            max_width="500px",
        ),
        open=State.show_batch_modal,
        on_open_change=lambda open: rx.cond(
            ~open,
            State.close_batch_modal,
            rx.noop(),
        ),
    )


def _batch_form() -> rx.Component:
    """Batch operation configuration form."""
    return rx.vstack(
        rx.cond(
            State.batch_error != "",
            rx.callout(
                State.batch_error,
                icon="circle-alert",
                color="red",
                size="1",
            ),
        ),

        rx.vstack(
            rx.text("Apply to:", size="2", weight="medium"),
            rx.select.root(
                rx.select.trigger(width="100%"),
                rx.select.content(
                    rx.foreach(
                        State.batch_scope_options,
                        lambda opt: rx.select.item(
                            opt["label"],
                            value=opt["value"],
                        ),
                    ),
                ),
                value=State.batch_scope,
                on_change=State.set_batch_scope,
            ),
            spacing="1",
            width="100%",
        ),

        rx.vstack(
            rx.text("Keyword filter (optional):", size="2", weight="medium"),
            rx.input(
                placeholder="e.g., 'Commentary', 'English'",
                value=State.batch_keyword_filter,
                on_change=State.set_keyword_filter,
                width="100%",
            ),
            rx.text(
                "Only match streams containing this keyword",
                size="1",
                color_scheme="gray",
            ),
            spacing="1",
            width="100%",
        ),

        rx.cond(
            State.batch_stream_type == "subtitle",
            rx.hstack(
                rx.checkbox(
                    checked=State.batch_set_none,
                    on_change=State.toggle_set_none,
                ),
                rx.text("Disable subtitles instead of matching", size="2"),
                spacing="2",
            ),
        ),

        rx.card(
            rx.vstack(
                rx.text("Source stream:", size="2", weight="medium"),
                rx.cond(
                    State.batch_stream_type == "audio",
                    rx.cond(
                        State.selected_audio_stream,
                        rx.text(
                            State.selected_audio_stream["display_title"],
                            size="2",
                        ),
                        rx.text("None selected", size="2", color_scheme="gray"),
                    ),
                    rx.cond(
                        State.batch_set_none,
                        rx.text("(Disable subtitles)", size="2", color_scheme="gray"),
                        rx.cond(
                            State.selected_subtitle_stream,
                            rx.text(
                                State.selected_subtitle_stream["display_title"],
                                size="2",
                            ),
                            rx.text("None selected", size="2", color_scheme="gray"),
                        ),
                    ),
                ),
                spacing="1",
                width="100%",
            ),
            size="1",
            variant="surface",
        ),

        rx.hstack(
            rx.dialog.close(
                rx.button("Cancel", variant="soft", color_scheme="gray"),
            ),
            rx.button(
                "Start Batch",
                on_click=State.start_batch,
                disabled=~State.can_start_batch,
            ),
            spacing="3",
            justify="end",
            width="100%",
        ),

        spacing="4",
        width="100%",
        padding_top="4",
    )


def _batch_progress() -> rx.Component:
    """Batch operation progress display."""
    return rx.vstack(
        rx.text(State.batch_message, size="2"),

        rx.progress(
            value=State.batch_progress_percent,
            max=100,
            width="100%",
        ),

        rx.hstack(
            rx.text(f"{State.batch_processed} / {State.batch_total}", size="2"),
            rx.spacer(),
            rx.text(f"{State.batch_progress_percent}%", size="2", weight="medium"),
            width="100%",
        ),

        rx.cond(
            State.batch_current_item != "",
            rx.text(
                f"Processing: {State.batch_current_item}",
                size="1",
                color_scheme="gray",
                truncate=True,
            ),
        ),

        rx.hstack(
            rx.badge(f"{State.batch_success} updated", color_scheme="green", size="1"),
            rx.badge(f"{State.batch_skipped} skipped", color_scheme="gray", size="1"),
            rx.badge(f"{State.batch_failed} failed", color_scheme="red", size="1"),
            spacing="2",
        ),

        spacing="3",
        width="100%",
        padding_y="4",
    )


def _batch_results() -> rx.Component:
    """Batch operation results summary."""
    return rx.vstack(
        rx.cond(
            State.batch_status == "completed",
            rx.callout(
                f"Completed: {State.batch_success} updated, {State.batch_skipped} skipped, {State.batch_failed} failed",
                icon="circle-check",
                color="green",
            ),
            rx.callout(
                State.batch_message,
                icon="circle-x",
                color="red",
            ),
        ),

        rx.cond(
            State.batch_failed > 0,
            rx.accordion.root(
                rx.accordion.item(
                    header="Show failed items",
                    content=rx.scroll_area(
                        rx.vstack(
                            rx.foreach(
                                State.batch_results,
                                lambda r: rx.cond(
                                    ~r["success"],
                                    rx.hstack(
                                        rx.text(r["title"], size="1", truncate=True),
                                        rx.text(rx.cond(r["error"], r["error"], "Unknown error"), size="1", color_scheme="red"),
                                        spacing="2",
                                        width="100%",
                                    ),
                                ),
                            ),
                            spacing="1",
                        ),
                        type="hover",
                        style={"max-height": "150px"},
                    ),
                ),
                type="single",
                collapsible=True,
            ),
        ),

        rx.hstack(
            rx.dialog.close(
                rx.button("Close", variant="soft"),
            ),
            justify="end",
            width="100%",
        ),

        spacing="4",
        width="100%",
        padding_y="4",
    )
