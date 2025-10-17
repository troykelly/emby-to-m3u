"""
Metadata enhancement service for music tracks.

Provides a fallback chain for retrieving music metadata:
1. Last.fm API (primary source)
2. aubio CLI tool (local audio analysis fallback)
3. SQLite cache for previously retrieved metadata

Features:
- Artist, track, album, genre, BPM, mood extraction
- Persistent caching to minimize API calls
- Configurable API credentials
- Graceful degradation when APIs unavailable
"""

import os
import json
import subprocess
import sqlite3
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta


@dataclass
class TrackMetadata:
    """Enhanced track metadata."""
    artist: Optional[str] = None
    title: Optional[str] = None
    album: Optional[str] = None
    genre: Optional[str] = None
    bpm: Optional[float] = None
    mood: Optional[str] = None
    tags: list[str] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TrackMetadata":
        """Create from dictionary."""
        return cls(**data)


class MetadataEnhancerService:
    """
    Service for enhancing track metadata using multiple sources.

    Retrieval chain:
    1. Check SQLite cache
    2. Try Last.fm API
    3. Fall back to aubio CLI analysis
    4. Cache successful results

    Example:
        >>> enhancer = MetadataEnhancerService(
        ...     cache_db="/tmp/metadata_cache.db",
        ...     lastfm_api_key=os.getenv("LASTFM_API_KEY")
        ... )
        >>> metadata = enhancer.enhance_track("Beatles", "Hey Jude")
        >>> print(f"Genre: {metadata.genre}, BPM: {metadata.bpm}")
    """

    def __init__(
        self,
        cache_db: Optional[str] = None,
        lastfm_api_key: Optional[str] = None,
        cache_ttl_days: int = 30
    ):
        """
        Initialize metadata enhancer.

        Args:
            cache_db: Path to SQLite cache database (default: ~/.ai_playlist/metadata_cache.db)
            lastfm_api_key: Last.fm API key (reads from env if not provided)
            cache_ttl_days: Days before cache entries expire
        """
        if cache_db is None:
            cache_dir = Path.home() / ".ai_playlist"
            cache_dir.mkdir(exist_ok=True)
            cache_db = str(cache_dir / "metadata_cache.db")

        self.cache_db = Path(cache_db)
        self.lastfm_api_key = lastfm_api_key or os.getenv("LASTFM_API_KEY")
        self.cache_ttl_days = cache_ttl_days

        self._init_cache()

    def _init_cache(self):
        """Initialize SQLite cache database."""
        self.cache_db.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(str(self.cache_db))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS metadata_cache (
                artist TEXT NOT NULL,
                title TEXT NOT NULL,
                metadata TEXT NOT NULL,
                cached_at TEXT NOT NULL,
                PRIMARY KEY (artist, title)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_cached_at
            ON metadata_cache(cached_at)
        """)
        conn.commit()
        conn.close()

    def enhance_track(
        self,
        artist: str,
        title: str,
        audio_file: Optional[str] = None
    ) -> TrackMetadata:
        """
        Enhance track metadata using available sources.

        Args:
            artist: Artist name
            title: Track title
            audio_file: Optional path to audio file (for aubio fallback)

        Returns:
            TrackMetadata with enhanced information
        """
        # Check cache first
        cached = self._get_from_cache(artist, title)
        if cached:
            return cached

        # Try Last.fm API
        if self.lastfm_api_key:
            metadata = self._fetch_from_lastfm(artist, title)
            if metadata:
                self._save_to_cache(artist, title, metadata)
                return metadata

        # Fall back to aubio if audio file provided
        if audio_file:
            metadata = self._analyze_with_aubio(audio_file)
            if metadata:
                # Merge with basic info
                metadata.artist = artist
                metadata.title = title
                self._save_to_cache(artist, title, metadata)
                return metadata

        # Return basic metadata if all else fails
        metadata = TrackMetadata(artist=artist, title=title)
        return metadata

    def _get_from_cache(self, artist: str, title: str) -> Optional[TrackMetadata]:
        """Retrieve metadata from cache if not expired."""
        conn = sqlite3.connect(str(self.cache_db))
        cursor = conn.execute(
            """
            SELECT metadata, cached_at FROM metadata_cache
            WHERE artist = ? AND title = ?
            """,
            (artist, title)
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        metadata_json, cached_at = row

        # Check if expired
        cached_date = datetime.fromisoformat(cached_at)
        expiry_date = cached_date + timedelta(days=self.cache_ttl_days)

        if datetime.now() > expiry_date:
            return None

        return TrackMetadata.from_dict(json.loads(metadata_json))

    def _save_to_cache(self, artist: str, title: str, metadata: TrackMetadata):
        """Save metadata to cache."""
        conn = sqlite3.connect(str(self.cache_db))
        conn.execute(
            """
            INSERT OR REPLACE INTO metadata_cache (artist, title, metadata, cached_at)
            VALUES (?, ?, ?, ?)
            """,
            (artist, title, json.dumps(metadata.to_dict()), datetime.now().isoformat())
        )
        conn.commit()
        conn.close()

    def _fetch_from_lastfm(self, artist: str, title: str) -> Optional[TrackMetadata]:
        """
        Fetch metadata from Last.fm API.

        Note: This is a simplified implementation. In production, you would:
        - Use proper HTTP client with retries
        - Handle rate limiting
        - Parse full API response
        """
        # Skip if no API key
        if not self.lastfm_api_key:
            return None

        try:
            import requests

            url = "http://ws.audioscrobbler.com/2.0/"
            params = {
                "method": "track.getInfo",
                "api_key": self.lastfm_api_key,
                "artist": artist,
                "track": title,
                "format": "json"
            }

            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()

            data = response.json()
            track = data.get("track", {})

            # Extract metadata
            metadata = TrackMetadata(
                artist=artist,
                title=title,
                album=track.get("album", {}).get("title"),
                genre=None,  # Last.fm uses tags
                tags=[tag["name"] for tag in track.get("toptags", {}).get("tag", [])[:5]]
            )

            # Extract mood/genre from tags
            if metadata.tags:
                metadata.genre = metadata.tags[0]

            return metadata

        except Exception:
            # Silently fail and try next source
            return None

    def _analyze_with_aubio(self, audio_file: str) -> Optional[TrackMetadata]:
        """
        Analyze audio file with aubio CLI tools.

        Extracts BPM using aubio's beat detection.
        """
        try:
            # Check if aubio is available
            result = subprocess.run(
                ["aubio", "tempo", audio_file],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                return None

            # Parse BPM from output
            # aubio tempo outputs lines like: "120.000000"
            bpm = None
            for line in result.stdout.strip().split("\n"):
                try:
                    bpm = float(line.strip())
                    break
                except ValueError:
                    continue

            if bpm:
                return TrackMetadata(bpm=bpm)

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return None

    def clear_cache(self, older_than_days: Optional[int] = None):
        """
        Clear cache entries.

        Args:
            older_than_days: Only clear entries older than this many days
                           (default: clear all)
        """
        conn = sqlite3.connect(str(self.cache_db))

        if older_than_days is None:
            conn.execute("DELETE FROM metadata_cache")
        else:
            cutoff_date = datetime.now() - timedelta(days=older_than_days)
            conn.execute(
                "DELETE FROM metadata_cache WHERE cached_at < ?",
                (cutoff_date.isoformat(),)
            )

        conn.commit()
        conn.close()

    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        conn = sqlite3.connect(str(self.cache_db))

        cursor = conn.execute("SELECT COUNT(*) FROM metadata_cache")
        total = cursor.fetchone()[0]

        cutoff_date = datetime.now() - timedelta(days=self.cache_ttl_days)
        cursor = conn.execute(
            "SELECT COUNT(*) FROM metadata_cache WHERE cached_at >= ?",
            (cutoff_date.isoformat(),)
        )
        valid = cursor.fetchone()[0]

        conn.close()

        return {
            "total_entries": total,
            "valid_entries": valid,
            "expired_entries": total - valid
        }
