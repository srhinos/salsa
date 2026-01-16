"""Tests for Reflex frontend state logic.

These tests verify the business logic in state classes
by testing computed vars and filter methods.
"""

import pytest

# =============================================================================
# =============================================================================

def filter_items(items: list[dict], search: str) -> list[dict]:
    """Filter items by title or year - mirrors BrowserState.filtered_items logic."""
    if not search:
        return items
    search = search.lower()
    return [
        i for i in items
        if search in i.get("title", "").lower()
        or search in str(i.get("year", ""))
    ]


def filter_seasons(seasons: list[dict], search: str) -> list[dict]:
    """Filter seasons by title - mirrors BrowserState.filtered_seasons logic."""
    if not search:
        return seasons
    search = search.lower()
    return [
        s for s in seasons
        if search in s.get("title", "").lower()
    ]


def filter_episodes(episodes: list[dict], search: str) -> list[dict]:
    """Filter episodes by title or number - mirrors BrowserState.filtered_episodes logic."""
    if not search:
        return episodes
    search = search.lower()
    return [
        e for e in episodes
        if search in e.get("title", "").lower()
        or search in str(e.get("index", ""))
    ]


class TestItemFilter:
    """Tests for item filtering logic."""

    @pytest.fixture
    def sample_items(self):
        """Sample TV show/movie items."""
        return [
            {"rating_key": "1", "title": "Breaking Bad", "type": "show", "year": 2008},
            {"rating_key": "2", "title": "Better Call Saul", "type": "show", "year": 2015},
            {"rating_key": "3", "title": "The Office", "type": "show", "year": 2005},
            {"rating_key": "4", "title": "Jujutsu Kaisen", "type": "show", "year": 2020},
            {"rating_key": "5", "title": "2 Fast 2 Furious", "type": "movie", "year": 2003},
        ]

    def test_filter_empty_returns_all(self, sample_items):
        """Empty search returns all items."""
        assert filter_items(sample_items, "") == sample_items

    def test_filter_by_title(self, sample_items):
        """Filter by title substring."""
        result = filter_items(sample_items, "breaking")
        assert len(result) == 1
        assert result[0]["title"] == "Breaking Bad"

    def test_filter_by_title_case_insensitive(self, sample_items):
        """Filter is case-insensitive."""
        result = filter_items(sample_items, "BREAKING")
        assert len(result) == 1
        assert result[0]["title"] == "Breaking Bad"

    def test_filter_by_year(self, sample_items):
        """Filter by year."""
        result = filter_items(sample_items, "2020")
        assert len(result) == 1
        assert result[0]["title"] == "Jujutsu Kaisen"

    def test_filter_partial_year(self, sample_items):
        """Filter by partial year."""
        result = filter_items(sample_items, "200")
        assert len(result) == 3

    def test_filter_multiple_matches(self, sample_items):
        """Filter returns multiple matches."""
        result = filter_items(sample_items, "the")
        assert len(result) == 1
        assert result[0]["title"] == "The Office"

    def test_filter_no_matches(self, sample_items):
        """Filter with no matches returns empty."""
        result = filter_items(sample_items, "xyz123")
        assert len(result) == 0

    def test_filter_partial_title(self, sample_items):
        """Filter by partial title."""
        result = filter_items(sample_items, "call")
        assert len(result) == 1
        assert result[0]["title"] == "Better Call Saul"


class TestSeasonFilter:
    """Tests for season filtering logic."""

    @pytest.fixture
    def sample_seasons(self):
        """Sample seasons."""
        return [
            {"rating_key": "101", "title": "Season 1", "index": 1},
            {"rating_key": "102", "title": "Season 2", "index": 2},
            {"rating_key": "103", "title": "Season 3", "index": 3},
            {"rating_key": "104", "title": "Specials", "index": 0},
        ]

    def test_filter_empty_returns_all(self, sample_seasons):
        """Empty search returns all seasons."""
        assert filter_seasons(sample_seasons, "") == sample_seasons

    def test_filter_by_number(self, sample_seasons):
        """Filter by season number."""
        result = filter_seasons(sample_seasons, "2")
        assert len(result) == 1
        assert result[0]["title"] == "Season 2"

    def test_filter_by_title(self, sample_seasons):
        """Filter by full title."""
        result = filter_seasons(sample_seasons, "specials")
        assert len(result) == 1
        assert result[0]["title"] == "Specials"


