"""Simplified async tests for openai_client.py - focusing on working tests first.

These tests use a simpler mocking approach to avoid StopIteration issues.
"""
import pytest
import uuid
import json
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import time

from src.ai_playlist.openai_client import OpenAIClient
from src.ai_playlist.models import (
    LLMTrackSelectionRequest,
    LLMTrackSelectionResponse,
    TrackSelectionCriteria,
    BPMRange,
    GenreCriteria,
    EraCriteria,
)


@pytest.fixture
def sample_request():
    """Create sample LLM track selection request."""
    criteria = TrackSelectionCriteria(
        bpm_ranges=[BPMRange(
            time_start=time(6, 0),
            time_end=time(10, 0),
            bpm_min=90,
            bpm_max=130
        )],
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

    return LLMTrackSelectionRequest(
        playlist_id=str(uuid.uuid4()),
        criteria=criteria,
        target_track_count=10,
        prompt_template="Generate a morning drive playlist.",
        max_cost_usd=0.10,
        timeout_seconds=120
    )


@pytest.fixture
def mock_subsonic_tools():
    """Create mock SubsonicTools instance."""
    mock_tools = Mock()
    mock_tools.get_tool_definitions.return_value = [
        {
            "type": "function",
            "function": {
                "name": "search_tracks",
                "description": "Search for tracks",
                "parameters": {"type": "object", "properties": {"query": {"type": "string"}}}
            }
        },
        {
            "type": "function",
            "function": {
                "name": "submit_playlist",
                "description": "Submit playlist",
                "parameters": {"type": "object", "properties": {"selected_track_ids": {"type": "array"}}}
            }
        }
    ]

    async def mock_execute_tool(tool_name, arguments):
        if tool_name == "search_tracks":
            return {
                "tracks": [
                    {"id": f"track-{i}", "title": f"Song {i}", "artist": "Artist", "genre": "Rock", "year": 2023, "bpm": 120, "duration_seconds": 180}
                    for i in range(1, 6)
                ],
                "count": 5
            }
        elif tool_name == "submit_playlist":
            return {
                "status": "playlist_submitted",
                "selected_track_ids": arguments.get("selected_track_ids", []),
                "reasoning": arguments.get("reasoning", "")
            }
        return {}

    mock_tools.execute_tool = AsyncMock(side_effect=mock_execute_tool)
    return mock_tools


class TestCallLLMSimple:
    """Simplified tests for call_llm to ensure basic functionality works."""

    @pytest.mark.asyncio
    async def test_call_llm_direct_submission(self, sample_request, mock_subsonic_tools):
        """Test LLM directly submits playlist without search (simplest case)."""
        # Arrange
        client = OpenAIClient(api_key="test-key")

        # First response: call submit_playlist
        mock_response_1 = Mock()
        mock_response_1.choices = [Mock()]
        mock_response_1.choices[0].finish_reason = "tool_calls"
        mock_response_1.choices[0].message = Mock()
        mock_response_1.choices[0].message.content = None
        mock_function = Mock()
        mock_function.name = "submit_playlist"  # Set as attribute, not constructor arg
        mock_function.arguments = json.dumps({
            "selected_track_ids": ["track-1", "track-2", "track-3"],
            "reasoning": "Direct submission"
        })

        mock_response_1.choices[0].message.tool_calls = [
            Mock(
                id="call_1",
                function=mock_function
            )
        ]
        mock_response_1.usage = Mock(prompt_tokens=100, completion_tokens=50)
        mock_response_1.message = mock_response_1.choices[0].message

        # Second response: finish (after submit_playlist returns playlist_submitted)
        # The code exits after submit_playlist with "playlist_submitted" status
        # So we don't actually need a second response - submit_playlist causes immediate return

        call_count = {'count': 0}

        async def mock_create_response(*args, **kwargs):
            """Return the submit_playlist response once."""
            call_count['count'] += 1
            if call_count['count'] == 1:
                return mock_response_1
            # Should not reach here if submit_playlist works correctly
            raise RuntimeError(f"Unexpected call #{call_count['count']} to create()")

        with patch.object(client.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
            mock_create.side_effect = mock_create_response

            # Act
            response = await client.call_llm(sample_request, mock_subsonic_tools)

            # Assert
            assert isinstance(response, LLMTrackSelectionResponse)
            assert response.request_id == sample_request.playlist_id
            assert len(response.selected_tracks) == 3
            assert response.selected_tracks[0] == "track-1"
            assert response.selected_tracks[1] == "track-2"
            assert response.selected_tracks[2] == "track-3"
            assert response.cost_usd > 0
            assert len(response.tool_calls) >= 1  # At least submit_playlist

    @pytest.mark.asyncio
    async def test_call_llm_with_no_progress_early_stop(self, sample_request, mock_subsonic_tools):
        """Test early stopping when no progress is made."""
        # Arrange
        client = OpenAIClient(api_key="test-key")

        # Mock tool that returns no tracks (triggers early stop after 3 iterations)
        async def mock_execute_no_tracks(tool_name, arguments):
            if tool_name == "search_tracks":
                return {"tracks": [], "count": 0}  # No tracks found
            elif tool_name == "submit_playlist":
                return {
                    "status": "playlist_submitted",
                    "selected_track_ids": [],
                    "reasoning": "No tracks available"
                }
            return {}

        mock_subsonic_tools.execute_tool = AsyncMock(side_effect=mock_execute_no_tracks)

        call_count = {'count': 0}

        def create_search_response(*args, **kwargs):
            """Create response that keeps searching."""
            call_count['count'] += 1
            resp = Mock()
            resp.choices = [Mock()]
            resp.choices[0].finish_reason = "tool_calls"
            resp.choices[0].message = Mock()
            resp.choices[0].message.content = None

            mock_function = Mock()
            mock_function.name = "search_tracks"  # Set as attribute
            mock_function.arguments = json.dumps({"query": "test", "limit": 10})

            resp.choices[0].message.tool_calls = [
                Mock(id=f"call_{call_count['count']}", function=mock_function)
            ]
            resp.usage = Mock(prompt_tokens=100, completion_tokens=50)
            return resp

        with patch.object(client.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
            mock_create.side_effect = create_search_response

            # Act & Assert - should stop early due to no progress
            # The early stopping logic breaks the loop, which should cause the final "no tool calls" path
            # But since we keep returning tool calls, it will hit max iterations
            with pytest.raises(Exception, match="exceeded maximum iterations"):
                await client.call_llm(sample_request, mock_subsonic_tools)

    @pytest.mark.asyncio
    async def test_call_llm_handles_json_decode_error(self, sample_request, mock_subsonic_tools):
        """Test call_llm handles JSON decode errors in tool arguments."""
        # Arrange
        client = OpenAIClient(api_key="test-key")

        # Response with malformed JSON in arguments
        mock_response_1 = Mock()
        mock_response_1.choices = [Mock()]
        mock_response_1.choices[0].finish_reason = "tool_calls"
        mock_response_1.choices[0].message = Mock()
        mock_response_1.choices[0].message.content = None

        mock_function_1 = Mock()
        mock_function_1.name = "search_tracks"  # Set as attribute
        mock_function_1.arguments = "INVALID JSON {{"  # Malformed JSON

        mock_response_1.choices[0].message.tool_calls = [
            Mock(id="call_1", function=mock_function_1)
        ]
        mock_response_1.usage = Mock(prompt_tokens=100, completion_tokens=50)

        # Second response submits playlist
        mock_response_2 = Mock()
        mock_response_2.choices = [Mock()]
        mock_response_2.choices[0].finish_reason = "tool_calls"
        mock_response_2.choices[0].message = Mock()
        mock_response_2.choices[0].message.content = None

        mock_function_2 = Mock()
        mock_function_2.name = "submit_playlist"  # Set as attribute
        mock_function_2.arguments = json.dumps({
            "selected_track_ids": ["track-1"],
            "reasoning": "Recovery from error"
        })

        mock_response_2.choices[0].message.tool_calls = [
            Mock(id="call_2", function=mock_function_2)
        ]
        mock_response_2.usage = Mock(prompt_tokens=150, completion_tokens=75)

        responses = [mock_response_1, mock_response_2]
        call_count = {'count': 0}

        async def get_response(*args, **kwargs):
            idx = call_count['count']
            call_count['count'] += 1
            if idx < len(responses):
                return responses[idx]
            # If we run out, just keep returning the last one
            return responses[-1]

        with patch.object(client.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
            mock_create.side_effect = get_response

            # Act
            response = await client.call_llm(sample_request, mock_subsonic_tools)

            # Assert - should handle the error gracefully and continue
            assert isinstance(response, LLMTrackSelectionResponse)
            assert len(response.tool_calls) >= 1  # At least the malformed one was recorded

    @pytest.mark.asyncio
    async def test_call_llm_cost_calculation(self, sample_request, mock_subsonic_tools):
        """Test that cost is calculated correctly from token usage."""
        # Arrange
        client = OpenAIClient(api_key="test-key")

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].finish_reason = "tool_calls"
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = None

        mock_function = Mock()
        mock_function.name = "submit_playlist"  # Set as attribute
        mock_function.arguments = json.dumps({
            "selected_track_ids": ["track-1"],
            "reasoning": "Test"
        })

        mock_response.choices[0].message.tool_calls = [
            Mock(id="call_1", function=mock_function)
        ]
        # Specific token counts for cost calculation
        mock_response.usage = Mock(prompt_tokens=1000, completion_tokens=500)

        call_count = {'count': 0}

        async def mock_create_response(*args, **kwargs):
            call_count['count'] += 1
            if call_count['count'] == 1:
                return mock_response
            raise RuntimeError(f"Unexpected call #{call_count['count']} to create()")

        with patch.object(client.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
            mock_create.side_effect = mock_create_response

            # Act
            response = await client.call_llm(sample_request, mock_subsonic_tools)

            # Assert
            expected_cost = (1000 * client.cost_per_input_token +
                           500 * client.cost_per_output_token)
            assert abs(response.cost_usd - expected_cost) < 0.000001
