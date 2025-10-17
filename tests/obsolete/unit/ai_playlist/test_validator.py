"""
Unit tests for validator.py - Phase 4.3 (T058)

Comprehensive test coverage for playlist validation logic including:
- Playlist validation logic (3 tests)
- Constraint scoring (5 tests)
- Flow quality metrics (3 tests)
- Gap analysis generation (3 tests)

Target coverage: ≥90%
"""

from datetime import datetime

import pytest

from src.ai_playlist.validator import (
    validate_playlist,
    _calculate_genre_satisfaction,
    _calculate_era_satisfaction,
    _calculate_australian_satisfaction,
    _calculate_flow_quality,
    _calculate_genre_diversity,
    _generate_gap_analysis,
)
from src.ai_playlist.models import SelectedTrack
from src.ai_playlist.models.validation import ValidationStatus


# ============================================================================
# Test Fixtures
# ============================================================================


class MockCriteria:  # pylint: disable=too-few-public-methods
    """Mock criteria object for validator testing."""
    def __init__(self, bpm_range, genre_mix, era_distribution, australian_min):
        self.bpm_range = bpm_range
        self.genre_mix = genre_mix
        self.era_distribution = era_distribution
        self.australian_min = australian_min


@pytest.fixture
def sample_criteria():
    """Create sample selection criteria for testing."""
    return MockCriteria(
        bpm_range=(120, 140),
        genre_mix={
            "Rock": (0.4, 0.6),
            "Pop": (0.3, 0.5),
        },
        era_distribution={
            "Current": (0.2, 0.4),
            "Recent": (0.3, 0.5),
            "Classic": (0.2, 0.4),
        },
        australian_min=0.30,
    )


@pytest.fixture
def valid_tracks():
    """Create valid playlist tracks that meet all criteria."""
    return [
        # 5 Rock tracks (50%) - BPM 125-135, mix of eras
        SelectedTrack(
            track_id="1",
            title="Rock Song 1",
            artist="Artist 1",
            album="Album 1",
            bpm=125,
            genre="Rock",
            year=2024,
            country="AU",
            duration_seconds=180,
            is_australian=True,
            rotation_category="A",
            position_in_playlist=0,
            selection_reasoning="Current Australian rock",
            validation_status="pass",
            validation_notes=[],
            metadata_source="library",
        ),
        SelectedTrack(
            track_id="2",
            title="Rock Song 2",
            artist="Artist 2",
            album="Album 2",
            bpm=130,
            genre="Rock",
            year=2020,
            country="AU",
            duration_seconds=200,
            is_australian=True,
            rotation_category="B",
            position_in_playlist=1,
            selection_reasoning="Recent Australian rock",
            validation_status="pass",
            validation_notes=[],
            metadata_source="library",
        ),
        SelectedTrack(
            track_id="3",
            title="Rock Song 3",
            artist="Artist 3",
            album="Album 3",
            bpm=128,
            genre="Rock",
            year=2010,
            country="US",
            duration_seconds=190,
            is_australian=False,
            rotation_category="C",
            position_in_playlist=2,
            selection_reasoning="Classic international rock",
            validation_status="pass",
            validation_notes=[],
            metadata_source="library",
        ),
        SelectedTrack(
            track_id="4",
            title="Rock Song 4",
            artist="Artist 4",
            album="Album 4",
            bpm=135,
            genre="Rock",
            year=2023,
            country="AU",
            duration_seconds=175,
            is_australian=True,
            rotation_category="A",
            position_in_playlist=3,
            selection_reasoning="Current Australian rock",
            validation_status="pass",
            validation_notes=[],
            metadata_source="library",
        ),
        SelectedTrack(
            track_id="5",
            title="Rock Song 5",
            artist="Artist 5",
            album="Album 5",
            bpm=132,
            genre="Rock",
            year=2018,
            country="UK",
            duration_seconds=185,
            is_australian=False,
            rotation_category="B",
            position_in_playlist=4,
            selection_reasoning="Recent international rock",
            validation_status="pass",
            validation_notes=[],
            metadata_source="library",
        ),
        # 4 Pop tracks (40%) - BPM 120-130, mix of eras
        SelectedTrack(
            track_id="6",
            title="Pop Song 1",
            artist="Artist 6",
            album="Album 6",
            bpm=120,
            genre="Pop",
            year=2024,
            country="US",
            duration_seconds=195,
            is_australian=False,
            rotation_category="A",
            position_in_playlist=5,
            selection_reasoning="Current pop hit",
            validation_status="pass",
            validation_notes=[],
            metadata_source="library",
        ),
        SelectedTrack(
            track_id="7",
            title="Pop Song 2",
            artist="Artist 7",
            album="Album 7",
            bpm=125,
            genre="Pop",
            year=2019,
            country="AU",
            duration_seconds=180,
            is_australian=True,
            rotation_category="B",
            position_in_playlist=6,
            selection_reasoning="Recent Australian pop",
            validation_status="pass",
            validation_notes=[],
            metadata_source="library",
        ),
        SelectedTrack(
            track_id="8",
            title="Pop Song 3",
            artist="Artist 8",
            album="Album 8",
            bpm=122,
            genre="Pop",
            year=2012,
            country="US",
            duration_seconds=170,
            is_australian=False,
            rotation_category="C",
            position_in_playlist=7,
            selection_reasoning="Classic pop",
            validation_status="pass",
            validation_notes=[],
            metadata_source="library",
        ),
        SelectedTrack(
            track_id="9",
            title="Pop Song 4",
            artist="Artist 9",
            album="Album 9",
            bpm=128,
            genre="Pop",
            year=2021,
            country="UK",
            duration_seconds=165,
            is_australian=False,
            rotation_category="B",
            position_in_playlist=8,
            selection_reasoning="Recent pop",
            validation_status="pass",
            validation_notes=[],
            metadata_source="library",
        ),
        # 1 more Australian track to reach 4/10 = 40% (exceeds 30% minimum)
        SelectedTrack(
            track_id="10",
            title="Rock Song 6",
            artist="Artist 10",
            album="Album 10",
            bpm=130,
            genre="Rock",
            year=2015,
            country="AU",
            duration_seconds=190,
            is_australian=True,
            rotation_category="B",
            position_in_playlist=9,
            selection_reasoning="Recent Australian rock",
            validation_status="pass",
            validation_notes=[],
            metadata_source="library",
        ),
    ]


