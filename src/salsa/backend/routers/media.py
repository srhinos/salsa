"""Media metadata and browsing API routes."""

import asyncio
import re
from collections import defaultdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from salsa.backend.config import Settings, get_settings
from salsa.backend.models.auth import ErrorResponse
from salsa.backend.models.plex import PlexMediaItem, PlexStream
from salsa.backend.routers.auth import get_token_from_header
from salsa.backend.routers.libraries import get_server_url
from salsa.backend.services.plex_client import (
    PlexClient,
    PlexClientError,
    PlexConnectionError,
)

router = APIRouter()

_TRACK_COUNT_PATTERN = re.compile(r"\s+\(\d+\)$")


# =============================================================================
# =============================================================================


class StreamResponse(BaseModel):
    """Audio or subtitle stream information."""

    id: int = Field(..., description="Stream ID")
    stream_type: int = Field(..., description="Stream type (2=audio, 3=subtitle)")
    codec: str | None = Field(default=None, description="Codec")
    language: str | None = Field(default=None, description="Language name")
    language_code: str | None = Field(default=None, description="Language code (e.g., 'en')")
    title: str | None = Field(default=None, description="Stream title")
    display_title: str | None = Field(default=None, description="Display title")
    selected: bool = Field(default=False, description="Currently selected")
    default: bool = Field(default=False, description="Default stream")
    channels: int | None = Field(default=None, description="Audio channels")
    forced: bool = Field(default=False, description="Forced subtitle")


class MediaStreamsResponse(BaseModel):
    """Streams for a media item."""

    rating_key: str = Field(..., description="Item rating key")
    title: str = Field(..., description="Item title")
    part_id: int | None = Field(default=None, description="Part ID for updates")
    audio_streams: list[StreamResponse] = Field(default_factory=list)
    subtitle_streams: list[StreamResponse] = Field(default_factory=list)


class MediaItemResponse(BaseModel):
    """Full media item with metadata."""

    rating_key: str
    key: str
    type: str
    title: str
    year: int | None = None
    summary: str | None = None
    thumb: str | None = None
    index: int | None = None
    parent_index: int | None = None
    parent_title: str | None = None
    grandparent_title: str | None = None
    has_streams: bool = False


class ChildrenResponse(BaseModel):
    """Children of a media item (seasons or episodes)."""

    parent_rating_key: str = Field(..., description="Parent item rating key")
    parent_title: str | None = Field(default=None, description="Parent item title")
    children: list[MediaItemResponse] = Field(default_factory=list)
    total: int = Field(..., description="Total number of children")


class LanguageCount(BaseModel):
    """Language count for stream summary."""

    language: str = Field(..., description="Language name")
    language_code: str | None = Field(default=None, description="ISO language code")
    count: int = Field(..., description="Number of items with this language")
    sample_stream_id: int | None = Field(
        default=None, description="Stream ID from first episode with this language"
    )
    sample_rating_key: str | None = Field(
        default=None, description="Rating key of episode containing sample stream"
    )


class CurrentSelection(BaseModel):
    """Currently selected stream info across episodes."""

    language: str = Field(..., description="Language name")
    count: int = Field(..., description="Number of episodes with this selection")
    is_uniform: bool = Field(
        ..., description="True if all episodes have the same selection"
    )


class StreamSummaryResponse(BaseModel):
    """Aggregated stream summary for a show or season."""

    rating_key: str = Field(..., description="Item rating key")
    title: str = Field(..., description="Item title")
    total_items: int = Field(..., description="Total number of episodes/items analyzed")
    audio_summary: list[LanguageCount] = Field(
        default_factory=list, description="Audio track language counts"
    )
    subtitle_summary: list[LanguageCount] = Field(
        default_factory=list, description="Subtitle track language counts"
    )
    current_audio: CurrentSelection | None = Field(
        default=None, description="Currently selected audio track across episodes"
    )
    current_subtitle: CurrentSelection | None = Field(
        default=None, description="Currently selected subtitle track (None = disabled)"
    )


# =============================================================================
# =============================================================================


def stream_to_response(stream: PlexStream) -> StreamResponse:
    """Convert PlexStream to StreamResponse."""
    return StreamResponse(
        id=stream.id,
        stream_type=stream.stream_type,
        codec=stream.codec,
        language=stream.language,
        language_code=stream.language_code,
        title=stream.title,
        display_title=stream.display_title,
        selected=stream.selected,
        default=stream.default,
        channels=stream.channels,
        forced=stream.forced,
    )


def _clean_title(title: str, item_type: str) -> str:
    """Clean title by removing track counts for episodes.

    Plex appends " (N)" to episode titles where N is the number of media parts.
    This is confusing to users since episodes already have index numbers displayed.
    """
    if item_type == "episode" and title:
        return _TRACK_COUNT_PATTERN.sub("", title)
    return title


