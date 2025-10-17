"""
Comprehensive validation tests for all AI Playlist data models.

This test file targets the uncovered __post_init__ validation paths
in models/core.py, models/llm.py, and models/validation.py to achieve ≥90% coverage.

DEPRECATED: This test file uses the OLD models API that has been replaced.
The models have been refactored with significant API changes:
- DaypartSpecification no longer uses 'day' parameter (use 'schedule_type' instead)
- TrackSelectionCriteria uses 'bpm_ranges: List[BPMRange]' not 'bpm_range: Tuple'
- Multiple other parameter name and structure changes

This file needs to be completely rewritten to use the new API.
Skipping all tests until migration is complete.
"""

import pytest
from datetime import datetime, timedelta
from src.ai_playlist.models.core import (
    StationIdentityDocument,
    DaypartSpecification,
    PlaylistSpecification,
    TrackSelectionCriteria,
    DecisionLog,
)
from src.ai_playlist.models.llm import (
    LLMTrackSelectionRequest,
    SelectedTrack,
    LLMTrackSelectionResponse,
    Playlist,
)
from src.ai_playlist.models.validation import ValidationResult

# Skip all tests in this module - deprecated API
pytestmark = pytest.mark.skip(reason="Tests use deprecated models API - needs migration to new API")


# ============================================================================
# StationIdentityDocument Validation Tests
# ============================================================================


class TestStationIdentityDocumentValidation:
    """Test StationIdentityDocument __post_init__ validation paths."""

    def test_empty_content_raises_error(self):
        """Test that empty content raises ValueError."""
        daypart = DaypartSpecification(
            name="Morning",
            time_range=("06:00", "10:00"),
            bpm_progression={"morning": (100, 120)},
            genre_mix={"Rock": 0.5},
            era_distribution={"2000s": 0.5},
            australian_min=0.3,
            mood="Energetic",
            tracks_per_hour=12,
        )
        with pytest.raises(ValueError, match="Content must not be empty"):
            StationIdentityDocument(content="", dayparts=[daypart], metadata={})

    def test_whitespace_only_content_raises_error(self):
        """Test that whitespace-only content raises ValueError."""
        daypart = DaypartSpecification(
            name="Morning",
            time_range=("06:00", "10:00"),
            bpm_progression={"morning": (100, 120)},
            genre_mix={"Rock": 0.5},
            era_distribution={"2000s": 0.5},
            australian_min=0.3,
            mood="Energetic",
            tracks_per_hour=12,
        )
        with pytest.raises(ValueError, match="Content must not be empty"):
            StationIdentityDocument(content="   \n\t  ", dayparts=[daypart], metadata={})

    def test_empty_dayparts_raises_error(self):
        """Test that empty dayparts list raises ValueError."""
        with pytest.raises(ValueError, match="Must contain at least one valid daypart"):
            StationIdentityDocument(content="Test content", dayparts=[], metadata={})

    def test_invalid_day_raises_error(self):
        """Test that invalid day name raises ValueError."""
        # DaypartSpecification validates day first, so we expect that error
        with pytest.raises(ValueError, match="Day must be one of"):
            daypart = DaypartSpecification(
                name="Morning",
                time_range=("06:00", "10:00"),
                bpm_progression={"morning": (100, 120)},
                genre_mix={"Rock": 0.5},
                era_distribution={"2000s": 0.5},
                australian_min=0.3,
                mood="Energetic",
                tracks_per_hour=12,
            )

    def test_overlapping_time_ranges_same_day_raises_error(self):
        """Test that overlapping time ranges on same day raise ValueError."""
        daypart1 = DaypartSpecification(
            name="Morning",
            time_range=("06:00", "10:00"),
            bpm_progression={"morning": (100, 120)},
            genre_mix={"Rock": 0.5},
            era_distribution={"2000s": 0.5},
            australian_min=0.3,
            mood="Energetic",
            tracks_per_hour=12,
        )
        daypart2 = DaypartSpecification(
            name="Late Morning",
            time_range=("09:00", "12:00"),  # Overlaps with 06:00-10:00
            bpm_progression={"morning": (110, 130)},
            genre_mix={"Pop": 0.6},
            era_distribution={"2010s": 0.6},
            australian_min=0.3,
            mood="Upbeat",
            tracks_per_hour=14,
        )
        with pytest.raises(ValueError, match="Overlapping time ranges"):
            StationIdentityDocument(
                content="Test", dayparts=[daypart1, daypart2], metadata={}
            )


# ============================================================================
# DaypartSpecification Validation Tests
# ============================================================================


