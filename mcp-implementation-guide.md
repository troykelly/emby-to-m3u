# Model Context Protocol (MCP) Implementation Guide
## Adding MCP Functionality to an Existing Python Library

**Document Version:** 1.0  
**Last Updated:** October 5, 2025  
**Target Audience:** LLM Coding Agents

---

## Table of Contents

1. [Overview](#overview)
2. [Current Technology Versions](#current-technology-versions)
3. [Prerequisites](#prerequisites)
4. [Project Setup](#project-setup)
5. [MCP Architecture](#mcp-architecture)
6. [Core Implementation](#core-implementation)
7. [Tools Implementation](#tools-implementation)
8. [Resources Implementation](#resources-implementation)
9. [Prompts Implementation](#prompts-implementation)
10. [Advanced Features](#advanced-features)
11. [Error Handling](#error-handling)
12. [Testing](#testing)
13. [Deployment](#deployment)
14. [Client Configuration](#client-configuration)
15. [Best Practices](#best-practices)

---

## Overview

The Model Context Protocol (MCP) is an open standard that enables seamless integration between LLM applications and external data sources and tools. This guide provides a complete reference for adding MCP server capabilities to an existing Python library.

### What is MCP?

MCP provides a standardized way for applications to:
- **Expose data through Resources** - GET-like endpoints that load information into LLM context
- **Provide functionality through Tools** - POST-like endpoints that execute code or produce side effects
- **Define interaction patterns through Prompts** - Reusable templates for LLM interactions

### Protocol Details

- **Protocol:** JSON-RPC 2.0 over stdio, SSE, or HTTP
- **Architecture:** Client-Server with stateful sessions
- **Transport:** stdio (local), Server-Sent Events (SSE), Streamable HTTP
- **Specification:** https://spec.modelcontextprotocol.io/specification/2025-06-18

---

## Current Technology Versions

All version numbers in this document reflect the current stable releases as of October 2025:

| Technology | Version | Release Date | Notes |
|------------|---------|--------------|-------|
| Python | 3.13.7 | Aug 14, 2025 | Latest stable with JIT compiler, free-threading mode |
| MCP Python SDK | 1.5.0 | Oct 2, 2025 | Official Anthropic SDK |
| uv | 0.8.22 | Sep 23, 2025 | Python package manager (Rust-based) |

### Python 3.13.7 Features

- New interactive interpreter with multi-line editing and color support
- Experimental free-threaded build mode (no GIL)
- Just-In-Time (JIT) compiler for improved performance
- Colorized exception tracebacks
- Enhanced type parameter support with defaults

---

## Prerequisites

### System Requirements

- **Operating System:** Linux, macOS, or Windows
- **Python:** 3.13.7 (minimum 3.10 supported)
- **Package Manager:** uv 0.8.22 (recommended) or pip

### Required Knowledge

- Async Python programming (asyncio)
- JSON-RPC protocol understanding
- REST API concepts
- Your existing library's architecture and API

---

## Project Setup

### 1. Install uv Package Manager

```bash
# macOS and Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Verify installation
uv --version  # Should show 0.8.22
```

### 2. Create MCP Server Directory Structure

```bash
# Navigate to your library root
cd /path/to/your-library

# Create MCP server directory
mkdir -p mcp_server
cd mcp_server

# Initialize uv project
uv init mcp-server
cd mcp-server
```

### 3. Configure pyproject.toml

Create or update `pyproject.toml`:

```toml
[project]
name = "your-library-mcp-server"
version = "0.1.0"
description = "MCP server for YourLibrary - integrates with Subsonic/OpenSubsonic protocol"
readme = "README.md"
requires-python = ">=3.10"
dependencies = [
    "mcp>=1.5.0",
    "your-existing-library>=1.0.0",  # Your library dependency
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "black>=24.0.0",
    "ruff>=0.5.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.uv]
dev-dependencies = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
]
```

### 4. Install Dependencies

```bash
# Install all dependencies including dev dependencies
uv sync

# Or install specific package
uv add mcp
```

---

## MCP Architecture

### Communication Flow

```
┌─────────────────┐         JSON-RPC         ┌──────────────────┐
│   MCP Client    │◄─────────────────────────►│   MCP Server     │
│  (Claude, etc)  │         (stdio)           │  (Your Library)  │
└─────────────────┘                           └──────────────────┘
                                                       │
                                                       ▼
                                              ┌──────────────────┐
                                              │ Your Library API │
                                              │ (Subsonic, etc)  │
                                              └──────────────────┘
```

### Server Lifecycle

1. **Initialization** - Server starts, capabilities negotiated
2. **Ready** - Server ready to handle requests
3. **Request/Response** - Tools called, resources read, prompts retrieved
4. **Shutdown** - Clean termination

### Core Components

- **Server** - Main MCP server instance
- **Tools** - Executable functions exposed to clients
- **Resources** - Data endpoints for context loading
- **Prompts** - Template definitions for LLM interactions
- **Notifications** - Server-to-client event streaming

---

## Core Implementation

### Directory Structure

```
mcp-server/
├── pyproject.toml
├── README.md
├── src/
│   └── mcp_server/
│       ├── __init__.py
│       ├── server.py           # Main server implementation
│       ├── tools.py            # Tool definitions
│       ├── resources.py        # Resource definitions
│       ├── prompts.py          # Prompt definitions
│       ├── handlers.py         # Request handlers
│       └── utils.py            # Utility functions
├── tests/
│   ├── test_tools.py
│   ├── test_resources.py
│   └── test_integration.py
└── examples/
    └── example_usage.py
```

### Main Server Implementation (server.py)

```python
"""
Main MCP server implementation using the official MCP SDK.
Version: 1.5.0
"""
import asyncio
import logging
from typing import Any, Sequence

import mcp.server.stdio
import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions

# Import your library
from your_library import YourLibraryClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class LibraryMCPServer:
    """MCP Server wrapper for your library."""
    
    def __init__(self, server_name: str = "your-library-mcp"):
        """Initialize the MCP server."""
        self.server = Server(server_name)
        self.library_client: YourLibraryClient | None = None
        
        # Register handlers
        self._register_handlers()
        
    def _register_handlers(self):
        """Register all MCP protocol handlers."""
        
        @self.server.list_tools()
        async def list_tools() -> list[types.Tool]:
            """List available tools."""
            return [
                types.Tool(
                    name="search_tracks",
                    description="Search for music tracks by title, artist, or album",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query string"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of results",
                                "default": 20
                            }
                        },
                        "required": ["query"]
                    }
                ),
                types.Tool(
                    name="download_track",
                    description="Download a specific track by ID",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "track_id": {
                                "type": "string",
                                "description": "Unique track identifier"
                            },
                            "output_path": {
                                "type": "string",
                                "description": "Path where track should be saved"
                            },
                            "format": {
                                "type": "string",
                                "enum": ["mp3", "flac", "ogg"],
                                "description": "Audio format",
                                "default": "mp3"
                            }
                        },
                        "required": ["track_id"]
                    }
                ),
            ]
        
        @self.server.call_tool()
        async def call_tool(
            name: str,
            arguments: dict[str, Any]
        ) -> Sequence[types.TextContent | types.ImageContent | types.EmbeddedResource]:
            """Execute a tool."""
            logger.info(f"Tool called: {name} with args: {arguments}")
            
            # Ensure client is initialized
            if not self.library_client:
                self.library_client = YourLibraryClient()
            
            try:
                if name == "search_tracks":
                    results = await self._search_tracks(
                        query=arguments["query"],
                        limit=arguments.get("limit", 20)
                    )
                    return [types.TextContent(
                        type="text",
                        text=self._format_search_results(results)
                    )]
                    
                elif name == "download_track":
                    result = await self._download_track(
                        track_id=arguments["track_id"],
                        output_path=arguments.get("output_path"),
                        format=arguments.get("format", "mp3")
                    )
                    return [types.TextContent(
                        type="text",
                        text=f"Track downloaded successfully to: {result}"
                    )]
                    
                else:
                    raise ValueError(f"Unknown tool: {name}")
                    
            except Exception as e:
                logger.error(f"Error executing tool {name}: {e}")
                return [types.TextContent(
                    type="text",
                    text=f"Error: {str(e)}"
                )]
        
        @self.server.list_resources()
        async def list_resources() -> list[types.Resource]:
            """List available resources."""
            return [
                types.Resource(
                    uri="library://playlists",
                    name="Available Playlists",
                    description="List of all playlists in the library",
                    mimeType="application/json"
                ),
                types.Resource(
                    uri="library://artists",
                    name="Available Artists",
                    description="List of all artists in the library",
                    mimeType="application/json"
                ),
            ]
        
        @self.server.read_resource()
        async def read_resource(uri: str) -> str:
            """Read a resource by URI."""
            logger.info(f"Resource requested: {uri}")
            
            if not self.library_client:
                self.library_client = YourLibraryClient()
            
            if uri == "library://playlists":
                playlists = await self.library_client.get_playlists()
                return self._format_playlists(playlists)
                
            elif uri == "library://artists":
                artists = await self.library_client.get_artists()
                return self._format_artists(artists)
                
            else:
                raise ValueError(f"Unknown resource URI: {uri}")
        
        @self.server.list_prompts()
        async def list_prompts() -> list[types.Prompt]:
            """List available prompts."""
            return [
                types.Prompt(
                    name="create_playlist",
                    description="Generate a playlist based on criteria",
                    arguments=[
                        types.PromptArgument(
                            name="mood",
                            description="Mood or genre for the playlist",
                            required=True
                        ),
                        types.PromptArgument(
                            name="duration",
                            description="Target duration in minutes",
                            required=False
                        ),
                    ]
                ),
            ]
        
        @self.server.get_prompt()
        async def get_prompt(name: str, arguments: dict[str, str] | None = None) -> types.GetPromptResult:
            """Get a specific prompt."""
            logger.info(f"Prompt requested: {name} with args: {arguments}")
            
            if name == "create_playlist":
                mood = arguments.get("mood", "mixed") if arguments else "mixed"
                duration = arguments.get("duration", "60") if arguments else "60"
                
                prompt_text = f"""Create a {mood} playlist with the following criteria:
- Mood/Genre: {mood}
- Target Duration: {duration} minutes
- Variety: Include different artists and decades
- Flow: Arrange tracks for smooth transitions

Search for tracks that match this criteria and create a cohesive playlist."""
                
                return types.GetPromptResult(
                    description=f"Playlist creation prompt for {mood} mood",
                    messages=[
                        types.PromptMessage(
                            role="user",
                            content=types.TextContent(
                                type="text",
                                text=prompt_text
                            )
                        )
                    ]
                )
            
            raise ValueError(f"Unknown prompt: {name}")
    
    async def _search_tracks(self, query: str, limit: int) -> list[dict]:
        """Search for tracks using your library."""
        # Implement using your library's search functionality
        return await self.library_client.search(query=query, limit=limit)
    
    async def _download_track(self, track_id: str, output_path: str | None, format: str) -> str:
        """Download a track using your library."""
        # Implement using your library's download functionality
        return await self.library_client.download(
            track_id=track_id,
            output_path=output_path,
            format=format
        )
    
    def _format_search_results(self, results: list[dict]) -> str:
        """Format search results for display."""
        if not results:
            return "No tracks found."
        
        output = f"Found {len(results)} tracks:\n\n"
        for i, track in enumerate(results, 1):
            output += f"{i}. {track.get('title', 'Unknown')} - {track.get('artist', 'Unknown')}\n"
            output += f"   Album: {track.get('album', 'Unknown')} | ID: {track.get('id', 'N/A')}\n\n"
        
        return output
    
    def _format_playlists(self, playlists: list[dict]) -> str:
        """Format playlists as JSON."""
        import json
        return json.dumps(playlists, indent=2)
    
    def _format_artists(self, artists: list[dict]) -> str:
        """Format artists as JSON."""
        import json
        return json.dumps(artists, indent=2)
    
    async def run(self):
        """Run the MCP server."""
        logger.info("Starting MCP server...")
        
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="your-library-mcp",
                    server_version="0.1.0",
                    capabilities=self.server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={}
                    )
                )
            )


async def main():
    """Main entry point."""
    server = LibraryMCPServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
```

---

## Tools Implementation

### Tool Design Principles

1. **Single Responsibility** - Each tool should do one thing well
2. **Clear Inputs/Outputs** - Use JSON Schema for validation
3. **Error Handling** - Return informative error messages
4. **Idempotency** - Same inputs should produce same outputs when possible
5. **Documentation** - Provide clear descriptions

### Advanced Tool Example (tools.py)

```python
"""
Tool implementations for MCP server.
"""
from typing import Any
import mcp.types as types


class ToolRegistry:
    """Registry for managing MCP tools."""
    
    def __init__(self, library_client):
        """Initialize tool registry."""
        self.client = library_client
        self.tools = self._define_tools()
    
    def _define_tools(self) -> dict[str, types.Tool]:
        """Define all available tools."""
        return {
            "search_tracks": types.Tool(
                name="search_tracks",
                description="Search for music tracks by title, artist, or album",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query string"
                        },
                        "artist": {
                            "type": "string",
                            "description": "Filter by specific artist (optional)"
                        },
                        "album": {
                            "type": "string",
                            "description": "Filter by specific album (optional)"
                        },
                        "year": {
                            "type": "integer",
                            "description": "Filter by release year (optional)"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results (1-100)",
                            "minimum": 1,
                            "maximum": 100,
                            "default": 20
                        },
                        "offset": {
                            "type": "integer",
                            "description": "Number of results to skip for pagination",
                            "minimum": 0,
                            "default": 0
                        }
                    },
                    "required": ["query"]
                }
            ),
            
            "download_track": types.Tool(
                name="download_track",
                description="Download a specific track by ID to the local filesystem",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "track_id": {
                            "type": "string",
                            "description": "Unique track identifier from the library"
                        },
                        "output_path": {
                            "type": "string",
                            "description": "Absolute path where track should be saved (optional, uses default if not specified)"
                        },
                        "format": {
                            "type": "string",
                            "enum": ["mp3", "flac", "ogg", "m4a", "opus"],
                            "description": "Desired audio format for the download",
                            "default": "mp3"
                        },
                        "quality": {
                            "type": "string",
                            "enum": ["low", "medium", "high", "lossless"],
                            "description": "Audio quality level",
                            "default": "high"
                        },
                        "overwrite": {
                            "type": "boolean",
                            "description": "Overwrite file if it already exists",
                            "default": false
                        }
                    },
                    "required": ["track_id"]
                }
            ),
            
            "create_playlist": types.Tool(
                name="create_playlist",
                description="Create a new playlist on the server",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Name for the new playlist",
                            "minLength": 1,
                            "maxLength": 200
                        },
                        "description": {
                            "type": "string",
                            "description": "Optional description for the playlist"
                        },
                        "track_ids": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            },
                            "description": "Array of track IDs to include in the playlist",
                            "minItems": 1
                        },
                        "public": {
                            "type": "boolean",
                            "description": "Whether the playlist should be public",
                            "default": false
                        }
                    },
                    "required": ["name", "track_ids"]
                }
            ),
            
            "get_track_info": types.Tool(
                name="get_track_info",
                description="Get detailed information about a specific track",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "track_id": {
                            "type": "string",
                            "description": "Unique track identifier"
                        },
                        "include_lyrics": {
                            "type": "boolean",
                            "description": "Include lyrics if available",
                            "default": false
                        },
                        "include_similar": {
                            "type": "boolean",
                            "description": "Include similar tracks",
                            "default": false
                        }
                    },
                    "required": ["track_id"]
                }
            ),
        }
    
    def get_all(self) -> list[types.Tool]:
        """Get all registered tools."""
        return list(self.tools.values())
    
    async def execute(self, name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
        """Execute a tool by name."""
        if name not in self.tools:
            raise ValueError(f"Unknown tool: {name}")
        
        # Route to appropriate handler
        handler = getattr(self, f"_handle_{name}", None)
        if not handler:
            raise NotImplementedError(f"Handler not implemented for tool: {name}")
        
        result = await handler(arguments)
        return [types.TextContent(type="text", text=result)]
    
    async def _handle_search_tracks(self, args: dict[str, Any]) -> str:
        """Handle search_tracks tool."""
        results = await self.client.search(
            query=args["query"],
            artist=args.get("artist"),
            album=args.get("album"),
            year=args.get("year"),
            limit=args.get("limit", 20),
            offset=args.get("offset", 0)
        )
        return self._format_search_results(results)
    
    async def _handle_download_track(self, args: dict[str, Any]) -> str:
        """Handle download_track tool."""
        path = await self.client.download(
            track_id=args["track_id"],
            output_path=args.get("output_path"),
            format=args.get("format", "mp3"),
            quality=args.get("quality", "high"),
            overwrite=args.get("overwrite", False)
        )
        return f"Track downloaded successfully to: {path}"
    
    async def _handle_create_playlist(self, args: dict[str, Any]) -> str:
        """Handle create_playlist tool."""
        playlist = await self.client.create_playlist(
            name=args["name"],
            description=args.get("description", ""),
            track_ids=args["track_ids"],
            public=args.get("public", False)
        )
        return f"Playlist '{playlist['name']}' created with ID: {playlist['id']}"
    
    async def _handle_get_track_info(self, args: dict[str, Any]) -> str:
        """Handle get_track_info tool."""
        info = await self.client.get_track_info(
            track_id=args["track_id"],
            include_lyrics=args.get("include_lyrics", False),
            include_similar=args.get("include_similar", False)
        )
        return self._format_track_info(info)
    
    def _format_search_results(self, results: list[dict]) -> str:
        """Format search results."""
        import json
        return json.dumps({
            "total": len(results),
            "tracks": results
        }, indent=2)
    
    def _format_track_info(self, info: dict) -> str:
        """Format track information."""
        import json
        return json.dumps(info, indent=2)
```

---

## Resources Implementation

### Resource Design Principles

1. **URI Scheme** - Use consistent, hierarchical URIs
2. **MIME Types** - Specify correct content types
3. **Caching** - Support resource caching where appropriate
4. **Templates** - Support URI templates for dynamic resources

### Resource Implementation (resources.py)

```python
"""
Resource implementations for MCP server.
"""
from typing import Any
import mcp.types as types
import json


class ResourceRegistry:
    """Registry for managing MCP resources."""
    
    def __init__(self, library_client):
        """Initialize resource registry."""
        self.client = library_client
        self.resources = self._define_resources()
    
    def _define_resources(self) -> dict[str, types.Resource]:
        """Define all available resources."""
        return {
            "playlists": types.Resource(
                uri="library://playlists",
                name="Available Playlists",
                description="Complete list of all playlists in the library with metadata",
                mimeType="application/json"
            ),
            
            "artists": types.Resource(
                uri="library://artists",
                name="Available Artists",
                description="Complete list of all artists in the library",
                mimeType="application/json"
            ),
            
            "albums": types.Resource(
                uri="library://albums",
                name="Available Albums",
                description="Complete list of all albums in the library",
                mimeType="application/json"
            ),
            
            "genres": types.Resource(
                uri="library://genres",
                name="Available Genres",
                description="List of all genres available in the library",
                mimeType="application/json"
            ),
            
            # Template resource for dynamic content
            "playlist_detail": types.Resource(
                uri="library://playlist/{playlist_id}",
                name="Playlist Details",
                description="Detailed information about a specific playlist including all tracks",
                mimeType="application/json"
            ),
        }
    
    def get_all(self) -> list[types.Resource]:
        """Get all registered resources."""
        return list(self.resources.values())
    
    async def read(self, uri: str) -> str:
        """Read a resource by URI."""
        # Handle template URIs
        if uri.startswith("library://playlist/"):
            playlist_id = uri.split("/")[-1]
            return await self._read_playlist_detail(playlist_id)
        
        # Handle static URIs
        resource_map = {
            "library://playlists": self._read_playlists,
            "library://artists": self._read_artists,
            "library://albums": self._read_albums,
            "library://genres": self._read_genres,
        }
        
        handler = resource_map.get(uri)
        if not handler:
            raise ValueError(f"Unknown resource URI: {uri}")
        
        return await handler()
    
    async def _read_playlists(self) -> str:
        """Read all playlists."""
        playlists = await self.client.get_playlists()
        return json.dumps({
            "total": len(playlists),
            "playlists": playlists
        }, indent=2)
    
    async def _read_artists(self) -> str:
        """Read all artists."""
        artists = await self.client.get_artists()
        return json.dumps({
            "total": len(artists),
            "artists": artists
        }, indent=2)
    
    async def _read_albums(self) -> str:
        """Read all albums."""
        albums = await self.client.get_albums()
        return json.dumps({
            "total": len(albums),
            "albums": albums
        }, indent=2)
    
    async def _read_genres(self) -> str:
        """Read all genres."""
        genres = await self.client.get_genres()
        return json.dumps({
            "total": len(genres),
            "genres": genres
        }, indent=2)
    
    async def _read_playlist_detail(self, playlist_id: str) -> str:
        """Read detailed playlist information."""
        playlist = await self.client.get_playlist(playlist_id)
        return json.dumps(playlist, indent=2)
```

---

## Prompts Implementation

### Prompt Design Principles

1. **Reusability** - Design prompts that work across contexts
2. **Parameterization** - Allow customization via arguments
3. **Clear Instructions** - Provide specific, actionable guidance
4. **Examples** - Include examples when beneficial

### Prompt Implementation (prompts.py)

```python
"""
Prompt implementations for MCP server.
"""
import mcp.types as types


class PromptRegistry:
    """Registry for managing MCP prompts."""
    
    def __init__(self, library_client):
        """Initialize prompt registry."""
        self.client = library_client
        self.prompts = self._define_prompts()
    
    def _define_prompts(self) -> dict[str, types.Prompt]:
        """Define all available prompts."""
        return {
            "create_playlist": types.Prompt(
                name="create_playlist",
                description="Generate a curated playlist based on specific criteria",
                arguments=[
                    types.PromptArgument(
                        name="mood",
                        description="Target mood or genre (e.g., relaxing, energetic, jazz, rock)",
                        required=True
                    ),
                    types.PromptArgument(
                        name="duration",
                        description="Target duration in minutes",
                        required=False
                    ),
                    types.PromptArgument(
                        name="era",
                        description="Time period or decade (e.g., 80s, 90s, modern)",
                        required=False
                    ),
                ]
            ),
            
            "discover_music": types.Prompt(
                name="discover_music",
                description="Discover new music based on user preferences and listening history",
                arguments=[
                    types.PromptArgument(
                        name="favorite_artists",
                        description="Comma-separated list of favorite artists",
                        required=True
                    ),
                    types.PromptArgument(
                        name="genres",
                        description="Comma-separated list of preferred genres",
                        required=False
                    ),
                ]
            ),
            
            "analyze_library": types.Prompt(
                name="analyze_library",
                description="Analyze music library and provide insights",
                arguments=[
                    types.PromptArgument(
                        name="analysis_type",
                        description="Type of analysis: genre_distribution, artist_diversity, or decade_breakdown",
                        required=True
                    ),
                ]
            ),
        }
    
    def get_all(self) -> list[types.Prompt]:
        """Get all registered prompts."""
        return list(self.prompts.values())
    
    async def get(self, name: str, arguments: dict[str, str] | None = None) -> types.GetPromptResult:
        """Get a specific prompt with arguments."""
        if name not in self.prompts:
            raise ValueError(f"Unknown prompt: {name}")
        
        # Route to appropriate handler
        handler = getattr(self, f"_generate_{name}", None)
        if not handler:
            raise NotImplementedError(f"Handler not implemented for prompt: {name}")
        
        return await handler(arguments or {})
    
    async def _generate_create_playlist(self, args: dict[str, str]) -> types.GetPromptResult:
        """Generate create_playlist prompt."""
        mood = args.get("mood", "mixed")
        duration = args.get("duration", "60")
        era = args.get("era", "any")
        
        prompt_text = f"""Create a {mood} playlist with the following criteria:

**Playlist Requirements:**
- **Mood/Genre:** {mood}
- **Target Duration:** {duration} minutes
- **Era/Period:** {era}
- **Variety:** Include different artists to maintain interest
- **Flow:** Arrange tracks for smooth transitions between songs

**Instructions:**
1. Search for tracks that match the {mood} mood/genre
2. Filter by the {era} time period if specified
3. Select a diverse mix of artists while maintaining cohesion
4. Arrange tracks with attention to:
   - Energy levels (start medium, build up, wind down)
   - Key compatibility for smooth transitions
   - Tempo variations to maintain interest
5. Create the playlist with a descriptive name

**Output Format:**
Provide a list of selected tracks with:
- Track title and artist
- Reason for inclusion
- Position in playlist flow

Then use the create_playlist tool to save it."""

        return types.GetPromptResult(
            description=f"Playlist creation prompt for {mood} mood, {duration} minutes, {era} era",
            messages=[
                types.PromptMessage(
                    role="user",
                    content=types.TextContent(
                        type="text",
                        text=prompt_text
                    )
                )
            ]
        )
    
    async def _generate_discover_music(self, args: dict[str, str]) -> types.GetPromptResult:
        """Generate discover_music prompt."""
        favorite_artists = args.get("favorite_artists", "")
        genres = args.get("genres", "various")
        
        # Get library statistics for context
        stats = await self.client.get_library_stats()
        
        prompt_text = f"""Discover new music based on these preferences:

**User Preferences:**
- **Favorite Artists:** {favorite_artists}
- **Preferred Genres:** {genres}

**Library Context:**
- Total Artists: {stats.get('total_artists', 'N/A')}
- Total Tracks: {stats.get('total_tracks', 'N/A')}
- Genres Available: {stats.get('total_genres', 'N/A')}

**Discovery Task:**
1. Search the library for artists similar to the favorites
2. Look for tracks in the preferred genres
3. Find hidden gems and lesser-known tracks
4. Consider:
   - Musical similarity (sound, style, instrumentation)
   - Era and period matching
   - Cross-genre exploration opportunities
5. Provide recommendations with explanations

**Output Format:**
List 10-15 recommended tracks with:
- Track and artist name
- Why it matches the user's taste
- Genre and style notes
- Confidence level (high/medium/low)"""

        return types.GetPromptResult(
            description=f"Music discovery based on {favorite_artists}",
            messages=[
                types.PromptMessage(
                    role="user",
                    content=types.TextContent(
                        type="text",
                        text=prompt_text
                    )
                )
            ]
        )
    
    async def _generate_analyze_library(self, args: dict[str, str]) -> types.GetPromptResult:
        """Generate analyze_library prompt."""
        analysis_type = args.get("analysis_type", "genre_distribution")
        
        # Get full library context
        library_data = await self.client.get_full_library_context()
        
        prompt_text = f"""Analyze the music library with focus on: {analysis_type}

**Library Overview:**
- Total Tracks: {library_data.get('total_tracks', 'N/A')}
- Total Artists: {library_data.get('total_artists', 'N/A')}
- Total Albums: {library_data.get('total_albums', 'N/A')}
- Genres: {library_data.get('total_genres', 'N/A')}

**Analysis Instructions:**
Based on the analysis type '{analysis_type}':

1. **genre_distribution:** 
   - Calculate percentage of each genre
   - Identify dominant and underrepresented genres
   - Suggest areas for library expansion

2. **artist_diversity:**
   - Analyze artist representation
   - Find artists with most/least tracks
   - Assess overall diversity score

3. **decade_breakdown:**
   - Group tracks by decade
   - Identify era concentrations
   - Note gaps in time periods

**Output Format:**
Provide:
- Statistical breakdown with numbers and percentages
- Visual representation (text-based charts)
- Key insights and patterns
- Actionable recommendations"""

        return types.GetPromptResult(
            description=f"Library analysis: {analysis_type}",
            messages=[
                types.PromptMessage(
                    role="user",
                    content=types.TextContent(
                        type="text",
                        text=prompt_text
                    )
                )
            ]
        )
```

---

## Advanced Features

### 1. Server-Sent Events (SSE) Transport

For production deployments, implement SSE transport for remote access:

```python
"""
SSE transport implementation for remote MCP access.
"""
from starlette.applications import Starlette
from starlette.routing import Route
from sse_starlette import EventSourceResponse
import mcp.server.sse


async def handle_sse(request):
    """Handle SSE connection."""
    async with mcp.server.sse.sse_server() as streams:
        await server.run(
            streams[0],
            streams[1],
            server.create_initialization_options()
        )


async def handle_message(request):
    """Handle incoming messages."""
    message = await request.json()
    # Process message
    return {"status": "ok"}


app = Starlette(routes=[
    Route("/sse", endpoint=handle_sse),
    Route("/message", endpoint=handle_message, methods=["POST"]),
])
```

### 2. Resource Subscriptions

Implement resource change notifications:

```python
"""
Resource subscription support.
"""
from mcp.server import Server
import mcp.types as types


class SubscriptionManager:
    """Manage resource subscriptions."""
    
    def __init__(self, server: Server):
        self.server = server
        self.subscriptions: dict[str, set[str]] = {}
    
    async def subscribe(self, uri: str, client_id: str):
        """Subscribe to resource updates."""
        if uri not in self.subscriptions:
            self.subscriptions[uri] = set()
        self.subscriptions[uri].add(client_id)
    
    async def unsubscribe(self, uri: str, client_id: str):
        """Unsubscribe from resource updates."""
        if uri in self.subscriptions:
            self.subscriptions[uri].discard(client_id)
    
    async def notify_update(self, uri: str):
        """Notify subscribers of resource update."""
        if uri in self.subscriptions:
            for client_id in self.subscriptions[uri]:
                await self.server.request_context.session.send_resource_updated(
                    uri=uri
                )
```

### 3. Sampling Support

Implement LLM sampling for agentic workflows:

```python
"""
Sampling support for agentic behavior.
"""
import mcp.types as types


async def handle_sampling(
    create_message_params: types.CreateMessageRequest
) -> types.CreateMessageResult:
    """
    Handle sampling requests from the server.
    
    This allows the server to request LLM completions during tool execution.
    """
    # Forward to client's LLM
    # This is typically handled by the MCP client
    pass
```

### 4. Progress Notifications

Report progress for long-running operations:

```python
"""
Progress notification support.
"""
from mcp.server import Server
import mcp.types as types


class ProgressTracker:
    """Track and report progress."""
    
    def __init__(self, server: Server):
        self.server = server
    
    async def report_progress(
        self,
        progress_token: str | int,
        progress: float,
        total: float | None = None
    ):
        """Report progress to client."""
        await self.server.request_context.session.send_progress_notification(
            progress_token=progress_token,
            progress=progress,
            total=total
        )


# Usage in tool
async def download_large_file(args: dict, tracker: ProgressTracker):
    """Download with progress reporting."""
    total_size = 1000000
    chunk_size = 10000
    
    for i in range(0, total_size, chunk_size):
        # Download chunk
        await download_chunk(i, chunk_size)
        
        # Report progress
        await tracker.report_progress(
            progress_token="download_123",
            progress=i + chunk_size,
            total=total_size
        )
```

### 5. Logging Configuration

Implement comprehensive logging:

```python
"""
Logging configuration for MCP server.
"""
import logging
import sys
from pathlib import Path


def setup_logging(log_level: str = "INFO", log_file: Path | None = None):
    """Configure logging for MCP server."""
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)
    
    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    root_logger.addHandler(console_handler)
    
    # File handler (optional)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    # Suppress noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
```

---

## Error Handling

### Error Handling Strategy

```python
"""
Comprehensive error handling for MCP server.
"""
import mcp.types as types
from typing import Any
import logging

logger = logging.getLogger(__name__)


class MCPError(Exception):
    """Base exception for MCP errors."""
    pass


class ToolExecutionError(MCPError):
    """Error during tool execution."""
    pass


class ResourceNotFoundError(MCPError):
    """Requested resource not found."""
    pass


class InvalidArgumentError(MCPError):
    """Invalid tool arguments."""
    pass


async def safe_tool_execution(
    tool_name: str,
    handler: callable,
    arguments: dict[str, Any]
) -> list[types.TextContent]:
    """
    Safely execute a tool with comprehensive error handling.
    """
    try:
        # Validate arguments
        validate_arguments(tool_name, arguments)
        
        # Execute handler
        result = await handler(arguments)
        
        return [types.TextContent(
            type="text",
            text=result
        )]
        
    except InvalidArgumentError as e:
        logger.error(f"Invalid arguments for {tool_name}: {e}")
        return [types.TextContent(
            type="text",
            text=f"Error: Invalid arguments - {str(e)}"
        )]
    
    except ResourceNotFoundError as e:
        logger.error(f"Resource not found in {tool_name}: {e}")
        return [types.TextContent(
            type="text",
            text=f"Error: Resource not found - {str(e)}"
        )]
    
    except ToolExecutionError as e:
        logger.error(f"Execution error in {tool_name}: {e}")
        return [types.TextContent(
            type="text",
            text=f"Error: Tool execution failed - {str(e)}"
        )]
    
    except Exception as e:
        logger.exception(f"Unexpected error in {tool_name}")
        return [types.TextContent(
            type="text",
            text=f"Error: An unexpected error occurred - {str(e)}"
        )]


def validate_arguments(tool_name: str, arguments: dict[str, Any]):
    """Validate tool arguments against schema."""
    # Implement JSON schema validation
    # Raise InvalidArgumentError if validation fails
    pass
```

---

## Testing

### Test Structure

```
tests/
├── conftest.py              # Pytest configuration and fixtures
├── test_server.py           # Server initialization tests
├── test_tools.py            # Tool execution tests
├── test_resources.py        # Resource reading tests
├── test_prompts.py          # Prompt generation tests
├── test_integration.py      # End-to-end integration tests
└── test_error_handling.py   # Error handling tests
```

### Test Implementation (conftest.py)

```python
"""
Pytest configuration and shared fixtures.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from your_library import YourLibraryClient


@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_library_client():
    """Mock library client for testing."""
    client = AsyncMock(spec=YourLibraryClient)
    
    # Configure mock responses
    client.search.return_value = [
        {
            "id": "track1",
            "title": "Test Track",
            "artist": "Test Artist",
            "album": "Test Album"
        }
    ]
    
    client.get_playlists.return_value = [
        {
            "id": "playlist1",
            "name": "Test Playlist",
            "track_count": 10
        }
    ]
    
    return client


@pytest.fixture
def mcp_server(mock_library_client):
    """Create MCP server instance for testing."""
    from mcp_server.server import LibraryMCPServer
    
    server = LibraryMCPServer()
    server.library_client = mock_library_client
    
    return server
```

### Tool Tests (test_tools.py)

```python
"""
Tests for MCP tools.
"""
import pytest
from mcp_server.tools import ToolRegistry


@pytest.mark.asyncio
async def test_search_tracks_tool(mock_library_client):
    """Test search_tracks tool."""
    registry = ToolRegistry(mock_library_client)
    
    result = await registry.execute("search_tracks", {
        "query": "test song",
        "limit": 10
    })
    
    assert len(result) == 1
    assert "Test Track" in result[0].text
    mock_library_client.search.assert_called_once()


@pytest.mark.asyncio
async def test_download_track_tool(mock_library_client):
    """Test download_track tool."""
    mock_library_client.download.return_value = "/path/to/track.mp3"
    
    registry = ToolRegistry(mock_library_client)
    
    result = await registry.execute("download_track", {
        "track_id": "track123",
        "format": "mp3"
    })
    
    assert "downloaded successfully" in result[0].text
    mock_library_client.download.assert_called_once()


@pytest.mark.asyncio
async def test_invalid_tool_name(mock_library_client):
    """Test handling of invalid tool name."""
    registry = ToolRegistry(mock_library_client)
    
    with pytest.raises(ValueError, match="Unknown tool"):
        await registry.execute("nonexistent_tool", {})
```

### Integration Tests (test_integration.py)

```python
"""
Integration tests for MCP server.
"""
import pytest
import json
from mcp_server.server import LibraryMCPServer


@pytest.mark.asyncio
async def test_full_workflow(mock_library_client):
    """Test complete workflow: search, get info, download."""
    server = LibraryMCPServer()
    server.library_client = mock_library_client
    
    # List tools
    tools = await server.server._list_tools_handlers[0]()
    assert len(tools) > 0
    
    # Search for tracks
    search_result = await server.server._call_tool_handlers[0](
        "search_tracks",
        {"query": "test", "limit": 5}
    )
    assert search_result is not None
    
    # Read resource
    playlists = await server.server._read_resource_handlers[0](
        "library://playlists"
    )
    data = json.loads(playlists)
    assert "playlists" in data
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=mcp_server --cov-report=html

# Run specific test file
uv run pytest tests/test_tools.py

# Run with verbose output
uv run pytest -v

# Run only integration tests
uv run pytest -m integration
```

---

## Deployment

### Package Building

```bash
# Build distribution packages
uv build

# This creates:
# dist/your-library-mcp-server-0.1.0.tar.gz
# dist/your_library_mcp_server-0.1.0-py3-none-any.whl
```

### Publishing to PyPI

```bash
# Publish to PyPI (requires account)
uv publish

# Publish to TestPyPI first
uv publish --publish-url https://test.pypi.org/legacy/
```

### Docker Deployment

Create `Dockerfile`:

```dockerfile
FROM python:3.13.7-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.8.22 /uv /usr/local/bin/uv

# Copy project files
COPY pyproject.toml uv.lock ./
COPY src ./src

# Install dependencies
RUN uv sync --frozen --no-dev

# Run server
CMD ["uv", "run", "python", "-m", "mcp_server.server"]
```

Build and run:

```bash
# Build image
docker build -t your-library-mcp:latest .

# Run container
docker run -i your-library-mcp:latest
```

### Systemd Service

Create `/etc/systemd/system/mcp-server.service`:

```ini
[Unit]
Description=MCP Server for Your Library
After=network.target

[Service]
Type=simple
User=mcp-user
WorkingDirectory=/opt/mcp-server
ExecStart=/home/mcp-user/.local/bin/uv run python -m mcp_server.server
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable mcp-server
sudo systemctl start mcp-server
sudo systemctl status mcp-server
```

---

## Client Configuration

### Claude Desktop Configuration

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`  
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`  
**Linux:** `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "your-library": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/mcp-server",
        "run",
        "python",
        "-m",
        "mcp_server.server"
      ],
      "env": {
        "LIBRARY_API_URL": "http://localhost:4040",
        "LIBRARY_API_KEY": "your-api-key"
      }
    }
  }
}
```

### Environment Variables

Create `.env` file:

```bash
# Library Configuration
LIBRARY_API_URL=http://localhost:4040
LIBRARY_API_KEY=your-api-key-here
LIBRARY_USERNAME=admin
LIBRARY_PASSWORD=secret

# MCP Server Configuration
MCP_SERVER_NAME=your-library-mcp
MCP_LOG_LEVEL=INFO
MCP_LOG_FILE=/var/log/mcp-server.log

# Feature Flags
ENABLE_CACHING=true
CACHE_TTL_SECONDS=300
MAX_SEARCH_RESULTS=100
```

### Multiple Servers

Configure multiple instances for different libraries:

```json
{
  "mcpServers": {
    "library-main": {
      "command": "uv",
      "args": ["--directory", "/path/to/main", "run", "python", "-m", "mcp_server.server"],
      "env": {
        "LIBRARY_API_URL": "http://main-server:4040"
      }
    },
    "library-backup": {
      "command": "uv",
      "args": ["--directory", "/path/to/backup", "run", "python", "-m", "mcp_server.server"],
      "env": {
        "LIBRARY_API_URL": "http://backup-server:4040"
      }
    }
  }
}
```

---

## Best Practices

### 1. Security

- **API Key Management:** Never hardcode credentials, use environment variables
- **Input Validation:** Always validate and sanitize tool inputs
- **Rate Limiting:** Implement rate limiting for resource-intensive operations
- **Access Control:** Verify permissions before executing operations

```python
"""
Security best practices.
"""
import os
from functools import wraps


def require_auth(func):
    """Decorator to require authentication."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        api_key = os.getenv("LIBRARY_API_KEY")
        if not api_key:
            raise ValueError("API key not configured")
        return await func(*args, **kwargs)
    return wrapper


def sanitize_path(path: str) -> str:
    """Sanitize file paths to prevent directory traversal."""
    import os.path
    return os.path.normpath(path).lstrip("/")
```

### 2. Performance

- **Caching:** Cache frequently accessed resources
- **Async Operations:** Use async/await for I/O operations
- **Connection Pooling:** Reuse HTTP connections
- **Batch Operations:** Group multiple operations when possible

```python
"""
Performance optimization.
"""
from functools import lru_cache
import asyncio


class CachedResourceManager:
    """Manage resources with caching."""
    
    def __init__(self, ttl_seconds: int = 300):
        self.ttl = ttl_seconds
        self.cache: dict[str, tuple[float, Any]] = {}
    
    async def get_resource(self, uri: str) -> Any:
        """Get resource with caching."""
        import time
        
        # Check cache
        if uri in self.cache:
            timestamp, data = self.cache[uri]
            if time.time() - timestamp < self.ttl:
                return data
        
        # Fetch fresh data
        data = await self._fetch_resource(uri)
        self.cache[uri] = (time.time(), data)
        
        return data
```

### 3. Error Messages

- **User-Friendly:** Provide clear, actionable error messages
- **Detailed Logging:** Log full error details for debugging
- **Error Codes:** Use consistent error codes
- **Recovery Guidance:** Suggest how to fix errors

```python
"""
User-friendly error handling.
"""


class UserError(Exception):
    """User-facing error with helpful message."""
    
    def __init__(self, message: str, suggestion: str = ""):
        self.message = message
        self.suggestion = suggestion
        super().__init__(message)
    
    def __str__(self):
        if self.suggestion:
            return f"{self.message}\n\nSuggestion: {self.suggestion}"
        return self.message


# Usage
raise UserError(
    "Track not found with ID: track123",
    "Verify the track ID is correct or search for the track first"
)
```

### 4. Documentation

- **Tool Descriptions:** Clear, concise descriptions
- **Parameter Documentation:** Explain each parameter
- **Examples:** Provide usage examples
- **API Documentation:** Maintain up-to-date API docs

### 5. Versioning

- **Semantic Versioning:** Follow semver (MAJOR.MINOR.PATCH)
- **Changelog:** Maintain detailed changelog
- **Deprecation Policy:** Deprecate features gracefully
- **Backward Compatibility:** Maintain compatibility when possible

### 6. Testing

- **Unit Tests:** Test individual components
- **Integration Tests:** Test component interactions
- **End-to-End Tests:** Test complete workflows
- **Coverage:** Aim for >80% code coverage

### 7. Monitoring

- **Health Checks:** Implement health check endpoints
- **Metrics:** Track usage metrics
- **Logging:** Comprehensive structured logging
- **Alerting:** Set up alerts for errors

```python
"""
Monitoring implementation.
"""
import logging
from datetime import datetime


class MetricsCollector:
    """Collect usage metrics."""
    
    def __init__(self):
        self.metrics = {
            "tool_calls": {},
            "resource_reads": {},
            "errors": 0,
            "start_time": datetime.now()
        }
    
    def record_tool_call(self, tool_name: str):
        """Record tool execution."""
        if tool_name not in self.metrics["tool_calls"]:
            self.metrics["tool_calls"][tool_name] = 0
        self.metrics["tool_calls"][tool_name] += 1
    
    def record_error(self):
        """Record error occurrence."""
        self.metrics["errors"] += 1
    
    def get_metrics(self) -> dict:
        """Get current metrics."""
        uptime = (datetime.now() - self.metrics["start_time"]).total_seconds()
        return {
            **self.metrics,
            "uptime_seconds": uptime
        }
```

---

## Appendix

### A. MCP Specification Reference

- **Full Specification:** https://spec.modelcontextprotocol.io/specification/2025-06-18
- **JSON-RPC 2.0:** https://www.jsonrpc.org/specification
- **Python SDK Docs:** https://github.com/modelcontextprotocol/python-sdk
- **MCP Registry:** https://github.com/modelcontextprotocol/registry

### B. Example Complete Server

See the `/examples` directory for:
- Complete working server implementation
- Integration with sample Subsonic server
- Test suite
- Docker deployment example

### C. Common Patterns

#### Pattern 1: Pagination Support

```python
async def handle_paginated_search(args: dict) -> str:
    """Handle search with pagination."""
    page = args.get("page", 1)
    per_page = args.get("per_page", 20)
    offset = (page - 1) * per_page
    
    results = await client.search(
        query=args["query"],
        limit=per_page,
        offset=offset
    )
    
    return json.dumps({
        "page": page,
        "per_page": per_page,
        "total": results["total"],
        "results": results["items"]
    })
```

#### Pattern 2: Batch Operations

```python
async def handle_batch_download(args: dict) -> str:
    """Download multiple tracks."""
    track_ids = args["track_ids"]
    results = []
    
    for track_id in track_ids:
        try:
            path = await client.download(track_id)
            results.append({"track_id": track_id, "status": "success", "path": path})
        except Exception as e:
            results.append({"track_id": track_id, "status": "error", "error": str(e)})
    
    return json.dumps(results, indent=2)
```

#### Pattern 3: Resource Templating

```python
def expand_uri_template(template: str, params: dict) -> str:
    """Expand URI template with parameters."""
    uri = template
    for key, value in params.items():
        uri = uri.replace(f"{{{key}}}", str(value))
    return uri


# Usage
uri = expand_uri_template(
    "library://playlist/{playlist_id}/track/{track_id}",
    {"playlist_id": "123", "track_id": "456"}
)
# Result: "library://playlist/123/track/456"
```

### D. Troubleshooting

#### Issue: Server not appearing in Claude Desktop

**Solution:**
1. Check `claude_desktop_config.json` syntax (valid JSON)
2. Verify absolute paths in configuration
3. Check server logs: `~/Library/Logs/Claude/mcp-server-*.log`
4. Restart Claude Desktop after config changes

#### Issue: Import errors when running server

**Solution:**
```bash
# Ensure dependencies are installed
uv sync

# Check Python version
python --version  # Should be 3.10+

# Verify uv installation
uv --version  # Should be 0.8.22
```

#### Issue: Tools not executing

**Solution:**
1. Check tool handler registration
2. Verify input schema matches arguments
3. Review error logs for exceptions
4. Test tool in isolation with pytest

---

## Conclusion

This guide provides a complete foundation for implementing MCP functionality in your Python library. Key takeaways:

1. **Use Official SDK:** MCP Python SDK 1.5.0 provides all necessary components
2. **Follow Standards:** Adhere to MCP specification for compatibility
3. **Test Thoroughly:** Comprehensive testing ensures reliability
4. **Document Well:** Clear documentation aids adoption
5. **Monitor Usage:** Track metrics for optimization

For additional support:
- MCP Community: https://github.com/modelcontextprotocol
- Python SDK Issues: https://github.com/modelcontextprotocol/python-sdk/issues
- Specification Discussions: https://github.com/modelcontextprotocol/specification/discussions

---

**Document Metadata:**
- **Version:** 1.0
- **Last Updated:** October 5, 2025
- **Python Version:** 3.13.7
- **MCP SDK Version:** 1.5.0
- **uv Version:** 0.8.22
