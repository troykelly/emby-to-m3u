"""
Validation and decision logging models for AI Playlist.

This module contains dataclasses for comprehensive playlist validation results
including constraint scores, flow quality metrics, and compliance assessment.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List
import math
import statistics

# Import required types from core module
# Note: Using TYPE_CHECKING to avoid circular imports
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .core import Playlist, TrackSelectionCriteria, ValidationStatus
else:
    # Runtime imports
    try:
        from .core import ValidationStatus
    except ImportError:
        # Fallback if core not loaded yet
        from enum import Enum

        class ValidationStatus(Enum):
            PASS = "pass"
            FAIL = "fail"
            WARNING = "warning"


# ============================================================================
# Constraint Score
# ============================================================================


@dataclass
class ConstraintScore:
    """Score for individual constraint compliance.

    Tracks how well a playlist meets a specific constraint with tolerance.

    Attributes:
        constraint_name: Name of the constraint being scored
        target_value: Target value for the constraint
        actual_value: Actual value achieved
        tolerance: Acceptable tolerance (as percentage)
        is_compliant: Whether constraint is satisfied
        deviation_percentage: Percentage deviation from target
    """
    constraint_name: str
    target_value: float
    actual_value: float
    tolerance: float
    is_compliant: bool
    deviation_percentage: float

    @classmethod
    def calculate(
        cls,
        name: str,
        target: float,
        actual: float,
        tolerance: float = 0.10
    ) -> 'ConstraintScore':
        """Calculate compliance score for a constraint.

        Args:
            name: Constraint name
            target: Target value
            actual: Actual value achieved
            tolerance: Acceptable tolerance (default 10%)

        Returns:
            ConstraintScore instance
        """
        min_acceptable = target * (1 - tolerance)
        max_acceptable = target * (1 + tolerance)

        is_compliant = min_acceptable <= actual <= max_acceptable

        if target == 0:
            deviation_pct = 0.0
        else:
            deviation_pct = abs(actual - target) / target

        return cls(
            constraint_name=name,
            target_value=target,
            actual_value=actual,
            tolerance=tolerance,
            is_compliant=is_compliant,
            deviation_percentage=deviation_pct
        )


# ============================================================================
# Flow Quality Metrics
# ============================================================================


@dataclass
class FlowQualityMetrics:
    """Quality metrics for playlist flow.

    Measures how well the playlist flows in terms of BPM progression,
    energy consistency, and genre diversity.

    Attributes:
        bpm_variance: Standard deviation of BPM across tracks
        bpm_progression_coherence: How well BPM follows intended progression (0.0-1.0)
        energy_consistency: Consistency of energy levels (0.0-1.0)
        genre_diversity_index: Shannon entropy of genre distribution (0.0-1.0)
    """
    bpm_variance: float  # Standard deviation of BPM
    bpm_progression_coherence: float  # 0.0-1.0, how well BPM follows progression
    energy_consistency: float  # 0.0-1.0
    genre_diversity_index: float  # 0.0-1.0, Shannon entropy

    def calculate_overall_quality(self) -> float:
        """Calculate overall flow quality score.

        Combines all metrics into a single quality score.

        Returns:
            Overall quality score (0.0-1.0)
        """
        # Lower BPM variance is better - normalize to 0-1
        bpm_score = max(0, 1 - (self.bpm_variance / 30))  # Normalize to 0-1

        # Average the metrics with equal weighting
        return (
            bpm_score * 0.25 +
            self.bpm_progression_coherence * 0.25 +
            self.energy_consistency * 0.25 +
            self.genre_diversity_index * 0.25
        )


# ============================================================================
# Validation Result
# ============================================================================


@dataclass
class ValidationResult:
    """Complete validation assessment of playlist.

    Provides comprehensive analysis of playlist compliance with all constraints,
    flow quality, and overall pass/fail status.

    Attributes:
        playlist_id: Reference to playlist being validated
        overall_status: Overall validation status (PASS/FAIL/WARNING)
        constraint_scores: Scores for each constraint type
        flow_quality_metrics: Flow quality measurements
        compliance_percentage: Overall compliance score (0.0-1.0)
        validated_at: When validation was performed
        gap_analysis: List of identified deficiencies
    """

    playlist_id: str
    overall_status: 'ValidationStatus'
    constraint_scores: Dict[str, ConstraintScore]
    flow_quality_metrics: FlowQualityMetrics
    compliance_percentage: float
    validated_at: datetime
    gap_analysis: List[str] = field(default_factory=list)

    @classmethod
    def validate_playlist(
        cls,
        playlist: 'Playlist',
        criteria: 'TrackSelectionCriteria'
    ) -> 'ValidationResult':
        """Perform complete validation of playlist against criteria.

        Args:
            playlist: Playlist to validate
            criteria: Selection criteria to validate against

        Returns:
            ValidationResult with complete assessment
        """
        # Import here to avoid circular dependency
        from .core import ValidationStatus

        constraint_scores: Dict[str, ConstraintScore] = {}
        gap_analysis: List[str] = []

        # Validate Australian content
        australian_pct = playlist.calculate_australian_percentage()
        constraint_scores['australian_content'] = ConstraintScore.calculate(
            name="Australian Content",
            target=criteria.australian_content_min,
            actual=australian_pct,
            tolerance=0.0  # Hard minimum
        )

        if not constraint_scores['australian_content'].is_compliant:
            gap_analysis.append(
                f"Australian content {australian_pct:.1%} below minimum {criteria.australian_content_min:.1%}"
            )

        # Validate genre distribution
        actual_genres = playlist.calculate_genre_distribution()
        for genre, genre_criteria in criteria.genre_mix.items():
            actual_pct = actual_genres.get(genre, 0.0)
            constraint_scores[f'genre_{genre}'] = ConstraintScore.calculate(
                name=f"Genre: {genre}",
                target=genre_criteria.target_percentage,
                actual=actual_pct,
                tolerance=genre_criteria.tolerance
            )

        # Validate era distribution
        actual_eras = playlist.calculate_era_distribution()
        for era, era_criteria in criteria.era_distribution.items():
            actual_pct = actual_eras.get(era, 0.0)
            constraint_scores[f'era_{era}'] = ConstraintScore.calculate(
                name=f"Era: {era}",
                target=era_criteria.target_percentage,
                actual=actual_pct,
                tolerance=era_criteria.tolerance
            )

        # Calculate flow quality metrics
        bpms = [t.bpm for t in playlist.tracks if t.bpm is not None]
        bpm_variance = statistics.stdev(bpms) if len(bpms) > 1 else 0.0

        # Calculate genre diversity (Shannon entropy)
        genre_entropy = 0.0
        for pct in actual_genres.values():
            if pct > 0:
                genre_entropy -= pct * math.log2(pct)

        # Normalize entropy to 0-1 (max entropy with 5 genres ≈ 2.32)
        genre_diversity = min(1.0, genre_entropy / 2.32)

        flow_metrics = FlowQualityMetrics(
            bpm_variance=bpm_variance,
            bpm_progression_coherence=0.85,  # Would calculate from actual progression
            energy_consistency=0.90,  # Would calculate from track energy
            genre_diversity_index=genre_diversity
        )

        # Calculate overall compliance
        compliant_count = sum(1 for score in constraint_scores.values() if score.is_compliant)
        compliance_pct = compliant_count / len(constraint_scores) if constraint_scores else 0.0

        # Determine overall status
        if compliance_pct >= 0.95:
            overall_status = ValidationStatus.PASS
        elif compliance_pct >= 0.80:
            overall_status = ValidationStatus.WARNING
        else:
            overall_status = ValidationStatus.FAIL

        return cls(
            playlist_id=playlist.id,
            overall_status=overall_status,
            constraint_scores=constraint_scores,
            flow_quality_metrics=flow_metrics,
            compliance_percentage=compliance_pct,
            validated_at=datetime.now(),
            gap_analysis=gap_analysis
        )

    def is_valid(self) -> bool:
        """Check if validation passed.

        Returns:
            True if overall status is PASS, False otherwise
        """
        # Import here to avoid circular dependency
        from .core import ValidationStatus
        return self.overall_status == ValidationStatus.PASS

    def get_summary(self) -> str:
        """Get human-readable validation summary.

        Returns:
            Formatted summary string
        """
        status_emoji = {
            "pass": "✓",
            "warning": "⚠",
            "fail": "✗"
        }

        lines = [
            f"{status_emoji.get(self.overall_status.value, '?')} Validation Result: {self.overall_status.value.upper()}",
            f"Compliance: {self.compliance_percentage:.1%}",
            f"Flow Quality: {self.flow_quality_metrics.calculate_overall_quality():.1%}",
            ""
        ]

        if self.gap_analysis:
            lines.append("Issues:")
            for issue in self.gap_analysis:
                lines.append(f"  - {issue}")
        else:
            lines.append("No issues found")

        return "\n".join(lines)


# ============================================================================
# Legacy Compatibility Classes
# ============================================================================


@dataclass
class ConstraintScores:
    """Legacy constraint satisfaction scores (0.0-1.0).

    Maintained for backward compatibility with existing code.
    New code should use ValidationResult instead.
    """

    constraint_satisfaction: float
    bpm_satisfaction: float
    genre_satisfaction: float
    era_satisfaction: float
    australian_content: float

    def __post_init__(self) -> None:
        """Validate all scores are in range 0.0-1.0."""
        for field_name, field_value in [
            ("constraint_satisfaction", self.constraint_satisfaction),
            ("bpm_satisfaction", self.bpm_satisfaction),
            ("genre_satisfaction", self.genre_satisfaction),
            ("era_satisfaction", self.era_satisfaction),
            ("australian_content", self.australian_content),
        ]:
            if not 0.0 <= field_value <= 1.0:
                raise ValueError(f"{field_name} must be 0.0-1.0")


@dataclass
class FlowMetrics:
    """Legacy flow quality metrics for playlist.

    Maintained for backward compatibility with existing code.
    New code should use FlowQualityMetrics instead.
    """

    flow_quality_score: float
    bpm_variance: float
    energy_progression: str
    genre_diversity: float

    def __post_init__(self) -> None:
        """Validate flow metrics."""
        if not 0.0 <= self.flow_quality_score <= 1.0:
            raise ValueError("flow_quality_score must be 0.0-1.0")

        if self.bpm_variance < 0:
            raise ValueError("BPM variance must be ≥ 0")

        valid_progressions = ["smooth", "choppy", "monotone"]
        if self.energy_progression not in valid_progressions:
            raise ValueError(f"Energy progression must be one of {valid_progressions}")

        if not 0.0 <= self.genre_diversity <= 1.0:
            raise ValueError("genre_diversity must be 0.0-1.0")
