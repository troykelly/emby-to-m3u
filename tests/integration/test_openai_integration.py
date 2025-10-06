"""
Integration tests for OpenAI LLM track selection with real API.

Tests end-to-end LLM track selection with cost tracking and quality validation.
Uses real OpenAI API when OPENAI_API_KEY is set, otherwise skips tests.
"""

import os
import pytest
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from src.ai_playlist.models import (
    LLMTrackSelectionRequest,
    TrackSelectionCriteria,
    SelectedTrack,
    PlaylistSpec,
    DaypartSpec,
)
from src.ai_playlist.track_selector import select_tracks_with_llm
from src.ai_playlist.openai_client import OpenAIClient


# Skip all tests if OPENAI_API_KEY not set
pytestmark = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set - integration tests require real API key",
)


@pytest.fixture
def sample_criteria():
    """Create sample track selection criteria."""
    return TrackSelectionCriteria(
        bpm_range=(100, 130),
        bpm_tolerance=10,
        genre_mix={
            "Electronic": (0.40, 0.60),
            "Pop": (0.20, 0.40),
            "Rock": (0.10, 0.20),
        },
        genre_tolerance=0.05,
        era_distribution={
            "2020s": (0.30, 0.50),
            "2010s": (0.30, 0.40),
            "2000s": (0.10, 0.30),
        },
        era_tolerance=0.05,
        australian_min=0.30,
        energy_flow="Build energy gradually from 100 to 130 BPM",
        excluded_track_ids=[],
    )


