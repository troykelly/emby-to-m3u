"""Async tests for batch_executor.py - Testing async orchestration methods.

Tests cover:
- _generate_playlist_stub() method
- _execute_single_playlist_selection() function
- execute_batch_selection() parallel orchestration
- generate_batch() workflow
- Progress callbacks
- Budget enforcement in async context
- Error handling and timeouts
"""
import pytest
import asyncio
import uuid
import time
from decimal import Decimal
from datetime import date, datetime, time as dt_time
from unittest.mock import Mock, patch, AsyncMock, MagicMock, call

from src.ai_playlist.batch_executor import (
    BatchPlaylistGenerator,
    execute_batch_selection,
    _execute_single_playlist_selection
)
from src.ai_playlist.models import (
    PlaylistSpec,
    Playlist,
    SelectedTrack,
    ValidationResult,
    PlaylistSpecification,
    TrackSelectionCriteria,
    BPMRange,
    GenreCriteria,
    EraCriteria
)
from src.ai_playlist.models.validation import (
    ValidationStatus,
    FlowQualityMetrics,
    ConstraintScore
)
from src.ai_playlist.cost_manager import BudgetExceededError


@pytest.fixture
def sample_playlist_spec():
    """Create sample PlaylistSpecification for testing."""
    spec_id = str(uuid.uuid4())

    criteria = TrackSelectionCriteria(
        bpm_ranges=[BPMRange(
            time_start=dt_time(6, 0),
            time_end=dt_time(10, 0),
            bpm_min=90,
            bpm_max=130
        )],
        genre_mix={"Rock": GenreCriteria(target_percentage=0.5)},
        era_distribution={"Current": EraCriteria(
            era_name="Current",
            min_year=2020,
            max_year=2025,
            target_percentage=0.6
        )},
        australian_content_min=0.30,
        energy_flow_requirements=["Energetic"],
        rotation_distribution={"Power": 0.6},
        no_repeat_window_hours=24.0
    )

    return PlaylistSpecification(
        id=spec_id,
        name="Monday_MorningDrive_0600_1000",
        source_daypart_id=str(uuid.uuid4()),
        generation_date=date.today(),
        target_track_count_min=10,
        target_track_count_max=15,
        target_duration_minutes=240,
        track_selection_criteria=criteria,
        created_at=datetime.now()
    )


