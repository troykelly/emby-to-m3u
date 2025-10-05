"""Integration tests for SubsonicClient.

These tests use pytest-mock to mock httpx.Client responses and validate
the SubsonicClient implementation against the Subsonic API specification.
All HTTP calls are mocked - no real server requests are made.

Test Coverage:
- Authentication (ping) success and failure
- Song retrieval with pagination
- Empty library handling
- Track streaming
- Error handling (404, timeouts)
"""

import json
from pathlib import Path
from typing import Any, Dict

import httpx
import pytest
from pytest_mock import MockerFixture

from src.subsonic.client import SubsonicClient
from src.subsonic.exceptions import (
    SubsonicAuthenticationError,
    SubsonicNotFoundError,
)
from src.subsonic.models import SubsonicConfig


# Fixture: Load response fixtures
@pytest.fixture
def fixtures() -> Dict[str, Any]:
    """Load Subsonic API response fixtures from JSON file.

    Returns:
        Dictionary containing all fixture responses
    """
    fixtures_path = Path(__file__).parent / "fixtures" / "subsonic_responses.json"
    with open(fixtures_path, "r") as f:
        return json.load(f)


# Fixture: Create SubsonicClient with test config
@pytest.fixture
def client(mocker: MockerFixture) -> SubsonicClient:
    """Create a SubsonicClient instance with test configuration.

    Mock the httpx.Client to avoid HTTP/2 dependency and network calls.

    Returns:
        Configured SubsonicClient for testing
    """
    config = SubsonicConfig(
        url="https://music.example.com",
        username="testuser",
        password="testpass",
        client_name="playlistgen-test",
        api_version="1.16.1",
    )

    # Mock httpx.Client to avoid HTTP/2 dependency
    mock_client = mocker.MagicMock(spec=httpx.Client)
    mocker.patch("httpx.Client", return_value=mock_client)

    return SubsonicClient(config)


# Fixture: Mock httpx.Response helper
def mock_response(status_code: int, json_data: Dict[str, Any]) -> httpx.Response:
    """Create a mock httpx.Response object.

    Args:
        status_code: HTTP status code
        json_data: JSON response body

    Returns:
        Mock httpx.Response with specified data
    """
    response = httpx.Response(
        status_code=status_code,
        json=json_data,
        request=httpx.Request("GET", "https://music.example.com/rest/ping"),
    )
    return response


class TestAuthentication:
    """Test cases for Subsonic authentication (ping endpoint)."""

    def test_ping_success(
        self, client: SubsonicClient, fixtures: Dict[str, Any], mocker: MockerFixture
    ):
        """Test successful authentication with valid credentials.

        Validates:
        - Client sends correct auth parameters (u, t, s)
        - Client properly handles successful ping response
        - Client returns True for successful auth
        """
        # Arrange: Mock successful ping response on the client's get method
        client.client.get = mocker.MagicMock(
            return_value=mock_response(200, fixtures["ping_success"])
        )

        # Act: Perform ping
        result = client.ping()

        # Assert: Verify success
        assert result is True

        # Verify request was made with correct params
        client.client.get.assert_called_once()
        call_args = client.client.get.call_args
        assert "params" in call_args.kwargs
        params = call_args.kwargs["params"]
        assert "u" in params
        assert "t" in params
        assert "s" in params
        assert params["c"] == "playlistgen-test"
        assert params["v"] == "1.16.1"
        assert params["f"] == "json"

    def test_ping_auth_failure(
        self, client: SubsonicClient, fixtures: Dict[str, Any], mocker: MockerFixture
    ):
        """Test authentication failure with wrong credentials.

        Validates:
        - Client handles 200 OK response with error code 40 in JSON
        - Client raises SubsonicAuthenticationError
        - Exception contains error code 40 and message from server
        """
        # Arrange: Mock auth failure response (200 OK with error in JSON)
        client.client.get = mocker.MagicMock(
            return_value=mock_response(200, fixtures["ping_auth_failure"])
        )

        # Act & Assert: Verify SubsonicAuthenticationError is raised
        with pytest.raises(SubsonicAuthenticationError) as exc_info:
            client.ping()

        # Verify error details
        error = exc_info.value
        assert error.code == 40
        assert "Wrong username or password" in error.message

    def test_ping_opensubsonic_detection(
        self, client: SubsonicClient, fixtures: Dict[str, Any], mocker: MockerFixture
    ):
        """Test OpenSubsonic server detection during ping.

        Validates:
        - Client detects OpenSubsonic server from ping response
        - opensubsonic attribute is set to True
        - opensubsonic_version is populated from response
        """
        # Arrange: Mock OpenSubsonic ping response
        client.client.get = mocker.MagicMock(
            return_value=mock_response(200, fixtures["ping_opensubsonic"])
        )

        # Act: Perform ping
        result = client.ping()

        # Assert: Verify OpenSubsonic detection
        assert result is True
        assert client.opensubsonic is True
        assert client.opensubsonic_version == "0.1.0"


