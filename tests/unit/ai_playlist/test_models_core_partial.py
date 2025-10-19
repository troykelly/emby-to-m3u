"""
Partial tests for models/core.py module.

Tests supporting dataclasses including:
- BPMRange and validation
- GenreCriteria with min/max percentage properties
- EraCriteria with min/max percentage properties
- SpecialtyConstraint
- RotationCategory
- Simple enum types
- ContentRequirements
- RotationStrategy
- ProgrammingStructure
- GenreDefinition
- StationIdentityDocument
"""
import pytest
from datetime import time, datetime

from src.ai_playlist.models.core import (
    BPMRange,
    GenreCriteria,
    EraCriteria,
    SpecialtyConstraint,
    RotationCategory,
    ScheduleType,
    ValidationStatus,
    DecisionType,
    ContentRequirements,
    RotationStrategy,
    ProgrammingStructure,
    GenreDefinition,
    StationIdentityDocument,
)


class TestBPMRange:
    """Tests for BPMRange dataclass."""

    def test_bpm_range_creation(self):
        """Test creating a valid BPMRange instance."""
        # Arrange & Act
        bpm_range = BPMRange(
            time_start=time(6, 0),
            time_end=time(10, 0),
            bpm_min=120,
            bpm_max=140,
        )

        # Assert
        assert bpm_range.time_start == time(6, 0)
        assert bpm_range.time_end == time(10, 0)
        assert bpm_range.bpm_min == 120
        assert bpm_range.bpm_max == 140

    def test_validate_valid_range(self):
        """Test validate() returns empty list for valid range."""
        # Arrange
        bpm_range = BPMRange(
            time_start=time(6, 0),
            time_end=time(10, 0),
            bpm_min=120,
            bpm_max=140,
        )

        # Act
        errors = bpm_range.validate()

        # Assert
        assert errors == []

    def test_validate_min_equals_max_fails(self):
        """Test validate() fails when min equals max."""
        # Arrange
        bpm_range = BPMRange(
            time_start=time(6, 0),
            time_end=time(10, 0),
            bpm_min=130,
            bpm_max=130,
        )

        # Act
        errors = bpm_range.validate()

        # Assert
        assert len(errors) == 1
        assert "BPM min (130) must be < max (130)" in errors[0]

    def test_validate_min_greater_than_max_fails(self):
        """Test validate() fails when min > max."""
        # Arrange
        bpm_range = BPMRange(
            time_start=time(6, 0),
            time_end=time(10, 0),
            bpm_min=150,
            bpm_max=120,
        )

        # Act
        errors = bpm_range.validate()

        # Assert
        assert len(errors) >= 1
        assert any("must be < max" in e for e in errors)

    def test_validate_bpm_min_too_low(self):
        """Test validate() fails when bpm_min < 60."""
        # Arrange
        bpm_range = BPMRange(
            time_start=time(6, 0),
            time_end=time(10, 0),
            bpm_min=50,
            bpm_max=140,
        )

        # Act
        errors = bpm_range.validate()

        # Assert
        assert len(errors) >= 1
        assert any("outside valid range 60-200" in e for e in errors)

    def test_validate_bpm_min_too_high(self):
        """Test validate() fails when bpm_min > 200."""
        # Arrange
        bpm_range = BPMRange(
            time_start=time(6, 0),
            time_end=time(10, 0),
            bpm_min=210,
            bpm_max=220,
        )

        # Act
        errors = bpm_range.validate()

        # Assert
        assert len(errors) >= 1
        assert any("outside valid range 60-200" in e for e in errors)

    def test_validate_bpm_max_too_low(self):
        """Test validate() fails when bpm_max < 60."""
        # Arrange
        bpm_range = BPMRange(
            time_start=time(6, 0),
            time_end=time(10, 0),
            bpm_min=50,
            bpm_max=55,
        )

        # Act
        errors = bpm_range.validate()

        # Assert
        # Both min and max are out of range
        assert len(errors) >= 2

    def test_validate_bpm_max_too_high(self):
        """Test validate() fails when bpm_max > 200."""
        # Arrange
        bpm_range = BPMRange(
            time_start=time(6, 0),
            time_end=time(10, 0),
            bpm_min=190,
            bpm_max=210,
        )

        # Act
        errors = bpm_range.validate()

        # Assert
        assert len(errors) >= 1
        assert any("outside valid range 60-200" in e for e in errors)

    def test_validate_boundary_values(self):
        """Test validate() with boundary values 60-200."""
        # Arrange
        bpm_range = BPMRange(
            time_start=time(6, 0),
            time_end=time(10, 0),
            bpm_min=60,
            bpm_max=200,
        )

        # Act
        errors = bpm_range.validate()

        # Assert
        assert errors == []


