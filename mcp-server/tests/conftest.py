"""Test configuration and shared fixtures for Subsonic MCP Server tests.

This module provides pytest fixtures for mocking SubsonicClient and common test data.
All tests use mocked SubsonicClient to avoid dependency on real Subsonic servers.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_subsonic_client():
    """Create a mocked SubsonicClient for testing.

    Returns:
        MagicMock: Mocked SubsonicClient with async methods
    """
    client = MagicMock()

    # Mock all SubsonicClient methods as AsyncMock
    client.search = AsyncMock()
    client.get_track = AsyncMock()
    client.get_artists = AsyncMock()
    client.get_artist_albums = AsyncMock()
    client.get_album_tracks = AsyncMock()
    client.search_similar = AsyncMock()
    client.get_genres = AsyncMock()
    client.get_tracks_by_genre = AsyncMock()
    client.analyze_library = AsyncMock()
    client.get_stream_url = AsyncMock()
    client.get_playlists = AsyncMock()
    client.get_recent_tracks = AsyncMock()

    return client


@pytest.fixture
def sample_track():
    """Sample track data for testing.

    Returns:
        dict: Track with all required and optional fields
    """
    return {
        "id": "track-123",
        "title": "Come Together",
        "artist": "The Beatles",
        "album": "Abbey Road",
        "genre": "Rock",
        "year": 1969,
        "duration": 259,
        "bitrate": 320,
        "streaming_url": "https://music.example.com/stream/track-123"
    }


@pytest.fixture
def sample_artist():
    """Sample artist data for testing.

    Returns:
        dict: Artist with metadata
    """
    return {
        "id": "artist-456",
        "name": "The Beatles",
        "album_count": 13,
        "track_count": 213
    }


@pytest.fixture
def sample_album():
    """Sample album data for testing.

    Returns:
        dict: Album with metadata
    """
    return {
        "id": "album-789",
        "name": "Abbey Road",
        "artist": "The Beatles",
        "year": 1969,
        "track_count": 17
    }


@pytest.fixture
def sample_genre():
    """Sample genre data for testing.

    Returns:
        dict: Genre with counts
    """
    return {
        "name": "Rock",
        "track_count": 1250,
        "album_count": 87
    }


@pytest.fixture
def sample_playlist():
    """Sample playlist data for testing.

    Returns:
        dict: Playlist with tracks
    """
    return {
        "id": "playlist-001",
        "name": "Classic Rock Favorites",
        "description": "Best of 70s and 80s rock",
        "track_count": 25,
        "tracks": []
    }


@pytest.fixture
def sample_library_stats():
    """Sample library statistics for testing.

    Returns:
        dict: Complete library stats
    """
    return {
        "total_tracks": 5432,
        "total_artists": 234,
        "total_albums": 456,
        "total_genres": 45,
        "library_size_mb": 32768.5,
        "average_bitrate": 256.3,
        "cache_stats": {
            "cached_items": 15,
            "hit_rate": 0.85
        }
    }


class SubsonicNotFoundError(Exception):
    """Mock exception for testing not found scenarios."""
    pass


class SubsonicConnectionError(Exception):
    """Mock exception for testing connection failures."""
    pass