class TestSongRetrieval:
    """Test cases for song/track retrieval operations using ID3 browsing."""

    def test_get_album_success(
        self, client: SubsonicClient, fixtures: Dict[str, Any], mocker: MockerFixture
    ):
        """Test fetching album tracks via get_album (ID3 browsing).

        Validates:
        - Client fetches album tracks correctly
        - Client properly parses song data from getAlbum response
        - Client returns List[SubsonicTrack] with critical ID3 fields
        - Client filters out video content (isVideo=false only)
        """
        # Arrange: Mock getAlbum response with 2 tracks
        album_response = fixtures["getAlbum_success"]

        client.client.get = mocker.MagicMock(
            return_value=mock_response(200, album_response)
        )

        # Act: Fetch album tracks
        tracks = client.get_album(album_id="200")

        # Assert: Verify we got the tracks
        assert len(tracks) == 2
        assert tracks[0].title == "Bohemian Rhapsody"
        assert tracks[0].artist == "Queen"
        assert tracks[0].id == "300"
        assert tracks[0].albumId == "200"
        assert tracks[0].artistId == "100"
        assert tracks[0].parent == "200"
        assert tracks[0].isVideo is False
        assert tracks[1].title == "Death on Two Legs"
        assert tracks[1].id == "301"
        assert tracks[1].albumId == "200"

        # Verify API call was made
        client.client.get.assert_called_once()
        call_args = client.client.get.call_args
        assert "getAlbum" in call_args[0][0]
        assert call_args.kwargs["params"]["id"] == "200"

    def test_get_album_empty(
        self, client: SubsonicClient, fixtures: Dict[str, Any], mocker: MockerFixture
    ):
        """Test handling of empty album (no tracks).

        Validates:
        - Client handles empty track list gracefully
        - Client returns empty list (not None or error)
        """
        # Arrange: Mock empty album response
        client.client.get = mocker.MagicMock(
            return_value=mock_response(200, fixtures["getAlbum_empty"])
        )

        # Act: Fetch album with no tracks
        tracks = client.get_album(album_id="201")

        # Assert: Verify empty list returned
        assert tracks == []
        assert isinstance(tracks, list)

    def test_get_album_filters_video(
        self, client: SubsonicClient, fixtures: Dict[str, Any], mocker: MockerFixture
    ):
        """Test that get_album filters out video content (isVideo=true).

        Validates:
        - Client filters out tracks with isVideo=true
        - Client only returns audio tracks (isVideo=false)
        - Video filtering happens during parsing
        """
        # Arrange: Mock album response with mixed audio/video
        client.client.get = mocker.MagicMock(
            return_value=mock_response(200, fixtures["getAlbum_with_video"])
        )

        # Act: Fetch album tracks
        tracks = client.get_album(album_id="202")

        # Assert: Only audio track returned, video filtered out
        assert len(tracks) == 1
        assert tracks[0].id == "400"
        assert tracks[0].title == "Audio Track"
        assert tracks[0].isVideo is False


