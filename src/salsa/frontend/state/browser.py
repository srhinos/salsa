"""Browser state for navigating media libraries."""

from typing import TypedDict

import reflex as rx

from salsa.frontend.api import APIError, api
from salsa.frontend.state.auth import AuthState


class LibraryItem(TypedDict):
    """Library item type."""

    key: str
    title: str
    type: str
    uuid: str


class MediaItem(TypedDict, total=False):
    """Media item type (show, movie, season, episode)."""

    rating_key: str
    title: str
    type: str
    year: int
    thumb: str
    index: int
    parent_index: int
    grandparent_title: str
    has_streams: bool


class StreamItem(TypedDict, total=False):
    """Audio/subtitle stream type."""

    id: int
    stream_type: int
    codec: str
    language: str
    language_code: str
    title: str
    display_title: str
    selected: bool
    default: bool
    channels: int
    forced: bool


class LanguageCountItem(TypedDict, total=False):
    """Language count for stream summary."""

    language: str
    language_code: str | None
    count: int
    sample_stream_id: int | None
    sample_rating_key: str | None


class CurrentSelectionItem(TypedDict, total=False):
    """Currently selected stream info."""

    language: str
    count: int
    is_uniform: bool


class StreamSummaryItem(TypedDict):
    """Stream summary for a show or season."""

    rating_key: str
    title: str
    total_items: int
    audio_summary: list[LanguageCountItem]
    subtitle_summary: list[LanguageCountItem]
    current_audio: CurrentSelectionItem | None
    current_subtitle: CurrentSelectionItem | None


class BreadcrumbItem(TypedDict):
    """Breadcrumb item type."""

    key: str
    title: str
    level: str


