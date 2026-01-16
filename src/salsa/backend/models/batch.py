"""Batch operation models."""

from enum import Enum

from pydantic import BaseModel, Field


class BatchScope(str, Enum):
    """Scope of a batch update operation."""

    EPISODE = "episode"
    SEASON = "season"
    SHOW = "show"
    LIBRARY = "library"


class StreamType(str, Enum):
    """Type of stream to update."""

    AUDIO = "audio"
    SUBTITLE = "subtitle"


class BatchStatus(str, Enum):
    """Status of a batch operation."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# =============================================================================
# =============================================================================


class BatchUpdateRequest(BaseModel):
    """Request to start a batch update operation."""

    scope: BatchScope = Field(..., description="Scope of the batch update")
    stream_type: StreamType = Field(..., description="Type of stream to update")
    target_rating_key: str = Field(..., description="Rating key of target item/library")

    source_stream_id: int = Field(..., description="ID of the source stream to match")
    source_rating_key: str | None = Field(
        default=None,
        description="Rating key of item containing source stream (for matching)",
    )

    keyword_filter: str | None = Field(
        default=None,
        description="Only match streams containing this keyword",
    )

    set_none: bool = Field(
        default=False,
        description="Set subtitles to none instead of matching",
    )


class SingleUpdateRequest(BaseModel):
    """Request to update a single item's stream."""

    part_id: int = Field(..., description="Part ID to update")
    stream_id: int = Field(..., description="Stream ID to set (0 for no subtitles)")
    stream_type: StreamType = Field(..., description="Type of stream")


# =============================================================================
# =============================================================================


class ItemResult(BaseModel):
    """Result for a single item in a batch operation."""

    rating_key: str = Field(..., description="Item rating key")
    title: str = Field(..., description="Item title")
    success: bool = Field(..., description="Whether update succeeded")
    skipped: bool = Field(default=False, description="Whether item was skipped")
    error: str | None = Field(default=None, description="Error message if failed")
    match_level: str | None = Field(default=None, description="Match level used")
    already_selected: bool = Field(
        default=False,
        description="Stream was already selected",
    )


class BatchProgress(BaseModel):
    """Progress of a batch operation."""

    batch_id: str = Field(..., description="Batch operation ID")
    status: BatchStatus = Field(..., description="Current status")
    total: int = Field(..., description="Total items to process")
    processed: int = Field(default=0, description="Items processed so far")
    success: int = Field(default=0, description="Successful updates")
    failed: int = Field(default=0, description="Failed updates")
    skipped: int = Field(default=0, description="Skipped items")
    current_item: str | None = Field(default=None, description="Currently processing")
    message: str | None = Field(default=None, description="Status message")


class BatchResultSummary(BaseModel):
    """Summary of a completed batch operation."""

    batch_id: str = Field(..., description="Batch operation ID")
    status: BatchStatus = Field(..., description="Final status")
    total: int = Field(..., description="Total items processed")
    success: int = Field(..., description="Successful updates")
    failed: int = Field(..., description="Failed updates")
    skipped: int = Field(..., description="Skipped items")
    duration_seconds: float = Field(..., description="Total duration")
    results: list[ItemResult] = Field(
        default_factory=list,
        description="Individual results (may be truncated for large batches)",
    )


class SingleUpdateResponse(BaseModel):
    """Response for a single update."""

    success: bool = Field(..., description="Whether update succeeded")
    message: str = Field(..., description="Status message")


class BatchStartResponse(BaseModel):
    """Response when starting a batch operation."""

    batch_id: str = Field(..., description="Batch operation ID")
    status: BatchStatus = Field(default=BatchStatus.PENDING)
    message: str = Field(default="Batch operation started")
    total_items: int = Field(..., description="Estimated total items")