class TestStreamTrack:
    """Test cases for track streaming/download operations."""

    def test_stream_track_success(
        self, client: SubsonicClient, mocker: MockerFixture
    ):
        """Test successful track audio download.

        Validates:
        - Client requests correct stream endpoint
        - Client handles binary audio data
        - Client returns audio bytes
        """
        # Arrange: Mock successful audio stream
        audio_data = b"fake_mp3_audio_data_here"

        mock_response_obj = httpx.Response(
            status_code=200,
            content=audio_data,
            headers={"content-type": "audio/mpeg"},
            request=httpx.Request("GET", "https://music.example.com/rest/stream"),
        )
        client.client.get = mocker.MagicMock(return_value=mock_response_obj)

        # Act: Stream track
        result = client.stream_track(track_id="300")

        # Assert: Verify audio data returned
        assert result == audio_data
        assert isinstance(result, bytes)

        # Verify stream endpoint called
        client.client.get.assert_called_once()
        call_args = client.client.get.call_args
        assert "params" in call_args.kwargs
        assert "id" in call_args.kwargs["params"]
        assert call_args.kwargs["params"]["id"] == "300"

    def test_stream_track_not_found(
        self, client: SubsonicClient, fixtures: Dict[str, Any], mocker: MockerFixture
    ):
        """Test handling of not found error when track doesn't exist.

        Validates:
        - Client handles error code 70 (not found) in JSON response
        - Client raises SubsonicNotFoundError
        - Exception contains error code and message
        """
        # Arrange: Mock JSON error response (200 OK with error in JSON)
        error_response = httpx.Response(
            status_code=200,
            json=fixtures["stream_not_found"],
            headers={"content-type": "application/json"},
            request=httpx.Request("GET", "https://music.example.com/rest/stream"),
        )
        client.client.get = mocker.MagicMock(return_value=error_response)

        # Act & Assert: Verify SubsonicNotFoundError is raised
        with pytest.raises(SubsonicNotFoundError) as exc_info:
            client.stream_track(track_id="999")

        # Verify error details
        error = exc_info.value
        assert error.code == 70
        assert "Song not found" in error.message


class TestErrorHandling:
    """Test cases for network errors and edge cases."""

    def test_network_timeout(
        self, client: SubsonicClient, mocker: MockerFixture
    ):
        """Test handling of network timeout errors.

        Validates:
        - Client has reasonable timeout configured
        - Client raises appropriate exception on timeout
        - Exception is httpx.TimeoutException or similar
        """
        # Arrange: Mock timeout
        client.client.get = mocker.MagicMock(
            side_effect=httpx.TimeoutException("Request timed out")
        )

        # Act & Assert: Verify timeout exception is raised
        with pytest.raises(httpx.TimeoutException) as exc_info:
            client.ping()

        # Verify timeout message
        assert "timed out" in str(exc_info.value).lower()

    def test_connection_error(
        self, client: SubsonicClient, mocker: MockerFixture
    ):
        """Test handling of connection errors (server unreachable).

        Validates:
        - Client handles connection failures gracefully
        - Client raises appropriate exception
        """
        # Arrange: Mock connection error
        client.client.get = mocker.MagicMock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        # Act & Assert: Verify connection exception is raised
        with pytest.raises(httpx.ConnectError):
            client.ping()

    def test_generic_api_error(
        self, client: SubsonicClient, fixtures: Dict[str, Any], mocker: MockerFixture
    ):
        """Test handling of generic API errors.

        Validates:
        - Client handles Subsonic error responses
        - Client extracts error code and message
        """
        # Arrange: Mock generic error (200 OK with error in JSON)
        client.client.get = mocker.MagicMock(
            return_value=mock_response(200, fixtures["generic_error"])
        )

        # Act & Assert: Verify exception is raised
        from src.subsonic.exceptions import SubsonicError

        with pytest.raises(SubsonicError) as exc_info:
            client.ping()

        # Verify error message
        error = exc_info.value
        assert error.code == 0
        assert "generic error" in error.message.lower()