class BrowserState(AuthState):
    """State for browsing media libraries."""

    mobile_menu_open: bool = False

    libraries: list[LibraryItem] = []
    selected_library_key: str = ""
    selected_library_title: str = ""
    selected_library_type: str = ""

    items: list[MediaItem] = []
    selected_item_key: str = ""
    selected_item_title: str = ""
    selected_item_type: str = ""

    seasons: list[MediaItem] = []
    selected_season_key: str = ""
    selected_season_title: str = ""

    episodes: list[MediaItem] = []
    selected_episode_key: str = ""
    selected_episode_title: str = ""

    current_part_id: int = 0
    audio_streams: list[StreamItem] = []
    subtitle_streams: list[StreamItem] = []

    stream_summary: StreamSummaryItem | None = None
    is_loading_summary: bool = False

    is_loading_libraries: bool = False
    is_loading_items: bool = False
    is_loading_seasons: bool = False
    is_loading_episodes: bool = False
    is_loading_streams: bool = False

    item_filter: str = ""
    season_filter: str = ""
    episode_filter: str = ""

    browser_error: str = ""

    @rx.event
    def toggle_mobile_menu(self):
        """Toggle the mobile sidebar menu."""
        self.mobile_menu_open = not self.mobile_menu_open

    @rx.event
    def close_mobile_menu(self):
        """Close the mobile sidebar menu."""
        self.mobile_menu_open = False

    @rx.event
    def set_item_filter(self, value: str):
        """Set the item filter."""
        self.item_filter = value

    @rx.event
    def set_season_filter(self, value: str):
        """Set the season filter."""
        self.season_filter = value

    @rx.event
    def set_episode_filter(self, value: str):
        """Set the episode filter."""
        self.episode_filter = value

    @rx.var
    def breadcrumbs(self) -> list[BreadcrumbItem]:
        """Generate breadcrumb navigation."""
        crumbs: list[BreadcrumbItem] = []

        if self.selected_library_title:
            crumbs.append({
                "key": self.selected_library_key,
                "title": self.selected_library_title,
                "level": "library",
            })

        if self.selected_item_title:
            crumbs.append({
                "key": self.selected_item_key,
                "title": self.selected_item_title,
                "level": "item",
            })

        if self.selected_season_title:
            crumbs.append({
                "key": self.selected_season_key,
                "title": self.selected_season_title,
                "level": "season",
            })

        if self.selected_episode_title:
            crumbs.append({
                "key": self.selected_episode_key,
                "title": self.selected_episode_title,
                "level": "episode",
            })

        return crumbs

    @rx.var
    def has_streams(self) -> bool:
        """Check if streams are loaded."""
        return len(self.audio_streams) > 0 or len(self.subtitle_streams) > 0

    @rx.var
    def selected_audio_stream(self) -> dict | None:
        """Get the currently selected audio stream."""
        for stream in self.audio_streams:
            if stream.get("selected"):
                return stream
        return None

    @rx.var
    def current_audio_text(self) -> str:
        """Get the current audio selection text for display."""
        if not self.stream_summary:
            return ""
        current = self.stream_summary.get("current_audio")
        if not current:
            return ""
        lang = current.get("language", "Unknown")
        count = current.get("count", 0)
        total = self.stream_summary.get("total_items", 0)
        is_uniform = current.get("is_uniform", False)
        if is_uniform:
            return f"{lang} on all episodes"
        return f"{lang} on {count}/{total} episodes"

    @rx.var
    def current_subtitle_text(self) -> str:
        """Get the current subtitle selection text for display."""
        if not self.stream_summary:
            return ""
        current = self.stream_summary.get("current_subtitle")
        if not current:
            return ""
        lang = current.get("language", "Unknown")
        count = current.get("count", 0)
        total = self.stream_summary.get("total_items", 0)
        is_uniform = current.get("is_uniform", False)
        if lang == "None":
            if is_uniform:
                return "Disabled on all episodes"
            return f"Disabled on {count}/{total} episodes"
        if is_uniform:
            return f"{lang} on all episodes"
        return f"{lang} on {count}/{total} episodes"

    @rx.var
    def has_current_audio(self) -> bool:
        """Check if there's current audio selection info."""
        if not self.stream_summary:
            return False
        return self.stream_summary.get("current_audio") is not None

    @rx.var
    def has_current_subtitle(self) -> bool:
        """Check if there's current subtitle selection info."""
        if not self.stream_summary:
            return False
        return self.stream_summary.get("current_subtitle") is not None

    @rx.var
    def current_subtitle_is_disabled(self) -> bool:
        """Check if current subtitle is disabled (None)."""
        if not self.stream_summary:
            return False
        current = self.stream_summary.get("current_subtitle")
        if not current:
            return False
        return current.get("language") == "None"

    @rx.var
    def current_audio_language(self) -> str:
        """Get the currently selected audio language name."""
        if not self.stream_summary:
            return ""
        current = self.stream_summary.get("current_audio")
        if not current:
            return ""
        return current.get("language", "")

    @rx.var
    def current_subtitle_language(self) -> str:
        """Get the currently selected subtitle language name."""
        if not self.stream_summary:
            return ""
        current = self.stream_summary.get("current_subtitle")
        if not current:
            return ""
        return current.get("language", "")

    @rx.var
    def selected_subtitle_stream(self) -> dict | None:
        """Get the currently selected subtitle stream."""
        for stream in self.subtitle_streams:
            if stream.get("selected"):
                return stream
        return None

    @rx.var
    def filtered_items(self) -> list[MediaItem]:
        """Items filtered by search string."""
        if not self.item_filter:
            return self.items
        search = self.item_filter.lower()
        return [
            i for i in self.items
            if search in i.get("title", "").lower()
            or search in str(i.get("year", ""))
        ]

    @rx.var
    def filtered_seasons(self) -> list[MediaItem]:
        """Seasons filtered by search string."""
        if not self.season_filter:
            return self.seasons
        search = self.season_filter.lower()
        return [
            s for s in self.seasons
            if search in s.get("title", "").lower()
        ]

    @rx.var
    def filtered_episodes(self) -> list[MediaItem]:
        """Episodes filtered by search string."""
        if not self.episode_filter:
            return self.episodes
        search = self.episode_filter.lower()
        return [
            e for e in self.episodes
            if search in e.get("title", "").lower()
            or search in str(e.get("index", ""))
        ]

    @rx.event
    async def load_libraries(self):
        """Load all libraries."""
        if not self.token:
            return

        self.is_loading_libraries = True
        self.browser_error = ""

        try:
            result = await api.get_libraries(self.token)
            self.libraries = result.get("libraries", [])
        except APIError as e:
            self.browser_error = f"Failed to load libraries: {e.message}"
        finally:
            self.is_loading_libraries = False

    @rx.event
    async def select_library(self, library_key: str):
        """Select a library and load its items."""
        library = next((l for l in self.libraries if l["key"] == library_key), None)
        if not library:
            return

        self.selected_library_key = library_key
        self.selected_library_title = library.get("title", "")
        self.selected_library_type = library.get("type", "")

        self._clear_item_selection()

        await self._load_items(library_key)

    async def _load_items(self, library_key: str):
        """Load items in a library."""
        self.is_loading_items = True
        self.browser_error = ""

        try:
            result = await api.get_library_items(self.token, library_key)
            self.items = result.get("items", [])
        except APIError as e:
            self.browser_error = f"Failed to load items: {e.message}"
        finally:
            self.is_loading_items = False

    @rx.event
    async def select_item(self, item_key: str):
        """Select an item (show/movie)."""
        item = next((i for i in self.items if i["rating_key"] == item_key), None)
        if not item:
            return

        self.selected_item_key = item_key
        self.selected_item_title = item.get("title", "")
        self.selected_item_type = item.get("type", "")

        self._clear_season_selection()

        if item.get("type") == "show":
            await self._load_seasons(item_key)
            yield BrowserState.load_stream_summary(item_key)
        elif item.get("type") == "movie":
            self.mobile_menu_open = False
            await self._load_streams(item_key)

    async def _load_seasons(self, show_key: str):
        """Load seasons for a show."""
        self.is_loading_seasons = True
        self.browser_error = ""

        try:
            result = await api.get_children(self.token, show_key)
            self.seasons = [
                c for c in result.get("children", [])
                if c.get("type") == "season"
            ]
        except APIError as e:
            self.browser_error = f"Failed to load seasons: {e.message}"
        finally:
            self.is_loading_seasons = False

    @rx.event
    async def select_season(self, season_key: str):
        """Select a season."""
        season = next((s for s in self.seasons if s["rating_key"] == season_key), None)
        if not season:
            return

        self.selected_season_key = season_key
        self.selected_season_title = season.get("title", "")

        self.mobile_menu_open = False

        self._clear_episode_selection()

        await self._load_episodes(season_key)

        yield BrowserState.load_stream_summary(season_key)

    async def _load_episodes(self, season_key: str):
        """Load episodes for a season."""
        self.is_loading_episodes = True
        self.browser_error = ""

        try:
            result = await api.get_children(self.token, season_key)
            self.episodes = [
                c for c in result.get("children", [])
                if c.get("type") == "episode"
            ]
        except APIError as e:
            self.browser_error = f"Failed to load episodes: {e.message}"
        finally:
            self.is_loading_episodes = False

    @rx.event
    async def select_episode(self, episode_key: str):
        """Select an episode and load its streams."""
        episode = next((e for e in self.episodes if e["rating_key"] == episode_key), None)
        if not episode:
            return

        self.selected_episode_key = episode_key
        self.selected_episode_title = episode.get("title", "")

        self.mobile_menu_open = False

        await self._load_streams(episode_key)

    async def _load_streams(self, rating_key: str):
        """Load streams for a media item."""
        self.is_loading_streams = True
        self.browser_error = ""

        try:
            result = await api.get_streams(self.token, rating_key)
            self.current_part_id = result.get("part_id", 0)
            self.audio_streams = result.get("audio_streams", [])
            self.subtitle_streams = result.get("subtitle_streams", [])
        except APIError as e:
            self.browser_error = f"Failed to load streams: {e.message}"
        finally:
            self.is_loading_streams = False

    @rx.event(background=True)
    async def load_stream_summary(self, rating_key: str):
        """Load aggregated stream summary for a show or season."""
        async with self:
            self.is_loading_summary = True
            self.stream_summary = None
            token = self.token

        try:
            result = await api.get_stream_summary(token, rating_key)
            async with self:
                self.stream_summary = result
        except APIError as e:
            async with self:
                self.browser_error = f"Failed to load stream summary: {e.message}"
        finally:
            async with self:
                self.is_loading_summary = False

    @rx.event
    async def set_audio_stream(self, stream_id: int):
        """Set the audio stream."""
        if not self.current_part_id:
            return

        try:
            await api.set_audio_track(self.token, self.current_part_id, stream_id)
            for stream in self.audio_streams:
                stream["selected"] = stream["id"] == stream_id
        except APIError as e:
            self.browser_error = f"Failed to set audio: {e.message}"

    @rx.event
    async def set_subtitle_stream(self, stream_id: int):
        """Set the subtitle stream (0 to disable)."""
        if not self.current_part_id:
            return

        try:
            await api.set_subtitle_track(self.token, self.current_part_id, stream_id)
            for stream in self.subtitle_streams:
                stream["selected"] = stream["id"] == stream_id
        except APIError as e:
            self.browser_error = f"Failed to set subtitle: {e.message}"

    @rx.event
    def navigate_to(self, level: str, key: str):
        """Navigate to a specific breadcrumb level."""
        if level == "library":
            self._clear_item_selection()
        elif level == "item":
            self._clear_season_selection()
        elif level == "season":
            self._clear_episode_selection()

    def _clear_item_selection(self):
        """Clear item and below."""
        self.selected_item_key = ""
        self.selected_item_title = ""
        self.selected_item_type = ""
        self.items = []
        self.item_filter = ""
        self.stream_summary = None
        self._clear_season_selection()

    def _clear_season_selection(self):
        """Clear season and below."""
        self.selected_season_key = ""
        self.selected_season_title = ""
        self.seasons = []
        self.season_filter = ""
        self._clear_episode_selection()

    def _clear_episode_selection(self):
        """Clear episode selection and streams."""
        self.selected_episode_key = ""
        self.selected_episode_title = ""
        self.episodes = []
        self.episode_filter = ""
        self._clear_streams()

    def _clear_streams(self):
        """Clear stream data."""
        self.current_part_id = 0
        self.audio_streams = []
        self.subtitle_streams = []

    @rx.event
    def clear_item_filter(self):
        """Clear item filter and scroll to selected item."""
        self.item_filter = ""
        if self.selected_item_key:
            return rx.call_script(
                f"setTimeout(() => document.getElementById('item-{self.selected_item_key}')?.scrollIntoView({{block: 'center', behavior: 'smooth'}}), 50)"
            )

    @rx.event
    def clear_episode_filter(self):
        """Clear episode filter and scroll to selected episode."""
        self.episode_filter = ""
        if self.selected_episode_key:
            return rx.call_script(
                f"setTimeout(() => document.getElementById('episode-{self.selected_episode_key}')?.scrollIntoView({{block: 'center', behavior: 'smooth'}}), 50)"
            )

    @rx.event
    def clear_item_selection(self):
        """Clear item selection and return to items list (public event)."""
        self.selected_item_key = ""
        self.selected_item_title = ""
        self.selected_item_type = ""
        self.stream_summary = None
        self._clear_season_selection()

    @rx.event
    def clear_season_selection(self):
        """Clear season selection and return to seasons list (public event)."""
        self.selected_season_key = ""
        self.selected_season_title = ""
        self._clear_episode_selection()
        if self.selected_item_key:
            return BrowserState.load_stream_summary(self.selected_item_key)
