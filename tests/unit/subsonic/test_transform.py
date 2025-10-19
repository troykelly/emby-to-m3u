"""
Comprehensive tests for src/subsonic/transform.py to achieve >70% coverage.

Tests cover:
- transform_genre: string to list conversion, None/empty handling
- transform_duration: seconds to ticks conversion
- transform_musicbrainz_id: ID mapping to ProviderIds format
- is_duplicate: track duplicate detection with case-insensitive comparison
- detect_duplicates: batch duplicate detection
- transform_subsonic_track: full track transformation with all field mapping
"""
import pytest
from unittest.mock import Mock, MagicMock
from typing import Dict, List

from src.subsonic.transform import (
    transform_genre,
    transform_duration,
    transform_musicbrainz_id,
    is_duplicate,
    detect_duplicates,
    transform_subsonic_track,
    TICKS_PER_SECOND,
)
from src.subsonic.models import SubsonicTrack


class TestTransformGenre:
    """Tests for transform_genre function."""

    def test_transform_genre_valid_string(self):
        """Test genre transformation with valid string."""
        result = transform_genre("Rock")
        assert result == ["Rock"]

    def test_transform_genre_with_whitespace(self):
        """Test genre transformation strips whitespace."""
        result = transform_genre("  Jazz  ")
        assert result == ["Jazz"]

    def test_transform_genre_none(self):
        """Test genre transformation with None returns empty list."""
        result = transform_genre(None)
        assert result == []

    def test_transform_genre_empty_string(self):
        """Test genre transformation with empty string returns empty list."""
        result = transform_genre("")
        assert result == []

    def test_transform_genre_whitespace_only(self):
        """Test genre transformation with whitespace-only string returns empty list."""
        result = transform_genre("   ")
        assert result == []

    def test_transform_genre_special_characters(self):
        """Test genre transformation preserves special characters."""
        result = transform_genre("Hip-Hop/R&B")
        assert result == ["Hip-Hop/R&B"]


class TestTransformDuration:
    """Tests for transform_duration function."""

    def test_transform_duration_standard(self):
        """Test standard duration conversion (3 minutes)."""
        result = transform_duration(180)
        assert result == 1_800_000_000
        assert result == 180 * TICKS_PER_SECOND

    def test_transform_duration_zero(self):
        """Test zero duration."""
        result = transform_duration(0)
        assert result == 0

    def test_transform_duration_one_second(self):
        """Test one second conversion."""
        result = transform_duration(1)
        assert result == 10_000_000
        assert result == TICKS_PER_SECOND

    def test_transform_duration_one_hour(self):
        """Test one hour conversion (3600 seconds)."""
        result = transform_duration(3600)
        assert result == 36_000_000_000

    def test_transform_duration_large_value(self):
        """Test large duration value."""
        result = transform_duration(10000)
        assert result == 100_000_000_000


class TestTransformMusicBrainzId:
    """Tests for transform_musicbrainz_id function."""

    def test_transform_musicbrainz_id_valid(self):
        """Test MusicBrainz ID transformation with valid UUID."""
        mb_id = "f3f72a0e-a554-4c8a-9c52-94e1d11b84b0"
        result = transform_musicbrainz_id(mb_id)
        assert result == {"MusicBrainzTrack": mb_id}

    def test_transform_musicbrainz_id_none(self):
        """Test MusicBrainz ID transformation with None returns empty dict."""
        result = transform_musicbrainz_id(None)
        assert result == {}

    def test_transform_musicbrainz_id_empty_string(self):
        """Test MusicBrainz ID transformation with empty string returns empty dict."""
        result = transform_musicbrainz_id("")
        assert result == {}

    def test_transform_musicbrainz_id_preserves_format(self):
        """Test that MusicBrainz ID format is preserved exactly."""
        mb_id = "abc-123-def"
        result = transform_musicbrainz_id(mb_id)
        assert result == {"MusicBrainzTrack": "abc-123-def"}