class TestRequestParameters:
    """Test cases for correct request parameter formatting."""

    def test_authentication_params_format(
        self, client: SubsonicClient, mocker: MockerFixture
    ):
        """Test that authentication parameters are correctly formatted.

        Validates:
        - Token is MD5 hash
        - Salt is included
        - Username is included
        - Standard params (c, v, f) are present
        """
        # Arrange: Mock response
        client.client.get = mocker.MagicMock(
            return_value=mock_response(200, {
                "subsonic-response": {"status": "ok", "version": "1.16.1"}
            })
        )

        # Act: Make any request
        client.ping()

        # Assert: Verify auth params format
        call_args = client.client.get.call_args
        params = call_args.kwargs["params"]

        # Check auth params
        assert "u" in params
        assert "t" in params  # Token should be present
        assert "s" in params  # Salt should be present
        assert len(params["t"]) == 32  # MD5 hash is 32 chars
        assert len(params["s"]) > 0  # Salt should be non-empty

        # Check standard params
        assert params["c"] == "playlistgen-test"
        assert params["v"] == "1.16.1"
        assert params["f"] == "json"

    def test_album_query_parameters(
        self, client: SubsonicClient, fixtures: Dict[str, Any], mocker: MockerFixture
    ):
        """Test that get_album query parameters are correctly included.

        Validates:
        - Album ID parameter is passed correctly
        - getAlbum endpoint is called
        """
        # Arrange: Mock response
        client.client.get = mocker.MagicMock(
            return_value=mock_response(200, fixtures["getAlbum_empty"])
        )

        # Act: Query album
        client.get_album(album_id="201")

        # Assert: Verify query params
        call_args = client.client.get.call_args
        params = call_args.kwargs["params"]

        assert params.get("id") == "201"
        assert "getAlbum" in call_args[0][0]


class TestHTTP2Fallback:
    """Test cases for HTTP/2 fallback to HTTP/1.1."""

    def test_http2_fallback(self, mocker: MockerFixture):
        """Test HTTP/2 fallback to HTTP/1.1 when h2 not installed.

        Validates:
        - Client falls back gracefully when HTTP/2 is unavailable
        - HTTP/1.1 client is created instead
        - No errors are raised
        """
        # Arrange: Mock httpx.Client to raise ImportError on http2=True
        original_client = httpx.Client

        def mock_client_with_http2_fail(*args, **kwargs):
            if kwargs.get("http2"):
                raise ImportError("h2 package not installed")
            return original_client(*args, **kwargs)

        mocker.patch("httpx.Client", side_effect=mock_client_with_http2_fail)

        config = SubsonicConfig(
            url="https://music.example.com",
            username="testuser",
            password="testpass",
        )

        # Act: Create client (should fallback to HTTP/1.1)
        client = SubsonicClient(config)

        # Assert: Client was created successfully
        assert client is not None
        assert client.client is not None

        # Cleanup
        client.close()


