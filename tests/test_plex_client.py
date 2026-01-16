"""Tests for the Plex API client with mocked responses."""

import pytest
import respx
from httpx import Response

from salsa.backend.config import Settings
from salsa.backend.services.plex_client import (
    PlexAuthError,
    PlexClient,
    PlexClientError,
)


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
def mock_pin_response() -> dict:
    """Mock PIN creation response."""
    return {
        "id": 12345,
        "code": "ABCD",
        "authToken": None,
        "expiresIn": 600,
        "clientIdentifier": "test-client-id",
    }


@pytest.fixture
def mock_user_response() -> dict:
    """Mock user info response."""
    return {
        "id": 1,
        "uuid": "user-uuid-123",
        "username": "testuser",
        "title": "Test User",
        "email": "test@example.com",
        "thumb": "https://plex.tv/users/avatar.png",
    }


@pytest.fixture
def mock_server_identity() -> dict:
    """Mock server identity response."""
    return {
        "MediaContainer": {
            "machineIdentifier": "abc123",
            "version": "1.32.0",
        }
    }


@pytest.fixture
def mock_libraries_response() -> dict:
    """Mock libraries response."""
    return {
        "MediaContainer": {
            "Directory": [
                {
                    "key": "1",
                    "title": "Movies",
                    "type": "movie",
                    "uuid": "lib-uuid-1",
                },
                {
                    "key": "2",
                    "title": "TV Shows",
                    "type": "show",
                    "uuid": "lib-uuid-2",
                },
            ]
        }
    }


@pytest.fixture
def mock_media_item_response() -> dict:
    """Mock media item with streams."""
    return {
        "MediaContainer": {
            "size": 1,
            "Metadata": [
                {
                    "ratingKey": "12345",
                    "key": "/library/metadata/12345",
                    "type": "episode",
                    "title": "Pilot",
                    "index": 1,
                    "parentIndex": 1,
                    "Media": [
                        {
                            "id": 100,
                            "duration": 3600000,
                            "Part": [
                                {
                                    "id": 200,
                                    "key": "/library/parts/200/file.mkv",
                                    "Stream": [
                                        {
                                            "id": 301,
                                            "streamType": 2,
                                            "codec": "aac",
                                            "language": "English",
                                            "languageCode": "eng",
                                            "displayTitle": "English (AAC Stereo)",
                                            "selected": True,
                                            "channels": 2,
                                        },
                                        {
                                            "id": 302,
                                            "streamType": 2,
                                            "codec": "aac",
                                            "language": "Japanese",
                                            "languageCode": "jpn",
                                            "displayTitle": "Japanese (AAC Stereo)",
                                            "selected": False,
                                            "channels": 2,
                                        },
                                        {
                                            "id": 401,
                                            "streamType": 3,
                                            "codec": "srt",
                                            "language": "English",
                                            "languageCode": "eng",
                                            "displayTitle": "English (SRT)",
                                            "selected": False,
                                        },
                                    ],
                                }
                            ],
                        }
                    ],
                }
            ],
        }
    }


