"""
Comprehensive Edge Case Tests for Playlist Planner

Tests edge cases, boundary conditions, and error paths for the playlist_planner module.

Coverage target: 95%
"""

import pytest
from datetime import datetime, time
from typing import List, Dict, Tuple
import uuid

from src.ai_playlist.playlist_planner import (
    generate_playlist_specs,
    _generate_playlist_name,
    _to_camel_case,
    _calculate_duration_minutes,
    _generate_track_criteria,
)
from src.ai_playlist.models import DaypartSpec, PlaylistSpec, TrackSelectionCriteria


# Test fixtures
@pytest.fixture
def minimal_daypart():
    """Create minimal valid daypart for testing"""
    return DaypartSpec(
        name="Test Show",
        day="Monday",
        time_range=("10:00", "12:00"),
        bpm_progression={"10:00-11:00": (100, 120)},
        genre_mix={"Alternative": 1.0},
        era_distribution={},
        australian_min=0.30,
        mood="test mood",
        tracks_per_hour=12,
    )


@pytest.fixture
def complex_daypart():
    """Create complex daypart with all fields populated"""
    return DaypartSpec(
        name="Complex Production Show",
        day="Wednesday",
        time_range=("06:00", "10:00"),
        bpm_progression={
            "06:00-07:00": (90, 115),
            "07:00-09:00": (110, 135),
            "09:00-10:00": (100, 120),
        },
        genre_mix={
            "Alternative": 0.25,
            "Electronic": 0.20,
            "Quality Pop": 0.20,
            "Global Sounds": 0.15,
            "Contemporary Jazz": 0.10,
            "Indie": 0.10,
        },
        era_distribution={
            "Current (0-2 years)": 0.40,
            "Recent (2-5 years)": 0.35,
            "Modern Classics (5-10 years)": 0.20,
            "Throwbacks (10-20 years)": 0.05,
        },
        australian_min=0.30,
        mood="energetic morning drive",
        tracks_per_hour=14,
    )


class TestEmptyAndInvalidInput:
    """Test handling of empty and invalid inputs"""

    def test_empty_dayparts_list_raises_error(self):
        """Test that empty dayparts list raises ValueError"""
        with pytest.raises(ValueError, match="Dayparts list must not be empty"):
            generate_playlist_specs([])

    def test_none_dayparts_list_raises_error(self):
        """Test that None dayparts list raises appropriate error"""
        with pytest.raises((ValueError, TypeError)):
            generate_playlist_specs(None)

    def test_single_daypart_success(self, minimal_daypart):
        """Test single daypart generates one playlist spec"""
        result = generate_playlist_specs([minimal_daypart])

        assert len(result) == 1
        assert isinstance(result[0], PlaylistSpec)
        assert result[0].daypart == minimal_daypart


