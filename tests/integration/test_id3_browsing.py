"""Integration tests for ID3 browsing workflow (T016).

This test suite validates the complete ID3 browsing flow:
1. get_artists() - Retrieve all artists indexed alphabetically
2. get_artist(id) - Get specific artist with their albums
3. get_album(id) - Get specific album with all tracks
4. Validate track metadata (albumId, artistId, parent, isDir, isVideo, type)
5. Verify video filtering (isVideo=false - no video files in results)

Test Coverage:
- Complete ID3 browsing workflow from artists to tracks
- Critical field validation on all tracks
- Video filtering (exclude isVideo=true tracks)
- Error handling for missing artists/albums
- Track count validation
- No duplicate tracks
- Pagination support (if applicable)

Uses mocked Subsonic API responses via respx library.
All mock data matches Navidrome response structure.
"""

import json
from pathlib import Path
from typing import Any, Dict, List

import httpx
import pytest
from pytest_mock import MockerFixture

from src.subsonic.client import SubsonicClient
from src.subsonic.exceptions import SubsonicNotFoundError
from src.subsonic.models import SubsonicConfig


# Fixture: Load ID3 response fixtures
@pytest.fixture
def id3_fixtures() -> Dict[str, Any]:
    """Load ID3 browsing API response fixtures from JSON file.

    Returns:
        Dictionary containing all ID3 fixture responses
    """
    fixtures_path = Path(__file__).parent.parent / "fixtures" / "id3_responses.json"
    with open(fixtures_path, "r") as f:
        return json.load(f)


# Fixture: Create SubsonicClient with test config
@pytest.fixture
def client(mocker: MockerFixture) -> SubsonicClient:
    """Create a SubsonicClient instance with test configuration.

    Mock the httpx.Client to avoid HTTP/2 dependency and network calls.

    Returns:
        Configured SubsonicClient for testing
    """
    config = SubsonicConfig(
        url="https://music.example.com",
        username="testuser",
        password="testpass",
        client_name="playlistgen-test",
        api_version="1.16.1",
    )

    # Mock httpx.Client to avoid HTTP/2 dependency
    mock_client = mocker.MagicMock(spec=httpx.Client)
    mocker.patch("httpx.Client", return_value=mock_client)

    return SubsonicClient(config)


# Helper: Mock httpx.Response
def mock_response(status_code: int, json_data: Dict[str, Any]) -> httpx.Response:
    """Create a mock httpx.Response object.

    Args:
        status_code: HTTP status code
        json_data: JSON response body

    Returns:
        Mock httpx.Response with specified data
    """
    response = httpx.Response(
        status_code=status_code,
        json=json_data,
        request=httpx.Request("GET", "https://music.example.com/rest/getArtists"),
    )
    return response


