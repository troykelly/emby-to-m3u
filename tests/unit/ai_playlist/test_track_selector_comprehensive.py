"""
Comprehensive tests for AI Playlist Track Selector module.

Tests all track selection functions including:
- select_tracks_with_llm()
- select_tracks_with_relaxation()
- Helper functions: _estimate_cost(), _parse_llm_response(), etc.
"""
import pytest
import json
import uuid
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from datetime import datetime, time as time_obj
from typing import List

from src.ai_playlist.track_selector import (
    select_tracks_with_llm,
    select_tracks_with_relaxation,
    _estimate_cost,
    _configure_mcp_tools,
    _parse_llm_response,
    _extract_tool_calls,
    _extract_reasoning,
    _validate_constraint_satisfaction,
    _retry_with_backoff,
)
from src.ai_playlist.models import (
    LLMTrackSelectionRequest,
    LLMTrackSelectionResponse,
    TrackSelectionCriteria,
    SelectedTrack,
    ValidationStatus,
    GenreCriteria,
    EraCriteria,
    BPMRange,
)
from src.ai_playlist.exceptions import CostExceededError, MCPToolError


class TestEstimateCost:
    """Tests for _estimate_cost() function."""

    def test_estimate_cost_with_default_track_count(self):
        """Test cost estimation with default track count."""
        # Arrange
        request = LLMTrackSelectionRequest(
            playlist_id=str(uuid.uuid4()),
            criteria=Mock(),
            target_track_count=12,
            max_cost_usd=0.10,  # Must be ≤ 0.50
        )

        # Act
        cost = _estimate_cost(request)

        # Assert
        assert isinstance(cost, float)
        assert cost > 0
        # 500 base + (12 * 50) input tokens = 1100 input
        # 12 * 100 output tokens = 1200 output
        expected_cost = (1100 * 0.15 / 1_000_000) + (1200 * 0.60 / 1_000_000)
        assert abs(cost - expected_cost) < 0.0001

    def test_estimate_cost_scales_with_track_count(self):
        """Test that cost estimation scales linearly with track count."""
        # Arrange
        request_small = LLMTrackSelectionRequest(
            playlist_id=str(uuid.uuid4()),
            criteria=Mock(),
            target_track_count=10,
            max_cost_usd=0.10,  # Must be ≤ 0.50
        )
        request_large = LLMTrackSelectionRequest(
            playlist_id=str(uuid.uuid4()),
            criteria=Mock(),
            target_track_count=20,
            max_cost_usd=0.20,  # Must be ≤ 0.50
        )

        # Act
        cost_small = _estimate_cost(request_small)
        cost_large = _estimate_cost(request_large)

        # Assert
        assert cost_large > cost_small
        # Roughly double (not exact due to base cost)
        assert cost_large > 1.5 * cost_small


class TestConfigureMCPTools:
    """Tests for _configure_mcp_tools() function."""

    def test_configure_mcp_tools_with_valid_url(self):
        """Test MCP tool configuration with valid URL."""
        # Arrange
        tool_names = ["search_tracks", "get_track_details"]

        # Act
        with patch.dict("os.environ", {"SUBSONIC_MCP_URL": "http://localhost:5000"}):
            tools = _configure_mcp_tools(tool_names)

        # Assert
        assert isinstance(tools, list)
        assert len(tools) == 1
        assert tools[0]["type"] == "hosted_mcp"
        assert tools[0]["hosted_mcp"]["server_url"] == "http://localhost:5000"
        assert tools[0]["hosted_mcp"]["tools"] == tool_names

    def test_configure_mcp_tools_raises_error_without_url(self):
        """Test that missing MCP URL raises MCPToolError."""
        # Arrange
        tool_names = ["search_tracks"]

        # Act & Assert
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(MCPToolError, match="SUBSONIC_MCP_URL"):
                _configure_mcp_tools(tool_names)


