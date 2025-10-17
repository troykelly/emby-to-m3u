"""
Comprehensive tests for Playlist Planner module.

Tests playlist specification generation including:
- generate_playlist_specs()
- Playlist name generation
- Duration calculation
- Track count calculation
- Track criteria generation
- CamelCase conversion
"""
import pytest
from datetime import datetime, time as time_obj, date
from typing import List

from src.ai_playlist.playlist_planner import (
    generate_playlist_specs,
    _generate_playlist_name,
    _to_camel_case,
    _calculate_track_count,
    _calculate_duration_minutes,
    _generate_track_criteria,
)
from src.ai_playlist.models import (
    DaypartSpec,
    PlaylistSpec,
    TrackSelectionCriteria,
    ScheduleType,
    BPMRange,
    GenreCriteria,
    EraCriteria,
)


@pytest.fixture
def sample_daypart() -> DaypartSpec:
    """Create a sample daypart specification for testing."""
    return DaypartSpec(
        id="daypart-001",
        name="Morning Drive",
        schedule_type=ScheduleType.WEEKDAY,
        time_start=time_obj(6, 0),
        time_end=time_obj(10, 0),
        duration_hours=4.0,
        target_demographic="General audience",
        bpm_progression=[
            BPMRange(
                time_start=time_obj(6, 0),
                time_end=time_obj(8, 0),
                bpm_min=100,
                bpm_max=120,
            ),
            BPMRange(
                time_start=time_obj(8, 0),
                time_end=time_obj(10, 0),
                bpm_min=120,
                bpm_max=130,
            ),
        ],
        genre_mix={"Electronic": 0.50, "Pop": 0.30, "Rock": 0.20},
        era_distribution={"Current": 0.40, "Recent": 0.40, "Modern Classics": 0.20},
        mood_guidelines=["Energetic morning vibes"],
        content_focus="Morning Drive Programming",
        rotation_percentages={"Power": 0.30, "Medium": 0.40, "Light": 0.30},
        tracks_per_hour=(12, 15),
    )


class TestGeneratePlaylistSpecs:
    """Tests for generate_playlist_specs() function."""

    def test_generate_specs_from_single_daypart(self, sample_daypart: DaypartSpec):
        """Test generating playlist specs from a single daypart."""
        # Act
        specs = generate_playlist_specs([sample_daypart])

        # Assert
        assert len(specs) == 1
        assert isinstance(specs[0], PlaylistSpec)
        assert specs[0].name is not None
        assert specs[0].source_daypart_id == sample_daypart.id

    def test_generate_specs_from_multiple_dayparts(self, sample_daypart: DaypartSpec):
        """Test generating specs from multiple dayparts."""
        # Arrange
        daypart2 = DaypartSpec(
            id="daypart-002",
            name="Afternoon Session",
            schedule_type=ScheduleType.WEEKDAY,
            time_start=time_obj(14, 0),
            time_end=time_obj(18, 0),
            duration_hours=4.0,
            target_demographic="General audience",
            bpm_progression=[],
            genre_mix={"Rock": 0.60, "Alternative": 0.40},
            era_distribution={"Current": 0.50, "Recent": 0.50},
            mood_guidelines=["Energetic"],
            content_focus="Afternoon",
            rotation_percentages={"Power": 0.50, "Medium": 0.50},
            tracks_per_hour=(12, 15),
        )

        # Act
        specs = generate_playlist_specs([sample_daypart, daypart2])

        # Assert
        assert len(specs) == 2
        assert specs[0].source_daypart_id == sample_daypart.id
        assert specs[1].source_daypart_id == daypart2.id

    def test_generate_specs_raises_error_for_empty_list(self):
        """Test that empty dayparts list raises ValueError."""
        # Act & Assert
        with pytest.raises(ValueError, match="Dayparts list must not be empty"):
            generate_playlist_specs([])

    def test_generated_spec_has_valid_track_criteria(self, sample_daypart: DaypartSpec):
        """Test that generated spec has valid track selection criteria."""
        # Act
        specs = generate_playlist_specs([sample_daypart])

        # Assert
        criteria = specs[0].track_selection_criteria
        assert isinstance(criteria, TrackSelectionCriteria)
        assert len(criteria.bpm_ranges) > 0
        assert len(criteria.genre_mix) > 0

    def test_generated_spec_has_valid_track_counts(self, sample_daypart: DaypartSpec):
        """Test that generated spec has valid min/max track counts."""
        # Act
        specs = generate_playlist_specs([sample_daypart])

        # Assert
        assert specs[0].target_track_count_min > 0
        assert specs[0].target_track_count_max >= specs[0].target_track_count_min
        # 4 hours * 12-15 tracks/hour = 48-60 tracks
        assert 40 <= specs[0].target_track_count_min <= 60
        assert 40 <= specs[0].target_track_count_max <= 80

    def test_generated_spec_has_unique_id(self, sample_daypart: DaypartSpec):
        """Test that each generated spec has a unique ID."""
        # Act
        specs = generate_playlist_specs([sample_daypart, sample_daypart])

        # Assert
        assert specs[0].id != specs[1].id

    def test_generated_spec_has_current_generation_date(self, sample_daypart: DaypartSpec):
        """Test that generated spec has today's date."""
        # Act
        specs = generate_playlist_specs([sample_daypart])

        # Assert
        assert specs[0].generation_date == date.today()


