import os
import time
import logging
from base64 import b64encode
from typing import Dict, List, Union, Optional, Any
from io import BytesIO

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tqdm import tqdm
from track.main import Track

from replaygain.main import has_replaygain_metadata

logger = logging.getLogger(__name__)


class AzuraCastSync:
    """Client for interacting with the AzuraCast API for syncing playlists."""

    def __init__(self) -> None:
        """Initializes the AzuraCast client with environment variables."""
        self.host: str = os.getenv("AZURACAST_HOST", "")
        self.api_key: str = os.getenv("AZURACAST_API_KEY", "")
        self.station_id: str = os.getenv("AZURACAST_STATIONID", "")

    def _get_session(self) -> requests.Session:
        """Creates a new session with retry strategy.

        Returns:
            Configured session object.
        """
        session: requests.Session = requests.Session()
        retries: Retry = Retry(
            total=1,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST"],
        )
        adapter: HTTPAdapter = HTTPAdapter(max_retries=retries)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def _perform_request(
        self,
        method: str,
        endpoint: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Union[str, int]]] = None,
        data: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> requests.Response:
        """Performs an HTTP request with connection handling and retry logic.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE).
            endpoint: API endpoint.
            headers: Request headers.
            params: URL parameters.
            data: Data to be sent in the body of the request.
            json: JSON data to be sent in the body of the request.

        Returns:
            The response object if successful.

        Raises:
            requests.exceptions.RequestException: If the HTTP request encounters an error.
        """
        url: str = f"{self.host}/api{endpoint}"
        headers = headers or {}
        headers.update({"X-API-Key": self.api_key})

        max_attempts: int = 6
        timeout: int = 240

        for attempt in range(1, max_attempts + 1):
            session: Optional[requests.Session] = None
            response: Optional[requests.Response] = None
            try:
                session = self._get_session()
                logger.debug("Attempt %d: Making request to %s", attempt, url)
                response = session.request(
                    method,
                    url,
                    headers=headers,
                    params=params,
                    data=data,
                    json=json,
                    timeout=timeout,
                )
                response.raise_for_status()

                if response.status_code == 413:
                    logger.warning(
                        "Attempt %d: Request to %s failed due to size limit. Retrying...",
                        attempt,
                        url,
                    )
                    time.sleep(2 ** attempt)
                    continue  # Retry on 413 error

                return response

            except (
                requests.exceptions.SSLError,
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
            ) as e:
                logger.warning(
                    "Attempt %d: Request to %s failed: %s. Retrying...",
                    attempt,
                    url,
                    e,
                )
                time.sleep(2 ** attempt)
            except requests.exceptions.RequestException as e:
                response_text: str = response.text if response else "No response"
                logger.error(
                    "Attempt %d: Request to %s failed: %s - Response: %s",
                    attempt,
                    url,
                    e,
                    response_text,
                )
                raise e
            finally:
                if session:
                    session.close()

        logger.error("Request to %s failed after %d attempts", url, max_attempts)
        raise requests.exceptions.RequestException(f"Failed after {max_attempts} attempts")

    def get_known_tracks(self) -> List[Dict[str, Any]]:
        """Retrieves a list of all known tracks in AzuraCast.

        Returns:
            List of dictionaries containing the known files' metadata.
        """
        endpoint: str = f"/station/{self.station_id}/files"
        response: requests.Response = self._perform_request("GET", endpoint)
        return response.json()  # Ensure the JSON content is returned

    def check_file_in_azuracast(self, known_tracks: List[Dict[str, Any]], track: Dict[str, Any]) -> bool:
        """Checks if a file with the same metadata exists in AzuraCast.

        Args:
            known_tracks: List of known file metadata.
            track: The track object to check.

        Returns:
            True if the file is known to AzuraCast, False otherwise.
        """
        artist: str = track.get("AlbumArtist", "")
        album: str = track.get("Album", "")
        title: str = track.get("Name", "")
        length: str = str(track.get("RunTimeTicks", 0) // 10000000)  # Convert ticks to seconds

        for known_track in known_tracks:
            if (
                known_track.get("artist") == artist
                and known_track.get("album") == album
                and known_track.get("title") == title
            ):
                track["azuracast_file_id"] = known_track["id"]
                logger.debug(
                    "File '%s' already exists in Azuracast with ID '%s'",
                    title,
                    track["azuracast_file_id"],
                )
                return True
        logger.debug("File '%s' does not exist in Azuracast", title)
        return False

    def upload_file_to_azuracast(self, file_content: bytes, file_key: str) -> Dict[str, Any]:
        """Uploads a file to AzuraCast.

        Args:
            file_content: Content of the file to be uploaded.
            file_key: Key (name) of the file to be uploaded.

        Returns:
            Response from the server, commonly including the uploaded file's metadata.
        """
        endpoint: str = f"/station/{self.station_id}/files"

        if not file_content or not file_key:
            logger.error("Missing filename or fileobj argument")
            raise ValueError("Missing filename or fileobj argument")
        
        # Calculate file length in bytes
        file_size: int = len(file_content)
        
        # Check that the file is at least the minimum file size for a normal audio file - raise otherwise
        if file_size < 1000:
            logger.error("File '%s' is too small to be a valid audio file with %d bytes", file_key, file_size)
            raise ValueError("File is too small to be a valid audio file")
        
        logger.debug("Uploading file '%s' with %d bytes", file_key, file_size)

        b64_content: str = b64encode(file_content).decode("utf-8")
        data: Dict[str, Union[str, bytes]] = {"path": file_key, "file": b64_content}

        file_size: str = self._sizeof_fmt(len(file_content))
        logger.debug("Uploading file: %s, Size: %s", file_key, file_size)

        response: requests.Response = self._perform_request("POST", endpoint, json=data)
        return response.json()

    def get_playlist(self, playlist_name: str) -> Optional[Dict[str, Any]]:
        """Retrieves a playlist by name from AzuraCast.

        Args:
            playlist_name: Name of the playlist.

        Returns:
            Playlist information if found, None otherwise.
        """
        endpoint: str = f"/station/{self.station_id}/playlists"
        response: requests.Response = self._perform_request("GET", endpoint)
        playlists: List[Any] = response.json()
        for playlist in playlists:
            if playlist["name"] == playlist_name:
                return playlist
        return None

    def create_playlist(self, playlist_name: str) -> Dict[str, Any]:
        """Creates a new playlist in AzuraCast.

        Args:
            playlist_name: Name of the new playlist.

        Returns:
            Information of the created playlist.
        """
        endpoint: str = f"/station/{self.station_id}/playlists"
        data: Dict[str, str] = {"name": playlist_name, "type": "default"}
        response: requests.Response = self._perform_request("POST", endpoint, json=data)
        return response.json()

    def empty_playlist(self, playlist_id: int) -> Dict[str, Any]:
        """Empties a playlist.

        Args:
            playlist_id: ID of the playlist to be emptied.

        Returns:
            JSON response from the server.
        """
        endpoint: str = f"/station/{self.station_id}/playlist/{playlist_id}/empty"
        response: requests.Response = self._perform_request("DELETE", endpoint)
        return response.json()

    def add_to_playlist(self, file_id: str, playlist_id: int) -> Dict[str, Any]:
        """Adds a file to a playlist.

        Args:
            file_id: ID of the file to be added.
            playlist_id: ID of the playlist.

        Returns:
            JSON response from the server.
        """
        endpoint: str = f"/station/{self.station_id}/file/{file_id}"
        data: Dict[str, List[int]] = {"playlists": [playlist_id]}
        response: requests.Response = self._perform_request("PUT", endpoint, json=data)
        return response.json()

    def clear_playlist_by_name(self, playlist_name: str) -> None:
        """Clears the existing AzuraCast playlist if it exists by name.

        Args:
            playlist_name: Name of the playlist.
        """
        playlist: Optional[Dict[str, Any]] = self.get_playlist(playlist_name)
        if playlist:
            self.empty_playlist(playlist["id"])

    def generate_file_path(self, track: Dict[str, Any]) -> str:
        """Generate file path used to store file in AzuraCast."""
        artist_name: str = track.get("AlbumArtist", "Unknown Artist")
        album_name: str = f"{track.get('Album', 'Unknown Album')} ({track.get('ProductionYear', 'Unknown Year')})"
        disk_number: int = track.get("ParentIndexNumber", 1)
        track_number: int = track.get("IndexNumber", 1)
        title: str = track.get("Name", "Unknown Title")
        file_path: str = track.get("Path", "")
        file_extension: str = os.path.splitext(file_path)[1]

        return f"{artist_name}/{album_name}/{disk_number:02d} {track_number:02d} {title}{file_extension}"

    def upload_file_and_set_track_id(self, track: Track, pbar_upload_playlist: tqdm) -> bool:
        """Upload file to Azuracast and set the track's azuracast_file_id.

        Args:
            track: Track instance to upload.

        Returns:
            True if file was successfully uploaded or already exists in Azuracast, False otherwise.
        """
        
        artist_name: str = track.get("AlbumArtist", "Unknown Artist")
        title: str = track.get("Name", "Unknown Title")

        try:
            known_tracks: List[Dict[str, Any]] = self.get_known_tracks()

            if not self.check_file_in_azuracast(known_tracks, track):
                pbar_upload_playlist.set_description(f"Uploading '{title}' by '{artist_name}'")
                # File does not exist, proceed with upload
                file_content: bytes = track.download()
                upload_response: Dict[str, Any] = self.upload_file_to_azuracast(file_content, self.generate_file_path(track))
                track["azuracast_file_id"] = upload_response.get("id")
                if track["azuracast_file_id"]:
                    logger.debug(
                        "Uploaded file '%s' to Azuracast with ID '%s'",
                        track["Name"],
                        track["azuracast_file_id"],
                    )
                else:
                    logger.error("Failed to set azuracast_file_id for '%s'", track["Name"])
                    return False
            else:
                pbar_upload_playlist.set_description(f"Existing '{title}' by '{artist_name}'")
                # File exists, check if it has ReplayGain metadata
                if not track["azuracast_file_id"]:
                    logger.error("azuracast_file_id is None for existing file '%s'", track["Name"])
                    return False

                track_id: str = track["azuracast_file_id"]
                file_content: bytes = self.download_file_from_azuracast(track_id)
                content: BytesIO = BytesIO(file_content)

                if not has_replaygain_metadata(content, os.path.splitext(track["Path"])[1]):
                    logger.debug(
                        "File '%s' does not have ReplayGain metadata, deleting it from Azuracast.",
                        track["Name"],
                    )
                    
                    pbar_upload_playlist.set_description(f"Deleting '{title}' by '{artist_name}'")
                    
                    if self.delete_file_from_azuracast(track_id):
                        # Re-analyze and upload with ReplayGain metadata
                        new_file_content: bytes = track.download()
                        pbar_upload_playlist.set_description(f"Uploading '{title}' by '{artist_name}'")
                        upload_response = self.upload_file_to_azuracast(new_file_content, self.generate_file_path(track))
                        if upload_response and "id" in upload_response:
                            track["azuracast_file_id"] = upload_response["id"]
                            logger.debug(
                                "Re-uploaded file '%s' to Azuracast with ReplayGain ID '%s'",
                                track["Name"],
                                track["azuracast_file_id"],
                            )
                        else:
                            logger.error(
                                "Failed to upload file '%s' after deletion",
                                track["Name"],
                            )
                            return False
                    else:
                        pbar_upload_playlist.set_description(f"Delete failed '{title}' by '{artist_name}'")
                        logger.error(
                            "Failed to delete file '%s' from Azuracast, cannot re-upload",
                            track["Name"],
                        )
                        return False
                else:
                    logger.debug(
                        "File '%s' already exists in Azuracast with ID '%s' and has ReplayGain metadata",
                        track["Name"],
                        track["azuracast_file_id"],
                    )

            pbar_upload_playlist.set_description(f"Complete '{title}' by '{artist_name}'")
            return True
        except Exception as e:
            logger.error("Error uploading '%s' to Azuracast: %s", track["Name"], e)
            return False

    def download_file_from_azuracast(self, track_id: str) -> bytes:
        """Downloads a file from Azuracast.

        Args:
            track_id: ID of the file to download.

        Returns:
            Content of the file.
        """
        endpoint: str = f"/station/{self.station_id}/file/{track_id}/play"
        response: requests.Response = self._perform_request("GET", endpoint)
        return response.content

    def delete_file_from_azuracast(self, track_id: str) -> bool:
        """Deletes a file from Azuracast.

        Args:
            track_id: ID of the file to delete.

        Returns:
            True if the file was successfully deleted, False otherwise.
        """
        endpoint: str = f"/station/{self.station_id}/file/{track_id}"
        response: requests.Response = self._perform_request("DELETE", endpoint)

        if response.status_code == 200:
            result: Dict[str, Any] = response.json()
            if result.get("success") is True:
                logger.debug("Successfully deleted file with ID '%s' from Azuracast", track_id)
                return True
            logger.error(
                "Failed to delete file with ID '%s' from Azuracast: %s",
                track_id,
                result.get("message"),
            )
        else:
            logger.error(
                "Failed to get a valid response for deleting file with ID '%s' from Azuracast: HTTP %s",
                track_id,
                response.status_code,
            )

        return False

    def upload_playlist(self, playlist: List[Dict[str, Any]]) -> bool:
        """Uploads tracks to AzuraCast and sets their azuracast_file_id without updating the playlist.

        Args:
            playlist: List of Track instances to upload.

        Returns:
            True if the playlist upload was successful.
        """
        with tqdm(
            total=len(playlist), desc="Uploading tracks to AzuraCast", unit="track"
        ) as pbar_upload_playlist:
            for track in playlist:
                artist_name: str = track.get("AlbumArtist", "Unknown Artist")
                title: str = track.get("Name", "Unknown Title")
                pbar_upload_playlist.set_description(f"Checking '{title}' by '{artist_name}'")
                if not self.upload_file_and_set_track_id(track, pbar_upload_playlist):
                    logger.warning("Failed to upload '%s' to Azuracast", track["Name"])
                pbar_upload_playlist.update(1)
        return True

    def sync_playlist(self, playlist_name: str, playlist: List[Dict[str, Any]]) -> None:
        """Syncs the playlist to AzuraCast by clearing the playlist and adding tracks by their IDs.

        Args:
            playlist_name: Name of the playlist.
            playlist: List of Track instances to add to the playlist.
        """
        self.clear_playlist_by_name(playlist_name)

        with tqdm(total=len(playlist), desc=f"Syncing playlist '{playlist_name}'", unit="track") as pbar:
            for track in playlist:
                if "azuracast_file_id" in track:
                    playlist_info: Optional[Dict[str, Any]] = self.get_playlist(
                        playlist_name
                    )
                    if playlist_info:
                        self.add_to_playlist(track["azuracast_file_id"], playlist_info["id"])
                        logger.debug(
                            "Added '%s' to '%s' playlist in Azuracast.",
                            track["Name"],
                            playlist_name,
                        )
                    else:
                        created_playlist: Dict[str, Any] = self.create_playlist(
                            playlist_name
                        )
                        self.add_to_playlist(track["azuracast_file_id"], created_playlist["id"])
                        logger.debug(
                            "Created and added '%s' to new '%s' playlist in Azuracast.",
                            track["Name"],
                            playlist_name,
                        )
                else:
                    logger.warning(f"Skipping '{track['Name']}' as it has no AzuraCast ID.")
                pbar.update(1)

    def _find_azuracast_track_id(self, known_tracks: List[Dict[str, Any]], azuracast_file_path: str) -> Optional[str]:
        """Finds the AzuraCast file ID based on the file path.

        Args:
            known_tracks: List of known tracks.
            azuracast_file_path: File path in AzuraCast.

        Returns:
            Track ID if found, None otherwise.
        """
        for known_track in known_tracks:
            if known_track["path"] == azuracast_file_path:
                return known_track["id"]
        return None

    @staticmethod
    def _sizeof_fmt(num: int, suffix: str = "B") -> str:
        """Converts file size to a readable format.

        Args:
            num: File size in bytes.
            suffix: Suffix for the unit of file size.

        Returns:
            Readable file size format.
        """
        for unit in ["", "K", "M", "G", "T", "P", "E", "Z"]:
            if abs(num) < 1024.0:
                return f"{num:3.1f}{unit}{suffix}"
            num /= 1024.0
        return f"{num:.1f}Y{suffix}"