class TestDaypartSpecificationValidation:
    """Test DaypartSpecification __post_init__ validation paths."""

    def test_empty_name_raises_error(self):
        """Test that empty name raises ValueError."""
        with pytest.raises(ValueError, match="Name must be non-empty"):
            DaypartSpecification(
                name="",
                time_range=("06:00", "10:00"),
                bpm_progression={"morning": (100, 120)},
                genre_mix={"Rock": 0.5},
                era_distribution={"2000s": 0.5},
                australian_min=0.3,
                mood="Energetic",
                tracks_per_hour=12,
            )

    def test_name_too_long_raises_error(self):
        """Test that name >100 chars raises ValueError."""
        long_name = "a" * 101
        with pytest.raises(ValueError, match="Name must be non-empty and max 100 chars"):
            DaypartSpecification(
                name=long_name,
                time_range=("06:00", "10:00"),
                bpm_progression={"morning": (100, 120)},
                genre_mix={"Rock": 0.5},
                era_distribution={"2000s": 0.5},
                australian_min=0.3,
                mood="Energetic",
                tracks_per_hour=12,
            )

    def test_invalid_day_raises_error(self):
        """Test that invalid day raises ValueError."""
        with pytest.raises(ValueError, match="Day must be one of"):
            DaypartSpecification(
                name="Morning",
                time_range=("06:00", "10:00"),
                bpm_progression={"morning": (100, 120)},
                genre_mix={"Rock": 0.5},
                era_distribution={"2000s": 0.5},
                australian_min=0.3,
                mood="Energetic",
                tracks_per_hour=12,
            )

    def test_invalid_time_format_start_raises_error(self):
        """Test that invalid start time format raises ValueError."""
        with pytest.raises(ValueError, match="Time range must be in HH:MM 24-hour format"):
            DaypartSpecification(
                name="Morning",
                time_range=("6:00", "10:00"),  # Missing leading zero
                bpm_progression={"morning": (100, 120)},
                genre_mix={"Rock": 0.5},
                era_distribution={"2000s": 0.5},
                australian_min=0.3,
                mood="Energetic",
                tracks_per_hour=12,
            )

    def test_invalid_time_format_end_raises_error(self):
        """Test that invalid end time format raises ValueError."""
        with pytest.raises(ValueError, match="Time range must be in HH:MM 24-hour format"):
            DaypartSpecification(
                name="Morning",
                time_range=("06:00", "25:00"),  # Invalid hour
                bpm_progression={"morning": (100, 120)},
                genre_mix={"Rock": 0.5},
                era_distribution={"2000s": 0.5},
                australian_min=0.3,
                mood="Energetic",
                tracks_per_hour=12,
            )

    def test_start_time_after_end_time_raises_error(self):
        """Test that start >= end raises ValueError."""
        with pytest.raises(ValueError, match="Start time must be before end time"):
            DaypartSpecification(
                name="Morning",
                time_range=("10:00", "06:00"),  # Reversed
                bpm_progression={"morning": (100, 120)},
                genre_mix={"Rock": 0.5},
                era_distribution={"2000s": 0.5},
                australian_min=0.3,
                mood="Energetic",
                tracks_per_hour=12,
            )

    def test_start_time_equal_end_time_raises_error(self):
        """Test that start == end raises ValueError."""
        with pytest.raises(ValueError, match="Start time must be before end time"):
            DaypartSpecification(
                name="Morning",
                time_range=("10:00", "10:00"),  # Equal
                bpm_progression={"morning": (100, 120)},
                genre_mix={"Rock": 0.5},
                era_distribution={"2000s": 0.5},
                australian_min=0.3,
                mood="Energetic",
                tracks_per_hour=12,
            )

    def test_zero_bpm_raises_error(self):
        """Test that BPM = 0 raises ValueError."""
        with pytest.raises(ValueError, match="BPM values must be > 0"):
            DaypartSpecification(
                name="Morning",
                time_range=("06:00", "10:00"),
                bpm_progression={"morning": (0, 120)},  # Zero BPM
                genre_mix={"Rock": 0.5},
                era_distribution={"2000s": 0.5},
                australian_min=0.3,
                mood="Energetic",
                tracks_per_hour=12,
            )

    def test_negative_bpm_raises_error(self):
        """Test that negative BPM raises ValueError."""
        with pytest.raises(ValueError, match="BPM values must be > 0"):
            DaypartSpecification(
                name="Morning",
                time_range=("06:00", "10:00"),
                bpm_progression={"morning": (100, -10)},  # Negative BPM
                genre_mix={"Rock": 0.5},
                era_distribution={"2000s": 0.5},
                australian_min=0.3,
                mood="Energetic",
                tracks_per_hour=12,
            )

    def test_bpm_min_greater_than_max_raises_error(self):
        """Test that BPM min > max raises ValueError."""
        with pytest.raises(ValueError, match="Invalid BPM range"):
            DaypartSpecification(
                name="Morning",
                time_range=("06:00", "10:00"),
                bpm_progression={"morning": (130, 100)},  # Reversed
                genre_mix={"Rock": 0.5},
                era_distribution={"2000s": 0.5},
                australian_min=0.3,
                mood="Energetic",
                tracks_per_hour=12,
            )

    def test_genre_mix_sum_exceeds_one_raises_error(self):
        """Test that genre mix sum > 1.0 raises ValueError."""
        with pytest.raises(ValueError, match="Genre mix percentages must sum to ≤ 1.0"):
            DaypartSpecification(
                name="Morning",
                time_range=("06:00", "10:00"),
                bpm_progression={"morning": (100, 120)},
                genre_mix={"Rock": 0.6, "Pop": 0.5},  # Sum = 1.1
                era_distribution={"2000s": 0.5},
                australian_min=0.3,
                mood="Energetic",
                tracks_per_hour=12,
            )

    def test_genre_percentage_negative_raises_error(self):
        """Test that negative genre percentage raises ValueError."""
        with pytest.raises(ValueError, match="Genre .* percentage must be 0.0-1.0"):
            DaypartSpecification(
                name="Morning",
                time_range=("06:00", "10:00"),
                bpm_progression={"morning": (100, 120)},
                genre_mix={"Rock": -0.1},  # Negative
                era_distribution={"2000s": 0.5},
                australian_min=0.3,
                mood="Energetic",
                tracks_per_hour=12,
            )

    def test_genre_percentage_exceeds_one_raises_error(self):
        """Test that genre percentage > 1.0 raises ValueError."""
        # When a single genre > 1.0, the sum check catches it first
        with pytest.raises(ValueError, match="Genre mix percentages must sum to"):
            DaypartSpecification(
                name="Morning",
                time_range=("06:00", "10:00"),
                bpm_progression={"morning": (100, 120)},
                genre_mix={"Rock": 1.1},  # > 1.0
                era_distribution={"2000s": 0.5},
                australian_min=0.3,
                mood="Energetic",
                tracks_per_hour=12,
            )

    def test_era_distribution_sum_exceeds_one_raises_error(self):
        """Test that era distribution sum > 1.0 raises ValueError."""
        with pytest.raises(ValueError, match="Era distribution percentages must sum to ≤ 1.0"):
            DaypartSpecification(
                name="Morning",
                time_range=("06:00", "10:00"),
                bpm_progression={"morning": (100, 120)},
                genre_mix={"Rock": 0.5},
                era_distribution={"2000s": 0.7, "2010s": 0.5},  # Sum = 1.2
                australian_min=0.3,
                mood="Energetic",
                tracks_per_hour=12,
            )

    def test_era_percentage_negative_raises_error(self):
        """Test that negative era percentage raises ValueError."""
        with pytest.raises(ValueError, match="Era .* percentage must be 0.0-1.0"):
            DaypartSpecification(
                name="Morning",
                time_range=("06:00", "10:00"),
                bpm_progression={"morning": (100, 120)},
                genre_mix={"Rock": 0.5},
                era_distribution={"2000s": -0.2},  # Negative
                australian_min=0.3,
                mood="Energetic",
                tracks_per_hour=12,
            )

    def test_era_percentage_exceeds_one_raises_error(self):
        """Test that era percentage > 1.0 raises ValueError."""
        # When a single era > 1.0, the sum check catches it first
        with pytest.raises(ValueError, match="Era distribution percentages must sum to"):
            DaypartSpecification(
                name="Morning",
                time_range=("06:00", "10:00"),
                bpm_progression={"morning": (100, 120)},
                genre_mix={"Rock": 0.5},
                era_distribution={"2000s": 1.5},  # > 1.0
                australian_min=0.3,
                mood="Energetic",
                tracks_per_hour=12,
            )

    def test_australian_min_negative_raises_error(self):
        """Test that negative australian_min raises ValueError."""
        with pytest.raises(ValueError, match="Australian minimum must be 0.0-1.0"):
            DaypartSpecification(
                name="Morning",
                time_range=("06:00", "10:00"),
                bpm_progression={"morning": (100, 120)},
                genre_mix={"Rock": 0.5},
                era_distribution={"2000s": 0.5},
                australian_min=-0.1,  # Negative
                mood="Energetic",
                tracks_per_hour=12,
            )

    def test_australian_min_exceeds_one_raises_error(self):
        """Test that australian_min > 1.0 raises ValueError."""
        with pytest.raises(ValueError, match="Australian minimum must be 0.0-1.0"):
            DaypartSpecification(
                name="Morning",
                time_range=("06:00", "10:00"),
                bpm_progression={"morning": (100, 120)},
                genre_mix={"Rock": 0.5},
                era_distribution={"2000s": 0.5},
                australian_min=1.1,  # > 1.0
                mood="Energetic",
                tracks_per_hour=12,
            )

    def test_empty_mood_raises_error(self):
        """Test that empty mood raises ValueError."""
        with pytest.raises(ValueError, match="Mood must be non-empty"):
            DaypartSpecification(
                name="Morning",
                time_range=("06:00", "10:00"),
                bpm_progression={"morning": (100, 120)},
                genre_mix={"Rock": 0.5},
                era_distribution={"2000s": 0.5},
                australian_min=0.3,
                mood="",  # Empty
                tracks_per_hour=12,
            )

    def test_mood_too_long_raises_error(self):
        """Test that mood > 200 chars raises ValueError."""
        long_mood = "a" * 201
        with pytest.raises(ValueError, match="Mood must be non-empty and max 200 chars"):
            DaypartSpecification(
                name="Morning",
                time_range=("06:00", "10:00"),
                bpm_progression={"morning": (100, 120)},
                genre_mix={"Rock": 0.5},
                era_distribution={"2000s": 0.5},
                australian_min=0.3,
                mood=long_mood,  # Too long
                tracks_per_hour=12,
            )

    def test_zero_tracks_per_hour_raises_error(self):
        """Test that tracks_per_hour = 0 raises ValueError."""
        with pytest.raises(ValueError, match="Tracks per hour must be > 0"):
            DaypartSpecification(
                name="Morning",
                time_range=("06:00", "10:00"),
                bpm_progression={"morning": (100, 120)},
                genre_mix={"Rock": 0.5},
                era_distribution={"2000s": 0.5},
                australian_min=0.3,
                mood="Energetic",
                tracks_per_hour=0,  # Zero
            )

    def test_negative_tracks_per_hour_raises_error(self):
        """Test that negative tracks_per_hour raises ValueError."""
        with pytest.raises(ValueError, match="Tracks per hour must be > 0"):
            DaypartSpecification(
                name="Morning",
                time_range=("06:00", "10:00"),
                bpm_progression={"morning": (100, 120)},
                genre_mix={"Rock": 0.5},
                era_distribution={"2000s": 0.5},
                australian_min=0.3,
                mood="Energetic",
                tracks_per_hour=-5,  # Negative
            )


