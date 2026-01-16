"""Batch update service for bulk stream changes."""

import asyncio
import time
import uuid
from dataclasses import dataclass, field

from loguru import logger

from salsa.backend.config import Settings, get_settings
from salsa.backend.models.batch import (
    BatchProgress,
    BatchResultSummary,
    BatchScope,
    BatchStatus,
    ItemResult,
    StreamType,
)
from salsa.backend.models.plex import PlexMediaItem, PlexStream
from salsa.backend.services.matcher import StreamMatcher
from salsa.backend.services.plex_client import PlexClient, PlexClientError


@dataclass
class BatchOperation:
    """State of a batch operation."""

    batch_id: str
    status: BatchStatus = BatchStatus.PENDING
    total: int = 0
    processed: int = 0
    success: int = 0
    failed: int = 0
    skipped: int = 0
    current_item: str | None = None
    message: str | None = None
    results: list[ItemResult] = field(default_factory=list)
    start_time: float = 0.0
    end_time: float = 0.0

    def to_progress(self) -> BatchProgress:
        """Convert to progress response."""
        return BatchProgress(
            batch_id=self.batch_id,
            status=self.status,
            total=self.total,
            processed=self.processed,
            success=self.success,
            failed=self.failed,
            skipped=self.skipped,
            current_item=self.current_item,
            message=self.message,
        )

    def to_summary(self) -> BatchResultSummary:
        """Convert to summary response."""
        duration = self.end_time - self.start_time if self.end_time else 0.0
        max_results = 1000
        return BatchResultSummary(
            batch_id=self.batch_id,
            status=self.status,
            total=self.total,
            success=self.success,
            failed=self.failed,
            skipped=self.skipped,
            duration_seconds=round(duration, 2),
            results=self.results[:max_results],
        )


class BatchStore:
    """In-memory store for batch operations."""

    def __init__(self) -> None:
        self._operations: dict[str, BatchOperation] = {}

    def create(self, batch_id: str) -> BatchOperation:
        """Create a new batch operation."""
        op = BatchOperation(batch_id=batch_id)
        self._operations[batch_id] = op
        return op

    def get(self, batch_id: str) -> BatchOperation | None:
        """Get a batch operation by ID."""
        return self._operations.get(batch_id)

    def delete(self, batch_id: str) -> None:
        """Delete a batch operation."""
        self._operations.pop(batch_id, None)


_batch_store = BatchStore()


def get_batch_store() -> BatchStore:
    """Get the global batch store."""
    return _batch_store


