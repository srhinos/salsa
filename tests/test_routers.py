"""Integration tests for API routers using real Plex fixture data."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import respx
from fastapi.testclient import TestClient
from httpx import Response

from salsa.backend.config import Settings
from salsa.backend.main import create_app
from salsa.backend.services.auth import AuthService, Session

# =============================================================================
# =============================================================================

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "plex_responses"


def load_fixture(name: str) -> dict:
    """Load a JSON fixture file."""
    with open(FIXTURES_DIR / f"{name}.json") as f:
        return json.load(f)


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
def mock_user():
    """Create a mock user."""
    from salsa.backend.models.plex import PlexUser
    return PlexUser(
        id=1,
        uuid="test-user-uuid",
        username="testuser",
        title="Test User",
        email="test@example.com",
        thumb=None,
    )


@pytest.fixture
def mock_session(mock_user):
    """Create a mock session."""
    return Session(
        token="test-token",
        user=mock_user,
        server_url="http://localhost:32400",
        server_name="Test Server",
    )


@pytest.fixture
def app(settings, mock_session):
    """Create test app with mocked auth dependencies."""
    application = create_app()

    mock_auth_service = MagicMock(spec=AuthService)
    mock_auth_service.get_session.return_value = mock_session

    from salsa.backend.services.auth import get_auth_service
    application.dependency_overrides[get_auth_service] = lambda: mock_auth_service

    return application


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Create auth headers."""
    return {"X-Plex-Token": "test-token"}


# =============================================================================
# =============================================================================


@pytest.fixture
def libraries_response():
    """Load libraries fixture."""
    return load_fixture("libraries")


@pytest.fixture
def library_items_response():
    """Load library items (TV Shows) fixture."""
    return load_fixture("library_1_items")


@pytest.fixture
def episode_metadata():
    """Load episode metadata fixture with streams."""
    return load_fixture("episode_39066_metadata")


@pytest.fixture
def seasons_response():
    """Load seasons fixture."""
    return load_fixture("show_39040_seasons")


@pytest.fixture
def show_metadata():
    """Load show metadata fixture."""
    return load_fixture("show_39040_metadata")


# =============================================================================
# =============================================================================


