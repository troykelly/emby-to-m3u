"""
Playlist Validator with ±10% Tolerance - T034

Validates generated playlists against station identity criteria with tolerances.

Success Criteria (T026):
- Genre distribution: target ±10% tolerance (25% allows 15-35%)
- Era distribution: target ±10% tolerance
- Australian content: hard 30% minimum (no tolerance)
- BPM progression: coherence score 0-1.0
"""

from typing import Dict, List
from dataclasses import dataclass
import statistics
import logging

from src.ai_playlist.models.core import (
    Playlist,
    PlaylistSpecification,
    TrackSelectionCriteria
)
from src.ai_playlist.models.validation import (
    ValidationResult,
    ConstraintScore,
    FlowQualityMetrics,
    ValidationStatus
)

logger = logging.getLogger(__name__)


class PlaylistValidator:
    """Validator for AI-generated playlists."""

    def validate(
        self,
        playlist: Playlist,
        specification: PlaylistSpecification
    ) -> ValidationResult:
        """Validate playlist against specification.

        Args:
            playlist: Playlist to validate
            specification: Specification with criteria

        Returns:
            ValidationResult with overall status and scores
        """
        criteria = specification.track_selection_criteria

        # Validate Australian content (hard minimum, no tolerance)
        australian_score = self._validate_australian_content(
            playlist,
            criteria.australian_content_min
        )

        # Validate genre distribution (±10% tolerance)
        genre_score = self._validate_genre_distribution(
            playlist,
            criteria.genre_mix
        )

        # Validate era distribution (±10% tolerance)
        era_score = self._validate_era_distribution(
            playlist,
            criteria.era_distribution
        )

        # Validate BPM progression
        bpm_score, flow_metrics = self._validate_bpm_progression(
            playlist,
            criteria.bpm_ranges
        )

        # Calculate overall compliance
        constraint_scores = {
            "australian_content": australian_score,
            "genre_distribution": genre_score,
            "era_distribution": era_score,
            "bpm_progression": bpm_score
        }

        # Overall compliance is average of all scores
        # Calculate score from compliance and deviation
        def calculate_score(cs: ConstraintScore) -> float:
            if cs.is_compliant:
                return 1.0 - (cs.deviation_percentage * 0.5)  # Reduce score slightly for deviation
            else:
                return max(0.0, 1.0 - cs.deviation_percentage)  # Penalize non-compliance

        compliance_percentage = sum(
            calculate_score(score) for score in constraint_scores.values()
        ) / len(constraint_scores)

        # Determine overall status
        if compliance_percentage >= 0.95:
            overall_status = ValidationStatus.PASS
        elif compliance_percentage >= 0.80:
            overall_status = ValidationStatus.WARNING
        else:
            overall_status = ValidationStatus.FAIL

        return ValidationResult(
            playlist_id=playlist.id,
            overall_status=overall_status.value,
            constraint_scores=constraint_scores,
            flow_quality_metrics=flow_metrics,
            compliance_percentage=compliance_percentage,
            validated_at=datetime.now(),
            gap_analysis=[]
        )

    def _validate_australian_content(
        self,
        playlist: Playlist,
        min_required: float
    ) -> ConstraintScore:
        """Validate Australian content (hard minimum, no tolerance)."""
        actual = playlist.calculate_australian_percentage()

        # Australian content has NO tolerance
        is_compliant = actual >= min_required

        # Calculate deviation percentage
        if min_required > 0:
            deviation_percentage = abs(actual - min_required) / min_required
        else:
            deviation_percentage = 0.0

        return ConstraintScore(
            constraint_name="australian_content",
            target_value=min_required,
            actual_value=actual,
            tolerance=0.0,  # Hard minimum, no tolerance
            is_compliant=is_compliant,
            deviation_percentage=deviation_percentage
        )

    def _validate_genre_distribution(
        self,
        playlist: Playlist,
        target_mix: Dict[str, any]
    ) -> ConstraintScore:
        """Validate genre distribution (±10% tolerance)."""
        actual_distribution = playlist.calculate_genre_distribution()

        total_deviation = 0.0
        total_target = 0.0
        all_compliant = True

        for genre, criteria in target_mix.items():
            target = criteria.target_percentage
            tolerance = criteria.tolerance
            actual = actual_distribution.get(genre, 0.0)

            min_allowed = target - tolerance
            max_allowed = target + tolerance

            if not (min_allowed <= actual <= max_allowed):
                all_compliant = False
                deviation = min(
                    abs(actual - min_allowed),
                    abs(actual - max_allowed)
                )
                total_deviation += deviation

            total_target += target

        # Calculate overall deviation percentage
        avg_deviation = total_deviation / len(target_mix) if target_mix else 0.0
        deviation_percentage = avg_deviation / (total_target / len(target_mix)) if target_mix and total_target > 0 else 0.0

        # Use a representative target (average) and actual (sum of all actual values)
        avg_target = total_target / len(target_mix) if target_mix else 0.0
        avg_actual = sum(actual_distribution.values()) / len(actual_distribution) if actual_distribution else 0.0

        return ConstraintScore(
            constraint_name="genre_distribution",
            target_value=avg_target,
            actual_value=avg_actual,
            tolerance=0.10,  # ±10% tolerance
            is_compliant=all_compliant,
            deviation_percentage=deviation_percentage
        )

    def _validate_era_distribution(
        self,
        playlist: Playlist,
        target_distribution: Dict[str, any]
    ) -> ConstraintScore:
        """Validate era distribution (±10% tolerance)."""
        actual_distribution = playlist.calculate_era_distribution()

        total_deviation = 0.0
        total_target = 0.0
        all_compliant = True

        for era, criteria in target_distribution.items():
            target = criteria.target_percentage
            tolerance = criteria.tolerance
            actual = actual_distribution.get(era, 0.0)

            min_allowed = target - tolerance
            max_allowed = target + tolerance

            if not (min_allowed <= actual <= max_allowed):
                all_compliant = False
                deviation = min(
                    abs(actual - min_allowed),
                    abs(actual - max_allowed)
                )
                total_deviation += deviation

            total_target += target

        # Calculate overall deviation percentage
        avg_deviation = total_deviation / len(target_distribution) if target_distribution else 0.0
        deviation_percentage = avg_deviation / (total_target / len(target_distribution)) if target_distribution and total_target > 0 else 0.0

        # Use a representative target (average) and actual (sum of all actual values)
        avg_target = total_target / len(target_distribution) if target_distribution else 0.0
        avg_actual = sum(actual_distribution.values()) / len(actual_distribution) if actual_distribution else 0.0

        return ConstraintScore(
            constraint_name="era_distribution",
            target_value=avg_target,
            actual_value=avg_actual,
            tolerance=0.10,  # ±10% tolerance
            is_compliant=all_compliant,
            deviation_percentage=deviation_percentage
        )

    def _validate_bpm_progression(
        self,
        playlist: Playlist,
        target_ranges: List[tuple]
    ) -> tuple:
        """Validate BPM progression coherence."""
        bpm_values = [t.bpm for t in playlist.tracks if t.bpm and t.bpm > 0]

        if not bpm_values:
            return (
                ConstraintScore(
                    constraint_name="bpm_progression",
                    target_value=0.0,
                    actual_value=0.0,
                    tolerance=0.0,
                    is_compliant=False,
                    deviation_percentage=1.0  # 100% deviation since no data
                ),
                FlowQualityMetrics(
                    bpm_variance=0.0,
                    bpm_progression_coherence=0.0,
                    energy_consistency=0.0,
                    genre_diversity_index=0.0
                )
            )

        # Calculate variance
        bpm_variance = statistics.stdev(bpm_values) if len(bpm_values) > 1 else 0.0

        # Count large jumps (>20 BPM)
        large_jumps = 0
        for i in range(len(bpm_values) - 1):
            if abs(bpm_values[i+1] - bpm_values[i]) > 20:
                large_jumps += 1

        jump_percentage = (large_jumps / (len(bpm_values) - 1)) * 100 if len(bpm_values) > 1 else 0

        # Energy progression score (0-1.0)
        # Lower variance and fewer jumps = higher score
        variance_score = max(0.0, 1.0 - (bpm_variance / 50))  # 50 stdev = 0 score
        jump_score = max(0.0, 1.0 - (jump_percentage / 25))  # 25% jumps = 0 score

        bpm_progression_coherence = (variance_score + jump_score) / 2
        energy_consistency = jump_score  # Energy consistency based on transition quality

        # Calculate genre diversity for flow metrics
        genre_distribution = playlist.calculate_genre_distribution()
        import math
        genre_entropy = 0.0
        for pct in genre_distribution.values():
            if pct > 0:
                genre_entropy -= pct * math.log2(pct)
        genre_diversity_index = min(1.0, genre_entropy / 2.32) if genre_entropy > 0 else 0.0

        flow_metrics = FlowQualityMetrics(
            bpm_variance=bpm_variance,
            bpm_progression_coherence=bpm_progression_coherence,
            energy_consistency=energy_consistency,
            genre_diversity_index=genre_diversity_index
        )

        # Overall BPM score - compliant if coherence >= 0.7
        is_compliant = bpm_progression_coherence >= 0.7

        # Deviation from perfect score (1.0)
        deviation_percentage = 1.0 - bpm_progression_coherence

        # Use average BPM as representative values
        avg_bpm = statistics.mean(bpm_values) if bpm_values else 0.0

        bpm_score = ConstraintScore(
            constraint_name="bpm_progression",
            target_value=1.0,  # Target is perfect coherence (1.0)
            actual_value=bpm_progression_coherence,
            tolerance=0.30,  # 30% tolerance (0.7 threshold)
            is_compliant=is_compliant,
            deviation_percentage=deviation_percentage
        )

        return bpm_score, flow_metrics


from datetime import datetime
