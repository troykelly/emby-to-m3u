"""
Comprehensive tests for models/validation.py module.

Tests validation model dataclasses including:
- ConstraintScore and its calculate() method
- FlowQualityMetrics and calculate_overall_quality()
- ValidationResult and is_valid() method
"""
import pytest
from datetime import datetime

from src.ai_playlist.models.validation import (
    ConstraintScore,
    FlowQualityMetrics,
    ValidationResult,
    ValidationStatus,
)


class TestConstraintScore:
    """Tests for ConstraintScore dataclass."""

    def test_constraint_score_creation(self):
        """Test creating a ConstraintScore instance."""
        # Arrange & Act
        score = ConstraintScore(
            constraint_name="Australian Content",
            target_value=0.30,
            actual_value=0.33,
            tolerance=0.10,
            is_compliant=True,
            deviation_percentage=0.10,
        )

        # Assert
        assert score.constraint_name == "Australian Content"
        assert score.target_value == 0.30
        assert score.actual_value == 0.33
        assert score.is_compliant is True

    def test_calculate_compliant_score(self):
        """Test calculate() method with compliant values."""
        # Act
        score = ConstraintScore.calculate(
            name="Australian Content",
            target=0.30,
            actual=0.33,
            tolerance=0.10
        )

        # Assert
        assert score.constraint_name == "Australian Content"
        assert score.target_value == 0.30
        assert score.actual_value == 0.33
        assert score.is_compliant is True
        assert score.tolerance == 0.10
        assert abs(score.deviation_percentage - 0.10) < 0.01

    def test_calculate_non_compliant_score(self):
        """Test calculate() method with non-compliant values."""
        # Act
        score = ConstraintScore.calculate(
            name="Genre Mix",
            target=0.50,
            actual=0.20,  # Way below target
            tolerance=0.10
        )

        # Assert
        assert score.is_compliant is False
        assert score.actual_value == 0.20
        assert score.deviation_percentage == 0.60  # 60% deviation

    def test_calculate_with_zero_target(self):
        """Test calculate() handles zero target gracefully."""
        # Act
        score = ConstraintScore.calculate(
            name="Test",
            target=0.0,
            actual=0.1,
            tolerance=0.10
        )

        # Assert
        assert score.deviation_percentage == 0.0  # Special case for zero target

    def test_calculate_at_lower_tolerance_boundary(self):
        """Test calculate() at lower boundary of tolerance."""
        # Arrange
        target = 0.50
        tolerance = 0.10
        actual = target * (1 - tolerance)  # Exactly at lower boundary

        # Act
        score = ConstraintScore.calculate(
            name="Test",
            target=target,
            actual=actual,
            tolerance=tolerance
        )

        # Assert
        assert score.is_compliant is True

    def test_calculate_at_upper_tolerance_boundary(self):
        """Test calculate() at upper boundary of tolerance."""
        # Arrange
        target = 0.50
        tolerance = 0.10
        actual = target * (1 + tolerance)  # Exactly at upper boundary

        # Act
        score = ConstraintScore.calculate(
            name="Test",
            target=target,
            actual=actual,
            tolerance=tolerance
        )

        # Assert
        assert score.is_compliant is True

    def test_calculate_below_lower_tolerance(self):
        """Test calculate() just below lower tolerance boundary."""
        # Arrange
        target = 0.50
        tolerance = 0.10
        actual = target * (1 - tolerance) - 0.01  # Just below boundary

        # Act
        score = ConstraintScore.calculate(
            name="Test",
            target=target,
            actual=actual,
            tolerance=tolerance
        )

        # Assert
        assert score.is_compliant is False

    def test_calculate_above_upper_tolerance(self):
        """Test calculate() just above upper tolerance boundary."""
        # Arrange
        target = 0.50
        tolerance = 0.10
        actual = target * (1 + tolerance) + 0.01  # Just above boundary

        # Act
        score = ConstraintScore.calculate(
            name="Test",
            target=target,
            actual=actual,
            tolerance=tolerance
        )

        # Assert
        assert score.is_compliant is False


