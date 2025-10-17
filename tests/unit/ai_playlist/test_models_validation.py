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
