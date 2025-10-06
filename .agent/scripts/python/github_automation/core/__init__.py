"""Core utilities and base classes for GitHub automation."""

from .exceptions import (
    GitHubAutomationError,
    ConfigurationError,
    ProcessError,
    GitError,
    ProcessTimeoutError,
)
from .logging_setup import setup_logging
from .git_utils import GitRepository
from .process_manager import ProcessManager

__all__ = [
    "GitHubAutomationError",
    "ConfigurationError",
    "ProcessError", 
    "GitError",
    "ProcessTimeoutError",
    "setup_logging",
    "GitRepository",
    "ProcessManager",
]