"""
Unit Tests for Main Orchestration Module

Tests run_automation workflow, batch track selection, file operations, and error handling.
"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock, mock_open
from datetime import datetime

from src.ai_playlist.main import run_automation
from src.ai_playlist.workflow import (
    load_programming_document,
    batch_track_selection,
    save_playlist_file,
    sync_to_azuracast
)
# Serialization helpers are in workflow module
# We'll import them directly in tests
from src.ai_playlist.models import (
    DaypartSpec,
    PlaylistSpec,
    TrackSelectionCriteria,
    SelectedTrack,
    ValidationResult,
    Playlist
)
from src.ai_playlist.exceptions import (
    ParseError,
    ValidationError,
    CostExceededError,
    MCPToolError
)


class TestLoadProgrammingDocument:
    """Test suite for programming document loading."""

    def test_loads_valid_document(self, tmp_path):
        """Test loading a valid programming document."""
        doc_path = tmp_path / "test.md"
        doc_path.write_text("# Test Content\nValid document")

        content = load_programming_document(str(doc_path))

        assert content == "# Test Content\nValid document"

    def test_raises_file_not_found_for_missing_file(self):
        """Test FileNotFoundError for missing document."""
        with pytest.raises(FileNotFoundError, match="Programming document not found"):
            load_programming_document("/nonexistent/path/doc.md")

    def test_raises_value_error_for_empty_document(self, tmp_path):
        """Test ValueError for empty document."""
        empty_doc = tmp_path / "empty.md"
        empty_doc.write_text("")

        with pytest.raises(ValueError, match="Programming document is empty"):
            load_programming_document(str(empty_doc))

    def test_raises_value_error_for_whitespace_only_document(self, tmp_path):
        """Test ValueError for whitespace-only document."""
        whitespace_doc = tmp_path / "whitespace.md"
        whitespace_doc.write_text("   \n\t\n   ")

        with pytest.raises(ValueError, match="Programming document is empty"):
            load_programming_document(str(whitespace_doc))


class TestSavePlaylistFile:
    """Test suite for playlist file saving."""

    def test_saves_playlist_as_json(self, tmp_path):
        """Test playlist is saved as valid JSON file."""
        playlist = Playlist(
            id="test-123",
            name="Test_Playlist",
            tracks=[
                SelectedTrack(
                    track_id="track-1",
                    title="Test Track",
                    artist="Test Artist",
                    album="Test Album",
                    bpm=120,
                    genre="Rock",
                    year=2020,
                    country="Australia",
                    duration_seconds=180,
                    position=1,
                    selection_reason="Test reason"
                )
            ],
            spec=Mock(),
            validation_result=ValidationResult(
                constraint_satisfaction=0.85,
                bpm_satisfaction=0.90,
                genre_satisfaction=0.85,
                era_satisfaction=0.80,
                australian_content=0.40,
                flow_quality_score=0.75,
                bpm_variance=8.5,
                energy_progression="smooth",
                genre_diversity=0.70,
                gap_analysis={},
                passes_validation=True
            ),
            created_at=datetime.now()
        )

        output_file = save_playlist_file(playlist, tmp_path)

        assert output_file.exists()
        assert output_file.name == "Test_Playlist.json"

        # Verify JSON content
        import json
        with open(output_file) as f:
            data = json.load(f)

        assert data["id"] == "test-123"
        assert data["name"] == "Test_Playlist"
        assert len(data["tracks"]) == 1
        assert data["tracks"][0]["title"] == "Test Track"

    def test_saves_playlist_with_validation_metrics(self, tmp_path):
        """Test saved playlist includes validation metrics."""
        validation = ValidationResult(
            constraint_satisfaction=0.88,
            bpm_satisfaction=0.92,
            genre_satisfaction=0.87,
            era_satisfaction=0.84,
            australian_content=0.42,
            flow_quality_score=0.78,
            bpm_variance=7.2,
            energy_progression="building",
            genre_diversity=0.75,
            gap_analysis={"bpm_gaps": []},
            passes_validation=True
        )

        playlist = Playlist(
            id="test-456",
            name="Test_Playlist_2",
            tracks=[],
            spec=Mock(),
            validation_result=validation,
            created_at=datetime.now()
        )

        output_file = save_playlist_file(playlist, tmp_path)

        import json
        with open(output_file) as f:
            data = json.load(f)

        assert data["validation"]["constraint_satisfaction"] == 0.88
        assert data["validation"]["flow_quality_score"] == 0.78


class TestSerializationHelpers:
    """Test suite for serialization helper functions."""

    def test_serialize_criteria(self):
        """Test TrackSelectionCriteria serialization."""
        criteria = TrackSelectionCriteria(
            bpm_range=(90, 130),
            bpm_tolerance=10,
            genre_mix={"Rock": (0.45, 0.55), "Pop": (0.30, 0.40)},
            genre_tolerance=0.05,
            era_distribution={"Current (0-2 years)": (0.35, 0.45)},
            era_tolerance=0.05,
            australian_min=0.30,
            energy_flow="steady energy"
        )

        from src.ai_playlist.workflow import serialize_criteria
        serialized = serialize_criteria(criteria)

        assert serialized["bpm_range"] == (90, 130)
        assert serialized["bpm_tolerance"] == 10
        assert serialized["genre_mix"]["Rock"] == (0.45, 0.55)
        assert serialized["australian_min"] == 0.30
        assert serialized["energy_flow"] == "steady energy"

    def test_serialize_tracks(self):
        """Test SelectedTrack list serialization."""
        tracks = [
            SelectedTrack(
                track_id="track-1",
                title="Track 1",
                artist="Artist 1",
                album="Album 1",
                bpm=120,
                genre="Rock",
                year=2020,
                country="Australia",
                duration_seconds=180,
                position=1,
                selection_reason="Reason 1"
            ),
            SelectedTrack(
                track_id="track-2",
                title="Track 2",
                artist="Artist 2",
                album="Album 2",
                bpm=125,
                genre="Pop",
                year=2021,
                country="USA",
                duration_seconds=200,
                position=2,
                selection_reason="Reason 2"
            )
        ]

        from src.ai_playlist.workflow import serialize_tracks
        serialized = serialize_tracks(tracks)

        assert len(serialized) == 2
        assert serialized[0]["track_id"] == "track-1"
        assert serialized[0]["title"] == "Track 1"
        assert serialized[1]["track_id"] == "track-2"
        assert serialized[1]["bpm"] == 125

    def test_serialize_validation(self):
        """Test ValidationResult serialization."""
        validation = ValidationResult(
            constraint_satisfaction=0.85,
            bpm_satisfaction=0.90,
            genre_satisfaction=0.85,
            era_satisfaction=0.80,
            australian_content=0.40,
            flow_quality_score=0.75,
            bpm_variance=8.5,
            energy_progression="smooth",
            genre_diversity=0.70,
            gap_analysis={"bpm_gaps": []},
            passes_validation=True
        )

        from src.ai_playlist.workflow import serialize_validation
        serialized = serialize_validation(validation)

        assert serialized["constraint_satisfaction"] == 0.85
        assert serialized["flow_quality_score"] == 0.75
        assert serialized["bpm_variance"] == 8.5
        assert serialized["passes_validation"] is True


@pytest.mark.asyncio
class TestBatchTrackSelection:
    """Test suite for batch track selection."""

    async def test_batch_selection_success(self):
        """Test successful batch track selection."""
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

        mock_logger = Mock()
        mock_logger.get_log_file = Mock(return_value=Path("/tmp/log.jsonl"))
        mock_logger.log_decision = Mock()

        mock_response = Mock()
        mock_response.selected_tracks = [
            SelectedTrack(
                track_id=f"track-{i}",
                title=f"Track {i}",
                artist=f"Artist {i}",
                album=f"Album {i}",
                bpm=120,
                genre="Rock",
                year=2020,
                country="Australia",
                duration_seconds=180,
                position=i,
                selection_reason=f"Reason {i}"
            )
            for i in range(1, 61)
        ]
        mock_response.cost_usd = 0.005
        mock_response.execution_time_seconds = 5.0
        mock_response.reasoning = "Test reasoning"

        with patch("src.ai_playlist.main.select_tracks_with_llm", new=AsyncMock(return_value=mock_response)):
            with patch("src.ai_playlist.main.validate_playlist") as mock_validate:
                mock_validate.return_value = ValidationResult(
                    constraint_satisfaction=0.85,
                    bpm_satisfaction=0.90,
                    genre_satisfaction=0.85,
                    era_satisfaction=0.80,
                    australian_content=0.40,
                    flow_quality_score=0.75,
                    bpm_variance=8.5,
                    energy_progression="smooth",
                    genre_diversity=0.70,
                    gap_analysis={},
                    passes_validation=True
                )

                playlists = await batch_track_selection(
                    playlist_specs=[spec],
                    max_cost_usd=0.50,
                    decision_logger=mock_logger
                )

        assert len(playlists) == 1
        assert playlists[0].name == "Test_Playlist"

    async def test_batch_selection_cost_exceeded(self):
        """Test batch selection raises CostExceededError when budget exceeded."""
        spec = Mock()
        spec.name = "Test"
        spec.id = "test-123"
        spec.target_duration_minutes = 240
        spec.daypart = Mock(tracks_per_hour=15)
        spec.track_criteria = Mock()

        mock_logger = Mock()
        mock_logger.log_decision = Mock()

        mock_response = Mock()
        mock_response.selected_tracks = []
        mock_response.cost_usd = 1.00  # Exceeds budget
        mock_response.execution_time_seconds = 5.0
        mock_response.reasoning = "Test"

        with patch("src.ai_playlist.workflow.select_tracks_with_llm", new=AsyncMock(return_value=mock_response)):
            with patch("src.ai_playlist.workflow.validate_playlist"):
                with pytest.raises(CostExceededError, match="exceeds budget"):
                    await _batch_track_selection(
                        playlist_specs=[spec],
                        max_cost_usd=0.50,
                        decision_logger=mock_logger
                    )


@pytest.mark.asyncio
class TestSyncToAzuraCast:
    """Test suite for AzuraCast sync."""

    async def test_sync_success(self):
        """Test successful sync to AzuraCast."""
        playlist = Mock()
        playlist.name = "Test_Playlist"

        synced_playlist = Mock()
        synced_playlist.azuracast_id = 123

        with patch("src.ai_playlist.workflow.sync_playlist_to_azuracast", new=AsyncMock(return_value=synced_playlist)):
            results = await sync_to_azuracast([playlist])

        assert len(results) == 1
        assert results[playlist] == 123

    async def test_sync_handles_failures(self):
        """Test sync continues on individual playlist failures."""
        from src.ai_playlist.azuracast_sync import AzuraCastPlaylistSyncError

        playlist1 = Mock()
        playlist1.name = "Playlist_1"

        playlist2 = Mock()
        playlist2.name = "Playlist_2"

        synced = Mock()
        synced.azuracast_id = 456

        async def mock_sync(playlist):
            if playlist == playlist1:
                raise AzuraCastPlaylistSyncError("Sync failed")
            return synced

        with patch("src.ai_playlist.workflow.sync_playlist_to_azuracast", side_effect=mock_sync):
            results = await sync_to_azuracast([playlist1, playlist2])

        # Should have result for playlist2 only
        assert len(results) == 1
        assert results[playlist2] == 456


@pytest.mark.asyncio
class TestRunAutomation:
    """Test suite for run_automation orchestration."""

    async def test_run_automation_success(self, tmp_path):
        """Test complete automation workflow."""
        input_file = tmp_path / "test.md"
        input_file.write_text("# Test Content")

        output_dir = tmp_path / "output"

        # Mock all dependencies
        mock_dayparts = [
            DaypartSpec(
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
        ]

        with patch("src.ai_playlist.main.parse_programming_document", return_value=mock_dayparts):
            with patch("src.ai_playlist.main.generate_playlist_specs") as mock_gen:
                mock_gen.return_value = [Mock()]

                with patch("src.ai_playlist.main.configure_and_verify_mcp", new=AsyncMock()):
                    with patch("src.ai_playlist.workflow.batch_track_selection", new=AsyncMock()) as mock_batch:
                        mock_playlist = Mock()
                        mock_playlist.name = "Test"
                        mock_playlist.validation_result = Mock()
                        mock_playlist.validation_result.is_valid = Mock(return_value=True)
                        mock_playlist.validation_result.constraint_satisfaction = 0.85
                        mock_playlist.validation_result.flow_quality_score = 0.75
                        mock_playlist.spec = Mock()
                        mock_playlist.spec.track_criteria = Mock(bpm_tolerance=10)
                        mock_batch.return_value = [mock_playlist]

                        with patch("src.ai_playlist.workflow.save_playlist_file", return_value=Path("/tmp/playlist.json")):
                            summary = await run_automation(
                                input_file=str(input_file),
                                output_dir=str(output_dir),
                                max_cost_usd=0.50,
                                dry_run=True
                            )

        assert summary["success_count"] == 1
        assert summary["failed_count"] == 0
        assert summary["total_cost"] >= 0

    async def test_run_automation_no_valid_playlists_raises_error(self, tmp_path):
        """Test automation raises ValidationError when no playlists pass validation."""
        input_file = tmp_path / "test.md"
        input_file.write_text("# Test")

        mock_dayparts = [Mock()]

        with patch("src.ai_playlist.main.parse_programming_document", return_value=mock_dayparts):
            with patch("src.ai_playlist.main.generate_playlist_specs", return_value=[Mock()]):
                with patch("src.ai_playlist.main.configure_and_verify_mcp", new=AsyncMock()):
                    with patch("src.ai_playlist.workflow.batch_track_selection", new=AsyncMock()) as mock_batch:
                        # All playlists fail validation
                        mock_playlist = Mock()
                        mock_playlist.validation_result = Mock()
                        mock_playlist.validation_result.is_valid = Mock(return_value=False)
                        mock_batch.return_value = [mock_playlist]

                        with pytest.raises(ValidationError, match="No playlists passed validation"):
                            await run_automation(
                                input_file=str(input_file),
                                output_dir=str(tmp_path / "output"),
                                max_cost_usd=0.50,
                                dry_run=True
                            )
