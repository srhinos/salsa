"""Plex API header utilities."""

from salsa.backend.config import Settings, get_settings


def get_plex_headers(
    token: str | None = None,
    settings: Settings | None = None,
) -> dict[str, str]:
    """
    Build standard Plex API headers.

    Args:
        token: Optional Plex authentication token
        settings: Optional settings instance (uses cached default if not provided)

    Returns:
        Dictionary of headers for Plex API requests
    """
    if settings is None:
        settings = get_settings()

    headers = {
        "X-Plex-Client-Identifier": settings.get_client_id(),
        "X-Plex-Product": settings.app_name,
        "X-Plex-Version": settings.app_version,
        "X-Plex-Platform": "Web",
        "X-Plex-Device": "Web",
        "X-Plex-Device-Name": f"{settings.app_name} (Web)",
        "Accept": "application/json",
    }

    if token:
        headers["X-Plex-Token"] = token

    return headers


PLEX_TV_URL = "https://plex.tv/api/v2"
