"""Batch operation state management."""

import asyncio
from typing import TypedDict

import reflex as rx

from salsa.frontend.api import APIError, api
from salsa.frontend.state.browser import BrowserState


class BatchResultItem(TypedDict, total=False):
    """Batch result item type."""

    rating_key: str
    title: str
    success: bool
    skipped: bool
    error: str
    match_level: str
    already_selected: bool


class ScopeOption(TypedDict):
    """Scope option type."""

    value: str
    label: str


class BatchState(BrowserState):
    """State for batch update operations."""

    batch_id: str = ""
    batch_status: str = ""
    batch_total: int = 0
    batch_processed: int = 0
    batch_success: int = 0
    batch_failed: int = 0
    batch_skipped: int = 0
    batch_current_item: str | None = None
    batch_message: str = ""
    batch_results: list[BatchResultItem] = []

    show_batch_modal: bool = False
    batch_scope: str = "episode"
    batch_stream_type: str = "audio"
    batch_keyword_filter: str = ""
    batch_set_none: bool = False
    is_batch_running: bool = False
    batch_error: str = ""

    @rx.var
    def batch_progress_percent(self) -> int:
        """Calculate batch progress percentage."""
        if self.batch_total == 0:
            return 0
        return int((self.batch_processed / self.batch_total) * 100)

    @rx.var
    def can_start_batch(self) -> bool:
        """Check if batch can be started."""
        if self.batch_stream_type == "audio":
            return self.selected_audio_stream is not None
        else:
            return self.selected_subtitle_stream is not None or self.batch_set_none

    @rx.var
    def batch_scope_options(self) -> list[ScopeOption]:
        """Get available batch scope options based on current selection."""
        options: list[ScopeOption] = []

        if self.selected_episode_key:
            options.append({"value": "episode", "label": "This Episode"})
        if self.selected_season_key:
            options.append({"value": "season", "label": "Entire Season"})
        if self.selected_item_key and self.selected_item_type == "show":
            options.append({"value": "show", "label": "Entire Show"})
        if self.selected_library_key:
            options.append({"value": "library", "label": "Entire Library"})

        return options

    @rx.var
    def batch_target_key(self) -> str:
        """Get the target key based on selected scope."""
        if self.batch_scope == "episode":
            return self.selected_episode_key
        elif self.batch_scope == "season":
            return self.selected_season_key
        elif self.batch_scope == "show":
            return self.selected_item_key
        elif self.batch_scope == "library":
            return self.selected_library_key
        return ""

    @rx.var
    def source_stream_id(self) -> int:
        """Get the source stream ID for matching."""
        if self.batch_stream_type == "audio":
            stream = self.selected_audio_stream
        else:
            stream = self.selected_subtitle_stream
        return stream.get("id", 0) if stream else 0

    @rx.event
    async def open_batch_modal(self, stream_type: str = "audio"):
        """Open the batch operation modal, or apply directly at episode level."""
        self.batch_stream_type = stream_type
        self.batch_keyword_filter = ""
        self.batch_set_none = False
        self.batch_error = ""
        self._reset_batch_state()

        if self.selected_episode_key:
            self.batch_scope = "episode"
            yield BatchState.start_batch
            return

        self.batch_scope = "season" if self.selected_season_key else "show"
        self.show_batch_modal = True

    @rx.event
    def close_batch_modal(self):
        """Close the batch modal."""
        self.show_batch_modal = False
        self._reset_batch_state()

    @rx.event
    def set_batch_scope(self, scope: str):
        """Set the batch scope."""
        self.batch_scope = scope

    @rx.event
    def set_keyword_filter(self, value: str):
        """Set the keyword filter."""
        self.batch_keyword_filter = value

    @rx.event
    def toggle_set_none(self):
        """Toggle the set_none option for subtitles."""
        self.batch_set_none = not self.batch_set_none

    @rx.event
    async def start_batch(self):
        """Start a batch operation."""
        if not self.can_start_batch:
            self.batch_error = "No source stream selected"
            return

        target_key = self.batch_target_key
        if not target_key:
            self.batch_error = "No target selected"
            return

        self.is_batch_running = True
        self.batch_error = ""
        self._reset_batch_state()

        try:
            source_key = self.selected_episode_key or self.selected_item_key

            result = await api.start_batch(
                token=self.token,
                scope=self.batch_scope,
                stream_type=self.batch_stream_type,
                target_rating_key=target_key,
                source_stream_id=self.source_stream_id,
                source_rating_key=source_key,
                keyword_filter=self.batch_keyword_filter or None,
                set_none=self.batch_set_none,
            )

            self.batch_id = result.get("batch_id", "")
            self.batch_status = result.get("status", "running")
            self.batch_total = result.get("total_items", 0)

            yield BatchState.poll_batch_progress

        except APIError as e:
            self.batch_error = f"Failed to start batch: {e.message}"
            self.is_batch_running = False

    @rx.event(background=True)
    async def poll_batch_progress(self):
        """Poll for batch operation progress."""
        while True:
            async with self:
                if not self.is_batch_running or not self.batch_id:
                    return
                token = self.token
                batch_id = self.batch_id

            try:
                result = await api.get_batch_progress(token, batch_id)

                async with self:
                    self.batch_status = result.get("status", "")
                    self.batch_total = result.get("total", 0)
                    self.batch_processed = result.get("processed", 0)
                    self.batch_success = result.get("success", 0)
                    self.batch_failed = result.get("failed", 0)
                    self.batch_skipped = result.get("skipped", 0)
                    self.batch_current_item = result.get("current_item", "")
                    self.batch_message = result.get("message", "")

                    if self.batch_status == "completed":
                        self.is_batch_running = False
                        await self._load_batch_results()
                        msg = f"Done! {self.batch_success} updated"
                        if self.batch_skipped > 0:
                            msg += f", {self.batch_skipped} skipped"
                        if self.batch_failed > 0:
                            msg += f", {self.batch_failed} failed"
                        return rx.toast.success(msg)

                    if self.batch_status == "failed":
                        self.is_batch_running = False
                        await self._load_batch_results()
                        return rx.toast.error(
                            f"Batch failed: {self.batch_message or 'Unknown error'}"
                        )

            except APIError as e:
                async with self:
                    self.batch_error = f"Error checking progress: {e.message}"
                    self.is_batch_running = False
                return rx.toast.error(f"Error: {e.message}")

            await asyncio.sleep(0.5)

    async def _load_batch_results(self):
        """Load final batch results."""
        if not self.batch_id:
            return

        try:
            result = await api.get_batch_result(self.token, self.batch_id)
            self.batch_results = result.get("results", [])
        except APIError:
            pass

    def _reset_batch_state(self):
        """Reset batch operation state."""
        self.batch_id = ""
        self.batch_status = ""
        self.batch_total = 0
        self.batch_processed = 0
        self.batch_success = 0
        self.batch_failed = 0
        self.batch_skipped = 0
        self.batch_current_item = None
        self.batch_message = ""
        self.batch_results = []

    @rx.event
    async def apply_audio_to_scope(
        self, language: str, sample_stream_id: int, sample_rating_key: str
    ):
        """Apply audio language to all episodes in current scope (show or season)."""
        if self.selected_season_key:
            scope = "season"
            target_key = self.selected_season_key
            scope_label = f"season '{self.selected_season_title}'"
        elif self.selected_item_key and self.selected_item_type == "show":
            scope = "show"
            target_key = self.selected_item_key
            scope_label = f"show '{self.selected_item_title}'"
        else:
            yield rx.toast.error("No show or season selected")
            return

        if not sample_stream_id or not sample_rating_key:
            yield rx.toast.error("No sample stream available for this language")
            return

        self.is_batch_running = True
        self.batch_error = ""
        self._reset_batch_state()

        try:
            result = await api.start_batch(
                token=self.token,
                scope=scope,
                stream_type="audio",
                target_rating_key=target_key,
                source_stream_id=sample_stream_id,
                source_rating_key=sample_rating_key,
            )

            self.batch_id = result.get("batch_id", "")
            self.batch_status = result.get("status", "running")
            self.batch_total = result.get("total_items", 0)

            yield rx.toast.info(f"Setting {language} audio for {scope_label}...")
            yield BatchState.poll_batch_progress

        except APIError as e:
            self.batch_error = f"Failed to start batch: {e.message}"
            self.is_batch_running = False
            yield rx.toast.error(f"Failed: {e.message}")

    @rx.event
    async def apply_subtitle_to_scope(
        self,
        language: str,
        sample_stream_id: int | None = None,
        sample_rating_key: str | None = None,
    ):
        """Apply subtitle language to all episodes in current scope (show or season)."""
        if self.selected_season_key:
            scope = "season"
            target_key = self.selected_season_key
            scope_label = f"season '{self.selected_season_title}'"
        elif self.selected_item_key and self.selected_item_type == "show":
            scope = "show"
            target_key = self.selected_item_key
            scope_label = f"show '{self.selected_item_title}'"
        else:
            yield rx.toast.error("No show or season selected")
            return

        set_none = language == "none"

        if not set_none and (not sample_stream_id or not sample_rating_key):
            yield rx.toast.error("No sample stream available for this language")
            return

        self.is_batch_running = True
        self.batch_error = ""
        self._reset_batch_state()

        try:
            result = await api.start_batch(
                token=self.token,
                scope=scope,
                stream_type="subtitle",
                target_rating_key=target_key,
                source_stream_id=sample_stream_id or 0,
                source_rating_key=sample_rating_key,
                set_none=set_none,
            )

            self.batch_id = result.get("batch_id", "")
            self.batch_status = result.get("status", "running")
            self.batch_total = result.get("total_items", 0)

            msg = (
                f"Disabling subtitles for {scope_label}..."
                if set_none
                else f"Setting {language} subtitles for {scope_label}..."
            )
            yield rx.toast.info(msg)
            yield BatchState.poll_batch_progress

        except APIError as e:
            self.batch_error = f"Failed to start batch: {e.message}"
            self.is_batch_running = False
            yield rx.toast.error(f"Failed: {e.message}")
