"""
MCP Connector for Subsonic Integration - Phase 1 Implementation

Configures and manages connection to Subsonic MCP server for track search and analysis.
Provides health checking and error handling for MCP availability.
"""

import os
import logging
from typing import Any, Dict, List, Optional
import aiohttp
import asyncio

logger = logging.getLogger(__name__)


class MCPConnector:
    """Connector for Subsonic MCP server integration."""

    def __init__(self, server_url: Optional[str] = None):
        """
        Initialize MCP connector.

        Args:
            server_url: Subsonic MCP server URL. If None, reads from SUBSONIC_MCP_URL env var.

        Raises:
            ValueError: If server URL is not provided or found in environment.
        """
        self.server_url = server_url or os.getenv("SUBSONIC_MCP_URL")
        if not self.server_url:
            raise ValueError("SUBSONIC_MCP_URL must be provided or set in environment")

        # Strip trailing slash
        self.server_url = self.server_url.rstrip("/")

        # Default tool set for playlist generation
        self.default_tools = [
            "search_tracks",
            "get_genres",
            "search_similar",
            "analyze_library",
        ]

        logger.info(f"MCP connector initialized with server: {self.server_url}")

    def configure_subsonic_mcp_tools(self, tools: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Configure Subsonic MCP tools for OpenAI integration.

        Args:
            tools: List of tool names to enable. If None, uses default tools.

        Returns:
            HostedMCPTool configuration dict for OpenAI API.
        """
        tool_list = tools or self.default_tools

        config: Dict[str, Any] = {
            "type": "hosted_mcp",
            "hosted_mcp": {
                "server_url": self.server_url,
                "tools": tool_list,
            },
        }

        logger.debug(f"Configured MCP tools: {tool_list} for server {self.server_url}")

        return config

    async def verify_mcp_available(self, timeout: int = 5) -> bool:
        """
        Verify MCP server is available and responsive.

        Args:
            timeout: Timeout in seconds for health check.

        Returns:
            True if MCP server is available, False otherwise.
        """
        health_endpoint = f"{self.server_url}/health"

        logger.debug(f"Checking MCP server health at {health_endpoint}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    health_endpoint, timeout=aiohttp.ClientTimeout(total=timeout)
                ) as response:
                    if response.status == 200:
                        logger.info(f"MCP server health check passed: {self.server_url}")
                        return True
                    else:
                        logger.warning(
                            f"MCP server health check failed: "
                            f"HTTP {response.status} from {health_endpoint}"
                        )
                        return False

        except aiohttp.ClientError as e:
            logger.error(
                f"MCP server connection error: {e} (server: {self.server_url})",
                exc_info=True,
            )
            return False

        except asyncio.TimeoutError:
            logger.error(
                f"MCP server health check timeout after {timeout}s " f"(server: {self.server_url})"
            )
            return False

        except Exception as e:
            logger.error(
                f"Unexpected error during MCP health check: {e}",
                exc_info=True,
            )
            return False

    async def get_available_tools(self) -> List[str]:
        """
        Get list of available tools from MCP server.

        Returns:
            List of available tool names.

        Raises:
            Exception: If MCP server is unavailable or request fails.
        """
        tools_endpoint = f"{self.server_url}/tools"

        logger.debug(f"Fetching available tools from {tools_endpoint}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    tools_endpoint, timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        tools: List[str] = data.get("tools", [])
                        logger.info(f"Retrieved {len(tools)} tools from MCP server: {tools}")
                        return tools
                    else:
                        raise Exception(f"Failed to fetch tools: HTTP {response.status}")

        except Exception as e:
            logger.error(
                f"Failed to get available tools from MCP server: {e}",
                exc_info=True,
            )
            raise

    async def verify_required_tools(self, required_tools: Optional[List[str]] = None) -> bool:
        """
        Verify that required tools are available on MCP server.

        Args:
            required_tools: List of required tool names. If None, uses default tools.

        Returns:
            True if all required tools are available, False otherwise.
        """
        required = set(required_tools or self.default_tools)

        try:
            available = set(await self.get_available_tools())

            missing = required - available

            if missing:
                logger.warning(
                    f"Missing required MCP tools: {missing} " f"(available: {available})"
                )
                return False

            logger.info(f"All required MCP tools available: {required}")
            return True

        except Exception as e:
            logger.error(f"Failed to verify required tools: {e}")
            return False

    async def test_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Test MCP tool call with given arguments.

        Args:
            tool_name: Name of tool to call.
            arguments: Tool arguments as dict.

        Returns:
            Tool response as dict.

        Raises:
            Exception: If tool call fails.
        """
        tool_endpoint = f"{self.server_url}/tools/{tool_name}"

        logger.debug(f"Testing MCP tool call: {tool_name} with arguments {arguments}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    tool_endpoint,
                    json=arguments,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    if response.status == 200:
                        result: Dict[str, Any] = await response.json()
                        logger.info(f"Tool {tool_name} call succeeded")
                        return result
                    else:
                        error_text = await response.text()
                        raise Exception(
                            f"Tool {tool_name} call failed: "
                            f"HTTP {response.status} - {error_text}"
                        )

        except Exception as e:
            logger.error(
                f"MCP tool call failed for {tool_name}: {e}",
                exc_info=True,
            )
            raise


# Singleton instance
_connector_instance: Optional[MCPConnector] = None


def get_connector() -> MCPConnector:
    """
    Get singleton MCP connector instance.

    Returns:
        MCPConnector instance.
    """
    global _connector_instance
    if _connector_instance is None:
        _connector_instance = MCPConnector()
    return _connector_instance


async def configure_and_verify_mcp() -> Dict[str, Any]:
    """
    Configure MCP tools and verify server availability.

    Returns:
        MCP tool configuration dict if successful.

    Raises:
        Exception: If MCP server is unavailable or required tools are missing.
    """
    connector = get_connector()

    # Verify server is available
    if not await connector.verify_mcp_available():
        raise Exception(
            f"MCP server not available at {connector.server_url}. "
            "Please ensure SUBSONIC_MCP_URL is set correctly and server is running."
        )

    # Verify required tools are available
    if not await connector.verify_required_tools():
        raise Exception(
            f"Required MCP tools not available on server {connector.server_url}. "
            f"Expected tools: {connector.default_tools}"
        )

    # Configure tools for OpenAI
    mcp_config = connector.configure_subsonic_mcp_tools()

    logger.info("MCP configuration and verification complete")

    return mcp_config