class TestPlaylistNameGeneration:
    """Test playlist name generation edge cases"""

    def test_name_with_special_characters(self):
        """Test daypart name with special characters is cleaned"""
        daypart = DaypartSpec(
            name="The Show! (2024) - Special Edition",
            day="Monday",
            time_range=("10:00", "12:00"),
            bpm_progression={"10:00-11:00": (100, 120)},
            genre_mix={"Alternative": 1.0},
            era_distribution={},
            australian_min=0.30,
            mood="test",
            tracks_per_hour=12,
        )

        name = _generate_playlist_name(daypart)
        # Special characters should be removed
        assert "!" not in name
        assert "(" not in name
        assert ")" not in name
        assert "-" not in name

    def test_name_with_multiple_spaces(self):
        """Test daypart name with multiple consecutive spaces"""
        daypart = DaypartSpec(
            name="The    Big    Show",
            day="Tuesday",
            time_range=("14:00", "18:00"),
            bpm_progression={"14:00-15:00": (100, 120)},
            genre_mix={"Alternative": 1.0},
            era_distribution={},
            australian_min=0.30,
            mood="test",
            tracks_per_hour=12,
        )

        name = _generate_playlist_name(daypart)
        assert "Tuesday_TheBigShow_1400_1800" == name

    def test_name_with_hyphens(self):
        """Test daypart name with hyphens"""
        daypart = DaypartSpec(
            name="The-Morning-Show",
            day="Friday",
            time_range=("06:00", "10:00"),
            bpm_progression={"06:00-07:00": (100, 120)},
            genre_mix={"Alternative": 1.0},
            era_distribution={},
            australian_min=0.30,
            mood="test",
            tracks_per_hour=12,
        )

        name = _generate_playlist_name(daypart)
        assert name == "Friday_TheMorningShow_0600_1000"

    def test_name_unicode_characters(self):
        """Test daypart name with Unicode characters"""
        daypart = DaypartSpec(
            name="Café Music Show ☀️",
            day="Saturday",
            time_range=("08:00", "12:00"),
            bpm_progression={"08:00-09:00": (100, 120)},
            genre_mix={"Alternative": 1.0},
            era_distribution={},
            australian_min=0.30,
            mood="test",
            tracks_per_hour=12,
        )

        name = _generate_playlist_name(daypart)
        # Unicode should be removed
        assert "Saturday_CafMusicShow_0800_1200" == name

    def test_name_single_word(self):
        """Test single-word daypart name"""
        daypart = DaypartSpec(
            name="Sunrise",
            day="Sunday",
            time_range=("05:00", "08:00"),
            bpm_progression={"05:00-06:00": (100, 120)},
            genre_mix={"Alternative": 1.0},
            era_distribution={},
            australian_min=0.30,
            mood="test",
            tracks_per_hour=12,
        )

        name = _generate_playlist_name(daypart)
        assert name == "Sunday_Sunrise_0500_0800"

    def test_name_all_lowercase(self):
        """Test all lowercase daypart name is properly capitalized"""
        daypart = DaypartSpec(
            name="morning vibes",
            day="Monday",
            time_range=("06:00", "10:00"),
            bpm_progression={"06:00-07:00": (100, 120)},
            genre_mix={"Alternative": 1.0},
            era_distribution={},
            australian_min=0.30,
            mood="test",
            tracks_per_hour=12,
        )

        name = _generate_playlist_name(daypart)
        assert name == "Monday_MorningVibes_0600_1000"

    def test_name_all_uppercase(self):
        """Test all uppercase daypart name"""
        daypart = DaypartSpec(
            name="MORNING SHOW",
            day="Thursday",
            time_range=("06:00", "10:00"),
            bpm_progression={"06:00-07:00": (100, 120)},
            genre_mix={"Alternative": 1.0},
            era_distribution={},
            australian_min=0.30,
            mood="test",
            tracks_per_hour=12,
        )

        name = _generate_playlist_name(daypart)
        assert name == "Thursday_MorningShow_0600_1000"


class TestCamelCaseConversion:
    """Test _to_camel_case function edge cases"""

    def test_empty_string(self):
        """Test empty string returns empty"""
        assert _to_camel_case("") == ""

    def test_single_character(self):
        """Test single character"""
        assert _to_camel_case("a") == "A"

    def test_numbers_in_text(self):
        """Test text with numbers"""
        assert _to_camel_case("Show 2024") == "Show2024"

    def test_only_special_characters(self):
        """Test string with only special characters"""
        assert _to_camel_case("!!!@@@###") == ""

    def test_mixed_separators(self):
        """Test string with mixed separators"""
        # Underscore is not treated as separator in current implementation
        assert _to_camel_case("the-morning show-time") == "TheMorningShowTime"


class TestDurationCalculation:
    """Test duration calculation edge cases"""

    def test_short_duration_5_minutes(self):
        """Test very short 5-minute duration"""
        duration = _calculate_duration_minutes(("12:00", "12:05"))
        assert duration == 5

    def test_long_duration_12_hours(self):
        """Test long 12-hour duration"""
        duration = _calculate_duration_minutes(("06:00", "18:00"))
        assert duration == 720

    def test_full_day_duration(self):
        """Test nearly full day duration (23:59)"""
        duration = _calculate_duration_minutes(("00:00", "23:59"))
        assert duration == 1439

    def test_one_minute_duration(self):
        """Test 1-minute duration"""
        duration = _calculate_duration_minutes(("10:00", "10:01"))
        assert duration == 1

    def test_exactly_one_hour(self):
        """Test exactly 1-hour duration"""
        duration = _calculate_duration_minutes(("10:00", "11:00"))
        assert duration == 60

    def test_midnight_crossing(self):
        """Test time range crossing midnight (results in negative, not handled)"""
        # This is a known limitation - crossing midnight not supported
        duration = _calculate_duration_minutes(("23:00", "01:00"))
        assert duration == -1320  # Negative duration, needs special handling

    def test_same_start_and_end_time(self):
        """Test same start and end time results in 0 duration"""
        duration = _calculate_duration_minutes(("12:00", "12:00"))
        assert duration == 0

    def test_times_with_minutes(self):
        """Test non-hour-aligned times"""
        duration = _calculate_duration_minutes(("09:15", "10:45"))
        assert duration == 90


