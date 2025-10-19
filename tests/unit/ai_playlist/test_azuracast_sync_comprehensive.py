"""Comprehensive tests for azuracast_sync.py - AzuraCast playlist synchronization.

Tests cover:
- SubsonicTrack initialization and methods (lines 33-35, 46-59, 63)
- Environment variable validation (lines 94-125)
- Playlist sync workflow (lines 127-227)
- Track conversion (lines 245-269)
- Error handling and edge cases
- AzuraCast API interactions

Target coverage: >60% (currently 17.59%)
"""
import pytest
import os
from datetime import datetime
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock, AsyncMock, PropertyMock
from typing import Dict, Any
import uuid

from src.ai_playlist.azuracast_sync import (
    SubsonicTrack,
    AzuraCastPlaylistSyncError,
    sync_playlist_to_azuracast,
    _convert_selected_tracks_to_subsonic_tracks,
)
from src.ai_playlist.models import Playlist, SelectedTrack, ValidationStatus
from src.subsonic.client import SubsonicClient
from src.subsonic.models import SubsonicConfig


@pytest.fixture
def mock_subsonic_client():
    """Create a mock Subsonic client."""
    client = Mock(spec=SubsonicClient)
    client.download_track = Mock(return_value=b"fake_audio_data")
    return client


@pytest.fixture
def sample_track_data() -> Dict[str, Any]:
    """Create sample track data dictionary."""
    return {
        "Id": "track-123",
        "Name": "Test Song",
        "AlbumArtist": "Test Artist",
        "Album": "Test Album",
        "ProductionYear": 2023,
        "Path": "/music/test/path.mp3",
        "ParentIndexNumber": 1,
        "IndexNumber": 5,
    }


@pytest.fixture
def selected_tracks() -> list:
    """Create sample SelectedTrack objects."""
    return [
        SelectedTrack(
            track_id="track-1",
            title="Song One",
            artist="Artist One",
            album="Album One",
            duration_seconds=180,
            is_australian=True,
            rotation_category="Power",
            position_in_playlist=0,
            selection_reasoning="Great energy",
            validation_status=ValidationStatus.PASS,
            metadata_source="subsonic",
            bpm=120,
            genre="Rock",
            year=2023,
            country="AU",
        ),
        SelectedTrack(
            track_id="track-2",
            title="Song Two",
            artist="Artist Two",
            album="Album Two",
            duration_seconds=200,
            is_australian=False,
            rotation_category="Regular",
            position_in_playlist=1,
            selection_reasoning="Good flow",
            validation_status=ValidationStatus.PASS,
            metadata_source="subsonic",
            bpm=110,
            genre="Pop",
            year=None,  # Test missing year
            country="US",
        ),
    ]


@pytest.fixture
def test_playlist(selected_tracks) -> Playlist:
    """Create a test Playlist object."""
    return Playlist(
        id=str(uuid.uuid4()),
        name="Test Playlist",
        specification_id=str(uuid.uuid4()),
        tracks=selected_tracks,
        validation_result=None,
        created_at=datetime.now(),
        cost_actual=Decimal("0.50"),
        generation_time_seconds=2.5,
    )


@pytest.fixture
def mock_env_vars():
    """Provide mock environment variables."""
    return {
        "AZURACAST_HOST": "https://test.azuracast.com",
        "AZURACAST_API_KEY": "test-api-key",
        "AZURACAST_STATIONID": "1",
        "SUBSONIC_URL": "https://test.subsonic.com",
        "SUBSONIC_USER": "testuser",
        "SUBSONIC_PASSWORD": "testpass",
    }