class BatchService:
    """Service for executing batch stream updates."""

    def __init__(
        self,
        settings: Settings | None = None,
        batch_store: BatchStore | None = None,
    ):
        self.settings = settings or get_settings()
        self.batch_store = batch_store or get_batch_store()

    async def _get_items_for_scope(
        self,
        client: PlexClient,
        token: str,
        server_url: str,
        scope: BatchScope,
        target_key: str,
    ) -> list[PlexMediaItem]:
        """Get all items that should be updated for the given scope."""
        items: list[PlexMediaItem] = []

        match scope:
            case BatchScope.EPISODE:
                item = await client.get_metadata(server_url, token, target_key)
                if item:
                    items = [item]

            case BatchScope.SEASON:
                episodes = await client.get_children(server_url, token, target_key)
                items = [e for e in episodes if e.is_episode]

            case BatchScope.SHOW:
                seasons = await client.get_children(server_url, token, target_key)
                for season in seasons:
                    if season.is_season:
                        episodes = await client.get_children(server_url, token, season.rating_key)
                        items.extend([e for e in episodes if e.is_episode])

            case BatchScope.LIBRARY:
                container = await client.get_library_items(server_url, token, target_key)
                for item in container.metadata:
                    if item.is_movie:
                        items.append(item)
                    elif item.is_show:
                        seasons = await client.get_children(server_url, token, item.rating_key)
                        for season in seasons:
                            if season.is_season:
                                episodes = await client.get_children(
                                    server_url, token, season.rating_key
                                )
                                items.extend([e for e in episodes if e.is_episode])

        return items

    async def _fetch_item_streams(
        self,
        client: PlexClient,
        token: str,
        server_url: str,
        item: PlexMediaItem,
    ) -> PlexMediaItem | None:
        """Fetch full metadata with streams for an item if not already populated."""
        if item.first_part and len(item.first_part.streams) > 0:
            return item

        return await client.get_metadata(
            server_url,
            token,
            item.rating_key,
        )

    async def start_batch(
        self,
        token: str,
        server_url: str,
        scope: BatchScope,
        stream_type: StreamType,
        target_key: str,
        source_stream_id: int,
        source_rating_key: str | None = None,
        keyword_filter: str | None = None,
        set_none: bool = False,
    ) -> str:
        """
        Start a batch update operation.

        Returns the batch ID for tracking progress.
        """
        batch_id = str(uuid.uuid4())[:8]
        logger.info(
            f"BATCH {batch_id} created: scope={scope}, target={target_key}, type={stream_type}"
        )
        operation = self.batch_store.create(batch_id)
        operation.start_time = time.time()
        operation.status = BatchStatus.RUNNING
        operation.message = "Collecting items..."

        task = asyncio.create_task(
            self._run_batch(
                batch_id=batch_id,
                token=token,
                server_url=server_url,
                scope=scope,
                stream_type=stream_type,
                target_key=target_key,
                source_stream_id=source_stream_id,
                source_rating_key=source_rating_key,
                keyword_filter=keyword_filter,
                set_none=set_none,
            )
        )
        operation.task = task  # type: ignore[attr-defined]

        return batch_id

    async def _run_batch(
        self,
        batch_id: str,
        token: str,
        server_url: str,
        scope: BatchScope,
        stream_type: StreamType,
        target_key: str,
        source_stream_id: int,
        source_rating_key: str | None,
        keyword_filter: str | None,
        set_none: bool,
    ) -> None:
        """Execute the batch operation."""
        logger.info(f"BATCH {batch_id} starting: scope={scope}, target={target_key}")

        operation = self.batch_store.get(batch_id)
        if not operation:
            logger.error(f"BATCH {batch_id} operation not found in store")
            return

        try:
            logger.debug(f"BATCH {batch_id} creating PlexClient")
            async with PlexClient(self.settings) as client:
                source_key = source_rating_key or (
                    target_key if scope == BatchScope.EPISODE else None
                )
                logger.debug(f"BATCH {batch_id} source_key={source_key}, set_none={set_none}")
                if not source_key and not set_none:
                    operation.status = BatchStatus.FAILED
                    operation.message = "No source item specified for matching"
                    operation.end_time = time.time()
                    return

                logger.debug(f"BATCH {batch_id} fetching source metadata from {server_url}")
                source_item = (
                    await client.get_metadata(
                        server_url,
                        token,
                        source_key or "",
                    )
                    if source_key
                    else None
                )
                logger.debug(f"BATCH {batch_id} source_item={source_item is not None}")

                source_stream: PlexStream | None = None
                if source_item and source_item.first_part:
                    streams = (
                        source_item.first_part.audio_streams
                        if stream_type == StreamType.AUDIO
                        else source_item.first_part.subtitle_streams
                    )
                    for s in streams:
                        if s.id == source_stream_id:
                            source_stream = s
                            break

                if not source_stream and not set_none:
                    operation.status = BatchStatus.FAILED
                    operation.message = "Source stream not found"
                    operation.end_time = time.time()
                    return

                operation.message = "Collecting items to update..."
                items = await self._get_items_for_scope(
                    client, token, server_url, scope, target_key
                )
                operation.total = len(items)

                if not items:
                    operation.status = BatchStatus.COMPLETED
                    operation.message = "No items to update"
                    operation.end_time = time.time()
                    return

                matcher = StreamMatcher(keyword_filter=keyword_filter)

                for item in items:
                    operation.current_item = item.display_name
                    operation.processed += 1

                    result = await self._process_item(
                        client=client,
                        token=token,
                        server_url=server_url,
                        item=item,
                        stream_type=stream_type,
                        source_stream=source_stream,
                        matcher=matcher,
                        set_none=set_none,
                    )

                    if result.success:
                        if result.skipped:
                            operation.skipped += 1
                        else:
                            operation.success += 1
                    else:
                        operation.failed += 1

                    operation.results.append(result)

                    await asyncio.sleep(0.1)

                operation.status = BatchStatus.COMPLETED
                operation.message = (
                    f"Completed: {operation.success} updated, "
                    f"{operation.skipped} skipped, {operation.failed} failed"
                )

        except PlexClientError as e:
            logger.error(f"BATCH {batch_id} PlexClientError: {e.message}")
            operation.status = BatchStatus.FAILED
            operation.message = f"Error: {e.message}"
        except Exception as e:
            logger.exception(f"BATCH {batch_id} unexpected error: {e!s}")
            operation.status = BatchStatus.FAILED
            operation.message = f"Unexpected error: {e!s}"
        finally:
            operation.end_time = time.time()
            operation.current_item = None
            logger.info(
                f"BATCH {batch_id} done: {operation.status} "
                f"(ok={operation.success}, skip={operation.skipped}, fail={operation.failed})"
            )

    async def _process_item(
        self,
        client: PlexClient,
        token: str,
        server_url: str,
        item: PlexMediaItem,
        stream_type: StreamType,
        source_stream: PlexStream | None,
        matcher: StreamMatcher,
        set_none: bool,
    ) -> ItemResult:
        """Process a single item in the batch."""
        try:
            full_item = await self._fetch_item_streams(client, token, server_url, item)
            if not full_item:
                return ItemResult(
                    rating_key=item.rating_key,
                    title=item.display_name,
                    success=False,
                    error="Failed to fetch item metadata",
                )
            if not full_item.first_part:
                return ItemResult(
                    rating_key=item.rating_key,
                    title=item.display_name,
                    success=False,
                    error="No media/part information available",
                )

            part = full_item.first_part
            candidates = (
                part.audio_streams if stream_type == StreamType.AUDIO else part.subtitle_streams
            )

            if set_none and stream_type == StreamType.SUBTITLE:
                await client.set_subtitle_stream(
                    server_url,
                    token,
                    part.id,
                    None,
                )
                return ItemResult(
                    rating_key=item.rating_key,
                    title=item.display_name,
                    success=True,
                    match_level="NONE",
                )

            if not source_stream:
                return ItemResult(
                    rating_key=item.rating_key,
                    title=item.display_name,
                    success=False,
                    error="No source stream for matching",
                )

            match_result = matcher.find_match(source_stream, candidates)

            if not match_result.matched or not match_result.stream:
                return ItemResult(
                    rating_key=item.rating_key,
                    title=item.display_name,
                    success=False,
                    error=match_result.reason,
                )

            if match_result.already_selected:
                return ItemResult(
                    rating_key=item.rating_key,
                    title=item.display_name,
                    success=True,
                    skipped=True,
                    already_selected=True,
                    match_level=match_result.match_level.name,
                )

            if stream_type == StreamType.AUDIO:
                await client.set_audio_stream(
                    server_url,
                    token,
                    part.id,
                    match_result.stream.id,
                )
            else:
                await client.set_subtitle_stream(
                    server_url,
                    token,
                    part.id,
                    match_result.stream.id,
                )

            return ItemResult(
                rating_key=item.rating_key,
                title=item.display_name,
                success=True,
                match_level=match_result.match_level.name,
            )

        except PlexClientError as e:
            return ItemResult(
                rating_key=item.rating_key,
                title=item.display_name,
                success=False,
                error=str(e.message),
            )

    def get_progress(self, batch_id: str) -> BatchProgress | None:
        """Get progress of a batch operation."""
        operation = self.batch_store.get(batch_id)
        return operation.to_progress() if operation else None

    def get_result(self, batch_id: str) -> BatchResultSummary | None:
        """Get result summary of a completed batch operation."""
        operation = self.batch_store.get(batch_id)
        return operation.to_summary() if operation else None


def get_batch_service() -> BatchService:
    """Get a BatchService instance for dependency injection."""
    return BatchService()
