"""Test suite for Subsonic MCP Server.

This test package validates the MCP server implementation with comprehensive coverage:
    - Contract tests: Validate tools, resources, and prompts against JSON schemas
    - Integration tests: Verify MCP protocol compliance and end-to-end workflows
    - Cache tests: Validate TTL expiration and dynamic throttling logic
    - Error handling tests: Ensure graceful degradation and user-friendly messages

All tests use mocked SubsonicClient to avoid dependency on real Subsonic servers.
Target coverage: 80%+ (stretch goal: 90%)
"""