class TestFlowQualityMetrics:
    """Tests for FlowQualityMetrics dataclass."""

    def test_flow_quality_metrics_creation(self):
        """Test creating FlowQualityMetrics instance."""
        # Arrange & Act
        metrics = FlowQualityMetrics(
            bpm_variance=5.0,
            bpm_progression_coherence=0.90,
            energy_consistency=0.85,
            genre_diversity_index=0.75,
        )

        # Assert
        assert metrics.bpm_variance == 5.0
        assert metrics.bpm_progression_coherence == 0.90
        assert metrics.energy_consistency == 0.85
        assert metrics.genre_diversity_index == 0.75

    def test_calculate_overall_quality_excellent(self):
        """Test calculate_overall_quality() with excellent metrics."""
        # Arrange
        metrics = FlowQualityMetrics(
            bpm_variance=5.0,  # Low variance is good
            bpm_progression_coherence=0.95,
            energy_consistency=0.90,
            genre_diversity_index=0.85,
        )

        # Act
        quality = metrics.calculate_overall_quality()

        # Assert
        assert 0.0 <= quality <= 1.0
        assert quality > 0.80  # Should be high quality

    def test_calculate_overall_quality_poor(self):
        """Test calculate_overall_quality() with poor metrics."""
        # Arrange
        metrics = FlowQualityMetrics(
            bpm_variance=50.0,  # High variance is bad
            bpm_progression_coherence=0.30,
            energy_consistency=0.20,
            genre_diversity_index=0.10,
        )

        # Act
        quality = metrics.calculate_overall_quality()

        # Assert
        assert 0.0 <= quality <= 1.0
        assert quality < 0.50  # Should be low quality

    def test_calculate_overall_quality_zero_variance(self):
        """Test calculate_overall_quality() with zero BPM variance."""
        # Arrange
        metrics = FlowQualityMetrics(
            bpm_variance=0.0,  # Perfect consistency
            bpm_progression_coherence=1.0,
            energy_consistency=1.0,
            genre_diversity_index=1.0,
        )

        # Act
        quality = metrics.calculate_overall_quality()

        # Assert
        assert quality == 1.0  # Perfect score

    def test_calculate_overall_quality_high_variance(self):
        """Test calculate_overall_quality() with very high BPM variance."""
        # Arrange
        metrics = FlowQualityMetrics(
            bpm_variance=100.0,  # Very high variance
            bpm_progression_coherence=0.0,
            energy_consistency=0.0,
            genre_diversity_index=0.0,
        )

        # Act
        quality = metrics.calculate_overall_quality()

        # Assert
        assert 0.0 <= quality <= 1.0
        # BPM score should be clamped to 0, so overall should be close to 0
        assert quality < 0.10


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_validation_result_creation(self):
        """Test creating ValidationResult instance."""
        # Arrange
        metrics = FlowQualityMetrics(
            bpm_variance=5.0,
            bpm_progression_coherence=0.90,
            energy_consistency=0.85,
            genre_diversity_index=0.75,
        )

        score = ConstraintScore(
            constraint_name="Australian Content",
            target_value=0.30,
            actual_value=0.33,
            tolerance=0.10,
            is_compliant=True,
            deviation_percentage=0.10,
        )

        # Act
        result = ValidationResult(
            playlist_id="test-playlist-001",
            overall_status=ValidationStatus.PASS,
            constraint_scores={"australian_content": score},
            flow_quality_metrics=metrics,
            compliance_percentage=0.92,
            validated_at=datetime.now(),
            gap_analysis=[],
        )

        # Assert
        assert result.playlist_id == "test-playlist-001"
        assert result.overall_status == ValidationStatus.PASS
        assert result.compliance_percentage == 0.92
        assert len(result.constraint_scores) == 1

    def test_validation_result_with_gap_analysis(self):
        """Test ValidationResult with gap analysis."""
        # Arrange
        metrics = FlowQualityMetrics(
            bpm_variance=15.0,
            bpm_progression_coherence=0.70,
            energy_consistency=0.65,
            genre_diversity_index=0.60,
        )

        # Act
        result = ValidationResult(
            playlist_id="test-playlist-002",
            overall_status=ValidationStatus.WARNING,
            constraint_scores={},
            flow_quality_metrics=metrics,
            compliance_percentage=0.75,
            validated_at=datetime.now(),
            gap_analysis=[
                "BPM variance too high",
                "Genre diversity below target",
            ],
        )

        # Assert
        assert result.overall_status == ValidationStatus.WARNING
        assert len(result.gap_analysis) == 2
        assert "BPM variance" in result.gap_analysis[0]

    def test_validation_result_failed(self):
        """Test ValidationResult with FAIL status."""
        # Arrange
        metrics = FlowQualityMetrics(
            bpm_variance=30.0,
            bpm_progression_coherence=0.40,
            energy_consistency=0.35,
            genre_diversity_index=0.30,
        )

        # Act
        result = ValidationResult(
            playlist_id="test-playlist-003",
            overall_status=ValidationStatus.FAIL,
            constraint_scores={},
            flow_quality_metrics=metrics,
            compliance_percentage=0.45,
            validated_at=datetime.now(),
            gap_analysis=[
                "Australian content requirement not met",
                "Genre distribution outside tolerance",
                "Flow quality below threshold",
            ],
        )

        # Assert
        assert result.overall_status == ValidationStatus.FAIL
        assert result.compliance_percentage < 0.50
        assert len(result.gap_analysis) == 3

    def test_is_valid_returns_true_for_pass(self):
        """Test is_valid() returns True for PASS status."""
        # Arrange
        metrics = FlowQualityMetrics(
            bpm_variance=5.0,
            bpm_progression_coherence=0.90,
            energy_consistency=0.85,
            genre_diversity_index=0.75,
        )

        result = ValidationResult(
            playlist_id="test-playlist-001",
            overall_status=ValidationStatus.PASS,
            constraint_scores={},
            flow_quality_metrics=metrics,
            compliance_percentage=0.92,
            validated_at=datetime.now(),
            gap_analysis=[],
        )

        # Act & Assert
        assert result.is_valid() is True

    def test_is_valid_returns_false_for_fail(self):
        """Test is_valid() returns False for FAIL status."""
        # Arrange
        metrics = FlowQualityMetrics(
            bpm_variance=30.0,
            bpm_progression_coherence=0.40,
            energy_consistency=0.35,
            genre_diversity_index=0.30,
        )

        result = ValidationResult(
            playlist_id="test-playlist-003",
            overall_status=ValidationStatus.FAIL,
            constraint_scores={},
            flow_quality_metrics=metrics,
            compliance_percentage=0.45,
            validated_at=datetime.now(),
            gap_analysis=["Multiple issues"],
        )

        # Act & Assert
        assert result.is_valid() is False

    def test_is_valid_returns_false_for_warning(self):
        """Test is_valid() returns False for WARNING status."""
        # Arrange
        metrics = FlowQualityMetrics(
            bpm_variance=15.0,
            bpm_progression_coherence=0.70,
            energy_consistency=0.65,
            genre_diversity_index=0.60,
        )

        result = ValidationResult(
            playlist_id="test-playlist-002",
            overall_status=ValidationStatus.WARNING,
            constraint_scores={},
            flow_quality_metrics=metrics,
            compliance_percentage=0.75,
            validated_at=datetime.now(),
            gap_analysis=["Minor issues"],
        )

        # Act & Assert
        assert result.is_valid() is False  # Only PASS returns True