class TestGeneratePlaylistName:
    """Tests for _generate_playlist_name() function."""

    def test_generate_name_with_standard_format(self):
        """Test generating name with standard daypart format."""
        # Arrange
        daypart = DaypartSpec(
            id="test-001",
            name="Morning Drive",
            schedule_type=ScheduleType.WEEKDAY,
            time_start=time_obj(6, 0),
            time_end=time_obj(10, 0),
            duration_hours=4.0,
            target_demographic="Test",
            bpm_progression=[],
            genre_mix={},
            era_distribution={},
            mood_guidelines=[],
            content_focus="Test",
            rotation_percentages={},
            tracks_per_hour=(12, 15),
        )

        # Act
        name = _generate_playlist_name(daypart)

        # Assert - New format is {ScheduleType}_{ShowName}_{StartTime}_{EndTime}
        assert name == "Weekday_MorningDrive_0600_1000"
        assert "MorningDrive" in name
        assert "0600" in name
        assert "1000" in name

    def test_camel_case_removes_spaces(self):
        """Test that spaces are removed in camel case conversion."""
        # Act
        result = _to_camel_case("Morning Drive")

        # Assert
        assert result == "MorningDrive"
        assert " " not in result

    def test_camel_case_removes_special_characters(self):
        """Test that special characters are removed."""
        # Act
        result = _to_camel_case("The Session!")

        # Assert
        assert result == "TheSession"
        assert "!" not in result

    def test_camel_case_handles_hyphens(self):
        """Test that hyphens are handled correctly."""
        # Act
        result = _to_camel_case("Rock-Alternative")

        # Assert
        assert result == "RockAlternative"
        assert "-" not in result

    def test_camel_case_capitalizes_each_word(self):
        """Test that each word is capitalized."""
        # Act
        result = _to_camel_case("morning drive show")

        # Assert
        assert result == "MorningDriveShow"
        assert result[0].isupper()
        assert result[7].isupper()  # 'D' in Drive
        assert result[12].isupper()  # 'S' in Show


class TestCalculateTrackCount:
    """Tests for _calculate_track_count() function."""

    def test_calculate_track_count_with_tracks_per_hour(self):
        """Test calculating track count from tracks_per_hour attribute."""
        # Arrange
        daypart = DaypartSpec(
            id="test-001",
            name="Test",
            schedule_type=ScheduleType.WEEKDAY,
            time_start=time_obj(6, 0),
            time_end=time_obj(10, 0),
            duration_hours=4.0,
            target_demographic="Test",
            bpm_progression=[],
            genre_mix={},
            era_distribution={},
            mood_guidelines=[],
            content_focus="Test",
            rotation_percentages={},
            tracks_per_hour=(10, 14),  # 10-14 tracks per hour
        )

        # Act
        min_tracks, max_tracks = _calculate_track_count(daypart, 240)  # 4 hours = 240 min

        # Assert
        assert min_tracks == 40  # 4 hours * 10 tracks/hour
        assert max_tracks == 56  # 4 hours * 14 tracks/hour

    def test_calculate_track_count_uses_defaults_without_attribute(self):
        """Test that default values are used when tracks_per_hour is missing."""
        # Arrange
        class MinimalDaypart:
            pass

        daypart = MinimalDaypart()

        # Act
        min_tracks, max_tracks = _calculate_track_count(daypart, 180)  # 3 hours

        # Assert
        assert min_tracks == 36  # 3 hours * 12 tracks/hour (default)
        assert max_tracks == 45  # 3 hours * 15 tracks/hour (default)

    def test_calculate_track_count_handles_fractional_hours(self):
        """Test calculating track count with fractional hours."""
        # Arrange
        daypart = DaypartSpec(
            id="test-001",
            name="Test",
            schedule_type=ScheduleType.WEEKDAY,
            time_start=time_obj(6, 0),
            time_end=time_obj(7, 30),
            duration_hours=1.5,
            target_demographic="Test",
            bpm_progression=[],
            genre_mix={},
            era_distribution={},
            mood_guidelines=[],
            content_focus="Test",
            rotation_percentages={},
            tracks_per_hour=(12, 15),
        )

        # Act
        min_tracks, max_tracks = _calculate_track_count(daypart, 90)  # 1.5 hours

        # Assert
        assert min_tracks == 18  # 1.5 * 12
        assert max_tracks == 22  # 1.5 * 15 = 22.5 -> 22


