"""Simple coverage tests for track_selector.py missing lines.

Simplified approach to hit specific uncovered lines.
"""
import pytest
from unittest.mock import AsyncMock, patch, Mock
import asyncio

from src.ai_playlist.track_selector import (
    _call_openai_api,
    _retry_with_backoff
)


class TestAPITimeouts:
    """Test exception handling in _call_openai_api (lines 269-272)."""

    @pytest.mark.asyncio
    async def test_timeout_raises_mcp_tool_error(self):
        """Test asyncio.TimeoutError is wrapped in MCPToolError (lines 269-270)."""
        # Arrange
        mock_client = AsyncMock()
        mock_client.chat.completions.create.side_effect = asyncio.TimeoutError()

        # Act & Assert
        from src.ai_playlist.exceptions import MCPToolError
        with pytest.raises(MCPToolError, match="timed out"):
            await _call_openai_api(
                client=mock_client,
                prompt="test",
                tools=[],
                timeout=1
            )

    @pytest.mark.asyncio
    async def test_generic_exception_raises_mcp_tool_error(self):
        """Test generic exceptions wrapped in MCPToolError (lines 271-272)."""
        # Arrange
        mock_client = AsyncMock()
        mock_client.chat.completions.create.side_effect = ValueError("Test error")

        # Act & Assert
        from src.ai_playlist.exceptions import MCPToolError
        with pytest.raises(MCPToolError, match="OpenAI API error"):
            await _call_openai_api(
                client=mock_client,
                prompt="test",
                tools=[],
                timeout=1
            )


class TestRetryBackoff:
    """Test _retry_with_backoff function."""

    @pytest.mark.asyncio
    async def test_retry_raises_on_final_attempt(self):
        """Test that retry raises exception on final attempt (line 288)."""
        # Arrange
        call_count = [0]

        async def failing_func():
            call_count[0] += 1
            raise ValueError(f"Attempt {call_count[0]} failed")

        # Act & Assert - Should raise on final attempt
        with pytest.raises(ValueError, match="Attempt 3 failed"):
            await _retry_with_backoff(
                func=failing_func,
                max_attempts=3,
                base_delay=0.01,
                max_delay=0.1
            )

        # Verify it tried 3 times
        assert call_count[0] == 3
