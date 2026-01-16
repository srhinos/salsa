"""FastAPI application entry point."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from salsa.backend.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Plex server configured at: {settings.plex_url}")
    logger.debug(f"Client ID: {settings.get_client_id()}")

    yield

    logger.info("Shutting down...")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Plex audio/subtitle track management tool",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["Health"])
    async def health() -> dict[str, str]:
        return {"status": "healthy"}

    @app.get("/ready", tags=["Health"])
    async def ready() -> dict[str, str]:
        return {"status": "ready"}

    @app.get("/", tags=["Root"])
    async def root() -> dict[str, str]:
        return {
            "app": settings.app_name,
            "version": settings.app_version,
        }

    from salsa.backend.routers import auth, libraries, media, servers, tracks

    app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
    app.include_router(servers.router, prefix="/api/server", tags=["Server"])
    app.include_router(libraries.router, prefix="/api/libraries", tags=["Libraries"])
    app.include_router(media.router, prefix="/api/media", tags=["Media"])
    app.include_router(tracks.router, prefix="/api/tracks", tags=["Tracks"])

    return app


app = create_app()
