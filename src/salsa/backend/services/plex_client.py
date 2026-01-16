"""Async HTTP client for Plex API communication."""

import asyncio
import warnings
from typing import Any

import httpx
from loguru import logger

from salsa.backend.config import Settings, get_settings
from salsa.backend.models.plex import (
    PlexHomeUser,
    PlexMediaContainer,
    PlexMediaItem,
    PlexPin,
    PlexServer,
    PlexServerIdentity,
    PlexUser,
)
from salsa.backend.utils.headers import PLEX_TV_URL, get_plex_headers

warnings.filterwarnings("ignore", message="Unverified HTTPS request")


class PlexClientError(Exception):
    """Base exception for Plex client errors."""

    def __init__(self, message: str, status_code: int | None = None):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class PlexAuthError(PlexClientError):
    """Authentication error (invalid token, etc.)."""

    pass


class PlexConnectionError(PlexClientError):
    """Connection error (timeout, network issue, etc.)."""

    pass


class PlexClient:
    """
    Async client for Plex API communication.

    Handles both plex.tv API calls and direct Plex Media Server calls.
    """

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "PlexClient":
        """Async context manager entry."""
        self._client = httpx.AsyncClient(
            timeout=self.settings.plex_timeout,
            verify=False,
        )
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Get the HTTP client, ensuring it's initialized."""
        if self._client is None:
            raise RuntimeError("PlexClient must be used as async context manager")
        return self._client

    # =========================================================================
    # =========================================================================

    async def create_pin(self) -> PlexPin:
        """
        Create a new PIN for OAuth authentication.

        Returns:
            PlexPin with id, code, and other details
        """
        headers = get_plex_headers(settings=self.settings)

        try:
            response = await self.client.post(
                f"{PLEX_TV_URL}/pins",
                params={"strong": "true"},
                headers=headers,
            )
            response.raise_for_status()
            return PlexPin.model_validate(response.json())
        except httpx.HTTPStatusError as e:
            raise PlexClientError(f"Failed to create PIN: {e}", e.response.status_code)
        except httpx.RequestError as e:
            raise PlexConnectionError(f"Connection error creating PIN: {e}")

    async def check_pin(self, pin_id: int, code: str) -> PlexPin:
        """
        Check if a PIN has been authenticated.

        Args:
            pin_id: The PIN ID from create_pin
            code: The PIN code from create_pin

        Returns:
            PlexPin with auth_token populated if authenticated
        """
        headers = get_plex_headers(settings=self.settings)

        try:
            response = await self.client.get(
                f"{PLEX_TV_URL}/pins/{pin_id}",
                params={"code": code},
                headers=headers,
            )
            response.raise_for_status()
            return PlexPin.model_validate(response.json())
        except httpx.HTTPStatusError as e:
            raise PlexClientError(f"Failed to check PIN: {e}", e.response.status_code)
        except httpx.RequestError as e:
            raise PlexConnectionError(f"Connection error checking PIN: {e}")

    async def poll_for_auth_token(
        self,
        pin_id: int,
        code: str,
        timeout: float = 120.0,
        interval: float = 1.0,
    ) -> str:
        """
        Poll for authentication token until user completes OAuth flow.

        Args:
            pin_id: The PIN ID from create_pin
            code: The PIN code from create_pin
            timeout: Maximum time to wait (seconds)
            interval: Time between polls (seconds)

        Returns:
            The authentication token

        Raises:
            PlexAuthError: If timeout reached without authentication
        """
        elapsed = 0.0
        while elapsed < timeout:
            pin = await self.check_pin(pin_id, code)
            if pin.auth_token:
                return pin.auth_token
            await asyncio.sleep(interval)
            elapsed += interval

        raise PlexAuthError("Authentication timeout - user did not complete login")

    # =========================================================================
    # =========================================================================

    async def get_user(self, token: str) -> PlexUser:
        """
        Get the current user's information.

        Args:
            token: Plex authentication token

        Returns:
            PlexUser with user details
        """
        headers = get_plex_headers(token=token, settings=self.settings)

        try:
            response = await self.client.get(f"{PLEX_TV_URL}/user", headers=headers)
            response.raise_for_status()
            return PlexUser.model_validate(response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise PlexAuthError("Invalid authentication token")
            raise PlexClientError(f"Failed to get user: {e}", e.response.status_code)
        except httpx.RequestError as e:
            raise PlexConnectionError(f"Connection error getting user: {e}")

    async def get_home_users(self, token: str) -> list[PlexHomeUser]:
        """
        Get list of home/managed users.

        Args:
            token: Plex authentication token (admin)

        Returns:
            List of home users
        """
        headers = get_plex_headers(token=token, settings=self.settings)

        try:
            response = await self.client.get(
                f"{PLEX_TV_URL}/home/users",
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            users = data.get("users", [])
            return [PlexHomeUser.model_validate(u) for u in users]
        except httpx.HTTPStatusError as e:
            raise PlexClientError(f"Failed to get home users: {e}", e.response.status_code)
        except httpx.RequestError as e:
            raise PlexConnectionError(f"Connection error getting home users: {e}")

    async def switch_home_user(self, token: str, user_uuid: str, pin: str | None = None) -> str:
        """
        Switch to a home/managed user.

        Args:
            token: Admin authentication token
            user_uuid: UUID of the user to switch to
            pin: PIN if user is protected

        Returns:
            New authentication token for the switched user
        """
        headers = get_plex_headers(token=token, settings=self.settings)

        try:
            data = {}
            if pin:
                data["pin"] = pin

            response = await self.client.post(
                f"{PLEX_TV_URL}/home/users/{user_uuid}/switch",
                headers=headers,
                data=data if data else None,
            )
            response.raise_for_status()
            result = response.json()
            return result.get("authToken", "")
        except httpx.HTTPStatusError as e:
            raise PlexClientError(f"Failed to switch user: {e}", e.response.status_code)
        except httpx.RequestError as e:
            raise PlexConnectionError(f"Connection error switching user: {e}")

    # =========================================================================
    # =========================================================================

    async def get_resources(self, token: str) -> list[PlexServer]:
        """
        Get available Plex resources (servers, players, etc.).

        Args:
            token: Plex authentication token

        Returns:
            List of Plex resources
        """
        headers = get_plex_headers(token=token, settings=self.settings)

        try:
            response = await self.client.get(
                f"{PLEX_TV_URL}/resources",
                params={"includeRelay": "0"},
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            return [PlexServer.model_validate(r) for r in data]
        except httpx.HTTPStatusError as e:
            raise PlexClientError(f"Failed to get resources: {e}", e.response.status_code)
        except httpx.RequestError as e:
            raise PlexConnectionError(f"Connection error getting resources: {e}")

    async def get_servers(self, token: str) -> list[PlexServer]:
        """
        Get available Plex Media Servers.

        Args:
            token: Plex authentication token

        Returns:
            List of Plex Media Servers only
        """
        resources = await self.get_resources(token)
        return [r for r in resources if r.is_plex_media_server]

    # =========================================================================
    # =========================================================================

    async def check_server_identity(
        self,
        server_url: str,
        token: str,
        timeout: float | None = None,
    ) -> PlexServerIdentity:
        """
        Check server identity/connectivity.

        Args:
            server_url: Base URL of the Plex server
            token: Plex authentication token
            timeout: Override default timeout (uses identity_timeout by default)

        Returns:
            PlexServerIdentity with machine identifier
        """
        headers = get_plex_headers(token=token, settings=self.settings)
        request_timeout = timeout or self.settings.plex_identity_timeout

        try:
            response = await self.client.get(
                f"{server_url}/identity",
                headers=headers,
                timeout=request_timeout,
            )
            response.raise_for_status()
            data = response.json()
            return PlexServerIdentity.model_validate(data["MediaContainer"])
        except httpx.HTTPStatusError as e:
            raise PlexClientError(f"Server identity check failed: {e}", e.response.status_code)
        except httpx.RequestError as e:
            raise PlexConnectionError(f"Cannot connect to server: {e}")

    async def get_libraries(self, server_url: str, token: str) -> list[dict[str, Any]]:
        """
        Get libraries (sections) from a Plex server.

        Args:
            server_url: Base URL of the Plex server
            token: Plex authentication token

        Returns:
            List of library dictionaries
        """
        headers = get_plex_headers(token=token, settings=self.settings)

        try:
            response = await self.client.get(
                f"{server_url}/library/sections",
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("MediaContainer", {}).get("Directory", [])
        except httpx.HTTPStatusError as e:
            raise PlexClientError(f"Failed to get libraries: {e}", e.response.status_code)
        except httpx.RequestError as e:
            raise PlexConnectionError(f"Connection error getting libraries: {e}")

    async def get_library_items(
        self,
        server_url: str,
        token: str,
        library_key: str,
    ) -> PlexMediaContainer:
        """
        Get items in a library.

        Args:
            server_url: Base URL of the Plex server
            token: Plex authentication token
            library_key: Library section key

        Returns:
            PlexMediaContainer with library items
        """
        headers = get_plex_headers(token=token, settings=self.settings)

        try:
            response = await self.client.get(
                f"{server_url}/library/sections/{library_key}/all",
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            return PlexMediaContainer.model_validate(data.get("MediaContainer", {}))
        except httpx.HTTPStatusError as e:
            raise PlexClientError(f"Failed to get library items: {e}", e.response.status_code)
        except httpx.RequestError as e:
            raise PlexConnectionError(f"Connection error getting library items: {e}")

    async def get_metadata(
        self,
        server_url: str,
        token: str,
        rating_key: str,
    ) -> PlexMediaItem | None:
        """
        Get metadata for a specific item.

        Args:
            server_url: Base URL of the Plex server
            token: Plex authentication token
            rating_key: Item's rating key

        Returns:
            PlexMediaItem or None if not found
        """
        headers = get_plex_headers(token=token, settings=self.settings)
        url = f"{server_url}/library/metadata/{rating_key}"
        logger.debug(f"get_metadata: fetching {url}")

        try:
            response = await self.client.get(
                url,
                headers=headers,
                params={
                    "checkFiles": "1",
                    "includeElements": "Stream",
                },
            )
            response.raise_for_status()
            data = response.json()
            container = PlexMediaContainer.model_validate(data.get("MediaContainer", {}))
            return container.metadata[0] if container.metadata else None
        except httpx.HTTPStatusError as e:
            logger.error(f"get_metadata HTTP error: {e.response.status_code} for {url}")
            raise PlexClientError(f"Failed to get metadata: {e}", e.response.status_code)
        except httpx.RequestError as e:
            logger.error(f"get_metadata connection error for {url}: {e}")
            raise PlexConnectionError(f"Connection error getting metadata: {e}")

    async def get_children(
        self,
        server_url: str,
        token: str,
        rating_key: str,
    ) -> list[PlexMediaItem]:
        """
        Get children of an item (seasons of show, episodes of season).

        Args:
            server_url: Base URL of the Plex server
            token: Plex authentication token
            rating_key: Parent item's rating key

        Returns:
            List of child PlexMediaItems
        """
        headers = get_plex_headers(token=token, settings=self.settings)

        try:
            response = await self.client.get(
                f"{server_url}/library/metadata/{rating_key}/children",
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            container = PlexMediaContainer.model_validate(data.get("MediaContainer", {}))
            return container.metadata
        except httpx.HTTPStatusError as e:
            raise PlexClientError(f"Failed to get children: {e}", e.response.status_code)
        except httpx.RequestError as e:
            raise PlexConnectionError(f"Connection error getting children: {e}")

    # =========================================================================
    # =========================================================================

    async def set_audio_stream(
        self,
        server_url: str,
        token: str,
        part_id: int,
        stream_id: int,
    ) -> None:
        """
        Set the default audio stream for a media part.

        Args:
            server_url: Base URL of the Plex server
            token: Plex authentication token
            part_id: Media part ID
            stream_id: Audio stream ID to set as default
        """
        headers = get_plex_headers(token=token, settings=self.settings)

        try:
            response = await self.client.put(
                f"{server_url}/library/parts/{part_id}",
                params={"audioStreamID": stream_id, "allParts": "1"},
                headers=headers,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise PlexClientError(f"Failed to set audio stream: {e}", e.response.status_code)
        except httpx.RequestError as e:
            raise PlexConnectionError(f"Connection error setting audio stream: {e}")

    async def set_subtitle_stream(
        self,
        server_url: str,
        token: str,
        part_id: int,
        stream_id: int | None,
    ) -> None:
        """
        Set the default subtitle stream for a media part.

        Args:
            server_url: Base URL of the Plex server
            token: Plex authentication token
            part_id: Media part ID
            stream_id: Subtitle stream ID (0 or None for no subtitles)
        """
        headers = get_plex_headers(token=token, settings=self.settings)

        subtitle_id = stream_id if stream_id else 0

        try:
            response = await self.client.put(
                f"{server_url}/library/parts/{part_id}",
                params={"subtitleStreamID": subtitle_id, "allParts": "1"},
                headers=headers,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise PlexClientError(f"Failed to set subtitle stream: {e}", e.response.status_code)
        except httpx.RequestError as e:
            raise PlexConnectionError(f"Connection error setting subtitle stream: {e}")


# =============================================================================
# =============================================================================


async def get_plex_client() -> PlexClient:
    """
    Get a PlexClient instance.

    Note: Caller is responsible for using as context manager or closing.
    """
    return PlexClient()