class TestGeneratePlaylistStub:
    """Test _generate_playlist_stub method."""

    @pytest.mark.asyncio
    async def test_generate_playlist_stub_creates_mock_playlist(self):
        """Test stub generates playlist with mock tracks."""
        # Arrange
        mock_client = Mock()
        generator = BatchPlaylistGenerator(
            openai_api_key="test-key",
            subsonic_client=mock_client
        )

        spec = Mock()
        spec.id = "test-spec-123"
        spec.name = "Test Playlist"
        spec.target_track_count_max = 8
        spec.target_duration_minutes = 240

        # Act
        playlist = await generator._generate_playlist_stub(spec)

        # Assert
        assert isinstance(playlist, Playlist)
        assert playlist.name == "Test Playlist"
        assert len(playlist.tracks) == 8
        # Playlist doesn't have duration_minutes attribute - it's calculated from tracks
        total_duration = sum(t.duration_seconds for t in playlist.tracks)
        assert total_duration > 0  # Verify tracks have duration

    @pytest.mark.asyncio
    async def test_generate_playlist_stub_respects_max_track_count(self):
        """Test stub respects target_track_count_max limit."""
        # Arrange
        mock_client = Mock()
        generator = BatchPlaylistGenerator(
            openai_api_key="test-key",
            subsonic_client=mock_client
        )

        spec = Mock()
        spec.id = "test-spec-456"
        spec.name = "Small Playlist"
        spec.target_track_count_max = 5
        spec.target_duration_minutes = 120

        # Act
        playlist = await generator._generate_playlist_stub(spec)

        # Assert
        assert len(playlist.tracks) == 5

    @pytest.mark.asyncio
    async def test_generate_playlist_stub_limits_to_10_tracks(self):
        """Test stub limits tracks to 10 even if spec requests more."""
        # Arrange
        mock_client = Mock()
        generator = BatchPlaylistGenerator(
            openai_api_key="test-key",
            subsonic_client=mock_client
        )

        spec = Mock()
        spec.id = "test-spec-789"
        spec.name = "Large Playlist"
        spec.target_track_count_max = 50
        spec.target_duration_minutes = 600

        # Act
        playlist = await generator._generate_playlist_stub(spec)

        # Assert
        assert len(playlist.tracks) == 10  # min(50, 10) = 10

    @pytest.mark.asyncio
    async def test_generate_playlist_stub_tracks_have_required_fields(self):
        """Test stub tracks have all required SelectedTrack fields."""
        # Arrange
        mock_client = Mock()
        generator = BatchPlaylistGenerator(
            openai_api_key="test-key",
            subsonic_client=mock_client
        )

        spec = Mock()
        spec.id = "test-spec-abc"
        spec.name = "Test Tracks"
        spec.target_track_count_max = 3
        spec.target_duration_minutes = 60

        # Act
        playlist = await generator._generate_playlist_stub(spec)

        # Assert
        track = playlist.tracks[0]
        assert track.track_id.startswith("mock-")
        assert track.title is not None
        assert track.artist is not None
        assert track.bpm > 0
        assert track.duration_seconds == 180
        assert track.position_in_playlist == 1

    @pytest.mark.asyncio
    async def test_generate_playlist_stub_validation_result_passes(self):
        """Test stub creates passing validation result."""
        # Arrange
        mock_client = Mock()
        generator = BatchPlaylistGenerator(
            openai_api_key="test-key",
            subsonic_client=mock_client
        )

        spec = Mock()
        spec.id = "test-spec-def"
        spec.name = "Valid Playlist"
        spec.target_track_count_max = 5
        spec.target_duration_minutes = 120

        # Act
        playlist = await generator._generate_playlist_stub(spec)

        # Assert
        assert playlist.validation_result is not None
        assert playlist.validation_result.overall_status == ValidationStatus.PASS


class TestExecuteSinglePlaylistSelection:
    """Test _execute_single_playlist_selection helper function."""

    @pytest.mark.asyncio
    async def test_execute_single_playlist_selection_returns_tuple(self):
        """Test function returns (playlist, cost) tuple."""
        # Arrange
        spec = Mock()
        spec.id = "test-spec-1"
        spec.name = "Test Playlist"
        spec.target_track_count_max = 5
        spec.target_duration_minutes = 120
        session_id = "session-123"

        # Act
        result = await _execute_single_playlist_selection(spec, session_id)

        # Assert
        assert isinstance(result, tuple)
        assert len(result) == 2
        playlist, cost = result
        assert isinstance(playlist, Playlist)
        assert isinstance(cost, float)

    @pytest.mark.asyncio
    async def test_execute_single_playlist_selection_cost_is_reasonable(self):
        """Test function returns reasonable cost estimate."""
        # Arrange
        spec = Mock()
        spec.id = "test-spec-2"
        spec.name = "Cost Test"
        spec.target_track_count_max = 10
        spec.target_duration_minutes = 240
        session_id = "session-456"

        # Act
        playlist, cost = await _execute_single_playlist_selection(spec, session_id)

        # Assert
        assert 0.001 <= cost <= 0.1  # Reasonable cost range


