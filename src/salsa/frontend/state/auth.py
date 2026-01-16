"""Authentication state management."""

import asyncio
import contextlib

import reflex as rx
from pydantic import BaseModel

from salsa.frontend.api import APIError, api


class ServerConnection(BaseModel):
    """A connection option for a Plex server."""

    uri: str = ""
    local: bool = False
    relay: bool = False


class PlexServerInfo(BaseModel):
    """Information about a Plex server."""

    name: str = ""
    machine_identifier: str = ""
    owned: bool = False
    version: str = ""
    connections: list[ServerConnection] = []


class AuthState(rx.State):
    """Authentication and user state."""

    is_authenticated: bool = False
    is_loading: bool = False
    error_message: str = ""

    token: str = ""
    user_id: int = 0
    username: str = ""
    email: str = ""
    thumb: str = ""

    pin_id: int = 0
    pin_code: str = ""
    auth_url: str = ""
    is_polling: bool = False

    is_selecting_server: bool = False
    is_loading_servers: bool = False
    available_servers: list[PlexServerInfo] = []
    custom_server_url: str = ""
    server_selection_error: str = ""
    connection_status: dict[str, str] = {}
    custom_server_status: str = ""
    custom_server_error: str = ""
    custom_server_latency: int = 0

    server_connected: bool = False
    server_url: str = ""
    server_name: str = ""
    server_version: str = ""

    home_users: list[dict] = []
    current_user_uuid: str = ""

    @rx.event
    async def create_pin(self):
        """Start PIN-based authentication."""
        self.is_loading = True
        self.error_message = ""

        try:
            result = await api.create_pin()
            self.pin_id = result["pin_id"]
            self.pin_code = result["code"]
            self.auth_url = result["auth_url"]
            self.is_polling = True

            yield rx.call_script(
                f"window.plexAuthPopup = window.open('{self.auth_url}', 'plexAuth', 'width=600,height=700,left=200,top=100')"
            )

            yield AuthState.poll_for_auth
        except APIError as e:
            self.error_message = f"Failed to create PIN: {e.message}"
        finally:
            self.is_loading = False

    @rx.event(background=True)
    async def poll_for_auth(self):
        """Poll for PIN authentication completion."""
        max_attempts = 120
        attempts = 0

        while attempts < max_attempts:
            async with self:
                if not self.is_polling:
                    return

            try:
                result = await api.check_pin(self.pin_id, self.pin_code)
                if result.get("authenticated"):
                    async with self:
                        await self._complete_auth()
                        yield rx.call_script(
                            "if (window.plexAuthPopup && !window.plexAuthPopup.closed) { window.plexAuthPopup.close(); }"
                        )
                    return
            except APIError:
                pass

            await asyncio.sleep(1)
            attempts += 1

        async with self:
            self.is_polling = False
            self.error_message = "Authentication timed out"

    async def _complete_auth(self):
        """Complete authentication after PIN is authorized."""
        try:
            result = await api.complete_pin(self.pin_id, self.pin_code)
            if result.get("success"):
                user = result.get("user", {})
                self.token = user.get("authToken", "")
                self.user_id = user.get("id", 0)
                self.username = user.get("username", "")
                self.email = user.get("email", "")
                self.thumb = user.get("thumb", "")
                self.is_polling = False

                await self._load_servers()
        except APIError as e:
            self.error_message = f"Failed to complete auth: {e.message}"
            self.is_polling = False

    @rx.event
    async def login_with_token(self, token: str):
        """Login with an existing Plex token."""
        self.is_loading = True
        self.error_message = ""

        try:
            result = await api.login_with_token(token)
            if result.get("success"):
                user = result.get("user", {})
                self.token = user.get("authToken", token)
                self.user_id = user.get("id", 0)
                self.username = user.get("username", "")
                self.email = user.get("email", "")
                self.thumb = user.get("thumb", "")

                await self._load_servers()
        except APIError as e:
            self.error_message = f"Login failed: {e.message}"
        finally:
            self.is_loading = False

    async def _check_server(self):
        """Check server connectivity."""
        try:
            result = await api.get_server_status(self.token)
            self.server_connected = result.get("connected", False)
            self.server_url = result.get("url", "")
            self.server_version = result.get("version", "")
        except APIError:
            self.server_connected = False

    async def _load_servers(self):
        """Load available Plex servers for selection."""
        self.is_loading_servers = True
        self.server_selection_error = ""
        self.connection_status = {}

        try:
            result = await api.get_servers(self.token)
            servers = []
            all_urls = []
            for server_data in result.get("servers", []):
                connections = [
                    ServerConnection(
                        uri=conn.get("uri", ""),
                        local=conn.get("local", False),
                        relay=conn.get("relay", False),
                    )
                    for conn in server_data.get("connections", [])
                ]
                servers.append(
                    PlexServerInfo(
                        name=server_data.get("name", ""),
                        machine_identifier=server_data.get("machine_identifier", ""),
                        owned=server_data.get("owned", False),
                        version=server_data.get("version", ""),
                        connections=connections,
                    )
                )
                all_urls.extend(conn.uri for conn in connections)

            self.available_servers = servers
            self.connection_status = {url: "testing" for url in all_urls}
            self.is_selecting_server = True
        except APIError as e:
            self.server_selection_error = f"Failed to load servers: {e.message}"
            self.is_selecting_server = True
        finally:
            self.is_loading_servers = False

    @rx.event(background=True)
    async def test_all_connections(self):
        """Test all server connections in the background."""
        async with self:
            urls_to_test = list(self.connection_status.keys())
            token = self.token

        for url in urls_to_test:
            try:
                result = await api.test_connection(token, url)
                async with self:
                    if result.get("reachable"):
                        self.connection_status[url] = "ok"
                    else:
                        self.connection_status[url] = "error"
            except APIError:
                async with self:
                    self.connection_status[url] = "error"

    @rx.event
    async def select_server(self, server_url: str):
        """Select and connect to a Plex server."""
        self.is_loading_servers = True
        self.server_selection_error = ""

        try:
            result = await api.select_server(self.token, server_url)
            if result.get("success"):
                self.server_url = result.get("server_url", server_url)
                self.server_name = result.get("server_name", "")
                self.server_version = result.get("version", "")
                self.server_connected = True
                self.is_selecting_server = False
                self.is_authenticated = True
            else:
                self.server_selection_error = result.get("error", "Connection failed")
        except APIError as e:
            self.server_selection_error = f"Failed to connect: {e.message}"
        finally:
            self.is_loading_servers = False

    @rx.event
    async def select_custom_server(self):
        """Use the custom server URL entered by user."""
        if not self.custom_server_url.strip():
            self.server_selection_error = "Please enter a server URL"
            return
        if self.custom_server_status != "valid":
            self.server_selection_error = "Please wait for URL validation"
            return
        yield AuthState.select_server(self.custom_server_url.strip())

    @rx.event
    async def set_custom_server_url(self, url: str):
        """Update the custom server URL input and trigger validation."""
        self.custom_server_url = url
        self.server_selection_error = ""
        self.custom_server_error = ""

        if not url.strip():
            self.custom_server_status = ""
            self.custom_server_latency = 0
            return

        url_stripped = url.strip()
        if not (url_stripped.startswith("http://") or url_stripped.startswith("https://")):
            self.custom_server_status = "invalid"
            self.custom_server_error = "URL must start with http:// or https://"
            return

        self.custom_server_status = "testing"
        yield AuthState.validate_custom_server_url

    @rx.event(background=True)
    async def validate_custom_server_url(self):
        """Test the custom server URL in background."""
        async with self:
            url = self.custom_server_url.strip()
            token = self.token

        if not url:
            return

        try:
            result = await api.test_connection(token, url)
            async with self:
                if self.custom_server_url.strip() != url:
                    return

                if result.get("reachable"):
                    self.custom_server_status = "valid"
                    self.custom_server_latency = result.get("latency_ms", 0)
                    self.custom_server_error = ""
                else:
                    self.custom_server_status = "invalid"
                    self.custom_server_error = result.get("error", "Server not reachable")
                    self.custom_server_latency = 0
        except APIError as e:
            async with self:
                if self.custom_server_url.strip() == url:
                    self.custom_server_status = "invalid"
                    self.custom_server_error = str(e.message)
                    self.custom_server_latency = 0

    @rx.event
    async def logout(self):
        """Logout and clear state."""
        if self.token:
            with contextlib.suppress(APIError):
                await api.logout(self.token)

        self.is_authenticated = False
        self.token = ""
        self.user_id = 0
        self.username = ""
        self.email = ""
        self.thumb = ""
        self.pin_id = 0
        self.pin_code = ""
        self.auth_url = ""
        self.is_polling = False
        self.home_users = []

        self.is_selecting_server = False
        self.is_loading_servers = False
        self.available_servers = []
        self.custom_server_url = ""
        self.server_selection_error = ""
        self.connection_status = {}
        self.custom_server_status = ""
        self.custom_server_error = ""
        self.custom_server_latency = 0
        self.server_connected = False
        self.server_url = ""
        self.server_name = ""
        self.server_version = ""

    @rx.event
    async def cancel_pin_auth(self):
        """Cancel PIN authentication."""
        self.is_polling = False
        self.pin_id = 0
        self.pin_code = ""
        self.auth_url = ""
        yield rx.call_script(
            "if (window.plexAuthPopup && !window.plexAuthPopup.closed) { window.plexAuthPopup.close(); }"
        )

    @rx.event
    async def load_home_users(self):
        """Load home/managed users."""
        if not self.token:
            return

        try:
            result = await api.get_home_users(self.token)
            self.home_users = result.get("users", [])
        except APIError as e:
            self.error_message = f"Failed to load users: {e.message}"

    @rx.event
    async def switch_user(self, user_uuid: str, pin: str = ""):
        """Switch to a different home user."""
        self.is_loading = True
        self.error_message = ""

        try:
            result = await api.switch_user(self.token, user_uuid, pin or None)
            if result.get("success"):
                user = result.get("user", {})
                self.token = user.get("authToken", self.token)
                self.username = user.get("username", "")
                self.current_user_uuid = user_uuid
        except APIError as e:
            self.error_message = f"Failed to switch user: {e.message}"
        finally:
            self.is_loading = False

    @rx.event
    async def check_session(self):
        """Check if there's an existing valid session."""
        if not self.token:
            return

        try:
            result = await api.get_session(self.token)
            if result.get("authenticated"):
                user = result.get("user", {})
                self.user_id = user.get("id", 0)
                self.username = user.get("username", "")
                self.email = user.get("email", "")
                self.thumb = user.get("thumb", "")
                self.is_authenticated = True
                await self._check_server()
        except APIError:
            self.token = ""
            self.is_authenticated = False
