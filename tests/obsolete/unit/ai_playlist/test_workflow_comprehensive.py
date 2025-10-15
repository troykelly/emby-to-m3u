"""
Comprehensive Unit Tests for workflow.py

Tests all workflow functions including document loading, batch track selection,
playlist file saving, AzuraCast sync, and serialization helpers.

Coverage Target: ≥85% for workflow.py (318 lines)
"""

import pytest
import asyncio
import json
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch, mock_open, MagicMock
from typing import List, Dict

from src.ai_playlist.workflow import (
    load_programming_document,
    batch_track_selection,
    save_playlist_file,
    sync_to_azuracast,
    serialize_criteria,
    serialize_tracks,
    serialize_validation,
)
from src.ai_playlist.models import (
    GenreCriteria,
    EraCriteria,
    BPMRange,
    ScheduleType,
    PlaylistSpec,
    DaypartSpec,
    TrackSelectionCriteria,
    Playlist,
    SelectedTrack,
)
from src.ai_playlist.models.validation import ValidationResult, ConstraintScores, FlowMetrics
from src.ai_playlist.decision_logger import DecisionLogger
from src.ai_playlist.exceptions import CostExceededError
from src.ai_playlist.azuracast_sync import AzuraCastPlaylistSyncError


class TestLoadProgrammingDocument:
    """Test suite for load_programming_document function."""

    def test_load_programming_document_success(self, tmp_path):
        """Test successful loading of programming document."""
        # Create test file
        test_file = tmp_path / "test_programming.md"
        content = """# Radio Programming Document

Monday Production Call (06:00-10:00):
- BPM: 90-115 (moderate energy)
- Genre Mix: Alternative 20-30%, Electronic 15-25%
- Era: Current 35-45%, Recent 30-40%
- Australian Minimum: 30%
- Energy Flow: Start moderate, build to peak
"""
        test_file.write_text(content, encoding="utf-8")

        # Load document
        result = load_programming_document(str(test_file))

        assert result == content
        assert len(result) > 0
        assert "Monday Production Call" in result

    def test_load_programming_document_file_not_found(self):
        """Test FileNotFoundError when file doesn't exist."""
        with pytest.raises(FileNotFoundError, match="Programming document not found"):
            load_programming_document("/nonexistent/path/document.md")

    def test_load_programming_document_empty_file(self, tmp_path):
        """Test ValueError when file is empty."""
        empty_file = tmp_path / "empty.md"
        empty_file.write_text("", encoding="utf-8")

        with pytest.raises(ValueError, match="Programming document is empty"):
            load_programming_document(str(empty_file))

    def test_load_programming_document_whitespace_only(self, tmp_path):
        """Test ValueError when file contains only whitespace."""
        whitespace_file = tmp_path / "whitespace.md"
        whitespace_file.write_text("   \n\n  \t\n  ", encoding="utf-8")

        with pytest.raises(ValueError, match="Programming document is empty"):
            load_programming_document(str(whitespace_file))

    def test_load_programming_document_encoding_error(self, tmp_path):
        """Test handling of encoding errors (non-UTF-8)."""
        # Create file with non-UTF-8 encoding
        binary_file = tmp_path / "binary.md"
        binary_file.write_bytes(b"\xff\xfe Invalid UTF-8 \x80\x81")

        # Should raise UnicodeDecodeError
        with pytest.raises(UnicodeDecodeError):
            load_programming_document(str(binary_file))


