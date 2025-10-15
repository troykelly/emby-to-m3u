"""
Unit tests for MetadataEnhancerService.

Tests cover:
- Last.fm API retrieval
- aubio CLI fallback
- SQLite caching
- Cache expiration
- Fallback chain behavior
- Error handling
"""

import os
import json
import tempfile
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, call
import pytest

from ai_playlist.services.metadata_enhancer import (
    MetadataEnhancerService,
    TrackMetadata,
)


class TestTrackMetadata:
    """Test TrackMetadata dataclass."""

    def test_metadata_creation(self):
        """Test creating metadata with all fields."""
        metadata = TrackMetadata(
            artist="The Beatles",
            title="Hey Jude",
            album="The Beatles 1967-1970",
            genre="Rock",
            bpm=147.0,
            mood="Uplifting",
            tags=["classic rock", "60s"]
        )

        assert metadata.artist == "The Beatles"
        assert metadata.title == "Hey Jude"
        assert metadata.bpm == 147.0
        assert len(metadata.tags) == 2

    def test_metadata_defaults(self):
        """Test metadata with default values."""
        metadata = TrackMetadata()

        assert metadata.artist is None
        assert metadata.title is None
        assert metadata.tags == []

    def test_metadata_to_dict(self):
        """Test converting metadata to dictionary."""
        metadata = TrackMetadata(
            artist="Beatles",
            title="Hey Jude",
            bpm=147.0
        )

        data = metadata.to_dict()

        assert data["artist"] == "Beatles"
        assert data["title"] == "Hey Jude"
        assert data["bpm"] == 147.0
        assert isinstance(data, dict)

    def test_metadata_from_dict(self):
        """Test creating metadata from dictionary."""
        data = {
            "artist": "Beatles",
            "title": "Hey Jude",
            "album": None,
            "genre": "Rock",
            "bpm": 147.0,
            "mood": None,
            "tags": ["rock"]
        }

        metadata = TrackMetadata.from_dict(data)

        assert metadata.artist == "Beatles"
        assert metadata.bpm == 147.0
        assert metadata.tags == ["rock"]


class TestMetadataEnhancerInit:
    """Test MetadataEnhancerService initialization."""

    def test_init_default(self):
        """Test initialization with defaults."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_db = Path(tmp_dir) / "test.db"

            service = MetadataEnhancerService(
                cache_db=str(cache_db)
            )

            assert service.cache_db == cache_db
            assert service.cache_ttl_days == 30
            assert cache_db.exists()

    def test_init_custom_params(self):
        """Test initialization with custom parameters."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_db = Path(tmp_dir) / "custom.db"

            service = MetadataEnhancerService(
                cache_db=str(cache_db),
                lastfm_api_key="test_key_123",
                cache_ttl_days=7
            )

            assert service.lastfm_api_key == "test_key_123"
            assert service.cache_ttl_days == 7

    def test_cache_database_created(self):
        """Test cache database is created with correct schema."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_db = Path(tmp_dir) / "test.db"

            service = MetadataEnhancerService(cache_db=str(cache_db))

            # Verify table exists
            conn = sqlite3.connect(str(cache_db))
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='metadata_cache'"
            )
            assert cursor.fetchone() is not None

            # Verify columns
            cursor = conn.execute("PRAGMA table_info(metadata_cache)")
            columns = {row[1] for row in cursor.fetchall()}
            assert columns == {"artist", "title", "metadata", "cached_at"}

            conn.close()

    def test_init_creates_cache_directory(self):
        """Test cache directory is created if missing."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_db = Path(tmp_dir) / "nested" / "dirs" / "test.db"

            service = MetadataEnhancerService(cache_db=str(cache_db))

            assert cache_db.parent.exists()
            assert cache_db.exists()


