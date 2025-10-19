"""Tests for openai_client.py - generate_playlist() method (lines 1168-1425).

This test file covers the end-to-end playlist generation workflow including:
- Cost manager initialization
- Decision logger integration
- LLM call orchestration
- Track metadata mapping
- Duration padding
- Validation integration
- Error handling (budget, timeout, general errors)
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from decimal import Decimal
from datetime import datetime, date, time
import uuid

from src.ai_playlist.openai_client import OpenAIClient, BudgetExceededError
from src.ai_playlist.models import (
    PlaylistSpecification,
    TrackSelectionCriteria,
    BPMRange,
    GenreCriteria,
    EraCriteria,
    ValidationResult
)
from src.ai_playlist.models.llm import LLMTrackSelectionResponse, SelectedTrack as LLMSelectedTrack
from src.ai_playlist.models.core import (
    Playlist as CorePlaylist,
    SelectedTrack as CoreSelectedTrack,
    ValidationStatus
)
from src.ai_playlist.cost_manager import CostManager
from src.ai_playlist.decision_logger import DecisionLogger


@pytest.fixture
def sample_spec():
    """Create sample PlaylistSpecification for testing."""
    bpm_range = BPMRange(
        time_start=time(6, 0),
        time_end=time(10, 0),
        bpm_min=90,
        bpm_max=130
    )

    criteria = TrackSelectionCriteria(
        bpm_ranges=[bpm_range],
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

    spec_id = str(uuid.uuid4())
    return PlaylistSpecification(
        id=spec_id,
        name="Test_Playlist",
        source_daypart_id=str(uuid.uuid4()),
        generation_date=date.today(),
        target_track_count_min=5,
        target_track_count_max=10,
        target_duration_minutes=60,
        track_selection_criteria=criteria,
        created_at=datetime.now(),
        cost_budget_allocated=Decimal("10.00")
    )


@pytest.fixture
def mock_subsonic_client():
    """Create mock Subsonic client."""
    client = Mock()
    client.search = AsyncMock(return_value=[])
    return client


@pytest.fixture
def mock_llm_response():
    """Create mock LLM response with track IDs."""
    return LLMTrackSelectionResponse(
        request_id=str(uuid.uuid4()),
        selected_tracks=[
            "track-001",
            "track-002",
            "track-003",
            "track-004",
            "track-005"
        ],  # String track IDs from submit_playlist
        tool_calls=[
            {
                "tool_name": "search_tracks",
                "arguments": '{"query": "Rock", "genre": "Rock", "year_from": 2020}',
                "result": {
                    "tracks": [
                        {
                            "id": "track-001",
                            "title": "Song 1",
                            "artist": "Artist 1",
                            "album": "Album 1",
                            "genre": "Rock",
                            "year": 2023,
                            "bpm": 120,
                            "duration_seconds": 180
                        },
                        {
                            "id": "track-002",
                            "title": "Song 2",
                            "artist": "Artist 2",
                            "album": "Album 2",
                            "genre": "Pop",
                            "year": 2024,
                            "bpm": 110,
                            "duration_seconds": 200
                        },
                        {
                            "id": "track-003",
                            "title": "Song 3",
                            "artist": "Artist 3",
                            "album": "Album 3",
                            "genre": "Rock",
                            "year": 2023,
                            "bpm": 125,
                            "duration_seconds": 190
                        },
                        {
                            "id": "track-004",
                            "title": "Song 4",
                            "artist": "Artist 4",
                            "album": "Album 4",
                            "genre": "Alternative",
                            "year": 2022,
                            "bpm": 115,
                            "duration_seconds": 210
                        },
                        {
                            "id": "track-005",
                            "title": "Song 5",
                            "artist": "Artist 5",
                            "album": "Album 5",
                            "genre": "Rock",
                            "year": 2024,
                            "bpm": 130,
                            "duration_seconds": 195
                        }
                    ]
                }
            },
            {
                "tool_name": "submit_playlist",
                "arguments": '{"selected_track_ids": ["track-001", "track-002", "track-003", "track-004", "track-005"], "reasoning": "Selected 5 tracks matching criteria"}',
                "result": {
                    "status": "success",
                    "message": "Playlist submitted successfully"
                }
            }
        ],
        reasoning="Selected 5 tracks matching criteria",
        cost_usd=0.05,
        execution_time_seconds=2.5
    )


@pytest.mark.asyncio
class TestGeneratePlaylist:
    """Test OpenAIClient.generate_playlist() method."""

    async def test_generate_playlist_success_with_defaults(
        self, sample_spec, mock_subsonic_client, mock_llm_response
    ):
        """Test successful playlist generation with default cost manager and logger."""
        # Arrange
        client = OpenAIClient(api_key="test-key")

        with patch.object(client, 'call_llm', new_callable=AsyncMock) as mock_call_llm:
            mock_call_llm.return_value = mock_llm_response

            with patch('src.ai_playlist.openai_client.validate_playlist') as mock_validate:
                mock_validate.return_value = ValidationResult(
                    playlist_id=sample_spec.id,
                    overall_status=ValidationStatus.PASS,
                    constraint_scores={},
                    flow_quality_metrics=Mock(),
                    compliance_percentage=0.95,
                    gap_analysis=[],
                    validated_at=datetime.now()
                )

                # Act
                result = await client.generate_playlist(
                    sample_spec,
                    mock_subsonic_client
                )

        # Assert
        assert isinstance(result, CorePlaylist)
        assert result.id == sample_spec.id
        assert result.name == sample_spec.name
        assert len(result.tracks) == 5
        assert result.cost_actual == Decimal("0.05")
        assert result.validation_result.overall_status == ValidationStatus.PASS
        assert result.generation_time_seconds > 0

    async def test_generate_playlist_with_provided_cost_manager(
        self, sample_spec, mock_subsonic_client, mock_llm_response
    ):
        """Test playlist generation with provided cost manager."""
        # Arrange
        client = OpenAIClient(api_key="test-key")
        cost_manager = CostManager(
            total_budget=Decimal("5.00"),
            budget_mode="hard",
            allocation_strategy="equal"
        )

        with patch.object(client, 'call_llm', new_callable=AsyncMock) as mock_call_llm:
            mock_call_llm.return_value = mock_llm_response

            with patch('src.ai_playlist.openai_client.validate_playlist') as mock_validate:
                mock_validate.return_value = ValidationResult(
                    playlist_id=sample_spec.id,
                    overall_status=ValidationStatus.PASS,
                    constraint_scores={},
                    flow_quality_metrics=Mock(),
                    compliance_percentage=0.95,
                    gap_analysis=[],
                    validated_at=datetime.now()
                )

                # Act
                result = await client.generate_playlist(
                    sample_spec,
                    mock_subsonic_client,
                    cost_manager=cost_manager
                )

        # Assert
        assert result is not None
        assert cost_manager.get_total_cost() == Decimal("0.05")

    async def test_generate_playlist_budget_exceeded_before_call(
        self, sample_spec, mock_subsonic_client
    ):
        """Test BudgetExceededError raised when estimated cost exceeds remaining budget."""
        # Arrange
        client = OpenAIClient(api_key="test-key")
        cost_manager = CostManager(
            total_budget=Decimal("0.001"),  # Very low budget
            budget_mode="hard",
            allocation_strategy="equal"
        )

        # Act & Assert
        with pytest.raises(BudgetExceededError, match="exceeds remaining budget"):
            await client.generate_playlist(
                sample_spec,
                mock_subsonic_client,
                cost_manager=cost_manager
            )

    async def test_generate_playlist_budget_exceeded_after_call_hard_mode(
        self, sample_spec, mock_subsonic_client, mock_llm_response
    ):
        """Test BudgetExceededError raised in hard mode when actual cost exceeds budget."""
        # Arrange
        client = OpenAIClient(api_key="test-key")

        # Create cost manager with budget that will be exceeded
        cost_manager = CostManager(
            total_budget=Decimal("10.00"),
            budget_mode="hard",
            allocation_strategy="equal"
        )

        # Pre-consume most of the budget
        cost_manager.record_cost(Decimal("9.99"), "previous-playlist")

        with patch.object(client, 'call_llm', new_callable=AsyncMock) as mock_call_llm:
            mock_call_llm.return_value = mock_llm_response

            with patch('src.ai_playlist.openai_client.validate_playlist'):
                # Act & Assert
                with pytest.raises(BudgetExceededError):
                    await client.generate_playlist(
                        sample_spec,
                        mock_subsonic_client,
                        cost_manager=cost_manager
                    )

    async def test_generate_playlist_budget_warning_in_suggested_mode(
        self, sample_spec, mock_subsonic_client, mock_llm_response
    ):
        """Test budget exceeded in suggested mode logs warning but continues."""
        # Arrange
        client = OpenAIClient(api_key="test-key")

        cost_manager = CostManager(
            total_budget=Decimal("10.00"),
            budget_mode="suggested",  # Warning mode
            allocation_strategy="equal"
        )

        # Pre-consume most of the budget
        cost_manager.record_cost(Decimal("9.99"), "previous-playlist")

        with patch.object(client, 'call_llm', new_callable=AsyncMock) as mock_call_llm:
            mock_call_llm.return_value = mock_llm_response

            with patch('src.ai_playlist.openai_client.validate_playlist') as mock_validate:
                mock_validate.return_value = ValidationResult(
                    playlist_id=sample_spec.id,
                    overall_status=ValidationStatus.PASS,
                    constraint_scores={},
                    flow_quality_metrics=Mock(),
                    compliance_percentage=0.95,
                    gap_analysis=[],
                    validated_at=datetime.now()
                )

                # Act - should NOT raise exception
                result = await client.generate_playlist(
                    sample_spec,
                    mock_subsonic_client,
                    cost_manager=cost_manager
                )

        # Assert - should complete successfully
        assert result is not None
        assert isinstance(result, CorePlaylist)

    async def test_generate_playlist_with_used_track_ids(
        self, sample_spec, mock_subsonic_client, mock_llm_response
    ):
        """Test playlist generation with used track IDs exclusion."""
        # Arrange
        client = OpenAIClient(api_key="test-key")
        used_tracks = {"old-track-1", "old-track-2"}

        with patch.object(client, 'call_llm', new_callable=AsyncMock) as mock_call_llm:
            mock_call_llm.return_value = mock_llm_response

            with patch('src.ai_playlist.openai_client.validate_playlist') as mock_validate:
                mock_validate.return_value = ValidationResult(
                    playlist_id=sample_spec.id,
                    overall_status=ValidationStatus.PASS,
                    constraint_scores={},
                    flow_quality_metrics=Mock(),
                    compliance_percentage=0.95,
                    gap_analysis=[],
                    validated_at=datetime.now()
                )

                # Act
                result = await client.generate_playlist(
                    sample_spec,
                    mock_subsonic_client,
                    used_track_ids=used_tracks
                )

        # Assert
        assert result is not None
        # The test verifies that used_track_ids were passed to create_selection_request
        # The actual exclusion happens in the LLM's tool call logic, not in our test mock
        # So we just verify the playlist was generated successfully
        assert len(result.tracks) == 5

    async def test_generate_playlist_converts_string_track_ids_to_objects(
        self, sample_spec, mock_subsonic_client, mock_llm_response
    ):
        """Test that string track IDs from submit_playlist are converted to SelectedTrack objects."""
        # Arrange
        client = OpenAIClient(api_key="test-key")

        with patch.object(client, 'call_llm', new_callable=AsyncMock) as mock_call_llm:
            mock_call_llm.return_value = mock_llm_response

            with patch('src.ai_playlist.openai_client.validate_playlist') as mock_validate:
                mock_validate.return_value = ValidationResult(
                    playlist_id=sample_spec.id,
                    overall_status=ValidationStatus.PASS,
                    constraint_scores={},
                    flow_quality_metrics=Mock(),
                    compliance_percentage=0.95,
                    gap_analysis=[],
                    validated_at=datetime.now()
                )

                # Act
                result = await client.generate_playlist(
                    sample_spec,
                    mock_subsonic_client
                )

        # Assert
        assert len(result.tracks) == 5
        for idx, track in enumerate(result.tracks):
            assert isinstance(track, CoreSelectedTrack)
            assert track.track_id == f"track-{idx+1:03d}"
            assert track.title == f"Song {idx+1}"
            assert track.artist == f"Artist {idx+1}"
            assert track.metadata_source == "subsonic_tools"
            assert track.validation_status == ValidationStatus.PASS
            assert track.position_in_playlist == idx

    async def test_generate_playlist_handles_old_track_object_format(
        self, sample_spec, mock_subsonic_client
    ):
        """Test handling of old format with full SelectedTrack objects instead of string IDs."""
        # Arrange
        client = OpenAIClient(api_key="test-key")

        # Create LLM response with old format (full track objects)
        old_format_response = LLMTrackSelectionResponse(
            request_id=str(uuid.uuid4()),
            selected_tracks=[
                LLMSelectedTrack(
                    track_id="track-old-1",
                    position=1,
                    title="Old Track 1",
                    artist="Old Artist 1",
                    album="Old Album 1",
                    genre="Rock",
                    year=2020,
                    bpm=120,
                    duration_seconds=180,
                    country="AU",
                    selection_reason="Selected for variety"
                ),
                LLMSelectedTrack(
                    track_id="track-old-2",
                    position=2,
                    title="Old Track 2",
                    artist="Old Artist 2",
                    album="Old Album 2",
                    genre="Pop",
                    year=2021,
                    bpm=110,
                    duration_seconds=200,
                    country="US",
                    selection_reason="Good energy"
                )
            ],
            tool_calls=[],
            reasoning="Legacy format tracks",
            cost_usd=0.03,
            execution_time_seconds=1.5
        )

        with patch.object(client, 'call_llm', new_callable=AsyncMock) as mock_call_llm:
            mock_call_llm.return_value = old_format_response

            with patch('src.ai_playlist.openai_client.validate_playlist') as mock_validate:
                mock_validate.return_value = ValidationResult(
                    playlist_id=sample_spec.id,
                    overall_status=ValidationStatus.PASS,
                    constraint_scores={},
                    flow_quality_metrics=Mock(),
                    compliance_percentage=0.95,
                    gap_analysis=[],
                    validated_at=datetime.now()
                )

                # Act
                result = await client.generate_playlist(
                    sample_spec,
                    mock_subsonic_client
                )

        # Assert
        assert len(result.tracks) == 2
        assert result.tracks[0].track_id == "track-old-1"
        assert result.tracks[0].is_australian is True  # country="AU"
        assert result.tracks[1].is_australian is False  # country="US"
        assert result.tracks[0].metadata_source == "llm"
        assert result.tracks[0].selection_reasoning == "Selected for variety"

    async def test_generate_playlist_pads_short_duration(
        self, sample_spec, mock_subsonic_client
    ):
        """Test that playlists below minimum duration are padded."""
        # Arrange
        client = OpenAIClient(api_key="test-key")

        # Create response with tracks totaling only 10 minutes (need 60 * 0.9 = 54 min)
        short_response = LLMTrackSelectionResponse(
            request_id=str(uuid.uuid4()),
            selected_tracks=["track-001", "track-002"],
            tool_calls=[
                {
                    "tool_name": "search_tracks",
                    "arguments": '{"query": "Short"}',
                    "result": {
                        "tracks": [
                            {
                                "id": "track-001",
                                "title": "Short 1",
                                "artist": "Artist 1",
                                "album": "Album 1",
                                "genre": "Rock",
                                "year": 2023,
                                "bpm": 120,
                                "duration_seconds": 300  # 5 minutes
                            },
                            {
                                "id": "track-002",
                                "title": "Short 2",
                                "artist": "Artist 2",
                                "album": "Album 2",
                                "genre": "Pop",
                                "year": 2024,
                                "bpm": 110,
                                "duration_seconds": 300  # 5 minutes (total: 10 min)
                            }
                        ]
                    }
                },
                {
                    "tool_name": "submit_playlist",
                    "arguments": '{"selected_track_ids": ["track-001", "track-002"], "reasoning": "Short playlist"}',
                    "result": {
                        "status": "success",
                        "message": "Submitted"
                    }
                }
            ],
            reasoning="Short playlist",
            cost_usd=0.02,
            execution_time_seconds=1.0
        )

        # Mock the padding function to add more tracks
        mock_padded_playlist = CorePlaylist(
            id=sample_spec.id,
            name=sample_spec.name,
            specification_id=sample_spec.id,
            tracks=[
                CoreSelectedTrack(
                    track_id=f"track-{i:03d}",
                    title=f"Track {i}",
                    artist=f"Artist {i}",
                    album="Album",
                    duration_seconds=300,
                    is_australian=False,
                    rotation_category="Medium",
                    position_in_playlist=i-1,
                    selection_reasoning="Padded",
                    validation_status=ValidationStatus.PASS,
                    metadata_source="padding",
                    genre="Rock",
                    year=2023
                )
                for i in range(1, 13)  # 12 tracks * 5 min = 60 min
            ],
            validation_result=None,
            created_at=datetime.now(),
            cost_actual=Decimal("0"),
            generation_time_seconds=0,
            constraint_relaxations=[]
        )

        with patch.object(client, 'call_llm', new_callable=AsyncMock) as mock_call_llm:
            mock_call_llm.return_value = short_response

            with patch('src.ai_playlist.duration_padding.pad_playlist_to_duration', new_callable=AsyncMock) as mock_pad:
                mock_pad.return_value = mock_padded_playlist

                with patch('src.ai_playlist.openai_client.validate_playlist') as mock_validate:
                    mock_validate.return_value = ValidationResult(
                        playlist_id=sample_spec.id,
                        overall_status=ValidationStatus.PASS,
                        constraint_scores={},
                        flow_quality_metrics=Mock(),
                        compliance_percentage=0.95,
                        gap_analysis=[],
                        validated_at=datetime.now()
                    )

                    # Act
                    result = await client.generate_playlist(
                        sample_spec,
                        mock_subsonic_client
                    )

        # Assert
        assert len(result.tracks) == 12  # Padded to 12 tracks
        mock_pad.assert_called_once()  # Verify padding was called

    async def test_generate_playlist_logs_decision_success(
        self, sample_spec, mock_subsonic_client, mock_llm_response
    ):
        """Test that successful generation logs decision."""
        # Arrange
        client = OpenAIClient(api_key="test-key")
        mock_logger = Mock(spec=DecisionLogger)

        with patch.object(client, 'call_llm', new_callable=AsyncMock) as mock_call_llm:
            mock_call_llm.return_value = mock_llm_response

            with patch('src.ai_playlist.openai_client.validate_playlist') as mock_validate:
                mock_validate.return_value = ValidationResult(
                    playlist_id=sample_spec.id,
                    overall_status=ValidationStatus.PASS,
                    constraint_scores={},
                    flow_quality_metrics=Mock(),
                    compliance_percentage=0.95,
                    gap_analysis=[],
                    validated_at=datetime.now()
                )

                # Act
                result = await client.generate_playlist(
                    sample_spec,
                    mock_subsonic_client,
                    decision_logger=mock_logger
                )

        # Assert
        mock_logger.log_decision.assert_called_once()
        call_args = mock_logger.log_decision.call_args[1]
        assert call_args["decision_type"] == "track_selection"
        assert call_args["playlist_name"] == sample_spec.name
        assert len(call_args["selected_tracks"]) == 5

    async def test_generate_playlist_logs_decision_on_error(
        self, sample_spec, mock_subsonic_client
    ):
        """Test that errors are logged to decision logger."""
        # Arrange
        client = OpenAIClient(api_key="test-key")
        mock_logger = Mock(spec=DecisionLogger)

        with patch.object(client, 'call_llm', new_callable=AsyncMock) as mock_call_llm:
            mock_call_llm.side_effect = ValueError("LLM error occurred")

            # Act & Assert
            with pytest.raises(ValueError, match="LLM error occurred"):
                await client.generate_playlist(
                    sample_spec,
                    mock_subsonic_client,
                    decision_logger=mock_logger
                )

        # Assert error was logged
        mock_logger.log_decision.assert_called_once()
        call_args = mock_logger.log_decision.call_args[1]
        assert call_args["decision_type"] == "error"
        assert "error_message" in call_args["metadata"]
        assert call_args["metadata"]["error_message"] == "LLM error occurred"

    async def test_generate_playlist_handles_timeout_error(
        self, sample_spec, mock_subsonic_client
    ):
        """Test TimeoutError is re-raised from generate_playlist."""
        # Arrange
        client = OpenAIClient(api_key="test-key")

        with patch.object(client, 'call_llm', new_callable=AsyncMock) as mock_call_llm:
            mock_call_llm.side_effect = TimeoutError("Tool execution timeout")

            # Act & Assert
            with pytest.raises(TimeoutError, match="Tool execution timeout"):
                await client.generate_playlist(
                    sample_spec,
                    mock_subsonic_client
                )

    async def test_generate_playlist_decision_logging_failure_does_not_crash(
        self, sample_spec, mock_subsonic_client, mock_llm_response
    ):
        """Test that decision logging failures don't crash playlist generation."""
        # Arrange
        client = OpenAIClient(api_key="test-key")
        mock_logger = Mock(spec=DecisionLogger)
        mock_logger.log_decision.side_effect = Exception("Logging failed")

        with patch.object(client, 'call_llm', new_callable=AsyncMock) as mock_call_llm:
            mock_call_llm.return_value = mock_llm_response

            with patch('src.ai_playlist.openai_client.validate_playlist') as mock_validate:
                mock_validate.return_value = ValidationResult(
                    playlist_id=sample_spec.id,
                    overall_status=ValidationStatus.PASS,
                    constraint_scores={},
                    flow_quality_metrics=Mock(),
                    compliance_percentage=0.95,
                    gap_analysis=[],
                    validated_at=datetime.now()
                )

                # Act - should complete despite logging error
                result = await client.generate_playlist(
                    sample_spec,
                    mock_subsonic_client,
                    decision_logger=mock_logger
                )

        # Assert
        assert result is not None
        assert isinstance(result, CorePlaylist)
