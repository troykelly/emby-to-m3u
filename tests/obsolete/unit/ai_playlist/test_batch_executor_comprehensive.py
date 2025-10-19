"""
Comprehensive Unit Tests for batch_executor.py

Tests batch execution, parallel processing, budget enforcement, and validation.

Coverage Target: ≥90% for batch_executor.py (52 statements)
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, time

from src.ai_playlist.batch_executor import (
    execute_batch_selection,
    _execute_single_playlist_selection,
)
from src.ai_playlist.models import (
    ScheduleType,
    BPMRange,
    GenreCriteria,
    EraCriteria,
    PlaylistSpec,
    DaypartSpec,
    TrackSelectionCriteria,
    Playlist,
    SelectedTrack,
    ValidationResult,
)


@pytest.mark.asyncio
class TestExecuteBatchSelection:
    """Test suite for execute_batch_selection function."""

    @pytest.fixture
    def sample_daypart(self):
        """Create sample daypart spec."""
        return DaypartSpec(
            id="test-daypart-001",
            name="Test Daypart",
            schedule_type=ScheduleType.WEEKDAY,
            time_start=time(6, 0),
            time_end=time(10, 0),
            duration_hours=4.0,
            target_demographic="Test audience",
            bpm_progression=[BPMRange(time(6, 0), time(10, 0), 90, 130)],
            genre_mix={"Rock": 0.50, "Electronic": 0.30},
            era_distribution={"Current (0-2 years)": 0.60, "Recent (2-5 years)": 0.30},
            mood_guidelines=["energetic"],
            content_focus="Test programming",
            rotation_percentages={"Power": 0.30, "Medium": 0.40, "Light": 0.30},
            tracks_per_hour=(15, 15),
        ),
            bpm_progression={"06:00-10:00": (90, 130)},
            genre_mix={"Rock": 0.50, "Electronic": 0.30},
            era_distribution={"Current (0-2 years)": 0.60, "Recent (2-5 years)": 0.30},
            australian_min=0.30,
            mood="energetic",
            tracks_per_hour=15,
        )

    @pytest.fixture
    def sample_criteria(self):
        """Create sample track selection criteria."""
        return TrackSelectionCriteria(
            bpm_ranges=[BPMRange(time(0, 0), time(23, 59), 90, 130)],
            genre_mix={
                "Rock": GenreCriteria(target_percentage=0.50, tolerance=0.05),
                "Electronic": GenreCriteria(target_percentage=0.30, tolerance=0.05),
            },
            era_distribution={
                "Current (0-2 years)": EraCriteria("Current (0-2 years)", 2023, 2025, 0.60, 0.05),
                "Recent (2-5 years)": EraCriteria("Recent (2-5 years)", 2020, 2022, 0.30, 0.05),
            },
            australian_content_min=0.30,
            energy_flow_requirements=["energetic"],
            rotation_distribution={"Power": 0.30, "Medium": 0.40, "Light": 0.30},
            no_repeat_window_hours=4.0,
        ),
            bpm_tolerance=10,
            genre_mix={"Rock": (0.45, 0.55), "Electronic": (0.25, 0.35)},
            genre_tolerance=0.05,
            era_distribution={"Current (0-2 years)": (0.55, 0.65), "Recent (2-5 years)": (0.25, 0.35)},
            era_tolerance=0.05,
            australian_min=0.30,
            energy_flow="energetic",
        )

    @pytest.fixture
    def create_playlist_specs(self, sample_daypart, sample_criteria):
        """Create playlist specs factory."""
        def _create(count):
            return [
                PlaylistSpec(
                    id=f"550e8400-e29b-41d4-a716-44665544000{i}",
                    name=f"Monday_Playlist{i}_0600_1000",
                    daypart=sample_daypart,
                    track_criteria=sample_criteria,
                    target_duration_minutes=240,
                    created_at=datetime.now(),
                )
                for i in range(count)
            ]
        return _create

    async def test_execute_batch_selection_processes_all_specs(self, create_playlist_specs):
        """Test execute_batch_selection processes all specs."""
        specs = create_playlist_specs(3)

        playlists = await execute_batch_selection(specs)

        assert len(playlists) == 3
        assert all(isinstance(p, Playlist) for p in playlists)

    async def test_execute_batch_selection_mesh_topology_initialization(self, create_playlist_specs):
        """Test mesh topology initialization."""
        specs = create_playlist_specs(5)

        with patch("src.ai_playlist.batch_executor.logger") as mock_logger:
            playlists = await execute_batch_selection(specs)

            # Verify mesh topology logging
            assert any(
                "Mesh topology" in str(call) for call in mock_logger.info.call_args_list
            )

    async def test_execute_batch_selection_session_tracking(self, create_playlist_specs):
        """Test session tracking."""
        specs = create_playlist_specs(2)

        with patch("src.ai_playlist.batch_executor.time.time", return_value=1234567890):
            playlists = await execute_batch_selection(specs)

            # Verify session was created (logs contain session-1234567890)
            assert len(playlists) == 2

    async def test_execute_batch_selection_parallel_task_spawning(self, create_playlist_specs):
        """Test parallel task spawning (max 10)."""
        specs = create_playlist_specs(15)

        start_time = time.time()
        playlists = await execute_batch_selection(specs)
        elapsed = time.time() - start_time

        # 15 specs should process in 2 batches (10 + 5)
        assert len(playlists) == 15
        # With 0.1s sleep per spec, parallel execution should be faster than 15*0.1 = 1.5s
        assert elapsed < 1.0  # Should complete in ~0.2s with parallelism

    async def test_execute_batch_selection_result_aggregation(self, create_playlist_specs):
        """Test result aggregation."""
        specs = create_playlist_specs(7)

        playlists = await execute_batch_selection(specs)

        # Verify all playlists aggregated
        assert len(playlists) == 7
        # Verify all have correct structure
        for i, playlist in enumerate(playlists):
            assert playlist.id == specs[i].id
            assert playlist.name == specs[i].name
            assert len(playlist.tracks) == 10  # Mock tracks

    async def test_execute_batch_selection_empty_spec_list(self):
        """Test empty spec list handling."""
        playlists = await execute_batch_selection([])

        assert playlists == []

    async def test_execute_batch_selection_single_spec(self, create_playlist_specs):
        """Test single spec handling."""
        specs = create_playlist_specs(1)

        playlists = await execute_batch_selection(specs)

        assert len(playlists) == 1
        assert playlists[0].name == "Monday_Playlist0_0600_1000"

    async def test_execute_batch_selection_cost_budget_validation(self, create_playlist_specs):
        """Test cost budget validation (<$0.50)."""
        specs = create_playlist_specs(3)

        # Mock to return high cost
        async def expensive_selection(spec, session_id):
            playlist = Mock()
            playlist.name = spec.name
            playlist.tracks = []
            playlist.validation_result = Mock()
            playlist.validation_result.is_valid = Mock(return_value=True)
            return playlist, 0.30  # $0.30 per playlist (would exceed $0.50)

        with patch(
            "src.ai_playlist.batch_executor._execute_single_playlist_selection",
            side_effect=expensive_selection,
        ):
            with pytest.raises(RuntimeError, match="Budget exceeded"):
                await execute_batch_selection(specs)

    async def test_execute_batch_selection_time_budget_validation(self, create_playlist_specs):
        """Test time budget validation (<10 min)."""
        specs = create_playlist_specs(1)

        # Mock time to simulate timeout
        with patch("src.ai_playlist.batch_executor.time.time") as mock_time:
            mock_time.side_effect = [
                1000,  # start_time
                1000,  # First check
                1700,  # After processing (700 seconds elapsed)
            ]

            with pytest.raises(RuntimeError, match="Time budget exceeded"):
                await execute_batch_selection(specs)

    async def test_execute_batch_selection_runtime_error_on_cost_exceeded(self, create_playlist_specs):
        """Test RuntimeError on cost exceeded."""
        specs = create_playlist_specs(2)

        async def expensive_selection(spec, session_id):
            playlist = Mock()
            playlist.validation_result = Mock()
            playlist.validation_result.is_valid = Mock(return_value=True)
            return playlist, 0.40  # Exceeds $0.50 after 2

        with patch(
            "src.ai_playlist.batch_executor._execute_single_playlist_selection",
            side_effect=expensive_selection,
        ):
            with pytest.raises(RuntimeError, match="Budget exceeded.*0.50"):
                await execute_batch_selection(specs)

    async def test_execute_batch_selection_runtime_error_on_time_exceeded(self, create_playlist_specs):
        """Test RuntimeError on time exceeded."""
        specs = create_playlist_specs(1)

        with patch("src.ai_playlist.batch_executor.time.time") as mock_time:
            # Simulate 11 minutes elapsed
            mock_time.side_effect = [0, 0, 700]  # 700 seconds > 600 seconds

            with pytest.raises(RuntimeError, match="Time budget exceeded.*600"):
                await execute_batch_selection(specs)

    async def test_execute_batch_selection_validation_check(self, create_playlist_specs):
        """Test playlist validation (≥80% constraint, ≥70% flow)."""
        specs = create_playlist_specs(2)

        # All playlists should pass validation by default (mock returns valid results)
        playlists = await execute_batch_selection(specs)

        for playlist in playlists:
            assert playlist.validation_result.constraint_satisfaction >= 0.80
            assert playlist.validation_result.flow_quality_score >= 0.70
            assert playlist.validation_result.is_valid()

    async def test_execute_batch_selection_value_error_on_validation_failures(
        self, create_playlist_specs
    ):
        """Test ValueError on validation failures."""
        specs = create_playlist_specs(2)

        # Mock to return invalid playlists
        async def invalid_selection(spec, session_id):
            playlist = Mock()
            playlist.name = spec.name
            playlist.tracks = []
            playlist.validation_result = Mock()
            playlist.validation_result.is_valid = Mock(return_value=False)
            return playlist, 0.005

        with patch(
            "src.ai_playlist.batch_executor._execute_single_playlist_selection",
            side_effect=invalid_selection,
        ):
            with pytest.raises(ValueError, match="playlists failed validation"):
                await execute_batch_selection(specs)

    async def test_execute_batch_selection_partial_validation_results(self, create_playlist_specs):
        """Test partial validation results."""
        specs = create_playlist_specs(3)

        # Mix of valid and invalid
        async def mixed_validation(spec, session_id):
            playlist = Mock()
            playlist.name = spec.name
            playlist.tracks = []
            is_valid = "0" in spec.name or "2" in spec.name  # 0 and 2 are valid
            playlist.validation_result = Mock()
            playlist.validation_result.is_valid = Mock(return_value=is_valid)
            return playlist, 0.005

        with patch(
            "src.ai_playlist.batch_executor._execute_single_playlist_selection",
            side_effect=mixed_validation,
        ):
            with pytest.raises(ValueError, match="1 playlists failed validation"):
                await execute_batch_selection(specs)

    async def test_execute_batch_selection_validation_error_messages(self, create_playlist_specs):
        """Test validation error messages."""
        specs = create_playlist_specs(2)

        async def invalid_selection(spec, session_id):
            playlist = Mock()
            playlist.name = spec.name
            playlist.tracks = []
            playlist.validation_result = Mock()
            playlist.validation_result.is_valid = Mock(return_value=False)
            return playlist, 0.005

        with patch(
            "src.ai_playlist.batch_executor._execute_single_playlist_selection",
            side_effect=invalid_selection,
        ):
            with pytest.raises(ValueError) as exc_info:
                await execute_batch_selection(specs)

            # Verify error message contains playlist names
            error_msg = str(exc_info.value)
            assert "Monday_Playlist0_0600_1000" in error_msg
            assert "Monday_Playlist1_0600_1000" in error_msg


@pytest.mark.asyncio
class TestExecuteSinglePlaylistSelection:
    """Test suite for _execute_single_playlist_selection helper."""

    @pytest.fixture
    def sample_spec(self):
        """Create sample playlist spec."""
        daypart = DaypartSpec(
            name="Test",
            time_range=("06:00", "10:00"),
            bpm_progression={"06:00-10:00": (90, 130)},
            genre_mix={"Rock": 0.50},
            era_distribution={"Current (0-2 years)": 0.60},
            australian_min=0.30,
            mood="energetic",
            tracks_per_hour=15,
        )

        criteria = TrackSelectionCriteria(
            bpm_range=(90, 130),
            bpm_tolerance=10,
            genre_mix={"Rock": (0.45, 0.55)},
            genre_tolerance=0.05,
            era_distribution={"Current (0-2 years)": (0.55, 0.65)},
            era_tolerance=0.05,
            australian_min=0.30,
            energy_flow="energetic",
        )

        return PlaylistSpec(
            id="550e8400-e29b-41d4-a716-446655440000",
            name="Monday_TestPlaylist_0600_1000",
            daypart=daypart,
            track_criteria=criteria,
            target_duration_minutes=240,
            created_at=datetime.now(),
        )

    async def test_single_selection_returns_playlist_and_cost(self, sample_spec):
        """Test single playlist selection returns playlist and cost."""
        playlist, cost = await _execute_single_playlist_selection(sample_spec, "session-123")

        assert isinstance(playlist, Playlist)
        assert isinstance(cost, float)
        assert cost > 0
        assert cost == 0.005  # Mock cost

    async def test_single_selection_creates_mock_tracks(self, sample_spec):
        """Test single selection creates mock tracks."""
        playlist, cost = await _execute_single_playlist_selection(sample_spec, "session-456")

        assert len(playlist.tracks) == 10
        for i, track in enumerate(playlist.tracks):
            assert isinstance(track, SelectedTrack)
            assert track.track_id == f"mock-track-{i}"
            assert track.position == i + 1
            assert track.bpm == 120 + i

    async def test_single_selection_validation_passes(self, sample_spec):
        """Test single selection creates playlist that passes validation."""
        playlist, cost = await _execute_single_playlist_selection(sample_spec, "session-789")

        assert playlist.validation_result.is_valid()
        assert playlist.validation_result.constraint_satisfaction == 0.85
        assert playlist.validation_result.flow_quality_score == 0.75
        assert playlist.validation_result.australian_content == 0.40

    async def test_single_selection_playlist_structure(self, sample_spec):
        """Test single selection creates correct playlist structure."""
        playlist, cost = await _execute_single_playlist_selection(sample_spec, "session-abc")

        assert playlist.id == sample_spec.id
        assert playlist.name == sample_spec.name
        assert playlist.spec == sample_spec
        assert isinstance(playlist.created_at, datetime)
        assert playlist.synced_at is None
        assert playlist.azuracast_id is None

    async def test_single_selection_session_id_usage(self, sample_spec):
        """Test single selection uses session_id for coordination."""
        with patch("src.ai_playlist.batch_executor.logger") as mock_logger:
            await _execute_single_playlist_selection(sample_spec, "session-test-123")

            # Verify session_id is used in logging
            debug_calls = [str(call) for call in mock_logger.debug.call_args_list]
            assert any("session-test-123" in call for call in debug_calls)

    async def test_single_selection_async_execution(self, sample_spec):
        """Test single selection executes asynchronously."""
        start_time = time.time()

        # Run multiple selections in parallel
        tasks = [
            _execute_single_playlist_selection(sample_spec, f"session-{i}")
            for i in range(5)
        ]
        results = await asyncio.gather(*tasks)

        elapsed = time.time() - start_time

        assert len(results) == 5
        # Parallel execution should be faster than 5*0.1 = 0.5s sequential
        assert elapsed < 0.3

    async def test_single_selection_cost_calculation(self, sample_spec):
        """Test single selection cost calculation."""
        playlist, cost = await _execute_single_playlist_selection(sample_spec, "session-cost")

        # Mock cost should be consistent
        assert cost == 0.005
        # Cost should be well under budget per playlist
        assert cost < 0.05  # <$0.50 total budget / 10 playlists

    async def test_single_selection_validation_thresholds(self, sample_spec):
        """Test single selection meets validation thresholds."""
        playlist, cost = await _execute_single_playlist_selection(sample_spec, "session-val")

        val = playlist.validation_result
        # Verify meets required thresholds
        assert val.constraint_satisfaction >= 0.80
        assert val.flow_quality_score >= 0.70
        assert val.australian_content >= 0.30
        assert val.bpm_variance < 10
        assert val.passes_validation is True
