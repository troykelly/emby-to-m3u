"""
Comprehensive Integration Tests for main.py Workflow Orchestration

Tests complete automation workflow from document parsing to AzuraCast sync,
covering happy paths, error paths, edge cases, and all workflow combinations.
All external dependencies are mocked for deterministic testing.
"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime
import json

from src.ai_playlist.main import run_automation
from src.ai_playlist.models import (
    DaypartSpec,
    PlaylistSpec,
    TrackSelectionCriteria,
    SelectedTrack,
    Playlist,
    LLMTrackSelectionResponse,
)
from src.ai_playlist.models.validation import ValidationResult, ConstraintScores, FlowMetrics
from src.ai_playlist.exceptions import (
    ParseError,
    ValidationError,
    CostExceededError,
    MCPToolError,
)
from src.ai_playlist.azuracast_sync import AzuraCastPlaylistSyncError


# ============================================================================
# Fixtures - Realistic Test Data
# ============================================================================


@pytest.fixture
def sample_programming_document():
    """Sample programming document content."""
    return """# Station Identity - Contemporary Radio Station

## Monday Morning Drive (06:00-10:00)
- BPM: 110-140
- Genre Mix: Alternative 45%, Electronic 35%, Quality Pop 20%
- Era: Current (0-2 years) 60%, Recent (3-5 years) 40%
- Australian Content: 30% minimum
- Mood: Energetic, uplifting
- Tracks per hour: 15
"""


@pytest.fixture
def sample_dayparts():
    """Sample parsed dayparts."""
    return [
        DaypartSpec(
            name="Monday_MorningDrive_0600_1000",
            day="Monday",
            time_range=("06:00", "10:00"),
            bpm_progression={"06:00-10:00": (110, 140)},
            genre_mix={"Alternative": 0.45, "Electronic": 0.35, "Quality Pop": 0.20},
            era_distribution={"Current (0-2 years)": 0.60, "Recent (3-5 years)": 0.40},
            australian_min=0.30,
            mood="energetic",
            tracks_per_hour=15,
        ),
        DaypartSpec(
            name="Monday_Midday_1000_1400",
            day="Monday",
            time_range=("10:00", "14:00"),
            bpm_progression={"10:00-14:00": (95, 125)},
            genre_mix={"Alternative": 0.40, "Quality Pop": 0.35, "Electronic": 0.25},
            era_distribution={"Current (0-2 years)": 0.50, "Recent (3-5 years)": 0.50},
            australian_min=0.30,
            mood="relaxed",
            tracks_per_hour=14,
        ),
    ]


@pytest.fixture
def sample_playlist_specs(sample_dayparts):
    """Sample playlist specifications."""
    specs = []
    for daypart in sample_dayparts:
        spec = PlaylistSpec(
            id="12345678-{daypart.name}",
            name=daypart.name,
            daypart=daypart,
            track_criteria=TrackSelectionCriteria(
                bpm_range=daypart.bpm_progression[list(daypart.bpm_progression.keys())[0]],
                bpm_tolerance=10,
                genre_mix={g: (v - 0.05, v + 0.05) for g, v in daypart.genre_mix.items()},
                genre_tolerance=0.05,
                era_distribution={
                    e: (v - 0.05, v + 0.05) for e, v in daypart.era_distribution.items()
                },
                era_tolerance=0.05,
                australian_min=daypart.australian_min,
                energy_flow=daypart.mood,
            ),
            target_duration_minutes=240,
            created_at=datetime.now(),
        )
        specs.append(spec)
    return specs


@pytest.fixture
def sample_tracks():
    """Sample selected tracks based on fixture data."""
    # Load from fixtures/mock_track_metadata.json
    tracks = [
        SelectedTrack(
            track_id="AU001",
            title="Midnight Run",
            artist="The Temper Trap",
            album="Trembling Hands",
            bpm=128,
            genre="Alternative",
            year=2024,
            country="Australia",
            duration_seconds=243,
            position=1,
            selection_reason="High energy Australian track for morning drive",
        ),
        SelectedTrack(
            track_id="AU002",
            title="Electric Dreams",
            artist="Flume",
            album="Things Don't Last",
            bpm=118,
            genre="Electronic",
            year=2023,
            country="Australia",
            duration_seconds=198,
            position=2,
            selection_reason="Electronic diversity, Australian content",
        ),
        SelectedTrack(
            track_id="US001",
            title="Starlight",
            artist="The Killers",
            album="Pressure Machine Deluxe",
            bpm=135,
            genre="Alternative",
            year=2024,
            country="USA",
            duration_seconds=254,
            position=3,
            selection_reason="High BPM alternative track for energy flow",
        ),
    ]

    # Extend to 60 tracks for realistic playlist
    extended_tracks = []
    for i in range(60):
        track = tracks[i % len(tracks)]
        extended_tracks.append(
            SelectedTrack(
                track_id=f"{track.track_id}_{i}",
                title=f"{track.title} {i}",
                artist=track.artist,
                album=track.album,
                bpm=track.bpm + (i % 5) - 2,  # Slight BPM variation
                genre=track.genre,
                year=track.year,
                country=track.country,
                duration_seconds=track.duration_seconds,
                position=i + 1,
                selection_reason=track.selection_reason,
            )
        )
    return extended_tracks


@pytest.fixture
def valid_validation_result():
    """Valid validation result passing all constraints."""
    return ValidationResult(
        constraint_scores=ConstraintScores(
            constraint_satisfaction=0.87,
            bpm_satisfaction=0.92,
            genre_satisfaction=0.88,
            era_satisfaction=0.84,
            australian_content=0.35,
        ),
        flow_metrics=FlowMetrics(
            flow_quality_score=0.82,
            bpm_variance=8.3,
            energy_progression="smooth",
            genre_diversity=0.76,
        ),
        gap_analysis={},
        passes_validation=True,
    )


@pytest.fixture
def failed_validation_result():
    """Failed validation result (constraint satisfaction <80%)."""
    return ValidationResult(
        constraint_scores=ConstraintScores(
            constraint_satisfaction=0.72,  # Below 80% threshold
            bpm_satisfaction=0.65,
            genre_satisfaction=0.75,
            era_satisfaction=0.78,
            australian_content=0.18,  # Below 30% minimum
        ),
        flow_metrics=FlowMetrics(
            flow_quality_score=0.68,
            bpm_variance=18.5,
            energy_progression="choppy",  # Valid value: 'smooth', 'choppy', 'monotone'
            genre_diversity=0.45,
        ),
        gap_analysis={"australian_content": "18% < 30% minimum"},
        passes_validation=False,
    )


@pytest.fixture
def mock_decision_logger():
    """Mock decision logger."""
    logger = Mock()
    logger.get_log_file.return_value = Path("/tmp/test/decisions/log.jsonl")
    logger.log_decision = Mock()
    return logger


# ============================================================================
# Happy Path Tests - Complete Workflow Success
# ============================================================================


@pytest.mark.asyncio
class TestCompleteWorkflowHappyPath:
    """Test successful end-to-end workflow execution."""

    async def test_complete_workflow_single_playlist(
        self, tmp_path, sample_programming_document, sample_dayparts, sample_tracks, valid_validation_result
    ):
        """Test complete workflow with single playlist - parse → generate → select → validate → sync."""
        # Setup
        input_file = tmp_path / "station-identity.md"
        input_file.write_text(sample_programming_document)
        output_dir = tmp_path / "output"

        # Mock all workflow steps
        with patch("src.ai_playlist.main.parse_programming_document", return_value=[sample_dayparts[0]]):
            with patch("src.ai_playlist.main.generate_playlist_specs") as mock_gen_specs:
                spec = sample_dayparts[0]
                mock_spec = Mock()
                mock_spec.id = "12345678-1234-4123-8123-1234567890ab"
                mock_spec.name = "Monday_MorningDrive_0600_1000"
                mock_spec.target_duration_minutes = 240
                mock_spec.daypart = spec
                mock_spec.track_criteria = TrackSelectionCriteria(
                    bpm_range=(110, 140),
                    bpm_tolerance=10,
                    genre_mix={"Alternative": (0.40, 0.50)},
                    genre_tolerance=0.05,
                    era_distribution={"Current (0-2 years)": (0.55, 0.65)},
                    era_tolerance=0.05,
                    australian_min=0.30,
                    energy_flow="energetic",
                )
                mock_gen_specs.return_value = [mock_spec]

                with patch("src.ai_playlist.main.configure_and_verify_mcp", new=AsyncMock()):
                    with patch("src.ai_playlist.workflow.select_tracks_with_llm", new=AsyncMock()) as mock_select:
                        # Mock LLM response
                        mock_response = LLMTrackSelectionResponse(                            request_id="12345678-1234-4123-8123-123456789012",
                            selected_tracks=sample_tracks,
                            tool_calls=[{"tool_name": "search_tracks", "arguments": {}, "result": {}}],
                            reasoning="Selected diverse tracks matching criteria",
                            cost_usd=0.008,
                            execution_time_seconds=4.2,)
                        mock_select.return_value = mock_response

                        with patch("src.ai_playlist.workflow.validate_playlist", return_value=valid_validation_result):
                            with patch("src.ai_playlist.workflow.sync_playlist_to_azuracast", new=AsyncMock()) as mock_sync:
                                mock_synced = Mock()
                                mock_synced.azuracast_id = 456
                                mock_sync.return_value = mock_synced

                                # Execute
                                summary = await run_automation(
                                    input_file=str(input_file),
                                    output_dir=str(output_dir),
                                    max_cost_usd=0.50,
                                    dry_run=False,
                                )

        # Verify
        assert summary["playlist_count"] == 1
        assert summary["success_count"] == 1
        assert summary["failed_count"] == 0
        assert summary["total_cost"] > 0
        assert summary["total_time"] > 0
        assert len(summary["output_files"]) == 1
        assert "decision_log" in summary

        # Verify file was created
        playlist_file = output_dir / "Monday_MorningDrive_0600_1000.json"
        assert playlist_file.exists()

        # Verify JSON content
        with open(playlist_file) as f:
            playlist_data = json.load(f)
        assert playlist_data["name"] == "Monday_MorningDrive_0600_1000"
        assert len(playlist_data["tracks"]) == 60
        assert playlist_data["validation"]["constraint_scores"]["constraint_satisfaction"] == 0.87

        # Verify sync was called
        mock_sync.assert_called_once()

    async def test_complete_workflow_multiple_playlists(
        self, tmp_path, sample_programming_document, sample_dayparts, sample_tracks, valid_validation_result
    ):
        """Test workflow with multiple playlists processed in batch."""
        input_file = tmp_path / "station-identity.md"
        input_file.write_text(sample_programming_document)
        output_dir = tmp_path / "output"

        # Create specs for both dayparts
        specs = []
        for i, daypart in enumerate(sample_dayparts):
            spec = Mock()
            spec.id = f"12345678-1234-4123-8123-12345678{i:04d}"
            spec.name = daypart.name
            spec.target_duration_minutes = 240
            spec.daypart = daypart
            spec.track_criteria = TrackSelectionCriteria(
                bpm_range=(110, 140),
                bpm_tolerance=10,
                genre_mix={"Alternative": (0.40, 0.50)},
                genre_tolerance=0.05,
                era_distribution={"Current (0-2 years)": (0.55, 0.65)},
                era_tolerance=0.05,
                australian_min=0.30,
                energy_flow="energetic",
            )
            specs.append(spec)

        with patch("src.ai_playlist.main.parse_programming_document", return_value=sample_dayparts):
            with patch("src.ai_playlist.main.generate_playlist_specs", return_value=specs):
                with patch("src.ai_playlist.main.configure_and_verify_mcp", new=AsyncMock()):
                    with patch("src.ai_playlist.workflow.select_tracks_with_llm", new=AsyncMock()) as mock_select:
                        mock_response = LLMTrackSelectionResponse(                            request_id="12345678-1234-4123-8123-123456789012",
                            selected_tracks=sample_tracks,
                            tool_calls=[{"tool_name": "search_tracks", "arguments": {}, "result": {}}],
                            reasoning="Test",
                            cost_usd=0.008,
                            execution_time_seconds=4.2,)
                        mock_select.return_value = mock_response

                        with patch("src.ai_playlist.workflow.validate_playlist", return_value=valid_validation_result):
                            with patch("src.ai_playlist.workflow.sync_playlist_to_azuracast", new=AsyncMock()) as mock_sync:
                                mock_synced = Mock()
                                mock_synced.azuracast_id = 789
                                mock_sync.return_value = mock_synced

                                summary = await run_automation(
                                    input_file=str(input_file),
                                    output_dir=str(output_dir),
                                    max_cost_usd=0.50,
                                    dry_run=False,
                                )

        assert summary["playlist_count"] == 2
        assert summary["success_count"] == 2
        assert summary["failed_count"] == 0
        assert len(summary["output_files"]) == 2

        # Verify both playlists created
        assert (output_dir / "Monday_Morning_Drive.json").exists()
        assert (output_dir / "Monday_Midday.json").exists()

        # Verify sync called twice
        assert mock_sync.call_count == 2

    async def test_workflow_dry_run_skips_sync(
        self, tmp_path, sample_programming_document, sample_dayparts, sample_tracks, valid_validation_result
    ):
        """Test dry run mode skips AzuraCast sync but completes other steps."""
        input_file = tmp_path / "station-identity.md"
        input_file.write_text(sample_programming_document)
        output_dir = tmp_path / "output"

        with patch("src.ai_playlist.main.parse_programming_document", return_value=[sample_dayparts[0]]):
            with patch("src.ai_playlist.main.generate_playlist_specs") as mock_gen:
                spec = Mock()
                spec.id = "12345678-1234-4123-8123-1234567890ab"
                spec.name = "Test_Dry_Run"
                spec.target_duration_minutes = 240
                spec.daypart = sample_dayparts[0]
                spec.track_criteria = Mock(bpm_tolerance=10)
                mock_gen.return_value = [spec]

                with patch("src.ai_playlist.main.configure_and_verify_mcp", new=AsyncMock()):
                    with patch("src.ai_playlist.workflow.select_tracks_with_llm", new=AsyncMock()) as mock_select:
                        mock_response = LLMTrackSelectionResponse(                            request_id="12345678-1234-4123-8123-123456789012",
                            selected_tracks=sample_tracks[:10],
                            tool_calls=[{"tool_name": "search_tracks", "arguments": {}, "result": {}}],
                            reasoning="Test",
                            cost_usd=0.005,
                            execution_time_seconds=3.0,)
                        mock_select.return_value = mock_response

                        with patch("src.ai_playlist.workflow.validate_playlist", return_value=valid_validation_result):
                            with patch("src.ai_playlist.workflow.sync_playlist_to_azuracast", new=AsyncMock()) as mock_sync:
                                summary = await run_automation(
                                    input_file=str(input_file),
                                    output_dir=str(output_dir),
                                    max_cost_usd=0.50,
                                    dry_run=True,  # DRY RUN MODE
                                )

        # Verify sync was NOT called
        mock_sync.assert_not_called()

        # Verify other steps completed
        assert summary["success_count"] == 1
        assert (output_dir / "Test_Dry_Run.json").exists()


# ============================================================================
# Error Path Tests - Parsing Failures
# ============================================================================


@pytest.mark.asyncio
class TestParsingErrorPaths:
    """Test error handling for document parsing failures."""

    async def test_missing_input_file_raises_error(self, tmp_path):
        """Test FileNotFoundError when input file doesn't exist."""
        with pytest.raises(FileNotFoundError, match="Programming document not found"):
            await run_automation(
                input_file="/nonexistent/file.md",
                output_dir=str(tmp_path / "output"),
                max_cost_usd=0.50,
                dry_run=True,
            )

    async def test_empty_programming_document_raises_error(self, tmp_path):
        """Test ValueError when programming document is empty."""
        input_file = tmp_path / "empty.md"
        input_file.write_text("")

        with pytest.raises(ValueError, match="Programming document is empty"):
            await run_automation(
                input_file=str(input_file),
                output_dir=str(tmp_path / "output"),
                max_cost_usd=0.50,
                dry_run=True,
            )

    async def test_parser_raises_parse_error(self, tmp_path, sample_programming_document):
        """Test ParseError propagation when document parsing fails."""
        input_file = tmp_path / "invalid.md"
        input_file.write_text(sample_programming_document)

        with patch("src.ai_playlist.main.parse_programming_document", side_effect=ParseError("Invalid format")):
            with pytest.raises(ParseError, match="Invalid format"):
                await run_automation(
                    input_file=str(input_file),
                    output_dir=str(tmp_path / "output"),
                    max_cost_usd=0.50,
                    dry_run=True,
                )

    async def test_no_dayparts_parsed_raises_error(self, tmp_path, sample_programming_document):
        """Test error when parser returns empty daypart list."""
        input_file = tmp_path / "test.md"
        input_file.write_text(sample_programming_document)

        with patch("src.ai_playlist.main.parse_programming_document", return_value=[]):
            # Should raise ValueError because ProgrammingDocument requires at least one daypart
            with pytest.raises(ValueError, match="Must contain at least one valid daypart"):
                await run_automation(
                    input_file=str(input_file),
                    output_dir=str(tmp_path / "output"),
                    max_cost_usd=0.50,
                    dry_run=True,
                )


