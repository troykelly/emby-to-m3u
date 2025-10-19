"""
Comprehensive tests for src/subsonic/transform.py to achieve 90%+ coverage.

This test suite provides extensive coverage of all transformation functions with:
- All field mappings and transformations
- Edge cases (missing fields, null values, empty strings)
- Data type conversions and validations
- Error handling for malformed input
- Boundary value testing
- Unicode and special character handling
- Performance and memory considerations

Coverage Areas:
1. transform_genre: Genre string to list conversion
2. transform_duration: Seconds to Emby ticks conversion
3. transform_musicbrainz_id: MusicBrainz ID mapping
4. is_duplicate: Duplicate track detection
5. detect_duplicates: Batch duplicate detection
6. transform_subsonic_track: Complete track transformation

Test Strategy:
- Equivalence partitioning for input domains
- Boundary value analysis for numeric fields
- Error guessing for malformed inputs
- State transition testing for complex transformations
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from typing import Dict, List
import logging

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


# ============================================================================
# Test Data Fixtures
# ============================================================================

@pytest.fixture
def sample_subsonic_track():
    """Create a fully populated sample SubsonicTrack for testing."""
    return SubsonicTrack(
        id="track-123",
        title="Bohemian Rhapsody",
        artist="Queen",
        album="A Night at the Opera",
        duration=354,  # 5:54
        path="/music/Queen/A Night at the Opera/01 Bohemian Rhapsody.flac",
        suffix="flac",
        created="2024-01-15T10:30:00.000Z",
        parent="album-456",
        albumId="album-456",
        artistId="artist-789",
        isDir=False,
        isVideo=False,
        type="music",
        genre="Progressive Rock",
        track=1,
        discNumber=1,
        year=1975,
        musicBrainzId="b1a9c0e7-0f12-4fa4-8f5a-9c3d2e1b7a0f",
        coverArt="cover-456",
        size=42857143,  # ~41 MB
        bitRate=1411,  # CD quality
        contentType="audio/flac",
    )


@pytest.fixture
def minimal_subsonic_track():
    """Create a SubsonicTrack with only required fields."""
    return SubsonicTrack(
        id="min-001",
        title="Minimal Track",
        artist="Test Artist",
        album="Test Album",
        duration=180,
        path="/music/test.mp3",
        suffix="mp3",
        created="2024-01-01T00:00:00.000Z",
    )


@pytest.fixture
def mock_playlist_manager():
    """Create a mock PlaylistManager for testing."""
    return Mock()


# ============================================================================
# Genre Transformation Tests
# ============================================================================

class TestTransformGenreComprehensive:
    """Comprehensive tests for transform_genre function."""

    # Valid inputs
    def test_single_word_genre(self):
        """Test transformation of single-word genre."""
        assert transform_genre("Rock") == ["Rock"]
        assert transform_genre("Jazz") == ["Jazz"]
        assert transform_genre("Classical") == ["Classical"]

    def test_multi_word_genre(self):
        """Test transformation of multi-word genres."""
        assert transform_genre("Progressive Rock") == ["Progressive Rock"]
        assert transform_genre("Death Metal") == ["Death Metal"]
        assert transform_genre("Smooth Jazz") == ["Smooth Jazz"]

    def test_genre_with_hyphens(self):
        """Test genres containing hyphens."""
        assert transform_genre("Hip-Hop") == ["Hip-Hop"]
        assert transform_genre("Post-Rock") == ["Post-Rock"]
        assert transform_genre("Neo-Soul") == ["Neo-Soul"]

    def test_genre_with_slashes(self):
        """Test genres with slash separators."""
        assert transform_genre("Hip-Hop/R&B") == ["Hip-Hop/R&B"]
        assert transform_genre("Rock/Pop") == ["Rock/Pop"]

    def test_genre_with_ampersands(self):
        """Test genres containing ampersands."""
        assert transform_genre("Country & Western") == ["Country & Western"]
        assert transform_genre("Rhythm & Blues") == ["Rhythm & Blues"]

    def test_genre_with_numbers(self):
        """Test genres containing numbers."""
        assert transform_genre("80s Pop") == ["80s Pop"]
        assert transform_genre("90s Rock") == ["90s Rock"]

    # Whitespace handling
    def test_genre_leading_whitespace(self):
        """Test genre with leading whitespace is stripped."""
        assert transform_genre("  Jazz") == ["Jazz"]
        assert transform_genre("\t\tRock") == ["Rock"]

    def test_genre_trailing_whitespace(self):
        """Test genre with trailing whitespace is stripped."""
        assert transform_genre("Jazz  ") == ["Jazz"]
        assert transform_genre("Rock\t\t") == ["Rock"]

    def test_genre_both_whitespace(self):
        """Test genre with whitespace on both sides."""
        assert transform_genre("  Classical  ") == ["Classical"]
        assert transform_genre("\t Metal \n") == ["Metal"]

    def test_genre_internal_whitespace_preserved(self):
        """Test that internal whitespace is preserved."""
        assert transform_genre("  Progressive  Rock  ") == ["Progressive  Rock"]

    # Null and empty handling
    def test_genre_none_returns_empty_list(self):
        """Test None genre returns empty list."""
        assert transform_genre(None) == []

    def test_genre_empty_string_returns_empty_list(self):
        """Test empty string returns empty list."""
        assert transform_genre("") == []

    def test_genre_whitespace_only_returns_empty_list(self):
        """Test whitespace-only string returns empty list."""
        assert transform_genre("   ") == []
        assert transform_genre("\t\n") == []
        assert transform_genre("  \t  \n  ") == []

    # Special characters and Unicode
    def test_genre_unicode_characters(self):
        """Test genres with Unicode characters."""
        assert transform_genre("Música Popular Brasileira") == ["Música Popular Brasileira"]
        assert transform_genre("Café del Mar") == ["Café del Mar"]
        assert transform_genre("日本のポップ") == ["日本のポップ"]

    def test_genre_special_symbols(self):
        """Test genres with various special symbols."""
        assert transform_genre("Rock & Roll") == ["Rock & Roll"]
        assert transform_genre("Drum 'n' Bass") == ["Drum 'n' Bass"]
        assert transform_genre("Post-Punk/New Wave") == ["Post-Punk/New Wave"]

    def test_genre_parentheses_and_brackets(self):
        """Test genres with parentheses and brackets."""
        assert transform_genre("Alternative (Indie)") == ["Alternative (Indie)"]
        assert transform_genre("Jazz [Contemporary]") == ["Jazz [Contemporary]"]

    # Edge cases
    def test_genre_single_character(self):
        """Test single character genre."""
        assert transform_genre("A") == ["A"]

    def test_genre_very_long_string(self):
        """Test very long genre string."""
        long_genre = "A" * 1000
        result = transform_genre(long_genre)
        assert result == [long_genre]
        assert len(result[0]) == 1000

    def test_genre_case_sensitivity(self):
        """Test that case is preserved."""
        assert transform_genre("ROCK") == ["ROCK"]
        assert transform_genre("rock") == ["rock"]
        assert transform_genre("RoCk") == ["RoCk"]

    # Return type validation
    def test_genre_always_returns_list(self):
        """Test that return type is always a list."""
        assert isinstance(transform_genre("Rock"), list)
        assert isinstance(transform_genre(None), list)
        assert isinstance(transform_genre(""), list)

    def test_genre_list_length(self):
        """Test returned list has correct length."""
        assert len(transform_genre("Rock")) == 1
        assert len(transform_genre(None)) == 0
        assert len(transform_genre("")) == 0


# ============================================================================
# Duration Transformation Tests
# ============================================================================

class TestTransformDurationComprehensive:
    """Comprehensive tests for transform_duration function."""

    # Standard conversions
    def test_zero_duration(self):
        """Test zero duration conversion."""
        assert transform_duration(0) == 0

    def test_one_second(self):
        """Test one second conversion."""
        assert transform_duration(1) == TICKS_PER_SECOND
        assert transform_duration(1) == 10_000_000

    def test_one_minute(self):
        """Test one minute (60 seconds) conversion."""
        assert transform_duration(60) == 600_000_000

    def test_one_hour(self):
        """Test one hour (3600 seconds) conversion."""
        assert transform_duration(3600) == 36_000_000_000

    def test_standard_song_duration(self):
        """Test typical 3-minute song duration."""
        assert transform_duration(180) == 1_800_000_000

    def test_long_song_duration(self):
        """Test long song (10 minutes)."""
        assert transform_duration(600) == 6_000_000_000

    # Boundary values
    def test_very_short_duration(self):
        """Test very short durations."""
        assert transform_duration(1) == 10_000_000
        assert transform_duration(5) == 50_000_000

    def test_very_long_duration(self):
        """Test very long durations (symphonies, audiobooks)."""
        one_day_seconds = 86400
        assert transform_duration(one_day_seconds) == 864_000_000_000

    def test_maximum_reasonable_duration(self):
        """Test maximum reasonable duration (e.g., 24 hours)."""
        max_duration = 86400
        result = transform_duration(max_duration)
        assert result == 864_000_000_000
        assert result > 0

    # Mathematical accuracy
    def test_conversion_factor_accuracy(self):
        """Test conversion factor is correctly applied."""
        for seconds in [1, 10, 100, 1000, 10000]:
            expected = seconds * 10_000_000
            assert transform_duration(seconds) == expected

    def test_no_rounding_errors(self):
        """Test no rounding errors in conversion."""
        # Integer multiplication should be exact
        assert transform_duration(123) == 1_230_000_000
        assert transform_duration(456) == 4_560_000_000
        assert transform_duration(789) == 7_890_000_000

    # Return type validation
    def test_return_type_is_int(self):
        """Test return type is integer."""
        result = transform_duration(180)
        assert isinstance(result, int)

    def test_result_always_positive_or_zero(self):
        """Test result is always non-negative."""
        assert transform_duration(0) >= 0
        assert transform_duration(100) > 0
        assert transform_duration(1000) > 0

    # Real-world examples
    def test_bohemian_rhapsody_duration(self):
        """Test Bohemian Rhapsody duration (5:54 = 354 seconds)."""
        assert transform_duration(354) == 3_540_000_000

    def test_stairway_to_heaven_duration(self):
        """Test Stairway to Heaven duration (8:02 = 482 seconds)."""
        assert transform_duration(482) == 4_820_000_000

    def test_in_a_gadda_da_vida_duration(self):
        """Test In-A-Gadda-Da-Vida duration (17:05 = 1025 seconds)."""
        assert transform_duration(1025) == 10_250_000_000

    # Edge cases with large numbers
    def test_large_duration_no_overflow(self):
        """Test large durations don't cause overflow."""
        week_in_seconds = 604800  # 7 days
        result = transform_duration(week_in_seconds)
        assert result == 6_048_000_000_000
        assert result > 0

    def test_duration_precision(self):
        """Test that exact tick values are preserved."""
        test_values = [1, 2, 3, 5, 10, 30, 60, 120, 300, 600]
        for seconds in test_values:
            ticks = transform_duration(seconds)
            # Verify we can recover the original value
            assert ticks // TICKS_PER_SECOND == seconds


