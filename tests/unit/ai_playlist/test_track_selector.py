"""
Comprehensive Unit Tests for Track Selector (0% → 90%+ coverage)

Tests all aspects of LLM-based track selection including:
- LLM selection with OpenAI mocking
- Cost tracking and budget enforcement
- Timeout handling
- Retry logic with exponential backoff
- Constraint relaxation iterations
- Helper functions
- Error handling

Target: 90%+ coverage of track_selector.py (170 statements)
"""

import pytest
import asyncio
import json
import uuid
from unittest.mock import Mock, AsyncMock, patch, MagicMock, call
from datetime import datetime
import os

from src.ai_playlist.track_selector import (
    select_tracks_with_llm,
    select_tracks_with_relaxation,
    _estimate_cost,
    # _build_prompt,  # Removed - no longer exists
    # _build_relaxation_prompt,  # Removed - no longer exists
    _configure_mcp_tools,
    _call_openai_api,
    _retry_with_backoff,
    _parse_llm_response,
    _extract_tool_calls,
    _extract_reasoning,
    _validate_constraint_satisfaction,
    PRICING,
)
from src.ai_playlist.models import (
    LLMTrackSelectionRequest,
    LLMTrackSelectionResponse,
    TrackSelectionCriteria,
    SelectedTrack,
)
from src.ai_playlist.exceptions import (
    CostExceededError,
    MCPToolError,
    APIError,
)


# Test Fixtures

@pytest.fixture
def basic_criteria():
    """Basic track selection criteria for tests."""
    return TrackSelectionCriteria(
        bpm_range=(90, 130),
        bpm_tolerance=10,
        genre_mix={"Rock": (0.4, 0.6), "Pop": (0.2, 0.4)},
        genre_tolerance=0.05,
        era_distribution={"Current (0-2 years)": (0.3, 0.5)},
        era_tolerance=0.05,
        australian_min=0.30,
        energy_flow="uplifting progression",
    )


@pytest.fixture
def basic_request(basic_criteria):
    """Basic LLM track selection request."""
    return LLMTrackSelectionRequest(
        playlist_id="2d1f901c-7c41-444e-9739-75016b37c599",
        criteria=basic_criteria,
        target_track_count=12,
        mcp_tools=["search_tracks", "get_genres"],
        prompt_template="Test prompt",
        max_cost_usd=0.01,
        timeout_seconds=30,
    )


@pytest.fixture
def mock_openai_response():
    """Mock OpenAI API response."""
    tracks_data = [
        {
            "track_id": f"track-{i}",
            "title": f"Song {i}",
            "artist": f"Artist {i}",
            "album": f"Album {i}",
            "bpm": 100 + i,
            "genre": "Rock" if i % 2 == 0 else "Pop",
            "year": 2024,
            "country": "AU" if i < 4 else "US",
            "duration_seconds": 180,
            "selection_reason": f"Selected for test {i}",
        }
        for i in range(12)
    ]

    content = json.dumps({
        "tracks": tracks_data,
        "reasoning": "Selected tracks based on criteria"
    })

    mock_response = Mock()
    mock_response.choices = [
        Mock(
            message=Mock(
                content=content,
                tool_calls=None
            )
        )
    ]
    mock_response.usage = Mock(
        prompt_tokens=500,
        completion_tokens=1200,
        total_tokens=1700
    )

    return mock_response


# LLM Selection Tests (15 tests)

