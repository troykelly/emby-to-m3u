"""Integration tests for CacheManager TTL and throttling behavior.

Tests validate cache expiration logic and dynamic throttling based on
server response times.
"""

import pytest
import asyncio
from subsonic_mcp.cache import CacheManager


@pytest.mark.asyncio
async def test_cache_ttl_expiration():
    """Verify TTL expiration removes cached entries after timeout."""
    cache = CacheManager(default_ttl=300)

    # Set cache entry with 2-second TTL
    await cache.set("test_key", "test_data", ttl=2)

    # Immediately after: cache hit
    result = await cache.get("test_key")
    assert result == "test_data"

    # After 3 seconds: cache miss (expired)
    await asyncio.sleep(3)
    result = await cache.get("test_key")
    assert result is None


@pytest.mark.asyncio
async def test_cache_default_ttl():
    """Verify default TTL is used when no TTL specified."""
    cache = CacheManager(default_ttl=5)

    # Set without explicit TTL
    await cache.set("key1", "value1")

    # Should exist initially
    assert await cache.get("key1") == "value1"

    # After 6 seconds: should be expired
    await asyncio.sleep(6)
    assert await cache.get("key1") is None


@pytest.mark.asyncio
async def test_cache_nonexistent_key():
    """Verify getting nonexistent key returns None."""
    cache = CacheManager()

    result = await cache.get("nonexistent_key")
    assert result is None


@pytest.mark.asyncio
async def test_cache_update_overwrites():
    """Verify updating existing key overwrites old value."""
    cache = CacheManager(default_ttl=300)

    # Set initial value
    await cache.set("key", "old_value")
    assert await cache.get("key") == "old_value"

    # Update with new value
    await cache.set("key", "new_value")
    assert await cache.get("key") == "new_value"


@pytest.mark.asyncio
async def test_dynamic_throttling_not_triggered():
    """Verify throttling NOT triggered when avg response time < 2s."""
    cache = CacheManager()

    # Add fast responses (< 2s average)
    for _ in range(15):
        cache.update_response_time(0.5)

    # Should not throttle
    assert cache.should_throttle() is False


@pytest.mark.asyncio
async def test_dynamic_throttling_triggered():
    """Verify throttling kicks in when avg response time > 2s."""
    cache = CacheManager()

    # Add slow responses (> 2s average)
    for _ in range(15):
        cache.update_response_time(3.0)

    # Should throttle
    assert cache.should_throttle() is True


@pytest.mark.asyncio
async def test_throttling_requires_minimum_samples():
    """Verify throttling requires at least 10 samples."""
    cache = CacheManager()

    # Add only 5 slow responses (< 10 minimum)
    for _ in range(5):
        cache.update_response_time(5.0)

    # Should NOT throttle (insufficient samples)
    assert cache.should_throttle() is False

    # Add 5 more (now 10 total)
    for _ in range(5):
        cache.update_response_time(5.0)

    # Now should throttle
    assert cache.should_throttle() is True


@pytest.mark.asyncio
async def test_response_time_rolling_window():
    """Verify response times use rolling window (max 100)."""
    cache = CacheManager()

    # Add 100 fast responses
    for _ in range(100):
        cache.update_response_time(0.5)

    assert cache.should_throttle() is False

    # Add 100 slow responses (should push out fast ones)
    for _ in range(100):
        cache.update_response_time(3.0)

    # Now should throttle (only slow responses in window)
    assert cache.should_throttle() is True


@pytest.mark.asyncio
async def test_cache_stats():
    """Verify get_cache_stats returns correct information."""
    cache = CacheManager(default_ttl=300)

    # Add some entries
    await cache.set("key1", "value1")
    await cache.set("key2", "value2")
    await cache.set("key3", "value3", ttl=1)

    # Wait for one to expire
    await asyncio.sleep(2)

    stats = cache.get_cache_stats()

    assert stats["cached_items"] == 3  # Total entries (including expired)
    assert stats["expired_items"] == 1  # One expired
    assert "should_throttle" in stats


@pytest.mark.asyncio
async def test_cache_clear():
    """Verify clear() removes all cache entries."""
    cache = CacheManager()

    # Add entries
    await cache.set("key1", "value1")
    await cache.set("key2", "value2")

    # Verify entries exist
    assert await cache.get("key1") == "value1"
    assert await cache.get("key2") == "value2"

    # Clear cache
    cache.clear()

    # Verify entries removed
    assert await cache.get("key1") is None
    assert await cache.get("key2") is None
