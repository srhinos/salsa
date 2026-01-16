"""Pydantic models for Plex API data structures."""

from pydantic import BaseModel, Field

# =============================================================================
# =============================================================================


class PlexPin(BaseModel):
    """PIN for OAuth authentication flow."""

    id: int
    code: str
    auth_token: str | None = Field(default=None, alias="authToken")
    expires_in: int = Field(alias="expiresIn")
    client_identifier: str = Field(alias="clientIdentifier")

    model_config = {"populate_by_name": True}


class PlexUser(BaseModel):
    """Plex user information."""

    id: int
    uuid: str
    username: str
    title: str
    email: str | None = None
    thumb: str | None = None
    auth_token: str | None = Field(default=None, alias="authToken")

    model_config = {"populate_by_name": True}


class PlexHomeUser(BaseModel):
    """Managed/home user information."""

    id: int
    uuid: str
    title: str
    username: str | None = None
    thumb: str | None = None
    protected: bool = False
    admin: bool = False

    model_config = {"populate_by_name": True}


# =============================================================================
# =============================================================================


class PlexConnection(BaseModel):
    """Server connection option."""

    protocol: str
    address: str
    port: int
    uri: str
    local: bool
    relay: bool = False

    model_config = {"populate_by_name": True}


class PlexServer(BaseModel):
    """Plex server/resource information."""

    name: str
    product: str
    product_version: str = Field(alias="productVersion")
    platform: str | None = None
    client_identifier: str = Field(alias="clientIdentifier")
    access_token: str | None = Field(default=None, alias="accessToken")
    provides: str | None = None
    owned: bool = False
    connections: list[PlexConnection] = []

    model_config = {"populate_by_name": True}

    @property
    def is_plex_media_server(self) -> bool:
        """Check if this resource is a Plex Media Server."""
        return self.product == "Plex Media Server"


class PlexServerIdentity(BaseModel):
    """Server identity response."""

    machine_identifier: str = Field(alias="machineIdentifier")
    version: str | None = None

    model_config = {"populate_by_name": True}


# =============================================================================
# =============================================================================


class PlexLibrary(BaseModel):
    """Media library (section) or directory entry."""

    key: str | None = None
    title: str
    type: str | None = None
    uuid: str | None = None
    agent: str | None = None
    scanner: str | None = None

    model_config = {"populate_by_name": True}

    @property
    def is_video_library(self) -> bool:
        """Check if this is a video library (movies or shows)."""
        return self.type in ("movie", "show") if self.type else False


# =============================================================================
# =============================================================================


class PlexStream(BaseModel):
    """Audio or subtitle stream."""

    id: int
    stream_type: int = Field(alias="streamType")
    codec: str | None = None
    language: str | None = None
    language_code: str | None = Field(default=None, alias="languageCode")
    language_tag: str | None = Field(default=None, alias="languageTag")
    title: str | None = None
    display_title: str | None = Field(default=None, alias="displayTitle")
    selected: bool = False
    default: bool = False
    index: int | None = None
    channels: int | None = None
    audio_channel_layout: str | None = Field(default=None, alias="audioChannelLayout")
    bit_depth: int | None = Field(default=None, alias="bitDepth")
    bitrate: int | None = None
    forced: bool = False
    hearing_impaired: bool = Field(default=False, alias="hearingImpaired")

    model_config = {"populate_by_name": True}

    @property
    def is_audio(self) -> bool:
        """Check if this is an audio stream."""
        return self.stream_type == 2

    @property
    def is_subtitle(self) -> bool:
        """Check if this is a subtitle stream."""
        return self.stream_type == 3


class PlexPart(BaseModel):
    """Media part containing streams."""

    id: int
    key: str | None = None
    file: str | None = None
    container: str | None = None
    streams: list[PlexStream] = Field(default_factory=list, alias="Stream")

    model_config = {"populate_by_name": True}

    @property
    def audio_streams(self) -> list[PlexStream]:
        """Get audio streams only."""
        return [s for s in self.streams if s.is_audio]

    @property
    def subtitle_streams(self) -> list[PlexStream]:
        """Get subtitle streams only."""
        return [s for s in self.streams if s.is_subtitle]


class PlexMedia(BaseModel):
    """Media container with parts."""

    id: int
    duration: int | None = None
    bitrate: int | None = None
    video_codec: str | None = Field(default=None, alias="videoCodec")
    audio_codec: str | None = Field(default=None, alias="audioCodec")
    audio_channels: int | None = Field(default=None, alias="audioChannels")
    container: str | None = None
    video_resolution: str | None = Field(default=None, alias="videoResolution")
    parts: list[PlexPart] = Field(default_factory=list, alias="Part")

    model_config = {"populate_by_name": True}


class PlexMediaItem(BaseModel):
    """Base media item (movie, show, season, or episode)."""

    rating_key: str = Field(alias="ratingKey")
    key: str
    type: str
    title: str
    title_sort: str | None = Field(default=None, alias="titleSort")
    summary: str | None = None
    thumb: str | None = None
    art: str | None = None
    year: int | None = None
    duration: int | None = None

    index: int | None = None
    parent_index: int | None = Field(default=None, alias="parentIndex")
    parent_rating_key: str | None = Field(default=None, alias="parentRatingKey")
    parent_title: str | None = Field(default=None, alias="parentTitle")
    grandparent_rating_key: str | None = Field(default=None, alias="grandparentRatingKey")
    grandparent_title: str | None = Field(default=None, alias="grandparentTitle")

    media: list[PlexMedia] = Field(default_factory=list, alias="Media")

    model_config = {"populate_by_name": True}

    @property
    def is_movie(self) -> bool:
        return self.type == "movie"

    @property
    def is_show(self) -> bool:
        return self.type == "show"

    @property
    def is_season(self) -> bool:
        return self.type == "season"

    @property
    def is_episode(self) -> bool:
        return self.type == "episode"

    @property
    def has_media(self) -> bool:
        """Check if this item has media/stream information."""
        return len(self.media) > 0

    @property
    def first_part(self) -> PlexPart | None:
        """Get the first part of the first media (most common case)."""
        if self.media and self.media[0].parts:
            return self.media[0].parts[0]
        return None

    @property
    def display_name(self) -> str:
        """Human-readable name for display."""
        if self.is_episode:
            season = f"S{self.parent_index:02d}" if self.parent_index else "S??"
            episode = f"E{self.index:02d}" if self.index else "E??"
            return f"{season}{episode} - {self.title}"
        return self.title


# =============================================================================
# =============================================================================


class PlexMediaContainer(BaseModel):
    """Generic Plex API response container."""

    size: int = 0
    total_size: int | None = Field(default=None, alias="totalSize")
    offset: int | None = None
    identifier: str | None = None
    title1: str | None = None
    title2: str | None = None

    directory: list[PlexLibrary] = Field(default_factory=list, alias="Directory")
    metadata: list[PlexMediaItem] = Field(default_factory=list, alias="Metadata")
    device: list[PlexServer] = Field(default_factory=list, alias="Device")

    model_config = {"populate_by_name": True}


class PlexResponse(BaseModel):
    """Top-level Plex API response."""

    media_container: PlexMediaContainer = Field(alias="MediaContainer")

    model_config = {"populate_by_name": True}
