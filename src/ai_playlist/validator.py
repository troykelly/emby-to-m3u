"""
Playlist Validator - Phase 1 Implementation (T020)

Validates generated playlists against quality standards as specified in:
/workspaces/emby-to-m3u/specs/004-build-ai-ml/contracts/validator_contract.md

Key validation thresholds:
- Constraint satisfaction: ≥ 0.80 (80%)
- Flow quality score: ≥ 0.70 (70%)
"""

from typing import List, Dict
from datetime import datetime
from src.ai_playlist.models import (
    SelectedTrack,
    TrackSelectionCriteria,
    ValidationResult,
)


def validate_playlist(
    tracks: List[SelectedTrack], criteria: TrackSelectionCriteria
) -> ValidationResult:
    """Validate generated playlist meets quality standards.

    Args:
        tracks: List of selected tracks in order
        criteria: Original selection criteria

    Returns:
        ValidationResult with satisfaction metrics and pass/fail status

    Raises:
        ValueError: If tracks list is empty

    Contract:
        - Calculates 4 constraint satisfaction metrics (BPM, genre, era, Australian)
        - Calculates flow quality based on BPM transitions
        - Passes if constraint_satisfaction ≥ 0.80 AND flow_quality ≥ 0.70
        - Generates gap_analysis for any unmet criteria
    """
    # Precondition: tracks must not be empty
    if not tracks or len(tracks) == 0:
        raise ValueError("Tracks list cannot be empty")

    # Calculate individual satisfaction metrics
    bpm_satisfaction = _calculate_bpm_satisfaction(tracks, criteria)
    genre_satisfaction = _calculate_genre_satisfaction(tracks, criteria)
    era_satisfaction = _calculate_era_satisfaction(tracks, criteria)
    australian_satisfaction = _calculate_australian_satisfaction(tracks, criteria)

    # Calculate overall constraint satisfaction (average of 4 metrics)
    constraint_satisfaction = (
        bpm_satisfaction + genre_satisfaction + era_satisfaction + australian_satisfaction
    ) / 4.0

    # Calculate flow quality metrics
    flow_quality_score, bpm_variance, energy_progression = _calculate_flow_quality(tracks)

    # Calculate genre diversity
    genre_diversity = _calculate_genre_diversity(tracks)

    # Calculate actual Australian content percentage
    australian_content = _calculate_australian_content(tracks)

    # Generate gap analysis for unmet criteria
    gap_analysis = _generate_gap_analysis(
        tracks,
        criteria,
        bpm_satisfaction,
        genre_satisfaction,
        era_satisfaction,
        australian_content,
    )

    # Determine if validation passes
    passes_validation = constraint_satisfaction >= 0.80 and flow_quality_score >= 0.70

    # Build ValidationResult with new API
    from .models.validation import ConstraintScore, FlowQualityMetrics, ValidationStatus

    # Convert legacy satisfaction scores to ConstraintScore objects
    constraint_score_dict = {
        'bpm_satisfaction': ConstraintScore(
            constraint_name="BPM Range",
            target_value=1.0,
            actual_value=bpm_satisfaction,
            tolerance=0.0,
            is_compliant=bpm_satisfaction >= 0.80,
            deviation_percentage=abs(1.0 - bpm_satisfaction)
        ),
        'genre_satisfaction': ConstraintScore(
            constraint_name="Genre Mix",
            target_value=1.0,
            actual_value=genre_satisfaction,
            tolerance=0.0,
            is_compliant=genre_satisfaction >= 0.80,
            deviation_percentage=abs(1.0 - genre_satisfaction)
        ),
        'era_satisfaction': ConstraintScore(
            constraint_name="Era Distribution",
            target_value=1.0,
            actual_value=era_satisfaction,
            tolerance=0.0,
            is_compliant=era_satisfaction >= 0.80,
            deviation_percentage=abs(1.0 - era_satisfaction)
        ),
        'australian_content': ConstraintScore(
            constraint_name="Australian Content",
            target_value=criteria.australian_content_min,
            actual_value=australian_content,
            tolerance=0.0,
            is_compliant=australian_content >= criteria.australian_content_min,
            deviation_percentage=abs(criteria.australian_content_min - australian_content) / criteria.australian_content_min if criteria.australian_content_min > 0 else 0.0
        ),
    }

    # Convert legacy flow metrics to FlowQualityMetrics
    flow_quality_metrics_obj = FlowQualityMetrics(
        bpm_variance=bpm_variance,
        bpm_progression_coherence=flow_quality_score,  # Using flow_quality_score as coherence
        energy_consistency=0.85 if energy_progression == "smooth" else 0.5 if energy_progression == "moderate" else 0.3,
        genre_diversity_index=genre_diversity
    )

    # Convert gap_analysis dict to list of strings
    gap_analysis_list = [f"{key}: {value}" for key, value in gap_analysis.items()]

    # Calculate overall compliance percentage
    compliant_count = sum(1 for score in constraint_score_dict.values() if score.is_compliant)
    compliance_pct = compliant_count / len(constraint_score_dict)

    # Determine overall status
    if passes_validation:
        overall_status = ValidationStatus.PASS
    elif compliance_pct >= 0.50:
        overall_status = ValidationStatus.WARNING
    else:
        overall_status = ValidationStatus.FAIL

    return ValidationResult(
        playlist_id="generated_playlist",  # Default ID for generated playlists
        overall_status=overall_status,
        constraint_scores=constraint_score_dict,
        flow_quality_metrics=flow_quality_metrics_obj,
        compliance_percentage=compliance_pct,
        validated_at=datetime.now(),
        gap_analysis=gap_analysis_list,
    )


