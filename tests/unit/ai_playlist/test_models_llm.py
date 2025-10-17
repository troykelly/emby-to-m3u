"""
Comprehensive tests for models/llm.py module.

Tests all LLM model dataclasses including:
- LLMTrackSelectionRequest validation
- SelectedTrack validation
- LLMTrackSelectionResponse validation
- Playlist validation
"""
import pytest
import uuid
from datetime import datetime
from decimal import Decimal
from unittest.mock import Mock

from src.ai_playlist.models.llm import (
    LLMTrackSelectionRequest,
    SelectedTrack,
    LLMTrackSelectionResponse,
    Playlist,
)
from src.ai_playlist.models.core import TrackSelectionCriteria
from src.ai_playlist.models.validation import ValidationResult, ValidationStatus, FlowQualityMetrics


class TestLLMTrackSelectionRequest:
    """Tests for LLMTrackSelectionRequest validation."""

    def test_valid_request(self):
        """Test creating valid LLM track selection request."""
        # Arrange & Act
        request = LLMTrackSelectionRequest(
            playlist_id=str(uuid.uuid4()),
            criteria=Mock(spec=TrackSelectionCriteria),
            target_track_count=12,
            max_cost_usd=0.10,
        )

        # Assert
        assert request.playlist_id is not None
        assert request.target_track_count == 12
        assert len(request.mcp_tools) == 4  # Default tools

    def test_invalid_playlist_id_raises_error(self):
        """Test that invalid UUID playlist ID raises ValueError."""
        # Act & Assert
        with pytest.raises(ValueError, match="Playlist ID must be valid UUID4"):
            LLMTrackSelectionRequest(
                playlist_id="not-a-uuid",
                criteria=Mock(spec=TrackSelectionCriteria),
                target_track_count=12,
                max_cost_usd=0.10,
            )

    def test_zero_target_track_count_raises_error(self):
        """Test that zero target track count raises ValueError."""
        # Act & Assert
        with pytest.raises(ValueError, match="Target track count must be > 0"):
            LLMTrackSelectionRequest(
                playlist_id=str(uuid.uuid4()),
                criteria=Mock(spec=TrackSelectionCriteria),
                target_track_count=0,
                max_cost_usd=0.10,
            )

    def test_excessive_target_track_count_raises_error(self):
        """Test that track count > 1000 raises ValueError."""
        # Act & Assert
        with pytest.raises(ValueError, match="Target track count must be > 0 and ≤ 1000"):
            LLMTrackSelectionRequest(
                playlist_id=str(uuid.uuid4()),
                criteria=Mock(spec=TrackSelectionCriteria),
                target_track_count=1001,
                max_cost_usd=0.10,
            )

    def test_empty_mcp_tools_raises_error(self):
        """Test that empty MCP tools list raises ValueError."""
        # Act & Assert
        with pytest.raises(ValueError, match="MCP tools must be non-empty"):
            LLMTrackSelectionRequest(
                playlist_id=str(uuid.uuid4()),
                criteria=Mock(spec=TrackSelectionCriteria),
                target_track_count=12,
                mcp_tools=[],
                max_cost_usd=0.10,
            )

    def test_zero_max_cost_raises_error(self):
        """Test that zero max cost raises ValueError."""
        # Act & Assert
        with pytest.raises(ValueError, match="Max cost must be > 0"):
            LLMTrackSelectionRequest(
                playlist_id=str(uuid.uuid4()),
                criteria=Mock(spec=TrackSelectionCriteria),
                target_track_count=12,
                max_cost_usd=0.0,
            )

    def test_excessive_max_cost_raises_error(self):
        """Test that max cost > 0.50 raises ValueError."""
        # Act & Assert
        with pytest.raises(ValueError, match="Max cost must be > 0 and ≤ 0.50"):
            LLMTrackSelectionRequest(
                playlist_id=str(uuid.uuid4()),
                criteria=Mock(spec=TrackSelectionCriteria),
                target_track_count=12,
                max_cost_usd=1.0,
            )

    def test_zero_timeout_raises_error(self):
        """Test that zero timeout raises ValueError."""
        # Act & Assert
        with pytest.raises(ValueError, match="Timeout must be > 0"):
            LLMTrackSelectionRequest(
                playlist_id=str(uuid.uuid4()),
                criteria=Mock(spec=TrackSelectionCriteria),
                target_track_count=12,
                max_cost_usd=0.10,
                timeout_seconds=0,
            )

    def test_excessive_timeout_raises_error(self):
        """Test that timeout > 2700 raises ValueError."""
        # Act & Assert
        with pytest.raises(ValueError, match="Timeout must be > 0 and ≤ 2700"):
            LLMTrackSelectionRequest(
                playlist_id=str(uuid.uuid4()),
                criteria=Mock(spec=TrackSelectionCriteria),
                target_track_count=12,
                max_cost_usd=0.10,
                timeout_seconds=3000,
            )


