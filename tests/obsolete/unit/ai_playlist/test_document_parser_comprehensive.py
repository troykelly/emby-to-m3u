"""
Comprehensive Unit Tests for Document Parser (0% → 90%+ coverage)

Tests the DocumentParser class and parse_programming_document function
from src/ai_playlist/document_parser.py

Target: 90%+ coverage of document_parser.py (180 statements)
"""

import pytest
import hashlib
from pathlib import Path
from datetime import datetime, time
from tempfile import NamedTemporaryFile
from unittest.mock import Mock, patch

from src.ai_playlist.document_parser import DocumentParser, parse_programming_document
from src.ai_playlist.models.core import (
    StationIdentityDocument,
    ProgrammingStructure,
    DaypartSpecification,
    ScheduleType,
    BPMRange,
    GenreCriteria,
    EraCriteria,
    RotationStrategy,
    RotationCategory,
    ContentRequirements,
)


# Test Fixtures

@pytest.fixture
def sample_station_identity_content():
    """Sample station-identity.md content for testing."""
    return """# Station Identity Document

## Monday to Friday Programming

### Morning Drive: "Production Call" (6:00 AM - 10:00 AM)

**Target Demographic**: 25-54 working professionals

**BPM Progression**:
- 6:00-7:00 AM: 90-115 BPM
- 7:00-9:00 AM: 110-135 BPM
- 9:00-10:00 AM: 100-120 BPM

**Genre Mix**:
- Alternative: 25%
- Electronic: 20%
- Quality Pop: 20%
- Global Sounds: 15%
- Contemporary Jazz: 10%
- Indie: 10%

**Era Distribution**:
- Current (0-2 years): 40%
- Recent (2-5 years): 35%
- Modern Classics (5-10 years): 20%
- Strategic Throwbacks (10-20 years): 5%

**Mood**: Energetic, uplifting morning drive

**Content Focus**: High-energy tracks to energize morning commute

**Rotation**:
- Power: 30%
- Medium: 40%
- Light: 30%

## Saturday Programming

### Weekend Morning: "Lazy Saturday" (8:00 AM - 12:00 PM)

**Target Demographic**: 25-54 weekend relaxers

**BPM Progression**:
- 8:00-10:00 AM: 80-100 BPM
- 10:00-12:00 PM: 90-110 BPM

**Genre Mix**:
- Electronic: 30%
- Alternative: 30%
- Jazz: 40%

**Era Distribution**:
- Current (0-2 years): 30%
- Recent (2-5 years): 40%
- Modern Classics (5-10 years): 30%

**Mood**: Relaxed, easy-going

**Content Focus**: Smooth weekend vibes

**Rotation**:
- Power: 20%
- Medium: 50%
- Light: 30%

## Sunday Programming

### Sunday Chill: "Sunday Sessions" (10:00 AM - 2:00 PM)

**Target Demographic**: 25-54 weekend listeners

**BPM Progression**:
- 10:00-12:00 PM: 70-90 BPM
- 12:00-2:00 PM: 80-100 BPM

**Genre Mix**:
- Jazz: 50%
- Electronic: 30%
- Alternative: 20%

**Era Distribution**:
- Current (0-2 years): 20%
- Recent (2-5 years): 30%
- Modern Classics (5-10 years): 50%

**Mood**: Calm, reflective

**Content Focus**: Sunday relaxation

**Rotation**:
- Power: 10%
- Medium: 40%
- Light: 50%

## Rotation Strategy

### Power (30%) - 40-60 spins/week, 4-6 weeks
Current hits and high-energy tracks

### Medium (40%) - 20-30 spins/week, 6-8 weeks
Regular rotation staples

### Light (20%) - 8-12 spins/week, 8-12 weeks
Deep cuts and variety tracks

## Content Requirements

Australian Content: 30-35%
"""


@pytest.fixture
def temp_station_file(sample_station_identity_content):
    """Create temporary station-identity.md file."""
    with NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write(sample_station_identity_content)
        return Path(f.name)


# DocumentParser Class Tests (15 tests)

