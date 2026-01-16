"""Pytest configuration and fixtures."""

import pytest
from httpx import ASGITransport, AsyncClient

from salsa.backend.config import Settings


@pytest.fixture
def anyio_backend() -> str:
    """Use asyncio backend for anyio."""
    return "asyncio"


@pytest.fixture
def test_settings() -> Settings:
    """Create test settings with mock values."""
    return Settings(
        secret_key="test-secret-key-for-testing",
        plex_host="localhost",
        plex_port=32400,
        plex_protocol="http",
        plex_client_id="test-client-id",
    )


@pytest.fixture
async def client():
    """Create async test client for API tests."""
    from salsa.backend.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as test_client:
        yield test_client
