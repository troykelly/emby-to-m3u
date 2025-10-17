"""
Track metadata enhancement using Last.fm API and aubio audio analysis.

Provides two-tier metadata enrichment:
1. Last.fm API (primary) - Retrieve genre, BPM, country from community tags
2. aubio CLI (fallback) - Audio analysis for BPM detection when Last.fm fails

All metadata is permanently cached in SQLite to minimize API calls and processing.

FR-029: Metadata enhancement with permanent caching.
"""

import os
import subprocess
import logging
import sqlite3
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from datetime import datetime
import json

logger = logging.getLogger(__name__)

# Optional Last.fm support
try:
    import pylast
    HAS_PYLAST = True
except ImportError:
    HAS_PYLAST = False
    logger.warning("pylast not installed - Last.fm metadata unavailable")


class MetadataEnhancerError(Exception):
    """Base exception for metadata enhancement errors."""
    pass


class MetadataEnhancer:
    """
    Two-tier metadata enhancement with permanent caching.

    Retrieves missing track metadata (BPM, genre, country) using:
    1. Last.fm API (community-tagged metadata)
    2. aubio CLI (audio analysis fallback for BPM)

    All results are cached in SQLite to minimize API calls.

    Attributes:
        cache_db_path: Path to SQLite cache database
        lastfm_api_key: Last.fm API key (optional)
        lastfm_network: Initialized pylast Network object
        aubio_cli_path: Path to aubio executable
    """

    DEFAULT_CACHE_DB = ".swarm/memory.db"
    AUBIO_CLI_PATH = "/usr/bin/aubio"

    def __init__(
        self,
        cache_db_path: Optional[str] = None,
        lastfm_api_key: Optional[str] = None
    ):
        """
        Initialize metadata enhancer.

        Args:
            cache_db_path: Path to SQLite cache (default: .swarm/memory.db)
            lastfm_api_key: Last.fm API key (reads from env if not provided)
        """
        self.cache_db_path = Path(
            cache_db_path or self.DEFAULT_CACHE_DB
        ).resolve()

        # Initialize Last.fm if available
        self.lastfm_api_key = lastfm_api_key or os.getenv("LASTFM_API_KEY")
        self.lastfm_network = None

        if HAS_PYLAST and self.lastfm_api_key:
            try:
                self.lastfm_network = pylast.LastFMNetwork(
                    api_key=self.lastfm_api_key
                )
                logger.info("Last.fm API initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Last.fm: {e}")

        # Locate aubio CLI
        self.aubio_cli_path = self._find_aubio_cli()

        # Initialize cache database
        self._init_cache_db()

    def _find_aubio_cli(self) -> Optional[Path]:
        """
        Locate aubio CLI executable.

        Returns:
            Path to aubio executable or None if not found
        """
        # Check default path
        if Path(self.AUBIO_CLI_PATH).exists():
            return Path(self.AUBIO_CLI_PATH)

        # Check PATH
        aubio_path = subprocess.run(
            ["which", "aubio"],
            capture_output=True,
            text=True
        ).stdout.strip()

        if aubio_path:
            logger.info(f"Found aubio at: {aubio_path}")
            return Path(aubio_path)

        logger.warning("aubio CLI not found - BPM fallback unavailable")
        return None

    def _init_cache_db(self) -> None:
        """Initialize SQLite cache database with schema."""
        self.cache_db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(str(self.cache_db_path))
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS track_metadata_cache (
                    track_id TEXT PRIMARY KEY,
                    bpm REAL,
                    genre TEXT,
                    country TEXT,
                    source TEXT NOT NULL,
                    cached_at TEXT NOT NULL,
                    metadata_json TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_cached_at
                ON track_metadata_cache(cached_at)
            """)
            conn.commit()
            logger.debug(f"Initialized metadata cache at: {self.cache_db_path}")
        finally:
            conn.close()

    def enhance_track(
        self,
        track_id: str,
        artist: str,
        title: str,
        audio_file_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Enhance track metadata with BPM, genre, country.

        Tries in order:
        1. Check cache
        2. Last.fm API
        3. aubio CLI (BPM only)

        Args:
            track_id: Unique track identifier
            artist: Track artist name
            title: Track title
            audio_file_path: Path to audio file (for aubio fallback)

        Returns:
            Dictionary with keys: bpm, genre, country, source

        Raises:
            MetadataEnhancerError: If all enhancement methods fail
        """
        # Check cache first
        cached = self._get_cached_metadata(track_id)
        if cached:
            logger.debug(f"Cache hit for track {track_id}: {cached['source']}")
            return cached

        # Try Last.fm
        if self.lastfm_network:
            try:
                metadata = self._enhance_from_lastfm(artist, title)
                if metadata:
                    self._cache_metadata(track_id, metadata, source="lastfm")
                    logger.info(
                        f"Enhanced {track_id} from Last.fm: "
                        f"BPM={metadata.get('bpm')}, genre={metadata.get('genre')}"
                    )
                    return metadata
            except Exception as e:
                logger.warning(f"Last.fm failed for {track_id}: {e}")

        # Try aubio fallback (BPM only)
        if self.aubio_cli_path and audio_file_path:
            try:
                bpm = self._enhance_bpm_from_aubio(audio_file_path)
                if bpm:
                    metadata = {"bpm": bpm, "genre": None, "country": None}
                    self._cache_metadata(track_id, metadata, source="aubio")
                    logger.info(f"Enhanced {track_id} BPM from aubio: {bpm}")
                    return metadata
            except Exception as e:
                logger.warning(f"aubio failed for {track_id}: {e}")

        # No enhancement available
        logger.warning(f"No metadata enhancement available for {track_id}")
        return {"bpm": None, "genre": None, "country": None, "source": "none"}

    def _enhance_from_lastfm(
        self,
        artist: str,
        title: str
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve metadata from Last.fm API.

        Args:
            artist: Track artist name
            title: Track title

        Returns:
            Dictionary with bpm, genre, country or None if not found
        """
        if not self.lastfm_network:
            return None

        try:
            # Get track object
            track = self.lastfm_network.get_track(artist, title)
            if not track:
                return None

            # Retrieve metadata
            metadata: Dict[str, Any] = {
                "bpm": None,
                "genre": None,
                "country": None
            }

            # Get top tags (genres)
            try:
                tags = track.get_top_tags(limit=5)
                if tags:
                    # Primary genre is top tag
                    metadata["genre"] = tags[0].item.name
            except Exception as e:
                logger.debug(f"Failed to get tags: {e}")

            # Get BPM from track info (if available)
            try:
                track_info = track.get_info()
                if hasattr(track_info, "bpm") and track_info.bpm:
                    metadata["bpm"] = float(track_info.bpm)
            except Exception as e:
                logger.debug(f"Failed to get BPM: {e}")

            # Get artist country
            try:
                artist_obj = self.lastfm_network.get_artist(artist)
                artist_info = artist_obj.get_info()
                if hasattr(artist_info, "country") and artist_info.country:
                    metadata["country"] = artist_info.country
            except Exception as e:
                logger.debug(f"Failed to get country: {e}")

            return metadata

        except pylast.WSError as e:
            logger.warning(f"Last.fm API error: {e}")
            return None

    def _enhance_bpm_from_aubio(self, audio_file_path: str) -> Optional[float]:
        """
        Analyze BPM using aubio CLI.

        Args:
            audio_file_path: Path to audio file

        Returns:
            BPM value or None if analysis fails
        """
        if not self.aubio_cli_path:
            return None

        audio_path = Path(audio_file_path)
        if not audio_path.exists():
            logger.warning(f"Audio file not found: {audio_file_path}")
            return None

        try:
            # Run aubio tempo analysis
            result = subprocess.run(
                [str(self.aubio_cli_path), "tempo", str(audio_path)],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                logger.warning(f"aubio failed: {result.stderr}")
                return None

            # Parse BPM from output (format: "120.000000 bpm")
            output = result.stdout.strip()
            if "bpm" in output.lower():
                bpm_str = output.split()[0]
                bpm = float(bpm_str)
                return round(bpm, 1)

            return None

        except subprocess.TimeoutExpired:
            logger.warning(f"aubio timeout for {audio_file_path}")
            return None
        except (ValueError, IndexError) as e:
            logger.warning(f"Failed to parse aubio output: {e}")
            return None

    def _get_cached_metadata(self, track_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve metadata from cache.

        Args:
            track_id: Unique track identifier

        Returns:
            Cached metadata dictionary or None if not cached
        """
        conn = sqlite3.connect(str(self.cache_db_path))
        try:
            cursor = conn.execute(
                "SELECT bpm, genre, country, source FROM track_metadata_cache "
                "WHERE track_id = ?",
                (track_id,)
            )
            row = cursor.fetchone()

            if row:
                return {
                    "bpm": row[0],
                    "genre": row[1],
                    "country": row[2],
                    "source": row[3]
                }

            return None

        finally:
            conn.close()

    def _cache_metadata(
        self,
        track_id: str,
        metadata: Dict[str, Any],
        source: str
    ) -> None:
        """
        Store metadata in cache.

        Args:
            track_id: Unique track identifier
            metadata: Dictionary with bpm, genre, country
            source: Metadata source (lastfm, aubio, etc.)
        """
        conn = sqlite3.connect(str(self.cache_db_path))
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO track_metadata_cache
                (track_id, bpm, genre, country, source, cached_at, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    track_id,
                    metadata.get("bpm"),
                    metadata.get("genre"),
                    metadata.get("country"),
                    source,
                    datetime.utcnow().isoformat(),
                    json.dumps(metadata)
                )
            )
            conn.commit()
            logger.debug(f"Cached metadata for {track_id} from {source}")

        finally:
            conn.close()

    def get_cache_stats(self) -> Dict[str, int]:
        """
        Get cache statistics.

        Returns:
            Dictionary with total_cached, lastfm_count, aubio_count
        """
        conn = sqlite3.connect(str(self.cache_db_path))
        try:
            cursor = conn.execute(
                "SELECT source, COUNT(*) FROM track_metadata_cache GROUP BY source"
            )
            stats = {"total_cached": 0, "lastfm_count": 0, "aubio_count": 0}

            for source, count in cursor.fetchall():
                stats["total_cached"] += count
                if source == "lastfm":
                    stats["lastfm_count"] = count
                elif source == "aubio":
                    stats["aubio_count"] = count

            return stats

        finally:
            conn.close()


def test_metadata_enhancement():
    """Test metadata enhancement with sample track."""
    import tempfile

    # Create temporary cache
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        cache_path = tmp.name

    try:
        enhancer = MetadataEnhancer(cache_db_path=cache_path)

        # Test enhancement (will use Last.fm if key available)
        metadata = enhancer.enhance_track(
            track_id="test_001",
            artist="Daft Punk",
            title="Get Lucky"
        )

        print(f"Enhanced metadata: {metadata}")

        # Check cache
        cached = enhancer._get_cached_metadata("test_001")
        assert cached is not None, "Metadata should be cached"

        # Get stats
        stats = enhancer.get_cache_stats()
        print(f"Cache stats: {stats}")

        print("✓ Metadata enhancement test passed")

    finally:
        os.unlink(cache_path)


if __name__ == "__main__":
    test_metadata_enhancement()
