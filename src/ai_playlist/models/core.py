"""
Core data models for AI/ML-Powered Playlist Generation.

This module contains the fundamental dataclasses that define the complete
data model for Production City Radio's AI/ML-powered playlist generation system.

Entities:
    - StationIdentityDocument: Authoritative programming guide with file locking
    - DaypartSpecification: Time-bound programming segments with musical requirements
    - PlaylistSpecification: Generated specification for playlist creation
    - TrackSelectionCriteria: Complete constraints for AI/ML track selection
    - SelectedTrack: Individual track chosen by AI/ML
    - Playlist: Complete generated playlist with validation
    - ConstraintRelaxation: Record of progressive constraint relaxation
"""

from dataclasses import dataclass, field
from datetime import datetime, date, time
from decimal import Decimal
from typing import Optional, List, Dict, Tuple, Any
from pathlib import Path
from enum import Enum
import hashlib
import uuid
import math
import statistics


# ============================================================================
# Enumerations
# ============================================================================


class ScheduleType(Enum):
    """Day-of-week schedule type for programming structures."""
    WEEKDAY = "weekday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


class ValidationStatus(Enum):
    """Validation status for tracks and playlists."""
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"


class DecisionType(Enum):
    """Type of decision in audit log."""
    TRACK_SELECTION = "track_selection"
    VALIDATION = "validation"
    ERROR = "error"
    RELAXATION = "relaxation"
    METADATA_RETRIEVAL = "metadata_retrieval"


# ============================================================================
# Supporting Dataclasses
# ============================================================================


