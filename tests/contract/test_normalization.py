"""Contract tests for normalization functions (T004-T006)."""
import pytest
from src.azuracast.normalization import normalize_string, normalize_artist, build_track_fingerprint

class TestNormalizeString:
    def test_basic(self):
        assert normalize_string("  Test  ") == "test"
