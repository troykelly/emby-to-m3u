"""Custom exceptions for GitHub automation scripts."""

import re
from typing import Optional, Any, Dict


class GitHubAutomationError(Exception):
    """Base exception for all GitHub automation errors."""
    
    # Sensitive patterns to redact from error messages
    _SENSITIVE_PATTERNS = [
        r'ghp_[a-zA-Z0-9]{36}',  # GitHub Personal Access Tokens
        r'github_pat_[a-zA-Z0-9_]{82}',  # GitHub PAT (new format)
        r'(?i)password["\s]*[:=]["\s]*[^\s"]+',  # Password fields
        r'(?i)token["\s]*[:=]["\s]*[^\s"]+',  # Token fields
        r'(?i)secret["\s]*[:=]["\s]*[^\s"]+',  # Secret fields
        r'(?i)api[_-]?key["\s]*[:=]["\s]*[^\s"]+',  # API keys
    ]
    
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(message)
        self.message = self._sanitize_message(message)
        self.details = self._sanitize_details(details or {})
        self.cause = cause
    
    def _sanitize_message(self, message: str) -> str:
        """Sanitize message to remove sensitive information."""
        if not isinstance(message, str):
            return str(message)
        
        sanitized = message
        for pattern in self._SENSITIVE_PATTERNS:
            sanitized = re.sub(pattern, '[REDACTED]', sanitized, flags=re.IGNORECASE)
        return sanitized
    
    def _sanitize_details(self, details: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize details dictionary to remove sensitive information."""
        sanitized = {}
        for key, value in details.items():
            if isinstance(value, str):
                sanitized[key] = self._sanitize_message(value)
            elif key.lower() in ('password', 'token', 'secret', 'api_key', 'pat'):
                sanitized[key] = '[REDACTED]'
            else:
                sanitized[key] = value
        return sanitized
    
    def __str__(self) -> str:
        """Return formatted error message."""
        base_msg = self.message
        if self.details:
            # Only include non-sensitive details in string representation
            safe_details = {k: v for k, v in self.details.items() if v != '[REDACTED]'}
            if safe_details:
                details_str = ", ".join(f"{k}={v}" for k, v in safe_details.items())
                base_msg += f" (Details: {details_str})"
        if self.cause:
            base_msg += f" (Caused by: {self.cause})"
        return base_msg


class ConfigurationError(GitHubAutomationError):
    """Raised when there are configuration-related errors."""
    pass


class ProcessError(GitHubAutomationError):
    """Raised when subprocess operations fail."""
    
    def __init__(
        self,
        message: str,
        command: Optional[str] = None,
        exit_code: Optional[int] = None,
        stdout: Optional[str] = None,
        stderr: Optional[str] = None,
        **kwargs
    ):
        details = {
            "command": command,
            "exit_code": exit_code,
            "stdout": self._truncate_output(stdout),
            "stderr": self._truncate_output(stderr),
        }
        # Remove None values
        details = {k: v for k, v in details.items() if v is not None}
        super().__init__(message, details, **kwargs)
    
    @staticmethod
    def _truncate_output(output: Optional[str], max_length: int = 500) -> Optional[str]:
        """Truncate long output for readability."""
        if not output:
            return output
        if len(output) > max_length:
            return output[:max_length] + f"... (truncated, {len(output)} total chars)"
        return output


class GitError(GitHubAutomationError):
    """Raised when Git operations fail."""
    
    def __init__(
        self,
        message: str,
        repository_path: Optional[str] = None,
        git_command: Optional[str] = None,
        **kwargs
    ):
        details = {
            "repository_path": repository_path,
            "git_command": git_command,
        }
        # Remove None values
        details = {k: v for k, v in details.items() if v is not None}
        super().__init__(message, details, **kwargs)


class ProcessTimeoutError(GitHubAutomationError):
    """Raised when operations timeout. Renamed to avoid collision with built-in TimeoutError."""
    
    def __init__(
        self,
        message: str,
        timeout_seconds: Optional[int] = None,
        operation: Optional[str] = None,
        **kwargs
    ):
        details = {
            "timeout_seconds": timeout_seconds,
            "operation": operation,
        }
        # Remove None values
        details = {k: v for k, v in details.items() if v is not None}
        super().__init__(message, details, **kwargs)


class GitHubAPIError(GitHubAutomationError):
    """Raised when GitHub API operations fail."""
    
    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_body: Optional[str] = None,
        endpoint: Optional[str] = None,
        **kwargs
    ):
        details = {
            "status_code": status_code,
            "endpoint": endpoint,
            "response_body": response_body[:500] + "..." if response_body and len(response_body) > 500 else response_body,
        }
        # Remove None values
        details = {k: v for k, v in details.items() if v is not None}
        super().__init__(message, details, **kwargs)


class ClaudeFlowError(GitHubAutomationError):
    """Raised when Claude-Flow operations fail."""
    
    def __init__(
        self,
        message: str,
        hive_mind_id: Optional[str] = None,
        session_id: Optional[str] = None,
        objective: Optional[str] = None,
        **kwargs
    ):
        details = {
            "hive_mind_id": hive_mind_id,
            "session_id": session_id,
            "objective": objective[:200] + "..." if objective and len(objective) > 200 else objective,
        }
        # Remove None values
        details = {k: v for k, v in details.items() if v is not None}
        super().__init__(message, details, **kwargs)


class WorkflowError(GitHubAutomationError):
    """Raised when workflow operations fail."""
    pass