class TestSelectedTrack:
    """Tests for SelectedTrack validation."""

    def test_valid_selected_track(self):
        """Test creating valid selected track."""
        # Arrange & Act
        track = SelectedTrack(
            track_id="track-123",
            title="Test Track",
            artist="Test Artist",
            album="Test Album",
            bpm=120,
            genre="Electronic",
            year=2024,
            country="AU",
            duration_seconds=180,
            position=1,
            selection_reason="Great track for morning drive",
        )

        # Assert
        assert track.track_id == "track-123"
        assert track.title == "Test Track"
        assert track.bpm == 120

    def test_empty_track_id_raises_error(self):
        """Test that empty track ID raises ValueError."""
        # Act & Assert
        with pytest.raises(ValueError, match="Track ID must be non-empty"):
            SelectedTrack(
                track_id="",
                title="Test Track",
                artist="Test Artist",
                album="Test Album",
                bpm=120,
                genre="Electronic",
                year=2024,
                country="AU",
                duration_seconds=180,
                position=1,
                selection_reason="Test",
            )

    def test_empty_title_raises_error(self):
        """Test that empty title raises ValueError."""
        # Act & Assert
        with pytest.raises(ValueError, match="title must be non-empty"):
            SelectedTrack(
                track_id="track-123",
                title="",
                artist="Test Artist",
                album="Test Album",
                bpm=120,
                genre="Electronic",
                year=2024,
                country="AU",
                duration_seconds=180,
                position=1,
                selection_reason="Test",
            )

    def test_excessive_title_length_raises_error(self):
        """Test that title > 200 chars raises ValueError."""
        # Act & Assert
        with pytest.raises(ValueError, match="title must be non-empty and max 200 chars"):
            SelectedTrack(
                track_id="track-123",
                title="A" * 201,
                artist="Test Artist",
                album="Test Album",
                bpm=120,
                genre="Electronic",
                year=2024,
                country="AU",
                duration_seconds=180,
                position=1,
                selection_reason="Test",
            )

    def test_empty_artist_raises_error(self):
        """Test that empty artist raises ValueError."""
        # Act & Assert
        with pytest.raises(ValueError, match="artist must be non-empty"):
            SelectedTrack(
                track_id="track-123",
                title="Test Track",
                artist="",
                album="Test Album",
                bpm=120,
                genre="Electronic",
                year=2024,
                country="AU",
                duration_seconds=180,
                position=1,
                selection_reason="Test",
            )

    def test_zero_bpm_raises_error(self):
        """Test that BPM = 0 raises ValueError."""
        # Act & Assert
        with pytest.raises(ValueError, match="BPM must be > 0"):
            SelectedTrack(
                track_id="track-123",
                title="Test Track",
                artist="Test Artist",
                album="Test Album",
                bpm=0,
                genre="Electronic",
                year=2024,
                country="AU",
                duration_seconds=180,
                position=1,
                selection_reason="Test",
            )

    def test_excessive_bpm_raises_error(self):
        """Test that BPM > 300 raises ValueError."""
        # Act & Assert
        with pytest.raises(ValueError, match="BPM must be > 0 and ≤ 300"):
            SelectedTrack(
                track_id="track-123",
                title="Test Track",
                artist="Test Artist",
                album="Test Album",
                bpm=301,
                genre="Electronic",
                year=2024,
                country="AU",
                duration_seconds=180,
                position=1,
                selection_reason="Test",
            )

    def test_none_bpm_is_valid(self):
        """Test that None BPM is valid."""
        # Arrange & Act
        track = SelectedTrack(
            track_id="track-123",
            title="Test Track",
            artist="Test Artist",
            album="Test Album",
            bpm=None,
            genre="Electronic",
            year=2024,
            country="AU",
            duration_seconds=180,
            position=1,
            selection_reason="Test",
        )

        # Assert
        assert track.bpm is None

    def test_empty_genre_raises_error(self):
        """Test that empty genre string raises ValueError."""
        # Act & Assert
        with pytest.raises(ValueError, match="Genre must be non-empty"):
            SelectedTrack(
                track_id="track-123",
                title="Test Track",
                artist="Test Artist",
                album="Test Album",
                bpm=120,
                genre="",
                year=2024,
                country="AU",
                duration_seconds=180,
                position=1,
                selection_reason="Test",
            )

    def test_excessive_genre_length_raises_error(self):
        """Test that genre > 50 chars raises ValueError."""
        # Act & Assert
        with pytest.raises(ValueError, match="Genre must be non-empty and max 50 chars"):
            SelectedTrack(
                track_id="track-123",
                title="Test Track",
                artist="Test Artist",
                album="Test Album",
                bpm=120,
                genre="A" * 51,
                year=2024,
                country="AU",
                duration_seconds=180,
                position=1,
                selection_reason="Test",
            )

    def test_year_too_old_raises_error(self):
        """Test that year < 1900 raises ValueError."""
        # Act & Assert
        with pytest.raises(ValueError, match="Year must be 1900-"):
            SelectedTrack(
                track_id="track-123",
                title="Test Track",
                artist="Test Artist",
                album="Test Album",
                bpm=120,
                genre="Electronic",
                year=1899,
                country="AU",
                duration_seconds=180,
                position=1,
                selection_reason="Test",
            )

    def test_year_future_raises_error(self):
        """Test that year > current_year + 1 raises ValueError."""
        # Arrange
        future_year = datetime.now().year + 2

        # Act & Assert
        with pytest.raises(ValueError, match="Year must be 1900-"):
            SelectedTrack(
                track_id="track-123",
                title="Test Track",
                artist="Test Artist",
                album="Test Album",
                bpm=120,
                genre="Electronic",
                year=future_year,
                country="AU",
                duration_seconds=180,
                position=1,
                selection_reason="Test",
            )

    def test_zero_duration_raises_error(self):
        """Test that duration = 0 raises ValueError."""
        # Act & Assert
        with pytest.raises(ValueError, match="Duration must be > 0"):
            SelectedTrack(
                track_id="track-123",
                title="Test Track",
                artist="Test Artist",
                album="Test Album",
                bpm=120,
                genre="Electronic",
                year=2024,
                country="AU",
                duration_seconds=0,
                position=1,
                selection_reason="Test",
            )

    def test_zero_position_raises_error(self):
        """Test that position = 0 raises ValueError."""
        # Act & Assert
        with pytest.raises(ValueError, match="Position must be > 0"):
            SelectedTrack(
                track_id="track-123",
                title="Test Track",
                artist="Test Artist",
                album="Test Album",
                bpm=120,
                genre="Electronic",
                year=2024,
                country="AU",
                duration_seconds=180,
                position=0,
                selection_reason="Test",
            )

    def test_empty_selection_reason_raises_error(self):
        """Test that empty selection reason raises ValueError."""
        # Act & Assert
        with pytest.raises(ValueError, match="Selection reason must be non-empty"):
            SelectedTrack(
                track_id="track-123",
                title="Test Track",
                artist="Test Artist",
                album="Test Album",
                bpm=120,
                genre="Electronic",
                year=2024,
                country="AU",
                duration_seconds=180,
                position=1,
                selection_reason="",
            )

    def test_excessive_selection_reason_length_raises_error(self):
        """Test that selection reason > 500 chars raises ValueError."""
        # Act & Assert
        with pytest.raises(ValueError, match="Selection reason must be non-empty and max 500 chars"):
            SelectedTrack(
                track_id="track-123",
                title="Test Track",
                artist="Test Artist",
                album="Test Album",
                bpm=120,
                genre="Electronic",
                year=2024,
                country="AU",
                duration_seconds=180,
                position=1,
                selection_reason="A" * 501,
            )


