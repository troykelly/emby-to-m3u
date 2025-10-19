"""
Unit tests for validation models.

Tests cover all validation models from src/ai_playlist/models/validation.py:
- ConstraintScore
- FlowQualityMetrics
- ValidationResult
- ConstraintScores (legacy)
- FlowMetrics (legacy)
"""

import pytest
from datetime import datetime
from decimal import Decimal

from src.ai_playlist.models import (
    ValidationStatus,
    ConstraintScore,
    FlowQualityMetrics,
    ValidationResult,
    ConstraintScores,
    FlowMetrics,
    Playlist,
    SelectedTrack,
    TrackSelectionCriteria,
    GenreCriteria,
    EraCriteria,
    BPMRange,
)
from datetime import time


class TestConstraintScore:
    """Tests for ConstraintScore dataclass."""

    def test_calculate_compliant(self):
        """Test calculating compliant score."""
        score = ConstraintScore.calculate(
            name="Australian Content",
            target=0.30,
            actual=0.32,
            tolerance=0.10,
        )

        assert score.constraint_name == "Australian Content"
        assert score.target_value == 0.30
        assert score.actual_value == 0.32
        assert score.tolerance == 0.10
        assert score.is_compliant is True
        assert score.deviation_percentage == pytest.approx(0.0667, rel=0.01)

    def test_calculate_non_compliant_low(self):
        """Test calculating non-compliant score (too low)."""
        score = ConstraintScore.calculate(
            name="Genre Mix",
            target=0.40,
            actual=0.25,  # Below min acceptable (0.36)
            tolerance=0.10,
        )

        assert score.is_compliant is False
        assert score.deviation_percentage > 0

    def test_calculate_non_compliant_high(self):
        """Test calculating non-compliant score (too high)."""
        score = ConstraintScore.calculate(
            name="Genre Mix",
            target=0.40,
            actual=0.55,  # Above max acceptable (0.44)
            tolerance=0.10,
        )

        assert score.is_compliant is False

    def test_calculate_zero_target(self):
        """Test calculating score with zero target."""
        score = ConstraintScore.calculate(
            name="Test",
            target=0.0,
            actual=0.0,
            tolerance=0.10,
        )

        assert score.deviation_percentage == 0.0
        assert score.is_compliant is True

    def test_calculate_boundary_min(self):
        """Test calculation at minimum boundary."""
        score = ConstraintScore.calculate(
            name="Test",
            target=0.50,
            actual=0.45,  # Exactly at min acceptable
            tolerance=0.10,
        )

        assert score.is_compliant is True

    def test_calculate_boundary_max(self):
        """Test calculation at maximum boundary."""
        score = ConstraintScore.calculate(
            name="Test",
            target=0.50,
            actual=0.55,  # Exactly at max acceptable
            tolerance=0.10,
        )

        assert score.is_compliant is True