class TestErrorCodes:
    """Test cases for specific Subsonic API error codes."""

    def test_error_code_50_authorization(
        self, client: SubsonicClient, mocker: MockerFixture
    ):
        """Test SubsonicAuthorizationError for code 50.

        Validates:
        - Client raises SubsonicAuthorizationError for error code 50
        - Error message is preserved
        """
        from src.subsonic.exceptions import SubsonicAuthorizationError

        # Arrange: Mock response with authorization error
        error_response = {
            "subsonic-response": {
                "status": "failed",
                "version": "1.16.1",
                "error": {"code": 50, "message": "User is not authorized for this operation"},
            }
        }
        client.client.get = mocker.MagicMock(return_value=mock_response(200, error_response))

        # Act & Assert: Verify SubsonicAuthorizationError is raised
        with pytest.raises(SubsonicAuthorizationError) as exc_info:
            client.ping()

        assert exc_info.value.code == 50
        assert "not authorized" in exc_info.value.message.lower()

    def test_error_code_20_version(
        self, client: SubsonicClient, mocker: MockerFixture
    ):
        """Test SubsonicVersionError for code 20.

        Validates:
        - Client raises SubsonicVersionError for error code 20
        - Version incompatibility message is preserved
        """
        from src.subsonic.exceptions import SubsonicVersionError

        # Arrange: Mock response with version error
        error_response = {
            "subsonic-response": {
                "status": "failed",
                "version": "1.16.1",
                "error": {
                    "code": 20,
                    "message": "Incompatible Subsonic REST protocol version. Client must upgrade.",
                },
            }
        }
        client.client.get = mocker.MagicMock(return_value=mock_response(200, error_response))

        # Act & Assert: Verify SubsonicVersionError is raised
        with pytest.raises(SubsonicVersionError) as exc_info:
            client.ping()

        assert exc_info.value.code == 20
        assert "version" in exc_info.value.message.lower()

    def test_error_code_30_version(
        self, client: SubsonicClient, mocker: MockerFixture
    ):
        """Test SubsonicVersionError for code 30.

        Validates:
        - Client raises SubsonicVersionError for error code 30
        - Server version error message is preserved
        """
        from src.subsonic.exceptions import SubsonicVersionError

        # Arrange: Mock response with server version error
        error_response = {
            "subsonic-response": {
                "status": "failed",
                "version": "1.16.1",
                "error": {
                    "code": 30,
                    "message": "Incompatible Subsonic REST protocol version. Server must upgrade.",
                },
            }
        }
        client.client.get = mocker.MagicMock(return_value=mock_response(200, error_response))

        # Act & Assert: Verify SubsonicVersionError is raised
        with pytest.raises(SubsonicVersionError) as exc_info:
            client.ping()

        assert exc_info.value.code == 30
        assert "version" in exc_info.value.message.lower()

    def test_error_code_10_parameter(
        self, client: SubsonicClient, mocker: MockerFixture
    ):
        """Test SubsonicParameterError for code 10.

        Validates:
        - Client raises SubsonicParameterError for error code 10
        - Parameter error message is preserved
        """
        from src.subsonic.exceptions import SubsonicParameterError

        # Arrange: Mock response with parameter error
        error_response = {
            "subsonic-response": {
                "status": "failed",
                "version": "1.16.1",
                "error": {"code": 10, "message": "Required parameter is missing."},
            }
        }
        client.client.get = mocker.MagicMock(return_value=mock_response(200, error_response))

        # Act & Assert: Verify SubsonicParameterError is raised
        with pytest.raises(SubsonicParameterError) as exc_info:
            client.ping()

        assert exc_info.value.code == 10
        assert "parameter" in exc_info.value.message.lower()

    def test_error_code_60_trial(
        self, client: SubsonicClient, mocker: MockerFixture
    ):
        """Test SubsonicTrialError for code 60.

        Validates:
        - Client raises SubsonicTrialError for error code 60
        - Trial expiration message is preserved
        """
        from src.subsonic.exceptions import SubsonicTrialError

        # Arrange: Mock response with trial error
        error_response = {
            "subsonic-response": {
                "status": "failed",
                "version": "1.16.1",
                "error": {"code": 60, "message": "The trial period for the Subsonic server is over."},
            }
        }
        client.client.get = mocker.MagicMock(return_value=mock_response(200, error_response))

        # Act & Assert: Verify SubsonicTrialError is raised
        with pytest.raises(SubsonicTrialError) as exc_info:
            client.ping()

        assert exc_info.value.code == 60
        assert "trial" in exc_info.value.message.lower()


class TestEdgeCaseAlbumContainer:
    """Test cases for edge case handling in album track retrieval."""

    def test_album_empty_songs_list(
        self, client: SubsonicClient, mocker: MockerFixture
    ):
        """Test edge case where album has no tracks.

        Validates:
        - Client handles album with empty song list gracefully
        - Returns empty list when no tracks
        """
        # Arrange: Mock response where album has empty song array
        empty_album_response = {
            "subsonic-response": {
                "status": "ok",
                "version": "1.16.1",
                "album": {
                    "id": "999",
                    "name": "Empty Album",
                    "song": []  # Empty array, no tracks
                }
            }
        }

        client.client.get = mocker.MagicMock(return_value=mock_response(200, empty_album_response))

        # Act: Fetch album tracks
        tracks = client.get_album(album_id="999")

        # Assert: Verify empty list returned
        assert len(tracks) == 0
        assert tracks == []

    def test_album_track_with_missing_field(
        self, client: SubsonicClient, fixtures: Dict[str, Any], mocker: MockerFixture
    ):
        """Test handling of album track with missing required field (id).

        Validates:
        - Client skips tracks with missing required 'id' field
        - KeyError is caught and logged
        - Other tracks are still returned (even with minimal data)
        - Critical ID3 fields (albumId, artistId, parent) are validated when present
        """
        # Arrange: Mock response with mixed valid/invalid tracks
        client.client.get = mocker.MagicMock(
            return_value=mock_response(200, fixtures["getAlbum_missing_fields"])
        )

        # Act: Fetch album tracks (should skip ones without 'id')
        tracks = client.get_album(album_id="203")

        # Assert: Two tracks returned (one with missing 'id' was skipped)
        assert len(tracks) == 2

        # First track - has all fields
        assert tracks[0].id == "500"
        assert tracks[0].title == "Valid Track"
        assert tracks[0].parent == "203"
        assert tracks[0].albumId == "203"
        assert tracks[0].artistId == "102"

        # Second track - has id but missing title (uses defaults)
        assert tracks[1].id == "502"
        assert tracks[1].title == ""  # Default from .get()
        assert tracks[1].parent == "203"
        assert tracks[1].albumId is None  # Missing optional field
        assert tracks[1].artistId is None  # Missing optional field