class TestGenreCriteria:
    """Tests for GenreCriteria dataclass."""

    def test_genre_criteria_creation(self):
        """Test creating GenreCriteria instance."""
        # Arrange & Act
        criteria = GenreCriteria(
            target_percentage=0.30,
            tolerance=0.10,
        )

        # Assert
        assert criteria.target_percentage == 0.30
        assert criteria.tolerance == 0.10

    def test_genre_criteria_default_tolerance(self):
        """Test GenreCriteria has default tolerance of 0.10."""
        # Arrange & Act
        criteria = GenreCriteria(target_percentage=0.30)

        # Assert
        assert criteria.tolerance == 0.10

    def test_min_percentage_property(self):
        """Test min_percentage property calculation."""
        # Arrange
        criteria = GenreCriteria(
            target_percentage=0.50,
            tolerance=0.10,
        )

        # Act
        min_pct = criteria.min_percentage

        # Assert
        assert min_pct == 0.40

    def test_max_percentage_property(self):
        """Test max_percentage property calculation."""
        # Arrange
        criteria = GenreCriteria(
            target_percentage=0.50,
            tolerance=0.10,
        )

        # Act
        max_pct = criteria.max_percentage

        # Assert
        assert max_pct == 0.60

    def test_min_percentage_clamped_to_zero(self):
        """Test min_percentage clamped to 0.0 when negative."""
        # Arrange
        criteria = GenreCriteria(
            target_percentage=0.05,
            tolerance=0.10,
        )

        # Act
        min_pct = criteria.min_percentage

        # Assert
        assert min_pct == 0.0  # Clamped from -0.05

    def test_max_percentage_clamped_to_one(self):
        """Test max_percentage clamped to 1.0 when > 1."""
        # Arrange
        criteria = GenreCriteria(
            target_percentage=0.95,
            tolerance=0.10,
        )

        # Act
        max_pct = criteria.max_percentage

        # Assert
        assert max_pct == 1.0  # Clamped from 1.05


