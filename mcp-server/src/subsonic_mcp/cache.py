"""In-memory caching with TTL expiration and dynamic throttling logic.

This module provides CacheManager for caching Subsonic API responses to reduce
server load and improve performance. Features:
    - Configurable TTL (default 5 minutes)
    - Automatic expiration checking
    - Dynamic throttling based on server response times
    - Response time tracking with rolling average
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from collections import deque


@dataclass
class CacheEntry:
    """Cache entry with data, timestamp, and TTL.

    Attributes:
        data: Cached data (any JSON-serializable type)
        timestamp: When entry was created
        ttl_seconds: Time to live in seconds (default 300 = 5 minutes)
    """

    data: Any
    timestamp: datetime
    ttl_seconds: int = 300

    def is_expired(self) -> bool:
        """Check if cache entry has expired.

        Returns:
            bool: True if (now - timestamp) >= ttl_seconds
        """
        age = (datetime.now() - self.timestamp).total_seconds()
        return age >= self.ttl_seconds


class CacheManager:
    """In-memory cache with TTL and dynamic throttling.

    Provides caching for Subsonic API responses with configurable TTL
    and automatic throttling when server response times degrade.

    Attributes:
        cache: Dictionary of cache keys to CacheEntry objects
        default_ttl: Default TTL in seconds (5 minutes)
        response_times: Rolling window of last 100 response times
    """

    def __init__(self, default_ttl: int = 300):
        """Initialize cache manager.

        Args:
            default_ttl: Default TTL in seconds (default: 300 = 5 minutes)
        """
        self.cache: Dict[str, CacheEntry] = {}
        self.default_ttl = default_ttl
        self.response_times: deque[float] = deque(maxlen=100)

    async def get(self, key: str) -> Optional[Any]:
        """Retrieve cached data if not expired.

        Args:
            key: Cache key

        Returns:
            Cached data if exists and not expired, else None
        """
        if key not in self.cache:
            return None

        entry = self.cache[key]

        # Check expiration
        if entry.is_expired():
            # Remove expired entry
            del self.cache[key]
            return None

        return entry.data

    async def set(self, key: str, data: Any, ttl: Optional[int] = None):
        """Store data in cache with TTL.

        Args:
            key: Cache key
            data: Data to cache
            ttl: Optional TTL override (uses default_ttl if None)
        """
        ttl_seconds = ttl if ttl is not None else self.default_ttl

        entry = CacheEntry(data=data, timestamp=datetime.now(), ttl_seconds=ttl_seconds)

        self.cache[key] = entry

    def update_response_time(self, duration: float):
        """Track Subsonic server response time.

        Args:
            duration: Response time in seconds
        """
        self.response_times.append(duration)

    def should_throttle(self) -> bool:
        """Check if we should throttle requests based on server performance.

        Returns True if average response time over last 100 requests exceeds 2 seconds,
        indicating server stress. Requires at least 10 samples.

        Returns:
            bool: True if average response time > 2.0 seconds
        """
        if len(self.response_times) < 10:
            return False

        avg_response_time = sum(self.response_times) / len(self.response_times)
        return avg_response_time > 2.0

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics for monitoring.

        Returns:
            dict: Cache statistics including hit count, size, etc.
        """
        total_entries = len(self.cache)
        expired_entries = sum(1 for entry in self.cache.values() if entry.is_expired())

        return {
            "cached_items": total_entries,
            "expired_items": expired_entries,
            "response_times_count": len(self.response_times),
            "should_throttle": self.should_throttle(),
        }

    def clear(self):
        """Clear all cache entries."""
        self.cache.clear()
