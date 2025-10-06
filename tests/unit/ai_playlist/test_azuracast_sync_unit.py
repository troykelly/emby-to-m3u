"""
Unit Tests for AzuraCast Playlist Synchronization

Tests playlist creation, update, error handling, and API integration.
Covers FR-005 (Update existing playlists) and T021 (AzuraCast sync).
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
import uuid

from src.ai_playlist.models import (
    Playlist,
    PlaylistSpec,
    SelectedTrack,
    ValidationResult,
    TrackSelectionCriteria,
    DaypartSpec,
)
from src.ai_playlist.azuracast_sync import (
    sync_playlist_to_azuracast,
    _convert_selected_tracks_to_dict,
    AzuraCastPlaylistSyncError,
)


class TestSyncPlaylistToAzuraCast:
    """Test suite for sync_playlist_to_azuracast function."""

    @pytest.fixture
    def sample_playlist(self):
        """Create a sample validated playlist for testing."""
        daypart = DaypartSpec(
            name="Test Show",
            day="Monday",
            time_range=("06:00", "10:00"),
            bpm_progression={"06:00-10:00": (90, 130)},
            genre_mix={"Alternative": 0.25},
            era_distribution={"Current (0-2 years)": 0.40},
            australian_min=0.30,
            mood="energetic",
            tracks_per_hour=15,
        )

        criteria = TrackSelectionCriteria(
            bpm_range=(90, 130),
            bpm_tolerance=10,
            genre_mix={"Alternative": (0.20, 0.30)},
            genre_tolerance=0.05,
            era_distribution={"Current (0-2 years)": (0.35, 0.45)},
            era_tolerance=0.05,
            australian_min=0.30,
            energy_flow="energetic",
            excluded_track_ids=[],
        )

        playlist_id = str(uuid.uuid4())
        spec = PlaylistSpec(
            id=playlist_id,
            name="Monday_TestShow_0600_1000",
            daypart=daypart,
            target_duration_minutes=240,
            track_criteria=criteria,
            created_at=datetime.now(),
        )

        tracks = [
            SelectedTrack(
                track_id="track1",
                title="Test Song 1",
                artist="Artist 1",
                album="Album 1",
                bpm=120,
                genre="Alternative",
                year=2023,
                country="AU",
                duration_seconds=180,
                position=1,
                selection_reason="Matches criteria",
            ),
            SelectedTrack(
                track_id="track2",
                title="Test Song 2",
                artist="Artist 2",
                album="Album 2",
                bpm=110,
                genre="Alternative",
                year=2022,
                country="AU",
                duration_seconds=200,
                position=2,
                selection_reason="Matches criteria",
            ),
        ]

        validation = ValidationResult(
            constraint_satisfaction=0.85,
            bpm_satisfaction=0.90,
            genre_satisfaction=0.85,
            era_satisfaction=0.80,
            australian_content=0.50,
            flow_quality_score=0.75,
            bpm_variance=5.0,
            energy_progression="smooth",
            genre_diversity=0.80,
            gap_analysis={},
            passes_validation=True,
        )

        return Playlist(
            id=playlist_id,
            name="Monday_TestShow_0600_1000",
            tracks=tracks,
            spec=spec,
            validation_result=validation,
            created_at=datetime.now(),
        )

    @pytest.mark.asyncio
    @patch.dict(
        "os.environ",
        {
            "AZURACAST_HOST": "https://test.azuracast.com",
            "AZURACAST_API_KEY": "test_api_key",
            "AZURACAST_STATIONID": "1",
        },
    )
    @patch("src.ai_playlist.azuracast_sync.AzuraCastSync")
    async def test_sync_new_playlist_creates_playlist(
        self, mock_azuracast_class, sample_playlist
    ):
        """Test syncing a new playlist creates it in AzuraCast."""
        # Setup mock client
        mock_client = Mock()
        mock_azuracast_class.return_value = mock_client

        # Playlist does not exist
        mock_client.get_playlist.return_value = None

        # Create playlist returns new playlist info
        mock_client.create_playlist.return_value = {
            "id": 123,
            "name": "Monday_TestShow_0600_1000",
        }

        # Upload succeeds
        mock_client.upload_playlist.return_value = True

        # Tracks get azuracast_file_id set during upload
        def set_file_ids(tracks):
            for idx, track in enumerate(tracks):
                track["azuracast_file_id"] = f"file_{idx + 1}"
            return True

        mock_client.upload_playlist.side_effect = set_file_ids

        # Add to playlist succeeds
        mock_client.add_to_playlist.return_value = True

        # Execute sync
        result = await sync_playlist_to_azuracast(sample_playlist)

        # Verify playlist creation
        mock_client.get_playlist.assert_called_once_with("Monday_TestShow_0600_1000")
        mock_client.create_playlist.assert_called_once_with("Monday_TestShow_0600_1000")
        mock_client.empty_playlist.assert_not_called()

        # Verify sync metadata set
        assert result.synced_at is not None
        assert result.azuracast_id == 123
        assert (datetime.now() - result.synced_at).total_seconds() < 5

    @pytest.mark.asyncio
    @patch.dict(
        "os.environ",
        {
            "AZURACAST_HOST": "https://test.azuracast.com",
            "AZURACAST_API_KEY": "test_api_key",
            "AZURACAST_STATIONID": "1",
        },
    )
    @patch("src.ai_playlist.azuracast_sync.AzuraCastSync")
    async def test_sync_existing_playlist_updates_tracks(
        self, mock_azuracast_class, sample_playlist
    ):
        """Test syncing an existing playlist empties and updates it (FR-005)."""
        # Setup mock client
        mock_client = Mock()
        mock_azuracast_class.return_value = mock_client

        # Playlist exists
        mock_client.get_playlist.return_value = {
            "id": 456,
            "name": "Monday_TestShow_0600_1000",
        }

        # Empty playlist succeeds
        mock_client.empty_playlist.return_value = True

        # Upload succeeds with file IDs
        def set_file_ids(tracks):
            for idx, track in enumerate(tracks):
                track["azuracast_file_id"] = f"file_{idx + 1}"
            return True

        mock_client.upload_playlist.side_effect = set_file_ids

        # Add to playlist succeeds
        mock_client.add_to_playlist.return_value = True

        # Execute sync
        result = await sync_playlist_to_azuracast(sample_playlist)

        # Verify update flow (FR-005)
        mock_client.get_playlist.assert_called_once_with("Monday_TestShow_0600_1000")
        mock_client.empty_playlist.assert_called_once_with(456)
        mock_client.create_playlist.assert_not_called()

        # Verify tracks added
        assert mock_client.add_to_playlist.call_count == 2

        # Verify sync metadata
        assert result.synced_at is not None
        assert result.azuracast_id == 456

    @pytest.mark.asyncio
    @patch.dict(
        "os.environ",
        {
            "AZURACAST_HOST": "https://test.azuracast.com",
            "AZURACAST_API_KEY": "test_api_key",
            "AZURACAST_STATIONID": "1",
        },
    )
    @patch("src.ai_playlist.azuracast_sync.AzuraCastSync")
    async def test_sync_missing_env_vars_raises_error(
        self, mock_azuracast_class, sample_playlist
    ):
        """Test sync fails with clear error when environment variables missing."""
        # Clear environment
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(
                AzuraCastPlaylistSyncError,
                match="Missing required environment variables: "
                "AZURACAST_HOST, AZURACAST_API_KEY, AZURACAST_STATIONID",
            ):
                await sync_playlist_to_azuracast(sample_playlist)

    @pytest.mark.asyncio
    @patch.dict(
        "os.environ",
        {
            "AZURACAST_HOST": "https://test.azuracast.com",
            "AZURACAST_API_KEY": "test_api_key",
            "AZURACAST_STATIONID": "1",
        },
    )
    @patch("src.ai_playlist.azuracast_sync.AzuraCastSync")
    async def test_sync_playlist_creation_failure_raises_error(
        self, mock_azuracast_class, sample_playlist
    ):
        """Test sync fails when playlist creation fails."""
        # Setup mock client
        mock_client = Mock()
        mock_azuracast_class.return_value = mock_client

        # Playlist does not exist
        mock_client.get_playlist.return_value = None

        # Create playlist fails
        mock_client.create_playlist.return_value = None

        # Execute sync and expect error
        with pytest.raises(
            AzuraCastPlaylistSyncError,
            match="Failed to create playlist 'Monday_TestShow_0600_1000'",
        ):
            await sync_playlist_to_azuracast(sample_playlist)

    @pytest.mark.asyncio
    @patch.dict(
        "os.environ",
        {
            "AZURACAST_HOST": "https://test.azuracast.com",
            "AZURACAST_API_KEY": "test_api_key",
            "AZURACAST_STATIONID": "1",
        },
    )
    @patch("src.ai_playlist.azuracast_sync.AzuraCastSync")
    async def test_sync_empty_playlist_failure_raises_error(
        self, mock_azuracast_class, sample_playlist
    ):
        """Test sync fails when emptying existing playlist fails."""
        # Setup mock client
        mock_client = Mock()
        mock_azuracast_class.return_value = mock_client

        # Playlist exists
        mock_client.get_playlist.return_value = {
            "id": 789,
            "name": "Monday_TestShow_0600_1000",
        }

        # Empty playlist fails
        mock_client.empty_playlist.return_value = False

        # Execute sync and expect error
        with pytest.raises(
            AzuraCastPlaylistSyncError,
            match="Failed to empty existing playlist 'Monday_TestShow_0600_1000' \\(ID: 789\\)",
        ):
            await sync_playlist_to_azuracast(sample_playlist)

    @pytest.mark.asyncio
    @patch.dict(
        "os.environ",
        {
            "AZURACAST_HOST": "https://test.azuracast.com",
            "AZURACAST_API_KEY": "test_api_key",
            "AZURACAST_STATIONID": "1",
        },
    )
    @patch("src.ai_playlist.azuracast_sync.AzuraCastSync")
    async def test_sync_upload_failure_raises_error(
        self, mock_azuracast_class, sample_playlist
    ):
        """Test sync fails when track upload fails."""
        # Setup mock client
        mock_client = Mock()
        mock_azuracast_class.return_value = mock_client

        # Playlist exists
        mock_client.get_playlist.return_value = {
            "id": 999,
            "name": "Monday_TestShow_0600_1000",
        }

        # Empty succeeds
        mock_client.empty_playlist.return_value = True

        # Upload fails
        mock_client.upload_playlist.return_value = False

        # Execute sync and expect error
        with pytest.raises(
            AzuraCastPlaylistSyncError,
            match="Failed to upload tracks for playlist 'Monday_TestShow_0600_1000'",
        ):
            await sync_playlist_to_azuracast(sample_playlist)


class TestConvertSelectedTracksToDict:
    """Test suite for SelectedTrack to dict conversion."""

    def test_convert_tracks_maps_fields_correctly(self):
        """Test track conversion maps all fields correctly."""
        tracks = [
            SelectedTrack(
                track_id="track1",
                title="Test Song",
                artist="Test Artist",
                album="Test Album",
                bpm=120,
                genre="Alternative",
                year=2023,
                country="AU",
                duration_seconds=180,
                position=1,
                selection_reason="Test",
            )
        ]

        result = _convert_selected_tracks_to_dict(tracks)

        assert len(result) == 1
        track_dict = result[0]

        # Verify field mapping
        assert track_dict["Id"] == "track1"
        assert track_dict["Name"] == "Test Song"
        assert track_dict["AlbumArtist"] == "Test Artist"
        assert track_dict["Album"] == "Test Album"
        assert track_dict["ProductionYear"] == 2023
        assert track_dict["IndexNumber"] == 1

        # Verify duplicate detection fields
        assert track_dict["artist"] == "Test Artist"
        assert track_dict["album"] == "Test Album"
        assert track_dict["title"] == "Test Song"

    def test_convert_tracks_handles_missing_year(self):
        """Test conversion handles None year gracefully."""
        tracks = [
            SelectedTrack(
                track_id="track1",
                title="Test Song",
                artist="Test Artist",
                album="Test Album",
                bpm=None,
                genre=None,
                year=None,  # Missing year
                country=None,
                duration_seconds=180,
                position=1,
                selection_reason="Test",
            )
        ]

        result = _convert_selected_tracks_to_dict(tracks)

        assert result[0]["ProductionYear"] == "Unknown Year"

    def test_convert_empty_list_returns_empty(self):
        """Test conversion of empty list returns empty list."""
        result = _convert_selected_tracks_to_dict([])
        assert result == []

    def test_convert_multiple_tracks_preserves_order(self):
        """Test conversion preserves track order."""
        tracks = [
            SelectedTrack(
                track_id=f"track{i}",
                title=f"Song {i}",
                artist="Artist",
                album="Album",
                bpm=120,
                genre="Rock",
                year=2023,
                country="AU",
                duration_seconds=180,
                position=i,
                selection_reason="Test",
            )
            for i in range(1, 6)
        ]

        result = _convert_selected_tracks_to_dict(tracks)

        assert len(result) == 5
        for i, track_dict in enumerate(result, start=1):
            assert track_dict["Name"] == f"Song {i}"
            assert track_dict["IndexNumber"] == i
