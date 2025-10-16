"""
Comprehensive tests for AI Playlist Document Parser module.

Tests all document parsing functions including:
- load_document()
- _parse_programming_structures()
- _parse_dayparts()
- All helper parsing methods
"""
import pytest
from pathlib import Path
from datetime import datetime, time as time_obj
from typing import List

from src.ai_playlist.document_parser import DocumentParser
from src.ai_playlist.models.core import (
    StationIdentityDocument,
    ProgrammingStructure,
    DaypartSpecification,
    ScheduleType,
    BPMRange,
    GenreCriteria,
    EraCriteria,
)


class TestLoadDocument:
    """Tests for load_document() main function."""

    @pytest.fixture
    def sample_document_content(self) -> str:
        """Create minimal valid station identity document."""
        return """# Station Identity

## Weekday Programming

### Morning Drive (06:00-10:00)
- **Time**: 06:00-10:00
- **Target Demographic**: 25-45 Adults
- **BPM Progression**:
  - 06:00-08:00: 100-120 BPM
  - 08:00-10:00: 120-130 BPM
- **Genre Mix**:
  - Electronic: 40%
  - Rock: 30%
  - Pop: 30%
- **Era Distribution**:
  - Current (2023-2025): 50%
  - Recent (2018-2022): 30%
  - Throwbacks (2000-2017): 20%
- **Tracks Per Hour**: 12-15
- **Mood Guidelines**: Build energy, Uplifting, Drive-time focus
- **Content Focus**: High-energy start to the day

## Rotation Strategy
- **Power (30%)**: 8-12 plays per track per week
- **Medium (40%)**: 5-8 plays per track per week
- **Light (30%)**: 2-5 plays per track per week

## Content Requirements
- **Australian Content Minimum**: 30%

## Genre Definitions
- **Electronic**: House, Techno, Trance
"""

    @pytest.fixture
    def sample_document_file(self, tmp_path: Path, sample_document_content: str) -> Path:
        """Create temporary station identity file."""
        doc_file = tmp_path / "station-identity.md"
        doc_file.write_text(sample_document_content)
        return doc_file

    def test_load_existing_document(self, sample_document_file: Path):
        """Test loading an existing station identity document."""
        # Arrange
        parser = DocumentParser()

        # Act
        doc = parser.load_document(sample_document_file)

        # Assert
        assert isinstance(doc, StationIdentityDocument)
        assert doc.document_path == sample_document_file
        assert len(doc.programming_structures) > 0
        assert doc.version is not None
        assert len(doc.version) == 64  # SHA256 hash

    def test_load_nonexistent_document_raises_error(self, tmp_path: Path):
        """Test that loading nonexistent file raises FileNotFoundError."""
        # Arrange
        parser = DocumentParser()
        nonexistent = tmp_path / "nonexistent.md"

        # Act & Assert
        with pytest.raises(FileNotFoundError, match="Station identity file not found"):
            parser.load_document(nonexistent)

    def test_load_empty_document_raises_error(self, tmp_path: Path):
        """Test that loading empty file raises ValueError."""
        # Arrange
        parser = DocumentParser()
        empty_file = tmp_path / "empty.md"
        empty_file.write_text("")

        # Act & Assert
        with pytest.raises(ValueError, match="Station identity file is empty"):
            parser.load_document(empty_file)

    def test_load_document_parses_programming_structures(self, sample_document_file: Path):
        """Test that document loads programming structures."""
        # Arrange
        parser = DocumentParser()

        # Act
        doc = parser.load_document(sample_document_file)

        # Assert
        assert len(doc.programming_structures) >= 1
        weekday_structure = doc.programming_structures[0]
        assert weekday_structure.schedule_type == ScheduleType.WEEKDAY

    def test_load_document_parses_rotation_strategy(self, sample_document_file: Path):
        """Test that document loads rotation strategy."""
        # Arrange
        parser = DocumentParser()

        # Act
        doc = parser.load_document(sample_document_file)

        # Assert
        assert doc.rotation_strategy is not None
        assert len(doc.rotation_strategy.categories) > 0

    def test_load_document_parses_content_requirements(self, sample_document_file: Path):
        """Test that document loads content requirements."""
        # Arrange
        parser = DocumentParser()

        # Act
        doc = parser.load_document(sample_document_file)

        # Assert
        assert doc.content_requirements is not None
        assert doc.content_requirements.australian_minimum == 0.30


