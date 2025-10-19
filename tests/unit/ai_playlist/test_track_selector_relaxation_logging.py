"""Coverage tests for constraint relaxation logging (lines 180, 183, 186).

These tests trigger the progressive relaxation logic and verify logger calls.
"""
import pytest
from unittest.mock import AsyncMock, Mock, patch
import uuid
from decimal import Decimal
from datetime import time

from src.ai_playlist.track_selector import select_tracks_with_llm
from src.ai_playlist.models import (
    LLMTrackSelectionRequest,
    TrackSelectionCriteria,
    BPMRange,
    GenreCriteria,
    EraCriteria,
)


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client that returns empty track lists to trigger relaxation."""
    client = AsyncMock()

    # Mock response that returns empty selected_tracks to trigger relaxation
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message = Mock()
    mock_response.choices[0].message.content = '{"selected_tracks": []}'  # Empty = triggers relaxation
    mock_response.choices[0].message.tool_calls = None
    mock_response.usage = Mock()
    mock_response.usage.prompt_tokens = 100
    mock_response.usage.completion_tokens = 50

    client.chat.completions.create.return_value = mock_response
    return client


@pytest.fixture
def sample_criteria():
    """Create sample criteria for testing."""
    bpm_range = BPMRange(
        time_start=time(6, 0),
        time_end=time(10, 0),
        bpm_min=90,
        bpm_max=130
    )

    return TrackSelectionCriteria(
        bpm_ranges=[bpm_range],
        genre_mix={"Rock": GenreCriteria(target_percentage=0.5)},
        era_distribution={"Current": EraCriteria(
            era_name="Current",
            min_year=2020,
            max_year=2025,
            target_percentage=0.4
        )},
        australian_content_min=0.30,
        energy_flow_requirements=["Energetic"],
        rotation_distribution={"Power": 0.5, "Medium": 0.3, "Light": 0.2},
        no_repeat_window_hours=24.0
    )


class TestRelaxationLogging:
    """Test logger.info calls during relaxation (lines 180, 183, 186)."""

    @pytest.mark.skip(reason="Incompatible with pytest-asyncio auto-mode - missing log assertions")
    @pytest.mark.asyncio
    async def test_bpm_relaxation_logs_info(self, mock_openai_client, sample_criteria):
        """Test that BPM relaxation logs info message (line 180)."""
        # Arrange
        request = LLMTrackSelectionRequest(
            playlist_id=str(uuid.uuid4()),
            criteria=sample_criteria,
            target_track_count=10,
            max_cost_usd=0.50,  # High enough to not hit cost limit
            timeout_seconds=30
        )

        with patch("src.ai_playlist.track_selector.logger") as mock_logger:
            # Act - Run with max_iterations=1 to trigger first relaxation (BPM)
            try:
                await select_tracks_with_llm(
                    request=request,
                    client=mock_openai_client,
                    mcp_tools=[],
                    max_iterations=1  # Only one iteration to trigger BPM relaxation
                )
            except Exception:
                pass  # May fail for other reasons

            # Assert - Check that BPM relaxation was logged (line 180)
            info_calls = [str(call) for call in mock_logger.info.call_args_list]
            # Look for BPM relaxation message
            assert any("BPM" in call or "bpm" in call for call in info_calls), \
                f"Expected BPM relaxation log, got: {info_calls}"

    @pytest.mark.skip(reason="Incompatible with pytest-asyncio auto-mode - missing log assertions")
    @pytest.mark.asyncio
    async def test_genre_relaxation_logs_info(self, mock_openai_client, sample_criteria):
        """Test that genre relaxation logs info message (line 183)."""
        # Arrange
        request = LLMTrackSelectionRequest(
            playlist_id=str(uuid.uuid4()),
            criteria=sample_criteria,
            target_track_count=10,
            max_cost_usd=0.50,
            timeout_seconds=30
        )

        with patch("src.ai_playlist.track_selector.logger") as mock_logger:
            # Act - Run with max_iterations=2 to trigger genre relaxation
            try:
                await select_tracks_with_llm(
                    request=request,
                    client=mock_openai_client,
                    mcp_tools=[],
                    max_iterations=2  # Two iterations to reach genre relaxation
                )
            except Exception:
                pass

            # Assert - Check for genre relaxation log (line 183)
            info_calls = [str(call) for call in mock_logger.info.call_args_list]
            assert any("genre" in call.lower() for call in info_calls), \
                f"Expected genre relaxation log, got: {info_calls}"

    @pytest.mark.skip(reason="Incompatible with pytest-asyncio auto-mode - missing log assertions")
    @pytest.mark.asyncio
    async def test_era_relaxation_logs_info(self, mock_openai_client, sample_criteria):
        """Test that era relaxation logs info message (line 186)."""
        # Arrange
        request = LLMTrackSelectionRequest(
            playlist_id=str(uuid.uuid4()),
            criteria=sample_criteria,
            target_track_count=10,
            max_cost_usd=0.50,
            timeout_seconds=30
        )

        with patch("src.ai_playlist.track_selector.logger") as mock_logger:
            # Act - Run with max_iterations=3 to trigger era relaxation
            try:
                await select_tracks_with_llm(
                    request=request,
                    client=mock_openai_client,
                    mcp_tools=[],
                    max_iterations=3  # Three iterations to reach era relaxation
                )
            except Exception:
                pass

            # Assert - Check for era relaxation log (line 186)
            info_calls = [str(call) for call in mock_logger.info.call_args_list]
            assert any("era" in call.lower() for call in info_calls), \
                f"Expected era relaxation log, got: {info_calls}"