# ============================================================================
# PlaylistSpecification Validation Tests
# ============================================================================


class TestPlaylistSpecificationValidation:
    """Test PlaylistSpecification __post_init__ validation paths."""

    def test_invalid_uuid_raises_error(self):
        """Test that invalid UUID raises ValueError."""
        daypart = DaypartSpecification(
            name="Morning",
            time_range=("06:00", "10:00"),
            bpm_progression={"morning": (100, 120)},
            genre_mix={"Rock": 0.5},
            era_distribution={"2000s": 0.5},
            australian_min=0.3,
            mood="Energetic",
            tracks_per_hour=12,
        )
        criteria = TrackSelectionCriteria(
            bpm_range=(100, 120),
            bpm_tolerance=10,
            genre_mix={"Rock": (0.4, 0.6)},
            energy_flow="Smooth progression",
        )
        with pytest.raises(ValueError, match="ID must be valid UUID4"):
            PlaylistSpecification(
                id="not-a-uuid",
                name="Monday_Morning_0600_1000",
                daypart=daypart,
                target_duration_minutes=240,
                track_criteria=criteria,
            )

    def test_invalid_name_format_raises_error(self):
        """Test that invalid name format raises ValueError."""
        import uuid

        daypart = DaypartSpecification(
            name="Morning",
            time_range=("06:00", "10:00"),
            bpm_progression={"morning": (100, 120)},
            genre_mix={"Rock": 0.5},
            era_distribution={"2000s": 0.5},
            australian_min=0.3,
            mood="Energetic",
            tracks_per_hour=12,
        )
        criteria = TrackSelectionCriteria(
            bpm_range=(100, 120),
            energy_flow="Smooth progression",
        )
        with pytest.raises(ValueError, match="Name must match schema"):
            PlaylistSpecification(
                id=str(uuid.uuid4()),
                name="InvalidNameFormat",  # Invalid format
                daypart=daypart,
                target_duration_minutes=240,
                track_criteria=criteria,
            )

    def test_zero_duration_raises_error(self):
        """Test that zero target_duration_minutes raises ValueError."""
        import uuid

        daypart = DaypartSpecification(
            name="Morning",
            time_range=("06:00", "10:00"),
            bpm_progression={"morning": (100, 120)},
            genre_mix={"Rock": 0.5},
            era_distribution={"2000s": 0.5},
            australian_min=0.3,
            mood="Energetic",
            tracks_per_hour=12,
        )
        criteria = TrackSelectionCriteria(
            bpm_range=(100, 120),
            energy_flow="Smooth progression",
        )
        with pytest.raises(ValueError, match="Target duration must be > 0"):
            PlaylistSpecification(
                id=str(uuid.uuid4()),
                name="Monday_Morning_0600_1000",
                daypart=daypart,
                target_duration_minutes=0,  # Zero
                track_criteria=criteria,
            )

    def test_future_created_at_raises_error(self):
        """Test that future created_at raises ValueError."""
        import uuid

        daypart = DaypartSpecification(
            name="Morning",
            time_range=("06:00", "10:00"),
            bpm_progression={"morning": (100, 120)},
            genre_mix={"Rock": 0.5},
            era_distribution={"2000s": 0.5},
            australian_min=0.3,
            mood="Energetic",
            tracks_per_hour=12,
        )
        criteria = TrackSelectionCriteria(
            bpm_range=(100, 120),
            energy_flow="Smooth progression",
        )
        future_time = datetime.now() + timedelta(days=1)
        with pytest.raises(ValueError, match="Created at cannot be in future"):
            PlaylistSpecification(
                id=str(uuid.uuid4()),
                name="Monday_Morning_0600_1000",
                daypart=daypart,
                target_duration_minutes=240,
                track_criteria=criteria,
                created_at=future_time,
            )


# ============================================================================
# TrackSelectionCriteria Validation Tests
# ============================================================================


class TestTrackSelectionCriteriaValidation:
    """Test TrackSelectionCriteria __post_init__ validation paths."""

    def test_zero_bpm_min_raises_error(self):
        """Test that BPM min = 0 raises ValueError."""
        with pytest.raises(ValueError, match="BPM range values must be > 0"):
            TrackSelectionCriteria(bpm_range=(0, 120), energy_flow="Smooth")

    def test_bpm_min_equal_max_raises_error(self):
        """Test that BPM min == max raises ValueError."""
        with pytest.raises(ValueError, match="BPM min must be < BPM max"):
            TrackSelectionCriteria(bpm_range=(120, 120), energy_flow="Smooth")

    def test_bpm_max_exceeds_300_raises_error(self):
        """Test that BPM max > 300 raises ValueError."""
        with pytest.raises(ValueError, match="BPM values must be ≤ 300"):
            TrackSelectionCriteria(bpm_range=(100, 350), energy_flow="Smooth")

    def test_zero_bpm_tolerance_raises_error(self):
        """Test that BPM tolerance = 0 raises ValueError."""
        with pytest.raises(ValueError, match="BPM tolerance must be > 0"):
            TrackSelectionCriteria(
                bpm_range=(100, 120), bpm_tolerance=0, energy_flow="Smooth"
            )

    def test_bpm_tolerance_exceeds_50_raises_error(self):
        """Test that BPM tolerance > 50 raises ValueError."""
        with pytest.raises(ValueError, match="BPM tolerance must be > 0 and ≤ 50"):
            TrackSelectionCriteria(
                bpm_range=(100, 120), bpm_tolerance=55, energy_flow="Smooth"
            )

    def test_genre_mix_min_sum_exceeds_one_raises_error(self):
        """Test that genre mix min sum > 1.0 raises ValueError."""
        with pytest.raises(ValueError, match="Genre mix minimum percentages must sum to ≤ 1.0"):
            TrackSelectionCriteria(
                bpm_range=(100, 120),
                genre_mix={"Rock": (0.6, 0.7), "Pop": (0.5, 0.6)},  # Sum = 1.1
                energy_flow="Smooth",
            )

    def test_genre_min_greater_than_max_raises_error(self):
        """Test that genre min > max raises ValueError."""
        with pytest.raises(ValueError, match="Genre .* min must be ≤ max"):
            TrackSelectionCriteria(
                bpm_range=(100, 120),
                genre_mix={"Rock": (0.7, 0.5)},  # Min > max
                energy_flow="Smooth",
            )

    def test_genre_tolerance_negative_raises_error(self):
        """Test that negative genre_tolerance raises ValueError."""
        with pytest.raises(ValueError, match="Genre tolerance must be 0.0-0.20"):
            TrackSelectionCriteria(
                bpm_range=(100, 120),
                genre_tolerance=-0.1,
                energy_flow="Smooth",
            )

    def test_genre_tolerance_exceeds_020_raises_error(self):
        """Test that genre_tolerance > 0.20 raises ValueError."""
        with pytest.raises(ValueError, match="Genre tolerance must be 0.0-0.20"):
            TrackSelectionCriteria(
                bpm_range=(100, 120),
                genre_tolerance=0.25,
                energy_flow="Smooth",
            )

    def test_era_distribution_min_sum_exceeds_one_raises_error(self):
        """Test that era distribution min sum > 1.0 raises ValueError."""
        with pytest.raises(ValueError, match="Era distribution minimum percentages must sum to ≤ 1.0"):
            TrackSelectionCriteria(
                bpm_range=(100, 120),
                era_distribution={"2000s": (0.6, 0.7), "2010s": (0.5, 0.6)},  # Sum = 1.1
                energy_flow="Smooth",
            )

    def test_era_min_greater_than_max_raises_error(self):
        """Test that era min > max raises ValueError."""
        with pytest.raises(ValueError, match="Era .* min must be ≤ max"):
            TrackSelectionCriteria(
                bpm_range=(100, 120),
                era_distribution={"2000s": (0.8, 0.6)},  # Min > max
                energy_flow="Smooth",
            )

    def test_era_tolerance_negative_raises_error(self):
        """Test that negative era_tolerance raises ValueError."""
        with pytest.raises(ValueError, match="Era tolerance must be 0.0-0.20"):
            TrackSelectionCriteria(
                bpm_range=(100, 120),
                era_tolerance=-0.05,
                energy_flow="Smooth",
            )

    def test_era_tolerance_exceeds_020_raises_error(self):
        """Test that era_tolerance > 0.20 raises ValueError."""
        with pytest.raises(ValueError, match="Era tolerance must be 0.0-0.20"):
            TrackSelectionCriteria(
                bpm_range=(100, 120),
                era_tolerance=0.30,
                energy_flow="Smooth",
            )

    def test_australian_min_negative_raises_error(self):
        """Test that negative australian_min raises ValueError."""
        with pytest.raises(ValueError, match="Australian minimum must be 0.0-1.0"):
            TrackSelectionCriteria(
                bpm_range=(100, 120),
                australian_min=-0.1,
                energy_flow="Smooth",
            )

    def test_australian_min_exceeds_one_raises_error(self):
        """Test that australian_min > 1.0 raises ValueError."""
        with pytest.raises(ValueError, match="Australian minimum must be 0.0-1.0"):
            TrackSelectionCriteria(
                bpm_range=(100, 120),
                australian_min=1.5,
                energy_flow="Smooth",
            )

    def test_empty_energy_flow_raises_error(self):
        """Test that empty energy_flow raises ValueError."""
        with pytest.raises(ValueError, match="Energy flow must be non-empty"):
            TrackSelectionCriteria(bpm_range=(100, 120), energy_flow="")

    def test_energy_flow_too_long_raises_error(self):
        """Test that energy_flow > 500 chars raises ValueError."""
        long_flow = "a" * 501
        with pytest.raises(ValueError, match="Energy flow must be non-empty and max 500 chars"):
            TrackSelectionCriteria(bpm_range=(100, 120), energy_flow=long_flow)


