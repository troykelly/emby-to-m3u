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

from datetime import time as time_obj

from src.ai_playlist.models import (
    Playlist,
    PlaylistSpec,
    DaypartSpec,
    TrackSelectionCriteria,
    SelectedTrack,
    ValidationResult,
    ValidationStatus,
    ConstraintScore,
    FlowQualityMetrics,
    ScheduleType,
    BPMRange,
    GenreCriteria,
    EraCriteria,
)
from src.ai_playlist.azuracast_sync import sync_playlist_to_azuracast


@pytest.fixture
def sample_daypart():
    """Create sample daypart specification."""
    return DaypartSpec(
        id="daypart-test-002",
        name="Morning Drive",
        schedule_type=ScheduleType.WEEKDAY,
        time_start=time_obj(6, 0),
        time_end=time_obj(10, 0),
        duration_hours=4.0,
        target_demographic="General audience",
        bpm_progression=[
            BPMRange(time_start=time_obj(6, 0), time_end=time_obj(8, 0), bpm_min=100, bpm_max=120),
            BPMRange(time_start=time_obj(8, 0), time_end=time_obj(10, 0), bpm_min=120, bpm_max=130),
        ],
        genre_mix={"Electronic": 0.50, "Pop": 0.30, "Rock": 0.20},
        era_distribution={"Current": 0.40, "Recent": 0.40, "Modern Classics": 0.20},
        mood_guidelines=["Energetic morning vibes"],
        content_focus="Morning Drive Programming",
        rotation_percentages={"Power": 0.30, "Medium": 0.40, "Light": 0.30},
        tracks_per_hour=(10, 14),
    )


@pytest.fixture
def sample_criteria():
    """Create sample track selection criteria."""
    return TrackSelectionCriteria(
        bpm_ranges=[
            BPMRange(time_start=time_obj(6, 0), time_end=time_obj(10, 0), bpm_min=100, bpm_max=130)
        ],
        genre_mix={
            "Electronic": GenreCriteria(target_percentage=0.50, tolerance=0.10),
            "Pop": GenreCriteria(target_percentage=0.30, tolerance=0.10),
            "Rock": GenreCriteria(target_percentage=0.20, tolerance=0.10),
        },
        era_distribution={
            "Current": EraCriteria("Current", 2023, 2025, 0.40, 0.10),
            "Recent": EraCriteria("Recent", 2018, 2022, 0.40, 0.10),
            "Modern Classics": EraCriteria("Modern Classics", 2010, 2017, 0.20, 0.10),
        },
        australian_content_min=0.30,
        energy_flow_requirements=["Build energy gradually from 100 to 130 BPM"],
        rotation_distribution={"Power": 0.30, "Medium": 0.40, "Light": 0.30},
        no_repeat_window_hours=4.0,
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
            is_australian=(i % 3 == 0),
            rotation_category=["Power", "Medium", "Light"][i % 3],
            position_in_playlist=i,
            selection_reasoning=f"Track {i} selected for energy progression",
            validation_status=ValidationStatus.PASS,
            metadata_source="test_fixture",
        )
        for i in range(12)
    ]


@pytest.fixture
def sample_validation_result():
    """Create sample validation result that passes."""
    # Create constraint scores
    constraint_scores = {
        "australian_content": ConstraintScore(
            constraint_name="Australian Content",
            target_value=0.30,
            actual_value=0.33,
            tolerance=0.0,
            is_compliant=True,
            deviation_percentage=0.10,
        ),
        "genre_Electronic": ConstraintScore(
            constraint_name="Genre: Electronic",
            target_value=0.50,
            actual_value=0.50,
            tolerance=0.10,
            is_compliant=True,
            deviation_percentage=0.0,
        ),
    }

    # Create flow quality metrics
    flow_metrics = FlowQualityMetrics(
        bpm_variance=0.15,
        bpm_progression_coherence=0.90,
        energy_consistency=0.85,
        genre_diversity_index=0.75,
    )

    return ValidationResult(
        playlist_id="test-playlist-002",
        overall_status=ValidationStatus.PASS,
        constraint_scores=constraint_scores,
        flow_quality_metrics=flow_metrics,
        compliance_percentage=0.85,
        validated_at=datetime.now(),
        gap_analysis=[],
    )


@pytest.fixture
def sample_playlist(sample_daypart, sample_criteria, sample_tracks, sample_validation_result):
    """Create sample validated playlist."""
    from datetime import date
    from decimal import Decimal

    playlist_id = str(uuid.uuid4())
    spec = PlaylistSpec(
        id=playlist_id,
        name="Monday_MorningDrive_0600_1000",
        source_daypart_id=sample_daypart.id,
        generation_date=date.today(),
        target_track_count_min=40,
        target_track_count_max=56,
        track_selection_criteria=sample_criteria,
        created_at=datetime.now(),
    )

    from decimal import Decimal

    return Playlist(
        id=playlist_id,
        name=spec.name,
        specification_id=spec.id,
        tracks=sample_tracks,
        validation_result=sample_validation_result,
        created_at=datetime.now(),
        cost_actual=Decimal('0.00'),
        generation_time_seconds=0.0,
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
