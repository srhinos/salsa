"""API client for communicating with the SALSA backend."""

from typing import Any

import httpx

from salsa.backend.config import get_settings


class APIError(Exception):
    """API request error."""

    def __init__(self, message: str, status_code: int | None = None):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class APIClient:
    """HTTP client for SALSA backend API."""

    def __init__(self, base_url: str | None = None):
        if base_url is None:
            settings = get_settings()
            base_url = settings.backend_url
        self.base_url = base_url.rstrip("/")

    def _get_headers(self, token: str | None = None) -> dict[str, str]:
        """Build request headers."""
        headers = {"Content-Type": "application/json"}
        if token:
            headers["X-Plex-Token"] = token
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        token: str | None = None,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an async HTTP request."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method=method,
                url=f"{self.base_url}{path}",
                headers=self._get_headers(token),
                params=params,
                json=json,
            )

            if response.status_code >= 400:
                try:
                    error = response.json()
                    message = error.get("detail", str(error))
                except Exception:
                    message = response.text or f"HTTP {response.status_code}"
                raise APIError(message, response.status_code)

            return response.json()

    # =========================================================================
    # =========================================================================

    async def create_pin(self) -> dict[str, Any]:
        """Create a new PIN for OAuth authentication."""
        return await self._request("POST", "/api/auth/pin")

    async def check_pin(self, pin_id: int, code: str) -> dict[str, Any]:
        """Check if a PIN has been authenticated."""
        return await self._request("GET", f"/api/auth/pin/{pin_id}", params={"code": code})

    async def complete_pin(self, pin_id: int, code: str) -> dict[str, Any]:
        """Complete PIN authentication and create session."""
        return await self._request(
            "POST", f"/api/auth/pin/{pin_id}/complete", params={"code": code}
        )

    async def login_with_token(self, token: str) -> dict[str, Any]:
        """Login with an existing Plex token."""
        return await self._request("POST", "/api/auth/token", json={"token": token})

    async def get_session(self, token: str) -> dict[str, Any]:
        """Get current session info."""
        return await self._request("GET", "/api/auth/session", token=token)

    async def get_user(self, token: str) -> dict[str, Any]:
        """Get current user info."""
        return await self._request("GET", "/api/auth/user", token=token)

    async def logout(self, token: str) -> dict[str, Any]:
        """Logout and destroy session."""
        return await self._request("POST", "/api/auth/logout", token=token)

    async def get_home_users(self, token: str) -> dict[str, Any]:
        """Get list of home/managed users."""
        return await self._request("GET", "/api/auth/home-users", token=token)

    async def switch_user(
        self, token: str, user_uuid: str, pin: str | None = None
    ) -> dict[str, Any]:
        """Switch to a different home user."""
        data = {"user_uuid": user_uuid}
        if pin:
            data["pin"] = pin
        return await self._request("POST", "/api/auth/switch-user", token=token, json=data)

    # =========================================================================
    # =========================================================================

    async def get_server_config(self) -> dict[str, Any]:
        """Get server configuration."""
        return await self._request("GET", "/api/server/config")

    async def get_server_status(self, token: str) -> dict[str, Any]:
        """Check server connectivity."""
        return await self._request("GET", "/api/server/status", token=token)

    async def get_servers(self, token: str) -> dict[str, Any]:
        """Get list of available Plex servers."""
        return await self._request("GET", "/api/server/list", token=token)

    async def select_server(self, token: str, server_url: str) -> dict[str, Any]:
        """Select and connect to a Plex server."""
        return await self._request(
            "POST", "/api/server/select", token=token, json={"server_url": server_url}
        )

    async def test_connection(self, token: str, url: str) -> dict[str, Any]:
        """Test if a server URL is reachable."""
        return await self._request("POST", "/api/server/test", token=token, json={"url": url})

    # =========================================================================
    # =========================================================================

    async def get_libraries(self, token: str) -> dict[str, Any]:
        """Get all libraries."""
        return await self._request("GET", "/api/libraries", token=token)

    async def get_library(self, token: str, library_key: str) -> dict[str, Any]:
        """Get library details."""
        return await self._request("GET", f"/api/libraries/{library_key}", token=token)

    async def get_library_items(self, token: str, library_key: str) -> dict[str, Any]:
        """Get items in a library."""
        return await self._request("GET", f"/api/libraries/{library_key}/items", token=token)

    # =========================================================================
    # =========================================================================

    async def get_media_item(self, token: str, rating_key: str) -> dict[str, Any]:
        """Get media item metadata."""
        return await self._request("GET", f"/api/media/{rating_key}", token=token)

    async def get_children(self, token: str, rating_key: str) -> dict[str, Any]:
        """Get children of a media item (seasons/episodes)."""
        return await self._request("GET", f"/api/media/{rating_key}/children", token=token)

    async def get_streams(self, token: str, rating_key: str) -> dict[str, Any]:
        """Get audio/subtitle streams for a media item."""
        return await self._request("GET", f"/api/media/{rating_key}/streams", token=token)

    async def get_stream_summary(self, token: str, rating_key: str) -> dict[str, Any]:
        """Get aggregated stream summary for a show or season."""
        return await self._request("GET", f"/api/media/{rating_key}/stream-summary", token=token)

    # =========================================================================
    # =========================================================================

    async def set_audio_track(self, token: str, part_id: int, stream_id: int) -> dict[str, Any]:
        """Set audio track for a media item."""
        return await self._request(
            "PUT",
            "/api/tracks/audio",
            token=token,
            json={"part_id": part_id, "stream_id": stream_id, "stream_type": "audio"},
        )

    async def set_subtitle_track(self, token: str, part_id: int, stream_id: int) -> dict[str, Any]:
        """Set subtitle track for a media item (0 to disable)."""
        return await self._request(
            "PUT",
            "/api/tracks/subtitle",
            token=token,
            json={"part_id": part_id, "stream_id": stream_id, "stream_type": "subtitle"},
        )

    async def start_batch(
        self,
        token: str,
        scope: str,
        stream_type: str,
        target_rating_key: str,
        source_stream_id: int,
        source_rating_key: str | None = None,
        keyword_filter: str | None = None,
        set_none: bool = False,
    ) -> dict[str, Any]:
        """Start a batch update operation."""
        data = {
            "scope": scope,
            "stream_type": stream_type,
            "target_rating_key": target_rating_key,
            "source_stream_id": source_stream_id,
            "set_none": set_none,
        }
        if source_rating_key:
            data["source_rating_key"] = source_rating_key
        if keyword_filter:
            data["keyword_filter"] = keyword_filter
        return await self._request("POST", "/api/tracks/batch", token=token, json=data)

    async def get_batch_progress(self, token: str, batch_id: str) -> dict[str, Any]:
        """Get batch operation progress."""
        return await self._request("GET", f"/api/tracks/batch/{batch_id}", token=token)

    async def get_batch_result(self, token: str, batch_id: str) -> dict[str, Any]:
        """Get batch operation result."""
        return await self._request("GET", f"/api/tracks/batch/{batch_id}/result", token=token)


api = APIClient()