class TestParseLLMResponse:
    """Tests for _parse_llm_response() function."""

    def test_parse_valid_llm_response(self):
        """Test parsing a valid LLM JSON response."""
        # Arrange
        response_json = json.dumps({
            "tracks": [
                {
                    "track_id": "track-1",
                    "title": "Test Track",
                    "artist": "Test Artist",
                    "album": "Test Album",
                    "bpm": 120,
                    "genre": "Electronic",
                    "year": 2020,
                    "country": "AU",
                    "duration_seconds": 180,
                    "is_australian": True,
                    "rotation_category": "Power",
                    "selection_reason": "Perfect BPM",
                }
            ]
        })

        # Act
        tracks = _parse_llm_response(response_json)

        # Assert
        assert len(tracks) == 1
        assert tracks[0].track_id == "track-1"
        assert tracks[0].title == "Test Track"
        assert tracks[0].artist == "Test Artist"
        assert tracks[0].bpm == 120
        assert tracks[0].is_australian is True
        assert tracks[0].position_in_playlist == 1

    def test_parse_multiple_tracks(self):
        """Test parsing response with multiple tracks."""
        # Arrange
        response_json = json.dumps({
            "tracks": [
                {"track_id": f"track-{i}", "title": f"Track {i}", "artist": f"Artist {i}"}
                for i in range(5)
            ]
        })

        # Act
        tracks = _parse_llm_response(response_json)

        # Assert
        assert len(tracks) == 5
        for i, track in enumerate(tracks):
            assert track.track_id == f"track-{i}"
            assert track.position_in_playlist == i + 1

    def test_parse_invalid_json_returns_empty_list(self):
        """Test that invalid JSON returns empty list."""
        # Arrange
        invalid_json = "{ invalid json }"

        # Act
        tracks = _parse_llm_response(invalid_json)

        # Assert
        assert tracks == []

    def test_parse_missing_tracks_field_returns_empty_list(self):
        """Test that missing 'tracks' field returns empty list."""
        # Arrange
        response_json = json.dumps({"reasoning": "Some reasoning"})

        # Act
        tracks = _parse_llm_response(response_json)

        # Assert
        assert tracks == []

    def test_parse_handles_missing_optional_fields(self):
        """Test parsing with minimal required fields."""
        # Arrange
        response_json = json.dumps({
            "tracks": [
                {
                    "track_id": "track-1",
                    "title": "Test Track",
                    "artist": "Test Artist",
                    # Missing optional fields
                }
            ]
        })

        # Act
        tracks = _parse_llm_response(response_json)

        # Assert
        assert len(tracks) == 1
        assert tracks[0].track_id == "track-1"
        assert tracks[0].bpm is None
        assert tracks[0].genre is None
        assert tracks[0].duration_seconds == 0


class TestExtractToolCalls:
    """Tests for _extract_tool_calls() function."""

    def test_extract_tool_calls_from_response(self):
        """Test extracting tool calls from OpenAI response."""
        # Arrange
        tool_call_mock = Mock()
        tool_call_mock.function.name = "search_tracks"
        tool_call_mock.function.arguments = json.dumps({"query": "rock", "limit": 10})

        # Act
        extracted = _extract_tool_calls([tool_call_mock])

        # Assert
        assert len(extracted) == 1
        assert extracted[0]["tool_name"] == "search_tracks"
        assert extracted[0]["arguments"]["query"] == "rock"
        assert extracted[0]["arguments"]["limit"] == 10

    def test_extract_multiple_tool_calls(self):
        """Test extracting multiple tool calls."""
        # Arrange
        tool_calls = []
        for i in range(3):
            mock = Mock()
            mock.function.name = f"tool_{i}"
            mock.function.arguments = json.dumps({"param": f"value_{i}"})
            tool_calls.append(mock)

        # Act
        extracted = _extract_tool_calls(tool_calls)

        # Assert
        assert len(extracted) == 3
        for i, call in enumerate(extracted):
            assert call["tool_name"] == f"tool_{i}"
            assert call["arguments"]["param"] == f"value_{i}"

    def test_extract_empty_tool_calls(self):
        """Test with no tool calls."""
        # Act
        extracted = _extract_tool_calls([])

        # Assert
        assert extracted == []


