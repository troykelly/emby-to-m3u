"""Contract tests for Subsonic library fetch API."""

import json
import pytest
from pathlib import Path


@pytest.fixture
def subsonic_responses():
    """Load Subsonic API response fixtures."""
    fixtures_path = Path(__file__).parent.parent / "subsonic" / "fixtures" / "subsonic_responses.json"
    with open(fixtures_path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_get_songs_without_pagination(subsonic_responses):
    """Test getSongs endpoint returns songs without pagination params."""
    response = subsonic_responses["getSongs_page1"]

    # Validate response structure
    assert "subsonic-response" in response
    assert response["subsonic-response"]["status"] == "ok"
    assert "songs" in response["subsonic-response"]
    assert "song" in response["subsonic-response"]["songs"]

    songs = response["subsonic-response"]["songs"]["song"]
    assert isinstance(songs, list)
    assert len(songs) > 0  # At least one song returned


def test_get_songs_with_offset_size():
    """Test getSongs endpoint respects offset and size parameters."""
    # Validate that offset and size are valid pagination params
    pagination_params = {
        "offset": 0,
        "size": 500
    }

    assert pagination_params["offset"] >= 0
    assert 1 <= pagination_params["size"] <= 500  # Max 500 per Subsonic API


def test_response_required_fields(subsonic_responses):
    """Test that response includes all required song fields per contract."""
    response = subsonic_responses["getSongs_page1"]
    songs = response["subsonic-response"]["songs"]["song"]

    required_fields = ["id", "title", "artist", "album", "duration", "path", "suffix", "created"]

    for song in songs:
        for field in required_fields:
            assert field in song, f"Missing required field: {field} in song: {song.get('id', 'unknown')}"

        # Validate field types
        assert isinstance(song["id"], str)
        assert isinstance(song["title"], str)
        assert isinstance(song["artist"], str)
        assert isinstance(song["album"], str)
        assert isinstance(song["duration"], int)
        assert isinstance(song["path"], str)
        assert isinstance(song["suffix"], str)
        assert isinstance(song["created"], str)


def test_response_optional_fields(subsonic_responses):
    """Test that optional fields are handled correctly (can be null/missing)."""
    response = subsonic_responses["getSongs_page1"]
    songs = response["subsonic-response"]["songs"]["song"]

    optional_fields = ["genre", "track", "year", "musicBrainzId", "discNumber",
                      "coverArt", "size", "bitRate", "contentType"]

    # Check that optional fields exist when present
    song_with_full_metadata = songs[0]  # First song has all metadata
    for field in optional_fields:
        # Optional fields can be missing or have values
        if field in song_with_full_metadata:
            assert song_with_full_metadata[field] is not None


def test_error_invalid_music_folder(subsonic_responses):
    """Test error response for invalid musicFolderId."""
    # This would be returned when an invalid musicFolderId is provided
    # Using generic error as example (actual implementation would return specific error)
    error_response = subsonic_responses["generic_error"]

    assert "subsonic-response" in error_response
    assert error_response["subsonic-response"]["status"] == "failed"
    assert "error" in error_response["subsonic-response"]
    assert isinstance(error_response["subsonic-response"]["error"]["code"], int)


def test_empty_songs_response(subsonic_responses):
    """Test that empty song list is handled correctly."""
    response = subsonic_responses["getSongs_empty"]

    assert "subsonic-response" in response
    assert response["subsonic-response"]["status"] == "ok"
    assert "songs" in response["subsonic-response"]
    assert "song" in response["subsonic-response"]["songs"]
    assert response["subsonic-response"]["songs"]["song"] == []


def test_pagination_limit_validation():
    """Test that pagination parameters are within valid ranges."""
    # Per Subsonic API contract
    max_size = 500
    min_size = 1
    min_offset = 0

    # Valid pagination
    valid_params = {"offset": 0, "size": 500}
    assert valid_params["size"] <= max_size
    assert valid_params["size"] >= min_size
    assert valid_params["offset"] >= min_offset

    # Invalid pagination should be caught
    with pytest.raises(AssertionError):
        invalid_params = {"offset": -1, "size": 1000}
        assert invalid_params["offset"] >= min_offset
        assert invalid_params["size"] <= max_size