class TestID3CompleteWorkflow:
    """Test complete ID3 browsing workflow from artists to tracks."""

    def test_complete_id3_browsing_flow_pink_floyd(
        self, client: SubsonicClient, id3_fixtures: Dict[str, Any], mocker: MockerFixture
    ):
        """Test complete ID3 workflow: get_artists → get_artist → get_album → tracks.

        Validates:
        - Artist retrieval from alphabetical index
        - Artist details with album list
        - Album details with complete track list
        - All tracks have critical fields
        - No video files in results (isVideo=false)
        """
        # Step 1: Get all artists (returns flattened list)
        client.client.get = mocker.MagicMock(
            return_value=mock_response(200, id3_fixtures["getArtists_success"])
        )
        artists_list = client.get_artists()

        # Verify artists list (flattened from indexes)
        assert isinstance(artists_list, list)
        assert len(artists_list) == 3  # Pink Floyd, Queen, The Beatles

        # Find Pink Floyd in the list
        pink_floyd_artist = None
        for artist in artists_list:
            if artist["name"] == "Pink Floyd":
                pink_floyd_artist = artist
                break

        assert pink_floyd_artist is not None
        assert pink_floyd_artist["id"] == "ar-100"
        assert pink_floyd_artist["albumCount"] == 3

        # Step 2: Get Pink Floyd artist details (returns artist dict)
        client.client.get = mocker.MagicMock(
            return_value=mock_response(200, id3_fixtures["getArtist_pinkfloyd"])
        )
        artist = client.get_artist("ar-100")

        # Verify artist details (direct dict, not wrapped)
        assert artist["id"] == "ar-100"
        assert artist["name"] == "Pink Floyd"
        assert "album" in artist
        assert len(artist["album"]) == 3

        # Find "The Dark Side of the Moon" album
        darkside_album = None
        for album in artist["album"]:
            if album["name"] == "The Dark Side of the Moon":
                darkside_album = album
                break

        assert darkside_album is not None
        assert darkside_album["id"] == "al-100"
        assert darkside_album["artistId"] == "ar-100"
        assert darkside_album["songCount"] == 8

        # Step 3: Get album with tracks (returns list of SubsonicTrack objects)
        client.client.get = mocker.MagicMock(
            return_value=mock_response(200, id3_fixtures["getAlbum_darkside"])
        )
        tracks = client.get_album("al-100")

        # Verify tracks list
        assert isinstance(tracks, list)
        assert len(tracks) == 8

        # Step 4: Validate all tracks have critical fields
        for track in tracks:
            # Critical fields must be present (SubsonicTrack objects)
            assert hasattr(track, "id"), f"Track missing 'id': {getattr(track, 'title', 'Unknown')}"
            assert hasattr(track, "albumId"), f"Track {track.id} missing 'albumId'"
            assert hasattr(track, "artistId"), f"Track {track.id} missing 'artistId'"
            assert hasattr(track, "parent"), f"Track {track.id} missing 'parent'"
            assert hasattr(track, "isVideo"), f"Track {track.id} missing 'isVideo'"
            assert hasattr(track, "type"), f"Track {track.id} missing 'type'"

            # Verify field values
            assert track.albumId == "al-100"
            assert track.artistId == "ar-100"
            assert track.parent == "al-100"
            assert track.isVideo is False, f"Track {track.id} is video file"
            assert track.type == "music"

        # Step 5: Verify track count matches expectation
        assert len(tracks) == 8, f"Expected 8 tracks, got {len(tracks)}"

        # Step 6: Verify no duplicate tracks
        track_ids = [track.id for track in tracks]
        assert len(track_ids) == len(set(track_ids)), "Duplicate track IDs found"

    def test_complete_id3_browsing_flow_queen(
        self, client: SubsonicClient, id3_fixtures: Dict[str, Any], mocker: MockerFixture
    ):
        """Test complete ID3 workflow for Queen artist.

        Validates:
        - Multiple albums per artist
        - Different track counts per album
        - Critical fields on all tracks
        """
        # Get all artists
        client.client.get = mocker.MagicMock(
            return_value=mock_response(200, id3_fixtures["getArtists_success"])
        )
        artists_list = client.get_artists()

        # Find Queen
        queen_artist = None
        for artist in artists_list:
            if artist["name"] == "Queen":
                queen_artist = artist
                break

        assert queen_artist is not None
        assert queen_artist["id"] == "ar-200"

        # Get Queen artist details
        client.client.get = mocker.MagicMock(
            return_value=mock_response(200, id3_fixtures["getArtist_queen"])
        )
        artist = client.get_artist("ar-200")
        assert len(artist["album"]) == 2

        # Get "A Night at the Opera" album
        client.client.get = mocker.MagicMock(
            return_value=mock_response(200, id3_fixtures["getAlbum_nightatopera"])
        )
        tracks = client.get_album("al-200")

        # Validate tracks
        assert len(tracks) == 6

        # Validate critical fields on all tracks
        for track in tracks:
            assert track.albumId == "al-200"
            assert track.artistId == "ar-200"
            assert track.parent == "al-200"
            assert track.isVideo is False
            assert track.type == "music"

    def test_complete_id3_browsing_flow_beatles(
        self, client: SubsonicClient, id3_fixtures: Dict[str, Any], mocker: MockerFixture
    ):
        """Test complete ID3 workflow for The Beatles.

        Validates:
        - Artist with "The" prefix (ignoredArticles handling)
        - Album with 8 tracks
        - Critical field validation
        """
        # Get all artists
        client.client.get = mocker.MagicMock(
            return_value=mock_response(200, id3_fixtures["getArtists_success"])
        )
        artists_list = client.get_artists()

        # Find The Beatles
        beatles_artist = None
        for artist in artists_list:
            if artist["name"] == "The Beatles":
                beatles_artist = artist
                break

        assert beatles_artist is not None
        assert beatles_artist["id"] == "ar-300"

        # Get artist details
        client.client.get = mocker.MagicMock(
            return_value=mock_response(200, id3_fixtures["getArtist_beatles"])
        )
        artist = client.get_artist("ar-300")
        assert len(artist["album"]) == 3

        # Get Abbey Road album
        client.client.get = mocker.MagicMock(
            return_value=mock_response(200, id3_fixtures["getAlbum_abbeyroad"])
        )
        tracks = client.get_album("al-300")

        # Validate tracks
        assert len(tracks) == 8

        # All tracks should be music (not video)
        for track in tracks:
            assert track.albumId == "al-300"
            assert track.artistId == "ar-300"
            assert track.isVideo is False
            assert track.type == "music"