"""
Comprehensive tests for models/validation.py - Additional coverage.

This file adds tests for:
- ValidationResult.validate_playlist() class method
- ValidationResult.get_summary() method
- Legacy ConstraintScores and FlowMetrics validation
"""

import pytest
from datetime import datetime
from decimal import Decimal
from unittest.mock import Mock

from src.ai_playlist.models.validation import (
    ConstraintScore,
    FlowQualityMetrics,
    ValidationResult,
    ConstraintScores,
    FlowMetrics,
)
from src.ai_playlist.models.core import ValidationStatus


class TestValidationResultGetSummary:
    """Test ValidationResult.get_summary() method."""

    def test_get_summary_pass_status(self):
        """Test get_summary with PASS status."""
        result = ValidationResult(
            playlist_id="test-pass",
            overall_status=ValidationStatus.PASS,
            constraint_scores={},
            flow_quality_metrics=FlowQualityMetrics(
                bpm_variance=10.0,
                bpm_progression_coherence=0.90,
                energy_consistency=0.85,
                genre_diversity_index=0.75
            ),
            compliance_percentage=0.98,
            gap_analysis=[],
            validated_at=datetime.now()
        )

        summary = result.get_summary()

        assert "✓" in summary
        assert "PASS" in summary
        assert "No issues found" in summary
        assert "98.0%" in summary  # Compliance percentage

    def test_get_summary_warning_status(self):
        """Test get_summary with WARNING status."""
        result = ValidationResult(
            playlist_id="test-warning",
            overall_status=ValidationStatus.WARNING,
            constraint_scores={},
            flow_quality_metrics=FlowQualityMetrics(
                bpm_variance=15.0,
                bpm_progression_coherence=0.75,
                energy_consistency=0.80,
                genre_diversity_index=0.60
            ),
            compliance_percentage=0.85,
            gap_analysis=["Australian content below target"],
            validated_at=datetime.now()
        )

        summary = result.get_summary()

        assert "⚠" in summary
        assert "WARNING" in summary
        assert "Issues:" in summary
        assert "Australian content below target" in summary

    def test_get_summary_fail_status(self):
        """Test get_summary with FAIL status."""
        result = ValidationResult(
            playlist_id="test-fail",
            overall_status=ValidationStatus.FAIL,
            constraint_scores={},
            flow_quality_metrics=FlowQualityMetrics(
                bpm_variance=25.0,
                bpm_progression_coherence=0.50,
                energy_consistency=0.60,
                genre_diversity_index=0.40
            ),
            compliance_percentage=0.65,
            gap_analysis=[
                "Australian content 10.0% below minimum 30.0%",
                "Genre distribution non-compliant"
            ],
            validated_at=datetime.now()
        )

        summary = result.get_summary()

        assert "✗" in summary
        assert "FAIL" in summary
        assert "Issues:" in summary
        assert "Australian content" in summary
        assert "Genre distribution" in summary


