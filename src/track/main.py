# src/track/main.py

import requests
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playlist.main import PlaylistManager

class Track(dict):
    """Represents an audio track with extended functionality for downloading."""

    def __init__(self, track_data: dict, playlist_manager: 'PlaylistManager') -> None:
        """Initializes the Track with metadata and a reference to PlaylistManager.

        Args:
            track_data: Dictionary containing the track metadata.
            playlist_manager: The PlaylistManager instance that manages this track.
        """
        super().__init__(track_data)
        self.playlist_manager = playlist_manager

    def download(self) -> bytes:
        """Downloads the track's binary content from the Emby server.

        Returns:
            Binary content of the track's file.

        Raises:
            ValueError: If Emby server URL or API key is not set.
        """
        track_id = self['Id']
        emby_server_url = os.getenv('EMBY_SERVER_URL')
        emby_api_key = os.getenv('EMBY_API_KEY')
        
        if not emby_server_url or not emby_api_key:
            raise ValueError("Emby server URL and API key are required to fetch track content.")
        
        download_url = f"{emby_server_url}/Items/{track_id}/File?api_key={emby_api_key}"
        response = requests.get(download_url, stream=True)
        response.raise_for_status()
        return response.content
