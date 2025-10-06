"""MCP Resources Registry - 6 resources for library exploration.

This module implements the ResourceRegistry class that exposes 6 MCP resources
for exploring the Subsonic music library. All resource contracts match resources.json schema.
"""

from typing import Any
import mcp.types as types
import json
import sys
import os

# Add parent directory to path to import SubsonicClient
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from src.subsonic.client import SubsonicClient
from .cache import CacheManager


class ResourceRegistry:
    """Registry for all 6 MCP resources with caching.

    Provides 6 resources that match the resources.json contract schema:
        1. library://stats - Complete library statistics (5-min TTL)
        2. library://artists - Available artists (5-min TTL)
        3. library://albums - Available albums (5-min TTL)
        4. library://genres - Available genres (5-min TTL)
        5. library://playlists - User playlists (2-min TTL)
        6. library://recent - Recently added tracks (1-min TTL)
    """

    def __init__(self, subsonic_client: SubsonicClient, cache: CacheManager):
        """Initialize resource registry.

        Args:
            subsonic_client: Configured SubsonicClient instance
            cache: CacheManager for response caching
        """
        self.client = subsonic_client
        self.cache = cache
        self.resources = self._define_resources()

    def _define_resources(self) -> dict[str, types.Resource]:
        """Define all 6 resources per resources.json contract.

        Returns:
            Dictionary mapping resource URIs to Resource definitions
        """
        return {
            "library://stats": types.Resource(
                uri="library://stats",
                name="Library Statistics",
                description="Complete library statistics with cache info",
                mimeType="application/json",
            ),
            "library://artists": types.Resource(
                uri="library://artists",
                name="Available Artists",
                description="Complete artist catalog with metadata",
                mimeType="application/json",
            ),
            "library://albums": types.Resource(
                uri="library://albums",
                name="Available Albums",
                description="Album collection with metadata",
                mimeType="application/json",
            ),
            "library://genres": types.Resource(
                uri="library://genres",
                name="Available Genres",
                description="Genre taxonomy with track counts",
                mimeType="application/json",
            ),
            "library://playlists": types.Resource(
                uri="library://playlists",
                name="User Playlists",
                description="User-created playlists with track details",
                mimeType="application/json",
            ),
            "library://recent": types.Resource(
                uri="library://recent",
                name="Recently Added Tracks",
                description="Recently added or modified tracks (last 100)",
                mimeType="application/json",
            ),
        }

    def get_all(self) -> list[types.Resource]:
        """Get all resource definitions.

        Returns:
            List of all 6 Resource objects
        """
        return list(self.resources.values())

    @staticmethod
    async def read_resource(uri: str, client: SubsonicClient) -> dict[str, Any]:
        """Read a resource by URI (used in tests).

        Args:
            uri: Resource URI (e.g., "library://stats")
            client: SubsonicClient instance

        Returns:
            Resource read result with contents

        Raises:
            ValueError: If URI is invalid
        """
        # Create temporary registry for execution
        from .cache import CacheManager

        cache = CacheManager()
        registry = ResourceRegistry(client, cache)

        # Route to appropriate handler
        handlers = {
            "library://stats": (registry._read_library_stats, 300),
            "library://artists": (registry._read_artists, 300),
            "library://albums": (registry._read_albums, 300),
            "library://genres": (registry._read_genres, 300),
            "library://playlists": (registry._read_playlists, 120),
            "library://recent": (registry._read_recent_tracks, 60),
        }

        if uri not in handlers:
            raise ValueError(f"Unknown resource URI: {uri}")

        handler, ttl = handlers[uri]

        # Check cache first
        cache_key = f"resource:{uri}"
        cached = await cache.get(cache_key)
        if cached is not None:
            return {
                "uri": uri,
                "mimeType": "application/json",
                "contents": [cached],
            }

        # Execute handler
        contents = await handler()

        # Cache result
        await cache.set(cache_key, contents, ttl=ttl)

        return {
            "uri": uri,
            "mimeType": "application/json",
            "contents": [contents],
        }

    # Resource handler methods (private)

    async def _read_library_stats(self) -> dict[str, Any]:
        """Read library://stats resource."""
        stats = await self.client.analyze_library()

        # Add/update cache stats if not already present in stats
        if "cache_stats" not in stats:
            cache_stats = self.cache.get_cache_stats()
            stats["cache_stats"] = {
                "cached_items": cache_stats["cached_items"],
                "hit_rate": 0.0,  # Will be calculated over time
            }

        return stats

    async def _read_artists(self) -> dict[str, Any]:
        """Read library://artists resource."""
        artists = await self.client.get_artists()

        return {"total": len(artists), "artists": artists}

    async def _read_albums(self) -> dict[str, Any]:
        """Read library://albums resource."""
        # Call SubsonicClient get_albums method
        albums = await self.client.get_albums()

        return {"total": len(albums), "albums": albums}

    async def _read_genres(self) -> dict[str, Any]:
        """Read library://genres resource."""
        genres = await self.client.get_genres()

        return {"total": len(genres), "genres": genres}

    async def _read_playlists(self) -> dict[str, Any]:
        """Read library://playlists resource."""
        playlists = await self.client.get_playlists()

        return {"total": len(playlists), "playlists": playlists}

    async def _read_recent_tracks(self) -> dict[str, Any]:
        """Read library://recent resource (max 100 tracks)."""
        recent = await self.client.get_recent_tracks()

        # Limit to 100 tracks
        if len(recent) > 100:
            recent = recent[:100]

        return {"total": len(recent), "tracks": recent}