@pytest.fixture
def invalid_tracks():
    """Create invalid playlist tracks that fail criteria."""
    return [
        # All tracks out of BPM range, wrong genres, no Australian content
        SelectedTrack(
            track_id="1",
            title="Jazz Song",
            artist="Artist 1",
            album="Album 1",
            bpm=90,  # Too slow
            genre="Jazz",  # Not in genre_mix
            year=2024,
            country="US",
            duration_seconds=180,
            is_australian=False,
            rotation_category="A",
            position_in_playlist=0,
            selection_reasoning="Jazz track",
            validation_status="fail",
            validation_notes=["BPM out of range", "Genre not in mix"],
            metadata_source="library",
        ),
        SelectedTrack(
            track_id="2",
            title="Classical Song",
            artist="Artist 2",
            album="Album 2",
            bpm=160,  # Too fast
            genre="Classical",  # Not in genre_mix
            year=2020,
            country="DE",
            duration_seconds=200,
            is_australian=False,
            rotation_category="B",
            position_in_playlist=1,
            selection_reasoning="Classical track",
            validation_status="fail",
            validation_notes=["BPM out of range", "Genre not in mix"],
            metadata_source="library",
        ),
    ]


@pytest.fixture
def empty_tracks():
    """Empty tracks list for edge case testing."""
    return []


# ============================================================================
# 1. Playlist Validation Logic Tests (3 tests)
# ============================================================================


def test_validate_playlist_valid_passes_all_checks(valid_tracks, sample_criteria):
    """Test that a valid playlist passes all validation checks."""
    result = validate_playlist(valid_tracks, sample_criteria)

    # Should pass validation
    assert result.overall_status == ValidationStatus.PASS
    assert result.compliance_percentage >= 0.80
    assert result.flow_quality_metrics.calculate_overall_quality() >= 0.70

    # Check all constraint scores are compliant
    assert result.constraint_scores["bpm_satisfaction"].is_compliant
    assert result.constraint_scores["genre_satisfaction"].is_compliant
    assert result.constraint_scores["australian_content"].is_compliant

    # Should have minimal gap analysis
    assert len(result.gap_analysis) <= 2


