"""
Configuration for contract tests.

Provides common fixtures and utilities for OpenAPI contract validation.
"""
import sys
from pathlib import Path
import pytest

# Add project root to Python path so that 'src' prefix works
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture(scope="session")
def contracts_dir():
    """Path to OpenAPI contract specifications"""
    return Path("/workspaces/emby-to-m3u/specs/005-refactor-core-playlist/contracts")


@pytest.fixture(scope="session")
def base_url():
    """Base URL for API testing"""
    return "http://localhost:8000/api/v1"


def pytest_configure(config):
    """Register custom markers for contract tests"""
    config.addinivalue_line(
        "markers",
        "contract: OpenAPI contract validation tests (expected to fail in TDD RED phase)"
    )