class TestLegacyConstraintScores:
    """Test legacy ConstraintScores dataclass validation."""

    def test_constraint_scores_valid_creation(self):
        """Test creating ConstraintScores with valid data."""
        constraints = ConstraintScores(
            constraint_satisfaction=0.95,
            bpm_satisfaction=0.90,
            genre_satisfaction=0.88,
            era_satisfaction=0.92,
            australian_content=0.35
        )

        assert constraints.constraint_satisfaction == 0.95
        assert constraints.bpm_satisfaction == 0.90
        assert constraints.genre_satisfaction == 0.88
        assert constraints.era_satisfaction == 0.92
        assert constraints.australian_content == 0.35

    def test_constraint_scores_boundary_values(self):
        """Test ConstraintScores with boundary values (0.0 and 1.0)."""
        constraints = ConstraintScores(
            constraint_satisfaction=0.0,
            bpm_satisfaction=1.0,
            genre_satisfaction=0.0,
            era_satisfaction=1.0,
            australian_content=0.5
        )

        assert constraints.constraint_satisfaction == 0.0
        assert constraints.bpm_satisfaction == 1.0

    def test_constraint_scores_invalid_constraint_satisfaction(self):
        """Test ConstraintScores validates constraint_satisfaction range."""
        with pytest.raises(ValueError, match="must be 0.0-1.0"):
            ConstraintScores(
                constraint_satisfaction=1.5,  # Invalid > 1.0
                bpm_satisfaction=0.90,
                genre_satisfaction=0.88,
                era_satisfaction=0.92,
                australian_content=0.35
            )

    def test_constraint_scores_invalid_negative(self):
        """Test ConstraintScores validates negative values."""
        with pytest.raises(ValueError, match="must be 0.0-1.0"):
            ConstraintScores(
                constraint_satisfaction=0.95,
                bpm_satisfaction=-0.10,  # Invalid negative
                genre_satisfaction=0.88,
                era_satisfaction=0.92,
                australian_content=0.35
            )


