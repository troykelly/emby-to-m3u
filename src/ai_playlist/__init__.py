"""AI-Powered Radio Playlist Automation

This module provides AI/ML-based playlist generation for radio stations,
parsing programming documents and using LLM with MCP tools to select tracks.
"""

from src.ai_playlist.azuracast_sync import (
    sync_playlist_to_azuracast,
    AzuraCastPlaylistSyncError,
)

__version__ = "1.0.0"

__all__ = [
    "sync_playlist_to_azuracast",
    "AzuraCastPlaylistSyncError",
]
