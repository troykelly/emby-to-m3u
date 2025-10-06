"""
Unit Tests for OpenAI Client

Tests LLM request creation, token estimation, cost calculation, and async API calls.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime

from src.ai_playlist.openai_client import (
    OpenAIClient,
    get_client,
    _client_instance
)
from src.ai_playlist.models import (
    PlaylistSpec,
    DaypartSpec,
    TrackSelectionCriteria,
    LLMTrackSelectionRequest,
)


class TestOpenAIClientInit:
    """Test suite for OpenAI client initialization."""

    def test_init_with_explicit_api_key(self):
        """Test initialization with explicit API key."""
        client = OpenAIClient(api_key="test-api-key-123")

        assert client.api_key == "test-api-key-123"
        assert client.model == "gpt-5"
        assert client.cost_per_input_token == 0.00000015
        assert client.cost_per_output_token == 0.00000060

    def test_init_with_env_var(self, monkeypatch):
        """Test initialization from OPENAI_API_KEY environment variable."""
        monkeypatch.setenv("OPENAI_API_KEY", "env-api-key-456")

        client = OpenAIClient()

        assert client.api_key == "env-api-key-456"

    def test_init_with_openai_key_env_var(self, monkeypatch):
        """Test initialization from OPENAI_KEY environment variable."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("OPENAI_KEY", "env-openai-key-789")

        client = OpenAIClient()

        assert client.api_key == "env-openai-key-789"

    def test_init_prefers_openai_api_key_over_openai_key(self, monkeypatch):
        """Test that OPENAI_API_KEY takes precedence over OPENAI_KEY."""
        monkeypatch.setenv("OPENAI_API_KEY", "api-key-first")
        monkeypatch.setenv("OPENAI_KEY", "openai-key-second")

        client = OpenAIClient()

        assert client.api_key == "api-key-first"

    def test_init_without_api_key_raises_error(self, monkeypatch):
        """Test that missing API key raises ValueError."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_KEY", raising=False)

        with pytest.raises(ValueError, match="OPENAI_API_KEY or OPENAI_KEY must be provided"):
            OpenAIClient()

    def test_client_creates_async_openai_instance(self):
        """Test that AsyncOpenAI client is created."""
        client = OpenAIClient(api_key="test-key")

        assert client.client is not None
        # Verify it's an AsyncOpenAI instance
        assert hasattr(client.client, 'chat')


class TestCreateSelectionRequest:
    """Test suite for LLM request creation from playlist spec."""

    def test_creates_request_with_correct_structure(self):
        """Test request creation from valid playlist spec."""
        daypart = DaypartSpec(
            name="Production Call",
            day="Monday",
            time_range=("06:00", "10:00"),
            bpm_progression={"06:00-10:00": (90, 130)},
            genre_mix={"Alternative": 0.25, "Electronic": 0.20},
            era_distribution={"Current (0-2 years)": 0.40},
            australian_min=0.30,
            mood="energetic morning vibe",
            tracks_per_hour=15
        )

        spec = PlaylistSpec(
            id="550e8400-e29b-41d4-a716-446655440000",
            name="Monday_ProductionCall_0600_1000",
            daypart=daypart,
            track_criteria=TrackSelectionCriteria(
                bpm_range=(90, 130),
                bpm_tolerance=10,
                genre_mix={"Alternative": (0.20, 0.30)},
                genre_tolerance=0.05,
                era_distribution={"Current (0-2 years)": (0.35, 0.45)},
                era_tolerance=0.05,
                australian_min=0.30,
                energy_flow="energetic morning vibe"
            ),
            target_duration_minutes=240,
            created_at=datetime.now()
        )

        client = OpenAIClient(api_key="test-key")
        request = client.create_selection_request(spec)

        assert isinstance(request, LLMTrackSelectionRequest)
        assert request.playlist_id == "550e8400-e29b-41d4-a716-446655440000"
        assert request.target_track_count == 60  # 4 hours * 15 tracks/hour
        assert request.max_cost_usd == 0.01
        assert request.timeout_seconds == 30
        assert "search_tracks" in request.mcp_tools
        assert "get_genres" in request.mcp_tools

    def test_calculates_target_track_count_correctly(self):
        """Test target track count calculation from duration and tracks per hour."""
        daypart = DaypartSpec(
            name="Test Show",
            day="Tuesday",
            time_range=("08:00", "12:00"),
            bpm_progression={"08:00-12:00": (100, 120)},
            genre_mix={"Rock": 0.50},
            era_distribution={"Current (0-2 years)": 0.60},
            australian_min=0.30,
            mood="steady energy",
            tracks_per_hour=18  # Higher track rate
        )

        spec = PlaylistSpec(
            id="660e8400-e29b-41d4-a716-446655440001",
            name="Tuesday_TestShow_0800_1200",
            daypart=daypart,
            track_criteria=TrackSelectionCriteria(
                bpm_range=(100, 120),
                bpm_tolerance=10,
                genre_mix={"Rock": (0.45, 0.55)},
                genre_tolerance=0.05,
                era_distribution={"Current (0-2 years)": (0.55, 0.65)},
                era_tolerance=0.05,
                australian_min=0.30,
                energy_flow="steady energy"
            ),
            target_duration_minutes=240,  # 4 hours
            created_at=datetime.now()
        )

        client = OpenAIClient(api_key="test-key")
        request = client.create_selection_request(spec)

        assert request.target_track_count == 72  # 4 hours * 18 tracks/hour

    def test_prompt_includes_all_constraints(self):
        """Test that prompt template includes all constraints."""
        daypart = DaypartSpec(
            name="Test",
            day="Monday",
            time_range=("06:00", "10:00"),
            bpm_progression={"06:00-10:00": (90, 130)},
            genre_mix={"Alternative": 0.25},
            era_distribution={"Current (0-2 years)": 0.40},
            australian_min=0.35,
            mood="energetic",
            tracks_per_hour=15
        )

        spec = PlaylistSpec(
            id="770e8400-e29b-41d4-a716-446655440002",
            name="Monday_Test_0600_1000",
            daypart=daypart,
            track_criteria=TrackSelectionCriteria(
                bpm_range=(90, 130),
                bpm_tolerance=10,
                genre_mix={"Alternative": (0.20, 0.30)},
                genre_tolerance=0.05,
                era_distribution={"Current (0-2 years)": (0.35, 0.45)},
                era_tolerance=0.05,
                australian_min=0.35,
                energy_flow="energetic"
            ),
            target_duration_minutes=240,
            created_at=datetime.now()
        )

        client = OpenAIClient(api_key="test-key")
        request = client.create_selection_request(spec)

        prompt = request.prompt_template

        # Verify all key constraints are in prompt
        assert "90-130 BPM" in prompt
        assert "Alternative" in prompt
        assert "Current (0-2 years)" in prompt
        assert "35% minimum" in prompt  # Australian content
        assert "energetic" in prompt


class TestEstimateTokens:
    """Test suite for token estimation."""

    def test_estimates_tokens_correctly(self):
        """Test token count estimation for request."""
        daypart = DaypartSpec(
            name="Test",
            day="Monday",
            time_range=("06:00", "10:00"),
            bpm_progression={"06:00-10:00": (90, 130)},
            genre_mix={"Alternative": 0.25},
            era_distribution={"Current (0-2 years)": 0.40},
            australian_min=0.30,
            mood="energetic",
            tracks_per_hour=15
        )

        spec = PlaylistSpec(
            id="880e8400-e29b-41d4-a716-446655440003",
            name="Monday_Test_0600_1000",
            daypart=daypart,
            track_criteria=TrackSelectionCriteria(
                bpm_range=(90, 130),
                bpm_tolerance=10,
                genre_mix={"Alternative": (0.20, 0.30)},
                genre_tolerance=0.05,
                era_distribution={"Current (0-2 years)": (0.35, 0.45)},
                era_tolerance=0.05,
                australian_min=0.30,
                energy_flow="energetic"
            ),
            target_duration_minutes=240,
            created_at=datetime.now()
        )

        client = OpenAIClient(api_key="test-key")
        request = client.create_selection_request(spec)

        tokens = client.estimate_tokens(request)

        # Should have input tokens + estimated output tokens (60 tracks * 200)
        assert tokens > 0
        assert tokens >= 12000  # 60 tracks * 200 tokens minimum

    def test_output_tokens_scale_with_track_count(self):
        """Test that output token estimate scales with target track count."""
        client = OpenAIClient(api_key="test-key")

        # Create two requests with different track counts
        request_small = LLMTrackSelectionRequest(
            playlist_id="990e8400-e29b-41d4-a716-446655440004",
            criteria=TrackSelectionCriteria(
                bpm_range=(90, 130),
                bpm_tolerance=10,
                genre_mix={"Rock": (0.45, 0.55)},
                genre_tolerance=0.05,
                era_distribution={"Current (0-2 years)": (0.35, 0.45)},
                era_tolerance=0.05,
                australian_min=0.30,
                energy_flow="steady"
            ),
            target_track_count=10,
            mcp_tools=["search_tracks"],
            prompt_template="Short test prompt",
            max_cost_usd=0.01,
            timeout_seconds=30
        )

        request_large = LLMTrackSelectionRequest(
            playlist_id="aa0e8400-e29b-41d4-a716-446655440005",
            criteria=TrackSelectionCriteria(
                bpm_range=(90, 130),
                bpm_tolerance=10,
                genre_mix={"Rock": (0.45, 0.55)},
                genre_tolerance=0.05,
                era_distribution={"Current (0-2 years)": (0.35, 0.45)},
                era_tolerance=0.05,
                australian_min=0.30,
                energy_flow="steady"
            ),
            target_track_count=100,
            mcp_tools=["search_tracks"],
            prompt_template="Short test prompt",
            max_cost_usd=0.01,
            timeout_seconds=30
        )

        tokens_small = client.estimate_tokens(request_small)
        tokens_large = client.estimate_tokens(request_large)

        # Larger request should have more tokens
        assert tokens_large > tokens_small
        # Difference should be roughly 90 tracks * 200 tokens = 18000
        assert abs((tokens_large - tokens_small) - 18000) < 2000


class TestEstimateCost:
    """Test suite for cost estimation."""

    def test_calculates_cost_correctly(self):
        """Test cost calculation from token counts."""
        client = OpenAIClient(api_key="test-key")

        request = LLMTrackSelectionRequest(
            playlist_id="bb0e8400-e29b-41d4-a716-446655440006",
            criteria=TrackSelectionCriteria(
                bpm_range=(90, 130),
                bpm_tolerance=10,
                genre_mix={"Rock": (0.45, 0.55)},
                genre_tolerance=0.05,
                era_distribution={"Current (0-2 years)": (0.35, 0.45)},
                era_tolerance=0.05,
                australian_min=0.30,
                energy_flow="steady"
            ),
            target_track_count=60,
            mcp_tools=["search_tracks"],
            prompt_template="Test prompt for cost calculation",
            max_cost_usd=0.01,
            timeout_seconds=30
        )

        cost = client.estimate_cost(request)

        # Cost should be positive and reasonable
        assert cost > 0
        assert cost < 0.02  # Should be under max cost

    def test_cost_scales_with_output_tokens(self):
        """Test that cost scales proportionally with output token count."""
        client = OpenAIClient(api_key="test-key")

        # Small request
        request_small = LLMTrackSelectionRequest(
            playlist_id="cc0e8400-e29b-41d4-a716-446655440007",
            criteria=TrackSelectionCriteria(
                bpm_range=(90, 130),
                bpm_tolerance=10,
                genre_mix={"Rock": (0.45, 0.55)},
                genre_tolerance=0.05,
                era_distribution={"Current (0-2 years)": (0.35, 0.45)},
                era_tolerance=0.05,
                australian_min=0.30,
                energy_flow="steady"
            ),
            target_track_count=10,
            mcp_tools=["search_tracks"],
            prompt_template="Test",
            max_cost_usd=0.01,
            timeout_seconds=30
        )

        # Large request (10x more tracks)
        request_large = LLMTrackSelectionRequest(
            playlist_id="dd0e8400-e29b-41d4-a716-446655440008",
            criteria=TrackSelectionCriteria(
                bpm_range=(90, 130),
                bpm_tolerance=10,
                genre_mix={"Rock": (0.45, 0.55)},
                genre_tolerance=0.05,
                era_distribution={"Current (0-2 years)": (0.35, 0.45)},
                era_tolerance=0.05,
                australian_min=0.30,
                energy_flow="steady"
            ),
            target_track_count=100,
            mcp_tools=["search_tracks"],
            prompt_template="Test",
            max_cost_usd=0.01,
            timeout_seconds=30
        )

        cost_small = client.estimate_cost(request_small)
        cost_large = client.estimate_cost(request_large)

        # Larger request should cost more
        assert cost_large > cost_small


@pytest.mark.asyncio
class TestCallLLM:
    """Test suite for async LLM API calls."""

    async def test_call_llm_success(self):
        """Test successful LLM call with mocked OpenAI API."""
        client = OpenAIClient(api_key="test-key")

        # Mock the OpenAI response with tracks
        mock_response = Mock()
        mock_response.choices = [
            Mock(
                message=Mock(
                    content='{"tracks": [{"id": "track-1", "artist": "Test Artist", "title": "Test Song", "bpm": 120}]}',
                    tool_calls=None
                ),
                finish_reason="stop"
            )
        ]
        mock_response.usage = Mock(
            prompt_tokens=500,
            completion_tokens=1200
        )

        # Mock the async client call
        client.client.chat.completions.create = AsyncMock(return_value=mock_response)

        request = LLMTrackSelectionRequest(
            playlist_id="ee0e8400-e29b-41d4-a716-446655440009",
            criteria=TrackSelectionCriteria(
                bpm_range=(90, 130),
                bpm_tolerance=10,
                genre_mix={"Rock": (0.45, 0.55)},
                genre_tolerance=0.05,
                era_distribution={"Current (0-2 years)": (0.35, 0.45)},
                era_tolerance=0.05,
                australian_min=0.30,
                energy_flow="steady"
            ),
            target_track_count=60,
            mcp_tools=["search_tracks"],
            prompt_template="Test prompt",
            max_cost_usd=0.01,
            timeout_seconds=30
        )

        mcp_tools = {"type": "hosted_mcp"}

        # Mock the placeholder track parser to return tracks
        with patch.object(client, '_parse_tracks_from_response') as mock_parser:
            mock_parser.return_value = [{"id": "track-1", "artist": "Test Artist", "title": "Test Song", "bpm": 120}]

            response = await client.call_llm(request, mcp_tools)

            assert response.request_id == "ee0e8400-e29b-41d4-a716-446655440009"
            assert response.cost_usd > 0
            assert response.execution_time_seconds > 0
            assert len(response.selected_tracks) > 0

    async def test_call_llm_timeout(self):
        """Test LLM call timeout handling."""
        client = OpenAIClient(api_key="test-key")

        # Mock a timeout
        async def slow_call(*args, **kwargs):
            await asyncio.sleep(10)  # Longer than timeout

        client.client.chat.completions.create = slow_call

        request = LLMTrackSelectionRequest(
            playlist_id="ff0e8400-e29b-41d4-a716-446655440010",
            criteria=TrackSelectionCriteria(
                bpm_range=(90, 130),
                bpm_tolerance=10,
                genre_mix={"Rock": (0.45, 0.55)},
                genre_tolerance=0.05,
                era_distribution={"Current (0-2 years)": (0.35, 0.45)},
                era_tolerance=0.05,
                australian_min=0.30,
                energy_flow="steady"
            ),
            target_track_count=60,
            mcp_tools=["search_tracks"],
            prompt_template="Test",
            max_cost_usd=0.01,
            timeout_seconds=1  # Short timeout
        )

        mcp_tools = {"type": "hosted_mcp"}

        with pytest.raises(TimeoutError, match="LLM call exceeded timeout"):
            await client.call_llm(request, mcp_tools)

    async def test_call_llm_with_tool_calls(self):
        """Test LLM call with tool calls in response."""
        client = OpenAIClient(api_key="test-key")

        # Mock response with tool calls and tracks
        mock_tool_call = Mock()
        mock_tool_call.function.name = "search_tracks"
        mock_tool_call.function.arguments = '{"genre": "Rock"}'

        mock_response = Mock()
        mock_response.choices = [
            Mock(
                message=Mock(
                    content='{"tracks": [{"id": "track-1", "artist": "Test", "title": "Song", "bpm": 120}]}',
                    tool_calls=[mock_tool_call]
                )
            )
        ]
        mock_response.usage = Mock(prompt_tokens=500, completion_tokens=1200)

        client.client.chat.completions.create = AsyncMock(return_value=mock_response)

        request = LLMTrackSelectionRequest(
            playlist_id="010e8400-e29b-41d4-a716-446655440011",
            criteria=TrackSelectionCriteria(
                bpm_range=(90, 130),
                bpm_tolerance=10,
                genre_mix={"Rock": (0.45, 0.55)},
                genre_tolerance=0.05,
                era_distribution={"Current (0-2 years)": (0.35, 0.45)},
                era_tolerance=0.05,
                australian_min=0.30,
                energy_flow="steady"
            ),
            target_track_count=60,
            mcp_tools=["search_tracks"],
            prompt_template="Test",
            max_cost_usd=0.01,
            timeout_seconds=30
        )

        mcp_tools = {"type": "hosted_mcp"}

        # Mock the placeholder track parser to return tracks
        with patch.object(client, '_parse_tracks_from_response') as mock_parser:
            mock_parser.return_value = [{"id": "track-1", "artist": "Test", "title": "Song", "bpm": 120}]

            response = await client.call_llm(request, mcp_tools)

            # Verify tool calls are recorded
            assert len(response.tool_calls) > 0
            assert response.tool_calls[0]["tool_name"] == "search_tracks"


class TestGetClient:
    """Test suite for singleton client instance."""

    def test_get_client_returns_instance(self):
        """Test get_client returns OpenAIClient instance."""
        # Clear singleton
        import src.ai_playlist.openai_client as module
        module._client_instance = None

        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            client = get_client()

            assert isinstance(client, OpenAIClient)

    def test_get_client_returns_same_instance(self):
        """Test get_client returns singleton instance."""
        # Clear singleton
        import src.ai_playlist.openai_client as module
        module._client_instance = None

        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            client1 = get_client()
            client2 = get_client()

            assert client1 is client2
