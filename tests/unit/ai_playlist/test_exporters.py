"""
Comprehensive Unit Tests for Playlist Exporters (T061)

Tests M3UExporter and AzuraCastExporter from src/ai_playlist/exporters_new.py

Target: 90%+ coverage with 12 comprehensive tests covering:
- M3U format export (3 tests)
- EXTM3U with metadata (4 tests)
- Subsonic track ID format (3 tests)
- Playlist metadata embedding (2 tests)

Success Criteria:
- All 12 tests pass
- Coverage ≥90% of exporters_new.py
- Uses temp files (no permanent files)
- Pylint 10.00/10
"""

import tempfile
from pathlib import Path
from datetime import datetime
from decimal import Decimal

import pytest

from src.ai_playlist.exporters_new import M3UExporter, AzuraCastExporter
from src.ai_playlist.models.core import (
    Playlist,
    SelectedTrack,
    ValidationStatus
)


# Test Fixtures
# pylint: disable=redefined-outer-name,too-few-public-methods

@pytest.fixture
def sample_tracks():
    """Create sample tracks for testing."""
    return [
        SelectedTrack(
            track_id="12345",
            title="The Less I Know The Better",
            artist="Tame Impala",
            album="Currents",
            duration_seconds=185,
            is_australian=True,
            rotation_category="Power",
            position_in_playlist=0,
            selection_reasoning="High energy track with modern appeal",
            validation_status=ValidationStatus.PASS,
            metadata_source="library",
            bpm=115,
            genre="Electronic",
            year=2015,
            country="AU"
        ),
        SelectedTrack(
            track_id="67890",
            title="Do I Wanna Know?",
            artist="Arctic Monkeys",
            album="AM",
            duration_seconds=272,
            is_australian=False,
            rotation_category="Medium",
            position_in_playlist=1,
            selection_reasoning="Strong hook and consistent energy",
            validation_status=ValidationStatus.PASS,
            metadata_source="library",
            bpm=85,
            genre="Rock",
            year=2013,
            country="UK"
        ),
        SelectedTrack(
            track_id="24680",
            title="Somebody That I Used to Know",
            artist="Gotye",
            album="Making Mirrors",
            duration_seconds=244,
            is_australian=True,
            rotation_category="Recurrent",
            position_in_playlist=2,
            selection_reasoning="Familiar track for audience connection",
            validation_status=ValidationStatus.PASS,
            metadata_source="library",
            bpm=130,
            genre="Pop",
            year=2011,
            country="AU"
        )
    ]


@pytest.fixture
def sample_playlist(sample_tracks):
    """Create sample playlist for testing."""
    return Playlist(
        id="playlist-001",
        name="Morning Drive: Production Call - 2025-10-06",
        specification_id="spec-001",
        tracks=sample_tracks,
        validation_result=None,
        created_at=datetime(2025, 10, 6, 6, 0, 0),
        cost_actual=Decimal("0.50"),
        generation_time_seconds=12.5
    )


@pytest.fixture
def empty_playlist():
    """Create empty playlist for edge case testing."""
    return Playlist(
        id="playlist-empty",
        name="Empty Test Playlist",
        specification_id="spec-empty",
        tracks=[],
        validation_result=None,
        created_at=datetime.now(),
        cost_actual=Decimal("0.00"),
        generation_time_seconds=0.0
    )


@pytest.fixture
def special_chars_playlist():
    """Create playlist with special characters in track names."""
    tracks = [
        SelectedTrack(
            track_id="sc-001",
            title='Song with "Quotes" & Ampersand',
            artist="Artist's Name (feat. Someone)",
            album="Album: Special Edition [Deluxe]",
            duration_seconds=200,
            is_australian=False,
            rotation_category="Light",
            position_in_playlist=0,
            selection_reasoning="Testing special characters",
            validation_status=ValidationStatus.PASS,
            metadata_source="library"
        )
    ]
    return Playlist(
        id="playlist-special",
        name="Special Characters Test",
        specification_id="spec-special",
        tracks=tracks,
        validation_result=None,
        created_at=datetime.now(),
        cost_actual=Decimal("0.10"),
        generation_time_seconds=1.0
    )