class TestTrackCriteriaGeneration:
    """Test track selection criteria generation edge cases"""

    def test_criteria_from_minimal_daypart(self, minimal_daypart):
        """Test criteria generation from minimal daypart"""
        criteria = _generate_track_criteria(minimal_daypart)

        assert isinstance(criteria, TrackSelectionCriteria)
        assert criteria.bpm_range == (100, 120)
        assert criteria.bpm_tolerance == 10
        assert criteria.australian_min == 0.30
        assert criteria.energy_flow == "test mood"

    def test_criteria_genre_mix_tolerance(self, complex_daypart):
        """Test genre mix includes ±5% tolerance"""
        criteria = _generate_track_criteria(complex_daypart)

        # Check Alternative: 0.25 becomes (0.20, 0.30)
        assert criteria.genre_mix["Alternative"] == pytest.approx((0.20, 0.30))
        # Check Electronic: 0.20 becomes (0.15, 0.25)
        min_elec, max_elec = criteria.genre_mix["Electronic"]
        assert min_elec == pytest.approx(0.15)
        assert max_elec == pytest.approx(0.25)

    def test_criteria_era_tolerance(self, complex_daypart):
        """Test era distribution includes ±5% tolerance"""
        criteria = _generate_track_criteria(complex_daypart)

        # Check Current: 0.40 becomes (0.35, 0.45)
        min_curr, max_curr = criteria.era_distribution["Current (0-2 years)"]
        assert min_curr == pytest.approx(0.35)
        assert max_curr == pytest.approx(0.45)
        # Check Throwbacks: 0.05 becomes (0.00, 0.10)
        min_throw, max_throw = criteria.era_distribution["Throwbacks (10-20 years)"]
        assert min_throw == pytest.approx(0.00)
        assert max_throw == pytest.approx(0.10)

    def test_criteria_tolerance_clamping_at_zero(self):
        """Test tolerance doesn't go below 0%"""
        daypart = DaypartSpec(
            name="Test",
            day="Monday",
            time_range=("10:00", "12:00"),
            bpm_progression={"10:00-11:00": (100, 120)},
            genre_mix={"Alternative": 0.03},  # 3%
            era_distribution={"Current (0-2 years)": 0.02},  # 2%
            australian_min=0.30,
            mood="test",
            tracks_per_hour=12,
        )

        criteria = _generate_track_criteria(daypart)

        # 3% ± 5% should clamp at 0%, not go negative
        min_genre, max_genre = criteria.genre_mix["Alternative"]
        assert min_genre == 0.0
        assert max_genre == 0.08

        # 2% ± 5% should clamp at 0%
        min_era, max_era = criteria.era_distribution["Current (0-2 years)"]
        assert min_era == 0.0
        assert max_era == 0.07

    def test_criteria_tolerance_clamping_at_one(self):
        """Test tolerance doesn't exceed 100%"""
        daypart = DaypartSpec(
            name="Test",
            day="Monday",
            time_range=("10:00", "12:00"),
            bpm_progression={"10:00-11:00": (100, 120)},
            genre_mix={"Alternative": 0.98},  # 98%
            era_distribution={"Current (0-2 years)": 0.97},  # 97%
            australian_min=0.30,
            mood="test",
            tracks_per_hour=12,
        )

        criteria = _generate_track_criteria(daypart)

        # 98% ± 5% should clamp at 100%
        min_genre, max_genre = criteria.genre_mix["Alternative"]
        assert min_genre == pytest.approx(0.93)
        assert max_genre == pytest.approx(1.0)

        # 97% ± 5% should clamp at 100%
        min_era, max_era = criteria.era_distribution["Current (0-2 years)"]
        assert min_era == pytest.approx(0.92)
        assert max_era == pytest.approx(1.0)

    def test_criteria_bpm_range_extraction(self):
        """Test BPM range uses overall min and max"""
        daypart = DaypartSpec(
            name="Test",
            day="Monday",
            time_range=("06:00", "10:00"),
            bpm_progression={
                "06:00-07:00": (80, 100),
                "07:00-09:00": (120, 150),
                "09:00-10:00": (90, 110),
            },
            genre_mix={"Alternative": 1.0},
            era_distribution={},
            australian_min=0.30,
            mood="test",
            tracks_per_hour=12,
        )

        criteria = _generate_track_criteria(daypart)

        # Should use overall min (80) and overall max (150)
        assert criteria.bpm_range == (80, 150)

    def test_criteria_empty_era_distribution(self, minimal_daypart):
        """Test criteria with empty era distribution"""
        criteria = _generate_track_criteria(minimal_daypart)

        assert criteria.era_distribution == {}

    def test_criteria_excluded_tracks_empty(self, minimal_daypart):
        """Test excluded_track_ids starts empty"""
        criteria = _generate_track_criteria(minimal_daypart)

        assert criteria.excluded_track_ids == []