@pytest.mark.asyncio
class TestSelectTracksWithLLM:
    """Test suite for select_tracks_with_llm function."""

    async def test_success_path_with_mocked_openai(self, basic_request, mock_openai_response, monkeypatch):
        """Test successful LLM track selection with mocked OpenAI."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key-123")
        monkeypatch.setenv("SUBSONIC_MCP_URL", "http://test-mcp.local")

        with patch('src.ai_playlist.track_selector.AsyncOpenAI') as mock_client_class:
            mock_client = Mock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_openai_response)
            mock_client_class.return_value = mock_client

            response = await select_tracks_with_llm(basic_request)

            assert isinstance(response, LLMTrackSelectionResponse)
            assert response.request_id == "2d1f901c-7c41-444e-9739-75016b37c599"
            assert len(response.selected_tracks) == 12
            assert response.cost_usd > 0
            assert response.execution_time_seconds > 0
            assert response.reasoning == "Selected tracks based on criteria"

    async def test_cost_tracking_token_counting(self, basic_request, mock_openai_response, monkeypatch):
        """Test cost calculation from token counts."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("SUBSONIC_MCP_URL", "http://test-mcp.local")

        with patch('src.ai_playlist.track_selector.AsyncOpenAI') as mock_client_class:
            mock_client = Mock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_openai_response)
            mock_client_class.return_value = mock_client

            response = await select_tracks_with_llm(basic_request)

            # Verify cost calculation: 500 input + 1200 output tokens
            expected_cost = (500 * PRICING["input_tokens"]) + (1200 * PRICING["output_tokens"])
            assert abs(response.cost_usd - expected_cost) < 0.0001

    async def test_cost_pricing_calculations(self, basic_request, monkeypatch):
        """Test pricing calculations match GPT-4o-mini rates."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("SUBSONIC_MCP_URL", "http://test-mcp.local")

        # Verify pricing constants
        assert PRICING["input_tokens"] == 0.15 / 1_000_000
        assert PRICING["output_tokens"] == 0.60 / 1_000_000

        # Need at least one track for response validation
        content = json.dumps({
            "tracks": [{
                "track_id": "test-1",
                "title": "Song 1",
                "artist": "Artist 1",
                "album": "Album 1",
                "bpm": 100,
                "genre": "Rock",
                "year": 2024,
                "country": "AU",
                "duration_seconds": 180,
                "selection_reason": "Test"
            }],
            "reasoning": "test"
        })

        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content=content, tool_calls=None))]
        mock_response.usage = Mock(prompt_tokens=1000, completion_tokens=2000, total_tokens=3000)

        with patch('src.ai_playlist.track_selector.AsyncOpenAI') as mock_client_class:
            mock_client = Mock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            response = await select_tracks_with_llm(basic_request)

            # 1000 * $0.00000015 + 2000 * $0.00000060 = $0.0015
            expected_cost = 1000 * 0.00000015 + 2000 * 0.00000060
            assert abs(response.cost_usd - expected_cost) < 0.00001

    async def test_timeout_enforcement_default_30s(self, basic_request, monkeypatch):
        """Test default 30s timeout enforcement."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("SUBSONIC_MCP_URL", "http://test-mcp.local")

        with patch('src.ai_playlist.track_selector.AsyncOpenAI') as mock_client_class:
            mock_client = Mock()
            # Simulate timeout
            async def slow_call(*args, **kwargs):
                await asyncio.sleep(35)
            mock_client.chat.completions.create = slow_call
            mock_client_class.return_value = mock_client

            with pytest.raises(MCPToolError, match="timed out after 30s"):
                await select_tracks_with_llm(basic_request)

    async def test_timeout_enforcement_custom(self, basic_criteria, monkeypatch):
        """Test custom timeout enforcement."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("SUBSONIC_MCP_URL", "http://test-mcp.local")

        request = LLMTrackSelectionRequest(
            playlist_id="3e2f901c-7c41-444e-9739-75016b37c599",
            criteria=basic_criteria,
            target_track_count=12,
            mcp_tools=["search_tracks"],
            prompt_template="Test",
            max_cost_usd=0.01,
            timeout_seconds=5,  # Custom short timeout
        )

        with patch('src.ai_playlist.track_selector.AsyncOpenAI') as mock_client_class:
            mock_client = Mock()
            async def slow_call(*args, **kwargs):
                await asyncio.sleep(10)
            mock_client.chat.completions.create = slow_call
            mock_client_class.return_value = mock_client

            with pytest.raises(MCPToolError, match="timed out after 5s"):
                await select_tracks_with_llm(request)

    async def test_openai_api_error_handling(self, basic_request, monkeypatch):
        """Test OpenAI API error handling."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("SUBSONIC_MCP_URL", "http://test-mcp.local")

        with patch('src.ai_playlist.track_selector.AsyncOpenAI') as mock_client_class:
            mock_client = Mock()
            mock_client.chat.completions.create = AsyncMock(side_effect=Exception("API Error"))
            mock_client_class.return_value = mock_client

            with pytest.raises(Exception, match="API Error"):
                await select_tracks_with_llm(basic_request)

    async def test_mcp_tool_integration_mocked(self, basic_request, monkeypatch):
        """Test MCP tool integration with mocked tools."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("SUBSONIC_MCP_URL", "http://test-mcp.local")

        with patch('src.ai_playlist.track_selector.AsyncOpenAI') as mock_client_class:
            mock_client = Mock()
            # Need at least one track
            content = json.dumps({
                "tracks": [{
                    "track_id": "test-1",
                    "title": "Song",
                    "artist": "Artist",
                    "album": "Album",
                    "bpm": 100,
                    "genre": "Rock",
                    "year": 2024,
                    "country": "AU",
                    "duration_seconds": 180,
                    "selection_reason": "Test"
                }],
                "reasoning": "test"
            })
            mock_response = Mock()
            mock_response.choices = [Mock(message=Mock(content=content, tool_calls=None))]
            mock_response.usage = Mock(prompt_tokens=100, completion_tokens=200, total_tokens=300)
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            response = await select_tracks_with_llm(basic_request)

            # Note: tools parameter removed from API call in recent update
            # MCP tools are configured but not passed to OpenAI directly
            assert response is not None
            assert len(response.selected_tracks) > 0

    async def test_response_parsing_selected_track_extraction(self, basic_request, mock_openai_response, monkeypatch):
        """Test extraction of SelectedTrack objects from LLM JSON response."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("SUBSONIC_MCP_URL", "http://test-mcp.local")

        with patch('src.ai_playlist.track_selector.AsyncOpenAI') as mock_client_class:
            mock_client = Mock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_openai_response)
            mock_client_class.return_value = mock_client

            response = await select_tracks_with_llm(basic_request)

            # Verify track extraction
            assert len(response.selected_tracks) == 12
            for i, track in enumerate(response.selected_tracks):
                assert isinstance(track, SelectedTrack)
                assert track.track_id == f"track-{i}"
                assert track.title == f"Song {i}"
                assert track.position == i + 1

    async def test_tool_calls_recording(self, basic_request, monkeypatch):
        """Test recording of tool_calls from LLM response."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("SUBSONIC_MCP_URL", "http://test-mcp.local")

        mock_tool_call = Mock()
        mock_tool_call.function.name = "search_tracks"
        mock_tool_call.function.arguments = '{"genre": "Rock", "bpm_min": 90}'

        # Need at least one track
        content = json.dumps({
            "tracks": [{
                "track_id": "test-1",
                "title": "Song",
                "artist": "Artist",
                "album": "Album",
                "bpm": 100,
                "genre": "Rock",
                "year": 2024,
                "country": "AU",
                "duration_seconds": 180,
                "selection_reason": "Test"
            }],
            "reasoning": "Used search_tracks"
        })

        mock_response = Mock()
        mock_response.choices = [
            Mock(message=Mock(
                content=content,
                tool_calls=[mock_tool_call]
            ))
        ]
        mock_response.usage = Mock(prompt_tokens=100, completion_tokens=200, total_tokens=300)

        with patch('src.ai_playlist.track_selector.AsyncOpenAI') as mock_client_class:
            mock_client = Mock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            response = await select_tracks_with_llm(basic_request)

            # Verify tool calls recorded
            assert len(response.tool_calls) == 1
            assert response.tool_calls[0]["tool_name"] == "search_tracks"
            assert response.tool_calls[0]["arguments"]["genre"] == "Rock"

    async def test_reasoning_capture(self, basic_request, mock_openai_response, monkeypatch):
        """Test capture of reasoning from LLM response."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("SUBSONIC_MCP_URL", "http://test-mcp.local")

        with patch('src.ai_playlist.track_selector.AsyncOpenAI') as mock_client_class:
            mock_client = Mock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_openai_response)
            mock_client_class.return_value = mock_client

            response = await select_tracks_with_llm(basic_request)

            assert response.reasoning == "Selected tracks based on criteria"

    async def test_max_cost_usd_budget_enforcement_estimated(self, basic_criteria, monkeypatch):
        """Test CostExceededError when estimated cost exceeds budget."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("SUBSONIC_MCP_URL", "http://test-mcp.local")

        # Create request with very low budget
        request = LLMTrackSelectionRequest(
            playlist_id="4e2f901c-7c41-444e-9739-75016b37c599",
            criteria=basic_criteria,
            target_track_count=1000,  # Large number
            mcp_tools=["search_tracks"],
            prompt_template="Test",
            max_cost_usd=0.0001,  # Very low budget
            timeout_seconds=30,
        )

        with pytest.raises(CostExceededError, match="Estimated cost .* exceeds budget"):
            await select_tracks_with_llm(request)

    async def test_max_cost_usd_budget_enforcement_actual(self, basic_request, monkeypatch):
        """Test CostExceededError when actual cost exceeds budget."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("SUBSONIC_MCP_URL", "http://test-mcp.local")

        # Mock response with high token usage
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content='{"tracks":[],"reasoning":"test"}', tool_calls=None))]
        mock_response.usage = Mock(prompt_tokens=100000, completion_tokens=200000, total_tokens=300000)

        with patch('src.ai_playlist.track_selector.AsyncOpenAI') as mock_client_class:
            mock_client = Mock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            with pytest.raises(CostExceededError, match="Actual cost .* exceeds budget"):
                await select_tracks_with_llm(basic_request)

    async def test_mcp_unavailable_raises_error(self, basic_request, monkeypatch):
        """Test MCPToolError when SUBSONIC_MCP_URL not set."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.delenv("SUBSONIC_MCP_URL", raising=False)

        with pytest.raises(MCPToolError, match="SUBSONIC_MCP_URL environment variable not set"):
            await select_tracks_with_llm(basic_request)

    async def test_empty_response_handling(self, basic_request, monkeypatch):
        """Test handling of LLM response with parsing that yields empty tracks (parse error returns empty list)."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("SUBSONIC_MCP_URL", "http://test-mcp.local")

        # Note: LLMTrackSelectionResponse requires non-empty selected_tracks
        # But _parse_llm_response can return empty list on malformed data
        # This tests the parse function indirectly - if parse returns empty,
        # the response construction will fail validation (expected)

        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content='{"bad_key":"no tracks"}', tool_calls=None))]
        mock_response.usage = Mock(prompt_tokens=100, completion_tokens=50, total_tokens=150)

        with patch('src.ai_playlist.track_selector.AsyncOpenAI') as mock_client_class:
            mock_client = Mock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            # Should raise ValueError because selected_tracks is empty after parsing
            with pytest.raises(ValueError, match="Selected tracks must be non-empty"):
                await select_tracks_with_llm(basic_request)

    async def test_malformed_json_response_handling(self, basic_request, monkeypatch):
        """Test handling of malformed JSON in LLM response."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("SUBSONIC_MCP_URL", "http://test-mcp.local")

        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content='Invalid JSON {{{', tool_calls=None))]
        mock_response.usage = Mock(prompt_tokens=100, completion_tokens=50, total_tokens=150)

        with patch('src.ai_playlist.track_selector.AsyncOpenAI') as mock_client_class:
            mock_client = Mock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            # Parse error returns empty list, which fails validation
            with pytest.raises(ValueError, match="Selected tracks must be non-empty"):
                await select_tracks_with_llm(basic_request)


# Retry Logic Tests (10 tests)

@pytest.mark.asyncio
class TestRetryLogic:
    """Test suite for retry logic with exponential backoff."""

    async def test_exponential_backoff_delays(self):
        """Test 3-retry exponential backoff with 1s, 2s, 4s delays."""
        call_count = 0

        async def failing_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Retry needed")
            return "success"

        with patch('src.ai_playlist.track_selector.asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            result = await _retry_with_backoff(failing_func, max_attempts=3, base_delay=1.0)

            assert result == "success"
            assert call_count == 3
            # Verify exponential delays: 1s, 2s
            assert mock_sleep.call_count == 2
            delays = [call.args[0] for call in mock_sleep.call_args_list]
            assert delays[0] == 1.0  # 2^0 * 1
            assert delays[1] == 2.0  # 2^1 * 1

    async def test_success_on_retry_1(self):
        """Test success on first retry attempt."""
        call_count = 0

        async def func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("First attempt fails")
            return "success"

        with patch('src.ai_playlist.track_selector.asyncio.sleep', return_value=asyncio.sleep(0)):
            result = await _retry_with_backoff(func, max_attempts=3)
            assert result == "success"
            assert call_count == 2

    async def test_success_on_retry_2(self):
        """Test success on second retry attempt."""
        call_count = 0

        async def func():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise Exception("Retry")
            return "success"

        with patch('src.ai_playlist.track_selector.asyncio.sleep', return_value=asyncio.sleep(0)):
            result = await _retry_with_backoff(func, max_attempts=3)
            assert result == "success"
            assert call_count == 3

    async def test_success_on_retry_3(self):
        """Test success on third retry attempt."""
        call_count = 0

        async def func():
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                raise Exception("Keep retrying")
            return "success"

        with patch('src.ai_playlist.track_selector.asyncio.sleep', return_value=asyncio.sleep(0)):
            result = await _retry_with_backoff(func, max_attempts=4)
            assert result == "success"
            assert call_count == 4

    async def test_failure_after_all_retries_exhausted(self):
        """Test failure after all retries exhausted."""
        async def always_fails():
            raise Exception("Always fails")

        with patch('src.ai_playlist.track_selector.asyncio.sleep', return_value=asyncio.sleep(0)):
            with pytest.raises(Exception, match="Always fails"):
                await _retry_with_backoff(always_fails, max_attempts=3)

    async def test_api_error_triggers_retry(self):
        """Test that APIError triggers retry."""
        call_count = 0

        async def func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise APIError("API failed")
            return "success"

        with patch('src.ai_playlist.track_selector.asyncio.sleep', return_value=asyncio.sleep(0)):
            result = await _retry_with_backoff(func, max_attempts=3)
            assert result == "success"
            assert call_count == 2

    async def test_timeout_triggers_retry(self):
        """Test that asyncio.TimeoutError triggers retry."""
        call_count = 0

        async def func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise asyncio.TimeoutError()
            return "success"

        with patch('src.ai_playlist.track_selector.asyncio.sleep', return_value=asyncio.sleep(0)):
            result = await _retry_with_backoff(func, max_attempts=3)
            assert result == "success"
            assert call_count == 2

    async def test_mcp_error_triggers_retry(self):
        """Test that MCPToolError triggers retry."""
        call_count = 0

        async def func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise MCPToolError("MCP unavailable")
            return "success"

        with patch('src.ai_playlist.track_selector.asyncio.sleep', return_value=asyncio.sleep(0)):
            result = await _retry_with_backoff(func, max_attempts=3)
            assert result == "success"

    async def test_exponential_delay_calculation(self):
        """Test exponential delay calculation: base * 2^attempt."""
        async def failing_func():
            raise Exception("Test")

        with patch('src.ai_playlist.track_selector.asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(Exception):
                await _retry_with_backoff(failing_func, max_attempts=4, base_delay=2.0)

            delays = [call.args[0] for call in mock_sleep.call_args_list]
            assert delays[0] == 2.0   # 2 * 2^0
            assert delays[1] == 4.0   # 2 * 2^1
            assert delays[2] == 8.0   # 2 * 2^2

    async def test_max_delay_cap_60s(self):
        """Test max_delay cap at 60s."""
        async def failing_func():
            raise Exception("Test")

        with patch('src.ai_playlist.track_selector.asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(Exception):
                await _retry_with_backoff(failing_func, max_attempts=10, base_delay=20.0, max_delay=60.0)

            delays = [call.args[0] for call in mock_sleep.call_args_list]
            # 20 * 2^0 = 20, 20 * 2^1 = 40, 20 * 2^2 = 80 (capped at 60)
            assert delays[0] == 20.0
            assert delays[1] == 40.0
            assert delays[2] == 60.0  # Capped
            assert all(d <= 60.0 for d in delays)


# Constraint Relaxation Tests (15 tests)

@pytest.mark.asyncio
class TestSelectTracksWithRelaxation:
    """Test suite for constraint relaxation iterations."""

    async def test_strict_criteria_iteration_0(self, basic_criteria, monkeypatch):
        """Test iteration 0 with strict criteria (no relaxation)."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("SUBSONIC_MCP_URL", "http://test-mcp.local")

        # Mock successful response with high satisfaction
        mock_tracks = [
            SelectedTrack(
                track_id=f"track-{i}",
                title=f"Song {i}",
                artist=f"Artist {i}",
                album="Album",
                bpm=100,
                genre="Rock",
                year=2024,
                country="AU" if i < 4 else "US",
                duration_seconds=180,
                position=i + 1,
                selection_reason="Test"
            )
            for i in range(12)
        ]

        with patch('src.ai_playlist.track_selector.select_tracks_with_llm') as mock_select:
            mock_select.return_value = LLMTrackSelectionResponse(
                request_id="9e2f901c-7c41-444e-9739-75016b37c599",
                selected_tracks=mock_tracks,
                tool_calls=[],
                reasoning="Test",
                cost_usd=0.001,
                execution_time_seconds=1.0,
                created_at=datetime.now()
            )

            with patch('src.ai_playlist.track_selector.uuid.uuid4') as mock_uuid:
                mock_uuid.return_value = uuid.UUID("9e2f901c-7c41-444e-9739-75016b37c599")
                tracks = await select_tracks_with_relaxation(basic_criteria, max_iterations=3)

            assert len(tracks) == 12
            # First call should use original criteria
            first_call_criteria = mock_select.call_args_list[0][0][0].criteria
            assert first_call_criteria.bpm_range == (90, 130)

    async def test_bpm_relaxation_iteration_1(self, basic_criteria, monkeypatch):
        """Test BPM relaxation in iteration 1 (±10 BPM)."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("SUBSONIC_MCP_URL", "http://test-mcp.local")

        # Mock low satisfaction on first attempt
        mock_tracks = [SelectedTrack(
            track_id=f"track-{i}", title=f"Song {i}", artist=f"Artist {i}",
            album="Album", bpm=100, genre="Rock", year=2024, country="US",
            duration_seconds=180, position=i+1, selection_reason="Test"
        ) for i in range(12)]

        call_count = 0

        async def mock_select_func(request):
            nonlocal call_count
            call_count += 1
            # Return success on iteration 1 (BPM relaxed)
            return LLMTrackSelectionResponse(
                request_id=request.playlist_id,
                selected_tracks=mock_tracks if call_count == 2 else [],
                tool_calls=[],
                reasoning="Test",
                cost_usd=0.001,
                execution_time_seconds=1.0,
                created_at=datetime.now()
            )

        with patch('src.ai_playlist.track_selector.select_tracks_with_llm', side_effect=mock_select_func):
            with patch('src.ai_playlist.track_selector.uuid.uuid4') as mock_uuid:
                mock_uuid.return_value = uuid.UUID("9e2f901c-7c41-444e-9739-75016b37c599")
                with patch('src.ai_playlist.track_selector._validate_constraint_satisfaction', side_effect=[0.5, 0.85]):
                    tracks = await select_tracks_with_relaxation(basic_criteria, max_iterations=3)

        assert len(tracks) == 12
        assert call_count == 2  # Iteration 0 + 1

    async def test_genre_relaxation_iteration_2(self, basic_criteria, monkeypatch):
        """Test genre relaxation in iteration 2 (±5% tolerance)."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("SUBSONIC_MCP_URL", "http://test-mcp.local")

        mock_tracks = [SelectedTrack(
            track_id=f"track-{i}", title=f"Song {i}", artist=f"Artist {i}",
            album="Album", bpm=100, genre="Rock", year=2024, country="AU" if i < 4 else "US",
            duration_seconds=180, position=i+1, selection_reason="Test"
        ) for i in range(12)]

        call_count = 0
        satisfaction_values = [0.5, 0.6, 0.85]

        async def mock_select_func(request):
            nonlocal call_count
            call_count += 1
            return LLMTrackSelectionResponse(
                request_id=request.playlist_id,
                selected_tracks=mock_tracks,
                tool_calls=[],
                reasoning="Test",
                cost_usd=0.001,
                execution_time_seconds=1.0,
                created_at=datetime.now()
            )

        with patch('src.ai_playlist.track_selector.select_tracks_with_llm', side_effect=mock_select_func):
            with patch('src.ai_playlist.track_selector.uuid.uuid4') as mock_uuid:
                mock_uuid.return_value = uuid.UUID("9e2f901c-7c41-444e-9739-75016b37c599")
                with patch('src.ai_playlist.track_selector._validate_constraint_satisfaction', side_effect=satisfaction_values):
                    tracks = await select_tracks_with_relaxation(basic_criteria, max_iterations=3)

        assert call_count == 3  # Iterations 0, 1, 2

    async def test_era_relaxation_iteration_3(self, basic_criteria, monkeypatch):
        """Test era relaxation in iteration 3 (±5% tolerance)."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("SUBSONIC_MCP_URL", "http://test-mcp.local")

        mock_tracks = [SelectedTrack(
            track_id=f"track-{i}", title=f"Song {i}", artist=f"Artist {i}",
            album="Album", bpm=100, genre="Rock", year=2024, country="AU" if i < 4 else "US",
            duration_seconds=180, position=i+1, selection_reason="Test"
        ) for i in range(12)]

        call_count = 0
        satisfaction_values = [0.5, 0.6, 0.7, 0.85]

        async def mock_select_func(request):
            nonlocal call_count
            call_count += 1
            return LLMTrackSelectionResponse(
                request_id=request.playlist_id,
                selected_tracks=mock_tracks,
                tool_calls=[],
                reasoning="Test",
                cost_usd=0.001,
                execution_time_seconds=1.0,
                created_at=datetime.now()
            )

        with patch('src.ai_playlist.track_selector.select_tracks_with_llm', side_effect=mock_select_func):
            with patch('src.ai_playlist.track_selector.uuid.uuid4') as mock_uuid:
                mock_uuid.return_value = uuid.UUID("9e2f901c-7c41-444e-9739-75016b37c599")
                with patch('src.ai_playlist.track_selector._validate_constraint_satisfaction', side_effect=satisfaction_values):
                    tracks = await select_tracks_with_relaxation(basic_criteria, max_iterations=3)

        assert call_count == 4  # Iterations 0, 1, 2, 3

    async def test_australian_minimum_maintained_30_percent(self, monkeypatch):
        """Test Australian minimum is maintained at 30% (non-negotiable)."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("SUBSONIC_MCP_URL", "http://test-mcp.local")

        criteria = TrackSelectionCriteria(
            bpm_range=(90, 130),
            bpm_tolerance=10,
            genre_mix={"Rock": (0.5, 0.7)},
            genre_tolerance=0.05,
            era_distribution={"Current (0-2 years)": (0.4, 0.6)},
            era_tolerance=0.05,
            australian_min=0.30,
            energy_flow="test",
        )

        captured_criteria = []

        async def capture_criteria(request):
            captured_criteria.append(request.criteria)
            return LLMTrackSelectionResponse(
                request_id=request.playlist_id,
                selected_tracks=[],
                tool_calls=[],
                reasoning="Test",
                cost_usd=0.001,
                execution_time_seconds=1.0,
                created_at=datetime.now()
            )

        with patch('src.ai_playlist.track_selector.select_tracks_with_llm', side_effect=capture_criteria):
            with patch('src.ai_playlist.track_selector.uuid.uuid4') as mock_uuid:
                mock_uuid.return_value = uuid.UUID("9e2f901c-7c41-444e-9739-75016b37c599")
                with patch('src.ai_playlist.track_selector._validate_constraint_satisfaction', return_value=0.85):
                    await select_tracks_with_relaxation(criteria, max_iterations=3)

        # All iterations should maintain 30% Australian minimum
        for c in captured_criteria:
            assert c.australian_min == 0.30

    async def test_constraint_satisfaction_validation_after_each_iteration(self, basic_criteria, monkeypatch):
        """Test constraint satisfaction is validated after each iteration."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("SUBSONIC_MCP_URL", "http://test-mcp.local")

        mock_tracks = [SelectedTrack(
            track_id=f"track-{i}", title=f"Song {i}", artist=f"Artist {i}",
            album="Album", bpm=100, genre="Rock", year=2024, country="AU" if i < 4 else "US",
            duration_seconds=180, position=i+1, selection_reason="Test"
        ) for i in range(12)]

        with patch('src.ai_playlist.track_selector.select_tracks_with_llm') as mock_select:
            mock_select.return_value = LLMTrackSelectionResponse(
                request_id="9e2f901c-7c41-444e-9739-75016b37c599",
                selected_tracks=mock_tracks,
                tool_calls=[],
                reasoning="Test",
                cost_usd=0.001,
                execution_time_seconds=1.0,
                created_at=datetime.now()
            )

            with patch('src.ai_playlist.track_selector.uuid.uuid4') as mock_uuid:
                mock_uuid.return_value = uuid.UUID("9e2f901c-7c41-444e-9739-75016b37c599")
                with patch('src.ai_playlist.track_selector._validate_constraint_satisfaction', side_effect=[0.5, 0.85]) as mock_validate:
                    tracks = await select_tracks_with_relaxation(basic_criteria, max_iterations=3)

                    # Validation called twice (iteration 0 and 1)
                    assert mock_validate.call_count == 2

    async def test_stop_when_satisfaction_80_percent(self, basic_criteria, monkeypatch):
        """Test stops when satisfaction ≥80%."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("SUBSONIC_MCP_URL", "http://test-mcp.local")

        mock_tracks = [SelectedTrack(
            track_id=f"track-{i}", title=f"Song {i}", artist=f"Artist {i}",
            album="Album", bpm=100, genre="Rock", year=2024, country="AU" if i < 4 else "US",
            duration_seconds=180, position=i+1, selection_reason="Test"
        ) for i in range(12)]

        call_count = 0

        async def mock_select_func(request):
            nonlocal call_count
            call_count += 1
            return LLMTrackSelectionResponse(
                request_id=request.playlist_id,
                selected_tracks=mock_tracks,
                tool_calls=[],
                reasoning="Test",
                cost_usd=0.001,
                execution_time_seconds=1.0,
                created_at=datetime.now()
            )

        with patch('src.ai_playlist.track_selector.select_tracks_with_llm', side_effect=mock_select_func):
            with patch('src.ai_playlist.track_selector.uuid.uuid4') as mock_uuid:
                mock_uuid.return_value = uuid.UUID("9e2f901c-7c41-444e-9739-75016b37c599")
                with patch('src.ai_playlist.track_selector._validate_constraint_satisfaction', return_value=0.82):
                    tracks = await select_tracks_with_relaxation(basic_criteria, max_iterations=3)

        # Should stop after first iteration when satisfaction is 82%
        assert call_count == 1

    async def test_max_3_iterations_enforcement(self, basic_criteria, monkeypatch):
        """Test maximum 3 iterations enforcement."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("SUBSONIC_MCP_URL", "http://test-mcp.local")

        mock_tracks = [SelectedTrack(
            track_id=f"track-{i}", title=f"Song {i}", artist=f"Artist {i}",
            album="Album", bpm=100, genre="Rock", year=2024, country="AU",
            duration_seconds=180, position=i+1, selection_reason="Test"
        ) for i in range(12)]

        call_count = 0

        async def mock_select_func(request):
            nonlocal call_count
            call_count += 1
            return LLMTrackSelectionResponse(
                request_id=request.playlist_id,
                selected_tracks=mock_tracks,
                tool_calls=[],
                reasoning="Test",
                cost_usd=0.001,
                execution_time_seconds=1.0,
                created_at=datetime.now()
            )

        with patch('src.ai_playlist.track_selector.select_tracks_with_llm', side_effect=mock_select_func):
            with patch('src.ai_playlist.track_selector.uuid.uuid4') as mock_uuid:
                mock_uuid.return_value = uuid.UUID("9e2f901c-7c41-444e-9739-75016b37c599")
                # Always return low satisfaction to force all iterations
                with patch('src.ai_playlist.track_selector._validate_constraint_satisfaction', return_value=0.5):
                    tracks = await select_tracks_with_relaxation(basic_criteria, max_iterations=3)

        # Should run iterations 0, 1, 2, 3 (4 total)
        assert call_count == 4

    async def test_best_effort_return_if_all_fail(self, basic_criteria, monkeypatch):
        """Test best effort return if all iterations fail."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("SUBSONIC_MCP_URL", "http://test-mcp.local")

        mock_tracks = [SelectedTrack(
            track_id=f"track-{i}", title=f"Song {i}", artist=f"Artist {i}",
            album="Album", bpm=100, genre="Rock", year=2024, country="US",
            duration_seconds=180, position=i+1, selection_reason="Test"
        ) for i in range(12)]

        async def mock_select_func(request):
            return LLMTrackSelectionResponse(
                request_id=request.playlist_id,
                selected_tracks=mock_tracks,
                tool_calls=[],
                reasoning="Test",
                cost_usd=0.001,
                execution_time_seconds=1.0,
                created_at=datetime.now()
            )

        with patch('src.ai_playlist.track_selector.select_tracks_with_llm', side_effect=mock_select_func):
            with patch('src.ai_playlist.track_selector.uuid.uuid4') as mock_uuid:
                mock_uuid.return_value = uuid.UUID("9e2f901c-7c41-444e-9739-75016b37c599")
                # All iterations have low satisfaction
                with patch('src.ai_playlist.track_selector._validate_constraint_satisfaction', return_value=0.5):
                    tracks = await select_tracks_with_relaxation(basic_criteria, max_iterations=3)

        # Should return best effort tracks
        assert len(tracks) == 12

    async def test_relaxation_decision_logging(self, basic_criteria, monkeypatch, caplog):
        """Test relaxation decision logging."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("SUBSONIC_MCP_URL", "http://test-mcp.local")

        mock_tracks = [SelectedTrack(
            track_id="track-1", title="Song", artist="Artist",
            album="Album", bpm=100, genre="Rock", year=2024, country="AU",
            duration_seconds=180, position=1, selection_reason="Test"
        )]

        with patch('src.ai_playlist.track_selector.select_tracks_with_llm') as mock_select:
            mock_select.return_value = LLMTrackSelectionResponse(
                request_id="9e2f901c-7c41-444e-9739-75016b37c599",
                selected_tracks=mock_tracks,
                tool_calls=[],
                reasoning="Test",
                cost_usd=0.001,
                execution_time_seconds=1.0,
                created_at=datetime.now()
            )

            with patch('src.ai_playlist.track_selector.uuid.uuid4') as mock_uuid:
                mock_uuid.return_value = uuid.UUID("9e2f901c-7c41-444e-9739-75016b37c599")
                with patch('src.ai_playlist.track_selector._validate_constraint_satisfaction', side_effect=[0.5, 0.85]):
                    import logging
                    caplog.set_level(logging.INFO)
                    tracks = await select_tracks_with_relaxation(basic_criteria, max_iterations=3)

                    # Check for relaxation log messages
                    log_messages = [record.message for record in caplog.records]
                    assert any("iteration 0" in msg.lower() for msg in log_messages)
                    assert any("iteration 1" in msg.lower() for msg in log_messages)

    async def test_multiple_sequential_relaxations(self, basic_criteria, monkeypatch):
        """Test multiple sequential relaxations."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("SUBSONIC_MCP_URL", "http://test-mcp.local")

        mock_tracks = [SelectedTrack(
            track_id=f"track-{i}", title=f"Song {i}", artist=f"Artist {i}",
            album="Album", bpm=100, genre="Rock", year=2024, country="AU" if i < 4 else "US",
            duration_seconds=180, position=i+1, selection_reason="Test"
        ) for i in range(12)]

        captured_criteria = []

        async def capture_criteria(request):
            captured_criteria.append(request.criteria)
            return LLMTrackSelectionResponse(
                request_id=request.playlist_id,
                selected_tracks=mock_tracks,
                tool_calls=[],
                reasoning="Test",
                cost_usd=0.001,
                execution_time_seconds=1.0,
                created_at=datetime.now()
            )

        with patch('src.ai_playlist.track_selector.select_tracks_with_llm', side_effect=capture_criteria):
            with patch('src.ai_playlist.track_selector.uuid.uuid4') as mock_uuid:
                mock_uuid.return_value = uuid.UUID("9e2f901c-7c41-444e-9739-75016b37c599")
                # Low satisfaction forces all relaxations
                with patch('src.ai_playlist.track_selector._validate_constraint_satisfaction', return_value=0.5):
                    tracks = await select_tracks_with_relaxation(basic_criteria, max_iterations=3)

        # Verify sequential relaxations
        assert len(captured_criteria) == 4
        # Iteration 0: original
        assert captured_criteria[0].bpm_range == (90, 130)
        # Iteration 1: BPM relaxed
        assert captured_criteria[1].bpm_range == (80, 140)

    async def test_relaxation_with_different_starting_criteria(self, monkeypatch):
        """Test relaxation with different starting criteria."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("SUBSONIC_MCP_URL", "http://test-mcp.local")

        tight_criteria = TrackSelectionCriteria(
            bpm_range=(100, 105),  # Very tight BPM
            bpm_tolerance=5,
            genre_mix={"Jazz": (0.45, 0.55)},  # Tight genre
            genre_tolerance=0.02,
            era_distribution={"Classic": (0.48, 0.52)},  # Tight era
            era_tolerance=0.02,
            australian_min=0.30,
            energy_flow="calm",
        )

        mock_tracks = [SelectedTrack(
            track_id="track-1", title="Song", artist="Artist",
            album="Album", bpm=102, genre="Jazz", year=1970, country="AU",
            duration_seconds=180, position=1, selection_reason="Test"
        )]

        with patch('src.ai_playlist.track_selector.select_tracks_with_llm') as mock_select:
            mock_select.return_value = LLMTrackSelectionResponse(
                request_id="9e2f901c-7c41-444e-9739-75016b37c599",
                selected_tracks=mock_tracks,
                tool_calls=[],
                reasoning="Test",
                cost_usd=0.001,
                execution_time_seconds=1.0,
                created_at=datetime.now()
            )

            with patch('src.ai_playlist.track_selector.uuid.uuid4') as mock_uuid:
                mock_uuid.return_value = uuid.UUID("9e2f901c-7c41-444e-9739-75016b37c599")
                with patch('src.ai_playlist.track_selector._validate_constraint_satisfaction', return_value=0.85):
                    tracks = await select_tracks_with_relaxation(tight_criteria, max_iterations=3)

                    assert len(tracks) == 1

    async def test_relaxation_preserves_excluded_track_ids(self, monkeypatch):
        """Test relaxation preserves excluded_track_ids."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("SUBSONIC_MCP_URL", "http://test-mcp.local")

        criteria = TrackSelectionCriteria(
            bpm_range=(90, 130),
            bpm_tolerance=10,
            genre_mix={"Rock": (0.5, 0.7)},
            genre_tolerance=0.05,
            era_distribution={"Current (0-2 years)": (0.4, 0.6)},
            era_tolerance=0.05,
            australian_min=0.30,
            energy_flow="test",
            excluded_track_ids=["exclude-1", "exclude-2"],
        )

        captured_criteria = []

        async def capture_criteria(request):
            captured_criteria.append(request.criteria)
            return LLMTrackSelectionResponse(
                request_id=request.playlist_id,
                selected_tracks=[],
                tool_calls=[],
                reasoning="Test",
                cost_usd=0.001,
                execution_time_seconds=1.0,
                created_at=datetime.now()
            )

        with patch('src.ai_playlist.track_selector.select_tracks_with_llm', side_effect=capture_criteria):
            with patch('src.ai_playlist.track_selector.uuid.uuid4') as mock_uuid:
                mock_uuid.return_value = uuid.UUID("9e2f901c-7c41-444e-9739-75016b37c599")
                with patch('src.ai_playlist.track_selector._validate_constraint_satisfaction', return_value=0.85):
                    await select_tracks_with_relaxation(criteria, max_iterations=3)

        # All iterations should preserve excluded track IDs
        for c in captured_criteria:
            assert c.excluded_track_ids == ["exclude-1", "exclude-2"]

    async def test_relaxation_boundary_conditions(self, monkeypatch):
        """Test relaxation with boundary conditions (already at max tolerance)."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("SUBSONIC_MCP_URL", "http://test-mcp.local")

        # Start with max tolerances
        criteria = TrackSelectionCriteria(
            bpm_range=(90, 130),
            bpm_tolerance=10,
            genre_mix={"Rock": (0.5, 0.7)},
            genre_tolerance=0.20,  # Already at max
            era_distribution={"Current (0-2 years)": (0.4, 0.6)},
            era_tolerance=0.20,  # Already at max
            australian_min=0.30,
            energy_flow="test",
        )

        mock_tracks = [SelectedTrack(
            track_id="track-1", title="Song", artist="Artist",
            album="Album", bpm=100, genre="Rock", year=2024, country="AU",
            duration_seconds=180, position=1, selection_reason="Test"
        )]

        with patch('src.ai_playlist.track_selector.select_tracks_with_llm') as mock_select:
            mock_select.return_value = LLMTrackSelectionResponse(
                request_id="9e2f901c-7c41-444e-9739-75016b37c599",
                selected_tracks=mock_tracks,
                tool_calls=[],
                reasoning="Test",
                cost_usd=0.001,
                execution_time_seconds=1.0,
                created_at=datetime.now()
            )

            with patch('src.ai_playlist.track_selector.uuid.uuid4') as mock_uuid:
                mock_uuid.return_value = uuid.UUID("9e2f901c-7c41-444e-9739-75016b37c599")
                with patch('src.ai_playlist.track_selector._validate_constraint_satisfaction', return_value=0.85):
                    tracks = await select_tracks_with_relaxation(criteria, max_iterations=3)

                    assert len(tracks) == 1

    async def test_relaxation_with_partial_constraint_satisfaction(self, basic_criteria, monkeypatch):
        """Test relaxation with partial constraint satisfaction."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("SUBSONIC_MCP_URL", "http://test-mcp.local")

        mock_tracks = [SelectedTrack(
            track_id=f"track-{i}", title=f"Song {i}", artist=f"Artist {i}",
            album="Album", bpm=100, genre="Rock", year=2024, country="AU" if i < 4 else "US",
            duration_seconds=180, position=i+1, selection_reason="Test"
        ) for i in range(12)]

        # Gradually increasing satisfaction
        satisfaction_values = [0.4, 0.6, 0.75, 0.85]

        with patch('src.ai_playlist.track_selector.select_tracks_with_llm') as mock_select:
            mock_select.return_value = LLMTrackSelectionResponse(
                request_id="9e2f901c-7c41-444e-9739-75016b37c599",
                selected_tracks=mock_tracks,
                tool_calls=[],
                reasoning="Test",
                cost_usd=0.001,
                execution_time_seconds=1.0,
                created_at=datetime.now()
            )

            with patch('src.ai_playlist.track_selector.uuid.uuid4') as mock_uuid:
                mock_uuid.return_value = uuid.UUID("9e2f901c-7c41-444e-9739-75016b37c599")
                with patch('src.ai_playlist.track_selector._validate_constraint_satisfaction', side_effect=satisfaction_values):
                    tracks = await select_tracks_with_relaxation(basic_criteria, max_iterations=3)

                    assert len(tracks) == 12


