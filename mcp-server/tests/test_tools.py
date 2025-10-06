"""Contract tests for 10 MCP tools - ALL MUST FAIL BEFORE IMPLEMENTATION.

These tests validate tool contracts against tools.json schema.
All tests import from subsonic_mcp.tools which doesn't exist yet (TDD approach).
"""

import pytest
from subsonic_mcp.tools import ToolRegistry  # Will fail - not implemented yet
from tests.conftest import SubsonicNotFoundError


# T004: search_tracks success scenario
@pytest.mark.asyncio
async def test_search_tracks_success(mock_subsonic_client, sample_track):
    """Test search_tracks returns formatted track data."""
    # Mock client to return sample tracks
    mock_subsonic_client.search.return_value = [sample_track, sample_track]

    # Execute tool
    result = await ToolRegistry.execute(
        "search_tracks",
        {"query": "beatles", "limit": 10},
        mock_subsonic_client
    )

    # Validate response structure
    assert "total" in result
    assert "tracks" in result
    assert result["total"] == 2
    assert len(result["tracks"]) == 2
    assert result["tracks"][0]["id"] == "track-123"
    assert result["tracks"][0]["streaming_url"]


# T005: search_tracks with 100 result limit
@pytest.mark.asyncio
async def test_search_tracks_result_limit(mock_subsonic_client, sample_track):
    """Test search_tracks enforces 100 result limit with pagination note."""
    # Mock client to return 150 tracks
    mock_subsonic_client.search.return_value = [sample_track] * 150

    # Execute with limit=100
    result = await ToolRegistry.execute(
        "search_tracks",
        {"query": "test", "limit": 100},
        mock_subsonic_client
    )

    # Validate exactly 100 results
    assert len(result["tracks"]) == 100
    assert "pagination_note" in result
    assert "Showing first 100 results" in result["pagination_note"]


# T006: search_tracks no results
@pytest.mark.asyncio
async def test_search_tracks_no_results(mock_subsonic_client):
    """Test search_tracks handles empty results gracefully."""
    # Mock empty results
    mock_subsonic_client.search.return_value = []

    # Execute search
    result = await ToolRegistry.execute(
        "search_tracks",
        {"query": "nonexistent"},
        mock_subsonic_client
    )

    # Validate friendly message
    assert result["total"] == 0
    assert len(result["tracks"]) == 0


# T007: get_track_info success
@pytest.mark.asyncio
async def test_get_track_info_success(mock_subsonic_client, sample_track):
    """Test get_track_info returns complete track metadata."""
    # Mock track retrieval
    mock_subsonic_client.get_track.return_value = sample_track

    # Execute tool
    result = await ToolRegistry.execute(
        "get_track_info",
        {"track_id": "123"},
        mock_subsonic_client
    )

    # Validate all required fields
    assert result["id"] == "track-123"
    assert result["title"] == "Come Together"
    assert result["artist"] == "The Beatles"
    assert result["album"] == "Abbey Road"
    assert result["genre"] == "Rock"
    assert result["year"] == 1969
    assert result["duration"] == 259
    assert result["bitrate"] == 320
    assert result["streaming_url"]


# T008: get_track_info not found
@pytest.mark.asyncio
async def test_get_track_info_not_found(mock_subsonic_client):
    """Test get_track_info handles missing track gracefully."""
    # Mock not found error
    mock_subsonic_client.get_track.side_effect = SubsonicNotFoundError("Track not found")

    # Execute and expect error to be raised
    with pytest.raises(SubsonicNotFoundError):
        await ToolRegistry.execute(
            "get_track_info",
            {"track_id": "invalid"},
            mock_subsonic_client
        )


# T009: get_artists success
@pytest.mark.asyncio
async def test_get_artists_success(mock_subsonic_client, sample_artist):
    """Test get_artists returns artist list with counts."""
    # Mock artist list
    mock_subsonic_client.get_artists.return_value = [sample_artist] * 5

    # Execute tool
    result = await ToolRegistry.execute(
        "get_artists",
        {},
        mock_subsonic_client
    )

    # Validate Artist schema
    assert result["total"] == 5
    assert len(result["artists"]) == 5
    assert result["artists"][0]["id"] == "artist-456"
    assert result["artists"][0]["name"] == "The Beatles"
    assert result["artists"][0]["album_count"] == 13
    assert result["artists"][0]["track_count"] == 213