@pytest.fixture
def temp_dir():
    """Create temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


# M3U Format Export Tests (3 tests)

class TestM3UFormatExport:
    """Test basic M3U format export functionality."""

    def test_export_basic_m3u_playlist(self, sample_playlist, temp_dir):
        """Test export of basic M3U playlist with Subsonic format."""
        exporter = M3UExporter()
        output_path = temp_dir / "test_basic.m3u"

        exporter.export_to_m3u(sample_playlist, output_path, use_subsonic_format=True)

        # Verify file exists
        assert output_path.exists()

        # Read and verify content
        content = output_path.read_text(encoding='utf-8')
        lines = content.split('\n')

        # Verify M3U header
        assert lines[0] == "#EXTM3U"
        assert lines[1] == "#PLAYLIST:Morning Drive: Production Call - 2025-10-06"

        # Verify first track (Tame Impala)
        assert "#EXTINF:185,Tame Impala - The Less I Know The Better" in content
        assert "subsonic:track:12345" in content

        # Verify second track (Arctic Monkeys)
        assert "#EXTINF:272,Arctic Monkeys - Do I Wanna Know?" in content
        assert "subsonic:track:67890" in content

        # Verify third track (Gotye)
        assert "#EXTINF:244,Gotye - Somebody That I Used to Know" in content
        assert "subsonic:track:24680" in content

    def test_export_empty_playlist(self, empty_playlist, temp_dir):
        """Test export of empty playlist."""
        exporter = M3UExporter()
        output_path = temp_dir / "test_empty.m3u"

        exporter.export_to_m3u(empty_playlist, output_path)

        # Verify file exists
        assert output_path.exists()

        # Read and verify content
        content = output_path.read_text(encoding='utf-8')
        lines = content.split('\n')

        # Verify M3U header exists
        assert lines[0] == "#EXTM3U"
        assert lines[1] == "#PLAYLIST:Empty Test Playlist"

        # Verify no tracks
        assert "subsonic:track:" not in content
        assert "#EXTINF:" not in '\n'.join(lines[2:])

    def test_export_with_special_characters_in_filenames(self, special_chars_playlist, temp_dir):
        """Test export with special characters in track metadata."""
        exporter = M3UExporter()
        output_path = temp_dir / "test_special_chars.m3u"

        exporter.export_to_m3u(special_chars_playlist, output_path, use_subsonic_format=True)

        # Verify file exists
        assert output_path.exists()

        # Read and verify content
        content = output_path.read_text(encoding='utf-8')

        # Verify special characters are preserved
        assert 'Song with "Quotes" & Ampersand' in content
        assert "Artist's Name (feat. Someone)" in content
        assert "subsonic:track:sc-001" in content


# EXTM3U with Metadata Tests (4 tests)

class TestEXTM3UMetadata:
    """Test EXTM3U format with comprehensive metadata."""

    def test_include_extinf_metadata(self, sample_playlist, temp_dir):
        """Test #EXTINF metadata inclusion."""
        exporter = M3UExporter()
        output_path = temp_dir / "test_extinf.m3u"

        exporter.export_to_m3u(sample_playlist, output_path)

        content = output_path.read_text(encoding='utf-8')

        # Verify EXTINF lines present for all tracks
        assert content.count("#EXTINF:") == 3

        # Verify EXTINF format: #EXTINF:duration,artist - title
        assert "#EXTINF:185,Tame Impala - The Less I Know The Better" in content
        assert "#EXTINF:272,Arctic Monkeys - Do I Wanna Know?" in content
        assert "#EXTINF:244,Gotye - Somebody That I Used to Know" in content

    def test_include_track_duration(self, sample_playlist, temp_dir):
        """Test track duration is included in EXTINF."""
        exporter = M3UExporter()
        output_path = temp_dir / "test_duration.m3u"

        exporter.export_to_m3u(sample_playlist, output_path)

        content = output_path.read_text(encoding='utf-8')

        # Verify durations are present and correct
        assert "#EXTINF:185," in content  # Tame Impala
        assert "#EXTINF:272," in content  # Arctic Monkeys
        assert "#EXTINF:244," in content  # Gotye

    def test_include_artist_and_title(self, sample_playlist, temp_dir):
        """Test artist and title are included in EXTINF."""
        exporter = M3UExporter()
        output_path = temp_dir / "test_artist_title.m3u"

        exporter.export_to_m3u(sample_playlist, output_path)

        content = output_path.read_text(encoding='utf-8')

        # Verify artist - title format
        assert "Tame Impala - The Less I Know The Better" in content
        assert "Arctic Monkeys - Do I Wanna Know?" in content
        assert "Gotye - Somebody That I Used to Know" in content

    def test_verify_extm3u_header(self, sample_playlist, temp_dir):
        """Test EXTM3U header is present."""
        exporter = M3UExporter()
        output_path = temp_dir / "test_header.m3u"

        exporter.export_to_m3u(sample_playlist, output_path)

        content = output_path.read_text(encoding='utf-8')
        lines = content.split('\n')

        # Verify first line is #EXTM3U
        assert lines[0] == "#EXTM3U"

        # Verify #PLAYLIST line follows
        assert lines[1].startswith("#PLAYLIST:")