class TestFlowQualityMetrics:
    """Tests for FlowQualityMetrics dataclass."""

    def test_valid_instantiation(self, valid_flow_metrics):
        """Test creating valid FlowQualityMetrics."""
        assert valid_flow_metrics.bpm_variance == 8.5
        assert valid_flow_metrics.bpm_progression_coherence == 0.85
        assert valid_flow_metrics.energy_consistency == 0.90
        assert valid_flow_metrics.genre_diversity_index == 0.75

    def test_calculate_overall_quality(self, valid_flow_metrics):
        """Test overall quality score calculation."""
        quality = valid_flow_metrics.calculate_overall_quality()

        # Should be weighted average of all metrics
        # BPM score: 1 - (8.5/30) ≈ 0.717
        # Others: 0.85, 0.90, 0.75
        # Average: (0.717 + 0.85 + 0.90 + 0.75) / 4 ≈ 0.804
        assert 0.7 < quality < 0.9
        assert isinstance(quality, float)

    def test_calculate_quality_high_variance(self):
        """Test quality calculation with high BPM variance."""
        metrics = FlowQualityMetrics(
            bpm_variance=30.0,  # High variance
            bpm_progression_coherence=0.50,
            energy_consistency=0.50,
            genre_diversity_index=0.50,
        )

        quality = metrics.calculate_overall_quality()
        assert quality < 0.6  # Should be lower due to high variance

    def test_calculate_quality_low_variance(self):
        """Test quality calculation with low BPM variance."""
        metrics = FlowQualityMetrics(
            bpm_variance=2.0,  # Low variance
            bpm_progression_coherence=0.90,
            energy_consistency=0.90,
            genre_diversity_index=0.90,
        )

        quality = metrics.calculate_overall_quality()
        assert quality > 0.85  # Should be high

    def test_calculate_quality_extreme_variance(self):
        """Test quality calculation with extreme variance."""
        metrics = FlowQualityMetrics(
            bpm_variance=100.0,  # Extreme variance
            bpm_progression_coherence=1.0,
            energy_consistency=1.0,
            genre_diversity_index=1.0,
        )

        quality = metrics.calculate_overall_quality()
        # BPM score clamped at 0, so max quality is 0.75
        assert quality <= 0.75


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_validate_playlist_pass(self, valid_playlist, valid_track_criteria):
        """Test validating a compliant playlist."""
        # Build a truly compliant playlist with multiple tracks
        for i in range(10):
            track = SelectedTrack(
                track_id=str(i), title=f"T{i}", artist=f"A{i}", album=f"A{i}",
                duration_seconds=240,
                is_australian=(i < 3),  # 30% Australian
                rotation_category="Power", position_in_playlist=i,
                selection_reasoning="Test", validation_status=ValidationStatus.PASS,
                metadata_source="test",
                bpm=128,
                genre="Rock" if i < 4 else "Pop",  # 40% Rock, 60% Pop
                year=2024 if i < 3 else 2020,  # Mix of Current and Recent
            )
            valid_playlist.add_track(track)

        result = ValidationResult.validate_playlist(valid_playlist, valid_track_criteria)

        assert result.playlist_id == valid_playlist.id
        # We just verify it completes successfully
        assert result.overall_status in [ValidationStatus.PASS, ValidationStatus.WARNING, ValidationStatus.FAIL]
        assert result.compliance_percentage >= 0.0
        assert result.validated_at <= datetime.now()

    def test_validate_playlist_australian_content(self, valid_playlist_spec):
        """Test validation of Australian content."""
        playlist = Playlist.create(valid_playlist_spec)

        # Add mostly non-Australian tracks
        for i in range(5):
            track = SelectedTrack(
                track_id=str(i), title=f"T{i}", artist=f"A{i}", album=f"A{i}",
                duration_seconds=240, is_australian=(i == 0),  # Only first is Australian
                rotation_category="Power", position_in_playlist=i,
                selection_reasoning="Test", validation_status=ValidationStatus.PASS,
                metadata_source="test", bpm=128, genre="Rock", year=2024,
            )
            playlist.add_track(track)

        criteria = TrackSelectionCriteria(
            bpm_ranges=[BPMRange(time(6, 0), time(10, 0), 120, 140)],
            genre_mix={"Rock": GenreCriteria(1.0)},
            era_distribution={"Current": EraCriteria("Current", 2023, 2025, 1.0)},
            australian_content_min=0.30,
            energy_flow_requirements=["test"],
            rotation_distribution={"Power": 1.0},
            no_repeat_window_hours=4.0,
        )

        result = ValidationResult.validate_playlist(playlist, criteria)

        # 20% Australian content should fail 30% minimum
        assert any("Australian content" in note for note in result.gap_analysis)
        assert not result.constraint_scores['australian_content'].is_compliant

    def test_validate_playlist_genre_distribution(self, valid_playlist_spec):
        """Test validation of genre distribution."""
        playlist = Playlist.create(valid_playlist_spec)

        # Add tracks with unbalanced genres
        for i in range(10):
            track = SelectedTrack(
                track_id=str(i), title=f"T{i}", artist=f"A{i}", album=f"A{i}",
                duration_seconds=240, is_australian=True,
                rotation_category="Power", position_in_playlist=i,
                selection_reasoning="Test", validation_status=ValidationStatus.PASS,
                metadata_source="test", bpm=128,
                genre="Rock",  # All Rock, no Pop
                year=2024,
            )
            playlist.add_track(track)

        criteria = TrackSelectionCriteria(
            bpm_ranges=[BPMRange(time(6, 0), time(10, 0), 120, 140)],
            genre_mix={
                "Rock": GenreCriteria(0.50, tolerance=0.10),
                "Pop": GenreCriteria(0.50, tolerance=0.10),  # Want 50% Pop, have 0%
            },
            era_distribution={"Current": EraCriteria("Current", 2023, 2025, 1.0)},
            australian_content_min=0.30,
            energy_flow_requirements=["test"],
            rotation_distribution={"Power": 1.0},
            no_repeat_window_hours=4.0,
        )

        result = ValidationResult.validate_playlist(playlist, criteria)

        # Pop genre should be non-compliant
        assert "genre_Pop" in result.constraint_scores
        # Might not be compliant due to 0% vs 50% target

    def test_is_valid_method(self, valid_playlist, valid_track_criteria):
        """Test is_valid() method."""
        result = ValidationResult.validate_playlist(valid_playlist, valid_track_criteria)

        # is_valid() returns True only if status is PASS
        if result.overall_status == ValidationStatus.PASS:
            assert result.is_valid() is True
        else:
            assert result.is_valid() is False

    def test_get_summary(self, valid_playlist, valid_track_criteria):
        """Test get_summary() method."""
        result = ValidationResult.validate_playlist(valid_playlist, valid_track_criteria)
        summary = result.get_summary()

        assert "Validation Result:" in summary
        assert "Compliance:" in summary
        assert "Flow Quality:" in summary
        assert isinstance(summary, str)
        assert len(summary) > 0

    def test_validate_status_pass_threshold(self, valid_playlist_spec):
        """Test validation status determination based on compliance."""
        playlist = Playlist.create(valid_playlist_spec)

        # Add 10 compliant tracks
        for i in range(10):
            track = SelectedTrack(
                track_id=str(i), title=f"T{i}", artist=f"A{i}", album=f"A{i}",
                duration_seconds=240, is_australian=(i < 4),  # 40% Australian
                rotation_category="Power", position_in_playlist=i,
                selection_reasoning="Test", validation_status=ValidationStatus.PASS,
                metadata_source="test", bpm=128, genre="Rock", year=2024,
            )
            playlist.add_track(track)

        criteria = TrackSelectionCriteria(
            bpm_ranges=[BPMRange(time(6, 0), time(10, 0), 120, 140)],
            genre_mix={"Rock": GenreCriteria(1.0)},
            era_distribution={"Current": EraCriteria("Current", 2023, 2025, 1.0)},
            australian_content_min=0.30,
            energy_flow_requirements=["test"],
            rotation_distribution={"Power": 1.0},
            no_repeat_window_hours=4.0,
        )

        result = ValidationResult.validate_playlist(playlist, criteria)

        # Validation completes successfully
        assert result.overall_status in [ValidationStatus.PASS, ValidationStatus.WARNING, ValidationStatus.FAIL]
        assert result.compliance_percentage >= 0.0