def test_validate_playlist_invalid_fails_appropriately(invalid_tracks, sample_criteria):
    """Test that an invalid playlist fails validation appropriately."""
    result = validate_playlist(invalid_tracks, sample_criteria)

    # Should fail validation
    assert result.overall_status in [ValidationStatus.FAIL, ValidationStatus.WARNING]
    assert result.compliance_percentage < 0.80

    # Check constraint scores show non-compliance
    assert not result.constraint_scores["bpm_satisfaction"].is_compliant
    assert not result.constraint_scores["genre_satisfaction"].is_compliant
    assert not result.constraint_scores["australian_content"].is_compliant

    # Should have detailed gap analysis
    assert len(result.gap_analysis) > 0


def test_validate_playlist_empty_raises_value_error(empty_tracks, sample_criteria):
    """Test that validation with empty playlist raises ValueError."""
    with pytest.raises(ValueError, match="Tracks list cannot be empty"):
        validate_playlist(empty_tracks, sample_criteria)


# ============================================================================
# 2. Constraint Scoring Tests (5 tests)
# ============================================================================


def test_constraint_scoring_bpm_progression_coherence(valid_tracks):
    """Test BPM progression coherence scoring."""
    # Valid tracks have smooth BPM progression (125, 130, 128, 135, 132, 120, 125, 122, 128, 130)
    flow_quality, bpm_variance, energy_progression = _calculate_flow_quality(valid_tracks)

    # Should have good coherence (small BPM variance)
    assert 0.70 <= flow_quality <= 1.0
    assert bpm_variance < 15.0  # Average change < 15 BPM
    assert energy_progression in ["smooth", "moderate"]


def test_constraint_scoring_genre_distribution_tolerance(valid_tracks, sample_criteria):
    """Test genre distribution within ±10% tolerance."""
    genre_satisfaction = _calculate_genre_satisfaction(valid_tracks, sample_criteria)

    # Valid tracks: 6 Rock (60%), 4 Pop (40%)
    # Criteria: Rock (40-60%), Pop (30-50%)
    # Both should be within tolerance
    assert genre_satisfaction == 1.0  # All genres meet requirements


def test_constraint_scoring_era_distribution_tolerance(valid_tracks):
    """Test era distribution within ±10% tolerance."""
    criteria = MockCriteria(
        bpm_range=(120, 140),
        genre_mix={},
        era_distribution={
            "Current": (0.2, 0.4),  # Target ~30%
            "Recent": (0.3, 0.5),  # Target ~40%
            "Classic": (0.2, 0.4),  # Target ~30%
        },
        australian_min=0.30,
    )

    era_satisfaction = _calculate_era_satisfaction(valid_tracks, criteria)

    # Valid tracks have good era distribution
    # Current (2023-2025): 3 tracks (30%)
    # Recent (2015-2022): 4 tracks (40%)
    # Classic (<2015): 3 tracks (30%)
    assert era_satisfaction >= 0.66  # At least 2 out of 3 eras met


def test_constraint_scoring_australian_content_hard_minimum():
    """Test Australian content hard minimum (30%)."""
    criteria = MockCriteria(
        bpm_range=(120, 140),
        genre_mix={},
        era_distribution={},
        australian_min=0.30,
    )

    # 3 Australian tracks out of 10 = 30% (exactly at minimum)
    tracks = [
        SelectedTrack(
            track_id=str(i),
            title=f"Track {i}",
            artist=f"Artist {i}",
            album=f"Album {i}",
            bpm=125,
            genre="Rock",
            year=2024,
            country="AU" if i < 3 else "US",
            duration_seconds=180,
            is_australian=i < 3,
            rotation_category="A",
            position_in_playlist=i,
            selection_reasoning="Test track",
            validation_status="pass",
            validation_notes=[],
            metadata_source="library",
        )
        for i in range(10)
    ]

    australian_satisfaction = _calculate_australian_satisfaction(tracks, criteria)
    assert australian_satisfaction == 1.0  # Exactly meets requirement

    # 2 Australian tracks out of 10 = 20% (below minimum)
    tracks_below = tracks[:]
    tracks_below[2].country = "US"
    tracks_below[2].is_australian = False

    australian_satisfaction_below = _calculate_australian_satisfaction(tracks_below, criteria)
    assert australian_satisfaction_below < 1.0  # Below requirement