class TestSubsonicTrack:
    """Test SubsonicTrack class initialization and methods."""

    def test_init_stores_track_data_and_client(
        self, sample_track_data, mock_subsonic_client
    ):
        """Test SubsonicTrack initialization (lines 33-35)."""
        # Act
        track = SubsonicTrack(sample_track_data, mock_subsonic_client)

        # Assert
        assert track["Id"] == "track-123"
        assert track["Name"] == "Test Song"
        assert track._subsonic_client is mock_subsonic_client
        assert track._content is None

    def test_download_calls_subsonic_client(
        self, sample_track_data, mock_subsonic_client
    ):
        """Test download() method calls Subsonic client (lines 46-59)."""
        # Arrange
        track = SubsonicTrack(sample_track_data, mock_subsonic_client)
        mock_subsonic_client.download_track.return_value = b"audio_content"

        # Act
        result = track.download()

        # Assert
        assert result == b"audio_content"
        mock_subsonic_client.download_track.assert_called_once_with("track-123")
        assert track._content == b"audio_content"

    def test_download_caches_content(self, sample_track_data, mock_subsonic_client):
        """Test download() caches content and doesn't re-download (line 46-47)."""
        # Arrange
        track = SubsonicTrack(sample_track_data, mock_subsonic_client)
        mock_subsonic_client.download_track.return_value = b"audio_content"

        # Act
        result1 = track.download()
        result2 = track.download()

        # Assert
        assert result1 == result2
        mock_subsonic_client.download_track.assert_called_once()  # Only once

    def test_download_raises_on_missing_track_id(self, mock_subsonic_client):
        """Test download() raises ValueError when track ID is missing (lines 50-51)."""
        # Arrange
        track_data = {"Name": "No ID Song"}
        track = SubsonicTrack(track_data, mock_subsonic_client)

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            track.download()

        assert "Track ID missing" in str(exc_info.value)
        assert "No ID Song" in str(exc_info.value)

    def test_download_propagates_client_exception(
        self, sample_track_data, mock_subsonic_client
    ):
        """Test download() propagates exceptions from Subsonic client (lines 57-59)."""
        # Arrange
        track = SubsonicTrack(sample_track_data, mock_subsonic_client)
        mock_subsonic_client.download_track.side_effect = ConnectionError(
            "Network error"
        )

        # Act & Assert
        with pytest.raises(ConnectionError) as exc_info:
            track.download()

        assert "Network error" in str(exc_info.value)

    def test_clear_content_clears_cache(self, sample_track_data, mock_subsonic_client):
        """Test clear_content() clears cached audio data (line 63)."""
        # Arrange
        track = SubsonicTrack(sample_track_data, mock_subsonic_client)
        track.download()  # Cache content
        assert track._content is not None

        # Act
        track.clear_content()

        # Assert
        assert track._content is None


class TestSyncPlaylistEnvironmentValidation:
    """Test environment variable validation in sync_playlist_to_azuracast."""

    @pytest.mark.asyncio
    async def test_missing_azuracast_host_raises_error(self, test_playlist):
        """Test missing AZURACAST_HOST raises error (lines 94-108)."""
        # Arrange
        env = {
            "AZURACAST_API_KEY": "key",
            "AZURACAST_STATIONID": "1",
            "SUBSONIC_URL": "url",
            "SUBSONIC_USER": "user",
            "SUBSONIC_PASSWORD": "pass",
        }

        # Act & Assert
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(AzuraCastPlaylistSyncError) as exc_info:
                await sync_playlist_to_azuracast(test_playlist)

            assert "AZURACAST_HOST" in str(exc_info.value)
            assert "Missing required environment variables" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_missing_azuracast_api_key_raises_error(self, test_playlist):
        """Test missing AZURACAST_API_KEY raises error (lines 94-108)."""
        # Arrange
        env = {
            "AZURACAST_HOST": "host",
            "AZURACAST_STATIONID": "1",
            "SUBSONIC_URL": "url",
            "SUBSONIC_USER": "user",
            "SUBSONIC_PASSWORD": "pass",
        }

        # Act & Assert
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(AzuraCastPlaylistSyncError) as exc_info:
                await sync_playlist_to_azuracast(test_playlist)

            assert "AZURACAST_API_KEY" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_missing_azuracast_station_id_raises_error(self, test_playlist):
        """Test missing AZURACAST_STATIONID raises error (lines 94-108)."""
        # Arrange
        env = {
            "AZURACAST_HOST": "host",
            "AZURACAST_API_KEY": "key",
            "SUBSONIC_URL": "url",
            "SUBSONIC_USER": "user",
            "SUBSONIC_PASSWORD": "pass",
        }

        # Act & Assert
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(AzuraCastPlaylistSyncError) as exc_info:
                await sync_playlist_to_azuracast(test_playlist)

            assert "AZURACAST_STATIONID" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_missing_subsonic_url_raises_error(self, test_playlist):
        """Test missing SUBSONIC_URL raises error (lines 110-125)."""
        # Arrange
        env = {
            "AZURACAST_HOST": "host",
            "AZURACAST_API_KEY": "key",
            "AZURACAST_STATIONID": "1",
            "SUBSONIC_USER": "user",
            "SUBSONIC_PASSWORD": "pass",
        }

        # Act & Assert
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(AzuraCastPlaylistSyncError) as exc_info:
                await sync_playlist_to_azuracast(test_playlist)

            assert "SUBSONIC_URL" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_missing_subsonic_user_raises_error(self, test_playlist):
        """Test missing SUBSONIC_USER raises error (lines 110-125)."""
        # Arrange
        env = {
            "AZURACAST_HOST": "host",
            "AZURACAST_API_KEY": "key",
            "AZURACAST_STATIONID": "1",
            "SUBSONIC_URL": "url",
            "SUBSONIC_PASSWORD": "pass",
        }

        # Act & Assert
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(AzuraCastPlaylistSyncError) as exc_info:
                await sync_playlist_to_azuracast(test_playlist)

            assert "SUBSONIC_USER" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_missing_subsonic_password_raises_error(self, test_playlist):
        """Test missing SUBSONIC_PASSWORD raises error (lines 110-125)."""
        # Arrange
        env = {
            "AZURACAST_HOST": "host",
            "AZURACAST_API_KEY": "key",
            "AZURACAST_STATIONID": "1",
            "SUBSONIC_URL": "url",
            "SUBSONIC_USER": "user",
        }

        # Act & Assert
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(AzuraCastPlaylistSyncError) as exc_info:
                await sync_playlist_to_azuracast(test_playlist)

            assert "SUBSONIC_PASSWORD" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_missing_multiple_variables_lists_all(self, test_playlist):
        """Test multiple missing variables are all listed (lines 99-108)."""
        # Arrange
        env = {"SUBSONIC_URL": "url"}  # Missing most vars

        # Act & Assert
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(AzuraCastPlaylistSyncError) as exc_info:
                await sync_playlist_to_azuracast(test_playlist)

            error_msg = str(exc_info.value)
            assert "AZURACAST_HOST" in error_msg
            assert "AZURACAST_API_KEY" in error_msg
            assert "AZURACAST_STATIONID" in error_msg


