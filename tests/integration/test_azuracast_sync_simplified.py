"""
Integration tests for AzuraCast playlist synchronization - Simplified Version.

Tests playlist creation, updates, and duplicate detection with mocked AzuraCast API.
All tests use mocked implementations to avoid external dependencies.
"""

import os
import pytest
import uuid
from datetime import datetime
from unittest.mock import MagicMock, patch

from src.ai_playlist.models import (
    Playlist,
    PlaylistSpec,
    DaypartSpec,
    TrackSelectionCriteria,
    SelectedTrack,
    ValidationResult,
)
from src.ai_playlist.azuracast_sync import sync_playlist_to_azuracast


@pytest.fixture
def sample_daypart():
    """Create sample daypart specification."""
    return DaypartSpec(
        name="Morning Drive",
        day="Monday",
        time_range=("06:00", "10:00"),
        bpm_progression={"06:00-08:00": (100, 120), "08:00-10:00": (120, 130)},
        genre_mix={"Electronic": 0.50, "Pop": 0.30, "Rock": 0.20},
        era_distribution={"2020s": 0.40, "2010s": 0.40, "2000s": 0.20},
        australian_min=0.30,
        mood="Energetic morning vibes",
        tracks_per_hour=12,
    )


@pytest.fixture
def sample_criteria():
    """Create sample track selection criteria."""
    return TrackSelectionCriteria(
        bpm_range=(100, 130),
        bpm_tolerance=10,
        genre_mix={
            "Electronic": (0.40, 0.60),
            "Pop": (0.20, 0.40),
            "Rock": (0.10, 0.20),
        },
        genre_tolerance=0.05,
        era_distribution={
            "2020s": (0.30, 0.50),
            "2010s": (0.30, 0.40),
            "2000s": (0.10, 0.30),
        },
        era_tolerance=0.05,
        australian_min=0.30,
        energy_flow="Build energy gradually from 100 to 130 BPM",
        excluded_track_ids=[],
    )


@pytest.fixture
def sample_tracks():
    """Create sample selected tracks."""
    return [
        SelectedTrack(
            track_id=f"track-{i}",
            title=f"Test Track {i}",
            artist=f"Test Artist {i}",
            album=f"Test Album {i}",
            bpm=100 + (i * 3),
            genre=["Electronic", "Pop", "Rock"][i % 3],
            year=2020 + (i % 5),
            country="AU" if i % 3 == 0 else "US",
            duration_seconds=180 + (i * 10),
            position=i + 1,
            selection_reason=f"Track {i} selected for energy progression",
        )
        for i in range(12)
    ]


@pytest.fixture
def sample_validation_result():
    """Create sample validation result that passes."""
    return ValidationResult(
        constraint_satisfaction=0.85,
        bpm_satisfaction=0.90,
        genre_satisfaction=0.82,
        era_satisfaction=0.88,
        australian_content=0.33,
        flow_quality_score=0.78,
        bpm_variance=0.15,
        energy_progression="smooth",
        genre_diversity=0.75,
        gap_analysis={},
        passes_validation=True,
    )


@pytest.fixture
def sample_playlist(sample_daypart, sample_criteria, sample_tracks, sample_validation_result):
    """Create sample validated playlist."""
    playlist_id = str(uuid.uuid4())
    spec = PlaylistSpec(
        id=playlist_id,
        name="Monday_MorningDrive_0600_1000",
        daypart=sample_daypart,
        target_duration_minutes=240,
        track_criteria=sample_criteria,
    )

    return Playlist(
        id=playlist_id,
        name=spec.name,
        tracks=sample_tracks,
        spec=spec,
        validation_result=sample_validation_result,
        created_at=datetime.now(),
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_new_playlist_in_azuracast(sample_playlist):
    """Test creating a new playlist in AzuraCast."""
    with patch("src.ai_playlist.azuracast_sync.AzuraCastSync") as MockClient:
        mock_client = MockClient.return_value

        # Mock methods
        mock_client.get_playlist = MagicMock(return_value=None)
        mock_client.create_playlist = MagicMock(return_value={"id": 42, "name": sample_playlist.name})
        mock_client.upload_playlist = MagicMock(return_value=True)
        mock_client.add_to_playlist = MagicMock(return_value=True)

        # Sync playlist
        synced_playlist = await sync_playlist_to_azuracast(sample_playlist)

        # Validate
        assert synced_playlist.azuracast_id == 42
        assert synced_playlist.synced_at is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_update_existing_playlist(sample_playlist):
    """Test updating an existing playlist."""
    with patch("src.ai_playlist.azuracast_sync.AzuraCastSync") as MockClient:
        mock_client = MockClient.return_value

        # Mock finding existing playlist
        existing_playlist_id = 99
        mock_client.get_playlist = MagicMock(return_value={"id": existing_playlist_id, "name": sample_playlist.name})
        mock_client.empty_playlist = MagicMock(return_value=True)
        mock_client.upload_playlist = MagicMock(return_value=True)
        mock_client.add_to_playlist = MagicMock(return_value=True)

        # Sync playlist
        synced_playlist = await sync_playlist_to_azuracast(sample_playlist)

        # Validate
        assert synced_playlist.azuracast_id == existing_playlist_id
        mock_client.empty_playlist.assert_called_once_with(existing_playlist_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_verify_tracks_uploaded(sample_playlist):
    """Test verifying that tracks are uploaded correctly."""
    with patch("src.ai_playlist.azuracast_sync.AzuraCastSync") as MockClient:
        with patch("src.ai_playlist.azuracast_sync._convert_selected_tracks_to_dict") as mock_convert:
            mock_client = MockClient.return_value

            # Mock track conversion to include azuracast_file_id
            mock_convert.return_value = [
                {
                    "Id": f"track-{i}",
                    "Name": f"Test Track {i}",
                    "azuracast_file_id": f"azuracast-file-{i}",
                }
                for i in range(12)
            ]

            # Mock methods
            mock_client.get_playlist = MagicMock(return_value=None)
            mock_client.create_playlist = MagicMock(return_value={"id": 50, "name": sample_playlist.name})
            mock_client.upload_playlist = MagicMock(return_value=True)
            mock_client.add_to_playlist = MagicMock(return_value=True)

            # Sync playlist
            synced_playlist = await sync_playlist_to_azuracast(sample_playlist)

            # Validate
            assert synced_playlist.azuracast_id == 50
            assert mock_client.add_to_playlist.call_count == 12


@pytest.mark.integration
@pytest.mark.asyncio
async def test_azuracast_api_error_handling(sample_playlist):
    """Test error handling for AzuraCast API failures."""
    with patch("src.ai_playlist.azuracast_sync.AzuraCastSync") as MockClient:
        mock_client = MockClient.return_value

        # Mock API error
        mock_client.get_playlist = MagicMock(side_effect=Exception("AzuraCast API Error"))

        # Import the error class
        from src.ai_playlist.azuracast_sync import AzuraCastPlaylistSyncError

        # Should raise exception
        with pytest.raises((AzuraCastPlaylistSyncError, Exception)):
            await sync_playlist_to_azuracast(sample_playlist)