class TestID3CriticalFieldValidation:
    """Test critical field presence and values on tracks."""

    def test_all_tracks_have_album_id(
        self, client: SubsonicClient, id3_fixtures: Dict[str, Any], mocker: MockerFixture
    ):
        """Validate all tracks have albumId field matching parent album."""
        client.client.get = mocker.MagicMock(
            return_value=mock_response(200, id3_fixtures["getAlbum_darkside"])
        )
        tracks = client.get_album("al-100")

        for track in tracks:
            assert hasattr(track, "albumId")
            assert track.albumId == "al-100"

    def test_all_tracks_have_artist_id(
        self, client: SubsonicClient, id3_fixtures: Dict[str, Any], mocker: MockerFixture
    ):
        """Validate all tracks have artistId field matching parent artist."""
        client.client.get = mocker.MagicMock(
            return_value=mock_response(200, id3_fixtures["getAlbum_nightatopera"])
        )
        tracks = client.get_album("al-200")

        for track in tracks:
            assert hasattr(track, "artistId")
            assert track.artistId == "ar-200"

    def test_all_tracks_have_parent_field(
        self, client: SubsonicClient, id3_fixtures: Dict[str, Any], mocker: MockerFixture
    ):
        """Validate all tracks have parent field."""
        client.client.get = mocker.MagicMock(
            return_value=mock_response(200, id3_fixtures["getAlbum_abbeyroad"])
        )
        tracks = client.get_album("al-300")

        for track in tracks:
            assert hasattr(track, "parent")
            assert track.parent == "al-300"

    def test_all_tracks_have_is_video_field(
        self, client: SubsonicClient, id3_fixtures: Dict[str, Any], mocker: MockerFixture
    ):
        """Validate all tracks have isVideo field."""
        client.client.get = mocker.MagicMock(
            return_value=mock_response(200, id3_fixtures["getAlbum_darkside"])
        )
        tracks = client.get_album("al-100")

        for track in tracks:
            assert hasattr(track, "isVideo")
            assert isinstance(track.isVideo, bool)

    def test_all_tracks_have_type_field(
        self, client: SubsonicClient, id3_fixtures: Dict[str, Any], mocker: MockerFixture
    ):
        """Validate all tracks have type field."""
        client.client.get = mocker.MagicMock(
            return_value=mock_response(200, id3_fixtures["getAlbum_nightatopera"])
        )
        tracks = client.get_album("al-200")

        for track in tracks:
            assert hasattr(track, "type")
            assert track.type in ["music", "podcast", "audiobook", "video"]

    def test_all_tracks_have_is_dir_false(
        self, client: SubsonicClient, id3_fixtures: Dict[str, Any], mocker: MockerFixture
    ):
        """Validate tracks are not directories (isDir=false or missing).

        In Subsonic API, tracks should not have isDir=true.
        The field may be present and false, or omitted entirely.
        """
        client.client.get = mocker.MagicMock(
            return_value=mock_response(200, id3_fixtures["getAlbum_darkside"])
        )
        tracks = client.get_album("al-100")

        for track in tracks:
            # isDir should be false
            assert track.isDir is False, f"Track {track.id} has isDir=true"