def test_constraint_scoring_tolerance_violation_detection():
    """Test detection of tolerance violations."""
    criteria = MockCriteria(
        bpm_range=(120, 140),
        genre_mix={
            "Rock": (0.5, 0.7),  # Require 50-70%
        },
        era_distribution={},
        australian_min=0.30,
    )

    # 8 Rock out of 10 = 80% (exceeds tolerance)
    tracks = [
        SelectedTrack(
            track_id=str(i),
            title=f"Track {i}",
            artist=f"Artist {i}",
            album=f"Album {i}",
            bpm=125,
            genre="Rock" if i < 8 else "Pop",
            year=2024,
            country="AU",
            duration_seconds=180,
            is_australian=True,
            rotation_category="A",
            position_in_playlist=i,
            selection_reasoning="Test track",
            validation_status="pass",
            validation_notes=[],
            metadata_source="library",
        )
        for i in range(10)
    ]

    genre_satisfaction = _calculate_genre_satisfaction(tracks, criteria)
    assert genre_satisfaction == 0.0  # Genre exceeds max tolerance


# ============================================================================
# 3. Flow Quality Metrics Tests (3 tests)
# ============================================================================


def test_flow_quality_bpm_variance_calculation():
    """Test BPM variance calculation."""
    # Tracks with known BPM values: [120, 125, 130, 135, 140]
    tracks = [
        SelectedTrack(
            track_id=str(i),
            title=f"Track {i}",
            artist=f"Artist {i}",
            album=f"Album {i}",
            bpm=120 + (i * 5),
            genre="Rock",
            year=2024,
            country="AU",
            duration_seconds=180,
            is_australian=True,
            rotation_category="A",
            position_in_playlist=i,
            selection_reasoning="Test track",
            validation_status="pass",
            validation_notes=[],
            metadata_source="library",
        )
        for i in range(5)
    ]

    _flow_quality, bpm_variance, energy_progression = _calculate_flow_quality(tracks)

    # BPM changes: [5, 5, 5, 5] -> average = 5.0
    assert bpm_variance == 5.0
    assert energy_progression == "smooth"  # Variance < 10


def test_flow_quality_energy_consistency_scoring():
    """Test energy consistency scoring."""
    # Tracks with choppy BPM changes: [120, 150, 110, 145, 105]
    tracks = [
        SelectedTrack(
            track_id=str(i),
            title=f"Track {i}",
            artist=f"Artist {i}",
            album=f"Album {i}",
            bpm=bpm,
            genre="Rock",
            year=2024,
            country="AU",
            duration_seconds=180,
            is_australian=True,
            rotation_category="A",
            position_in_playlist=i,
            selection_reasoning="Test track",
            validation_status="pass",
            validation_notes=[],
            metadata_source="library",
        )
        for i, bpm in enumerate([120, 150, 110, 145, 105])
    ]

    flow_quality, bpm_variance, energy_progression = _calculate_flow_quality(tracks)

    # BPM changes: [30, 40, 35, 40] -> average = 36.25
    assert bpm_variance > 30.0
    assert energy_progression == "choppy"  # Variance > 20
    assert flow_quality < 0.50  # Poor flow quality


