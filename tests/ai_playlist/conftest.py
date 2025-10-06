"""Configuration for AI playlist tests."""
import sys
from pathlib import Path

# Add project root to Python path so that 'src' prefix works
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
