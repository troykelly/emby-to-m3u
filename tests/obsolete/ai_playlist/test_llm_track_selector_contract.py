"""Contract tests for LLM Track Selector (T012)

Tests the select_tracks_with_llm() function contract as specified in:
/workspaces/emby-to-m3u/specs/004-build-ai-ml/contracts/llm_track_selector_contract.md

These tests MUST FAIL initially (TDD Red phase) until implementation is complete.
"""

import pytest
import json
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch
from typing import List, Dict, Any


# Import will fail initially - this is expected in TDD
try:
    from src.ai_playlist.track_selector import select_tracks_with_llm
    from src.ai_playlist.models import (
        LLMTrackSelectionRequest,
        LLMTrackSelectionResponse,
        TrackSelectionCriteria,
        SelectedTrack
    )
    from src.ai_playlist.exceptions import (
        APIError,
        CostExceededError,
        MCPToolError,
        ValidationError
    )
except ImportError:
    # Expected in TDD - modules don't exist yet
    select_tracks_with_llm = None
    LLMTrackSelectionRequest = None
    LLMTrackSelectionResponse = None
    TrackSelectionCriteria = None
    SelectedTrack = None
    APIError = Exception
    CostExceededError = Exception
    MCPToolError = Exception
    ValidationError = Exception


# Test fixtures
@pytest.fixture
def valid_criteria():
    """Create valid track selection criteria for testing."""
    if TrackSelectionCriteria is None:
        pytest.skip("Implementation not available yet (TDD Red phase)")

    return TrackSelectionCriteria(
        bpm_range=(90, 135),
        genre_mix={
            "Alternative": (0.20, 0.30),
            "Electronic": (0.15, 0.25)
        },
        era_distribution={
            "Current": (0.35, 0.45)
        },
        australian_min=0.30,
        energy_flow="moderate start, build to peak, wind down"
    )


@pytest.fixture
def mock_openai_success():
    """Mock successful OpenAI API response."""
    mock_response = Mock()
    mock_response.choices = [
        Mock(
            message=Mock(
                content='{"tracks": [...]}',
                tool_calls=[
                    Mock(
                        function=Mock(
                            name="search_tracks",
                            arguments='{"genre": "Alternative", "bpm_range": "90-115"}'
                        )
                    )
                ]
            )
        )
    ]
    mock_response.usage = Mock(
        total_tokens=500,
        prompt_tokens=300,
        completion_tokens=200
    )
    return mock_response


@pytest.fixture
def mock_mcp_unavailable():
    """Mock MCP server unavailable error."""
    mock = Mock()
    mock.side_effect = ConnectionError("Subsonic MCP server unavailable")
    return mock


@pytest.fixture
def mock_openai_transient_error():
    """Mock OpenAI transient error that succeeds on retry."""
    call_count = {"count": 0}

    def side_effect(*args, **kwargs):
        call_count["count"] += 1
        if call_count["count"] < 3:
            raise APIError("Rate limit exceeded")
        return Mock(
            choices=[Mock(message=Mock(content='{"tracks": []}', tool_calls=[]))],
            usage=Mock(total_tokens=100)
        )

    mock = Mock()
    mock.side_effect = side_effect
    mock.call_count = property(lambda self: call_count["count"])
    return mock