# ============================================================================
# MusicBrainz ID Transformation Tests
# ============================================================================

class TestTransformMusicBrainzIdComprehensive:
    """Comprehensive tests for transform_musicbrainz_id function."""

    # Valid UUIDs
    def test_valid_uuid_v4(self):
        """Test valid UUID v4 format."""
        mb_id = "f3f72a0e-a554-4c8a-9c52-94e1d11b84b0"
        result = transform_musicbrainz_id(mb_id)
        assert result == {"MusicBrainzTrack": mb_id}

    def test_valid_uuid_uppercase(self):
        """Test UUID with uppercase letters."""
        mb_id = "F3F72A0E-A554-4C8A-9C52-94E1D11B84B0"
        result = transform_musicbrainz_id(mb_id)
        assert result == {"MusicBrainzTrack": mb_id}

    def test_valid_uuid_mixed_case(self):
        """Test UUID with mixed case."""
        mb_id = "F3f72A0e-a554-4c8A-9C52-94e1d11b84b0"
        result = transform_musicbrainz_id(mb_id)
        assert result == {"MusicBrainzTrack": mb_id}

    # Null and empty handling
    def test_none_returns_empty_dict(self):
        """Test None returns empty dictionary."""
        assert transform_musicbrainz_id(None) == {}

    def test_empty_string_returns_empty_dict(self):
        """Test empty string returns empty dictionary."""
        assert transform_musicbrainz_id("") == {}

    # Non-standard but accepted IDs
    def test_non_uuid_id_format(self):
        """Test non-standard ID format (some servers use custom IDs)."""
        custom_id = "custom-mb-id-12345"
        result = transform_musicbrainz_id(custom_id)
        assert result == {"MusicBrainzTrack": custom_id}

    def test_numeric_only_id(self):
        """Test numeric-only ID."""
        numeric_id = "123456789"
        result = transform_musicbrainz_id(numeric_id)
        assert result == {"MusicBrainzTrack": numeric_id}

    def test_alphanumeric_id(self):
        """Test alphanumeric ID without hyphens."""
        alpha_id = "abc123def456"
        result = transform_musicbrainz_id(alpha_id)
        assert result == {"MusicBrainzTrack": alpha_id}

    # Special cases
    def test_id_with_spaces_preserved(self):
        """Test that spaces in ID are preserved (though unusual)."""
        spaced_id = "id with spaces"
        result = transform_musicbrainz_id(spaced_id)
        assert result == {"MusicBrainzTrack": spaced_id}

    def test_very_long_id(self):
        """Test very long ID string."""
        long_id = "a" * 1000
        result = transform_musicbrainz_id(long_id)
        assert result == {"MusicBrainzTrack": long_id}

    def test_single_character_id(self):
        """Test single character ID."""
        result = transform_musicbrainz_id("x")
        assert result == {"MusicBrainzTrack": "x"}

    # Return format validation
    def test_return_type_is_dict(self):
        """Test return type is always dictionary."""
        assert isinstance(transform_musicbrainz_id("valid-id"), dict)
        assert isinstance(transform_musicbrainz_id(None), dict)
        assert isinstance(transform_musicbrainz_id(""), dict)

    def test_return_dict_has_correct_key(self):
        """Test returned dictionary has correct key."""
        result = transform_musicbrainz_id("test-id")
        assert "MusicBrainzTrack" in result
        assert len(result) == 1

    def test_empty_dict_when_falsy(self):
        """Test empty dict is returned for all falsy values."""
        assert transform_musicbrainz_id(None) == {}
        assert transform_musicbrainz_id("") == {}
        assert len(transform_musicbrainz_id(None)) == 0

    # Real-world MusicBrainz IDs
    def test_real_musicbrainz_track_ids(self):
        """Test with actual MusicBrainz track IDs."""
        # These are real track IDs from MusicBrainz
        real_ids = [
            "b1a9c0e7-0f12-4fa4-8f5a-9c3d2e1b7a0f",  # Example track
            "5b11f4ce-a62d-471e-81fc-a69a8278c7da",  # Another example
        ]
        for mb_id in real_ids:
            result = transform_musicbrainz_id(mb_id)
            assert result == {"MusicBrainzTrack": mb_id}
            assert len(result) == 1


