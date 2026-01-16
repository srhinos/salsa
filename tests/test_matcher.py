"""Tests for the stream matching algorithm."""


from salsa.backend.models.plex import PlexStream
from salsa.backend.services.matcher import (
    MatchLevel,
    StreamMatcher,
    find_matching_stream,
    find_stream_by_id,
)


def make_stream(
    stream_id: int = 1,
    stream_type: int = 2,
    codec: str | None = "aac",
    language: str | None = "English",
    language_code: str | None = "eng",
    title: str | None = None,
    display_title: str | None = "English (AAC Stereo)",
    selected: bool = False,
    channels: int | None = 2,
) -> PlexStream:
    """Create a PlexStream for testing."""
    return PlexStream(
        id=stream_id,
        streamType=stream_type,
        codec=codec,
        language=language,
        languageCode=language_code,
        title=title,
        displayTitle=display_title,
        selected=selected,
        channels=channels,
    )


class TestStreamMatcher:
    """Tests for StreamMatcher class."""

    def test_no_candidates_returns_no_match(self):
        """Should return no match when candidates list is empty."""
        matcher = StreamMatcher()
        target = make_stream()

        result = matcher.find_match(target, [])

        assert not result.matched
        assert result.stream is None
        assert "No candidate streams" in result.reason

    def test_exact_match(self):
        """Should match exactly when all properties match."""
        target = make_stream(
            codec="aac",
            language="English",
            language_code="eng",
            title="Main Audio",
            display_title="English (AAC Stereo)",
            channels=2,
        )
        candidate = make_stream(
            stream_id=2,
            codec="aac",
            language="English",
            language_code="eng",
            title="Main Audio",
            display_title="English (AAC Stereo)",
            channels=2,
        )

        matcher = StreamMatcher()
        result = matcher.find_match(target, [candidate])

        assert result.matched
        assert result.stream == candidate
        assert result.match_level == MatchLevel.EXACT

    def test_title_display_codec_match(self):
        """Should match on title + display_title + codec."""
        target = make_stream(
            title="Director Commentary",
            display_title="English (Commentary)",
            codec="ac3",
            channels=6,
        )
        candidate = make_stream(
            stream_id=2,
            title="Director Commentary",
            display_title="English (Commentary)",
            codec="ac3",
            channels=2,
        )

        matcher = StreamMatcher()
        result = matcher.find_match(target, [candidate])

        assert result.matched
        assert result.match_level == MatchLevel.TITLE_DISPLAY_CODEC

    def test_title_display_match(self):
        """Should match on title + display_title."""
        target = make_stream(
            title="Japanese",
            display_title="Japanese (DTS-HD MA 5.1)",
            codec="dts",
        )
        candidate = make_stream(
            stream_id=2,
            title="Japanese",
            display_title="Japanese (DTS-HD MA 5.1)",
            codec="aac",
        )

        matcher = StreamMatcher()
        result = matcher.find_match(target, [candidate])

        assert result.matched
        assert result.match_level == MatchLevel.TITLE_DISPLAY

    def test_title_only_match(self):
        """Should match on title only."""
        target = make_stream(
            title="Japanese",
            display_title="Japanese (AAC Stereo)",
        )
        candidate = make_stream(
            stream_id=2,
            title="Japanese",
            display_title="Something Different",
        )

        matcher = StreamMatcher()
        result = matcher.find_match(target, [candidate])

        assert result.matched
        assert result.match_level == MatchLevel.TITLE

    def test_display_title_match(self):
        """Should match on display_title only when title doesn't match."""
        target = make_stream(
            title="Track A",
            display_title="English (Stereo)",
            channels=6,
        )
        candidate = make_stream(
            stream_id=2,
            title="Track B",
            display_title="English (Stereo)",
            channels=2,
        )

        matcher = StreamMatcher()
        result = matcher.find_match(target, [candidate])

        assert result.matched
        assert result.match_level == MatchLevel.DISPLAY_TITLE

    def test_language_match(self):
        """Should match on language name."""
        target = make_stream(
            title=None,
            display_title="Different",
            language="Japanese",
        )
        candidate = make_stream(
            stream_id=2,
            title="Other",
            display_title="Other Display",
            language="Japanese",
        )

        matcher = StreamMatcher()
        result = matcher.find_match(target, [candidate])

        assert result.matched
        assert result.match_level == MatchLevel.LANGUAGE

    def test_language_code_match(self):
        """Should match on language code as last resort."""
        target = make_stream(
            title=None,
            display_title="Different",
            language=None,
            language_code="jpn",
        )
        candidate = make_stream(
            stream_id=2,
            title=None,
            display_title="Other",
            language=None,
            language_code="jpn",
        )

        matcher = StreamMatcher()
        result = matcher.find_match(target, [candidate])

        assert result.matched
        assert result.match_level == MatchLevel.LANGUAGE_CODE

    def test_no_match_found(self):
        """Should return no match when nothing matches."""
        target = make_stream(
            title="German",
            display_title="German (AAC)",
            language="German",
            language_code="ger",
        )
        candidate = make_stream(
            stream_id=2,
            title="Japanese",
            display_title="Japanese (AAC)",
            language="Japanese",
            language_code="jpn",
        )

        matcher = StreamMatcher()
        result = matcher.find_match(target, [candidate])

        assert not result.matched
        assert "No matching stream found" in result.reason


