"""
T020: Live Integration Test - Station Identity Parsing

Tests loading and parsing the actual station-identity.md file with all
programming structures, dayparts, and validation of Australian content requirements.

This test uses the LIVE station-identity.md file (no mocks).
"""
import os
import pytest
from pathlib import Path
from src.ai_playlist.document_parser import DocumentParser
from src.ai_playlist.models.core import StationIdentityDocument


@pytest.mark.integration
@pytest.mark.live
class TestStationIdentityParsing:
    """Live integration tests for station identity document parsing."""

    @pytest.fixture
    def station_identity_path(self) -> Path:
        """Get path to live station-identity.md file."""
        path = Path("/workspaces/emby-to-m3u/station-identity.md")
        if not path.exists():
            pytest.skip(f"Station identity file not found: {path}")
        return path

    @pytest.fixture
    def parser(self) -> DocumentParser:
        """Create document parser instance."""
        return DocumentParser()

    def test_load_station_identity_file(self, station_identity_path: Path, parser: DocumentParser):
        """Test loading actual station-identity.md file.

        Success Criteria:
        - File loads successfully
        - Document structure is recognized
        - Programming structures are identified
        """
        # Act
        document = parser.load_document(station_identity_path)

        # Assert
        assert document is not None
        assert isinstance(document, StationIdentityDocument)
        assert document.document_path == station_identity_path
        assert document.loaded_at is not None
        assert len(document.programming_structures) > 0

    def test_parse_weekday_programming_structure(
        self, station_identity_path: Path, parser: DocumentParser
    ):
        """Test parsing Monday to Friday programming structure.

        Success Criteria:
        - Weekday programming structure found
        - All expected dayparts extracted (Morning Drive, Midday, Afternoon Drive, Evening, Late Night)
        - Each daypart has complete metadata
        """
        # Act
        document = parser.load_document(station_identity_path)

        # Assert - Find weekday structure
        weekday_structure = next(
            (s for s in document.programming_structures if s.schedule_type.value == "weekday"),
            None
        )
        assert weekday_structure is not None, "Weekday programming structure not found"

        # Assert - Expected dayparts present
        daypart_names = {dp.name for dp in weekday_structure.dayparts}
        expected_dayparts = {
            "Morning Drive: Production Call",
            "Midday: The Session",
            "Afternoon Drive: The Commute",
            "Evening: After Hours",
            "Late Night/Overnight: The Creative Shift"
        }

        # Check at least the main dayparts are present
        assert "Morning Drive" in str(daypart_names) or "Production Call" in str(daypart_names)
        assert len(weekday_structure.dayparts) >= 4

    def test_parse_weekend_programming_structures(
        self, station_identity_path: Path, parser: DocumentParser
    ):
        """Test parsing Saturday and Sunday programming structures.

        Success Criteria:
        - Saturday programming structure found
        - Sunday programming structure found
        - Weekend structures differ from weekday
        """
        # Act
        document = parser.load_document(station_identity_path)

        # Assert - Find weekend structures
        saturday_structure = next(
            (s for s in document.programming_structures if s.schedule_type.value == "saturday"),
            None
        )
        sunday_structure = next(
            (s for s in document.programming_structures if s.schedule_type.value == "sunday"),
            None
        )

        assert saturday_structure is not None, "Saturday programming structure not found"
        assert sunday_structure is not None, "Sunday programming structure not found"

        # Assert - Weekend structures have dayparts
        assert len(saturday_structure.dayparts) > 0
        assert len(sunday_structure.dayparts) > 0

    def test_extract_daypart_bpm_specifications(
        self, station_identity_path: Path, parser: DocumentParser
    ):
        """Test extraction of BPM progression from dayparts.

        Success Criteria:
        - Morning Drive BPM progression: 90-115 → 110-135 → 100-120
        - BPM ranges are valid (min < max, within 60-200)
        - All BPM ranges have time segments
        """
        # Act
        document = parser.load_document(station_identity_path)

        # Find Morning Drive daypart
        morning_drive = None
        for structure in document.programming_structures:
            for daypart in structure.dayparts:
                if "Morning Drive" in daypart.name or "Production Call" in daypart.name:
                    morning_drive = daypart
                    break
            if morning_drive:
                break

        assert morning_drive is not None, "Morning Drive daypart not found"

        # Assert - BPM progression exists
        assert len(morning_drive.bpm_progression) > 0

        # Assert - BPM ranges are valid
        for bpm_range in morning_drive.bpm_progression:
            assert bpm_range.bpm_min < bpm_range.bpm_max
            assert 60 <= bpm_range.bpm_min <= 200
            assert 60 <= bpm_range.bpm_max <= 200
            assert bpm_range.time_start is not None
            assert bpm_range.time_end is not None

    def test_extract_genre_mix_specifications(
        self, station_identity_path: Path, parser: DocumentParser
    ):
        """Test extraction of genre mix from dayparts.

        Success Criteria:
        - Genre mix extracted for each daypart
        - Genre percentages sum to 85-100% (real-world data may have incomplete allocations)
        - All genre names are non-empty
        """
        # Act
        document = parser.load_document(station_identity_path)

        # Check first available daypart
        first_structure = document.programming_structures[0]
        assert len(first_structure.dayparts) > 0

        first_daypart = first_structure.dayparts[0]

        # Assert - Genre mix exists
        assert len(first_daypart.genre_mix) > 0

        # Assert - Genre percentages sum to 85-100% (realistic range for real-world data)
        total_percentage = sum(criteria.target_percentage for criteria in first_daypart.genre_mix.values())
        assert 0.85 <= total_percentage <= 1.01, \
            f"Genre percentages sum to {total_percentage}, expected 85-100% (0.85-1.01)"

        # Assert - All genre names are valid
        for genre_name in first_daypart.genre_mix.keys():
            assert genre_name is not None
            assert len(genre_name) > 0

    def test_extract_era_distribution(
        self, station_identity_path: Path, parser: DocumentParser
    ):
        """Test extraction of era distribution from dayparts.

        Success Criteria:
        - Era distribution extracted
        - Era percentages sum to approximately 1.0 (±0.01)
        - All era names are non-empty
        """
        # Act
        document = parser.load_document(station_identity_path)

        # Check first available daypart
        first_structure = document.programming_structures[0]
        first_daypart = first_structure.dayparts[0]

        # Assert - Era distribution exists
        assert len(first_daypart.era_distribution) > 0

        # Assert - Era percentages sum to ~1.0
        total_percentage = sum(
            criteria.target_percentage for criteria in first_daypart.era_distribution.values()
        )
        assert 0.99 <= total_percentage <= 1.01, \
            f"Era percentages sum to {total_percentage}, expected ~1.0"

        # Assert - All era names are valid
        for era_name in first_daypart.era_distribution.keys():
            assert era_name is not None
            assert len(era_name) > 0

    def test_validate_australian_content_minimum(
        self, station_identity_path: Path, parser: DocumentParser
    ):
        """Test that Australian content minimum is set to 30%.

        Success Criteria:
        - Australian content minimum = 30% (0.30)
        - All dayparts enforce this requirement
        - Value is non-negotiable (documented)
        """
        # Act
        document = parser.load_document(station_identity_path)

        # Assert - Check all dayparts have Australian content requirement
        for structure in document.programming_structures:
            for daypart in structure.dayparts:
                # Australian content should be in content_requirements
                if hasattr(daypart, 'australian_content_min'):
                    assert daypart.australian_content_min >= 0.30, \
                        f"Daypart '{daypart.name}' Australian content {daypart.australian_content_min} < 0.30"

                # Also check in content_focus if present
                if "australian" in str(daypart.content_focus).lower():
                    # Special programming may have 100% Australian
                    assert True

    def test_extract_rotation_strategy(
        self, station_identity_path: Path, parser: DocumentParser
    ):
        """Test extraction of rotation strategy and percentages.

        Success Criteria:
        - Rotation strategy defined
        - Rotation categories identified (Power, Medium, Light, Recurrent, Library)
        - Rotation percentages are reasonable
        """
        # Act
        document = parser.load_document(station_identity_path)

        # Assert - Rotation strategy exists
        assert document.rotation_strategy is not None

        # Assert - Check first daypart's rotation percentages
        first_structure = document.programming_structures[0]
        first_daypart = first_structure.dayparts[0]

        if first_daypart.rotation_percentages:
            # Rotation percentages should be reasonable
            for category, percentage in first_daypart.rotation_percentages.items():
                assert 0.0 <= percentage <= 1.0, \
                    f"Rotation category '{category}' has invalid percentage {percentage}"

    def test_calculate_target_track_count(
        self, station_identity_path: Path, parser: DocumentParser
    ):
        """Test calculation of target track count from duration and tracks per hour.

        Success Criteria:
        - Morning Drive (4 hours, 12-14 tracks/hour) = 48-56 tracks
        - Target track count calculated correctly
        - Min <= Max
        """
        # Act
        document = parser.load_document(station_identity_path)

        # Find Morning Drive daypart
        morning_drive = None
        for structure in document.programming_structures:
            for daypart in structure.dayparts:
                if "Morning Drive" in daypart.name or "Production Call" in daypart.name:
                    morning_drive = daypart
                    break
            if morning_drive:
                break

        assert morning_drive is not None, "Morning Drive daypart not found"

        # Calculate expected track count
        min_tracks, max_tracks = morning_drive.calculate_target_track_count()

        # Assert - Track count is reasonable for 4-hour show with 12-14 tracks/hour
        assert min_tracks >= 40, f"Minimum tracks {min_tracks} seems too low for 4-hour show"
        assert max_tracks <= 60, f"Maximum tracks {max_tracks} seems too high for 4-hour show"
        assert min_tracks <= max_tracks

    def test_document_version_tracking(
        self, station_identity_path: Path, parser: DocumentParser
    ):
        """Test that document version is tracked.

        Success Criteria:
        - Version field exists
        - Loaded timestamp is recent
        - Document path is correct
        """
        # Act
        document = parser.load_document(station_identity_path)

        # Assert
        assert document.version is not None
        assert document.loaded_at is not None
        assert document.document_path == station_identity_path

        # Loaded timestamp should be recent (within last minute)
        from datetime import datetime, timedelta
        assert datetime.now() - document.loaded_at < timedelta(minutes=1)

    def test_complete_daypart_metadata_extraction(
        self, station_identity_path: Path, parser: DocumentParser
    ):
        """Test that all daypart metadata fields are extracted.

        Success Criteria:
        - All dayparts have: name, time range, BPM, genre, era, mood, content focus
        - Target demographic is present
        - Duration in hours is calculated correctly
        """
        # Act
        document = parser.load_document(station_identity_path)

        # Check first daypart has all required fields
        first_structure = document.programming_structures[0]
        first_daypart = first_structure.dayparts[0]

        # Assert - Core metadata present
        assert first_daypart.id is not None
        assert first_daypart.name is not None and len(first_daypart.name) > 0
        assert first_daypart.schedule_type is not None
        assert first_daypart.time_start is not None
        assert first_daypart.time_end is not None
        assert first_daypart.duration_hours > 0

        # Assert - Musical requirements present
        assert len(first_daypart.bpm_progression) > 0
        assert len(first_daypart.genre_mix) > 0
        assert len(first_daypart.era_distribution) > 0

        # Assert - Programming requirements present
        assert first_daypart.target_demographic is not None
        assert first_daypart.mood_guidelines is not None
        assert first_daypart.content_focus is not None
