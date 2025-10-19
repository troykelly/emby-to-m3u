"""
Comprehensive tests for SubsonicClient to achieve >50% coverage.

Tests cover:
1. __init__ with valid config and HTTP/2 fallback
2. Rate limiting behavior
3. URL building
4. Request execution with various responses
5. Error handling (auth errors, not found, etc.)
6. ping() method with OpenSubsonic detection
7. get_random_songs() method
8. search3() method
9. Stream and download methods
10. Artist/Album/Track retrieval
11. Playlist methods
12. Starred items
13. Scrobbling
14. Context manager support
"""

import time
from unittest.mock import Mock, patch, MagicMock
from collections import deque

import httpx
import pytest

from src.subsonic.client import SubsonicClient
from src.subsonic.models import SubsonicConfig, SubsonicTrack
from src.subsonic.exceptions import (
    SubsonicAuthenticationError,
    SubsonicAuthorizationError,
    SubsonicNotFoundError,
    SubsonicParameterError,
    SubsonicError,
    TokenAuthenticationNotSupportedError,
    ClientVersionTooOldError,
    ServerVersionTooOldError,
    SubsonicVersionError,
    SubsonicTrialError,
)


@pytest.fixture
def valid_config():
    """Return a valid SubsonicConfig for testing."""
    return SubsonicConfig(
        url="https://music.example.com",
        username="testuser",
        password="testpass",
        client_name="test-client",
        api_version="1.16.1",
    )


@pytest.fixture
def mock_httpx_client():
    """Return a mocked httpx.Client."""
    return Mock(spec=httpx.Client)


class TestSubsonicClientInit:
    """Tests for SubsonicClient.__init__()."""

    def test_init_with_valid_config(self, valid_config):
        """Test initialization with valid config."""
        # Act
        client = SubsonicClient(valid_config)

        # Assert
        assert client.config == valid_config
        assert client._base_url == "https://music.example.com"
        assert client.opensubsonic is False
        assert client.opensubsonic_version is None
        assert client.rate_limit is None
        assert client._request_times is None
        assert client.client is not None

        # Cleanup
        client.close()

    def test_init_strips_trailing_slash_from_url(self, valid_config):
        """Test that trailing slash is removed from base URL."""
        # Arrange
        valid_config.url = "https://music.example.com/"

        # Act
        client = SubsonicClient(valid_config)

        # Assert
        assert client._base_url == "https://music.example.com"

        # Cleanup
        client.close()

    def test_init_with_rate_limit(self, valid_config):
        """Test initialization with rate limiting enabled."""
        # Act
        client = SubsonicClient(valid_config, rate_limit=10)

        # Assert
        assert client.rate_limit == 10
        assert client._request_times is not None
        assert isinstance(client._request_times, deque)
        assert client._request_times.maxlen == 100

        # Cleanup
        client.close()

    @patch("src.subsonic.client.httpx.Client")
    def test_init_with_http2_fallback(self, mock_client_class, valid_config):
        """Test HTTP/2 fallback when h2 package not available."""
        # Arrange - First call raises ImportError, second succeeds
        mock_client_instance = MagicMock()
        mock_client_class.side_effect = [ImportError("h2 not available"), mock_client_instance]

        # Act
        client = SubsonicClient(valid_config)

        # Assert - Client was created twice (once with http2=True, once without)
        assert mock_client_class.call_count == 2
        first_call = mock_client_class.call_args_list[0]
        second_call = mock_client_class.call_args_list[1]

        # First call should have http2=True
        assert first_call[1].get("http2") is True
        # Second call should NOT have http2 parameter
        assert "http2" not in second_call[1]

        # Cleanup
        client.close()


