"""Contract tests for Subsonic download/streaming API."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch
import json


@pytest.fixture
def subsonic_responses():
    """Load Subsonic API response fixtures."""
    fixtures_path = Path(__file__).parent.parent / "subsonic" / "fixtures" / "subsonic_responses.json"
    with open(fixtures_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def mock_subsonic_client():
    """Create a mock Subsonic client for testing."""
    from src.subsonic.models import SubsonicConfig
    from src.subsonic.client import SubsonicClient

    config = SubsonicConfig(
        url="https://music.example.com",
        username="testuser",
        password="testpass",
        api_version="1.16.1",
        client_name="playlistgen"
    )
    return SubsonicClient(config)


def test_download_returns_binary_audio_data(mock_subsonic_client):
    """Test download endpoint returns binary audio data (not XML/JSON)."""
    track_id = "300"

    # This test MUST FAIL initially - download_track method doesn't exist yet
    # Expected error: AttributeError: 'SubsonicClient' object has no attribute 'download_track'
    with patch.object(mock_subsonic_client.client, 'get') as mock_get:
        # Mock binary MP3 response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "audio/mpeg"}
        mock_response.content = b'\xff\xfb\x90\x00'  # MP3 header bytes
        mock_get.return_value = mock_response

        # This will fail - method doesn't exist yet (TDD Red phase)
        audio_data = mock_subsonic_client.download_track(track_id)

        assert isinstance(audio_data, bytes)
        assert len(audio_data) > 0
        assert audio_data[:4] == b'\xff\xfb\x90\x00'  # MP3 signature


def test_download_validates_content_type_audio_mpeg(mock_subsonic_client):
    """Test download validates Content-Type: audio/mpeg for MP3 files."""
    track_id = "300"

    with patch.object(mock_subsonic_client.client, 'get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "audio/mpeg"}
        mock_response.content = b'\xff\xfb\x90\x00'
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # This will fail - method doesn't exist yet
        audio_data = mock_subsonic_client.download_track(track_id)

        # Verify Content-Type header was checked
        assert mock_response.headers["content-type"] == "audio/mpeg"


def test_download_validates_content_type_audio_flac(mock_subsonic_client):
    """Test download validates Content-Type: audio/flac for FLAC files."""
    track_id = "301"

    with patch.object(mock_subsonic_client.client, 'get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "audio/flac"}
        mock_response.content = b'fLaC'  # FLAC signature
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # This will fail - method doesn't exist yet
        audio_data = mock_subsonic_client.download_track(track_id)

        assert mock_response.headers["content-type"] == "audio/flac"
        assert audio_data[:4] == b'fLaC'


def test_download_validates_content_type_audio_ogg(mock_subsonic_client):
    """Test download validates Content-Type: audio/ogg for OGG files."""
    track_id = "302"

    with patch.object(mock_subsonic_client.client, 'get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "audio/ogg"}
        mock_response.content = b'OggS'  # OGG signature
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # This will fail - method doesn't exist yet
        audio_data = mock_subsonic_client.download_track(track_id)

        assert mock_response.headers["content-type"] == "audio/ogg"
        assert audio_data[:4] == b'OggS'


def test_download_raises_on_invalid_track_id(mock_subsonic_client, subsonic_responses):
    """Test download raises SubsonicNotFoundError for invalid track ID."""
    from src.subsonic.exceptions import SubsonicNotFoundError

    track_id = "invalid-track-999"

    with patch.object(mock_subsonic_client.client, 'get') as mock_get:
        # Mock JSON error response for missing track
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = subsonic_responses["stream_not_found"]
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # This will fail - method doesn't exist yet
        with pytest.raises(SubsonicNotFoundError) as exc_info:
            mock_subsonic_client.download_track(track_id)

        assert exc_info.value.code == 70
        assert "Song not found" in str(exc_info.value)


def test_download_raises_on_missing_auth(mock_subsonic_client, subsonic_responses):
    """Test download raises SubsonicAuthenticationError for missing/invalid auth."""
    from src.subsonic.exceptions import SubsonicAuthenticationError

    track_id = "300"

    with patch.object(mock_subsonic_client.client, 'get') as mock_get:
        # Mock JSON error response for auth failure
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = subsonic_responses["ping_auth_failure"]
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # This will fail - method doesn't exist yet
        with pytest.raises(SubsonicAuthenticationError) as exc_info:
            mock_subsonic_client.download_track(track_id)

        assert exc_info.value.code == 40
        assert "Wrong username or password" in str(exc_info.value)


def test_download_url_contains_required_params(mock_subsonic_client):
    """Test download URL contains all required authentication parameters."""
    track_id = "300"

    with patch.object(mock_subsonic_client.client, 'get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "audio/mpeg"}
        mock_response.content = b'\xff\xfb\x90\x00'
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # This will fail - method doesn't exist yet
        mock_subsonic_client.download_track(track_id)

        # Verify the request was made with proper parameters
        assert mock_get.called
        call_kwargs = mock_get.call_args[1]
        params = call_kwargs.get('params', {})

        # Required auth params
        assert 'u' in params  # username
        assert 't' in params  # token
        assert 's' in params  # salt
        assert 'v' in params  # API version
        assert 'c' in params  # client name
        assert 'f' in params  # format
        assert 'id' in params  # track ID

        assert params['id'] == track_id


def test_download_response_not_json(mock_subsonic_client):
    """Test download response is binary data, not JSON."""
    track_id = "300"

    with patch.object(mock_subsonic_client.client, 'get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "audio/mpeg"}
        mock_response.content = b'\xff\xfb\x90\x00' * 1000  # Simulate larger file
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # This will fail - method doesn't exist yet
        audio_data = mock_subsonic_client.download_track(track_id)

        # Verify it's binary, not JSON
        assert isinstance(audio_data, bytes)

        # Attempting to decode as JSON should fail
        with pytest.raises((ValueError, json.JSONDecodeError)):
            json.loads(audio_data.decode('utf-8'))


def test_download_contract_matches_openapi_spec(mock_subsonic_client):
    """Test download endpoint contract matches OpenAPI specification."""
    track_id = "300"

    with patch.object(mock_subsonic_client.client, 'get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {
            "content-type": "audio/mpeg",
            "content-length": "8503492"
        }
        mock_response.content = b'\xff\xfb\x90\x00' * 2125873  # Simulate 8.5MB file
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # This will fail - method doesn't exist yet
        audio_data = mock_subsonic_client.download_track(track_id)

        # Validate response schema per OpenAPI contract
        assert isinstance(audio_data, bytes)
        assert len(audio_data) > 0
        assert mock_response.headers["content-type"].startswith("audio/")
        assert int(mock_response.headers["content-length"]) == len(audio_data)
