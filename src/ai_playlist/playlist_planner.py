"""
Playlist Planner - Generates PlaylistSpec from DaypartSpec

Converts structured daypart specifications into concrete playlist specifications
with calculated durations, naming schema, and track selection criteria.
"""

from typing import List
from datetime import datetime, time
import uuid
import re

from .models import DaypartSpec, PlaylistSpec, TrackSelectionCriteria


def generate_playlist_specs(dayparts: List[DaypartSpec]) -> List[PlaylistSpec]:
    """
    Generate playlist specifications from daypart specifications.

    Args:
        dayparts: List of daypart specifications to convert

    Returns:
        List of playlist specifications ready for track selection

    Raises:
        ValueError: If dayparts list is empty or contains invalid specs
    """
    if not dayparts:
        raise ValueError("Dayparts list must not be empty")

    playlist_specs = []

    for daypart in dayparts:
        # Generate unique UUID for playlist
        playlist_id = str(uuid.uuid4())

        # Generate name using schema: {Day}_{ShowName}_{StartTime}_{EndTime}
        playlist_name = _generate_playlist_name(daypart)

        # Calculate target duration from time range
        target_duration = _calculate_duration_minutes(daypart.time_range)

        # Generate track selection criteria from daypart constraints
        track_criteria = _generate_track_criteria(daypart)

        # Create playlist spec
        playlist_spec = PlaylistSpec(
            id=playlist_id,
            name=playlist_name,
            daypart=daypart,
            target_duration_minutes=target_duration,
            track_criteria=track_criteria,
            created_at=datetime.now(),
        )

        playlist_specs.append(playlist_spec)

    return playlist_specs


def _generate_playlist_name(daypart: DaypartSpec) -> str:
    """
    Generate playlist name using schema: {Day}_{ShowName}_{StartTime}_{EndTime}

    Examples:
        "Monday_ProductionCall_0600_1000"
        "Saturday_TheSession_1400_1800"

    Args:
        daypart: Daypart specification with name, day, and time_range

    Returns:
        Formatted playlist name
    """
    # Convert show name to camelCase, remove spaces and special chars
    show_name = _to_camel_case(daypart.name)

    # Format times as HHMM (remove colon)
    start_time = daypart.time_range[0].replace(":", "")
    end_time = daypart.time_range[1].replace(":", "")

    return f"{daypart.day}_{show_name}_{start_time}_{end_time}"


def _to_camel_case(text: str) -> str:
    """
    Convert text to camelCase, removing spaces and special characters.

    Examples:
        "Production Call" -> "ProductionCall"
        "The Session" -> "TheSession"
        "Morning Show!" -> "MorningShow"

    Args:
        text: Input text to convert

    Returns:
        camelCase string with no spaces or special characters
    """
    # Remove special characters, keep only alphanumeric, spaces, and hyphens
    clean_text = re.sub(r"[^a-zA-Z0-9\s-]", "", text)

    # Split on spaces and hyphens, filter out empty strings
    words = [word for word in re.split(r"[\s-]+", clean_text) if word]

    # Capitalize first letter of each word, join without spaces
    camel_case = "".join(word.capitalize() for word in words)

    return camel_case


def _calculate_duration_minutes(time_range: tuple[str, str]) -> int:
    """
    Calculate duration in minutes from time range.

    Args:
        time_range: Tuple of (start_time, end_time) in "HH:MM" format

    Returns:
        Duration in minutes

    Examples:
        ("06:00", "10:00") -> 240 minutes
        ("14:00", "18:00") -> 240 minutes
    """
    start_str, end_str = time_range

    # Parse times
    start_hour, start_min = map(int, start_str.split(":"))
    end_hour, end_min = map(int, end_str.split(":"))

    # Convert to minutes since midnight
    start_minutes = start_hour * 60 + start_min
    end_minutes = end_hour * 60 + end_min

    # Calculate duration
    duration = end_minutes - start_minutes

    return duration


def _generate_track_criteria(daypart: DaypartSpec) -> TrackSelectionCriteria:
    """
    Generate track selection criteria from daypart constraints.

    Converts daypart specifications into criteria suitable for LLM track selection:
    - Genre percentages -> (min%, max%) ranges with ±5% tolerance
    - Era distributions -> (min%, max%) ranges with ±5% tolerance
    - BPM progression -> single range for the entire daypart
    - Sets BPM tolerance to 10
    - Preserves Australian minimum requirement
    - Copies energy flow from daypart mood

    Args:
        daypart: Daypart specification with constraints

    Returns:
        Track selection criteria ready for LLM
    """
    # Extract BPM range from progression (use overall min and max)
    bpm_values = []
    for bpm_min, bpm_max in daypart.bpm_progression.values():
        bpm_values.extend([bpm_min, bpm_max])

    overall_bpm_min = min(bpm_values)
    overall_bpm_max = max(bpm_values)
    bpm_range = (overall_bpm_min, overall_bpm_max)

    # Convert genre_mix percentages to (min%, max%) ranges with ±5% tolerance
    genre_mix_ranges = {}
    for genre, percentage in daypart.genre_mix.items():
        min_pct = max(0.0, percentage - 0.05)  # ±5% tolerance
        max_pct = min(1.0, percentage + 0.05)
        genre_mix_ranges[genre] = (min_pct, max_pct)

    # Convert era_distribution to (min%, max%) ranges with ±5% tolerance
    era_distribution_ranges = {}
    for era, percentage in daypart.era_distribution.items():
        min_pct = max(0.0, percentage - 0.05)  # ±5% tolerance
        max_pct = min(1.0, percentage + 0.05)
        era_distribution_ranges[era] = (min_pct, max_pct)

    # Create criteria
    criteria = TrackSelectionCriteria(
        bpm_range=bpm_range,
        bpm_tolerance=10,  # Set to 10 as specified
        genre_mix=genre_mix_ranges,
        genre_tolerance=0.05,  # Default 5%
        era_distribution=era_distribution_ranges,
        era_tolerance=0.05,  # Default 5%
        australian_min=daypart.australian_min,  # Preserve from daypart
        energy_flow=daypart.mood,  # Copy mood as energy flow
        excluded_track_ids=[],  # Start with empty exclusion list
    )

    return criteria
