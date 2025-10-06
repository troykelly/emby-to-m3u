"""
Core data models for AI Playlist - Programming documents and specifications.

This module contains the fundamental dataclasses for programming documents,
daypart specifications, playlist specifications, and track selection criteria.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Tuple
import uuid
import re

from ._validation_helpers import validate_playlist_name


@dataclass
class ProgrammingDocument:
    """Represents parsed plain-language radio programming strategy."""

    content: str
    dayparts: List["DaypartSpec"]
    metadata: Dict[str, str]

    def __post_init__(self) -> None:
        """Validate programming document constraints."""
        if not self.content or not self.content.strip():
            raise ValueError("Content must not be empty")

        if not self.dayparts or len(self.dayparts) == 0:
            raise ValueError("Must contain at least one valid daypart")

        # Validate no overlapping time ranges
        time_ranges = []
        for daypart in self.dayparts:
            if daypart.day not in [
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
                "Sunday",
            ]:
                raise ValueError(f"Invalid day: {daypart.day}")
            time_ranges.append((daypart.day, daypart.time_range))

        # Check for overlaps on same day
        for i, (day1, (start1, end1)) in enumerate(time_ranges):
            for day2, (start2, end2) in time_ranges[i + 1 :]:
                if day1 == day2:
                    if not (end1 <= start2 or end2 <= start1):
                        overlap_msg = (
                            f"Overlapping time ranges on {day1}: "
                            f"{start1}-{end1} and {start2}-{end2}"
                        )
                        raise ValueError(overlap_msg)


@dataclass
class DaypartSpec:
    """Structured specification for a radio programming time block."""

    name: str
    day: str
    time_range: Tuple[str, str]
    bpm_progression: Dict[str, Tuple[int, int]]
    genre_mix: Dict[str, float]
    era_distribution: Dict[str, float]
    australian_min: float
    mood: str
    tracks_per_hour: int

    def __post_init__(self) -> None:
        """Validate daypart specification constraints."""
        # Name validation
        if not self.name or len(self.name) > 100:
            raise ValueError("Name must be non-empty and max 100 chars")

        # Day validation
        valid_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        if self.day not in valid_days:
            raise ValueError(f"Day must be one of {valid_days}")

        # Time range validation (24-hour format HH:MM)
        time_pattern = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
        start, end = self.time_range
        if not time_pattern.match(start) or not time_pattern.match(end):
            raise ValueError("Time range must be in HH:MM 24-hour format")
        if start >= end:
            raise ValueError("Start time must be before end time")

        # BPM progression validation
        for _, (bpm_min, bpm_max) in self.bpm_progression.items():
            if bpm_min <= 0 or bpm_max <= 0:
                raise ValueError("BPM values must be > 0")
            if bpm_min > bpm_max:
                raise ValueError(f"Invalid BPM range: {bpm_min}-{bpm_max}")

        # Genre mix validation
        if sum(self.genre_mix.values()) > 1.0:
            raise ValueError("Genre mix percentages must sum to ≤ 1.0")
        for genre, pct in self.genre_mix.items():
            if not 0.0 <= pct <= 1.0:
                raise ValueError(f"Genre {genre} percentage must be 0.0-1.0")

        # Era distribution validation
        if sum(self.era_distribution.values()) > 1.0:
            raise ValueError("Era distribution percentages must sum to ≤ 1.0")
        for era, pct in self.era_distribution.items():
            if not 0.0 <= pct <= 1.0:
                raise ValueError(f"Era {era} percentage must be 0.0-1.0")

        # Australian minimum validation
        if not 0.0 <= self.australian_min <= 1.0:
            raise ValueError("Australian minimum must be 0.0-1.0")

        # Mood validation
        if not self.mood or len(self.mood) > 200:
            raise ValueError("Mood must be non-empty and max 200 chars")

        # Tracks per hour validation
        if self.tracks_per_hour <= 0:
            raise ValueError("Tracks per hour must be > 0")


@dataclass
class PlaylistSpec:
    """Generated playlist specification ready for track selection."""

    id: str
    name: str
    daypart: DaypartSpec
    target_duration_minutes: int
    track_criteria: "TrackSelectionCriteria"
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        """Validate playlist specification constraints."""
        # ID validation (UUID4)
        try:
            uuid.UUID(self.id, version=4)
        except ValueError as exc:
            raise ValueError("ID must be valid UUID4") from exc

        # Name validation (schema: {Day}_{ShowName}_{StartTime}_{EndTime})
        validate_playlist_name(self.name)

        # Duration validation
        if self.target_duration_minutes <= 0:
            raise ValueError("Target duration must be > 0")

        # Created at validation
        if self.created_at > datetime.now():
            raise ValueError("Created at cannot be in future")


@dataclass
class TrackSelectionCriteria:
    """Multi-dimensional constraint set for LLM track selection."""

    bpm_range: Tuple[int, int]
    bpm_tolerance: int = 10
    genre_mix: Dict[str, Tuple[float, float]] = field(default_factory=dict)
    genre_tolerance: float = 0.05
    era_distribution: Dict[str, Tuple[float, float]] = field(default_factory=dict)
    era_tolerance: float = 0.05
    australian_min: float = 0.30
    energy_flow: str = ""
    excluded_track_ids: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate track selection criteria constraints."""
        # BPM range validation
        bpm_min, bpm_max = self.bpm_range
        if bpm_min <= 0 or bpm_max <= 0:
            raise ValueError("BPM range values must be > 0")
        if bpm_min >= bpm_max:
            raise ValueError("BPM min must be < BPM max")
        if bpm_max > 300:
            raise ValueError("BPM values must be ≤ 300")

        # BPM tolerance validation
        if self.bpm_tolerance <= 0 or self.bpm_tolerance > 50:
            raise ValueError("BPM tolerance must be > 0 and ≤ 50")

        # Genre mix validation
        min_sum = sum(min_pct for min_pct, _ in self.genre_mix.values())
        if min_sum > 1.0:
            raise ValueError("Genre mix minimum percentages must sum to ≤ 1.0")
        for genre, (min_pct, max_pct) in self.genre_mix.items():
            if min_pct > max_pct:
                raise ValueError(f"Genre {genre}: min must be ≤ max")

        # Genre tolerance validation
        if not 0.0 <= self.genre_tolerance <= 0.20:
            raise ValueError("Genre tolerance must be 0.0-0.20")

        # Era distribution validation
        min_sum = sum(min_pct for min_pct, _ in self.era_distribution.values())
        if min_sum > 1.0:
            raise ValueError("Era distribution minimum percentages must sum to ≤ 1.0")
        for era, (min_pct, max_pct) in self.era_distribution.items():
            if min_pct > max_pct:
                raise ValueError(f"Era {era}: min must be ≤ max")

        # Era tolerance validation
        if not 0.0 <= self.era_tolerance <= 0.20:
            raise ValueError("Era tolerance must be 0.0-0.20")

        # Australian minimum validation
        if not 0.0 <= self.australian_min <= 1.0:
            raise ValueError("Australian minimum must be 0.0-1.0")

        # Energy flow validation
        if not self.energy_flow or len(self.energy_flow) > 500:
            raise ValueError("Energy flow must be non-empty and max 500 chars")

    def relax_bpm(self, increment: int = 10) -> "TrackSelectionCriteria":
        """Create relaxed criteria with expanded BPM range."""
        bpm_min, bpm_max = self.bpm_range
        return TrackSelectionCriteria(
            bpm_range=(max(0, bpm_min - increment), min(300, bpm_max + increment)),
            bpm_tolerance=self.bpm_tolerance,
            genre_mix=self.genre_mix.copy(),
            genre_tolerance=self.genre_tolerance,
            era_distribution=self.era_distribution.copy(),
            era_tolerance=self.era_tolerance,
            australian_min=self.australian_min,
            energy_flow=self.energy_flow,
            excluded_track_ids=self.excluded_track_ids.copy(),
        )

    def relax_genre(self, tolerance: float = 0.05) -> "TrackSelectionCriteria":
        """Create relaxed criteria with expanded genre tolerance."""
        relaxed_genre_mix = {
            genre: (max(0.0, min_pct - tolerance), min(1.0, max_pct + tolerance))
            for genre, (min_pct, max_pct) in self.genre_mix.items()
        }
        return TrackSelectionCriteria(
            bpm_range=self.bpm_range,
            bpm_tolerance=self.bpm_tolerance,
            genre_mix=relaxed_genre_mix,
            genre_tolerance=min(0.20, self.genre_tolerance + tolerance),
            era_distribution=self.era_distribution.copy(),
            era_tolerance=self.era_tolerance,
            australian_min=self.australian_min,
            energy_flow=self.energy_flow,
            excluded_track_ids=self.excluded_track_ids.copy(),
        )

    def relax_era(self, tolerance: float = 0.05) -> "TrackSelectionCriteria":
        """Create relaxed criteria with expanded era tolerance."""
        relaxed_era_dist = {
            era: (max(0.0, min_pct - tolerance), min(1.0, max_pct + tolerance))
            for era, (min_pct, max_pct) in self.era_distribution.items()
        }
        return TrackSelectionCriteria(
            bpm_range=self.bpm_range,
            bpm_tolerance=self.bpm_tolerance,
            genre_mix=self.genre_mix.copy(),
            genre_tolerance=self.genre_tolerance,
            era_distribution=relaxed_era_dist,
            era_tolerance=min(0.20, self.era_tolerance + tolerance),
            australian_min=self.australian_min,
            energy_flow=self.energy_flow,
            excluded_track_ids=self.excluded_track_ids.copy(),
        )