# ============================================================================
# Error Path Tests - Validation Failures
# ============================================================================


@pytest.mark.asyncio
class TestValidationErrorPaths:
    """Test error handling for playlist validation failures."""

    async def test_all_playlists_fail_validation_raises_error(
        self, tmp_path, sample_programming_document, sample_dayparts, sample_tracks, failed_validation_result
    ):
        """Test ValidationError when all playlists fail validation (constraint <80%)."""
        input_file = tmp_path / "test.md"
        input_file.write_text(sample_programming_document)

        with patch("src.ai_playlist.main.parse_programming_document", return_value=[sample_dayparts[0]]):
            with patch("src.ai_playlist.main.generate_playlist_specs") as mock_gen:
                spec = Mock()
                spec.id = "12345678-1234-4123-8123-1234567890ab"
                spec.name = "Test_Failed"
                spec.target_duration_minutes = 240
                spec.daypart = sample_dayparts[0]
                spec.track_criteria = Mock(bpm_tolerance=10)
                mock_gen.return_value = [spec]

                with patch("src.ai_playlist.main.configure_and_verify_mcp", new=AsyncMock()):
                    with patch("src.ai_playlist.workflow.select_tracks_with_llm", new=AsyncMock()) as mock_select:
                        mock_response = LLMTrackSelectionResponse(                            request_id="12345678-1234-4123-8123-123456789012",
                            selected_tracks=sample_tracks[:10],
                            tool_calls=[{"tool_name": "search_tracks", "arguments": {}, "result": {}}],
                            reasoning="Test",
                            cost_usd=0.005,
                            execution_time_seconds=2.0,)
                        mock_select.return_value = mock_response

                        # All playlists fail validation
                        with patch("src.ai_playlist.workflow.validate_playlist", return_value=failed_validation_result):
                            with pytest.raises(ValidationError, match="No playlists passed validation"):
                                await run_automation(
                                    input_file=str(input_file),
                                    output_dir=str(tmp_path / "output"),
                                    max_cost_usd=0.50,
                                    dry_run=True,
                                )

    async def test_partial_validation_success_continues(
        self,
        tmp_path,
        sample_programming_document,
        sample_dayparts,
        sample_tracks,
        valid_validation_result,
        failed_validation_result,
    ):
        """Test workflow continues with valid playlists when some fail validation."""
        input_file = tmp_path / "test.md"
        input_file.write_text(sample_programming_document)

        # Create 3 specs
        specs = []
        for i in range(3):
            spec = Mock()
            spec.id = "12345678-1234-4123-8123-1234567890ab"
            spec.name = f"Playlist_{i}"
            spec.target_duration_minutes = 240
            spec.daypart = sample_dayparts[0]
            spec.track_criteria = Mock(bpm_tolerance=10)
            specs.append(spec)

        with patch("src.ai_playlist.main.parse_programming_document", return_value=sample_dayparts):
            with patch("src.ai_playlist.main.generate_playlist_specs", return_value=specs):
                with patch("src.ai_playlist.main.configure_and_verify_mcp", new=AsyncMock()):
                    with patch("src.ai_playlist.workflow.select_tracks_with_llm", new=AsyncMock()) as mock_select:
                        mock_response = LLMTrackSelectionResponse(                            request_id="12345678-1234-4123-8123-123456789012",
                            selected_tracks=sample_tracks[:20],
                            tool_calls=[{"tool_name": "search_tracks", "arguments": {}, "result": {}}],
                            reasoning="Test",
                            cost_usd=0.006,
                            execution_time_seconds=2.5,)
                        mock_select.return_value = mock_response

                        # First playlist fails, second and third pass
                        validation_results = [
                            failed_validation_result,
                            valid_validation_result,
                            valid_validation_result,
                        ]
                        with patch("src.ai_playlist.workflow.validate_playlist", side_effect=validation_results):
                            summary = await run_automation(
                                input_file=str(input_file),
                                output_dir=str(tmp_path / "output"),
                                max_cost_usd=0.50,
                                dry_run=True,
                            )

        # Verify partial success
        assert summary["playlist_count"] == 3
        assert summary["success_count"] == 2
        assert summary["failed_count"] == 1
        assert len(summary["output_files"]) == 2


