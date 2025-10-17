"""
Unit Tests for Playlist Planner

Tests spec generation, naming schema, duration calculation, and criteria conversion.
"""

import pytest
from datetime import datetime
import uuid

from src.ai_playlist.models import DaypartSpec
from src.ai_playlist.playlist_planner import (
    generate_playlist_specs,
    _generate_playlist_name,
    _to_camel_case,
    _calculate_duration_minutes,
    _generate_track_criteria
)


class TestGeneratePlaylistSpecs:
    """Test suite for generate_playlist_specs function."""

    def test_generate_specs_from_valid_dayparts(self):
        """Test spec generation from valid daypart list."""
        dayparts = [
            DaypartSpec(
                name="Production Call",
                day="Monday",
                time_range=("06:00", "10:00"),
                bpm_progression={
                    "06:00-07:00": (90, 115),
                    "07:00-09:00": (110, 135),
                    "09:00-10:00": (105, 130)
                },
                genre_mix={
                    "Alternative": 0.25,
                    "Electronic": 0.20,
                    "Quality Pop": 0.20
                },
                era_distribution={
                    "Current (0-2 years)": 0.40,
                    "Recent (2-5 years)": 0.35
                },
                australian_min=0.30,
                mood="energetic morning vibe building to peak",
                tracks_per_hour=15
            ),
            DaypartSpec(
                name="The Session",
                day="Saturday",
                time_range=("14:00", "18:00"),
                bpm_progression={
                    "14:00-16:00": (120, 140),
                    "16:00-18:00": (125, 145)
                },
                genre_mix={
                    "Electronic": 0.40,
                    "Alternative": 0.30
                },
                era_distribution={
                    "Current (0-2 years)": 0.50,
                    "Recent (2-5 years)": 0.30
                },
                australian_min=0.30,
                mood="high energy sustained throughout",
                tracks_per_hour=18
            )
        ]

        specs = generate_playlist_specs(dayparts)

        # Verify correct number of specs generated
        assert len(specs) == 2

        # Verify first spec
        assert specs[0].name == "Monday_ProductionCall_0600_1000"
        assert specs[0].daypart == dayparts[0]
        assert specs[0].target_duration_minutes == 240  # 4 hours
        assert specs[0].track_criteria.australian_min == 0.30
        assert specs[0].track_criteria.energy_flow == "energetic morning vibe building to peak"

        # Verify second spec
        assert specs[1].name == "Saturday_TheSession_1400_1800"
        assert specs[1].daypart == dayparts[1]
        assert specs[1].target_duration_minutes == 240  # 4 hours

        # Verify UUID generation
        assert uuid.UUID(specs[0].id, version=4)
        assert uuid.UUID(specs[1].id, version=4)
        assert specs[0].id != specs[1].id

        # Verify created_at is recent
        now = datetime.now()
        assert (now - specs[0].created_at).total_seconds() < 5
        assert (now - specs[1].created_at).total_seconds() < 5

    def test_generate_specs_empty_dayparts_raises_error(self):
        """Test that empty dayparts list raises ValueError."""
        with pytest.raises(ValueError, match="Dayparts list must not be empty"):
            generate_playlist_specs([])

    def test_generate_specs_single_daypart(self):
        """Test spec generation from single daypart."""
        dayparts = [
            DaypartSpec(
                name="Test Show",
                day="Tuesday",
                time_range=("08:00", "12:00"),
                bpm_progression={"08:00-12:00": (100, 120)},
                genre_mix={"Rock": 0.50},
                era_distribution={"Current (0-2 years)": 0.60},
                australian_min=0.30,
                mood="steady energy",
                tracks_per_hour=15
            )
        ]

        specs = generate_playlist_specs(dayparts)

        assert len(specs) == 1
        assert specs[0].name == "Tuesday_TestShow_0800_1200"


class TestGeneratePlaylistName:
    """Test suite for playlist naming schema."""

    def test_naming_schema_correctness(self):
        """Test name generation follows schema: {Day}_{ShowName}_{StartTime}_{EndTime}."""
        daypart = DaypartSpec(
            name="Production Call",
            day="Monday",
            time_range=("06:00", "10:00"),
            bpm_progression={"06:00-10:00": (90, 130)},
            genre_mix={"Alternative": 0.25},
            era_distribution={"Current (0-2 years)": 0.40},
            australian_min=0.30,
            mood="energetic",
            tracks_per_hour=15
        )

        name = _generate_playlist_name(daypart)

        assert name == "Monday_ProductionCall_0600_1000"

    def test_naming_schema_with_spaces(self):
        """Test name generation removes spaces from show name."""
        daypart = DaypartSpec(
            name="The Morning Show",
            day="Wednesday",
            time_range=("07:00", "11:00"),
            bpm_progression={"07:00-11:00": (95, 125)},
            genre_mix={"Pop": 0.40},
            era_distribution={"Current (0-2 years)": 0.50},
            australian_min=0.30,
            mood="upbeat",
            tracks_per_hour=16
        )

        name = _generate_playlist_name(daypart)

        assert name == "Wednesday_TheMorningShow_0700_1100"
        assert " " not in name  # No spaces

    def test_naming_schema_with_special_characters(self):
        """Test name generation removes special characters."""
        daypart = DaypartSpec(
            name="Rock & Roll Hour!",
            day="Friday",
            time_range=("18:00", "20:00"),
            bpm_progression={"18:00-20:00": (120, 150)},
            genre_mix={"Rock": 0.60},
            era_distribution={"Classic (10+ years)": 0.70},
            australian_min=0.30,
            mood="high energy",
            tracks_per_hour=18
        )

        name = _generate_playlist_name(daypart)

        assert name == "Friday_RockRollHour_1800_2000"
        assert "&" not in name
        assert "!" not in name


