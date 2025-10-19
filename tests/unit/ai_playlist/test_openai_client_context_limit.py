"""Tests for openai_client.py - Context Length Limit Handling (lines 593-688).

This test file covers the auto-submit logic when OpenAI context length limits are hit:
- Detecting context_length_exceeded error
- Auto-submitting when enough tracks discovered
- Building track metadata from tool call results
- Fallback message injection when insufficient tracks
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
import uuid
import json

from src.ai_playlist.openai_client import OpenAIClient
from src.ai_playlist.models import (
    TrackSelectionCriteria,
    BPMRange,
    GenreCriteria,
    EraCriteria
)
from src.ai_playlist.models.llm import LLMTrackSelectionRequest
from openai.types.chat import ChatCompletion, ChatCompletionMessage


@pytest.fixture
def sample_request():
    """Create sample LLM request."""
    criteria = TrackSelectionCriteria(
        bpm_ranges=[BPMRange(time_start=None, time_end=None, bpm_min=90, bpm_max=130)],
        genre_mix={"Rock": GenreCriteria(target_percentage=0.5)},
        era_distribution={"Current": EraCriteria(
            era_name="Current",
            min_year=2020,
            max_year=2025,
            target_percentage=0.6
        )},
        australian_content_min=0.30,
        energy_flow_requirements=[],
        rotation_distribution={},
        no_repeat_window_hours=24.0
    )

    return LLMTrackSelectionRequest(
        playlist_id=str(uuid.uuid4()),
        criteria=criteria,
        target_track_count=10,
        prompt_template="Test prompt",
        max_cost_usd=0.10,
        timeout_seconds=60
    )


@pytest.fixture
def mock_subsonic_tools():
    """Create mock SubsonicTools."""
    tools = Mock()
    tools.get_tool_definitions.return_value = [
        {
            "type": "function",
            "function": {
                "name": "search_tracks",
                "description": "Search for tracks"
            }
        },
        {
            "type": "function",
            "function": {
                "name": "submit_playlist",
                "description": "Submit final playlist"
            }
        }
    ]

    async def mock_execute(tool_name, arguments):
        if tool_name == "search_tracks":
            return {
                "status": "success",
                "tracks": [
                    {
                        "id": f"track-{i:03d}",
                        "title": f"Song {i}",
                        "artist": f"Artist {i}",
                        "album": "Album",
                        "genre": "Rock",
                        "year": 2023,
                        "bpm": 120,
                        "duration_seconds": 180
                    }
                    for i in range(1, 6)
                ]
            }
        return {"status": "success"}

    tools.execute_tool = mock_execute
    return tools


@pytest.mark.asyncio
class TestContextLengthLimitHandling:
    """Test context length limit detection and auto-submit logic."""

    async def test_context_limit_with_enough_tracks_auto_submits(
        self, sample_request, mock_subsonic_tools
    ):
        """Test auto-submit when context limit hit with enough tracks discovered."""
        # Arrange
        client = OpenAIClient(api_key="test-key")

        # Simulate several successful tool calls discovering tracks
        discovered_track_ids = {f"track-{i:03d}" for i in range(1, 16)}  # 15 tracks discovered

        # First few responses succeed, then context length error
        response_sequence = []

        # Response 1: Search tracks (iteration 1)
        mock_msg_1 = Mock(spec=ChatCompletionMessage)
        mock_msg_1.content = None
        mock_msg_1.tool_calls = [Mock()]
        mock_msg_1.tool_calls[0].id = "call_1"
        mock_fn_1 = Mock()
        mock_fn_1.name = "search_tracks"
        mock_fn_1.arguments = '{"query": "Rock", "genre": "Rock"}'
        mock_msg_1.tool_calls[0].function = mock_fn_1

        mock_response_1 = Mock(spec=ChatCompletion)
        mock_response_1.choices = [Mock(message=mock_msg_1, finish_reason="tool_calls")]
        mock_response_1.usage = Mock(prompt_tokens=100, completion_tokens=50)
        response_sequence.append(mock_response_1)

        # Response 2: Context length limit hit (finish_reason='length')
        mock_msg_2 = Mock(spec=ChatCompletionMessage)
        mock_msg_2.content = "I need to search for more tracks..."
        mock_msg_2.tool_calls = None

        mock_response_2 = Mock(spec=ChatCompletion)
        mock_response_2.choices = [Mock(message=mock_msg_2, finish_reason="length")]  # Context limit!
        mock_response_2.usage = Mock(prompt_tokens=120000, completion_tokens=50)
        response_sequence.append(mock_response_2)

        with patch.object(client.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
            mock_create.side_effect = response_sequence

            with patch.object(mock_subsonic_tools, 'execute_tool', new_callable=AsyncMock) as mock_execute:
                # First call returns tracks
                mock_execute.return_value = {
                    "status": "success",
                    "tracks": [
                        {
                            "id": f"track-{i:03d}",
                            "title": f"Song {i}",
                            "artist": f"Artist {i}",
                            "album": "Album",
                            "genre": "Rock",
                            "year": 2023,
                            "bpm": 120,
                            "duration_seconds": 180
                        }
                        for i in range(1, 16)  # 15 tracks
                    ]
                }

                # Act
                result = await client.call_llm(sample_request, mock_subsonic_tools)

        # Assert
        assert result is not None
        assert len(result.selected_tracks) == 10  # Limited to target_track_count
        assert result.stop_reason == "context_length_limit"
        assert result.stopped_early is True
        # Verify tracks came from discovered set
        for track in result.selected_tracks:
            assert track.track_id.startswith("track-")

    async def test_context_limit_builds_track_metadata_from_tool_calls(
        self, sample_request, mock_subsonic_tools
    ):
        """Test that track metadata is correctly built from tool call results."""
        # Arrange
        client = OpenAIClient(api_key="test-key")

        # Create mock response with tool calls
        mock_msg = Mock(spec=ChatCompletionMessage)
        mock_msg.content = None
        mock_msg.tool_calls = [Mock()]
        mock_msg.tool_calls[0].id = "call_1"
        mock_fn = Mock()
        mock_fn.name = "search_tracks"
        mock_fn.arguments = '{"query": "Rock"}'
        mock_msg.tool_calls[0].function = mock_fn

        mock_response_1 = Mock(spec=ChatCompletion)
        mock_response_1.choices = [Mock(message=mock_msg, finish_reason="tool_calls")]
        mock_response_1.usage = Mock(prompt_tokens=100, completion_tokens=50)

        # Second response: context length limit (finish_reason='length')
        mock_msg_limit = Mock(spec=ChatCompletionMessage)
        mock_msg_limit.content = "Searching for tracks..."
        mock_msg_limit.tool_calls = None

        mock_response_limit = Mock(spec=ChatCompletion)
        mock_response_limit.choices = [Mock(message=mock_msg_limit, finish_reason="length")]
        mock_response_limit.usage = Mock(prompt_tokens=120000, completion_tokens=50)

        with patch.object(client.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
            mock_create.side_effect = [mock_response_1, mock_response_limit]

            with patch.object(mock_subsonic_tools, 'execute_tool', new_callable=AsyncMock) as mock_execute:
                mock_execute.return_value = {
                    "status": "success",
                    "tracks": [
                        {
                            "id": "track-special-001",
                            "title": "Special Song",
                            "artist": "Special Artist",
                            "album": "Special Album",
                            "genre": "Alternative Rock",
                            "year": 2024,
                            "bpm": 125,
                            "duration_seconds": 210,
                            "country": "AU"
                        }
                        for i in range(12)  # Enough tracks
                    ]
                }

                # Act
                result = await client.call_llm(sample_request, mock_subsonic_tools)

        # Assert - verify metadata was correctly mapped
        assert len(result.selected_tracks) == 10
        first_track = result.selected_tracks[0]
        assert first_track.track_id == "track-special-001"
        assert first_track.title == "Special Song"
        assert first_track.artist == "Special Artist"
        assert first_track.album == "Special Album"
        assert first_track.genre == "Alternative Rock"
        assert first_track.year == 2024
        assert first_track.bpm == 125
        assert first_track.duration_seconds == 210
        assert first_track.selection_reason == "Auto-selected due to context length limit"

    async def test_context_limit_with_insufficient_tracks_injects_fallback_message(
        self, sample_request, mock_subsonic_tools
    ):
        """Test fallback message injection when not enough tracks discovered."""
        # Arrange
        client = OpenAIClient(api_key="test-key")

        # Mock responses
        mock_msg_1 = Mock(spec=ChatCompletionMessage)
        mock_msg_1.content = None
        mock_msg_1.tool_calls = [Mock()]
        mock_msg_1.tool_calls[0].id = "call_1"
        mock_fn_1 = Mock()
        mock_fn_1.name = "search_tracks"
        mock_fn_1.arguments = '{"query": "Rock"}'
        mock_msg_1.tool_calls[0].function = mock_fn_1

        mock_response_1 = Mock(spec=ChatCompletion)
        mock_response_1.choices = [Mock(message=mock_msg_1, finish_reason="tool_calls")]
        mock_response_1.usage = Mock(prompt_tokens=100, completion_tokens=50)

        # Second response: context length limit
        mock_msg_limit = Mock(spec=ChatCompletionMessage)
        mock_msg_limit.content = "Need more tracks..."
        mock_msg_limit.tool_calls = None

        mock_response_limit = Mock(spec=ChatCompletion)
        mock_response_limit.choices = [Mock(message=mock_msg_limit, finish_reason="length")]
        mock_response_limit.usage = Mock(prompt_tokens=120000, completion_tokens=50)

        # Response after fallback message - submits with available tracks
        mock_msg_submit = Mock(spec=ChatCompletionMessage)
        mock_msg_submit.content = None
        mock_msg_submit.tool_calls = [Mock()]
        mock_msg_submit.tool_calls[0].id = "call_submit"
        mock_fn_submit = Mock()
        mock_fn_submit.name = "submit_playlist"
        mock_fn_submit.arguments = json.dumps({
            "selected_track_ids": ["track-001", "track-002", "track-003"],
            "reasoning": "Submitting available tracks due to context limit"
        })
        mock_msg_submit.tool_calls[0].function = mock_fn_submit

        mock_response_submit = Mock(spec=ChatCompletion)
        mock_response_submit.choices = [Mock(message=mock_msg_submit, finish_reason="tool_calls")]
        mock_response_submit.usage = Mock(prompt_tokens=150, completion_tokens=30)

        with patch.object(client.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
            mock_create.side_effect = [mock_response_1, mock_response_limit, mock_response_submit]

            with patch.object(mock_subsonic_tools, 'execute_tool', new_callable=AsyncMock) as mock_execute:
                # First call returns only 3 tracks (below minimum of 5)
                async def execute_side_effect(tool_name, arguments):
                    if tool_name == "search_tracks":
                        return {
                            "status": "success",
                            "tracks": [
                                {
                                    "id": f"track-{i:03d}",
                                    "title": f"Song {i}",
                                    "artist": f"Artist {i}",
                                    "album": "Album",
                                    "genre": "Rock",
                                    "year": 2023,
                                    "bpm": 120,
                                    "duration_seconds": 180
                                }
                                for i in range(1, 4)  # Only 3 tracks (insufficient)
                            ]
                        }
                    elif tool_name == "submit_playlist":
                        return {
                            "status": "success",
                            "message": "Playlist submitted"
                        }
                    return {"status": "success"}

                mock_execute.side_effect = execute_side_effect

                # Act
                result = await client.call_llm(sample_request, mock_subsonic_tools)

        # Assert
        assert result is not None
        assert len(result.selected_tracks) == 3  # All available tracks used
        # Verify the fallback message was effectively triggered
        assert mock_create.call_count == 3  # Initial + context error + after fallback message

    async def test_context_limit_calculates_efficiency_metrics(
        self, sample_request, mock_subsonic_tools
    ):
        """Test that efficiency metrics are calculated correctly on context limit."""
        # Arrange
        client = OpenAIClient(api_key="test-key")

        mock_msg = Mock(spec=ChatCompletionMessage)
        mock_msg.content = None
        mock_msg.tool_calls = [Mock()]
        mock_msg.tool_calls[0].id = "call_1"
        mock_fn = Mock()
        mock_fn.name = "search_tracks"
        mock_fn.arguments = '{"query": "Rock"}'
        mock_msg.tool_calls[0].function = mock_fn

        mock_response = Mock(spec=ChatCompletion)
        mock_response.choices = [Mock(message=mock_msg, finish_reason="tool_calls")]
        mock_response.usage = Mock(prompt_tokens=1000, completion_tokens=500)

        mock_response_limit = Mock(spec=ChatCompletion)
        mock_msg_limit = Mock(spec=ChatCompletionMessage)
        mock_msg_limit.content = ""
        mock_msg_limit.tool_calls = None
        mock_response_limit.choices = [Mock(message=mock_msg_limit, finish_reason="length")]
        mock_response_limit.usage = Mock(prompt_tokens=120000, completion_tokens=50)

        with patch.object(client.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
            mock_create.side_effect = [mock_response, mock_response_limit]

            with patch.object(mock_subsonic_tools, 'execute_tool', new_callable=AsyncMock) as mock_execute:
                mock_execute.return_value = {
                    "status": "success",
                    "tracks": [
                        {
                            "id": f"track-{i:03d}",
                            "title": f"Song {i}",
                            "artist": f"Artist {i}",
                            "album": "Album",
                            "genre": "Rock",
                            "year": 2023,
                            "bpm": 120,
                            "duration_seconds": 180
                        }
                        for i in range(1, 16)
                    ]
                }

                # Act
                result = await client.call_llm(sample_request, mock_subsonic_tools)

        # Assert - verify metrics
        assert result.stopped_early is True
        assert result.stop_reason == "context_length_limit"
        assert result.tool_calls_used == 1  # One tool call before context limit
        assert result.iterations_used == 2  # Two iterations
        # Efficiency: 10 tracks selected / 1 tool call = 1000%
        assert result.efficiency_percent == 1000.0
        assert result.cost_usd > 0  # Cost calculated from tokens

    async def test_context_limit_preserves_tool_call_history(
        self, sample_request, mock_subsonic_tools
    ):
        """Test that tool call history is preserved in response."""
        # Arrange
        client = OpenAIClient(api_key="test-key")

        mock_msg = Mock(spec=ChatCompletionMessage)
        mock_msg.content = None
        mock_msg.tool_calls = [Mock()]
        mock_msg.tool_calls[0].id = "call_search_1"
        mock_fn = Mock()
        mock_fn.name = "search_tracks"
        mock_fn.arguments = '{"query": "Rock Alternative"}'
        mock_msg.tool_calls[0].function = mock_fn

        mock_response = Mock(spec=ChatCompletion)
        mock_response.choices = [Mock(message=mock_msg, finish_reason="tool_calls")]
        mock_response.usage = Mock(prompt_tokens=500, completion_tokens=200)

        mock_response_limit = Mock(spec=ChatCompletion)
        mock_msg_limit = Mock(spec=ChatCompletionMessage)
        mock_msg_limit.content = ""
        mock_msg_limit.tool_calls = None
        mock_response_limit.choices = [Mock(message=mock_msg_limit, finish_reason="length")]
        mock_response_limit.usage = Mock(prompt_tokens=120000, completion_tokens=50)

        with patch.object(client.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
            mock_create.side_effect = [mock_response, mock_response_limit]

            with patch.object(mock_subsonic_tools, 'execute_tool', new_callable=AsyncMock) as mock_execute:
                mock_execute.return_value = {
                    "status": "success",
                    "tracks": [{"id": f"track-{i:03d}", "title": f"Song {i}",
                                "artist": f"Artist {i}", "album": "Album",
                                "genre": "Rock", "year": 2023, "bpm": 120,
                                "duration_seconds": 180} for i in range(1, 16)]
                }

                # Act
                result = await client.call_llm(sample_request, mock_subsonic_tools)

        # Assert - verify tool calls preserved
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0]["tool_name"] == "search_tracks"
        assert "Rock Alternative" in result.tool_calls[0]["arguments"]
        assert result.tool_calls[0]["result"]["status"] == "success"
        assert len(result.tool_calls[0]["result"]["tracks"]) == 15

    async def test_context_limit_limits_selected_tracks_to_target_count(
        self, sample_request, mock_subsonic_tools
    ):
        """Test that auto-submit limits tracks to target_track_count."""
        # Arrange
        client = OpenAIClient(api_key="test-key")
        sample_request.target_track_count = 8  # Set specific target

        mock_msg = Mock(spec=ChatCompletionMessage)
        mock_msg.content = None
        mock_msg.tool_calls = [Mock()]
        mock_msg.tool_calls[0].id = "call_1"
        mock_fn = Mock()
        mock_fn.name = "search_tracks"
        mock_fn.arguments = '{"query": "Rock"}'
        mock_msg.tool_calls[0].function = mock_fn

        mock_response = Mock(spec=ChatCompletion)
        mock_response.choices = [Mock(message=mock_msg, finish_reason="tool_calls")]
        mock_response.usage = Mock(prompt_tokens=100, completion_tokens=50)

        mock_response_limit = Mock(spec=ChatCompletion)
        mock_msg_limit = Mock(spec=ChatCompletionMessage)
        mock_msg_limit.content = ""
        mock_msg_limit.tool_calls = None
        mock_response_limit.choices = [Mock(message=mock_msg_limit, finish_reason="length")]
        mock_response_limit.usage = Mock(prompt_tokens=120000, completion_tokens=50)

        with patch.object(client.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
            mock_create.side_effect = [mock_response, mock_response_limit]

            with patch.object(mock_subsonic_tools, 'execute_tool', new_callable=AsyncMock) as mock_execute:
                # Return 25 tracks (more than target)
                mock_execute.return_value = {
                    "status": "success",
                    "tracks": [{"id": f"track-{i:03d}", "title": f"Song {i}",
                                "artist": f"Artist {i}", "album": "Album",
                                "genre": "Rock", "year": 2023, "bpm": 120,
                                "duration_seconds": 180} for i in range(1, 26)]
                }

                # Act
                result = await client.call_llm(sample_request, mock_subsonic_tools)

        # Assert - should be limited to target_track_count (8)
        assert len(result.selected_tracks) == 8
        # Verify they're the first 8 from discovered tracks
        for i, track in enumerate(result.selected_tracks, start=1):
            assert track.track_id == f"track-{i:03d}"
            assert track.position == i

    async def test_context_limit_sets_reasoning_message(
        self, sample_request, mock_subsonic_tools
    ):
        """Test that auto-submit sets appropriate reasoning message."""
        # Arrange
        client = OpenAIClient(api_key="test-key")

        mock_msg = Mock(spec=ChatCompletionMessage)
        mock_msg.content = None
        mock_msg.tool_calls = [Mock()]
        mock_msg.tool_calls[0].id = "call_1"
        mock_fn = Mock()
        mock_fn.name = "search_tracks"
        mock_fn.arguments = '{"query": "Rock"}'
        mock_msg.tool_calls[0].function = mock_fn

        mock_response = Mock(spec=ChatCompletion)
        mock_response.choices = [Mock(message=mock_msg, finish_reason="tool_calls")]
        mock_response.usage = Mock(prompt_tokens=100, completion_tokens=50)

        mock_response_limit = Mock(spec=ChatCompletion)
        mock_msg_limit = Mock(spec=ChatCompletionMessage)
        mock_msg_limit.content = ""
        mock_msg_limit.tool_calls = None
        mock_response_limit.choices = [Mock(message=mock_msg_limit, finish_reason="length")]
        mock_response_limit.usage = Mock(prompt_tokens=120000, completion_tokens=50)

        with patch.object(client.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
            mock_create.side_effect = [mock_response, mock_response_limit]

            with patch.object(mock_subsonic_tools, 'execute_tool', new_callable=AsyncMock) as mock_execute:
                mock_execute.return_value = {
                    "status": "success",
                    "tracks": [{"id": f"track-{i:03d}", "title": f"Song {i}",
                                "artist": f"Artist {i}", "album": "Album",
                                "genre": "Rock", "year": 2023, "bpm": 120,
                                "duration_seconds": 180} for i in range(1, 16)]
                }

                # Act
                result = await client.call_llm(sample_request, mock_subsonic_tools)

        # Assert
        assert "Context limit reached" in result.reasoning
        assert "auto-submitted" in result.reasoning.lower()