class TestRateLimiting:
    """Tests for rate limiting functionality."""

    def test_apply_rate_limit_no_limit_set(self, valid_config):
        """Test that no rate limiting occurs when rate_limit is None."""
        # Arrange
        client = SubsonicClient(valid_config, rate_limit=None)

        # Act - Should complete instantly
        start = time.time()
        client._apply_rate_limit()
        duration = time.time() - start

        # Assert - No delay
        assert duration < 0.01

        # Cleanup
        client.close()

    def test_apply_rate_limit_enforces_limit(self, valid_config):
        """Test that rate limiting delays requests when limit is reached."""
        # Arrange
        client = SubsonicClient(valid_config, rate_limit=2)

        # Act - Make 3 requests in quick succession
        client._apply_rate_limit()  # Request 1
        client._apply_rate_limit()  # Request 2
        start = time.time()
        client._apply_rate_limit()  # Request 3 - should sleep
        duration = time.time() - start

        # Assert - Third request was delayed (~1 second)
        assert duration >= 0.9  # Allow some tolerance

        # Cleanup
        client.close()

    def test_apply_rate_limit_sliding_window(self, valid_config):
        """Test that rate limiting uses sliding window."""
        # Arrange
        client = SubsonicClient(valid_config, rate_limit=2)

        # Act - First two requests
        client._apply_rate_limit()
        client._apply_rate_limit()

        # Wait for window to slide
        time.sleep(1.1)

        # Third request should not be delayed (old requests expired)
        start = time.time()
        client._apply_rate_limit()
        duration = time.time() - start

        # Assert - No significant delay
        assert duration < 0.1

        # Cleanup
        client.close()


class TestBuildUrl:
    """Tests for _build_url method."""

    def test_build_url_simple_endpoint(self, valid_config):
        """Test URL building for simple endpoint."""
        # Arrange
        client = SubsonicClient(valid_config)

        # Act
        url = client._build_url("ping")

        # Assert
        assert url == "https://music.example.com/rest/ping"

        # Cleanup
        client.close()

    def test_build_url_complex_endpoint(self, valid_config):
        """Test URL building for complex endpoint."""
        # Arrange
        client = SubsonicClient(valid_config)

        # Act
        url = client._build_url("search3")

        # Assert
        assert url == "https://music.example.com/rest/search3"

        # Cleanup
        client.close()


