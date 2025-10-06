"""
Unit Tests for Batch Executor

Tests parallel track selection execution, budget enforcement, and error handling.
"""

import pytest
import asyncio
import uuid
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from src.ai_playlist.batch_executor import (
    execute_batch_selection,
    _execute_single_playlist_selection
)
from src.ai_playlist.models import (
    PlaylistSpec,
    DaypartSpec,
    TrackSelectionCriteria,
    Playlist,
    SelectedTrack,
    ValidationResult
)


@pytest.mark.asyncio
class TestExecuteBatchSelection:
    """Test suite for execute_batch_selection function."""

    async def test_batch_selection_success(self):
        """Test successful batch execution with valid playlists."""
        daypart = DaypartSpec(
            name="Test",
            day="Monday",
            time_range=("06:00", "10:00"),
            bpm_progression={"06:00-10:00": (90, 130)},
            genre_mix={"Rock": 0.50},
            era_distribution={"Current (0-2 years)": 0.60},
            australian_min=0.30,
            mood="energetic",
            tracks_per_hour=15
        )

        specs = [
            PlaylistSpec(
                id=str(uuid.uuid4()),
                name=f"Monday_TestPlaylist{i}_0600_1000",
                daypart=daypart,
                track_criteria=TrackSelectionCriteria(
                    bpm_range=(90, 130),
                    bpm_tolerance=10,
                    genre_mix={"Rock": (0.45, 0.55)},
                    genre_tolerance=0.05,
                    era_distribution={"Current (0-2 years)": (0.55, 0.65)},
                    era_tolerance=0.05,
                    australian_min=0.30,
                    energy_flow="energetic"
                ),
                target_duration_minutes=240,
                created_at=datetime.now()
            )
            for i in range(3)
        ]

        playlists = await execute_batch_selection(specs)

        assert len(playlists) == 3
        for playlist in playlists:
            assert playlist.validation_result.is_valid()
            assert len(playlist.tracks) == 10  # Mock tracks

    async def test_batch_selection_parallel_execution(self):
        """Test batch selection executes tasks in parallel."""
        daypart = DaypartSpec(
            name="Test",
            day="Monday",
            time_range=("06:00", "10:00"),
            bpm_progression={"06:00-10:00": (90, 130)},
            genre_mix={"Rock": 0.50},
            era_distribution={"Current (0-2 years)": 0.60},
            australian_min=0.30,
            mood="energetic",
            tracks_per_hour=15
        )

        # Create 15 specs (should process in 2 batches of 10)
        specs = [
            PlaylistSpec(
                id=str(uuid.uuid4()),
                name=f"Monday_Test{i}_0600_1000",
                daypart=daypart,
                track_criteria=TrackSelectionCriteria(
                    bpm_range=(90, 130),
                    bpm_tolerance=10,
                    genre_mix={"Rock": (0.45, 0.55)},
                    genre_tolerance=0.05,
                    era_distribution={"Current (0-2 years)": (0.55, 0.65)},
                    era_tolerance=0.05,
                    australian_min=0.30,
                    energy_flow="energetic"
                ),
                target_duration_minutes=240,
                created_at=datetime.now()
            )
            for i in range(15)
        ]

        import time
        start_time = time.time()
        playlists = await execute_batch_selection(specs)
        elapsed_time = time.time() - start_time

        assert len(playlists) == 15
        # Parallel execution should be faster than 15 * 0.1s = 1.5s sequential
        assert elapsed_time < 1.0  # Should complete in ~0.2s with parallelism

    async def test_batch_selection_cost_budget_enforcement(self):
        """Test batch selection enforces cost budget."""
        daypart = DaypartSpec(
            name="Test",
            day="Monday",
            time_range=("06:00", "10:00"),
            bpm_progression={"06:00-10:00": (90, 130)},
            genre_mix={"Rock": 0.50},
            era_distribution={"Current (0-2 years)": 0.60},
            australian_min=0.30,
            mood="energetic",
            tracks_per_hour=15
        )

        # Create many specs to potentially exceed budget
        specs = [
            PlaylistSpec(
                id=str(uuid.uuid4()),
                name=f"Monday_Test{i}_0600_1000",
                daypart=daypart,
                track_criteria=TrackSelectionCriteria(
                    bpm_range=(90, 130),
                    bpm_tolerance=10,
                    genre_mix={"Rock": (0.45, 0.55)},
                    genre_tolerance=0.05,
                    era_distribution={"Current (0-2 years)": (0.55, 0.65)},
                    era_tolerance=0.05,
                    australian_min=0.30,
                    energy_flow="energetic"
                ),
                target_duration_minutes=240,
                created_at=datetime.now()
            )
            for i in range(200)  # Many playlists
        ]

        # Mock to return high cost per playlist
        async def mock_expensive_selection(spec, session_id):
            playlist = Mock()
            playlist.name = spec.name
            playlist.tracks = []
            playlist.validation_result = Mock()
            playlist.validation_result.is_valid = Mock(return_value=True)
            return playlist, 0.10  # $0.10 per playlist (would exceed $0.50 after 5)

        with patch("src.ai_playlist.batch_executor._execute_single_playlist_selection", side_effect=mock_expensive_selection):
            with pytest.raises(RuntimeError, match="Budget exceeded"):
                await execute_batch_selection(specs)

    async def test_batch_selection_time_budget_enforcement(self):
        """Test batch selection enforces time budget."""
        daypart = DaypartSpec(
            name="Test",
            day="Monday",
            time_range=("06:00", "10:00"),
            bpm_progression={"06:00-10:00": (90, 130)},
            genre_mix={"Rock": 0.50},
            era_distribution={"Current (0-2 years)": 0.60},
            australian_min=0.30,
            mood="energetic",
            tracks_per_hour=15
        )

        specs = [
            PlaylistSpec(
                id="test-1",
                name="Test_1",
                daypart=daypart,
                track_criteria=TrackSelectionCriteria(
                    bpm_range=(90, 130),
                    bpm_tolerance=10,
                    genre_mix={"Rock": (0.45, 0.55)},
                    genre_tolerance=0.05,
                    era_distribution={"Current (0-2 years)": (0.55, 0.65)},
                    era_tolerance=0.05,
                    australian_min=0.30,
                    energy_flow="energetic"
                ),
                target_duration_minutes=240,
                created_at=datetime.now()
            )
        ]

        # Mock slow selection (would exceed 10 minute timeout)
        async def mock_slow_selection(spec, session_id):
            await asyncio.sleep(700)  # 11+ minutes
            return Mock(), 0.005

        with patch("src.ai_playlist.batch_executor._execute_single_playlist_selection", side_effect=mock_slow_selection):
            with pytest.raises(RuntimeError, match="Time budget exceeded"):
                await execute_batch_selection(specs)

    async def test_batch_selection_failed_validation_raises_error(self):
        """Test batch selection raises ValueError when playlists fail validation."""
        daypart = DaypartSpec(
            name="Test",
            day="Monday",
            time_range=("06:00", "10:00"),
            bpm_progression={"06:00-10:00": (90, 130)},
            genre_mix={"Rock": 0.50},
            era_distribution={"Current (0-2 years)": 0.60},
            australian_min=0.30,
            mood="energetic",
            tracks_per_hour=15
        )

        spec = PlaylistSpec(
            id="test-fail",
            name="Test_Fail",
            daypart=daypart,
            track_criteria=TrackSelectionCriteria(
                bpm_range=(90, 130),
                bpm_tolerance=10,
                genre_mix={"Rock": (0.45, 0.55)},
                genre_tolerance=0.05,
                era_distribution={"Current (0-2 years)": (0.55, 0.65)},
                era_tolerance=0.05,
                australian_min=0.30,
                energy_flow="energetic"
            ),
            target_duration_minutes=240,
            created_at=datetime.now()
        )

        # Mock selection that returns invalid playlist
        async def mock_invalid_selection(spec, session_id):
            playlist = Mock()
            playlist.name = spec.name
            playlist.tracks = []
            playlist.validation_result = Mock()
            playlist.validation_result.is_valid = Mock(return_value=False)  # Invalid
            return playlist, 0.005

        with patch("src.ai_playlist.batch_executor._execute_single_playlist_selection", side_effect=mock_invalid_selection):
            with pytest.raises(ValueError, match="playlists failed validation"):
                await execute_batch_selection([spec])

    async def test_batch_selection_handles_task_exception(self):
        """Test batch selection raises RuntimeError on task exception."""
        daypart = DaypartSpec(
            name="Test",
            day="Monday",
            time_range=("06:00", "10:00"),
            bpm_progression={"06:00-10:00": (90, 130)},
            genre_mix={"Rock": 0.50},
            era_distribution={"Current (0-2 years)": 0.60},
            australian_min=0.30,
            mood="energetic",
            tracks_per_hour=15
        )

        spec = PlaylistSpec(
            id="test-error",
            name="Test_Error",
            daypart=daypart,
            track_criteria=TrackSelectionCriteria(
                bpm_range=(90, 130),
                bpm_tolerance=10,
                genre_mix={"Rock": (0.45, 0.55)},
                genre_tolerance=0.05,
                era_distribution={"Current (0-2 years)": (0.55, 0.65)},
                era_tolerance=0.05,
                australian_min=0.30,
                energy_flow="energetic"
            ),
            target_duration_minutes=240,
            created_at=datetime.now()
        )

        # Mock selection that raises exception
        async def mock_error_selection(spec, session_id):
            raise Exception("Test error")

        with patch("src.ai_playlist.batch_executor._execute_single_playlist_selection", side_effect=mock_error_selection):
            with pytest.raises(RuntimeError, match="Playlist selection failed"):
                await execute_batch_selection([spec])