class TestParseTime:
    """Tests for _parse_time() helper function."""

    def test_parse_time_with_colon_format(self):
        """Test parsing time in HH:MM format."""
        # Arrange
        parser = DocumentParser()

        # Act
        result = parser._parse_time("14:30")

        # Assert
        assert result == time_obj(14, 30)

    def test_parse_time_with_leading_zero(self):
        """Test parsing time with leading zero."""
        # Arrange
        parser = DocumentParser()

        # Act
        result = parser._parse_time("06:00")

        # Assert
        assert result == time_obj(6, 0)

    def test_parse_time_midnight(self):
        """Test parsing midnight."""
        # Arrange
        parser = DocumentParser()

        # Act
        result = parser._parse_time("00:00")

        # Assert
        assert result == time_obj(0, 0)


class TestCalculateDuration:
    """Tests for _calculate_duration() helper function."""

    def test_calculate_duration_4_hours(self):
        """Test calculating 4-hour duration."""
        # Arrange
        parser = DocumentParser()

        # Act
        duration = parser._calculate_duration(time_obj(6, 0), time_obj(10, 0))

        # Assert
        assert duration == 4.0

    def test_calculate_duration_with_minutes(self):
        """Test calculating duration with minutes."""
        # Arrange
        parser = DocumentParser()

        # Act
        duration = parser._calculate_duration(time_obj(6, 30), time_obj(10, 15))

        # Assert
        assert duration == 3.75

    def test_calculate_duration_short_block(self):
        """Test calculating short duration."""
        # Arrange
        parser = DocumentParser()

        # Act
        duration = parser._calculate_duration(time_obj(12, 0), time_obj(13, 0))

        # Assert
        assert duration == 1.0


class TestParseBPMProgression:
    """Tests for _parse_bpm_progression() function."""

    def test_parse_bpm_progression_with_time_ranges(self):
        """Test parsing BPM progression with time ranges."""
        # Arrange
        parser = DocumentParser()
        content = """
**BPM Progression**:
- 06:00-08:00: 100-120 BPM
- 08:00-10:00: 120-130 BPM
"""

        # Act
        result = parser._parse_bpm_progression(content, time_obj(6, 0))

        # Assert
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0].time_start == time_obj(6, 0)
        assert result[0].time_end == time_obj(8, 0)
        assert result[0].bpm_min == 100
        assert result[0].bpm_max == 120

    def test_parse_bpm_progression_single_range(self):
        """Test parsing single BPM range."""
        # Arrange
        parser = DocumentParser()
        content = """
**BPM Progression**:
- 14:00-18:00: 110-125 BPM
"""

        # Act
        result = parser._parse_bpm_progression(content, time_obj(14, 0))

        # Assert
        assert len(result) == 1
        assert result[0].bpm_min == 110
        assert result[0].bpm_max == 125


class TestParseGenreMix:
    """Tests for _parse_genre_mix() function."""

    def test_parse_genre_mix_with_percentages(self):
        """Test parsing genre mix with percentages."""
        # Arrange
        parser = DocumentParser()
        content = """
**Genre Mix**:
- Electronic: 40%
- Rock: 30%
- Pop: 30%
"""

        # Act
        result = parser._parse_genre_mix(content)

        # Assert
        assert isinstance(result, dict)
        assert len(result) == 3
        assert "Electronic" in result
        assert result["Electronic"].target_percentage == 0.40
        assert result["Rock"].target_percentage == 0.30
        assert result["Pop"].target_percentage == 0.30

    def test_parse_genre_mix_calculates_tolerance(self):
        """Test that genre mix includes tolerance."""
        # Arrange
        parser = DocumentParser()
        content = """
**Genre Mix**:
- Electronic: 50%
"""

        # Act
        result = parser._parse_genre_mix(content)

        # Assert
        assert result["Electronic"].tolerance == 0.10  # Default ±10%


class TestParseEraDistribution:
    """Tests for _parse_era_distribution() function."""

    def test_parse_era_distribution_with_years(self):
        """Test parsing era distribution with year ranges."""
        # Arrange
        parser = DocumentParser()
        content = """
**Era Distribution**:
- Current (2023-2025): 50%
- Recent (2018-2022): 30%
- Throwbacks (2000-2017): 20%
"""

        # Act
        result = parser._parse_era_distribution(content)

        # Assert
        assert isinstance(result, dict)
        assert len(result) == 3
        assert "Current" in result
        assert result["Current"].era_name == "Current"
        assert result["Current"].min_year == 2023
        assert result["Current"].max_year == 2025
        assert result["Current"].target_percentage == 0.50