# ============================================================================
# Error Path Tests - Cost Budget Exceeded
# ============================================================================


@pytest.mark.asyncio
class TestCostBudgetErrors:
    """Test cost budget enforcement and error handling."""

    async def test_cost_exceeded_raises_error(
        self, tmp_path, sample_programming_document, sample_dayparts, sample_tracks
    ):
        """Test CostExceededError when LLM cost exceeds budget."""
        input_file = tmp_path / "test.md"
        input_file.write_text(sample_programming_document)

        with patch("src.ai_playlist.main.parse_programming_document", return_value=[sample_dayparts[0]]):
            with patch("src.ai_playlist.main.generate_playlist_specs") as mock_gen:
                spec = Mock()
                spec.id = "12345678-1234-4123-8123-1234567890ab"
                spec.name = "Test_Cost"
                spec.target_duration_minutes = 240
                spec.daypart = sample_dayparts[0]
                spec.track_criteria = Mock(bpm_tolerance=10)
                mock_gen.return_value = [spec]

                with patch("src.ai_playlist.main.configure_and_verify_mcp", new=AsyncMock()):
                    with patch("src.ai_playlist.workflow.select_tracks_with_llm", new=AsyncMock()) as mock_select:
                        # Return response with cost exceeding budget
                        mock_response = LLMTrackSelectionResponse(
                            request_id="12345678-1234-4123-8123-123456789012",
                            selected_tracks=sample_tracks,
                            tool_calls=[{"tool_name": "search_tracks", "arguments": {}, "result": {}}],
                            reasoning="Expensive operation",
                            cost_usd=1.00,  # Exceeds $0.50 budget
                            execution_time_seconds=10.0,
                        )
                        mock_select.return_value = mock_response

                        with pytest.raises(CostExceededError, match="exceeds budget"):
                            await run_automation(
                                input_file=str(input_file),
                                output_dir=str(tmp_path / "output"),
                                max_cost_usd=0.50,
                                dry_run=True,
                            )

    async def test_budget_distributed_across_playlists(
        self, tmp_path, sample_programming_document, sample_dayparts, sample_tracks, valid_validation_result
    ):
        """Test budget is correctly distributed per playlist."""
        input_file = tmp_path / "test.md"
        input_file.write_text(sample_programming_document)

        # Create 5 playlists
        specs = []
        for i in range(5):
            spec = Mock()
            spec.id = "12345678-1234-4123-8123-1234567890ab"
            spec.name = f"Playlist_{i}"
            spec.target_duration_minutes = 240
            spec.daypart = sample_dayparts[0]
            spec.track_criteria = Mock(bpm_tolerance=10)
            specs.append(spec)

        with patch("src.ai_playlist.main.parse_programming_document", return_value=sample_dayparts):
            with patch("src.ai_playlist.main.generate_playlist_specs", return_value=specs):
                with patch("src.ai_playlist.main.configure_and_verify_mcp", new=AsyncMock()):
                    with patch("src.ai_playlist.workflow.select_tracks_with_llm", new=AsyncMock()) as mock_select:
                        # Each playlist costs $0.09 (total $0.45 < $0.50 budget)
                        mock_response = LLMTrackSelectionResponse(                            request_id="12345678-1234-4123-8123-123456789012",
                            selected_tracks=sample_tracks[:20],
                            tool_calls=[{"tool_name": "search_tracks", "arguments": {}, "result": {}}],
                            reasoning="Test",
                            cost_usd=0.09,
                            execution_time_seconds=3.0,)
                        mock_select.return_value = mock_response

                        with patch("src.ai_playlist.workflow.validate_playlist", return_value=valid_validation_result):
                            summary = await run_automation(
                                input_file=str(input_file),
                                output_dir=str(tmp_path / "output"),
                                max_cost_usd=0.50,
                                dry_run=True,
                            )

        # Should succeed - total cost under budget
        assert summary["success_count"] == 5
        assert summary["total_cost"] <= 0.50


