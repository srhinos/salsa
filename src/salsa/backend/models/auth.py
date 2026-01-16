"""Authentication request/response models."""

from pydantic import BaseModel, Field

from salsa.backend.models.plex import PlexHomeUser, PlexUser

# =============================================================================
# =============================================================================


class TokenLoginRequest(BaseModel):
    """Manual token login request."""

    token: str = Field(..., description="Plex authentication token")


class SwitchUserRequest(BaseModel):
    """Request to switch to a managed user."""

    user_uuid: str = Field(..., description="UUID of the user to switch to")
    pin: str | None = Field(default=None, description="PIN if user is protected")


# =============================================================================
# =============================================================================


class PinResponse(BaseModel):
    """PIN creation response for OAuth flow."""

    pin_id: int = Field(..., description="PIN ID for polling")
    code: str = Field(..., description="PIN code to display/use in auth URL")
    auth_url: str = Field(..., description="URL to open for user authentication")
    expires_in: int = Field(..., description="Seconds until PIN expires")


class AuthStatusResponse(BaseModel):
    """Authentication status check response."""

    authenticated: bool
    auth_token: str | None = None


class SessionResponse(BaseModel):
    """Current session information."""

    authenticated: bool
    user: PlexUser | None = None
    server_url: str | None = None
    server_name: str | None = None


class LoginResponse(BaseModel):
    """Successful login response."""

    success: bool = True
    user: PlexUser
    message: str = "Login successful"


class HomeUsersResponse(BaseModel):
    """List of home/managed users."""

    users: list[PlexHomeUser]
    current_user_uuid: str | None = None


class SwitchUserResponse(BaseModel):
    """Response after switching users."""

    success: bool = True
    user: PlexUser
    message: str = "Switched user successfully"


class LogoutResponse(BaseModel):
    """Logout response."""

    success: bool = True
    message: str = "Logged out successfully"


class ErrorResponse(BaseModel):
    """Error response."""

    error: str
    detail: str | None = None