# ============================================================================
# Duplicate Detection Tests
# ============================================================================

class TestIsDuplicateComprehensive:
    """Comprehensive tests for is_duplicate function."""

    # Exact matches
    def test_exact_match_all_fields(self):
        """Test exact duplicate detection."""
        track1 = {"Name": "Song", "Artists": ["Artist"], "Album": "Album"}
        track2 = {"Name": "Song", "Artists": ["Artist"], "Album": "Album"}
        assert is_duplicate(track1, track2) is True

    # Case insensitivity
    def test_case_insensitive_title(self):
        """Test case-insensitive title comparison."""
        track1 = {"Name": "Song Name", "Artists": ["Artist"], "Album": "Album"}
        track2 = {"Name": "SONG NAME", "Artists": ["Artist"], "Album": "Album"}
        assert is_duplicate(track1, track2) is True

    def test_case_insensitive_artist(self):
        """Test case-insensitive artist comparison."""
        track1 = {"Name": "Song", "Artists": ["Led Zeppelin"], "Album": "Album"}
        track2 = {"Name": "Song", "Artists": ["LED ZEPPELIN"], "Album": "Album"}
        assert is_duplicate(track1, track2) is True

    def test_case_insensitive_album(self):
        """Test case-insensitive album comparison."""
        track1 = {"Name": "Song", "Artists": ["Artist"], "Album": "Abbey Road"}
        track2 = {"Name": "Song", "Artists": ["Artist"], "Album": "ABBEY ROAD"}
        assert is_duplicate(track1, track2) is True

    def test_mixed_case_all_fields(self):
        """Test mixed case in all fields."""
        track1 = {"Name": "BoHeMiAn RhApSoDy", "Artists": ["QuEeN"], "Album": "A NiGhT aT tHe OpErA"}
        track2 = {"Name": "BOHEMIAN RHAPSODY", "Artists": ["queen"], "Album": "a night at the opera"}
        assert is_duplicate(track1, track2) is True

    # Whitespace handling
    def test_whitespace_in_title(self):
        """Test whitespace stripping in title."""
        track1 = {"Name": "Song", "Artists": ["Artist"], "Album": "Album"}
        track2 = {"Name": "  Song  ", "Artists": ["Artist"], "Album": "Album"}
        assert is_duplicate(track1, track2) is True

    def test_whitespace_in_artist(self):
        """Test whitespace stripping in artist."""
        track1 = {"Name": "Song", "Artists": ["Artist"], "Album": "Album"}
        track2 = {"Name": "Song", "Artists": ["  Artist  "], "Album": "Album"}
        assert is_duplicate(track1, track2) is True

    def test_whitespace_in_album(self):
        """Test whitespace stripping in album."""
        track1 = {"Name": "Song", "Artists": ["Artist"], "Album": "Album"}
        track2 = {"Name": "Song", "Artists": ["Artist"], "Album": "  Album  "}
        assert is_duplicate(track1, track2) is True

    def test_tabs_and_newlines(self):
        """Test handling of tabs and newlines."""
        track1 = {"Name": "Song", "Artists": ["Artist"], "Album": "Album"}
        track2 = {"Name": "\t\nSong\t\n", "Artists": ["\t\nArtist\t\n"], "Album": "\t\nAlbum\t\n"}
        assert is_duplicate(track1, track2) is True

    # Different tracks
    def test_different_title(self):
        """Test non-duplicate with different title."""
        track1 = {"Name": "Song 1", "Artists": ["Artist"], "Album": "Album"}
        track2 = {"Name": "Song 2", "Artists": ["Artist"], "Album": "Album"}
        assert is_duplicate(track1, track2) is False

    def test_different_artist(self):
        """Test non-duplicate with different artist."""
        track1 = {"Name": "Song", "Artists": ["Artist 1"], "Album": "Album"}
        track2 = {"Name": "Song", "Artists": ["Artist 2"], "Album": "Album"}
        assert is_duplicate(track1, track2) is False

    def test_different_album(self):
        """Test non-duplicate with different album."""
        track1 = {"Name": "Song", "Artists": ["Artist"], "Album": "Album 1"}
        track2 = {"Name": "Song", "Artists": ["Artist"], "Album": "Album 2"}
        assert is_duplicate(track1, track2) is False

    def test_different_two_fields(self):
        """Test non-duplicate with two different fields."""
        track1 = {"Name": "Song 1", "Artists": ["Artist 1"], "Album": "Album"}
        track2 = {"Name": "Song 2", "Artists": ["Artist 2"], "Album": "Album"}
        assert is_duplicate(track1, track2) is False

    def test_different_all_fields(self):
        """Test completely different tracks."""
        track1 = {"Name": "Song 1", "Artists": ["Artist 1"], "Album": "Album 1"}
        track2 = {"Name": "Song 2", "Artists": ["Artist 2"], "Album": "Album 2"}
        assert is_duplicate(track1, track2) is False

    # Multiple artists
    def test_multiple_artists_compares_first_only(self):
        """Test that only first artist is compared."""
        track1 = {"Name": "Song", "Artists": ["Artist 1", "Artist 2"], "Album": "Album"}
        track2 = {"Name": "Song", "Artists": ["Artist 1", "Artist 3"], "Album": "Album"}
        assert is_duplicate(track1, track2) is True

    def test_multiple_artists_different_first(self):
        """Test multiple artists with different first artist."""
        track1 = {"Name": "Song", "Artists": ["Artist 1", "Artist 2"], "Album": "Album"}
        track2 = {"Name": "Song", "Artists": ["Artist 3", "Artist 2"], "Album": "Album"}
        assert is_duplicate(track1, track2) is False

    def test_single_vs_multiple_artists(self):
        """Test comparison between single and multiple artists."""
        track1 = {"Name": "Song", "Artists": ["Artist"], "Album": "Album"}
        track2 = {"Name": "Song", "Artists": ["Artist", "Featured Artist"], "Album": "Album"}
        assert is_duplicate(track1, track2) is True

    # Empty and missing fields
    def test_empty_artists_list(self):
        """Test with empty artists lists."""
        track1 = {"Name": "Song", "Artists": [], "Album": "Album"}
        track2 = {"Name": "Song", "Artists": [], "Album": "Album"}
        assert is_duplicate(track1, track2) is True

    def test_missing_name_field(self):
        """Test with missing Name field."""
        track1 = {"Artists": ["Artist"], "Album": "Album"}
        track2 = {"Artists": ["Artist"], "Album": "Album"}
        assert is_duplicate(track1, track2) is True

    def test_missing_artists_field(self):
        """Test with missing Artists field."""
        track1 = {"Name": "Song", "Album": "Album"}
        track2 = {"Name": "Song", "Album": "Album"}
        assert is_duplicate(track1, track2) is True

    def test_missing_album_field(self):
        """Test with missing Album field."""
        track1 = {"Name": "Song", "Artists": ["Artist"]}
        track2 = {"Name": "Song", "Artists": ["Artist"]}
        assert is_duplicate(track1, track2) is True

    def test_all_fields_missing(self):
        """Test with all fields missing."""
        track1 = {}
        track2 = {}
        assert is_duplicate(track1, track2) is True

    def test_empty_string_values(self):
        """Test with empty string values."""
        track1 = {"Name": "", "Artists": [""], "Album": ""}
        track2 = {"Name": "", "Artists": [""], "Album": ""}
        assert is_duplicate(track1, track2) is True

    def test_mixed_empty_and_missing(self):
        """Test mix of empty and missing fields."""
        track1 = {"Name": "Song", "Artists": [], "Album": ""}
        track2 = {"Name": "Song", "Album": ""}
        assert is_duplicate(track1, track2) is True

    # Unicode and special characters
    def test_unicode_characters(self):
        """Test with Unicode characters."""
        track1 = {"Name": "Café del Mar", "Artists": ["José González"], "Album": "Señor"}
        track2 = {"Name": "Café del Mar", "Artists": ["José González"], "Album": "Señor"}
        assert is_duplicate(track1, track2) is True

    def test_special_characters(self):
        """Test with special characters."""
        track1 = {"Name": "Ain't No Mountain High Enough", "Artists": ["Artist"], "Album": "Album"}
        track2 = {"Name": "Ain't No Mountain High Enough", "Artists": ["Artist"], "Album": "Album"}
        assert is_duplicate(track1, track2) is True

    def test_emoji_in_names(self):
        """Test with emoji characters."""
        track1 = {"Name": "Song 🎵", "Artists": ["Artist 🎤"], "Album": "Album 💿"}
        track2 = {"Name": "Song 🎵", "Artists": ["Artist 🎤"], "Album": "Album 💿"}
        assert is_duplicate(track1, track2) is True

    # Additional fields shouldn't affect comparison
    def test_extra_fields_ignored(self):
        """Test that extra fields don't affect duplicate detection."""
        track1 = {
            "Name": "Song",
            "Artists": ["Artist"],
            "Album": "Album",
            "Id": "123",
            "Duration": 180,
        }
        track2 = {
            "Name": "Song",
            "Artists": ["Artist"],
            "Album": "Album",
            "Id": "456",
            "Duration": 200,
        }
        assert is_duplicate(track1, track2) is True