# ============================================================================
# Error Path Tests - MCP Server Failures
# ============================================================================


@pytest.mark.asyncio
class TestMCPServerErrors:
    """Test MCP server availability and error handling."""

    async def test_mcp_server_unavailable_raises_error(self, tmp_path, sample_programming_document, sample_dayparts):
        """Test MCPToolError when Subsonic MCP server is unavailable."""
        input_file = tmp_path / "test.md"
        input_file.write_text(sample_programming_document)

        with patch("src.ai_playlist.main.parse_programming_document", return_value=[sample_dayparts[0]]):
            with patch("src.ai_playlist.main.generate_playlist_specs", return_value=[Mock()]):
                # MCP verification fails
                with patch(
                    "src.ai_playlist.main.configure_and_verify_mcp",
                    new=AsyncMock(side_effect=MCPToolError("MCP server not available")),
                ):
                    with pytest.raises(MCPToolError, match="MCP server not available"):
                        await run_automation(
                            input_file=str(input_file),
                            output_dir=str(tmp_path / "output"),
                            max_cost_usd=0.50,
                            dry_run=True,
                        )

    async def test_mcp_timeout_raises_error(self, tmp_path, sample_programming_document, sample_dayparts):
        """Test timeout error when MCP server doesn't respond."""
        input_file = tmp_path / "test.md"
        input_file.write_text(sample_programming_document)

        with patch("src.ai_playlist.main.parse_programming_document", return_value=[sample_dayparts[0]]):
            with patch("src.ai_playlist.main.generate_playlist_specs", return_value=[Mock()]):
                with patch(
                    "src.ai_playlist.main.configure_and_verify_mcp",
                    new=AsyncMock(side_effect=asyncio.TimeoutError("MCP timeout")),
                ):
                    with pytest.raises(asyncio.TimeoutError):
                        await run_automation(
                            input_file=str(input_file),
                            output_dir=str(tmp_path / "output"),
                            max_cost_usd=0.50,
                            dry_run=True,
                        )


