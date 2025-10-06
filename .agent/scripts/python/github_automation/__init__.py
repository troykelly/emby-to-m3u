"""
GitHub Automation Scripts with Claude-Flow Integration.

Best-in-class Python automation scripts for GitHub PR and Issue processing
with intelligent timeout, real-time log interpretation, and robust error handling.
"""

__version__ = "1.0.0"
__author__ = "Aperim Template"
__email__ = "automation@aperim.com"

from .config.models import Settings, GitHubConfig
from .core.exceptions import (
    GitHubAutomationError,
    ConfigurationError,
    ProcessError,
    GitError,
    ProcessTimeoutError,
    WorkflowError,
    GitHubAPIError,
    ClaudeFlowError,
)

__all__ = [
    "Settings",
    "GitHubConfig",
    "GitHubAutomationError",
    "ConfigurationError", 
    "ProcessError",
    "GitError",
    "ProcessTimeoutError",
    "WorkflowError",
    "GitHubAPIError",
    "ClaudeFlowError",
]