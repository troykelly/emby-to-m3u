"""
Unit Tests for Validation Metrics (T032)

Tests the validator.py functions that calculate playlist quality metrics
and satisfaction scores against defined criteria.

Test Coverage:
- BPM satisfaction calculation
- Genre satisfaction calculation
- Era satisfaction calculation
- Flow quality score calculation
- Energy progression classification
- Gap analysis generation
- Overall constraint satisfaction
- Edge cases (empty playlists, extreme values)
"""

import pytest
from datetime import datetime
from src.ai_playlist.models import SelectedTrack, TrackSelectionCriteria
from src.ai_playlist.validator import (
    validate_playlist,
    _calculate_bpm_satisfaction,
    _calculate_genre_satisfaction,
    _calculate_era_satisfaction,
    _calculate_australian_satisfaction,
    _calculate_flow_quality,
    _generate_gap_analysis,
)


class TestBPMSatisfaction:
    """Test BPM satisfaction: tracks_in_range / total_tracks."""

    def test_all_tracks_in_range(self):
        """Should return 1.0 when all tracks within BPM range."""
        tracks = [
            SelectedTrack(
                track_id=f"track{i}",
                title=f"Song {i}",
                artist="Artist",
                album="Album",
                bpm=100 + i * 10,
                genre="Rock",
                year=2023,
                country="AU",
                duration_seconds=180,
                position=i + 1,
                selection_reason="test",
            )
            for i in range(4)  # BPMs: 100, 110, 120, 130
        ]
        criteria = TrackSelectionCriteria(
            bpm_range=(90, 140),
            genre_mix={"Rock": (0.5, 0.7)},
            era_distribution={"Current": (0.4, 0.6)},
            australian_min=0.30,
            energy_flow="test",
        )

        satisfaction = _calculate_bpm_satisfaction(tracks, criteria)

        assert satisfaction == 1.0

    def test_partial_tracks_in_range(self):
        """Should return correct proportion for partial match."""
        tracks = [
            # In range: 100, 120
            SelectedTrack("t1", "S1", "A", "AL", 100, "Rock", 2023, "AU", 180, 1, "test"),
            SelectedTrack("t2", "S2", "A", "AL", 120, "Rock", 2023, "AU", 180, 2, "test"),
            # Out of range: 80, 150
            SelectedTrack("t3", "S3", "A", "AL", 80, "Rock", 2023, "AU", 180, 3, "test"),
            SelectedTrack("t4", "S4", "A", "AL", 150, "Rock", 2023, "AU", 180, 4, "test"),
        ]
        criteria = TrackSelectionCriteria(
            bpm_range=(90, 140),
            genre_mix={"Rock": (0.5, 0.7)},
            era_distribution={"Current": (0.4, 0.6)},
            australian_min=0.30,
            energy_flow="test",
        )

        satisfaction = _calculate_bpm_satisfaction(tracks, criteria)

        assert satisfaction == 0.5  # 2 out of 4

    def test_no_tracks_in_range(self):
        """Should return 0.0 when no tracks within BPM range."""
        tracks = [
            SelectedTrack("t1", "S1", "A", "AL", 50, "Rock", 2023, "AU", 180, 1, "test"),
            SelectedTrack("t2", "S2", "A", "AL", 200, "Rock", 2023, "AU", 180, 2, "test"),
        ]
        criteria = TrackSelectionCriteria(
            bpm_range=(90, 140),
            genre_mix={"Rock": (0.5, 0.7)},
            era_distribution={"Current": (0.4, 0.6)},
            australian_min=0.30,
            energy_flow="test",
        )

        satisfaction = _calculate_bpm_satisfaction(tracks, criteria)

        assert satisfaction == 0.0

    def test_tracks_with_none_bpm(self):
        """Should handle tracks with None BPM values."""
        tracks = [
            SelectedTrack("t1", "S1", "A", "AL", 100, "Rock", 2023, "AU", 180, 1, "test"),
            SelectedTrack("t2", "S2", "A", "AL", None, "Rock", 2023, "AU", 180, 2, "test"),
            SelectedTrack("t3", "S3", "A", "AL", 120, "Rock", 2023, "AU", 180, 3, "test"),
            SelectedTrack("t4", "S4", "A", "AL", None, "Rock", 2023, "AU", 180, 4, "test"),
        ]
        criteria = TrackSelectionCriteria(
            bpm_range=(90, 140),
            genre_mix={"Rock": (0.5, 0.7)},
            era_distribution={"Current": (0.4, 0.6)},
            australian_min=0.30,
            energy_flow="test",
        )

        satisfaction = _calculate_bpm_satisfaction(tracks, criteria)

        assert satisfaction == 0.5  # 2 valid out of 4 total