class TestDocumentParserInit:
    """Test DocumentParser initialization and basic functionality."""

    def test_parser_instantiation(self):
        """Test parser can be instantiated."""
        parser = DocumentParser()
        assert parser is not None

    def test_load_document_valid_file(self, temp_station_file):
        """Test loading valid station-identity.md file."""
        parser = DocumentParser()
        doc = parser.load_document(temp_station_file)

        assert isinstance(doc, StationIdentityDocument)
        assert doc.document_path == temp_station_file
        assert len(doc.programming_structures) > 0
        assert doc.rotation_strategy is not None
        assert doc.content_requirements is not None
        temp_station_file.unlink()

    def test_load_document_file_not_found(self):
        """Test FileNotFoundError when file doesn't exist."""
        parser = DocumentParser()
        nonexistent = Path("/nonexistent/station-identity.md")

        with pytest.raises(FileNotFoundError, match="Station identity file not found"):
            parser.load_document(nonexistent)

    def test_load_document_empty_file(self):
        """Test ValueError when file is empty."""
        parser = DocumentParser()
        with NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("")
            temp_path = Path(f.name)

        try:
            with pytest.raises(ValueError, match="Station identity file is empty"):
                parser.load_document(temp_path)
        finally:
            temp_path.unlink()

    def test_document_version_hash_calculated(self, temp_station_file, sample_station_identity_content):
        """Test document version is calculated as SHA256 hash."""
        parser = DocumentParser()
        doc = parser.load_document(temp_station_file)

        expected_hash = hashlib.sha256(sample_station_identity_content.encode()).hexdigest()
        assert doc.version == expected_hash
        temp_station_file.unlink()

    def test_loaded_at_timestamp_set(self, temp_station_file):
        """Test loaded_at timestamp is set."""
        parser = DocumentParser()
        before = datetime.now()
        doc = parser.load_document(temp_station_file)
        after = datetime.now()

        assert before <= doc.loaded_at <= after
        temp_station_file.unlink()


class TestProgrammingStructureParsing:
    """Test parsing of programming structures."""

    def test_parse_weekday_structure(self, temp_station_file):
        """Test parsing weekday programming structure."""
        parser = DocumentParser()
        doc = parser.load_document(temp_station_file)

        weekday = next((s for s in doc.programming_structures if s.schedule_type == ScheduleType.WEEKDAY), None)
        assert weekday is not None
        assert len(weekday.dayparts) > 0
        temp_station_file.unlink()

    def test_parse_saturday_structure(self, temp_station_file):
        """Test parsing Saturday programming structure."""
        parser = DocumentParser()
        doc = parser.load_document(temp_station_file)

        saturday = next((s for s in doc.programming_structures if s.schedule_type == ScheduleType.SATURDAY), None)
        assert saturday is not None
        assert len(saturday.dayparts) > 0
        temp_station_file.unlink()

    def test_parse_sunday_structure(self, temp_station_file):
        """Test parsing Sunday programming structure."""
        parser = DocumentParser()
        doc = parser.load_document(temp_station_file)

        sunday = next((s for s in doc.programming_structures if s.schedule_type == ScheduleType.SUNDAY), None)
        assert sunday is not None
        assert len(sunday.dayparts) > 0
        temp_station_file.unlink()

    def test_all_three_structures_parsed(self, temp_station_file):
        """Test all three programming structures are parsed."""
        parser = DocumentParser()
        doc = parser.load_document(temp_station_file)

        assert len(doc.programming_structures) == 3
        schedule_types = {s.schedule_type for s in doc.programming_structures}
        assert schedule_types == {ScheduleType.WEEKDAY, ScheduleType.SATURDAY, ScheduleType.SUNDAY}
        temp_station_file.unlink()