def item_to_response(item: PlexMediaItem) -> MediaItemResponse:
    """Convert PlexMediaItem to MediaItemResponse."""
    return MediaItemResponse(
        rating_key=item.rating_key,
        key=item.key,
        type=item.type,
        title=_clean_title(item.title, item.type),
        year=item.year,
        summary=item.summary[:200] if item.summary else None,
        thumb=item.thumb,
        index=item.index,
        parent_index=item.parent_index,
        parent_title=item.parent_title,
        grandparent_title=item.grandparent_title,
        has_streams=item.has_media,
    )


# =============================================================================
# =============================================================================


@router.get(
    "/{rating_key}",
    response_model=MediaItemResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Item not found"},
        503: {"model": ErrorResponse, "description": "Server unreachable"},
        500: {"model": ErrorResponse},
    },
    summary="Get media item",
    description="Get metadata for a specific media item.",
)
async def get_media_item(
    rating_key: str,
    token: Annotated[str, Depends(get_token_from_header)],
    server_url: Annotated[str, Depends(get_server_url)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> MediaItemResponse:
    """Get metadata for a media item."""
    try:
        async with PlexClient(settings) as client:
            item = await client.get_metadata(
                server_url=server_url,
                token=token,
                rating_key=rating_key,
            )

        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Media item with key '{rating_key}' not found",
            )

        return item_to_response(item)

    except PlexConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Cannot connect to Plex server: {e.message}",
        )
    except PlexClientError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{rating_key}/children",
    response_model=ChildrenResponse,
    responses={
        503: {"model": ErrorResponse, "description": "Server unreachable"},
        500: {"model": ErrorResponse},
    },
    summary="Get children",
    description="Get children of a media item (seasons of show, episodes of season).",
)
async def get_children(
    rating_key: str,
    token: Annotated[str, Depends(get_token_from_header)],
    server_url: Annotated[str, Depends(get_server_url)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ChildrenResponse:
    """Get children of a media item."""
    try:
        async with PlexClient(settings) as client:
            parent = await client.get_metadata(
                server_url=server_url,
                token=token,
                rating_key=rating_key,
            )
            parent_title = parent.title if parent else None

            children = await client.get_children(
                server_url=server_url,
                token=token,
                rating_key=rating_key,
            )

        return ChildrenResponse(
            parent_rating_key=rating_key,
            parent_title=parent_title,
            children=[item_to_response(c) for c in children],
            total=len(children),
        )

    except PlexConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Cannot connect to Plex server: {e.message}",
        )
    except PlexClientError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{rating_key}/streams",
    response_model=MediaStreamsResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Item not found or has no streams"},
        503: {"model": ErrorResponse, "description": "Server unreachable"},
        500: {"model": ErrorResponse},
    },
    summary="Get streams",
    description="Get audio and subtitle streams for a media item.",
)
async def get_streams(
    rating_key: str,
    token: Annotated[str, Depends(get_token_from_header)],
    server_url: Annotated[str, Depends(get_server_url)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> MediaStreamsResponse:
    """Get audio and subtitle streams for a media item."""
    try:
        async with PlexClient(settings) as client:
            item = await client.get_metadata(
                server_url=server_url,
                token=token,
                rating_key=rating_key,
            )

        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Media item with key '{rating_key}' not found",
            )

        part = item.first_part
        if not part:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Media item '{rating_key}' has no stream information",
            )

        return MediaStreamsResponse(
            rating_key=item.rating_key,
            title=item.display_name,
            part_id=part.id,
            audio_streams=[stream_to_response(s) for s in part.audio_streams],
            subtitle_streams=[stream_to_response(s) for s in part.subtitle_streams],
        )

    except PlexConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Cannot connect to Plex server: {e.message}",
        )
    except PlexClientError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{rating_key}/stream-summary",
    response_model=StreamSummaryResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid item type"},
        404: {"model": ErrorResponse, "description": "Item not found"},
        503: {"model": ErrorResponse, "description": "Server unreachable"},
        500: {"model": ErrorResponse},
    },
    summary="Get stream summary",
    description="Get aggregated audio/subtitle stream info for all episodes under a show or season.",
)
async def get_stream_summary(
    rating_key: str,
    token: Annotated[str, Depends(get_token_from_header)],
    server_url: Annotated[str, Depends(get_server_url)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> StreamSummaryResponse:
    """Get aggregated stream summary for a show or season."""
    try:
        async with PlexClient(settings) as client:
            item = await client.get_metadata(
                server_url=server_url,
                token=token,
                rating_key=rating_key,
            )

            if not item:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Media item with key '{rating_key}' not found",
                )

            episodes: list[str] = []

            if item.type == "show":
                seasons = await client.get_children(
                    server_url=server_url,
                    token=token,
                    rating_key=rating_key,
                )
                for season in seasons:
                    if season.type == "season":
                        season_episodes = await client.get_children(
                            server_url=server_url,
                            token=token,
                            rating_key=season.rating_key,
                        )
                        episodes.extend(
                            ep.rating_key for ep in season_episodes if ep.type == "episode"
                        )

            elif item.type == "season":
                season_episodes = await client.get_children(
                    server_url=server_url,
                    token=token,
                    rating_key=rating_key,
                )
                episodes.extend(
                    ep.rating_key for ep in season_episodes if ep.type == "episode"
                )

            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Stream summary only available for shows and seasons",
                )

            audio_counts: dict[tuple[str, str | None], int] = defaultdict(int)
            subtitle_counts: dict[tuple[str, str | None], int] = defaultdict(int)
            audio_samples: dict[tuple[str, str | None], tuple[int, str]] = {}
            subtitle_samples: dict[tuple[str, str | None], tuple[int, str]] = {}
            selected_audio_langs: list[str] = []
            selected_subtitle_langs: list[str] = []

            async def get_episode_streams(ep_key: str) -> None:
                """Fetch streams for one episode."""
                ep_item = await client.get_metadata(
                    server_url=server_url,
                    token=token,
                    rating_key=ep_key,
                )
                if ep_item and ep_item.first_part:
                    part = ep_item.first_part
                    seen_audio: set[tuple[str, str | None]] = set()
                    seen_subs: set[tuple[str, str | None]] = set()
                    selected_audio: str | None = None
                    selected_subtitle: str | None = None

                    for stream in part.audio_streams:
                        lang = stream.language or "Unknown"
                        code = stream.language_code
                        key = (lang, code)
                        if key not in seen_audio:
                            seen_audio.add(key)
                            audio_counts[key] += 1
                            if key not in audio_samples:
                                audio_samples[key] = (stream.id, ep_key)
                        if stream.selected:
                            selected_audio = lang

                    for stream in part.subtitle_streams:
                        lang = stream.language or "Unknown"
                        code = stream.language_code
                        key = (lang, code)
                        if key not in seen_subs:
                            seen_subs.add(key)
                            subtitle_counts[key] += 1
                            if key not in subtitle_samples:
                                subtitle_samples[key] = (stream.id, ep_key)
                        if stream.selected:
                            selected_subtitle = lang

                    if selected_audio:
                        selected_audio_langs.append(selected_audio)
                    selected_subtitle_langs.append(selected_subtitle or "None")

            batch_size = 10
            for i in range(0, len(episodes), batch_size):
                batch = episodes[i : i + batch_size]
                await asyncio.gather(*[get_episode_streams(ep) for ep in batch])

            audio_summary = []
            for (lang, code), count in sorted(
                audio_counts.items(), key=lambda x: (-x[1], x[0][0])
            ):
                sample = audio_samples.get((lang, code))
                audio_summary.append(
                    LanguageCount(
                        language=lang,
                        language_code=code,
                        count=count,
                        sample_stream_id=sample[0] if sample else None,
                        sample_rating_key=sample[1] if sample else None,
                    )
                )

            subtitle_summary = []
            for (lang, code), count in sorted(
                subtitle_counts.items(), key=lambda x: (-x[1], x[0][0])
            ):
                sample = subtitle_samples.get((lang, code))
                subtitle_summary.append(
                    LanguageCount(
                        language=lang,
                        language_code=code,
                        count=count,
                        sample_stream_id=sample[0] if sample else None,
                        sample_rating_key=sample[1] if sample else None,
                    )
                )

            current_audio = None
            if selected_audio_langs:
                from collections import Counter

                audio_counter = Counter(selected_audio_langs)
                most_common_audio, audio_count = audio_counter.most_common(1)[0]
                current_audio = CurrentSelection(
                    language=most_common_audio,
                    count=audio_count,
                    is_uniform=audio_count == len(episodes),
                )

            current_subtitle = None
            if selected_subtitle_langs:
                sub_counter = Counter(selected_subtitle_langs)
                most_common_sub, sub_count = sub_counter.most_common(1)[0]
                current_subtitle = CurrentSelection(
                    language=most_common_sub,
                    count=sub_count,
                    is_uniform=sub_count == len(episodes),
                )

            return StreamSummaryResponse(
                rating_key=item.rating_key,
                title=item.title,
                total_items=len(episodes),
                audio_summary=audio_summary,
                subtitle_summary=subtitle_summary,
                current_audio=current_audio,
                current_subtitle=current_subtitle,
            )

    except PlexConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Cannot connect to Plex server: {e.message}",
        )
    except PlexClientError as e:
        raise HTTPException(status_code=500, detail=str(e))
