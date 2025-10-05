"""Contract tests for Subsonic ID3 getAlbum API."""

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
def id3_album_response():
    """Mock response for getAlbum endpoint with song array."""
    return {
        "subsonic-response": {
            "status": "ok",
            "version": "1.16.1",
            "album": {
                "id": "al-200",
                "name": "A Night at the Opera",
                "artist": "Queen",
                "artistId": "ar-100",
                "coverArt": "al-200",
                "songCount": 12,
                "duration": 2561,
                "created": "2024-01-15T10:30:00.000Z",
                "year": 1975,
                "genre": "Rock",
                "song": [
                    {
                        "id": "300",
                        "parent": "al-200",
                        "title": "Death on Two Legs",
                        "album": "A Night at the Opera",
                        "artist": "Queen",
                        "albumId": "al-200",
                        "artistId": "ar-100",
                        "track": 1,
                        "year": 1975,
                        "genre": "Rock",
                        "coverArt": "al-200",
                        "size": 4123456,
                        "contentType": "audio/mpeg",
                        "suffix": "mp3",
                        "duration": 208,
                        "bitRate": 320,
                        "path": "Queen/A Night at the Opera/01 Death on Two Legs.mp3",
                        "created": "2024-01-15T10:30:00.000Z",
                        "isDir": False,
                        "isVideo": False,
                        "type": "music"
                    },
                    {
                        "id": "301",
                        "parent": "al-200",
                        "title": "Lazing on a Sunday Afternoon",
                        "album": "A Night at the Opera",
                        "artist": "Queen",
                        "albumId": "al-200",
                        "artistId": "ar-100",
                        "track": 2,
                        "year": 1975,
                        "genre": "Rock",
                        "coverArt": "al-200",
                        "size": 1234567,
                        "contentType": "audio/mpeg",
                        "suffix": "mp3",
                        "duration": 69,
                        "bitRate": 320,
                        "path": "Queen/A Night at the Opera/02 Lazing on a Sunday Afternoon.mp3",
                        "created": "2024-01-15T10:30:00.000Z",
                        "isDir": False,
                        "isVideo": False,
                        "type": "music"
                    },
                    {
                        "id": "302",
                        "parent": "al-200",
                        "title": "Bohemian Rhapsody",
                        "album": "A Night at the Opera",
                        "artist": "Queen",
                        "albumId": "al-200",
                        "artistId": "ar-100",
                        "track": 11,
                        "year": 1975,
                        "genre": "Rock",
                        "coverArt": "al-200",
                        "size": 8503491,
                        "contentType": "audio/mpeg",
                        "suffix": "mp3",
                        "duration": 354,
                        "bitRate": 320,
                        "path": "Queen/A Night at the Opera/11 Bohemian Rhapsody.mp3",
                        "created": "2024-01-15T10:30:00.000Z",
                        "musicBrainzId": "b1a9c0e9-d987-4042-ae91-78d6a3267d69",
                        "isDir": False,
                        "isVideo": False,
                        "type": "music"
                    }
                ]
            }
        }
    }


@pytest.fixture
def id3_album_with_video_response():
    """Mock response with mixed audio/video content for filtering tests."""
    return {
        "subsonic-response": {
            "status": "ok",
            "version": "1.16.1",
            "album": {
                "id": "al-300",
                "name": "Greatest Hits",
                "artist": "Queen",
                "artistId": "ar-100",
                "songCount": 5,
                "duration": 1800,
                "song": [
                    {
                        "id": "400",
                        "parent": "al-300",
                        "title": "Bohemian Rhapsody",
                        "albumId": "al-300",
                        "artistId": "ar-100",
                        "isDir": False,
                        "isVideo": False,
                        "type": "music",
                        "contentType": "audio/mpeg"
                    },
                    {
                        "id": "401",
                        "parent": "al-300",
                        "title": "Bohemian Rhapsody (Music Video)",
                        "albumId": "al-300",
                        "artistId": "ar-100",
                        "isDir": False,
                        "isVideo": True,
                        "type": "video",
                        "contentType": "video/mp4"
                    },
                    {
                        "id": "402",
                        "parent": "al-300",
                        "title": "We Will Rock You",
                        "albumId": "al-300",
                        "artistId": "ar-100",
                        "isDir": False,
                        "isVideo": False,
                        "type": "music",
                        "contentType": "audio/mpeg"
                    }
                ]
            }
        }
    }


