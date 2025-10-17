"""
Prompt building helpers for LLM track selection.

This module contains functions to build prompts for various scenarios
including initial selection and constraint relaxation.
"""

from typing import Dict, Tuple

from .models import LLMTrackSelectionRequest, TrackSelectionCriteria


def build_selection_prompt(request: LLMTrackSelectionRequest) -> str:
    """Build LLM prompt from request."""
    if request.prompt_template:
        return request.prompt_template

    # Build default prompt
    criteria = request.criteria

    # Build genre requirements string
    genre_requirements = "\n".join(
        f"- {genre}: {criteria_obj.target_percentage - criteria_obj.tolerance:.0%}-{criteria_obj.target_percentage + criteria_obj.tolerance:.0%}"
        for genre, criteria_obj in criteria.genre_mix.items()
    )

    # Build era requirements string
    era_requirements = "\n".join(
        f"- {era}: {criteria_obj.target_percentage - criteria_obj.tolerance:.0%}-{criteria_obj.target_percentage + criteria_obj.tolerance:.0%}"
        for era, criteria_obj in criteria.era_distribution.items()
    )

    # Get BPM range from bpm_ranges
    if criteria.bpm_ranges:
        bpm_min = min(r.bpm_min for r in criteria.bpm_ranges)
        bpm_max = max(r.bpm_max for r in criteria.bpm_ranges)
        bpm_range_str = f"{bpm_min}-{bpm_max} BPM"
    else:
        bpm_range_str = "No BPM constraints"

    # Get energy flow
    energy_flow = ", ".join(criteria.energy_flow_requirements) if criteria.energy_flow_requirements else "Natural flow"

    prompt = f"""Select tracks for a radio playlist matching these criteria:

**BPM Requirements:**
- Range: {bpm_range_str}
- Progression: {energy_flow}

**Genre Mix:**
{genre_requirements}

**Era Distribution:**
{era_requirements}

**Australian Content:**
- Minimum: {criteria.australian_content_min:.0%} of tracks MUST be from Australian artists

**Target:**
- {request.target_track_count} tracks
- Ordered for smooth energy flow and tempo transitions

**Instructions:**
1. Use search_tracks MCP tool to find candidates matching BPM and genre
2. Use get_genres to verify available genres
3. Use search_similar to find tracks with compatible musical characteristics
4. Ensure Australian content minimum is met
5. Order tracks for optimal energy progression and tempo transitions
6. Provide reasoning for each selection

**Output Format:**
Return a JSON object with:
- tracks: array of {request.target_track_count} tracks, each with: track_id, title, artist, album, bpm, genre, year, country, duration_seconds, selection_reason
- reasoning: overall selection strategy and rationale
"""

    return prompt


def build_relaxation_prompt(criteria: TrackSelectionCriteria, iteration: int) -> str:
    """Build prompt for constraint relaxation iteration."""
    relaxation_note = ""
    if iteration == 0:
        relaxation_note = "(Strict criteria)"
    elif iteration == 1:
        relaxation_note = "(BPM relaxed ±10)"
    elif iteration == 2:
        relaxation_note = "(BPM + Genre relaxed)"
    elif iteration == 3:
        relaxation_note = "(BPM + Genre + Era relaxed)"

    # Build genre requirements
    genre_requirements = "\n".join(
        f"- {genre}: {criteria_obj.target_percentage - criteria_obj.tolerance:.0%}-{criteria_obj.target_percentage + criteria_obj.tolerance:.0%}"
        for genre, criteria_obj in criteria.genre_mix.items()
    )

    # Build era requirements
    era_requirements = "\n".join(
        f"- {era}: {criteria_obj.target_percentage - criteria_obj.tolerance:.0%}-{criteria_obj.target_percentage + criteria_obj.tolerance:.0%}"
        for era, criteria_obj in criteria.era_distribution.items()
    )

    # Get BPM range from bpm_ranges
    if criteria.bpm_ranges:
        bpm_min = min(r.bpm_min for r in criteria.bpm_ranges)
        bpm_max = max(r.bpm_max for r in criteria.bpm_ranges)
        bpm_range_str = f"{bpm_min}-{bpm_max} BPM"
    else:
        bpm_range_str = "No BPM constraints"

    # Calculate tolerance based on iteration
    tolerance = 0 if iteration == 0 else 10

    prompt = f"""Select tracks for a radio playlist {relaxation_note}:

**BPM Requirements:**
- Range: {bpm_range_str}
- Tolerance: ±{tolerance} BPM

**Genre Mix:**
{genre_requirements}

**Era Distribution:**
{era_requirements}

**Australian Content (NON-NEGOTIABLE):**
- Minimum: {criteria.australian_content_min:.0%} of tracks MUST be from Australian artists

**Target:**
- 12 tracks
- Ordered for smooth energy flow and tempo transitions

Return JSON with tracks array and reasoning.
"""

    return prompt


def format_genre_requirements(genre_mix: Dict[str, Tuple[float, float]]) -> str:
    """Format genre mix requirements as string."""
    return "\n".join(
        f"- {genre}: {min_pct:.0%}-{max_pct:.0%}" for genre, (min_pct, max_pct) in genre_mix.items()
    )


def format_era_requirements(era_distribution: Dict[str, Tuple[float, float]]) -> str:
    """Format era distribution requirements as string."""
    return "\n".join(
        f"- {era}: {min_pct:.0%}-{max_pct:.0%}"
        for era, (min_pct, max_pct) in era_distribution.items()
    )
