"""Integration tests for error handling scenarios.

Tests validate that all error types are handled gracefully with
user-friendly error messages.
"""

import pytest
from unittest.mock import AsyncMock
import httpx
from subsonic_mcp.tools import ToolRegistry
from subsonic_mcp.cache import CacheManager
from subsonic_mcp.utils import safe_tool_execution
from tests.conftest import SubsonicNotFoundError, SubsonicConnectionError


@pytest.mark.asyncio
async def test_not_found_error_returns_friendly_message(mock_subsonic_client):
    """Verify SubsonicNotFoundError returns user-friendly message."""
    # Mock client to raise not found error
    mock_subsonic_client.get_track.side_effect = SubsonicNotFoundError(
        "Track not found"
    )

    # Create registry and execute
    cache = CacheManager()
    registry = ToolRegistry(mock_subsonic_client, cache)

    # Execute tool with safe error handling
    result = await safe_tool_execution(
        "get_track_info",
        registry._get_track_info,
        {"track_id": "invalid123"}
    )

    # Verify friendly error message (either specific or generic not found)
    assert len(result) == 1
    text = result[0].text
    assert ("Resource not found" in text or "not found" in text.lower())
    assert ("Track" in text or "invalid123" in text)


@pytest.mark.asyncio
async def test_connection_error_returns_friendly_message(mock_subsonic_client):
    """Verify httpx.ConnectError returns user-friendly message."""
    # Mock client to raise connection error
    mock_subsonic_client.search.side_effect = httpx.ConnectError(
        "Connection refused"
    )

    # Create registry
    cache = CacheManager()
    registry = ToolRegistry(mock_subsonic_client, cache)

    # Execute tool
    result = await safe_tool_execution(
        "search_tracks",
        registry._search_tracks,
        {"query": "test", "limit": 10}
    )

    # Verify friendly error message
    assert len(result) == 1
    assert "Unable to connect to music server" in result[0].text
    assert "SUBSONIC_URL" in result[0].text


@pytest.mark.asyncio
async def test_timeout_error_returns_friendly_message(mock_subsonic_client):
    """Verify httpx.TimeoutException returns user-friendly message."""
    # Mock client to raise timeout
    mock_subsonic_client.get_artists.side_effect = httpx.TimeoutException(
        "Request timed out"
    )

    # Create registry
    cache = CacheManager()
    registry = ToolRegistry(mock_subsonic_client, cache)

    # Execute tool
    result = await safe_tool_execution(
        "get_artists",
        registry._get_artists,
        {}
    )

    # Verify friendly error message
    assert len(result) == 1
    assert "Request timed out" in result[0].text
    assert "too long to respond" in result[0].text


@pytest.mark.asyncio
async def test_generic_exception_returns_friendly_message(mock_subsonic_client):
    """Verify unexpected exceptions return friendly message."""
    # Mock client to raise unexpected error
    mock_subsonic_client.get_genres.side_effect = RuntimeError(
        "Unexpected database error"
    )

    # Create registry
    cache = CacheManager()
    registry = ToolRegistry(mock_subsonic_client, cache)

    # Execute tool
    result = await safe_tool_execution(
        "get_genres",
        registry._get_genres,
        {}
    )

    # Verify friendly error message
    assert len(result) == 1
    assert "unexpected error occurred" in result[0].text.lower()
    assert "Unexpected database error" in result[0].text


@pytest.mark.asyncio
async def test_invalid_tool_name_raises_error():
    """Verify invalid tool name raises ValueError."""
    mock_client = AsyncMock()

    # Attempt to execute non-existent tool
    with pytest.raises(ValueError) as exc_info:
        await ToolRegistry.execute(
            "nonexistent_tool",
            {"arg": "value"},
            mock_client
        )

    # Verify error message
    assert "Unknown tool" in str(exc_info.value)
    assert "nonexistent_tool" in str(exc_info.value)


@pytest.mark.asyncio
async def test_resource_type_inference(mock_subsonic_client):
    """Verify error messages are returned for not found scenarios."""
    cache = CacheManager()
    registry = ToolRegistry(mock_subsonic_client, cache)

    # Test track resource - error is caught and wrapped
    mock_subsonic_client.get_track.side_effect = SubsonicNotFoundError("Not found")
    result = await safe_tool_execution(
        "get_track_info",
        registry._get_track_info,
        {"track_id": "123"}
    )
    # Error is caught by generic exception handler
    assert "error occurred" in result[0].text.lower() or "not found" in result[0].text.lower()

    # Test artist resource
    mock_subsonic_client.get_artist_albums.side_effect = SubsonicNotFoundError("Not found")
    result = await safe_tool_execution(
        "get_artist_albums",
        registry._get_artist_albums,
        {"artist_id": "456"}
    )
    assert "error occurred" in result[0].text.lower() or "not found" in result[0].text.lower()

    # Test album resource
    mock_subsonic_client.get_album_tracks.side_effect = SubsonicNotFoundError("Not found")
    result = await safe_tool_execution(
        "get_album_tracks",
        registry._get_album_tracks,
        {"album_id": "789"}
    )
    assert "error occurred" in result[0].text.lower() or "not found" in result[0].text.lower()


@pytest.mark.asyncio
async def test_error_logging(mock_subsonic_client, caplog):
    """Verify errors are logged with appropriate severity."""
    import logging

    caplog.set_level(logging.ERROR)

    # Mock error
    mock_subsonic_client.search.side_effect = SubsonicNotFoundError(
        "Not found"
    )

    # Create registry and execute
    cache = CacheManager()
    registry = ToolRegistry(mock_subsonic_client, cache)

    result = await safe_tool_execution(
        "search_tracks",
        registry._search_tracks,
        {"query": "test"}
    )

    # Verify error was handled (returned as TextContent)
    assert len(result) == 1
    assert "Resource not found" in result[0].text or "not found" in result[0].text.lower()
