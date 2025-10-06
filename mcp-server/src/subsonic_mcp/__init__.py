"""Subsonic MCP Server - Model Context Protocol integration for Subsonic music libraries.

This package provides a Model Context Protocol (MCP) server that exposes Subsonic/OpenSubsonic
music libraries to LLM applications like Claude Desktop, enabling AI-powered playlist generation
and music discovery.

Components:
    - server.py: Main MCP server class with stdio transport
    - tools.py: 10 MCP tools for music operations (search, analyze, stream)
    - resources.py: 6 MCP resources for library exploration
    - prompts.py: 5 MCP prompts for common music workflows
    - cache.py: In-memory caching with TTL and dynamic throttling
    - utils.py: Error handling and utility functions
"""

__version__ = "0.1.0"