class TestToCamelCase:
    """Test suite for camelCase conversion."""

    def test_simple_conversion(self):
        """Test basic camelCase conversion."""
        assert _to_camel_case("Production Call") == "ProductionCall"
        assert _to_camel_case("The Session") == "TheSession"

    def test_single_word(self):
        """Test single word capitalization."""
        assert _to_camel_case("Morning") == "Morning"
        assert _to_camel_case("show") == "Show"

    def test_special_characters_removed(self):
        """Test special character removal."""
        assert _to_camel_case("Rock & Roll!") == "RockRoll"
        assert _to_camel_case("Test-Show@#$") == "TestShow"

    def test_multiple_spaces(self):
        """Test handling of multiple spaces."""
        assert _to_camel_case("The   Morning   Show") == "TheMorningShow"

    def test_empty_string(self):
        """Test empty string handling."""
        assert _to_camel_case("") == ""


class TestCalculateDurationMinutes:
    """Test suite for duration calculation."""

    def test_duration_calculation_four_hours(self):
        """Test duration calculation for 4-hour show."""
        duration = _calculate_duration_minutes(("06:00", "10:00"))
        assert duration == 240  # 4 hours = 240 minutes

    def test_duration_calculation_one_hour(self):
        """Test duration calculation for 1-hour show."""
        duration = _calculate_duration_minutes(("14:00", "15:00"))
        assert duration == 60  # 1 hour = 60 minutes

    def test_duration_calculation_with_minutes(self):
        """Test duration calculation with non-zero minutes."""
        duration = _calculate_duration_minutes(("08:30", "12:45"))
        assert duration == 255  # 4h 15m = 255 minutes

    def test_duration_calculation_overnight_not_supported(self):
        """Test that overnight spans return negative (not currently supported)."""
        # This would require special handling for midnight crossover
        duration = _calculate_duration_minutes(("22:00", "02:00"))
        assert duration < 0  # Current implementation doesn't handle this