class TestKeywordFilter:
    """Tests for keyword filtering functionality."""

    def test_keyword_filter_in_title(self):
        """Should only match streams containing keyword in title."""
        target = make_stream(title="Commentary")
        candidates = [
            make_stream(stream_id=1, title="Main Audio", language="English"),
            make_stream(stream_id=2, title="Director Commentary", language="English"),
        ]

        matcher = StreamMatcher(keyword_filter="commentary")
        result = matcher.find_match(target, candidates)

        assert result.matched
        assert result.stream is not None
        assert result.stream.id == 2

    def test_keyword_filter_in_display_title(self):
        """Should match keyword in display_title."""
        target = make_stream(display_title="Japanese (SDH)")
        candidates = [
            make_stream(stream_id=1, display_title="English (Normal)"),
            make_stream(stream_id=2, display_title="English (SDH)"),
        ]

        matcher = StreamMatcher(keyword_filter="SDH")
        result = matcher.find_match(target, candidates)

        assert result.matched
        assert result.stream is not None
        assert result.stream.id == 2

    def test_keyword_filter_case_insensitive(self):
        """Keyword filter should be case insensitive."""
        target = make_stream(title="COMMENTARY")
        candidates = [
            make_stream(stream_id=1, title="commentary track"),
        ]

        matcher = StreamMatcher(keyword_filter="COMMENTARY")
        result = matcher.find_match(target, candidates)

        assert result.matched

    def test_keyword_filter_no_matches(self):
        """Should return no match when keyword doesn't match any candidate."""
        target = make_stream(title="Commentary")
        candidates = [
            make_stream(stream_id=1, title="Main Audio"),
            make_stream(stream_id=2, title="Secondary Audio"),
        ]

        matcher = StreamMatcher(keyword_filter="commentary")
        result = matcher.find_match(target, candidates)

        assert not result.matched
        assert "keyword filter" in result.reason


class TestAlreadySelected:
    """Tests for already_selected detection."""

    def test_already_selected_true(self):
        """Should detect when matched stream is already selected."""
        target = make_stream(title="Japanese")
        candidate = make_stream(stream_id=2, title="Japanese", selected=True)

        matcher = StreamMatcher()
        result = matcher.find_match(target, [candidate])

        assert result.matched
        assert result.already_selected

    def test_already_selected_false(self):
        """Should return false when matched stream is not selected."""
        target = make_stream(title="Japanese")
        candidate = make_stream(stream_id=2, title="Japanese", selected=False)

        matcher = StreamMatcher()
        result = matcher.find_match(target, [candidate])

        assert result.matched
        assert not result.already_selected


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_find_matching_stream(self):
        """Should work as convenience wrapper."""
        target = make_stream(title="Japanese")
        candidates = [make_stream(stream_id=2, title="Japanese")]

        result = find_matching_stream(target, candidates)

        assert result.matched
        assert result.stream is not None
        assert result.stream.id == 2

    def test_find_matching_stream_with_keyword(self):
        """Should apply keyword filter."""
        target = make_stream(title="Commentary")
        candidates = [
            make_stream(stream_id=1, title="Main"),
            make_stream(stream_id=2, title="Commentary"),
        ]

        result = find_matching_stream(target, candidates, keyword_filter="commentary")

        assert result.matched
        assert result.stream is not None
        assert result.stream.id == 2

    def test_find_stream_by_id_found(self):
        """Should find stream by ID."""
        candidates = [
            make_stream(stream_id=1),
            make_stream(stream_id=2),
            make_stream(stream_id=3),
        ]

        result = find_stream_by_id(2, candidates)

        assert result is not None
        assert result.id == 2

    def test_find_stream_by_id_not_found(self):
        """Should return None when ID not found."""
        candidates = [
            make_stream(stream_id=1),
            make_stream(stream_id=2),
        ]

        result = find_stream_by_id(999, candidates)

        assert result is None


class TestMatchPriority:
    """Tests to ensure match levels are tried in correct priority order."""

    def test_exact_match_preferred_over_title(self):
        """Exact match should be preferred over partial matches."""
        target = make_stream(
            title="Japanese",
            display_title="Japanese (AAC Stereo)",
            codec="aac",
            language="Japanese",
            language_code="jpn",
            channels=2,
        )
        exact = make_stream(
            stream_id=1,
            title="Japanese",
            display_title="Japanese (AAC Stereo)",
            codec="aac",
            language="Japanese",
            language_code="jpn",
            channels=2,
        )
        title_only = make_stream(
            stream_id=2,
            title="Japanese",
            display_title="Different",
            codec="dts",
            language="English",
            language_code="eng",
        )

        matcher = StreamMatcher()
        result = matcher.find_match(target, [title_only, exact])

        assert result.matched
        assert result.stream is not None
        assert result.stream.id == 1
        assert result.match_level == MatchLevel.EXACT

    def test_multiple_candidates_selects_first_at_level(self):
        """When multiple candidates match at same level, select first."""
        target = make_stream(title="Japanese")
        candidates = [
            make_stream(stream_id=1, title="Japanese"),
            make_stream(stream_id=2, title="Japanese"),
        ]

        matcher = StreamMatcher()
        result = matcher.find_match(target, candidates)

        assert result.matched
        assert result.stream is not None
        assert result.stream.id == 1
