"""Error handling utilities for Subsonic MCP Server.

This module provides comprehensive error handling with user-friendly messages
for all Subsonic API errors, network failures, and unexpected exceptions.
"""

import logging
from typing import Any, Callable
import mcp.types as types
import httpx
import sys
import os

# Add parent directory to path to import SubsonicClient
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from src.subsonic.exceptions import (
    SubsonicAuthenticationError,
    SubsonicAuthorizationError,
    SubsonicNotFoundError,
    SubsonicParameterError,
    SubsonicError,
)

logger = logging.getLogger(__name__)


class MCPError(Exception):
    """Base exception for MCP server errors."""

    pass


async def safe_tool_execution(
    tool_name: str, handler: Callable, arguments: dict[str, Any]
) -> list[types.TextContent]:
    """Execute tool with comprehensive error handling.

    Wraps tool execution with error handling that provides user-friendly
    messages for all error scenarios.

    Args:
        tool_name: Name of the tool being executed
        handler: Async function to execute
        arguments: Tool arguments

    Returns:
        list[types.TextContent]: Tool result or error message
    """
    try:
        result = await handler(arguments)

        # Convert result to TextContent
        if isinstance(result, str):
            return [types.TextContent(type="text", text=result)]
        elif isinstance(result, dict):
            import json

            return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
        else:
            return [types.TextContent(type="text", text=str(result))]

    except SubsonicAuthenticationError as e:
        logger.error(f"Authentication failed in {tool_name}: {e}")
        return [
            types.TextContent(
                type="text",
                text="Authentication failed. Please verify SUBSONIC_USER and SUBSONIC_PASSWORD environment variables are correct.",
            )
        ]

    except SubsonicAuthorizationError as e:
        logger.error(f"Authorization failed in {tool_name}: {e}")
        return [
            types.TextContent(
                type="text",
                text="Authorization denied. Your account does not have permission to access this resource.",
            )
        ]

    except SubsonicNotFoundError as e:
        logger.error(f"Resource not found in {tool_name}: {e}")
        resource_type = _infer_resource_type(tool_name, arguments)
        resource_id = _get_resource_id(arguments)
        return [
            types.TextContent(
                type="text",
                text=f"Resource not found. {resource_type} with ID '{resource_id}' does not exist.",
            )
        ]

    except SubsonicParameterError as e:
        logger.error(f"Parameter error in {tool_name}: {e}")
        return [
            types.TextContent(
                type="text", text=f"Invalid parameters. Please check your input: {str(e)}"
            )
        ]

    except httpx.ConnectError as e:
        logger.error(f"Connection failed in {tool_name}: {e}")
        return [
            types.TextContent(
                type="text",
                text="Unable to connect to music server. Please check that your server is running and SUBSONIC_URL is correct.",
            )
        ]

    except httpx.TimeoutException as e:
        logger.error(f"Request timeout in {tool_name}: {e}")
        return [
            types.TextContent(
                type="text",
                text="Request timed out. The music server took too long to respond. Please try again.",
            )
        ]

    except SubsonicError as e:
        logger.error(f"Subsonic error in {tool_name}: {e}")
        return [
            types.TextContent(
                type="text", text=f"Music server error: {str(e)}"
            )
        ]

    except Exception as e:
        logger.exception(f"Unexpected error in {tool_name}")
        return [
            types.TextContent(
                type="text",
                text=f"An unexpected error occurred: {str(e)}. Please check the logs for details.",
            )
        ]


def _infer_resource_type(tool_name: str, arguments: dict[str, Any]) -> str:
    """Infer resource type from tool name and arguments.

    Args:
        tool_name: Name of the tool
        arguments: Tool arguments

    Returns:
        Human-friendly resource type (e.g., "Track", "Artist", "Album")
    """
    if "track" in tool_name.lower():
        return "Track"
    elif "artist" in tool_name.lower():
        return "Artist"
    elif "album" in tool_name.lower():
        return "Album"
    elif "genre" in tool_name.lower():
        return "Genre"
    elif "playlist" in tool_name.lower():
        return "Playlist"
    else:
        return "Resource"


def _get_resource_id(arguments: dict[str, Any]) -> str:
    """Extract resource ID from arguments.

    Args:
        arguments: Tool arguments

    Returns:
        Resource ID or "unknown" if not found
    """
    for key in ["track_id", "artist_id", "album_id", "playlist_id", "id"]:
        if key in arguments:
            return str(arguments[key])
    return "unknown"
