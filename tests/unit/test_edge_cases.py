"""Unit tests for edge cases in duplicate detection (T037).

This module tests edge cases that could cause runtime errors or unexpected
behavior in production scenarios.
"""
import pytest
import time
from unittest.mock import Mock, patch
from src.azuracast.normalization import normalize_string, normalize_artist, build_track_fingerprint
from src.azuracast.models import KnownTracksCache
from src.azuracast.cache import get_cached_known_tracks
from src.azuracast.detection import check_file_exists_by_musicbrainz, check_file_exists_by_metadata


class TestEmptyFieldHandling:
    """Test handling of empty or missing metadata fields."""

    def test_empty_artist(self):
        """Test that empty artist field raises ValueError."""
        track = {"Album": "Test Album", "Name": "Test Song"}
        with pytest.raises(ValueError, match="Missing required fields: artist"):
            build_track_fingerprint(track)

    def test_empty_album(self):
        """Test that empty album field raises ValueError."""
        track = {"AlbumArtist": "Test Artist", "Name": "Test Song"}
        with pytest.raises(ValueError, match="Missing required fields: album"):
            build_track_fingerprint(track)

    def test_empty_title(self):
        """Test that empty title field raises ValueError."""
        track = {"AlbumArtist": "Test Artist", "Album": "Test Album"}
        with pytest.raises(ValueError, match="Missing required fields: title"):
            build_track_fingerprint(track)

    def test_whitespace_only_artist(self):
        """Test that whitespace-only artist field raises ValueError after normalization."""
        track = {"AlbumArtist": "   ", "Album": "Test Album", "Name": "Test Song"}
        with pytest.raises(ValueError, match="Empty fields after normalization"):
            build_track_fingerprint(track)

    def test_special_chars_only_becomes_empty(self):
        """Test that fields with only special characters become empty after normalization."""
        track = {"AlbumArtist": "!!!###", "Album": "Test Album", "Name": "Test Song"}
        with pytest.raises(ValueError, match="Empty fields after normalization"):
            build_track_fingerprint(track)

    def test_normalize_empty_string(self):
        """Test that normalize_string handles empty input."""
        assert normalize_string("") == ""
        assert normalize_string("   ") == ""

    def test_normalize_artist_empty_string(self):
        """Test that normalize_artist handles empty input."""
        assert normalize_artist("") == ""
        assert normalize_artist("   ") == ""


class TestMalformedUnicode:
    """Test handling of malformed or unusual Unicode characters."""

    def test_emoji_removal(self):
        """Test that emoji characters are removed during normalization."""
        result = normalize_string("Artist 🎵 Name")
        assert result == "artist name"

    def test_combining_diacritics(self):
        """Test handling of combining diacritical marks."""
        # e + combining acute accent
        result = normalize_string("Cafe\u0301")
        assert result == "cafe"

    def test_unicode_normalization_nfkd(self):
        """Test NFKD normalization for various Unicode forms."""
        # Latin small letter a with acute (composed)
        composed = "café"
        # Same but decomposed
        decomposed = "cafe\u0301"
        assert normalize_string(composed) == normalize_string(decomposed)

    def test_right_to_left_marks(self):
        """Test removal of right-to-left and left-to-right marks."""
        # Text with RTL/LTR marks
        result = normalize_string("\u200eArtist\u200f Name")
        assert result == "artist name"

    def test_zero_width_characters(self):
        """Test removal of zero-width spaces and joiners."""
        result = normalize_string("Art\u200bist")  # Zero-width space
        # Zero-width space becomes a regular space after regex removal
        assert result == "art ist"

    def test_fullwidth_characters(self):
        """Test normalization of fullwidth Latin characters."""
        # Fullwidth "ARTIST"
        result = normalize_string("ＡＲＴＩＳＴ")
        assert result == "artist"

    def test_non_latin_scripts_removed(self):
        """Test that non-Latin scripts are handled gracefully."""
        result = normalize_string("Artist 日本語 Name")
        assert result == "artist name"


class TestVeryLongStrings:
    """Test handling of very long metadata strings."""

    def test_very_long_artist_name(self):
        """Test normalization of extremely long artist name."""
        long_artist = "A" * 10000
        result = normalize_artist(long_artist)
        assert len(result) == 10000
        assert result == "a" * 10000

    def test_very_long_fingerprint(self):
        """Test fingerprint generation with very long fields."""
        track = {
            "AlbumArtist": "A" * 5000,
            "Album": "B" * 5000,
            "Name": "C" * 5000
        }
        fingerprint = build_track_fingerprint(track)
        # Format: "artist|album|title"
        expected_length = 5000 + 1 + 5000 + 1 + 5000  # Including pipes
        assert len(fingerprint) == expected_length

    def test_long_string_with_many_spaces(self):
        """Test collapsing of many consecutive spaces."""
        long_spaced = "Artist" + (" " * 1000) + "Name"
        result = normalize_string(long_spaced)
        assert result == "artist name"

    def test_long_special_char_string(self):
        """Test removal of many special characters."""
        special_chars = "Artist" + ("!@#$%^&*()" * 100) + "Name"
        result = normalize_string(special_chars)
        assert result == "artist name"