class TestHandleResponse:
    """Tests for _handle_response method."""

    def test_handle_response_success(self, valid_config):
        """Test handling successful response."""
        # Arrange
        client = SubsonicClient(valid_config)
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "ok",
                "version": "1.16.1",
            }
        }
        mock_response.headers = {"content-type": "application/json"}

        # Act
        result = client._handle_response(mock_response)

        # Assert
        assert result["status"] == "ok"
        assert result["version"] == "1.16.1"

        # Cleanup
        client.close()

    def test_handle_response_authentication_error_code_40(self, valid_config):
        """Test handling authentication error (code 40)."""
        # Arrange
        client = SubsonicClient(valid_config)
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "failed",
                "error": {"code": 40, "message": "Wrong username or password"},
            }
        }
        mock_response.headers = {"content-type": "application/json"}

        # Act & Assert
        with pytest.raises(SubsonicAuthenticationError) as exc_info:
            client._handle_response(mock_response)

        assert exc_info.value.code == 40
        assert "Wrong username or password" in str(exc_info.value)

        # Cleanup
        client.close()

    def test_handle_response_authentication_error_code_41(self, valid_config):
        """Test handling authentication error (code 41)."""
        # Arrange
        client = SubsonicClient(valid_config)
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "failed",
                "error": {"code": 41, "message": "Token authentication required"},
            }
        }
        mock_response.headers = {"content-type": "application/json"}

        # Act & Assert
        with pytest.raises(SubsonicAuthenticationError) as exc_info:
            client._handle_response(mock_response)

        assert exc_info.value.code == 41

        # Cleanup
        client.close()

    def test_handle_response_token_auth_not_supported(self, valid_config):
        """Test handling token auth not supported error (code 42)."""
        # Arrange
        client = SubsonicClient(valid_config)
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "failed",
                "error": {"code": 42, "message": "Token authentication not supported"},
            }
        }
        mock_response.headers = {"content-type": "application/json"}

        # Act & Assert
        with pytest.raises(TokenAuthenticationNotSupportedError) as exc_info:
            client._handle_response(mock_response)

        assert exc_info.value.code == 42

        # Cleanup
        client.close()

    def test_handle_response_client_version_too_old(self, valid_config):
        """Test handling client version too old error (code 43)."""
        # Arrange
        client = SubsonicClient(valid_config)
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "failed",
                "error": {"code": 43, "message": "Client must upgrade"},
            }
        }
        mock_response.headers = {"content-type": "application/json"}

        # Act & Assert
        with pytest.raises(ClientVersionTooOldError) as exc_info:
            client._handle_response(mock_response)

        assert exc_info.value.code == 43

        # Cleanup
        client.close()

    def test_handle_response_server_version_too_old(self, valid_config):
        """Test handling server version too old error (code 44)."""
        # Arrange
        client = SubsonicClient(valid_config)
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "failed",
                "error": {"code": 44, "message": "Server must upgrade"},
            }
        }
        mock_response.headers = {"content-type": "application/json"}

        # Act & Assert
        with pytest.raises(ServerVersionTooOldError) as exc_info:
            client._handle_response(mock_response)

        assert exc_info.value.code == 44

        # Cleanup
        client.close()

    def test_handle_response_authorization_error(self, valid_config):
        """Test handling authorization error (code 50)."""
        # Arrange
        client = SubsonicClient(valid_config)
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "failed",
                "error": {"code": 50, "message": "User not authorized"},
            }
        }
        mock_response.headers = {"content-type": "application/json"}

        # Act & Assert
        with pytest.raises(SubsonicAuthorizationError) as exc_info:
            client._handle_response(mock_response)

        assert exc_info.value.code == 50

        # Cleanup
        client.close()

    def test_handle_response_not_found_error(self, valid_config):
        """Test handling not found error (code 70)."""
        # Arrange
        client = SubsonicClient(valid_config)
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "failed",
                "error": {"code": 70, "message": "Resource not found"},
            }
        }
        mock_response.headers = {"content-type": "application/json"}

        # Act & Assert
        with pytest.raises(SubsonicNotFoundError) as exc_info:
            client._handle_response(mock_response)

        assert exc_info.value.code == 70

        # Cleanup
        client.close()

    def test_handle_response_version_error_code_20(self, valid_config):
        """Test handling version incompatibility error (code 20)."""
        # Arrange
        client = SubsonicClient(valid_config)
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "failed",
                "error": {"code": 20, "message": "Incompatible client version"},
            }
        }
        mock_response.headers = {"content-type": "application/json"}

        # Act & Assert
        with pytest.raises(SubsonicVersionError) as exc_info:
            client._handle_response(mock_response)

        assert exc_info.value.code == 20

        # Cleanup
        client.close()

    def test_handle_response_parameter_error(self, valid_config):
        """Test handling parameter error (code 10)."""
        # Arrange
        client = SubsonicClient(valid_config)
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "failed",
                "error": {"code": 10, "message": "Required parameter missing"},
            }
        }
        mock_response.headers = {"content-type": "application/json"}

        # Act & Assert
        with pytest.raises(SubsonicParameterError) as exc_info:
            client._handle_response(mock_response)

        assert exc_info.value.code == 10

        # Cleanup
        client.close()

    def test_handle_response_trial_expired_error(self, valid_config):
        """Test handling trial expired error (code 60)."""
        # Arrange
        client = SubsonicClient(valid_config)
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "failed",
                "error": {"code": 60, "message": "Trial period expired"},
            }
        }
        mock_response.headers = {"content-type": "application/json"}

        # Act & Assert
        with pytest.raises(SubsonicTrialError) as exc_info:
            client._handle_response(mock_response)

        assert exc_info.value.code == 60

        # Cleanup
        client.close()

    def test_handle_response_generic_error(self, valid_config):
        """Test handling generic error (unknown code)."""
        # Arrange
        client = SubsonicClient(valid_config)
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "failed",
                "error": {"code": 99, "message": "Unknown error"},
            }
        }
        mock_response.headers = {"content-type": "application/json"}

        # Act & Assert
        with pytest.raises(SubsonicError) as exc_info:
            client._handle_response(mock_response)

        assert exc_info.value.code == 99

        # Cleanup
        client.close()