# ============================================================================
# Error Path Tests - AzuraCast Sync Failures
# ============================================================================


@pytest.mark.asyncio
class TestAzuraCastSyncErrors:
    """Test AzuraCast sync error handling."""

    async def test_azuracast_sync_partial_failure_continues(
        self, tmp_path, sample_programming_document, sample_dayparts, sample_tracks, valid_validation_result
    ):
        """Test workflow continues when some playlists fail to sync."""
        input_file = tmp_path / "test.md"
        input_file.write_text(sample_programming_document)

        # Create 3 playlists
        specs = []
        for i in range(3):
            spec = Mock()
            spec.id = "12345678-1234-4123-8123-1234567890ab"
            spec.name = f"Playlist_{i}"
            spec.target_duration_minutes = 240
            spec.daypart = sample_dayparts[0]
            spec.track_criteria = Mock(bpm_tolerance=10)
            specs.append(spec)

        with patch("src.ai_playlist.main.parse_programming_document", return_value=sample_dayparts):
            with patch("src.ai_playlist.main.generate_playlist_specs", return_value=specs):
                with patch("src.ai_playlist.main.configure_and_verify_mcp", new=AsyncMock()):
                    with patch("src.ai_playlist.workflow.select_tracks_with_llm", new=AsyncMock()) as mock_select:
                        mock_response = LLMTrackSelectionResponse(                            request_id="12345678-1234-4123-8123-123456789012",
                            selected_tracks=sample_tracks[:20],
                            tool_calls=[{"tool_name": "search_tracks", "arguments": {}, "result": {}}],
                            reasoning="Test",
                            cost_usd=0.007,
                            execution_time_seconds=2.5,)
                        mock_select.return_value = mock_response

                        with patch("src.ai_playlist.workflow.validate_playlist", return_value=valid_validation_result):
                            # First sync fails, others succeed
                            call_count = [0]

                            async def mock_sync_side_effect(playlist):
                                call_count[0] += 1
                                if call_count[0] == 1:
                                    raise AzuraCastPlaylistSyncError("Sync failed")
                                mock_result = Mock()
                                mock_result.azuracast_id = 100 + call_count[0]
                                return mock_result

                            with patch(
                                "src.ai_playlist.workflow.sync_playlist_to_azuracast",
                                side_effect=mock_sync_side_effect,
                            ):
                                summary = await run_automation(
                                    input_file=str(input_file),
                                    output_dir=str(tmp_path / "output"),
                                    max_cost_usd=0.50,
                                    dry_run=False,  # Enable sync
                                )

        # Workflow should complete successfully
        assert summary["success_count"] == 3
        # All playlists should be saved even if sync fails
        assert len(summary["output_files"]) == 3

    async def test_azuracast_all_sync_failures_completes(
        self, tmp_path, sample_programming_document, sample_dayparts, sample_tracks, valid_validation_result
    ):
        """Test workflow completes even when all AzuraCast syncs fail."""
        input_file = tmp_path / "test.md"
        input_file.write_text(sample_programming_document)

        with patch("src.ai_playlist.main.parse_programming_document", return_value=[sample_dayparts[0]]):
            with patch("src.ai_playlist.main.generate_playlist_specs") as mock_gen:
                spec = Mock()
                spec.id = "12345678-1234-4123-8123-1234567890ab"
                spec.name = "Test_Sync_Fail"
                spec.target_duration_minutes = 240
                spec.daypart = sample_dayparts[0]
                spec.track_criteria = Mock(bpm_tolerance=10)
                mock_gen.return_value = [spec]

                with patch("src.ai_playlist.main.configure_and_verify_mcp", new=AsyncMock()):
                    with patch("src.ai_playlist.workflow.select_tracks_with_llm", new=AsyncMock()) as mock_select:
                        mock_response = LLMTrackSelectionResponse(                            request_id="12345678-1234-4123-8123-123456789012",
                            selected_tracks=sample_tracks[:15],
                            tool_calls=[{"tool_name": "search_tracks", "arguments": {}, "result": {}}],
                            reasoning="Test",
                            cost_usd=0.005,
                            execution_time_seconds=2.0,)
                        mock_select.return_value = mock_response

                        with patch("src.ai_playlist.workflow.validate_playlist", return_value=valid_validation_result):
                            # All syncs fail
                            with patch(
                                "src.ai_playlist.workflow.sync_playlist_to_azuracast",
                                new=AsyncMock(side_effect=AzuraCastPlaylistSyncError("All sync failed")),
                            ):
                                summary = await run_automation(
                                    input_file=str(input_file),
                                    output_dir=str(tmp_path / "output"),
                                    max_cost_usd=0.50,
                                    dry_run=False,
                                )

        # Should still complete successfully (sync failures are logged, not fatal)
        assert summary["success_count"] == 1
        assert len(summary["output_files"]) == 1


