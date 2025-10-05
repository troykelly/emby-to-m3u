"""Unit tests for Subsonic to Emby track transformation logic."""

import json
import pytest
from pathlib import Path
from typing import Dict, List
from unittest.mock import Mock, MagicMock

from src.subsonic.models import SubsonicTrack
from src.subsonic.transform import (
    transform_genre,
    transform_duration,
    transform_musicbrainz_id,
    is_duplicate,
    detect_duplicates,
    transform_subsonic_track,
    TICKS_PER_SECOND,
)


# Fixtures

@pytest.fixture
def track_samples() -> Dict:
    """Load track samples from fixtures file."""
    fixture_path = Path(__file__).parent / "fixtures" / "track_samples.json"
    with open(fixture_path) as f:
        return json.load(f)


@pytest.fixture
def mock_playlist_manager():
    """Create a mock PlaylistManager for testing."""
    manager = Mock()
    manager.tracks = []
    manager.add_track = Mock()
    return manager


@pytest.fixture
def sample_subsonic_track() -> SubsonicTrack:
    """Create a sample SubsonicTrack for testing."""
    return SubsonicTrack(
        id="1",
        title="Stairway to Heaven",
        artist="Led Zeppelin",
        album="Led Zeppelin IV",
        duration=482,
        path="Led Zeppelin/Led Zeppelin IV/04 Stairway to Heaven.mp3",
        suffix="mp3",
        created="2024-01-01T00:00:00.000Z",
        genre="Rock",
        track=4,
        discNumber=1,
        year=1971,
    )


# Genre Transformation Tests

def test_genre_string_to_array():
    """Test genre transformation from string to array."""
    result = transform_genre("Rock")
    assert result == ["Rock"]
    assert isinstance(result, list)


def test_genre_empty():
    """Test genre transformation with None/empty values."""
    assert transform_genre(None) == []
    assert transform_genre("") == []


def test_genre_with_spaces():
    """Test genre transformation strips whitespace."""
    result = transform_genre(" Jazz ")
    assert result == ["Jazz"]


def test_genre_whitespace_only():
    """Test genre with only whitespace returns empty list."""
    result = transform_genre("   ")
    assert result == []


def test_genre_multiple_words():
    """Test genre with multiple words is preserved."""
    result = transform_genre("Progressive Rock")
    assert result == ["Progressive Rock"]


# Duration Transformation Tests

def test_duration_to_ticks():
    """Test duration conversion from seconds to ticks."""
    # 180 seconds = 1,800,000,000 ticks
    result = transform_duration(180)
    assert result == 1_800_000_000
    assert result == 180 * TICKS_PER_SECOND


def test_duration_zero():
    """Test zero duration conversion."""
    result = transform_duration(0)
    assert result == 0


def test_duration_large():
    """Test large duration conversion (1 hour)."""
    # 3600 seconds = 36,000,000,000 ticks
    result = transform_duration(3600)
    assert result == 36_000_000_000
    assert result == 3600 * TICKS_PER_SECOND


def test_duration_one_second():
    """Test single second conversion."""
    result = transform_duration(1)
    assert result == TICKS_PER_SECOND
    assert result == 10_000_000


def test_duration_typical_song():
    """Test typical song duration (3:45 = 225 seconds)."""
    result = transform_duration(225)
    assert result == 2_250_000_000


# MusicBrainz ID Transformation Tests

def test_musicbrainz_preserved():
    """Test MusicBrainz ID is correctly mapped to ProviderIds."""
    mb_id = "f3f72a0e-a554-4c8a-9c52-94e1d11b84b0"
    result = transform_musicbrainz_id(mb_id)

    assert "MusicBrainzTrack" in result
    assert result["MusicBrainzTrack"] == mb_id


def test_musicbrainz_missing():
    """Test None MusicBrainz ID returns empty dict."""
    result = transform_musicbrainz_id(None)
    assert result == {}
    assert isinstance(result, dict)


def test_musicbrainz_empty_string():
    """Test empty string MusicBrainz ID returns empty dict."""
    result = transform_musicbrainz_id("")
    assert result == {}


def test_musicbrainz_with_uuid_format():
    """Test MusicBrainz ID with standard UUID format."""
    mb_id = "8c7f4e8f-3ae1-4f15-9a6c-9f7c1b4f7e8f"
    result = transform_musicbrainz_id(mb_id)
    assert result["MusicBrainzTrack"] == mb_id


# Duplicate Detection Tests