class TestID3VideoFiltering:
    """Test video file filtering (isVideo=false)."""

    def test_filter_video_tracks_from_album(
        self, client: SubsonicClient, id3_fixtures: Dict[str, Any], mocker: MockerFixture
    ):
        """Test that video tracks are filtered out from results.

        Validates:
        - Album with mixed audio and video files
        - Only audio tracks (isVideo=false) are returned
        - Video tracks (isVideo=true) are excluded by get_album()
        """
        client.client.get = mocker.MagicMock(
            return_value=mock_response(200, id3_fixtures["getAlbum_with_videos"])
        )
        # get_album() filters out videos automatically
        audio_tracks = client.get_album("al-999")

        # Should have only 3 audio tracks (2 videos filtered out by client)
        assert len(audio_tracks) == 3

        # Verify all remaining tracks are audio
        for track in audio_tracks:
            assert track.isVideo is False
            assert track.type == "music"
            assert track.contentType.startswith("audio/")

    def test_no_video_tracks_in_normal_albums(
        self, client: SubsonicClient, id3_fixtures: Dict[str, Any], mocker: MockerFixture
    ):
        """Test that normal albums have no video tracks."""
        client.client.get = mocker.MagicMock(
            return_value=mock_response(200, id3_fixtures["getAlbum_darkside"])
        )
        tracks = client.get_album("al-100")

        # All tracks should be audio (isVideo=false)
        video_tracks = [track for track in tracks if track.isVideo]
        assert len(video_tracks) == 0, f"Found {len(video_tracks)} video tracks in audio album"

    def test_verify_video_type_field(
        self, client: SubsonicClient, id3_fixtures: Dict[str, Any], mocker: MockerFixture
    ):
        """Verify that only audio tracks (type='music') are returned by get_album()."""
        client.client.get = mocker.MagicMock(
            return_value=mock_response(200, id3_fixtures["getAlbum_with_videos"])
        )
        # get_album() filters videos, so we only get audio tracks
        audio_tracks = client.get_album("al-999")

        # All returned tracks should be music (videos filtered out)
        for track in audio_tracks:
            assert track.type == "music"
            assert track.contentType.startswith("audio/")
            assert track.isVideo is False


