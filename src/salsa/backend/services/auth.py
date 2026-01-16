"""Authentication service for session management."""

from dataclasses import dataclass
from typing import Any

from salsa.backend.config import Settings, get_settings
from salsa.backend.models.plex import PlexUser
from salsa.backend.services.plex_client import PlexAuthError, PlexClient


@dataclass
class Session:
    """User session data."""

    token: str
    user: PlexUser
    admin_token: str | None = None
    server_url: str | None = None
    server_name: str | None = None
    server_machine_id: str | None = None
    is_managed_user: bool = False


class SessionStore:
    """
    In-memory session storage.

    Note: Sessions are lost on restart by design (unless SECRET_KEY is set,
    but even then we use in-memory storage for simplicity).
    """

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def create(self, session_id: str, session: Session) -> None:
        """Store a new session."""
        self._sessions[session_id] = session

    def get(self, session_id: str) -> Session | None:
        """Retrieve a session by ID."""
        return self._sessions.get(session_id)

    def update(self, session_id: str, **kwargs: Any) -> bool:
        """Update session fields."""
        session = self._sessions.get(session_id)
        if not session:
            return False
        for key, value in kwargs.items():
            if hasattr(session, key):
                setattr(session, key, value)
        return True

    def delete(self, session_id: str) -> bool:
        """Delete a session."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def clear(self) -> None:
        """Clear all sessions."""
        self._sessions.clear()


_session_store = SessionStore()


def get_session_store() -> SessionStore:
    """Get the global session store."""
    return _session_store


class AuthService:
    """
    Authentication service handling login flows and session management.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        session_store: SessionStore | None = None,
    ):
        self.settings = settings or get_settings()
        self.session_store = session_store or get_session_store()

    def _generate_session_id(self, token: str) -> str:
        """Generate a session ID from the token."""
        import hashlib

        return hashlib.sha256(f"{token}{self.settings.secret_key}".encode()).hexdigest()[:32]

    async def create_pin(self) -> dict[str, Any]:
        """
        Create a new PIN for OAuth authentication.

        Returns:
            Dict with pin_id, code, auth_url, expires_in
        """
        async with PlexClient(self.settings) as client:
            pin = await client.create_pin()

        client_id = self.settings.get_client_id()
        auth_url = (
            f"https://app.plex.tv/auth#?"
            f"clientID={client_id}&"
            f"code={pin.code}&"
            f"context%5Bdevice%5D%5Bproduct%5D=SALSA"
        )

        return {
            "pin_id": pin.id,
            "code": pin.code,
            "auth_url": auth_url,
            "expires_in": pin.expires_in,
        }

    async def check_pin(self, pin_id: int, code: str) -> dict[str, Any]:
        """
        Check if a PIN has been authenticated.

        Returns:
            Dict with authenticated status and token if available
        """
        async with PlexClient(self.settings) as client:
            pin = await client.check_pin(pin_id, code)

        return {
            "authenticated": pin.auth_token is not None,
            "auth_token": pin.auth_token,
        }

    async def login_with_token(self, token: str) -> Session:
        """
        Login with a Plex token (either from PIN flow or manual entry).

        Args:
            token: Plex authentication token

        Returns:
            Session object

        Raises:
            PlexAuthError: If token is invalid
        """
        async with PlexClient(self.settings) as client:
            user = await client.get_user(token)

        session_id = self._generate_session_id(token)
        session = Session(token=token, user=user)
        self.session_store.create(session_id, session)

        return session

    async def validate_token(self, token: str) -> PlexUser:
        """
        Validate a token and return user info.

        Args:
            token: Plex authentication token

        Returns:
            PlexUser if valid

        Raises:
            PlexAuthError: If token is invalid
        """
        async with PlexClient(self.settings) as client:
            return await client.get_user(token)

    def get_session(self, token: str) -> Session | None:
        """
        Get an existing session by token.

        Args:
            token: Plex authentication token

        Returns:
            Session if found, None otherwise
        """
        session_id = self._generate_session_id(token)
        return self.session_store.get(session_id)

    def get_or_create_session(self, token: str, user: PlexUser) -> Session:
        """
        Get existing session or create a new one.

        Args:
            token: Plex authentication token
            user: PlexUser object

        Returns:
            Session object
        """
        session = self.get_session(token)
        if session:
            return session

        session_id = self._generate_session_id(token)
        session = Session(token=token, user=user)
        self.session_store.create(session_id, session)
        return session

    async def get_home_users(self, token: str) -> list[dict[str, Any]]:
        """
        Get list of home/managed users.

        Args:
            token: Admin authentication token

        Returns:
            List of home user dicts
        """
        async with PlexClient(self.settings) as client:
            users = await client.get_home_users(token)
            return [u.model_dump() for u in users]

    async def switch_user(
        self,
        admin_token: str,
        user_uuid: str,
        pin: str | None = None,
    ) -> Session:
        """
        Switch to a managed user.

        Args:
            admin_token: Admin authentication token
            user_uuid: UUID of user to switch to
            pin: PIN if user is protected

        Returns:
            New session for the switched user
        """
        async with PlexClient(self.settings) as client:
            new_token = await client.switch_home_user(admin_token, user_uuid, pin)
            if not new_token:
                raise PlexAuthError("Failed to get token for switched user")

            user = await client.get_user(new_token)

        session_id = self._generate_session_id(new_token)
        session = Session(
            token=new_token,
            user=user,
            admin_token=admin_token,
            is_managed_user=True,
        )
        self.session_store.create(session_id, session)

        return session

    def logout(self, token: str) -> bool:
        """
        Logout and clear session.

        Args:
            token: Plex authentication token

        Returns:
            True if session was cleared, False if not found
        """
        session_id = self._generate_session_id(token)
        return self.session_store.delete(session_id)

    def update_session_server(
        self,
        token: str,
        server_url: str,
        server_name: str,
        machine_id: str,
    ) -> bool:
        """
        Update session with connected server info.

        Args:
            token: Plex authentication token
            server_url: Connected server URL
            server_name: Server display name
            machine_id: Server machine identifier

        Returns:
            True if updated, False if session not found
        """
        session_id = self._generate_session_id(token)
        return self.session_store.update(
            session_id,
            server_url=server_url,
            server_name=server_name,
            server_machine_id=machine_id,
        )


def get_auth_service() -> AuthService:
    """Get an AuthService instance for dependency injection."""
    return AuthService()