class TestLLMTrackSelectionResponse:
    """Tests for LLMTrackSelectionResponse validation."""

    @pytest.fixture
    def valid_track(self):
        """Create a valid SelectedTrack for testing."""
        return SelectedTrack(
            track_id="track-123",
            title="Test Track",
            artist="Test Artist",
            album="Test Album",
            bpm=120,
            genre="Electronic",
            year=2024,
            country="AU",
            duration_seconds=180,
            position=1,
            selection_reason="Test",
        )

    def test_valid_response(self, valid_track):
        """Test creating valid LLM track selection response."""
        # Arrange & Act
        response = LLMTrackSelectionResponse(
            request_id=str(uuid.uuid4()),
            selected_tracks=[valid_track],
            tool_calls=[
                {"tool_name": "search_tracks", "arguments": {}, "result": {}}
            ],
            reasoning="Selected based on criteria",
            cost_usd=0.05,
            execution_time_seconds=10.5,
        )

        # Assert
        assert response.request_id is not None
        assert len(response.selected_tracks) == 1
        assert response.cost_usd == 0.05

    def test_invalid_request_id_raises_error(self, valid_track):
        """Test that invalid UUID request ID raises ValueError."""
        # Act & Assert
        with pytest.raises(ValueError, match="Request ID must be valid UUID4"):
            LLMTrackSelectionResponse(
                request_id="not-a-uuid",
                selected_tracks=[valid_track],
                tool_calls=[],
                reasoning="Test",
                cost_usd=0.05,
                execution_time_seconds=10.5,
            )

    def test_empty_selected_tracks_raises_error(self):
        """Test that empty selected tracks list raises ValueError."""
        # Act & Assert
        with pytest.raises(ValueError, match="Selected tracks must be non-empty"):
            LLMTrackSelectionResponse(
                request_id=str(uuid.uuid4()),
                selected_tracks=[],
                tool_calls=[],
                reasoning="Test",
                cost_usd=0.05,
                execution_time_seconds=10.5,
            )

    def test_invalid_tool_call_structure_raises_error(self, valid_track):
        """Test that tool call missing required keys raises ValueError."""
        # Act & Assert
        with pytest.raises(ValueError, match="Tool call must have tool_name, arguments, result"):
            LLMTrackSelectionResponse(
                request_id=str(uuid.uuid4()),
                selected_tracks=[valid_track],
                tool_calls=[
                    {"tool_name": "search_tracks"}  # Missing arguments and result
                ],
                reasoning="Test",
                cost_usd=0.05,
                execution_time_seconds=10.5,
            )

    def test_empty_reasoning_raises_error(self, valid_track):
        """Test that empty reasoning raises ValueError."""
        # Act & Assert
        with pytest.raises(ValueError, match="Reasoning must be non-empty"):
            LLMTrackSelectionResponse(
                request_id=str(uuid.uuid4()),
                selected_tracks=[valid_track],
                tool_calls=[],
                reasoning="",
                cost_usd=0.05,
                execution_time_seconds=10.5,
            )

    def test_excessive_reasoning_length_raises_error(self, valid_track):
        """Test that reasoning > 2000 chars raises ValueError."""
        # Act & Assert
        with pytest.raises(ValueError, match="Reasoning must be non-empty and max 2000 chars"):
            LLMTrackSelectionResponse(
                request_id=str(uuid.uuid4()),
                selected_tracks=[valid_track],
                tool_calls=[],
                reasoning="A" * 2001,
                cost_usd=0.05,
                execution_time_seconds=10.5,
            )

    def test_negative_cost_raises_error(self, valid_track):
        """Test that negative cost raises ValueError."""
        # Act & Assert
        with pytest.raises(ValueError, match="Cost must be ≥ 0"):
            LLMTrackSelectionResponse(
                request_id=str(uuid.uuid4()),
                selected_tracks=[valid_track],
                tool_calls=[],
                reasoning="Test",
                cost_usd=-0.05,
                execution_time_seconds=10.5,
            )

    def test_negative_execution_time_raises_error(self, valid_track):
        """Test that negative execution time raises ValueError."""
        # Act & Assert
        with pytest.raises(ValueError, match="Execution time must be ≥ 0"):
            LLMTrackSelectionResponse(
                request_id=str(uuid.uuid4()),
                selected_tracks=[valid_track],
                tool_calls=[],
                reasoning="Test",
                cost_usd=0.05,
                execution_time_seconds=-1.0,
            )

    def test_future_created_at_raises_error(self, valid_track):
        """Test that future created_at raises ValueError."""
        # Arrange
        from datetime import timedelta
        future_time = datetime.now() + timedelta(days=1)

        # Act & Assert
        with pytest.raises(ValueError, match="Created at cannot be in future"):
            LLMTrackSelectionResponse(
                request_id=str(uuid.uuid4()),
                selected_tracks=[valid_track],
                tool_calls=[],
                reasoning="Test",
                cost_usd=0.05,
                execution_time_seconds=10.5,
                created_at=future_time,
            )