class TestRandomSongs:
    """Test cases for get_random_songs method."""

    def test_get_random_songs_success(
        self, client: SubsonicClient, mocker: MockerFixture
    ):
        """Test get_random_songs() method.

        Validates:
        - Client calls getRandomSongs endpoint
        - Client properly parses random song data
        - Client returns SubsonicTrack objects
        """
        # Arrange: Mock random songs response
        random_response = {
            "subsonic-response": {
                "status": "ok",
                "version": "1.16.1",
                "randomSongs": {
                    "song": [
                        {
                            "id": "500",
                            "title": "Random Song 1",
                            "artist": "Random Artist 1",
                            "album": "Random Album 1",
                            "duration": 240,
                        },
                        {
                            "id": "501",
                            "title": "Random Song 2",
                            "artist": "Random Artist 2",
                            "album": "Random Album 2",
                            "duration": 180,
                        },
                    ]
                },
            }
        }

        client.client.get = mocker.MagicMock(return_value=mock_response(200, random_response))

        # Act: Fetch random songs
        songs = client.get_random_songs(size=10)

        # Assert: Verify songs were returned
        assert len(songs) == 2
        assert songs[0].id == "500"
        assert songs[0].title == "Random Song 1"
        assert songs[1].id == "501"
        assert songs[1].title == "Random Song 2"

        # Verify correct endpoint was called
        client.client.get.assert_called_once()
        call_args = client.client.get.call_args
        assert "getRandomSongs" in call_args[0][0]

    def test_get_random_songs_with_size_limit(
        self, client: SubsonicClient, mocker: MockerFixture
    ):
        """Test get_random_songs() respects size limit.

        Validates:
        - Client enforces max size of 500
        - Size parameter is passed correctly
        """
        # Arrange: Mock response
        client.client.get = mocker.MagicMock(
            return_value=mock_response(
                200,
                {
                    "subsonic-response": {
                        "status": "ok",
                        "version": "1.16.1",
                        "randomSongs": {"song": []},
                    }
                },
            )
        )

        # Act: Request large number of songs
        client.get_random_songs(size=1000)

        # Assert: Size is capped at 500
        call_args = client.client.get.call_args
        params = call_args.kwargs["params"]
        assert params["size"] == "500"  # Capped at max

    def test_get_random_songs_missing_field(
        self, client: SubsonicClient, mocker: MockerFixture
    ):
        """Test get_random_songs() handles missing required fields.

        Validates:
        - Client skips songs with missing required fields
        - Valid songs are still returned
        """
        # Arrange: Mock response with invalid song
        mixed_response = {
            "subsonic-response": {
                "status": "ok",
                "version": "1.16.1",
                "randomSongs": {
                    "song": [
                        {
                            "id": "600",
                            "title": "Valid Random Song",
                            "artist": "Valid Artist",
                        },
                        {
                            # Missing 'id' - should be skipped
                            "title": "Invalid Song",
                        },
                    ]
                },
            }
        }

        client.client.get = mocker.MagicMock(return_value=mock_response(200, mixed_response))

        # Act: Fetch random songs
        songs = client.get_random_songs()

        # Assert: Only valid song is returned
        assert len(songs) == 1
        assert songs[0].id == "600"
        assert songs[0].title == "Valid Random Song"

    def test_get_random_songs_empty_result(
        self, client: SubsonicClient, mocker: MockerFixture
    ):
        """Test get_random_songs with empty result.

        Validates:
        - Client handles empty randomSongs dict gracefully
        - Returns empty list when no songs available
        """
        # Arrange: Mock response with empty randomSongs dict
        empty_response = {
            "subsonic-response": {
                "status": "ok",
                "version": "1.16.1",
                "randomSongs": {},  # Empty dict, no 'song' key
            }
        }

        client.client.get = mocker.MagicMock(return_value=mock_response(200, empty_response))

        # Act: Fetch random songs
        songs = client.get_random_songs()

        # Assert: Verify empty list returned
        assert len(songs) == 0
        assert songs == []


