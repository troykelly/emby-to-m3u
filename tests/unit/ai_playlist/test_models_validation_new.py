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