class TestCalculateDurationMinutes:
    """Tests for _calculate_duration_minutes() function."""

    def test_calculate_standard_duration(self):
        """Test calculating duration for standard time range."""
        # Act
        duration = _calculate_duration_minutes(("06:00", "10:00"))

        # Assert
        assert duration == 240  # 4 hours

    def test_calculate_afternoon_duration(self):
        """Test calculating duration for afternoon time range."""
        # Act
        duration = _calculate_duration_minutes(("14:00", "18:00"))

        # Assert
        assert duration == 240  # 4 hours

    def test_calculate_short_duration(self):
        """Test calculating duration for short time range."""
        # Act
        duration = _calculate_duration_minutes(("10:00", "11:00"))

        # Assert
        assert duration == 60  # 1 hour

    def test_calculate_duration_with_minutes(self):
        """Test calculating duration with non-zero minutes."""
        # Act
        duration = _calculate_duration_minutes(("06:30", "09:45"))

        # Assert
        assert duration == 195  # 3 hours 15 minutes

    def test_calculate_early_morning_duration(self):
        """Test calculating duration starting at midnight."""
        # Act
        duration = _calculate_duration_minutes(("00:00", "06:00"))

        # Assert
        assert duration == 360  # 6 hours


class TestGenerateTrackCriteria:
    """Tests for _generate_track_criteria() function."""

    def test_generate_criteria_with_bpm_progression_list(self, sample_daypart: DaypartSpec):
        """Test generating criteria when BPM progression is already a list."""
        # Act
        criteria = _generate_track_criteria(sample_daypart)

        # Assert
        assert isinstance(criteria, TrackSelectionCriteria)
        assert len(criteria.bpm_ranges) == 2
        assert criteria.bpm_ranges[0].bpm_min == 100
        assert criteria.bpm_ranges[0].bpm_max == 120

    def test_generate_criteria_converts_genre_mix_to_criteria_objects(
        self, sample_daypart: DaypartSpec
    ):
        """Test that genre percentages are converted to GenreCriteria objects."""
        # Act
        criteria = _generate_track_criteria(sample_daypart)

        # Assert
        assert len(criteria.genre_mix) == 3
        assert "Electronic" in criteria.genre_mix
        assert isinstance(criteria.genre_mix["Electronic"], GenreCriteria)
        assert criteria.genre_mix["Electronic"].target_percentage == 0.50
        assert criteria.genre_mix["Electronic"].tolerance == 0.10

    def test_generate_criteria_converts_era_distribution_to_criteria_objects(
        self, sample_daypart: DaypartSpec
    ):
        """Test that era distributions are converted to EraCriteria objects."""
        # Act
        criteria = _generate_track_criteria(sample_daypart)

        # Assert
        assert len(criteria.era_distribution) == 3
        assert "Current" in criteria.era_distribution
        assert isinstance(criteria.era_distribution["Current"], EraCriteria)
        assert criteria.era_distribution["Current"].target_percentage == 0.40
        assert criteria.era_distribution["Current"].tolerance == 0.10

    def test_generate_criteria_sets_era_year_ranges_correctly(
        self, sample_daypart: DaypartSpec
    ):
        """Test that era year ranges are calculated correctly."""
        # Act
        criteria = _generate_track_criteria(sample_daypart)
        current_year = datetime.now().year

        # Assert
        current_era = criteria.era_distribution["Current"]
        assert current_era.min_year == current_year - 2
        assert current_era.max_year == current_year

        recent_era = criteria.era_distribution["Recent"]
        assert recent_era.min_year == current_year - 5
        assert recent_era.max_year == current_year - 2

    def test_generate_criteria_uses_default_australian_content(self):
        """Test that default Australian content minimum is used."""
        # Arrange
        daypart = DaypartSpec(
            id="test-001",
            name="Test",
            schedule_type=ScheduleType.WEEKDAY,
            time_start=time_obj(6, 0),
            time_end=time_obj(10, 0),
            duration_hours=4.0,
            target_demographic="Test",
            bpm_progression=[],
            genre_mix={},
            era_distribution={},
            mood_guidelines=[],
            content_focus="Test",
            rotation_percentages={},
            tracks_per_hour=(12, 15),
        )

        # Act
        criteria = _generate_track_criteria(daypart)

        # Assert
        assert criteria.australian_content_min == 0.30  # Default

    def test_generate_criteria_extracts_energy_flow_from_mood_guidelines(
        self, sample_daypart: DaypartSpec
    ):
        """Test that energy flow is extracted from mood_guidelines."""
        # Act
        criteria = _generate_track_criteria(sample_daypart)

        # Assert
        assert len(criteria.energy_flow_requirements) > 0
        assert "Energetic morning vibes" in criteria.energy_flow_requirements

    def test_generate_criteria_extracts_rotation_distribution(
        self, sample_daypart: DaypartSpec
    ):
        """Test that rotation distribution is extracted."""
        # Act
        criteria = _generate_track_criteria(sample_daypart)

        # Assert
        assert "Power" in criteria.rotation_distribution
        assert criteria.rotation_distribution["Power"] == 0.30
        assert criteria.rotation_distribution["Medium"] == 0.40

    def test_generate_criteria_sets_no_repeat_window_from_duration(
        self, sample_daypart: DaypartSpec
    ):
        """Test that no-repeat window is set from daypart duration."""
        # Act
        criteria = _generate_track_criteria(sample_daypart)

        # Assert
        assert criteria.no_repeat_window_hours == 4.0  # Same as duration_hours

    def test_generate_criteria_handles_missing_attributes_gracefully(self):
        """Test that missing optional attributes don't cause errors."""
        # Arrange - Minimal daypart with only required fields
        daypart = DaypartSpec(
            id="test-001",
            name="Minimal",
            schedule_type=ScheduleType.WEEKDAY,
            time_start=time_obj(6, 0),
            time_end=time_obj(10, 0),
            duration_hours=4.0,
            target_demographic="Test",
            bpm_progression=[],
            genre_mix={},
            era_distribution={},
            mood_guidelines=[],
            content_focus="Test",
            rotation_percentages={},
            tracks_per_hour=(12, 15),
        )

        # Act
        criteria = _generate_track_criteria(daypart)

        # Assert
        assert isinstance(criteria, TrackSelectionCriteria)
        assert criteria.australian_content_min == 0.30  # Default

    def test_generate_criteria_handles_bpm_progression_dict(self):
        """Test converting BPM progression from dict format to BPMRange list."""
        # Arrange
        class DaypartWithDictBPM:
            def __init__(self):
                self.bpm_progression = {
                    "06:00-08:00": (100, 120),
                    "08:00-10:00": (120, 130),
                }
                self.time_start = time_obj(6, 0)
                self.time_end = time_obj(10, 0)
                self.genre_mix = {}
                self.era_distribution = {}
                self.duration_hours = 4.0
                self.mood_guidelines = []
                self.rotation_percentages = {}

        daypart = DaypartWithDictBPM()

        # Act
        criteria = _generate_track_criteria(daypart)

        # Assert
        assert len(criteria.bpm_ranges) == 2
        assert all(isinstance(r, BPMRange) for r in criteria.bpm_ranges)

    def test_generate_criteria_handles_string_mood(self):
        """Test that single string mood is converted to list."""
        # Arrange
        class DaypartWithStringMood:
            def __init__(self):
                self.mood = "Energetic"  # String instead of list
                self.bpm_progression = []
                self.genre_mix = {}
                self.era_distribution = {}
                self.duration_hours = 4.0
                self.rotation_percentages = {}

        daypart = DaypartWithStringMood()

        # Act
        criteria = _generate_track_criteria(daypart)

        # Assert
        assert "Energetic" in criteria.energy_flow_requirements


class TestDaypartEdgeCases:
    """Tests for edge cases in daypart criteria extraction."""

    def test_daypart_without_time_attributes(self):
        """Test handling daypart without time_start/time_end attributes."""
        # Arrange
        from unittest.mock import Mock
        daypart = Mock()
        # Mock has bpm_progression but no time_start/time_end
        daypart.bpm_progression = {"120-130": "6:00-10:00"}
        # Remove time attributes
        del daypart.time_start
