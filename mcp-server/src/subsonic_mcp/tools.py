"""MCP Tools Registry - 10 tools for music library operations.

This module implements the ToolRegistry class that exposes 10 MCP tools for
interacting with Subsonic music libraries. All tool contracts match tools.json schema.
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
from .utils import safe_tool_execution


class ToolRegistry:
    """Registry for all 10 MCP tools with caching and error handling.

    Provides 10 tools that match the tools.json contract schema:
        1. search_tracks - Search for tracks by query
        2. get_track_info - Get detailed track information
        3. get_artists - List all artists
        4. get_artist_albums - Get albums for an artist
        5. get_album_tracks - Get tracks for an album
        6. search_similar - Find similar tracks
        7. get_genres - List all genres
        8. get_tracks_by_genre - Get tracks filtered by genre
        9. analyze_library - Get library statistics
        10. stream_track - Generate streaming URL
    """

    def __init__(self, subsonic_client: SubsonicClient, cache: CacheManager):
        """Initialize tool registry.

        Args:
            subsonic_client: Configured SubsonicClient instance
            cache: CacheManager for response caching
        """
        self.client = subsonic_client
        self.cache = cache
        self.tools = self._define_tools()

    def _define_tools(self) -> dict[str, types.Tool]:
        """Define all 10 tools per tools.json contract.

        Returns:
            Dictionary mapping tool names to Tool definitions
        """
        return {
            "search_tracks": types.Tool(
                name="search_tracks",
                description="Search for music tracks by title, artist, or album (max 100 results)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query string",
                            "minLength": 1,
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results (1-100)",
                            "minimum": 1,
                            "maximum": 100,
                            "default": 20,
                        },
                    },
                    "required": ["query"],
                },
            ),
            "get_track_info": types.Tool(
                name="get_track_info",
                description="Get detailed information about a specific track",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "track_id": {
                            "type": "string",
                            "description": "Unique track identifier",
                            "minLength": 1,
                        }
                    },
                    "required": ["track_id"],
                },
            ),
            "get_artists": types.Tool(
                name="get_artists",
                description="List all artists in the library",
                inputSchema={"type": "object", "properties": {}},
            ),
            "get_artist_albums": types.Tool(
                name="get_artist_albums",
                description="Get albums for a specific artist",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "artist_id": {
                            "type": "string",
                            "description": "Artist identifier",
                            "minLength": 1,
                        }
                    },
                    "required": ["artist_id"],
                },
            ),
            "get_album_tracks": types.Tool(
                name="get_album_tracks",
                description="Get tracks for a specific album",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "album_id": {
                            "type": "string",
                            "description": "Album identifier",
                            "minLength": 1,
                        }
                    },
                    "required": ["album_id"],
                },
            ),
            "search_similar": types.Tool(
                name="search_similar",
                description="Find tracks similar to given query by artist/genre (max 100 results)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Artist name or genre to find similar tracks",
                            "minLength": 1,
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results (1-100)",
                            "minimum": 1,
                            "maximum": 100,
                            "default": 20,
                        },
                    },
                    "required": ["query"],
                },
            ),
            "get_genres": types.Tool(
                name="get_genres",
                description="List all genres with track counts",
                inputSchema={"type": "object", "properties": {}},
            ),
            "get_tracks_by_genre": types.Tool(
                name="get_tracks_by_genre",
                description="Get tracks filtered by genre (max 100 results)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "genre": {
                            "type": "string",
                            "description": "Genre name",
                            "minLength": 1,
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results (1-100)",
                            "minimum": 1,
                            "maximum": 100,
                            "default": 20,
                        },
                    },
                    "required": ["genre"],
                },
            ),
            "analyze_library": types.Tool(
                name="analyze_library",
                description="Return library-wide statistics and analysis",
                inputSchema={"type": "object", "properties": {}},
            ),
            "stream_track": types.Tool(
                name="stream_track",
                description="Generate streaming URL for track playback",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "track_id": {
                            "type": "string",
                            "description": "Track identifier",
                            "minLength": 1,
                        }
                    },
                    "required": ["track_id"],
                },
            ),
        }

    def get_all(self) -> list[types.Tool]:
        """Get all tool definitions.

        Returns:
            List of all 10 Tool objects
        """
        return list(self.tools.values())

    @staticmethod
    async def execute(
        tool_name: str, arguments: dict[str, Any], client: SubsonicClient
    ) -> dict[str, Any]:
        """Execute a tool by name (used in tests).

        Args:
            tool_name: Name of tool to execute
            arguments: Tool arguments
            client: SubsonicClient instance

        Returns:
            Tool execution result

        Raises:
            ValueError: If tool_name is invalid
        """
        # Create temporary registry for execution
        from .cache import CacheManager

        cache = CacheManager()
        registry = ToolRegistry(client, cache)

        # Route to appropriate handler
        handlers = {
            "search_tracks": registry._search_tracks,
            "get_track_info": registry._get_track_info,
            "get_artists": registry._get_artists,
            "get_artist_albums": registry._get_artist_albums,
            "get_album_tracks": registry._get_album_tracks,
            "search_similar": registry._search_similar,
            "get_genres": registry._get_genres,
            "get_tracks_by_genre": registry._get_tracks_by_genre,
            "analyze_library": registry._analyze_library,
            "stream_track": registry._stream_track,
        }

        if tool_name not in handlers:
            raise ValueError(f"Unknown tool: {tool_name}")

        return await handlers[tool_name](arguments)

    # Tool handler methods (private)

    async def _search_tracks(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Search for tracks by query."""
        query = arguments["query"]
        limit = arguments.get("limit", 20)

        # Call SubsonicClient search
        tracks = await self.client.search(query, limit)

        # Enforce 100 result limit
        total = len(tracks)
        if total > 100:
            tracks = tracks[:100]
            pagination_note = f"Showing first 100 results out of {total}. Please refine your search for more specific results."
            return {"total": total, "tracks": tracks, "pagination_note": pagination_note}

        return {"total": total, "tracks": tracks}

    async def _get_track_info(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Get detailed track information."""
        track_id = arguments["track_id"]

        # Call SubsonicClient
        track = await self.client.get_track(track_id)

        return track

    async def _get_artists(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """List all artists."""
        # Call SubsonicClient
        artists = await self.client.get_artists()

        return {"total": len(artists), "artists": artists}

    async def _get_artist_albums(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Get albums for an artist."""
        artist_id = arguments["artist_id"]

        # Call SubsonicClient
        result = await self.client.get_artist_albums(artist_id)

        return result

    async def _get_album_tracks(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Get tracks for an album."""
        album_id = arguments["album_id"]

        # Call SubsonicClient
        result = await self.client.get_album_tracks(album_id)

        return result

    async def _search_similar(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Find similar tracks by artist/genre."""
        query = arguments["query"]
        limit = arguments.get("limit", 20)

        # Call SubsonicClient
        similar_tracks = await self.client.search_similar(query, limit)

        # Enforce 100 result limit
        total = len(similar_tracks)
        if total > 100:
            similar_tracks = similar_tracks[:100]
            pagination_note = f"Showing first 100 similar tracks out of {total}."
            return {
                "query": query,
                "similar_tracks": similar_tracks,
                "pagination_note": pagination_note,
            }

        return {"query": query, "similar_tracks": similar_tracks}

    async def _get_genres(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """List all genres."""
        # Call SubsonicClient
        genres = await self.client.get_genres()

        return {"total": len(genres), "genres": genres}

    async def _get_tracks_by_genre(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Get tracks filtered by genre."""
        genre = arguments["genre"]
        limit = arguments.get("limit", 20)

        # Call SubsonicClient
        tracks = await self.client.get_tracks_by_genre(genre, limit)

        # Enforce 100 result limit
        total = len(tracks)
        if total > 100:
            tracks = tracks[:100]
            pagination_note = f"Showing first 100 {genre} tracks out of {total}."
            return {"genre": genre, "tracks": tracks, "pagination_note": pagination_note}

        return {"genre": genre, "tracks": tracks}

    async def _analyze_library(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Get library statistics."""
        # Call SubsonicClient
        stats = await self.client.analyze_library()

        # Add/update cache stats if not already present
        if "cache_stats" not in stats:
            cache_stats = self.cache.get_cache_stats()
            stats["cache_stats"] = {
                "cached_items": cache_stats["cached_items"],
                "hit_rate": 0.0,  # Will be calculated over time
            }

        return stats

    async def _stream_track(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Generate streaming URL."""
        track_id = arguments["track_id"]

        # Call SubsonicClient
        result = await self.client.get_stream_url(track_id)

        return result