class TestEraCriteria:
    """Tests for EraCriteria dataclass."""

    def test_era_criteria_creation(self):
        """Test creating EraCriteria instance."""
        # Arrange & Act
        criteria = EraCriteria(
            era_name="Modern Classics",
            min_year=2010,
            max_year=2019,
            target_percentage=0.25,
            tolerance=0.05,
        )

        # Assert
        assert criteria.era_name == "Modern Classics"
        assert criteria.min_year == 2010
        assert criteria.max_year == 2019
        assert criteria.target_percentage == 0.25
        assert criteria.tolerance == 0.05

    def test_era_criteria_default_tolerance(self):
        """Test EraCriteria has default tolerance of 0.10."""
        # Arrange & Act
        criteria = EraCriteria(
            era_name="Current",
            min_year=2020,
            max_year=2025,
            target_percentage=0.40,
        )

        # Assert
        assert criteria.tolerance == 0.10

    def test_min_percentage_property(self):
        """Test min_percentage property calculation."""
        # Arrange
        criteria = EraCriteria(
            era_name="Recent",
            min_year=2015,
            max_year=2024,
            target_percentage=0.30,
            tolerance=0.10,
        )

        # Act
        min_pct = criteria.min_percentage

        # Assert
        assert abs(min_pct - 0.20) < 0.001  # Allow for floating point imprecision

    def test_max_percentage_property(self):
        """Test max_percentage property calculation."""
        # Arrange
        criteria = EraCriteria(
            era_name="Recent",
            min_year=2015,
            max_year=2024,
            target_percentage=0.30,
            tolerance=0.10,
        )

        # Act
        max_pct = criteria.max_percentage

        # Assert
        assert max_pct == 0.40

    def test_min_percentage_clamped_to_zero(self):
        """Test min_percentage clamped to 0.0 when negative."""
        # Arrange
        criteria = EraCriteria(
            era_name="Rare Era",
            min_year=1980,
            max_year=1989,
            target_percentage=0.03,
            tolerance=0.10,
        )

        # Act
        min_pct = criteria.min_percentage

        # Assert
        assert min_pct == 0.0  # Clamped from -0.07

    def test_max_percentage_clamped_to_one(self):
        """Test max_percentage clamped to 1.0 when > 1."""
        # Arrange
        criteria = EraCriteria(
            era_name="All Time",
            min_year=1950,
            max_year=2025,
            target_percentage=0.98,
            tolerance=0.10,
        )

        # Act
        max_pct = criteria.max_percentage

        # Assert
        assert max_pct == 1.0  # Clamped from 1.08


class TestSpecialtyConstraint:
    """Tests for SpecialtyConstraint dataclass."""

    def test_specialty_constraint_creation(self):
        """Test creating SpecialtyConstraint instance."""
        # Arrange & Act
        constraint = SpecialtyConstraint(
            constraint_type="australian_only",
            description="100% Australian content for Australia Day",
            parameters={"enforce_strict": True, "allow_expat_artists": False},
        )

        # Assert
        assert constraint.constraint_type == "australian_only"
        assert "Australian content" in constraint.description
        assert constraint.parameters["enforce_strict"] is True
        assert constraint.parameters["allow_expat_artists"] is False

    def test_specialty_constraint_empty_parameters(self):
        """Test SpecialtyConstraint with empty parameters dict."""
        # Arrange & Act
        constraint = SpecialtyConstraint(
            constraint_type="theme_based",
            description="Summer vibes playlist",
            parameters={},
        )

        # Assert
        assert constraint.parameters == {}


class TestRotationCategory:
    """Tests for RotationCategory dataclass."""

    def test_rotation_category_creation(self):
        """Test creating RotationCategory instance."""
        # Arrange & Act
        category = RotationCategory(
            name="Power",
            spins_per_week=40,
            lifecycle_weeks=4,
        )

        # Assert
        assert category.name == "Power"
        assert category.spins_per_week == 40
        assert category.lifecycle_weeks == 4

    def test_rotation_category_light_rotation(self):
        """Test creating Light rotation category."""
        # Arrange & Act
        category = RotationCategory(
            name="Light",
            spins_per_week=10,
            lifecycle_weeks=12,
        )

        # Assert
        assert category.name == "Light"
        assert category.spins_per_week == 10
        assert category.lifecycle_weeks == 12