def test_duplicate_same_metadata():
    """Test duplicate detection with identical metadata."""
    track1 = {
        "Id": "1",
        "Name": "Imagine",
        "Artists": ["John Lennon"],
        "Album": "Imagine"
    }
    track2 = {
        "Id": "2",
        "Name": "Imagine",
        "Artists": ["John Lennon"],
        "Album": "Imagine"
    }

    assert is_duplicate(track1, track2) is True


def test_duplicate_different_id():
    """Test that different IDs with same metadata are still duplicates."""
    track1 = {
        "Id": "100",
        "Name": "Song",
        "Artists": ["Artist"],
        "Album": "Album"
    }
    track2 = {
        "Id": "999",
        "Name": "Song",
        "Artists": ["Artist"],
        "Album": "Album"
    }

    assert is_duplicate(track1, track2) is True


def test_unique_tracks():
    """Test unique tracks are not detected as duplicates."""
    track1 = {
        "Id": "1",
        "Name": "Song A",
        "Artists": ["Artist A"],
        "Album": "Album A"
    }
    track2 = {
        "Id": "2",
        "Name": "Song B",
        "Artists": ["Artist B"],
        "Album": "Album B"
    }

    assert is_duplicate(track1, track2) is False


def test_case_insensitive_duplicate():
    """Test duplicate detection is case-insensitive."""
    track1 = {
        "Id": "1",
        "Name": "Rock Song",
        "Artists": ["The Band"],
        "Album": "Rock Album"
    }
    track2 = {
        "Id": "2",
        "Name": "rock song",
        "Artists": ["the band"],
        "Album": "ROCK ALBUM"
    }

    assert is_duplicate(track1, track2) is True


def test_duplicate_different_title():
    """Test tracks with different titles are not duplicates."""
    track1 = {
        "Id": "1",
        "Name": "Song A",
        "Artists": ["Artist"],
        "Album": "Album"
    }
    track2 = {
        "Id": "2",
        "Name": "Song B",
        "Artists": ["Artist"],
        "Album": "Album"
    }

    assert is_duplicate(track1, track2) is False


def test_duplicate_different_artist():
    """Test tracks with different artists are not duplicates."""
    track1 = {
        "Id": "1",
        "Name": "Song",
        "Artists": ["Artist A"],
        "Album": "Album"
    }
    track2 = {
        "Id": "2",
        "Name": "Song",
        "Artists": ["Artist B"],
        "Album": "Album"
    }

    assert is_duplicate(track1, track2) is False


def test_duplicate_different_album():
    """Test tracks with different albums are not duplicates."""
    track1 = {
        "Id": "1",
        "Name": "Song",
        "Artists": ["Artist"],
        "Album": "Album A"
    }
    track2 = {
        "Id": "2",
        "Name": "Song",
        "Artists": ["Artist"],
        "Album": "Album B"
    }

    assert is_duplicate(track1, track2) is False


def test_duplicate_with_whitespace():
    """Test duplicate detection handles whitespace correctly."""
    track1 = {
        "Id": "1",
        "Name": " Song ",
        "Artists": [" Artist "],
        "Album": " Album "
    }
    track2 = {
        "Id": "2",
        "Name": "Song",
        "Artists": ["Artist"],
        "Album": "Album"
    }

    assert is_duplicate(track1, track2) is True


def test_detect_duplicates_in_list():
    """Test detecting duplicates in a list of tracks."""
    tracks = [
        {"Id": "1", "Name": "Song", "Artists": ["Artist"], "Album": "Album"},
        {"Id": "2", "Name": "Song", "Artists": ["Artist"], "Album": "Album"},  # Duplicate
        {"Id": "3", "Name": "Different", "Artists": ["Artist"], "Album": "Album"},
        {"Id": "4", "Name": "Song", "Artists": ["Artist"], "Album": "Album"},  # Duplicate
    ]

    duplicates = detect_duplicates(tracks)

    # IDs 2 and 4 should be marked as duplicates (1 is kept as original)
    assert "2" in duplicates
    assert "4" in duplicates
    assert "1" not in duplicates
    assert "3" not in duplicates
    assert len(duplicates) == 2


def test_detect_duplicates_no_duplicates():
    """Test detect_duplicates with no duplicates."""
    tracks = [
        {"Id": "1", "Name": "Song A", "Artists": ["Artist A"], "Album": "Album A"},
        {"Id": "2", "Name": "Song B", "Artists": ["Artist B"], "Album": "Album B"},
        {"Id": "3", "Name": "Song C", "Artists": ["Artist C"], "Album": "Album C"},
    ]

    duplicates = detect_duplicates(tracks)
    assert len(duplicates) == 0