# Helper Function Tests (10+ tests)

class TestHelperFunctions:
    """Test suite for helper functions."""

    def test_estimate_cost(self, basic_request):
        """Test cost estimation from request."""
        cost = _estimate_cost(basic_request)

        # 500 + (12 * 50) = 1100 input tokens
        # 12 * 100 = 1200 output tokens
        expected_input = 500 + (12 * 50)
        expected_output = 12 * 100
        expected_cost = (expected_input * PRICING["input_tokens"]) + (expected_output * PRICING["output_tokens"])

        assert abs(cost - expected_cost) < 0.00001

    def test_token_estimation_scales_with_track_count(self):
        """Test token estimation scales with target track count."""
        small_request = LLMTrackSelectionRequest(
            playlist_id="5e2f901c-7c41-444e-9739-75016b37c599",
            criteria=TrackSelectionCriteria(
                bpm_range=(90, 130),
                bpm_tolerance=10,
                genre_mix={"Rock": (0.5, 0.7)},
                genre_tolerance=0.05,
                era_distribution={"Current (0-2 years)": (0.4, 0.6)},
                era_tolerance=0.05,
                australian_min=0.30,
                energy_flow="test",
            ),
            target_track_count=10,
            mcp_tools=["search_tracks"],
            prompt_template="Test",
            max_cost_usd=0.01,
            timeout_seconds=30,
        )

        large_request = LLMTrackSelectionRequest(
            playlist_id="6e2f901c-7c41-444e-9739-75016b37c599",
            criteria=TrackSelectionCriteria(
                bpm_range=(90, 130),
                bpm_tolerance=10,
                genre_mix={"Rock": (0.5, 0.7)},
                genre_tolerance=0.05,
                era_distribution={"Current (0-2 years)": (0.4, 0.6)},
                era_tolerance=0.05,
                australian_min=0.30,
                energy_flow="test",
            ),
            target_track_count=100,
            mcp_tools=["search_tracks"],
            prompt_template="Test",
            max_cost_usd=0.01,
            timeout_seconds=30,
        )

        cost_small = _estimate_cost(small_request)
        cost_large = _estimate_cost(large_request)

        assert cost_large > cost_small

    def test_build_prompt_with_custom_template(self, basic_criteria):
        """Test prompt building with custom template."""
        request = LLMTrackSelectionRequest(
            playlist_id="7e2f901c-7c41-444e-9739-75016b37c599",
            criteria=basic_criteria,
            target_track_count=12,
            mcp_tools=["search_tracks"],
            prompt_template="Custom prompt template",
            max_cost_usd=0.01,
            timeout_seconds=30,
        )

        prompt = _build_prompt(request)
        assert prompt == "Custom prompt template"

    def test_build_prompt_default_includes_all_criteria(self, basic_request):
        """Test default prompt includes all criteria."""
        request = LLMTrackSelectionRequest(
            playlist_id="8e2f901c-7c41-444e-9739-75016b37c599",
            criteria=basic_request.criteria,
            target_track_count=12,
            mcp_tools=["search_tracks"],
            prompt_template="",  # Empty string for default
            max_cost_usd=0.01,
            timeout_seconds=30,
        )

        prompt = _build_prompt(request)

        assert "90-130 BPM" in prompt
        assert "Rock" in prompt
        assert "Pop" in prompt
        assert "Current (0-2 years)" in prompt
        assert "30%" in prompt  # Australian minimum
        assert "uplifting progression" in prompt

    def test_build_relaxation_prompt_iteration_notes(self, basic_criteria):
        """Test relaxation prompt includes iteration notes."""
        prompt_0 = _build_relaxation_prompt(basic_criteria, 0)
        prompt_1 = _build_relaxation_prompt(basic_criteria, 1)
        prompt_2 = _build_relaxation_prompt(basic_criteria, 2)
        prompt_3 = _build_relaxation_prompt(basic_criteria, 3)

        assert "(Strict criteria)" in prompt_0
        assert "(BPM relaxed ±10)" in prompt_1
        assert "(BPM + Genre relaxed)" in prompt_2
        assert "(BPM + Genre + Era relaxed)" in prompt_3

    def test_configure_mcp_tools_with_url(self, monkeypatch):
        """Test MCP tools configuration with SUBSONIC_MCP_URL."""
        monkeypatch.setenv("SUBSONIC_MCP_URL", "http://test-mcp.local:8080")

        tools = _configure_mcp_tools(["search_tracks", "get_genres"])

        assert len(tools) == 1
        assert tools[0]["type"] == "hosted_mcp"
        assert tools[0]["hosted_mcp"]["server_url"] == "http://test-mcp.local:8080"
        assert "search_tracks" in tools[0]["hosted_mcp"]["tools"]
        assert "get_genres" in tools[0]["hosted_mcp"]["tools"]

    def test_configure_mcp_tools_missing_url_raises_error(self, monkeypatch):
        """Test MCP tools configuration raises error when URL missing."""
        monkeypatch.delenv("SUBSONIC_MCP_URL", raising=False)

        with pytest.raises(MCPToolError, match="SUBSONIC_MCP_URL environment variable not set"):
            _configure_mcp_tools(["search_tracks"])

    def test_parse_llm_response_valid_json(self):
        """Test parsing valid LLM JSON response."""
        content = json.dumps({
            "tracks": [
                {
                    "track_id": "track-1",
                    "title": "Song 1",
                    "artist": "Artist 1",
                    "album": "Album 1",
                    "bpm": 100,
                    "genre": "Rock",
                    "year": 2024,
                    "country": "AU",
                    "duration_seconds": 180,
                    "selection_reason": "Great track"
                }
            ],
            "reasoning": "Selected based on criteria"
        })

        tracks = _parse_llm_response(content)

        assert len(tracks) == 1
        assert tracks[0].track_id == "track-1"
        assert tracks[0].title == "Song 1"
        assert tracks[0].position == 1

    def test_parse_llm_response_malformed_json(self):
        """Test parsing malformed JSON returns empty list."""
        content = "Invalid JSON {{{{"

        tracks = _parse_llm_response(content)

        assert tracks == []

    def test_parse_llm_response_missing_tracks_key(self):
        """Test parsing JSON without tracks key."""
        content = json.dumps({"reasoning": "No tracks"})

        tracks = _parse_llm_response(content)

        assert tracks == []

    def test_extract_tool_calls(self):
        """Test extraction of tool calls from response."""
        mock_tool_call_1 = Mock()
        mock_tool_call_1.function.name = "search_tracks"
        mock_tool_call_1.function.arguments = '{"genre": "Rock"}'

        mock_tool_call_2 = Mock()
        mock_tool_call_2.function.name = "get_genres"
        mock_tool_call_2.function.arguments = '{}'

        tool_calls = _extract_tool_calls([mock_tool_call_1, mock_tool_call_2])

        assert len(tool_calls) == 2
        assert tool_calls[0]["tool_name"] == "search_tracks"
        assert tool_calls[0]["arguments"]["genre"] == "Rock"
        assert tool_calls[1]["tool_name"] == "get_genres"

    def test_extract_reasoning_from_content(self):
        """Test extraction of reasoning from JSON content."""
        content = json.dumps({
            "tracks": [],
            "reasoning": "Selected tracks with high BPM for energy"
        })

        reasoning = _extract_reasoning(content)

        assert reasoning == "Selected tracks with high BPM for energy"

    def test_extract_reasoning_malformed_json(self):
        """Test reasoning extraction from malformed JSON returns empty string."""
        content = "Invalid JSON"

        reasoning = _extract_reasoning(content)

        assert reasoning == ""

    def test_validate_constraint_satisfaction_empty_tracks(self, basic_criteria):
        """Test constraint satisfaction with empty track list."""
        satisfaction = _validate_constraint_satisfaction([], basic_criteria)

        assert satisfaction == 0.0

    def test_validate_constraint_satisfaction_bpm_in_range(self):
        """Test BPM constraint satisfaction."""
        criteria = TrackSelectionCriteria(
            bpm_range=(90, 130),
            bpm_tolerance=10,
            genre_mix={},
            genre_tolerance=0.05,
            era_distribution={},
            era_tolerance=0.05,
            australian_min=0.30,
            energy_flow="test",
        )

        tracks = [
            SelectedTrack(
                track_id=f"track-{i}",
                title=f"Song {i}",
                artist=f"Artist {i}",
                album="Album",
                bpm=100,  # In range
                genre="Rock",
                year=2024,
                country="AU" if i < 4 else "US",
                duration_seconds=180,
                position=i + 1,
                selection_reason="Test"
            )
            for i in range(10)
        ]

        satisfaction = _validate_constraint_satisfaction(tracks, criteria)

        # BPM all in range (100%) + AU content (40% > 30%, 100%) = average 100%
        assert satisfaction == 1.0

    def test_validate_constraint_satisfaction_genre_mix(self):
        """Test genre mix constraint satisfaction."""
        criteria = TrackSelectionCriteria(
            bpm_range=(90, 130),
            bpm_tolerance=10,
            genre_mix={"Rock": (0.4, 0.6), "Pop": (0.3, 0.5)},
            genre_tolerance=0.05,
            era_distribution={},
            era_tolerance=0.05,
            australian_min=0.30,
            energy_flow="test",
        )

        tracks = [
            SelectedTrack(
                track_id=f"track-{i}",
                title=f"Song {i}",
                artist=f"Artist {i}",
                album="Album",
                bpm=100,
                genre="Rock" if i < 5 else "Pop",  # 50% Rock, 50% Pop
                year=2024,
                country="AU" if i < 4 else "US",
                duration_seconds=180,
                position=i + 1,
                selection_reason="Test"
            )
            for i in range(10)
        ]

        satisfaction = _validate_constraint_satisfaction(tracks, criteria)

        # Rock: 50% in range (0.4, 0.6) ✓
        # Pop: 50% in range (0.3, 0.5) ✓
        # BPM: 100% ✓
        # AU: 40% ≥ 30% ✓
        assert satisfaction > 0.8

    def test_validate_constraint_satisfaction_australian_minimum(self):
        """Test Australian minimum constraint satisfaction."""
        criteria = TrackSelectionCriteria(
            bpm_range=(90, 130),
            bpm_tolerance=10,
            genre_mix={},
            genre_tolerance=0.05,
            era_distribution={},
            era_tolerance=0.05,
            australian_min=0.30,
            energy_flow="test",
        )

        # 3 AU tracks out of 10 = 30% (exactly minimum)
        tracks = [
            SelectedTrack(
                track_id=f"track-{i}",
                title=f"Song {i}",
                artist=f"Artist {i}",
                album="Album",
                bpm=100,
                genre="Rock",
                year=2024,
                country="AU" if i < 3 else "US",
                duration_seconds=180,
                position=i + 1,
                selection_reason="Test"
            )
            for i in range(10)
        ]

        satisfaction = _validate_constraint_satisfaction(tracks, criteria)

        # BPM 100% + AU 100% (meets minimum) = 100%
        assert satisfaction == 1.0