class TestLegacyFlowMetrics:
    """Test legacy FlowMetrics dataclass validation."""

    def test_flow_metrics_valid_creation(self):
        """Test creating FlowMetrics with valid data."""
        metrics = FlowMetrics(
            flow_quality_score=0.85,
            bpm_variance=12.5,
            energy_progression="smooth",
            genre_diversity=0.70
        )

        assert metrics.flow_quality_score == 0.85
        assert metrics.bpm_variance == 12.5
        assert metrics.energy_progression == "smooth"
        assert metrics.genre_diversity == 0.70

    def test_flow_metrics_all_valid_progressions(self):
        """Test FlowMetrics accepts all valid energy progression values."""
        valid_progressions = ["smooth", "choppy", "monotone"]

        for progression in valid_progressions:
            metrics = FlowMetrics(
                flow_quality_score=0.85,
                bpm_variance=10.0,
                energy_progression=progression,
                genre_diversity=0.70
            )
            assert metrics.energy_progression == progression

    def test_flow_metrics_invalid_quality_score_above_range(self):
        """Test FlowMetrics validates flow_quality_score ≤ 1.0."""
        with pytest.raises(ValueError, match="flow_quality_score must be 0.0-1.0"):
            FlowMetrics(
                flow_quality_score=1.2,  # Invalid > 1.0
                bpm_variance=12.5,
                energy_progression="smooth",
                genre_diversity=0.70
            )

    def test_flow_metrics_invalid_quality_score_negative(self):
        """Test FlowMetrics validates flow_quality_score ≥ 0.0."""
        with pytest.raises(ValueError, match="flow_quality_score must be 0.0-1.0"):
            FlowMetrics(
                flow_quality_score=-0.1,  # Invalid negative
                bpm_variance=12.5,
                energy_progression="smooth",
                genre_diversity=0.70
            )

    def test_flow_metrics_invalid_bpm_variance(self):
        """Test FlowMetrics validates BPM variance is non-negative."""
        with pytest.raises(ValueError, match="BPM variance must be ≥ 0"):
            FlowMetrics(
                flow_quality_score=0.85,
                bpm_variance=-5.0,  # Invalid negative
                energy_progression="smooth",
                genre_diversity=0.70
            )

    def test_flow_metrics_invalid_energy_progression(self):
        """Test FlowMetrics validates energy_progression values."""
        with pytest.raises(ValueError, match="Energy progression must be one of"):
            FlowMetrics(
                flow_quality_score=0.85,
                bpm_variance=12.5,
                energy_progression="invalid",  # Not in valid list
                genre_diversity=0.70
            )

    def test_flow_metrics_invalid_genre_diversity_above_range(self):
        """Test FlowMetrics validates genre_diversity ≤ 1.0."""
        with pytest.raises(ValueError, match="genre_diversity must be 0.0-1.0"):
            FlowMetrics(
                flow_quality_score=0.85,
                bpm_variance=12.5,
                energy_progression="smooth",
                genre_diversity=1.5  # Invalid > 1.0
            )

    def test_flow_metrics_invalid_genre_diversity_negative(self):
        """Test FlowMetrics validates genre_diversity ≥ 0.0."""
        with pytest.raises(ValueError, match="genre_diversity must be 0.0-1.0"):
            FlowMetrics(
                flow_quality_score=0.85,
                bpm_variance=12.5,
                energy_progression="smooth",
                genre_diversity=-0.2  # Invalid negative
            )