class TestIsDuplicate:
    """Tests for is_duplicate function."""

    def test_is_duplicate_exact_match(self):
        """Test duplicate detection with exact match."""
        track1 = {"Name": "Song", "Artists": ["Artist"], "Album": "Album"}
        track2 = {"Name": "Song", "Artists": ["Artist"], "Album": "Album"}
        assert is_duplicate(track1, track2) is True

    def test_is_duplicate_case_insensitive(self):
        """Test duplicate detection is case-insensitive."""
        track1 = {"Name": "Song", "Artists": ["Artist"], "Album": "Album"}
        track2 = {"Name": "SONG", "Artists": ["ARTIST"], "Album": "ALBUM"}
        assert is_duplicate(track1, track2) is True

    def test_is_duplicate_with_whitespace(self):
        """Test duplicate detection strips whitespace."""
        track1 = {"Name": "Song", "Artists": ["Artist"], "Album": "Album"}
        track2 = {"Name": "  Song  ", "Artists": ["  Artist  "], "Album": "  Album  "}
        assert is_duplicate(track1, track2) is True

    def test_is_duplicate_different_album(self):
        """Test non-duplicate with different album."""
        track1 = {"Name": "Song", "Artists": ["Artist"], "Album": "Album1"}
        track2 = {"Name": "Song", "Artists": ["Artist"], "Album": "Album2"}
        assert is_duplicate(track1, track2) is False

    def test_is_duplicate_different_title(self):
        """Test non-duplicate with different title."""
        track1 = {"Name": "Song1", "Artists": ["Artist"], "Album": "Album"}
        track2 = {"Name": "Song2", "Artists": ["Artist"], "Album": "Album"}
        assert is_duplicate(track1, track2) is False

    def test_is_duplicate_different_artist(self):
        """Test non-duplicate with different artist."""
        track1 = {"Name": "Song", "Artists": ["Artist1"], "Album": "Album"}
        track2 = {"Name": "Song", "Artists": ["Artist2"], "Album": "Album"}
        assert is_duplicate(track1, track2) is False

    def test_is_duplicate_empty_artists_list(self):
        """Test duplicate detection with empty artists list."""
        track1 = {"Name": "Song", "Artists": [], "Album": "Album"}
        track2 = {"Name": "Song", "Artists": [], "Album": "Album"}
        assert is_duplicate(track1, track2) is True

    def test_is_duplicate_missing_fields(self):
        """Test duplicate detection with missing fields."""
        track1 = {"Name": "Song"}
        track2 = {"Name": "Song"}
        assert is_duplicate(track1, track2) is True

    def test_is_duplicate_multiple_artists_uses_first(self):
        """Test that only first artist is compared."""
        track1 = {"Name": "Song", "Artists": ["Artist1", "Artist2"], "Album": "Album"}
        track2 = {"Name": "Song", "Artists": ["Artist1", "Artist3"], "Album": "Album"}
        assert is_duplicate(track1, track2) is True


class TestDetectDuplicates:
    """Tests for detect_duplicates function."""

    def test_detect_duplicates_single_duplicate(self):
        """Test detecting a single duplicate track."""
        tracks = [
            {"Id": "1", "Name": "Song", "Artists": ["Artist"], "Album": "Album"},
            {"Id": "2", "Name": "Song", "Artists": ["Artist"], "Album": "Album"},
            {"Id": "3", "Name": "Different", "Artists": ["Artist"], "Album": "Album"},
        ]
        duplicates = detect_duplicates(tracks)
        assert duplicates == {"2"}

    def test_detect_duplicates_multiple_duplicates(self):
        """Test detecting multiple duplicate tracks."""
        tracks = [
            {"Id": "1", "Name": "Song", "Artists": ["Artist"], "Album": "Album"},
            {"Id": "2", "Name": "Song", "Artists": ["Artist"], "Album": "Album"},
            {"Id": "3", "Name": "Song", "Artists": ["Artist"], "Album": "Album"},
        ]
        duplicates = detect_duplicates(tracks)
        assert duplicates == {"2", "3"}

    def test_detect_duplicates_no_duplicates(self):
        """Test with no duplicates present."""
        tracks = [
            {"Id": "1", "Name": "Song1", "Artists": ["Artist"], "Album": "Album"},
            {"Id": "2", "Name": "Song2", "Artists": ["Artist"], "Album": "Album"},
            {"Id": "3", "Name": "Song3", "Artists": ["Artist"], "Album": "Album"},
        ]
        duplicates = detect_duplicates(tracks)
        assert duplicates == set()

    def test_detect_duplicates_empty_list(self):
        """Test with empty track list."""
        duplicates = detect_duplicates([])
        assert duplicates == set()

    def test_detect_duplicates_preserves_first_occurrence(self):
        """Test that first occurrence is kept, later ones marked as duplicates."""
        tracks = [
            {"Id": "first", "Name": "Song", "Artists": ["Artist"], "Album": "Album"},
            {"Id": "second", "Name": "Song", "Artists": ["Artist"], "Album": "Album"},
        ]
        duplicates = detect_duplicates(tracks)
        assert "first" not in duplicates
        assert "second" in duplicates

    def test_detect_duplicates_case_insensitive(self):
        """Test duplicate detection is case-insensitive."""
        tracks = [
            {"Id": "1", "Name": "Song", "Artists": ["Artist"], "Album": "Album"},
            {"Id": "2", "Name": "SONG", "Artists": ["ARTIST"], "Album": "ALBUM"},
        ]
        duplicates = detect_duplicates(tracks)
        assert duplicates == {"2"}


