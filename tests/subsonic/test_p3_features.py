"""Unit tests for P3 optional features (star, scrobble, API key auth, rate limiting)."""

import time
from unittest.mock import Mock, patch

import pytest

from src.subsonic.client import SubsonicClient
from src.subsonic.models import SubsonicConfig, SubsonicTrack


@pytest.fixture
def subsonic_config():
    """Create test Subsonic configuration with password."""
    return SubsonicConfig(
        url="https://test.example.com",
        username="testuser",
        password="testpass",
    )


@pytest.fixture
def subsonic_config_apikey():
    """Create test Subsonic configuration with API key."""
    return SubsonicConfig(
        url="https://test.example.com",
        username="testuser",
        api_key="test-api-key-123",
    )


@pytest.fixture
def subsonic_client(subsonic_config):
    """Create SubsonicClient with mocked httpx.Client."""
    with patch.object(SubsonicClient, "__init__", lambda x, y, z=None: None):
        client = SubsonicClient.__new__(SubsonicClient)
        client.config = subsonic_config
        client._base_url = subsonic_config.url
        client.opensubsonic = False
        client.opensubsonic_version = None
        client.rate_limit = None
        client._request_times = None
        client.client = Mock()
        yield client


class TestStarFeatures:
    """Test star/unstar/get_starred2 functionality."""

    def test_star_song(self, subsonic_client):
        """Test starring a song."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {
            "subsonic-response": {"status": "ok", "version": "1.16.1"}
        }

        subsonic_client.client.get = Mock(return_value=mock_response)
        result = subsonic_client.star("track-123", "song")

        assert result is True
        subsonic_client.client.get.assert_called_once()

    def test_star_album(self, subsonic_client):
        """Test starring an album."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {
            "subsonic-response": {"status": "ok", "version": "1.16.1"}
        }

        subsonic_client.client.get = Mock(return_value=mock_response)
        result = subsonic_client.star("album-456", "album")

        assert result is True

    def test_star_artist(self, subsonic_client):
        """Test starring an artist."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {
            "subsonic-response": {"status": "ok", "version": "1.16.1"}
        }

        subsonic_client.client.get = Mock(return_value=mock_response)
        result = subsonic_client.star("artist-789", "artist")

        assert result is True

    def test_unstar_song(self, subsonic_client):
        """Test unstarring a song."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {
            "subsonic-response": {"status": "ok", "version": "1.16.1"}
        }

        subsonic_client.client.get = Mock(return_value=mock_response)
        result = subsonic_client.unstar("track-123", "song")

        assert result is True

    def test_get_starred2_success(self, subsonic_client):
        """Test getting starred items."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "ok",
                "version": "1.16.1",
                "starred2": {
                    "artist": [{"id": "1", "name": "Artist 1"}],
                    "album": [{"id": "10", "name": "Album 1"}],
                    "song": [
                        {
                            "id": "100",
                            "title": "Song 1",
                            "artist": "Artist 1",
                            "album": "Album 1",
                            "duration": 180,
                            "path": "path.mp3",
                            "suffix": "mp3",
                            "created": "2023-01-01T00:00:00.000Z",
                        }
                    ],
                },
            }
        }

        subsonic_client.client.get = Mock(return_value=mock_response)
        result = subsonic_client.get_starred2()

        assert len(result["artist"]) == 1
        assert len(result["album"]) == 1
        assert len(result["song"]) == 1
        assert isinstance(result["song"][0], SubsonicTrack)

    def test_get_starred2_empty(self, subsonic_client):
        """Test getting starred items when none exist."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "ok",
                "version": "1.16.1",
                "starred2": {},
            }
        }

        subsonic_client.client.get = Mock(return_value=mock_response)
        result = subsonic_client.get_starred2()

        assert result["artist"] == []
        assert result["album"] == []
        assert result["song"] == []