class TestEnumerations:
    """Tests for enum types."""

    def test_schedule_type_enum_values(self):
        """Test ScheduleType enum has correct values."""
        # Assert
        assert ScheduleType.WEEKDAY.value == "weekday"
        assert ScheduleType.SATURDAY.value == "saturday"
        assert ScheduleType.SUNDAY.value == "sunday"

    def test_validation_status_enum_values(self):
        """Test ValidationStatus enum has correct values."""
        # Assert
        assert ValidationStatus.PASS.value == "pass"
        assert ValidationStatus.FAIL.value == "fail"
        assert ValidationStatus.WARNING.value == "warning"

    def test_decision_type_enum_values(self):
        """Test DecisionType enum has all expected values."""
        # Assert
        assert DecisionType.TRACK_SELECTION.value == "track_selection"
        assert DecisionType.VALIDATION.value == "validation"
        assert DecisionType.ERROR.value == "error"
        assert DecisionType.RELAXATION.value == "relaxation"
        assert DecisionType.METADATA_RETRIEVAL.value == "metadata_retrieval"

    def test_schedule_type_enum_comparison(self):
        """Test ScheduleType enum member comparison."""
        # Act & Assert
        assert ScheduleType.WEEKDAY == ScheduleType.WEEKDAY
        assert ScheduleType.WEEKDAY != ScheduleType.SATURDAY

    def test_validation_status_enum_comparison(self):
        """Test ValidationStatus enum member comparison."""
        # Act & Assert
        assert ValidationStatus.PASS == ValidationStatus.PASS
        assert ValidationStatus.PASS != ValidationStatus.FAIL


class TestContentRequirements:
    """Tests for ContentRequirements dataclass."""

    def test_content_requirements_creation(self):
        """Test creating ContentRequirements instance."""
        # Arrange & Act
        requirements = ContentRequirements(
            australian_content_min=0.30,
            australian_content_target=0.35,
        )

        # Assert
        assert requirements.australian_content_min == 0.30
        assert requirements.australian_content_target == 0.35

    def test_content_requirements_typical_values(self):
        """Test ContentRequirements with typical radio values."""
        # Arrange & Act
        requirements = ContentRequirements(
            australian_content_min=0.30,
            australian_content_target=0.33,
        )

        # Assert
        assert requirements.australian_content_min == 0.30
        assert requirements.australian_content_target == 0.33


class TestRotationStrategy:
    """Tests for RotationStrategy dataclass."""

    def test_rotation_strategy_creation(self):
        """Test creating RotationStrategy with categories."""
        # Arrange
        power_category = RotationCategory(
            name="Power",
            spins_per_week=40,
            lifecycle_weeks=4,
        )
        medium_category = RotationCategory(
            name="Medium",
            spins_per_week=20,
            lifecycle_weeks=8,
        )

        # Act
        strategy = RotationStrategy(
            categories={
                "Power": power_category,
                "Medium": medium_category,
            }
        )

        # Assert
        assert len(strategy.categories) == 2
        assert strategy.categories["Power"].spins_per_week == 40
        assert strategy.categories["Medium"].spins_per_week == 20

    def test_rotation_strategy_empty_categories(self):
        """Test creating RotationStrategy with no categories."""
        # Arrange & Act
        strategy = RotationStrategy(categories={})

        # Assert
        assert len(strategy.categories) == 0


class TestProgrammingStructure:
    """Tests for ProgrammingStructure dataclass."""

    def test_programming_structure_creation(self):
        """Test creating ProgrammingStructure instance."""
        # Arrange & Act
        structure = ProgrammingStructure(
            schedule_type=ScheduleType.WEEKDAY,
            dayparts=[],
        )

        # Assert
        assert structure.schedule_type == ScheduleType.WEEKDAY
        assert structure.dayparts == []

    def test_programming_structure_weekend(self):
        """Test creating weekend programming structure."""
        # Arrange & Act
        structure = ProgrammingStructure(
            schedule_type=ScheduleType.SATURDAY,
            dayparts=[],
        )

        # Assert
        assert structure.schedule_type == ScheduleType.SATURDAY


class TestGenreDefinition:
    """Tests for GenreDefinition dataclass."""

    def test_genre_definition_creation(self):
        """Test creating GenreDefinition instance."""
        # Arrange & Act
        genre = GenreDefinition(
            name="Electronic",
            description="Electronic dance music and related sub-genres",
            parent_genre="Dance",
            typical_bpm_range=(120, 140),
        )

        # Assert
        assert genre.name == "Electronic"
        assert genre.description == "Electronic dance music and related sub-genres"
        assert genre.parent_genre == "Dance"
        assert genre.typical_bpm_range == (120, 140)

    def test_genre_definition_no_parent(self):
        """Test creating GenreDefinition with no parent genre."""
        # Arrange & Act
        genre = GenreDefinition(
            name="Rock",
            description="Rock music",
            parent_genre=None,
            typical_bpm_range=(100, 140),
        )

        # Assert
        assert genre.parent_genre is None