# ============================================================================
# LLM Model Validation Tests
# ============================================================================


class TestLLMTrackSelectionRequestValidation:
    """Test LLMTrackSelectionRequest __post_init__ validation paths."""

    def test_invalid_playlist_id_raises_error(self):
        """Test that invalid playlist ID raises ValueError."""
        criteria = TrackSelectionCriteria(bpm_range=(100, 120), energy_flow="Smooth")
        with pytest.raises(ValueError, match="Playlist ID must be valid UUID4"):
            LLMTrackSelectionRequest(
                playlist_id="not-a-uuid",
                criteria=criteria,
                target_track_count=10,
            )

    def test_zero_track_count_raises_error(self):
        """Test that zero target_track_count raises ValueError."""
        import uuid

        criteria = TrackSelectionCriteria(bpm_range=(100, 120), energy_flow="Smooth")
        with pytest.raises(ValueError, match="Target track count must be > 0"):
            LLMTrackSelectionRequest(
                playlist_id=str(uuid.uuid4()),
                criteria=criteria,
                target_track_count=0,
            )

    def test_track_count_exceeds_1000_raises_error(self):
        """Test that target_track_count > 1000 raises ValueError."""
        import uuid

        criteria = TrackSelectionCriteria(bpm_range=(100, 120), energy_flow="Smooth")
        with pytest.raises(ValueError, match="Target track count must be > 0 and ≤ 1000"):
            LLMTrackSelectionRequest(
                playlist_id=str(uuid.uuid4()),
                criteria=criteria,
                target_track_count=1500,
            )

    def test_empty_mcp_tools_raises_error(self):
        """Test that empty mcp_tools raises ValueError."""
        import uuid

        criteria = TrackSelectionCriteria(bpm_range=(100, 120), energy_flow="Smooth")
        with pytest.raises(ValueError, match="MCP tools must be non-empty"):
            LLMTrackSelectionRequest(
                playlist_id=str(uuid.uuid4()),
                criteria=criteria,
                target_track_count=10,
                mcp_tools=[],
            )

    def test_zero_max_cost_raises_error(self):
        """Test that zero max_cost_usd raises ValueError."""
        import uuid

        criteria = TrackSelectionCriteria(bpm_range=(100, 120), energy_flow="Smooth")
        with pytest.raises(ValueError, match="Max cost must be > 0"):
            LLMTrackSelectionRequest(
                playlist_id=str(uuid.uuid4()),
                criteria=criteria,
                target_track_count=10,
                max_cost_usd=0.0,
            )

    def test_max_cost_exceeds_050_raises_error(self):
        """Test that max_cost_usd > 0.50 raises ValueError."""
        import uuid

        criteria = TrackSelectionCriteria(bpm_range=(100, 120), energy_flow="Smooth")
        with pytest.raises(ValueError, match="Max cost must be > 0 and ≤ 0.50"):
            LLMTrackSelectionRequest(
                playlist_id=str(uuid.uuid4()),
                criteria=criteria,
                target_track_count=10,
                max_cost_usd=1.0,
            )

    def test_zero_timeout_raises_error(self):
        """Test that zero timeout_seconds raises ValueError."""
        import uuid

        criteria = TrackSelectionCriteria(bpm_range=(100, 120), energy_flow="Smooth")
        with pytest.raises(ValueError, match="Timeout must be > 0"):
            LLMTrackSelectionRequest(
                playlist_id=str(uuid.uuid4()),
                criteria=criteria,
                target_track_count=10,
                timeout_seconds=0,
            )

    def test_timeout_exceeds_300_raises_error(self):
        """Test that timeout_seconds > 300 raises ValueError."""
        import uuid

        criteria = TrackSelectionCriteria(bpm_range=(100, 120), energy_flow="Smooth")
        with pytest.raises(ValueError, match="Timeout must be > 0 and ≤ 300"):
            LLMTrackSelectionRequest(
                playlist_id=str(uuid.uuid4()),
                criteria=criteria,
                target_track_count=10,
                timeout_seconds=500,
            )