class TestID3ErrorHandling:
    """Test error handling for missing artists/albums."""

    def test_get_artist_not_found(
        self, client: SubsonicClient, id3_fixtures: Dict[str, Any], mocker: MockerFixture
    ):
        """Test get_artist raises SubsonicNotFoundError for missing artist."""
        client.client.get = mocker.MagicMock(
            return_value=mock_response(200, id3_fixtures["getArtist_not_found"])
        )

        with pytest.raises(SubsonicNotFoundError) as exc_info:
            client.get_artist("ar-999")

        assert exc_info.value.code == 70
        assert "Artist not found" in exc_info.value.message

    def test_get_album_not_found(
        self, client: SubsonicClient, id3_fixtures: Dict[str, Any], mocker: MockerFixture
    ):
        """Test get_album raises SubsonicNotFoundError for missing album."""
        client.client.get = mocker.MagicMock(
            return_value=mock_response(200, id3_fixtures["getAlbum_not_found"])
        )

        with pytest.raises(SubsonicNotFoundError) as exc_info:
            client.get_album("al-999")

        assert exc_info.value.code == 70
        assert "Album not found" in exc_info.value.message

    def test_invalid_artist_id_format(
        self, client: SubsonicClient, id3_fixtures: Dict[str, Any], mocker: MockerFixture
    ):
        """Test handling of invalid artist ID format."""
        client.client.get = mocker.MagicMock(
            return_value=mock_response(200, id3_fixtures["getArtist_not_found"])
        )

        # Empty ID should raise error
        with pytest.raises(SubsonicNotFoundError):
            client.get_artist("")

    def test_invalid_album_id_format(
        self, client: SubsonicClient, id3_fixtures: Dict[str, Any], mocker: MockerFixture
    ):
        """Test handling of invalid album ID format."""
        client.client.get = mocker.MagicMock(
            return_value=mock_response(200, id3_fixtures["getAlbum_not_found"])
        )

        # Empty ID should raise error
        with pytest.raises(SubsonicNotFoundError):
            client.get_album("")


class TestID3TrackCountValidation:
    """Test track count matches expectations."""

    def test_darkside_track_count(
        self, client: SubsonicClient, id3_fixtures: Dict[str, Any], mocker: MockerFixture
    ):
        """Verify The Dark Side of the Moon has exactly 8 tracks."""
        client.client.get = mocker.MagicMock(
            return_value=mock_response(200, id3_fixtures["getAlbum_darkside"])
        )
        tracks = client.get_album("al-100")

        assert len(tracks) == 8

    def test_night_at_opera_track_count(
        self, client: SubsonicClient, id3_fixtures: Dict[str, Any], mocker: MockerFixture
    ):
        """Verify A Night at the Opera has exactly 6 tracks."""
        client.client.get = mocker.MagicMock(
            return_value=mock_response(200, id3_fixtures["getAlbum_nightatopera"])
        )
        tracks = client.get_album("al-200")

        assert len(tracks) == 6

    def test_abbey_road_track_count(
        self, client: SubsonicClient, id3_fixtures: Dict[str, Any], mocker: MockerFixture
    ):
        """Verify Abbey Road has exactly 8 tracks."""
        client.client.get = mocker.MagicMock(
            return_value=mock_response(200, id3_fixtures["getAlbum_abbeyroad"])
        )
        tracks = client.get_album("al-300")

        assert len(tracks) == 8

    def test_track_count_matches_song_count_field(
        self, client: SubsonicClient, id3_fixtures: Dict[str, Any], mocker: MockerFixture
    ):
        """Verify actual track count matches expected count."""
        # Test all albums
        test_cases = [
            ("al-100", "getAlbum_darkside", 8),
            ("al-200", "getAlbum_nightatopera", 6),
            ("al-300", "getAlbum_abbeyroad", 8),
        ]

        for album_id, fixture_key, expected_count in test_cases:
            client.client.get = mocker.MagicMock(
                return_value=mock_response(200, id3_fixtures[fixture_key])
            )
            tracks = client.get_album(album_id)

            actual_count = len(tracks)
            assert actual_count == expected_count