class TestCacheExpirationEdgeCases:
    """Test cache expiration boundary conditions."""

    def test_cache_exactly_at_ttl_boundary(self):
        """Test cache expiration exactly at TTL boundary."""
        cache = KnownTracksCache(tracks=[{"id": "1"}], fetched_at=time.time(), ttl_seconds=5)

        # Just before expiration
        time.sleep(4.9)
        assert not cache.is_expired()

        # Just after expiration
        time.sleep(0.2)  # Total: 5.1 seconds
        assert cache.is_expired()

    def test_cache_with_zero_ttl(self):
        """Test cache with zero TTL expires immediately."""
        cache = KnownTracksCache(tracks=[{"id": "1"}], ttl_seconds=0)
        time.sleep(0.01)  # Any passage of time
        assert cache.is_expired()

    def test_cache_refresh_updates_timestamp(self):
        """Test that refresh updates the fetched_at timestamp."""
        cache = KnownTracksCache(tracks=[{"id": "1"}], ttl_seconds=5)
        original_time = cache.fetched_at

        time.sleep(0.1)
        cache.refresh([{"id": "2"}])

        assert cache.fetched_at > original_time
        assert cache.get_tracks() == [{"id": "2"}]

    def test_cache_invalidation_sets_expired_time(self):
        """Test that invalidate makes cache expired."""
        cache = KnownTracksCache(tracks=[{"id": "1"}], ttl_seconds=300)
        assert not cache.is_expired()

        cache.invalidate()
        assert cache.is_expired()

    def test_get_cached_tracks_force_refresh(self):
        """Test force_refresh bypasses unexpired cache."""
        # Reset global cache to expired state before test
        from src.azuracast import cache
        cache._known_tracks_cache = KnownTracksCache(tracks=[], fetched_at=0.0)

        call_count = 0

        def mock_fetch():
            nonlocal call_count
            call_count += 1
            return [{"id": str(call_count)}]

        # First call - cache is expired, should fetch
        tracks1 = get_cached_known_tracks(mock_fetch, force_refresh=False)
        assert call_count == 1

        # Second call without force - should use cache (not expired yet)
        tracks2 = get_cached_known_tracks(mock_fetch, force_refresh=False)
        assert call_count == 1  # Should still be 1 (cache hit)
        assert tracks1 == tracks2

        # Third call with force - should fetch again
        tracks3 = get_cached_known_tracks(mock_fetch, force_refresh=True)
        assert call_count == 2  # Should increment to 2
        assert tracks3 != tracks1


class TestConcurrentSourceDuplicates:
    """Test handling of multiple source tracks matching same AzuraCast track."""

    def test_three_source_tracks_same_mbid(self):
        """Test detection when 3+ source tracks have same MusicBrainz ID."""
        known_tracks = [
            {"id": "az-1", "custom_fields": {"musicbrainz_trackid": "mbid-123"}}
        ]

        # Three different source tracks with same MBID
        track1 = {"ProviderIds": {"MusicBrainzTrack": "mbid-123"}, "Name": "Track 1"}
        track2 = {"ProviderIds": {"MusicBrainzTrack": "mbid-123"}, "Name": "Track 2"}
        track3 = {"ProviderIds": {"MusicBrainzTrack": "mbid-123"}, "Name": "Track 3"}

        # All should match the same AzuraCast track
        result1 = check_file_exists_by_musicbrainz(known_tracks, track1)
        result2 = check_file_exists_by_musicbrainz(known_tracks, track2)
        result3 = check_file_exists_by_musicbrainz(known_tracks, track3)

        assert result1 == "az-1"
        assert result2 == "az-1"
        assert result3 == "az-1"

    def test_multiple_source_tracks_same_fingerprint(self):
        """Test detection when multiple source tracks have same normalized fingerprint."""
        # AzuraCast stores original metadata, not pre-normalized
        known_tracks = [
            {
                "id": "az-1",
                "artist": "The Beatles",
                "album": "Abbey Road",
                "title": "Come Together",
                "length": 259
            }
        ]

        # Same song with case variations (should match)
        track1 = {
            "AlbumArtist": "The Beatles",
            "Album": "Abbey Road",
            "Name": "Come Together",
            "RunTimeTicks": 2590000000  # 259 seconds
        }
        track2 = {
            "AlbumArtist": "the beatles",  # lowercase variation
            "Album": "ABBEY ROAD",  # uppercase variation
            "Name": "come together",  # lowercase variation
            "RunTimeTicks": 2600000000  # 260 seconds (within ±5s tolerance)
        }
        track3 = {
            "AlbumArtist": "THE BEATLES",
            "Album": "abbey road",
            "Name": "Come Together",
            "RunTimeTicks": 2580000000  # 258 seconds
        }

        # All should match due to case-insensitive normalization
        result1 = check_file_exists_by_metadata(known_tracks, track1)
        result2 = check_file_exists_by_metadata(known_tracks, track2)
        result3 = check_file_exists_by_metadata(known_tracks, track3)

        assert result1 == "az-1"
        assert result2 == "az-1"
        assert result3 == "az-1"

    def test_source_duplicate_with_different_quality(self):
        """Test when same song exists in different qualities/formats."""
        known_tracks = [
            {
                "id": "az-1",
                "artist": "pink floyd",
                "album": "dark side of the moon the",
                "title": "time",
                "length": 413
            }
        ]

        # Same song, different bitrates/formats
        track_mp3 = {
            "AlbumArtist": "Pink Floyd",
            "Album": "The Dark Side of the Moon",
            "Name": "Time",
            "Path": "/music/Pink Floyd/DSOTM/Time.mp3",
            "RunTimeTicks": 4130000000
        }
        track_flac = {
            "AlbumArtist": "Pink Floyd",
            "Album": "The Dark Side of the Moon",
            "Name": "Time",
            "Path": "/music/Pink Floyd/DSOTM [FLAC]/Time.flac",
            "RunTimeTicks": 4130000000
        }

        # Both should be detected as duplicates
        result_mp3 = check_file_exists_by_metadata(known_tracks, track_mp3)
        result_flac = check_file_exists_by_metadata(known_tracks, track_flac)

        assert result_mp3 == "az-1"
        assert result_flac == "az-1"