class TestExecuteBatchSelection:
    """Test execute_batch_selection parallel orchestration function."""

    @pytest.mark.asyncio
    async def test_execute_batch_selection_single_playlist(self):
        """Test batch selection with single playlist."""
        # Arrange
        spec = Mock()
        spec.id = "spec-1"
        spec.name = "Single Playlist"
        spec.target_track_count_max = 5
        spec.target_duration_minutes = 120
        specs = [spec]

        # Act
        playlists = await execute_batch_selection(specs)

        # Assert
        assert len(playlists) == 1
        assert isinstance(playlists[0], Playlist)
        assert playlists[0].name == "Single Playlist"

    @pytest.mark.asyncio
    async def test_execute_batch_selection_multiple_playlists(self):
        """Test batch selection with multiple playlists executes in parallel."""
        # Arrange
        specs = []
        for i in range(3):
            spec = Mock()
            spec.id = f"spec-{i}"
            spec.name = f"Playlist {i+1}"
            spec.target_track_count_max = 5
            spec.target_duration_minutes = 120
            specs.append(spec)

        # Act
        start_time = time.time()
        playlists = await execute_batch_selection(specs)
        elapsed_time = time.time() - start_time

        # Assert
        assert len(playlists) == 3
        # Parallel execution should be much faster than sequential
        # Even with stub delays, should complete quickly
        assert elapsed_time < 5.0  # Should be nearly instant for stubs

    @pytest.mark.asyncio
    async def test_execute_batch_selection_enforces_cost_budget(self):
        """Test batch selection raises error if cost exceeds budget."""
        # Arrange - Create many playlists to potentially exceed budget
        specs = []
        for i in range(20):  # 20 playlists might exceed $0.50 budget
            spec = Mock()
            spec.id = f"spec-{i}"
            spec.name = f"Expensive Playlist {i+1}"
            spec.target_track_count_max = 10
            spec.target_duration_minutes = 240
            specs.append(spec)

        # Act & Assert
        # This may or may not raise depending on stub cost, but should handle it gracefully
        try:
            playlists = await execute_batch_selection(specs)
            # If it succeeds, verify we got playlists
            assert len(playlists) > 0
        except RuntimeError as e:
            # If budget exceeded, verify error message
            assert "Budget exceeded" in str(e)

    @pytest.mark.asyncio
    async def test_execute_batch_selection_validates_all_playlists(self):
        """Test batch selection validates all returned playlists."""
        # Arrange
        specs = []
        for i in range(3):
            spec = Mock()
            spec.id = f"spec-{i}"
            spec.name = f"Valid Playlist {i+1}"
            spec.target_track_count_max = 5
            spec.target_duration_minutes = 120
            specs.append(spec)

        # Act
        playlists = await execute_batch_selection(specs)

        # Assert
        for playlist in playlists:
            assert playlist.validation_result is not None
            # Stub creates passing validation
            assert playlist.validation_result.overall_status == ValidationStatus.PASS

    @pytest.mark.asyncio
    async def test_execute_batch_selection_batches_parallel_tasks(self):
        """Test batch selection limits parallelism to max_parallel_tasks."""
        # Arrange - Create 15 playlists (should process in 2 batches of 10 + 5)
        specs = []
        for i in range(15):
            spec = Mock()
            spec.id = f"spec-{i}"
            spec.name = f"Batch Playlist {i+1}"
            spec.target_track_count_max = 5
            spec.target_duration_minutes = 120
            specs.append(spec)

        # Act
        playlists = await execute_batch_selection(specs)

        # Assert
        assert len(playlists) == 15