class TestGenreSatisfaction:
    """Test genre satisfaction: genres_meeting_requirements / total_genres."""

    def test_all_genres_meet_requirements(self):
        """Should return 1.0 when all genres within required ranges."""
        tracks = [
            # Rock: 4 tracks (40%)
            SelectedTrack("t1", "S1", "A", "AL", 100, "Rock", 2023, "AU", 180, 1, "test"),
            SelectedTrack("t2", "S2", "A", "AL", 110, "Rock", 2023, "AU", 180, 2, "test"),
            SelectedTrack("t3", "S3", "A", "AL", 120, "Rock", 2023, "AU", 180, 3, "test"),
            SelectedTrack("t4", "S4", "A", "AL", 130, "Rock", 2023, "AU", 180, 4, "test"),
            # Pop: 4 tracks (40%)
            SelectedTrack("t5", "S5", "A", "AL", 100, "Pop", 2023, "AU", 180, 5, "test"),
            SelectedTrack("t6", "S6", "A", "AL", 110, "Pop", 2023, "AU", 180, 6, "test"),
            SelectedTrack("t7", "S7", "A", "AL", 120, "Pop", 2023, "AU", 180, 7, "test"),
            SelectedTrack("t8", "S8", "A", "AL", 130, "Pop", 2023, "AU", 180, 8, "test"),
            # Jazz: 2 tracks (20%)
            SelectedTrack("t9", "S9", "A", "AL", 100, "Jazz", 2023, "AU", 180, 9, "test"),
            SelectedTrack("t10", "S10", "A", "AL", 110, "Jazz", 2023, "AU", 180, 10, "test"),
        ]
        criteria = TrackSelectionCriteria(
            bpm_range=(90, 140),
            genre_mix={
                "Rock": (0.30, 0.50),  # 40% is within range
                "Pop": (0.30, 0.50),   # 40% is within range
                "Jazz": (0.10, 0.30),  # 20% is within range
            },
            era_distribution={"Current": (0.4, 0.6)},
            australian_min=0.30,
            energy_flow="test",
        )

        satisfaction = _calculate_genre_satisfaction(tracks, criteria)

        assert satisfaction == 1.0

    def test_partial_genres_meet_requirements(self):
        """Should return correct proportion for partial genre match."""
        tracks = [
            # Rock: 6 tracks (60%) - meets requirement (0.40-0.70)
            *[SelectedTrack(f"t{i}", "S", "A", "AL", 100, "Rock", 2023, "AU", 180, i, "test")
              for i in range(1, 7)],
            # Pop: 1 track (10%) - DOES NOT meet requirement (0.20-0.40)
            SelectedTrack("t7", "S7", "A", "AL", 100, "Pop", 2023, "AU", 180, 7, "test"),
            # Jazz: 3 tracks (30%) - meets requirement (0.20-0.40)
            *[SelectedTrack(f"t{i}", "S", "A", "AL", 100, "Jazz", 2023, "AU", 180, i, "test")
              for i in range(8, 11)],
        ]
        criteria = TrackSelectionCriteria(
            bpm_range=(90, 140),
            genre_mix={
                "Rock": (0.40, 0.70),  # Met (60%)
                "Pop": (0.20, 0.40),   # NOT met (10%)
                "Jazz": (0.20, 0.40),  # Met (30%)
            },
            era_distribution={"Current": (0.4, 0.6)},
            australian_min=0.30,
            energy_flow="test",
        )

        satisfaction = _calculate_genre_satisfaction(tracks, criteria)

        assert abs(satisfaction - 0.667) < 0.01  # 2/3 genres meet requirements

    def test_no_genre_requirements(self):
        """Should return 1.0 when no genre requirements specified."""
        tracks = [
            SelectedTrack("t1", "S1", "A", "AL", 100, "Rock", 2023, "AU", 180, 1, "test"),
        ]
        criteria = TrackSelectionCriteria(
            bpm_range=(90, 140),
            genre_mix={},  # No genre requirements
            era_distribution={"Current": (0.4, 0.6)},
            australian_min=0.30,
            energy_flow="test",
        )

        satisfaction = _calculate_genre_satisfaction(tracks, criteria)

        assert satisfaction == 1.0