@dataclass
class BPMRange:
    """BPM range for a time segment within daypart."""
    time_start: time
    time_end: time
    bpm_min: int
    bpm_max: int

    def validate(self) -> List[str]:
        """Validate BPM range constraints.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        if self.bpm_min >= self.bpm_max:
            errors.append(f"BPM min ({self.bpm_min}) must be < max ({self.bpm_max})")
        if not (60 <= self.bpm_min <= 200):
            errors.append(f"BPM min ({self.bpm_min}) outside valid range 60-200")
        if not (60 <= self.bpm_max <= 200):
            errors.append(f"BPM max ({self.bpm_max}) outside valid range 60-200")
        return errors


@dataclass
class SpecialtyConstraint:
    """Special programming constraint (e.g., 100% Australian)."""
    constraint_type: str  # "australian_only", "genre_only", "theme_based"
    description: str
    parameters: Dict[str, Any]


@dataclass
class GenreCriteria:
    """Genre selection criteria with tolerance."""
    target_percentage: float  # 0.0-1.0
    tolerance: float = 0.10  # ±10% default

    @property
    def min_percentage(self) -> float:
        """Minimum acceptable percentage."""
        return max(0.0, self.target_percentage - self.tolerance)

    @property
    def max_percentage(self) -> float:
        """Maximum acceptable percentage."""
        return min(1.0, self.target_percentage + self.tolerance)


@dataclass
class EraCriteria:
    """Era selection criteria with tolerance."""
    era_name: str  # "Current", "Recent", "Modern Classics", "Throwbacks"
    min_year: int  # Inclusive
    max_year: int  # Inclusive
    target_percentage: float  # 0.0-1.0
    tolerance: float = 0.10  # ±10% default

    @property
    def min_percentage(self) -> float:
        """Minimum acceptable percentage."""
        return max(0.0, self.target_percentage - self.tolerance)

    @property
    def max_percentage(self) -> float:
        """Maximum acceptable percentage."""
        return min(1.0, self.target_percentage + self.tolerance)


@dataclass
class ProgrammingStructure:
    """Weekly programming structure (Monday-Friday, Weekend)."""
    schedule_type: ScheduleType
    dayparts: List['DaypartSpecification']


@dataclass
class RotationCategory:
    """Rotation category definition."""
    name: str  # "Power", "Medium", "Light", "Recurrent", "Library"
    spins_per_week: int
    lifecycle_weeks: int


@dataclass
class RotationStrategy:
    """Station rotation strategy."""
    categories: Dict[str, RotationCategory]


@dataclass
class ContentRequirements:
    """Station-wide content requirements."""
    australian_content_min: float  # 0.30 minimum
    australian_content_target: float  # 0.30-0.35


@dataclass
class GenreDefinition:
    """Genre definition with metadata."""
    name: str
    description: str
    parent_genre: Optional[str]
    typical_bpm_range: Tuple[int, int]


# ============================================================================
# Core Entity: Station Identity Document
# ============================================================================


@dataclass
class StationIdentityDocument:
    """Station programming guide - single source of truth for playlist generation.

    This document contains all programming rules and is locked during generation
    to prevent concurrent modifications.

    Attributes:
        document_path: Path to station-identity.md file
        programming_structures: List of programming structures (Weekday/Weekend)
        rotation_strategy: Power/Medium/Light rotation definitions
        content_requirements: Australian content requirements
        genre_definitions: All genres with metadata
        version: SHA-256 hash of document content
        loaded_at: When document was parsed
        lock_id: Exclusive lock identifier during generation
        lock_timestamp: When lock was acquired
        locked_by: Process/session that holds lock
    """

    document_path: Path
    programming_structures: List[ProgrammingStructure]
    rotation_strategy: RotationStrategy
    content_requirements: ContentRequirements
    genre_definitions: List[GenreDefinition]
    version: str
    loaded_at: datetime
    lock_id: Optional[str] = None
    lock_timestamp: Optional[datetime] = None
    locked_by: Optional[str] = None

    @classmethod
    def from_file(cls, path: Path) -> 'StationIdentityDocument':
        """Load and parse station-identity.md file.

        Args:
            path: Path to station-identity.md

        Returns:
            Parsed StationIdentityDocument instance

        Note:
            Actual parsing logic would be implemented in document_parser module
        """
        with open(path, 'r') as f:
            content = f.read()

        version = hashlib.sha256(content.encode()).hexdigest()

        # Placeholder for actual parsing - would use document_parser
        programming_structures = []
        rotation_strategy = RotationStrategy(categories={})
        content_requirements = ContentRequirements(
            australian_content_min=0.30,
            australian_content_target=0.35
        )
        genre_definitions = []

        return cls(
            document_path=path,
            programming_structures=programming_structures,
            rotation_strategy=rotation_strategy,
            content_requirements=content_requirements,
            genre_definitions=genre_definitions,
            version=version,
            loaded_at=datetime.now()
        )

    def acquire_lock(self, session_id: str) -> bool:
        """Acquire exclusive lock on document.

        Args:
            session_id: Unique identifier for the session requesting lock

        Returns:
            True if lock acquired, False if already locked
        """
        if self.lock_id is not None:
            return False  # Already locked

        self.lock_id = str(uuid.uuid4())
        self.lock_timestamp = datetime.now()
        self.locked_by = session_id
        return True

    def release_lock(self) -> None:
        """Release lock on document."""
        self.lock_id = None
        self.lock_timestamp = None
        self.locked_by = None

    def validate(self) -> List[str]:
        """Validate document structure and content.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        if not self.programming_structures:
            errors.append("At least one programming structure required")

        if self.content_requirements.australian_content_min < 0.30:
            errors.append("Australian content minimum must be >= 30%")

        return errors


# ============================================================================
# Core Entity: Daypart Specification
# ============================================================================