class TestNormalizationEdgeCases:
    """Additional edge cases for normalization functions."""

    def test_the_only_word(self):
        """Test artist name is literally just 'The'."""
        result = normalize_artist("The")
        assert result == "the"

    def test_multiple_the_prefix(self):
        """Test handling of 'The The The Artist'."""
        result = normalize_artist("The The The Artist")
        # Only first "The" is moved
        assert result == "the the artist the"

    def test_mixed_case_the(self):
        """Test case-insensitive 'The' handling."""
        assert normalize_artist("THE Beatles") == "beatles the"
        assert normalize_artist("the Beatles") == "beatles the"
        assert normalize_artist("ThE Beatles") == "beatles the"

    def test_numbers_in_artist_name(self):
        """Test that numbers are preserved in normalization."""
        result = normalize_artist("Blink-182")
        assert result == "blink 182"

    def test_parentheses_and_brackets(self):
        """Test removal of parentheses and brackets."""
        result = normalize_string("Artist (feat. Guest) [Remastered]")
        assert result == "artist feat guest remastered"

    def test_apostrophes_and_quotes(self):
        """Test handling of apostrophes and quotes."""
        result = normalize_string("Artist's \"Best\" Song")
        assert result == "artist s best song"

    def test_ampersand_normalization(self):
        """Test ampersand becomes space."""
        result = normalize_string("Simon & Garfunkel")
        assert result == "simon garfunkel"

    def test_forward_slash_normalization(self):
        """Test forward slash becomes space."""
        result = normalize_string("AC/DC")
        assert result == "ac dc"


class TestDurationToleranceEdgeCases:
    """Test duration comparison edge cases."""

    def test_duration_exactly_5_seconds_difference(self):
        """Test duration difference of exactly 5 seconds (boundary)."""
        known_tracks = [
            {
                "id": "az-1",
                "artist": "artist",
                "album": "album",
                "title": "song",
                "length": 300  # 5 minutes
            }
        ]
        track = {
            "AlbumArtist": "Artist",
            "Album": "Album",
            "Name": "Song",
            "RunTimeTicks": 3050000000  # 305 seconds (exactly +5s)
        }

        # Should still match (within tolerance)
        result = check_file_exists_by_metadata(known_tracks, track)
        assert result == "az-1"

    def test_duration_6_seconds_difference(self):
        """Test duration difference of 6 seconds (beyond tolerance)."""
        known_tracks = [
            {
                "id": "az-1",
                "artist": "artist",
                "album": "album",
                "title": "song",
                "length": 300
            }
        ]
        track = {
            "AlbumArtist": "Artist",
            "Album": "Album",
            "Name": "Song",
            "RunTimeTicks": 3060000000  # 306 seconds (+6s)
        }

        # Should NOT match (beyond tolerance)
        result = check_file_exists_by_metadata(known_tracks, track)
        assert result is None

    def test_missing_duration_in_known_track(self):
        """Test when AzuraCast track has no duration field."""
        known_tracks = [
            {
                "id": "az-1",
                "artist": "artist",
                "album": "album",
                "title": "song"
                # No 'length' field
            }
        ]
        track = {
            "AlbumArtist": "Artist",
            "Album": "Album",
            "Name": "Song",
            "RunTimeTicks": 3000000000
        }

        # Should still match on fingerprint alone
        result = check_file_exists_by_metadata(known_tracks, track)
        assert result == "az-1"

    def test_missing_duration_in_source_track(self):
        """Test when source track has no duration field."""
        known_tracks = [
            {
                "id": "az-1",
                "artist": "artist",
                "album": "album",
                "title": "song",
                "length": 300
            }
        ]
        track = {
            "AlbumArtist": "Artist",
            "Album": "Album",
            "Name": "Song"
            # No RunTimeTicks field
        }

        # Should still match on fingerprint alone
        result = check_file_exists_by_metadata(known_tracks, track)
        assert result == "az-1"
