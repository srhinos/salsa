"""Application configuration using Pydantic settings."""

import secrets
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SALSA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "SALSA"
    app_version: str = "1.0.0"
    debug: bool = False

    secret_key: str = secrets.token_hex(32)

    backend_url: str = "http://localhost:8001"

    api_url: str = "http://localhost:8000"

    plex_host: str = "plex"
    plex_port: int = 32400
    plex_protocol: str = "http"

    plex_client_id: str = ""

    plex_timeout: int = 20
    plex_identity_timeout: int = 5

    plex_rate_limit_requests: int = 10
    plex_rate_limit_period: float = 1.0

    @property
    def plex_url(self) -> str:
        return f"{self.plex_protocol}://{self.plex_host}:{self.plex_port}"

    def get_client_id(self) -> str:
        if self.plex_client_id:
            return self.plex_client_id
        import hashlib

        return f"salsa-{hashlib.sha256(self.secret_key.encode()).hexdigest()[:12]}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