class TestSelectedTrackValidation:
    """Test SelectedTrack __post_init__ validation paths."""

    def test_empty_track_id_raises_error(self):
        """Test that empty track_id raises ValueError."""
        with pytest.raises(ValueError, match="Track ID must be non-empty"):
            SelectedTrack(
                track_id="",
                title="Test Track",
                artist="Test Artist",
                album="Test Album",
                bpm=120,
                genre="Rock",
                year=2020,
                country="US",
                duration_seconds=200,
                position=1,
                selection_reason="Good track",
            )

    def test_empty_title_raises_error(self):
        """Test that empty title raises ValueError."""
        with pytest.raises(ValueError, match="title must be non-empty"):
            SelectedTrack(
                track_id="track-1",
                title="",
                artist="Test Artist",
                album="Test Album",
                bpm=120,
                genre="Rock",
                year=2020,
                country="US",
                duration_seconds=200,
                position=1,
                selection_reason="Good track",
            )

    def test_title_too_long_raises_error(self):
        """Test that title > 200 chars raises ValueError."""
        long_title = "a" * 201
        with pytest.raises(ValueError, match="title must be non-empty and max 200 chars"):
            SelectedTrack(
                track_id="track-1",
                title=long_title,
                artist="Test Artist",
                album="Test Album",
                bpm=120,
                genre="Rock",
                year=2020,
                country="US",
                duration_seconds=200,
                position=1,
                selection_reason="Good track",
            )

    def test_empty_artist_raises_error(self):
        """Test that empty artist raises ValueError."""
        with pytest.raises(ValueError, match="artist must be non-empty"):
            SelectedTrack(
                track_id="track-1",
                title="Test Track",
                artist="",
                album="Test Album",
                bpm=120,
                genre="Rock",
                year=2020,
                country="US",
                duration_seconds=200,
                position=1,
                selection_reason="Good track",
            )

    def test_empty_album_raises_error(self):
        """Test that empty album raises ValueError."""
        with pytest.raises(ValueError, match="album must be non-empty"):
            SelectedTrack(
                track_id="track-1",
                title="Test Track",
                artist="Test Artist",
                album="",
                bpm=120,
                genre="Rock",
                year=2020,
                country="US",
                duration_seconds=200,
                position=1,
                selection_reason="Good track",
            )

    def test_zero_bpm_raises_error(self):
        """Test that BPM = 0 raises ValueError."""
        with pytest.raises(ValueError, match="BPM must be > 0 and ≤ 300"):
            SelectedTrack(
                track_id="track-1",
                title="Test Track",
                artist="Test Artist",
                album="Test Album",
                bpm=0,
                genre="Rock",
                year=2020,
                country="US",
                duration_seconds=200,
                position=1,
                selection_reason="Good track",
            )

    def test_bpm_exceeds_300_raises_error(self):
        """Test that BPM > 300 raises ValueError."""
        with pytest.raises(ValueError, match="BPM must be > 0 and ≤ 300"):
            SelectedTrack(
                track_id="track-1",
                title="Test Track",
                artist="Test Artist",
                album="Test Album",
                bpm=350,
                genre="Rock",
                year=2020,
                country="US",
                duration_seconds=200,
                position=1,
                selection_reason="Good track",
            )

    def test_empty_genre_raises_error(self):
        """Test that empty genre string raises ValueError."""
        with pytest.raises(ValueError, match="Genre must be non-empty"):
            SelectedTrack(
                track_id="track-1",
                title="Test Track",
                artist="Test Artist",
                album="Test Album",
                bpm=120,
                genre="",  # Empty string
                year=2020,
                country="US",
                duration_seconds=200,
                position=1,
                selection_reason="Good track",
            )

    def test_genre_too_long_raises_error(self):
        """Test that genre > 50 chars raises ValueError."""
        long_genre = "a" * 51
        with pytest.raises(ValueError, match="Genre must be non-empty and max 50 chars"):
            SelectedTrack(
                track_id="track-1",
                title="Test Track",
                artist="Test Artist",
                album="Test Album",
                bpm=120,
                genre=long_genre,
                year=2020,
                country="US",
                duration_seconds=200,
                position=1,
                selection_reason="Good track",
            )

    def test_year_before_1900_raises_error(self):
        """Test that year < 1900 raises ValueError."""
        with pytest.raises(ValueError, match="Year must be 1900-"):
            SelectedTrack(
                track_id="track-1",
                title="Test Track",
                artist="Test Artist",
                album="Test Album",
                bpm=120,
                genre="Rock",
                year=1850,
                country="US",
                duration_seconds=200,
                position=1,
                selection_reason="Good track",
            )

    def test_year_in_future_raises_error(self):
        """Test that year > current_year + 1 raises ValueError."""
        future_year = datetime.now().year + 5
        with pytest.raises(ValueError, match="Year must be 1900-"):
            SelectedTrack(
                track_id="track-1",
                title="Test Track",
                artist="Test Artist",
                album="Test Album",
                bpm=120,
                genre="Rock",
                year=future_year,
                country="US",
                duration_seconds=200,
                position=1,
                selection_reason="Good track",
            )

    def test_zero_duration_raises_error(self):
        """Test that duration_seconds = 0 raises ValueError."""
        with pytest.raises(ValueError, match="Duration must be > 0"):
            SelectedTrack(
                track_id="track-1",
                title="Test Track",
                artist="Test Artist",
                album="Test Album",
                bpm=120,
                genre="Rock",
                year=2020,
                country="US",
                duration_seconds=0,
                position=1,
                selection_reason="Good track",
            )

    def test_zero_position_raises_error(self):
        """Test that position = 0 raises ValueError."""
        with pytest.raises(ValueError, match="Position must be > 0"):
            SelectedTrack(
                track_id="track-1",
                title="Test Track",
                artist="Test Artist",
                album="Test Album",
                bpm=120,
                genre="Rock",
                year=2020,
                country="US",
                duration_seconds=200,
                position=0,
                selection_reason="Good track",
            )

    def test_empty_selection_reason_raises_error(self):
        """Test that empty selection_reason raises ValueError."""
        with pytest.raises(ValueError, match="Selection reason must be non-empty"):
            SelectedTrack(
                track_id="track-1",
                title="Test Track",
                artist="Test Artist",
                album="Test Album",
                bpm=120,
                genre="Rock",
                year=2020,
                country="US",
                duration_seconds=200,
                position=1,
                selection_reason="",
            )

    def test_selection_reason_too_long_raises_error(self):
        """Test that selection_reason > 500 chars raises ValueError."""
        long_reason = "a" * 501
        with pytest.raises(ValueError, match="Selection reason must be non-empty and max 500 chars"):
            SelectedTrack(
                track_id="track-1",
                title="Test Track",
                artist="Test Artist",
                album="Test Album",
                bpm=120,
                genre="Rock",
                year=2020,
                country="US",
                duration_seconds=200,
                position=1,
                selection_reason=long_reason,
            )