class TestMetadataEnhancerCache:
    """Test caching functionality."""

    def test_cache_save_and_retrieve(self):
        """Test saving and retrieving from cache."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_db = Path(tmp_dir) / "test.db"
            service = MetadataEnhancerService(cache_db=str(cache_db))

            metadata = TrackMetadata(
                artist="Beatles",
                title="Hey Jude",
                genre="Rock",
                bpm=147.0
            )

            # Save to cache
            service._save_to_cache("Beatles", "Hey Jude", metadata)

            # Retrieve from cache
            cached = service._get_from_cache("Beatles", "Hey Jude")

            assert cached is not None
            assert cached.artist == "Beatles"
            assert cached.title == "Hey Jude"
            assert cached.bpm == 147.0

    def test_cache_miss(self):
        """Test cache miss returns None."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_db = Path(tmp_dir) / "test.db"
            service = MetadataEnhancerService(cache_db=str(cache_db))

            cached = service._get_from_cache("Unknown", "Track")

            assert cached is None

    def test_cache_expiration(self):
        """Test expired cache entries are not returned."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_db = Path(tmp_dir) / "test.db"
            service = MetadataEnhancerService(
                cache_db=str(cache_db),
                cache_ttl_days=1
            )

            metadata = TrackMetadata(artist="Beatles", title="Hey Jude")

            # Manually insert old cache entry
            conn = sqlite3.connect(str(cache_db))
            old_date = (datetime.now() - timedelta(days=2)).isoformat()
            conn.execute(
                "INSERT INTO metadata_cache (artist, title, metadata, cached_at) VALUES (?, ?, ?, ?)",
                ("Beatles", "Hey Jude", json.dumps(metadata.to_dict()), old_date)
            )
            conn.commit()
            conn.close()

            # Should return None (expired)
            cached = service._get_from_cache("Beatles", "Hey Jude")
            assert cached is None

    def test_cache_update(self):
        """Test updating existing cache entry."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_db = Path(tmp_dir) / "test.db"
            service = MetadataEnhancerService(cache_db=str(cache_db))

            # Save initial metadata
            metadata1 = TrackMetadata(artist="Beatles", title="Hey Jude", bpm=147.0)
            service._save_to_cache("Beatles", "Hey Jude", metadata1)

            # Update with new metadata
            metadata2 = TrackMetadata(artist="Beatles", title="Hey Jude", bpm=148.0, genre="Rock")
            service._save_to_cache("Beatles", "Hey Jude", metadata2)

            # Should get updated metadata
            cached = service._get_from_cache("Beatles", "Hey Jude")
            assert cached.bpm == 148.0
            assert cached.genre == "Rock"


