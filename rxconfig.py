"""Reflex configuration."""

import reflex as rx

from salsa.backend.config import get_settings

settings = get_settings()

config = rx.Config(
    app_name="salsa",
    app_module_import="salsa.frontend.app",
    api_url=settings.api_url,
    show_built_with_reflex=False,
)