class TestPinAuthentication:
    """Tests for PIN-based authentication."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_create_pin(self, settings: Settings, mock_pin_response: dict):
        """Should create a PIN for OAuth flow."""
        respx.post("https://plex.tv/api/v2/pins").mock(
            return_value=Response(200, json=mock_pin_response)
        )

        async with PlexClient(settings) as client:
            pin = await client.create_pin()

        assert pin.id == 12345
        assert pin.code == "ABCD"
        assert pin.auth_token is None
        assert pin.expires_in == 600

    @pytest.mark.asyncio
    @respx.mock
    async def test_create_pin_sends_strong_as_query_param(self, settings: Settings, mock_pin_response: dict):
        """Verify strong=true is sent as query param, not header."""
        route = respx.post("https://plex.tv/api/v2/pins").mock(
            return_value=Response(200, json=mock_pin_response)
        )

        async with PlexClient(settings) as client:
            await client.create_pin()

        assert route.called
        request = route.calls[0].request
        assert "strong=true" in str(request.url)

    @pytest.mark.asyncio
    @respx.mock
    async def test_check_pin(self, settings: Settings):
        """Should check PIN status."""
        authenticated_response = {
            "id": 12345,
            "code": "ABCD",
            "authToken": "user-auth-token",
            "expiresIn": 500,
            "clientIdentifier": "test-client-id",
        }
        respx.get("https://plex.tv/api/v2/pins/12345").mock(
            return_value=Response(200, json=authenticated_response)
        )

        async with PlexClient(settings) as client:
            pin = await client.check_pin(12345, "ABCD")

        assert pin.auth_token == "user-auth-token"

    @pytest.mark.asyncio
    @respx.mock
    async def test_check_pin_sends_code_as_query_param(self, settings: Settings, mock_pin_response: dict):
        """Verify code is sent as query param, not header."""
        route = respx.get("https://plex.tv/api/v2/pins/12345").mock(
            return_value=Response(200, json=mock_pin_response)
        )

        async with PlexClient(settings) as client:
            await client.check_pin(12345, "ABCD")

        assert route.called
        request = route.calls[0].request
        assert "code=ABCD" in str(request.url)


class TestUserManagement:
    """Tests for user management."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_user(self, settings: Settings, mock_user_response: dict):
        """Should get current user info."""
        respx.get("https://plex.tv/api/v2/user").mock(
            return_value=Response(200, json=mock_user_response)
        )

        async with PlexClient(settings) as client:
            user = await client.get_user("test-token")

        assert user.username == "testuser"
        assert user.email == "test@example.com"

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_user_invalid_token(self, settings: Settings):
        """Should raise PlexAuthError for invalid token."""
        respx.get("https://plex.tv/api/v2/user").mock(
            return_value=Response(401, json={"error": "Invalid token"})
        )

        async with PlexClient(settings) as client:
            with pytest.raises(PlexAuthError):
                await client.get_user("invalid-token")

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_home_users(self, settings: Settings):
        """Should get list of home users."""
        home_users_response = {
            "users": [
                {
                    "id": 1,
                    "uuid": "user-1-uuid",
                    "title": "Admin",
                    "admin": True,
                    "protected": False,
                },
                {
                    "id": 2,
                    "uuid": "user-2-uuid",
                    "title": "Kid",
                    "admin": False,
                    "protected": True,
                },
            ]
        }
        respx.get("https://plex.tv/api/v2/home/users").mock(
            return_value=Response(200, json=home_users_response)
        )

        async with PlexClient(settings) as client:
            users = await client.get_home_users("admin-token")

        assert len(users) == 2
        assert users[0].admin is True
        assert users[1].protected is True


class TestServerConnection:
    """Tests for direct server communication."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_check_server_identity(self, settings: Settings, mock_server_identity: dict):
        """Should get server identity."""
        respx.get("http://localhost:32400/identity").mock(
            return_value=Response(200, json=mock_server_identity)
        )

        async with PlexClient(settings) as client:
            identity = await client.check_server_identity(
                "http://localhost:32400",
                "test-token",
            )

        assert identity.machine_identifier == "abc123"
        assert identity.version == "1.32.0"

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_libraries(self, settings: Settings, mock_libraries_response: dict):
        """Should get library list."""
        respx.get("http://localhost:32400/library/sections").mock(
            return_value=Response(200, json=mock_libraries_response)
        )

        async with PlexClient(settings) as client:
            libraries = await client.get_libraries(
                "http://localhost:32400",
                "test-token",
            )

        assert len(libraries) == 2
        assert libraries[0]["title"] == "Movies"
        assert libraries[1]["title"] == "TV Shows"


class TestMetadata:
    """Tests for metadata retrieval."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_metadata(self, settings: Settings, mock_media_item_response: dict):
        """Should get item metadata with streams."""
        respx.get("http://localhost:32400/library/metadata/12345").mock(
            return_value=Response(200, json=mock_media_item_response)
        )

        async with PlexClient(settings) as client:
            item = await client.get_metadata(
                "http://localhost:32400",
                "test-token",
                "12345",
            )

        assert item is not None
        assert item.rating_key == "12345"
        assert item.title == "Pilot"
        assert item.first_part is not None
        assert len(item.first_part.streams) == 3
        assert len(item.first_part.audio_streams) == 2
        assert len(item.first_part.subtitle_streams) == 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_metadata_includes_checkfiles_param(
        self, settings: Settings, mock_media_item_response: dict
    ):
        """Should include checkFiles=1 parameter."""
        route = respx.get("http://localhost:32400/library/metadata/12345").mock(
            return_value=Response(200, json=mock_media_item_response)
        )

        async with PlexClient(settings) as client:
            await client.get_metadata("http://localhost:32400", "test-token", "12345")

        assert route.called
        request = route.calls[0].request
        assert "checkFiles=1" in str(request.url)

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_children(self, settings: Settings):
        """Should get child items."""
        children_response = {
            "MediaContainer": {
                "size": 2,
                "Metadata": [
                    {
                        "ratingKey": "100",
                        "key": "/library/metadata/100/children",
                        "type": "season",
                        "title": "Season 1",
                        "index": 1,
                    },
                    {
                        "ratingKey": "101",
                        "key": "/library/metadata/101/children",
                        "type": "season",
                        "title": "Season 2",
                        "index": 2,
                    },
                ],
            }
        }
        respx.get("http://localhost:32400/library/metadata/50/children").mock(
            return_value=Response(200, json=children_response)
        )

        async with PlexClient(settings) as client:
            children = await client.get_children(
                "http://localhost:32400",
                "test-token",
                "50",
            )

        assert len(children) == 2
        assert children[0].is_season
        assert children[1].is_season