class TestSyncPlaylistWorkflow:
    """Test main sync_playlist_to_azuracast workflow."""

    @pytest.mark.asyncio
    async def test_sync_creates_new_playlist_when_not_exists(
        self, test_playlist, mock_env_vars
    ):
        """Test creating new playlist when it doesn't exist (lines 159-167)."""
        # Arrange
        with patch.dict(os.environ, mock_env_vars, clear=True):
            with patch("src.ai_playlist.azuracast_sync.AzuraCastSync") as MockAzura:
                with patch("src.ai_playlist.azuracast_sync.SubsonicClient"):
                    mock_client = MockAzura.return_value
                    mock_client.get_playlist.return_value = None  # Doesn't exist
                    mock_client.create_playlist.return_value = {"id": "new-123"}
                    mock_client.upload_playlist.return_value = True
                    mock_client.add_to_playlist.return_value = True

                    # Act
                    result = await sync_playlist_to_azuracast(test_playlist)

                    # Assert
                    mock_client.get_playlist.assert_called_once_with("Test Playlist")
                    mock_client.create_playlist.assert_called_once_with("Test Playlist")
                    assert result.azuracast_id == "new-123"
                    assert result.synced_at is not None

    @pytest.mark.asyncio
    async def test_sync_updates_existing_playlist(self, test_playlist, mock_env_vars):
        """Test updating existing playlist (lines 147-158)."""
        # Arrange
        with patch.dict(os.environ, mock_env_vars, clear=True):
            with patch("src.ai_playlist.azuracast_sync.AzuraCastSync") as MockAzura:
                with patch("src.ai_playlist.azuracast_sync.SubsonicClient"):
                    mock_client = MockAzura.return_value
                    mock_client.get_playlist.return_value = {
                        "id": "existing-456",
                        "name": "Test Playlist",
                    }
                    mock_client.empty_playlist.return_value = True
                    mock_client.upload_playlist.return_value = True
                    mock_client.add_to_playlist.return_value = True

                    # Act
                    result = await sync_playlist_to_azuracast(test_playlist)

                    # Assert
                    mock_client.get_playlist.assert_called_once()
                    mock_client.empty_playlist.assert_called_once_with("existing-456")
                    assert result.azuracast_id == "existing-456"

    @pytest.mark.asyncio
    async def test_sync_raises_error_when_empty_playlist_fails(
        self, test_playlist, mock_env_vars
    ):
        """Test error when emptying existing playlist fails (lines 154-157)."""
        # Arrange
        with patch.dict(os.environ, mock_env_vars, clear=True):
            with patch("src.ai_playlist.azuracast_sync.AzuraCastSync") as MockAzura:
                with patch("src.ai_playlist.azuracast_sync.SubsonicClient"):
                    mock_client = MockAzura.return_value
                    mock_client.get_playlist.return_value = {"id": "fail-789"}
                    mock_client.empty_playlist.return_value = False  # Fails

                    # Act & Assert
                    with pytest.raises(AzuraCastPlaylistSyncError) as exc_info:
                        await sync_playlist_to_azuracast(test_playlist)

                    assert "Failed to empty existing playlist" in str(exc_info.value)
                    assert "fail-789" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_sync_raises_error_when_create_playlist_fails(
        self, test_playlist, mock_env_vars
    ):
        """Test error when creating playlist fails (lines 163-164)."""
        # Arrange
        with patch.dict(os.environ, mock_env_vars, clear=True):
            with patch("src.ai_playlist.azuracast_sync.AzuraCastSync") as MockAzura:
                with patch("src.ai_playlist.azuracast_sync.SubsonicClient"):
                    mock_client = MockAzura.return_value
                    mock_client.get_playlist.return_value = None
                    mock_client.create_playlist.return_value = None  # Fails

                    # Act & Assert
                    with pytest.raises(AzuraCastPlaylistSyncError) as exc_info:
                        await sync_playlist_to_azuracast(test_playlist)

                    assert "Failed to create playlist" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_sync_raises_error_when_upload_fails(
        self, test_playlist, mock_env_vars
    ):
        """Test error when upload_playlist fails (lines 177-180)."""
        # Arrange
        with patch.dict(os.environ, mock_env_vars, clear=True):
            with patch("src.ai_playlist.azuracast_sync.AzuraCastSync") as MockAzura:
                with patch("src.ai_playlist.azuracast_sync.SubsonicClient"):
                    mock_client = MockAzura.return_value
                    mock_client.get_playlist.return_value = None
                    mock_client.create_playlist.return_value = {"id": "upload-fail"}
                    mock_client.upload_playlist.return_value = False  # Upload fails

                    # Act & Assert
                    with pytest.raises(AzuraCastPlaylistSyncError) as exc_info:
                        await sync_playlist_to_azuracast(test_playlist)

                    assert "Failed to upload tracks" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_sync_adds_tracks_to_playlist(self, test_playlist, mock_env_vars):
        """Test adding tracks to playlist (lines 183-204)."""
        # Arrange
        with patch.dict(os.environ, mock_env_vars, clear=True):
            with patch("src.ai_playlist.azuracast_sync.AzuraCastSync") as MockAzura:
                with patch(
                    "src.ai_playlist.azuracast_sync._convert_selected_tracks_to_subsonic_tracks"
                ) as mock_convert:
                    with patch("src.ai_playlist.azuracast_sync.SubsonicClient"):
                        mock_client = MockAzura.return_value
                        mock_client.get_playlist.return_value = None
                        mock_client.create_playlist.return_value = {"id": "add-tracks"}
                        mock_client.upload_playlist.return_value = True
                        mock_client.add_to_playlist.return_value = True

                        # Mock converted tracks with azuracast_file_id
                        mock_track1 = {"Name": "Track 1", "azuracast_file_id": "file-1"}
                        mock_track2 = {"Name": "Track 2", "azuracast_file_id": "file-2"}
                        mock_convert.return_value = [mock_track1, mock_track2]

                        # Act
                        result = await sync_playlist_to_azuracast(test_playlist)

                        # Assert
                        assert mock_client.add_to_playlist.call_count == 2
                        mock_client.add_to_playlist.assert_any_call("file-1", "add-tracks")
                        mock_client.add_to_playlist.assert_any_call("file-2", "add-tracks")

    @pytest.mark.asyncio
    async def test_sync_skips_tracks_without_azuracast_file_id(
        self, test_playlist, mock_env_vars
    ):
        """Test skipping tracks without azuracast_file_id (lines 189-195)."""
        # Arrange
        with patch.dict(os.environ, mock_env_vars, clear=True):
            with patch("src.ai_playlist.azuracast_sync.AzuraCastSync") as MockAzura:
                with patch(
                    "src.ai_playlist.azuracast_sync._convert_selected_tracks_to_subsonic_tracks"
                ) as mock_convert:
                    with patch("src.ai_playlist.azuracast_sync.SubsonicClient"):
                        mock_client = MockAzura.return_value
                        mock_client.get_playlist.return_value = None
                        mock_client.create_playlist.return_value = {"id": "skip-test"}
                        mock_client.upload_playlist.return_value = True

                        # Mock track without azuracast_file_id
                        mock_track = {"Name": "No ID Track"}
                        mock_convert.return_value = [mock_track]

                        # Act
                        result = await sync_playlist_to_azuracast(test_playlist)

                        # Assert
                        mock_client.add_to_playlist.assert_not_called()

    @pytest.mark.asyncio
    async def test_sync_handles_add_to_playlist_failure(
        self, test_playlist, mock_env_vars
    ):
        """Test handling add_to_playlist failures (lines 197-204)."""
        # Arrange
        with patch.dict(os.environ, mock_env_vars, clear=True):
            with patch("src.ai_playlist.azuracast_sync.AzuraCastSync") as MockAzura:
                with patch(
                    "src.ai_playlist.azuracast_sync._convert_selected_tracks_to_subsonic_tracks"
                ) as mock_convert:
                    with patch("src.ai_playlist.azuracast_sync.SubsonicClient"):
                        mock_client = MockAzura.return_value
                        mock_client.get_playlist.return_value = None
                        mock_client.create_playlist.return_value = {"id": "fail-add"}
                        mock_client.upload_playlist.return_value = True
                        mock_client.add_to_playlist.return_value = False  # Fails

                        mock_track = {"Name": "Fail Track", "azuracast_file_id": "fail"}
                        mock_convert.return_value = [mock_track]

                        # Act
                        result = await sync_playlist_to_azuracast(test_playlist)

                        # Assert - sync completes but logs warning
                        assert result.azuracast_id == "fail-add"

    @pytest.mark.asyncio
    async def test_sync_sets_metadata_on_success(self, test_playlist, mock_env_vars):
        """Test synced_at and azuracast_id are set on success (lines 211-218)."""
        # Arrange
        with patch.dict(os.environ, mock_env_vars, clear=True):
            with patch("src.ai_playlist.azuracast_sync.AzuraCastSync") as MockAzura:
                with patch("src.ai_playlist.azuracast_sync.SubsonicClient"):
                    mock_client = MockAzura.return_value
                    mock_client.get_playlist.return_value = None
                    mock_client.create_playlist.return_value = {"id": "success-999"}
                    mock_client.upload_playlist.return_value = True
                    mock_client.add_to_playlist.return_value = True

                    # Act
                    result = await sync_playlist_to_azuracast(test_playlist)

                    # Assert
                    assert hasattr(result, 'synced_at')
                    assert result.synced_at is not None
                    assert hasattr(result, 'azuracast_id')
                    assert result.azuracast_id == "success-999"
                    assert isinstance(result.synced_at, datetime)

    @pytest.mark.asyncio
    async def test_sync_catches_and_wraps_exceptions(
        self, test_playlist, mock_env_vars
    ):
        """Test exception handling wraps errors (lines 222-226)."""
        # Arrange
        with patch.dict(os.environ, mock_env_vars, clear=True):
            with patch("src.ai_playlist.azuracast_sync.AzuraCastSync") as MockAzura:
                with patch("src.ai_playlist.azuracast_sync.SubsonicClient"):
                    mock_client = MockAzura.return_value
                    mock_client.get_playlist.side_effect = ConnectionError(
                        "Network failed"
                    )

                    # Act & Assert
                    with pytest.raises(AzuraCastPlaylistSyncError) as exc_info:
                        await sync_playlist_to_azuracast(test_playlist)

                    assert "Failed to sync playlist" in str(exc_info.value)
                    assert "Test Playlist" in str(exc_info.value)