class TestPingMethod:
    """Tests for ping() method."""

    def test_ping_success(self, valid_config):
        """Test successful ping."""
        # Arrange
        client = SubsonicClient(valid_config)
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "ok",
                "version": "1.16.1",
            }
        }
        mock_response.headers = {"content-type": "application/json"}

        with patch.object(client.client, "get", return_value=mock_response):
            # Act
            result = client.ping()

            # Assert
            assert result is True
            assert client.opensubsonic is False
            assert client.opensubsonic_version is None

        # Cleanup
        client.close()

    def test_ping_detects_opensubsonic(self, valid_config):
        """Test ping detects OpenSubsonic server."""
        # Arrange
        client = SubsonicClient(valid_config)
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "ok",
                "version": "1.16.1",
                "openSubsonic": {
                    "serverVersion": "0.1.0",
                },
            }
        }
        mock_response.headers = {"content-type": "application/json"}

        with patch.object(client.client, "get", return_value=mock_response):
            # Act
            result = client.ping()

            # Assert
            assert result is True
            assert client.opensubsonic is True
            assert client.opensubsonic_version == "0.1.0"

        # Cleanup
        client.close()


class TestGetRandomSongs:
    """Tests for get_random_songs() method."""

    def test_get_random_songs_success(self, valid_config):
        """Test successful retrieval of random songs."""
        # Arrange
        client = SubsonicClient(valid_config)
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "ok",
                "randomSongs": {
                    "song": [
                        {
                            "id": "123",
                            "title": "Test Song",
                            "artist": "Test Artist",
                            "album": "Test Album",
                            "duration": 180,
                            "path": "/music/test.mp3",
                            "suffix": "mp3",
                            "created": "2024-01-01T00:00:00Z",
                        }
                    ]
                },
            }
        }
        mock_response.headers = {"content-type": "application/json"}

        with patch.object(client.client, "get", return_value=mock_response):
            # Act
            tracks = client.get_random_songs(size=10)

            # Assert
            assert len(tracks) == 1
            assert isinstance(tracks[0], SubsonicTrack)
            assert tracks[0].id == "123"
            assert tracks[0].title == "Test Song"

        # Cleanup
        client.close()

    def test_get_random_songs_enforces_max_size(self, valid_config):
        """Test that size is capped at 500."""
        # Arrange
        client = SubsonicClient(valid_config)
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "ok",
                "randomSongs": {"song": []},
            }
        }
        mock_response.headers = {"content-type": "application/json"}

        with patch.object(client.client, "get", return_value=mock_response) as mock_get:
            # Act
            client.get_random_songs(size=1000)

            # Assert - Should request max 500
            call_params = mock_get.call_args[1]["params"]
            assert call_params["size"] == "500"

        # Cleanup
        client.close()

    def test_get_random_songs_handles_missing_fields(self, valid_config):
        """Test that tracks with missing required fields are skipped."""
        # Arrange
        client = SubsonicClient(valid_config)
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "ok",
                "randomSongs": {
                    "song": [
                        {
                            "id": "123",
                            "title": "Test Song",
                            "artist": "Test Artist",
                            "album": "Test Album",
                            "duration": 180,
                            "path": "/music/test.mp3",
                            "suffix": "mp3",
                            "created": "2024-01-01T00:00:00Z",
                        },
                        {
                            # Missing 'id' - should be skipped
                            "title": "Invalid Song",
                            "artist": "Test Artist",
                        },
                    ]
                },
            }
        }
        mock_response.headers = {"content-type": "application/json"}

        with patch.object(client.client, "get", return_value=mock_response):
            # Act
            tracks = client.get_random_songs(size=10)

            # Assert - Only valid track returned
            assert len(tracks) == 1
            assert tracks[0].id == "123"

        # Cleanup
        client.close()