@pytest.mark.asyncio
class TestExecuteSinglePlaylistSelection:
    """Test suite for _execute_single_playlist_selection helper."""

    async def test_single_selection_returns_playlist_and_cost(self):
        """Test single playlist selection returns playlist and cost."""
        daypart = DaypartSpec(
            name="Test",
            day="Monday",
            time_range=("06:00", "10:00"),
            bpm_progression={"06:00-10:00": (90, 130)},
            genre_mix={"Rock": 0.50},
            era_distribution={"Current (0-2 years)": 0.60},
            australian_min=0.30,
            mood="energetic",
            tracks_per_hour=15
        )

        spec = PlaylistSpec(
            id="test-123",
            name="Test_Playlist",
            daypart=daypart,
            track_criteria=TrackSelectionCriteria(
                bpm_range=(90, 130),
                bpm_tolerance=10,
                genre_mix={"Rock": (0.45, 0.55)},
                genre_tolerance=0.05,
                era_distribution={"Current (0-2 years)": (0.55, 0.65)},
                era_tolerance=0.05,
                australian_min=0.30,
                energy_flow="energetic"
            ),
            target_duration_minutes=240,
            created_at=datetime.now()
        )

        playlist, cost = await _execute_single_playlist_selection(spec, "session-123")

        assert isinstance(playlist, Playlist)
        assert playlist.name == "Test_Playlist"
        assert isinstance(cost, float)
        assert cost > 0
        assert cost < 0.01  # Mock cost should be small

    async def test_single_selection_creates_mock_tracks(self):
        """Test single selection creates mock tracks."""
        daypart = DaypartSpec(
            name="Test",
            day="Monday",
            time_range=("06:00", "10:00"),
            bpm_progression={"06:00-10:00": (90, 130)},
            genre_mix={"Rock": 0.50},
            era_distribution={"Current (0-2 years)": 0.60},
            australian_min=0.30,
            mood="energetic",
            tracks_per_hour=15
        )

        spec = PlaylistSpec(
            id="test-456",
            name="Test_Playlist_2",
            daypart=daypart,
            track_criteria=TrackSelectionCriteria(
                bpm_range=(90, 130),
                bpm_tolerance=10,
                genre_mix={"Rock": (0.45, 0.55)},
                genre_tolerance=0.05,
                era_distribution={"Current (0-2 years)": (0.55, 0.65)},
                era_tolerance=0.05,
                australian_min=0.30,
                energy_flow="energetic"
            ),
            target_duration_minutes=240,
            created_at=datetime.now()
        )

        playlist, cost = await _execute_single_playlist_selection(spec, "session-456")

        # Should have 10 mock tracks
        assert len(playlist.tracks) == 10
        for i, track in enumerate(playlist.tracks):
            assert track.track_id == f"mock-track-{i}"
            assert track.position == i + 1

    async def test_single_selection_validation_passes(self):
        """Test single selection creates playlist that passes validation."""
        daypart = DaypartSpec(
            name="Test",
            day="Monday",
            time_range=("06:00", "10:00"),
            bpm_progression={"06:00-10:00": (90, 130)},
            genre_mix={"Rock": 0.50},
            era_distribution={"Current (0-2 years)": 0.60},
            australian_min=0.30,
            mood="energetic",
            tracks_per_hour=15
        )

        spec = PlaylistSpec(
            id="test-789",
            name="Test_Playlist_3",
            daypart=daypart,
            track_criteria=TrackSelectionCriteria(
                bpm_range=(90, 130),
                bpm_tolerance=10,
                genre_mix={"Rock": (0.45, 0.55)},
                genre_tolerance=0.05,
                era_distribution={"Current (0-2 years)": (0.55, 0.65)},
                era_tolerance=0.05,
                australian_min=0.30,
                energy_flow="energetic"
            ),
            target_duration_minutes=240,
            created_at=datetime.now()
        )

        playlist, cost = await _execute_single_playlist_selection(spec, "session-789")

        # Validation should pass
        assert playlist.validation_result.is_valid() is True
        assert playlist.validation_result.constraint_satisfaction >= 0.80
        assert playlist.validation_result.flow_quality_score >= 0.70
        assert playlist.validation_result.australian_content >= 0.30