def test_get_album_returns_song_array(mock_subsonic_client, id3_album_response):
    """Test getAlbum endpoint returns list of SubsonicTrack objects."""
    album_id = "al-200"

    # This test MUST FAIL initially - get_album method doesn't exist yet
    # Expected error: AttributeError: 'SubsonicClient' object has no attribute 'get_album'
    with patch.object(mock_subsonic_client.client, 'get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = id3_album_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # This will fail - method doesn't exist yet (TDD Red phase)
        result = mock_subsonic_client.get_album(album_id)

        # Implementation returns List[SubsonicTrack]
        assert isinstance(result, list)
        assert len(result) > 0


def test_get_album_validates_song_critical_fields(mock_subsonic_client, id3_album_response):
    """Test song objects contain critical fields: id, parent, albumId, artistId, isDir, isVideo, type."""
    album_id = "al-200"

    with patch.object(mock_subsonic_client.client, 'get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = id3_album_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # This will fail - method doesn't exist yet
        result = mock_subsonic_client.get_album(album_id)

        # Validate first track has critical fields for M3U generation
        first_track = result[0]

        critical_fields = ["id", "parent", "albumId", "artistId", "isDir", "isVideo", "type"]
        for field in critical_fields:
            assert hasattr(first_track, field), f"Missing critical field: {field}"

        # Validate field types and values
        assert isinstance(first_track.id, str)
        assert isinstance(first_track.parent, str)
        assert isinstance(first_track.albumId, str)
        assert isinstance(first_track.artistId, str)
        assert isinstance(first_track.isDir, bool)
        assert isinstance(first_track.isVideo, bool)
        assert isinstance(first_track.type, str)

        # For music tracks
        assert first_track.isDir is False
        assert first_track.type in ["music", "video"]


def test_get_album_song_parent_matches_album_id(mock_subsonic_client, id3_album_response):
    """Test all songs have parent field matching album ID."""
    album_id = "al-200"

    with patch.object(mock_subsonic_client.client, 'get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = id3_album_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # This will fail - method doesn't exist yet
        result = mock_subsonic_client.get_album(album_id)

        # All tracks should reference the correct album ID as parent
        for track in result:
            assert track.parent == album_id
            assert track.albumId == album_id


def test_get_album_song_artistid_matches_album_artistid(mock_subsonic_client, id3_album_response):
    """Test all songs have artistId matching album's artistId."""
    album_id = "al-200"

    with patch.object(mock_subsonic_client.client, 'get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = id3_album_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # This will fail - method doesn't exist yet
        result = mock_subsonic_client.get_album(album_id)

        # Get expected artist ID from fixture
        expected_artist_id = id3_album_response["subsonic-response"]["album"]["artistId"]

        # All tracks should reference the same artist ID
        for track in result:
            assert track.artistId == expected_artist_id


def test_get_album_filters_video_content(mock_subsonic_client, id3_album_with_video_response):
    """Test filtering videos (isVideo=false) to get only audio tracks."""
    album_id = "al-300"

    with patch.object(mock_subsonic_client.client, 'get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = id3_album_with_video_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # This will fail - method doesn't exist yet
        result = mock_subsonic_client.get_album(album_id)

        # Implementation filters out videos automatically - result only contains audio
        # Original fixture has 3 items: 2 audio + 1 video
        # After filtering, should only have 2 audio tracks
        assert len(result) == 2  # Only audio tracks returned

        # Verify all returned tracks are audio
        for track in result:
            assert track.isVideo is False
            assert track.type == "music"


def test_get_album_validates_album_metadata(mock_subsonic_client, id3_album_response):
    """Test tracks contain album metadata in their fields."""
    album_id = "al-200"

    with patch.object(mock_subsonic_client.client, 'get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = id3_album_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # This will fail - method doesn't exist yet
        result = mock_subsonic_client.get_album(album_id)

        # Implementation returns List[SubsonicTrack], not album dict
        # Verify tracks contain album metadata
        assert len(result) > 0
        first_track = result[0]

        assert first_track.albumId == album_id
        assert isinstance(first_track.album, str)
        assert isinstance(first_track.artist, str)
        assert isinstance(first_track.artistId, str)


def test_get_album_url_contains_album_id_param(mock_subsonic_client, id3_album_response):
    """Test getAlbum URL contains id parameter with album ID."""
    album_id = "al-200"

    with patch.object(mock_subsonic_client.client, 'get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = id3_album_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # This will fail - method doesn't exist yet
        mock_subsonic_client.get_album(album_id)

        # Verify the request was made with album ID parameter
        assert mock_get.called
        call_kwargs = mock_get.call_args[1]
        params = call_kwargs.get('params', {})

        assert 'id' in params
        assert params['id'] == album_id


def test_get_album_url_contains_required_auth_params(mock_subsonic_client, id3_album_response):
    """Test getAlbum URL contains all required authentication parameters."""
    album_id = "al-200"

    with patch.object(mock_subsonic_client.client, 'get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = id3_album_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # This will fail - method doesn't exist yet
        mock_subsonic_client.get_album(album_id)

        call_kwargs = mock_get.call_args[1]
        params = call_kwargs.get('params', {})

        # Required auth params
        assert 'u' in params  # username
        assert 't' in params  # token
        assert 's' in params  # salt
        assert 'v' in params  # API version
        assert 'c' in params  # client name
        assert 'f' in params  # format


def test_get_album_raises_on_invalid_album_id(mock_subsonic_client):
    """Test getAlbum raises SubsonicNotFoundError for invalid album ID."""
    from src.subsonic.exceptions import SubsonicNotFoundError

    album_id = "invalid-album-999"

    # Mock "not found" error response
    not_found_response = {
        "subsonic-response": {
            "status": "failed",
            "version": "1.16.1",
            "error": {
                "code": 70,
                "message": "Album not found."
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
            mock_subsonic_client.get_album(album_id)

        assert exc_info.value.code == 70


def test_get_album_raises_on_auth_failure(mock_subsonic_client, subsonic_responses):
    """Test getAlbum raises SubsonicAuthenticationError on auth failure."""
    from src.subsonic.exceptions import SubsonicAuthenticationError

    album_id = "al-200"

    with patch.object(mock_subsonic_client.client, 'get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = subsonic_responses["ping_auth_failure"]
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # This will fail - method doesn't exist yet
        with pytest.raises(SubsonicAuthenticationError) as exc_info:
            mock_subsonic_client.get_album(album_id)

        assert exc_info.value.code == 40


def test_get_album_contract_matches_openapi_spec(mock_subsonic_client, id3_album_response):
    """Test getAlbum endpoint contract matches OpenAPI specification."""
    album_id = "al-200"

    with patch.object(mock_subsonic_client.client, 'get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = id3_album_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # This will fail - method doesn't exist yet
        result = mock_subsonic_client.get_album(album_id)

        # Validate complete schema per OpenAPI contract
        assert "subsonic-response" in id3_album_response
        assert id3_album_response["subsonic-response"]["status"] == "ok"

        # Implementation returns List[SubsonicTrack]
        assert isinstance(result, list)
        assert len(result) > 0

        # Validate track schema with critical fields
        for track in result:
            assert hasattr(track, "id")
            assert hasattr(track, "parent")
            assert hasattr(track, "albumId")
            assert hasattr(track, "artistId")
            assert hasattr(track, "isDir")
            assert hasattr(track, "isVideo")
            assert hasattr(track, "type")