class TestSearch3Method:
    """Tests for search3() method."""

    def test_search3_success(self, valid_config):
        """Test successful search3."""
        # Arrange
        client = SubsonicClient(valid_config)
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "ok",
                "searchResult3": {
                    "artist": [{"id": "1", "name": "Beatles"}],
                    "album": [{"id": "2", "name": "Abbey Road"}],
                    "song": [
                        {
                            "id": "3",
                            "title": "Come Together",
                            "artist": "Beatles",
                            "album": "Abbey Road",
                            "duration": 259,
                            "path": "/music/beatles.mp3",
                            "suffix": "mp3",
                            "created": "2024-01-01T00:00:00Z",
                        }
                    ],
                },
            }
        }
        mock_response.headers = {"content-type": "application/json"}

        with patch.object(client.client, "get", return_value=mock_response):
            # Act
            result = client.search3("beatles", song_count=10)

            # Assert
            assert "searchResult3" in result
            assert len(result["searchResult3"]["artist"]) == 1
            assert len(result["searchResult3"]["song"]) == 1

        # Cleanup
        client.close()


class TestStreamTrack:
    """Tests for stream_track() method."""

    def test_stream_track_success(self, valid_config):
        """Test successful track streaming."""
        # Arrange
        client = SubsonicClient(valid_config)
        audio_data = b"fake audio data"
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status = Mock()
        mock_response.content = audio_data
        mock_response.headers = {"content-type": "audio/mpeg"}

        with patch.object(client.client, "get", return_value=mock_response):
            # Act
            result = client.stream_track("123")

            # Assert
            assert result == audio_data

        # Cleanup
        client.close()

    def test_stream_track_json_error_response(self, valid_config):
        """Test stream_track handles JSON error response."""
        # Arrange
        client = SubsonicClient(valid_config)
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "failed",
                "error": {"code": 70, "message": "Track not found"},
            }
        }
        mock_response.headers = {"content-type": "application/json"}

        with patch.object(client.client, "get", return_value=mock_response):
            # Act & Assert
            with pytest.raises(SubsonicNotFoundError):
                client.stream_track("999")

        # Cleanup
        client.close()


class TestGetStreamUrl:
    """Tests for get_stream_url() method."""

    def test_get_stream_url(self, valid_config):
        """Test stream URL generation."""
        # Arrange
        client = SubsonicClient(valid_config)

        # Act
        url = client.get_stream_url("123")

        # Assert
        assert "https://music.example.com/rest/stream" in url
        assert "id=123" in url
        assert "u=testuser" in url
        assert "t=" in url  # Token present
        assert "s=" in url  # Salt present

        # Cleanup
        client.close()


class TestContextManager:
    """Tests for context manager support."""

    def test_context_manager_enter_exit(self, valid_config):
        """Test using client as context manager."""
        # Act
        with SubsonicClient(valid_config) as client:
            # Assert - Client is usable
            assert client is not None
            assert client.client is not None

        # After exit, client should be closed (can't test directly, but no errors)

    def test_manual_close(self, valid_config):
        """Test manual close() method."""
        # Arrange
        client = SubsonicClient(valid_config)

        # Act
        client.close()

        # Assert - No errors (client is closed)


class TestGetArtists:
    """Tests for get_artists() method."""

    def test_get_artists_success(self, valid_config):
        """Test successful retrieval of artists."""
        # Arrange
        client = SubsonicClient(valid_config)
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "ok",
                "artists": {
                    "index": [
                        {
                            "name": "B",
                            "artist": [
                                {"id": "1", "name": "Beatles", "albumCount": 13}
                            ],
                        }
                    ]
                },
            }
        }
        mock_response.headers = {"content-type": "application/json"}

        with patch.object(client.client, "get", return_value=mock_response):
            # Act
            artists = client.get_artists()

            # Assert
            assert len(artists) == 1
            assert artists[0]["name"] == "Beatles"

        # Cleanup
        client.close()


