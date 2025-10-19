"""Shared fixtures for integration tests with live servers."""

import os
import pytest
from pathlib import Path
from dotenv import load_dotenv
from src.subsonic.client import SubsonicClient

# Load .env file from project root
env_path = Path(__file__).parent.parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)


# Monkey-patch SubsonicClient to make search_tracks async
# This allows tests to use `await subsonic_client.search_tracks()`
# without changing test code
_original_search_tracks = SubsonicClient.search_tracks


async def _async_search_tracks_wrapper(self, query="", limit=500, genre_filter=None):
    """Async wrapper for search_tracks to enable await in tests."""
    import asyncio
    return await asyncio.to_thread(
        _original_search_tracks,
        self,
        query=query,
        limit=limit,
        genre_filter=genre_filter,
    )


# Apply monkey-patch
SubsonicClient.search_tracks = _async_search_tracks_wrapper


@pytest.fixture(scope="session")
def subsonic_config():
    """Subsonic server configuration from environment variables."""
    return {
        "host": os.getenv("SUBSONIC_HOST"),
        "user": os.getenv("SUBSONIC_USER"),
        "password": os.getenv("SUBSONIC_PASSWORD"),
        "playlist_name": os.getenv("SUBSONIC_PLAYLIST_NAME", "TestPlaylist_DuplicateDetection"),
    }


@pytest.fixture(scope="session")
def azuracast_config():
    """AzuraCast server configuration from environment variables."""
    return {
        "host": os.getenv("AZURACAST_HOST"),
        "api_key": os.getenv("AZURACAST_API_KEY"),
        "station_id": os.getenv("AZURACAST_STATIONID"),  # Using AZURACAST_STATIONID not AZURACAST_STATIONID
    }


@pytest.fixture(scope="session")
def test_config():
    """General test configuration from environment variables."""
    return {
        "track_count": int(os.getenv("TEST_TRACK_COUNT", "10")),
        "log_level": os.getenv("LOG_LEVEL", "INFO"),
        "performance_track_count": 100,
    }


@pytest.fixture(scope="session")
def skip_if_no_subsonic(subsonic_config):
    """Skip test if Subsonic server not configured."""
    if not subsonic_config["host"]:
        pytest.skip("Subsonic server not configured (SUBSONIC_HOST not set)")


@pytest.fixture(scope="session")
def skip_if_no_azuracast(azuracast_config):
    """Skip test if AzuraCast server not configured."""
    if not azuracast_config["host"]:
        pytest.skip("AzuraCast server not configured (AZURACAST_HOST not set)")


@pytest.fixture(scope="session")
def skip_if_no_servers(skip_if_no_subsonic, skip_if_no_azuracast):
    """Skip test if either server not configured."""
    pass


@pytest.fixture
def uploaded_track_ids(scope="session"):
    """Track IDs uploaded during tests for cleanup."""
    return []


def pytest_configure(config):
    """Add custom markers for integration tests."""
    config.addinivalue_line(
        "markers",
        "integration: mark test as an integration test that requires live servers"
    )
    config.addinivalue_line(
        "markers",
        "slow: mark test as slow running (typically >5 seconds)"
    )
    config.addinivalue_line(
        "markers",
        "cleanup: mark test that performs cleanup operations"
    )