def test_detect_duplicates_empty_list():
    """Test detect_duplicates with empty list."""
    duplicates = detect_duplicates([])
    assert len(duplicates) == 0


# Complete Transformation Tests

def test_transform_complete(sample_subsonic_track, mock_playlist_manager):
    """Test complete track transformation with all fields."""
    result = transform_subsonic_track(sample_subsonic_track, mock_playlist_manager)

    # Verify core fields
    assert result["Id"] == "1"
    assert result["Name"] == "Stairway to Heaven"
    assert result["Artists"] == ["Led Zeppelin"]
    assert result["Album"] == "Led Zeppelin IV"
    assert result["Path"] == "Led Zeppelin/Led Zeppelin IV/04 Stairway to Heaven.mp3"

    # Verify transformed fields
    assert result["Genres"] == ["Rock"]
    assert result["RunTimeTicks"] == 482 * TICKS_PER_SECOND
    assert result["IndexNumber"] == 4
    assert result["ParentIndexNumber"] == 1
    assert result["ProductionYear"] == 1971

    # Verify ProviderIds
    assert result["ProviderIds"] == {}  # No MusicBrainz ID in this sample

    # Verify Subsonic metadata preserved
    assert result["_subsonic_id"] == "1"
    assert result["_subsonic_suffix"] == "mp3"
    assert result["_subsonic_created"] == "2024-01-01T00:00:00.000Z"


def test_subsonic_metadata_preserved(mock_playlist_manager):
    """Test that _subsonic_* fields are present in transformed track."""
    track = SubsonicTrack(
        id="123",
        title="Test Track",
        artist="Test Artist",
        album="Test Album",
        duration=300,
        path="test/path.flac",
        suffix="flac",
        created="2024-01-15T12:00:00.000Z",
        coverArt="cover-123",
        size=12345678,
        bitRate=320,
        contentType="audio/flac",
    )

    result = transform_subsonic_track(track, mock_playlist_manager)

    # Verify all Subsonic metadata is preserved
    assert result["_subsonic_id"] == "123"
    assert result["_subsonic_suffix"] == "flac"
    assert result["_subsonic_created"] == "2024-01-15T12:00:00.000Z"
    assert result["_subsonic_cover_art"] == "cover-123"
    assert result["_subsonic_size"] == 12345678
    assert result["_subsonic_bit_rate"] == 320
    assert result["_subsonic_content_type"] == "audio/flac"


def test_transform_with_musicbrainz(mock_playlist_manager):
    """Test transformation preserves MusicBrainz ID."""
    mb_id = "f3f72a0e-a554-4c8a-9c52-94e1d11b84b0"
    track = SubsonicTrack(
        id="2",
        title="Take Five",
        artist="Dave Brubeck",
        album="Time Out",
        duration=324,
        path="Dave Brubeck/Time Out/03 Take Five.flac",
        suffix="flac",
        created="2024-01-02T00:00:00.000Z",
        musicBrainzId=mb_id,
    )

    result = transform_subsonic_track(track, mock_playlist_manager)

    assert "MusicBrainzTrack" in result["ProviderIds"]
    assert result["ProviderIds"]["MusicBrainzTrack"] == mb_id


def test_transform_minimal_metadata(mock_playlist_manager):
    """Test transformation with minimal required metadata."""
    track = SubsonicTrack(
        id="999",
        title="Minimal Track",
        artist="Unknown Artist",
        album="Unknown Album",
        duration=0,
        path="unknown/path.mp3",
        suffix="mp3",
        created="2024-01-01T00:00:00.000Z",
    )

    result = transform_subsonic_track(track, mock_playlist_manager)

    # Verify core fields are present
    assert result["Id"] == "999"
    assert result["Name"] == "Minimal Track"
    assert result["Artists"] == ["Unknown Artist"]
    assert result["Album"] == "Unknown Album"
    assert result["RunTimeTicks"] == 0

    # Verify optional fields are None/empty
    assert result["Genres"] == []
    assert result["IndexNumber"] is None
    assert result["ParentIndexNumber"] is None
    assert result["ProductionYear"] is None
    assert result["ProviderIds"] == {}