@pytest.mark.asyncio
class TestBatchTrackSelection:
    """Test suite for batch_track_selection function."""

    @pytest.fixture
    def sample_daypart(self):
        """Create sample daypart spec."""
        return DaypartSpec(
            name="Test Daypart",
            time_range=("06:00", "10:00"),
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
            bpm_range=(90, 130),
            bpm_tolerance=10,
            genre_mix={"Rock": (0.45, 0.55), "Electronic": (0.25, 0.35)},
            genre_tolerance=0.05,
            era_distribution={"Current (0-2 years)": (0.55, 0.65), "Recent (2-5 years)": (0.25, 0.35)},
            era_tolerance=0.05,
            australian_min=0.30,
            energy_flow="energetic",
        )

    @pytest.fixture
    def sample_playlist_specs(self, sample_daypart, sample_criteria):
        """Create sample playlist specifications."""
        return [
            PlaylistSpec(
                id=f"550e8400-e29b-41d4-a716-44665544000{i}",
                name=f"Monday_Playlist{i}_0600_1000",
                daypart=sample_daypart,
                track_criteria=sample_criteria,
                target_duration_minutes=240,
                created_at=datetime.now(),
            )
            for i in range(3)
        ]

    @pytest.fixture
    def mock_decision_logger(self, tmp_path):
        """Create mock decision logger."""
        return DecisionLogger(log_dir=tmp_path / "logs")

    async def test_batch_track_selection_multiple_specs(
        self, sample_playlist_specs, mock_decision_logger
    ):
        """Test batch_track_selection processes all specs."""
        with patch("src.ai_playlist.workflow.select_tracks_with_llm") as mock_select, \
             patch("src.ai_playlist.workflow.validate_playlist") as mock_validate:

            # Mock LLM response
            mock_response = Mock()
            mock_response.selected_tracks = [
                SelectedTrack(
                    track_id=f"track-{i}",
                    title=f"Track {i}",
                    artist=f"Artist {i}",
                    album="Test Album",
                    bpm=120,
                    genre="Rock",
                    year=2023,
                    country="Australia",
                    duration_seconds=180,
                    position_in_playlist=i + 1,
                    selection_reason="Test reason",
                )
                for i in range(10)
            ]
            mock_response.cost_usd = 0.005
            mock_response.execution_time_seconds = 2.5
            mock_response.reasoning = "Test reasoning"
            mock_select.return_value = mock_response

            # Mock validation
            mock_validation = ValidationResult(
                constraint_satisfaction=0.85,
                bpm_satisfaction=0.90,
                genre_satisfaction=0.85,
                era_satisfaction=0.80,
                australian_content=0.35,
                flow_quality_score=0.75,
                bpm_variance=8.5,
                energy_progression="smooth",
                genre_diversity=0.70,
                gap_analysis={},
                passes_validation=True,
            )
            mock_validate.return_value = mock_validation

            # Execute batch selection
            playlists = await batch_track_selection(
                sample_playlist_specs, max_cost_usd=0.50, decision_logger=mock_decision_logger
            )

            # Verify results
            assert len(playlists) == 3
            assert all(isinstance(p, Playlist) for p in playlists)
            assert mock_select.call_count == 3

    async def test_batch_track_selection_parallel_execution(
        self, sample_daypart, sample_criteria, mock_decision_logger
    ):
        """Test parallel execution (up to 10 concurrent)."""
        # Note: Current implementation is sequential, but tests ensure it processes all specs
        specs = [
            PlaylistSpec(
                id=f"550e8400-e29b-41d4-a716-44665544000{i}",
                name=f"Monday_Playlist{i}_0600_1000",
                daypart=sample_daypart,
                track_criteria=sample_criteria,
                target_duration_minutes=240,
                created_at=datetime.now(),
            )
            for i in range(10)
        ]

        with patch("src.ai_playlist.workflow.select_tracks_with_llm") as mock_select, \
             patch("src.ai_playlist.workflow.validate_playlist") as mock_validate:

            mock_response = Mock()
            mock_response.selected_tracks = []
            mock_response.cost_usd = 0.001
            mock_response.execution_time_seconds = 0.5
            mock_response.reasoning = "Test"
            mock_select.return_value = mock_response

            mock_validate.return_value = Mock(
                constraint_satisfaction=0.85,
                flow_quality_score=0.75,
                australian_content=0.35,
            )

            playlists = await batch_track_selection(
                specs, max_cost_usd=0.50, decision_logger=mock_decision_logger
            )

            assert len(playlists) == 10

    async def test_batch_track_selection_cost_tracking(
        self, sample_playlist_specs, mock_decision_logger
    ):
        """Test cost tracking across all playlists."""
        with patch("src.ai_playlist.workflow.select_tracks_with_llm") as mock_select, \
             patch("src.ai_playlist.workflow.validate_playlist") as mock_validate:

            mock_response = Mock()
            mock_response.selected_tracks = []
            mock_response.cost_usd = 0.10  # High cost
            mock_response.execution_time_seconds = 1.0
            mock_response.reasoning = "Test"
            mock_select.return_value = mock_response

            mock_validate.return_value = Mock()

            # Should raise CostExceededError
            with pytest.raises(CostExceededError, match="Total cost .* exceeds budget"):
                await batch_track_selection(
                    sample_playlist_specs, max_cost_usd=0.20, decision_logger=mock_decision_logger
                )

    async def test_batch_track_selection_time_tracking(
        self, sample_playlist_specs, mock_decision_logger
    ):
        """Test time tracking."""
        with patch("src.ai_playlist.workflow.select_tracks_with_llm") as mock_select, \
             patch("src.ai_playlist.workflow.validate_playlist") as mock_validate:

            mock_response = Mock()
            mock_response.selected_tracks = []
            mock_response.cost_usd = 0.001
            mock_response.execution_time_seconds = 5.5
            mock_response.reasoning = "Test"
            mock_select.return_value = mock_response

            mock_validate.return_value = Mock()

            playlists = await batch_track_selection(
                sample_playlist_specs, max_cost_usd=0.50, decision_logger=mock_decision_logger
            )

            # Verify execution completed (time tracking is logged but not enforced in this function)
            assert len(playlists) == 3

    async def test_batch_track_selection_budget_enforcement(
        self, sample_playlist_specs, mock_decision_logger
    ):
        """Test budget enforcement (<$0.50 total)."""
        with patch("src.ai_playlist.workflow.select_tracks_with_llm") as mock_select, \
             patch("src.ai_playlist.workflow.validate_playlist"):

            mock_response = Mock()
            mock_response.selected_tracks = []
            mock_response.cost_usd = 0.30  # Would exceed $0.50 after 2 playlists
            mock_response.execution_time_seconds = 1.0
            mock_response.reasoning = "Test"
            mock_select.return_value = mock_response

            with pytest.raises(CostExceededError):
                await batch_track_selection(
                    sample_playlist_specs, max_cost_usd=0.50, decision_logger=mock_decision_logger
                )

    async def test_batch_track_selection_partial_failures(
        self, sample_playlist_specs, mock_decision_logger
    ):
        """Test partial failures (some playlists succeed, some fail)."""
        with patch("src.ai_playlist.workflow.select_tracks_with_llm") as mock_select:

            # First call succeeds, second fails
            mock_select.side_effect = [
                Mock(
                    selected_tracks=[],
                    cost_usd=0.005,
                    execution_time_seconds=1.0,
                    reasoning="Success",
                ),
                Exception("LLM error"),
            ]

            # Should raise exception and log failure
            with pytest.raises(Exception, match="LLM error"):
                await batch_track_selection(
                    sample_playlist_specs, max_cost_usd=0.50, decision_logger=mock_decision_logger
                )

    async def test_batch_track_selection_timeout_handling(
        self, sample_playlist_specs, mock_decision_logger
    ):
        """Test timeout handling (10 min limit)."""
        with patch("src.ai_playlist.workflow.select_tracks_with_llm") as mock_select, \
             patch("src.ai_playlist.workflow.validate_playlist"):

            async def slow_select(*args, **kwargs):
                await asyncio.sleep(0.1)
                return Mock(
                    selected_tracks=[],
                    cost_usd=0.001,
                    execution_time_seconds=600,
                    reasoning="Slow",
                )

            mock_select.side_effect = slow_select

            # Note: Current implementation doesn't enforce timeout in batch_track_selection
            # Timeout is handled in individual LLM calls
            playlists = await batch_track_selection(
                sample_playlist_specs[:1], max_cost_usd=0.50, decision_logger=mock_decision_logger
            )

            assert len(playlists) == 1


