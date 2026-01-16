"""Track update API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from salsa.backend.config import Settings, get_settings
from salsa.backend.models.auth import ErrorResponse
from salsa.backend.models.batch import (
    BatchProgress,
    BatchResultSummary,
    BatchStartResponse,
    BatchStatus,
    BatchUpdateRequest,
    SingleUpdateRequest,
    SingleUpdateResponse,
    StreamType,
)
from salsa.backend.routers.auth import get_token_from_header
from salsa.backend.routers.libraries import get_server_url
from salsa.backend.services.batch import BatchService, get_batch_service
from salsa.backend.services.plex_client import (
    PlexClient,
    PlexClientError,
    PlexConnectionError,
)

router = APIRouter()


# =============================================================================
# =============================================================================


class BatchIdResponse(BaseModel):
    """Response containing just a batch ID."""

    batch_id: str = Field(..., description="Batch operation ID")


# =============================================================================
# =============================================================================


@router.put(
    "/audio",
    response_model=SingleUpdateResponse,
    responses={
        503: {"model": ErrorResponse, "description": "Server unreachable"},
        500: {"model": ErrorResponse},
    },
    summary="Set audio track",
    description="Set the audio track for a single media item.",
)
async def set_audio_track(
    request: SingleUpdateRequest,
    token: Annotated[str, Depends(get_token_from_header)],
    server_url: Annotated[str, Depends(get_server_url)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SingleUpdateResponse:
    """Set audio track for a media item."""
    if request.stream_type != StreamType.AUDIO:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="stream_type must be 'audio' for this endpoint",
        )

    try:
        async with PlexClient(settings) as client:
            await client.set_audio_stream(
                server_url=server_url,
                token=token,
                part_id=request.part_id,
                stream_id=request.stream_id,
            )

        return SingleUpdateResponse(
            success=True,
            message="Audio track updated successfully",
        )

    except PlexConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Cannot connect to Plex server: {e.message}",
        )
    except PlexClientError as e:
        return SingleUpdateResponse(
            success=False,
            message=f"Failed to update audio track: {e.message}",
        )


@router.put(
    "/subtitle",
    response_model=SingleUpdateResponse,
    responses={
        503: {"model": ErrorResponse, "description": "Server unreachable"},
        500: {"model": ErrorResponse},
    },
    summary="Set subtitle track",
    description="Set the subtitle track for a media item. Use stream_id=0 to disable.",
)
async def set_subtitle_track(
    request: SingleUpdateRequest,
    token: Annotated[str, Depends(get_token_from_header)],
    server_url: Annotated[str, Depends(get_server_url)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SingleUpdateResponse:
    """Set subtitle track for a media item."""
    if request.stream_type != StreamType.SUBTITLE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="stream_type must be 'subtitle' for this endpoint",
        )

    try:
        async with PlexClient(settings) as client:
            stream_id = request.stream_id if request.stream_id != 0 else None
            await client.set_subtitle_stream(
                server_url=server_url,
                token=token,
                part_id=request.part_id,
                stream_id=stream_id,
            )

        message = (
            "Subtitles disabled"
            if request.stream_id == 0
            else "Subtitle track updated successfully"
        )
        return SingleUpdateResponse(success=True, message=message)

    except PlexConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Cannot connect to Plex server: {e.message}",
        )
    except PlexClientError as e:
        return SingleUpdateResponse(
            success=False,
            message=f"Failed to update subtitle track: {e.message}",
        )


# =============================================================================
# =============================================================================


@router.post(
    "/batch",
    response_model=BatchStartResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        503: {"model": ErrorResponse, "description": "Server unreachable"},
        500: {"model": ErrorResponse},
    },
    summary="Start batch update",
    description="Start a batch update operation to apply stream selections across multiple items.",
)
async def start_batch_update(
    request: BatchUpdateRequest,
    token: Annotated[str, Depends(get_token_from_header)],
    server_url: Annotated[str, Depends(get_server_url)],
    settings: Annotated[Settings, Depends(get_settings)],
    batch_service: Annotated[BatchService, Depends(get_batch_service)],
) -> BatchStartResponse:
    """Start a batch update operation."""
    if request.set_none and request.stream_type != StreamType.SUBTITLE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="set_none is only valid for subtitle updates",
        )

    try:
        batch_id = await batch_service.start_batch(
            token=token,
            server_url=server_url,
            scope=request.scope,
            stream_type=request.stream_type,
            target_key=request.target_rating_key,
            source_stream_id=request.source_stream_id,
            source_rating_key=request.source_rating_key,
            keyword_filter=request.keyword_filter,
            set_none=request.set_none,
        )

        progress = batch_service.get_progress(batch_id)
        total_items = progress.total if progress else 0

        return BatchStartResponse(
            batch_id=batch_id,
            status=BatchStatus.RUNNING,
            message="Batch operation started",
            total_items=total_items,
        )

    except PlexConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Cannot connect to Plex server: {e.message}",
        )
    except PlexClientError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Plex error: {e.message}",
        )


@router.get(
    "/batch/{batch_id}",
    response_model=BatchProgress,
    responses={
        404: {"model": ErrorResponse, "description": "Batch not found"},
    },
    summary="Get batch progress",
    description="Get the current progress of a batch operation.",
)
async def get_batch_progress(
    batch_id: str,
    batch_service: Annotated[BatchService, Depends(get_batch_service)],
) -> BatchProgress:
    """Get progress of a batch operation."""
    progress = batch_service.get_progress(batch_id)

    if not progress:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch operation '{batch_id}' not found",
        )

    return progress


@router.get(
    "/batch/{batch_id}/result",
    response_model=BatchResultSummary,
    responses={
        404: {"model": ErrorResponse, "description": "Batch not found"},
        400: {"model": ErrorResponse, "description": "Batch not complete"},
    },
    summary="Get batch result",
    description="Get the detailed result of a completed batch operation.",
)
async def get_batch_result(
    batch_id: str,
    batch_service: Annotated[BatchService, Depends(get_batch_service)],
) -> BatchResultSummary:
    """Get result of a completed batch operation."""
    result = batch_service.get_result(batch_id)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch operation '{batch_id}' not found",
        )

    if result.status not in (BatchStatus.COMPLETED, BatchStatus.FAILED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Batch operation is still running",
        )

    return result