@dataclass
class DaypartSpecification:
    """Time-bound programming segment with musical requirements.

    Represents a specific time block in the programming schedule with detailed
    requirements for BPM progression, genre mix, era distribution, and mood.

    Attributes:
        id: Unique identifier (UUID v4)
        name: Display name (e.g., "Morning Drive: Production Call")
        schedule_type: WEEKDAY, SATURDAY, or SUNDAY
        time_start: Start time (e.g., 06:00)
        time_end: End time (e.g., 10:00)
        duration_hours: Calculated duration in hours
        target_demographic: Target audience description
        bpm_progression: BPM ranges over daypart duration
        genre_mix: Genre → percentage mapping
        era_distribution: Era → percentage mapping
        mood_guidelines: Mood/energy descriptors
        content_focus: Programming content description
        rotation_percentages: Rotation category → % mapping
        tracks_per_hour: (min, max) tracks per hour
        mood_exclusions: Moods to avoid
        specialty_constraints: Special programming rules
    """

    id: str
    name: str
    schedule_type: ScheduleType
    time_start: time
    time_end: time
    duration_hours: float
    target_demographic: str
    bpm_progression: List[BPMRange]
    genre_mix: Dict[str, float]  # Genre name → percentage
    era_distribution: Dict[str, float]  # Era name → percentage
    mood_guidelines: List[str]
    content_focus: str
    rotation_percentages: Dict[str, float]  # Category → percentage
    tracks_per_hour: Tuple[int, int]  # (min, max)
    mood_exclusions: List[str] = field(default_factory=list)
    specialty_constraints: Optional[SpecialtyConstraint] = None

    def __hash__(self) -> int:
        """Make DaypartSpecification hashable based on ID."""
        return hash(self.id)

    def __eq__(self, other) -> bool:
        """Compare DaypartSpecification by ID."""
        if not isinstance(other, DaypartSpecification):
            return False
        return self.id == other.id

    def calculate_target_track_count(self) -> Tuple[int, int]:
        """Calculate min/max tracks needed for this daypart.

        Returns:
            Tuple of (min_tracks, max_tracks)
        """
        min_tracks = int(self.duration_hours * self.tracks_per_hour[0])
        max_tracks = int(self.duration_hours * self.tracks_per_hour[1])
        return (min_tracks, max_tracks)

    def get_bpm_range_at_time(self, at_time: time) -> Optional[BPMRange]:
        """Get BPM range for specific time within daypart.

        Args:
            at_time: Time to query

        Returns:
            BPMRange if found, None otherwise
        """
        for bpm_range in self.bpm_progression:
            if bpm_range.time_start <= at_time < bpm_range.time_end:
                return bpm_range
        return None

    def validate(self) -> List[str]:
        """Validate daypart specification.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Validate time range
        if self.time_end <= self.time_start:
            errors.append(f"End time ({self.time_end}) must be after start time ({self.time_start})")

        # Validate genre mix percentages
        genre_sum = sum(self.genre_mix.values())
        if not (0.99 <= genre_sum <= 1.01):
            errors.append(f"Genre mix percentages sum to {genre_sum:.2f}, must equal 1.0")

        # Validate era distribution
        era_sum = sum(self.era_distribution.values())
        if not (0.99 <= era_sum <= 1.01):
            errors.append(f"Era distribution percentages sum to {era_sum:.2f}, must equal 1.0")

        # Validate BPM progression
        for bpm_range in self.bpm_progression:
            errors.extend(bpm_range.validate())

        # Validate tracks per hour
        if self.tracks_per_hour[0] <= 0:
            errors.append("Minimum tracks per hour must be > 0")
        if self.tracks_per_hour[1] < self.tracks_per_hour[0]:
            errors.append("Maximum tracks per hour must be >= minimum")

        return errors


# ============================================================================
# Core Entity: Track Selection Criteria
# ============================================================================


@dataclass
class TrackSelectionCriteria:
    """Complete set of constraints for AI/ML track selection.

    Derived from daypart specification, contains all selection constraints
    with tolerances for progressive relaxation.

    Attributes:
        bpm_ranges: BPM requirements over time
        genre_mix: Genre → criteria mapping
        era_distribution: Era → criteria mapping
        australian_content_min: Minimum Australian % (0.30-1.0)
        energy_flow_requirements: Energy progression descriptors
        rotation_distribution: Rotation category → % mapping
        no_repeat_window_hours: Hours before track can repeat
        tolerance_bpm: BPM tolerance in progressive relaxation
        tolerance_genre_percent: Genre % tolerance
        tolerance_era_percent: Era % tolerance
        mood_filters_include: Required moods
        mood_filters_exclude: Excluded moods
        specialty_constraints: Special rules
    """

    bpm_ranges: List[BPMRange]
    genre_mix: Dict[str, GenreCriteria]
    era_distribution: Dict[str, EraCriteria]
    australian_content_min: float
    energy_flow_requirements: List[str]
    rotation_distribution: Dict[str, float]
    no_repeat_window_hours: float
    tolerance_bpm: int = 10
    tolerance_genre_percent: float = 0.10
    tolerance_era_percent: float = 0.10
    mood_filters_include: List[str] = field(default_factory=list)
    mood_filters_exclude: List[str] = field(default_factory=list)
    excluded_track_ids: List[str] = field(default_factory=list)
    specialty_constraints: Optional[SpecialtyConstraint] = None

    @classmethod
    def from_daypart(cls, daypart: DaypartSpecification) -> 'TrackSelectionCriteria':
        """Create selection criteria from daypart specification.

        Args:
            daypart: Source daypart specification

        Returns:
            TrackSelectionCriteria instance
        """
        # Convert genre mix to GenreCriteria
        # Handle both float and GenreCriteria types (for backward compatibility)
        genre_mix = {}
        for genre, value in daypart.genre_mix.items():
            # Use duck typing to check if it's already a GenreCriteria
            if hasattr(value, '__dataclass_fields__') and 'target_percentage' in value.__dataclass_fields__:
                # Already a GenreCriteria object
                genre_mix[genre] = value
            elif isinstance(value, float):
                # Convert float percentage to GenreCriteria
                genre_mix[genre] = GenreCriteria(target_percentage=value)
            else:
                # It's already a GenreCriteria but from different module load
                # Just copy its attributes
                genre_mix[genre] = GenreCriteria(
                    target_percentage=value.target_percentage,
                    tolerance=value.tolerance
                )

        # Convert era distribution to EraCriteria
        current_year = datetime.now().year

        # Default era mapping (can be overridden by custom era names)
        default_era_mapping = {
            "Current": (current_year - 2, current_year),
            "Recent": (current_year - 5, current_year - 2),
            "Modern Classics": (current_year - 10, current_year - 5),
            "Throwbacks": (current_year - 20, current_year - 10),
            "Strategic Throwbacks": (current_year - 20, current_year - 10),  # Alias for Throwbacks
        }

        era_distribution = {}
        for era, value in daypart.era_distribution.items():
            # Handle both float and EraCriteria types
            if isinstance(value, EraCriteria):
                # Already an EraCriteria object
                era_distribution[era] = value
            else:
                # Convert float percentage to EraCriteria
                # Use default mapping if available, otherwise infer reasonable range
                if era in default_era_mapping:
                    min_year, max_year = default_era_mapping[era]
                else:
                    # For unknown eras, use a wide range (last 20 years)
                    min_year = current_year - 20
                    max_year = current_year
                    logger.warning(
                        f"Unknown era '{era}' - using default range {min_year}-{max_year}"
                    )

                era_distribution[era] = EraCriteria(
                    era_name=era,
                    min_year=min_year,
                    max_year=max_year,
                    target_percentage=value
                )

        return cls(
            bpm_ranges=daypart.bpm_progression,
            genre_mix=genre_mix,
            era_distribution=era_distribution,
            australian_content_min=0.30,  # From content requirements
            energy_flow_requirements=daypart.mood_guidelines,
            rotation_distribution=daypart.rotation_percentages,
            no_repeat_window_hours=daypart.duration_hours,
            mood_filters_include=[],
            mood_filters_exclude=daypart.mood_exclusions,
            specialty_constraints=daypart.specialty_constraints
        )

    def validate(self) -> List[str]:
        """Validate criteria.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        if not (0.30 <= self.australian_content_min <= 1.0):
            errors.append(f"Australian content minimum ({self.australian_content_min}) must be 0.30-1.0")

        if self.no_repeat_window_hours < 0:
            errors.append("No-repeat window must be >= 0 hours")

        # Validate genre mix
        genre_sum = sum(gc.target_percentage for gc in self.genre_mix.values())
        if not (0.99 <= genre_sum <= 1.01):
            errors.append(f"Genre criteria percentages sum to {genre_sum:.2f}, must equal 1.0")

        # Validate era distribution
        era_sum = sum(ec.target_percentage for ec in self.era_distribution.values())
        if not (0.99 <= era_sum <= 1.01):
            errors.append(f"Era criteria percentages sum to {era_sum:.2f}, must equal 1.0")

        return errors


