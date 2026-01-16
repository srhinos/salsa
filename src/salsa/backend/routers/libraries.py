"""Library browsing API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
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


def get_server_url(
    token: Annotated[str, Depends(get_token_from_header)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> str:
    """Get the selected server URL from the session."""
    session = auth_service.get_session(token)
    if not session or not session.server_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No server selected. Please select a Plex server first.",
        )
    return session.server_url


# =============================================================================
# =============================================================================


class LibraryResponse(BaseModel):
    """Single library information."""

    key: str = Field(..., description="Library section key")
    title: str = Field(..., description="Library title")
    type: str = Field(..., description="Library type (movie, show, etc.)")
    uuid: str | None = Field(default=None, description="Library UUID")


class LibrariesResponse(BaseModel):
    """List of libraries."""

    libraries: list[LibraryResponse]
    total: int = Field(..., description="Total number of libraries")


class LibraryItemSummary(BaseModel):
    """Summary of a library item (without full media details)."""

    rating_key: str = Field(..., description="Item rating key")
    title: str = Field(..., description="Item title")
    type: str = Field(..., description="Item type")
    year: int | None = Field(default=None, description="Release year")
    thumb: str | None = Field(default=None, description="Thumbnail path")
    summary: str | None = Field(default=None, description="Item summary/description")

    index: int | None = Field(default=None, description="Episode number")
    parent_index: int | None = Field(default=None, description="Season number")
    grandparent_title: str | None = Field(default=None, description="Show title (for episodes)")


class LibraryItemsResponse(BaseModel):
    """List of items in a library."""

    items: list[LibraryItemSummary]
    total: int = Field(..., description="Total number of items")
    library_key: str = Field(..., description="Library section key")
    library_title: str | None = Field(default=None, description="Library title")


# =============================================================================
# =============================================================================


@router.get(
    "",
    response_model=LibrariesResponse,
    responses={
        400: {"model": ErrorResponse, "description": "No server selected"},
        503: {"model": ErrorResponse, "description": "Server unreachable"},
        500: {"model": ErrorResponse},
    },
    summary="List libraries",
    description="Get all libraries (sections) from the Plex server.",
)
async def list_libraries(
    token: Annotated[str, Depends(get_token_from_header)],
    server_url: Annotated[str, Depends(get_server_url)],
    settings: Annotated[Settings, Depends(get_settings)],
    video_only: Annotated[
        bool,
        Query(description="Only return video libraries (movie, show)"),
    ] = True,
) -> LibrariesResponse:
    """Get all libraries from the server."""
    try:
        async with PlexClient(settings) as client:
            libraries_data = await client.get_libraries(
                server_url=server_url,
                token=token,
            )

        libraries = []
        for lib_data in libraries_data:
            lib = LibraryResponse(
                key=lib_data.get("key", ""),
                title=lib_data.get("title", ""),
                type=lib_data.get("type", ""),
                uuid=lib_data.get("uuid"),
            )
            if video_only and lib.type not in ("movie", "show"):
                continue
            libraries.append(lib)

        return LibrariesResponse(libraries=libraries, total=len(libraries))

    except PlexConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Cannot connect to Plex server: {e.message}",
        )
    except PlexClientError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{library_key}",
    response_model=LibraryResponse,
    responses={
        400: {"model": ErrorResponse, "description": "No server selected"},
        404: {"model": ErrorResponse, "description": "Library not found"},
        503: {"model": ErrorResponse, "description": "Server unreachable"},
        500: {"model": ErrorResponse},
    },
    summary="Get library",
    description="Get information about a specific library.",
)
async def get_library(
    library_key: str,
    token: Annotated[str, Depends(get_token_from_header)],
    server_url: Annotated[str, Depends(get_server_url)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> LibraryResponse:
    """Get a specific library by key."""
    try:
        async with PlexClient(settings) as client:
            libraries_data = await client.get_libraries(
                server_url=server_url,
                token=token,
            )

        for lib_data in libraries_data:
            if lib_data.get("key") == library_key:
                return LibraryResponse(
                    key=lib_data.get("key", ""),
                    title=lib_data.get("title", ""),
                    type=lib_data.get("type", ""),
                    uuid=lib_data.get("uuid"),
                )

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Library with key '{library_key}' not found",
        )

    except PlexConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Cannot connect to Plex server: {e.message}",
        )
    except PlexClientError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{library_key}/items",
    response_model=LibraryItemsResponse,
    responses={
        400: {"model": ErrorResponse, "description": "No server selected"},
        503: {"model": ErrorResponse, "description": "Server unreachable"},
        500: {"model": ErrorResponse},
    },
    summary="List library items",
    description="Get all items in a library (movies or shows).",
)
async def list_library_items(
    library_key: str,
    token: Annotated[str, Depends(get_token_from_header)],
    server_url: Annotated[str, Depends(get_server_url)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> LibraryItemsResponse:
    """Get all items in a library."""
    try:
        async with PlexClient(settings) as client:
            libraries_data = await client.get_libraries(
                server_url=server_url,
                token=token,
            )
            library_title = None
            for lib in libraries_data:
                if lib.get("key") == library_key:
                    library_title = lib.get("title")
                    break

            container = await client.get_library_items(
                server_url=server_url,
                token=token,
                library_key=library_key,
            )

        items = []
        for item in container.metadata:
            items.append(
                LibraryItemSummary(
                    rating_key=item.rating_key,
                    title=item.title,
                    type=item.type,
                    year=item.year,
                    thumb=item.thumb,
                    summary=item.summary[:200] if item.summary else None,
                    index=item.index,
                    parent_index=item.parent_index,
                    grandparent_title=item.grandparent_title,
                )
            )

        return LibraryItemsResponse(
            items=items,
            total=len(items),
            library_key=library_key,
            library_title=library_title,
        )

    except PlexConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Cannot connect to Plex server: {e.message}",
        )
    except PlexClientError as e:
        raise HTTPException(status_code=500, detail=str(e))