class TestMultipleDaypartsProcessing:
    """Test processing of multiple dayparts"""

    def test_multiple_dayparts_same_day(self):
        """Test multiple dayparts for same day"""
        dayparts = [
            DaypartSpec(
                name="Morning Show",
                day="Monday",
                time_range=("06:00", "10:00"),
                bpm_progression={"06:00-07:00": (100, 120)},
                genre_mix={"Alternative": 1.0},
                era_distribution={},
                australian_min=0.30,
                mood="morning",
                tracks_per_hour=12,
            ),
            DaypartSpec(
                name="Afternoon Show",
                day="Monday",
                time_range=("14:00", "18:00"),
                bpm_progression={"14:00-15:00": (90, 110)},
                genre_mix={"Jazz": 1.0},
                era_distribution={},
                australian_min=0.30,
                mood="afternoon",
                tracks_per_hour=12,
            ),
        ]

        result = generate_playlist_specs(dayparts)

        assert len(result) == 2
        assert result[0].name == "Monday_MorningShow_0600_1000"
        assert result[1].name == "Monday_AfternoonShow_1400_1800"

    def test_multiple_dayparts_different_days(self):
        """Test dayparts across different days"""
        dayparts = []
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

        for day in days:
            dayparts.append(
                DaypartSpec(
                    name=f"{day} Morning",
                    day=day,
                    time_range=("06:00", "10:00"),
                    bpm_progression={"06:00-07:00": (100, 120)},
                    genre_mix={"Alternative": 1.0},
                    era_distribution={},
                    australian_min=0.30,
                    mood="morning",
                    tracks_per_hour=12,
                )
            )

        result = generate_playlist_specs(dayparts)

        assert len(result) == 7
        for i, day in enumerate(days):
            assert result[i].daypart.day == day

    def test_very_large_number_of_dayparts(self):
        """Test processing 100+ dayparts"""
        dayparts = []

        for i in range(100):
            dayparts.append(
                DaypartSpec(
                    name=f"Show {i}",
                    day="Monday",
                    time_range=("10:00", "12:00"),
                    bpm_progression={"10:00-11:00": (100, 120)},
                    genre_mix={"Alternative": 1.0},
                    era_distribution={},
                    australian_min=0.30,
                    mood="test",
                    tracks_per_hour=12,
                )
            )

        result = generate_playlist_specs(dayparts)

        assert len(result) == 100
        # Verify each has unique ID
        ids = [spec.id for spec in result]
        assert len(set(ids)) == 100


class TestPlaylistSpecCreation:
    """Test complete playlist spec creation"""

    def test_playlist_spec_has_valid_uuid(self, minimal_daypart):
        """Test playlist spec has valid UUID"""
        result = generate_playlist_specs([minimal_daypart])

        # Should be parseable as UUID
        uuid_obj = uuid.UUID(result[0].id)
        assert str(uuid_obj) == result[0].id

    def test_playlist_spec_created_at_is_recent(self, minimal_daypart):
        """Test created_at timestamp is recent"""
        before = datetime.now()
        result = generate_playlist_specs([minimal_daypart])
        after = datetime.now()

        assert before <= result[0].created_at <= after

    def test_playlist_spec_target_duration_matches(self, minimal_daypart):
        """Test target duration is correctly calculated"""
        result = generate_playlist_specs([minimal_daypart])

        # 10:00 to 12:00 = 120 minutes
        assert result[0].target_duration_minutes == 120

    def test_playlist_spec_contains_all_fields(self, complex_daypart):
        """Test playlist spec contains all required fields"""
        result = generate_playlist_specs([complex_daypart])

        spec = result[0]
        assert spec.id is not None
        assert spec.name is not None
        assert spec.daypart == complex_daypart
        assert spec.target_duration_minutes == 240  # 4 hours
        assert spec.track_criteria is not None
        assert spec.created_at is not None


