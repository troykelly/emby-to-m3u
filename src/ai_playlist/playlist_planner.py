"""
Playlist Planner - Generates PlaylistSpec from DaypartSpec

Converts structured daypart specifications into concrete playlist specifications
with calculated durations, naming schema, and track selection criteria.
"""

from typing import List
from datetime import datetime, time, date
import uuid
import re

from .models import DaypartSpec, PlaylistSpec, TrackSelectionCriteria, GenreCriteria, EraCriteria, BPMRange


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

        # Calculate target track count from duration and tracks per hour
        min_tracks, max_tracks = _calculate_track_count(daypart, target_duration)

        # Create playlist spec using correct signature
        playlist_spec = PlaylistSpec(
            id=playlist_id,
            name=playlist_name,
            source_daypart_id=daypart.id if hasattr(daypart, 'id') else playlist_id,
            generation_date=date.today(),
            target_track_count_min=min_tracks,
            target_track_count_max=max_tracks,
            track_selection_criteria=track_criteria,
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


def _calculate_track_count(daypart: DaypartSpec, duration_minutes: int) -> tuple[int, int]:
    """
    Calculate target track count from daypart and duration.

    Args:
        daypart: Daypart specification with tracks_per_hour tuple
        duration_minutes: Duration in minutes

    Returns:
        Tuple of (min_tracks, max_tracks)
    """
    duration_hours = duration_minutes / 60.0

    # If daypart has tracks_per_hour, use it
    if hasattr(daypart, 'tracks_per_hour'):
        min_per_hour, max_per_hour = daypart.tracks_per_hour
        min_tracks = int(duration_hours * min_per_hour)
        max_tracks = int(duration_hours * max_per_hour)
    else:
        # Default to 12-15 tracks per hour
        min_tracks = int(duration_hours * 12)
        max_tracks = int(duration_hours * 15)

    return (min_tracks, max_tracks)


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
    - Genre percentages -> GenreCriteria objects with ±10% tolerance
    - Era distributions -> EraCriteria objects with year ranges and ±10% tolerance
    - BPM progression -> List of BPMRange objects
    - Preserves Australian minimum requirement
    - Copies energy flow from daypart mood

    Args:
        daypart: Daypart specification with constraints

    Returns:
        Track selection criteria ready for LLM
    """
    # Convert BPM progression to list of BPMRange objects
    bpm_ranges: List[BPMRange] = []

    if hasattr(daypart, 'bpm_progression') and isinstance(daypart.bpm_progression, list):
        # If already a list of BPMRange objects
        bpm_ranges = daypart.bpm_progression
    elif hasattr(daypart, 'bpm_progression') and isinstance(daypart.bpm_progression, dict):
        # Convert dict format to BPMRange list
        for time_label, (bpm_min, bpm_max) in daypart.bpm_progression.items():
            # Parse time from label or use defaults
            if isinstance(time_label, str) and '-' in time_label:
                start_str, end_str = time_label.split('-')
                start_time = time.fromisoformat(start_str.strip())
                end_time = time.fromisoformat(end_str.strip())
            else:
                # Default to full daypart range
                start_time = daypart.time_start if hasattr(daypart, 'time_start') else time(0, 0)
                end_time = daypart.time_end if hasattr(daypart, 'time_end') else time(23, 59)

            bpm_ranges.append(BPMRange(
                time_start=start_time,
                time_end=end_time,
                bpm_min=bpm_min,
                bpm_max=bpm_max
            ))

    # Convert genre_mix to GenreCriteria objects
    genre_mix: dict[str, GenreCriteria] = {}
    if hasattr(daypart, 'genre_mix'):
        for genre, percentage in daypart.genre_mix.items():
            genre_mix[genre] = GenreCriteria(
                target_percentage=percentage,
                tolerance=0.10  # ±10% tolerance
            )

    # Convert era_distribution to EraCriteria objects
    era_distribution: dict[str, EraCriteria] = {}
    current_year = datetime.now().year

    # Define era year ranges
    era_mapping = {
        "Current": (current_year - 2, current_year),
        "Recent": (current_year - 5, current_year - 2),
        "Modern Classics": (current_year - 10, current_year - 5),
        "Throwbacks": (current_year - 20, current_year - 10),
    }

    if hasattr(daypart, 'era_distribution'):
        for era, percentage in daypart.era_distribution.items():
            if era in era_mapping:
                min_year, max_year = era_mapping[era]
                era_distribution[era] = EraCriteria(
                    era_name=era,
                    min_year=min_year,
                    max_year=max_year,
                    target_percentage=percentage,
                    tolerance=0.10  # ±10% tolerance
                )

    # Extract Australian minimum
    australian_min = 0.30  # Default
    if hasattr(daypart, 'australian_min'):
        australian_min = daypart.australian_min

    # Extract energy flow from mood
    energy_flow = []
    if hasattr(daypart, 'mood'):
        if isinstance(daypart.mood, str):
            energy_flow = [daypart.mood]
        elif isinstance(daypart.mood, list):
            energy_flow = daypart.mood
    elif hasattr(daypart, 'mood_guidelines'):
        energy_flow = daypart.mood_guidelines

    # Extract rotation distribution
    rotation_dist = {}
    if hasattr(daypart, 'rotation_percentages'):
        rotation_dist = daypart.rotation_percentages

    # Calculate no-repeat window from duration
    no_repeat_hours = daypart.duration_hours if hasattr(daypart, 'duration_hours') else 4.0

    # Extract mood exclusions
    mood_exclude = []
    if hasattr(daypart, 'mood_exclusions'):
        mood_exclude = daypart.mood_exclusions

    # Create criteria with correct signature
    criteria = TrackSelectionCriteria(
        bpm_ranges=bpm_ranges,
        genre_mix=genre_mix,
        era_distribution=era_distribution,
        australian_content_min=australian_min,
        energy_flow_requirements=energy_flow,
        rotation_distribution=rotation_dist,
        no_repeat_window_hours=no_repeat_hours,
        tolerance_bpm=10,
        tolerance_genre_percent=0.10,
        tolerance_era_percent=0.10,
        mood_filters_include=[],
        mood_filters_exclude=mood_exclude,
        specialty_constraints=daypart.specialty_constraints if hasattr(daypart, 'specialty_constraints') else None
    )

    return criteria
