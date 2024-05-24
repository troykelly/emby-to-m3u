import os
import requests
import logging
from base64 import b64encode
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

logging.basicConfig(level=logging.INFO)


class AzuraCastSync:
    """Client for interacting with the AzuraCast API for syncing playlists."""

    def __init__(self):
        """Initializes the AzuraCast client with environment variables."""
        self.host = os.getenv('AZURACAST_HOST')
        self.api_key = os.getenv('AZURACAST_API_KEY')
        self.station_id = os.getenv('AZURACAST_STATIONID')

        # Initialize a session for connection reuse and reliability
        self.session = requests.Session()
        retries = Retry(total=5, backoff_factor=0.3, status_forcelist=[500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)

    def _perform_request(self, method, endpoint, headers=None, data=None, json=None):
        """Performs an HTTP request.

        Args:
            method (str): HTTP method (GET, POST, PUT, DELETE).
            endpoint (str): API endpoint.
            headers (dict, optional): Request headers.
            data (dict, optional): Data to be sent in the body of the request.
            json (dict, optional): JSON data to be sent in the body of the request.

        Returns:
            dict: JSON response.

        Raises:
            requests.exceptions.HTTPError: If the HTTP request returned an unsuccessful status code.
        """
        url = f"{self.host}/api{endpoint}"
        headers = headers or {}
        headers.update({"X-API-Key": self.api_key})

        try:
            response = self.session.request(method, url, headers=headers, data=data, json=json, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"Request to {url} failed: {e}")
            raise

    def get_known_tracks(self):
        """Retrieves a list of all known tracks in Azuracast.

        Returns:
            list: List of file paths known to Azuracast.
        """
        endpoint = f"/station/{self.station_id}/files/list"
        response = self._perform_request("GET", endpoint)
        return [file_info["path"] for file_info in response]

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
            str: ID of the uploaded file.
        """
        endpoint = f"/station/{self.station_id}/files"
        b64_content = b64encode(file_content).decode("utf-8")
        data = {"path": file_key, "file": b64_content}
        response = self._perform_request("POST", endpoint, json=data)
        return response.get("id")

    def link_azuracast_id_to_emby(self, emby_api_key, emby_server_url, emby_track_id, azuracast_id):
        """Links Azuracast ID back to Emby by adding a custom field to the track.

        Args:
            emby_api_key (str): API key for Emby.
            emby_server_url (str): Base URL of the Emby server.
            emby_track_id (str): ID of the track in Emby.
            azuracast_id (str): ID of the track in Azuracast.

        Returns:
            bool: True if the custom field was successfully added, False otherwise.
        """
        endpoint = f"{emby_server_url}/Items/{emby_track_id}?api_key={emby_api_key}"
        headers = {"Content-Type": "application/json"}
        json_body = {
            "CustomFields": [
                {
                    "Name": "AzuraCastID",
                    "Value": azuracast_id
                }
            ]
        }

        try:
            response = self.session.post(endpoint, headers=headers, json=json_body, timeout=10)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to link Azuracast ID to Emby: {e}")
            return False
