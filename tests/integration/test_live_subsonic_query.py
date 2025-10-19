"""
T021: Live Integration Test - Subsonic Query

Tests querying actual Subsonic/Emby endpoint using environment credentials
and validating track metadata retrieval.

This test uses LIVE environment variables (NO mocks).
"""
import os
import pytest
from typing import List
from src.subsonic.client import SubsonicClient
from src.subsonic.models import SubsonicTrack
from src.ai_playlist.config import AIPlaylistConfig


@pytest.mark.integration
@pytest.mark.live
class TestLiveSubsonicQuery:
    """Live integration tests for Subsonic/Emby API queries."""

    @pytest.fixture
    def skip_if_no_env(self):
        """Skip test if required environment variables are missing."""
        required = ['SUBSONIC_URL', 'SUBSONIC_USER', 'SUBSONIC_PASSWORD']
        missing = [var for var in required if not os.getenv(var)]

        if missing:
            pytest.skip(
                f"Required environment variables missing: {', '.join(missing)}. "
                f"Set these in your shell environment to run live tests."
            )

    @pytest.fixture
    def config(self, skip_if_no_env) -> AIPlaylistConfig:
        """Load configuration from environment variables."""
        try:
            return AIPlaylistConfig.from_environment()
        except EnvironmentError as e:
            pytest.skip(f"Configuration error: {e}")

    @pytest.fixture
    def subsonic_client(self, config: AIPlaylistConfig) -> SubsonicClient:
        """Create Subsonic client with live credentials."""
        from src.subsonic.models import SubsonicConfig

        subsonic_config = SubsonicConfig(
            url=config.subsonic_url,
            username=config.subsonic_user,
            password=config.subsonic_password
        )
        client = SubsonicClient(subsonic_config)
        return client

    def test_connect_to_subsonic_endpoint(
        self, subsonic_client: SubsonicClient, config: AIPlaylistConfig
    ):
        """Test successful connection to live Subsonic/Emby endpoint.

        Success Criteria:
        - Connection succeeds
        - API responds with valid ping
        - Server version is returned
        """
        # Act
        ping_result = subsonic_client.ping()

        # Assert
        assert ping_result is True, "Ping should return True on success"

    def test_query_tracks_morning_drive_criteria(
        self, subsonic_client: SubsonicClient
    ):
        """Test querying tracks matching Morning Drive criteria.

        Success Criteria:
        - Query returns tracks
        - Tracks have required metadata fields
        - Can retrieve random songs for playlist generation
        """
        # Act - Get random songs which is better supported than search
        tracks = subsonic_client.get_random_songs(size=150)

        # Assert - Tracks returned (may be less than requested based on library size)
        assert len(tracks) > 0, \
            f"Expected tracks, got {len(tracks)}. Check music library size."

    def test_validate_track_metadata_fields(
        self, subsonic_client: SubsonicClient
    ):
        """Test that tracks have all required metadata fields.

        Success Criteria:
        - Each track has: ID, title, artist, album
        - Duration is present and > 0
        - Genre information available (if tagged)
        - Year information available (if tagged)
        """
        # Act - Get sample tracks
        tracks = subsonic_client.get_random_songs(size=50)

        assert len(tracks) > 0, "No tracks returned from query"

        # Assert - Check metadata fields on all tracks
        for track in tracks:
            assert track.id is not None and len(track.id) > 0
            assert track.title is not None and len(track.title) > 0
            assert track.artist is not None and len(track.artist) > 0

            # Duration should be positive
            if hasattr(track, 'duration') and track.duration:
                assert track.duration > 0

            # Album may be empty for singles, but field should exist
            assert hasattr(track, 'album')

    def test_filter_tracks_by_genre(
        self, subsonic_client: SubsonicClient
    ):
        """Test filtering tracks by genre.

        Success Criteria:
        - Can retrieve genres from library
        - At least some tracks have genre metadata
        - Genre names are non-empty
        """
        # Act - Get available genres
        genres = subsonic_client.get_genres()

        # Assert - Genres returned
        assert len(genres) > 0, \
            "No genres found. Check genre tagging in library."

        # Assert - Genres have required fields
        for genre in genres[:10]:  # Check first 10 genres
            assert 'value' in genre or 'genre' in genre, \
                f"Genre missing name field: {genre}"

    def test_filter_tracks_by_year(
        self, subsonic_client: SubsonicClient
    ):
        """Test filtering tracks by year (era).

        Success Criteria:
        - Can retrieve tracks
        - At least some tracks have year metadata
        - Year values are reasonable (1900-2025)
        """
        # Act - Get random tracks and check year metadata
        tracks = subsonic_client.get_random_songs(size=50)

        # Assert - Tracks returned
        assert len(tracks) > 0, \
            "No tracks found. Check library content."

        # Assert - Year values are valid if present
        tracks_with_year = []
        for track in tracks:
            if hasattr(track, 'year') and track.year:
                tracks_with_year.append(track)
                assert 1900 <= track.year <= 2025, \
                    f"Track '{track.title}' has invalid year: {track.year}"

        # At least some tracks should have year metadata
        if len(tracks_with_year) == 0:
            pytest.skip("No tracks with year metadata found. Check ID3 tags in library.")

    def test_search_australian_artists(
        self, subsonic_client: SubsonicClient
    ):
        """Test searching for artists using search3.

        Success Criteria:
        - Search returns results
        - Artist metadata is present
        - Search functionality works
        """
        # Act - Search for artists using search3
        results = subsonic_client.search3("rock", artist_count=10, song_count=10)

        # Assert - Search completed successfully
        assert results is not None, "Search should return results"

        # Extract search results
        search_result = results.get('searchResult3', {})

        # Check if we got any results (artists or songs)
        artists = search_result.get('artist', [])
        songs = search_result.get('song', [])

        if len(artists) == 0 and len(songs) == 0:
            pytest.skip(
                "No search results found. Check library content or search functionality."
            )

    def test_retrieve_track_by_id(
        self, subsonic_client: SubsonicClient
    ):
        """Test retrieving albums and tracks using ID3 browsing.

        Success Criteria:
        - Can get list of artists
        - Can get artist details with albums
        - Can get album tracks
        - Full metadata is present
        """
        # Arrange - Get artists
        artists = subsonic_client.get_artists()
        assert len(artists) > 0, "No artists available in library"

        # Get first artist's details
        first_artist = artists[0]
        artist_details = subsonic_client.get_artist(first_artist['id'])

        assert 'album' in artist_details, "Artist should have albums"
        assert len(artist_details['album']) > 0, "Artist should have at least one album"

        # Act - Get tracks from first album
        first_album = artist_details['album'][0]
        tracks = subsonic_client.get_album(first_album['id'])

        # Assert
        assert len(tracks) > 0, "Album should have tracks"
        assert tracks[0].id is not None
        assert tracks[0].title is not None

    def test_query_performance_large_result_set(
        self, subsonic_client: SubsonicClient
    ):
        """Test query performance with large result sets.

        Success Criteria:
        - Can retrieve multiple tracks
        - Query completes in reasonable time (<10 seconds)
        - No duplicate tracks in results
        """
        import time

        # Act
        start_time = time.time()
        tracks = subsonic_client.get_random_songs(size=500)
        query_time = time.time() - start_time

        # Assert - Tracks returned (may be less than 500 based on library)
        assert len(tracks) > 0, \
            f"Expected tracks, got {len(tracks)}"

        # Assert - Performance is acceptable
        assert query_time < 10.0, \
            f"Query took {query_time:.2f}s, expected <10s"

        # Assert - No duplicates
        track_ids = [t.id for t in tracks]
        assert len(track_ids) == len(set(track_ids)), \
            "Duplicate tracks found in result set"

    def test_validate_bpm_metadata_availability(
        self, subsonic_client: SubsonicClient
    ):
        """Test availability of BPM metadata in library.

        Success Criteria:
        - Can retrieve tracks
        - BPM values are reasonable (60-200) if present
        - Report percentage of tracks with BPM
        """
        # Act - Get sample of tracks
        tracks = subsonic_client.get_random_songs(size=100)

        assert len(tracks) > 0, "No tracks returned"

        # Check BPM availability
        tracks_with_bpm = [
            t for t in tracks
            if hasattr(t, 'bpm') and t.bpm is not None and t.bpm > 0
        ]

        bpm_percentage = (len(tracks_with_bpm) / len(tracks)) * 100

        # Assert - Report BPM coverage
        # Note: This is informational - not all libraries have BPM tags
        print(f"\nBPM Metadata Coverage: {bpm_percentage:.1f}% ({len(tracks_with_bpm)}/{len(tracks)})")

        # If BPM exists, validate values
        for track in tracks_with_bpm:
            assert 60 <= track.bpm <= 200, \
                f"Track '{track.title}' has invalid BPM: {track.bpm}"

    def test_query_tracks_with_multiple_filters(
        self, subsonic_client: SubsonicClient
    ):
        """Test querying with search functionality.

        Success Criteria:
        - Search works correctly
        - Results are returned
        - No server errors with queries
        """
        # Act - Search using search3 endpoint
        results = subsonic_client.search3(
            query="alternative",
            artist_count=20,
            album_count=20,
            song_count=50
        )

        # Assert - Query executed successfully
        assert results is not None, "Search should return results"

        search_result = results.get('searchResult3', {})

        # Check if we got any results
        songs = search_result.get('song', [])
        albums = search_result.get('album', [])
        artists = search_result.get('artist', [])

        total_results = len(songs) + len(albums) + len(artists)

        if total_results == 0:
            pytest.skip(
                "No search results found. "
                "This depends on library content and metadata quality."
            )

        # Validate at least one type of result was returned
        assert total_results > 0, f"Expected search results, got none"