class TestLibrariesRouter:
    """Tests for /api/libraries endpoints."""

    @respx.mock
    def test_list_libraries(self, client, auth_headers, libraries_response):
        """Should list available libraries."""
        respx.get("http://localhost:32400/library/sections").mock(
            return_value=Response(200, json=libraries_response)
        )

        response = client.get("/api/libraries", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "libraries" in data
        assert "total" in data
        assert data["total"] == 2

        library_types = {lib["type"] for lib in data["libraries"]}
        assert "movie" in library_types
        assert "show" in library_types

    @respx.mock
    def test_list_libraries_video_only_filter(self, client, auth_headers, libraries_response):
        """Should filter to video libraries only by default."""
        modified_response = dict(libraries_response)
        modified_response["MediaContainer"] = dict(libraries_response["MediaContainer"])
        modified_response["MediaContainer"]["Directory"] = libraries_response["MediaContainer"]["Directory"].copy()
        modified_response["MediaContainer"]["Directory"].append({
            "key": "3",
            "title": "Music",
            "type": "artist",
            "uuid": "music-uuid",
        })

        respx.get("http://localhost:32400/library/sections").mock(
            return_value=Response(200, json=modified_response)
        )

        response = client.get("/api/libraries", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        library_types = {lib["type"] for lib in data["libraries"]}
        assert "artist" not in library_types

    @respx.mock
    def test_get_library(self, client, auth_headers, libraries_response):
        """Should get a specific library by key."""
        respx.get("http://localhost:32400/library/sections").mock(
            return_value=Response(200, json=libraries_response)
        )

        response = client.get("/api/libraries/1", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["key"] == "1"
        assert data["title"] == "TV Shows"
        assert data["type"] == "show"

    @respx.mock
    def test_get_library_not_found(self, client, auth_headers, libraries_response):
        """Should return 404 for non-existent library."""
        respx.get("http://localhost:32400/library/sections").mock(
            return_value=Response(200, json=libraries_response)
        )

        response = client.get("/api/libraries/999", headers=auth_headers)

        assert response.status_code == 404

    @respx.mock
    def test_list_library_items(self, client, auth_headers, libraries_response, library_items_response):
        """Should list items in a library."""
        respx.get("http://localhost:32400/library/sections").mock(
            return_value=Response(200, json=libraries_response)
        )
        respx.get("http://localhost:32400/library/sections/1/all").mock(
            return_value=Response(200, json=library_items_response)
        )

        response = client.get("/api/libraries/1/items", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert data["total"] == 3
        assert data["library_key"] == "1"

        first_item = data["items"][0]
        assert first_item["rating_key"] == "1001"
        assert first_item["title"] == "Test Anime Show"
        assert first_item["type"] == "show"

    def test_list_libraries_requires_auth(self, client):
        """Should require authentication."""
        response = client.get("/api/libraries")
        assert response.status_code == 401


# =============================================================================
# =============================================================================


class TestMediaRouter:
    """Tests for /api/media endpoints."""

    @respx.mock
    def test_get_media_item(self, client, auth_headers, episode_metadata):
        """Should get media item metadata."""
        respx.get("http://localhost:32400/library/metadata/39066").mock(
            return_value=Response(200, json=episode_metadata)
        )

        response = client.get("/api/media/39066", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["rating_key"] == "39066"
        assert data["title"] == "Test Episode One"
        assert data["type"] == "episode"
        assert data["has_streams"] is True

    @respx.mock
    def test_get_media_item_not_found(self, client, auth_headers):
        """Should return 404 for non-existent item."""
        respx.get("http://localhost:32400/library/metadata/99999").mock(
            return_value=Response(200, json={"MediaContainer": {"size": 0, "Metadata": []}})
        )

        response = client.get("/api/media/99999", headers=auth_headers)

        assert response.status_code == 404

    @respx.mock
    def test_get_children_seasons(self, client, auth_headers, show_metadata, seasons_response):
        """Should get children (seasons) of a show."""
        respx.get("http://localhost:32400/library/metadata/39040").mock(
            return_value=Response(200, json=show_metadata)
        )
        respx.get("http://localhost:32400/library/metadata/39040/children").mock(
            return_value=Response(200, json=seasons_response)
        )

        response = client.get("/api/media/39040/children", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["parent_rating_key"] == "39040"
        assert data["total"] == 2

        season_titles = [c["title"] for c in data["children"]]
        assert "Season 1" in season_titles
        assert "Season 2" in season_titles

    @respx.mock
    def test_get_streams(self, client, auth_headers, episode_metadata):
        """Should get audio and subtitle streams for an episode."""
        respx.get("http://localhost:32400/library/metadata/39066").mock(
            return_value=Response(200, json=episode_metadata)
        )

        response = client.get("/api/media/39066/streams", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["rating_key"] == "39066"
        assert data["part_id"] == 60039

        audio_streams = data["audio_streams"]
        assert len(audio_streams) == 2
        audio_langs = {s["language"] for s in audio_streams}
        assert "English" in audio_langs
        assert "Japanese" in audio_langs

        subtitle_streams = data["subtitle_streams"]
        assert len(subtitle_streams) == 4

    @respx.mock
    def test_get_streams_selected_state(self, client, auth_headers, episode_metadata):
        """Should correctly identify selected streams."""
        respx.get("http://localhost:32400/library/metadata/39066").mock(
            return_value=Response(200, json=episode_metadata)
        )

        response = client.get("/api/media/39066/streams", headers=auth_headers)

        data = response.json()

        selected_audio = [s for s in data["audio_streams"] if s["selected"]]
        assert len(selected_audio) == 1
        assert selected_audio[0]["language_code"] == "jpn"

        selected_sub = [s for s in data["subtitle_streams"] if s["selected"]]
        assert len(selected_sub) == 1
        assert selected_sub[0]["language_code"] == "eng"


# =============================================================================
# =============================================================================


class TestTracksRouter:
    """Tests for /api/tracks endpoints."""

    @respx.mock
    def test_set_audio_track(self, client, auth_headers):
        """Should set audio track for an item."""
        respx.put("http://localhost:32400/library/parts/60039").mock(
            return_value=Response(200)
        )

        response = client.put(
            "/api/tracks/audio",
            headers=auth_headers,
            json={
                "part_id": 60039,
                "stream_id": 493670,
                "stream_type": "audio",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "updated" in data["message"].lower()

    def test_set_audio_track_wrong_stream_type(self, client, auth_headers):
        """Should reject audio endpoint with subtitle stream type."""
        response = client.put(
            "/api/tracks/audio",
            headers=auth_headers,
            json={
                "part_id": 60039,
                "stream_id": 493671,
                "stream_type": "subtitle",
            },
        )

        assert response.status_code == 400

    @respx.mock
    def test_set_subtitle_track(self, client, auth_headers):
        """Should set subtitle track for an item."""
        respx.put("http://localhost:32400/library/parts/60039").mock(
            return_value=Response(200)
        )

        response = client.put(
            "/api/tracks/subtitle",
            headers=auth_headers,
            json={
                "part_id": 60039,
                "stream_id": 493671,
                "stream_type": "subtitle",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @respx.mock
    def test_disable_subtitles(self, client, auth_headers):
        """Should disable subtitles when stream_id is 0."""
        route = respx.put("http://localhost:32400/library/parts/60039").mock(
            return_value=Response(200)
        )

        response = client.put(
            "/api/tracks/subtitle",
            headers=auth_headers,
            json={
                "part_id": 60039,
                "stream_id": 0,
                "stream_type": "subtitle",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "disabled" in data["message"].lower()

        request = route.calls[0].request
        assert "subtitleStreamID=0" in str(request.url)


# =============================================================================
# =============================================================================


class TestAuthRouter:
    """Tests for /api/auth endpoints."""

    def test_get_session_authenticated(self, client, auth_headers, mock_session):
        """Should return session for authenticated user."""
        response = client.get("/api/auth/session", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["authenticated"] is True
        assert data["user"]["username"] == "testuser"
        assert data["server_url"] == "http://localhost:32400"

    def test_get_session_requires_auth(self, client):
        """Should require authentication."""
        response = client.get("/api/auth/session")
        assert response.status_code == 401

    def test_logout(self, client, auth_headers):
        """Should logout and clear session."""
        response = client.post("/api/auth/logout", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


# =============================================================================
# =============================================================================


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    def test_health_endpoint(self, client):
        """Should return healthy status."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_ready_endpoint(self, client):
        """Should return ready status."""
        response = client.get("/ready")
        assert response.status_code == 200
        assert response.json()["status"] == "ready"

    def test_root_endpoint(self, client):
        """Should return app info."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "app" in data
        assert "version" in data


# =============================================================================
# =============================================================================


class TestErrorHandling:
    """Tests for error handling scenarios."""

    @respx.mock
    def test_plex_server_error(self, client, auth_headers):
        """Should handle Plex server errors gracefully."""
        respx.get("http://localhost:32400/library/sections").mock(
            return_value=Response(500, json={"error": "Internal server error"})
        )

        response = client.get("/api/libraries", headers=auth_headers)

        assert response.status_code == 500
