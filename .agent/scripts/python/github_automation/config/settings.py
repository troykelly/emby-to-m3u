"""Settings loader and configuration management."""

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

from .models import Settings


@lru_cache()
def get_settings(config_file: Optional[Path] = None) -> Settings:
    """
    Get application settings with caching and security validation.
    
    Args:
        config_file: Optional path to configuration file
        
    Returns:
        Settings instance with loaded configuration
        
    Raises:
        ValueError: If config file path is invalid or insecure
    """
    # Validate config file path for security
    if config_file is not None:
        if isinstance(config_file, str):
            # Sanitize string path
            clean_path = re.sub(r'\.\./', '', config_file)
            config_file = Path(clean_path)
        
        if not isinstance(config_file, Path):
            raise ValueError("config_file must be a Path object or string")
            
        # Resolve and validate the path
        try:
            resolved_path = config_file.resolve()
        except (OSError, RuntimeError) as e:
            raise ValueError(f"Invalid config file path: {e}")
        
        # Security check - prevent access outside allowed directories
        allowed_dirs = [
            Path.cwd(),
            Path.home() / ".config" / "github-automation",
            Path.home() / ".local" / "share" / "github-automation"
        ]
        
        if not any(str(resolved_path).startswith(str(allowed_dir)) for allowed_dir in allowed_dirs):
            raise ValueError(f"Config file path not in allowed directories: {resolved_path}")
        
        # Check if file exists and is readable
        if not resolved_path.exists():
            raise ValueError(f"Config file does not exist: {resolved_path}")
        if not resolved_path.is_file():
            raise ValueError(f"Config path is not a file: {resolved_path}")
        
        # Set environment file securely
        os.environ.setdefault("GITHUB_AUTOMATION_ENV_FILE", str(resolved_path))
    
    return Settings()


def reload_settings() -> Settings:
    """
    Reload settings by clearing cache and re-creating.
    
    Returns:
        Fresh Settings instance
    """
    get_settings.cache_clear()
    return get_settings()