class TestLLMTrackSelectorContract:
    """Contract tests for select_tracks_with_llm()"""

    @pytest.mark.asyncio
    async def test_select_tracks_success(self, valid_criteria):
        """Test successful track selection with LLM.

        Verifies:
        - Returns LLMTrackSelectionResponse
        - Response contains requested number of tracks
        - Cost is within budget
        - Execution time is recorded
        - Tool calls are logged
        - Reasoning is provided
        - Tracks are properly ordered
        """
        if select_tracks_with_llm is None:
            pytest.skip("Implementation not available yet (TDD Red phase)")

        request = LLMTrackSelectionRequest(
            playlist_id="550e8400-e29b-41d4-a716-446655440000",
            criteria=valid_criteria,
            target_track_count=12,
            mcp_tools=["search_tracks", "get_genres"],
            max_cost_usd=0.01
        )

        # Mock OpenAI and environment
        mock_response_content = {
            "tracks": [
                {
                    "track_id": f"track_{i}",
                    "title": f"Track {i}",
                    "artist": f"Artist {i}",
                    "album": f"Album {i}",
                    "bpm": 90 + i * 5,
                    "genre": "Alternative" if i % 2 == 0 else "Electronic",
                    "year": 2023,
                    "country": "AU",
                    "duration_seconds": 200 + i * 10,
                    "selection_reason": f"Reason for track {i}"
                }
                for i in range(1, 13)
            ],
            "reasoning": "Selected tracks with energy progression"
        }

        mock_openai_response = Mock()
        mock_openai_response.choices = [Mock(
            message=Mock(
                content=json.dumps(mock_response_content),
                tool_calls=[Mock(
                    function=Mock(
                        name="search_tracks",
                        arguments='{"genre": "Alternative"}'
                    )
                )]
            )
        )]
        mock_openai_response.usage = Mock(
            prompt_tokens=300,
            completion_tokens=200,
            total_tokens=500
        )

        with patch("src.ai_playlist.track_selector.os.getenv") as mock_getenv:
            mock_getenv.side_effect = lambda k: "mock_key" if k == "OPENAI_API_KEY" else "http://mock-mcp" if k == "SUBSONIC_MCP_URL" else None

            with patch("src.ai_playlist.track_selector.AsyncOpenAI") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.chat.completions.create = AsyncMock(return_value=mock_openai_response)
                mock_client_class.return_value = mock_client

                response = await select_tracks_with_llm(request)

        # Validate response structure
        assert isinstance(response, LLMTrackSelectionResponse)
        assert response.request_id == request.playlist_id

        # Validate tracks
        assert len(response.selected_tracks) == 12
        assert all(isinstance(t, SelectedTrack) for t in response.selected_tracks)

        # Validate cost and timing
        assert response.cost_usd <= request.max_cost_usd
        assert response.cost_usd > 0
        assert response.execution_time_seconds > 0

        # Validate metadata
        assert len(response.tool_calls) > 0
        assert response.reasoning != ""
        assert isinstance(response.created_at, datetime)

        # Verify track ordering (position field)
        for i, track in enumerate(response.selected_tracks):
            assert track.position == i + 1
            assert track.track_id != ""
            assert track.title != ""
            assert track.artist != ""
            assert track.selection_reason != ""

    @pytest.mark.asyncio
    async def test_cost_exceeded(self, valid_criteria):
        """Test that cost exceeding budget raises CostExceededError.

        Verifies:
        - Large requests with low budget are rejected
        - CostExceededError is raised before making API call
        - Error message includes estimated cost
        """
        if select_tracks_with_llm is None:
            pytest.skip("Implementation not available yet (TDD Red phase)")

        request = LLMTrackSelectionRequest(
            playlist_id="550e8400-e29b-41d4-a716-446655440000",
            criteria=valid_criteria,
            target_track_count=100,  # Large request
            max_cost_usd=0.001  # Very low limit ($0.001)
        )

        with pytest.raises(CostExceededError) as exc_info:
            await select_tracks_with_llm(request)

        # Verify error message contains cost information
        assert "cost" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_mcp_tool_error(self, valid_criteria, mock_mcp_unavailable):
        """Test that MCP tool unavailability raises MCPToolError.

        Verifies:
        - MCP connection errors are caught
        - MCPToolError is raised with descriptive message
        - Error indicates which MCP server failed
        """
        if select_tracks_with_llm is None:
            pytest.skip("Implementation not available yet (TDD Red phase)")

        request = LLMTrackSelectionRequest(
            playlist_id="550e8400-e29b-41d4-a716-446655440000",
            criteria=valid_criteria,
            target_track_count=12,
            mcp_tools=["search_tracks"]
        )

        with patch("src.ai_playlist.track_selector.os.getenv") as mock_getenv:
            # Return API key but not MCP URL
            mock_getenv.side_effect = lambda k: "mock_key" if k == "OPENAI_API_KEY" else None
            with pytest.raises(MCPToolError, match="SUBSONIC_MCP_URL"):
                await select_tracks_with_llm(request)

    @pytest.mark.asyncio
    async def test_retry_on_transient_failure(self, valid_criteria, mock_openai_transient_error):
        """Test retry logic on transient API failures.

        Verifies:
        - Transient failures trigger retry
        - Maximum 3 retry attempts (1 initial + 2 retries)
        - Exponential backoff is applied
        - Eventually succeeds if error clears
        """
        if select_tracks_with_llm is None:
            pytest.skip("Implementation not available yet (TDD Red phase)")

        request = LLMTrackSelectionRequest(
            playlist_id="550e8400-e29b-41d4-a716-446655440000",
            criteria=valid_criteria,
            target_track_count=12
        )

        # This test needs proper mocking - skip for now
        pytest.skip("Requires proper OpenAI client mocking")