# T010: get_artists empty library
@pytest.mark.asyncio
async def test_get_artists_empty_library(mock_subsonic_client):
    """Test get_artists handles empty library gracefully."""
    # Mock empty library
    mock_subsonic_client.get_artists.return_value = []

    # Execute tool
    result = await ToolRegistry.execute(
        "get_artists",
        {},
        mock_subsonic_client
    )

    # Validate empty response
    assert result["total"] == 0
    assert len(result["artists"]) == 0


# T011: get_artist_albums success
@pytest.mark.asyncio
async def test_get_artist_albums_success(mock_subsonic_client, sample_album):
    """Test get_artist_albums returns album list for artist."""
    # Mock album list
    mock_subsonic_client.get_artist_albums.return_value = {
        "artist_id": "artist-456",
        "artist_name": "The Beatles",
        "albums": [sample_album] * 3
    }

    # Execute tool
    result = await ToolRegistry.execute(
        "get_artist_albums",
        {"artist_id": "artist-456"},
        mock_subsonic_client
    )

    # Validate response
    assert result["artist_id"] == "artist-456"
    assert result["artist_name"] == "The Beatles"
    assert len(result["albums"]) == 3
    assert result["albums"][0]["id"] == "album-789"
    assert result["albums"][0]["track_count"] == 17


# T012: get_artist_albums not found
@pytest.mark.asyncio
async def test_get_artist_albums_not_found(mock_subsonic_client):
    """Test get_artist_albums handles missing artist gracefully."""
    # Mock not found
    mock_subsonic_client.get_artist_albums.side_effect = SubsonicNotFoundError()

    # Execute and expect error to be raised
    with pytest.raises(SubsonicNotFoundError):
        await ToolRegistry.execute(
            "get_artist_albums",
            {"artist_id": "invalid"},
            mock_subsonic_client
        )


# T013: get_album_tracks success
@pytest.mark.asyncio
async def test_get_album_tracks_success(mock_subsonic_client, sample_track):
    """Test get_album_tracks returns track list for album."""
    # Mock track list
    mock_subsonic_client.get_album_tracks.return_value = {
        "album_id": "album-789",
        "album_name": "Abbey Road",
        "tracks": [sample_track] * 17
    }

    # Execute tool
    result = await ToolRegistry.execute(
        "get_album_tracks",
        {"album_id": "album-789"},
        mock_subsonic_client
    )

    # Validate response
    assert result["album_id"] == "album-789"
    assert result["album_name"] == "Abbey Road"
    assert len(result["tracks"]) == 17


# T014: get_album_tracks invalid album
@pytest.mark.asyncio
async def test_get_album_tracks_invalid_album(mock_subsonic_client):
    """Test get_album_tracks handles invalid album gracefully."""
    # Mock not found
    mock_subsonic_client.get_album_tracks.side_effect = SubsonicNotFoundError()

    # Execute and expect error to be raised
    with pytest.raises(SubsonicNotFoundError):
        await ToolRegistry.execute(
            "get_album_tracks",
            {"album_id": "invalid"},
            mock_subsonic_client
        )


# T015: search_similar success
@pytest.mark.asyncio
async def test_search_similar_success(mock_subsonic_client, sample_track):
    """Test search_similar returns related tracks."""
    # Mock similarity search
    similar_tracks = [
        {**sample_track, "id": f"track-{i}", "artist": "Pink Floyd"}
        for i in range(10)
    ]
    mock_subsonic_client.search_similar.return_value = similar_tracks

    # Execute tool
    result = await ToolRegistry.execute(
        "search_similar",
        {"query": "Pink Floyd", "limit": 20},
        mock_subsonic_client
    )

    # Validate response
    assert result["query"] == "Pink Floyd"
    assert len(result["similar_tracks"]) == 10
    assert result["similar_tracks"][0]["artist"] == "Pink Floyd"