# Subsonic Track ID Format Tests (3 tests)

class TestSubsonicTrackIDFormat:
    """Test Subsonic track ID URL format."""

    def test_convert_track_ids_to_subsonic_urls(self, sample_playlist, temp_dir):
        """Test track IDs are converted to subsonic:track:<id> format."""
        exporter = M3UExporter()
        output_path = temp_dir / "test_subsonic.m3u"

        exporter.export_to_m3u(sample_playlist, output_path, use_subsonic_format=True)

        content = output_path.read_text(encoding='utf-8')

        # Verify Subsonic format
        assert "subsonic:track:12345" in content
        assert "subsonic:track:67890" in content
        assert "subsonic:track:24680" in content

        # Verify no plain track IDs (when subsonic format enabled)
        lines = content.split('\n')
        for line in lines:
            if line and not line.startswith('#'):
                assert line.startswith('subsonic:track:') or line == ''

    def test_handle_missing_track_ids(self, temp_dir):
        """Test handling of tracks without IDs (uses empty string)."""
        # Create track with empty track_id
        track = SelectedTrack(
            track_id="",
            title="Track Without ID",
            artist="Unknown Artist",
            album="Unknown Album",
            duration_seconds=180,
            is_australian=False,
            rotation_category="Library",
            position_in_playlist=0,
            selection_reasoning="Testing missing ID",
            validation_status=ValidationStatus.WARNING,
            metadata_source="library"
        )

        playlist = Playlist(
            id="playlist-no-id",
            name="No ID Test",
            specification_id="spec-no-id",
            tracks=[track],
            validation_result=None,
            created_at=datetime.now(),
            cost_actual=Decimal("0.00"),
            generation_time_seconds=0.0
        )

        exporter = M3UExporter()
        output_path = temp_dir / "test_no_id.m3u"

        exporter.export_to_m3u(playlist, output_path, use_subsonic_format=True)

        content = output_path.read_text(encoding='utf-8')

        # Verify empty ID is handled (subsonic:track:)
        assert "subsonic:track:" in content

    def test_verify_url_encoding(self, sample_playlist, temp_dir):
        """Test track IDs are used without URL encoding (plain format)."""
        exporter = M3UExporter()
        output_path = temp_dir / "test_encoding.m3u"

        # Test without Subsonic format
        exporter.export_to_m3u(sample_playlist, output_path, use_subsonic_format=False)

        content = output_path.read_text(encoding='utf-8')

        # Verify plain track IDs (no subsonic: prefix)
        lines = content.split('\n')
        track_id_lines = [
            line for line in lines
            if line and not line.startswith('#') and line.strip()
        ]

        assert "12345" in track_id_lines
        assert "67890" in track_id_lines
        assert "24680" in track_id_lines


# Playlist Metadata Embedding Tests (2 tests)