class TestDetectDuplicatesComprehensive:
    """Comprehensive tests for detect_duplicates function."""

    # Single duplicate
    def test_single_duplicate_in_list(self):
        """Test detecting single duplicate."""
        tracks = [
            {"Id": "1", "Name": "Song", "Artists": ["Artist"], "Album": "Album"},
            {"Id": "2", "Name": "Song", "Artists": ["Artist"], "Album": "Album"},
        ]
        duplicates = detect_duplicates(tracks)
        assert duplicates == {"2"}

    def test_single_duplicate_keeps_first(self):
        """Test that first occurrence is preserved."""
        tracks = [
            {"Id": "original", "Name": "Song", "Artists": ["Artist"], "Album": "Album"},
            {"Id": "duplicate", "Name": "Song", "Artists": ["Artist"], "Album": "Album"},
        ]
        duplicates = detect_duplicates(tracks)
        assert "original" not in duplicates
        assert "duplicate" in duplicates

    # Multiple duplicates
    def test_multiple_duplicates_of_same_track(self):
        """Test multiple duplicates of the same track."""
        tracks = [
            {"Id": "1", "Name": "Song", "Artists": ["Artist"], "Album": "Album"},
            {"Id": "2", "Name": "Song", "Artists": ["Artist"], "Album": "Album"},
            {"Id": "3", "Name": "Song", "Artists": ["Artist"], "Album": "Album"},
            {"Id": "4", "Name": "Song", "Artists": ["Artist"], "Album": "Album"},
        ]
        duplicates = detect_duplicates(tracks)
        assert duplicates == {"2", "3", "4"}
        assert "1" not in duplicates

    def test_multiple_different_duplicates(self):
        """Test multiple sets of different duplicates."""
        tracks = [
            {"Id": "1", "Name": "Song A", "Artists": ["Artist"], "Album": "Album"},
            {"Id": "2", "Name": "Song A", "Artists": ["Artist"], "Album": "Album"},
            {"Id": "3", "Name": "Song B", "Artists": ["Artist"], "Album": "Album"},
            {"Id": "4", "Name": "Song B", "Artists": ["Artist"], "Album": "Album"},
        ]
        duplicates = detect_duplicates(tracks)
        assert duplicates == {"2", "4"}

    # No duplicates
    def test_no_duplicates_empty_result(self):
        """Test list with no duplicates returns empty set."""
        tracks = [
            {"Id": "1", "Name": "Song 1", "Artists": ["Artist"], "Album": "Album"},
            {"Id": "2", "Name": "Song 2", "Artists": ["Artist"], "Album": "Album"},
            {"Id": "3", "Name": "Song 3", "Artists": ["Artist"], "Album": "Album"},
        ]
        duplicates = detect_duplicates(tracks)
        assert duplicates == set()

    def test_all_unique_tracks(self):
        """Test large list of all unique tracks."""
        tracks = [
            {"Id": str(i), "Name": f"Song {i}", "Artists": ["Artist"], "Album": "Album"}
            for i in range(100)
        ]
        duplicates = detect_duplicates(tracks)
        assert duplicates == set()

    # Edge cases
    def test_empty_list(self):
        """Test empty track list."""
        assert detect_duplicates([]) == set()

    def test_single_track(self):
        """Test single track (can't be duplicate of anything)."""
        tracks = [{"Id": "1", "Name": "Song", "Artists": ["Artist"], "Album": "Album"}]
        duplicates = detect_duplicates(tracks)
        assert duplicates == set()

    def test_two_identical_tracks(self):
        """Test exactly two identical tracks."""
        tracks = [
            {"Id": "1", "Name": "Song", "Artists": ["Artist"], "Album": "Album"},
            {"Id": "2", "Name": "Song", "Artists": ["Artist"], "Album": "Album"},
        ]
        duplicates = detect_duplicates(tracks)
        assert duplicates == {"2"}

    # Case insensitivity
    def test_case_insensitive_detection(self):
        """Test case-insensitive duplicate detection."""
        tracks = [
            {"Id": "1", "Name": "Song", "Artists": ["Artist"], "Album": "Album"},
            {"Id": "2", "Name": "SONG", "Artists": ["ARTIST"], "Album": "ALBUM"},
        ]
        duplicates = detect_duplicates(tracks)
        assert duplicates == {"2"}

    # Whitespace handling
    def test_whitespace_trimming(self):
        """Test whitespace is trimmed in detection."""
        tracks = [
            {"Id": "1", "Name": "Song", "Artists": ["Artist"], "Album": "Album"},
            {"Id": "2", "Name": "  Song  ", "Artists": ["  Artist  "], "Album": "  Album  "},
        ]
        duplicates = detect_duplicates(tracks)
        assert duplicates == {"2"}

    # Complex scenarios
    def test_interleaved_duplicates(self):
        """Test duplicates interleaved with unique tracks."""
        tracks = [
            {"Id": "1", "Name": "Song A", "Artists": ["Artist"], "Album": "Album"},
            {"Id": "2", "Name": "Song B", "Artists": ["Artist"], "Album": "Album"},
            {"Id": "3", "Name": "Song A", "Artists": ["Artist"], "Album": "Album"},  # Duplicate of 1
            {"Id": "4", "Name": "Song C", "Artists": ["Artist"], "Album": "Album"},
            {"Id": "5", "Name": "Song B", "Artists": ["Artist"], "Album": "Album"},  # Duplicate of 2
        ]
        duplicates = detect_duplicates(tracks)
        assert duplicates == {"3", "5"}

    def test_partial_duplicates(self):
        """Test tracks that are similar but not duplicates."""
        tracks = [
            {"Id": "1", "Name": "Song", "Artists": ["Artist 1"], "Album": "Album 1"},
            {"Id": "2", "Name": "Song", "Artists": ["Artist 1"], "Album": "Album 2"},  # Different album
            {"Id": "3", "Name": "Song", "Artists": ["Artist 2"], "Album": "Album 1"},  # Different artist
        ]
        duplicates = detect_duplicates(tracks)
        assert duplicates == set()  # None are complete duplicates

    # Performance with large datasets
    def test_large_dataset_all_duplicates(self):
        """Test performance with many duplicates."""
        # First track + 99 duplicates
        tracks = [
            {"Id": "1", "Name": "Song", "Artists": ["Artist"], "Album": "Album"}
        ] + [
            {"Id": str(i), "Name": "Song", "Artists": ["Artist"], "Album": "Album"}
            for i in range(2, 101)
        ]
        duplicates = detect_duplicates(tracks)
        assert len(duplicates) == 99
        assert "1" not in duplicates

    def test_large_dataset_no_duplicates(self):
        """Test performance with no duplicates."""
        tracks = [
            {"Id": str(i), "Name": f"Song {i}", "Artists": ["Artist"], "Album": "Album"}
            for i in range(1000)
        ]
        duplicates = detect_duplicates(tracks)
        assert duplicates == set()

    # Return type validation
    def test_return_type_is_set(self):
        """Test return type is always a set."""
        tracks = [{"Id": "1", "Name": "Song", "Artists": ["Artist"], "Album": "Album"}]
        result = detect_duplicates(tracks)
        assert isinstance(result, set)

    def test_empty_list_returns_empty_set(self):
        """Test empty list returns empty set, not None."""
        result = detect_duplicates([])
        assert result == set()
        assert result is not None

    # ID preservation
    def test_duplicate_ids_are_correct(self):
        """Test that correct IDs are marked as duplicates."""
        tracks = [
            {"Id": "keep-1", "Name": "Song A", "Artists": ["Artist"], "Album": "Album"},
            {"Id": "dup-1", "Name": "Song A", "Artists": ["Artist"], "Album": "Album"},
            {"Id": "keep-2", "Name": "Song B", "Artists": ["Artist"], "Album": "Album"},
            {"Id": "dup-2", "Name": "Song B", "Artists": ["Artist"], "Album": "Album"},
        ]
        duplicates = detect_duplicates(tracks)
        assert "dup-1" in duplicates
        assert "dup-2" in duplicates
        assert "keep-1" not in duplicates
        assert "keep-2" not in duplicates


