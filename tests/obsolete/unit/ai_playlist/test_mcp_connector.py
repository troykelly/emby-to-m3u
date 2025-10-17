"""
Unit Tests for MCP Connector

Tests MCP server connection, tool configuration, health checks, and error handling.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import aiohttp

from src.ai_playlist.mcp_connector import (
    MCPConnector,
    get_connector,
    configure_and_verify_mcp
)


class TestMCPConnectorInit:
    """Test suite for MCP connector initialization."""

    def test_init_with_explicit_url(self):
        """Test initialization with explicit server URL."""
        connector = MCPConnector(server_url="http://localhost:8080")

        assert connector.server_url == "http://localhost:8080"
        assert "search_tracks" in connector.default_tools
        assert "get_genres" in connector.default_tools

    def test_init_with_env_var(self, monkeypatch):
        """Test initialization from SUBSONIC_MCP_URL environment variable."""
        monkeypatch.setenv("SUBSONIC_MCP_URL", "http://mcp-server:9000")

        connector = MCPConnector()

        assert connector.server_url == "http://mcp-server:9000"

    def test_init_without_url_raises_error(self, monkeypatch):
        """Test that missing server URL raises ValueError."""
        monkeypatch.delenv("SUBSONIC_MCP_URL", raising=False)

        with pytest.raises(ValueError, match="SUBSONIC_MCP_URL must be provided"):
            MCPConnector()

    def test_init_strips_trailing_slash(self):
        """Test that trailing slash is removed from server URL."""
        connector = MCPConnector(server_url="http://localhost:8080/")

        assert connector.server_url == "http://localhost:8080"

    def test_init_sets_default_tools(self):
        """Test default tools are set correctly."""
        connector = MCPConnector(server_url="http://localhost:8080")

        assert len(connector.default_tools) == 4
        assert "search_tracks" in connector.default_tools
        assert "get_genres" in connector.default_tools
        assert "search_similar" in connector.default_tools
        assert "analyze_library" in connector.default_tools


class TestConfigureSubsonicMCPTools:
    """Test suite for MCP tool configuration."""

    def test_configure_with_default_tools(self):
        """Test tool configuration with default tools."""
        connector = MCPConnector(server_url="http://localhost:8080")

        config = connector.configure_subsonic_mcp_tools()

        assert config["type"] == "hosted_mcp"
        assert config["hosted_mcp"]["server_url"] == "http://localhost:8080"
        assert len(config["hosted_mcp"]["tools"]) == 4
        assert "search_tracks" in config["hosted_mcp"]["tools"]

    def test_configure_with_custom_tools(self):
        """Test tool configuration with custom tool list."""
        connector = MCPConnector(server_url="http://localhost:8080")

        custom_tools = ["search_tracks", "get_genres"]
        config = connector.configure_subsonic_mcp_tools(tools=custom_tools)

        assert config["hosted_mcp"]["tools"] == custom_tools
        assert len(config["hosted_mcp"]["tools"]) == 2

    def test_configure_preserves_server_url(self):
        """Test configuration preserves server URL."""
        connector = MCPConnector(server_url="http://test-server:8080")

        config = connector.configure_subsonic_mcp_tools()

        assert config["hosted_mcp"]["server_url"] == "http://test-server:8080"


@pytest.mark.asyncio
class TestVerifyMCPAvailable:
    """Test suite for MCP server health checks."""

    async def test_verify_server_available_success(self):
        """Test successful health check."""
        connector = MCPConnector(server_url="http://localhost:8080")

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None

        mock_session = AsyncMock()
        mock_session.get.return_value = mock_response
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None

        with patch("aiohttp.ClientSession", return_value=mock_session):
            available = await connector.verify_mcp_available()

        assert available is True

    async def test_verify_server_unavailable_http_error(self):
        """Test health check fails with HTTP error."""
        connector = MCPConnector(server_url="http://localhost:8080")

        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None

        mock_session = AsyncMock()
        mock_session.get.return_value = mock_response
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None

        with patch("aiohttp.ClientSession", return_value=mock_session):
            available = await connector.verify_mcp_available()

        assert available is False

    async def test_verify_server_timeout(self):
        """Test health check handles timeout."""
        connector = MCPConnector(server_url="http://localhost:8080")

        mock_session = AsyncMock()
        mock_session.get.side_effect = asyncio.TimeoutError()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None

        with patch("aiohttp.ClientSession", return_value=mock_session):
            available = await connector.verify_mcp_available()

        assert available is False

    async def test_verify_server_connection_error(self):
        """Test health check handles connection error."""
        connector = MCPConnector(server_url="http://localhost:8080")

        mock_session = AsyncMock()
        mock_session.get.side_effect = aiohttp.ClientError("Connection refused")
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None

        with patch("aiohttp.ClientSession", return_value=mock_session):
            available = await connector.verify_mcp_available()

        assert available is False

    async def test_verify_custom_timeout(self):
        """Test health check with custom timeout."""
        connector = MCPConnector(server_url="http://localhost:8080")

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None

        mock_session = AsyncMock()
        mock_session.get.return_value = mock_response
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None

        with patch("aiohttp.ClientSession", return_value=mock_session):
            available = await connector.verify_mcp_available(timeout=10)

        assert available is True


@pytest.mark.asyncio
class TestGetAvailableTools:
    """Test suite for fetching available tools."""

    async def test_get_tools_success(self):
        """Test successful tool list retrieval."""
        connector = MCPConnector(server_url="http://localhost:8080")

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"tools": ["search_tracks", "get_genres"]})
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None

        mock_session = AsyncMock()
        mock_session.get.return_value = mock_response
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None

        with patch("aiohttp.ClientSession", return_value=mock_session):
            tools = await connector.get_available_tools()

        assert len(tools) == 2
        assert "search_tracks" in tools
        assert "get_genres" in tools

    async def test_get_tools_http_error(self):
        """Test tool retrieval fails with HTTP error."""
        connector = MCPConnector(server_url="http://localhost:8080")

        mock_response = AsyncMock()
        mock_response.status = 404
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None

        mock_session = AsyncMock()
        mock_session.get.return_value = mock_response
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None

        with patch("aiohttp.ClientSession", return_value=mock_session):
            with pytest.raises(Exception, match="Failed to fetch tools"):
                await connector.get_available_tools()


@pytest.mark.asyncio
class TestVerifyRequiredTools:
    """Test suite for required tool verification."""

    async def test_verify_all_required_tools_available(self):
        """Test verification succeeds when all required tools are available."""
        connector = MCPConnector(server_url="http://localhost:8080")

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "tools": ["search_tracks", "get_genres", "search_similar", "analyze_library"]
        })
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None

        mock_session = AsyncMock()
        mock_session.get.return_value = mock_response
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None

        with patch("aiohttp.ClientSession", return_value=mock_session):
            verified = await connector.verify_required_tools()

        assert verified is True

    async def test_verify_missing_required_tools(self):
        """Test verification fails when required tools are missing."""
        connector = MCPConnector(server_url="http://localhost:8080")

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "tools": ["search_tracks"]  # Missing other tools
        })
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None

        mock_session = AsyncMock()
        mock_session.get.return_value = mock_response
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None

        with patch("aiohttp.ClientSession", return_value=mock_session):
            verified = await connector.verify_required_tools()

        assert verified is False

    async def test_verify_custom_required_tools(self):
        """Test verification with custom required tools list."""
        connector = MCPConnector(server_url="http://localhost:8080")

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "tools": ["search_tracks", "get_genres"]
        })
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None

        mock_session = AsyncMock()
        mock_session.get.return_value = mock_response
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None

        with patch("aiohttp.ClientSession", return_value=mock_session):
            verified = await connector.verify_required_tools(
                required_tools=["search_tracks", "get_genres"]
            )

        assert verified is True


@pytest.mark.asyncio
class TestTestToolCall:
    """Test suite for MCP tool call testing."""

    async def test_tool_call_success(self):
        """Test successful tool call."""
        connector = MCPConnector(server_url="http://localhost:8080")

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"result": "success"})
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None

        mock_session = AsyncMock()
        mock_session.post.return_value = mock_response
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await connector.test_tool_call("search_tracks", {"genre": "Rock"})

        assert result["result"] == "success"

    async def test_tool_call_http_error(self):
        """Test tool call handles HTTP error."""
        connector = MCPConnector(server_url="http://localhost:8080")

        mock_response = AsyncMock()
        mock_response.status = 400
        mock_response.text = AsyncMock(return_value="Bad request")
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None

        mock_session = AsyncMock()
        mock_session.post.return_value = mock_response
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None

        with patch("aiohttp.ClientSession", return_value=mock_session):
            with pytest.raises(Exception, match="Tool .* call failed"):
                await connector.test_tool_call("search_tracks", {"genre": "Rock"})


class TestGetConnector:
    """Test suite for singleton connector instance."""

    def test_get_connector_returns_instance(self):
        """Test get_connector returns MCPConnector instance."""
        # Clear singleton
        import src.ai_playlist.mcp_connector as module
        module._connector_instance = None

        with patch.dict('os.environ', {'SUBSONIC_MCP_URL': 'http://localhost:8080'}):
            connector = get_connector()

            assert isinstance(connector, MCPConnector)

    def test_get_connector_returns_same_instance(self):
        """Test get_connector returns singleton instance."""
        # Clear singleton
        import src.ai_playlist.mcp_connector as module
        module._connector_instance = None

        with patch.dict('os.environ', {'SUBSONIC_MCP_URL': 'http://localhost:8080'}):
            connector1 = get_connector()
            connector2 = get_connector()

            assert connector1 is connector2


@pytest.mark.asyncio
class TestConfigureAndVerifyMCP:
    """Test suite for configure_and_verify_mcp helper function."""

    async def test_configure_and_verify_success(self):
        """Test successful configuration and verification."""
        with patch.dict('os.environ', {'SUBSONIC_MCP_URL': 'http://localhost:8080'}):
            # Clear singleton
            import src.ai_playlist.mcp_connector as module
            module._connector_instance = None

            connector = get_connector()

            # Mock successful verification
            connector.verify_mcp_available = AsyncMock(return_value=True)
            connector.verify_required_tools = AsyncMock(return_value=True)

            config = await configure_and_verify_mcp()

            assert config["type"] == "hosted_mcp"
            assert config["hosted_mcp"]["server_url"] == "http://localhost:8080"

    async def test_configure_and_verify_server_unavailable(self):
        """Test raises exception when MCP server is unavailable."""
        with patch.dict('os.environ', {'SUBSONIC_MCP_URL': 'http://localhost:8080'}):
            # Clear singleton
            import src.ai_playlist.mcp_connector as module
            module._connector_instance = None

            connector = get_connector()

            # Mock failed verification
            connector.verify_mcp_available = AsyncMock(return_value=False)

            with pytest.raises(Exception, match="MCP server not available"):
                await configure_and_verify_mcp()

    async def test_configure_and_verify_missing_tools(self):
        """Test raises exception when required tools are missing."""
        with patch.dict('os.environ', {'SUBSONIC_MCP_URL': 'http://localhost:8080'}):
            # Clear singleton
            import src.ai_playlist.mcp_connector as module
            module._connector_instance = None

            connector = get_connector()

            # Mock server available but tools missing
            connector.verify_mcp_available = AsyncMock(return_value=True)
            connector.verify_required_tools = AsyncMock(return_value=False)

            with pytest.raises(Exception, match="Required MCP tools not available"):
                await configure_and_verify_mcp()