def test_flow_quality_genre_diversity_index():
    """Test genre diversity index calculation (Simpson's diversity)."""
    # High diversity: 5 genres, 2 tracks each (10 total)
    tracks_diverse = [
        SelectedTrack(
            track_id=str(i),
            title=f"Track {i}",
            artist=f"Artist {i}",
            album=f"Album {i}",
            bpm=125,
            genre=["Rock", "Pop", "Jazz", "Blues", "Folk"][i // 2],
            year=2024,
            country="AU",
            duration_seconds=180,
            is_australian=True,
            rotation_category="A",
            position_in_playlist=i,
            selection_reasoning="Test track",
            validation_status="pass",
            validation_notes=[],
            metadata_source="library",
        )
        for i in range(10)
    ]

    diversity_high = _calculate_genre_diversity(tracks_diverse)
    assert diversity_high > 0.7  # High diversity

    # Low diversity: 1 genre, 10 tracks
    tracks_monotone = [
        SelectedTrack(
            track_id=str(i),
            title=f"Track {i}",
            artist=f"Artist {i}",
            album=f"Album {i}",
            bpm=125,
            genre="Rock",
            year=2024,
            country="AU",
            duration_seconds=180,
            is_australian=True,
            rotation_category="A",
            position_in_playlist=i,
            selection_reasoning="Test track",
            validation_status="pass",
            validation_notes=[],
            metadata_source="library",
        )
        for i in range(10)
    ]

    diversity_low = _calculate_genre_diversity(tracks_monotone)
    assert diversity_low == 0.0  # No diversity


# ============================================================================
# 4. Gap Analysis Generation Tests (3 tests)
# ============================================================================


def test_gap_analysis_identify_genre_gaps(sample_criteria):
    """Test identification of genre gaps."""
    # All Jazz tracks (0% Rock, 0% Pop)
    tracks = [
        SelectedTrack(
            track_id=str(i),
            title=f"Track {i}",
            artist=f"Artist {i}",
            album=f"Album {i}",
            bpm=125,
            genre="Jazz",
            year=2024,
            country="AU",
            duration_seconds=180,
            is_australian=True,
            rotation_category="A",
            position_in_playlist=i,
            selection_reasoning="Test track",
            validation_status="pass",
            validation_notes=[],
            metadata_source="library",
        )
        for i in range(10)
    ]

    gap_analysis = _generate_gap_analysis(
        tracks,
        sample_criteria,
        bpm_satisfaction=1.0,
        genre_satisfaction=0.0,
        era_satisfaction=1.0,
        australian_content=1.0,
    )

    assert "genre_mix" in gap_analysis
    assert "Rock" in gap_analysis["genre_mix"]
    assert "Pop" in gap_analysis["genre_mix"]


def test_gap_analysis_identify_era_gaps(sample_criteria):
    """Test identification of era gaps."""
    # All current tracks (100% Current, 0% Recent, 0% Classic)
    current_year = datetime.now().year
    tracks = [
        SelectedTrack(
            track_id=str(i),
            title=f"Track {i}",
            artist=f"Artist {i}",
            album=f"Album {i}",
            bpm=125,
            genre="Rock",
            year=current_year,
            country="AU",
            duration_seconds=180,
            is_australian=True,
            rotation_category="A",
            position_in_playlist=i,
            selection_reasoning="Test track",
            validation_status="pass",
            validation_notes=[],
            metadata_source="library",
        )
        for i in range(10)
    ]

    gap_analysis = _generate_gap_analysis(
        tracks,
        sample_criteria,
        bpm_satisfaction=1.0,
        genre_satisfaction=1.0,
        era_satisfaction=0.33,  # Only 1 out of 3 eras met
        australian_content=1.0,
    )

    assert "era_distribution" in gap_analysis
    # Should mention Recent and Classic eras are missing
    assert (
        "Recent" in gap_analysis["era_distribution"]
        or "Classic" in gap_analysis["era_distribution"]
    )


def test_gap_analysis_suggest_track_additions():
    """Test gap analysis suggests specific track additions."""
    criteria = MockCriteria(
        bpm_range=(120, 140),
        genre_mix={
            "Rock": (0.5, 0.7),
        },
        era_distribution={},
        australian_min=0.50,  # Require 50% Australian
    )

    # Only 20% Australian content
    tracks = [
        SelectedTrack(
            track_id=str(i),
            title=f"Track {i}",
            artist=f"Artist {i}",
            album=f"Album {i}",
            bpm=125,
            genre="Rock",
            year=2024,
            country="AU" if i < 2 else "US",
            duration_seconds=180,
            is_australian=i < 2,
            rotation_category="A",
            position_in_playlist=i,
            selection_reasoning="Test track",
            validation_status="pass",
            validation_notes=[],
            metadata_source="library",
        )
        for i in range(10)
    ]

    gap_analysis = _generate_gap_analysis(
        tracks,
        criteria,
        bpm_satisfaction=1.0,
        genre_satisfaction=1.0,
        era_satisfaction=1.0,
        australian_content=0.20,
    )

    assert "australian_content" in gap_analysis
    assert "20%" in gap_analysis["australian_content"]
    assert "50%" in gap_analysis["australian_content"]