class TestEraSatisfaction:
    """Test era satisfaction: eras_meeting_distribution / total_eras."""

    def test_all_eras_meet_requirements(self):
        """Should return 1.0 when all eras within required ranges."""
        current_year = datetime.now().year

        tracks = [
            # Current (last 2 years): 3 tracks (30%)
            *[SelectedTrack(f"t{i}", "S", "A", "AL", 100, "Rock", current_year, "AU", 180, i, "test")
              for i in range(1, 4)],
            # Recent (3-10 years): 4 tracks (40%)
            *[SelectedTrack(f"t{i}", "S", "A", "AL", 100, "Rock", current_year - 5, "AU", 180, i, "test")
              for i in range(4, 8)],
            # Classic (>10 years): 3 tracks (30%)
            *[SelectedTrack(f"t{i}", "S", "A", "AL", 100, "Rock", current_year - 15, "AU", 180, i, "test")
              for i in range(8, 11)],
        ]
        criteria = TrackSelectionCriteria(
            bpm_range=(90, 140),
            genre_mix={"Rock": (0.5, 0.7)},
            era_distribution={
                "Current": (0.20, 0.40),  # 30% meets
                "Recent": (0.30, 0.50),   # 40% meets
                "Classic": (0.20, 0.40),  # 30% meets
            },
            australian_min=0.30,
            energy_flow="test",
        )

        satisfaction = _calculate_era_satisfaction(tracks, criteria)

        assert satisfaction == 1.0

    def test_partial_eras_meet_requirements(self):
        """Should return correct proportion for partial era match."""
        current_year = datetime.now().year

        tracks = [
            # Current: 6 tracks (60%) - meets (0.50-0.70)
            *[SelectedTrack(f"t{i}", "S", "A", "AL", 100, "Rock", current_year, "AU", 180, i, "test")
              for i in range(1, 7)],
            # Recent: 1 track (10%) - DOES NOT meet (0.20-0.40)
            SelectedTrack("t7", "S7", "A", "AL", 100, "Rock", current_year - 5, "AU", 180, 7, "test"),
            # Classic: 3 tracks (30%) - meets (0.20-0.40)
            *[SelectedTrack(f"t{i}", "S", "A", "AL", 100, "Rock", current_year - 15, "AU", 180, i, "test")
              for i in range(8, 11)],
        ]
        criteria = TrackSelectionCriteria(
            bpm_range=(90, 140),
            genre_mix={"Rock": (0.5, 0.7)},
            era_distribution={
                "Current": (0.50, 0.70),   # Met (60%)
                "Recent": (0.20, 0.40),    # NOT met (10%)
                "Classic": (0.20, 0.40),   # Met (30%)
            },
            australian_min=0.30,
            energy_flow="test",
        )

        satisfaction = _calculate_era_satisfaction(tracks, criteria)

        assert abs(satisfaction - 0.667) < 0.01  # 2/3 eras meet requirements

    def test_no_era_requirements(self):
        """Should return 1.0 when no era requirements specified."""
        tracks = [
            SelectedTrack("t1", "S1", "A", "AL", 100, "Rock", 2023, "AU", 180, 1, "test"),
        ]
        criteria = TrackSelectionCriteria(
            bpm_range=(90, 140),
            genre_mix={"Rock": (0.5, 0.7)},
            era_distribution={},  # No era requirements
            australian_min=0.30,
            energy_flow="test",
        )

        satisfaction = _calculate_era_satisfaction(tracks, criteria)

        assert satisfaction == 1.0

    def test_tracks_with_none_year(self):
        """Should handle tracks with None year values."""
        current_year = datetime.now().year

        tracks = [
            SelectedTrack("t1", "S1", "A", "AL", 100, "Rock", current_year, "AU", 180, 1, "test"),
            SelectedTrack("t2", "S2", "A", "AL", 100, "Rock", None, "AU", 180, 2, "test"),
            SelectedTrack("t3", "S3", "A", "AL", 100, "Rock", current_year - 5, "AU", 180, 3, "test"),
        ]
        criteria = TrackSelectionCriteria(
            bpm_range=(90, 140),
            genre_mix={"Rock": (0.5, 0.7)},
            era_distribution={
                "Current": (0.20, 0.50),
                "Recent": (0.20, 0.50),
            },
            australian_min=0.30,
            energy_flow="test",
        )

        # Should skip tracks with None year
        satisfaction = _calculate_era_satisfaction(tracks, criteria)
        # 1 Current (33%), 1 Recent (33%) - both meet requirements
        assert satisfaction == 1.0