class TestTrackUpdates:
    """Tests for track update operations."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_set_audio_stream(self, settings: Settings):
        """Should set audio stream."""
        route = respx.put("http://localhost:32400/library/parts/200").mock(
            return_value=Response(200)
        )

        async with PlexClient(settings) as client:
            await client.set_audio_stream(
                "http://localhost:32400",
                "test-token",
                part_id=200,
                stream_id=302,
            )

        assert route.called
        request = route.calls[0].request
        assert "audioStreamID=302" in str(request.url)
        assert "allParts=1" in str(request.url)

    @pytest.mark.asyncio
    @respx.mock
    async def test_set_subtitle_stream(self, settings: Settings):
        """Should set subtitle stream."""
        route = respx.put("http://localhost:32400/library/parts/200").mock(
            return_value=Response(200)
        )

        async with PlexClient(settings) as client:
            await client.set_subtitle_stream(
                "http://localhost:32400",
                "test-token",
                part_id=200,
                stream_id=401,
            )

        assert route.called
        request = route.calls[0].request
        assert "subtitleStreamID=401" in str(request.url)

    @pytest.mark.asyncio
    @respx.mock
    async def test_set_subtitle_none(self, settings: Settings):
        """Should disable subtitles when stream_id is None."""
        route = respx.put("http://localhost:32400/library/parts/200").mock(
            return_value=Response(200)
        )

        async with PlexClient(settings) as client:
            await client.set_subtitle_stream(
                "http://localhost:32400",
                "test-token",
                part_id=200,
                stream_id=None,
            )

        assert route.called
        request = route.calls[0].request
        assert "subtitleStreamID=0" in str(request.url)


class TestErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_http_error(self, settings: Settings):
        """Should raise PlexClientError on HTTP errors."""
        respx.get("http://localhost:32400/library/sections").mock(
            return_value=Response(500, json={"error": "Internal error"})
        )

        async with PlexClient(settings) as client:
            with pytest.raises(PlexClientError) as exc_info:
                await client.get_libraries("http://localhost:32400", "test-token")

        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_client_must_be_context_manager(self, settings: Settings):
        """Should raise error if not used as context manager."""
        client = PlexClient(settings)

        with pytest.raises(RuntimeError, match="context manager"):
            _ = client.client


class TestPlexHeaders:
    """Tests for proper Plex header handling."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_includes_client_identifier(self, settings: Settings, mock_pin_response: dict):
        """Should include X-Plex-Client-Identifier header."""
        route = respx.post("https://plex.tv/api/v2/pins").mock(
            return_value=Response(200, json=mock_pin_response)
        )

        async with PlexClient(settings) as client:
            await client.create_pin()

        request = route.calls[0].request
        assert request.headers.get("X-Plex-Client-Identifier") == "test-client-id"

    @pytest.mark.asyncio
    @respx.mock
    async def test_includes_token_when_provided(self, settings: Settings, mock_user_response: dict):
        """Should include X-Plex-Token header when token provided."""
        route = respx.get("https://plex.tv/api/v2/user").mock(
            return_value=Response(200, json=mock_user_response)
        )

        async with PlexClient(settings) as client:
            await client.get_user("my-auth-token")

        request = route.calls[0].request
        assert request.headers.get("X-Plex-Token") == "my-auth-token"
