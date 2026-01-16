"""Tests for the batch update service."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from salsa.backend.config import Settings
from salsa.backend.models.batch import BatchScope, BatchStatus, StreamType
from salsa.backend.models.plex import (
    PlexMedia,
    PlexMediaItem,
    PlexPart,
    PlexStream,
)
from salsa.backend.services.batch import BatchOperation, BatchService, BatchStore

# =============================================================================
# =============================================================================

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "plex_responses"


def load_fixture(name: str) -> dict:
    """Load a JSON fixture file."""
    with open(FIXTURES_DIR / f"{name}.json") as f:
        return json.load(f)


class TestBatchStore:
    """Tests for BatchStore in-memory storage."""

    def test_create_operation(self):
        """Should create a new batch operation."""
        store = BatchStore()

        op = store.create("test-batch-1")

        assert op.batch_id == "test-batch-1"
        assert op.status == BatchStatus.PENDING
        assert op.total == 0
        assert op.processed == 0

    def test_get_operation(self):
        """Should retrieve an operation by ID."""
        store = BatchStore()
        store.create("test-batch-1")

        op = store.get("test-batch-1")

        assert op is not None
        assert op.batch_id == "test-batch-1"

    def test_get_nonexistent_operation(self):
        """Should return None for nonexistent operation."""
        store = BatchStore()

        op = store.get("nonexistent")

        assert op is None

    def test_delete_operation(self):
        """Should delete an operation."""
        store = BatchStore()
        store.create("test-batch-1")

        store.delete("test-batch-1")
        op = store.get("test-batch-1")

        assert op is None

    def test_delete_nonexistent_no_error(self):
        """Should not raise error when deleting nonexistent operation."""
        store = BatchStore()

        store.delete("nonexistent")


class TestBatchOperation:
    """Tests for BatchOperation dataclass."""

    def test_to_progress(self):
        """Should convert to BatchProgress."""
        op = BatchOperation(
            batch_id="test-1",
            status=BatchStatus.RUNNING,
            total=100,
            processed=50,
            success=45,
            failed=3,
            skipped=2,
            current_item="Episode 5",
            message="Processing...",
        )

        progress = op.to_progress()

        assert progress.batch_id == "test-1"
        assert progress.status == BatchStatus.RUNNING
        assert progress.total == 100
        assert progress.processed == 50
        assert progress.success == 45
        assert progress.failed == 3
        assert progress.skipped == 2
        assert progress.current_item == "Episode 5"
        assert progress.message == "Processing..."

    def test_to_summary(self):
        """Should convert to BatchResultSummary."""
        op = BatchOperation(
            batch_id="test-1",
            status=BatchStatus.COMPLETED,
            total=100,
            processed=100,
            success=95,
            failed=3,
            skipped=2,
            start_time=1000.0,
            end_time=1010.5,
        )

        summary = op.to_summary()

        assert summary.batch_id == "test-1"
        assert summary.status == BatchStatus.COMPLETED
        assert summary.total == 100
        assert summary.success == 95
        assert summary.failed == 3
        assert summary.skipped == 2
        assert summary.duration_seconds == 10.5

    def test_to_summary_limits_results(self):
        """Should limit results to prevent memory issues."""
        from salsa.backend.models.batch import ItemResult

        op = BatchOperation(batch_id="test-1")
        op.results = [
            ItemResult(rating_key=str(i), title=f"Item {i}", success=True)
            for i in range(1500)
        ]

        summary = op.to_summary()

        assert len(summary.results) == 1000


class TestBatchService:
    """Tests for BatchService."""

    def test_get_progress_existing(self):
        """Should get progress for existing operation."""
        store = BatchStore()
        op = store.create("test-1")
        op.status = BatchStatus.RUNNING
        op.total = 50
        op.processed = 25

        service = BatchService(batch_store=store)
        progress = service.get_progress("test-1")

        assert progress is not None
        assert progress.batch_id == "test-1"
        assert progress.status == BatchStatus.RUNNING

    def test_get_progress_nonexistent(self):
        """Should return None for nonexistent operation."""
        store = BatchStore()
        service = BatchService(batch_store=store)

        progress = service.get_progress("nonexistent")

        assert progress is None

    def test_get_result_existing(self):
        """Should get result for completed operation."""
        store = BatchStore()
        op = store.create("test-1")
        op.status = BatchStatus.COMPLETED
        op.total = 50
        op.success = 48
        op.failed = 2
        op.start_time = 100.0
        op.end_time = 110.0

        service = BatchService(batch_store=store)
        result = service.get_result("test-1")

        assert result is not None
        assert result.batch_id == "test-1"
        assert result.status == BatchStatus.COMPLETED
        assert result.duration_seconds == 10.0

    def test_get_result_nonexistent(self):
        """Should return None for nonexistent operation."""
        store = BatchStore()
        service = BatchService(batch_store=store)

        result = service.get_result("nonexistent")

        assert result is None


class TestBatchModels:
    """Tests for batch-related models."""

    def test_batch_scope_values(self):
        """BatchScope should have expected values."""
        assert BatchScope.EPISODE.value == "episode"
        assert BatchScope.SEASON.value == "season"
        assert BatchScope.SHOW.value == "show"
        assert BatchScope.LIBRARY.value == "library"

    def test_stream_type_values(self):
        """StreamType should have expected values."""
        assert StreamType.AUDIO.value == "audio"
        assert StreamType.SUBTITLE.value == "subtitle"

    def test_batch_status_values(self):
        """BatchStatus should have expected values."""
        assert BatchStatus.PENDING.value == "pending"
        assert BatchStatus.RUNNING.value == "running"
        assert BatchStatus.COMPLETED.value == "completed"
        assert BatchStatus.FAILED.value == "failed"
        assert BatchStatus.CANCELLED.value == "cancelled"


# =============================================================================
# =============================================================================


def create_plex_stream(stream_data: dict) -> PlexStream:
    """Create a PlexStream from fixture data."""
    return PlexStream(
        id=stream_data["id"],
        stream_type=stream_data["streamType"],
        codec=stream_data.get("codec"),
        language=stream_data.get("language"),
        language_code=stream_data.get("languageCode"),
        title=stream_data.get("title"),
        display_title=stream_data.get("displayTitle"),
        selected=stream_data.get("selected", False),
        default=stream_data.get("default", False),
        channels=stream_data.get("channels"),
        forced=stream_data.get("forced", False),
    )


def create_plex_item_from_fixture(metadata_dict: dict) -> PlexMediaItem:
    """Create a PlexMediaItem from raw fixture data."""
    item_data = metadata_dict["MediaContainer"]["Metadata"][0]

    media_list = []

    if item_data.get("Media"):
        for media_data in item_data["Media"]:
            parts = []
            if media_data.get("Part"):
                for part_data in media_data["Part"]:
                    streams = []
                    if "Stream" in part_data:
                        for s in part_data["Stream"]:
                            streams.append(create_plex_stream(s))
                    parts.append(PlexPart(
                        id=part_data["id"],
                        key=part_data.get("key", ""),
                        file=part_data.get("file"),
                        streams=streams,
                    ))
            media_list.append(PlexMedia(
                id=media_data["id"],
                duration=media_data.get("duration"),
                bitrate=media_data.get("bitrate"),
                container=media_data.get("container"),
                parts=parts,
            ))

    return PlexMediaItem(
        rating_key=item_data["ratingKey"],
        key=item_data["key"],
        type=item_data["type"],
        title=item_data["title"],
        year=item_data.get("year"),
        summary=item_data.get("summary"),
        thumb=item_data.get("thumb"),
        index=item_data.get("index"),
        parent_index=item_data.get("parentIndex"),
        parent_title=item_data.get("parentTitle"),
        grandparent_title=item_data.get("grandparentTitle"),
        media=media_list,
    )


def create_episode_items_from_fixture(fixture_dict: dict) -> list[PlexMediaItem]:
    """Create episode items from episodes fixture (without streams)."""
    items = []
    for item_data in fixture_dict["MediaContainer"].get("Metadata", []):
        items.append(PlexMediaItem(
            rating_key=item_data["ratingKey"],
            key=item_data["key"],
            type=item_data["type"],
            title=item_data["title"],
            index=item_data.get("index"),
            parent_index=item_data.get("parentIndex"),
            parent_title=item_data.get("parentTitle"),
            grandparent_title=item_data.get("grandparentTitle"),
        ))
    return items


def create_season_items_from_fixture(fixture_dict: dict) -> list[PlexMediaItem]:
    """Create season items from seasons fixture."""
    items = []
    for item_data in fixture_dict["MediaContainer"].get("Metadata", []):
        items.append(PlexMediaItem(
            rating_key=item_data["ratingKey"],
            key=item_data["key"],
            type=item_data["type"],
            title=item_data["title"],
            index=item_data.get("index"),
            parent_index=item_data.get("parentIndex"),
            parent_title=item_data.get("parentTitle"),
        ))
    return items


# =============================================================================
# =============================================================================


@pytest.fixture
def settings() -> Settings:
    """Create test settings."""
    return Settings(
        secret_key="test-secret-key",
        plex_host="localhost",
        plex_port=32400,
        plex_protocol="http",
        plex_client_id="test-client-id",
    )


@pytest.fixture
def episode_fixture():
    """Load episode metadata fixture with streams."""
    return load_fixture("episode_39066_metadata")


@pytest.fixture
def seasons_fixture():
    """Load seasons fixture."""
    return load_fixture("show_39040_seasons")


@pytest.fixture
def episodes_fixture():
    """Load episodes fixture."""
    return load_fixture("season_39065_episodes")


class TestBatchServiceIntegration:
    """Integration tests for BatchService with real fixture data."""

    @pytest.mark.asyncio
    async def test_get_items_for_scope_episode(self, settings, episode_fixture):
        """Should get single episode for EPISODE scope."""
        from salsa.backend.services.plex_client import PlexClient

        episode_item = create_plex_item_from_fixture(episode_fixture)
        store = BatchStore()
        service = BatchService(settings=settings, batch_store=store)

        with patch.object(
            PlexClient,
            "get_metadata",
            new_callable=AsyncMock,
            return_value=episode_item,
        ):
            mock_client = MagicMock()
            mock_client.get_metadata = AsyncMock(return_value=episode_item)

            items = await service._get_items_for_scope(
                client=mock_client,
                token="test-token",
                server_url="http://localhost:32400",
                scope=BatchScope.EPISODE,
                target_key="39066",
            )

        assert len(items) == 1
        assert items[0].rating_key == "39066"

    @pytest.mark.asyncio
    async def test_get_items_for_scope_season(self, settings, episodes_fixture):
        """Should get all episodes for SEASON scope."""

        episodes = create_episode_items_from_fixture(episodes_fixture)
        store = BatchStore()
        service = BatchService(settings=settings, batch_store=store)

        mock_client = MagicMock()
        mock_client.get_children = AsyncMock(return_value=episodes)

        items = await service._get_items_for_scope(
            client=mock_client,
            token="test-token",
            server_url="http://localhost:32400",
            scope=BatchScope.SEASON,
            target_key="39065",
        )

        assert len(items) == 3
        assert all(item.type == "episode" for item in items)

    @pytest.mark.asyncio
    async def test_get_items_for_scope_show(self, settings, seasons_fixture, episodes_fixture):
        """Should get all episodes from all seasons for SHOW scope."""

        seasons = create_season_items_from_fixture(seasons_fixture)
        episodes = create_episode_items_from_fixture(episodes_fixture)
        store = BatchStore()
        service = BatchService(settings=settings, batch_store=store)

        mock_client = MagicMock()
        mock_client.get_children = AsyncMock(side_effect=[
            seasons,
            episodes,
            episodes,
        ])

        items = await service._get_items_for_scope(
            client=mock_client,
            token="test-token",
            server_url="http://localhost:32400",
            scope=BatchScope.SHOW,
            target_key="39040",
        )

        assert len(items) == 3 + 3
        assert all(item.type == "episode" for item in items)

    @pytest.mark.asyncio
    async def test_fetch_item_streams_returns_cached(self, settings, episode_fixture):
        """Should return item directly if streams already populated."""
        episode_item = create_plex_item_from_fixture(episode_fixture)
        store = BatchStore()
        service = BatchService(settings=settings, batch_store=store)

        mock_client = MagicMock()
        mock_client.get_metadata = AsyncMock()

        result = await service._fetch_item_streams(
            client=mock_client,
            token="test-token",
            server_url="http://localhost:32400",
            item=episode_item,
        )

        assert result == episode_item
        mock_client.get_metadata.assert_not_called()

    @pytest.mark.asyncio
    async def test_fetch_item_streams_fetches_missing(self, settings, episode_fixture):
        """Should fetch full metadata when streams not populated."""
        item_without_streams = PlexMediaItem(
            rating_key="39066",
            key="/library/metadata/39066",
            type="episode",
            title="Ryomen Sukuna",
        )

        episode_item = create_plex_item_from_fixture(episode_fixture)
        store = BatchStore()
        service = BatchService(settings=settings, batch_store=store)

        mock_client = MagicMock()
        mock_client.get_metadata = AsyncMock(return_value=episode_item)

        result = await service._fetch_item_streams(
            client=mock_client,
            token="test-token",
            server_url="http://localhost:32400",
            item=item_without_streams,
        )

        assert result == episode_item
        mock_client.get_metadata.assert_called_once()


class TestBatchServiceProcessItem:
    """Tests for _process_item with fixture data."""

    @pytest.mark.asyncio
    async def test_process_item_finds_matching_stream(self, settings, episode_fixture):
        """Should find and apply matching stream."""
        episode_item = create_plex_item_from_fixture(episode_fixture)
        store = BatchStore()
        service = BatchService(settings=settings, batch_store=store)

        japanese_stream = None
        for stream in episode_item.first_part.audio_streams:
            if stream.language_code == "jpn":
                japanese_stream = stream
                break
        assert japanese_stream is not None

        mock_client = MagicMock()
        mock_client.get_metadata = AsyncMock(return_value=episode_item)
        mock_client.set_audio_stream = AsyncMock()

        from salsa.backend.services.matcher import StreamMatcher
        matcher = StreamMatcher()

        result = await service._process_item(
            client=mock_client,
            token="test-token",
            server_url="http://localhost:32400",
            item=episode_item,
            stream_type=StreamType.AUDIO,
            source_stream=japanese_stream,
            matcher=matcher,
            set_none=False,
        )

        assert result.success is True
        assert result.skipped is True
        assert result.already_selected is True

    @pytest.mark.asyncio
    async def test_process_item_set_none_disables_subtitles(self, settings, episode_fixture):
        """Should disable subtitles when set_none is True."""
        episode_item = create_plex_item_from_fixture(episode_fixture)
        store = BatchStore()
        service = BatchService(settings=settings, batch_store=store)

        mock_client = MagicMock()
        mock_client.get_metadata = AsyncMock(return_value=episode_item)
        mock_client.set_subtitle_stream = AsyncMock()

        from salsa.backend.services.matcher import StreamMatcher
        matcher = StreamMatcher()

        result = await service._process_item(
            client=mock_client,
            token="test-token",
            server_url="http://localhost:32400",
            item=episode_item,
            stream_type=StreamType.SUBTITLE,
            source_stream=None,
            matcher=matcher,
            set_none=True,
        )

        assert result.success is True
        assert result.match_level == "NONE"
        mock_client.set_subtitle_stream.assert_called_once_with(
            "http://localhost:32400",
            "test-token",
            episode_item.first_part.id,
            None,
        )

    @pytest.mark.asyncio
    async def test_process_item_handles_no_part(self, settings):
        """Should handle items without part information."""
        item_no_part = PlexMediaItem(
            rating_key="12345",
            key="/library/metadata/12345",
            type="episode",
            title="No Part Episode",
        )

        store = BatchStore()
        service = BatchService(settings=settings, batch_store=store)

        mock_client = MagicMock()
        mock_client.get_metadata = AsyncMock(return_value=item_no_part)

        from salsa.backend.services.matcher import StreamMatcher
        matcher = StreamMatcher()

        result = await service._process_item(
            client=mock_client,
            token="test-token",
            server_url="http://localhost:32400",
            item=item_no_part,
            stream_type=StreamType.AUDIO,
            source_stream=None,
            matcher=matcher,
            set_none=False,
        )

        assert result.success is False
        assert "part" in result.error.lower() or "media" in result.error.lower()


class TestBatchServiceRealDataPatterns:
    """Tests using real data patterns from captured fixtures."""

    @pytest.mark.asyncio
    async def test_anime_multilingual_audio_matching(self, settings, episode_fixture):
        """Test matching Japanese audio in anime (Jujutsu Kaisen fixture)."""
        episode_item = create_plex_item_from_fixture(episode_fixture)

        audio_streams = episode_item.first_part.audio_streams
        assert len(audio_streams) == 2

        lang_codes = {s.language_code for s in audio_streams}
        assert "eng" in lang_codes
        assert "jpn" in lang_codes

    @pytest.mark.asyncio
    async def test_multilingual_subtitle_matching(self, settings, episode_fixture):
        """Test matching subtitles with multiple languages (synthetic fixture has 4 streams)."""
        episode_item = create_plex_item_from_fixture(episode_fixture)

        subtitle_streams = episode_item.first_part.subtitle_streams
        assert len(subtitle_streams) == 4

        lang_codes = {s.language_code for s in subtitle_streams}
        expected_langs = {"eng", "fra", "deu"}
        assert expected_langs.issubset(lang_codes)

    @pytest.mark.asyncio
    async def test_stream_selection_state(self, settings, episode_fixture):
        """Verify correct stream selection state from fixture."""
        episode_item = create_plex_item_from_fixture(episode_fixture)

        selected_audio = [s for s in episode_item.first_part.audio_streams if s.selected]
        assert len(selected_audio) == 1
        assert selected_audio[0].language_code == "jpn"

        selected_sub = [s for s in episode_item.first_part.subtitle_streams if s.selected]
        assert len(selected_sub) == 1
        assert selected_sub[0].language_code == "eng"