class TestFlowQuality:
    """Test flow quality: max(0, 1.0 - (avg_bpm_variance / 50.0))."""

    def test_smooth_flow(self):
        """Should classify as 'smooth' when avg_bpm_variance < 10."""
        tracks = [
            SelectedTrack("t1", "S1", "A", "AL", 100, "Rock", 2023, "AU", 180, 1, "test"),
            SelectedTrack("t2", "S2", "A", "AL", 105, "Rock", 2023, "AU", 180, 2, "test"),
            SelectedTrack("t3", "S3", "A", "AL", 102, "Rock", 2023, "AU", 180, 3, "test"),
            SelectedTrack("t4", "S4", "A", "AL", 108, "Rock", 2023, "AU", 180, 4, "test"),
        ]

        score, variance, progression = _calculate_flow_quality(tracks)

        # Variances: |105-100|=5, |102-105|=3, |108-102|=6
        # avg_variance = (5+3+6)/3 = 4.67
        assert variance < 10
        assert progression == "smooth"
        # score = 1.0 - (4.67/50) ≈ 0.91
        assert score > 0.90

    def test_choppy_flow(self):
        """Should classify as 'choppy' when avg_bpm_variance > 20."""
        tracks = [
            SelectedTrack("t1", "S1", "A", "AL", 90, "Rock", 2023, "AU", 180, 1, "test"),
            SelectedTrack("t2", "S2", "A", "AL", 130, "Rock", 2023, "AU", 180, 2, "test"),
            SelectedTrack("t3", "S3", "A", "AL", 100, "Rock", 2023, "AU", 180, 3, "test"),
            SelectedTrack("t4", "S4", "A", "AL", 140, "Rock", 2023, "AU", 180, 4, "test"),
        ]

        score, variance, progression = _calculate_flow_quality(tracks)

        # Variances: |130-90|=40, |100-130|=30, |140-100|=40
        # avg_variance = (40+30+40)/3 = 36.67
        assert variance > 20
        assert progression == "choppy"
        # score = 1.0 - (36.67/50) ≈ 0.27
        assert score < 0.40

    def test_moderate_flow(self):
        """Should classify as 'moderate' when 10 <= avg_bpm_variance <= 20."""
        tracks = [
            SelectedTrack("t1", "S1", "A", "AL", 100, "Rock", 2023, "AU", 180, 1, "test"),
            SelectedTrack("t2", "S2", "A", "AL", 115, "Rock", 2023, "AU", 180, 2, "test"),
            SelectedTrack("t3", "S3", "A", "AL", 105, "Rock", 2023, "AU", 180, 3, "test"),
            SelectedTrack("t4", "S4", "A", "AL", 120, "Rock", 2023, "AU", 180, 4, "test"),
        ]

        score, variance, progression = _calculate_flow_quality(tracks)

        # Variances: |115-100|=15, |105-115|=10, |120-105|=15
        # avg_variance = (15+10+15)/3 = 13.33
        assert 10 <= variance <= 20
        assert progression == "moderate"
        # score = 1.0 - (13.33/50) ≈ 0.73
        assert 0.60 < score < 0.80

    def test_single_track_perfect_flow(self):
        """Should return perfect flow for single track."""
        tracks = [
            SelectedTrack("t1", "S1", "A", "AL", 100, "Rock", 2023, "AU", 180, 1, "test"),
        ]

        score, variance, progression = _calculate_flow_quality(tracks)

        assert score == 1.0
        assert variance == 0.0
        assert progression == "smooth"

    def test_tracks_with_none_bpm(self):
        """Should handle tracks with None BPM values."""
        tracks = [
            SelectedTrack("t1", "S1", "A", "AL", 100, "Rock", 2023, "AU", 180, 1, "test"),
            SelectedTrack("t2", "S2", "A", "AL", None, "Rock", 2023, "AU", 180, 2, "test"),
            SelectedTrack("t3", "S3", "A", "AL", 110, "Rock", 2023, "AU", 180, 3, "test"),
        ]

        score, variance, progression = _calculate_flow_quality(tracks)

        # Implementation skips tracks with None BPM when calculating transitions
        # Between t1(100) and t2(None): no valid BPM, skip
        # Between t2(None) and t3(110): no valid BPM from t2, skip
        # No valid transitions captured (implementation requires both BPMs valid)
        # Result: returns moderate flow with 0.0 variance as no valid BPM changes found
        assert variance == 0.0
        assert progression == "moderate"
        assert score == 0.5  # Default when no valid BPM data

    def test_extreme_variance(self):
        """Should handle extreme BPM variance gracefully."""
        tracks = [
            SelectedTrack("t1", "S1", "A", "AL", 60, "Rock", 2023, "AU", 180, 1, "test"),
            SelectedTrack("t2", "S2", "A", "AL", 180, "Rock", 2023, "AU", 180, 2, "test"),
        ]

        score, variance, progression = _calculate_flow_quality(tracks)

        # Variance: |180-60|=120
        # score = max(0, 1.0 - (120/50)) = max(0, -1.4) = 0.0
        assert variance == 120.0
        assert score == 0.0
        assert progression == "choppy"


