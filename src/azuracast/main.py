import os
import requests
import logging
from tqdm import tqdm
from base64 import b64encode
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time

logger = logging.getLogger(__name__)

class AzuraCastSync:
    """Client for interacting with the AzuraCast API for syncing playlists."""

    def __init__(self):
        """Initializes the Azuracast client with environment variables."""
        self.host = os.getenv('AZURACAST_HOST')
        self.api_key = os.getenv('AZURACAST_API_KEY')
        self.station_id = os.getenv('AZURACAST_STATIONID')

    def _get_session(self):
        """Creates a new session with retry strategy.

        Returns:
            requests.Session: Configured session object.
        """
        session = requests.Session()
        retries = Retry(
            total=1,  # Retry strategy within a single request
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST"]
        )
        adapter = HTTPAdapter(max_retries=retries)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session

    def _perform_request(self, method, endpoint, headers=None, data=None, json=None):
        """Performs an HTTP request with connection handling and retry logic.

        Args:
            method (str): HTTP method (GET, POST, PUT, DELETE).
            endpoint (str): API endpoint.
            headers (dict, optional): Request headers.
            data (dict, optional): Data to be sent in the body of the request.
            json (dict, optional): JSON data to be sent in the body of the request.

        Returns:
            dict: JSON response.

        Raises:
            requests.exceptions.RequestException: If the HTTP request encounters an error.
        """
        url = f"{self.host}/api{endpoint}"
        headers = headers or {}
        headers.update({"X-API-Key": self.api_key})

        max_attempts = 6
        timeout = 240  # Increased timeout for larger file uploads

        for attempt in range(1, max_attempts + 1):  # Retry up to 6 times
            session = None
            response = None  # Initialize the response variable to ensure it exists
            try:
                session = self._get_session()
                logger.debug("Attempt %d: Making request to %s", attempt, url)
                response = session.request(method, url, headers=headers, data=data, json=json, timeout=timeout)
                response.raise_for_status()

                if response.status_code == 413:
                    logger.warning("Attempt %d: Request to %s failed due to size limit. Retrying...", attempt, url)
                    time.sleep(2 ** attempt)
                    continue  # Retry on 413 error

                return response.json()

            except (requests.exceptions.SSLError, requests.exceptions.ConnectionError,
                    requests.exceptions.Timeout) as e:
                logger.warning("Attempt %d: Request to %s failed: %s. Retrying...", attempt, url, e)
                time.sleep(2 ** attempt)  # Exponential backoff

            except requests.exceptions.RequestException as e:
                # Check if response is available to avoid referencing a variable that might not be set
                response_text = response.text if response else "No response"
                logger.error("Attempt %d: Request to %s failed: %s - Response: %s", attempt, url, e, response_text)
                raise e  # Exit on non-retriable exceptions

            finally:
                if session:
                    session.close()  # Ensure session is closed after each attempt

        logger.error("Request to %s failed after %d attempts", url, max_attempts)
        raise requests.exceptions.RequestException(f"Failed after {max_attempts} attempts")

    def get_known_tracks(self):
        """Retrieves a list of all known tracks in Azuracast.

        Returns:
            list: List of file paths known to Azuracast.
        """
        endpoint = f"/station/{self.station_id}/files/list"
        return self._perform_request("GET", endpoint)

    def check_file_in_azuracast(self, known_tracks, file_path):
        """Checks if a file is in the list of known tracks.

        Args:
            known_tracks (list): List of known file paths.
            file_path (str): The path of the file to check.

        Returns:
            bool: True if the file is known to Azuracast, False otherwise.
        """
        return file_path in known_tracks

    def upload_file_to_azuracast(self, file_content, file_key):
        """Uploads a file to Azuracast.

        Args:
            file_content (bytes): Content of the file to be uploaded.
            file_key (str): Key (name) of the file to be uploaded.

        Returns:
            dict: Response from the server, commonly including the uploaded file's metadata.
        """
        endpoint = f"/station/{self.station_id}/files"
        b64_content = b64encode(file_content).decode("utf-8")
        data = {"path": file_key, "file": b64_content}

        # Log file size in a readable format
        file_size = self._sizeof_fmt(len(file_content))
        logger.debug("Uploading file: %s, Size: %s", file_key, file_size)

        # Introduce a delay to avoid rate limiting issues
        # time.sleep(1)

        response = self._perform_request("POST", endpoint, json=data)
        logger.debug("Uploaded file: %s, Response: %s", file_key, response)
        return response

    def get_playlist(self, playlist_name):
        """Retrieves a playlist by name from Azuracast.

        Args:
            playlist_name (str): Name of the playlist.

        Returns:
            dict: Playlist information if found, None otherwise.
        """
        endpoint = f"/station/{self.station_id}/playlists"
        playlists = self._perform_request("GET", endpoint)
        for playlist in playlists:
            if playlist['name'] == playlist_name:
                return playlist
        return None

    def create_playlist(self, playlist_name):
        """Creates a new playlist in Azuracast.

        Args:
            playlist_name (str): Name of the new playlist.

        Returns:
            dict: Information of the created playlist.
        """
        endpoint = f"/station/{self.station_id}/playlists"
        data = {"name": playlist_name, "type": "default"}
        return self._perform_request("POST", endpoint, json=data)

    def empty_playlist(self, playlist_id):
        """Empties a playlist.

        Args:
            playlist_id (int): ID of the playlist to be emptied.

        Returns:
            dict: JSON response from the server.
        """
        endpoint = f"/station/{self.station_id}/playlist/{playlist_id}/empty"
        return self._perform_request('DELETE', endpoint)

    def add_to_playlist(self, file_id, playlist_id):
        """Adds a file to a playlist.

        Args:
            file_id (int): ID of the file to be added.
            playlist_id (int): ID of the playlist.

        Returns:
            dict: JSON response from the server.
        """
        endpoint = f"/station/{self.station_id}/file/{file_id}"
        data = {"playlists": [playlist_id]}
        return self._perform_request('PUT', endpoint, json=data)

    def clear_playlist_by_name(self, playlist_name):
        """Clears the existing AzuraCast playlist if it exists by name.

        Args:
            playlist_name (str): Name of the playlist.
        """
        playlist = self.get_playlist(playlist_name)
        if playlist:
            self.empty_playlist(playlist['id'])
            
    def generate_file_path(self, track):
        """Generate file path used to store file in AzuraCast."""
        artist_name = track.get('AlbumArtist', 'Unknown Artist')
        album_name = f"{track.get('Album', 'Unknown Album')} ({track.get('ProductionYear', 'Unknown Year')})"
        disk_number = track.get('ParentIndexNumber', 1)
        track_number = track.get('IndexNumber', 1)
        title = track.get('Name', 'Unknown Title')
        file_path = track.get('Path')
        file_extension = os.path.splitext(file_path)[1]
        
        return f"{artist_name}/{album_name}/{disk_number:02d} {track_number:02d} {title}{file_extension}"

    def upload_playlist(self, playlist, playlist_name):
        """Uploads tracks to AzuraCast and adds them to the specified playlist.

        Args:
            playlist (list): List of track dictionaries.
            playlist_name (str): Name of the playlist.
        """
        known_tracks = self.get_known_tracks()

        # Integrate tqdm progress bar
        with tqdm(total=len(playlist), desc=f"Uploading playlist '{playlist_name}'", unit="track") as pbar:
            for track in playlist:
                try:
                    azuracast_file_path = self.generate_file_path(track)

                    if not self.check_file_in_azuracast(known_tracks, azuracast_file_path):
                        file_content = track.download()
                        
                        # Update progress bar description to show current file
                        pbar.set_description(f"Uploading '{track['Name']}' to playlist '{playlist_name}'")
                        
                        upload_response = self.upload_file_to_azuracast(file_content, azuracast_file_path)
                        
                        track_id = upload_response.get("id")  # Use the proper field from response

                        if not track_id:
                            logger.error("Failed to get a valid track ID for '%s'", track['Name'])
                            continue

                        logger.debug("Uploaded track '%s' to Azuracast.", track['Name'])
                    else:
                        logger.debug("Track '%s' already exists in Azuracast.", track['Name'])
                        track_id = self._find_azuracast_track_id(known_tracks, azuracast_file_path)
                        if not track_id:
                            logger.error("Failed to find existing track ID for '%s'", track['Name'])
                            continue

                    playlist_info = self.get_playlist(playlist_name)
                    if playlist_info:
                        self.add_to_playlist(track_id, playlist_info['id'])
                        logger.debug("Added '%s' to '%s' playlist in Azuracast.", track['Name'], playlist_name)
                    else:
                        created_playlist = self.create_playlist(playlist_name)
                        self.add_to_playlist(track_id, created_playlist['id'])
                        logger.debug("Created and added '%s' to new '%s' playlist in Azuracast.", track['Name'], playlist_name)

                except Exception as e:
                    logger.error("Failed to process track '%s' for Azuracast: %s", track['Name'], e)
                finally:
                    # Update the main progress bar
                    pbar.update(1)

    def _find_azuracast_track_id(self, known_tracks, azuracast_file_path):
        """Finds the AzuraCast file ID based on the file path.

        Args:
            known_tracks (list): List of known tracks.
            azuracast_file_path (str): File path in AzuraCast.

        Returns:
            str: Track ID if found, None otherwise.
        """
        for known_track in known_tracks:
            if known_track['path'] == azuracast_file_path:
                return known_track['id']
        return None

    @staticmethod
    def _sizeof_fmt(num, suffix='B'):
        """Converts file size to a readable format.

        Args:
            num (int): File size in bytes.
            suffix (str): Suffix for the unit of file size.

        Returns:
            str: Readable file size format.
        """
        for unit in ['','K','M','G','T','P','E','Z']:
            if abs(num) < 1024.0:
                return f"{num:3.1f}{unit}{suffix}"
            num /= 1024.0
        return f"{num:.1f}Y{suffix}"