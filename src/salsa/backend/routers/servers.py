"""Server status and connection API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from salsa.backend.config import Settings, get_settings
from salsa.backend.models.auth import ErrorResponse
from salsa.backend.routers.auth import get_token_from_header
from salsa.backend.services.auth import AuthService, get_auth_service
from salsa.backend.services.plex_client import (
    PlexClient,
    PlexClientError,
    PlexConnectionError,
)

router = APIRouter()


# =============================================================================
# =============================================================================


class ServerConfigResponse(BaseModel):
    """Server configuration (from environment)."""

    url: str = Field(..., description="Configured Plex server URL")
    host: str = Field(..., description="Configured host")
    port: int = Field(..., description="Configured port")
    protocol: str = Field(..., description="Configured protocol")


class ServerStatusResponse(BaseModel):
    """Server connection status."""

    connected: bool = Field(..., description="Whether server is reachable")
    url: str = Field(..., description="Server URL")
    machine_identifier: str | None = Field(default=None, description="Server machine ID")
    version: str | None = Field(default=None, description="Server version")
    error: str | None = Field(default=None, description="Error message if not connected")


class ServerIdentityResponse(BaseModel):
    """Server identity information."""

    machine_identifier: str = Field(..., description="Unique server identifier")
    version: str | None = Field(default=None, description="Plex Media Server version")
    url: str = Field(..., description="Server URL")


class ConnectionInfo(BaseModel):
    """Server connection option."""

    uri: str = Field(..., description="Full connection URI")
    local: bool = Field(..., description="Whether this is a local connection")
    relay: bool = Field(default=False, description="Whether this is a relay connection")


class ServerInfo(BaseModel):
    """Information about an available Plex server."""

    name: str = Field(..., description="Server name")
    machine_identifier: str = Field(..., description="Unique server identifier")
    owned: bool = Field(..., description="Whether the user owns this server")
    version: str = Field(..., description="Server version")
    connections: list[ConnectionInfo] = Field(..., description="Available connections")


class ServersListResponse(BaseModel):
    """List of available Plex servers."""

    servers: list[ServerInfo] = Field(..., description="Available servers")


class ServerSelectRequest(BaseModel):
    """Request to select/connect to a server."""

    server_url: str = Field(..., description="Server URL to connect to")


class ServerSelectResponse(BaseModel):
    """Response after selecting a server."""

    success: bool = Field(..., description="Whether connection was successful")
    server_url: str = Field(..., description="Connected server URL")
    server_name: str | None = Field(default=None, description="Server name")
    machine_identifier: str | None = Field(default=None, description="Server machine ID")
    version: str | None = Field(default=None, description="Server version")
    error: str | None = Field(default=None, description="Error message if failed")


class ConnectionTestRequest(BaseModel):
    """Request to test a connection URL."""

    url: str = Field(..., description="Server URL to test")


class ConnectionTestResponse(BaseModel):
    """Response from testing a connection."""

    url: str = Field(..., description="Tested URL")
    reachable: bool = Field(..., description="Whether the server is reachable")
    latency_ms: int | None = Field(default=None, description="Response time in milliseconds")
    error: str | None = Field(default=None, description="Error message if not reachable")


# =============================================================================
# =============================================================================


@router.get(
    "/config",
    response_model=ServerConfigResponse,
    summary="Get server configuration",
    description="Get the configured Plex server settings (from environment variables).",
)
async def get_server_config(
    settings: Annotated[Settings, Depends(get_settings)],
) -> ServerConfigResponse:
    """Get the configured server settings."""
    return ServerConfigResponse(
        url=settings.plex_url,
        host=settings.plex_host,
        port=settings.plex_port,
        protocol=settings.plex_protocol,
    )


@router.get(
    "/status",
    response_model=ServerStatusResponse,
    summary="Check server status",
    description="Check if the configured Plex server is reachable and responding.",
)
async def check_server_status(
    token: Annotated[str, Depends(get_token_from_header)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ServerStatusResponse:
    """Check server connectivity and get basic info."""
    try:
        async with PlexClient(settings) as client:
            identity = await client.check_server_identity(
                server_url=settings.plex_url,
                token=token,
            )

        return ServerStatusResponse(
            connected=True,
            url=settings.plex_url,
            machine_identifier=identity.machine_identifier,
            version=identity.version,
        )
    except PlexConnectionError as e:
        return ServerStatusResponse(
            connected=False,
            url=settings.plex_url,
            error=f"Connection failed: {e.message}",
        )
    except PlexClientError as e:
        return ServerStatusResponse(
            connected=False,
            url=settings.plex_url,
            error=f"Server error: {e.message}",
        )


@router.get(
    "/identity",
    response_model=ServerIdentityResponse,
    responses={
        503: {"model": ErrorResponse, "description": "Server unreachable"},
        500: {"model": ErrorResponse},
    },
    summary="Get server identity",
    description="Get the server's identity information. Fails if server is unreachable.",
)
async def get_server_identity(
    token: Annotated[str, Depends(get_token_from_header)],
    settings: Annotated[Settings, Depends(get_settings)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> ServerIdentityResponse:
    """Get server identity (requires server to be online)."""
    try:
        async with PlexClient(settings) as client:
            identity = await client.check_server_identity(
                server_url=settings.plex_url,
                token=token,
            )

        auth_service.update_session_server(
            token=token,
            server_url=settings.plex_url,
            server_name=settings.plex_host,
            machine_id=identity.machine_identifier,
        )

        return ServerIdentityResponse(
            machine_identifier=identity.machine_identifier,
            version=identity.version,
            url=settings.plex_url,
        )
    except PlexConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Cannot connect to Plex server: {e.message}",
        )
    except PlexClientError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/list",
    response_model=ServersListResponse,
    summary="List available servers",
    description="Get list of Plex servers available to the authenticated user.",
)
async def list_servers(
    token: Annotated[str, Depends(get_token_from_header)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ServersListResponse:
    """Fetch available Plex servers from plex.tv."""
    try:
        async with PlexClient(settings) as client:
            plex_servers = await client.get_servers(token)

        servers = [
            ServerInfo(
                name=server.name,
                machine_identifier=server.client_identifier,
                owned=server.owned,
                version=server.product_version,
                connections=[
                    ConnectionInfo(
                        uri=conn.uri,
                        local=conn.local,
                        relay=conn.relay,
                    )
                    for conn in server.connections
                ],
            )
            for server in plex_servers
        ]

        return ServersListResponse(servers=servers)
    except PlexClientError as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch servers: {e.message}")


@router.post(
    "/select",
    response_model=ServerSelectResponse,
    summary="Select and connect to a server",
    description="Validate connection to a server URL and set it as the active server.",
)
async def select_server(
    request: ServerSelectRequest,
    token: Annotated[str, Depends(get_token_from_header)],
    settings: Annotated[Settings, Depends(get_settings)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> ServerSelectResponse:
    """Validate and select a Plex server."""
    server_url = request.server_url.rstrip("/")

    try:
        async with PlexClient(settings) as client:
            identity = await client.check_server_identity(
                server_url=server_url,
                token=token,
            )

        auth_service.update_session_server(
            token=token,
            server_url=server_url,
            server_name=None,
            machine_id=identity.machine_identifier,
        )

        return ServerSelectResponse(
            success=True,
            server_url=server_url,
            machine_identifier=identity.machine_identifier,
            version=identity.version,
        )
    except PlexConnectionError as e:
        return ServerSelectResponse(
            success=False,
            server_url=server_url,
            error=f"Cannot connect: {e.message}",
        )
    except PlexClientError as e:
        return ServerSelectResponse(
            success=False,
            server_url=server_url,
            error=f"Server error: {e.message}",
        )


@router.post(
    "/test",
    response_model=ConnectionTestResponse,
    summary="Test a server connection",
    description="Test if a Plex server URL is reachable and measure latency.",
)
async def test_connection(
    request: ConnectionTestRequest,
    token: Annotated[str, Depends(get_token_from_header)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ConnectionTestResponse:
    """Test if a server URL is reachable."""
    import time

    from loguru import logger

    server_url = request.url.rstrip("/")
    start_time = time.monotonic()

    try:
        async with PlexClient(settings) as client:
            await client.check_server_identity(
                server_url=server_url,
                token=token,
                timeout=5.0,
            )

        latency_ms = int((time.monotonic() - start_time) * 1000)
        logger.info(f"Connection test OK: {server_url} ({latency_ms}ms)")
        return ConnectionTestResponse(
            url=server_url,
            reachable=True,
            latency_ms=latency_ms,
        )
    except PlexConnectionError as e:
        logger.warning(f"Connection test failed: {server_url} - {e.message}")
        return ConnectionTestResponse(
            url=server_url,
            reachable=False,
            error=e.message,
        )
    except PlexClientError as e:
        logger.warning(f"Connection test error: {server_url} - {e.message}")
        return ConnectionTestResponse(
            url=server_url,
            reachable=False,
            error=e.message,
        )