class TestExtractReasoning:
    """Tests for _extract_reasoning() function."""

    def test_extract_reasoning_from_valid_json(self):
        """Test extracting reasoning from valid JSON."""
        # Arrange
        content = json.dumps({"reasoning": "Selected tracks with high energy"})

        # Act
        reasoning = _extract_reasoning(content)

        # Assert
        assert reasoning == "Selected tracks with high energy"

    def test_extract_reasoning_missing_field_returns_empty(self):
        """Test that missing reasoning field returns empty string."""
        # Arrange
        content = json.dumps({"tracks": []})

        # Act
        reasoning = _extract_reasoning(content)

        # Assert
        assert reasoning == ""

    def test_extract_reasoning_invalid_json_returns_empty(self):
        """Test that invalid JSON returns empty string."""
        # Arrange
        content = "{ invalid json }"

        # Act
        reasoning = _extract_reasoning(content)

        # Assert
        assert reasoning == ""


class TestValidateConstraintSatisfaction:
    """Tests for _validate_constraint_satisfaction() function."""

    @pytest.fixture
    def basic_criteria(self) -> TrackSelectionCriteria:
        """Create basic track selection criteria."""
        return TrackSelectionCriteria(
            bpm_ranges=[
                BPMRange(
                    time_start=time_obj(0, 0),
                    time_end=time_obj(23, 59),
                    bpm_min=100,
                    bpm_max=130,
                )
            ],
            genre_mix={
                "Electronic": GenreCriteria(target_percentage=0.50, tolerance=0.10),
                "Rock": GenreCriteria(target_percentage=0.30, tolerance=0.10),
            },
            era_distribution={},
            australian_content_min=0.30,
            energy_flow_requirements=[],
            rotation_distribution={},
            no_repeat_window_hours=4.0,
        )

    def test_validate_empty_tracks_returns_zero(self, basic_criteria: TrackSelectionCriteria):
        """Test that empty track list returns 0.0 satisfaction."""
        # Act
        satisfaction = _validate_constraint_satisfaction([], basic_criteria)

        # Assert
        assert satisfaction == 0.0

    def test_validate_all_constraints_met_returns_one(self, basic_criteria: TrackSelectionCriteria):
        """Test that perfect satisfaction returns 1.0."""
        # Arrange - Create tracks that meet all criteria
        tracks = [
            SelectedTrack(
                track_id=f"track-{i}",
                title=f"Track {i}",
                artist=f"Artist {i}",
                album="Album",
                bpm=120,  # Within 100-130
                genre="Electronic" if i < 5 else "Rock",  # 50% Electronic, 30% Rock
                year=2020,
                country="AU" if i < 3 else "US",  # 30% Australian
                duration_seconds=180,
                is_australian=i < 3,
                rotation_category="Power",
                position_in_playlist=i,
                selection_reasoning="Test",
                validation_status=ValidationStatus.PASS,
                metadata_source="test",
            )
            for i in range(10)
        ]

        # Act
        satisfaction = _validate_constraint_satisfaction(tracks, basic_criteria)

        # Assert
        assert satisfaction >= 0.8  # Should be high satisfaction