class TestGetAlbum:
    """Tests for get_album() method."""

    def test_get_album_success(self, valid_config):
        """Test successful album retrieval."""
        # Arrange
        client = SubsonicClient(valid_config)
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "ok",
                "album": {
                    "id": "1",
                    "name": "Abbey Road",
                    "song": [
                        {
                            "id": "123",
                            "title": "Come Together",
                            "artist": "Beatles",
                            "album": "Abbey Road",
                            "duration": 259,
                            "path": "/music/beatles.mp3",
                            "suffix": "mp3",
                            "created": "2024-01-01T00:00:00Z",
                        }
                    ],
                },
            }
        }
        mock_response.headers = {"content-type": "application/json"}

        with patch.object(client.client, "get", return_value=mock_response):
            # Act
            tracks = client.get_album("1")

            # Assert
            assert len(tracks) == 1
            assert tracks[0].title == "Come Together"

        # Cleanup
        client.close()


class TestGetPlaylist:
    """Tests for get_playlist() method."""

    def test_get_playlist_success(self, valid_config):
        """Test successful playlist retrieval."""
        # Arrange
        client = SubsonicClient(valid_config)
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "ok",
                "playlist": {
                    "id": "1",
                    "name": "My Playlist",
                    "entry": [
                        {
                            "id": "123",
                            "title": "Test Song",
                            "artist": "Test Artist",
                            "album": "Test Album",
                            "duration": 180,
                            "path": "/music/test.mp3",
                            "suffix": "mp3",
                            "created": "2024-01-01T00:00:00Z",
                        }
                    ],
                },
            }
        }
        mock_response.headers = {"content-type": "application/json"}

        with patch.object(client.client, "get", return_value=mock_response):
            # Act
            tracks = client.get_playlist("1")

            # Assert
            assert len(tracks) == 1
            assert tracks[0].title == "Test Song"

        # Cleanup
        client.close()


class TestStarUnstar:
    """Tests for star() and unstar() methods."""

    def test_star_song_success(self, valid_config):
        """Test starring a song."""
        # Arrange
        client = SubsonicClient(valid_config)
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "subsonic-response": {"status": "ok"}
        }
        mock_response.headers = {"content-type": "application/json"}

        with patch.object(client.client, "get", return_value=mock_response):
            # Act
            result = client.star("123", "song")

            # Assert
            assert result is True

        # Cleanup
        client.close()

    def test_unstar_album_success(self, valid_config):
        """Test unstarring an album."""
        # Arrange
        client = SubsonicClient(valid_config)
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "subsonic-response": {"status": "ok"}
        }
        mock_response.headers = {"content-type": "application/json"}

        with patch.object(client.client, "get", return_value=mock_response):
            # Act
            result = client.unstar("456", "album")

            # Assert
            assert result is True

        # Cleanup
        client.close()


class TestScrobble:
    """Tests for scrobble() method."""

    def test_scrobble_success(self, valid_config):
        """Test successful scrobbling."""
        # Arrange
        client = SubsonicClient(valid_config)
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "subsonic-response": {"status": "ok"}
        }
        mock_response.headers = {"content-type": "application/json"}

        with patch.object(client.client, "get", return_value=mock_response):
            # Act
            result = client.scrobble("123")

            # Assert
            assert result is True

        # Cleanup
        client.close()

    def test_scrobble_now_playing(self, valid_config):
        """Test updating now playing without scrobbling."""
        # Arrange
        client = SubsonicClient(valid_config)
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "subsonic-response": {"status": "ok"}
        }
        mock_response.headers = {"content-type": "application/json"}

        with patch.object(client.client, "get", return_value=mock_response) as mock_get:
            # Act
            result = client.scrobble("123", submission=False)

            # Assert
            assert result is True
            # Check submission parameter
            call_params = mock_get.call_args[1]["params"]
            assert call_params["submission"] == "false"

        # Cleanup
        client.close()