class TestParseMoodGuidelines:
    """Tests for _parse_mood_guidelines() function."""

    def test_parse_mood_guidelines_list(self):
        """Test parsing mood guidelines as list."""
        # Arrange
        parser = DocumentParser()
        content = """
**Mood Guidelines**: Build energy, Uplifting, Drive-time focus
"""

        # Act
        result = parser._parse_mood_guidelines(content)

        # Assert
        assert isinstance(result, list)
        assert len(result) == 3
        assert "Build energy" in result
        assert "Uplifting" in result


class TestParseRotationPercentages:
    """Tests for _parse_rotation_percentages() function."""

    def test_parse_rotation_percentages(self):
        """Test parsing rotation percentages."""
        # Arrange
        parser = DocumentParser()
        content = """
**Rotation Distribution**:
- Power: 30%
- Medium: 40%
- Light: 30%
"""

        # Act
        result = parser._parse_rotation_percentages(content)

        # Assert
        assert isinstance(result, dict)
        assert result["Power"] == 0.30
        assert result["Medium"] == 0.40
        assert result["Light"] == 0.30


class TestParseTracksPerHour:
    """Tests for _parse_tracks_per_hour() function."""

    def test_parse_tracks_per_hour_range(self):
        """Test parsing tracks per hour range."""
        # Arrange
        parser = DocumentParser()
        content = """
**Tracks Per Hour**: 12-15
"""

        # Act
        result = parser._parse_tracks_per_hour(content)

        # Assert
        assert result == (12, 15)

    def test_parse_tracks_per_hour_single_value(self):
        """Test parsing single tracks per hour value."""
        # Arrange
        parser = DocumentParser()
        content = """
**Tracks Per Hour**: 14
"""

        # Act
        result = parser._parse_tracks_per_hour(content)

        # Assert
        # Should return same value for both min and max
        assert result[0] == result[1]


class TestParseAustralianContent:
    """Tests for _parse_australian_content() function."""

    def test_parse_australian_content_percentage(self):
        """Test parsing Australian content minimum."""
        # Arrange
        parser = DocumentParser()
        content = """
**Australian Content Minimum**: 30%
"""

        # Act
        result = parser._parse_australian_content(content)

        # Assert
        assert result == 0.30

    def test_parse_australian_content_different_percentage(self):
        """Test parsing different percentage value."""
        # Arrange
        parser = DocumentParser()
        content = """
**Australian Content Minimum**: 25%
"""

        # Act
        result = parser._parse_australian_content(content)

        # Assert
        assert result == 0.25


class TestParseTargetDemographic:
    """Tests for _parse_target_demographic() function."""

    def test_parse_target_demographic(self):
        """Test parsing target demographic."""
        # Arrange
        parser = DocumentParser()
        content = """
**Target Demographic**: 25-45 Adults
"""

        # Act
        result = parser._parse_target_demographic(content, "Morning Drive")

        # Assert
        assert result == "25-45 Adults"

    def test_parse_target_demographic_fallback(self):
        """Test fallback when demographic not found."""
        # Arrange
        parser = DocumentParser()
        content = "No demographic info"

        # Act
        result = parser._parse_target_demographic(content, "Test Show")

        # Assert
        assert result == "Test Show audience"


class TestParseContentFocus:
    """Tests for _parse_content_focus() function."""

    def test_parse_content_focus(self):
        """Test parsing content focus."""
        # Arrange
        parser = DocumentParser()
        content = """
**Content Focus**: High-energy start to the day
"""

        # Act
        result = parser._parse_content_focus(content, "Morning Drive")

        # Assert
        assert result == "High-energy start to the day"


