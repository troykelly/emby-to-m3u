"""Main MCP Server class with stdio transport for Claude Desktop integration.

This module implements the MCPServer class that coordinates all MCP components
(tools, resources, prompts) and provides stdio transport for Claude Desktop.
"""

import logging
import os
import sys
from typing import Any

import mcp.server.stdio
import mcp.types as types
from mcp.server import Server

# Add parent directory to path to import SubsonicClient
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from src.subsonic.client import SubsonicClient
from src.subsonic.models import SubsonicConfig

from .cache import CacheManager
from .tools import ToolRegistry
from .resources import ResourceRegistry
from .prompts import PromptRegistry
from .utils import safe_tool_execution

logger = logging.getLogger(__name__)


class MCPServer:
    """Main MCP server class coordinating tools, resources, and prompts.

    This class:
    - Initializes SubsonicClient from environment variables
    - Registers 10 tools, 6 resources, and 5 prompts
    - Provides stdio transport for Claude Desktop
    - Handles all MCP protocol methods
    """

    def __init__(self):
        """Initialize MCP server with Subsonic client and registries."""
        # Read Subsonic configuration from environment
        subsonic_url = os.getenv("SUBSONIC_URL")
        subsonic_user = os.getenv("SUBSONIC_USER")
        subsonic_password = os.getenv("SUBSONIC_PASSWORD")

        if not all([subsonic_url, subsonic_user, subsonic_password]):
            raise ValueError(
                "Missing required environment variables: SUBSONIC_URL, SUBSONIC_USER, SUBSONIC_PASSWORD"
            )

        # Initialize SubsonicClient
        config = SubsonicConfig(
            url=subsonic_url,
            username=subsonic_user,
            password=subsonic_password,
            client_name="Subsonic MCP Server",
        )
        self.subsonic_client = SubsonicClient(config)

        # Initialize cache
        self.cache = CacheManager(default_ttl=300)

        # Initialize registries
        self.tool_registry = ToolRegistry(self.subsonic_client, self.cache)
        self.resource_registry = ResourceRegistry(self.subsonic_client, self.cache)
        self.prompt_registry = PromptRegistry()

        # Create MCP server instance
        self.server = Server("subsonic-mcp-server")

        # Register handlers
        self._register_handlers()

        logger.info("Subsonic MCP Server initialized")

    def _register_handlers(self):
        """Register all MCP protocol handlers."""

        # List tools handler
        @self.server.list_tools()
        async def list_tools() -> list[types.Tool]:
            """Return all available tools."""
            tools = self.tool_registry.get_all()
            logger.info(f"Listing {len(tools)} tools")
            return tools

        # Call tool handler
        @self.server.call_tool()
        async def call_tool(
            name: str, arguments: dict[str, Any]
        ) -> list[types.TextContent]:
            """Execute a tool by name."""
            logger.info(f"Executing tool: {name} with args: {arguments}")

            # Route to tool handler
            handler = getattr(self.tool_registry, f"_{name}", None)
            if handler is None:
                raise ValueError(f"Unknown tool: {name}")

            # Execute with error handling
            return await safe_tool_execution(name, handler, arguments)

        # List resources handler
        @self.server.list_resources()
        async def list_resources() -> list[types.Resource]:
            """Return all available resources."""
            resources = self.resource_registry.get_all()
            logger.info(f"Listing {len(resources)} resources")
            return resources

        # Read resource handler
        @self.server.read_resource()
        async def read_resource(uri: str) -> str:
            """Read a resource by URI."""
            logger.info(f"Reading resource: {uri}")

            # Route to resource handler based on URI
            if uri == "library://stats":
                contents = await self.resource_registry._read_library_stats()
            elif uri == "library://artists":
                contents = await self.resource_registry._read_artists()
            elif uri == "library://albums":
                contents = await self.resource_registry._read_albums()
            elif uri == "library://genres":
                contents = await self.resource_registry._read_genres()
            elif uri == "library://playlists":
                contents = await self.resource_registry._read_playlists()
            elif uri == "library://recent":
                contents = await self.resource_registry._read_recent_tracks()
            else:
                raise ValueError(f"Unknown resource URI: {uri}")

            # Return as JSON string
            import json

            return json.dumps(contents, indent=2)

        # List prompts handler
        @self.server.list_prompts()
        async def list_prompts() -> list[types.Prompt]:
            """Return all available prompts."""
            prompts = self.prompt_registry.get_all()
            logger.info(f"Listing {len(prompts)} prompts")
            return prompts

        # Get prompt handler
        @self.server.get_prompt()
        async def get_prompt(
            name: str, arguments: dict[str, Any] | None
        ) -> types.GetPromptResult:
            """Get a prompt with arguments filled in."""
            logger.info(f"Getting prompt: {name} with args: {arguments}")

            # Get prompt result
            result = await self.prompt_registry.get_prompt(
                name, arguments or {}
            )

            # Convert to GetPromptResult
            messages = [
                types.PromptMessage(
                    role=msg["role"],
                    content=types.TextContent(
                        type="text", text=msg["content"]["text"]
                    ),
                )
                for msg in result["messages"]
            ]

            return types.GetPromptResult(
                description=result["description"], messages=messages
            )

    async def run(self):
        """Run the MCP server with stdio transport."""
        logger.info("Starting Subsonic MCP Server with stdio transport")

        # Run stdio server
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options(),
            )


async def main():
    """Main entry point for the MCP server."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Create and run server
    server = MCPServer()
    await server.run()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
