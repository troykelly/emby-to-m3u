"""Custom exceptions for AI Playlist module."""


class ParseError(Exception):
    """Raised when document parsing fails."""

    pass


class ValidationError(ValueError):
    """Raised when validation constraints are violated."""

    pass


class APIError(Exception):
    """Raised when OpenAI API fails."""

    pass


class CostExceededError(Exception):
    """Raised when estimated LLM cost exceeds budget."""

    pass


class MCPToolError(Exception):
    """Raised when MCP tool is unavailable or fails."""

    pass
