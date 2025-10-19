"""Additional tests for playlist_planner.py fallback paths.

These tests specifically target uncovered lines in _generate_track_criteria():
- Lines 236-237: time_start/time_end fallbacks
- Line 282: australian_min fallback
- Lines 289-290: mood as list handling
"""
import pytest
from datetime import time
from src.ai_playlist.playlist_planner import _generate_track_criteria


class TestFallbackDefaults:
    """Tests for fallback default values in _generate_track_criteria."""

    def test_missing_time_start_defaults_to_midnight(self):
        """Test that missing time_start attribute defaults to time(0, 0)."""
        # Arrange - daypart without time_start attribute
        class DaypartNoTimeStart:
            def __init__(self):
                # Missing time_start - should trigger line 236 fallback
                self.time_end = time(10, 0)
                # Use non-time string as dict key to trigger else fallback (lines 235-237)
                self.bpm_progression = {"morning": (90, 115)}
                self.genre_mix = {}
                self.era_distribution = {}
                self.duration_hours = 4.0
                self.mood_guidelines = []
                self.rotation_percentages = {}

        daypart = DaypartNoTimeStart()

        # Act
        criteria = _generate_track_criteria(daypart)

        # Assert - Should use default time(0, 0) when time_start attribute missing
        assert len(criteria.bpm_ranges) == 1
        assert criteria.bpm_ranges[0].time_start == time(0, 0)
        assert criteria.bpm_ranges[0].time_end == time(10, 0)

    def test_missing_time_end_defaults_to_end_of_day(self):
        """Test that missing time_end attribute defaults to time(23, 59)."""
        # Arrange - daypart without time_end attribute
        class DaypartNoTimeEnd:
            def __init__(self):
                self.time_start = time(6, 0)
                # Missing time_end - should trigger line 237 fallback
                # Use non-time string as dict key
                self.bpm_progression = {"afternoon": (100, 125)}
                self.genre_mix = {}
                self.era_distribution = {}
                self.duration_hours = 4.0
                self.mood_guidelines = []
                self.rotation_percentages = {}

        daypart = DaypartNoTimeEnd()

        # Act
        criteria = _generate_track_criteria(daypart)

        # Assert - Should use default time(23, 59) when time_end attribute missing
        assert len(criteria.bpm_ranges) == 1
        assert criteria.bpm_ranges[0].time_start == time(6, 0)
        assert criteria.bpm_ranges[0].time_end == time(23, 59)

    def test_missing_australian_min_defaults_to_thirty_percent(self):
        """Test that missing australian_min attribute defaults to 0.30 (30%)."""
        # Arrange - daypart without australian_min
        class DaypartNoAustralianMin:
            def __init__(self):
                # Missing australian_min - should trigger default on line 280
                self.bpm_progression = []
                self.genre_mix = {}
                self.era_distribution = {}
                self.duration_hours = 4.0
                self.mood_guidelines = []
                self.rotation_percentages = {}

        daypart = DaypartNoAustralianMin()

        # Act
        criteria = _generate_track_criteria(daypart)

        # Assert - Should use default 0.30
        assert criteria.australian_content_min == 0.30

    def test_provided_australian_min_is_used(self):
        """Test that provided australian_min attribute is used (line 282)."""
        # Arrange - daypart WITH australian_min
        class DaypartWithAustralianMin:
            def __init__(self):
                self.australian_min = 0.35  # Custom value - line 282
                self.bpm_progression = []
                self.genre_mix = {}
                self.era_distribution = {}
                self.duration_hours = 4.0
                self.mood_guidelines = []
                self.rotation_percentages = {}

        daypart = DaypartWithAustralianMin()

        # Act
        criteria = _generate_track_criteria(daypart)

        # Assert - Should use provided 0.35
        assert criteria.australian_content_min == 0.35

    def test_mood_as_list_used_directly(self):
        """Test that mood attribute as list is used directly (lines 289-290)."""
        # Arrange - daypart with mood as list
        class DaypartMoodList:
            def __init__(self):
                self.mood = ["Energetic", "Uplifting", "Focused"]  # Line 290
                self.bpm_progression = []
                self.genre_mix = {}
                self.era_distribution = {}
                self.duration_hours = 4.0
                self.rotation_percentages = {}

        daypart = DaypartMoodList()

        # Act
        criteria = _generate_track_criteria(daypart)

        # Assert - mood list should be used as energy_flow
        assert criteria.energy_flow_requirements == ["Energetic", "Uplifting", "Focused"]

    def test_mood_as_string_converts_to_list(self):
        """Test that mood as string is converted to single-item list."""
        # Arrange - daypart with mood as string (line 287-288)
        class DaypartMoodString:
            def __init__(self):
                self.mood = "Relaxed"  # String - line 288
                self.bpm_progression = []
                self.genre_mix = {}
                self.era_distribution = {}
                self.duration_hours = 4.0
                self.rotation_percentages = {}

        daypart = DaypartMoodString()

        # Act
        criteria = _generate_track_criteria(daypart)

        # Assert - string should be wrapped in list
        assert criteria.energy_flow_requirements == ["Relaxed"]