# ============================================================================
# SubsonicTrack Transformation Tests
# ============================================================================

class TestTransformSubsonicTrackComprehensive:
    """Comprehensive tests for transform_subsonic_track function."""

    # Full transformation with all fields
    def test_all_fields_populated(self, sample_subsonic_track, mock_playlist_manager):
        """Test transformation with all fields populated."""
        result = transform_subsonic_track(sample_subsonic_track, mock_playlist_manager)

        # Core metadata
        assert result["Id"] == "track-123"
        assert result["Name"] == "Bohemian Rhapsody"
        assert result["Artists"] == ["Queen"]
        assert result["Album"] == "A Night at the Opera"
        assert result["Path"] == "/music/Queen/A Night at the Opera/01 Bohemian Rhapsody.flac"

        # Duration conversion
        assert result["RunTimeTicks"] == 354 * TICKS_PER_SECOND
        assert result["RunTimeTicks"] == 3_540_000_000

        # Optional metadata
        assert result["Genres"] == ["Progressive Rock"]
        assert result["IndexNumber"] == 1
        assert result["ParentIndexNumber"] == 1
        assert result["ProductionYear"] == 1975

        # Provider IDs
        assert result["ProviderIds"] == {
            "MusicBrainzTrack": "b1a9c0e7-0f12-4fa4-8f5a-9c3d2e1b7a0f"
        }

        # Subsonic metadata preservation
        assert result["_subsonic_id"] == "track-123"
        assert result["_subsonic_suffix"] == "flac"
        assert result["_subsonic_created"] == "2024-01-15T10:30:00.000Z"
        assert result["_subsonic_cover_art"] == "cover-456"
        assert result["_subsonic_size"] == 42857143
        assert result["_subsonic_bit_rate"] == 1411
        assert result["_subsonic_content_type"] == "audio/flac"

    def test_minimal_fields_only(self, minimal_subsonic_track, mock_playlist_manager):
        """Test transformation with only required fields."""
        result = transform_subsonic_track(minimal_subsonic_track, mock_playlist_manager)

        # Required fields
        assert result["Id"] == "min-001"
        assert result["Name"] == "Minimal Track"
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

    # Individual field transformations
    def test_genre_transformation(self, mock_playlist_manager):
        """Test genre field transformation."""
        track_with_genre = SubsonicTrack(
            id="1", title="T", artist="A", album="Alb",
            duration=100, path="/p", suffix="mp3", created="2024-01-01T00:00:00.000Z",
            genre="  Rock  "
        )
        result = transform_subsonic_track(track_with_genre, mock_playlist_manager)
        assert result["Genres"] == ["Rock"]

    def test_no_genre(self, mock_playlist_manager):
        """Test transformation without genre."""
        track_no_genre = SubsonicTrack(
            id="1", title="T", artist="A", album="Alb",
            duration=100, path="/p", suffix="mp3", created="2024-01-01T00:00:00.000Z",
            genre=None
        )
        result = transform_subsonic_track(track_no_genre, mock_playlist_manager)
        assert result["Genres"] == []

    def test_empty_genre(self, mock_playlist_manager):
        """Test transformation with empty genre string."""
        track_empty_genre = SubsonicTrack(
            id="1", title="T", artist="A", album="Alb",
            duration=100, path="/p", suffix="mp3", created="2024-01-01T00:00:00.000Z",
            genre=""
        )
        result = transform_subsonic_track(track_empty_genre, mock_playlist_manager)
        assert result["Genres"] == []

    def test_duration_conversion(self, mock_playlist_manager):
        """Test duration conversion to ticks."""
        durations = [0, 1, 60, 180, 3600]
        for seconds in durations:
            track = SubsonicTrack(
                id="1", title="T", artist="A", album="Alb",
                duration=seconds, path="/p", suffix="mp3", created="2024-01-01T00:00:00.000Z"
            )
            result = transform_subsonic_track(track, mock_playlist_manager)
            assert result["RunTimeTicks"] == seconds * TICKS_PER_SECOND

    def test_musicbrainz_id_mapping(self, mock_playlist_manager):
        """Test MusicBrainz ID mapping to ProviderIds."""
        mb_id = "f3f72a0e-a554-4c8a-9c52-94e1d11b84b0"
        track = SubsonicTrack(
            id="1", title="T", artist="A", album="Alb",
            duration=100, path="/p", suffix="mp3", created="2024-01-01T00:00:00.000Z",
            musicBrainzId=mb_id
        )
        result = transform_subsonic_track(track, mock_playlist_manager)
        assert result["ProviderIds"] == {"MusicBrainzTrack": mb_id}

    def test_no_musicbrainz_id(self, mock_playlist_manager):
        """Test transformation without MusicBrainz ID."""
        track = SubsonicTrack(
            id="1", title="T", artist="A", album="Alb",
            duration=100, path="/p", suffix="mp3", created="2024-01-01T00:00:00.000Z",
            musicBrainzId=None
        )
        result = transform_subsonic_track(track, mock_playlist_manager)
        assert result["ProviderIds"] == {}

    # Artist transformation
    def test_artist_to_list_conversion(self, mock_playlist_manager):
        """Test single artist is converted to list."""
        track = SubsonicTrack(
            id="1", title="T", artist="Single Artist", album="Alb",
            duration=100, path="/p", suffix="mp3", created="2024-01-01T00:00:00.000Z"
        )
        result = transform_subsonic_track(track, mock_playlist_manager)
        assert isinstance(result["Artists"], list)
        assert result["Artists"] == ["Single Artist"]
        assert len(result["Artists"]) == 1

    # Track numbers
    def test_track_number_mapping(self, mock_playlist_manager):
        """Test track number mapping to IndexNumber."""
        track = SubsonicTrack(
            id="1", title="T", artist="A", album="Alb",
            duration=100, path="/p", suffix="mp3", created="2024-01-01T00:00:00.000Z",
            track=5
        )
        result = transform_subsonic_track(track, mock_playlist_manager)
        assert result["IndexNumber"] == 5

    def test_no_track_number(self, mock_playlist_manager):
        """Test transformation without track number."""
        track = SubsonicTrack(
            id="1", title="T", artist="A", album="Alb",
            duration=100, path="/p", suffix="mp3", created="2024-01-01T00:00:00.000Z",
            track=None
        )
        result = transform_subsonic_track(track, mock_playlist_manager)
        assert result["IndexNumber"] is None

    def test_track_number_zero(self, mock_playlist_manager):
        """Test track number zero."""
        track = SubsonicTrack(
            id="1", title="T", artist="A", album="Alb",
            duration=100, path="/p", suffix="mp3", created="2024-01-01T00:00:00.000Z",
            track=0
        )
        result = transform_subsonic_track(track, mock_playlist_manager)
        assert result["IndexNumber"] == 0

    # Disc numbers
    def test_disc_number_mapping(self, mock_playlist_manager):
        """Test disc number mapping to ParentIndexNumber."""
        track = SubsonicTrack(
            id="1", title="T", artist="A", album="Alb",
            duration=100, path="/p", suffix="mp3", created="2024-01-01T00:00:00.000Z",
            discNumber=2
        )
        result = transform_subsonic_track(track, mock_playlist_manager)
        assert result["ParentIndexNumber"] == 2

    def test_no_disc_number(self, mock_playlist_manager):
        """Test transformation without disc number."""
        track = SubsonicTrack(
            id="1", title="T", artist="A", album="Alb",
            duration=100, path="/p", suffix="mp3", created="2024-01-01T00:00:00.000Z",
            discNumber=None
        )
        result = transform_subsonic_track(track, mock_playlist_manager)
        assert result["ParentIndexNumber"] is None

    # Year
    def test_year_mapping(self, mock_playlist_manager):
        """Test year mapping to ProductionYear."""
        track = SubsonicTrack(
            id="1", title="T", artist="A", album="Alb",
            duration=100, path="/p", suffix="mp3", created="2024-01-01T00:00:00.000Z",
            year=2005
        )
        result = transform_subsonic_track(track, mock_playlist_manager)
        assert result["ProductionYear"] == 2005

    def test_no_year(self, mock_playlist_manager):
        """Test transformation without year."""
        track = SubsonicTrack(
            id="1", title="T", artist="A", album="Alb",
            duration=100, path="/p", suffix="mp3", created="2024-01-01T00:00:00.000Z",
            year=None
        )
        result = transform_subsonic_track(track, mock_playlist_manager)
        assert result["ProductionYear"] is None

    def test_old_year(self, mock_playlist_manager):
        """Test very old year."""
        track = SubsonicTrack(
            id="1", title="T", artist="A", album="Alb",
            duration=100, path="/p", suffix="mp3", created="2024-01-01T00:00:00.000Z",
            year=1920
        )
        result = transform_subsonic_track(track, mock_playlist_manager)
        assert result["ProductionYear"] == 1920

    # Subsonic metadata preservation
    def test_subsonic_metadata_preserved(self, sample_subsonic_track, mock_playlist_manager):
        """Test all Subsonic-specific fields are preserved with _subsonic_ prefix."""
        result = transform_subsonic_track(sample_subsonic_track, mock_playlist_manager)

        subsonic_fields = [
            "_subsonic_id",
            "_subsonic_suffix",
            "_subsonic_created",
            "_subsonic_cover_art",
            "_subsonic_size",
            "_subsonic_bit_rate",
            "_subsonic_content_type",
        ]

        for field in subsonic_fields:
            assert field in result

    def test_subsonic_optional_fields_none(self, minimal_subsonic_track, mock_playlist_manager):
        """Test Subsonic optional fields are None when not provided."""
        result = transform_subsonic_track(minimal_subsonic_track, mock_playlist_manager)

        assert result["_subsonic_cover_art"] is None
        assert result["_subsonic_size"] is None
        assert result["_subsonic_bit_rate"] is None
        assert result["_subsonic_content_type"] is None

    # Special characters and Unicode
    def test_unicode_in_title(self, mock_playlist_manager):
        """Test Unicode characters in title."""
        track = SubsonicTrack(
            id="1", title="Café del Mar", artist="A", album="Alb",
            duration=100, path="/p", suffix="mp3", created="2024-01-01T00:00:00.000Z"
        )
        result = transform_subsonic_track(track, mock_playlist_manager)
        assert result["Name"] == "Café del Mar"

    def test_unicode_in_artist(self, mock_playlist_manager):
        """Test Unicode characters in artist."""
        track = SubsonicTrack(
            id="1", title="T", artist="José González", album="Alb",
            duration=100, path="/p", suffix="mp3", created="2024-01-01T00:00:00.000Z"
        )
        result = transform_subsonic_track(track, mock_playlist_manager)
        assert result["Artists"] == ["José González"]

    def test_unicode_in_album(self, mock_playlist_manager):
        """Test Unicode characters in album."""
        track = SubsonicTrack(
            id="1", title="T", artist="A", album="Señor",
            duration=100, path="/p", suffix="mp3", created="2024-01-01T00:00:00.000Z"
        )
        result = transform_subsonic_track(track, mock_playlist_manager)
        assert result["Album"] == "Señor"

    def test_special_characters_in_title(self, mock_playlist_manager):
        """Test special characters in title."""
        track = SubsonicTrack(
            id="1", title="Ain't No Mountain High Enough", artist="A", album="Alb",
            duration=100, path="/p", suffix="mp3", created="2024-01-01T00:00:00.000Z"
        )
        result = transform_subsonic_track(track, mock_playlist_manager)
        assert result["Name"] == "Ain't No Mountain High Enough"

    def test_emoji_in_fields(self, mock_playlist_manager):
        """Test emoji characters in fields."""
        track = SubsonicTrack(
            id="1", title="Song 🎵", artist="Artist 🎤", album="Album 💿",
            duration=100, path="/p", suffix="mp3", created="2024-01-01T00:00:00.000Z"
        )
        result = transform_subsonic_track(track, mock_playlist_manager)
        assert result["Name"] == "Song 🎵"
        assert result["Artists"] == ["Artist 🎤"]
        assert result["Album"] == "Album 💿"

    # File formats and paths
    def test_various_audio_formats(self, mock_playlist_manager):
        """Test various audio file formats."""
        formats = ["mp3", "flac", "ogg", "m4a", "wav", "aac", "opus"]
        for fmt in formats:
            track = SubsonicTrack(
                id="1", title="T", artist="A", album="Alb",
                duration=100, path=f"/music/test.{fmt}", suffix=fmt,
                created="2024-01-01T00:00:00.000Z"
            )
            result = transform_subsonic_track(track, mock_playlist_manager)
            assert result["_subsonic_suffix"] == fmt
            assert result["Path"] == f"/music/test.{fmt}"

    def test_windows_path(self, mock_playlist_manager):
        """Test Windows-style file path."""
        track = SubsonicTrack(
            id="1", title="T", artist="A", album="Alb",
            duration=100, path="C:\\Music\\Artist\\Album\\Track.mp3",
            suffix="mp3", created="2024-01-01T00:00:00.000Z"
        )
        result = transform_subsonic_track(track, mock_playlist_manager)
        assert result["Path"] == "C:\\Music\\Artist\\Album\\Track.mp3"

    def test_network_path(self, mock_playlist_manager):
        """Test network/UNC path."""
        track = SubsonicTrack(
            id="1", title="T", artist="A", album="Alb",
            duration=100, path="//nas/music/track.mp3",
            suffix="mp3", created="2024-01-01T00:00:00.000Z"
        )
        result = transform_subsonic_track(track, mock_playlist_manager)
        assert result["Path"] == "//nas/music/track.mp3"

    def test_path_with_unicode(self, mock_playlist_manager):
        """Test file path with Unicode characters."""
        track = SubsonicTrack(
            id="1", title="T", artist="A", album="Alb",
            duration=100, path="/music/José González/Café del Mar/01 Señor.mp3",
            suffix="mp3", created="2024-01-01T00:00:00.000Z"
        )
        result = transform_subsonic_track(track, mock_playlist_manager)
        assert result["Path"] == "/music/José González/Café del Mar/01 Señor.mp3"

    # Edge cases for numeric fields
    def test_very_large_file_size(self, mock_playlist_manager):
        """Test very large file size."""
        large_size = 5_000_000_000  # 5 GB
        track = SubsonicTrack(
            id="1", title="T", artist="A", album="Alb",
            duration=100, path="/p", suffix="mp3", created="2024-01-01T00:00:00.000Z",
            size=large_size
        )
        result = transform_subsonic_track(track, mock_playlist_manager)
        assert result["_subsonic_size"] == large_size

    def test_very_high_bitrate(self, mock_playlist_manager):
        """Test very high bitrate."""
        high_bitrate = 9216  # DSD quality
        track = SubsonicTrack(
            id="1", title="T", artist="A", album="Alb",
            duration=100, path="/p", suffix="mp3", created="2024-01-01T00:00:00.000Z",
            bitRate=high_bitrate
        )
        result = transform_subsonic_track(track, mock_playlist_manager)
        assert result["_subsonic_bit_rate"] == high_bitrate

    def test_very_long_duration(self, mock_playlist_manager):
        """Test very long duration (audiobook, etc.)."""
        long_duration = 36000  # 10 hours
        track = SubsonicTrack(
            id="1", title="T", artist="A", album="Alb",
            duration=long_duration, path="/p", suffix="mp3",
            created="2024-01-01T00:00:00.000Z"
        )
        result = transform_subsonic_track(track, mock_playlist_manager)
        assert result["RunTimeTicks"] == long_duration * TICKS_PER_SECOND

    # Real-world examples
    def test_classic_rock_track(self, mock_playlist_manager):
        """Test transformation of classic rock track."""
        track = SubsonicTrack(
            id="led-zeppelin-1",
            title="Stairway to Heaven",
            artist="Led Zeppelin",
            album="Led Zeppelin IV",
            duration=482,
            path="/music/Led Zeppelin/Led Zeppelin IV/04 Stairway to Heaven.mp3",
            suffix="mp3",
            created="2024-01-01T00:00:00.000Z",
            genre="Rock",
            track=4,
            year=1971,
        )
        result = transform_subsonic_track(track, mock_playlist_manager)

        assert result["Name"] == "Stairway to Heaven"
        assert result["Artists"] == ["Led Zeppelin"]
        assert result["Album"] == "Led Zeppelin IV"
        assert result["Genres"] == ["Rock"]
        assert result["IndexNumber"] == 4
        assert result["ProductionYear"] == 1971
        assert result["RunTimeTicks"] == 4_820_000_000

    def test_modern_pop_track(self, mock_playlist_manager):
        """Test transformation of modern pop track."""
        track = SubsonicTrack(
            id="modern-pop-1",
            title="Blinding Lights",
            artist="The Weeknd",
            album="After Hours",
            duration=200,
            path="/music/The Weeknd/After Hours/03 Blinding Lights.m4a",
            suffix="m4a",
            created="2024-01-01T00:00:00.000Z",
            genre="Synth-pop",
            track=3,
            year=2020,
            bitRate=256,
            contentType="audio/mp4",
        )
        result = transform_subsonic_track(track, mock_playlist_manager)

        assert result["Name"] == "Blinding Lights"
        assert result["Artists"] == ["The Weeknd"]
        assert result["Genres"] == ["Synth-pop"]
        assert result["ProductionYear"] == 2020

    def test_classical_track(self, mock_playlist_manager):
        """Test transformation of classical music track."""
        track = SubsonicTrack(
            id="classical-1",
            title="Symphony No. 5 in C Minor, Op. 67: I. Allegro con brio",
            artist="Ludwig van Beethoven",
            album="Beethoven: Complete Symphonies",
            duration=450,
            path="/music/Beethoven/Complete Symphonies/Disc 1/01 Symphony No. 5.flac",
            suffix="flac",
            created="2024-01-01T00:00:00.000Z",
            genre="Classical",
            track=1,
            discNumber=1,
            year=1808,
            bitRate=1411,
        )
        result = transform_subsonic_track(track, mock_playlist_manager)

        assert "Symphony No. 5" in result["Name"]
        assert result["Artists"] == ["Ludwig van Beethoven"]
        assert result["Genres"] == ["Classical"]
        assert result["ParentIndexNumber"] == 1
        assert result["ProductionYear"] == 1808

    # Return value structure validation
    def test_return_type_is_dict(self, minimal_subsonic_track, mock_playlist_manager):
        """Test return type is dictionary."""
        result = transform_subsonic_track(minimal_subsonic_track, mock_playlist_manager)
        assert isinstance(result, dict)

    def test_required_emby_fields_present(self, minimal_subsonic_track, mock_playlist_manager):
        """Test all required Emby fields are present."""
        result = transform_subsonic_track(minimal_subsonic_track, mock_playlist_manager)

        required_fields = [
            "Id", "Name", "Artists", "Album", "RunTimeTicks", "Path",
            "Genres", "IndexNumber", "ParentIndexNumber", "ProductionYear",
            "ProviderIds"
        ]

        for field in required_fields:
            assert field in result

    def test_subsonic_fields_present(self, minimal_subsonic_track, mock_playlist_manager):
        """Test all Subsonic metadata fields are preserved."""
        result = transform_subsonic_track(minimal_subsonic_track, mock_playlist_manager)

        subsonic_fields = [
            "_subsonic_id", "_subsonic_suffix", "_subsonic_created",
            "_subsonic_cover_art", "_subsonic_size", "_subsonic_bit_rate",
            "_subsonic_content_type"
        ]

        for field in subsonic_fields:
            assert field in result

    # Logging behavior (optional - requires log capture)
    @patch('src.subsonic.transform.logger')
    def test_logging_on_transform(self, mock_logger, minimal_subsonic_track, mock_playlist_manager):
        """Test that transformation logs debug message."""
        transform_subsonic_track(minimal_subsonic_track, mock_playlist_manager)
        mock_logger.debug.assert_called_once()

    # Playlist manager parameter (currently unused but part of signature)
    def test_playlist_manager_not_modified(self, minimal_subsonic_track, mock_playlist_manager):
        """Test that playlist_manager is not modified during transformation."""
        transform_subsonic_track(minimal_subsonic_track, mock_playlist_manager)
        # Verify no methods were called on the mock
        assert not mock_playlist_manager.method_calls

    def test_works_with_none_playlist_manager(self, minimal_subsonic_track):
        """Test transformation works with None playlist_manager."""
        # Should not raise an error
        result = transform_subsonic_track(minimal_subsonic_track, None)
        assert result["Id"] == "min-001"