class TestScrobbleFeature:
    """Test scrobbling functionality for Last.fm integration."""

    def test_scrobble_with_default_time(self, subsonic_client):
        """Test scrobbling with automatic timestamp."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {
            "subsonic-response": {"status": "ok", "version": "1.16.1"}
        }

        subsonic_client.client.get = Mock(return_value=mock_response)
        result = subsonic_client.scrobble("track-123")

        assert result is True
        subsonic_client.client.get.assert_called_once()

    def test_scrobble_with_custom_time(self, subsonic_client):
        """Test scrobbling with specific timestamp."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {
            "subsonic-response": {"status": "ok", "version": "1.16.1"}
        }

        subsonic_client.client.get = Mock(return_value=mock_response)
        custom_time = int(time.time() * 1000)
        result = subsonic_client.scrobble("track-123", time=custom_time)

        assert result is True

    def test_scrobble_now_playing_only(self, subsonic_client):
        """Test updating now playing without scrobbling."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {
            "subsonic-response": {"status": "ok", "version": "1.16.1"}
        }

        subsonic_client.client.get = Mock(return_value=mock_response)
        result = subsonic_client.scrobble("track-123", submission=False)

        assert result is True


class TestAPIKeyAuthentication:
    """Test API key authentication for OpenSubsonic."""

    def test_config_with_api_key(self, subsonic_config_apikey):
        """Test SubsonicConfig accepts API key."""
        assert subsonic_config_apikey.api_key == "test-api-key-123"
        assert subsonic_config_apikey.password is None

    def test_config_requires_password_or_apikey(self):
        """Test that either password or API key is required."""
        with pytest.raises(ValueError, match="Either password or api_key"):
            SubsonicConfig(
                url="https://test.example.com",
                username="testuser",
            )

    def test_apikey_auth_params(self):
        """Test authentication parameters with API key."""
        from src.subsonic.auth import generate_token

        config = SubsonicConfig(
            url="https://test.example.com",
            username="testuser",
            api_key="test-key",
        )

        # Should return None for API key auth (no token needed)
        token = generate_token(config)
        assert token is None

    def test_client_uses_apikey(self, subsonic_config_apikey):
        """Test that client uses API key when available."""
        with patch("httpx.Client"):
            client = SubsonicClient(subsonic_config_apikey)
            auth_params = client._get_auth_params()

            assert "k" in auth_params
            assert auth_params["k"] == "test-api-key-123"
            assert "t" not in auth_params
            assert "s" not in auth_params


class TestRateLimiting:
    """Test client-side rate limiting."""

    def test_rate_limit_initialization(self, subsonic_config):
        """Test rate limit initialization."""
        with patch("httpx.Client"):
            client = SubsonicClient(subsonic_config, rate_limit=5)
            assert client.rate_limit == 5
            assert client._request_times is not None

    def test_no_rate_limit_by_default(self, subsonic_config):
        """Test that rate limiting is disabled by default."""
        with patch("httpx.Client"):
            client = SubsonicClient(subsonic_config)
            assert client.rate_limit is None
            assert client._request_times is None

    def test_rate_limit_enforcement(self, subsonic_config):
        """Test that rate limiting delays requests."""
        with patch("src.subsonic.client.httpx.Client") as MockClient:
            # Create mock client instance
            mock_http_client = Mock()
            mock_response = Mock()
            mock_response.raise_for_status = Mock()
            mock_response.headers = {"content-type": "application/json"}
            mock_response.json.return_value = {
                "subsonic-response": {"status": "ok", "version": "1.16.1"}
            }
            mock_http_client.get = Mock(return_value=mock_response)
            MockClient.return_value = mock_http_client

            # Create client with rate limit
            client = SubsonicClient(subsonic_config, rate_limit=2)

            # Make 4 requests (rate limit is 2/second)
            # First 2 should be immediate, 3rd and 4th should wait
            start_time = time.time()
            for _ in range(4):
                client.ping()
            elapsed_time = time.time() - start_time

            # Should take at least 0.8 seconds for 4 requests at 2/second
            # (requests 3-4 must wait ~0.5s each for sliding window)
            assert elapsed_time >= 0.8  # Allow small margin for timing

    def test_rate_limit_sliding_window(self, subsonic_config):
        """Test sliding window rate limiting."""
        with patch("src.subsonic.client.httpx.Client") as MockClient:
            mock_http_client = Mock()
            MockClient.return_value = mock_http_client

            client = SubsonicClient(subsonic_config, rate_limit=5)

            # Verify rate limiting is initialized
            assert client.rate_limit == 5
            assert client._request_times is not None
            assert len(client._request_times) == 0

            # Manually test sliding window - call _apply_rate_limit directly
            client._apply_rate_limit()
            assert len(client._request_times) == 1

            # Fill up to rate limit
            for _ in range(4):
                client._apply_rate_limit()
            assert len(client._request_times) == 5

            # Next request should be delayed due to rate limit
            start = time.time()
            client._apply_rate_limit()
            elapsed = time.time() - start

            # Should have delayed until oldest request expired (>1 second)
            # Since we filled to 5 requests instantly, 6th request must wait ~1s
            assert elapsed >= 0.9  # Allow margin for timing
            # Sliding window should have removed old requests
            assert len(client._request_times) <= 5