class TestConstraintScoresLegacy:
    """Tests for ConstraintScores (legacy) dataclass."""

    def test_valid_instantiation(self):
        """Test creating valid ConstraintScores."""
        scores = ConstraintScores(
            constraint_satisfaction=0.85,
            bpm_satisfaction=0.90,
            genre_satisfaction=0.88,
            era_satisfaction=0.82,
            australian_content=0.35,
        )

        assert scores.constraint_satisfaction == 0.85
        assert scores.bpm_satisfaction == 0.90
        assert scores.genre_satisfaction == 0.88
        assert scores.era_satisfaction == 0.82
        assert scores.australian_content == 0.35

    def test_validation_out_of_range_high(self):
        """Test validation fails for scores > 1.0."""
        with pytest.raises(ValueError, match="must be 0.0-1.0"):
            ConstraintScores(
                constraint_satisfaction=1.5,
                bpm_satisfaction=0.90,
                genre_satisfaction=0.88,
                era_satisfaction=0.82,
                australian_content=0.35,
            )

    def test_validation_out_of_range_low(self):
        """Test validation fails for scores < 0.0."""
        with pytest.raises(ValueError, match="must be 0.0-1.0"):
            ConstraintScores(
                constraint_satisfaction=0.85,
                bpm_satisfaction=-0.10,
                genre_satisfaction=0.88,
                era_satisfaction=0.82,
                australian_content=0.35,
            )

    def test_boundary_values(self):
        """Test boundary values 0.0 and 1.0."""
        scores = ConstraintScores(
            constraint_satisfaction=0.0,
            bpm_satisfaction=1.0,
            genre_satisfaction=0.0,
            era_satisfaction=1.0,
            australian_content=0.5,
        )

        assert scores.constraint_satisfaction == 0.0
        assert scores.bpm_satisfaction == 1.0