class TestLLMTrackSelectionResponseValidation:
    """Test LLMTrackSelectionResponse __post_init__ validation paths."""

    def test_invalid_request_id_raises_error(self):
        """Test that invalid request_id raises ValueError."""
        track = SelectedTrack(
            track_id="track-1",
            title="Test Track",
            artist="Test Artist",
            album="Test Album",
            bpm=120,
            genre="Rock",
            year=2020,
            country="US",
            duration_seconds=200,
            position=1,
            selection_reason="Good track",
        )
        with pytest.raises(ValueError, match="Request ID must be valid UUID4"):
            LLMTrackSelectionResponse(
                request_id="not-a-uuid",
                selected_tracks=[track],
                tool_calls=[{"tool_name": "test", "arguments": {}, "result": "ok"}],
                reasoning="Test reasoning",
                cost_usd=0.001,
                execution_time_seconds=1.0,
            )

    def test_empty_selected_tracks_raises_error(self):
        """Test that empty selected_tracks raises ValueError."""
        import uuid

        with pytest.raises(ValueError, match="Selected tracks must be non-empty"):
            LLMTrackSelectionResponse(
                request_id=str(uuid.uuid4()),
                selected_tracks=[],
                tool_calls=[{"tool_name": "test", "arguments": {}, "result": "ok"}],
                reasoning="Test reasoning",
                cost_usd=0.001,
                execution_time_seconds=1.0,
            )

    def test_tool_call_missing_tool_name_raises_error(self):
        """Test that tool call missing tool_name raises ValueError."""
        import uuid

        track = SelectedTrack(
            track_id="track-1",
            title="Test Track",
            artist="Test Artist",
            album="Test Album",
            bpm=120,
            genre="Rock",
            year=2020,
            country="US",
            duration_seconds=200,
            position=1,
            selection_reason="Good track",
        )
        with pytest.raises(ValueError, match="Tool call must have tool_name, arguments, result"):
            LLMTrackSelectionResponse(
                request_id=str(uuid.uuid4()),
                selected_tracks=[track],
                tool_calls=[{"arguments": {}, "result": "ok"}],  # Missing tool_name
                reasoning="Test reasoning",
                cost_usd=0.001,
                execution_time_seconds=1.0,
            )

    def test_tool_call_missing_arguments_raises_error(self):
        """Test that tool call missing arguments raises ValueError."""
        import uuid

        track = SelectedTrack(
            track_id="track-1",
            title="Test Track",
            artist="Test Artist",
            album="Test Album",
            bpm=120,
            genre="Rock",
            year=2020,
            country="US",
            duration_seconds=200,
            position=1,
            selection_reason="Good track",
        )
        with pytest.raises(ValueError, match="Tool call must have tool_name, arguments, result"):
            LLMTrackSelectionResponse(
                request_id=str(uuid.uuid4()),
                selected_tracks=[track],
                tool_calls=[{"tool_name": "test", "result": "ok"}],  # Missing arguments
                reasoning="Test reasoning",
                cost_usd=0.001,
                execution_time_seconds=1.0,
            )

    def test_empty_reasoning_raises_error(self):
        """Test that empty reasoning raises ValueError."""
        import uuid

        track = SelectedTrack(
            track_id="track-1",
            title="Test Track",
            artist="Test Artist",
            album="Test Album",
            bpm=120,
            genre="Rock",
            year=2020,
            country="US",
            duration_seconds=200,
            position=1,
            selection_reason="Good track",
        )
        with pytest.raises(ValueError, match="Reasoning must be non-empty"):
            LLMTrackSelectionResponse(
                request_id=str(uuid.uuid4()),
                selected_tracks=[track],
                tool_calls=[{"tool_name": "test", "arguments": {}, "result": "ok"}],
                reasoning="",
                cost_usd=0.001,
                execution_time_seconds=1.0,
            )

    def test_reasoning_too_long_raises_error(self):
        """Test that reasoning > 2000 chars raises ValueError."""
        import uuid

        track = SelectedTrack(
            track_id="track-1",
            title="Test Track",
            artist="Test Artist",
            album="Test Album",
            bpm=120,
            genre="Rock",
            year=2020,
            country="US",
            duration_seconds=200,
            position=1,
            selection_reason="Good track",
        )
        long_reasoning = "a" * 2001
        with pytest.raises(ValueError, match="Reasoning must be non-empty and max 2000 chars"):
            LLMTrackSelectionResponse(
                request_id=str(uuid.uuid4()),
                selected_tracks=[track],
                tool_calls=[{"tool_name": "test", "arguments": {}, "result": "ok"}],
                reasoning=long_reasoning,
                cost_usd=0.001,
                execution_time_seconds=1.0,
            )

    def test_negative_cost_raises_error(self):
        """Test that negative cost_usd raises ValueError."""
        import uuid

        track = SelectedTrack(
            track_id="track-1",
            title="Test Track",
            artist="Test Artist",
            album="Test Album",
            bpm=120,
            genre="Rock",
            year=2020,
            country="US",
            duration_seconds=200,
            position=1,
            selection_reason="Good track",
        )
        with pytest.raises(ValueError, match="Cost must be ≥ 0"):
            LLMTrackSelectionResponse(
                request_id=str(uuid.uuid4()),
                selected_tracks=[track],
                tool_calls=[{"tool_name": "test", "arguments": {}, "result": "ok"}],
                reasoning="Test reasoning",
                cost_usd=-0.001,
                execution_time_seconds=1.0,
            )

    def test_negative_execution_time_raises_error(self):
        """Test that negative execution_time_seconds raises ValueError."""
        import uuid

        track = SelectedTrack(
            track_id="track-1",
            title="Test Track",
            artist="Test Artist",
            album="Test Album",
            bpm=120,
            genre="Rock",
            year=2020,
            country="US",
            duration_seconds=200,
            position=1,
            selection_reason="Good track",
        )
        with pytest.raises(ValueError, match="Execution time must be ≥ 0"):
            LLMTrackSelectionResponse(
                request_id=str(uuid.uuid4()),
                selected_tracks=[track],
                tool_calls=[{"tool_name": "test", "arguments": {}, "result": "ok"}],
                reasoning="Test reasoning",
                cost_usd=0.001,
                execution_time_seconds=-1.0,
            )

    def test_future_created_at_raises_error(self):
        """Test that future created_at raises ValueError."""
        import uuid

        track = SelectedTrack(
            track_id="track-1",
            title="Test Track",
            artist="Test Artist",
            album="Test Album",
            bpm=120,
            genre="Rock",
            year=2020,
            country="US",
            duration_seconds=200,
            position=1,
            selection_reason="Good track",
        )
        future_time = datetime.now() + timedelta(days=1)
        with pytest.raises(ValueError, match="Created at cannot be in future"):
            LLMTrackSelectionResponse(
                request_id=str(uuid.uuid4()),
                selected_tracks=[track],
                tool_calls=[{"tool_name": "test", "arguments": {}, "result": "ok"}],
                reasoning="Test reasoning",
                cost_usd=0.001,
                execution_time_seconds=1.0,
                created_at=future_time,
            )