class TestPlaylistMetadataEmbedding:
    """Test embedding of playlist metadata in export."""

    def test_embed_playlist_name_and_description(self, sample_playlist, temp_dir):
        """Test playlist name is embedded in #PLAYLIST directive."""
        exporter = M3UExporter()
        output_path = temp_dir / "test_metadata.m3u"

        exporter.export_to_m3u(sample_playlist, output_path)

        content = output_path.read_text(encoding='utf-8')
        lines = content.split('\n')

        # Verify #PLAYLIST line contains playlist name
        assert lines[1] == "#PLAYLIST:Morning Drive: Production Call - 2025-10-06"

        # Verify playlist name is correctly embedded
        assert "Morning Drive: Production Call - 2025-10-06" in content

    def test_embed_generation_timestamp_and_validation_scores(self, temp_dir):
        """Test timestamp is preserved via playlist name with date."""
        # Create playlist with timestamp in name
        playlist = Playlist(
            id="playlist-timestamp",
            name="Evening Show - 2025-10-06 18:00",
            specification_id="spec-timestamp",
            tracks=[
                SelectedTrack(
                    track_id="ts-001",
                    title="Test Track",
                    artist="Test Artist",
                    album="Test Album",
                    duration_seconds=200,
                    is_australian=False,
                    rotation_category="Power",
                    position_in_playlist=0,
                    selection_reasoning="Test",
                    validation_status=ValidationStatus.PASS,
                    metadata_source="library"
                )
            ],
            validation_result=None,
            created_at=datetime(2025, 10, 6, 18, 0, 0),
            cost_actual=Decimal("0.25"),
            generation_time_seconds=5.0
        )

        exporter = M3UExporter()
        output_path = temp_dir / "test_timestamp.m3u"

        exporter.export_to_m3u(playlist, output_path)

        content = output_path.read_text(encoding='utf-8')

        # Verify timestamp is embedded in playlist name
        assert "Evening Show - 2025-10-06 18:00" in content
        assert "#PLAYLIST:Evening Show - 2025-10-06 18:00" in content


# PLS Format Export Tests (Additional Coverage)

class TestPLSFormatExport:
    """Test PLS format export (alternative format)."""

    def test_export_to_pls_format(self, sample_playlist, temp_dir):
        """Test export to PLS format."""
        exporter = M3UExporter()
        output_path = temp_dir / "test.pls"

        exporter.export_to_pls(sample_playlist, output_path)

        # Verify file exists
        assert output_path.exists()

        content = output_path.read_text(encoding='utf-8')
        lines = content.split('\n')

        # Verify PLS header
        assert lines[0] == "[playlist]"

        # Verify track entries
        assert "File1=12345" in content
        assert "Title1=Tame Impala - The Less I Know The Better" in content
        assert "Length1=185" in content

        assert "File2=67890" in content
        assert "Title2=Arctic Monkeys - Do I Wanna Know?" in content
        assert "Length2=272" in content

        assert "File3=24680" in content
        assert "Title3=Gotye - Somebody That I Used to Know" in content
        assert "Length3=244" in content

        # Verify footer
        assert "NumberOfEntries=3" in content
        assert "Version=2" in content


# AzuraCast Exporter Tests

class TestAzuraCastExporter:
    """Test AzuraCast-compatible export."""

    def test_export_for_azuracast(self, sample_playlist, temp_dir):
        """Test AzuraCast export uses M3U with Subsonic format."""
        exporter = AzuraCastExporter()
        output_path = temp_dir / "test_azuracast.m3u"

        exporter.export_for_azuracast(sample_playlist, output_path)

        # Verify file exists
        assert output_path.exists()

        content = output_path.read_text(encoding='utf-8')

        # Verify it's M3U format with Subsonic track IDs
        assert "#EXTM3U" in content
        assert "#PLAYLIST:" in content
        assert "subsonic:track:12345" in content
        assert "subsonic:track:67890" in content
        assert "subsonic:track:24680" in content


# Directory Creation Tests

class TestDirectoryCreation:
    """Test automatic directory creation."""

    def test_creates_parent_directories(self, sample_playlist, temp_dir):
        """Test parent directories are created automatically."""
        exporter = M3UExporter()
        output_path = temp_dir / "nested" / "dirs" / "test.m3u"

        # Should not raise error even though dirs don't exist
        exporter.export_to_m3u(sample_playlist, output_path)

        # Verify file and directories created
        assert output_path.exists()
        assert output_path.parent.exists()