class TestMetadataEnhancerLastFm:
    """Test Last.fm API integration."""

    @patch('requests.get')
    def test_lastfm_success(self, mock_get):
        """Test successful Last.fm API call."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_db = Path(tmp_dir) / "test.db"
            service = MetadataEnhancerService(
                cache_db=str(cache_db),
                lastfm_api_key="test_key"
            )

            # Mock successful API response
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "track": {
                    "name": "Hey Jude",
                    "artist": {"name": "The Beatles"},
                    "album": {"title": "The Beatles 1967-1970"},
                    "toptags": {
                        "tag": [
                            {"name": "classic rock"},
                            {"name": "60s"},
                            {"name": "british"}
                        ]
                    }
                }
            }
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            metadata = service._fetch_from_lastfm("The Beatles", "Hey Jude")

            assert metadata is not None
            assert metadata.artist == "The Beatles"
            assert metadata.title == "Hey Jude"
            assert metadata.album == "The Beatles 1967-1970"
            assert metadata.genre == "classic rock"
            assert "60s" in metadata.tags

    @patch('requests.get')
    def test_lastfm_failure(self, mock_get):
        """Test Last.fm API failure returns None."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_db = Path(tmp_dir) / "test.db"
            service = MetadataEnhancerService(
                cache_db=str(cache_db),
                lastfm_api_key="test_key"
            )

            # Mock API error
            mock_get.side_effect = Exception("API Error")

            metadata = service._fetch_from_lastfm("Beatles", "Hey Jude")

            assert metadata is None

    def test_lastfm_no_api_key(self):
        """Test Last.fm returns None when no API key."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_db = Path(tmp_dir) / "test.db"

            # Clear environment variable if it exists
            old_key = os.environ.pop('LASTFM_API_KEY', None)

            try:
                service = MetadataEnhancerService(cache_db=str(cache_db))

                # Should return None when no API key
                metadata = service._fetch_from_lastfm("Beatles", "Hey Jude")

                assert metadata is None
            finally:
                # Restore environment variable if it existed
                if old_key is not None:
                    os.environ['LASTFM_API_KEY'] = old_key


class TestMetadataEnhancerAubio:
    """Test aubio fallback functionality."""

    @patch('subprocess.run')
    def test_aubio_success(self, mock_run):
        """Test successful aubio BPM extraction."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_db = Path(tmp_dir) / "test.db"
            service = MetadataEnhancerService(cache_db=str(cache_db))

            # Mock aubio output
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "147.000000\n"
            mock_run.return_value = mock_result

            metadata = service._analyze_with_aubio("/path/to/audio.mp3")

            assert metadata is not None
            assert metadata.bpm == 147.0

            # Verify aubio was called correctly
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert args[0] == "aubio"
            assert args[1] == "tempo"

    @patch('subprocess.run')
    def test_aubio_not_installed(self, mock_run):
        """Test aubio fallback when tool not installed."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_db = Path(tmp_dir) / "test.db"
            service = MetadataEnhancerService(cache_db=str(cache_db))

            # Mock aubio not found
            mock_run.side_effect = FileNotFoundError()

            metadata = service._analyze_with_aubio("/path/to/audio.mp3")

            assert metadata is None

    @patch('subprocess.run')
    def test_aubio_timeout(self, mock_run):
        """Test aubio timeout handling."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_db = Path(tmp_dir) / "test.db"
            service = MetadataEnhancerService(cache_db=str(cache_db))

            # Mock timeout
            import subprocess
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="aubio", timeout=30)

            metadata = service._analyze_with_aubio("/path/to/audio.mp3")

            assert metadata is None

    @patch('subprocess.run')
    def test_aubio_invalid_output(self, mock_run):
        """Test aubio with invalid output."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_db = Path(tmp_dir) / "test.db"
            service = MetadataEnhancerService(cache_db=str(cache_db))

            # Mock invalid output
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "invalid\noutput\n"
            mock_run.return_value = mock_result

            metadata = service._analyze_with_aubio("/path/to/audio.mp3")

            assert metadata is None


class TestMetadataEnhancerFallbackChain:
    """Test the complete fallback chain."""

    @patch('subprocess.run')
    @patch('requests.get')
    def test_fallback_chain_cache_hit(self, mock_requests, mock_subprocess):
        """Test cache is checked first."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_db = Path(tmp_dir) / "test.db"
            service = MetadataEnhancerService(
                cache_db=str(cache_db),
                lastfm_api_key="test_key"
            )

            # Populate cache
            cached_metadata = TrackMetadata(
                artist="Beatles",
                title="Hey Jude",
                genre="Rock",
                bpm=147.0
            )
            service._save_to_cache("Beatles", "Hey Jude", cached_metadata)

            # Enhance should use cache
            metadata = service.enhance_track("Beatles", "Hey Jude", "/audio.mp3")

            assert metadata.genre == "Rock"
            assert metadata.bpm == 147.0

            # No API calls should be made
            mock_requests.assert_not_called()
            mock_subprocess.assert_not_called()

    @patch('subprocess.run')
    @patch('requests.get')
    def test_fallback_chain_lastfm(self, mock_requests, mock_subprocess):
        """Test Last.fm is tried after cache miss."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_db = Path(tmp_dir) / "test.db"
            service = MetadataEnhancerService(
                cache_db=str(cache_db),
                lastfm_api_key="test_key"
            )

            # Mock Last.fm success
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "track": {
                    "name": "Hey Jude",
                    "artist": {"name": "Beatles"},
                    "toptags": {"tag": [{"name": "rock"}]}
                }
            }
            mock_response.raise_for_status = MagicMock()
            mock_requests.return_value = mock_response

            metadata = service.enhance_track("Beatles", "Hey Jude")

            assert metadata.genre == "rock"
            mock_requests.assert_called_once()
            mock_subprocess.assert_not_called()

            # Should be cached now
            cached = service._get_from_cache("Beatles", "Hey Jude")
            assert cached is not None

    @patch('subprocess.run')
    @patch('requests.get')
    def test_fallback_chain_aubio(self, mock_requests, mock_subprocess):
        """Test aubio is tried after Last.fm fails."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_db = Path(tmp_dir) / "test.db"
            service = MetadataEnhancerService(
                cache_db=str(cache_db),
                lastfm_api_key="test_key"
            )

            # Mock Last.fm failure
            mock_requests.side_effect = Exception("API Error")

            # Mock aubio success
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "147.0\n"
            mock_subprocess.return_value = mock_result

            metadata = service.enhance_track("Beatles", "Hey Jude", "/audio.mp3")

            assert metadata.artist == "Beatles"
            assert metadata.bpm == 147.0

            mock_requests.assert_called_once()
            mock_subprocess.assert_called_once()

    @patch('subprocess.run')
    @patch('requests.get')
    def test_fallback_chain_all_fail(self, mock_requests, mock_subprocess):
        """Test graceful degradation when all sources fail."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_db = Path(tmp_dir) / "test.db"
            service = MetadataEnhancerService(
                cache_db=str(cache_db),
                lastfm_api_key="test_key"
            )

            # Mock all failures
            mock_requests.side_effect = Exception("API Error")
            mock_subprocess.side_effect = FileNotFoundError()

            metadata = service.enhance_track("Beatles", "Hey Jude", "/audio.mp3")

            # Should return basic metadata
            assert metadata.artist == "Beatles"
            assert metadata.title == "Hey Jude"
            assert metadata.bpm is None
            assert metadata.genre is None


class TestMetadataEnhancerUtilities:
    """Test utility methods."""

    def test_clear_cache_all(self):
        """Test clearing all cache entries."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_db = Path(tmp_dir) / "test.db"
            service = MetadataEnhancerService(cache_db=str(cache_db))

            # Add some entries
            for i in range(5):
                metadata = TrackMetadata(artist=f"Artist{i}", title=f"Track{i}")
                service._save_to_cache(f"Artist{i}", f"Track{i}", metadata)

            # Clear all
            service.clear_cache()

            # Verify empty
            conn = sqlite3.connect(str(cache_db))
            cursor = conn.execute("SELECT COUNT(*) FROM metadata_cache")
            count = cursor.fetchone()[0]
            conn.close()

            assert count == 0

    def test_clear_cache_old_only(self):
        """Test clearing only old cache entries."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_db = Path(tmp_dir) / "test.db"
            service = MetadataEnhancerService(cache_db=str(cache_db))

            # Add old entry
            conn = sqlite3.connect(str(cache_db))
            old_date = (datetime.now() - timedelta(days=40)).isoformat()
            conn.execute(
                "INSERT INTO metadata_cache VALUES (?, ?, ?, ?)",
                ("OldArtist", "OldTrack", "{}", old_date)
            )

            # Add recent entry
            recent_date = datetime.now().isoformat()
            conn.execute(
                "INSERT INTO metadata_cache VALUES (?, ?, ?, ?)",
                ("NewArtist", "NewTrack", "{}", recent_date)
            )
            conn.commit()
            conn.close()

            # Clear entries older than 30 days
            service.clear_cache(older_than_days=30)

            # Verify only recent entry remains
            conn = sqlite3.connect(str(cache_db))
            cursor = conn.execute("SELECT artist FROM metadata_cache")
            artists = [row[0] for row in cursor.fetchall()]
            conn.close()

            assert "NewArtist" in artists
            assert "OldArtist" not in artists

    def test_get_cache_stats(self):
        """Test cache statistics."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_db = Path(tmp_dir) / "test.db"
            service = MetadataEnhancerService(
                cache_db=str(cache_db),
                cache_ttl_days=30
            )

            # Add valid entries
            for i in range(3):
                metadata = TrackMetadata(artist=f"Artist{i}", title=f"Track{i}")
                service._save_to_cache(f"Artist{i}", f"Track{i}", metadata)

            # Add expired entry
            conn = sqlite3.connect(str(cache_db))
            old_date = (datetime.now() - timedelta(days=40)).isoformat()
            conn.execute(
                "INSERT INTO metadata_cache VALUES (?, ?, ?, ?)",
                ("OldArtist", "OldTrack", "{}", old_date)
            )
            conn.commit()
            conn.close()

            stats = service.get_cache_stats()

            assert stats["total_entries"] == 4
            assert stats["valid_entries"] == 3
            assert stats["expired_entries"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
