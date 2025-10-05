"""Contract tests for upload decision (T010-T011)."""
import time
import pytest

from src.azuracast.cache import should_skip_replaygain_conflict, get_cached_known_tracks

class TestReplayGain:
    def test_skip_conflict(self):
        az = {"id": "1", "replaygain_track_gain": -3.0}
        src = {"Name": "Song"}
        assert should_skip_replaygain_conflict(az, src) == True


class TestGetCachedKnownTracks:
    """Contract tests for get_cached_known_tracks() function (T011)."""

    def test_first_call_fetches_from_api(self):
        """First call should fetch from API (cache miss)."""
        call_count = 0

        def mock_fetch():
            nonlocal call_count
            call_count += 1
            return [{"id": "1", "title": "Song 1"}]

        # Import fresh to reset cache
        import importlib
        from src.azuracast import cache
        importlib.reload(cache)

        tracks = cache.get_cached_known_tracks(mock_fetch)

        assert len(tracks) == 1
        assert tracks[0]["id"] == "1"
        assert call_count == 1

    def test_second_call_within_ttl_returns_cached(self):
        """Second call within TTL should return cached data (cache hit)."""
        call_count = 0

        def mock_fetch():
            nonlocal call_count
            call_count += 1
            return [{"id": "2", "title": "Song 2"}]

        # Import fresh to reset cache
        import importlib
        from src.azuracast import cache
        importlib.reload(cache)

        # First call
        tracks1 = cache.get_cached_known_tracks(mock_fetch)
        assert call_count == 1

        # Second call (should be cached)
        tracks2 = cache.get_cached_known_tracks(mock_fetch)
        assert call_count == 1  # Should not call fetch again
        assert tracks1 == tracks2

    def test_call_after_ttl_expiry_refetches(self):
        """Call after TTL expiry should re-fetch from API."""
        call_count = 0

        def mock_fetch():
            nonlocal call_count
            call_count += 1
            return [{"id": "3", "title": "Song 3"}]

        # Import fresh to reset cache
        import importlib
        from src.azuracast import cache
        importlib.reload(cache)

        # Set very short TTL
        cache._known_tracks_cache.ttl_seconds = 0.1

        # First call
        cache.get_cached_known_tracks(mock_fetch)
        assert call_count == 1

        # Wait for expiry
        time.sleep(0.2)

        # Should re-fetch
        cache.get_cached_known_tracks(mock_fetch)
        assert call_count == 2

    def test_cache_invalidation(self):
        """Cache invalidation should force re-fetch."""
        call_count = 0

        def mock_fetch():
            nonlocal call_count
            call_count += 1
            return [{"id": "4", "title": "Song 4"}]

        # Import fresh to reset cache
        import importlib
        from src.azuracast import cache
        importlib.reload(cache)

        # First call
        cache.get_cached_known_tracks(mock_fetch)
        assert call_count == 1

        # Invalidate cache
        cache._known_tracks_cache.invalidate()

        # Should re-fetch
        cache.get_cached_known_tracks(mock_fetch)
        assert call_count == 2

    def test_force_refresh(self):
        """Force refresh should bypass cache."""
        call_count = 0

        def mock_fetch():
            nonlocal call_count
            call_count += 1
            return [{"id": "5", "title": "Song 5"}]

        # Import fresh to reset cache
        import importlib
        from src.azuracast import cache
        importlib.reload(cache)

        # First call
        cache.get_cached_known_tracks(mock_fetch)
        assert call_count == 1

        # Force refresh
        cache.get_cached_known_tracks(mock_fetch, force_refresh=True)
        assert call_count == 2
