"""Stream matching algorithm for batch updates."""

from dataclasses import dataclass
from enum import Enum

from salsa.backend.models.plex import PlexStream


class MatchLevel(Enum):
    """Match priority levels (lower = better match)."""

    EXACT = 1
    TITLE_DISPLAY_CODEC = 2
    TITLE_DISPLAY = 3
    TITLE = 4
    DISPLAY_TITLE = 5
    LANGUAGE = 6
    LANGUAGE_CODE = 7
    NO_MATCH = 99


@dataclass
class MatchResult:
    """Result of a stream matching attempt."""

    matched: bool
    stream: PlexStream | None = None
    match_level: MatchLevel = MatchLevel.NO_MATCH
    reason: str = ""

    @property
    def already_selected(self) -> bool:
        """Check if matched stream is already selected."""
        return self.matched and self.stream is not None and self.stream.selected


class StreamMatcher:
    """
    Intelligent stream matching for batch updates.

    Implements a 7-level priority matching algorithm to find the best
    matching stream across different episodes/items.
    """

    def __init__(self, keyword_filter: str | None = None):
        """
        Initialize the matcher.

        Args:
            keyword_filter: Optional keyword that must be present in stream
                           title or display_title (e.g., "Commentary", "English")
        """
        self.keyword_filter = keyword_filter.lower() if keyword_filter else None

    def _matches_keyword(self, stream: PlexStream) -> bool:
        """Check if stream matches the keyword filter."""
        if not self.keyword_filter:
            return True

        title = (stream.title or "").lower()
        display = (stream.display_title or "").lower()

        return self.keyword_filter in title or self.keyword_filter in display

    def _normalize(self, value: str | None) -> str:
        """Normalize a string for comparison."""
        if not value:
            return ""
        return value.lower().strip()

    def find_match(
        self,
        target: PlexStream,
        candidates: list[PlexStream],
    ) -> MatchResult:
        """
        Find the best matching stream from candidates.

        Args:
            target: The stream to match (from source item)
            candidates: Available streams to match against

        Returns:
            MatchResult with matched stream or reason for no match
        """
        if not candidates:
            return MatchResult(matched=False, reason="No candidate streams available")

        filtered = [s for s in candidates if self._matches_keyword(s)]
        if not filtered:
            return MatchResult(
                matched=False,
                reason=f"No streams match keyword filter: {self.keyword_filter}",
            )

        for level in MatchLevel:
            if level == MatchLevel.NO_MATCH:
                continue

            match = self._try_match_level(target, filtered, level)
            if match:
                return MatchResult(
                    matched=True,
                    stream=match,
                    match_level=level,
                    reason=f"Matched at level: {level.name}",
                )

        return MatchResult(matched=False, reason="No matching stream found at any level")

    def _try_match_level(
        self,
        target: PlexStream,
        candidates: list[PlexStream],
        level: MatchLevel,
    ) -> PlexStream | None:
        """Try to find a match at the specified level."""
        for candidate in candidates:
            if self._matches_at_level(target, candidate, level):
                return candidate
        return None

    def _matches_at_level(
        self,
        target: PlexStream,
        candidate: PlexStream,
        level: MatchLevel,
    ) -> bool:
        """Check if candidate matches target at the specified level."""
        t_title = self._normalize(target.title)
        t_display = self._normalize(target.display_title)
        t_codec = self._normalize(target.codec)
        t_lang = self._normalize(target.language)
        t_lang_code = self._normalize(target.language_code)

        c_title = self._normalize(candidate.title)
        c_display = self._normalize(candidate.display_title)
        c_codec = self._normalize(candidate.codec)
        c_lang = self._normalize(candidate.language)
        c_lang_code = self._normalize(candidate.language_code)

        match level:
            case MatchLevel.EXACT:
                return (
                    (not t_title or t_title == c_title)
                    and (not t_display or t_display == c_display)
                    and (not t_codec or t_codec == c_codec)
                    and (not t_lang or t_lang == c_lang)
                    and (not t_lang_code or t_lang_code == c_lang_code)
                    and candidate.channels == target.channels
                )

            case MatchLevel.TITLE_DISPLAY_CODEC:
                return bool(
                    t_title
                    and t_title == c_title
                    and t_display
                    and t_display == c_display
                    and t_codec
                    and t_codec == c_codec
                )

            case MatchLevel.TITLE_DISPLAY:
                return bool(t_title and t_title == c_title and t_display and t_display == c_display)

            case MatchLevel.TITLE:
                return bool(t_title and t_title == c_title)

            case MatchLevel.DISPLAY_TITLE:
                return bool(t_display and t_display == c_display)

            case MatchLevel.LANGUAGE:
                return bool(t_lang and t_lang == c_lang)

            case MatchLevel.LANGUAGE_CODE:
                return bool(t_lang_code and t_lang_code == c_lang_code)

            case _:
                return False


def find_matching_stream(
    target: PlexStream,
    candidates: list[PlexStream],
    keyword_filter: str | None = None,
) -> MatchResult:
    """
    Convenience function to find a matching stream.

    Args:
        target: The stream to match
        candidates: Available streams
        keyword_filter: Optional keyword filter

    Returns:
        MatchResult
    """
    matcher = StreamMatcher(keyword_filter=keyword_filter)
    return matcher.find_match(target, candidates)


def find_stream_by_id(
    stream_id: int,
    candidates: list[PlexStream],
) -> PlexStream | None:
    """
    Find a stream by its ID.

    Args:
        stream_id: Stream ID to find
        candidates: Available streams

    Returns:
        PlexStream if found, None otherwise
    """
    for stream in candidates:
        if stream.id == stream_id:
            return stream
    return None
