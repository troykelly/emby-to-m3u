import os
import time
import logging
import random
import string
from base64 import b64encode
from typing import Dict, List, Union, Optional, Any
from io import BytesIO

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tqdm import tqdm
from src.track.main import Track

from src.replaygain.main import has_replaygain_metadata
from src.logger import setup_logging
from .cache import get_cached_known_tracks
from .detection import check_file_in_azuracast as check_file_duplicate
from .models import DetectionStrategy

setup_logging()
logger = logging.getLogger(__name__)

BASE_BACKOFF = 2
MAX_BACKOFF = 64


def generate_unique_suffix() -> str:
    """Generates a unique suffix to append to requests."""
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=6))


class AzuraCastSync:
    """Client for interacting with the AzuraCast API for syncing playlists."""

    def __init__(self) -> None:
        """Initializes the AzuraCast client with environment variables."""
        self.host: str = os.getenv("AZURACAST_HOST", "")
        self.api_key: str = os.getenv("AZURACAST_API_KEY", "")
        self.station_id: str = os.getenv("AZURACAST_STATIONID", "")

        # T031: Cache and detection configuration
        self._cache_ttl: int = int(os.getenv("AZURACAST_CACHE_TTL", "300"))
        self._force_reupload: bool = (
            os.getenv("AZURACAST_FORCE_REUPLOAD", "false").lower() == "true"
        )
        self._legacy_detection: bool = (
            os.getenv("AZURACAST_LEGACY_DETECTION", "false").lower() == "true"
        )
        self._skip_replaygain_check: bool = (
            os.getenv("AZURACAST_SKIP_REPLAYGAIN_CHECK", "false").lower() == "true"
        )

        # T036: Configuration validation
        if not self.host:
            logger.warning("AZURACAST_HOST not set - API calls will fail")
        if not self.api_key:
            logger.warning("AZURACAST_API_KEY not set - API calls will fail")
        if not self.station_id:
            logger.warning("AZURACAST_STATIONID not set - API calls will fail")

        logger.info(
            f"AzuraCast initialized: cache_ttl={self._cache_ttl}s, force_reupload={self._force_reupload}, legacy_detection={self._legacy_detection}"
        )

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
        # Disable SSL verification for self-signed certificates
        session.verify = False
        # Suppress warnings about unverified HTTPS requests
        import urllib3

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
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

        for attempt in range(1, max_attempts + 1):
            session: Optional[requests.Session] = None
            response: Optional[requests.Response] = None
            unique_suffix: str = generate_unique_suffix()
            try:
                session = self._get_session()
                if params is None:
                    params = {}
                params["unique_suffix"] = unique_suffix
                logger.debug(
                    "Attempt %d: Making request to %s with params %s", attempt, url, params
                )
                response = session.request(
                    method,
                    url,
                    headers=headers,
                    params=params,
                    data=data,
                    json=json,
                    timeout=(10, 300),
                )
                if response.status_code == 404:
                    logger.warning(
                        "Attempt %d: Request to %s resulted in 404 Not Found", attempt, url
                    )
                    return response  # Handle 404 gracefully by returning the response

                # T033: Handle rate limiting (429 Too Many Requests)
                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    if retry_after:
                        try:
                            wait_time = int(retry_after)
                        except ValueError:
                            wait_time = min(BASE_BACKOFF * (2**attempt), MAX_BACKOFF)
                    else:
                        wait_time = min(BASE_BACKOFF * (2**attempt), MAX_BACKOFF)

                    logger.warning(
                        "Attempt %d: Rate limited (429). Waiting %d seconds before retry...",
                        attempt,
                        wait_time,
                    )
                    time.sleep(wait_time)
                    continue

                response.raise_for_status()

                if response.status_code == 413:
                    logger.warning(
                        "Attempt %d: Request to %s failed due to size limit. Retrying...",
                        attempt,
                        url,
                    )
                    time.sleep(min(BASE_BACKOFF * (2**attempt), MAX_BACKOFF))
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
                time.sleep(min(BASE_BACKOFF * (2**attempt), MAX_BACKOFF))
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

    def check_file_in_azuracast(
        self, known_tracks: List[Dict[str, Any]], track: Dict[str, Any]
    ) -> bool:
        """Checks if a file with the same metadata exists in AzuraCast.

        Args:
            known_tracks: List of known file metadata.
            track: The track object to check.

        Returns:
            True if the file is known to AzuraCast, False otherwise.
        """
        # T032: Use new detection logic unless legacy mode enabled
        if self._legacy_detection:
            # Legacy exact string matching
            artist: str = track.get("AlbumArtist", "")
            album: str = track.get("Album", "")
            title: str = track.get("Name", "")

            for known_track in known_tracks:
                if (
                    known_track.get("artist") == artist
                    and known_track.get("album") == album
                    and known_track.get("title") == title
                ):
                    track["azuracast_file_id"] = known_track["id"]
                    logger.debug(
                        "File '%s' already exists in Azuracast with ID '%s' (legacy detection)",
                        title,
                        track["azuracast_file_id"],
                    )
                    return True
            logger.debug("File '%s' does not exist in Azuracast (legacy detection)", title)
            return False

        # New multi-strategy detection
        decision = check_file_duplicate(known_tracks, track)

        # T035: INFO-level logging for duplicate decisions
        logger.info(decision.log_message())

        if not decision.should_upload:
            track["azuracast_file_id"] = decision.azuracast_file_id

        return not decision.should_upload

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
            logger.error(
                "File '%s' is too small to be a valid audio file with %d bytes", file_key, file_size
            )
            raise ValueError("File is too small to be a valid audio file")

        logger.debug("Uploading file '%s' with %d bytes", file_key, file_size)

        b64_content: str = b64encode(file_content).decode("utf-8")
        data: Dict[str, Union[str, bytes]] = {"path": file_key, "file": b64_content}

        file_size: str = self._sizeof_fmt(len(file_content))
        logger.debug("Uploading file: %s, Size: %s", file_key, file_size)

        response: requests.Response = self._perform_request("POST", endpoint, json=data)
        return response.json()

    def get_playlist(self, playlist_name: str) -> Optional[Dict[str, Any]]:
        """Retrieves a playlist by name from AzuraCast with full details including schedule.

        Args:
            playlist_name: Name of the playlist.

        Returns:
            Playlist information if found (including schedule_items), None otherwise.
        """
        try:
            # First get the list of playlists to find the ID
            endpoint: str = f"/station/{self.station_id}/playlists"
            response: requests.Response = self._perform_request("GET", endpoint)
            playlists: List[Any] = response.json()

            # Find playlist by name
            playlist_summary = next(
                (playlist for playlist in playlists if playlist["name"] == playlist_name), None
            )

            if not playlist_summary:
                return None

            # Get full playlist details including schedule_items
            playlist_id = playlist_summary["id"]
            detail_endpoint = f"/station/{self.station_id}/playlist/{playlist_id}"
            detail_response = self._perform_request("GET", detail_endpoint)

            return detail_response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get playlist '{playlist_name}': {e}")
            return None

    def create_playlist(self, playlist_name: str) -> Optional[Dict[str, Any]]:
        """Creates a new playlist in AzuraCast.

        Args:
            playlist_name: Name of the new playlist.

        Returns:
            Information of the created playlist or None if failed.
        """
        try:
            endpoint: str = f"/station/{self.station_id}/playlists"
            data: Dict[str, str] = {"name": playlist_name, "type": "default"}
            response: requests.Response = self._perform_request("POST", endpoint, json=data)
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to create playlist '{playlist_name}': {e}")
            return None

    def empty_playlist(self, playlist_id: int) -> bool:
        """Empties a playlist.

        Args:
            playlist_id: ID of the playlist to be emptied.

        Returns:
            True if successful, False otherwise.
        """
        try:
            endpoint: str = f"/station/{self.station_id}/playlist/{playlist_id}/empty"
            self._perform_request("DELETE", endpoint)
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to empty playlist with ID {playlist_id}: {e}")
            return False

    def add_to_playlist(self, file_id: str, playlist_id: int) -> bool:
        """Adds a file to a playlist.

        Args:
            file_id: ID of the file to be added.
            playlist_id: ID of the playlist.

        Returns:
            True if successful, False otherwise.
        """
        try:
            endpoint: str = f"/station/{self.station_id}/file/{file_id}"
            data: Dict[str, List[int]] = {"playlists": [playlist_id]}
            self._perform_request("PUT", endpoint, json=data)
            return True
        except requests.exceptions.RequestException as e:
            logger.error(
                f"Failed to add file with ID {file_id} to playlist with ID {playlist_id}: {e}"
            )
            return False

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
        album_name: str = (
            f"{track.get('Album', 'Unknown Album')} ({track.get('ProductionYear', 'Unknown Year')})"
        )
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

        # Mark track as not uploaded by default
        track["_was_uploaded"] = False

        try:
            # Use cached known tracks with TTL management
            known_tracks: List[Dict[str, Any]] = get_cached_known_tracks(
                fetch_fn=self.get_known_tracks, force_refresh=self._force_reupload
            )

            # Force reupload mode bypasses duplicate detection
            if self._force_reupload or not self.check_file_in_azuracast(known_tracks, track):
                pbar_upload_playlist.set_description(f"Uploading '{title}' by '{artist_name}'")
                # File does not exist, proceed with upload
                file_content: bytes = track.download()
                upload_response: Dict[str, Any] = self.upload_file_to_azuracast(
                    file_content, self.generate_file_path(track)
                )
                track["azuracast_file_id"] = upload_response.get("id")
                if track["azuracast_file_id"]:
                    track["_was_uploaded"] = True
                    logger.debug(
                        "Uploaded file '%s' to Azuracast with ID '%s'",
                        track["Name"],
                        track["azuracast_file_id"],
                    )
                    # Clear the track content to free memory
                    track.clear_content()

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
                # Skip ReplayGain check if configured to do so
                if self._skip_replaygain_check:
                    logger.debug(
                        "File '%s' already exists in Azuracast with ID '%s' (ReplayGain check skipped)",
                        track["Name"],
                        track["azuracast_file_id"],
                    )
                    return True

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
                        pbar_upload_playlist.set_description(
                            f"Uploading '{title}' by '{artist_name}'"
                        )
                        upload_response = self.upload_file_to_azuracast(
                            new_file_content, self.generate_file_path(track)
                        )
                        if upload_response and "id" in upload_response:
                            track["azuracast_file_id"] = upload_response["id"]
                            logger.debug(
                                "Re-uploaded file '%s' to Azuracast with ReplayGain ID '%s'",
                                track["Name"],
                                track["azuracast_file_id"],
                            )
                            # Clear the track content to free memory
                            track.clear_content()
                        else:
                            logger.error(
                                "Failed to upload file '%s' after deletion",
                                track["Name"],
                            )
                            return False
                    else:
                        pbar_upload_playlist.set_description(
                            f"Delete failed '{title}' by '{artist_name}'"
                        )
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
        try:
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

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to delete file with ID {track_id}: {e}")

        return False

    def upload_playlist(self, playlist: List[Dict[str, Any]]) -> bool:
        """Uploads tracks to AzuraCast and sets their azuracast_file_id without updating the playlist.

        Args:
            playlist: List of Track instances to upload.

        Returns:
            True if the playlist upload was successful.
        """
        # T034: Pre-count tracks that will need upload for progress reporting
        total_tracks = len(playlist)
        uploaded_count = 0
        skipped_count = 0
        failed_count = 0

        with tqdm(
            total=total_tracks, desc="Uploading tracks to AzuraCast", unit="track"
        ) as pbar_upload_playlist:
            for track in playlist:
                artist_name: str = track.get("AlbumArtist", "Unknown Artist")
                title: str = track.get("Name", "Unknown Title")
                pbar_upload_playlist.set_description(f"Checking '{title}' by '{artist_name}'")
                try:
                    result = self.upload_file_and_set_track_id(track, pbar_upload_playlist)
                    if result:
                        if "azuracast_file_id" in track:
                            # Track was either uploaded or already existed
                            if track.get("_was_uploaded", False):
                                uploaded_count += 1
                            else:
                                skipped_count += 1
                    else:
                        failed_count += 1
                        logger.warning("Failed to upload '%s' to Azuracast", track["Name"])
                except Exception as e:
                    failed_count += 1
                    logger.error(f"Failed to process track '{title}' by '{artist_name}': {e}")
                finally:
                    pbar_upload_playlist.update(1)

        # T034: Generate summary report
        logger.info(
            f"Upload complete: {uploaded_count} uploaded, {skipped_count} skipped (duplicates), "
            f"{failed_count} failed out of {total_tracks} total tracks"
        )

        return True

    def schedule_playlist(
        self,
        playlist_name: str,
        start_time: str,
        end_time: str,
        days: Optional[List[int]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> bool:
        """Schedule a playlist to play during specific time blocks.

        IDEMPOTENT: If the playlist already has the same schedule, it won't create duplicates.

        Args:
            playlist_name: Name of the playlist to schedule.
            start_time: Start time in HH:MM format (24-hour, e.g., "06:00").
            end_time: End time in HH:MM format (24-hour, e.g., "10:00").
            days: List of day numbers (0=Sunday, 1=Monday, ..., 6=Saturday).
                  If None, defaults to all weekdays (1-5).
            start_date: Start date in YYYY-MM-DD format (optional, for date-specific schedules).
            end_date: End date in YYYY-MM-DD format (optional, for date-specific schedules).

        Returns:
            True if scheduling was successful, False otherwise.
        """
        try:
            # Get playlist info
            playlist_info = self.get_playlist(playlist_name)
            if not playlist_info:
                logger.error(f"Playlist '{playlist_name}' not found, cannot schedule")
                return False

            playlist_id = playlist_info["id"]

            # Convert time string to HHMM integer format (e.g., "06:00" -> 600)
            def time_to_hhmm(time_str: str) -> int:
                hours, minutes = time_str.split(":")
                return int(hours) * 100 + int(minutes)

            start_hhmm = time_to_hhmm(start_time)
            end_hhmm = time_to_hhmm(end_time)

            # Default to weekdays if not specified
            if days is None:
                days = [1, 2, 3, 4, 5]  # Monday-Friday

            # Check if schedule already exists with same configuration
            existing_schedules = playlist_info.get("schedule_items", [])

            # Check if we already have this exact schedule
            schedule_exists = False
            for schedule in existing_schedules:
                if (schedule.get("start_time") == start_hhmm and
                    schedule.get("end_time") == end_hhmm and
                    sorted(schedule.get("days", [])) == sorted(days) and
                    schedule.get("start_date") == start_date and
                    schedule.get("end_date") == end_date):
                    schedule_exists = True
                    date_info = f" from {start_date} to {end_date}" if start_date else ""
                    logger.info(
                        f"✓ Schedule already exists for '{playlist_name}' "
                        f"({start_time}-{end_time} on days {days}{date_info})"
                    )
                    break

            if schedule_exists:
                # Schedule already configured - skip update
                return True

            # Build schedule_items array - REPLACE all existing schedules with just this one
            # This ensures idempotency - we don't accumulate duplicate schedules
            schedule_item = {
                "start_time": start_hhmm,
                "end_time": end_hhmm,
                "start_date": start_date,  # YYYY-MM-DD format or None for recurring
                "end_date": end_date,      # YYYY-MM-DD format or None for recurring
                "days": days,
                "loop_once": False,
            }

            # Update playlist with schedule (replaces all existing schedule_items)
            endpoint = f"/station/{self.station_id}/playlist/{playlist_id}"
            data = {
                "name": playlist_name,
                "schedule_items": [schedule_item],  # Single schedule item replaces all
            }

            response = self._perform_request("PUT", endpoint, json=data)

            if response.status_code == 200:
                date_info = f" from {start_date} to {end_date}" if start_date else ""
                logger.info(
                    f"✓ Scheduled '{playlist_name}' for {start_time}-{end_time} on days {days}{date_info}"
                )
                return True
            else:
                logger.error(
                    f"Failed to schedule '{playlist_name}': HTTP {response.status_code}"
                )
                return False

        except Exception as e:
            logger.error(f"Failed to schedule playlist '{playlist_name}': {e}")
            return False

    def sync_playlist(self, playlist_name: str, playlist: List[Dict[str, Any]]) -> None:
        """Syncs the playlist to AzuraCast by clearing the playlist and adding tracks by their IDs.

        Args:
            playlist_name: Name of the playlist.
            playlist: List of Track instances to add to the playlist.
        """
        self.clear_playlist_by_name(playlist_name)

        with tqdm(
            total=len(playlist), desc=f"Syncing playlist '{playlist_name}'", unit="track"
        ) as pbar:
            for track in playlist:
                try:
                    if "azuracast_file_id" in track:
                        playlist_info: Optional[Dict[str, Any]] = self.get_playlist(playlist_name)
                        if playlist_info:
                            self.add_to_playlist(track["azuracast_file_id"], playlist_info["id"])
                            logger.debug(
                                "Added '%s' to '%s' playlist in Azuracast.",
                                track["Name"],
                                playlist_name,
                            )
                        else:
                            created_playlist: Optional[Dict[str, Any]] = self.create_playlist(
                                playlist_name
                            )
                            if created_playlist:
                                self.add_to_playlist(
                                    track["azuracast_file_id"], created_playlist["id"]
                                )
                                logger.debug(
                                    "Created and added '%s' to new '%s' playlist in Azuracast.",
                                    track["Name"],
                                    playlist_name,
                                )
                    else:
                        logger.warning(f"Skipping '{track['Name']}' as it has no AzuraCast ID.")
                except Exception as e:
                    logger.error(
                        f"Failed to sync track '{track['Name']}' to playlist '{playlist_name}': {e}"
                    )
                finally:
                    pbar.update(1)

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