class TestConvertSelectedTracksToSubsonicTracks:
    """Test _convert_selected_tracks_to_subsonic_tracks function."""

    def test_converts_tracks_correctly(self, selected_tracks, mock_subsonic_client):
        """Test conversion creates SubsonicTrack objects (lines 245-269)."""
        # Act
        result = _convert_selected_tracks_to_subsonic_tracks(
            selected_tracks, mock_subsonic_client
        )

        # Assert
        assert len(result) == 2
        assert all(isinstance(track, SubsonicTrack) for track in result)

    def test_maps_selected_track_fields_to_dict(
        self, selected_tracks, mock_subsonic_client
    ):
        """Test field mapping from SelectedTrack to dict (lines 249-262)."""
        # Act
        result = _convert_selected_tracks_to_subsonic_tracks(
            selected_tracks, mock_subsonic_client
        )

        # Assert - Check first track
        track1 = result[0]
        assert track1["Id"] == "track-1"
        assert track1["Name"] == "Song One"
        assert track1["AlbumArtist"] == "Artist One"
        assert track1["Album"] == "Album One"
        assert track1["ProductionYear"] == 2023
        assert track1["IndexNumber"] == 0
        assert track1["artist"] == "Artist One"
        assert track1["album"] == "Album One"
        assert track1["title"] == "Song One"

    def test_handles_missing_year_field(self, selected_tracks, mock_subsonic_client):
        """Test handling of None year value (line 254)."""
        # Act
        result = _convert_selected_tracks_to_subsonic_tracks(
            selected_tracks, mock_subsonic_client
        )

        # Assert - Second track has year=None
        track2 = result[1]
        assert track2["ProductionYear"] == "Unknown Year"

    def test_assigns_subsonic_client_to_tracks(
        self, selected_tracks, mock_subsonic_client
    ):
        """Test SubsonicTrack objects have client reference (line 265)."""
        # Act
        result = _convert_selected_tracks_to_subsonic_tracks(
            selected_tracks, mock_subsonic_client
        )

        # Assert
        for track in result:
            assert track._subsonic_client is mock_subsonic_client

    def test_conversion_with_empty_list(self, mock_subsonic_client):
        """Test conversion with empty track list."""
        # Act
        result = _convert_selected_tracks_to_subsonic_tracks([], mock_subsonic_client)

        # Assert
        assert result == []

    def test_conversion_preserves_position_in_playlist(
        self, selected_tracks, mock_subsonic_client
    ):
        """Test position_in_playlist maps to IndexNumber (line 257)."""
        # Act
        result = _convert_selected_tracks_to_subsonic_tracks(
            selected_tracks, mock_subsonic_client
        )

        # Assert
        assert result[0]["IndexNumber"] == 0
        assert result[1]["IndexNumber"] == 1