class TestTransformSubsonicTrack:
    """Tests for transform_subsonic_track function."""

    def create_sample_track(self, **overrides) -> SubsonicTrack:
        """Create a sample SubsonicTrack for testing."""
        defaults = {
            "id": "123",
            "title": "Stairway to Heaven",
            "artist": "Led Zeppelin",
            "album": "Led Zeppelin IV",
            "duration": 482,
            "path": "Led Zeppelin/Led Zeppelin IV/04 Stairway to Heaven.mp3",
            "suffix": "mp3",
            "created": "2024-01-01T00:00:00.000Z",
            "genre": "Rock",
            "track": 4,
            "discNumber": 1,
            "year": 1971,
            "musicBrainzId": "f3f72a0e-a554-4c8a-9c52-94e1d11b84b0",
            "coverArt": "art-123",
            "size": 7123456,
            "bitRate": 320,
            "contentType": "audio/mpeg",
        }
        defaults.update(overrides)
        return SubsonicTrack(**defaults)

    def test_transform_subsonic_track_all_fields(self):
        """Test full track transformation with all fields populated."""
        track = self.create_sample_track()
        playlist_manager = Mock()

        result = transform_subsonic_track(track, playlist_manager)

        # Core metadata
        assert result["Id"] == "123"
        assert result["Name"] == "Stairway to Heaven"
        assert result["Artists"] == ["Led Zeppelin"]
        assert result["Album"] == "Led Zeppelin IV"
        assert result["RunTimeTicks"] == 482 * TICKS_PER_SECOND
        assert result["Path"] == "Led Zeppelin/Led Zeppelin IV/04 Stairway to Heaven.mp3"

        # Optional metadata
        assert result["Genres"] == ["Rock"]
        assert result["IndexNumber"] == 4
        assert result["ParentIndexNumber"] == 1
        assert result["ProductionYear"] == 1971

        # Provider IDs
        assert result["ProviderIds"] == {"MusicBrainzTrack": "f3f72a0e-a554-4c8a-9c52-94e1d11b84b0"}

        # Subsonic metadata
        assert result["_subsonic_id"] == "123"
        assert result["_subsonic_suffix"] == "mp3"
        assert result["_subsonic_created"] == "2024-01-01T00:00:00.000Z"
        assert result["_subsonic_cover_art"] == "art-123"
        assert result["_subsonic_size"] == 7123456
        assert result["_subsonic_bit_rate"] == 320
        assert result["_subsonic_content_type"] == "audio/mpeg"

    def test_transform_subsonic_track_minimal_fields(self):
        """Test track transformation with only required fields."""
        track = SubsonicTrack(
            id="456",
            title="Test Song",
            artist="Test Artist",
            album="Test Album",
            duration=180,
            path="/music/test.mp3",
            suffix="mp3",
            created="2024-01-01T00:00:00.000Z",
        )
        playlist_manager = Mock()

        result = transform_subsonic_track(track, playlist_manager)

        # Core fields
        assert result["Id"] == "456"
        assert result["Name"] == "Test Song"
        assert result["Artists"] == ["Test Artist"]
        assert result["Album"] == "Test Album"
        assert result["RunTimeTicks"] == 1_800_000_000
        assert result["Path"] == "/music/test.mp3"

        # Optional fields should be None or empty
        assert result["Genres"] == []
        assert result["IndexNumber"] is None
        assert result["ParentIndexNumber"] is None
        assert result["ProductionYear"] is None
        assert result["ProviderIds"] == {}

    def test_transform_subsonic_track_no_genre(self):
        """Test track transformation with no genre."""
        track = self.create_sample_track(genre=None)
        playlist_manager = Mock()

        result = transform_subsonic_track(track, playlist_manager)

        assert result["Genres"] == []

    def test_transform_subsonic_track_no_musicbrainz_id(self):
        """Test track transformation without MusicBrainz ID."""
        track = self.create_sample_track(musicBrainzId=None)
        playlist_manager = Mock()

        result = transform_subsonic_track(track, playlist_manager)

        assert result["ProviderIds"] == {}

    def test_transform_subsonic_track_zero_duration(self):
        """Test track transformation with zero duration."""
        track = self.create_sample_track(duration=0)
        playlist_manager = Mock()

        result = transform_subsonic_track(track, playlist_manager)

        assert result["RunTimeTicks"] == 0

    def test_transform_subsonic_track_no_track_number(self):
        """Test track transformation without track number."""
        track = self.create_sample_track(track=None)
        playlist_manager = Mock()

        result = transform_subsonic_track(track, playlist_manager)

        assert result["IndexNumber"] is None

    def test_transform_subsonic_track_no_disc_number(self):
        """Test track transformation without disc number."""
        track = self.create_sample_track(discNumber=None)
        playlist_manager = Mock()

        result = transform_subsonic_track(track, playlist_manager)

        assert result["ParentIndexNumber"] is None

    def test_transform_subsonic_track_no_year(self):
        """Test track transformation without year."""
        track = self.create_sample_track(year=None)
        playlist_manager = Mock()

        result = transform_subsonic_track(track, playlist_manager)

        assert result["ProductionYear"] is None

    def test_transform_subsonic_track_preserves_subsonic_metadata(self):
        """Test that original Subsonic metadata is preserved."""
        track = self.create_sample_track()
        playlist_manager = Mock()

        result = transform_subsonic_track(track, playlist_manager)

        # All Subsonic fields should be preserved with _ prefix
        assert "_subsonic_id" in result
        assert "_subsonic_suffix" in result
        assert "_subsonic_created" in result
        assert "_subsonic_cover_art" in result
        assert "_subsonic_size" in result
        assert "_subsonic_bit_rate" in result
        assert "_subsonic_content_type" in result

    def test_transform_subsonic_track_artist_to_list(self):
        """Test that single artist is converted to list."""
        track = self.create_sample_track(artist="Single Artist")
        playlist_manager = Mock()

        result = transform_subsonic_track(track, playlist_manager)

        assert isinstance(result["Artists"], list)
        assert result["Artists"] == ["Single Artist"]
        assert len(result["Artists"]) == 1

    def test_transform_subsonic_track_genre_whitespace_stripped(self):
        """Test that genre whitespace is stripped."""
        track = self.create_sample_track(genre="  Progressive Rock  ")
        playlist_manager = Mock()

        result = transform_subsonic_track(track, playlist_manager)

        assert result["Genres"] == ["Progressive Rock"]

    def test_transform_subsonic_track_long_duration(self):
        """Test track transformation with very long duration."""
        track = self.create_sample_track(duration=86400)  # 24 hours
        playlist_manager = Mock()

        result = transform_subsonic_track(track, playlist_manager)

        assert result["RunTimeTicks"] == 86400 * TICKS_PER_SECOND
        assert result["RunTimeTicks"] == 864_000_000_000

    def test_transform_subsonic_track_special_characters_in_title(self):
        """Test track transformation preserves special characters."""
        track = self.create_sample_track(title="Ain't No Mountain High Enough")
        playlist_manager = Mock()

        result = transform_subsonic_track(track, playlist_manager)

        assert result["Name"] == "Ain't No Mountain High Enough"

    def test_transform_subsonic_track_unicode_characters(self):
        """Test track transformation with Unicode characters."""
        track = self.create_sample_track(
            title="Café del Mar",
            artist="José González",
            album="Señor"
        )
        playlist_manager = Mock()

        result = transform_subsonic_track(track, playlist_manager)

        assert result["Name"] == "Café del Mar"
        assert result["Artists"] == ["José González"]
        assert result["Album"] == "Señor"