# ============================================================================
# Edge Case Tests
# ============================================================================


@pytest.mark.asyncio
class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    async def test_zero_playlists_specification(self, tmp_path, sample_programming_document):
        """Test handling of empty playlist specification list."""
        input_file = tmp_path / "test.md"
        input_file.write_text(sample_programming_document)

        with patch("src.ai_playlist.main.parse_programming_document", return_value=[]):
            # Empty daypart list should raise ValueError from ProgrammingDocument
            with pytest.raises(ValueError, match="Must contain at least one valid daypart"):
                await run_automation(
                    input_file=str(input_file),
                    output_dir=str(tmp_path / "output"),
                    max_cost_usd=0.50,
                    dry_run=True,
                )

    async def test_very_small_cost_budget(
        self, tmp_path, sample_programming_document, sample_dayparts, sample_tracks
    ):
        """Test workflow with very small cost budget ($0.01)."""
        input_file = tmp_path / "test.md"
        input_file.write_text(sample_programming_document)

        with patch("src.ai_playlist.main.parse_programming_document", return_value=[sample_dayparts[0]]):
            with patch("src.ai_playlist.main.generate_playlist_specs") as mock_gen:
                spec = Mock()
                spec.id = "12345678-1234-4123-8123-1234567890ab"
                spec.name = "Test_Small_Budget"
                spec.target_duration_minutes = 240
                spec.daypart = sample_dayparts[0]
                spec.track_criteria = Mock(bpm_tolerance=10)
                mock_gen.return_value = [spec]

                with patch("src.ai_playlist.main.configure_and_verify_mcp", new=AsyncMock()):
                    with patch("src.ai_playlist.workflow.select_tracks_with_llm", new=AsyncMock()) as mock_select:
                        # Cost exceeds tiny budget
                        mock_response = LLMTrackSelectionResponse(                            request_id="12345678-1234-4123-8123-123456789012",
                            selected_tracks=sample_tracks[:5],
                            tool_calls=[{"tool_name": "search_tracks", "arguments": {}, "result": {}}],
                            reasoning="Test",
                            cost_usd=0.02,  # Exceeds $0.01 budget
                            execution_time_seconds=1.0,)
                        mock_select.return_value = mock_response

                        with pytest.raises(CostExceededError, match="exceeds budget"):
                            await run_automation(
                                input_file=str(input_file),
                                output_dir=str(tmp_path / "output"),
                                max_cost_usd=0.01,  # Very small budget
                                dry_run=True,
                            )

    async def test_output_directory_created_if_missing(
        self, tmp_path, sample_programming_document, sample_dayparts, sample_tracks, valid_validation_result
    ):
        """Test output directory is created if it doesn't exist."""
        input_file = tmp_path / "test.md"
        input_file.write_text(sample_programming_document)
        output_dir = tmp_path / "nested" / "output" / "path"

        # Ensure directory doesn't exist
        assert not output_dir.exists()

        with patch("src.ai_playlist.main.parse_programming_document", return_value=[sample_dayparts[0]]):
            with patch("src.ai_playlist.main.generate_playlist_specs") as mock_gen:
                spec = Mock()
                spec.id = "12345678-1234-4123-8123-1234567890ab"
                spec.name = "Test_Dir"
                spec.target_duration_minutes = 240
                spec.daypart = sample_dayparts[0]
                spec.track_criteria = Mock(bpm_tolerance=10)
                mock_gen.return_value = [spec]

                with patch("src.ai_playlist.main.configure_and_verify_mcp", new=AsyncMock()):
                    with patch("src.ai_playlist.workflow.select_tracks_with_llm", new=AsyncMock()) as mock_select:
                        mock_response = LLMTrackSelectionResponse(                            request_id="12345678-1234-4123-8123-123456789012",
                            selected_tracks=sample_tracks[:10],
                            tool_calls=[{"tool_name": "search_tracks", "arguments": {}, "result": {}}],
                            reasoning="Test",
                            cost_usd=0.005,
                            execution_time_seconds=2.0,)
                        mock_select.return_value = mock_response

                        with patch("src.ai_playlist.workflow.validate_playlist", return_value=valid_validation_result):
                            summary = await run_automation(
                                input_file=str(input_file),
                                output_dir=str(output_dir),
                                max_cost_usd=0.50,
                                dry_run=True,
                            )

        # Directory should be created
        assert output_dir.exists()
        assert summary["success_count"] == 1

    async def test_playlist_with_zero_tracks_selected(
        self, tmp_path, sample_programming_document, sample_dayparts, valid_validation_result
    ):
        """Test handling when LLM returns zero tracks."""
        input_file = tmp_path / "test.md"
        input_file.write_text(sample_programming_document)

        with patch("src.ai_playlist.main.parse_programming_document", return_value=[sample_dayparts[0]]):
            with patch("src.ai_playlist.main.generate_playlist_specs") as mock_gen:
                spec = Mock()
                spec.id = "12345678-1234-4123-8123-1234567890ab"
                spec.name = "Test_Zero"
                spec.target_duration_minutes = 240
                spec.daypart = sample_dayparts[0]
                spec.track_criteria = Mock(bpm_tolerance=10)
                mock_gen.return_value = [spec]

                with patch("src.ai_playlist.main.configure_and_verify_mcp", new=AsyncMock()):
                    with patch("src.ai_playlist.workflow.select_tracks_with_llm", new=AsyncMock()) as mock_select:
                        # Return zero tracks
                        mock_response = LLMTrackSelectionResponse(
                            request_id="12345678-1234-4123-8123-123456789012",
                            selected_tracks=[],  # Zero tracks
                            tool_calls=[{"tool_name": "search_tracks", "arguments": {}, "result": {}}],
                            reasoning="No tracks found",
                            cost_usd=0.001,
                            execution_time_seconds=1.0,
                        )
                        mock_select.return_value = mock_response

                        with patch("src.ai_playlist.workflow.validate_playlist", return_value=valid_validation_result):
                            summary = await run_automation(
                                input_file=str(input_file),
                                output_dir=str(tmp_path / "output"),
                                max_cost_usd=0.50,
                                dry_run=True,
                            )

        # Should complete but with empty playlist
        assert summary["success_count"] == 1

    async def test_decision_logger_integration(
        self, tmp_path, sample_programming_document, sample_dayparts, sample_tracks, valid_validation_result
    ):
        """Test decision logger is properly initialized and used."""
        input_file = tmp_path / "test.md"
        input_file.write_text(sample_programming_document)
        output_dir = tmp_path / "output"

        with patch("src.ai_playlist.main.parse_programming_document", return_value=[sample_dayparts[0]]):
            with patch("src.ai_playlist.main.generate_playlist_specs") as mock_gen:
                spec = Mock()
                spec.id = "12345678-1234-4123-8123-1234567890ab"
                spec.name = "Test_Logger"
                spec.target_duration_minutes = 240
                spec.daypart = sample_dayparts[0]
                spec.track_criteria = Mock(bpm_tolerance=10)
                mock_gen.return_value = [spec]

                with patch("src.ai_playlist.main.configure_and_verify_mcp", new=AsyncMock()):
                    with patch("src.ai_playlist.workflow.select_tracks_with_llm", new=AsyncMock()) as mock_select:
                        mock_response = LLMTrackSelectionResponse(
                            request_id="12345678-1234-4123-8123-123456789012",
                            selected_tracks=sample_tracks[:10],
                            tool_calls=[{"tool_name": "search_tracks", "arguments": {}, "result": {}}],
                            reasoning="Test reasoning",
                            cost_usd=0.005,
                            execution_time_seconds=2.0,
                        )
                        mock_select.return_value = mock_response

                        with patch("src.ai_playlist.workflow.validate_playlist", return_value=valid_validation_result):
                            summary = await run_automation(
                                input_file=str(input_file),
                                output_dir=str(output_dir),
                                max_cost_usd=0.50,
                                dry_run=True,
                            )

        # Verify decision log was created
        assert "decision_log" in summary
        decision_log_dir = output_dir / "logs" / "decisions"
        assert decision_log_dir.exists()

    async def test_unicode_in_playlist_names(
        self, tmp_path, sample_programming_document, sample_tracks, valid_validation_result
    ):
        """Test handling of unicode characters in playlist names."""
        input_file = tmp_path / "test.md"
        input_file.write_text(sample_programming_document)

        # Create daypart with unicode name
        daypart = DaypartSpec(
            name="Monday_Morning_☀️_Café",  # Unicode emoji
            day="Monday",
            time_range=("06:00", "10:00"),
            bpm_progression={"06:00-10:00": (110, 140)},
            genre_mix={"Alternative": 0.50},
            era_distribution={"Current (0-2 years)": 0.60},
            australian_min=0.30,
            mood="energetic",
            tracks_per_hour=15,
        )

        with patch("src.ai_playlist.main.parse_programming_document", return_value=[daypart]):
            with patch("src.ai_playlist.main.generate_playlist_specs") as mock_gen:
                spec = Mock()
                spec.id = "12345678-1234-4123-8123-1234567890ab"
                spec.name = "Monday_Morning_☀️_Café"
                spec.target_duration_minutes = 240
                spec.daypart = daypart
                spec.track_criteria = Mock(bpm_tolerance=10)
                mock_gen.return_value = [spec]

                with patch("src.ai_playlist.main.configure_and_verify_mcp", new=AsyncMock()):
                    with patch("src.ai_playlist.workflow.select_tracks_with_llm", new=AsyncMock()) as mock_select:
                        mock_response = LLMTrackSelectionResponse(                            request_id="12345678-1234-4123-8123-123456789012",
                            selected_tracks=sample_tracks[:10],
                            tool_calls=[{"tool_name": "search_tracks", "arguments": {}, "result": {}}],
                            reasoning="Test",
                            cost_usd=0.005,
                            execution_time_seconds=2.0,)
                        mock_select.return_value = mock_response

                        with patch("src.ai_playlist.workflow.validate_playlist", return_value=valid_validation_result):
                            summary = await run_automation(
                                input_file=str(input_file),
                                output_dir=str(tmp_path / "output"),
                                max_cost_usd=0.50,
                                dry_run=True,
                            )

        # Should handle unicode correctly
        assert summary["success_count"] == 1