class TestIntegration:
    """Integration tests for full document parsing."""

    @pytest.fixture
    def full_document_file(self, tmp_path: Path) -> Path:
        """Create complete station identity document."""
        content = """# Station Identity - Test Radio

## Station Overview
Test Radio - Electronic Music Station

## Weekday Programming

### Morning Drive (06:00-10:00)
- **Time**: 06:00-10:00
- **Target Demographic**: 25-45 Adults
- **BPM Progression**:
  - 06:00-08:00: 100-120 BPM
  - 08:00-10:00: 120-130 BPM
- **Genre Mix**:
  - Electronic: 50%
  - Rock: 30%
  - Pop: 20%
- **Era Distribution**:
  - Current (2023-2025): 40%
  - Recent (2018-2022): 35%
  - Modern Classics (2013-2017): 25%
- **Tracks Per Hour**: 12-15
- **Mood Guidelines**: Build energy, Uplifting, Drive-time focus
- **Content Focus**: High-energy start to the day
- **Rotation Distribution**:
  - Power: 30%
  - Medium: 40%
  - Light: 30%

### Daytime (10:00-14:00)
- **Time**: 10:00-14:00
- **Target Demographic**: 25-54 Adults
- **BPM Progression**:
  - 10:00-14:00: 110-125 BPM
- **Genre Mix**:
  - Electronic: 40%
  - Pop: 35%
  - Rock: 25%
- **Era Distribution**:
  - Current (2023-2025): 45%
  - Recent (2018-2022): 30%
  - Throwbacks (2000-2017): 25%
- **Tracks Per Hour**: 14-16
- **Mood Guidelines**: Consistent energy, Workplace-friendly
- **Content Focus**: Steady daytime programming

## Saturday Programming

### Weekend Morning (08:00-12:00)
- **Time**: 08:00-12:00
- **Target Demographic**: 18-44 Adults
- **BPM Progression**:
  - 08:00-12:00: 115-130 BPM
- **Genre Mix**:
  - Electronic: 60%
  - Pop: 25%
  - Rock: 15%
- **Era Distribution**:
  - Current (2023-2025): 50%
  - Recent (2018-2022): 50%
- **Tracks Per Hour**: 12-14
- **Mood Guidelines**: Upbeat, Weekend energy
- **Content Focus**: Weekend party vibes

## Sunday Programming

### Sunday Chill (10:00-14:00)
- **Time**: 10:00-14:00
- **Target Demographic**: 25-54 Adults
- **BPM Progression**:
  - 10:00-14:00: 90-110 BPM
- **Genre Mix**:
  - Electronic: 50%
  - Ambient: 30%
  - Pop: 20%
- **Era Distribution**:
  - Current (2023-2025): 30%
  - Recent (2018-2022): 40%
  - Throwbacks (2000-2017): 30%
- **Tracks Per Hour**: 10-12
- **Mood Guidelines**: Relaxed, Mellow, Sunday vibes
- **Content Focus**: Easy listening for Sunday

## Rotation Strategy
- **Power (30%)**: 8-12 plays per track per week
- **Medium (40%)**: 5-8 plays per track per week
- **Light (30%)**: 2-5 plays per track per week

## Content Requirements
- **Australian Content Minimum**: 30%
- **Local Content Minimum**: 10%

## Genre Definitions
- **Electronic**: House, Techno, Trance, Electronica
- **Pop**: Contemporary Pop, Dance Pop
- **Rock**: Alternative Rock, Indie Rock
"""
        doc_file = tmp_path / "station-identity-full.md"
        doc_file.write_text(content)
        return doc_file

    def test_parse_complete_document(self, full_document_file: Path):
        """Test parsing complete station identity document."""
        # Arrange
        parser = DocumentParser()

        # Act
        doc = parser.load_document(full_document_file)

        # Assert
        assert isinstance(doc, StationIdentityDocument)

        # Check programming structures
        assert len(doc.programming_structures) == 3  # Weekday, Saturday, Sunday

        # Verify weekday programming
        weekday = doc.programming_structures[0]
        assert weekday.schedule_type == ScheduleType.WEEKDAY
        assert len(weekday.dayparts) == 2  # Morning Drive and Daytime

        # Verify first daypart
        morning_drive = weekday.dayparts[0]
        assert "Morning" in morning_drive.name or "Drive" in morning_drive.name
        assert morning_drive.time_start == time_obj(6, 0)
        assert morning_drive.time_end == time_obj(10, 0)
        assert len(morning_drive.bpm_progression) == 2
        assert len(morning_drive.genre_mix) == 3

        # Verify rotation strategy
        assert doc.rotation_strategy is not None
        assert len(doc.rotation_strategy.categories) == 3

        # Verify content requirements
        assert doc.content_requirements.australian_minimum == 0.30

    def test_parse_saturday_programming(self, full_document_file: Path):
        """Test parsing Saturday programming structure."""
        # Arrange
        parser = DocumentParser()

        # Act
        doc = parser.load_document(full_document_file)

        # Assert
        saturday = [s for s in doc.programming_structures if s.schedule_type == ScheduleType.SATURDAY][0]
        assert len(saturday.dayparts) == 1
        assert saturday.dayparts[0].time_start == time_obj(8, 0)

    def test_parse_sunday_programming(self, full_document_file: Path):
        """Test parsing Sunday programming structure."""
        # Arrange
        parser = DocumentParser()

        # Act
        doc = parser.load_document(full_document_file)

        # Assert
        sunday = [s for s in doc.programming_structures if s.schedule_type == ScheduleType.SUNDAY][0]
        assert len(sunday.dayparts) == 1
        assert "Chill" in sunday.dayparts[0].name or "Sunday" in sunday.dayparts[0].name
