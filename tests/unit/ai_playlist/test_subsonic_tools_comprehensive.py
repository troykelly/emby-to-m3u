"""
Comprehensive tests for src/ai_playlist/subsonic_tools.py

Tests cover:
- SubsonicTools initialization
- Tool definition retrieval
- All tool execution paths (submit_playlist, search_tracks, etc.)
- Retry logic with exponential backoff
- Error handling and recovery
- Data transformation and validation

Target: Achieve 60%+ coverage (currently 14.29%)
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import List, Dict, Any
import asyncio

from src.ai_playlist.subsonic_tools import SubsonicTools, MAX_RETRIES, RETRY_DELAYS
from src.subsonic.client import SubsonicClient


# Test fixtures
@pytest.fixture
def mock_subsonic_client():
    """Create mock SubsonicClient with async methods."""
    client = Mock(spec=SubsonicClient)

    # Mock async methods
    client.search_tracks_async = AsyncMock(return_value=[])
    client.get_genres_async = AsyncMock(return_value=[])
    client.get_newest_albums_async = AsyncMock(return_value=[])
    client.get_album_tracks_async = AsyncMock(return_value=[])
    client.get_artists_async = AsyncMock(return_value=[])

    return client


@pytest.fixture
def subsonic_tools(mock_subsonic_client):
    """Create SubsonicTools instance with mocked client."""
    return SubsonicTools(mock_subsonic_client)


@pytest.fixture
def sample_track():
    """Create sample track object."""
    track = Mock()
    track.id = "track-001"
    track.title = "Sample Song"
    track.artist = "Test Artist"
    track.album = "Test Album"
    track.genre = "Rock"
    track.year = 2024
    track.duration = 180
    track.bpm = 120
    return track


@pytest.fixture
def sample_album():
    """Create sample album object."""
    album = Mock()
    album.id = "album-001"
    album.name = "Test Album"
    album.artist = "Test Artist"
    return album


# Test: Initialization
class TestSubsonicToolsInitialization:
    """Test SubsonicTools initialization."""

    def test_init_stores_client(self, mock_subsonic_client):
        """Test that initialization stores the client."""
        tools = SubsonicTools(mock_subsonic_client)
        assert tools.client is mock_subsonic_client

    def test_init_with_real_client_type(self):
        """Test initialization accepts SubsonicClient type."""
        client = Mock(spec=SubsonicClient)
        tools = SubsonicTools(client)
        assert tools.client is client


# Test: Tool Definitions
class TestGetToolDefinitions:
    """Test get_tool_definitions() method."""

    def test_returns_list_of_tools(self, subsonic_tools):
        """Test that get_tool_definitions returns a list."""
        definitions = subsonic_tools.get_tool_definitions()
        assert isinstance(definitions, list)
        assert len(definitions) > 0

    def test_all_tools_have_required_fields(self, subsonic_tools):
        """Test that all tool definitions have required OpenAI fields."""
        definitions = subsonic_tools.get_tool_definitions()

        for tool in definitions:
            assert "type" in tool
            assert tool["type"] == "function"
            assert "function" in tool

            func = tool["function"]
            assert "name" in func
            assert "description" in func
            assert "parameters" in func

    def test_submit_playlist_tool_exists(self, subsonic_tools):
        """Test that submit_playlist tool is defined."""
        definitions = subsonic_tools.get_tool_definitions()
        tool_names = [t["function"]["name"] for t in definitions]
        assert "submit_playlist" in tool_names

    def test_search_tracks_tool_exists(self, subsonic_tools):
        """Test that search_tracks tool is defined."""
        definitions = subsonic_tools.get_tool_definitions()
        tool_names = [t["function"]["name"] for t in definitions]
        assert "search_tracks" in tool_names

    def test_all_expected_tools_present(self, subsonic_tools):
        """Test that all expected tools are present."""
        definitions = subsonic_tools.get_tool_definitions()
        tool_names = [t["function"]["name"] for t in definitions]

        expected_tools = [
            "submit_playlist",
            "search_tracks",
            "search_tracks_by_genre",
            "get_available_genres",
            "get_newly_added_tracks",
            "browse_artists",
            "get_artist_tracks"
        ]

        for tool in expected_tools:
            assert tool in tool_names


# Test: submit_playlist tool
class TestSubmitPlaylistTool:
    """Test submit_playlist tool execution."""

    @pytest.mark.asyncio
    async def test_submit_playlist_with_valid_tracks(self, subsonic_tools):
        """Test submitting playlist with valid track IDs."""
        arguments = {
            "selected_track_ids": ["track-1", "track-2", "track-3"],
            "reasoning": "Selected upbeat rock tracks for morning workout"
        }

        result = await subsonic_tools.execute_tool("submit_playlist", arguments)

        assert result["status"] == "playlist_submitted"
        assert result["selected_track_ids"] == ["track-1", "track-2", "track-3"]
        assert "morning workout" in result["reasoning"]
        assert "3 tracks" in result["message"]

    @pytest.mark.asyncio
    async def test_submit_playlist_rejects_empty_array(self, subsonic_tools):
        """Test that empty track array is rejected."""
        arguments = {
            "selected_track_ids": [],
            "reasoning": "Could not find suitable tracks"
        }

        result = await subsonic_tools.execute_tool("submit_playlist", arguments)

        assert "error" in result
        assert result["error"] == "validation_error"
        assert "cannot be empty" in result["message"]
        assert result["status"] == "rejected"

    @pytest.mark.asyncio
    async def test_submit_playlist_rejects_none_tracks(self, subsonic_tools):
        """Test that None track list is rejected."""
        arguments = {
            "selected_track_ids": None,
            "reasoning": "Attempted with None"
        }

        result = await subsonic_tools.execute_tool("submit_playlist", arguments)

        assert result["error"] == "validation_error"
        assert result["status"] == "rejected"

    @pytest.mark.asyncio
    async def test_submit_playlist_with_missing_reasoning(self, subsonic_tools):
        """Test submitting playlist without reasoning field."""
        arguments = {
            "selected_track_ids": ["track-1"]
        }

        result = await subsonic_tools.execute_tool("submit_playlist", arguments)

        assert result["status"] == "playlist_submitted"
        assert result["reasoning"] == ""  # Default empty string


# Test: search_tracks tool
class TestSearchTracksTool:
    """Test search_tracks tool execution."""

    @pytest.mark.asyncio
    async def test_search_tracks_with_results(self, subsonic_tools, mock_subsonic_client, sample_track):
        """Test searching tracks with results."""
        mock_subsonic_client.search_tracks_async.return_value = [sample_track]

        arguments = {"query": "rock music", "limit": 50}
        result = await subsonic_tools.execute_tool("search_tracks", arguments)

        assert result["count"] == 1
        assert len(result["tracks"]) == 1

        track = result["tracks"][0]
        assert track["id"] == "track-001"
        assert track["title"] == "Sample Song"
        assert track["artist"] == "Test Artist"
        assert track["genre"] == "Rock"
        assert track["bpm"] == 120

        mock_subsonic_client.search_tracks_async.assert_called_once_with(
            query="rock music",
            limit=50
        )

    @pytest.mark.asyncio
    async def test_search_tracks_empty_results(self, subsonic_tools, mock_subsonic_client):
        """Test searching tracks with no results."""
        mock_subsonic_client.search_tracks_async.return_value = []

        arguments = {"query": "nonexistent artist", "limit": 50}
        result = await subsonic_tools.execute_tool("search_tracks", arguments)

        assert result["count"] == 0
        assert result["tracks"] == []
        assert "suggestion" in result
        assert "No tracks found" in result["suggestion"]

    @pytest.mark.asyncio
    async def test_search_tracks_caps_limit_at_50(self, subsonic_tools, mock_subsonic_client):
        """Test that search_tracks caps limit at 50."""
        mock_subsonic_client.search_tracks_async.return_value = []

        arguments = {"query": "test", "limit": 100}
        await subsonic_tools.execute_tool("search_tracks", arguments)

        # Should cap at 50
        mock_subsonic_client.search_tracks_async.assert_called_once_with(
            query="test",
            limit=50
        )

    @pytest.mark.asyncio
    async def test_search_tracks_default_limit(self, subsonic_tools, mock_subsonic_client):
        """Test search_tracks with default limit."""
        mock_subsonic_client.search_tracks_async.return_value = []

        arguments = {"query": "test"}
        await subsonic_tools.execute_tool("search_tracks", arguments)

        mock_subsonic_client.search_tracks_async.assert_called_once_with(
            query="test",
            limit=50
        )

    @pytest.mark.asyncio
    async def test_search_tracks_track_without_bpm(self, subsonic_tools, mock_subsonic_client):
        """Test track serialization when BPM is missing."""
        track = Mock(spec=['id', 'title', 'artist', 'album', 'genre', 'year', 'duration'])
        track.id = "track-002"
        track.title = "No BPM Track"
        track.artist = "Artist"
        track.album = "Album"
        track.genre = "Pop"
        track.year = 2023
        track.duration = 200
        # No bpm attribute - using spec prevents auto-creation

        mock_subsonic_client.search_tracks_async.return_value = [track]

        arguments = {"query": "test"}
        result = await subsonic_tools.execute_tool("search_tracks", arguments)

        assert result["tracks"][0]["bpm"] is None


# Test: search_tracks_by_genre tool
class TestSearchTracksByGenreTool:
    """Test search_tracks_by_genre tool execution."""

    @pytest.mark.asyncio
    async def test_search_by_genre_with_results(self, subsonic_tools, mock_subsonic_client, sample_track):
        """Test searching by genre with results."""
        mock_subsonic_client.search_tracks_async.return_value = [sample_track]

        arguments = {"genres": ["Rock", "Alternative"], "limit": 50}
        result = await subsonic_tools.execute_tool("search_tracks_by_genre", arguments)

        assert result["count"] == 1
        assert len(result["tracks"]) == 1

        mock_subsonic_client.search_tracks_async.assert_called_once_with(
            query="",
            limit=50,
            genre_filter=["Rock", "Alternative"]
        )

    @pytest.mark.asyncio
    async def test_search_by_genre_empty_results(self, subsonic_tools, mock_subsonic_client):
        """Test searching by genre with no results."""
        mock_subsonic_client.search_tracks_async.return_value = []

        arguments = {"genres": ["Obscure Genre"]}
        result = await subsonic_tools.execute_tool("search_tracks_by_genre", arguments)

        assert result["count"] == 0
        assert "suggestion" in result
        assert "No tracks found for genres" in result["suggestion"]


# Test: get_available_genres tool
class TestGetAvailableGenresTool:
    """Test get_available_genres tool execution."""

    @pytest.mark.asyncio
    async def test_get_genres_returns_list(self, subsonic_tools, mock_subsonic_client):
        """Test getting available genres."""
        mock_subsonic_client.get_genres_async.return_value = [
            {"value": "Rock"},
            {"value": "Pop"},
            {"name": "Jazz"}  # Alternative format
        ]

        result = await subsonic_tools.execute_tool("get_available_genres", {})

        assert result["count"] == 3
        assert "Rock" in result["genres"]
        assert "Pop" in result["genres"]
        assert "Jazz" in result["genres"]

    @pytest.mark.asyncio
    async def test_get_genres_handles_string_format(self, subsonic_tools, mock_subsonic_client):
        """Test genre list with string format."""
        mock_subsonic_client.get_genres_async.return_value = ["Electronic", "Classical"]

        result = await subsonic_tools.execute_tool("get_available_genres", {})

        assert result["count"] == 2
        assert "Electronic" in result["genres"]
        assert "Classical" in result["genres"]

    @pytest.mark.asyncio
    async def test_get_genres_empty_library(self, subsonic_tools, mock_subsonic_client):
        """Test getting genres from empty library."""
        mock_subsonic_client.get_genres_async.return_value = []

        result = await subsonic_tools.execute_tool("get_available_genres", {})

        assert result["count"] == 0
        assert result["genres"] == []


# Test: get_newly_added_tracks tool
class TestGetNewlyAddedTracksTool:
    """Test get_newly_added_tracks tool execution."""

    @pytest.mark.asyncio
    async def test_get_newly_added_tracks(self, subsonic_tools, mock_subsonic_client, sample_album, sample_track):
        """Test getting newly added tracks."""
        mock_subsonic_client.get_newest_albums_async.return_value = [sample_album]
        mock_subsonic_client.get_album_tracks_async.return_value = [sample_track]

        arguments = {"limit": 50}
        result = await subsonic_tools.execute_tool("get_newly_added_tracks", arguments)

        assert result["count"] == 1
        assert len(result["tracks"]) == 1

        mock_subsonic_client.get_newest_albums_async.assert_called_once_with(size=20)
        mock_subsonic_client.get_album_tracks_async.assert_called_once_with("album-001")

    @pytest.mark.asyncio
    async def test_get_newly_added_tracks_with_genre_filter(self, subsonic_tools, mock_subsonic_client, sample_album):
        """Test getting newly added tracks filtered by genre."""
        rock_track = Mock()
        rock_track.id = "rock-001"
        rock_track.title = "Rock Song"
        rock_track.artist = "Rock Artist"
        rock_track.album = "Rock Album"
        rock_track.genre = "Rock"
        rock_track.year = 2024
        rock_track.duration = 180

        pop_track = Mock()
        pop_track.id = "pop-001"
        pop_track.title = "Pop Song"
        pop_track.artist = "Pop Artist"
        pop_track.album = "Pop Album"
        pop_track.genre = "Pop"
        pop_track.year = 2024
        pop_track.duration = 200

        mock_subsonic_client.get_newest_albums_async.return_value = [sample_album]
        mock_subsonic_client.get_album_tracks_async.return_value = [rock_track, pop_track]

        arguments = {"limit": 50, "genre": "Rock"}
        result = await subsonic_tools.execute_tool("get_newly_added_tracks", arguments)

        # Should only return rock tracks
        assert result["count"] == 1
        assert result["tracks"][0]["genre"] == "Rock"

    @pytest.mark.asyncio
    async def test_get_newly_added_tracks_respects_limit(self, subsonic_tools, mock_subsonic_client, sample_album):
        """Test that newly added tracks respects limit."""
        # Create 100 tracks
        tracks = []
        for i in range(100):
            track = Mock()
            track.id = f"track-{i:03d}"
            track.title = f"Track {i}"
            track.artist = "Artist"
            track.album = "Album"
            track.genre = "Rock"
            track.year = 2024
            track.duration = 180
            tracks.append(track)

        mock_subsonic_client.get_newest_albums_async.return_value = [sample_album]
        mock_subsonic_client.get_album_tracks_async.return_value = tracks

        arguments = {"limit": 25}
        result = await subsonic_tools.execute_tool("get_newly_added_tracks", arguments)

        assert result["count"] == 25


# Test: browse_artists tool
class TestBrowseArtistsTool:
    """Test browse_artists tool execution."""

    @pytest.mark.asyncio
    async def test_browse_artists(self, subsonic_tools, mock_subsonic_client):
        """Test browsing artists."""
        mock_subsonic_client.get_artists_async.return_value = [
            {"id": "artist-1", "name": "Artist One", "albumCount": 5},
            {"id": "artist-2", "name": "Artist Two", "albumCount": 3}
        ]

        result = await subsonic_tools.execute_tool("browse_artists", {})

        assert result["count"] == 2
        assert len(result["artists"]) == 2
        assert result["artists"][0]["name"] == "Artist One"
        assert result["artists"][0]["album_count"] == 5

    @pytest.mark.asyncio
    async def test_browse_artists_with_limit(self, subsonic_tools, mock_subsonic_client):
        """Test browsing artists with limit."""
        artists = [{"id": f"artist-{i}", "name": f"Artist {i}", "albumCount": i} for i in range(200)]
        mock_subsonic_client.get_artists_async.return_value = artists

        arguments = {"limit": 50}
        result = await subsonic_tools.execute_tool("browse_artists", arguments)

        assert result["count"] == 50

    @pytest.mark.asyncio
    async def test_browse_artists_with_genre_filter_warning(self, subsonic_tools, mock_subsonic_client):
        """Test that genre filter logs warning (not yet implemented)."""
        mock_subsonic_client.get_artists_async.return_value = [
            {"id": "artist-1", "name": "Artist", "albumCount": 1}
        ]

        with patch('src.ai_playlist.subsonic_tools.logger') as mock_logger:
            arguments = {"genre": "Rock"}
            await subsonic_tools.execute_tool("browse_artists", arguments)

            # Should log warning about genre filtering not implemented
            mock_logger.warning.assert_called()


# Test: get_artist_tracks tool
class TestGetArtistTracksTool:
    """Test get_artist_tracks tool execution."""

    @pytest.mark.asyncio
    async def test_get_artist_tracks(self, subsonic_tools, mock_subsonic_client):
        """Test getting tracks by artist."""
        track1 = Mock()
        track1.id = "track-1"
        track1.title = "Song 1"
        track1.artist = "The Beatles"
        track1.album = "Abbey Road"
        track1.genre = "Rock"
        track1.year = 1969
        track1.duration = 180

        track2 = Mock()
        track2.id = "track-2"
        track2.title = "Song 2"
        track2.artist = "The Rolling Stones"  # Different artist
        track2.album = "Sticky Fingers"
        track2.genre = "Rock"
        track2.year = 1971
        track2.duration = 200

        mock_subsonic_client.search_tracks_async.return_value = [track1, track2]

        arguments = {"artist_name": "Beatles", "limit": 100}
        result = await subsonic_tools.execute_tool("get_artist_tracks", arguments)

        # Should filter to only Beatles tracks
        assert result["count"] == 1
        assert result["tracks"][0]["artist"] == "The Beatles"

        mock_subsonic_client.search_tracks_async.assert_called_once_with(
            query="Beatles",
            limit=100
        )


# Test: Retry Logic
class TestExecuteWithRetry:
    """Test _execute_with_retry method."""

    @pytest.mark.asyncio
    async def test_retry_succeeds_on_first_attempt(self, subsonic_tools):
        """Test successful operation on first attempt."""
        async def success_operation():
            return {"result": "success"}

        result = await subsonic_tools._execute_with_retry(success_operation, "test_tool")
        assert result == {"result": "success"}

    @pytest.mark.asyncio
    async def test_retry_succeeds_after_transient_error(self, subsonic_tools):
        """Test retry succeeds after transient network error."""
        call_count = 0

        async def flaky_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Network timeout")
            return {"result": "success"}

        with patch('asyncio.sleep', new_callable=AsyncMock):
            result = await subsonic_tools._execute_with_retry(flaky_operation, "test_tool")

        assert result == {"result": "success"}
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_retry_exhausts_all_attempts(self, subsonic_tools):
        """Test retry logic exhausts all attempts on persistent error."""
        async def failing_operation():
            raise ConnectionError("Persistent network error")

        with patch('asyncio.sleep', new_callable=AsyncMock):
            with pytest.raises(ConnectionError):
                await subsonic_tools._execute_with_retry(failing_operation, "test_tool", max_retries=3)

    @pytest.mark.asyncio
    async def test_retry_non_transient_error_fails_immediately(self, subsonic_tools):
        """Test non-transient errors fail immediately without retry."""
        call_count = 0

        async def non_transient_error():
            nonlocal call_count
            call_count += 1
            raise ValueError("Bad argument")

        with pytest.raises(ValueError):
            await subsonic_tools._execute_with_retry(non_transient_error, "test_tool")

        # Should not retry
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_uses_exponential_backoff(self, subsonic_tools):
        """Test retry uses correct delay intervals."""
        async def failing_operation():
            raise TimeoutError("Timeout")

        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(TimeoutError):
                await subsonic_tools._execute_with_retry(failing_operation, "test_tool", max_retries=3)

            # Check sleep was called with correct delays
            assert mock_sleep.call_count == 2  # 3 attempts = 2 sleeps
            mock_sleep.assert_any_call(RETRY_DELAYS[0])
            mock_sleep.assert_any_call(RETRY_DELAYS[1])


# Test: Error Response Creation
class TestCreateErrorResponse:
    """Test _create_error_response method."""

    def test_create_error_response_structure(self, subsonic_tools):
        """Test error response has correct structure."""
        error = subsonic_tools._create_error_response(
            error_type="network_error",
            message="Connection failed",
            suggestion="Try again later",
            tool_name="search_tracks"
        )

        assert error["error"] == "network_error"
        assert error["message"] == "Connection failed"
        assert error["suggestion"] == "Try again later"
        assert error["tool_name"] == "search_tracks"
        assert error["tracks"] == []
        assert error["count"] == 0

    def test_create_different_error_types(self, subsonic_tools):
        """Test creating different error types."""
        errors = [
            ("validation_error", "Invalid input"),
            ("not_found", "Resource not found"),
            ("timeout", "Operation timeout")
        ]

        for error_type, message in errors:
            error = subsonic_tools._create_error_response(
                error_type=error_type,
                message=message,
                suggestion="Fix the issue",
                tool_name="test_tool"
            )
            assert error["error"] == error_type
            assert error["message"] == message


# Test: Error Handling in execute_tool
class TestExecuteToolErrorHandling:
    """Test error handling in execute_tool wrapper."""

    @pytest.mark.asyncio
    async def test_execute_tool_handles_connection_error(self, subsonic_tools, mock_subsonic_client):
        """Test execute_tool handles ConnectionError gracefully."""
        mock_subsonic_client.search_tracks_async.side_effect = ConnectionError("Network down")

        with patch('asyncio.sleep', new_callable=AsyncMock):
            result = await subsonic_tools.execute_tool("search_tracks", {"query": "test"})

        assert "error" in result
        assert result["error"] == "network_error"
        assert "Network connection failed" in result["message"]

    @pytest.mark.asyncio
    async def test_execute_tool_handles_unknown_tool(self, subsonic_tools):
        """Test execute_tool handles unknown tool name."""
        result = await subsonic_tools.execute_tool("unknown_tool", {})

        assert "error" in result
        assert result["error"] == "execution_error"

    @pytest.mark.asyncio
    async def test_execute_tool_handles_generic_exception(self, subsonic_tools, mock_subsonic_client):
        """Test execute_tool handles generic exceptions."""
        mock_subsonic_client.search_tracks_async.side_effect = RuntimeError("Unexpected error")

        with patch('asyncio.sleep', new_callable=AsyncMock):
            result = await subsonic_tools.execute_tool("search_tracks", {"query": "test"})

        assert "error" in result
        assert result["error"] == "execution_error"


# Test: Integration scenarios
class TestIntegrationScenarios:
    """Test realistic integration scenarios."""

    @pytest.mark.asyncio
    async def test_full_playlist_creation_workflow(self, subsonic_tools, mock_subsonic_client, sample_track):
        """Test complete workflow: search -> select -> submit."""
        # Step 1: Search for tracks
        mock_subsonic_client.search_tracks_async.return_value = [sample_track]
        search_result = await subsonic_tools.execute_tool("search_tracks", {"query": "rock"})
        assert search_result["count"] == 1

        # Step 2: Submit playlist
        track_id = search_result["tracks"][0]["id"]
        submit_result = await subsonic_tools.execute_tool(
            "submit_playlist",
            {"selected_track_ids": [track_id], "reasoning": "Great rock track"}
        )
        assert submit_result["status"] == "playlist_submitted"

    @pytest.mark.asyncio
    async def test_genre_discovery_workflow(self, subsonic_tools, mock_subsonic_client, sample_track):
        """Test workflow: get genres -> search by genre."""
        # Step 1: Get available genres
        mock_subsonic_client.get_genres_async.return_value = [{"value": "Rock"}, {"value": "Jazz"}]
        genres_result = await subsonic_tools.execute_tool("get_available_genres", {})
        assert "Rock" in genres_result["genres"]

        # Step 2: Search by genre
        mock_subsonic_client.search_tracks_async.return_value = [sample_track]
        search_result = await subsonic_tools.execute_tool(
            "search_tracks_by_genre",
            {"genres": ["Rock"]}
        )
        assert search_result["count"] == 1
