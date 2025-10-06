"""Configuration models using Pydantic for validation and type safety."""

import os
import re
import tempfile
from pathlib import Path
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class TimeoutConfig(BaseModel):
    """Configuration for timeout settings."""
    
    inactivity_minutes: int = Field(
        default=10,
        description="Minutes of inactivity before terminating processes",
        ge=1,
        le=120
    )
    check_interval_seconds: int = Field(
        default=5,
        description="Seconds between activity checks",
        ge=1,
        le=60
    )
    merge_wait_minutes: int = Field(
        default=60,
        description="Minutes to wait for manual merge before auto-merge",
        ge=5,
        le=1440
    )


class LoggingConfig(BaseModel):
    """Configuration for logging settings."""
    
    level: str = Field(default="INFO", description="Log level")
    format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log format string"
    )
    file_path: Optional[Path] = Field(
        default=None,
        description="Optional file path for log output"
    )
    rich_console: bool = Field(
        default=True,
        description="Use Rich console for colored output"
    )
    structured: bool = Field(
        default=False,
        description="Use structured JSON logging"
    )

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        """Validate log level."""
        if not isinstance(v, str):
            raise ValueError("Log level must be a string")
        
        # Sanitize input
        clean_level = re.sub(r'[^A-Za-z]', '', v).upper()
        
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if clean_level not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return clean_level
    
    @field_validator("file_path")
    @classmethod 
    def validate_file_path(cls, v: Optional[Path]) -> Optional[Path]:
        """Validate and sanitize file path."""
        if v is None:
            return None
            
        # Convert to Path if string
        if isinstance(v, str):
            # Sanitize path - prevent directory traversal
            clean_path = re.sub(r'\.\./', '', str(v))
            v = Path(clean_path)
        
        # Security checks
        resolved_path = v.resolve()
        
        # Prevent writing outside allowed directories
        allowed_dirs = [
            Path.home() / ".local" / "share" / "github-automation",
            Path("/tmp") / "github-automation",
            Path.cwd() / "logs"
        ]
        
        if not any(str(resolved_path).startswith(str(allowed_dir)) for allowed_dir in allowed_dirs):
            # Create safe default in user's local share directory
            safe_dir = Path.home() / ".local" / "share" / "github-automation" / "logs"
            safe_dir.mkdir(parents=True, exist_ok=True)
            return safe_dir / "github-automation.log"
            
        return resolved_path


class ClaudeFlowConfig(BaseModel):
    """Configuration for Claude-Flow integration."""
    
    executable: str = Field(
        default="npx",
        description="Claude-Flow executable command"
    )
    package: str = Field(
        default="claude-flow@alpha",
        description="Claude-Flow package to use"
    )
    max_agents: int = Field(
        default=8,
        description="Maximum number of agents to spawn",
        ge=1,
        le=50
    )
    strategy: str = Field(
        default="hierarchical",
        description="Agent coordination strategy"
    )
    namespace_prefix: str = Field(
        default="github-automation",
        description="Namespace prefix for hive-mind sessions"
    )
    flags: List[str] = Field(
        default_factory=lambda: [
            "--auto-scale",
            "--auto-spawn", 
            "--claude",
            "--non-interactive",
            "--verbose"
        ],
        description="Additional flags for Claude-Flow"
    )

    @field_validator("strategy")
    @classmethod
    def validate_strategy(cls, v: str) -> str:
        """Validate coordination strategy."""
        if not isinstance(v, str):
            raise ValueError("Strategy must be a string")
            
        # Sanitize input
        clean_strategy = re.sub(r'[^a-zA-Z-]', '', v).lower()
        
        valid_strategies = ["hierarchical", "flat", "swarm", "adaptive"]
        if clean_strategy not in valid_strategies:
            raise ValueError(f"Invalid strategy: {v}. Must be one of {valid_strategies}")
        return clean_strategy
    
    @field_validator("executable")
    @classmethod
    def validate_executable(cls, v: str) -> str:
        """Validate executable command for security."""
        if not isinstance(v, str):
            raise ValueError("Executable must be a string")
            
        # Only allow known safe executables
        allowed_executables = ["npx", "node", "npm", "yarn", "pnpm"]
        clean_executable = re.sub(r'[^a-zA-Z0-9-_]', '', v)
        
        if clean_executable not in allowed_executables:
            raise ValueError(f"Executable '{v}' not allowed. Must be one of {allowed_executables}")
        return clean_executable
    
    @field_validator("package")
    @classmethod
    def validate_package(cls, v: str) -> str:
        """Validate package name for security."""
        if not isinstance(v, str):
            raise ValueError("Package must be a string")
            
        # Sanitize package name to prevent injection
        # Allow letters, numbers, hyphens, @, /, and dots (for scoped packages and versions)
        clean_package = re.sub(r'[^a-zA-Z0-9@/.,-]', '', v)
        
        # Basic validation for package name format
        if not re.match(r'^[@a-zA-Z0-9][a-zA-Z0-9@/.,-]*$', clean_package):
            raise ValueError(f"Invalid package name format: {v}")
            
        return clean_package


class GitHubConfig(BaseModel):
    """Configuration for GitHub integration."""
    
    repository: str = Field(
        description="GitHub repository in OWNER/REPO format"
    )
    hive_namespace: str = Field(
        default="github-automation",
        description="Namespace for hive-mind instances"
    )
    max_agents: int = Field(
        default=10,
        description="Maximum number of agents to spawn",
        ge=1,
        le=100
    )
    auto_merge: bool = Field(
        default=True,
        description="Enable auto-merge when GITHUB_USER_PAT is available"
    )
    dry_run: bool = Field(
        default=False,
        description="Run in dry-run mode without making changes"
    )
    merge_check_interval_minutes: int = Field(
        default=5,
        description="Minutes between merge status checks",
        ge=1,
        le=60
    )
    priority_labels: List[str] = Field(
        default_factory=lambda: ["critical", "high", "medium", "low"],
        description="Issue priority labels in order of importance"
    )
    require_tests: bool = Field(
        default=True,
        description="Require comprehensive tests for issue implementations"
    )


