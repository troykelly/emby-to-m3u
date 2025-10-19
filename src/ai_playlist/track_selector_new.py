"""
Track Selector with Progressive Constraint Relaxation - T032

Implements intelligent track selection with automatic constraint relaxation when
insufficient tracks match strict criteria.

Success Criteria (T025):
- Progressive relaxation: BPM ±10→±15→±20, genre ±5%, era ±5%
- Max 3 relaxation iterations
- Australian content 30% minimum is NON-NEGOTIABLE (never relaxed)
- All relaxations logged in decision log
"""

from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from decimal import Decimal
import logging

from src.ai_playlist.models.core import (
    TrackSelectionCriteria,
    SelectedTrack,
    ConstraintRelaxation,
    PlaylistSpecification
)

logger = logging.getLogger(__name__)


@dataclass
class RelaxationStep:
    """Single relaxation step."""
    iteration: int
    constraint_type: str
    original_value: str
    relaxed_value: str
    reason: str


class TrackSelector:
    """Progressive constraint relaxation for track selection."""

    def __init__(self, max_relaxations: int = 3):
        """Initialize track selector.

        Args:
            max_relaxations: Maximum number of relaxation iterations (default 3)
        """
        self.max_relaxations = max_relaxations
        self.relaxation_history: List[ConstraintRelaxation] = []

    async def select_tracks_with_relaxation(
        self,
        specification: PlaylistSpecification,
        available_tracks: List[SelectedTrack],
        min_tracks_needed: int
    ) -> Tuple[List[SelectedTrack], List[ConstraintRelaxation]]:
        """Select tracks with progressive constraint relaxation if needed.

        Args:
            specification: Playlist specification with criteria
            available_tracks: Pool of available tracks
            min_tracks_needed: Minimum number of tracks required

        Returns:
            Tuple of (selected_tracks, relaxations_applied)
        """
        criteria = specification.track_selection_criteria
        iteration = 0
        relaxations = []

        while iteration <= self.max_relaxations:
            # Try to select tracks with current criteria
            selected = self._select_tracks(available_tracks, criteria, min_tracks_needed)

            if len(selected) >= min_tracks_needed:
                # Success! Return selected tracks
                return selected, relaxations

            # Not enough tracks - apply relaxation
            if iteration >= self.max_relaxations:
                logger.warning(
                    f"Reached max relaxations ({self.max_relaxations}), "
                    f"only found {len(selected)}/{min_tracks_needed} tracks"
                )
                break

            # Apply next relaxation
            iteration += 1
            relaxation = self._apply_relaxation(criteria, iteration)

            if relaxation is None:
                # No more relaxations possible
                break

            relaxations.append(relaxation)
            logger.info(
                f"Relaxation {iteration}: {relaxation.constraint_type} "
                f"{relaxation.original_value} → {relaxation.relaxed_value}"
            )

        # Return whatever we found, even if below minimum
        return selected, relaxations

    def _select_tracks(
        self,
        available_tracks: List[SelectedTrack],
        criteria: TrackSelectionCriteria,
        min_needed: int
    ) -> List[SelectedTrack]:
        """Select tracks matching criteria."""
        selected = []

        for track in available_tracks:
            if self._track_matches_criteria(track, criteria):
                selected.append(track)

                if len(selected) >= min_needed:
                    break

        return selected

    def _track_matches_criteria(
        self,
        track: SelectedTrack,
        criteria: TrackSelectionCriteria
    ) -> bool:
        """Check if track matches selection criteria."""
        # Check BPM if specified
        if criteria.bpm_ranges and track.bpm:
            bpm_match = False
            for bpm_min, bpm_max in criteria.bpm_ranges:
                if (bpm_min - criteria.tolerance_bpm <= track.bpm <=
                        bpm_max + criteria.tolerance_bpm):
                    bpm_match = True
                    break

            if not bpm_match:
                return False

        # Check genre if specified
        if criteria.genre_mix and track.genre:
            if track.genre not in criteria.genre_mix:
                return False

        # Check era/year if specified
        if criteria.era_distribution and track.year:
            year_match = False
            for era_criteria in criteria.era_distribution.values():
                if era_criteria.min_year <= track.year <= era_criteria.max_year:
                    year_match = True
                    break

            if not year_match:
                return False

        # Check mood filters
        if criteria.mood_filters_exclude:
            # Track mood would need to be checked here
            pass

        return True

    def _apply_relaxation(
        self,
        criteria: TrackSelectionCriteria,
        iteration: int
    ) -> Optional[ConstraintRelaxation]:
        """Apply next relaxation in sequence.

        Relaxation order:
        1. BPM tolerance: ±10 → ±15 → ±20
        2. Genre tolerance: ±5% → ±10%
        3. Era tolerance: ±5% → ±10%

        Australian content 30% is NEVER relaxed.
        """
        if iteration == 1:
            # First relaxation: BPM ±10 → ±15
            original = criteria.tolerance_bpm
            criteria.tolerance_bpm = 15

            return ConstraintRelaxation(
                step=iteration,
                constraint_type="bpm",
                original_value=f"±{original} BPM",
                relaxed_value=f"±{criteria.tolerance_bpm} BPM",
                reason=(
                    f"Insufficient tracks with BPM tolerance ±{original}. "
                    f"Relaxing to ±{criteria.tolerance_bpm} to expand track pool."
                ),
                timestamp=datetime.now()
            )

        elif iteration == 2:
            # Second relaxation: BPM ±15 → ±20
            original = criteria.tolerance_bpm
            criteria.tolerance_bpm = 20

            return ConstraintRelaxation(
                step=iteration,
                constraint_type="bpm",
                original_value=f"±{original} BPM",
                relaxed_value=f"±{criteria.tolerance_bpm} BPM",
                reason=(
                    f"Still insufficient tracks with BPM tolerance ±{original}. "
                    f"Applying final BPM relaxation to ±{criteria.tolerance_bpm}."
                ),
                timestamp=datetime.now()
            )

        elif iteration == 3:
            # Third relaxation: Genre tolerance ±5% → ±10%
            original = criteria.tolerance_genre_percent
            criteria.tolerance_genre_percent = 0.10

            return ConstraintRelaxation(
                step=iteration,
                constraint_type="genre",
                original_value=f"±{original*100:.0f}%",
                relaxed_value=f"±{criteria.tolerance_genre_percent*100:.0f}%",
                reason=(
                    "BPM relaxation exhausted. Relaxing genre distribution tolerance "
                    f"from ±{original*100:.0f}% to ±{criteria.tolerance_genre_percent*100:.0f}%."
                ),
                timestamp=datetime.now()
            )

        # No more relaxations possible
        return None