# ============================================================================
# Performance and Timing Tests
# ============================================================================


@pytest.mark.asyncio
class TestPerformanceAndTiming:
    """Test performance metrics and timing."""

    async def test_execution_time_tracked(
        self, tmp_path, sample_programming_document, sample_dayparts, sample_tracks, valid_validation_result
    ):
        """Test that total execution time is tracked."""
        input_file = tmp_path / "test.md"
        input_file.write_text(sample_programming_document)

        with patch("src.ai_playlist.main.parse_programming_document", return_value=[sample_dayparts[0]]):
            with patch("src.ai_playlist.main.generate_playlist_specs") as mock_gen:
                spec = Mock()
                spec.id = "12345678-1234-4123-8123-1234567890ab"
                spec.name = "Test_Time"
                spec.target_duration_minutes = 240
                spec.daypart = sample_dayparts[0]
                spec.track_criteria = Mock(bpm_tolerance=10)
                mock_gen.return_value = [spec]

                with patch("src.ai_playlist.main.configure_and_verify_mcp", new=AsyncMock()):
                    with patch("src.ai_playlist.workflow.select_tracks_with_llm", new=AsyncMock()) as mock_select:
                        mock_response = LLMTrackSelectionResponse(                            request_id="12345678-1234-4123-8123-123456789012",
                            selected_tracks=sample_tracks[:10],
                            tool_calls=[{"tool_name": "search_tracks", "arguments": {}, "result": {}}],
                            reasoning="Test",
                            cost_usd=0.005,
                            execution_time_seconds=3.5,)
                        mock_select.return_value = mock_response

                        with patch("src.ai_playlist.workflow.validate_playlist", return_value=valid_validation_result):
                            summary = await run_automation(
                                input_file=str(input_file),
                                output_dir=str(tmp_path / "output"),
                                max_cost_usd=0.50,
                                dry_run=True,
                            )

        # Verify timing is tracked
        assert "total_time" in summary
        assert summary["total_time"] > 0
        assert isinstance(summary["total_time"], (int, float))

    async def test_cost_tracking_accuracy(
        self, tmp_path, sample_programming_document, sample_dayparts, sample_tracks, valid_validation_result
    ):
        """Test that LLM costs are accurately tracked."""
        input_file = tmp_path / "test.md"
        input_file.write_text(sample_programming_document)

        # Create 3 playlists with known costs
        specs = []
        for i in range(3):
            spec = Mock()
            spec.id = "12345678-1234-4123-8123-1234567890ab"
            spec.name = f"Playlist_{i}"
            spec.target_duration_minutes = 240
            spec.daypart = sample_dayparts[0]
            spec.track_criteria = Mock(bpm_tolerance=10)
            specs.append(spec)

        with patch("src.ai_playlist.main.parse_programming_document", return_value=sample_dayparts):
            with patch("src.ai_playlist.main.generate_playlist_specs", return_value=specs):
                with patch("src.ai_playlist.main.configure_and_verify_mcp", new=AsyncMock()):
                    # Each costs exactly $0.01
                    costs = [0.01, 0.01, 0.01]
                    call_count = [0]

                    async def mock_select_side_effect(request):
                        idx = call_count[0]
                        call_count[0] += 1
                        return LLMTrackSelectionResponse(                            request_id="12345678-1234-4123-8123-123456789012",
                            selected_tracks=sample_tracks[:10],
                            tool_calls=[{"tool_name": "search_tracks", "arguments": {}, "result": {}}],
                            reasoning="Test",
                            cost_usd=costs[idx],
                            execution_time_seconds=2.0,)

                    with patch("src.ai_playlist.workflow.select_tracks_with_llm", side_effect=mock_select_side_effect):
                        with patch("src.ai_playlist.workflow.validate_playlist", return_value=valid_validation_result):
                            summary = await run_automation(
                                input_file=str(input_file),
                                output_dir=str(tmp_path / "output"),
                                max_cost_usd=0.50,
                                dry_run=True,
                            )

        # Verify cost tracking
        assert "total_cost" in summary
        assert summary["total_cost"] > 0