# T016: search_similar with limit
@pytest.mark.asyncio
async def test_search_similar_limit(mock_subsonic_client, sample_track):
    """Test search_similar enforces 100 result limit."""
    # Mock 150 tracks
    similar_tracks = [
        {**sample_track, "id": f"track-{i}"}
        for i in range(150)
    ]
    mock_subsonic_client.search_similar.return_value = similar_tracks

    # Execute with limit=100
    result = await ToolRegistry.execute(
        "search_similar",
        {"query": "test", "limit": 100},
        mock_subsonic_client
    )

    # Validate exactly 100 results with pagination note
    assert len(result["similar_tracks"]) == 100
    assert "pagination_note" in result


# T017: get_genres success
@pytest.mark.asyncio
async def test_get_genres_success(mock_subsonic_client, sample_genre):
    """Test get_genres returns genre list with counts."""
    # Mock genre list
    genres = [
        sample_genre,
        {"name": "Jazz", "track_count": 450, "album_count": 32},
        {"name": "Classical", "track_count": 890, "album_count": 65}
    ]
    mock_subsonic_client.get_genres.return_value = genres

    # Execute tool
    result = await ToolRegistry.execute(
        "get_genres",
        {},
        mock_subsonic_client
    )

    # Validate Genre schema
    assert result["total"] == 3
    assert len(result["genres"]) == 3
    assert result["genres"][0]["name"] == "Rock"
    assert result["genres"][0]["track_count"] == 1250
    assert result["genres"][0]["album_count"] == 87


# T018: get_tracks_by_genre success
@pytest.mark.asyncio
async def test_get_tracks_by_genre_success(mock_subsonic_client, sample_track):
    """Test get_tracks_by_genre filters by genre."""
    # Mock genre-filtered tracks
    rock_tracks = [
        {**sample_track, "id": f"track-{i}", "genre": "Rock"}
        for i in range(25)
    ]
    mock_subsonic_client.get_tracks_by_genre.return_value = rock_tracks

    # Execute tool
    result = await ToolRegistry.execute(
        "get_tracks_by_genre",
        {"genre": "Rock", "limit": 30},
        mock_subsonic_client
    )

    # Validate response
    assert result["genre"] == "Rock"
    assert len(result["tracks"]) == 25
    assert all(t["genre"] == "Rock" for t in result["tracks"])


# T019: analyze_library success
@pytest.mark.asyncio
async def test_analyze_library_success(mock_subsonic_client, sample_library_stats):
    """Test analyze_library returns complete stats."""
    # Mock library analysis
    mock_subsonic_client.analyze_library.return_value = sample_library_stats

    # Execute tool
    result = await ToolRegistry.execute(
        "analyze_library",
        {},
        mock_subsonic_client
    )

    # Validate LibraryStats schema
    assert result["total_tracks"] == 5432
    assert result["total_artists"] == 234
    assert result["total_albums"] == 456
    assert result["total_genres"] == 45
    assert result["library_size_mb"] == 32768.5
    assert result["average_bitrate"] == 256.3
    assert result["cache_stats"]["cached_items"] == 15
    assert result["cache_stats"]["hit_rate"] == 0.85


# T020: stream_track success
@pytest.mark.asyncio
async def test_stream_track_success(mock_subsonic_client):
    """Test stream_track generates streaming URL."""
    # Mock streaming URL
    mock_subsonic_client.get_stream_url.return_value = {
        "track_id": "track-123",
        "streaming_url": "https://music.example.com/stream/track-123?token=abc123",
        "expires_in": 3600
    }

    # Execute tool
    result = await ToolRegistry.execute(
        "stream_track",
        {"track_id": "track-123"},
        mock_subsonic_client
    )

    # Validate response
    assert result["track_id"] == "track-123"
    assert "streaming_url" in result
    assert result["streaming_url"].startswith("https://")
    assert "expires_in" in result