# ============================================================================
# Core Entity: Playlist Specification
# ============================================================================


@dataclass
class PlaylistSpecification:
    """Generated specification for playlist creation.

    Created from a daypart specification for a specific date, contains
    all information needed to generate a playlist.

    Attributes:
        id: Unique identifier (UUID v4)
        name: Generated playlist name (daypart + date)
        source_daypart_id: Reference to source daypart
        generation_date: Date this playlist is for
        target_track_count_min: Minimum tracks needed
        target_track_count_max: Maximum tracks needed
        target_duration_minutes: Required daypart duration in minutes
        track_selection_criteria: All selection constraints
        created_at: When specification was created
        cost_budget_allocated: Allocated cost budget
    """

    id: str
    name: str
    source_daypart_id: str
    generation_date: date
    target_track_count_min: int
    target_track_count_max: int
    target_duration_minutes: int  # NEW: Required daypart duration
    track_selection_criteria: TrackSelectionCriteria
    created_at: datetime
    cost_budget_allocated: Optional[Decimal] = None

    @classmethod
    def from_daypart(
        cls,
        daypart: DaypartSpecification,
        generation_date: date,
        cost_budget: Optional[Decimal] = None
    ) -> 'PlaylistSpecification':
        """Create playlist specification from daypart.

        Args:
            daypart: Source daypart specification
            generation_date: Date to generate playlist for
            cost_budget: Optional cost budget allocation

        Returns:
            PlaylistSpecification instance
        """
        min_tracks, max_tracks = daypart.calculate_target_track_count()

        name = f"{daypart.name} - {generation_date.isoformat()}"

        criteria = TrackSelectionCriteria.from_daypart(daypart)

        # Calculate duration in minutes from daypart's duration_hours
        duration_minutes = int(daypart.duration_hours * 60)

        return cls(
            id=str(uuid.uuid4()),
            name=name,
            source_daypart_id=daypart.id,
            generation_date=generation_date,
            target_track_count_min=min_tracks,
            target_track_count_max=max_tracks,
            target_duration_minutes=duration_minutes,  # NEW
            track_selection_criteria=criteria,
            created_at=datetime.now(),
            cost_budget_allocated=cost_budget
        )

    def validate(self) -> List[str]:
        """Validate playlist specification.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        if self.target_track_count_min <= 0:
            errors.append("Minimum track count must be > 0")

        if self.target_track_count_max < self.target_track_count_min:
            errors.append("Maximum track count must be >= minimum")

        if self.cost_budget_allocated is not None and self.cost_budget_allocated <= 0:
            errors.append("Cost budget must be > 0 if set")

        errors.extend(self.track_selection_criteria.validate())

        return errors


# ============================================================================
# Core Entity: Selected Track
# ============================================================================


@dataclass
class SelectedTrack:
    """Track selected by AI/ML for playlist inclusion.

    Represents an individual track chosen during generation with all metadata,
    validation status, and selection reasoning.

    Attributes:
        track_id: Subsonic/Emby track identifier
        title: Track title
        artist: Artist name
        album: Album name
        duration_seconds: Track duration
        is_australian: Whether artist is Australian
        rotation_category: Power/Medium/Light/Recurrent/Library
        position_in_playlist: 0-indexed position
        selection_reasoning: AI explanation for selection
        validation_status: Pass/Fail/Warning
        metadata_source: Where metadata came from
        bpm: Beats per minute
        genre: Primary genre
        year: Release year
        country: Artist country (ISO 3166-1)
        validation_notes: Validation issues if any
    """

    track_id: str
    title: str
    artist: str
    album: str
    duration_seconds: int
    is_australian: bool
    rotation_category: str
    position_in_playlist: int
    selection_reasoning: str
    validation_status: ValidationStatus
    metadata_source: str
    bpm: Optional[int] = None
    genre: Optional[str] = None
    year: Optional[int] = None
    country: Optional[str] = None
    validation_notes: List[str] = field(default_factory=list)

    def validate_against_criteria(
        self,
        criteria: TrackSelectionCriteria,
        playlist_time: time
    ) -> ValidationStatus:
        """Validate track against selection criteria.

        Args:
            criteria: Track selection criteria to validate against
            playlist_time: Time in playlist for BPM validation

        Returns:
            ValidationStatus enum value
        """
        issues = []

        # Validate BPM if available
        if self.bpm is not None:
            bpm_range = None
            for br in criteria.bpm_ranges:
                if br.time_start <= playlist_time < br.time_end:
                    bpm_range = br
                    break

            if bpm_range:
                if not (bpm_range.bpm_min <= self.bpm <= bpm_range.bpm_max):
                    issues.append(
                        f"BPM {self.bpm} outside range {bpm_range.bpm_min}-{bpm_range.bpm_max}"
                    )
        else:
            issues.append("BPM metadata missing")

        # Validate genre
        if self.genre is None:
            issues.append("Genre metadata missing")
        elif self.genre not in criteria.genre_mix:
            issues.append(f"Genre '{self.genre}' not in criteria")

        # Validate year/era
        if self.year is None:
            issues.append("Year metadata missing")
        else:
            in_valid_era = False
            for era_criteria in criteria.era_distribution.values():
                if era_criteria.min_year <= self.year <= era_criteria.max_year:
                    in_valid_era = True
                    break
            if not in_valid_era:
                issues.append(f"Year {self.year} not in any valid era range")

        # Check mood exclusions
        for excluded_mood in criteria.mood_filters_exclude:
            if excluded_mood.lower() in self.selection_reasoning.lower():
                issues.append(f"Contains excluded mood: {excluded_mood}")

        self.validation_notes = issues

        if not issues:
            self.validation_status = ValidationStatus.PASS
        elif len(issues) >= 3:
            self.validation_status = ValidationStatus.FAIL
        else:
            self.validation_status = ValidationStatus.WARNING

        return self.validation_status

    def to_m3u_entry(self) -> str:
        """Convert to M3U playlist entry.

        Returns:
            M3U format entry string
        """
        return f"#EXTINF:{self.duration_seconds},{self.artist} - {self.title}\n{self.track_id}"


# ============================================================================
# Core Entity: Constraint Relaxation
# ============================================================================


@dataclass
class ConstraintRelaxation:
    """Record of progressive constraint relaxation.

    Tracks when and why constraints were relaxed during generation.

    Attributes:
        step: Relaxation step number
        constraint_type: Type of constraint relaxed (bpm/genre/era)
        original_value: Original constraint value
        relaxed_value: Relaxed constraint value
        reason: Reason for relaxation
        timestamp: When relaxation occurred
    """
    step: int
    constraint_type: str  # "bpm", "genre", "era"
    original_value: str
    relaxed_value: str
    reason: str
    timestamp: datetime


# ============================================================================
# Core Entity: Playlist
# ============================================================================


@dataclass
class Playlist:
    """Complete generated playlist.

    Contains all selected tracks, validation results, and generation metadata.

    Attributes:
        id: Unique identifier (UUID v4)
        name: Playlist name
        specification_id: Reference to specification
        tracks: All selected tracks in order
        validation_result: Compliance assessment
        created_at: When playlist was generated
        cost_actual: Actual LLM API cost
        generation_time_seconds: Time to generate
        constraint_relaxations: Progressive relaxations applied
    """

    id: str
    name: str
    specification_id: str
    tracks: List[SelectedTrack]
    validation_result: Optional['ValidationResult']
    created_at: datetime
    cost_actual: Decimal
    generation_time_seconds: float
    constraint_relaxations: List[ConstraintRelaxation] = field(default_factory=list)

    @classmethod
    def create(cls, specification: PlaylistSpecification) -> 'Playlist':
        """Initialize new playlist from specification.

        Args:
            specification: Playlist specification

        Returns:
            New Playlist instance
        """
        return cls(
            id=str(uuid.uuid4()),
            name=specification.name,
            specification_id=specification.id,
            tracks=[],
            validation_result=None,  # Set after generation
            created_at=datetime.now(),
            cost_actual=Decimal('0.00'),
            generation_time_seconds=0.0
        )

    def add_track(self, track: SelectedTrack) -> None:
        """Add track to playlist.

        Args:
            track: Track to add
        """
        track.position_in_playlist = len(self.tracks)
        self.tracks.append(track)

    def calculate_australian_percentage(self) -> float:
        """Calculate percentage of Australian tracks.

        Returns:
            Percentage as decimal (0.0-1.0)
        """
        if not self.tracks:
            return 0.0
        australian_count = sum(1 for t in self.tracks if t.is_australian)
        return australian_count / len(self.tracks)

    def calculate_genre_distribution(self) -> Dict[str, float]:
        """Calculate actual genre distribution.

        Returns:
            Dictionary mapping genre to percentage
        """
        if not self.tracks:
            return {}

        genre_counts: Dict[str, int] = {}
        for track in self.tracks:
            if track.genre:
                genre_counts[track.genre] = genre_counts.get(track.genre, 0) + 1

        total = len(self.tracks)
        return {genre: count / total for genre, count in genre_counts.items()}

    def calculate_era_distribution(self) -> Dict[str, float]:
        """Calculate actual era distribution.

        Returns:
            Dictionary mapping era to percentage
        """
        if not self.tracks:
            return {}

        current_year = datetime.now().year

        era_counts = {
            "Current": 0,
            "Recent": 0,
            "Modern Classics": 0,
            "Throwbacks": 0,
            "Unknown": 0
        }

        for track in self.tracks:
            if track.year is None:
                era_counts["Unknown"] += 1
            elif track.year >= current_year - 2:
                era_counts["Current"] += 1
            elif track.year >= current_year - 5:
                era_counts["Recent"] += 1
            elif track.year >= current_year - 10:
                era_counts["Modern Classics"] += 1
            else:
                era_counts["Throwbacks"] += 1

        total = len(self.tracks)
        return {era: count / total for era, count in era_counts.items()}

    def to_m3u(self) -> str:
        """Export playlist to M3U format.

        Returns:
            M3U formatted string
        """
        lines = ["#EXTM3U"]
        lines.append(f"#PLAYLIST:{self.name}")

        for track in sorted(self.tracks, key=lambda t: t.position_in_playlist):
            lines.append(track.to_m3u_entry())

        return "\n".join(lines)

    def validate(self) -> List[str]:
        """Validate playlist structure.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        if not self.tracks:
            errors.append("Playlist must contain at least 1 track")

        # Check for position gaps
        positions = sorted([t.position_in_playlist for t in self.tracks])
        if positions != list(range(len(positions))):
            errors.append("Track positions must be sequential starting at 0")

        return errors