class TestBoundaryDurations:
    """Test boundary conditions for duration calculations"""

    def test_zero_duration_daypart(self):
        """Test daypart with 0 duration (edge case - may not be valid)"""
        # Note: Zero-duration dayparts may not pass DaypartSpec validation
        # This tests the planner's handling if such a daypart exists
        try:
            daypart = DaypartSpec(
                name="Instant",
                day="Monday",
                time_range=("12:00", "12:00"),  # 0 duration
                bpm_progression={"12:00-12:01": (100, 120)},  # Use valid range
                genre_mix={"Alternative": 1.0},
                era_distribution={},
                australian_min=0.30,
                mood="test",
                tracks_per_hour=12,
            )
            result = generate_playlist_specs([daypart])
            assert result[0].target_duration_minutes == 0
        except ValueError:
            # If DaypartSpec rejects this, that's acceptable
            pytest.skip("DaypartSpec validation rejects zero-duration dayparts")

    def test_maximum_practical_duration(self):
        """Test maximum practical duration (24 hours)"""
        daypart = DaypartSpec(
            name="All Day Marathon",
            day="Saturday",
            time_range=("00:00", "23:59"),
            bpm_progression={"00:00-01:00": (100, 120)},
            genre_mix={"Alternative": 1.0},
            era_distribution={},
            australian_min=0.30,
            mood="marathon",
            tracks_per_hour=12,
        )

        result = generate_playlist_specs([daypart])
        assert result[0].target_duration_minutes == 1439


class TestConstraintEdgeCases:
    """Test edge cases in constraint handling"""

    def test_very_tight_bpm_range(self):
        """Test very tight BPM range (1 BPM difference)"""
        daypart = DaypartSpec(
            name="Precise",
            day="Monday",
            time_range=("10:00", "12:00"),
            bpm_progression={"10:00-11:00": (120, 121)},
            genre_mix={"Alternative": 1.0},
            era_distribution={},
            australian_min=0.30,
            mood="test",
            tracks_per_hour=12,
        )

        criteria = _generate_track_criteria(daypart)
        assert criteria.bpm_range == (120, 121)

    def test_very_wide_bpm_range(self):
        """Test very wide BPM range"""
        daypart = DaypartSpec(
            name="Diverse",
            day="Monday",
            time_range=("10:00", "12:00"),
            bpm_progression={"10:00-11:00": (60, 200)},
            genre_mix={"Alternative": 1.0},
            era_distribution={},
            australian_min=0.30,
            mood="test",
            tracks_per_hour=12,
        )

        criteria = _generate_track_criteria(daypart)
        assert criteria.bpm_range == (60, 200)

    def test_single_genre_100_percent(self):
        """Test single genre at 100%"""
        daypart = DaypartSpec(
            name="Mono Genre",
            day="Monday",
            time_range=("10:00", "12:00"),
            bpm_progression={"10:00-11:00": (100, 120)},
            genre_mix={"Electronic": 1.0},
            era_distribution={},
            australian_min=0.30,
            mood="test",
            tracks_per_hour=12,
        )

        criteria = _generate_track_criteria(daypart)
        assert criteria.genre_mix["Electronic"] == (0.95, 1.0)

    def test_maximum_australian_content(self):
        """Test 100% Australian content requirement"""
        daypart = DaypartSpec(
            name="Aussie Only",
            day="Monday",
            time_range=("10:00", "12:00"),
            bpm_progression={"10:00-11:00": (100, 120)},
            genre_mix={"Alternative": 1.0},
            era_distribution={},
            australian_min=1.0,
            mood="test",
            tracks_per_hour=12,
        )

        criteria = _generate_track_criteria(daypart)
        assert criteria.australian_min == 1.0