def _calculate_bpm_satisfaction(
    tracks: List[SelectedTrack], criteria: TrackSelectionCriteria
) -> float:
    """Calculate percentage of tracks within BPM range.

    Formula: tracks_in_range / total_tracks
    """
    # Get overall BPM range from all BPM ranges in criteria
    if not criteria.bpm_ranges:
        return 1.0  # No BPM requirements

    bpm_min = min(r.bpm_min for r in criteria.bpm_ranges)
    bpm_max = max(r.bpm_max for r in criteria.bpm_ranges)

    in_range_count = sum(
        1 for track in tracks if track.bpm is not None and bpm_min <= track.bpm <= bpm_max
    )

    return in_range_count / len(tracks)


def _calculate_genre_satisfaction(
    tracks: List[SelectedTrack], criteria: TrackSelectionCriteria
) -> float:
    """Calculate percentage of genre requirements met.

    Formula: genres_meeting_requirements / total_genres

    A genre meets requirements if actual percentage is within [min, max] range.
    """
    if not criteria.genre_mix:
        return 1.0  # No genre requirements

    total_tracks = len(tracks)
    genre_matches = 0

    for genre, criteria_obj in criteria.genre_mix.items():
        # Count tracks in this genre
        genre_count = sum(1 for track in tracks if track.genre == genre)
        actual_pct = genre_count / total_tracks

        # Check if within required range
        min_pct = criteria_obj.min_percentage
        max_pct = criteria_obj.max_percentage
        if min_pct <= actual_pct <= max_pct:
            genre_matches += 1

    return genre_matches / len(criteria.genre_mix)


def _calculate_era_satisfaction(
    tracks: List[SelectedTrack], criteria: TrackSelectionCriteria
) -> float:
    """Calculate percentage of era requirements met.

    Formula: eras_meeting_requirements / total_eras

    Era definitions:
    - Current: Last 2 years (2023+)
    - Recent: 3-10 years ago (2015-2022)
    - Classic: >10 years ago (<2015)
    """
    if not criteria.era_distribution:
        return 1.0  # No era requirements

    current_year = datetime.now().year
    total_tracks = len(tracks)
    era_matches = 0

    # Categorize tracks by era
    era_counts = {
        "Current": 0,
        "Recent": 0,
        "Classic": 0,
    }

    for track in tracks:
        if track.year is None:
            continue

        if track.year >= current_year - 2:
            era_counts["Current"] += 1
        elif track.year >= current_year - 10:
            era_counts["Recent"] += 1
        else:
            era_counts["Classic"] += 1

    # Check each required era
    for era, criteria_obj in criteria.era_distribution.items():
        actual_pct = era_counts.get(era, 0) / total_tracks

        min_pct = criteria_obj.min_percentage
        max_pct = criteria_obj.max_percentage
        if min_pct <= actual_pct <= max_pct:
            era_matches += 1

    return era_matches / len(criteria.era_distribution)


def _calculate_australian_satisfaction(
    tracks: List[SelectedTrack], criteria: TrackSelectionCriteria
) -> float:
    """Calculate Australian content satisfaction.

    Formula: min(australian_content / australian_content_min, 1.0)

    Returns 1.0 if requirement is met or exceeded, proportional value if not.
    """
    australian_content = _calculate_australian_content(tracks)

    if criteria.australian_content_min == 0:
        return 1.0  # No Australian content requirement

    # Satisfaction is ratio of actual to required, capped at 1.0
    return min(australian_content / criteria.australian_content_min, 1.0)


def _calculate_australian_content(tracks: List[SelectedTrack]) -> float:
    """Calculate actual Australian content percentage.

    Formula: australian_tracks / total_tracks
    """
    australian_count = sum(1 for track in tracks if track.country and track.country.upper() == "AU")

    return australian_count / len(tracks)


