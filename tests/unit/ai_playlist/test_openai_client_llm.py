"""Core tests for openai_client.py - Part 2: LLM Async Methods.

Tests the main async LLM interaction methods:
- call_llm() - Multi-turn conversation with tool calling
- _parse_track_selection_response() - JSON and regex parsing
- _parse_tracks_from_response() - Track object creation
"""
import pytest
import uuid
import json
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from decimal import Decimal
from datetime import datetime, date, time

from src.ai_playlist.openai_client import OpenAIClient
from src.ai_playlist.models import (
    LLMTrackSelectionRequest,
    LLMTrackSelectionResponse,
    TrackSelectionCriteria,
    BPMRange,
    GenreCriteria,
    EraCriteria,
)
from src.ai_playlist.models.llm import SelectedTrack


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
        prompt_template="Generate a morning drive playlist with energetic rock music.",
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
                "description": "Search for tracks by query",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "limit": {"type": "integer"}
                    }
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "submit_playlist",
                "description": "Submit final playlist selection",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "selected_track_ids": {"type": "array"},
                        "reasoning": {"type": "string"}
                    },
                    "required": ["selected_track_ids"]
                }
            }
        }
    ]

    # Mock execute_tool to return search results or submission confirmation
    async def mock_execute_tool(tool_name, arguments):
        if tool_name == "search_tracks":
            return {
                "tracks": [
                    {
                        "id": f"track-{i}",
                        "title": f"Song {i}",
                        "artist": "Test Artist",
                        "album": "Test Album",
                        "genre": "Rock",
                        "year": 2023,
                        "bpm": 120,
                        "duration_seconds": 180,
                        "country": "AU"
                    }
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


class TestCallLLM:
    """Test OpenAIClient.call_llm async method."""

    @pytest.mark.asyncio
    async def test_call_llm_successful_submission(self, sample_request, mock_subsonic_tools):
        """Test successful LLM call with tool execution and submission."""
        # Arrange
        client = OpenAIClient(api_key="test-key")

        # Create responses list to allow iteration
        responses = []

        # First response: search_tracks tool call
        mock_response_1 = Mock()
        mock_response_1.choices = [Mock()]
        mock_response_1.choices[0].finish_reason = "tool_calls"
        mock_response_1.choices[0].message = Mock()
        mock_response_1.choices[0].message.content = None

        mock_function_1 = Mock()
        mock_function_1.name = "search_tracks"  # Set as attribute
        mock_function_1.arguments = json.dumps({"query": "rock", "limit": 10})

        mock_response_1.choices[0].message.tool_calls = [
            Mock(id="call_1", function=mock_function_1)
        ]
        mock_response_1.usage = Mock(prompt_tokens=100, completion_tokens=50)
        responses.append(mock_response_1)

        # Second response: submit_playlist tool call
        mock_response_2 = Mock()
        mock_response_2.choices = [Mock()]
        mock_response_2.choices[0].finish_reason = "tool_calls"
        mock_response_2.choices[0].message = Mock()
        mock_response_2.choices[0].message.content = None

        mock_function_2 = Mock()
        mock_function_2.name = "submit_playlist"  # Set as attribute
        mock_function_2.arguments = json.dumps({
            "selected_track_ids": ["track-1", "track-2", "track-3"],
            "reasoning": "Selected energetic rock tracks"
        })

        mock_response_2.choices[0].message.tool_calls = [
            Mock(id="call_2", function=mock_function_2)
        ]
        mock_response_2.usage = Mock(prompt_tokens=150, completion_tokens=75)
        responses.append(mock_response_2)

        response_iter = iter(responses)

        async def get_next_response(*args, **kwargs):
            try:
                return next(response_iter)
            except StopIteration:
                raise RuntimeError("No more mock responses available")

        with patch.object(client.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
            mock_create.side_effect = get_next_response

            # Act
            response = await client.call_llm(sample_request, mock_subsonic_tools)

            # Assert
            assert isinstance(response, LLMTrackSelectionResponse)
            assert response.request_id == sample_request.playlist_id
            assert len(response.selected_tracks) == 3
            assert response.selected_tracks == ["track-1", "track-2", "track-3"]
            assert response.cost_usd > 0
            assert response.execution_time_seconds > 0
            assert len(response.tool_calls) == 2  # search_tracks + submit_playlist

    @pytest.mark.asyncio
    async def test_call_llm_timeout_error(self, sample_request, mock_subsonic_tools):
        """Test LLM call raises TimeoutError when exceeding timeout."""
        # Arrange
        client = OpenAIClient(api_key="test-key")
        short_timeout_request = LLMTrackSelectionRequest(
            playlist_id=sample_request.playlist_id,
            criteria=sample_request.criteria,
            target_track_count=10,
            prompt_template="Test prompt",
            max_cost_usd=0.10,
            timeout_seconds=0.01  # Very short timeout (10ms)
        )

        # Mock slow OpenAI response that takes longer than timeout
        call_count = {'count': 0}

        async def slow_response(*args, **kwargs):
            call_count['count'] += 1
            await asyncio.sleep(0.05)  # 50ms delay - exceeds 10ms timeout
            mock_resp = Mock()
            mock_resp.choices = [Mock()]
            mock_resp.choices[0].finish_reason = "tool_calls"
            mock_resp.choices[0].message = Mock()
            mock_resp.choices[0].message.content = None
            mock_resp.choices[0].message.tool_calls = [
                Mock(
                    id=f"call_{call_count['count']}",
                    function=Mock(
                        name="search_tracks",
                        arguments=json.dumps({"query": "test", "limit": 10})
                    )
                )
            ]
            mock_resp.usage = Mock(prompt_tokens=100, completion_tokens=50)
            return mock_resp

        with patch.object(client.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
            mock_create.side_effect = slow_response

            # Act & Assert
            with pytest.raises(TimeoutError, match="exceeded timeout"):
                await client.call_llm(short_timeout_request, mock_subsonic_tools)

    @pytest.mark.asyncio
    async def test_call_llm_max_iterations_exceeded(self, sample_request, mock_subsonic_tools):
        """Test LLM call raises exception when exceeding max iterations."""
        # Arrange
        client = OpenAIClient(api_key="test-key")

        # Create a counter for unique call IDs
        call_counter = {'count': 0}

        def create_mock_response(*args, **kwargs):
            """Create mock response that keeps calling search_tracks."""
            call_counter['count'] += 1
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].finish_reason = "tool_calls"
            mock_response.choices[0].message = Mock()
            mock_response.choices[0].message.content = None
            mock_response.choices[0].message.tool_calls = [
                Mock(
                    id=f"call_{call_counter['count']}",
                    function=Mock(
                        name="search_tracks",
                        arguments=json.dumps({"query": "rock", "limit": 10})
                    )
                )
            ]
            mock_response.usage = Mock(prompt_tokens=100, completion_tokens=50)
            return mock_response

        with patch.object(client.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
            mock_create.side_effect = create_mock_response

            # Act & Assert
            with pytest.raises(Exception, match="exceeded maximum iterations"):
                await client.call_llm(sample_request, mock_subsonic_tools)

    @pytest.mark.asyncio
    async def test_call_llm_tool_execution_timeout(self, sample_request, mock_subsonic_tools):
        """Test LLM call handles tool execution timeouts gracefully."""
        # Arrange
        client = OpenAIClient(api_key="test-key", per_tool_timeout_seconds=0.001)

        # Mock slow tool execution
        async def slow_tool_execution(tool_name, arguments):
            if tool_name == "search_tracks":
                await asyncio.sleep(0.1)
                return {"tracks": []}
            elif tool_name == "submit_playlist":
                return {
                    "status": "playlist_submitted",
                    "selected_track_ids": arguments.get("selected_track_ids", []),
                    "reasoning": arguments.get("reasoning", "")
                }
            return {}

        mock_subsonic_tools.execute_tool = AsyncMock(side_effect=slow_tool_execution)

        # Create responses list
        responses = []

        # Mock OpenAI responses
        mock_response_1 = Mock()
        mock_response_1.choices = [Mock()]
        mock_response_1.choices[0].finish_reason = "tool_calls"
        mock_response_1.choices[0].message = Mock()
        mock_response_1.choices[0].message.content = None

        mock_func_1 = Mock()
        mock_func_1.name = "search_tracks"  # Set as attribute
        mock_func_1.arguments = json.dumps({"query": "rock", "limit": 10})

        mock_response_1.choices[0].message.tool_calls = [
            Mock(id="call_1", function=mock_func_1)
        ]
        mock_response_1.usage = Mock(prompt_tokens=100, completion_tokens=50)
        responses.append(mock_response_1)

        # Second response submits with empty playlist
        mock_response_2 = Mock()
        mock_response_2.choices = [Mock()]
        mock_response_2.choices[0].finish_reason = "tool_calls"
        mock_response_2.choices[0].message = Mock()
        mock_response_2.choices[0].message.content = None

        mock_func_2 = Mock()
        mock_func_2.name = "submit_playlist"  # Set as attribute
        mock_func_2.arguments = json.dumps({
            "selected_track_ids": ["fallback-track-1"],  # Need at least 1 track
            "reasoning": "Submitting with fallback tracks after timeout"
        })

        mock_response_2.choices[0].message.tool_calls = [
            Mock(id="call_2", function=mock_func_2)
        ]
        mock_response_2.usage = Mock(prompt_tokens=150, completion_tokens=75)
        responses.append(mock_response_2)

        response_iter = iter(responses)

        async def get_next_response(*args, **kwargs):
            try:
                return next(response_iter)
            except StopIteration:
                raise RuntimeError("No more mock responses available")

        with patch.object(client.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
            mock_create.side_effect = get_next_response

            # Act
            response = await client.call_llm(sample_request, mock_subsonic_tools)

            # Assert - should complete despite tool timeout
            assert isinstance(response, LLMTrackSelectionResponse)
            # Tool timeout should be recorded
            assert hasattr(response, '__dict__')
            if hasattr(response, '__dict__'):
                assert response.__dict__.get("tool_timeouts_count", 0) >= 1

    @pytest.mark.asyncio
    async def test_call_llm_rejected_submission_retry(self, sample_request, mock_subsonic_tools):
        """Test LLM retries after rejected submission."""
        # Arrange
        client = OpenAIClient(api_key="test-key")

        # Mock tool execution with rejection then success
        call_count = {'count': 0}

        async def mock_execute_with_rejection(tool_name, arguments):
            if tool_name == "submit_playlist":
                call_count['count'] += 1
                if call_count['count'] == 1:
                    # First submission rejected
                    return {
                        "status": "rejected",
                        "message": "Invalid track IDs provided"
                    }
                else:
                    # Second submission accepted
                    return {
                        "status": "playlist_submitted",
                        "selected_track_ids": arguments.get("selected_track_ids", []),
                        "reasoning": arguments.get("reasoning", "")
                    }
            elif tool_name == "search_tracks":
                return {
                    "tracks": [{"id": "track-1", "title": "Song 1", "artist": "Artist"}],
                    "count": 1
                }
            return {}

        mock_subsonic_tools.execute_tool = AsyncMock(side_effect=mock_execute_with_rejection)

        # Create responses list
        responses = []

        # Mock OpenAI responses
        mock_response_1 = Mock()
        mock_response_1.choices = [Mock()]
        mock_response_1.choices[0].finish_reason = "tool_calls"
        mock_response_1.choices[0].message = Mock()
        mock_response_1.choices[0].message.content = None

        mock_fn_1 = Mock()
        mock_fn_1.name = "submit_playlist"  # Set as attribute
        mock_fn_1.arguments = json.dumps({
            "selected_track_ids": ["invalid-id"],
            "reasoning": "Test"
        })

        mock_response_1.choices[0].message.tool_calls = [
            Mock(id="call_1", function=mock_fn_1)
        ]
        mock_response_1.usage = Mock(prompt_tokens=100, completion_tokens=50)
        responses.append(mock_response_1)

        mock_response_2 = Mock()
        mock_response_2.choices = [Mock()]
        mock_response_2.choices[0].finish_reason = "tool_calls"
        mock_response_2.choices[0].message = Mock()
        mock_response_2.choices[0].message.content = None

        mock_fn_2 = Mock()
        mock_fn_2.name = "submit_playlist"  # Set as attribute
        mock_fn_2.arguments = json.dumps({
            "selected_track_ids": ["track-1"],
            "reasoning": "Corrected submission"
        })

        mock_response_2.choices[0].message.tool_calls = [
            Mock(id="call_2", function=mock_fn_2)
        ]
        mock_response_2.usage = Mock(prompt_tokens=150, completion_tokens=75)
        responses.append(mock_response_2)

        response_iter = iter(responses)

        async def get_next_response(*args, **kwargs):
            try:
                return next(response_iter)
            except StopIteration:
                raise RuntimeError("No more mock responses available")

        with patch.object(client.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
            mock_create.side_effect = get_next_response

            # Act
            response = await client.call_llm(sample_request, mock_subsonic_tools)

            # Assert - should succeed on second attempt
            assert isinstance(response, LLMTrackSelectionResponse)
            assert len(response.selected_tracks) >= 1

    @pytest.mark.asyncio
    async def test_call_llm_api_error_propagates(self, sample_request, mock_subsonic_tools):
        """Test LLM call propagates OpenAI API errors."""
        # Arrange
        client = OpenAIClient(api_key="test-key")

        with patch.object(client.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
            mock_create.side_effect = Exception("OpenAI API error: Rate limit exceeded")

            # Act & Assert
            with pytest.raises(Exception, match="OpenAI API error"):
                await client.call_llm(sample_request, mock_subsonic_tools)

    @pytest.mark.asyncio
    async def test_call_llm_tracks_token_usage(self, sample_request, mock_subsonic_tools):
        """Test LLM call correctly tracks token usage and cost."""
        # Arrange
        client = OpenAIClient(api_key="test-key")

        # Create single response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].finish_reason = "tool_calls"
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = None

        mock_fn = Mock()
        mock_fn.name = "submit_playlist"  # Set as attribute
        mock_fn.arguments = json.dumps({
            "selected_track_ids": ["track-1"],
            "reasoning": "Test"
        })

        mock_response.choices[0].message.tool_calls = [
            Mock(id="call_1", function=mock_fn)
        ]
        mock_response.usage = Mock(prompt_tokens=1000, completion_tokens=500)

        response_iter = iter([mock_response])

        async def get_next_response(*args, **kwargs):
            try:
                return next(response_iter)
            except StopIteration:
                raise RuntimeError("No more mock responses available")

        with patch.object(client.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
            mock_create.side_effect = get_next_response

            # Act
            response = await client.call_llm(sample_request, mock_subsonic_tools)

            # Assert
            expected_cost = (1000 * client.cost_per_input_token +
                           500 * client.cost_per_output_token)
            assert abs(response.cost_usd - expected_cost) < 0.0001


class TestParseTrackSelectionResponse:
    """Test OpenAIClient._parse_track_selection_response method."""

    def test_parse_json_response_with_selected_track_ids(self):
        """Test parsing JSON response with selected_track_ids field."""
        # Arrange
        client = OpenAIClient(api_key="test-key")
        content = json.dumps({
            "selected_track_ids": ["track-1", "track-2", "track-3"],
            "reasoning": "Selected energetic rock tracks for morning drive"
        })

        # Act
        result = client._parse_track_selection_response(content)

        # Assert
        assert result["parse_method"] == "json"
        assert result["track_ids"] == ["track-1", "track-2", "track-3"]
        assert "energetic rock tracks" in result["reasoning"]

    def test_parse_json_response_with_track_ids_field(self):
        """Test parsing JSON response with track_ids field (alternative name)."""
        # Arrange
        client = OpenAIClient(api_key="test-key")
        content = json.dumps({
            "track_ids": ["track-a", "track-b"],
            "reasoning": "Test reasoning"
        })

        # Act
        result = client._parse_track_selection_response(content)

        # Assert
        assert result["parse_method"] == "json"
        assert result["track_ids"] == ["track-a", "track-b"]

    def test_parse_json_response_with_markdown_code_fence(self):
        """Test parsing JSON wrapped in markdown code fence."""
        # Arrange
        client = OpenAIClient(api_key="test-key")
        content = """Here's the playlist:

```json
{
    "selected_track_ids": ["track-1", "track-2"],
    "reasoning": "Test"
}
```
"""

        # Act
        result = client._parse_track_selection_response(content)

        # Assert
        assert result["parse_method"] == "json"
        assert result["track_ids"] == ["track-1", "track-2"]

    def test_parse_json_deduplicates_track_ids(self):
        """Test JSON parsing removes duplicate track IDs."""
        # Arrange
        client = OpenAIClient(api_key="test-key")
        content = json.dumps({
            "selected_track_ids": ["track-1", "track-2", "track-1", "track-3"],
            "reasoning": "Test"
        })

        # Act
        result = client._parse_track_selection_response(content)

        # Assert
        assert result["track_ids"] == ["track-1", "track-2", "track-3"]

    def test_parse_regex_fallback_track_id_format(self):
        """Test regex fallback for 'Track ID: <id>' format."""
        # Arrange
        client = OpenAIClient(api_key="test-key")
        content = """
Track ID: track-1
Track ID: track-2
Track ID: track-3
"""

        # Act
        result = client._parse_track_selection_response(content)

        # Assert
        assert result["parse_method"] == "regex_fallback"
        assert "track-1" in result["track_ids"]
        assert "track-2" in result["track_ids"]
        assert "track-3" in result["track_ids"]

    def test_parse_regex_fallback_numbered_list(self):
        """Test regex fallback for numbered list format."""
        # Arrange
        client = OpenAIClient(api_key="test-key")
        # Use format that matches the numbered_pattern regex: starts with digit dot space then track ID
        content = """
1. Track ID: track-alpha
2. Track ID: track-beta
3. Track ID: track-gamma
"""

        # Act
        result = client._parse_track_selection_response(content)

        # Assert
        assert result["parse_method"] == "regex_fallback"
        # Check that tracks were found
        assert len(result["track_ids"]) >= 3
        assert "track-alpha" in result["track_ids"]
        assert "track-beta" in result["track_ids"]
        assert "track-gamma" in result["track_ids"]

    def test_parse_malformed_json_falls_back_to_regex(self):
        """Test malformed JSON triggers regex fallback."""
        # Arrange
        client = OpenAIClient(api_key="test-key")
        content = """
{
    "selected_track_ids": ["track-1", "track-2"
    MALFORMED - missing closing brace

Track ID: track-fallback
"""

        # Act
        result = client._parse_track_selection_response(content)

        # Assert
        assert result["parse_method"] == "regex_fallback"
        assert "track-fallback" in result["track_ids"]

    def test_parse_empty_content_returns_empty_list(self):
        """Test parsing empty content returns empty track list."""
        # Arrange
        client = OpenAIClient(api_key="test-key")

        # Act
        result = client._parse_track_selection_response("")

        # Assert
        assert result["track_ids"] == []

    def test_parse_response_includes_content_snippet(self):
        """Test parsed result includes original content snippet for debugging."""
        # Arrange
        client = OpenAIClient(api_key="test-key")
        content = "A" * 500  # Long content

        # Act
        result = client._parse_track_selection_response(content)

        # Assert
        assert "original_content_snippet" in result
        assert len(result["original_content_snippet"]) == 200


class TestParseTracksFromResponse:
    """Test OpenAIClient._parse_tracks_from_response method."""

    def test_parse_tracks_creates_selected_track_objects(self):
        """Test parsing creates SelectedTrack objects with correct structure."""
        # Arrange
        client = OpenAIClient(api_key="test-key")
        content = json.dumps({
            "selected_track_ids": ["track-1", "track-2", "track-3"],
            "reasoning": "Test reasoning"
        })

        # Act
        tracks = client._parse_tracks_from_response(content, target_count=10)

        # Assert
        assert len(tracks) == 3
        assert all(isinstance(t, SelectedTrack) for t in tracks)
        assert tracks[0].track_id == "track-1"
        assert tracks[0].position == 1
        assert tracks[1].track_id == "track-2"
        assert tracks[1].position == 2

    def test_parse_tracks_limits_to_target_count(self):
        """Test parsing limits tracks to target count."""
        # Arrange
        client = OpenAIClient(api_key="test-key")
        content = json.dumps({
            "selected_track_ids": [f"track-{i}" for i in range(1, 21)],  # 20 tracks
            "reasoning": "Test"
        })

        # Act
        tracks = client._parse_tracks_from_response(content, target_count=10)

        # Assert
        assert len(tracks) == 10

    def test_parse_tracks_sets_default_metadata(self):
        """Test parsed tracks have sensible default metadata."""
        # Arrange
        client = OpenAIClient(api_key="test-key")
        content = json.dumps({
            "selected_track_ids": ["track-1"],
            "reasoning": "Selected for energy"
        })

        # Act
        tracks = client._parse_tracks_from_response(content, target_count=10)

        # Assert
        track = tracks[0]
        assert track.title == "Unknown"
        assert track.artist == "Unknown"
        assert track.album == "Unknown Album"
        assert track.genre == "Unknown"
        assert track.duration_seconds == 180
        assert "Selected for energy" in track.selection_reason or "Selected by LLM" in track.selection_reason

    def test_parse_tracks_returns_empty_list_when_no_ids(self):
        """Test parsing returns empty list when no track IDs found."""
        # Arrange
        client = OpenAIClient(api_key="test-key")
        content = "No track IDs in this content"

        # Act
        tracks = client._parse_tracks_from_response(content, target_count=10)

        # Assert
        assert tracks == []

    def test_parse_tracks_handles_regex_fallback(self):
        """Test track parsing works with regex fallback method."""
        # Arrange
        client = OpenAIClient(api_key="test-key")
        content = """
Track ID: track-regex-1
Track ID: track-regex-2
"""

        # Act
        tracks = client._parse_tracks_from_response(content, target_count=10)

        # Assert
        assert len(tracks) >= 2
        track_ids = [t.track_id for t in tracks]
        assert "track-regex-1" in track_ids
        assert "track-regex-2" in track_ids