# ============================================================================
# Summary Statistics Tests
# ============================================================================


@pytest.mark.asyncio
class TestSummaryStatistics:
    """Test summary output and statistics."""

    async def test_summary_contains_all_required_fields(
        self, tmp_path, sample_programming_document, sample_dayparts, sample_tracks, valid_validation_result
    ):
        """Test summary contains all expected fields."""
        input_file = tmp_path / "test.md"
        input_file.write_text(sample_programming_document)

        with patch("src.ai_playlist.main.parse_programming_document", return_value=[sample_dayparts[0]]):
            with patch("src.ai_playlist.main.generate_playlist_specs") as mock_gen:
                spec = Mock()
                spec.id = "12345678-1234-4123-8123-1234567890ab"
                spec.name = "Test_Summary"
                spec.target_duration_minutes = 240
                spec.daypart = sample_dayparts[0]
                spec.track_criteria = Mock(bpm_tolerance=10)
                mock_gen.return_value = [spec]

                with patch("src.ai_playlist.main.configure_and_verify_mcp", new=AsyncMock()):
                    with patch("src.ai_playlist.workflow.select_tracks_with_llm", new=AsyncMock()) as mock_select:
                        mock_response = LLMTrackSelectionResponse(                            request_id="12345678-1234-4123-8123-123456789012",
                            selected_tracks=sample_tracks[:10],
                            tool_calls=[{"tool_name": "search_tracks", "arguments": {}, "result": {}}],
                            reasoning="Test",
                            cost_usd=0.005,
                            execution_time_seconds=2.0,)
                        mock_select.return_value = mock_response

                        with patch("src.ai_playlist.workflow.validate_playlist", return_value=valid_validation_result):
                            summary = await run_automation(
                                input_file=str(input_file),
                                output_dir=str(tmp_path / "output"),
                                max_cost_usd=0.50,
                                dry_run=True,
                            )

        # Verify all required fields
        required_fields = [
            "playlist_count",
            "success_count",
            "failed_count",
            "total_cost",
            "total_time",
            "output_files",
            "decision_log",
        ]
        for field in required_fields:
            assert field in summary, f"Missing required field: {field}"

    async def test_summary_counts_accurate_with_mixed_results(
        self,
        tmp_path,
        sample_programming_document,
        sample_dayparts,
        sample_tracks,
        valid_validation_result,
        failed_validation_result,
    ):
        """Test summary counts are accurate with mixed success/failure."""
        input_file = tmp_path / "test.md"
        input_file.write_text(sample_programming_document)

        # Create 5 playlists
        specs = []
        for i in range(5):
            spec = Mock()
            spec.id = "12345678-1234-4123-8123-1234567890ab"
            spec.name = f"Playlist_{i}"
            spec.target_duration_minutes = 240
            spec.daypart = sample_dayparts[0]
            spec.track_criteria = Mock(bpm_tolerance=10)
            specs.append(spec)

        with patch("src.ai_playlist.main.parse_programming_document", return_value=sample_dayparts):
            with patch("src.ai_playlist.main.generate_playlist_specs", return_value=specs):
                with patch("src.ai_playlist.main.configure_and_verify_mcp", new=AsyncMock()):
                    with patch("src.ai_playlist.workflow.select_tracks_with_llm", new=AsyncMock()) as mock_select:
                        mock_response = LLMTrackSelectionResponse(                            request_id="12345678-1234-4123-8123-123456789012",
                            selected_tracks=sample_tracks[:20],
                            tool_calls=[{"tool_name": "search_tracks", "arguments": {}, "result": {}}],
                            reasoning="Test",
                            cost_usd=0.007,
                            execution_time_seconds=2.5,)
                        mock_select.return_value = mock_response

                        # 3 pass, 2 fail
                        validation_results = [
                            valid_validation_result,
                            valid_validation_result,
                            failed_validation_result,
                            valid_validation_result,
                            failed_validation_result,
                        ]
                        with patch("src.ai_playlist.workflow.validate_playlist", side_effect=validation_results):
                            summary = await run_automation(
                                input_file=str(input_file),
                                output_dir=str(tmp_path / "output"),
                                max_cost_usd=0.50,
                                dry_run=True,
                            )

        # Verify counts
        assert summary["playlist_count"] == 5
        assert summary["success_count"] == 3
        assert summary["failed_count"] == 2
        assert len(summary["output_files"]) == 3
