"""Contract tests for Subsonic ID3 getArtist API."""

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


@pytest.fixture
def id3_artist_response():
    """Mock response for getArtist endpoint."""
    return {
        "subsonic-response": {
            "status": "ok",
            "version": "1.16.1",
            "artist": {
                "id": "ar-100",
                "name": "Queen",
                "albumCount": 12,
                "coverArt": "ar-100",
                "artistImageUrl": "https://example.com/queen.jpg",
                "album": [
                    {
                        "id": "al-200",
                        "name": "A Night at the Opera",
                        "artist": "Queen",
                        "artistId": "ar-100",
                        "coverArt": "al-200",
                        "songCount": 12,
                        "duration": 2561,
                        "created": "2024-01-15T10:30:00.000Z",
                        "year": 1975,
                        "genre": "Rock"
                    },
                    {
                        "id": "al-201",
                        "name": "News of the World",
                        "artist": "Queen",
                        "artistId": "ar-100",
                        "coverArt": "al-201",
                        "songCount": 11,
                        "duration": 2401,
                        "created": "2024-01-15T11:00:00.000Z",
                        "year": 1977,
                        "genre": "Rock"
                    },
                    {
                        "id": "al-202",
                        "name": "The Works",
                        "artist": "Queen",
                        "artistId": "ar-100",
                        "coverArt": "al-202",
                        "songCount": 9,
                        "duration": 2156,
                        "created": "2024-01-15T12:00:00.000Z",
                        "year": 1984,
                        "genre": "Rock"
                    }
                ]
            }
        }
    }