class TestAdditionalMethods:
    """Test cases for additional client methods."""

    def test_get_stream_url(
        self, client: SubsonicClient, mocker: MockerFixture
    ):
        """Test generation of streaming URL with authentication.

        Validates:
        - URL includes all auth parameters
        - URL includes track ID
        - URL is properly formatted
        """
        # Act: Generate stream URL
        url = client.get_stream_url(track_id="12345")

        # Assert: Verify URL format
        assert "https://music.example.com/rest/stream" in url
        assert "id=12345" in url
        assert "u=testuser" in url
        assert "t=" in url  # Token
        assert "s=" in url  # Salt
        assert "c=playlistgen-test" in url
        assert "v=1.16.1" in url
        assert "f=json" in url

    def test_context_manager(
        self, client: SubsonicClient, mocker: MockerFixture
    ):
        """Test client works as context manager.

        Validates:
        - Client can be used in with statement
        - Client.close() is called on exit
        """
        # Arrange: Mock close method
        client.client.close = mocker.MagicMock()

        # Act: Use client in context manager
        with client as c:
            # Verify we get the same client back
            assert c is client

        # Assert: Verify close was called
        client.client.close.assert_called_once()

    def test_close_method(
        self, client: SubsonicClient, mocker: MockerFixture
    ):
        """Test explicit close method.

        Validates:
        - close() properly closes httpx client
        """
        # Arrange: Mock close method
        client.client.close = mocker.MagicMock()

        # Act: Call close
        client.close()

        # Assert: Verify httpx client close was called
        client.client.close.assert_called_once()

    def test_http_error_handling(
        self, client: SubsonicClient, mocker: MockerFixture
    ):
        """Test handling of HTTP status errors (4xx, 5xx).

        Validates:
        - Client raises httpx.HTTPStatusError for HTTP errors
        """
        # Arrange: Mock 500 Internal Server Error
        error_response = httpx.Response(
            status_code=500,
            request=httpx.Request("GET", "https://music.example.com/rest/ping"),
        )
        client.client.get = mocker.MagicMock(return_value=error_response)

        # Act & Assert: Verify HTTP error is raised
        with pytest.raises(httpx.HTTPStatusError):
            client.ping()

    def test_album_tracks_with_missing_fields(
        self, client: SubsonicClient, mocker: MockerFixture
    ):
        """Test handling of album tracks with missing optional fields.

        Validates:
        - Client handles tracks with missing optional fields gracefully
        - Client uses defaults for missing fields (artist, album, duration)
        - Critical ID3 fields (parent, albumId, artistId) are preserved when present
        """
        # Arrange: Mock response with minimal track data
        minimal_track_response = {
            "subsonic-response": {
                "status": "ok",
                "version": "1.16.1",
                "album": {
                    "id": "999",
                    "name": "Test Album",
                    "song": [
                        {
                            "id": "888",
                            "title": "Minimal Track",
                            "parent": "999",
                            "albumId": "999",
                            "artistId": "777"
                            # Missing artist, album, duration, etc.
                        }
                    ]
                },
            }
        }

        client.client.get = mocker.MagicMock(
            return_value=mock_response(200, minimal_track_response)
        )

        # Act: Fetch album tracks
        tracks = client.get_album(album_id="999")

        # Assert: Verify track was created with defaults and ID3 fields preserved
        assert len(tracks) == 1
        assert tracks[0].id == "888"
        assert tracks[0].title == "Minimal Track"
        assert tracks[0].parent == "999"
        assert tracks[0].albumId == "999"
        assert tracks[0].artistId == "777"
        assert tracks[0].artist == ""  # Default from .get()
        assert tracks[0].album == ""  # Default from .get()
        assert tracks[0].duration == 0  # Default from .get()