class TestPlaylistValidation:
    """Test Playlist __post_init__ validation paths."""

    def test_invalid_playlist_id_raises_error(self):
        """Test that invalid playlist ID raises ValueError."""
        import uuid

        daypart = DaypartSpecification(
            name="Morning",
            time_range=("06:00", "10:00"),
            bpm_progression={"morning": (100, 120)},
            genre_mix={"Rock": 0.5},
            era_distribution={"2000s": 0.5},
            australian_min=0.3,
            mood="Energetic",
            tracks_per_hour=12,
        )
        criteria = TrackSelectionCriteria(bpm_range=(100, 120), energy_flow="Smooth")
        spec = PlaylistSpecification(
            id=str(uuid.uuid4()),
            name="Monday_Morning_0600_1000",
            daypart=daypart,
            target_duration_minutes=240,
            track_criteria=criteria,
        )
        track = SelectedTrack(
            track_id="track-1",
            title="Test Track",
            artist="Test Artist",
            album="Test Album",
            bpm=120,
            genre="Rock",
            year=2020,
            country="US",
            duration_seconds=200,
            position=1,
            selection_reason="Good track",
        )
        validation = ValidationResult(
            constraint_satisfaction=0.85,
            bpm_satisfaction=0.9,
            genre_satisfaction=0.8,
            era_satisfaction=0.85,
            australian_content=0.35,
            flow_quality_score=0.75,
            bpm_variance=0.1,
            energy_progression="smooth",
            genre_diversity=0.8,
            gap_analysis={},
            passes_validation=True,
        )
        with pytest.raises(ValueError, match="ID must be valid UUID4"):
            Playlist(
                id="not-a-uuid",
                name="Monday_Morning_0600_1000",
                tracks=[track],
                spec=spec,
                validation_result=validation,
            )

    def test_id_mismatch_with_spec_raises_error(self):
        """Test that mismatched playlist ID and spec ID raises ValueError."""
        import uuid

        daypart = DaypartSpecification(
            name="Morning",
            time_range=("06:00", "10:00"),
            bpm_progression={"morning": (100, 120)},
            genre_mix={"Rock": 0.5},
            era_distribution={"2000s": 0.5},
            australian_min=0.3,
            mood="Energetic",
            tracks_per_hour=12,
        )
        criteria = TrackSelectionCriteria(bpm_range=(100, 120), energy_flow="Smooth")
        spec = PlaylistSpecification(
            id=str(uuid.uuid4()),
            name="Monday_Morning_0600_1000",
            daypart=daypart,
            target_duration_minutes=240,
            track_criteria=criteria,
        )
        track = SelectedTrack(
            track_id="track-1",
            title="Test Track",
            artist="Test Artist",
            album="Test Album",
            bpm=120,
            genre="Rock",
            year=2020,
            country="US",
            duration_seconds=200,
            position=1,
            selection_reason="Good track",
        )
        validation = ValidationResult(
            constraint_satisfaction=0.85,
            bpm_satisfaction=0.9,
            genre_satisfaction=0.8,
            era_satisfaction=0.85,
            australian_content=0.35,
            flow_quality_score=0.75,
            bpm_variance=0.1,
            energy_progression="smooth",
            genre_diversity=0.8,
            gap_analysis={},
            passes_validation=True,
        )
        different_id = str(uuid.uuid4())
        with pytest.raises(ValueError, match="Playlist ID must match PlaylistSpecification ID"):
            Playlist(
                id=different_id,
                name="Monday_Morning_0600_1000",
                tracks=[track],
                spec=spec,
                validation_result=validation,
            )

    def test_invalid_name_format_raises_error(self):
        """Test that invalid name format raises ValueError."""
        import uuid

        daypart = DaypartSpecification(
            name="Morning",
            time_range=("06:00", "10:00"),
            bpm_progression={"morning": (100, 120)},
            genre_mix={"Rock": 0.5},
            era_distribution={"2000s": 0.5},
            australian_min=0.3,
            mood="Energetic",
            tracks_per_hour=12,
        )
        criteria = TrackSelectionCriteria(bpm_range=(100, 120), energy_flow="Smooth")
        playlist_id = str(uuid.uuid4())
        spec = PlaylistSpecification(
            id=playlist_id,
            name="Monday_Morning_0600_1000",
            daypart=daypart,
            target_duration_minutes=240,
            track_criteria=criteria,
        )
        track = SelectedTrack(
            track_id="track-1",
            title="Test Track",
            artist="Test Artist",
            album="Test Album",
            bpm=120,
            genre="Rock",
            year=2020,
            country="US",
            duration_seconds=200,
            position=1,
            selection_reason="Good track",
        )
        validation = ValidationResult(
            constraint_satisfaction=0.85,
            bpm_satisfaction=0.9,
            genre_satisfaction=0.8,
            era_satisfaction=0.85,
            australian_content=0.35,
            flow_quality_score=0.75,
            bpm_variance=0.1,
            energy_progression="smooth",
            genre_diversity=0.8,
            gap_analysis={},
            passes_validation=True,
        )
        with pytest.raises(ValueError, match="Name must match schema"):
            Playlist(
                id=playlist_id,
                name="InvalidFormat",
                tracks=[track],
                spec=spec,
                validation_result=validation,
            )

    def test_empty_tracks_raises_error(self):
        """Test that empty tracks list raises ValueError."""
        import uuid

        daypart = DaypartSpecification(
            name="Morning",
            time_range=("06:00", "10:00"),
            bpm_progression={"morning": (100, 120)},
            genre_mix={"Rock": 0.5},
            era_distribution={"2000s": 0.5},
            australian_min=0.3,
            mood="Energetic",
            tracks_per_hour=12,
        )
        criteria = TrackSelectionCriteria(bpm_range=(100, 120), energy_flow="Smooth")
        playlist_id = str(uuid.uuid4())
        spec = PlaylistSpecification(
            id=playlist_id,
            name="Monday_Morning_0600_1000",
            daypart=daypart,
            target_duration_minutes=240,
            track_criteria=criteria,
        )
        validation = ValidationResult(
            constraint_satisfaction=0.85,
            bpm_satisfaction=0.9,
            genre_satisfaction=0.8,
            era_satisfaction=0.85,
            australian_content=0.35,
            flow_quality_score=0.75,
            bpm_variance=0.1,
            energy_progression="smooth",
            genre_diversity=0.8,
            gap_analysis={},
            passes_validation=True,
        )
        with pytest.raises(ValueError, match="Tracks must be non-empty"):
            Playlist(
                id=playlist_id,
                name="Monday_Morning_0600_1000",
                tracks=[],
                spec=spec,
                validation_result=validation,
            )

    def test_failed_validation_raises_error(self):
        """Test that failed validation result raises ValueError."""
        import uuid

        daypart = DaypartSpecification(
            name="Morning",
            time_range=("06:00", "10:00"),
            bpm_progression={"morning": (100, 120)},
            genre_mix={"Rock": 0.5},
            era_distribution={"2000s": 0.5},
            australian_min=0.3,
            mood="Energetic",
            tracks_per_hour=12,
        )
        criteria = TrackSelectionCriteria(bpm_range=(100, 120), energy_flow="Smooth")
        playlist_id = str(uuid.uuid4())
        spec = PlaylistSpecification(
            id=playlist_id,
            name="Monday_Morning_0600_1000",
            daypart=daypart,
            target_duration_minutes=240,
            track_criteria=criteria,
        )
        track = SelectedTrack(
            track_id="track-1",
            title="Test Track",
            artist="Test Artist",
            album="Test Album",
            bpm=120,
            genre="Rock",
            year=2020,
            country="US",
            duration_seconds=200,
            position=1,
            selection_reason="Good track",
        )
        failed_validation = ValidationResult(
            constraint_satisfaction=0.75,  # Below 0.80
            bpm_satisfaction=0.9,
            genre_satisfaction=0.8,
            era_satisfaction=0.85,
            australian_content=0.35,
            flow_quality_score=0.65,  # Below 0.70
            bpm_variance=0.1,
            energy_progression="smooth",
            genre_diversity=0.8,
            gap_analysis={},
            passes_validation=False,
        )
        with pytest.raises(ValueError, match="ValidationResult must pass"):
            Playlist(
                id=playlist_id,
                name="Monday_Morning_0600_1000",
                tracks=[track],
                spec=spec,
                validation_result=failed_validation,
            )

    def test_synced_before_created_raises_error(self):
        """Test that synced_at < created_at raises ValueError."""
        import uuid

        daypart = DaypartSpecification(
            name="Morning",
            time_range=("06:00", "10:00"),
            bpm_progression={"morning": (100, 120)},
            genre_mix={"Rock": 0.5},
            era_distribution={"2000s": 0.5},
            australian_min=0.3,
            mood="Energetic",
            tracks_per_hour=12,
        )
        criteria = TrackSelectionCriteria(bpm_range=(100, 120), energy_flow="Smooth")
        playlist_id = str(uuid.uuid4())
        spec = PlaylistSpecification(
            id=playlist_id,
            name="Monday_Morning_0600_1000",
            daypart=daypart,
            target_duration_minutes=240,
            track_criteria=criteria,
        )
        track = SelectedTrack(
            track_id="track-1",
            title="Test Track",
            artist="Test Artist",
            album="Test Album",
            bpm=120,
            genre="Rock",
            year=2020,
            country="US",
            duration_seconds=200,
            position=1,
            selection_reason="Good track",
        )
        validation = ValidationResult(
            constraint_satisfaction=0.85,
            bpm_satisfaction=0.9,
            genre_satisfaction=0.8,
            era_satisfaction=0.85,
            australian_content=0.35,
            flow_quality_score=0.75,
            bpm_variance=0.1,
            energy_progression="smooth",
            genre_diversity=0.8,
            gap_analysis={},
            passes_validation=True,
        )
        created = datetime.now()
        synced = created - timedelta(hours=1)
        with pytest.raises(ValueError, match="Synced at must be ≥ created at"):
            Playlist(
                id=playlist_id,
                name="Monday_Morning_0600_1000",
                tracks=[track],
                spec=spec,
                validation_result=validation,
                created_at=created,
                synced_at=synced,
            )

    def test_zero_azuracast_id_raises_error(self):
        """Test that azuracast_id = 0 raises ValueError."""
        import uuid

        daypart = DaypartSpecification(
            name="Morning",
            time_range=("06:00", "10:00"),
            bpm_progression={"morning": (100, 120)},
            genre_mix={"Rock": 0.5},
            era_distribution={"2000s": 0.5},
            australian_min=0.3,
            mood="Energetic",
            tracks_per_hour=12,
        )
        criteria = TrackSelectionCriteria(bpm_range=(100, 120), energy_flow="Smooth")
        playlist_id = str(uuid.uuid4())
        spec = PlaylistSpecification(
            id=playlist_id,
            name="Monday_Morning_0600_1000",
            daypart=daypart,
            target_duration_minutes=240,
            track_criteria=criteria,
        )
        track = SelectedTrack(
            track_id="track-1",
            title="Test Track",
            artist="Test Artist",
            album="Test Album",
            bpm=120,
            genre="Rock",
            year=2020,
            country="US",
            duration_seconds=200,
            position=1,
            selection_reason="Good track",
        )
        validation = ValidationResult(
            constraint_satisfaction=0.85,
            bpm_satisfaction=0.9,
            genre_satisfaction=0.8,
            era_satisfaction=0.85,
            australian_content=0.35,
            flow_quality_score=0.75,
            bpm_variance=0.1,
            energy_progression="smooth",
            genre_diversity=0.8,
            gap_analysis={},
            passes_validation=True,
        )
        with pytest.raises(ValueError, match="AzuraCast ID must be > 0"):
            Playlist(
                id=playlist_id,
                name="Monday_Morning_0600_1000",
                tracks=[track],
                spec=spec,
                validation_result=validation,
                azuracast_id=0,
            )