# ============================================================================
# Core Entity: Decision Log
# ============================================================================


@dataclass
class DecisionLog:
    """Audit trail entry for AI/ML decision.

    Provides complete transparency and debugging for the generation process.

    Attributes:
        id: Unique log entry identifier (UUID v4)
        playlist_id: Reference to playlist
        decision_type: Type of decision
        timestamp: When decision was made
        decision_data: Type-specific decision data
        cost_incurred: LLM cost for this decision
        execution_time_ms: Time taken in milliseconds
    """

    id: str
    playlist_id: str
    decision_type: DecisionType
    timestamp: datetime
    decision_data: Dict[str, Any]
    cost_incurred: Decimal
    execution_time_ms: int

    @classmethod
    def log_track_selection(
        cls,
        playlist_id: str,
        track: SelectedTrack,
        criteria_matched: List[str],
        cost: Decimal,
        execution_time_ms: int
    ) -> 'DecisionLog':
        """Create log entry for track selection.

        Args:
            playlist_id: ID of playlist being generated
            track: Selected track
            criteria_matched: List of criteria that matched
            cost: LLM API cost
            execution_time_ms: Execution time in milliseconds

        Returns:
            DecisionLog instance
        """
        return cls(
            id=str(uuid.uuid4()),
            playlist_id=playlist_id,
            decision_type=DecisionType.TRACK_SELECTION,
            timestamp=datetime.now(),
            decision_data={
                "track_id": track.track_id,
                "track_title": track.title,
                "track_artist": track.artist,
                "reasoning": track.selection_reasoning,
                "criteria_matched": criteria_matched,
                "position": track.position_in_playlist
            },
            cost_incurred=cost,
            execution_time_ms=execution_time_ms
        )

    @classmethod
    def log_constraint_relaxation(
        cls,
        playlist_id: str,
        relaxation: ConstraintRelaxation,
        cost: Decimal,
        execution_time_ms: int
    ) -> 'DecisionLog':
        """Create log entry for constraint relaxation.

        Args:
            playlist_id: ID of playlist being generated
            relaxation: Constraint relaxation details
            cost: LLM API cost
            execution_time_ms: Execution time in milliseconds

        Returns:
            DecisionLog instance
        """
        return cls(
            id=str(uuid.uuid4()),
            playlist_id=playlist_id,
            decision_type=DecisionType.RELAXATION,
            timestamp=datetime.now(),
            decision_data={
                "step": relaxation.step,
                "constraint_type": relaxation.constraint_type,
                "original_value": relaxation.original_value,
                "relaxed_value": relaxation.relaxed_value,
                "reason": relaxation.reason
            },
            cost_incurred=cost,
            execution_time_ms=execution_time_ms
        )

    @classmethod
    def log_error(
        cls,
        playlist_id: str,
        error_message: str,
        error_type: str,
        traceback: str,
        cost: Decimal
    ) -> 'DecisionLog':
        """Create log entry for error.

        Args:
            playlist_id: ID of playlist being generated
            error_message: Error message
            error_type: Type of error
            traceback: Full traceback
            cost: LLM API cost incurred before error

        Returns:
            DecisionLog instance
        """
        return cls(
            id=str(uuid.uuid4()),
            playlist_id=playlist_id,
            decision_type=DecisionType.ERROR,
            timestamp=datetime.now(),
            decision_data={
                "error_message": error_message,
                "error_type": error_type,
                "traceback": traceback
            },
            cost_incurred=cost,
            execution_time_ms=0
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dictionary representation
        """
        return {
            "id": self.id,
            "playlist_id": self.playlist_id,
            "decision_type": self.decision_type.value,
            "timestamp": self.timestamp.isoformat(),
            "decision_data": self.decision_data,
            "cost_incurred": str(self.cost_incurred),
            "execution_time_ms": self.execution_time_ms
        }