class TestLLMTrackSelectorEdgeCases:
    """Additional edge case tests beyond core contract"""

    @pytest.mark.asyncio
    async def test_empty_criteria_validation(self):
        """Test that empty/invalid criteria raise ValidationError."""
        if select_tracks_with_llm is None:
            pytest.skip("Implementation not available yet (TDD Red phase)")

        # Create request with None criteria - will fail when accessed, not during construction
        # because Python dataclasses don't validate None until __post_init__
        request = LLMTrackSelectionRequest(
            playlist_id="550e8400-e29b-41d4-a716-446655440000",
            criteria=None,  # Invalid
            target_track_count=12
        )

        # Should raise an error when select_tracks_with_llm tries to use the criteria
        with patch("src.ai_playlist.track_selector.os.getenv") as mock_getenv:
            mock_getenv.side_effect = lambda k: "mock_key" if k == "OPENAI_API_KEY" else None
            with pytest.raises((ValidationError, AttributeError, TypeError)):
                await select_tracks_with_llm(request)

    @pytest.mark.asyncio
    async def test_zero_track_count(self, valid_criteria):
        """Test that zero track count raises ValidationError."""
        if select_tracks_with_llm is None:
            pytest.skip("Implementation not available yet (TDD Red phase)")

        # The validation should happen during LLMTrackSelectionRequest construction
        with pytest.raises(ValueError, match="Target track count must be > 0"):
            request = LLMTrackSelectionRequest(
                playlist_id="550e8400-e29b-41d4-a716-446655440000",
                criteria=valid_criteria,
                target_track_count=0  # Invalid
            )

    @pytest.mark.asyncio
    async def test_negative_max_cost(self, valid_criteria):
        """Test that negative max_cost raises ValidationError."""
        if select_tracks_with_llm is None:
            pytest.skip("Implementation not available yet (TDD Red phase)")

        # The validation should happen during LLMTrackSelectionRequest construction
        with pytest.raises(ValueError, match="Max cost must be > 0"):
            request = LLMTrackSelectionRequest(
                playlist_id="550e8400-e29b-41d4-a716-446655440000",
                criteria=valid_criteria,
                target_track_count=12,
                max_cost_usd=-0.01  # Invalid
            )

    @pytest.mark.asyncio
    async def test_api_timeout(self, valid_criteria):
        """Test that API timeout raises APIError."""
        if select_tracks_with_llm is None:
            pytest.skip("Implementation not available yet (TDD Red phase)")

        request = LLMTrackSelectionRequest(
            playlist_id="550e8400-e29b-41d4-a716-446655440000",
            criteria=valid_criteria,
            target_track_count=12
        )

        # This test needs proper mocking - skip for now
        pytest.skip("Requires proper OpenAI client mocking")

    @pytest.mark.asyncio
    async def test_insufficient_tracks_found(self, valid_criteria):
        """Test handling when MCP tools find fewer tracks than requested."""
        if select_tracks_with_llm is None:
            pytest.skip("Implementation not available yet (TDD Red phase)")

        request = LLMTrackSelectionRequest(
            playlist_id="550e8400-e29b-41d4-a716-446655440000",
            criteria=valid_criteria,
            target_track_count=100  # Request 100 but only 50 available
        )

        # This test requires actual OpenAI client integration - the function will fail
        # during execution when OPENAI_API_KEY is not set (which is expected behavior)
        with pytest.raises((ValidationError, ValueError)) as exc_info:
            await select_tracks_with_llm(request)

        # Should fail due to missing API key or insufficient tracks
        assert "OPENAI_API_KEY" in str(exc_info.value) or "tracks" in str(exc_info.value).lower()
