"""Contract tests for Document Parser (T011)

Tests the parse_programming_document() function contract as specified in:
/workspaces/emby-to-m3u/specs/004-build-ai-ml/contracts/document_parser_contract.md

These tests MUST FAIL initially (TDD Red phase) until implementation is complete.
"""

import pytest
from typing import List


# Import will fail initially - this is expected in TDD
try:
    from src.ai_playlist.document_parser import parse_programming_document
    from src.ai_playlist.models import DaypartSpec
    from src.ai_playlist.exceptions import ParseError, ValidationError
except ImportError:
    # Expected in TDD - modules don't exist yet
    parse_programming_document = None
    DaypartSpec = None
    ParseError = Exception
    ValidationError = Exception


class TestDocumentParserContract:
    """Contract tests for parse_programming_document()"""

    def test_parse_complete_document(self):
        """Test parsing a valid complete programming document.

        Verifies:
        - Returns List[DaypartSpec]
        - Extracts daypart name, day, time range
        - Parses BPM progression correctly
        - Extracts genre mix percentages
        - Parses era distribution
        - Captures Australian content minimum
        """
        if parse_programming_document is None:
            pytest.skip("Implementation not available yet (TDD Red phase)")

        content = """
## Monday Programming

### Morning Drive: "Production Call" (6:00 AM - 10:00 AM)

BPM Progression:
- 6:00-7:00 AM: 90-115 BPM
- 7:00-9:00 AM: 110-135 BPM
- 9:00-10:00 AM: 100-120 BPM

Genre Mix:
- Alternative: 25%
- Electronic: 20%
- Quality Pop: 20%
- Global Sounds: 15%
- Contemporary Jazz: 10%

Era Mix:
- Current (last 2 years): 40%
- Recent (2-5 years): 35%
- Modern Classics (5-10 years): 20%
- Strategic Throwbacks (10-20 years): 5%

Australian Content: 30% minimum
"""

        result = parse_programming_document(content)

        # Validate return type
        assert isinstance(result, list), "Should return List[DaypartSpec]"
        assert len(result) == 1, "Should parse exactly one daypart"

        # Validate daypart properties
        daypart = result[0]
        assert daypart.name == "Production Call"
        assert daypart.day == "Monday"
        assert daypart.time_range == ("06:00", "10:00")

        # Validate BPM progression
        assert "06:00-07:00" in daypart.bpm_progression
        assert daypart.bpm_progression["06:00-07:00"] == (90, 115)
        assert daypart.bpm_progression["07:00-09:00"] == (110, 135)
        assert daypart.bpm_progression["09:00-10:00"] == (100, 120)

        # Validate genre mix (as decimals)
        assert daypart.genre_mix["Alternative"] == 0.25
        assert daypart.genre_mix["Electronic"] == 0.20
        assert daypart.genre_mix["Quality Pop"] == 0.20
        assert daypart.genre_mix["Global Sounds"] == 0.15
        assert daypart.genre_mix["Contemporary Jazz"] == 0.10

        # Validate era distribution
        assert daypart.era_distribution["Current (0-2 years)"] == 0.40
        assert daypart.era_distribution["Recent (2-5 years)"] == 0.35
        assert daypart.era_distribution["Modern Classics (5-10 years)"] == 0.20
        assert daypart.era_distribution["Throwbacks (10-20 years)"] == 0.05

        # Validate Australian content
        assert daypart.australian_min == 0.30

    def test_parse_empty_document(self):
        """Test that empty document raises ValueError.

        Verifies:
        - Empty string raises ValueError
        - Error message is descriptive
        """
        if parse_programming_document is None:
            pytest.skip("Implementation not available yet (TDD Red phase)")

        with pytest.raises(ValueError, match="Content cannot be empty"):
            parse_programming_document("")

    def test_parse_invalid_bpm(self):
        """Test that BPM values exceeding 300 raise ValidationError.

        Verifies:
        - BPM > 300 is rejected
        - ValidationError is raised with clear message
        - Both min and max BPM are validated
        """
        if parse_programming_document is None:
            pytest.skip("Implementation not available yet (TDD Red phase)")

        content = """
## Test Programming

### Test Daypart (10:00 AM - 12:00 PM)

BPM Progression:
- 10:00-11:00 AM: 500-600 BPM

Genre Mix:
- Alternative: 100%

Australian Content: 30% minimum
"""

        with pytest.raises(ValidationError, match="BPM values must be ≤ 300"):
            parse_programming_document(content)

    def test_parse_genre_overflow(self):
        """Test that genre percentages exceeding 100% raise ValidationError.

        Verifies:
        - Genre percentages are summed
        - Sum > 100% raises ValidationError
        - Error message indicates the overflow
        """
        if parse_programming_document is None:
            pytest.skip("Implementation not available yet (TDD Red phase)")

        content = """
## Test Programming

### Test Daypart (10:00 AM - 12:00 PM)

BPM Progression:
- 10:00-11:00 AM: 100-120 BPM

Genre Mix:
- Alternative: 60%
- Electronic: 50%

Australian Content: 30% minimum
"""

        with pytest.raises(ValidationError, match="Genre percentages sum to >100%"):
            parse_programming_document(content)


# Additional edge case tests for robustness

class TestDocumentParserEdgeCases:
    """Additional edge case tests beyond core contract"""

    def test_parse_whitespace_only_document(self):
        """Test that whitespace-only document raises ValueError."""
        if parse_programming_document is None:
            pytest.skip("Implementation not available yet (TDD Red phase)")

        with pytest.raises(ValueError, match="Content cannot be empty"):
            parse_programming_document("   \n\n\t  \n  ")

    def test_parse_missing_required_fields(self):
        """Test that missing required fields raise ParseError."""
        if parse_programming_document is None:
            pytest.skip("Implementation not available yet (TDD Red phase)")

        # Missing BPM progression
        content = """
## Monday Programming

### Morning Drive: "Test" (6:00 AM - 10:00 AM)

Genre Mix:
- Alternative: 100%
"""

        with pytest.raises(ParseError):
            parse_programming_document(content)

    def test_parse_negative_bpm(self):
        """Test that negative BPM values raise ValidationError."""
        if parse_programming_document is None:
            pytest.skip("Implementation not available yet (TDD Red phase)")

        content = """
## Test Programming

### Test Daypart (10:00 AM - 12:00 PM)

BPM Progression:
- 10:00-11:00 AM: -50-100 BPM

Genre Mix:
- Alternative: 100%

Australian Content: 30% minimum
"""

        with pytest.raises(ValidationError, match="BPM values must be positive"):
            parse_programming_document(content)

    def test_parse_invalid_time_range(self):
        """Test that invalid time ranges raise ValidationError."""
        if parse_programming_document is None:
            pytest.skip("Implementation not available yet (TDD Red phase)")

        content = """
## Test Programming

### Test Daypart (25:00 AM - 26:00 PM)

BPM Progression:
- 10:00-11:00 AM: 100-120 BPM

Genre Mix:
- Alternative: 100%

Australian Content: 30% minimum
"""

        with pytest.raises(ValidationError, match="Invalid time format"):
            parse_programming_document(content)