class TestGapAnalysis:
    """Test gap analysis generation for unmet criteria."""

    def test_bpm_gap_identified(self):
        """Should identify BPM gaps when tracks out of range."""
        tracks = [
            SelectedTrack("t1", "Track 1", "A", "AL", 80, "Rock", 2023, "AU", 180, 1, "test"),
            SelectedTrack("t2", "Track 2", "A", "AL", 100, "Rock", 2023, "AU", 180, 2, "test"),
            SelectedTrack("t3", "Track 3", "A", "AL", 150, "Rock", 2023, "AU", 180, 3, "test"),
        ]
        criteria = TrackSelectionCriteria(
            bpm_range=(90, 140),
            genre_mix={"Rock": (0.5, 0.7)},
            era_distribution={"Current": (0.8, 1.0)},
            australian_min=0.30,
            energy_flow="test",
        )

        gap_analysis = _generate_gap_analysis(
            tracks, criteria,
            bpm_satisfaction=0.67,
            genre_satisfaction=1.0,
            era_satisfaction=1.0,
            australian_content=1.0,
        )

        assert "bpm_range" in gap_analysis
        assert "Track 1 (80 BPM)" in gap_analysis["bpm_range"]
        assert "Track 3 (150 BPM)" in gap_analysis["bpm_range"]

    def test_genre_gap_identified(self):
        """Should identify genre gaps when distribution off."""
        tracks = [
            *[SelectedTrack(f"t{i}", f"S{i}", "A", "AL", 100, "Rock", 2023, "AU", 180, i, "test")
              for i in range(1, 9)],  # 8 Rock (80%)
            *[SelectedTrack(f"t{i}", f"S{i}", "A", "AL", 100, "Pop", 2023, "AU", 180, i, "test")
              for i in range(9, 11)],  # 2 Pop (20%)
        ]
        criteria = TrackSelectionCriteria(
            bpm_range=(90, 140),
            genre_mix={
                "Rock": (0.40, 0.60),  # Actual: 80% - OVER
                "Pop": (0.30, 0.50),   # Actual: 20% - UNDER
            },
            era_distribution={"Current": (0.8, 1.0)},
            australian_min=0.30,
            energy_flow="test",
        )

        gap_analysis = _generate_gap_analysis(
            tracks, criteria,
            bpm_satisfaction=1.0,
            genre_satisfaction=0.0,
            era_satisfaction=1.0,
            australian_content=1.0,
        )

        assert "genre_mix" in gap_analysis
        assert "Rock 80%" in gap_analysis["genre_mix"]
        assert "Pop 20%" in gap_analysis["genre_mix"]

    def test_era_gap_identified(self):
        """Should identify era gaps when distribution off."""
        current_year = datetime.now().year

        tracks = [
            *[SelectedTrack(f"t{i}", f"S{i}", "A", "AL", 100, "Rock", current_year, "AU", 180, i, "test")
              for i in range(1, 9)],  # 8 Current (80%)
            *[SelectedTrack(f"t{i}", f"S{i}", "A", "AL", 100, "Rock", current_year - 5, "AU", 180, i, "test")
              for i in range(9, 11)],  # 2 Recent (20%)
        ]
        criteria = TrackSelectionCriteria(
            bpm_range=(90, 140),
            genre_mix={"Rock": (0.5, 0.7)},
            era_distribution={
                "Current": (0.40, 0.60),  # Actual: 80% - OVER
                "Recent": (0.30, 0.50),   # Actual: 20% - UNDER
            },
            australian_min=0.30,
            energy_flow="test",
        )

        gap_analysis = _generate_gap_analysis(
            tracks, criteria,
            bpm_satisfaction=1.0,
            genre_satisfaction=1.0,
            era_satisfaction=0.0,
            australian_content=1.0,
        )

        assert "era_distribution" in gap_analysis
        assert "Current era 80%" in gap_analysis["era_distribution"]
        assert "Recent era 20%" in gap_analysis["era_distribution"]

    def test_australian_content_gap_identified(self):
        """Should identify Australian content gap."""
        tracks = [
            SelectedTrack("t1", "S1", "A", "AL", 100, "Rock", 2023, "AU", 180, 1, "test"),
            SelectedTrack("t2", "S2", "A", "AL", 100, "Rock", 2023, "US", 180, 2, "test"),
            SelectedTrack("t3", "S3", "A", "AL", 100, "Rock", 2023, "UK", 180, 3, "test"),
            SelectedTrack("t4", "S4", "A", "AL", 100, "Rock", 2023, "US", 180, 4, "test"),
        ]  # Only 25% Australian
        criteria = TrackSelectionCriteria(
            bpm_range=(90, 140),
            genre_mix={"Rock": (0.5, 0.7)},
            era_distribution={"Current": (0.8, 1.0)},
            australian_min=0.30,
            energy_flow="test",
        )

        gap_analysis = _generate_gap_analysis(
            tracks, criteria,
            bpm_satisfaction=1.0,
            genre_satisfaction=1.0,
            era_satisfaction=1.0,
            australian_content=0.25,
        )

        assert "australian_content" in gap_analysis
        assert "25%" in gap_analysis["australian_content"]
        assert "30%" in gap_analysis["australian_content"]

    def test_no_gaps(self):
        """Should return empty gap analysis when all criteria met."""
        tracks = [
            *[SelectedTrack(f"t{i}", f"S{i}", "A", "AL", 100, "Rock", 2023, "AU", 180, i, "test")
              for i in range(1, 11)],
        ]
        criteria = TrackSelectionCriteria(
            bpm_range=(90, 140),
            genre_mix={"Rock": (0.8, 1.0)},
            era_distribution={"Current": (0.8, 1.0)},
            australian_min=0.30,
            energy_flow="test",
        )

        gap_analysis = _generate_gap_analysis(
            tracks, criteria,
            bpm_satisfaction=1.0,
            genre_satisfaction=1.0,
            era_satisfaction=1.0,
            australian_content=1.0,
        )

        assert gap_analysis == {}


