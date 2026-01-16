"""Authentication API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status

from salsa.backend.models.auth import (
    AuthStatusResponse,
    ErrorResponse,
    HomeUsersResponse,
    LoginResponse,
    LogoutResponse,
    PinResponse,
    SessionResponse,
    SwitchUserRequest,
    SwitchUserResponse,
    TokenLoginRequest,
)
from salsa.backend.services.auth import AuthService, get_auth_service
from salsa.backend.services.plex_client import PlexAuthError, PlexClientError

router = APIRouter()


def get_token_from_header(
    x_plex_token: Annotated[str | None, Header()] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    """
    Extract token from request headers.

    Supports:
    - X-Plex-Token header
    - Authorization: Bearer <token> header
    """
    if x_plex_token:
        return x_plex_token

    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1]

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing authentication token",
    )


# =============================================================================
# =============================================================================


@router.post(
    "/pin",
    response_model=PinResponse,
    responses={500: {"model": ErrorResponse}},
    summary="Create authentication PIN",
    description="Generate a PIN for the Plex OAuth flow. Returns a PIN code and auth URL.",
)
async def create_pin(
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> PinResponse:
    """Create a new PIN for OAuth authentication."""
    try:
        result = await auth_service.create_pin()
        return PinResponse(**result)
    except PlexClientError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/pin/{pin_id}",
    response_model=AuthStatusResponse,
    responses={500: {"model": ErrorResponse}},
    summary="Check PIN status",
    description="Check if user has completed authentication for the given PIN.",
)
async def check_pin(
    pin_id: int,
    code: str,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthStatusResponse:
    """Check if a PIN has been authenticated."""
    try:
        result = await auth_service.check_pin(pin_id, code)
        return AuthStatusResponse(**result)
    except PlexClientError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/pin/{pin_id}/complete",
    response_model=LoginResponse,
    responses={
        401: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
    summary="Complete PIN authentication",
    description="Complete login after PIN has been authenticated. Creates a session.",
)
async def complete_pin_login(
    pin_id: int,
    code: str,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> LoginResponse:
    """Complete login after PIN authentication."""
    try:
        result = await auth_service.check_pin(pin_id, code)
        if not result["authenticated"] or not result["auth_token"]:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="PIN not yet authenticated",
            )

        session = await auth_service.login_with_token(result["auth_token"])
        return LoginResponse(user=session.user)

    except PlexAuthError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    except PlexClientError as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# =============================================================================


@router.post(
    "/token",
    response_model=LoginResponse,
    responses={
        401: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
    summary="Login with token",
    description="Login using a Plex authentication token directly.",
)
async def login_with_token(
    request: TokenLoginRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> LoginResponse:
    """Login with a Plex token."""
    try:
        session = await auth_service.login_with_token(request.token)
        return LoginResponse(user=session.user)
    except PlexAuthError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    except PlexClientError as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# =============================================================================


@router.get(
    "/session",
    response_model=SessionResponse,
    responses={401: {"model": ErrorResponse}},
    summary="Get current session",
    description="Get information about the current authenticated session.",
)
async def get_session(
    token: Annotated[str, Depends(get_token_from_header)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> SessionResponse:
    """Get current session information."""
    session = auth_service.get_session(token)

    if session:
        return SessionResponse(
            authenticated=True,
            user=session.user,
            server_url=session.server_url,
            server_name=session.server_name,
        )

    try:
        user = await auth_service.validate_token(token)
        auth_service.get_or_create_session(token, user)
        return SessionResponse(authenticated=True, user=user)
    except PlexAuthError:
        return SessionResponse(authenticated=False)


@router.get(
    "/user",
    response_model=LoginResponse,
    responses={
        401: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
    summary="Get current user",
    description="Get the current authenticated user's information.",
)
async def get_user(
    token: Annotated[str, Depends(get_token_from_header)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> LoginResponse:
    """Get current user information."""
    try:
        user = await auth_service.validate_token(token)
        return LoginResponse(user=user, message="User retrieved successfully")
    except PlexAuthError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    except PlexClientError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/logout",
    response_model=LogoutResponse,
    summary="Logout",
    description="Clear the current session.",
)
async def logout(
    token: Annotated[str, Depends(get_token_from_header)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> LogoutResponse:
    """Logout and clear session."""
    auth_service.logout(token)
    return LogoutResponse()


# =============================================================================
# =============================================================================


@router.get(
    "/home-users",
    response_model=HomeUsersResponse,
    responses={
        401: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
    summary="Get home users",
    description="Get list of home/managed users for the current account.",
)
async def get_home_users(
    token: Annotated[str, Depends(get_token_from_header)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> HomeUsersResponse:
    """Get list of home/managed users."""
    try:
        session = auth_service.get_session(token)
        current_uuid = session.user.uuid if session else None

        users_data = await auth_service.get_home_users(token)
        from salsa.backend.models.plex import PlexHomeUser

        users = [PlexHomeUser.model_validate(u) for u in users_data]

        return HomeUsersResponse(users=users, current_user_uuid=current_uuid)
    except PlexAuthError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    except PlexClientError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/switch-user",
    response_model=SwitchUserResponse,
    responses={
        401: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
    summary="Switch user",
    description="Switch to a different home/managed user.",
)
async def switch_user(
    request: SwitchUserRequest,
    token: Annotated[str, Depends(get_token_from_header)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> SwitchUserResponse:
    """Switch to a managed user."""
    try:
        session = await auth_service.switch_user(
            admin_token=token,
            user_uuid=request.user_uuid,
            pin=request.pin,
        )
        return SwitchUserResponse(user=session.user)
    except PlexAuthError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    except PlexClientError as e:
        raise HTTPException(status_code=500, detail=str(e))