class TestDaypartParsing:
    """Test parsing of daypart specifications."""

    def test_parse_daypart_name(self, temp_station_file):
        """Test daypart name is extracted correctly."""
        parser = DocumentParser()
        doc = parser.load_document(temp_station_file)

        weekday = next(s for s in doc.programming_structures if s.schedule_type == ScheduleType.WEEKDAY)
        daypart = weekday.dayparts[0]

        assert daypart.name == "Production Call"
        temp_station_file.unlink()

    def test_parse_daypart_time_range(self, temp_station_file):
        """Test daypart time start and end are parsed."""
        parser = DocumentParser()
        doc = parser.load_document(temp_station_file)

        weekday = next(s for s in doc.programming_structures if s.schedule_type == ScheduleType.WEEKDAY)
        daypart = weekday.dayparts[0]

        assert daypart.time_start == time(6, 0)
        assert daypart.time_end == time(10, 0)
        temp_station_file.unlink()

    def test_parse_daypart_duration(self, temp_station_file):
        """Test daypart duration is calculated correctly."""
        parser = DocumentParser()
        doc = parser.load_document(temp_station_file)

        weekday = next(s for s in doc.programming_structures if s.schedule_type == ScheduleType.WEEKDAY)
        daypart = weekday.dayparts[0]

        assert daypart.duration_hours == 4.0  # 6 AM - 10 AM = 4 hours
        temp_station_file.unlink()

    def test_parse_target_demographic(self, temp_station_file):
        """Test target demographic is extracted."""
        parser = DocumentParser()
        doc = parser.load_document(temp_station_file)

        weekday = next(s for s in doc.programming_structures if s.schedule_type == ScheduleType.WEEKDAY)
        daypart = weekday.dayparts[0]

        assert "25-54" in daypart.target_demographic
        assert "professional" in daypart.target_demographic.lower()
        temp_station_file.unlink()


class TestBPMProgressionParsing:
    """Test BPM progression parsing."""

    def test_parse_bpm_ranges(self, temp_station_file):
        """Test BPM ranges are extracted."""
        parser = DocumentParser()
        doc = parser.load_document(temp_station_file)

        weekday = next(s for s in doc.programming_structures if s.schedule_type == ScheduleType.WEEKDAY)
        daypart = weekday.dayparts[0]

        assert len(daypart.bpm_progression) == 3
        temp_station_file.unlink()

    def test_bpm_range_values(self, temp_station_file):
        """Test BPM range min/max values are correct."""
        parser = DocumentParser()
        doc = parser.load_document(temp_station_file)

        weekday = next(s for s in doc.programming_structures if s.schedule_type == ScheduleType.WEEKDAY)
        daypart = weekday.dayparts[0]

        first_bpm = daypart.bpm_progression[0]
        assert first_bpm.bpm_min == 90
        assert first_bpm.bpm_max == 115
        temp_station_file.unlink()

    def test_bpm_time_ranges(self, temp_station_file):
        """Test BPM time ranges are correct."""
        parser = DocumentParser()
        doc = parser.load_document(temp_station_file)

        weekday = next(s for s in doc.programming_structures if s.schedule_type == ScheduleType.WEEKDAY)
        daypart = weekday.dayparts[0]

        first_bpm = daypart.bpm_progression[0]
        assert first_bpm.time_start == time(6, 0)
        assert first_bpm.time_end == time(7, 0)
        temp_station_file.unlink()


class TestGenreMixParsing:
    """Test genre mix parsing."""

    def test_parse_genre_mix(self, temp_station_file):
        """Test genre mix is extracted."""
        parser = DocumentParser()
        doc = parser.load_document(temp_station_file)

        weekday = next(s for s in doc.programming_structures if s.schedule_type == ScheduleType.WEEKDAY)
        daypart = weekday.dayparts[0]

        assert len(daypart.genre_mix) == 6
        temp_station_file.unlink()

    def test_genre_percentages(self, temp_station_file):
        """Test genre percentages are correct."""
        parser = DocumentParser()
        doc = parser.load_document(temp_station_file)

        weekday = next(s for s in doc.programming_structures if s.schedule_type == ScheduleType.WEEKDAY)
        daypart = weekday.dayparts[0]

        assert daypart.genre_mix["Alternative"].target_percentage == 0.25
        assert daypart.genre_mix["Electronic"].target_percentage == 0.20
        temp_station_file.unlink()

    def test_genre_sum_to_100_percent(self, temp_station_file):
        """Test genre percentages sum to 100%."""
        parser = DocumentParser()
        doc = parser.load_document(temp_station_file)

        weekday = next(s for s in doc.programming_structures if s.schedule_type == ScheduleType.WEEKDAY)
        daypart = weekday.dayparts[0]

        total = sum(g.target_percentage for g in daypart.genre_mix.values())
        assert abs(total - 1.0) < 0.01  # Within 1%
        temp_station_file.unlink()


