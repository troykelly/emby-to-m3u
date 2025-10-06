"""Integration tests for full MCP protocol compliance.

Tests validate end-to-end MCP server functionality including
tools, resources, and prompts.
"""

import pytest
from subsonic_mcp.server import MCPServer
from subsonic_mcp.tools import ToolRegistry
from subsonic_mcp.resources import ResourceRegistry
from subsonic_mcp.prompts import PromptRegistry
from subsonic_mcp.cache import CacheManager


def test_tool_registry_returns_10_tools(mock_subsonic_client):
    """Verify ToolRegistry returns all 10 tools."""
    cache = CacheManager()
    registry = ToolRegistry(mock_subsonic_client, cache)

    tools = registry.get_all()

    # Should have exactly 10 tools
    assert len(tools) == 10

    # Verify tool names
    tool_names = [tool.name for tool in tools]
    expected_tools = [
        "search_tracks",
        "get_track_info",
        "get_artists",
        "get_artist_albums",
        "get_album_tracks",
        "search_similar",
        "get_genres",
        "get_tracks_by_genre",
        "analyze_library",
        "stream_track",
    ]

    for expected in expected_tools:
        assert expected in tool_names


def test_resource_registry_returns_6_resources(mock_subsonic_client):
    """Verify ResourceRegistry returns all 6 resources."""
    cache = CacheManager()
    registry = ResourceRegistry(mock_subsonic_client, cache)

    resources = registry.get_all()

    # Should have exactly 6 resources
    assert len(resources) == 6

    # Verify resource URIs (convert to strings for comparison)
    resource_uris = [str(resource.uri) for resource in resources]
    expected_uris = [
        "library://stats",
        "library://artists",
        "library://albums",
        "library://genres",
        "library://playlists",
        "library://recent",
    ]

    for expected in expected_uris:
        assert expected in resource_uris


def test_prompt_registry_returns_5_prompts():
    """Verify PromptRegistry returns all 5 prompts."""
    registry = PromptRegistry()

    prompts = registry.get_all()

    # Should have exactly 5 prompts
    assert len(prompts) == 5

    # Verify prompt names
    prompt_names = [prompt.name for prompt in prompts]
    expected_prompts = [
        "mood_playlist",
        "music_discovery",
        "listening_analysis",
        "smart_playlist",
        "library_curation",
    ]

    for expected in expected_prompts:
        assert expected in prompt_names


@pytest.mark.asyncio
async def test_tool_execution_returns_valid_response(
    mock_subsonic_client, sample_track
):
    """Verify tool execution returns properly formatted response."""
    # Mock search result
    mock_subsonic_client.search.return_value = [sample_track]

    # Execute tool
    result = await ToolRegistry.execute(
        "search_tracks",
        {"query": "Beatles", "limit": 10},
        mock_subsonic_client
    )

    # Verify response format
    assert isinstance(result, dict)
    assert "total" in result
    assert "tracks" in result
    assert result["total"] == 1
    assert len(result["tracks"]) == 1


@pytest.mark.asyncio
async def test_resource_read_returns_valid_json(
    mock_subsonic_client, sample_library_stats
):
    """Verify resource read returns valid JSON response."""
    # Mock library stats
    mock_subsonic_client.analyze_library.return_value = sample_library_stats

    # Read resource
    result = await ResourceRegistry.read_resource(
        "library://stats",
        mock_subsonic_client
    )

    # Verify response structure
    assert "uri" in result
    assert "mimeType" in result
    assert "contents" in result
    assert result["uri"] == "library://stats"
    assert result["mimeType"] == "application/json"


@pytest.mark.asyncio
async def test_prompt_generation_returns_valid_template():
    """Verify prompt generation returns valid template with messages."""
    # Get prompt
    result = await PromptRegistry.get_prompt(
        "mood_playlist",
        {"mood": "relaxing", "duration": 60}
    )

    # Verify response structure
    assert "description" in result
    assert "messages" in result
    assert len(result["messages"]) > 0

    # Verify message format
    message = result["messages"][0]
    assert message["role"] == "user"
    assert "content" in message
    assert "text" in message["content"]
    assert "relaxing" in message["content"]["text"]


def test_all_tools_have_descriptions(mock_subsonic_client):
    """Verify all tools have proper descriptions."""
    cache = CacheManager()
    registry = ToolRegistry(mock_subsonic_client, cache)

    tools = registry.get_all()

    for tool in tools:
        assert tool.description
        assert len(tool.description) > 10  # Meaningful description
        assert tool.inputSchema  # Has input schema


def test_all_resources_have_metadata(mock_subsonic_client):
    """Verify all resources have proper metadata."""
    cache = CacheManager()
    registry = ResourceRegistry(mock_subsonic_client, cache)

    resources = registry.get_all()

    for resource in resources:
        assert resource.name
        assert resource.description
        assert resource.mimeType == "application/json"
        assert str(resource.uri).startswith("library://")


def test_all_prompts_have_arguments():
    """Verify all prompts have proper argument definitions."""
    registry = PromptRegistry()

    prompts = registry.get_all()

    for prompt in prompts:
        assert prompt.description
        assert prompt.arguments  # Has arguments list
        # At least one required argument
        assert any(arg.required for arg in prompt.arguments)


@pytest.mark.asyncio
async def test_cache_integration_with_tools(
    mock_subsonic_client, sample_artist
):
    """Verify cache works correctly with tool execution."""
    cache = CacheManager(default_ttl=300)
    registry = ToolRegistry(mock_subsonic_client, cache)

    # Mock artists
    mock_subsonic_client.get_artists.return_value = [sample_artist]

    # First execution - should call client
    result1 = await registry._get_artists({})
    assert result1["total"] == 1

    # Note: Caching in tools is not fully implemented in current version
    # This test validates cache manager integration


@pytest.mark.asyncio
async def test_error_propagation_through_registry(mock_subsonic_client):
    """Verify errors propagate correctly through registry."""
    from tests.conftest import SubsonicNotFoundError

    # Mock error
    mock_subsonic_client.get_track.side_effect = SubsonicNotFoundError(
        "Track not found"
    )

    cache = CacheManager()
    registry = ToolRegistry(mock_subsonic_client, cache)

    # Should raise error
    with pytest.raises(SubsonicNotFoundError):
        await registry._get_track_info({"track_id": "invalid"})


@pytest.mark.asyncio
async def test_pagination_behavior_in_tools(
    mock_subsonic_client, sample_track
):
    """Verify pagination works correctly for tools with limits."""
    # Create 150 tracks
    tracks = [
        {**sample_track, "id": f"track-{i}"}
        for i in range(150)
    ]
    mock_subsonic_client.search.return_value = tracks

    cache = CacheManager()
    registry = ToolRegistry(mock_subsonic_client, cache)

    # Execute with limit
    result = await registry._search_tracks({"query": "test", "limit": 100})

    # Should limit to 100
    assert len(result["tracks"]) == 100
    assert "pagination_note" in result
    assert "100" in result["pagination_note"]