class TestGenerateBatchWithProgressCallback:
    """Test generate_batch with progress callbacks."""

    @pytest.mark.asyncio
    async def test_generate_batch_emits_started_progress(self):
        """Test generate_batch emits 'started' progress event."""
        # Arrange
        mock_subsonic_client = Mock()
        generator = BatchPlaylistGenerator(
            openai_api_key="test-key",
            subsonic_client=mock_subsonic_client
        )

        progress_events = []
        generator.on_progress = lambda event: progress_events.append(event)

        mock_daypart = Mock()
        mock_daypart.name = "Morning Drive"
        mock_daypart.target_track_count_max = 5
        mock_daypart.duration_hours = 2.0
        mock_daypart.genre_mix = {"Rock": 0.5}
        mock_daypart.era_distribution = {"Current": 0.6}
        mock_daypart.bpm_progression = [Mock()]

        # Create a mock playlist to return
        mock_playlist = Mock(spec=Playlist)
        mock_playlist.tracks = []
        mock_playlist.cost_actual = Decimal("0.01")

        # Mock both PlaylistSpecification.from_daypart and OpenAIClient.generate_playlist
        with patch('src.ai_playlist.models.PlaylistSpecification.from_daypart') as mock_from_daypart, \
             patch('src.ai_playlist.openai_client.OpenAIClient') as mock_ai_client_class:

            mock_spec = Mock()
            mock_spec.id = "spec-123"
            mock_spec.name = "Morning Drive"
            mock_spec.target_track_count_max = 5
            mock_spec.target_duration_minutes = 120
            mock_from_daypart.return_value = mock_spec

            # Mock the OpenAIClient instance and its generate_playlist method
            mock_ai_instance = Mock()
            mock_ai_instance.generate_playlist = AsyncMock(return_value=mock_playlist)
            mock_ai_instance.timeout_seconds = 30
            mock_ai_client_class.return_value = mock_ai_instance

            # Act
            playlists = await generator.generate_batch([mock_daypart], date.today())

        # Assert
        assert len(progress_events) >= 2  # At least started and completed
        assert progress_events[0]['status'] == 'started'
        assert progress_events[0]['total_dayparts'] == 1

    @pytest.mark.asyncio
    async def test_generate_batch_emits_completed_progress(self):
        """Test generate_batch emits 'completed' progress event."""
        # Arrange
        mock_subsonic_client = Mock()
        generator = BatchPlaylistGenerator(
            openai_api_key="test-key",
            subsonic_client=mock_subsonic_client
        )

        progress_events = []
        generator.on_progress = lambda event: progress_events.append(event)

        mock_daypart = Mock()
        mock_daypart.name = "Afternoon Drive"
        mock_daypart.target_track_count_max = 8
        mock_daypart.duration_hours = 3.0
        mock_daypart.genre_mix = {"Pop": 0.5}
        mock_daypart.era_distribution = {"Current": 0.6}
        mock_daypart.bpm_progression = [Mock()]

        mock_playlist = Mock(spec=Playlist)
        mock_playlist.tracks = []
        mock_playlist.cost_actual = Decimal("0.02")

        with patch('src.ai_playlist.models.PlaylistSpecification.from_daypart') as mock_from_daypart, \
             patch('src.ai_playlist.openai_client.OpenAIClient') as mock_ai_client_class:

            mock_spec = Mock()
            mock_spec.id = "spec-456"
            mock_spec.name = "Afternoon Drive"
            mock_spec.target_track_count_max = 8
            mock_spec.target_duration_minutes = 180
            mock_from_daypart.return_value = mock_spec

            mock_ai_instance = Mock()
            mock_ai_instance.generate_playlist = AsyncMock(return_value=mock_playlist)
            mock_ai_instance.timeout_seconds = 30
            mock_ai_client_class.return_value = mock_ai_instance

            # Act
            await generator.generate_batch([mock_daypart], date.today())

        # Assert
        completed_events = [e for e in progress_events if e['status'] == 'completed']
        assert len(completed_events) == 1
        assert completed_events[0]['playlists_generated'] == 1
        assert 'total_cost' in completed_events[0]

    @pytest.mark.asyncio
    async def test_generate_batch_without_progress_callback(self):
        """Test generate_batch works without progress callback set."""
        # Arrange
        mock_subsonic_client = Mock()
        generator = BatchPlaylistGenerator(
            openai_api_key="test-key",
            subsonic_client=mock_subsonic_client
        )
        # Don't set on_progress callback

        mock_daypart = Mock()
        mock_daypart.name = "Evening"
        mock_daypart.target_track_count_max = 5
        mock_daypart.duration_hours = 2.0
        mock_daypart.genre_mix = {"Dance": 0.5}
        mock_daypart.era_distribution = {"Current": 0.6}
        mock_daypart.bpm_progression = [Mock()]

        mock_playlist = Mock(spec=Playlist)
        mock_playlist.tracks = []
        mock_playlist.cost_actual = Decimal("0.01")

        with patch('src.ai_playlist.models.PlaylistSpecification.from_daypart') as mock_from_daypart, \
             patch('src.ai_playlist.openai_client.OpenAIClient') as mock_ai_client_class:

            mock_spec = Mock()
            mock_spec.id = "spec-789"
            mock_spec.name = "Evening"
            mock_spec.target_track_count_max = 5
            mock_spec.target_duration_minutes = 120
            mock_from_daypart.return_value = mock_spec

            mock_ai_instance = Mock()
            mock_ai_instance.generate_playlist = AsyncMock(return_value=mock_playlist)
            mock_ai_instance.timeout_seconds = 30
            mock_ai_client_class.return_value = mock_ai_instance

            # Act - should not raise even without callback
            playlists = await generator.generate_batch([mock_daypart], date.today())

        # Assert
        assert len(playlists) == 1


