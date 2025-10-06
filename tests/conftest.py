"""
Pytest configuration for emby-to-m3u test suite.

This module configures the Python path to ensure test files can import
from the src directory properly.
"""
import sys
from pathlib import Path

# Add project root to Python path so tests can import from src
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Also add src directory explicitly for both import styles
src_dir = project_root / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))