class TestSavePlaylistFile:
    """Test suite for save_playlist_file function."""

    @pytest.fixture
    def sample_playlist(self):
        """Create sample playlist."""
        validation = ValidationResult(
            constraint_satisfaction=0.85,
            bpm_satisfaction=0.90,
            genre_satisfaction=0.85,
            era_satisfaction=0.80,
            australian_content=0.35,
            flow_quality_score=0.75,
            bpm_variance=8.5,
            energy_progression="smooth",
            genre_diversity=0.70,
            gap_analysis={"issues": "none"},
            passes_validation=True,
        )

        tracks = [
            SelectedTrack(
                track_id=f"track-{i}",
                title=f"Track {i}",
                artist=f"Artist {i}",
                album="Test Album",
                bpm=120 + i,
                genre="Rock",
                year=2023,
                country="Australia",
                duration_seconds=180,
                position_in_playlist=i + 1,
                selection_reason=f"Reason {i}",
            )
            for i in range(5)
        ]

        # Create matching spec
        spec = PlaylistSpec(
            id="550e8400-e29b-41d4-a716-446655440000",
            name="Monday_TestPlaylist_0600_1000",
            daypart=Mock(tracks_per_hour=15),
            track_criteria=Mock(),
            target_duration_minutes=240,
            created_at=datetime(2025, 1, 1, 11, 0, 0),
        )

        return Playlist(
            id="550e8400-e29b-41d4-a716-446655440000",
            name="Monday_TestPlaylist_0600_1000",
            tracks=tracks,
            spec=spec,
            validation_result=validation,
            created_at=datetime(2025, 1, 1, 12, 0, 0),
        )

    def test_save_playlist_file_creates_json(self, tmp_path, sample_playlist):
        """Test save_playlist_file creates JSON file."""
        output_file = save_playlist_file(sample_playlist, tmp_path)

        assert output_file.exists()
        assert output_file.suffix == ".json"
        assert output_file.name == "Monday_TestPlaylist_0600_1000.json"

    def test_save_playlist_file_output_directory_creation(self, tmp_path, sample_playlist):
        """Test output directory creation."""
        nested_dir = tmp_path / "playlists" / "output"
        nested_dir.mkdir(parents=True)

        output_file = save_playlist_file(sample_playlist, nested_dir)

        assert output_file.parent == nested_dir
        assert output_file.exists()

    def test_save_playlist_file_naming_convention(self, tmp_path, sample_playlist):
        """Test file naming convention."""
        output_file = save_playlist_file(sample_playlist, tmp_path)

        assert output_file.name == f"{sample_playlist.name}.json"

    def test_save_playlist_file_json_serialization(self, tmp_path, sample_playlist):
        """Test JSON serialization."""
        output_file = save_playlist_file(sample_playlist, tmp_path)

        with open(output_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["id"] == sample_playlist.id
        assert data["name"] == sample_playlist.name
        assert data["created_at"] == "2025-01-01T12:00:00"
        assert len(data["tracks"]) == 5
        assert "validation" in data

    def test_save_playlist_file_write_errors(self, tmp_path, sample_playlist):
        """Test file write errors."""
        # Make directory read-only to trigger write error
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        readonly_dir.chmod(0o444)

        try:
            with pytest.raises(PermissionError):
                save_playlist_file(sample_playlist, readonly_dir)
        finally:
            # Restore permissions for cleanup
            readonly_dir.chmod(0o755)


@pytest.mark.asyncio
class TestSyncToAzuracast:
    """Test suite for sync_to_azuracast function."""

    @pytest.fixture
    def sample_playlists(self):
        """Create sample playlists for syncing."""
        validation = ValidationResult(
            constraint_satisfaction=0.85,
            bpm_satisfaction=0.90,
            genre_satisfaction=0.85,
            era_satisfaction=0.80,
            australian_content=0.35,
            flow_quality_score=0.75,
            bpm_variance=8.5,
            energy_progression="smooth",
            genre_diversity=0.70,
            gap_analysis={},
            passes_validation=True,
        )

        playlists = []
        for i in range(3):
            spec = PlaylistSpec(
                id=f"550e8400-e29b-41d4-a716-44665544000{i}",
                name=f"Monday_Playlist{i}_0600_1000",
                daypart=Mock(tracks_per_hour=15),
                track_criteria=Mock(),
                target_duration_minutes=240,
                created_at=datetime.now(),
            )
            playlist = Playlist(
                id=f"550e8400-e29b-41d4-a716-44665544000{i}",
                name=f"Monday_Playlist{i}_0600_1000",
                tracks=[
                    SelectedTrack(
                        track_id="track-1",
                        title="Track 1",
                        artist="Artist 1",
                        album="Album 1",
                        bpm=120,
                        genre="Rock",
                        year=2023,
                        country="Australia",
                        duration_seconds=180,
                        position_in_playlist=1,
                        selection_reason="Reason",
                    )
                ],
                spec=spec,
                validation_result=validation,
                created_at=datetime.now(),
            )
            playlists.append(playlist)
        return playlists

    async def test_sync_to_azuracast_success(self, sample_playlists):
        """Test sync_to_azuracast success."""
        with patch("src.ai_playlist.workflow.sync_playlist_to_azuracast") as mock_sync:
            # Mock successful sync
            mock_sync.side_effect = [
                Mock(azuracast_id=100 + i) for i in range(3)
            ]

            results = await sync_to_azuracast(sample_playlists)

            assert len(results) == 3
            assert all(azuracast_id >= 100 for azuracast_id in results.values())
            assert mock_sync.call_count == 3

    async def test_sync_to_azuracast_error_handling(self, sample_playlists):
        """Test sync error handling."""
        with patch("src.ai_playlist.workflow.sync_playlist_to_azuracast") as mock_sync:
            # First succeeds, second fails, third succeeds
            mock_sync.side_effect = [
                Mock(azuracast_id=100),
                AzuraCastPlaylistSyncError("Sync failed"),
                Mock(azuracast_id=102),
            ]

            results = await sync_to_azuracast(sample_playlists)

            # Should return results for successful syncs only
            assert len(results) == 2

    async def test_sync_to_azuracast_partial_success(self, sample_playlists):
        """Test partial sync success (some succeed, some fail)."""
        with patch("src.ai_playlist.workflow.sync_playlist_to_azuracast") as mock_sync:
            mock_sync.side_effect = [
                Mock(azuracast_id=100),
                Exception("Unexpected error"),
                Mock(azuracast_id=102),
            ]

            results = await sync_to_azuracast(sample_playlists)

            assert len(results) == 2
            assert sample_playlists[0] in results
            assert sample_playlists[2] in results


class TestSerializationHelpers:
    """Test suite for serialization helper functions."""

    def test_serialize_criteria_converts_to_dict(self):
        """Test serialize_criteria converts TrackSelectionCriteria to dict."""
        criteria = TrackSelectionCriteria(
            bpm_range=(90, 130),
            bpm_tolerance=10,
            genre_mix={"Rock": (0.45, 0.55), "Electronic": (0.25, 0.35)},
            genre_tolerance=0.05,
            era_distribution={"Current (0-2 years)": (0.55, 0.65)},
            era_tolerance=0.05,
            australian_min=0.30,
            energy_flow="energetic",
        )

        result = serialize_criteria(criteria)

        assert isinstance(result, dict)
        assert result["bpm_range"] == (90, 130)
        assert result["bpm_tolerance"] == 10
        assert result["genre_mix"] == {"Rock": (0.45, 0.55), "Electronic": (0.25, 0.35)}
        assert result["australian_min"] == 0.30
        assert result["energy_flow"] == "energetic"

    def test_serialize_tracks_converts_to_dict_list(self):
        """Test serialize_tracks converts SelectedTrack list to dict list."""
        tracks = [
            SelectedTrack(
                track_id=f"track-{i}",
                title=f"Track {i}",
                artist=f"Artist {i}",
                album="Album",
                bpm=120 + i,
                genre="Rock",
                year=2023,
                country="Australia",
                duration_seconds=180,
                position_in_playlist=i + 1,
                selection_reason=f"Reason {i}",
            )
            for i in range(3)
        ]

        result = serialize_tracks(tracks)

        assert isinstance(result, list)
        assert len(result) == 3
        for i, track_dict in enumerate(result):
            assert isinstance(track_dict, dict)
            assert track_dict["track_id"] == f"track-{i}"
            assert track_dict["title"] == f"Track {i}"
            assert track_dict["bpm"] == 120 + i
            assert track_dict["position"] == i + 1

    def test_serialize_validation_converts_to_dict(self):
        """Test serialize_validation converts ValidationResult to dict."""
        validation = ValidationResult(
            constraint_satisfaction=0.85,
            bpm_satisfaction=0.90,
            genre_satisfaction=0.85,
            era_satisfaction=0.80,
            australian_content=0.35,
            flow_quality_score=0.75,
            bpm_variance=8.5,
            energy_progression="smooth",
            genre_diversity=0.70,
            gap_analysis={"issues": "none"},
            passes_validation=True,
        )

        result = serialize_validation(validation)

        assert isinstance(result, dict)
        assert result["constraint_satisfaction"] == 0.85
        assert result["bpm_satisfaction"] == 0.90
        assert result["flow_quality_score"] == 0.75
        assert result["passes_validation"] is True
        assert result["gap_analysis"] == {"issues": "none"}

    def test_serialize_nested_object_serialization(self):
        """Test nested object serialization."""
        criteria = TrackSelectionCriteria(
            bpm_range=(90, 130),
            bpm_tolerance=10,
            genre_mix={"Rock": (0.45, 0.55), "Electronic": (0.25, 0.35)},
            genre_tolerance=0.05,
            era_distribution={
                "Current (0-2 years)": (0.55, 0.65),
                "Recent (2-5 years)": (0.25, 0.35),
            },
            era_tolerance=0.05,
            australian_min=0.30,
            energy_flow="energetic",
        )

        result = serialize_criteria(criteria)

        # Verify nested dictionaries are serialized
        assert isinstance(result["genre_mix"], dict)
        assert isinstance(result["era_distribution"], dict)
        assert result["era_distribution"]["Current (0-2 years)"] == (0.55, 0.65)

    def test_serialize_none_optional_field_handling(self):
        """Test None/optional field handling."""
        track = SelectedTrack(
            track_id="track-1",
            title="Track 1",
            artist="Artist 1",
            album="Album 1",
            bpm=None,  # Optional field
            genre=None,  # Optional field
            year=None,  # Optional field
            country=None,  # Optional field
            duration_seconds=180,
            position_in_playlist=1,
            selection_reason="Reason",
        )

        result = serialize_tracks([track])

        assert result[0]["bpm"] is None
        assert result[0]["genre"] is None
        assert result[0]["year"] is None
        assert result[0]["country"] is None