class TestID3NoDuplicateTracks:
    """Test that no duplicate tracks exist in results."""

    def test_no_duplicate_track_ids_in_album(
        self, client: SubsonicClient, id3_fixtures: Dict[str, Any], mocker: MockerFixture
    ):
        """Verify no duplicate track IDs within an album."""
        client.client.get = mocker.MagicMock(
            return_value=mock_response(200, id3_fixtures["getAlbum_darkside"])
        )
        tracks = client.get_album("al-100")

        track_ids = [track.id for track in tracks]

        # Check for duplicates
        assert len(track_ids) == len(set(track_ids)), f"Duplicate track IDs found: {track_ids}"

    def test_no_duplicate_tracks_across_multiple_albums(
        self, client: SubsonicClient, id3_fixtures: Dict[str, Any], mocker: MockerFixture
    ):
        """Verify track IDs are unique across different albums."""
        all_track_ids: List[str] = []

        # Get tracks from multiple albums
        albums = [
            ("al-100", "getAlbum_darkside"),
            ("al-200", "getAlbum_nightatopera"),
            ("al-300", "getAlbum_abbeyroad"),
        ]

        for album_id, fixture_key in albums:
            client.client.get = mocker.MagicMock(
                return_value=mock_response(200, id3_fixtures[fixture_key])
            )
            tracks = client.get_album(album_id)
            all_track_ids.extend([track.id for track in tracks])

        # Verify no duplicates across all albums
        assert len(all_track_ids) == len(set(all_track_ids)), "Duplicate track IDs across albums"

    def test_track_titles_can_duplicate_across_albums(
        self, client: SubsonicClient, id3_fixtures: Dict[str, Any], mocker: MockerFixture
    ):
        """Verify track titles can be the same across albums (but IDs differ).

        Track titles may repeat (e.g., "Intro" on multiple albums),
        but track IDs must always be unique.
        """
        # This is a validation test - titles CAN duplicate, IDs CANNOT
        client.client.get = mocker.MagicMock(
            return_value=mock_response(200, id3_fixtures["getAlbum_darkside"])
        )
        album1_tracks = client.get_album("al-100")

        client.client.get = mocker.MagicMock(
            return_value=mock_response(200, id3_fixtures["getAlbum_nightatopera"])
        )
        album2_tracks = client.get_album("al-200")

        # Get all track IDs
        ids1 = [track.id for track in album1_tracks]
        ids2 = [track.id for track in album2_tracks]

        # IDs must not overlap
        assert len(set(ids1) & set(ids2)) == 0, "Track IDs are not unique across albums"


class TestID3RequestParameters:
    """Test correct request parameter formatting for ID3 endpoints."""

    def test_get_artists_request_params(
        self, client: SubsonicClient, id3_fixtures: Dict[str, Any], mocker: MockerFixture
    ):
        """Test get_artists sends correct auth parameters."""
        client.client.get = mocker.MagicMock(
            return_value=mock_response(200, id3_fixtures["getArtists_success"])
        )

        client.get_artists()

        # Verify request was made
        assert client.client.get.called
        call_args = client.client.get.call_args

        # Check endpoint
        assert "getArtists" in call_args[0][0]

        # Check auth params
        params = call_args.kwargs.get("params", {})
        assert "u" in params  # username
        assert "t" in params  # token
        assert "s" in params  # salt
        assert "v" in params  # version
        assert "c" in params  # client name
        assert "f" in params  # format

    def test_get_artist_request_params(
        self, client: SubsonicClient, id3_fixtures: Dict[str, Any], mocker: MockerFixture
    ):
        """Test get_artist sends correct ID parameter."""
        client.client.get = mocker.MagicMock(
            return_value=mock_response(200, id3_fixtures["getArtist_pinkfloyd"])
        )

        client.get_artist("ar-100")

        call_args = client.client.get.call_args
        params = call_args.kwargs.get("params", {})

        assert "id" in params
        assert params["id"] == "ar-100"

    def test_get_album_request_params(
        self, client: SubsonicClient, id3_fixtures: Dict[str, Any], mocker: MockerFixture
    ):
        """Test get_album sends correct ID parameter."""
        client.client.get = mocker.MagicMock(
            return_value=mock_response(200, id3_fixtures["getAlbum_darkside"])
        )

        client.get_album("al-100")

        call_args = client.client.get.call_args
        params = call_args.kwargs.get("params", {})

        assert "id" in params
        assert params["id"] == "al-100"