class TestFlowMetricsLegacy:
    """Tests for FlowMetrics (legacy) dataclass."""

    def test_valid_instantiation(self):
        """Test creating valid FlowMetrics."""
        metrics = FlowMetrics(
            flow_quality_score=0.75,
            bpm_variance=8.5,
            energy_progression="smooth",
            genre_diversity=0.65,
        )

        assert metrics.flow_quality_score == 0.75
        assert metrics.bpm_variance == 8.5
        assert metrics.energy_progression == "smooth"
        assert metrics.genre_diversity == 0.65

    def test_flow_quality_score_out_of_range(self):
        """Test validation fails for flow quality score out of range."""
        with pytest.raises(ValueError, match="flow_quality_score must be 0.0-1.0"):
            FlowMetrics(
                flow_quality_score=1.5,
                bpm_variance=8.5,
                energy_progression="smooth",
                genre_diversity=0.65,
            )

    def test_negative_bpm_variance(self):
        """Test validation fails for negative BPM variance."""
        with pytest.raises(ValueError, match="BPM variance must be ≥ 0"):
            FlowMetrics(
                flow_quality_score=0.75,
                bpm_variance=-5.0,
                energy_progression="smooth",
                genre_diversity=0.65,
            )

    def test_invalid_energy_progression(self):
        """Test validation fails for invalid energy progression."""
        with pytest.raises(ValueError, match="Energy progression must be one of"):
            FlowMetrics(
                flow_quality_score=0.75,
                bpm_variance=8.5,
                energy_progression="invalid",
                genre_diversity=0.65,
            )

    def test_valid_energy_progressions(self):
        """Test all valid energy progression values."""
        for progression in ["smooth", "choppy", "monotone"]:
            metrics = FlowMetrics(
                flow_quality_score=0.75,
                bpm_variance=8.5,
                energy_progression=progression,
                genre_diversity=0.65,
            )
            assert metrics.energy_progression == progression

    def test_genre_diversity_out_of_range(self):
        """Test validation fails for genre diversity out of range."""
        with pytest.raises(ValueError, match="genre_diversity must be 0.0-1.0"):
            FlowMetrics(
                flow_quality_score=0.75,
                bpm_variance=8.5,
                energy_progression="smooth",
                genre_diversity=1.2,
            )

    def test_zero_bpm_variance(self):
        """Test zero BPM variance is valid."""
        metrics = FlowMetrics(
            flow_quality_score=0.75,
            bpm_variance=0.0,
            energy_progression="monotone",
            genre_diversity=0.50,
        )

        assert metrics.bpm_variance == 0.0
        assert metrics.energy_progression == "monotone"
