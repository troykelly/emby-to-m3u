"""
Subsonic MCP Tool Definitions for OpenAI Function Calling

Provides tool definitions that allow the LLM to dynamically query the Subsonic
music library to discover tracks, browse by genre, search for artists, and more.
"""

import logging
from typing import Any, Dict, List, Optional
from src.subsonic.client import SubsonicClient

logger = logging.getLogger(__name__)

# T111: Error recovery constants
MAX_RETRIES = 3
RETRY_DELAYS = [0.5, 1.0, 2.0]  # Exponential backoff


class SubsonicTools:
    """Wrapper providing OpenAI function calling interface to Subsonic."""

    def __init__(self, subsonic_client: SubsonicClient):
        """Initialize with Subsonic client.

        Args:
            subsonic_client: Configured SubsonicClient instance
        """
        self.client = subsonic_client

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Get OpenAI function calling tool definitions.

        Returns:
            List of tool definitions for OpenAI API
        """
        return [
            # T113: Add submit_playlist tool for final structured output
            # NOTE: strict mode disabled - GPT-5 returns empty response when forced via tool_choice
            {
                "type": "function",
                "function": {
                    "name": "submit_playlist",
                    "description": "Submit your final playlist selection. CALL THIS TOOL when you have finished exploring the music library and are ready to provide your track selections. This is the ONLY way to complete the playlist generation.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "selected_track_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of track IDs selected for the playlist, in playback order"
                            },
                            "reasoning": {
                                "type": "string",
                                "description": "Brief explanation of your selection strategy and any constraint trade-offs made"
                            }
                        },
                        "required": ["selected_track_ids", "reasoning"],
                        "additionalProperties": False
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_tracks",
                    "description": "Search for tracks in the music library by query string. Use this to find specific songs, artists, or albums. Returns track details including ID, title, artist, album, genre, BPM, year, and duration.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query (artist name, song title, album, etc.). Leave empty for random tracks."
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of tracks to return (default: 50, max: 50)",
                                "default": 50
                            }
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_tracks_by_genre",
                    "description": "Search for tracks filtered by specific genres. Use this when you need tracks from particular music genres.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "genres": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of genre names to filter by (e.g., ['Rock', 'Pop', 'Electronic'])"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of tracks to return (default: 50)",
                                "default": 50
                            }
                        },
                        "required": ["genres"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_available_genres",
                    "description": "Get list of all genres available in the music library. Use this to discover what genres are available before searching.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_newly_added_tracks",
                    "description": "Get recently added tracks to the library. Use this to discover new music that may not be in your training data.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of tracks to return (default: 50)",
                                "default": 50
                            },
                            "genre": {
                                "type": "string",
                                "description": "Optional genre filter for newly added tracks"
                            }
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "browse_artists",
                    "description": "Browse artists in the library. Use this to discover available artists alphabetically or by genre.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "genre": {
                                "type": "string",
                                "description": "Optional genre to filter artists by"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of artists to return (default: 100)",
                                "default": 100
                            }
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_artist_tracks",
                    "description": "Get all tracks by a specific artist. Use this after browsing artists to get their songs.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "artist_name": {
                                "type": "string",
                                "description": "Name of the artist"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of tracks to return (default: 100)",
                                "default": 100
                            }
                        },
                        "required": ["artist_name"]
                    }
                }
            }
        ]

    async def _execute_with_retry(
        self,
        operation,
        tool_name: str,
        max_retries: int = MAX_RETRIES
    ) -> Any:
        """
        T111: Execute operation with retry logic for transient failures.

        Args:
            operation: Async function to execute
            tool_name: Tool name for logging
            max_retries: Maximum retry attempts

        Returns:
            Operation result

        Raises:
            Last exception if all retries fail
        """
        import asyncio

        last_exception = None

        for attempt in range(max_retries):
            try:
                return await operation()

            except (ConnectionError, TimeoutError, OSError) as e:
                # Transient errors - retry
                last_exception = e
                if attempt < max_retries - 1:
                    delay = RETRY_DELAYS[attempt] if attempt < len(RETRY_DELAYS) else 2.0
                    logger.warning(
                        f"Tool {tool_name} failed (attempt {attempt + 1}/{max_retries}): {e}. "
                        f"Retrying in {delay}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"Tool {tool_name} failed after {max_retries} attempts: {e}"
                    )

            except Exception as e:
                # Non-transient errors - don't retry
                logger.error(f"Tool {tool_name} failed with non-retryable error: {e}")
                raise

        # All retries exhausted
        raise last_exception

    def _create_error_response(
        self,
        error_type: str,
        message: str,
        suggestion: str,
        tool_name: str
    ) -> Dict[str, Any]:
        """
        T111: Create structured error response for LLM.

        Args:
            error_type: Type of error (network, parse, not_found, etc.)
            message: Error message
            suggestion: Suggestion for LLM to try next
            tool_name: Tool that failed

        Returns:
            Structured error dict
        """
        return {
            "error": error_type,
            "message": message,
            "suggestion": suggestion,
            "tool_name": tool_name,
            "tracks": [],
            "count": 0
        }

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool call and return results.

        Args:
            tool_name: Name of the tool to execute
            arguments: Tool arguments

        Returns:
            Tool execution results (includes error structure if execution fails)

        Raises:
            ValueError: If tool name is unknown
        """
        logger.info(f"Executing Subsonic tool: {tool_name} with args: {arguments}")

        # T111: Wrap execution with error recovery
        try:
            return await self._execute_tool_impl(tool_name, arguments)
        except ConnectionError as e:
            return self._create_error_response(
                "network_error",
                f"Network connection failed: {e}",
                "Check network connectivity or try again later. Consider using cached results.",
                tool_name
            )
        except Exception as e:
            return self._create_error_response(
                "execution_error",
                str(e),
                "Try adjusting query parameters or using a different tool.",
                tool_name
            )

    async def _execute_tool_impl(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Internal implementation of tool execution with retries.

        Args:
            tool_name: Name of the tool to execute
            arguments: Tool arguments

        Returns:
            Tool execution results

        Raises:
            ValueError: If tool name is unknown
            Various exceptions on execution failures
        """

        # T113: Handle submit_playlist tool (final selection)
        if tool_name == "submit_playlist":
            # CRITICAL VALIDATION: Reject empty track arrays
            selected_track_ids = arguments.get("selected_track_ids", [])

            # Validate that the array is not empty
            if not selected_track_ids or len(selected_track_ids) == 0:
                # Count how many tracks were discovered in previous tool calls
                # (This would require passing discovered_track_ids, so we use a generic message)
                error_msg = (
                    "VALIDATION ERROR: selected_track_ids cannot be empty. "
                    "You have discovered tracks in your previous tool calls. "
                    "Please select at least some of them for the playlist. "
                    "Review the tracks you found and call submit_playlist again with actual track IDs."
                )
                logger.warning(f"LLM attempted to submit empty playlist - rejecting: {error_msg}")
                return {
                    "error": "validation_error",
                    "message": error_msg,
                    "suggestion": (
                        "Review the tracks you discovered in previous search_tracks_by_genre and "
                        "search_tracks calls. Select the best available tracks that match the "
                        "requirements and call submit_playlist again with their IDs."
                    ),
                    "status": "rejected"
                }

            # Validation passed - accept the submission
            logger.info(f"Playlist submission validated: {len(selected_track_ids)} tracks selected")
            return {
                "status": "playlist_submitted",
                "selected_track_ids": selected_track_ids,
                "reasoning": arguments.get("reasoning", ""),
                "message": f"Playlist submitted with {len(selected_track_ids)} tracks"
            }

        elif tool_name == "search_tracks":
            # T111: Use retry wrapper
            async def search_operation():
                # Cap limit at 50 to prevent GPT-5 latency issues with large contexts
                requested_limit = arguments.get("limit", 50)
                capped_limit = min(requested_limit, 50)
                return await self.client.search_tracks_async(
                    query=arguments.get("query", ""),
                    limit=capped_limit
                )

            tracks = await self._execute_with_retry(search_operation, tool_name)

            result = {
                "tracks": [
                    {
                        "id": t.id,
                        "title": t.title,
                        "artist": t.artist,
                        "album": t.album,
                        "genre": t.genre,
                        "year": t.year,
                        "duration_seconds": t.duration,
                        "bpm": getattr(t, 'bpm', None),
                    }
                    for t in tracks
                ],
                "count": len(tracks)
            }

            # T111: Add suggestion if no results found
            if result["count"] == 0:
                query = arguments.get("query", "")
                result["suggestion"] = (
                    f"No tracks found for '{query}'. Try: "
                    "1) Broader search terms, "
                    "2) get_available_genres() to discover genres, or "
                    "3) browse_artists() to explore by artist"
                )

            return result

        elif tool_name == "search_tracks_by_genre":
            # T111: Use retry wrapper
            async def genre_search_operation():
                return await self.client.search_tracks_async(
                    query="",
                    limit=arguments.get("limit", 50),
                    genre_filter=arguments.get("genres")
                )

            tracks = await self._execute_with_retry(genre_search_operation, tool_name)

            result = {
                "tracks": [
                    {
                        "id": t.id,
                        "title": t.title,
                        "artist": t.artist,
                        "album": t.album,
                        "genre": t.genre,
                        "year": t.year,
                        "duration_seconds": t.duration,
                        "bpm": getattr(t, 'bpm', None),
                    }
                    for t in tracks
                ],
                "count": len(tracks)
            }

            # T111: Add suggestion if no results found
            if result["count"] == 0:
                genres = arguments.get("genres", [])
                result["suggestion"] = (
                    f"No tracks found for genres {genres}. Try: "
                    "1) get_available_genres() to see all available genres, "
                    "2) search_tracks() with artist/album names, or "
                    "3) get_newly_added_tracks() for recent additions"
                )

            return result

        elif tool_name == "get_available_genres":
            genres = await self.client.get_genres_async()
            return {
                "genres": [g.get("value", g.get("name", "Unknown")) if isinstance(g, dict) else str(g) for g in genres],
                "count": len(genres)
            }

        elif tool_name == "get_newly_added_tracks":
            # Use get_newest_albums to find recently added content
            albums = await self.client.get_newest_albums_async(size=20)
            tracks = []
            for album in albums:
                album_tracks = await self.client.get_album_tracks_async(album.id)
                tracks.extend(album_tracks)
                if len(tracks) >= arguments.get("limit", 50):
                    break

            tracks = tracks[:arguments.get("limit", 50)]

            # Filter by genre if specified
            genre_filter = arguments.get("genre")
            if genre_filter:
                tracks = [t for t in tracks if t.genre and genre_filter.lower() in t.genre.lower()]

            return {
                "tracks": [
                    {
                        "id": t.id,
                        "title": t.title,
                        "artist": t.artist,
                        "album": t.album,
                        "genre": t.genre,
                        "year": t.year,
                        "duration_seconds": t.duration,
                        "bpm": getattr(t, 'bpm', None),
                    }
                    for t in tracks
                ],
                "count": len(tracks)
            }

        elif tool_name == "browse_artists":
            # Use getArtists to list all artists
            artists = await self.client.get_artists_async()

            # Filter by genre if specified
            genre_filter = arguments.get("genre")
            if genre_filter:
                # This would require fetching artist details, which is expensive
                # For now, just return all artists
                logger.warning(f"Genre filtering for artists not yet implemented")

            limit = arguments.get("limit", 100)
            artists = artists[:limit]

            return {
                "artists": [
                    {
                        "id": a.get("id") if isinstance(a, dict) else getattr(a, 'id', str(i)),
                        "name": a.get("name") if isinstance(a, dict) else getattr(a, 'name', f"Artist {i}"),
                        "album_count": a.get("albumCount", 0) if isinstance(a, dict) else getattr(a, 'albumCount', 0)
                    }
                    for i, a in enumerate(artists)
                ],
                "count": len(artists)
            }

        elif tool_name == "get_artist_tracks":
            artist_name = arguments["artist_name"]
            limit = arguments.get("limit", 100)

            # Search for the artist
            tracks = await self.client.search_tracks_async(
                query=artist_name,
                limit=limit
            )

            # Filter to tracks by this exact artist (case-insensitive)
            artist_tracks = [
                t for t in tracks
                if t.artist and artist_name.lower() in t.artist.lower()
            ]

            return {
                "tracks": [
                    {
                        "id": t.id,
                        "title": t.title,
                        "artist": t.artist,
                        "album": t.album,
                        "genre": t.genre,
                        "year": t.year,
                        "duration_seconds": t.duration,
                        "bpm": getattr(t, 'bpm', None),
                    }
                    for t in artist_tracks
                ],
                "count": len(artist_tracks)
            }

        else:
            raise ValueError(f"Unknown tool: {tool_name}")
