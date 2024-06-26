import os
import requests
import logging
from typing import TYPE_CHECKING, Optional, Tuple
from io import BytesIO

from replaygain.main import process_replaygain, has_replaygain_metadata

from logger import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from playlist.main import PlaylistManager

class Track(dict):
    """Represents an audio track with extended functionality for downloading and ReplayGain analysis."""

    def __init__(self, track_data: dict, playlist_manager: 'PlaylistManager') -> None:
        """Initializes the Track with metadata and a reference to PlaylistManager.

        Args:
            track_data: Dictionary containing the track metadata.
        playlist_manager: The PlaylistManager instance that manages this track.
        """
        super().__init__(track_data)
        self.playlist_manager = playlist_manager
        self.azuracast_file_id: Optional[str] = None
        self.replaygain_gain: Optional[float] = None
        self.replaygain_peak: Optional[float] = None
        self.content: Optional[BytesIO] = None

    def clear_content(self) -> None:
        """Clears the track content to free memory."""
        self.content = None

    def download(self) -> bytes:
        """Downloads the track's binary content from the Emby server.

        Returns:
            Binary content of the track's file.
        """
        track_id = self['Id']
        emby_server_url = os.getenv('EMBY_SERVER_URL')
        emby_api_key = os.getenv('EMBY_API_KEY')

        if not emby_server_url or not emby_api_key:
            raise ValueError("Emby server URL and API key are required to fetch track content.")

        download_url = f"{emby_server_url}/Items/{track_id}/File?api_key={emby_api_key}"
        response = requests.get(download_url, stream=True)
        response.raise_for_status()

        with BytesIO(response.content) as f:
            self.content = BytesIO(f.getvalue())
            self._check_and_apply_replaygain()
            self.content.seek(0)  # Ensure pointer reset after ReplayGain processing

            if len(self.content.getbuffer()) <= 4:
                raise ValueError(f"Downloaded track '{self['Name']}' is only 4 bytes or less")

            data = self.content.getvalue()
            self.content.close()  # Clean up memory
            return data

    def _check_and_apply_replaygain(self) -> None:
        file_format = self['Path'].split('.')[-1].lower()

        if not has_replaygain_metadata(self.content, file_format):
            self.content = BytesIO(process_replaygain(self.content.getvalue(), file_format))
            logger.debug(f"Applied ReplayGain to track '{self['Name']}'")
        else:
            logger.debug(f"ReplayGain metadata already present for track '{self['Name']}'")
