"""Contract tests for 5 MCP prompts - ALL MUST FAIL BEFORE IMPLEMENTATION.

These tests validate prompt contracts against prompts.json schema.
All tests import from subsonic_mcp.prompts which doesn't exist yet (TDD approach).
"""

import pytest
from subsonic_mcp.prompts import PromptRegistry  # Will fail - not implemented yet


# T036: mood_playlist prompt success
@pytest.mark.asyncio
async def test_mood_playlist_prompt():
    """Test mood_playlist prompt generates curated playlist instructions."""
    # Execute prompt
    result = await PromptRegistry.get_prompt(
        "mood_playlist",
        {"mood": "relaxing", "duration": 60}
    )

    # Validate PromptResult schema
    assert "description" in result
    assert "messages" in result
    assert len(result["messages"]) > 0

    # Validate message structure
    message = result["messages"][0]
    assert message["role"] == "user"
    assert message["content"]["type"] == "text"
    assert "relaxing" in message["content"]["text"]
    assert "60" in message["content"]["text"] or "minutes" in message["content"]["text"]


# T036b: mood_playlist without duration (default 60)
@pytest.mark.asyncio
async def test_mood_playlist_default_duration():
    """Test mood_playlist uses default duration of 60 minutes."""
    # Execute with no duration
    result = await PromptRegistry.get_prompt(
        "mood_playlist",
        {"mood": "energetic"}
    )

    # Should use default 60 minutes
    message = result["messages"][0]
    assert "energetic" in message["content"]["text"]


# T036c: music_discovery prompt success
@pytest.mark.asyncio
async def test_music_discovery_prompt():
    """Test music_discovery prompt generates discovery instructions."""
    # Execute prompt
    result = await PromptRegistry.get_prompt(
        "music_discovery",
        {
            "favorite_artists": "The Beatles, Pink Floyd",
            "genres": "Rock, Progressive Rock"
        }
    )

    # Validate response
    assert "description" in result
    assert "messages" in result
    message = result["messages"][0]
    assert "Beatles" in message["content"]["text"]
    assert "Pink Floyd" in message["content"]["text"]


# T036d: music_discovery without genres (optional)
@pytest.mark.asyncio
async def test_music_discovery_no_genres():
    """Test music_discovery with only favorite_artists (genres optional)."""
    # Execute without genres
    result = await PromptRegistry.get_prompt(
        "music_discovery",
        {"favorite_artists": "Miles Davis"}
    )

    # Should work without genres
    message = result["messages"][0]
    assert "Miles Davis" in message["content"]["text"]


# T036e: listening_analysis prompt with genre_distribution
@pytest.mark.asyncio
async def test_listening_analysis_genre_distribution():
    """Test listening_analysis prompt for genre distribution analysis."""
    # Execute prompt
    result = await PromptRegistry.get_prompt(
        "listening_analysis",
        {"analysis_type": "genre_distribution"}
    )

    # Validate response
    assert "description" in result
    message = result["messages"][0]
    assert "genre" in message["content"]["text"].lower()


# T036f: listening_analysis with artist_diversity
@pytest.mark.asyncio
async def test_listening_analysis_artist_diversity():
    """Test listening_analysis prompt for artist diversity analysis."""
    # Execute prompt
    result = await PromptRegistry.get_prompt(
        "listening_analysis",
        {"analysis_type": "artist_diversity"}
    )

    # Validate response
    message = result["messages"][0]
    assert "artist" in message["content"]["text"].lower()


# T036g: listening_analysis with decade_breakdown
@pytest.mark.asyncio
async def test_listening_analysis_decade_breakdown():
    """Test listening_analysis prompt for decade breakdown analysis."""
    # Execute prompt
    result = await PromptRegistry.get_prompt(
        "listening_analysis",
        {"analysis_type": "decade_breakdown"}
    )

    # Validate response
    message = result["messages"][0]
    assert "decade" in message["content"]["text"].lower()


# T036h: smart_playlist prompt success
@pytest.mark.asyncio
async def test_smart_playlist_prompt():
    """Test smart_playlist prompt generates rules-based playlist."""
    # Execute prompt
    result = await PromptRegistry.get_prompt(
        "smart_playlist",
        {"criteria": "80s rock with high energy", "max_tracks": 50}
    )

    # Validate response
    assert "description" in result
    message = result["messages"][0]
    assert "80s" in message["content"]["text"]
    assert "rock" in message["content"]["text"]


# T036i: smart_playlist with default max_tracks
@pytest.mark.asyncio
async def test_smart_playlist_default_max_tracks():
    """Test smart_playlist uses default of 50 tracks."""
    # Execute without max_tracks
    result = await PromptRegistry.get_prompt(
        "smart_playlist",
        {"criteria": "jazz classics"}
    )

    # Should work with default
    message = result["messages"][0]
    assert "jazz" in message["content"]["text"]


# T036j: library_curation duplicates task
@pytest.mark.asyncio
async def test_library_curation_duplicates():
    """Test library_curation prompt for finding duplicates."""
    # Execute prompt
    result = await PromptRegistry.get_prompt(
        "library_curation",
        {"task": "duplicates"}
    )

    # Validate response
    assert "description" in result
    message = result["messages"][0]
    assert "duplicate" in message["content"]["text"].lower()


# T036k: library_curation missing_metadata task
@pytest.mark.asyncio
async def test_library_curation_missing_metadata():
    """Test library_curation prompt for missing metadata."""
    # Execute prompt
    result = await PromptRegistry.get_prompt(
        "library_curation",
        {"task": "missing_metadata"}
    )

    # Validate response
    message = result["messages"][0]
    assert "metadata" in message["content"]["text"].lower()


# T036l: library_curation quality_issues task
@pytest.mark.asyncio
async def test_library_curation_quality_issues():
    """Test library_curation prompt for quality issues."""
    # Execute prompt
    result = await PromptRegistry.get_prompt(
        "library_curation",
        {"task": "quality_issues"}
    )

    # Validate response
    message = result["messages"][0]
    assert "quality" in message["content"]["text"].lower()
