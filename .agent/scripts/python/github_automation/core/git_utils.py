"""Git repository utilities and GitHub integration."""

import os
import re
import shlex
import subprocess
import time
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List
from dataclasses import dataclass

try:
    from git import Repo, InvalidGitRepositoryError
except ImportError as e:
    raise ImportError(f"GitPython not installed: {e}. Install with: pip install GitPython")

from rich.console import Console

from .exceptions import GitError, GitHubAPIError, ConfigurationError, ProcessError
from .logging_setup import get_logger


@dataclass
class RepositoryInfo:
    """Repository information extracted from git remote."""
    
    owner: str
    name: str
    full_name: str
    remote_url: str
    local_path: Path
    
    @property
    def github_url(self) -> str:
        """Get GitHub web URL."""
        return f"https://github.com/{self.full_name}"


class GitRepository:
    """Git repository operations and GitHub integration."""
    
    def __init__(self, repo_path: Optional[Path] = None):
        """
        Initialize Git repository handler.
        
        Args:
            repo_path: Optional path to repository (auto-detected if not provided)
            
        Raises:
            ValueError: If repo_path is invalid or insecure
        """
        self.logger = get_logger(__name__)
        self.console = Console()
        self._repo_path = self._validate_repo_path(repo_path)
        self._repo: Optional[Repo] = None
        self._repo_info: Optional[RepositoryInfo] = None
    
    def _validate_repo_path(self, repo_path: Optional[Path]) -> Optional[Path]:
        """
        Validate repository path for security.
        
        Args:
            repo_path: Path to validate
            
        Returns:
            Validated path or None
            
        Raises:
            ValueError: If path is invalid or insecure
        """
        if repo_path is None:
            return None
            
        # Convert string to Path if necessary
        if isinstance(repo_path, str):
            # Sanitize path - prevent directory traversal
            clean_path = re.sub(r'\.\./', '', repo_path)
            repo_path = Path(clean_path)
        
        if not isinstance(repo_path, Path):
            raise ValueError("repo_path must be a Path object or string")
        
        try:
            # Resolve path to absolute form
            resolved_path = repo_path.resolve()
        except (OSError, RuntimeError) as e:
            raise ValueError(f"Invalid repository path: {e}")
        
        # Security check - ensure path exists and is a directory
        if not resolved_path.exists():
            raise ValueError(f"Repository path does not exist: {resolved_path}")
        if not resolved_path.is_dir():
            raise ValueError(f"Repository path is not a directory: {resolved_path}")
        
        return resolved_path
    
    @property
    def repo_path(self) -> Path:
        """Get repository path, auto-detecting if necessary."""
        if self._repo_path is None:
            self._repo_path = self._find_repository_root()
        return self._repo_path
    
    @property
    def repo(self) -> Repo:
        """Get GitPython repository object."""
        if self._repo is None:
            try:
                self._repo = Repo(self.repo_path)
            except InvalidGitRepositoryError as e:
                raise GitError(
                    f"Invalid Git repository at {self.repo_path}",
                    repository_path=str(self.repo_path),
                    cause=e
                )
        return self._repo
    
    @property
    def info(self) -> RepositoryInfo:
        """Get repository information."""
        if self._repo_info is None:
            self._repo_info = self._extract_repository_info()
        return self._repo_info
    
    def _find_repository_root(self) -> Path:
        """Find Git repository root by walking up directory tree safely."""
        try:
            current = Path.cwd().resolve()
        except (OSError, RuntimeError) as e:
            raise GitError(f"Cannot determine current directory: {e}")
        
        # Limit traversal to prevent infinite loops and directory traversal attacks
        max_depth = 50
        depth = 0
        
        while current != current.parent and depth < max_depth:
            try:
                git_dir = current / ".git"
                if git_dir.exists() and (git_dir.is_dir() or git_dir.is_file()):
                    self.logger.debug(f"Found Git repository at {current}")
                    return current
            except (PermissionError, OSError):
                # Skip directories we can't access
                pass
            
            current = current.parent
            depth += 1
        
        raise GitError(
            "No Git repository found in current directory or parent directories",
            repository_path=str(Path.cwd())
        )
    
    def _extract_repository_info(self) -> RepositoryInfo:
        """Extract repository information from git remote safely."""
        try:
            # Get origin remote URL with safety checks
            if 'origin' not in [remote.name for remote in self.repo.remotes]:
                raise GitError(
                    "No 'origin' remote found in repository",
                    repository_path=str(self.repo_path)
                )
            
            origin = self.repo.remote('origin')
            remote_urls = list(origin.urls)
            
            if not remote_urls:
                raise GitError(
                    "No URLs found for 'origin' remote",
                    repository_path=str(self.repo_path)
                )
            
            remote_url = remote_urls[0]
            
            # Sanitize remote URL for logging (remove sensitive info)
            safe_url = re.sub(r'://[^@]*@', '://***@', remote_url)
            self.logger.debug(f"Remote URL: {safe_url}")
            
            # Validate that this is a GitHub URL for security
            if not self._is_valid_github_url(remote_url):
                raise GitError(
                    f"Remote URL is not a valid GitHub repository: {safe_url}",
                    repository_path=str(self.repo_path)
                )
            
            # Parse GitHub repository from various URL formats
            patterns = [
                r'github\.com[:/]([a-zA-Z0-9][a-zA-Z0-9\-]*[a-zA-Z0-9])/([a-zA-Z0-9][a-zA-Z0-9\-_.]*[a-zA-Z0-9])(?:\.git)?/?$',
                r'git@github\.com:([a-zA-Z0-9][a-zA-Z0-9\-]*[a-zA-Z0-9])/([a-zA-Z0-9][a-zA-Z0-9\-_.]*[a-zA-Z0-9])(?:\.git)?/?$',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, remote_url)
                if match:
                    owner, name = match.groups()
                    
                    # Additional validation of owner/name
                    if not self._is_valid_github_identifier(owner):
                        raise GitError(f"Invalid GitHub owner name: {owner}")
                    if not self._is_valid_github_identifier(name):
                        raise GitError(f"Invalid GitHub repository name: {name}")
                    
                    name = name.rstrip('.git')  # Remove .git suffix if present
                    
                    repo_info = RepositoryInfo(
                        owner=owner,
                        name=name,
                        full_name=f"{owner}/{name}",
                        remote_url=remote_url,
                        local_path=self.repo_path
                    )
                    
                    self.logger.info(f"Detected repository: {repo_info.full_name}")
                    return repo_info
            
            raise GitError(
                f"Could not parse GitHub repository from remote URL: {safe_url}",
                repository_path=str(self.repo_path),
                git_command="git remote get-url origin"
            )
            
        except Exception as e:
            if isinstance(e, GitError):
                raise
            raise GitError(
                "Failed to extract repository information",
                repository_path=str(self.repo_path),
                cause=e
            )
    
    def _is_valid_github_url(self, url: str) -> bool:
        """Validate that URL is a legitimate GitHub URL."""
        if not isinstance(url, str):
            return False
        
        # Check for GitHub domain
        github_patterns = [
            r'https?://github\.com/',
            r'git@github\.com:',
            r'ssh://git@github\.com/',
        ]
        
        return any(re.match(pattern, url) for pattern in github_patterns)
    
    def _is_valid_github_identifier(self, identifier: str) -> bool:
        """Validate GitHub username/repository name format."""
        if not isinstance(identifier, str):
            return False
        
        # GitHub username/repo rules: alphanumeric and hyphens, can't start/end with hyphen
        if len(identifier) < 1 or len(identifier) > 39:
            return False
        
        if identifier.startswith('-') or identifier.endswith('-'):
            return False
        
        return re.match(r'^[a-zA-Z0-9][a-zA-Z0-9\-]*[a-zA-Z0-9]$|^[a-zA-Z0-9]$', identifier) is not None
    
    def check_github_cli(self) -> bool:
        """
        Check if GitHub CLI is installed and authenticated securely.
        
        Returns:
            True if GitHub CLI is available and authenticated
        """
        try:
            # Check if gh command exists with secure execution
            result = self._run_secure_command(
                ["gh", "--version"],
                timeout=10,
                description="GitHub CLI version check"
            )
            
            if result.returncode != 0:
                self.logger.warning("GitHub CLI (gh) is not installed")
                return False
            
            # Check authentication
            result = self._run_secure_command(
                ["gh", "auth", "status"],
                timeout=10,
                description="GitHub CLI auth status"
            )
            
            if result.returncode != 0:
                self.logger.warning("GitHub CLI is not authenticated. Run 'gh auth login'")
                return False
            
            self.logger.debug("GitHub CLI is installed and authenticated")
            return True
            
        except subprocess.TimeoutExpired:
            self.logger.error("GitHub CLI check timed out")
            return False
        except FileNotFoundError:
            self.logger.warning("GitHub CLI (gh) command not found")
            return False
        except Exception as e:
            self.logger.error(f"Failed to check GitHub CLI: {e}")
            return False
    
    def _run_secure_command(
        self, 
        command: List[str], 
        timeout: int = 30,
        description: str = "command"
    ) -> subprocess.CompletedProcess:
        """
        Run a command securely with validation and timeout.
        
        Args:
            command: Command and arguments to run
            timeout: Timeout in seconds
            description: Description for logging
            
        Returns:
            CompletedProcess result
            
        Raises:
            ProcessError: If command execution fails
            ValueError: If command is invalid
        """
        if not command or not isinstance(command, list):
            raise ValueError("Command must be a non-empty list")
        
        # Validate command name (no path traversal)
        cmd_name = command[0]
        if not isinstance(cmd_name, str) or '/' in cmd_name or '\\' in cmd_name:
            raise ValueError(f"Invalid command name: {cmd_name}")
        
        # Whitelist allowed commands for security
        allowed_commands = {'gh', 'git'}
        if cmd_name not in allowed_commands:
            raise ValueError(f"Command '{cmd_name}' not allowed")
        
        # Sanitize arguments
        clean_args = []
        for arg in command:
            if not isinstance(arg, str):
                raise ValueError(f"Command argument must be string: {arg}")
            # Basic sanitization - no shell metacharacters
            if re.search(r'[;&|`$(){}[\]<>]', arg):
                raise ValueError(f"Command argument contains unsafe characters: {arg}")
            clean_args.append(arg)
        
        self.logger.debug(f"Running {description}: {' '.join(clean_args)}")
        
        try:
            result = subprocess.run(
                clean_args,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self.repo_path,
                env=dict(os.environ),  # Clean environment copy
                check=False  # Don't raise on non-zero exit
            )
            
            return result
            
        except subprocess.TimeoutExpired as e:
            raise ProcessError(
                f"Command '{description}' timed out after {timeout} seconds",
                command=' '.join(clean_args),
                exit_code=None,
                cause=e
            )
        except Exception as e:
            raise ProcessError(
                f"Failed to execute {description}",
                command=' '.join(clean_args),
                cause=e
            )
    
    def get_pr_status(self, pr_number: int) -> Dict[str, Any]:
        """
        Get PR status information using GitHub CLI.
        
        Args:
            pr_number: Pull request number
            
        Returns:
            Dictionary with PR status information
        """
        try:
            cmd = [
                "gh", "pr", "view", str(pr_number),
                "--repo", self.info.full_name,
                "--json", "state,mergeable,statusCheckRollup,mergeStateStatus,title,url"
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=self.repo_path
            )
            
            if result.returncode != 0:
                raise GitHubAPIError(
                    f"Failed to get PR #{pr_number} status",
                    endpoint=f"pr view {pr_number}",
                    response_body=result.stderr
                )
            
            import json
            pr_data = json.loads(result.stdout)
            
            # Analyze CI status
            failed_checks = 0
            if pr_data.get('statusCheckRollup'):
                for check in pr_data['statusCheckRollup']:
                    if check.get('conclusion') in ['FAILURE', 'CANCELLED', 'TIMED_OUT', 'ACTION_REQUIRED']:
                        failed_checks += 1
            
            # Determine if ready to merge
            is_ready = (
                pr_data.get('state') == 'OPEN' and
                pr_data.get('mergeable') == 'MERGEABLE' and
                failed_checks == 0
            )
            
            return {
                'number': pr_number,
                'state': pr_data.get('state', 'UNKNOWN'),
                'mergeable': pr_data.get('mergeable', 'UNKNOWN'),
                'merge_state_status': pr_data.get('mergeStateStatus', 'UNKNOWN'),
                'title': pr_data.get('title', ''),
                'url': pr_data.get('url', ''),
                'failed_checks': failed_checks,
                'is_ready_to_merge': is_ready,
                'raw_data': pr_data
            }
            
        except subprocess.TimeoutExpired:
            raise GitHubAPIError(
                f"Timeout getting PR #{pr_number} status",
                endpoint=f"pr view {pr_number}"
            )
        except Exception as e:
            if isinstance(e, GitHubAPIError):
                raise
            raise GitHubAPIError(
                f"Failed to get PR #{pr_number} status",
                endpoint=f"pr view {pr_number}",
                cause=e
            )
    
    def get_open_prs(self) -> List[int]:
        """
        Get list of open PR numbers sorted by creation date (oldest first).
        
        Returns:
            List of PR numbers
        """
        try:
            cmd = [
                "gh", "pr", "list",
                "--repo", self.info.full_name,
                "--state", "open",
                "--json", "number,createdAt",
                "--jq", "sort_by(.createdAt) | .[].number"
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=self.repo_path
            )
            
            if result.returncode != 0:
                raise GitHubAPIError(
                    "Failed to get open PRs",
                    endpoint="pr list",
                    response_body=result.stderr
                )
            
            pr_numbers = []
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    try:
                        pr_numbers.append(int(line.strip()))
                    except ValueError:
                        self.logger.warning(f"Invalid PR number: {line}")
            
            self.logger.info(f"Found {len(pr_numbers)} open PRs")
            return pr_numbers
            
        except subprocess.TimeoutExpired:
            raise GitHubAPIError("Timeout getting open PRs", endpoint="pr list")
        except Exception as e:
            if isinstance(e, GitHubAPIError):
                raise
            raise GitHubAPIError("Failed to get open PRs", endpoint="pr list", cause=e)
    
    def get_priority_issue(self, priority_labels: list[str]) -> Optional[int]:
        """
        Get highest priority open issue.
        
        Args:
            priority_labels: List of priority labels in order of importance
            
        Returns:
            Issue number or None if no issues found
        """
        try:
            # Try each priority level
            for priority in priority_labels:
                cmd = [
                    "gh", "issue", "list",
                    "--repo", self.info.full_name,
                    "--state", "open",
                    "--label", priority,
                    "--json", "number",
                    "--jq", ".[0].number"
                ]
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    cwd=self.repo_path
                )
                
                if result.returncode == 0 and result.stdout.strip() and result.stdout.strip() != "null":
                    issue_number = int(result.stdout.strip())
                    self.logger.info(f"Found {priority} priority issue #{issue_number}")
                    return issue_number
            
            # If no priority issues, get oldest open issue
            cmd = [
                "gh", "issue", "list",
                "--repo", self.info.full_name,
                "--state", "open",
                "--json", "number,createdAt",
                "--jq", "sort_by(.createdAt) | .[0].number"
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=self.repo_path
            )
            
            if result.returncode == 0 and result.stdout.strip() and result.stdout.strip() != "null":
                issue_number = int(result.stdout.strip())
                self.logger.info(f"Found oldest open issue #{issue_number}")
                return issue_number
            
            self.logger.info("No open issues found")
            return None
            
        except subprocess.TimeoutExpired:
            raise GitHubAPIError("Timeout getting priority issue", endpoint="issue list")
        except Exception as e:
            if isinstance(e, GitHubAPIError):
                raise
            raise GitHubAPIError("Failed to get priority issue", endpoint="issue list", cause=e)