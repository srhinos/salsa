"""State management for SALSA frontend."""

from salsa.frontend.state.auth import AuthState, PlexServerInfo, ServerConnection
from salsa.frontend.state.batch import BatchState
from salsa.frontend.state.browser import BrowserState

State = BatchState

__all__ = [
    "AuthState",
    "BatchState",
    "BrowserState",
    "PlexServerInfo",
    "ServerConnection",
    "State",
]
