"""HTTP client for Subsonic API v1.16.1."""

import asyncio
import logging
import time
from collections import deque
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import httpx

from .auth import create_auth_params, generate_token
from .exceptions import (
    ClientVersionTooOldError,
    ServerVersionTooOldError,
    SubsonicAuthenticationError,
    SubsonicAuthorizationError,
    SubsonicError,
    SubsonicNotFoundError,
    SubsonicParameterError,
    SubsonicTrialError,
    SubsonicVersionError,
    TokenAuthenticationNotSupportedError,
)
from .models import SubsonicConfig, SubsonicTrack

logger = logging.getLogger(__name__)


class SubsonicClient:
    """Synchronous HTTP client for Subsonic API v1.16.1.

    This client implements the Subsonic REST API with:
    - Token-based authentication (MD5 salt+hash)
    - Comprehensive error handling with typed exceptions
    - Connection pooling and timeout configuration
    - Pagination support for large libraries
    - Binary streaming for audio files

    Attributes:
        config: SubsonicConfig with server connection details
        client: httpx.Client for HTTP requests

    Example:
        >>> config = SubsonicConfig(
        ...     url="https://music.example.com",
        ...     username="john",
        ...     password="secret"
        ... )
        >>> client = SubsonicClient(config)
        >>> if client.ping():
        ...     tracks = client.get_all_songs(size=100)
        ...     print(f"Found {len(tracks)} tracks")
        >>> client.close()
    """

    def __init__(self, config: SubsonicConfig, rate_limit: Optional[int] = None):
        """Initialize Subsonic API client.

        Args:
            config: SubsonicConfig with server URL and credentials
            rate_limit: Optional maximum requests per second (default: None, no limit)

        Raises:
            ValueError: If config is invalid
        """
        self.config = config
        self._base_url = config.url.rstrip("/")

        # OpenSubsonic detection attributes
        self.opensubsonic = False
        self.opensubsonic_version = None

        # Rate limiting
        self.rate_limit = rate_limit
        self._request_times: deque = deque(maxlen=100) if rate_limit else None

        # Configure HTTP client with connection pooling and timeouts
        transport = httpx.HTTPTransport(
            limits=httpx.Limits(
                max_connections=100,  # Max total connections
                max_keepalive_connections=20,  # Max persistent connections
                keepalive_expiry=5.0,  # Keep connections alive for 5s
            ),
            retries=3,  # Automatic retries for network errors
        )

        # Try to enable HTTP/2 if available, fallback to HTTP/1.1
        try:
            self.client = httpx.Client(
                base_url=self._base_url,
                timeout=httpx.Timeout(
                    connect=30.0,  # 30s connection timeout
                    read=60.0,  # 60s read timeout (for large responses)
                    write=30.0,  # 30s write timeout
                    pool=5.0,  # 5s pool acquisition timeout
                ),
                transport=transport,
                follow_redirects=True,
                http2=True,  # Enable HTTP/2 for better performance
            )
        except ImportError:
            # h2 package not installed, use HTTP/1.1
            logger.debug("HTTP/2 not available, using HTTP/1.1")
            self.client = httpx.Client(
                base_url=self._base_url,
                timeout=httpx.Timeout(
                    connect=30.0,  # 30s connection timeout
                    read=60.0,  # 60s read timeout (for large responses)
                    write=30.0,  # 30s write timeout
                    pool=5.0,  # 5s pool acquisition timeout
                ),
                transport=transport,
                follow_redirects=True,
            )

        logger.info(f"Initialized Subsonic client for {self._base_url}")
        if rate_limit:
            logger.info(f"Rate limiting enabled: {rate_limit} requests/second")

    def _apply_rate_limit(self):
        """Apply rate limiting before making a request.

        If rate_limit is set, ensures requests don't exceed the specified
        rate per second. Uses a sliding window approach to track request times.
        """
        if not self.rate_limit or self._request_times is None:
            return

        now = time.time()

        # Remove requests older than 1 second
        while self._request_times and now - self._request_times[0] > 1.0:
            self._request_times.popleft()

        # If at rate limit, sleep until oldest request is > 1 second old
        if len(self._request_times) >= self.rate_limit:
            sleep_time = 1.0 - (now - self._request_times[0])
            if sleep_time > 0:
                logger.debug(f"Rate limit reached, sleeping for {sleep_time:.3f}s")
                time.sleep(sleep_time)
                # Remove old requests after sleep
                now = time.time()
                while self._request_times and now - self._request_times[0] > 1.0:
                    self._request_times.popleft()

        # Record this request
        self._request_times.append(time.time())

    def _build_url(self, endpoint: str) -> str:
        """Build full URL for API endpoint.

        Args:
            endpoint: API endpoint path (e.g., "ping", "getSong")

        Returns:
            Full URL with /rest/ prefix
        """
        return urljoin(self._base_url, f"/rest/{endpoint}")

    def _get_auth_params(self) -> Dict[str, str]:
        """Get authentication parameters for API request.

        Supports both token-based (MD5) and API key authentication.

        Returns:
            Dictionary with authentication parameters:
            - Token auth: u, t, s
            - API key auth: u, k (OpenSubsonic)
        """
        # Use API key authentication if available (OpenSubsonic)
        if self.config.api_key:
            return {
                "u": self.config.username,
                "k": self.config.api_key,
            }

        # Fall back to token authentication
        auth_token = generate_token(self.config)
        return auth_token.to_auth_params()

    def _build_params(self, **kwargs) -> Dict[str, str]:
        """Build query parameters with authentication and API version.

        Args:
            **kwargs: Additional endpoint-specific parameters

        Returns:
            Complete parameter dictionary for API request
        """
        params = {
            "v": self.config.api_version,
            "c": self.config.client_name,
            "f": "json",  # Request JSON response format
        }

        # Add authentication parameters
        params.update(self._get_auth_params())

        # Add endpoint-specific parameters
        for key, value in kwargs.items():
            if value is not None:
                params[key] = str(value)

        return params

    def _handle_response(self, response: httpx.Response, expect_binary: bool = False) -> dict:
        """Parse and validate Subsonic API response.

        Args:
            response: HTTP response from Subsonic server
            expect_binary: If True, check for unexpected JSON/XML when binary expected

        Returns:
            Parsed response data

        Raises:
            SubsonicError: If API returned an error response
            SubsonicAuthenticationError: For authentication failures (40, 41)
            TokenAuthenticationNotSupportedError: For token auth not supported (42)
            ClientVersionTooOldError: For client version too old (43)
            ServerVersionTooOldError: For server version too old (44)
            SubsonicAuthorizationError: For authorization failures (50)
            SubsonicNotFoundError: For missing resources (70)
            SubsonicVersionError: For version incompatibility (20, 30)
            SubsonicParameterError: For missing parameters (10)
            SubsonicTrialError: For trial expiration (60)
            httpx.HTTPStatusError: For HTTP-level errors
        """
        # If we expect binary but got XML/JSON, it's an error response
        content_type = response.headers.get("content-type", "")
        if expect_binary and content_type.startswith(("text/xml", "application/json")):
            logger.warning(f"Expected binary response but got {content_type}")
            # Parse error from XML/JSON response and raise appropriate exception
            # (will fall through to normal error handling below)

        # Raise for HTTP errors (4xx, 5xx)
        response.raise_for_status()

        # Parse JSON response
        data = response.json()
        subsonic_response = data.get("subsonic-response", {})

        # Check API-level status
        if subsonic_response.get("status") == "failed":
            error = subsonic_response.get("error", {})
            code = error.get("code", 0)
            message = error.get("message", "Unknown error")

            logger.error(f"Subsonic API error {code}: {message}")

            # Map error codes to specific exception types
            if code in (40, 41):
                raise SubsonicAuthenticationError(code, message)
            elif code == 42:
                raise TokenAuthenticationNotSupportedError(code, message)
            elif code == 43:
                raise ClientVersionTooOldError(code, message)
            elif code == 44:
                raise ServerVersionTooOldError(code, message)
            elif code == 50:
                raise SubsonicAuthorizationError(code, message)
            elif code == 70:
                raise SubsonicNotFoundError(code, message)
            elif code in (20, 30):
                raise SubsonicVersionError(code, message)
            elif code == 10:
                raise SubsonicParameterError(code, message)
            elif code == 60:
                raise SubsonicTrialError(code, message)
            else:
                raise SubsonicError(code, message)

        return subsonic_response

    def ping(self) -> bool:
        """Test server connectivity and authentication.

        This method validates that:
        - Server is reachable
        - Credentials are correct
        - API version is compatible
        - Detects OpenSubsonic support

        Returns:
            True if ping successful

        Raises:
            SubsonicAuthenticationError: If credentials are invalid
            SubsonicVersionError: If API version incompatible
            httpx.HTTPError: For network/HTTP errors

        Example:
            >>> client = SubsonicClient(config)
            >>> if client.ping():
            ...     print("Connected successfully!")
        """
        url = self._build_url("ping")
        params = self._build_params()

        logger.debug(f"Pinging Subsonic server at {self._base_url}")
        self._apply_rate_limit()
        response = self.client.get(url, params=params)
        data = self._handle_response(response)

        # Check for OpenSubsonic
        if "openSubsonic" in data and isinstance(data["openSubsonic"], dict):
            self.opensubsonic = True
            self.opensubsonic_version = data["openSubsonic"].get("serverVersion")
            logger.info(f"OpenSubsonic server detected: version {self.opensubsonic_version}")
        else:
            self.opensubsonic = False
            self.opensubsonic_version = None

        logger.info("Subsonic ping successful")
        return True

    # DEPRECATED: getSongs endpoint is not supported on all Subsonic servers (e.g., Navidrome)
    # Use ID3 browsing methods instead: get_artists() -> get_artist() -> get_album()
    #
    # def get_all_songs(self, offset: int = 0, size: int = 500) -> List[SubsonicTrack]:
    #     """Fetch songs from server with pagination support.
    #
    #     WARNING: This method uses the getSongs endpoint which is NOT supported by all
    #     Subsonic-compatible servers (e.g., Navidrome). Use ID3 browsing methods instead:
    #     get_artists() -> get_artist() -> get_album()
    #
    #     This uses the getSongs endpoint to retrieve tracks. For large libraries,
    #     call multiple times with different offsets to fetch all tracks.
    #
    #     Args:
    #         offset: Starting position in result set (0-based)
    #         size: Maximum number of songs to return (default: 500, max: 500)
    #
    #     Returns:
    #         List of SubsonicTrack objects
    #
    #     Raises:
    #         SubsonicAuthenticationError: If credentials are invalid
    #         SubsonicParameterError: If parameters are invalid
    #         httpx.HTTPError: For network/HTTP errors
    #
    #     Example:
    #         >>> # Fetch first 500 tracks
    #         >>> tracks = client.get_all_songs(offset=0, size=500)
    #         >>> print(f"Fetched {len(tracks)} tracks")
    #         >>>
    #         >>> # Fetch next 500 tracks
    #         >>> more_tracks = client.get_all_songs(offset=500, size=500)
    #     """
    #     url = self._build_url("getSongs")
    #     params = self._build_params(
    #         type="alphabeticalByName",  # Sort alphabetically
    #         size=min(size, 500),  # Enforce max size of 500
    #         offset=offset,
    #     )
    #
    #     logger.debug(f"Fetching songs: offset={offset}, size={size}")
    #     response = self.client.get(url, params=params)
    #     data = self._handle_response(response)
    #
    #     # Extract song list from response
    #     # Response structure: {"subsonic-response": {"songs": {"song": [...]}}}
    #     songs_container = data.get("songs", {})
    #     songs_data = songs_container.get("song", [])
    #
    #     # Handle case where response is directly a list
    #     if isinstance(songs_container, list):
    #         songs_data = songs_container
    #
    #     # Convert to SubsonicTrack objects
    #     tracks = []
    #     for song in songs_data:
    #         try:
    #             track = SubsonicTrack(
    #                 id=song["id"],
    #                 title=song["title"],
    #                 artist=song.get("artist", "Unknown Artist"),
    #                 album=song.get("album", "Unknown Album"),
    #                 duration=song.get("duration", 0),
    #                 path=song.get("path", ""),
    #                 suffix=song.get("suffix", "mp3"),
    #                 created=song.get("created", ""),
    #                 genre=song.get("genre"),
    #                 track=song.get("track"),
    #                 discNumber=song.get("discNumber"),
    #                 year=song.get("year"),
    #                 musicBrainzId=song.get("musicBrainzId"),
    #                 coverArt=song.get("coverArt"),
    #                 size=song.get("size"),
    #                 bitRate=song.get("bitRate"),
    #                 contentType=song.get("contentType"),
    #             )
    #             tracks.append(track)
    #         except KeyError as e:
    #             logger.warning(f"Skipping track with missing field: {e}")
    #             continue
    #
    #     logger.info(f"Retrieved {len(tracks)} tracks")
    #     return tracks

    def get_random_songs(self, size: int = 10) -> List[SubsonicTrack]:
        """Fetch random songs from server (Navidrome-compatible).

        This uses the getRandomSongs endpoint which is widely supported.
        For Navidrome servers, this is more reliable than getSongs.

        Args:
            size: Number of songs to return (default: 10, max: 500)

        Returns:
            List of SubsonicTrack objects

        Raises:
            SubsonicAuthenticationError: If credentials are invalid
            SubsonicParameterError: If parameters are invalid
            httpx.HTTPError: For network/HTTP errors

        Example:
            >>> tracks = client.get_random_songs(size=10)
            >>> print(f"Fetched {len(tracks)} random tracks")
        """
        url = self._build_url("getRandomSongs")
        params = self._build_params(size=min(size, 500))

        logger.debug(f"Fetching {size} random songs")
        self._apply_rate_limit()
        response = self.client.get(url, params=params)
        data = self._handle_response(response)

        # Extract song list from response
        songs_container = data.get("randomSongs", {})
        songs_data = songs_container.get("song", [])

        # Handle case where response is directly a list
        if isinstance(songs_container, list):
            songs_data = songs_container

        # Convert to SubsonicTrack objects
        tracks = []
        for song in songs_data:
            try:
                track = SubsonicTrack(
                    id=song["id"],
                    title=song["title"],
                    artist=song.get("artist", "Unknown Artist"),
                    album=song.get("album", "Unknown Album"),
                    duration=song.get("duration", 0),
                    path=song.get("path", ""),
                    suffix=song.get("suffix", "mp3"),
                    created=song.get("created", ""),
                    genre=song.get("genre"),
                    track=song.get("track"),
                    discNumber=song.get("discNumber"),
                    year=song.get("year"),
                    musicBrainzId=song.get("musicBrainzId"),
                    coverArt=song.get("coverArt"),
                    size=song.get("size"),
                    bitRate=song.get("bitRate"),
                    contentType=song.get("contentType"),
                )
                tracks.append(track)
            except KeyError as e:
                logger.warning(f"Skipping track with missing field: {e}")
                continue

        logger.info(f"Retrieved {len(tracks)} random tracks")
        return tracks

    def stream_track(self, track_id: str) -> bytes:
        """Download audio file for a track.

        This fetches the raw audio data for streaming or local playback.
        The format depends on the server's transcoding settings.

        Args:
            track_id: Unique identifier for the track

        Returns:
            Raw audio file bytes

        Raises:
            SubsonicNotFoundError: If track_id does not exist
            SubsonicAuthenticationError: If credentials are invalid
            httpx.HTTPError: For network/HTTP errors

        Example:
            >>> audio_data = client.stream_track("12345")
            >>> with open("track.mp3", "wb") as f:
            ...     f.write(audio_data)
        """
        url = self._build_url("stream")
        params = self._build_params(id=track_id)

        logger.debug(f"Streaming track: {track_id}")
        self._apply_rate_limit()
        response = self.client.get(url, params=params)

        # For stream endpoint, check if we got JSON error response
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            # This is an error response
            self._handle_response(response)
        else:
            # Binary audio data - just check HTTP status
            response.raise_for_status()

        logger.info(f"Downloaded {len(response.content)} bytes for track {track_id}")
        return response.content

    def get_stream_url(self, track_id: str) -> str:
        """Get streaming URL for a track without downloading.

        This generates a URL that can be used directly in M3U playlists
        or media players. The URL includes authentication parameters.

        Args:
            track_id: Unique identifier for the track

        Returns:
            Complete streaming URL with authentication

        Example:
            >>> url = client.get_stream_url("12345")
            >>> print(url)
            https://music.example.com/rest/stream?id=12345&u=john&t=...&s=...
        """
        url = self._build_url("stream")
        params = self._build_params(id=track_id)

        # Build URL with query parameters
        param_str = "&".join(f"{k}={v}" for k, v in params.items())
        stream_url = f"{url}?{param_str}"

        logger.debug(f"Generated stream URL for track {track_id}")
        return stream_url

    def close(self):
        """Close HTTP client and release resources.

        This should be called when done using the client to properly
        clean up connections.

        Example:
            >>> client = SubsonicClient(config)
            >>> try:
            ...     tracks = client.get_all_songs()
            ... finally:
            ...     client.close()
        """
        self.client.close()
        logger.info("Closed Subsonic client")

    def __enter__(self):
        """Context manager entry.

        Example:
            >>> with SubsonicClient(config) as client:
            ...     tracks = client.get_all_songs()
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - automatically close client."""
        self.close()

    def get_artists(self, music_folder_id: Optional[str] = None) -> List:
        """Get all artists using ID3 browsing (getArtists endpoint).

        Args:
            music_folder_id: Optional music folder ID to filter artists

        Returns:
            List of artist dictionaries with id, name, albumCount fields

        Raises:
            SubsonicError: If API returns error response

        Example:
            >>> artists = client.get_artists()
            >>> print(f"Found {len(artists)} artists")
        """
        url = self._build_url("getArtists")
        params = self._build_params()
        if music_folder_id:
            params["musicFolderId"] = music_folder_id

        logger.debug(f"Fetching artists (folder={music_folder_id})")
        response = self.client.get(url, params=params)
        data = self._handle_response(response)

        # Parse artists from response['artists']['index']
        artists = []
        if "artists" in data and "index" in data["artists"]:
            for index in data["artists"]["index"]:
                if "artist" in index:
                    artists.extend(index["artist"])

        logger.info(f"Retrieved {len(artists)} artists")
        return artists

    def get_artist(self, artist_id: str) -> Dict:
        """Get artist details with albums (getArtist endpoint).

        Args:
            artist_id: Artist ID from getArtists

        Returns:
            Artist dictionary with album array

        Raises:
            SubsonicError: If API returns error or artist not found

        Example:
            >>> artist = client.get_artist("123")
            >>> print(f"{artist['name']} has {len(artist['album'])} albums")
        """
        url = self._build_url("getArtist")
        params = self._build_params(id=artist_id)

        logger.debug(f"Fetching artist: {artist_id}")
        self._apply_rate_limit()
        response = self.client.get(url, params=params)
        data = self._handle_response(response)

        # Return artist data with album array
        if "artist" in data:
            logger.info(f"Retrieved artist {artist_id}")
            return data["artist"]

        raise SubsonicError(0, f"Artist {artist_id} not found in response")

    def get_album(self, album_id: str) -> List[SubsonicTrack]:
        """Get album tracks (getAlbum endpoint).

        Args:
            album_id: Album ID from getArtist

        Returns:
            List of SubsonicTrack objects with all critical fields

        Raises:
            SubsonicError: If API returns error or album not found

        Example:
            >>> tracks = client.get_album("456")
            >>> print(f"Album has {len(tracks)} tracks")
        """
        url = self._build_url("getAlbum")
        params = self._build_params(id=album_id)

        logger.debug(f"Fetching album: {album_id}")
        self._apply_rate_limit()
        response = self.client.get(url, params=params)
        data = self._handle_response(response)

        # Parse songs array, filter isVideo=false
        tracks = []
        if "album" in data and "song" in data["album"]:
            for song_data in data["album"]["song"]:
                # Filter out video content
                if song_data.get("isVideo", False):
                    logger.debug(f"Skipping video: {song_data.get('title', 'Unknown')}")
                    continue

                try:
                    # Create SubsonicTrack with all critical fields
                    track = SubsonicTrack(
                        id=song_data["id"],
                        title=song_data.get("title", ""),
                        artist=song_data.get("artist", ""),
                        album=song_data.get("album", ""),
                        duration=song_data.get("duration", 0),
                        path=song_data.get("path", ""),
                        suffix=song_data.get("suffix", "mp3"),
                        created=song_data.get("created", ""),
                        # Critical ID3 fields
                        parent=song_data.get("parent"),
                        albumId=song_data.get("albumId"),
                        artistId=song_data.get("artistId"),
                        isDir=song_data.get("isDir", False),
                        isVideo=song_data.get("isVideo", False),
                        type=song_data.get("type"),
                        # Optional fields
                        genre=song_data.get("genre"),
                        track=song_data.get("track"),
                        discNumber=song_data.get("discNumber"),
                        year=song_data.get("year"),
                        musicBrainzId=song_data.get("musicBrainzId"),
                        coverArt=song_data.get("coverArt"),
                        size=song_data.get("size"),
                        bitRate=song_data.get("bitRate"),
                        contentType=song_data.get("contentType"),
                    )
                    tracks.append(track)
                except KeyError as e:
                    logger.warning(f"Skipping track with missing required field: {e}")
                    continue

        logger.info(f"Retrieved {len(tracks)} tracks from album {album_id}")
        return tracks

    def get_song(self, song_id: str) -> Optional[SubsonicTrack]:
        """Get single song metadata by ID (getSong endpoint).

        Args:
            song_id: Unique song/track identifier

        Returns:
            SubsonicTrack object with full metadata or None if not found

        Raises:
            SubsonicNotFoundError: If song_id does not exist
            SubsonicAuthenticationError: If credentials are invalid
            httpx.HTTPError: For network/HTTP errors

        Example:
            >>> track = client.get_song("abc123")
            >>> if track:
            ...     print(f"{track.artist} - {track.title}")
        """
        url = self._build_url("getSong")
        params = self._build_params(id=song_id)

        logger.debug(f"Fetching song: {song_id}")
        self._apply_rate_limit()
        response = self.client.get(url, params=params)
        data = self._handle_response(response)

        # Parse song data
        if "song" not in data:
            logger.warning(f"Song {song_id} not found in response")
            return None

        song_data = data["song"]

        # Filter out video content
        if song_data.get("isVideo", False):
            logger.debug(f"Skipping video: {song_data.get('title', 'Unknown')}")
            return None

        try:
            track = SubsonicTrack(
                id=song_data["id"],
                title=song_data.get("title", ""),
                artist=song_data.get("artist", "Unknown Artist"),
                album=song_data.get("album", "Unknown Album"),
                duration=song_data.get("duration", 0),
                path=song_data.get("path", ""),
                suffix=song_data.get("suffix", "mp3"),
                created=song_data.get("created", ""),
                # Critical ID3 fields
                parent=song_data.get("parent"),
                albumId=song_data.get("albumId"),
                artistId=song_data.get("artistId"),
                isDir=song_data.get("isDir", False),
                isVideo=song_data.get("isVideo", False),
                type=song_data.get("type"),
                # Optional fields
                genre=song_data.get("genre"),
                track=song_data.get("track"),
                discNumber=song_data.get("discNumber"),
                year=song_data.get("year"),
                musicBrainzId=song_data.get("musicBrainzId"),
                coverArt=song_data.get("coverArt"),
                size=song_data.get("size"),
                bitRate=song_data.get("bitRate"),
                contentType=song_data.get("contentType"),
            )
            logger.info(f"Retrieved song {song_id}: {track.artist} - {track.title}")
            return track
        except KeyError as e:
            logger.warning(f"Song {song_id} missing required field: {e}")
            return None

    def download_track(self, track_id: str) -> bytes:
        """Download original file using download endpoint.

        Args:
            track_id: Track ID to download

        Returns:
            Binary audio file content

        Raises:
            SubsonicError: If API returns error response
            httpx.HTTPError: If download fails

        Example:
            >>> audio_data = client.download_track("789")
            >>> with open("track.flac", "wb") as f:
            ...     f.write(audio_data)
        """
        url = self._build_url("download")
        params = self._build_params(id=track_id)

        logger.debug(f"Downloading track: {track_id}")
        self._apply_rate_limit()
        response = self.client.get(url, params=params)

        # Check for error response (XML/JSON instead of binary)
        content_type = response.headers.get("content-type", "")
        if content_type.startswith(("text/xml", "application/json")):
            self._handle_response(response, expect_binary=True)  # Will raise SubsonicError

        response.raise_for_status()
        logger.info(f"Downloaded {len(response.content)} bytes for track {track_id}")
        return response.content

    def get_music_folders(self) -> List[Dict]:
        """Get all configured music folders.

        This retrieves the list of music library folders configured on the server.
        Each folder represents a top-level music collection that can be browsed
        independently.

        Returns:
            List of music folder dictionaries with id and name fields

        Raises:
            SubsonicAuthenticationError: If credentials are invalid
            httpx.HTTPError: For network/HTTP errors

        Example:
            >>> folders = client.get_music_folders()
            >>> for folder in folders:
            ...     print(f"Folder: {folder['name']} (ID: {folder['id']})")
        """
        url = self._build_url("getMusicFolders")
        params = self._build_params()

        logger.debug("Fetching music folders")
        self._apply_rate_limit()
        response = self.client.get(url, params=params)
        data = self._handle_response(response)

        folders = data.get("musicFolders", {}).get("musicFolder", [])
        logger.info(f"Retrieved {len(folders)} music folders")
        return folders

    def get_genres(self) -> List[Dict]:
        """Get all genres from the music library.

        This retrieves all unique genres found in the music library,
        along with counts of songs and albums for each genre.

        Returns:
            List of genre dictionaries with genre name, songCount, and albumCount

        Raises:
            SubsonicAuthenticationError: If credentials are invalid
            httpx.HTTPError: For network/HTTP errors

        Example:
            >>> genres = client.get_genres()
            >>> for genre in genres:
            ...     print(f"{genre['value']}: {genre['songCount']} songs")
        """
        url = self._build_url("getGenres")
        params = self._build_params()

        logger.debug("Fetching genres")
        self._apply_rate_limit()
        response = self.client.get(url, params=params)
        data = self._handle_response(response)

        genres = data.get("genres", {}).get("genre", [])
        logger.info(f"Retrieved {len(genres)} genres")
        return genres

    def get_scan_status(self) -> Dict:
        """Get library scan status.

        This checks whether the server is currently scanning the music library
        and returns the scan progress if a scan is in progress.

        Returns:
            Dictionary with scanning status (true/false) and count if scanning

        Raises:
            SubsonicAuthenticationError: If credentials are invalid
            httpx.HTTPError: For network/HTTP errors

        Example:
            >>> status = client.get_scan_status()
            >>> if status.get('scanning'):
            ...     print(f"Scan in progress: {status.get('count', 0)} items")
            >>> else:
            ...     print("No scan in progress")
        """
        url = self._build_url("getScanStatus")
        params = self._build_params()

        logger.debug("Fetching scan status")
        self._apply_rate_limit()
        response = self.client.get(url, params=params)
        data = self._handle_response(response)

        scan_status = data.get("scanStatus", {})
        logger.info(f"Scan status: {scan_status}")
        return scan_status

    def search3(
        self,
        query: str,
        artist_count: int = 20,
        album_count: int = 20,
        song_count: int = 20,
    ) -> Dict:
        """Search for artists, albums, and songs using search3 endpoint.

        This provides a unified search across all media types. Results are
        organized by type and ranked by relevance.

        Args:
            query: Search query string
            artist_count: Maximum number of artists to return (default: 20)
            album_count: Maximum number of albums to return (default: 20)
            song_count: Maximum number of songs to return (default: 20)

        Returns:
            Dictionary with searchResult3 containing:
            - artist: List of matching artists
            - album: List of matching albums
            - song: List of matching songs

        Raises:
            SubsonicAuthenticationError: If credentials are invalid
            SubsonicParameterError: If query is empty
            httpx.HTTPError: For network/HTTP errors

        Example:
            >>> results = client.search3("beatles", song_count=10)
            >>> artists = results.get('searchResult3', {}).get('artist', [])
            >>> print(f"Found {len(artists)} matching artists")
        """
        url = self._build_url("search3")
        params = self._build_params(
            query=query,
            artistCount=artist_count,
            albumCount=album_count,
            songCount=song_count,
        )

        logger.debug(
            f"Searching for '{query}' (artists={artist_count}, "
            f"albums={album_count}, songs={song_count})"
        )
        response = self.client.get(url, params=params)
        data = self._handle_response(response)

        logger.info(f"Search completed for query: {query}")
        return data

    def get_playlists(self, username: Optional[str] = None) -> List[Dict]:
        """Get all playlists for user.

        This retrieves metadata for all playlists accessible to the user.
        Use get_playlist() to fetch full playlist details with tracks.

        Args:
            username: Optional username to get playlists for (requires admin)

        Returns:
            List of playlist dictionaries with id, name, owner, songCount, etc.

        Raises:
            SubsonicAuthenticationError: If credentials are invalid
            SubsonicAuthorizationError: If username specified without admin rights
            httpx.HTTPError: For network/HTTP errors

        Example:
            >>> playlists = client.get_playlists()
            >>> for p in playlists:
            ...     print(f"{p['name']}: {p['songCount']} tracks")
        """
        url = self._build_url("getPlaylists")
        params = self._build_params()
        if username:
            params["username"] = username

        logger.debug(f"Fetching playlists (username={username})")
        response = self.client.get(url, params=params)
        data = self._handle_response(response)

        # Extract playlist array from response
        playlists = data.get("playlists", {}).get("playlist", [])
        logger.info(f"Retrieved {len(playlists)} playlists")
        return playlists

    def get_playlist(self, playlist_id: str) -> List[SubsonicTrack]:
        """Get playlist with full track details.

        This fetches a playlist with all its tracks. The tracks include
        complete metadata suitable for playback or M3U generation.

        Args:
            playlist_id: Unique playlist identifier from get_playlists()

        Returns:
            List of SubsonicTrack objects for all tracks in playlist

        Raises:
            SubsonicNotFoundError: If playlist_id does not exist
            SubsonicAuthenticationError: If credentials are invalid
            httpx.HTTPError: For network/HTTP errors

        Example:
            >>> tracks = client.get_playlist("123")
            >>> print(f"Playlist has {len(tracks)} tracks")
            >>> for track in tracks:
            ...     print(f"{track.artist} - {track.title}")
        """
        url = self._build_url("getPlaylist")
        params = self._build_params(id=playlist_id)

        logger.debug(f"Fetching playlist: {playlist_id}")
        self._apply_rate_limit()
        response = self.client.get(url, params=params)
        data = self._handle_response(response)

        # Parse entry array into SubsonicTrack list
        tracks = []
        if "playlist" in data and "entry" in data["playlist"]:
            for song_data in data["playlist"]["entry"]:
                try:
                    track = SubsonicTrack(
                        id=song_data["id"],
                        title=song_data.get("title", ""),
                        artist=song_data.get("artist", ""),
                        album=song_data.get("album", ""),
                        duration=song_data.get("duration", 0),
                        path=song_data.get("path", ""),
                        suffix=song_data.get("suffix", "mp3"),
                        created=song_data.get("created", ""),
                        # Include all other fields as in get_album
                        parent=song_data.get("parent"),
                        albumId=song_data.get("albumId"),
                        artistId=song_data.get("artistId"),
                        isDir=song_data.get("isDir", False),
                        isVideo=song_data.get("isVideo", False),
                        type=song_data.get("type"),
                        genre=song_data.get("genre"),
                        track=song_data.get("track"),
                        discNumber=song_data.get("discNumber"),
                        year=song_data.get("year"),
                        musicBrainzId=song_data.get("musicBrainzId"),
                        coverArt=song_data.get("coverArt"),
                        size=song_data.get("size"),
                        bitRate=song_data.get("bitRate"),
                        contentType=song_data.get("contentType"),
                    )
                    tracks.append(track)
                except KeyError as e:
                    logger.warning(f"Skipping track with missing field: {e}")
                    continue

        logger.info(f"Retrieved {len(tracks)} tracks from playlist {playlist_id}")
        return tracks

    def get_cover_art(self, cover_art_id: str, size: Optional[int] = None) -> bytes:
        """Download cover art image for album/artist/track.

        This fetches cover art images which can be embedded in M3U playlists
        or displayed in media players. The image format depends on server
        configuration (usually JPEG or PNG).

        Args:
            cover_art_id: Cover art identifier from track/album/artist metadata
            size: Optional size in pixels to scale image (maintains aspect ratio)

        Returns:
            Binary image data (JPEG/PNG)

        Raises:
            SubsonicNotFoundError: If cover_art_id does not exist
            SubsonicAuthenticationError: If credentials are invalid
            httpx.HTTPError: For network/HTTP errors

        Example:
            >>> # Get cover art from track metadata
            >>> track = client.get_album("456")[0]
            >>> if track.coverArt:
            ...     img_data = client.get_cover_art(track.coverArt, size=300)
            ...     with open("cover.jpg", "wb") as f:
            ...         f.write(img_data)
        """
        url = self._build_url("getCoverArt")
        params = self._build_params(id=cover_art_id)
        if size:
            params["size"] = size

        logger.debug(f"Fetching cover art: {cover_art_id} (size={size})")
        response = self.client.get(url, params=params)

        # Check for error response (XML/JSON instead of binary)
        content_type = response.headers.get("content-type", "")
        if content_type.startswith(("text/xml", "application/json")):
            self._handle_response(response, expect_binary=True)  # Will raise SubsonicError

        response.raise_for_status()
        logger.info(f"Downloaded {len(response.content)} bytes of cover art {cover_art_id}")
        return response.content

    def star(self, item_id: str, item_type: str = "song") -> bool:
        """Star (favorite) an item (song, album, or artist).

        This marks an item as a favorite/starred. The item will appear in
        starred lists and can be retrieved with get_starred2().

        Args:
            item_id: ID of the item to star
            item_type: Type of item - "song", "album", or "artist" (default: "song")

        Returns:
            True if successfully starred

        Raises:
            SubsonicNotFoundError: If item_id does not exist
            SubsonicAuthenticationError: If credentials are invalid
            httpx.HTTPError: For network/HTTP errors

        Example:
            >>> client.star("track-123", "song")
            True
            >>> client.star("album-456", "album")
            True
        """
        url = self._build_url("star")

        # Map item type to parameter name
        param_name = {"song": "id", "album": "albumId", "artist": "artistId"}.get(item_type, "id")

        params = self._build_params(**{param_name: item_id})

        logger.debug(f"Starring {item_type}: {item_id}")
        self._apply_rate_limit()
        response = self.client.get(url, params=params)
        self._handle_response(response)

        logger.info(f"Successfully starred {item_type} {item_id}")
        return True

    def unstar(self, item_id: str, item_type: str = "song") -> bool:
        """Unstar (unfavorite) an item (song, album, or artist).

        This removes an item from favorites/starred. The item will no longer
        appear in starred lists.

        Args:
            item_id: ID of the item to unstar
            item_type: Type of item - "song", "album", or "artist" (default: "song")

        Returns:
            True if successfully unstarred

        Raises:
            SubsonicNotFoundError: If item_id does not exist
            SubsonicAuthenticationError: If credentials are invalid
            httpx.HTTPError: For network/HTTP errors

        Example:
            >>> client.unstar("track-123", "song")
            True
            >>> client.unstar("album-456", "album")
            True
        """
        url = self._build_url("unstar")

        # Map item type to parameter name
        param_name = {"song": "id", "album": "albumId", "artist": "artistId"}.get(item_type, "id")

        params = self._build_params(**{param_name: item_id})

        logger.debug(f"Unstarring {item_type}: {item_id}")
        self._apply_rate_limit()
        response = self.client.get(url, params=params)
        self._handle_response(response)

        logger.info(f"Successfully unstarred {item_type} {item_id}")
        return True

    def get_starred2(self) -> Dict:
        """Get starred songs, albums, and artists using ID3 tags.

        This returns all items that have been marked as favorites/starred
        by the authenticated user. Uses ID3 organization (recommended).

        Returns:
            Dictionary with starred items organized by type:
            - artist: List of starred artists
            - album: List of starred albums
            - song: List of starred songs (as SubsonicTrack objects)

        Raises:
            SubsonicAuthenticationError: If credentials are invalid
            httpx.HTTPError: For network/HTTP errors

        Example:
            >>> starred = client.get_starred2()
            >>> print(f"Starred songs: {len(starred.get('song', []))}")
            >>> print(f"Starred albums: {len(starred.get('album', []))}")
            >>> print(f"Starred artists: {len(starred.get('artist', []))}")
        """
        url = self._build_url("getStarred2")
        params = self._build_params()

        logger.debug("Fetching starred items (ID3)")
        response = self.client.get(url, params=params)
        data = self._handle_response(response)

        result = {"artist": [], "album": [], "song": []}

        if "starred2" in data:
            starred_data = data["starred2"]

            # Parse artists
            if "artist" in starred_data:
                result["artist"] = (
                    starred_data["artist"]
                    if isinstance(starred_data["artist"], list)
                    else [starred_data["artist"]]
                )

            # Parse albums
            if "album" in starred_data:
                result["album"] = (
                    starred_data["album"]
                    if isinstance(starred_data["album"], list)
                    else [starred_data["album"]]
                )

            # Parse songs as SubsonicTrack objects
            if "song" in starred_data:
                songs_data = (
                    starred_data["song"]
                    if isinstance(starred_data["song"], list)
                    else [starred_data["song"]]
                )

                tracks = []
                for song in songs_data:
                    try:
                        track = SubsonicTrack(
                            id=song["id"],
                            title=song.get("title", ""),
                            artist=song.get("artist", ""),
                            album=song.get("album", ""),
                            duration=song.get("duration", 0),
                            path=song.get("path", ""),
                            suffix=song.get("suffix", "mp3"),
                            created=song.get("created", ""),
                            parent=song.get("parent"),
                            albumId=song.get("albumId"),
                            artistId=song.get("artistId"),
                            isDir=song.get("isDir", False),
                            isVideo=song.get("isVideo", False),
                            type=song.get("type"),
                            genre=song.get("genre"),
                            track=song.get("track"),
                            discNumber=song.get("discNumber"),
                            year=song.get("year"),
                            musicBrainzId=song.get("musicBrainzId"),
                            coverArt=song.get("coverArt"),
                            size=song.get("size"),
                            bitRate=song.get("bitRate"),
                            contentType=song.get("contentType"),
                        )
                        tracks.append(track)
                    except KeyError as e:
                        logger.warning(f"Skipping starred track with missing field: {e}")
                        continue

                result["song"] = tracks

        logger.info(
            f"Retrieved {len(result['artist'])} starred artists, "
            f"{len(result['album'])} albums, {len(result['song'])} songs"
        )
        return result

    def scrobble(self, track_id: str, time: Optional[int] = None, submission: bool = True) -> bool:
        """Register song playback with Last.fm scrobbling.

        This endpoint submits a song play to Last.fm for scrobbling. The song
        must be played for at least 30 seconds or half its length (whichever
        comes first) to be scrobbled.

        Args:
            track_id: ID of the track that was played
            time: Unix timestamp (milliseconds) when playback started.
                  If None, uses current time.
            submission: If True, scrobble to Last.fm. If False, just update "now playing"

        Returns:
            True if successfully scrobbled

        Raises:
            SubsonicNotFoundError: If track_id does not exist
            SubsonicAuthenticationError: If credentials are invalid
            httpx.HTTPError: For network/HTTP errors

        Example:
            >>> import time
            >>> # Scrobble a track (user listened to it)
            >>> client.scrobble("track-123")
            True
            >>>
            >>> # Update "now playing" without scrobbling
            >>> client.scrobble("track-456", submission=False)
            True
        """
        url = self._build_url("scrobble")

        # Use current time if not provided
        if time is None:
            import time as time_module

            time = int(time_module.time() * 1000)  # Convert to milliseconds

        params = self._build_params(
            id=track_id,
            time=time,
            submission=str(submission).lower(),  # Convert bool to lowercase string
        )

        action = "Scrobbling" if submission else "Updating now playing for"
        logger.debug(f"{action} track: {track_id}")
        self._apply_rate_limit()
        response = self.client.get(url, params=params)
        self._handle_response(response)

        logger.info(f"Successfully {action.lower()} track {track_id}")
        return True

    def _parse_song_to_track(self, song_data: Dict) -> Optional[SubsonicTrack]:
        """Parse song dictionary to SubsonicTrack object.

        Args:
            song_data: Song dictionary from API response

        Returns:
            SubsonicTrack object or None if parsing fails

        Note:
            This is a helper method to ensure consistent track parsing
            across different API endpoints (search3, getRandomSongs, etc.)
        """
        try:
            # Filter out video content
            if song_data.get("isVideo", False):
                logger.debug(f"Skipping video: {song_data.get('title', 'Unknown')}")
                return None

            track = SubsonicTrack(
                id=song_data["id"],
                title=song_data.get("title", ""),
                artist=song_data.get("artist", "Unknown Artist"),
                album=song_data.get("album", "Unknown Album"),
                duration=song_data.get("duration", 0),
                path=song_data.get("path", ""),
                suffix=song_data.get("suffix", "mp3"),
                created=song_data.get("created", ""),
                # Critical ID3 fields
                parent=song_data.get("parent"),
                albumId=song_data.get("albumId"),
                artistId=song_data.get("artistId"),
                isDir=song_data.get("isDir", False),
                isVideo=song_data.get("isVideo", False),
                type=song_data.get("type"),
                # Optional fields
                genre=song_data.get("genre"),
                track=song_data.get("track"),
                discNumber=song_data.get("discNumber"),
                year=song_data.get("year"),
                musicBrainzId=song_data.get("musicBrainzId"),
                coverArt=song_data.get("coverArt"),
                size=song_data.get("size"),
                bitRate=song_data.get("bitRate"),
                contentType=song_data.get("contentType"),
            )
            return track
        except KeyError as e:
            logger.warning(f"Skipping track with missing required field: {e}")
            return None

    def search_tracks(
        self,
        query: str = "",
        limit: int = 500,
        genre_filter: Optional[List[str]] = None,
    ) -> List[SubsonicTrack]:
        """Search for tracks matching criteria.

        This is a high-level helper method for playlist generation that combines
        search3 (for query-based search) and getRandomSongs (for random selection).
        Supports optional genre filtering.

        Args:
            query: Search query string. If empty, returns random songs.
            limit: Maximum number of tracks to return (default: 500)
            genre_filter: Optional list of genres to filter by (e.g., ["Rock", "Pop"])

        Returns:
            List of SubsonicTrack objects matching criteria

        Raises:
            SubsonicAuthenticationError: If credentials are invalid
            SubsonicParameterError: If parameters are invalid
            httpx.HTTPError: For network/HTTP errors

        Example:
            >>> # Get random tracks
            >>> tracks = client.search_tracks(query="", limit=100)
            >>> print(f"Got {len(tracks)} random tracks")
            >>>
            >>> # Search for Beatles tracks
            >>> tracks = client.search_tracks(query="beatles", limit=50)
            >>>
            >>> # Get Electronic tracks only
            >>> tracks = client.search_tracks(
            ...     query="",
            ...     limit=200,
            ...     genre_filter=["Electronic", "Dance"]
            ... )
        """
        tracks = []

        # If no query, use random songs as base pool
        if not query:
            logger.debug(f"Fetching random tracks (limit={limit})")
            # getRandomSongs has max 500 per call, so may need multiple calls
            remaining = limit
            while remaining > 0 and len(tracks) < limit:
                batch_size = min(remaining, 500)
                batch = self.get_random_songs(size=batch_size)
                if not batch:
                    break  # No more tracks available
                tracks.extend(batch)
                remaining -= len(batch)
                # If we got fewer tracks than requested, server has no more
                if len(batch) < batch_size:
                    break
        else:
            # Use search3 for query-based search
            logger.debug(f"Searching for '{query}' (limit={limit})")
            self._apply_rate_limit()
            results = self.search3(query=query, song_count=min(limit, 500))

            # Extract songs from search results
            search_result = results.get("searchResult3", {})
            songs_data = search_result.get("song", [])

            # Parse songs to tracks
            for song_data in songs_data:
                track = self._parse_song_to_track(song_data)
                if track:
                    tracks.append(track)

        # Apply genre filter if specified
        if genre_filter:
            logger.debug(f"Applying genre filter: {genre_filter}")
            # Normalize genre names for case-insensitive matching
            normalized_filters = [g.lower() for g in genre_filter]
            filtered_tracks = []
            for track in tracks:
                if track.genre:
                    # Check if track genre matches any filter (case-insensitive)
                    if track.genre.lower() in normalized_filters:
                        filtered_tracks.append(track)
                    else:
                        # Also check for partial matches (e.g., "Electronic" in "Electronic Dance")
                        for filter_genre in normalized_filters:
                            if filter_genre in track.genre.lower():
                                filtered_tracks.append(track)
                                break
            tracks = filtered_tracks
            logger.info(
                f"Genre filter reduced tracks from {len(tracks)} to {len(filtered_tracks)}"
            )

        # Trim to requested limit
        tracks = tracks[:limit]

        logger.info(f"Retrieved {len(tracks)} tracks")
        return tracks

    # Async wrapper methods for async/await compatibility
    # These allow the synchronous SubsonicClient to be used in async contexts

    async def search_tracks_async(
        self,
        query: str = "",
        limit: int = 500,
        genre_filter: Optional[List[str]] = None,
    ) -> List[SubsonicTrack]:
        """Async wrapper for search_tracks().

        This method allows the synchronous search_tracks() to be used in async
        contexts by running it in a thread pool.

        Args:
            query: Search query string. If empty, returns random songs.
            limit: Maximum number of tracks to return (default: 500)
            genre_filter: Optional list of genres to filter by

        Returns:
            List of SubsonicTrack objects matching criteria

        Example:
            >>> tracks = await client.search_tracks_async(query="", limit=100)
        """
        return await asyncio.to_thread(
            self.search_tracks,
            query=query,
            limit=limit,
            genre_filter=genre_filter,
        )

    async def get_genres_async(self) -> List:
        """Async wrapper for get_genres().
        
        Returns:
            List of genre dictionaries
        """
        return await asyncio.to_thread(self.get_genres)
    
    async def get_artists_async(self, music_folder_id: Optional[str] = None) -> List:
        """Async wrapper for get_artists().
        
        Args:
            music_folder_id: Optional music folder ID to filter artists
            
        Returns:
            List of artist dictionaries
        """
        return await asyncio.to_thread(self.get_artists, music_folder_id=music_folder_id)
    
    async def get_newest_albums_async(self, size: int = 20) -> List:
        """Get newest albums (simplified - uses search with empty query).
        
        Args:
            size: Number of albums to return
            
        Returns:
            List of album dictionaries (simulated from tracks)
        """
        # Simplified: Just return empty list for now, or use search_tracks
        # In a real implementation, this would call the getNewestAlbums endpoint
        tracks = await self.search_tracks_async(query="", limit=size * 10)
        # Group by album and return unique albums
        albums_seen = set()
        albums = []
        for track in tracks:
            if track.album and track.album not in albums_seen:
                albums_seen.add(track.album)
                albums.append({"id": track.id, "name": track.album, "artist": track.artist})
                if len(albums) >= size:
                    break
        return albums
    
    async def get_album_tracks_async(self, album_id: str) -> List:
        """Get tracks for an album (simplified - searches by album name).
        
        Args:
            album_id: Album ID (or name for simplified version)
            
        Returns:
            List of tracks
        """
        # Simplified: Search for tracks matching this album
        # In real implementation, would use getAlbum endpoint
        tracks = await self.search_tracks_async(query=album_id, limit=50)
        return tracks