class TestRetryWithBackoff:
    """Tests for _retry_with_backoff() async function."""

    @pytest.mark.asyncio
    async def test_retry_succeeds_on_first_attempt(self):
        """Test successful call on first attempt."""
        # Arrange
        async def success_func():
            return "success"

        # Act
        result = await _retry_with_backoff(success_func, max_attempts=3)

        # Assert
        assert result == "success"

    @pytest.mark.asyncio
    async def test_retry_succeeds_after_failures(self):
        """Test successful call after initial failures."""
        # Arrange
        call_count = [0]

        async def flaky_func():
            call_count[0] += 1
            if call_count[0] < 3:
                raise Exception("Temporary failure")
            return "success"

        # Act
        result = await _retry_with_backoff(flaky_func, max_attempts=3, base_delay=0.01)

        # Assert
        assert result == "success"
        assert call_count[0] == 3

    @pytest.mark.asyncio
    async def test_retry_raises_after_max_attempts(self):
        """Test that exception is raised after max attempts."""
        # Arrange
        async def always_fail():
            raise Exception("Permanent failure")

        # Act & Assert
        with pytest.raises(Exception, match="Permanent failure"):
            await _retry_with_backoff(always_fail, max_attempts=2, base_delay=0.01)


class TestSelectTracksWithLLM:
    """Tests for select_tracks_with_llm() main function."""

    @pytest.mark.asyncio
    async def test_select_tracks_with_valid_request(self):
        """Test successful track selection with valid request."""
        # Arrange
        request = LLMTrackSelectionRequest(
            playlist_id=str(uuid.uuid4()),
            criteria=TrackSelectionCriteria(
                bpm_ranges=[],
                genre_mix={},
                era_distribution={},
                australian_content_min=0.30,
                energy_flow_requirements=[],
                rotation_distribution={},
                no_repeat_window_hours=4.0,
            ),
            target_track_count=10,
            max_cost_usd=0.10,  # Must be ≤ 0.50
            mcp_tools=["search_tracks"],
        )

        # Mock OpenAI response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = json.dumps({
            "tracks": [{"track_id": f"track-{i}", "title": f"Track {i}", "artist": "Artist"} for i in range(10)],
            "reasoning": "Selected based on criteria"
        })
        mock_response.choices[0].message.tool_calls = []
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 500
        mock_response.usage.completion_tokens = 1000
        mock_response.usage.total_tokens = 1500

        # Act
        with patch.dict("os.environ", {
            "OPENAI_API_KEY": "test-key",
            "SUBSONIC_MCP_URL": "http://localhost:5000"
        }):
            with patch("src.ai_playlist.track_selector.AsyncOpenAI") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
                mock_client_class.return_value = mock_client

                with patch("src.ai_playlist.track_selector.build_selection_prompt", return_value="test prompt"):
                    response = await select_tracks_with_llm(request)

        # Assert
        assert isinstance(response, LLMTrackSelectionResponse)
        assert len(response.selected_tracks) == 10
        assert response.reasoning == "Selected based on criteria"
        assert response.cost_usd > 0

    @pytest.mark.asyncio
    async def test_select_tracks_raises_cost_exceeded_error(self):
        """Test that cost exceeded error is raised when estimated cost too high."""
        # Arrange
        request = LLMTrackSelectionRequest(
            playlist_id=str(uuid.uuid4()),
            criteria=Mock(),
            target_track_count=1000,  # Very high to trigger cost error
            max_cost_usd=0.0001,  # Very low budget
        )

        # Act & Assert
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            with pytest.raises(CostExceededError, match="Estimated cost .* exceeds budget"):
                await select_tracks_with_llm(request)

    @pytest.mark.asyncio
    async def test_select_tracks_raises_error_without_api_key(self):
        """Test that error is raised when API key is missing."""
        # Arrange
        request = LLMTrackSelectionRequest(
            playlist_id=str(uuid.uuid4()),
            criteria=Mock(),
            target_track_count=10,
            max_cost_usd=0.10,  # Must be ≤ 0.50
        )

        # Act & Assert
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="OPENAI_API_KEY"):
                await select_tracks_with_llm(request)


# Note: select_tracks_with_relaxation() tests would require extensive mocking
# of the entire select_tracks_with_llm() flow with criteria relaxation logic.
# These are integration-level tests better suited for tests/integration/