def _calculate_flow_quality(tracks: List[SelectedTrack]) -> tuple[float, float, str]:
    """Calculate flow quality metrics based on BPM transitions.

    Returns:
        (flow_quality_score, avg_bpm_variance, energy_progression)

    Flow quality formula:
        - Calculate BPM changes between consecutive tracks
        - avg_bpm_variance = average of absolute BPM changes
        - flow_quality_score = max(0, 1.0 - (avg_bpm_variance / 50.0))

    Energy progression:
        - "smooth": avg_bpm_variance < 10
        - "choppy": avg_bpm_variance > 20
        - "moderate": otherwise
    """
    if len(tracks) < 2:
        # Single track has perfect flow
        return 1.0, 0.0, "smooth"

    # Calculate BPM changes between consecutive tracks
    bpm_changes = []
    for i in range(len(tracks) - 1):
        current_bpm = tracks[i].bpm or 0
        next_bpm = tracks[i + 1].bpm or 0

        if current_bpm > 0 and next_bpm > 0:
            bpm_changes.append(abs(next_bpm - current_bpm))

    if not bpm_changes:
        # No valid BPM data
        return 0.5, 0.0, "moderate"

    # Calculate average BPM variance
    avg_bpm_variance = sum(bpm_changes) / len(bpm_changes)

    # Calculate flow quality score (0.0 - 1.0)
    flow_quality_score = max(0.0, 1.0 - (avg_bpm_variance / 50.0))

    # Determine energy progression
    if avg_bpm_variance < 10:
        energy_progression = "smooth"
    elif avg_bpm_variance > 20:
        energy_progression = "choppy"
    else:
        energy_progression = "moderate"

    return flow_quality_score, avg_bpm_variance, energy_progression


def _calculate_genre_diversity(tracks: List[SelectedTrack]) -> float:
    """Calculate genre diversity (Simpson's diversity index).

    Formula: 1 - sum((count_i / total)^2)

    Returns 0.0 for single genre, approaches 1.0 for high diversity.
    """
    if not tracks:
        return 0.0

    # Count genres
    genre_counts: Dict[str, int] = {}
    for track in tracks:
        if track.genre:
            genre_counts[track.genre] = genre_counts.get(track.genre, 0) + 1

    if not genre_counts:
        return 0.0

    total = len(tracks)

    # Simpson's diversity index: 1 - sum((n_i / N)^2)
    diversity = 1.0 - sum((count / total) ** 2 for count in genre_counts.values())

    return diversity


def _generate_gap_analysis(
    tracks: List[SelectedTrack],
    criteria: TrackSelectionCriteria,
    bpm_satisfaction: float,
    genre_satisfaction: float,
    era_satisfaction: float,
    australian_content: float,
) -> Dict[str, str]:
    """Generate gap analysis for unmet criteria.

    Returns dict with criterion -> explanation for each unmet requirement.
    """
    gap_analysis: Dict[str, str] = {}

    # Check BPM range
    if bpm_satisfaction < 1.0 and criteria.bpm_ranges:
        bpm_min = min(r.bpm_min for r in criteria.bpm_ranges)
        bpm_max = max(r.bpm_max for r in criteria.bpm_ranges)
        out_of_range = [
            f"{track.title} ({track.bpm} BPM)"
            for track in tracks
            if track.bpm is not None and not bpm_min <= track.bpm <= bpm_max
        ]
        gap_analysis["bpm_range"] = (
            f"{len(out_of_range)} tracks out of range {bpm_min}-{bpm_max}: "
            f"{', '.join(out_of_range[:3])}"
        )

    # Check genre mix
    if genre_satisfaction < 1.0:
        genre_issues = []
        total_tracks = len(tracks)

        for genre, criteria_obj in criteria.genre_mix.items():
            genre_count = sum(1 for track in tracks if track.genre == genre)
            actual_pct = genre_count / total_tracks

            min_pct = criteria_obj.min_percentage
            max_pct = criteria_obj.max_percentage
            if not min_pct <= actual_pct <= max_pct:
                genre_issues.append(
                    f"{genre} {actual_pct*100:.0f}% "
                    f"(target: {min_pct*100:.0f}-{max_pct*100:.0f}%)"
                )

        if genre_issues:
            gap_analysis["genre_mix"] = ", ".join(genre_issues)

    # Check era distribution
    if era_satisfaction < 1.0:
        current_year = datetime.now().year
        total_tracks = len(tracks)
        era_issues = []

        # Count tracks by era
        era_counts = {
            "Current": sum(1 for t in tracks if t.year and t.year >= current_year - 2),
            "Recent": sum(
                1 for t in tracks if t.year and current_year - 10 <= t.year < current_year - 2
            ),
            "Classic": sum(1 for t in tracks if t.year and t.year < current_year - 10),
        }

        for era, criteria_obj in criteria.era_distribution.items():
            actual_pct = era_counts.get(era, 0) / total_tracks

            min_pct = criteria_obj.min_percentage
            max_pct = criteria_obj.max_percentage
            if not min_pct <= actual_pct <= max_pct:
                era_issues.append(
                    f"{era} era {actual_pct*100:.0f}% "
                    f"(target: {min_pct*100:.0f}-{max_pct*100:.0f}%)"
                )

        if era_issues:
            gap_analysis["era_distribution"] = ", ".join(era_issues)

    # Check Australian content
    if australian_content < criteria.australian_content_min:
        gap_analysis["australian_content"] = (
            f"Australian content {australian_content*100:.0f}% "
            f"(minimum: {criteria.australian_content_min*100:.0f}%)"
        )

    return gap_analysis
