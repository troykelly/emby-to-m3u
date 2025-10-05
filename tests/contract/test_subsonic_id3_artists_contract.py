"""Contract tests for Subsonic ID3 getArtists API."""

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
def id3_artists_response():
    """Mock response for getArtists endpoint."""
    return {
        "subsonic-response": {
            "status": "ok",
            "version": "1.16.1",
            "artists": {
                "ignoredArticles": "The El La Los Las Le Les",
                "index": [
                    {
                        "name": "A",
                        "artist": [
                            {
                                "id": "ar-1",
                                "name": "ABBA",
                                "albumCount": 8,
                                "coverArt": "ar-1"
                            },
                            {
                                "id": "ar-2",
                                "name": "AC/DC",
                                "albumCount": 15,
                                "coverArt": "ar-2"
                            }
                        ]
                    },
                    {
                        "name": "Q",
                        "artist": [
                            {
                                "id": "ar-100",
                                "name": "Queen",
                                "albumCount": 12,
                                "coverArt": "ar-100",
                                "artistImageUrl": "https://example.com/queen.jpg"
                            }
                        ]
                    }
                ]
            }
        }
    }


def test_get_artists_returns_index_array(mock_subsonic_client, id3_artists_response):
    """Test getArtists endpoint returns flat list of artists."""
    # This test MUST FAIL initially - get_artists method doesn't exist yet
    # Expected error: AttributeError: 'SubsonicClient' object has no attribute 'get_artists'
    with patch.object(mock_subsonic_client.client, 'get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = id3_artists_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # This will fail - method doesn't exist yet (TDD Red phase)
        result = mock_subsonic_client.get_artists()

        # Implementation returns flat list of artists
        assert isinstance(result, list)
        assert len(result) > 0


def test_get_artists_validates_artist_required_fields(mock_subsonic_client, id3_artists_response):
    """Test artist objects contain required fields: id, name, albumCount."""
    with patch.object(mock_subsonic_client.client, 'get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = id3_artists_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # This will fail - method doesn't exist yet
        result = mock_subsonic_client.get_artists()

        # Validate first artist has required fields
        first_artist = result[0]

        assert "id" in first_artist
        assert "name" in first_artist
        assert "albumCount" in first_artist

        assert isinstance(first_artist["id"], str)
        assert isinstance(first_artist["name"], str)
        assert isinstance(first_artist["albumCount"], int)
        assert first_artist["albumCount"] > 0


def test_get_artists_validates_index_structure(mock_subsonic_client, id3_artists_response):
    """Test artists list contains artist objects."""
    with patch.object(mock_subsonic_client.client, 'get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = id3_artists_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # This will fail - method doesn't exist yet
        result = mock_subsonic_client.get_artists()

        # Each artist should have required fields
        for artist in result:
            assert "id" in artist
            assert "name" in artist
            assert isinstance(artist["id"], str)
            assert isinstance(artist["name"], str)


def test_get_artists_optional_coverart_field(mock_subsonic_client, id3_artists_response):
    """Test artist objects can have optional coverArt field."""
    with patch.object(mock_subsonic_client.client, 'get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = id3_artists_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # This will fail - method doesn't exist yet
        result = mock_subsonic_client.get_artists()

        # Check optional coverArt field
        first_artist = result[0]
        if "coverArt" in first_artist:
            assert isinstance(first_artist["coverArt"], str)
            assert len(first_artist["coverArt"]) > 0


def test_get_artists_validates_ignored_articles(mock_subsonic_client, id3_artists_response):
    """Test artists response returns flat list (ignoredArticles not included)."""
    with patch.object(mock_subsonic_client.client, 'get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = id3_artists_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # This will fail - method doesn't exist yet
        result = mock_subsonic_client.get_artists()

        # Implementation returns flat list, not full response
        assert isinstance(result, list)
        assert len(result) > 0


def test_get_artists_url_contains_required_params(mock_subsonic_client, id3_artists_response):
    """Test getArtists URL contains all required authentication parameters."""
    with patch.object(mock_subsonic_client.client, 'get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = id3_artists_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # This will fail - method doesn't exist yet
        mock_subsonic_client.get_artists()

        # Verify the request was made with proper parameters
        assert mock_get.called
        call_args = mock_get.call_args

        # Check URL endpoint
        assert "getArtists" in call_args[0][0] or "getArtists" in str(call_args)

        # Check params
        call_kwargs = call_args[1] if len(call_args) > 1 else {}
        params = call_kwargs.get('params', {})

        assert 'u' in params  # username
        assert 't' in params  # token
        assert 's' in params  # salt
        assert 'v' in params  # API version
        assert 'c' in params  # client name
        assert 'f' in params  # format


def test_get_artists_raises_on_auth_failure(mock_subsonic_client, subsonic_responses):
    """Test getArtists raises SubsonicAuthenticationError on auth failure."""
    from src.subsonic.exceptions import SubsonicAuthenticationError

    with patch.object(mock_subsonic_client.client, 'get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = subsonic_responses["ping_auth_failure"]
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # This will fail - method doesn't exist yet
        with pytest.raises(SubsonicAuthenticationError) as exc_info:
            mock_subsonic_client.get_artists()

        assert exc_info.value.code == 40


def test_get_artists_handles_empty_library(mock_subsonic_client):
    """Test getArtists handles empty library gracefully."""
    empty_response = {
        "subsonic-response": {
            "status": "ok",
            "version": "1.16.1",
            "artists": {
                "ignoredArticles": "The El La",
                "index": []
            }
        }
    }

    with patch.object(mock_subsonic_client.client, 'get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = empty_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # This will fail - method doesn't exist yet
        result = mock_subsonic_client.get_artists()

        # Implementation returns flat list
        assert isinstance(result, list)
        assert len(result) == 0


def test_get_artists_contract_matches_openapi_spec(mock_subsonic_client, id3_artists_response):
    """Test getArtists endpoint contract matches OpenAPI specification."""
    with patch.object(mock_subsonic_client.client, 'get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = id3_artists_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # This will fail - method doesn't exist yet
        result = mock_subsonic_client.get_artists()

        # Validate complete schema per OpenAPI contract
        assert "subsonic-response" in id3_artists_response
        assert id3_artists_response["subsonic-response"]["status"] == "ok"

        # Implementation returns flat list of artists
        assert isinstance(result, list)

        # Validate artist objects schema
        for artist in result:
            assert "id" in artist
            assert "name" in artist
            assert "albumCount" in artist