class TestEpisodeFilter:
    """Tests for episode filtering logic."""

    @pytest.fixture
    def sample_episodes(self):
        """Sample episodes."""
        return [
            {"rating_key": "201", "title": "Pilot", "index": 1},
            {"rating_key": "202", "title": "The Cat's in the Bag", "index": 2},
            {"rating_key": "203", "title": "Cancer Man", "index": 3},
            {"rating_key": "204", "title": "Gray Matter", "index": 4},
            {"rating_key": "205", "title": "Crazy Handful of Nothin'", "index": 5},
        ]

    def test_filter_empty_returns_all(self, sample_episodes):
        """Empty search returns all episodes."""
        assert filter_episodes(sample_episodes, "") == sample_episodes

    def test_filter_by_title(self, sample_episodes):
        """Filter by title substring."""
        result = filter_episodes(sample_episodes, "cat")
        assert len(result) == 1
        assert result[0]["title"] == "The Cat's in the Bag"

    def test_filter_by_episode_number(self, sample_episodes):
        """Filter by episode number."""
        result = filter_episodes(sample_episodes, "3")
        assert len(result) == 1
        assert result[0]["title"] == "Cancer Man"

    def test_filter_no_matches(self, sample_episodes):
        """No matches returns empty list."""
        result = filter_episodes(sample_episodes, "xyz")
        assert len(result) == 0


# =============================================================================
# =============================================================================


def generate_breadcrumbs(
    library_title: str = "",
    library_key: str = "",
    item_title: str = "",
    item_key: str = "",
    season_title: str = "",
    season_key: str = "",
    episode_title: str = "",
    episode_key: str = "",
) -> list[dict]:
    """Generate breadcrumb navigation - mirrors BrowserState.breadcrumbs logic."""
    crumbs = []

    if library_title:
        crumbs.append({
            "key": library_key,
            "title": library_title,
            "level": "library",
        })

    if item_title:
        crumbs.append({
            "key": item_key,
            "title": item_title,
            "level": "item",
        })

    if season_title:
        crumbs.append({
            "key": season_key,
            "title": season_title,
            "level": "season",
        })

    if episode_title:
        crumbs.append({
            "key": episode_key,
            "title": episode_title,
            "level": "episode",
        })

    return crumbs


class TestBreadcrumbGeneration:
    """Tests for breadcrumb generation logic."""

    def test_empty_state(self):
        """No selection returns empty breadcrumbs."""
        result = generate_breadcrumbs()
        assert result == []

    def test_library_only(self):
        """Only library selected."""
        result = generate_breadcrumbs(
            library_title="TV Shows",
            library_key="1",
        )
        assert len(result) == 1
        assert result[0]["title"] == "TV Shows"
        assert result[0]["level"] == "library"

    def test_library_and_show(self):
        """Library and show selected."""
        result = generate_breadcrumbs(
            library_title="TV Shows",
            library_key="1",
            item_title="Breaking Bad",
            item_key="100",
        )
        assert len(result) == 2
        assert result[0]["level"] == "library"
        assert result[1]["title"] == "Breaking Bad"
        assert result[1]["level"] == "item"

    def test_full_path(self):
        """Full navigation path."""
        result = generate_breadcrumbs(
            library_title="TV Shows",
            library_key="1",
            item_title="Breaking Bad",
            item_key="100",
            season_title="Season 1",
            season_key="101",
            episode_title="Pilot",
            episode_key="201",
        )
        assert len(result) == 4
        assert [c["level"] for c in result] == ["library", "item", "season", "episode"]
        assert result[3]["title"] == "Pilot"


# =============================================================================
# =============================================================================


def get_audio_text(stream_summary: dict | None) -> str:
    """Get current audio selection text - mirrors BrowserState.current_audio_text."""
    if not stream_summary:
        return ""
    current = stream_summary.get("current_audio")
    if not current:
        return ""
    lang = current.get("language", "Unknown")
    count = current.get("count", 0)
    total = stream_summary.get("total_items", 0)
    is_uniform = current.get("is_uniform", False)
    if is_uniform:
        return f"{lang} on all episodes"
    return f"{lang} on {count}/{total} episodes"