class TestGetMusicFolders:
    """Tests for get_music_folders() method."""

    def test_get_music_folders_success(self, valid_config):
        """Test successful retrieval of music folders."""
        # Arrange
        client = SubsonicClient(valid_config)
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "ok",
                "musicFolders": {
                    "musicFolder": [
                        {"id": "1", "name": "Music"},
                        {"id": "2", "name": "Podcasts"},
                    ]
                },
            }
        }
        mock_response.headers = {"content-type": "application/json"}

        with patch.object(client.client, "get", return_value=mock_response):
            # Act
            folders = client.get_music_folders()

            # Assert
            assert len(folders) == 2
            assert folders[0]["name"] == "Music"

        # Cleanup
        client.close()


class TestGetGenres:
    """Tests for get_genres() method."""

    def test_get_genres_success(self, valid_config):
        """Test successful retrieval of genres."""
        # Arrange
        client = SubsonicClient(valid_config)
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "ok",
                "genres": {
                    "genre": [
                        {"value": "Rock", "songCount": 100, "albumCount": 10},
                        {"value": "Jazz", "songCount": 50, "albumCount": 5},
                    ]
                },
            }
        }
        mock_response.headers = {"content-type": "application/json"}

        with patch.object(client.client, "get", return_value=mock_response):
            # Act
            genres = client.get_genres()

            # Assert
            assert len(genres) == 2
            assert genres[0]["value"] == "Rock"

        # Cleanup
        client.close()


class TestBuildParams:
    """Tests for _build_params() method."""

    def test_build_params_basic(self, valid_config):
        """Test building basic parameters."""
        # Arrange
        client = SubsonicClient(valid_config)

        # Act
        params = client._build_params()

        # Assert
        assert params["v"] == "1.16.1"
        assert params["c"] == "test-client"
        assert params["f"] == "json"
        assert params["u"] == "testuser"
        assert "t" in params  # Token
        assert "s" in params  # Salt

        # Cleanup
        client.close()

    def test_build_params_with_kwargs(self, valid_config):
        """Test building parameters with additional kwargs."""
        # Arrange
        client = SubsonicClient(valid_config)

        # Act
        params = client._build_params(query="test", size=10, offset=20)

        # Assert
        assert params["query"] == "test"
        assert params["size"] == "10"
        assert params["offset"] == "20"

        # Cleanup
        client.close()

    def test_build_params_filters_none_values(self, valid_config):
        """Test that None values are filtered out."""
        # Arrange
        client = SubsonicClient(valid_config)

        # Act
        params = client._build_params(query="test", size=None)

        # Assert
        assert params["query"] == "test"
        assert "size" not in params

        # Cleanup
        client.close()


class TestGetAuthParams:
    """Tests for _get_auth_params() method."""

    def test_get_auth_params_password_auth(self, valid_config):
        """Test authentication params with password."""
        # Arrange
        client = SubsonicClient(valid_config)

        # Act
        params = client._get_auth_params()

        # Assert
        assert params["u"] == "testuser"
        assert "t" in params
        assert "s" in params
        assert "k" not in params  # No API key

        # Cleanup
        client.close()

    def test_get_auth_params_api_key_auth(self):
        """Test authentication params with API key."""
        # Arrange
        config = SubsonicConfig(
            url="https://music.example.com",
            username="testuser",
            api_key="test-api-key",
        )
        client = SubsonicClient(config)

        # Act
        params = client._get_auth_params()

        # Assert
        assert params["u"] == "testuser"
        assert params["k"] == "test-api-key"
        assert "t" not in params  # No token
        assert "s" not in params  # No salt

        # Cleanup
        client.close()