class TestGenerateTrackCriteria:
    """Test suite for criteria conversion from daypart."""

    def test_criteria_conversion_bpm_range(self):
        """Test BPM range extraction from progression."""
        daypart = DaypartSpec(
            name="Test",
            day="Monday",
            time_range=("06:00", "10:00"),
            bpm_progression={
                "06:00-07:00": (90, 115),
                "07:00-09:00": (110, 135),
                "09:00-10:00": (105, 130)
            },
            genre_mix={"Alternative": 0.25},
            era_distribution={"Current (0-2 years)": 0.40},
            australian_min=0.30,
            mood="energetic",
            tracks_per_hour=15
        )

        criteria = _generate_track_criteria(daypart)

        # Should use overall min (90) and max (135) from progression
        assert criteria.bpm_range == (90, 135)
        assert criteria.bpm_tolerance == 10

    def test_criteria_conversion_genre_ranges(self):
        """Test genre mix conversion to ranges with ±5% tolerance."""
        daypart = DaypartSpec(
            name="Test",
            day="Monday",
            time_range=("06:00", "10:00"),
            bpm_progression={"06:00-10:00": (90, 130)},
            genre_mix={
                "Alternative": 0.25,
                "Electronic": 0.20,
                "Quality Pop": 0.20
            },
            era_distribution={"Current (0-2 years)": 0.40},
            australian_min=0.30,
            mood="energetic",
            tracks_per_hour=15
        )

        criteria = _generate_track_criteria(daypart)

        # Check genre ranges (±5% tolerance) with floating point tolerance
        alt_min, alt_max = criteria.genre_mix["Alternative"]
        assert abs(alt_min - 0.20) < 1e-10
        assert abs(alt_max - 0.30) < 1e-10

        elec_min, elec_max = criteria.genre_mix["Electronic"]
        assert abs(elec_min - 0.15) < 1e-10
        assert abs(elec_max - 0.25) < 1e-10

        pop_min, pop_max = criteria.genre_mix["Quality Pop"]
        assert abs(pop_min - 0.15) < 1e-10
        assert abs(pop_max - 0.25) < 1e-10

        assert criteria.genre_tolerance == 0.05

    def test_criteria_conversion_era_ranges(self):
        """Test era distribution conversion to ranges with ±5% tolerance."""
        daypart = DaypartSpec(
            name="Test",
            day="Monday",
            time_range=("06:00", "10:00"),
            bpm_progression={"06:00-10:00": (90, 130)},
            genre_mix={"Alternative": 0.25},
            era_distribution={
                "Current (0-2 years)": 0.40,
                "Recent (2-5 years)": 0.35,
                "Classic (5-10 years)": 0.15
            },
            australian_min=0.30,
            mood="energetic",
            tracks_per_hour=15
        )

        criteria = _generate_track_criteria(daypart)

        # Check era ranges (±5% tolerance) with floating point tolerance
        current_min, current_max = criteria.era_distribution["Current (0-2 years)"]
        assert abs(current_min - 0.35) < 1e-10
        assert abs(current_max - 0.45) < 1e-10

        recent_min, recent_max = criteria.era_distribution["Recent (2-5 years)"]
        assert abs(recent_min - 0.30) < 1e-10
        assert abs(recent_max - 0.40) < 1e-10

        classic_min, classic_max = criteria.era_distribution["Classic (5-10 years)"]
        assert abs(classic_min - 0.10) < 1e-10
        assert abs(classic_max - 0.20) < 1e-10

        assert criteria.era_tolerance == 0.05

    def test_criteria_conversion_preserves_australian_min(self):
        """Test Australian minimum is preserved from daypart."""
        daypart = DaypartSpec(
            name="Test",
            day="Monday",
            time_range=("06:00", "10:00"),
            bpm_progression={"06:00-10:00": (90, 130)},
            genre_mix={"Alternative": 0.25},
            era_distribution={"Current (0-2 years)": 0.40},
            australian_min=0.35,  # Non-default value
            mood="energetic",
            tracks_per_hour=15
        )

        criteria = _generate_track_criteria(daypart)

        assert criteria.australian_min == 0.35

    def test_criteria_conversion_copies_mood_to_energy_flow(self):
        """Test mood is copied to energy_flow."""
        daypart = DaypartSpec(
            name="Test",
            day="Monday",
            time_range=("06:00", "10:00"),
            bpm_progression={"06:00-10:00": (90, 130)},
            genre_mix={"Alternative": 0.25},
            era_distribution={"Current (0-2 years)": 0.40},
            australian_min=0.30,
            mood="energetic morning vibe building to peak energy at hour 3",
            tracks_per_hour=15
        )

        criteria = _generate_track_criteria(daypart)

        assert criteria.energy_flow == "energetic morning vibe building to peak energy at hour 3"

    def test_criteria_conversion_initializes_empty_exclusions(self):
        """Test excluded_track_ids is initialized as empty list."""
        daypart = DaypartSpec(
            name="Test",
            day="Monday",
            time_range=("06:00", "10:00"),
            bpm_progression={"06:00-10:00": (90, 130)},
            genre_mix={"Alternative": 0.25},
            era_distribution={"Current (0-2 years)": 0.40},
            australian_min=0.30,
            mood="energetic",
            tracks_per_hour=15
        )

        criteria = _generate_track_criteria(daypart)

        assert criteria.excluded_track_ids == []

    def test_criteria_conversion_edge_case_low_percentages(self):
        """Test genre/era ranges don't go below 0.0."""
        daypart = DaypartSpec(
            name="Test",
            day="Monday",
            time_range=("06:00", "10:00"),
            bpm_progression={"06:00-10:00": (90, 130)},
            genre_mix={"Alternative": 0.03},  # Low percentage
            era_distribution={"Current (0-2 years)": 0.02},  # Very low
            australian_min=0.30,
            mood="energetic",
            tracks_per_hour=15
        )

        criteria = _generate_track_criteria(daypart)

        # Check ranges don't go below 0.0
        assert criteria.genre_mix["Alternative"] == (0.0, 0.08)  # max(0.0, 0.03 - 0.05)
        assert criteria.era_distribution["Current (0-2 years)"] == (0.0, 0.07)

    def test_criteria_conversion_edge_case_high_percentages(self):
        """Test genre/era ranges don't go above 1.0."""
        daypart = DaypartSpec(
            name="Test",
            day="Monday",
            time_range=("06:00", "10:00"),
            bpm_progression={"06:00-10:00": (90, 130)},
            genre_mix={"Rock": 0.97},  # High percentage
            era_distribution={"Classic (10+ years)": 0.98},  # Very high
            australian_min=0.30,
            mood="energetic",
            tracks_per_hour=15
        )

        criteria = _generate_track_criteria(daypart)

        # Check ranges don't exceed 1.0 with floating point tolerance
        rock_min, rock_max = criteria.genre_mix["Rock"]
        assert abs(rock_min - 0.92) < 1e-10  # 0.97 - 0.05
        assert rock_max == 1.0  # min(1.0, 0.97 + 0.05)

        classic_min, classic_max = criteria.era_distribution["Classic (10+ years)"]
        assert abs(classic_min - 0.93) < 1e-10  # 0.98 - 0.05
        assert classic_max == 1.0  # min(1.0, 0.98 + 0.05)