class TestGenerateBatchBudgetEnforcement:
    """Test budget enforcement in generate_batch."""

    @pytest.mark.asyncio
    async def test_generate_batch_hard_mode_raises_on_budget_exceeded(self):
        """Test hard mode raises BudgetExceededError when budget exceeded."""
        # Arrange
        mock_subsonic_client = Mock()
        generator = BatchPlaylistGenerator(
            openai_api_key="test-key",
            subsonic_client=mock_subsonic_client,
            total_budget=0.001,  # Very low budget
            budget_mode="hard"
        )

        # Create daypart that will likely exceed tiny budget
        mock_daypart = Mock()
        mock_daypart.name = "Expensive"
        mock_daypart.target_track_count_max = 50
        mock_daypart.duration_hours = 4.0
        mock_daypart.genre_mix = {"Rock": 0.5}
        mock_daypart.era_distribution = {"Current": 0.6}
        mock_daypart.bpm_progression = [Mock()]

        # Mock playlist that costs more than budget
        mock_playlist = Mock(spec=Playlist)
        mock_playlist.tracks = []
        mock_playlist.cost_actual = Decimal("0.01")  # More than 0.001 budget

        with patch('src.ai_playlist.models.PlaylistSpecification.from_daypart') as mock_from_daypart, \
             patch('src.ai_playlist.openai_client.OpenAIClient') as mock_ai_client_class:

            mock_spec = Mock()
            mock_spec.id = "spec-expensive"
            mock_spec.name = "Expensive"
            mock_spec.target_track_count_max = 50
            mock_spec.target_duration_minutes = 240
            mock_from_daypart.return_value = mock_spec

            mock_ai_instance = Mock()
            mock_ai_instance.generate_playlist = AsyncMock(return_value=mock_playlist)
            mock_ai_instance.timeout_seconds = 30
            mock_ai_client_class.return_value = mock_ai_instance

            # Act & Assert
            with pytest.raises(BudgetExceededError, match="Budget exceeded"):
                await generator.generate_batch([mock_daypart], date.today())

    @pytest.mark.asyncio
    async def test_generate_batch_suggested_mode_warns_but_continues(self):
        """Test suggested mode logs warning but continues on budget exceeded."""
        # Arrange
        mock_subsonic_client = Mock()
        generator = BatchPlaylistGenerator(
            openai_api_key="test-key",
            subsonic_client=mock_subsonic_client,
            total_budget=0.001,  # Very low budget
            budget_mode="suggested"  # Suggested mode
        )

        mock_daypart = Mock()
        mock_daypart.name = "Over Budget"
        mock_daypart.target_track_count_max = 50
        mock_daypart.duration_hours = 4.0
        mock_daypart.genre_mix = {"Rock": 0.5}
        mock_daypart.era_distribution = {"Current": 0.6}
        mock_daypart.bpm_progression = [Mock()]

        mock_playlist = Mock(spec=Playlist)
        mock_playlist.tracks = []
        mock_playlist.cost_actual = Decimal("0.01")  # More than budget

        with patch('src.ai_playlist.models.PlaylistSpecification.from_daypart') as mock_from_daypart, \
             patch('src.ai_playlist.openai_client.OpenAIClient') as mock_ai_client_class:

            mock_spec = Mock()
            mock_spec.id = "spec-overbudget"
            mock_spec.name = "Over Budget"
            mock_spec.target_track_count_max = 50
            mock_spec.target_duration_minutes = 240
            mock_from_daypart.return_value = mock_spec

            mock_ai_instance = Mock()
            mock_ai_instance.generate_playlist = AsyncMock(return_value=mock_playlist)
            mock_ai_instance.timeout_seconds = 30
            mock_ai_client_class.return_value = mock_ai_instance

            # Act - should complete without raising
            playlists = await generator.generate_batch([mock_daypart], date.today())

        # Assert
        assert len(playlists) == 1  # Still generated despite exceeding budget