def get_subtitle_text(stream_summary: dict | None) -> str:
    """Get current subtitle selection text - mirrors BrowserState.current_subtitle_text."""
    if not stream_summary:
        return ""
    current = stream_summary.get("current_subtitle")
    if not current:
        return ""
    lang = current.get("language", "Unknown")
    count = current.get("count", 0)
    total = stream_summary.get("total_items", 0)
    is_uniform = current.get("is_uniform", False)
    if lang == "None":
        if is_uniform:
            return "Disabled on all episodes"
        return f"Disabled on {count}/{total} episodes"
    if is_uniform:
        return f"{lang} on all episodes"
    return f"{lang} on {count}/{total} episodes"


class TestStreamSelectionText:
    """Tests for stream selection text generation."""

    def test_audio_text_none_summary(self):
        """No summary returns empty string."""
        assert get_audio_text(None) == ""

    def test_audio_text_no_current(self):
        """No current selection returns empty string."""
        summary = {"total_items": 10}
        assert get_audio_text(summary) == ""

    def test_audio_text_uniform(self):
        """Uniform selection shows 'on all episodes'."""
        summary = {
            "total_items": 10,
            "current_audio": {
                "language": "Japanese",
                "count": 10,
                "is_uniform": True,
            },
        }
        assert get_audio_text(summary) == "Japanese on all episodes"

    def test_audio_text_mixed(self):
        """Mixed selection shows count."""
        summary = {
            "total_items": 10,
            "current_audio": {
                "language": "English",
                "count": 7,
                "is_uniform": False,
            },
        }
        assert get_audio_text(summary) == "English on 7/10 episodes"

    def test_subtitle_text_disabled_uniform(self):
        """All subtitles disabled."""
        summary = {
            "total_items": 10,
            "current_subtitle": {
                "language": "None",
                "count": 10,
                "is_uniform": True,
            },
        }
        assert get_subtitle_text(summary) == "Disabled on all episodes"

    def test_subtitle_text_disabled_mixed(self):
        """Some subtitles disabled."""
        summary = {
            "total_items": 10,
            "current_subtitle": {
                "language": "None",
                "count": 6,
                "is_uniform": False,
            },
        }
        assert get_subtitle_text(summary) == "Disabled on 6/10 episodes"

    def test_subtitle_text_with_language(self):
        """Subtitle with language selected."""
        summary = {
            "total_items": 24,
            "current_subtitle": {
                "language": "English",
                "count": 24,
                "is_uniform": True,
            },
        }
        assert get_subtitle_text(summary) == "English on all episodes"


# =============================================================================
# =============================================================================


def get_selected_stream(streams: list[dict]) -> dict | None:
    """Get currently selected stream - mirrors state methods."""
    for stream in streams:
        if stream.get("selected"):
            return stream
    return None


class TestStreamHelpers:
    """Tests for stream helper functions."""

    def test_get_selected_stream_found(self):
        """Returns selected stream when present."""
        streams = [
            {"id": 1, "language": "English", "selected": False},
            {"id": 2, "language": "Japanese", "selected": True},
            {"id": 3, "language": "French", "selected": False},
        ]
        result = get_selected_stream(streams)
        assert result is not None
        assert result["language"] == "Japanese"

    def test_get_selected_stream_none(self):
        """Returns None when no stream selected."""
        streams = [
            {"id": 1, "language": "English", "selected": False},
            {"id": 2, "language": "Japanese", "selected": False},
        ]
        result = get_selected_stream(streams)
        assert result is None

    def test_get_selected_stream_empty_list(self):
        """Returns None for empty list."""
        result = get_selected_stream([])
        assert result is None


# =============================================================================
# =============================================================================


def has_streams(audio_streams: list, subtitle_streams: list) -> bool:
    """Check if streams are loaded - mirrors BrowserState.has_streams."""
    return len(audio_streams) > 0 or len(subtitle_streams) > 0


class TestHasStreams:
    """Tests for has_streams logic."""

    def test_no_streams(self):
        """No streams loaded."""
        assert has_streams([], []) is False

    def test_only_audio(self):
        """Only audio streams."""
        assert has_streams([{"id": 1}], []) is True

    def test_only_subtitle(self):
        """Only subtitle streams."""
        assert has_streams([], [{"id": 1}]) is True

    def test_both_streams(self):
        """Both audio and subtitle streams."""
        assert has_streams([{"id": 1}], [{"id": 2}]) is True