class TestOverallConstraintSatisfaction:
    """Test overall constraint satisfaction: average of 4 metrics."""

    def test_perfect_satisfaction(self):
        """Should return constraint_satisfaction=1.0 when all metrics perfect."""
        tracks = [
            *[SelectedTrack(f"t{i}", f"S{i}", "A", "AL", 100, "Rock", 2023, "AU", 180, i, "test")
              for i in range(1, 11)],
        ]
        criteria = TrackSelectionCriteria(
            bpm_range=(90, 140),
            genre_mix={"Rock": (0.8, 1.0)},
            era_distribution={"Current": (0.8, 1.0)},
            australian_min=0.30,
            energy_flow="test",
        )

        result = validate_playlist(tracks, criteria)

        assert result.constraint_satisfaction == 1.0
        assert result.bpm_satisfaction == 1.0
        assert result.genre_satisfaction == 1.0
        assert result.era_satisfaction == 1.0

    def test_average_calculation(self):
        """Should correctly average the 4 satisfaction metrics."""
        current_year = datetime.now().year

        tracks = [
            # BPM: 2/4 in range (50%)
            SelectedTrack("t1", "S1", "A", "AL", 100, "Rock", current_year, "AU", 180, 1, "test"),
            SelectedTrack("t2", "S2", "A", "AL", 80, "Rock", current_year, "US", 180, 2, "test"),
            SelectedTrack("t3", "S3", "A", "AL", 120, "Pop", current_year, "AU", 180, 3, "test"),
            SelectedTrack("t4", "S4", "A", "AL", 150, "Pop", current_year, "US", 180, 4, "test"),
        ]
        criteria = TrackSelectionCriteria(
            bpm_range=(90, 140),
            genre_mix={
                "Rock": (0.40, 0.60),  # 50% actual - meets
                "Pop": (0.40, 0.60),   # 50% actual - meets
            },
            era_distribution={
                "Current": (0.80, 1.0),  # 100% actual - meets
            },
            australian_min=0.30,  # 50% actual - meets (50/30 = 1.0 capped)
            energy_flow="test",
        )

        result = validate_playlist(tracks, criteria)

        # BPM: 0.5, Genre: 1.0, Era: 1.0, Australian: 1.0
        # Average: (0.5 + 1.0 + 1.0 + 1.0) / 4 = 0.875
        assert abs(result.constraint_satisfaction - 0.875) < 0.01

    def test_validation_pass_threshold(self):
        """Should pass when constraint ≥ 0.80 and flow ≥ 0.70."""
        tracks = [
            *[SelectedTrack(f"t{i}", f"S{i}", "A", "AL", 100 + i, "Rock", 2023, "AU", 180, i, "test")
              for i in range(1, 11)],
        ]
        criteria = TrackSelectionCriteria(
            bpm_range=(90, 140),
            genre_mix={"Rock": (0.8, 1.0)},
            era_distribution={"Current": (0.8, 1.0)},
            australian_min=0.30,
            energy_flow="test",
        )

        result = validate_playlist(tracks, criteria)

        assert result.constraint_satisfaction >= 0.80
        assert result.flow_quality_score >= 0.70
        assert result.passes_validation is True

    def test_validation_fail_constraint(self):
        """Should fail when constraint < 0.80."""
        tracks = [
            *[SelectedTrack(f"t{i}", f"S{i}", "A", "AL", 200, "Rock", 2023, "US", 180, i, "test")
              for i in range(1, 11)],  # All out of BPM range, no Australian content
        ]
        criteria = TrackSelectionCriteria(
            bpm_range=(90, 140),
            genre_mix={"Rock": (0.8, 1.0)},
            era_distribution={"Current": (0.8, 1.0)},
            australian_min=0.30,
            energy_flow="test",
        )

        result = validate_playlist(tracks, criteria)

        assert result.constraint_satisfaction < 0.80
        assert result.passes_validation is False

    def test_empty_playlist_raises_error(self):
        """Should raise ValueError for empty playlist."""
        criteria = TrackSelectionCriteria(
            bpm_range=(90, 140),
            genre_mix={"Rock": (0.5, 0.7)},
            era_distribution={"Current": (0.4, 0.6)},
            australian_min=0.30,
            energy_flow="test",
        )

        with pytest.raises(ValueError, match="Tracks list cannot be empty"):
            validate_playlist([], criteria)