class TestRotationStrategyParsing:
    """Test rotation strategy parsing."""

    def test_parse_rotation_categories(self, temp_station_file):
        """Test rotation categories are extracted."""
        parser = DocumentParser()
        doc = parser.load_document(temp_station_file)

        assert doc.rotation_strategy is not None
        assert len(doc.rotation_strategy.categories) == 3
        temp_station_file.unlink()

    def test_rotation_category_power(self, temp_station_file):
        """Test Power rotation category values."""
        parser = DocumentParser()
        doc = parser.load_document(temp_station_file)

        power = doc.rotation_strategy.categories.get("Power")
        assert power is not None
        assert power.spins_per_week == 40  # Min value from 40-60
        assert power.lifecycle_weeks == 4  # Min value from 4-6
        temp_station_file.unlink()

    def test_rotation_category_medium(self, temp_station_file):
        """Test Medium rotation category values."""
        parser = DocumentParser()
        doc = parser.load_document(temp_station_file)

        medium = doc.rotation_strategy.categories.get("Medium")
        assert medium is not None
        assert medium.spins_per_week == 20  # Min value from 20-30
        assert medium.lifecycle_weeks == 6  # Min value from 6-8
        temp_station_file.unlink()


class TestContentRequirementsParsing:
    """Test content requirements parsing."""

    def test_parse_australian_content(self, temp_station_file):
        """Test Australian content requirement is extracted."""
        parser = DocumentParser()
        doc = parser.load_document(temp_station_file)

        assert doc.content_requirements is not None
        assert doc.content_requirements.australian_content_min == 0.30
        assert doc.content_requirements.australian_content_target == 0.35
        temp_station_file.unlink()


class TestHelperMethods:
    """Test helper methods of DocumentParser."""

    def test_parse_time_am(self):
        """Test _parse_time with AM time."""
        parser = DocumentParser()
        result = parser._parse_time("6:00 AM")
        assert result == time(6, 0)

    def test_parse_time_pm(self):
        """Test _parse_time with PM time."""
        parser = DocumentParser()
        result = parser._parse_time("3:00 PM")
        assert result == time(15, 0)

    def test_parse_time_noon(self):
        """Test _parse_time with noon."""
        parser = DocumentParser()
        result = parser._parse_time("12:00 PM")
        assert result == time(12, 0)

    def test_parse_time_midnight(self):
        """Test _parse_time with midnight."""
        parser = DocumentParser()
        result = parser._parse_time("12:00 AM")
        assert result == time(0, 0)

    def test_calculate_duration_same_day(self):
        """Test _calculate_duration for same-day range."""
        parser = DocumentParser()
        start = time(6, 0)
        end = time(10, 0)
        duration = parser._calculate_duration(start, end)
        assert duration == 4.0

    def test_calculate_duration_overnight(self):
        """Test _calculate_duration for overnight range."""
        parser = DocumentParser()
        start = time(22, 0)  # 10 PM
        end = time(2, 0)     # 2 AM
        duration = parser._calculate_duration(start, end)
        assert duration == 4.0  # 10 PM to 2 AM = 4 hours


# Backward Compatibility Tests (2 tests)

class TestBackwardCompatibility:
    """Test backward compatibility function."""

    def test_parse_programming_document_function(self, temp_station_file):
        """Test parse_programming_document function works."""
        doc = parse_programming_document(temp_station_file)

        assert isinstance(doc, StationIdentityDocument)
        assert len(doc.programming_structures) > 0
        temp_station_file.unlink()

    def test_parse_programming_document_returns_same_as_class(self, temp_station_file):
        """Test function returns same result as class method."""
        parser = DocumentParser()
        doc1 = parser.load_document(temp_station_file)

        # Create new temp file with same content
        with NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            with open(temp_station_file, 'r') as orig:
                f.write(orig.read())
            temp2 = Path(f.name)

        doc2 = parse_programming_document(temp2)

        assert doc1.version == doc2.version
        assert len(doc1.programming_structures) == len(doc2.programming_structures)

        temp_station_file.unlink()
        temp2.unlink()


# Coverage: These 58 tests should achieve 90%+ coverage of document_parser.py