# ============================================================================
# Integration Tests
# ============================================================================

class TestTransformationIntegration:
    """Integration tests combining multiple transformation functions."""

    def test_complete_workflow(self, sample_subsonic_track, mock_playlist_manager):
        """Test complete transformation workflow."""
        # Transform track
        result = transform_subsonic_track(sample_subsonic_track, mock_playlist_manager)

        # Verify genre transformation was applied
        assert isinstance(result["Genres"], list)
        assert len(result["Genres"]) == 1

        # Verify duration transformation was applied
        assert result["RunTimeTicks"] == sample_subsonic_track.duration * TICKS_PER_SECOND

        # Verify MusicBrainz ID transformation was applied
        assert "MusicBrainzTrack" in result["ProviderIds"]

    def test_duplicate_detection_after_transformation(self, mock_playlist_manager):
        """Test duplicate detection on transformed tracks."""
        track1 = SubsonicTrack(
            id="1", title="Song", artist="Artist", album="Album",
            duration=100, path="/p1", suffix="mp3", created="2024-01-01T00:00:00.000Z"
        )
        track2 = SubsonicTrack(
            id="2", title="Song", artist="Artist", album="Album",
            duration=100, path="/p2", suffix="mp3", created="2024-01-01T00:00:00.000Z"
        )

        # Transform both tracks
        emby1 = transform_subsonic_track(track1, mock_playlist_manager)
        emby2 = transform_subsonic_track(track2, mock_playlist_manager)

        # Detect duplicates
        assert is_duplicate(emby1, emby2) is True

        # Batch detection
        duplicates = detect_duplicates([emby1, emby2])
        assert duplicates == {"2"}

    def test_batch_transformation_and_deduplication(self, mock_playlist_manager):
        """Test transforming and deduplicating a batch of tracks."""
        subsonic_tracks = [
            SubsonicTrack(
                id="1", title="Song A", artist="Artist", album="Album",
                duration=100, path="/p1", suffix="mp3", created="2024-01-01T00:00:00.000Z"
            ),
            SubsonicTrack(
                id="2", title="Song A", artist="Artist", album="Album",  # Duplicate
                duration=100, path="/p2", suffix="mp3", created="2024-01-01T00:00:00.000Z"
            ),
            SubsonicTrack(
                id="3", title="Song B", artist="Artist", album="Album",
                duration=100, path="/p3", suffix="mp3", created="2024-01-01T00:00:00.000Z"
            ),
        ]

        # Transform all tracks
        emby_tracks = [
            transform_subsonic_track(track, mock_playlist_manager)
            for track in subsonic_tracks
        ]

        # Detect duplicates
        duplicates = detect_duplicates(emby_tracks)

        # Verify
        assert len(emby_tracks) == 3
        assert duplicates == {"2"}

    def test_mixed_quality_tracks(self, mock_playlist_manager):
        """Test transformation of tracks with varying data quality."""
        tracks = [
            # Full metadata
            SubsonicTrack(
                id="full", title="Full Track", artist="Full Artist", album="Full Album",
                duration=200, path="/full.flac", suffix="flac", created="2024-01-01T00:00:00.000Z",
                genre="Rock", track=1, discNumber=1, year=2020,
                musicBrainzId="full-mb-id", bitRate=1411
            ),
            # Minimal metadata
            SubsonicTrack(
                id="min", title="Min Track", artist="Min Artist", album="Min Album",
                duration=150, path="/min.mp3", suffix="mp3", created="2024-01-01T00:00:00.000Z"
            ),
        ]

        results = [transform_subsonic_track(t, mock_playlist_manager) for t in tracks]

        # Both should transform successfully
        assert len(results) == 2
        assert results[0]["Genres"] == ["Rock"]
        assert results[1]["Genres"] == []