class Settings(BaseSettings):
    """Main settings class with environment variable support."""
    
    model_config = SettingsConfigDict(
        env_prefix="GITHUB_AUTOMATION_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Core settings
    project_root: Optional[Path] = Field(
        default=None,
        description="Project root directory (auto-detected if not provided)"
    )
    dry_run: bool = Field(
        default=False,
        description="Run in dry-run mode without making changes"
    )
    verbose: bool = Field(
        default=False,
        description="Enable verbose output"
    )
    
    # Component configurations
    timeout: TimeoutConfig = Field(default_factory=TimeoutConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    claude_flow: ClaudeFlowConfig = Field(default_factory=ClaudeFlowConfig)
    github: GitHubConfig = Field(default_factory=GitHubConfig)
    
    # Environment-specific settings
    github_user_pat: Optional[str] = Field(
        default=None,
        description="GitHub Personal Access Token for auto-merge"
    )
    
    @field_validator("project_root", mode="before")
    @classmethod
    def validate_project_root(cls, v) -> Path:
        """Auto-detect and validate project root."""
        if v is None:
            # Try to find project root by looking for .git directory
            current = Path.cwd()
            while current != current.parent:
                if (current / ".git").exists():
                    return current
                current = current.parent
            # Fallback to current directory
            return Path.cwd()
            
        # Convert string to Path
        if isinstance(v, str):
            # Sanitize path - prevent directory traversal
            clean_path = re.sub(r'\.\./', '', str(v))
            v = Path(clean_path)
        
        # Security validation
        if not isinstance(v, Path):
            raise ValueError("project_root must be a Path object or string")
            
        resolved_path = v.resolve()
        
        # Ensure path exists and is a directory
        if not resolved_path.exists():
            raise ValueError(f"Project root path does not exist: {resolved_path}")
        if not resolved_path.is_dir():
            raise ValueError(f"Project root must be a directory: {resolved_path}")
            
        return resolved_path
    
    @field_validator("github_user_pat")
    @classmethod
    def validate_github_pat(cls, v: Optional[str]) -> Optional[str]:
        """Validate GitHub Personal Access Token format."""
        if v is None:
            return None
            
        if not isinstance(v, str):
            raise ValueError("GitHub PAT must be a string")
            
        # Basic format validation for GitHub tokens
        if v.startswith('ghp_') and len(v) == 40:
            return v  # Classic PAT format
        elif v.startswith('github_pat_') and len(v) == 93:
            return v  # Fine-grained PAT format
        else:
            raise ValueError("Invalid GitHub Personal Access Token format")
    
    @model_validator(mode="after")
    def validate_paths_security(self) -> "Settings":
        """Additional security validation for path combinations."""
        # Ensure log directory is within safe bounds
        if self.logging.file_path:
            log_path = self.logging.file_path
            project_root = self.project_root or Path.cwd()
            
            # Don't allow log files outside project or safe system directories
            safe_dirs = [
                project_root,
                Path.home() / ".local" / "share" / "github-automation",
                Path("/tmp") / "github-automation"
            ]
            
            if not any(str(log_path).startswith(str(safe_dir)) for safe_dir in safe_dirs):
                # Force to safe location
                safe_dir = Path.home() / ".local" / "share" / "github-automation" / "logs"
                safe_dir.mkdir(parents=True, exist_ok=True)
                self.logging.file_path = safe_dir / "github-automation.log"
                
        return self
    
    def get_log_file_path(self, worker_type: str, identifier: str) -> Path:
        """Get secure log file path for a specific worker and identifier."""
        # Sanitize inputs
        clean_worker_type = re.sub(r'[^a-zA-Z0-9-_]', '', worker_type)
        clean_identifier = re.sub(r'[^a-zA-Z0-9-_]', '', identifier)
        
        if not clean_worker_type or not clean_identifier:
            raise ValueError("Invalid worker_type or identifier")
        
        # Use secure log directory
        log_dir = Path.home() / ".local" / "share" / "github-automation" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        return log_dir / f"github-{clean_worker_type}-{clean_identifier}.log"
    
    def get_temp_file_path(self, worker_type: str, identifier: str, suffix: str) -> Path:
        """Get secure temporary file path for worker artifacts."""
        # Sanitize inputs
        clean_worker_type = re.sub(r'[^a-zA-Z0-9-_]', '', worker_type)
        clean_identifier = re.sub(r'[^a-zA-Z0-9-_]', '', identifier)
        clean_suffix = re.sub(r'[^a-zA-Z0-9-_.]', '', suffix)
        
        if not clean_worker_type or not clean_identifier or not clean_suffix:
            raise ValueError("Invalid worker_type, identifier, or suffix")
        
        # Use secure temp directory within user space
        temp_dir = Path.home() / ".local" / "share" / "github-automation" / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        return temp_dir / f"github-{clean_worker_type}-{clean_identifier}-{clean_suffix}"
    
    def get_secure_temp_dir(self) -> Path:
        """Get secure temporary directory for this session."""
        # Create session-specific temp directory
        temp_base = Path.home() / ".local" / "share" / "github-automation" / "temp"
        session_dir = temp_base / f"session-{os.getpid()}"
        session_dir.mkdir(parents=True, exist_ok=True)
        return session_dir