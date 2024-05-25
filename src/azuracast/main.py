import os
import requests
import logging
from base64 import b64encode
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AzuraCastSync:
    """Client for interacting with the AzuraCast API for syncing playlists."""

    def __init__(self):
        """Initializes the AzuraCast client with environment variables."""
        self.host = os.getenv('AZURACAST_HOST')
        self.api_key = os.getenv('AZURACAST_API_KEY')
        self.station_id = os.getenv('AZURACAST_STATIONID')

    def _get_session(self):
        """Creates a new session with retry strategy."""
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

        MAX_ATTEMPTS = 6
        TIMEOUT = 240  # Increased timeout for larger file uploads

        for attempt in range(1, MAX_ATTEMPTS + 1):  # Retry up to 6 times
            session = None
            response = None  # Initialize the response variable to ensure it exists
            try:
                session = self._get_session()
                logger.debug(f"Attempt {attempt}: Making request to {url}")
                response = session.request(method, url, headers=headers, data=data, json=json, timeout=TIMEOUT)
                response.raise_for_status()

                if response.status_code == 413:
                    logger.warning(f"Attempt {attempt}: Request to {url} failed due to size limit. Retrying...")
                    time.sleep(2 ** attempt)
                    continue  # Retry on 413 error

                return response.json()

            except (requests.exceptions.SSLError, requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                logger.warning(f"Attempt {attempt}: Request to {url} failed: {e}. Retrying...")
                time.sleep(2 ** attempt)  # Exponential backoff

            except requests.exceptions.RequestException as e:
                # Check if response is available to avoid referencing a variable that might not be set
                response_text = response.text if response else "No response"
                logger.error(f"Attempt {attempt}: Request to {url} failed: {e} - Response: {response_text}")
                raise e  # Exit on non-retriable exceptions

            finally:
                if session:
                    session.close()  # Ensure session is closed after each attempt
            
        logger.error(f"Request to {url} failed after {MAX_ATTEMPTS} attempts")
        raise requests.exceptions.RequestException(f"Failed after {MAX_ATTEMPTS} attempts")

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
            str: ID of the uploaded file.
        """
        endpoint = f"/station/{self.station_id}/files"
        b64_content = b64encode(file_content).decode("utf-8")
        data = {"path": file_key, "file": b64_content}

        # Log file size in a readable format
        file_size = sizeof_fmt(len(file_content))
        logger.debug(f"Uploading file: {file_key}, Size: {file_size}")

        # Introduce a delay to avoid rate limiting issues
        time.sleep(1)

        return self._perform_request("POST", endpoint, json=data)

def sizeof_fmt(num, suffix='B'):
    """Convert file size to a readable format."""
    for unit in ['','K','M','G','T','P','E','Z']:
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Y{suffix}"