class TestStationIdentityDocumentLocking:
    """Tests for StationIdentityDocument locking mechanism."""

    def test_acquire_lock_when_unlocked(self):
        """Test acquiring lock on unlocked document."""
        # Arrange
        from pathlib import Path
        doc = StationIdentityDocument(
            document_path=Path("test.md"),
            programming_structures=[],
            rotation_strategy=RotationStrategy(categories={}),
            content_requirements=ContentRequirements(
                australian_content_min=0.30,
                australian_content_target=0.35,
            ),
            genre_definitions=[],
            version="test-version",
            loaded_at=datetime.now(),
        )

        # Act
        result = doc.acquire_lock("session-123")

        # Assert
        assert result is True
        assert doc.lock_id is not None
        assert doc.locked_by == "session-123"
        assert doc.lock_timestamp is not None

    def test_acquire_lock_when_already_locked(self):
        """Test acquiring lock when document is already locked."""
        # Arrange
        from pathlib import Path
        doc = StationIdentityDocument(
            document_path=Path("test.md"),
            programming_structures=[],
            rotation_strategy=RotationStrategy(categories={}),
            content_requirements=ContentRequirements(
                australian_content_min=0.30,
                australian_content_target=0.35,
            ),
            genre_definitions=[],
            version="test-version",
            loaded_at=datetime.now(),
        )
        doc.acquire_lock("session-123")

        # Act - Try to acquire again
        result = doc.acquire_lock("session-456")

        # Assert
        assert result is False
        assert doc.locked_by == "session-123"  # Original lock holder

    def test_release_lock(self):
        """Test releasing lock on document."""
        # Arrange
        from pathlib import Path
        doc = StationIdentityDocument(
            document_path=Path("test.md"),
            programming_structures=[],
            rotation_strategy=RotationStrategy(categories={}),
            content_requirements=ContentRequirements(
                australian_content_min=0.30,
                australian_content_target=0.35,
            ),
            genre_definitions=[],
            version="test-version",
            loaded_at=datetime.now(),
        )
        doc.acquire_lock("session-123")

        # Act
        doc.release_lock()

        # Assert
        assert doc.lock_id is None
        assert doc.lock_timestamp is None
        assert doc.locked_by is None

    def test_validate_empty_programming_structures(self):
        """Test validation fails when no programming structures."""
        # Arrange
        from pathlib import Path
        doc = StationIdentityDocument(
            document_path=Path("test.md"),
            programming_structures=[],  # Empty - should fail
            rotation_strategy=RotationStrategy(categories={}),
            content_requirements=ContentRequirements(
                australian_content_min=0.30,
                australian_content_target=0.35,
            ),
            genre_definitions=[],
            version="test-version",
            loaded_at=datetime.now(),
        )

        # Act
        errors = doc.validate()

        # Assert
        assert len(errors) >= 1
        assert any("programming structure" in e.lower() for e in errors)

    def test_validate_low_australian_content(self):
        """Test validation fails when Australian content too low."""
        # Arrange
        from pathlib import Path
        doc = StationIdentityDocument(
            document_path=Path("test.md"),
            programming_structures=[
                ProgrammingStructure(
                    schedule_type=ScheduleType.WEEKDAY,
                    dayparts=[],
                )
            ],
            rotation_strategy=RotationStrategy(categories={}),
            content_requirements=ContentRequirements(
                australian_content_min=0.25,  # Below 30% - should fail
                australian_content_target=0.30,
            ),
            genre_definitions=[],
            version="test-version",
            loaded_at=datetime.now(),
        )

        # Act
        errors = doc.validate()

        # Assert
        assert len(errors) >= 1
        assert any("Australian content" in e for e in errors)