def test_get_artist_returns_album_array(mock_subsonic_client, id3_artist_response):
    """Test getArtist endpoint returns artist dict with album array."""
    artist_id = "ar-100"

    # This test MUST FAIL initially - get_artist method doesn't exist yet
    # Expected error: AttributeError: 'SubsonicClient' object has no attribute 'get_artist'
    with patch.object(mock_subsonic_client.client, 'get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = id3_artist_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # This will fail - method doesn't exist yet (TDD Red phase)
        result = mock_subsonic_client.get_artist(artist_id)

        # Implementation returns the artist dict directly
        assert "album" in result
        assert isinstance(result["album"], list)
        assert len(result["album"]) > 0


def test_get_artist_validates_album_required_fields(mock_subsonic_client, id3_artist_response):
    """Test album objects contain required fields: id, name, artist, artistId, songCount, duration, created."""
    artist_id = "ar-100"

    with patch.object(mock_subsonic_client.client, 'get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = id3_artist_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # This will fail - method doesn't exist yet
        result = mock_subsonic_client.get_artist(artist_id)

        # Validate first album has required fields
        first_album = result["album"][0]

        required_fields = ["id", "name", "artist", "artistId", "songCount", "duration", "created"]
        for field in required_fields:
            assert field in first_album, f"Missing required field: {field}"

        # Validate field types
        assert isinstance(first_album["id"], str)
        assert isinstance(first_album["name"], str)
        assert isinstance(first_album["artist"], str)
        assert isinstance(first_album["artistId"], str)
        assert isinstance(first_album["songCount"], int)
        assert isinstance(first_album["duration"], int)
        assert isinstance(first_album["created"], str)


def test_get_artist_validates_artist_metadata(mock_subsonic_client, id3_artist_response):
    """Test artist object contains metadata: id, name, albumCount."""
    artist_id = "ar-100"

    with patch.object(mock_subsonic_client.client, 'get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = id3_artist_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # This will fail - method doesn't exist yet
        result = mock_subsonic_client.get_artist(artist_id)

        # Result is the artist dict directly
        assert "id" in result
        assert "name" in result
        assert "albumCount" in result

        assert result["id"] == artist_id
        assert isinstance(result["name"], str)
        assert isinstance(result["albumCount"], int)
        assert result["albumCount"] > 0


def test_get_artist_album_artistid_matches_artist_id(mock_subsonic_client, id3_artist_response):
    """Test all albums have artistId matching the artist's id."""
    artist_id = "ar-100"

    with patch.object(mock_subsonic_client.client, 'get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = id3_artist_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # This will fail - method doesn't exist yet
        result = mock_subsonic_client.get_artist(artist_id)

        albums = result["album"]

        # All albums should reference the correct artist ID
        for album in albums:
            assert album["artistId"] == artist_id
            assert album["artist"] == result["name"]


def test_get_artist_optional_coverart_field(mock_subsonic_client, id3_artist_response):
    """Test artist and album objects can have optional coverArt field."""
    artist_id = "ar-100"

    with patch.object(mock_subsonic_client.client, 'get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = id3_artist_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # This will fail - method doesn't exist yet
        result = mock_subsonic_client.get_artist(artist_id)

        if "coverArt" in result:
            assert isinstance(result["coverArt"], str)

        # Check album cover art
        for album in result["album"]:
            if "coverArt" in album:
                assert isinstance(album["coverArt"], str)


def test_get_artist_url_contains_artist_id_param(mock_subsonic_client, id3_artist_response):
    """Test getArtist URL contains id parameter with artist ID."""
    artist_id = "ar-100"

    with patch.object(mock_subsonic_client.client, 'get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = id3_artist_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # This will fail - method doesn't exist yet
        mock_subsonic_client.get_artist(artist_id)

        # Verify the request was made with artist ID parameter
        assert mock_get.called
        call_kwargs = mock_get.call_args[1]
        params = call_kwargs.get('params', {})

        assert 'id' in params
        assert params['id'] == artist_id


def test_get_artist_url_contains_required_auth_params(mock_subsonic_client, id3_artist_response):
    """Test getArtist URL contains all required authentication parameters."""
    artist_id = "ar-100"

    with patch.object(mock_subsonic_client.client, 'get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = id3_artist_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # This will fail - method doesn't exist yet
        mock_subsonic_client.get_artist(artist_id)

        call_kwargs = mock_get.call_args[1]
        params = call_kwargs.get('params', {})

        # Required auth params
        assert 'u' in params  # username
        assert 't' in params  # token
        assert 's' in params  # salt
        assert 'v' in params  # API version
        assert 'c' in params  # client name
        assert 'f' in params  # format


def test_get_artist_raises_on_invalid_artist_id(mock_subsonic_client, subsonic_responses):
    """Test getArtist raises SubsonicNotFoundError for invalid artist ID."""
    from src.subsonic.exceptions import SubsonicNotFoundError

    artist_id = "invalid-artist-999"

    # Mock "not found" error response
    not_found_response = {
        "subsonic-response": {
            "status": "failed",
            "version": "1.16.1",
            "error": {
                "code": 70,
                "message": "Artist not found."
            }
        }
    }

    with patch.object(mock_subsonic_client.client, 'get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = not_found_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # This will fail - method doesn't exist yet
        with pytest.raises(SubsonicNotFoundError) as exc_info:
            mock_subsonic_client.get_artist(artist_id)

        assert exc_info.value.code == 70


def test_get_artist_raises_on_auth_failure(mock_subsonic_client, subsonic_responses):
    """Test getArtist raises SubsonicAuthenticationError on auth failure."""
    from src.subsonic.exceptions import SubsonicAuthenticationError

    artist_id = "ar-100"

    with patch.object(mock_subsonic_client.client, 'get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = subsonic_responses["ping_auth_failure"]
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # This will fail - method doesn't exist yet
        with pytest.raises(SubsonicAuthenticationError) as exc_info:
            mock_subsonic_client.get_artist(artist_id)

        assert exc_info.value.code == 40


def test_get_artist_contract_matches_openapi_spec(mock_subsonic_client, id3_artist_response):
    """Test getArtist endpoint contract matches OpenAPI specification."""
    artist_id = "ar-100"

    with patch.object(mock_subsonic_client.client, 'get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = id3_artist_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # This will fail - method doesn't exist yet
        result = mock_subsonic_client.get_artist(artist_id)

        # Validate complete schema per OpenAPI contract
        assert "subsonic-response" in id3_artist_response
        assert id3_artist_response["subsonic-response"]["status"] == "ok"

        # Implementation returns artist dict directly
        assert "id" in result
        assert "name" in result
        assert "albumCount" in result
        assert "album" in result
        assert isinstance(result["album"], list)

        # Validate album schema
        for album in result["album"]:
            assert "id" in album
            assert "name" in album
            assert "artist" in album
            assert "artistId" in album
            assert "songCount" in album
            assert "duration" in album
            assert "created" in album