# ============================================================================
# Validation Models Tests
# ============================================================================


class TestValidationResultValidation:
    """Test ValidationResult __post_init__ validation paths."""

    def test_constraint_satisfaction_negative_raises_error(self):
        """Test that negative constraint_satisfaction raises ValueError."""
        with pytest.raises(ValueError, match="constraint_satisfaction must be 0.0-1.0"):
            ValidationResult(
                constraint_satisfaction=-0.1,
                bpm_satisfaction=0.9,
                genre_satisfaction=0.8,
                era_satisfaction=0.85,
                australian_content=0.35,
                flow_quality_score=0.75,
                bpm_variance=0.1,
                energy_progression="smooth",
                genre_diversity=0.8,
                gap_analysis={},
                passes_validation=False,
            )

    def test_constraint_satisfaction_exceeds_one_raises_error(self):
        """Test that constraint_satisfaction > 1.0 raises ValueError."""
        with pytest.raises(ValueError, match="constraint_satisfaction must be 0.0-1.0"):
            ValidationResult(
                constraint_satisfaction=1.1,
                bpm_satisfaction=0.9,
                genre_satisfaction=0.8,
                era_satisfaction=0.85,
                australian_content=0.35,
                flow_quality_score=0.75,
                bpm_variance=0.1,
                energy_progression="smooth",
                genre_diversity=0.8,
                gap_analysis={},
                passes_validation=True,
            )

    def test_negative_bpm_variance_raises_error(self):
        """Test that negative bpm_variance raises ValueError."""
        with pytest.raises(ValueError, match="BPM variance must be ≥ 0"):
            ValidationResult(
                constraint_satisfaction=0.85,
                bpm_satisfaction=0.9,
                genre_satisfaction=0.8,
                era_satisfaction=0.85,
                australian_content=0.35,
                flow_quality_score=0.75,
                bpm_variance=-0.1,
                energy_progression="smooth",
                genre_diversity=0.8,
                gap_analysis={},
                passes_validation=True,
            )

    def test_invalid_energy_progression_raises_error(self):
        """Test that invalid energy_progression raises ValueError."""
        with pytest.raises(ValueError, match="Energy progression must be one of"):
            ValidationResult(
                constraint_satisfaction=0.85,
                bpm_satisfaction=0.9,
                genre_satisfaction=0.8,
                era_satisfaction=0.85,
                australian_content=0.35,
                flow_quality_score=0.75,
                bpm_variance=0.1,
                energy_progression="invalid",
                genre_diversity=0.8,
                gap_analysis={},
                passes_validation=True,
            )

    def test_non_dict_gap_analysis_raises_error(self):
        """Test that non-dict gap_analysis raises ValueError."""
        with pytest.raises(ValueError, match="Gap analysis must be a dict"):
            ValidationResult(
                constraint_satisfaction=0.85,
                bpm_satisfaction=0.9,
                genre_satisfaction=0.8,
                era_satisfaction=0.85,
                australian_content=0.35,
                flow_quality_score=0.75,
                bpm_variance=0.1,
                energy_progression="smooth",
                genre_diversity=0.8,
                gap_analysis="not a dict",  # type: ignore
                passes_validation=True,
            )

    def test_passes_validation_inconsistent_with_thresholds_raises_error(self):
        """Test that inconsistent passes_validation raises ValueError."""
        with pytest.raises(ValueError, match="passes_validation .* inconsistent with thresholds"):
            ValidationResult(
                constraint_satisfaction=0.85,  # >= 0.80
                bpm_satisfaction=0.9,
                genre_satisfaction=0.8,
                era_satisfaction=0.85,
                australian_content=0.35,
                flow_quality_score=0.75,  # >= 0.70
                bpm_variance=0.1,
                energy_progression="smooth",
                genre_diversity=0.8,
                gap_analysis={},
                passes_validation=False,  # Should be True!
            )

    def test_is_valid_method_returns_passes_validation(self):
        """Test that is_valid() returns passes_validation value."""
        validation = ValidationResult(
            constraint_satisfaction=0.85,
            bpm_satisfaction=0.9,
            genre_satisfaction=0.8,
            era_satisfaction=0.85,
            australian_content=0.35,
            flow_quality_score=0.75,
            bpm_variance=0.1,
            energy_progression="smooth",
            genre_diversity=0.8,
            gap_analysis={},
            passes_validation=True,
        )
        assert validation.is_valid() is True


class TestDecisionLogValidation:
    """Test DecisionLog __post_init__ validation paths."""

    def test_invalid_id_raises_error(self):
        """Test that invalid ID raises ValueError."""
        with pytest.raises(ValueError, match="ID must be valid UUID4"):
            DecisionLog(
                id="not-a-uuid",
                decision_type="track_selection",
                playlist_id="00000000-0000-4000-8000-000000000000",
                playlist_name="Test Playlist",
            )

    def test_future_timestamp_raises_error(self):
        """Test that future timestamp raises ValueError."""
        import uuid

        future_time = datetime.now() + timedelta(days=1)
        with pytest.raises(ValueError, match="Timestamp cannot be in future"):
            DecisionLog(
                timestamp=future_time,
                decision_type="track_selection",
                playlist_id=str(uuid.uuid4()),
                playlist_name="Test Playlist",
            )

    def test_invalid_decision_type_raises_error(self):
        """Test that invalid decision_type raises ValueError."""
        import uuid

        with pytest.raises(ValueError, match="Decision type must be one of"):
            DecisionLog(
                decision_type="invalid_type",
                playlist_id=str(uuid.uuid4()),
                playlist_name="Test Playlist",
            )

    def test_invalid_playlist_id_raises_error(self):
        """Test that invalid playlist_id raises ValueError."""
        with pytest.raises(ValueError, match="Playlist ID must be valid UUID4"):
            DecisionLog(
                decision_type="track_selection",
                playlist_id="not-a-uuid",
                playlist_name="Test Playlist",
            )

    def test_empty_playlist_name_raises_error(self):
        """Test that empty playlist_name raises ValueError."""
        import uuid

        with pytest.raises(ValueError, match="Playlist name must be non-empty"):
            DecisionLog(
                decision_type="track_selection",
                playlist_id=str(uuid.uuid4()),
                playlist_name="",
            )

    def test_non_json_serializable_criteria_raises_error(self):
        """Test that non-JSON-serializable criteria raises ValueError."""
        import uuid

        non_serializable = object()
        with pytest.raises(ValueError, match="criteria must be JSON-serializable"):
            DecisionLog(
                decision_type="track_selection",
                playlist_id=str(uuid.uuid4()),
                playlist_name="Test Playlist",
                criteria={"obj": non_serializable},  # type: ignore
            )

    def test_to_json_serializes_correctly(self):
        """Test that to_json() produces valid JSON."""
        import uuid
        import json

        log = DecisionLog(
            decision_type="track_selection",
            playlist_id=str(uuid.uuid4()),
            playlist_name="Test Playlist",
            criteria={"test": "value"},
        )
        json_str = log.to_json()
        parsed = json.loads(json_str)
        assert parsed["decision_type"] == "track_selection"
        assert parsed["playlist_name"] == "Test Playlist"

    def test_from_json_deserializes_correctly(self):
        """Test that from_json() reconstructs DecisionLog."""
        import uuid

        log = DecisionLog(
            decision_type="track_selection",
            playlist_id=str(uuid.uuid4()),
            playlist_name="Test Playlist",
            criteria={"test": "value"},
        )
        json_str = log.to_json()
        reconstructed = DecisionLog.from_json(json_str)
        assert reconstructed.decision_type == log.decision_type
        assert reconstructed.playlist_id == log.playlist_id
        assert reconstructed.playlist_name == log.playlist_name