def test_transform_with_fixture_samples(track_samples, mock_playlist_manager):
    """Test transformation using fixture samples."""
    for sample in track_samples["samples"]:
        # Create SubsonicTrack from sample
        track = SubsonicTrack(
            id=sample["id"],
            title=sample["title"],
            artist=sample["artist"],
            album=sample["album"],
            duration=sample["duration"],
            path=sample["path"],
            suffix=sample["suffix"],
            created=sample["created"],
            genre=sample.get("genre"),
            track=sample.get("track"),
            discNumber=sample.get("discNumber"),
            year=sample.get("year"),
            musicBrainzId=sample.get("musicBrainzId"),
        )

        result = transform_subsonic_track(track, mock_playlist_manager)

        # Verify basic transformation
        assert result["Id"] == sample["id"]
        assert result["Name"] == sample["title"]
        assert result["Artists"] == [sample["artist"]]
        assert result["Album"] == sample["album"]
        assert result["RunTimeTicks"] == sample["duration"] * TICKS_PER_SECOND

        # Verify genre transformation
        if sample.get("genre"):
            assert result["Genres"] == [sample["genre"]]
        else:
            assert result["Genres"] == []

        # Verify MusicBrainz ID if present
        if sample.get("musicBrainzId"):
            assert result["ProviderIds"]["MusicBrainzTrack"] == sample["musicBrainzId"]
        else:
            assert result["ProviderIds"] == {}


def test_transform_artists_array_format(mock_playlist_manager):
    """Test that artist is converted from string to array."""
    track = SubsonicTrack(
        id="test",
        title="Test",
        artist="Single Artist",
        album="Test Album",
        duration=100,
        path="test.mp3",
        suffix="mp3",
        created="2024-01-01T00:00:00.000Z",
    )

    result = transform_subsonic_track(track, mock_playlist_manager)

    # Subsonic single string artist should become Emby array
    assert isinstance(result["Artists"], list)
    assert len(result["Artists"]) == 1
    assert result["Artists"][0] == "Single Artist"


def test_transform_path_preserved(mock_playlist_manager):
    """Test that file path is preserved correctly."""
    original_path = "Artists/Led Zeppelin/Led Zeppelin IV/04 Stairway to Heaven.flac"
    track = SubsonicTrack(
        id="test",
        title="Test",
        artist="Artist",
        album="Album",
        duration=100,
        path=original_path,
        suffix="flac",
        created="2024-01-01T00:00:00.000Z",
    )

    result = transform_subsonic_track(track, mock_playlist_manager)

    assert result["Path"] == original_path


def test_transform_multiple_tracks(track_samples, mock_playlist_manager):
    """Test transforming multiple tracks maintains uniqueness."""
    transformed_tracks = []

    for sample in track_samples["samples"][:5]:  # Test first 5 samples
        track = SubsonicTrack(
            id=sample["id"],
            title=sample["title"],
            artist=sample["artist"],
            album=sample["album"],
            duration=sample["duration"],
            path=sample["path"],
            suffix=sample["suffix"],
            created=sample["created"],
        )

        result = transform_subsonic_track(track, mock_playlist_manager)
        transformed_tracks.append(result)

    # Verify all tracks are unique by ID
    ids = [t["Id"] for t in transformed_tracks]
    assert len(ids) == len(set(ids))

    # Verify all required fields are present
    for track in transformed_tracks:
        assert "Id" in track
        assert "Name" in track
        assert "Artists" in track
        assert "Album" in track
        assert "RunTimeTicks" in track
        assert "Path" in track
        assert "Genres" in track
        assert "ProviderIds" in track


# Edge Cases and Error Handling

def test_transform_none_playlist_manager():
    """Test transformation with None playlist_manager."""
    track = SubsonicTrack(
        id="1",
        title="Test",
        artist="Artist",
        album="Album",
        duration=100,
        path="test.mp3",
        suffix="mp3",
        created="2024-01-01T00:00:00.000Z",
    )

    # Should work fine - playlist_manager is not used in transformation
    result = transform_subsonic_track(track, None)
    assert result["Id"] == "1"
    assert result["Name"] == "Test"


def test_duplicate_with_missing_fields():
    """Test duplicate detection with missing optional fields."""
    track1 = {
        "Id": "1",
        "Name": "Song",
        "Artists": ["Artist"],
        "Album": "Album"
    }
    track2 = {
        "Id": "2",
        "Name": "Song",
        # Missing Artists field
        "Album": "Album"
    }

    # Should not crash, should handle missing fields gracefully
    result = is_duplicate(track1, track2)
    assert result is False  # Different because one has no artist


def test_duplicate_with_empty_artists():
    """Test duplicate detection with empty Artists array."""
    track1 = {
        "Id": "1",
        "Name": "Song",
        "Artists": [],
        "Album": "Album"
    }
    track2 = {
        "Id": "2",
        "Name": "Song",
        "Artists": [],
        "Album": "Album"
    }

    # Both have empty artists, should be duplicates based on name and album
    result = is_duplicate(track1, track2)
    assert result is True