# ============================================================================
# Performance and Edge Case Tests
# ============================================================================

class TestPerformanceAndEdgeCases:
    """Tests for performance characteristics and unusual edge cases."""

    def test_transformation_preserves_input(self, sample_subsonic_track, mock_playlist_manager):
        """Test that transformation doesn't modify input track."""
        original_id = sample_subsonic_track.id
        original_title = sample_subsonic_track.title

        transform_subsonic_track(sample_subsonic_track, mock_playlist_manager)

        # Input should be unchanged
        assert sample_subsonic_track.id == original_id
        assert sample_subsonic_track.title == original_title

    def test_multiple_transformations_same_track(self, sample_subsonic_track, mock_playlist_manager):
        """Test transforming the same track multiple times gives same result."""
        result1 = transform_subsonic_track(sample_subsonic_track, mock_playlist_manager)
        result2 = transform_subsonic_track(sample_subsonic_track, mock_playlist_manager)

        # Results should be identical
        assert result1 == result2

    def test_large_batch_transformation(self, mock_playlist_manager):
        """Test transforming a large batch of tracks."""
        tracks = [
            SubsonicTrack(
                id=str(i), title=f"Track {i}", artist="Artist", album="Album",
                duration=180, path=f"/p{i}", suffix="mp3", created="2024-01-01T00:00:00.000Z"
            )
            for i in range(1000)
        ]

        # Should complete without errors
        results = [transform_subsonic_track(t, mock_playlist_manager) for t in tracks]
        assert len(results) == 1000

    def test_memory_efficiency_with_large_dataset(self, mock_playlist_manager):
        """Test memory efficiency with large dataset."""
        # Create 100 tracks with large metadata
        tracks = [
            SubsonicTrack(
                id=str(i),
                title="A" * 1000,  # Large title
                artist="B" * 1000,  # Large artist
                album="C" * 1000,  # Large album
                duration=180,
                path=f"/p{i}",
                suffix="mp3",
                created="2024-01-01T00:00:00.000Z"
            )
            for i in range(100)
        ]

        # Should handle large strings efficiently
        results = [transform_subsonic_track(t, mock_playlist_manager) for t in tracks]
        assert len(results) == 100
        assert len(results[0]["Name"]) == 1000
