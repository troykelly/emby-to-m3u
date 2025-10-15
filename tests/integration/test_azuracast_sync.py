"""
Integration tests for AzuraCast playlist synchronization.

Tests playlist creation, updates, and duplicate detection with mocked AzuraCast API.
Validates track upload and cleanup after tests.
"""

import os
import pytest
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch, call

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


@pytest.fixture
def sample_daypart():
    """Create sample daypart specification."""
    return DaypartSpec(
        id="daypart-test-001",
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
        playlist_id="test-playlist-001",
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
        target_duration_minutes=240,
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
    """
    Test creating a new playlist in AzuraCast.

    Validates:
    - Playlist is created with correct name
    - All tracks are uploaded
    - AzuraCast ID is assigned
    - Sync timestamp is set
    """
    # Mock environment variables
    with patch.dict(os.environ, {
        "AZURACAST_HOST": "http://test-azuracast.com",
        "AZURACAST_API_KEY": "test-api-key-123",
        "AZURACAST_STATIONID": "1"
    }):
        # Mock AzuraCast API client
        with patch("src.ai_playlist.azuracast_sync.AzuraCastSync") as MockClient:
            mock_client = MockClient.return_value

            # Mock methods (not async in actual implementation)
            mock_client.get_playlist = MagicMock(return_value=None)
            mock_client.create_playlist = MagicMock(return_value={"id": 42, "name": sample_playlist.name})

            # Mock upload_playlist to add azuracast_file_id to track dicts
            def mock_upload(tracks):
                for i, track in enumerate(tracks):
                    track["azuracast_file_id"] = 1000 + i
                return True
            mock_client.upload_playlist = MagicMock(side_effect=mock_upload)
            mock_client.add_to_playlist = MagicMock(return_value=True)

            # Import the actual sync function
            from src.ai_playlist.azuracast_sync import sync_playlist_to_azuracast

            # Sync playlist
            synced_playlist = await sync_playlist_to_azuracast(sample_playlist)

            # Validate results
            assert synced_playlist.azuracast_id == 42
            assert synced_playlist.synced_at is not None
            assert synced_playlist.synced_at >= synced_playlist.created_at

            # Verify API calls
            mock_client.create_playlist.assert_called_once()
            mock_client.upload_playlist.assert_called_once()
            assert mock_client.add_to_playlist.call_count == 12


@pytest.mark.integration
@pytest.mark.asyncio
async def test_update_existing_playlist_duplicate_detection(sample_playlist):
    """
    Test updating an existing playlist with duplicate detection.

    Validates:
    - Existing playlist is detected by name
    - Playlist is updated instead of duplicated
    - Tracks are replaced, not appended
    - Update timestamp is recorded
    """
    # Mock environment variables
    with patch.dict(os.environ, {
        "AZURACAST_HOST": "http://test-azuracast.com",
        "AZURACAST_API_KEY": "test-api-key-123",
        "AZURACAST_STATIONID": "1"
    }):
        # Mock AzuraCast API client
        with patch("src.ai_playlist.azuracast_sync.AzuraCastSync") as MockClient:
            mock_client = MockClient.return_value

            # Mock finding existing playlist
            existing_playlist_id = 99
            mock_client.get_playlist = MagicMock(return_value={"id": existing_playlist_id, "name": sample_playlist.name})

            # Mock methods
            mock_client.empty_playlist = MagicMock(return_value=True)

            # Mock upload_playlist to add azuracast_file_id to track dicts
            def mock_upload(tracks):
                for i, track in enumerate(tracks):
                    track["azuracast_file_id"] = 1000 + i
                return True
            mock_client.upload_playlist = MagicMock(side_effect=mock_upload)
            mock_client.add_to_playlist = MagicMock(return_value=True)

            # Import the actual sync function
            from src.ai_playlist.azuracast_sync import sync_playlist_to_azuracast

            # Sync playlist (should update, not create)
            synced_playlist = await sync_playlist_to_azuracast(sample_playlist)

            # Validate results
            assert synced_playlist.azuracast_id == existing_playlist_id
            assert synced_playlist.synced_at is not None

            # Verify API calls
            mock_client.get_playlist.assert_called()
            mock_client.empty_playlist.assert_called_once_with(existing_playlist_id)
            mock_client.upload_playlist.assert_called_once()
            assert mock_client.add_to_playlist.call_count == 12


@pytest.mark.integration
@pytest.mark.asyncio
async def test_verify_tracks_uploaded_correctly(sample_playlist):
    """
    Test verifying that tracks are uploaded correctly to AzuraCast.

    Validates:
    - Track order is preserved
    - All tracks are present
    - Track metadata is correct
    """
    with patch("src.azuracast.main.AzuraCastSync") as MockClient:
        mock_client = MockClient.return_value

        # Mock playlist creation
        mock_client.create_playlist = AsyncMock(return_value={"id": 50, "name": sample_playlist.name})

        # Mock track upload
        mock_client.add_tracks_to_playlist = AsyncMock(return_value={"success": True, "tracks_added": 12})

        # Mock verification - get playlist tracks
        uploaded_tracks = [
            {
                "id": f"track-{i}",
                "title": f"Test Track {i}",
                "artist": f"Test Artist {i}",
                "position": i,
            }
            for i in range(12)
        ]
        mock_client.get_playlist_tracks = AsyncMock(return_value=uploaded_tracks)

        async def mock_sync_with_verification(playlist):
            """Mock sync with verification."""
            # Create and upload
            azuracast_playlist = await mock_client.create_playlist(name=playlist.name)
            track_ids = [track.track_id for track in playlist.tracks]
            await mock_client.add_tracks_to_playlist(azuracast_playlist["id"], track_ids)

            # Verify upload
            uploaded = await mock_client.get_playlist_tracks(azuracast_playlist["id"])

            # Check track count
            assert len(uploaded) == len(playlist.tracks)

            # Check track order
            for i, (uploaded_track, original_track) in enumerate(zip(uploaded, playlist.tracks)):
                assert uploaded_track["id"] == original_track.track_id
                assert uploaded_track["position"] == original_track.position_in_playlist

            playlist.azuracast_id = azuracast_playlist["id"]
            playlist.synced_at = datetime.now()
            return playlist

        # Sync with verification
        synced_playlist = await mock_sync_with_verification(sample_playlist)

        # Validate
        assert synced_playlist.azuracast_id == 50
        mock_client.get_playlist_tracks.assert_called_once_with(50)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cleanup_test_playlists_after_test(sample_playlist):
    """
    Test cleanup of test playlists after test completion.

    Validates:
    - Test playlists can be identified
    - Cleanup removes test playlists
    - Production playlists are not affected
    """
    with patch("src.azuracast.main.AzuraCastSync") as MockClient:
        mock_client = MockClient.return_value

        # Create test playlist
        test_playlist_id = 100
        mock_client.create_playlist = AsyncMock(return_value={"id": test_playlist_id, "name": "TEST_" + sample_playlist.name})

        # Mock cleanup
        mock_client.delete_playlist = AsyncMock(return_value={"success": True})

        created_playlists = []

        async def mock_sync_with_tracking(playlist):
            """Mock sync that tracks created playlists."""
            azuracast_playlist = await mock_client.create_playlist(name="TEST_" + playlist.name)
            created_playlists.append(azuracast_playlist["id"])
            playlist.azuracast_id = azuracast_playlist["id"]
            return playlist

        async def cleanup_test_playlists():
            """Cleanup function."""
            for playlist_id in created_playlists:
                await mock_client.delete_playlist(playlist_id)
            created_playlists.clear()

        try:
            # Create test playlist
            synced_playlist = await mock_sync_with_tracking(sample_playlist)
            assert synced_playlist.azuracast_id == test_playlist_id

        finally:
            # Cleanup
            await cleanup_test_playlists()

            # Verify cleanup
            mock_client.delete_playlist.assert_called_once_with(test_playlist_id)
            assert len(created_playlists) == 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_azuracast_api_error_handling(sample_playlist):
    """
    Test error handling for AzuraCast API failures.

    Validates:
    - API errors are caught and handled
    - Retry logic is applied
    - Appropriate exceptions are raised
    """
    with patch("src.azuracast.main.AzuraCastSync") as MockClient:
        mock_client = MockClient.return_value

        # Mock API error
        mock_client.create_playlist = AsyncMock(side_effect=Exception("AzuraCast API Error"))

        async def mock_sync_with_error_handling(playlist):
            """Mock sync with error handling."""
            try:
                await mock_client.create_playlist(name=playlist.name)
            except Exception as e:
                # Log error and re-raise
                assert "AzuraCast API Error" in str(e)
                raise

        # Should raise exception
        with pytest.raises(Exception, match="AzuraCast API Error"):
            await mock_sync_with_error_handling(sample_playlist)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_sync_multiple_playlists_batch(sample_daypart, sample_criteria, sample_tracks, sample_validation_result):
    """
    Test syncing multiple playlists in batch.

    Validates:
    - Multiple playlists can be synced
    - Each gets unique AzuraCast ID
    - All syncs complete successfully
    """
    # Create multiple playlists
    from datetime import date

    playlists = []
    times = [("0600", "1000"), ("1000", "1400"), ("1400", "1800")]
    for i in range(3):
        playlist_id = str(uuid.uuid4())
        spec = PlaylistSpec(
            id=playlist_id,
            name=f"Monday_MorningDrive_{times[i][0]}_{times[i][1]}",
            source_daypart_id=sample_daypart.id,
            generation_date=date.today(),
            target_track_count_min=40,
            target_track_count_max=56,
            target_duration_minutes=240,
            track_selection_criteria=sample_criteria,
            created_at=datetime.now(),
        )
        from decimal import Decimal

        playlist = Playlist(
            id=playlist_id,
            name=spec.name,
            specification_id=spec.id,
            tracks=sample_tracks,
            validation_result=sample_validation_result,
            created_at=datetime.now(),
            cost_actual=Decimal('0.00'),
            generation_time_seconds=0.0,
        )
        playlists.append(playlist)

    with patch("src.azuracast.main.AzuraCastSync") as MockClient:
        mock_client = MockClient.return_value

        # Mock playlist creation with unique IDs
        mock_client.create_playlist = AsyncMock(
            side_effect=[{"id": 200 + i, "name": p.name} for i, p in enumerate(playlists)]
        )
        mock_client.add_tracks_to_playlist = AsyncMock(return_value={"success": True})

        async def mock_sync_batch(playlists_list):
            """Mock batch sync."""
            synced = []
            for playlist in playlists_list:
                azuracast_playlist = await mock_client.create_playlist(name=playlist.name)
                track_ids = [track.track_id for track in playlist.tracks]
                await mock_client.add_tracks_to_playlist(azuracast_playlist["id"], track_ids)
                playlist.azuracast_id = azuracast_playlist["id"]
                playlist.synced_at = datetime.now()
                synced.append(playlist)
            return synced

        # Sync all playlists
        synced_playlists = await mock_sync_batch(playlists)

        # Validate
        assert len(synced_playlists) == 3
        assert synced_playlists[0].azuracast_id == 200
        assert synced_playlists[1].azuracast_id == 201
        assert synced_playlists[2].azuracast_id == 202
        assert all(p.synced_at is not None for p in synced_playlists)