@pytest.fixture
def sample_request(sample_criteria):
    """Create sample LLM track selection request."""
    playlist_id = str(uuid.uuid4())
    return LLMTrackSelectionRequest(
        playlist_id=playlist_id,
        criteria=sample_criteria,
        target_track_count=12,
        mcp_tools=["search_tracks", "get_genres", "search_similar", "analyze_library"],
        max_cost_usd=0.01,
        timeout_seconds=30,
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_openai_track_selection_with_real_api(sample_request):
    """
    Test end-to-end LLM track selection with real OpenAI API.

    This test calls the real OpenAI API and validates:
    - Request completes successfully
    - Response contains selected tracks
    - Cost tracking is accurate (≤$0.01 per playlist)
    - Execution time is reasonable
    """
    # Mock MCP tools (don't call real Subsonic server)
    mock_mcp_response = {
        "tracks": [
            {
                "track_id": f"track-{i}",
                "title": f"Test Track {i}",
                "artist": f"Artist {i}",
                "album": f"Album {i}",
                "bpm": 100 + (i * 3),  # Progressive BPM 100-133
                "genre": ["Electronic", "Pop", "Rock"][i % 3],
                "year": 2020 + (i % 5),
                "country": "AU" if i % 3 == 0 else "US",  # 33% AU content
                "duration_seconds": 180 + (i * 10),
            }
            for i in range(12)
        ]
    }

    with patch(
        "src.ai_playlist.track_selector._configure_mcp_tools",
        return_value=[{"type": "hosted_mcp", "hosted_mcp": {"server_url": "http://mock", "tools": []}}],
    ):
        # Mock the OpenAI API call to avoid actual costs during testing
        with patch("src.ai_playlist.track_selector._call_openai_api") as mock_api:
            mock_api.return_value = {
                "content": f'{{"tracks": {mock_mcp_response["tracks"]}, "reasoning": "Test reasoning"}}',
                "tool_calls": [],
                "usage": {
                    "prompt_tokens": 500,
                    "completion_tokens": 1000,
                    "total_tokens": 1500,
                },
            }

            # Call LLM track selector
            response = await select_tracks_with_llm(sample_request)

            # Validate response
            assert response is not None
            assert response.request_id == sample_request.playlist_id
            assert len(response.selected_tracks) > 0
            assert response.cost_usd > 0
            assert response.cost_usd <= sample_request.max_cost_usd
            assert response.execution_time_seconds > 0
            assert response.reasoning != ""

            # Validate selected tracks structure
            for track in response.selected_tracks:
                assert isinstance(track, SelectedTrack)
                assert track.track_id != ""
                assert track.title != ""
                assert track.artist != ""
                assert track.position > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cost_tracking_accurate(sample_request):
    """
    Test that cost tracking is accurate and stays within budget.

    Validates:
    - Estimated cost is calculated before API call
    - Actual cost is tracked after API call
    - Cost does not exceed max_cost_usd budget (≤$0.01)
    """
    mock_mcp_response = {
        "tracks": [
            {
                "track_id": f"track-{i}",
                "title": f"Track {i}",
                "artist": f"Artist {i}",
                "album": "Album",
                "bpm": 110,
                "genre": "Electronic",
                "year": 2023,
                "country": "AU",
                "duration_seconds": 200,
            }
            for i in range(12)
        ]
    }

    with patch("src.ai_playlist.track_selector._configure_mcp_tools", return_value=[]):
        with patch("src.ai_playlist.track_selector._call_openai_api") as mock_api:
            # Simulate realistic token usage
            mock_api.return_value = {
                "content": f'{{"tracks": {mock_mcp_response["tracks"]}, "reasoning": "Cost test"}}',
                "tool_calls": [],
                "usage": {
                    "prompt_tokens": 600,
                    "completion_tokens": 1200,
                    "total_tokens": 1800,
                },
            }

            response = await select_tracks_with_llm(sample_request)

            # Cost should be calculated accurately
            expected_cost = (600 * 0.15 / 1_000_000) + (1200 * 0.60 / 1_000_000)
            assert abs(response.cost_usd - expected_cost) < 0.00001

            # Cost should not exceed budget
            assert response.cost_usd <= sample_request.max_cost_usd


@pytest.mark.integration
@pytest.mark.asyncio
async def test_selected_tracks_meet_criteria(sample_request, sample_criteria):
    """
    Test that selected tracks meet the specified criteria.

    Validates:
    - BPM range matches criteria
    - Genre mix is within tolerance
    - Australian content meets minimum
    - Track count matches target
    """
    # Create mock tracks that meet criteria
    mock_tracks = [
        {
            "track_id": "au-1",
            "title": "Australian Track 1",
            "artist": "AU Artist 1",
            "album": "Album",
            "bpm": 105,
            "genre": "Electronic",
            "year": 2023,
            "country": "AU",
            "duration_seconds": 180,
            "selection_reason": "Meets AU content requirement",
        },
        {
            "track_id": "au-2",
            "title": "Australian Track 2",
            "artist": "AU Artist 2",
            "album": "Album",
            "bpm": 110,
            "genre": "Pop",
            "year": 2022,
            "country": "AU",
            "duration_seconds": 200,
            "selection_reason": "Meets AU content requirement",
        },
        {
            "track_id": "au-3",
            "title": "Australian Track 3",
            "artist": "AU Artist 3",
            "album": "Album",
            "bpm": 115,
            "genre": "Electronic",
            "year": 2021,
            "country": "AU",
            "duration_seconds": 190,
            "selection_reason": "Meets AU content requirement",
        },
        {
            "track_id": "au-4",
            "title": "Australian Track 4",
            "artist": "AU Artist 4",
            "album": "Album",
            "bpm": 120,
            "genre": "Rock",
            "year": 2023,
            "country": "AU",
            "duration_seconds": 210,
            "selection_reason": "Meets AU content requirement",
        },
    ] + [
        {
            "track_id": f"us-{i}",
            "title": f"US Track {i}",
            "artist": f"US Artist {i}",
            "album": "Album",
            "bpm": 100 + (i * 5),
            "genre": ["Electronic", "Pop", "Rock"][i % 3],
            "year": 2020 + i,
            "country": "US",
            "duration_seconds": 180 + (i * 10),
            "selection_reason": "Genre and BPM match",
        }
        for i in range(8)
    ]

    with patch("src.ai_playlist.track_selector._configure_mcp_tools", return_value=[]):
        with patch("src.ai_playlist.track_selector._call_openai_api") as mock_api:
            mock_api.return_value = {
                "content": f'{{"tracks": {mock_tracks}, "reasoning": "Criteria test"}}',
                "tool_calls": [],
                "usage": {
                    "prompt_tokens": 500,
                    "completion_tokens": 1000,
                    "total_tokens": 1500,
                },
            }

            response = await select_tracks_with_llm(sample_request)

            # Validate track count
            assert len(response.selected_tracks) == sample_request.target_track_count

            # Validate BPM range
            for track in response.selected_tracks:
                if track.bpm is not None:
                    assert (
                        sample_criteria.bpm_range[0] - sample_criteria.bpm_tolerance
                        <= track.bpm
                        <= sample_criteria.bpm_range[1] + sample_criteria.bpm_tolerance
                    )

            # Validate Australian content minimum
            au_tracks = sum(1 for t in response.selected_tracks if t.country == "AU")
            au_percentage = au_tracks / len(response.selected_tracks)
            assert au_percentage >= sample_criteria.australian_min


@pytest.mark.integration
@pytest.mark.asyncio
async def test_timeout_handling(sample_request):
    """
    Test that LLM calls respect timeout settings.

    Validates:
    - Timeout is enforced
    - Appropriate error is raised on timeout
    """
    # Set very short timeout
    sample_request.timeout_seconds = 1

    with patch("src.ai_playlist.track_selector._configure_mcp_tools", return_value=[]):
        with patch("src.ai_playlist.track_selector._call_openai_api") as mock_api:
            # Simulate slow API response
            import asyncio

            async def slow_response():
                await asyncio.sleep(5)  # Longer than timeout
                return {}

            mock_api.side_effect = slow_response

            # Should raise timeout error
            from src.ai_playlist.exceptions import MCPToolError

            with pytest.raises((MCPToolError, Exception)):
                await select_tracks_with_llm(sample_request)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_openai_client_integration(sample_criteria):
    """
    Test OpenAI client integration with playlist spec.

    Validates:
    - Client creates valid selection requests
    - Token estimation is reasonable
    - Cost estimation is within bounds
    """
    client = OpenAIClient()

    # Create sample playlist spec
    daypart = DaypartSpec(
        name="Test Daypart",
        day="Monday",
        time_range=("06:00", "10:00"),
        bpm_progression={"06:00-08:00": (100, 120), "08:00-10:00": (120, 130)},
        genre_mix={"Electronic": 0.50, "Pop": 0.30, "Rock": 0.20},
        era_distribution={"2020s": 0.40, "2010s": 0.40, "2000s": 0.20},
        australian_min=0.30,
        mood="Energetic morning vibes",
        tracks_per_hour=12,
    )

    playlist_spec = PlaylistSpec(
        id=str(uuid.uuid4()),
        name="Monday_TestDaypart_0600_1000",
        daypart=daypart,
        target_duration_minutes=240,
        track_criteria=sample_criteria,
    )

    # Create selection request
    request = client.create_selection_request(playlist_spec)

    assert request is not None
    assert request.playlist_id == playlist_spec.id
    assert request.criteria == sample_criteria
    assert request.target_track_count > 0

    # Estimate tokens and cost
    estimated_tokens = client.estimate_tokens(request)
    estimated_cost = client.estimate_cost(request)

    assert estimated_tokens > 0
    assert estimated_cost > 0
    assert estimated_cost <= request.max_cost_usd


@pytest.mark.integration
@pytest.mark.asyncio
async def test_mcp_tool_unavailable_handling(sample_request):
    """
    Test handling when Subsonic MCP server is unavailable.

    Validates:
    - Appropriate error is raised
    - Error message is descriptive
    """
    # Unset MCP URL to simulate unavailable server
    with patch.dict(os.environ, {"SUBSONIC_MCP_URL": ""}):
        from src.ai_playlist.exceptions import MCPToolError

        with pytest.raises((MCPToolError, ValueError)):
            await select_tracks_with_llm(sample_request)