class TestIntegrationScenarios:
    """Integration tests for complete sync scenarios."""

    @pytest.mark.asyncio
    async def test_complete_sync_workflow_new_playlist(
        self, test_playlist, mock_env_vars
    ):
        """Test complete workflow: create playlist, upload, add tracks."""
        # Arrange
        with patch.dict(os.environ, mock_env_vars, clear=True):
            with patch("src.ai_playlist.azuracast_sync.AzuraCastSync") as MockAzura:
                with patch("src.ai_playlist.azuracast_sync.SubsonicClient"):
                    mock_client = MockAzura.return_value
                    mock_client.get_playlist.return_value = None
                    mock_client.create_playlist.return_value = {"id": "integration-1"}
                    mock_client.upload_playlist.return_value = True
                    mock_client.add_to_playlist.return_value = True

                    # Mock track conversion
                    with patch(
                        "src.ai_playlist.azuracast_sync._convert_selected_tracks_to_subsonic_tracks"
                    ) as mock_convert:
                        mock_convert.return_value = [
                            {"azuracast_file_id": "f1"},
                            {"azuracast_file_id": "f2"},
                        ]

                        # Act
                        result = await sync_playlist_to_azuracast(test_playlist)

                        # Assert - Verify all steps executed
                        mock_client.get_playlist.assert_called_once()
                        mock_client.create_playlist.assert_called_once()
                        mock_client.upload_playlist.assert_called_once()
                        assert mock_client.add_to_playlist.call_count == 2
                        assert result.azuracast_id == "integration-1"
                        assert result.synced_at is not None

    @pytest.mark.asyncio
    async def test_complete_sync_workflow_update_existing(
        self, test_playlist, mock_env_vars
    ):
        """Test complete workflow: update existing playlist."""
        # Arrange
        with patch.dict(os.environ, mock_env_vars, clear=True):
            with patch("src.ai_playlist.azuracast_sync.AzuraCastSync") as MockAzura:
                with patch("src.ai_playlist.azuracast_sync.SubsonicClient"):
                    mock_client = MockAzura.return_value
                    mock_client.get_playlist.return_value = {"id": "existing-update"}
                    mock_client.empty_playlist.return_value = True
                    mock_client.upload_playlist.return_value = True
                    mock_client.add_to_playlist.return_value = True

                    with patch(
                        "src.ai_playlist.azuracast_sync._convert_selected_tracks_to_subsonic_tracks"
                    ) as mock_convert:
                        mock_convert.return_value = [{"azuracast_file_id": "upd-1"}]

                        # Act
                        result = await sync_playlist_to_azuracast(test_playlist)

                        # Assert
                        mock_client.empty_playlist.assert_called_once()
                        assert result.azuracast_id == "existing-update"
