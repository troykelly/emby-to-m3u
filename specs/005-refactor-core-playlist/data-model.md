# Data Model: AI/ML-Powered Playlist Generation

**Feature**: 005-refactor-core-playlist
**Created**: 2025-10-06
**Status**: Design Phase

## Overview

This document defines all entities involved in the AI/ML-powered playlist generation system for Production City Radio. Each entity includes field definitions, types, relationships, validation rules, and Python dataclass representations.

---

## Core Entities

### 1. Station Identity Document

The authoritative source for all playlist generation rules, containing comprehensive programming guidelines.

#### Fields

| Field | Type | Description | Required | Validation |
|-------|------|-------------|----------|------------|
| `document_path` | `str` | Path to station-identity.md file | Yes | Must exist on filesystem |
| `lock_id` | `Optional[str]` | Exclusive lock identifier during generation | No | UUID v4 format |
| `lock_timestamp` | `Optional[datetime]` | When lock was acquired | No | ISO 8601 format |
| `locked_by` | `Optional[str]` | Process/session that holds lock | No | - |
| `programming_structures` | `List[ProgrammingStructure]` | Monday-Friday, Weekend structures | Yes | Min 1 structure |
| `rotation_strategy` | `RotationStrategy` | Power/Medium/Light rotation definitions | Yes | - |
| `content_requirements` | `ContentRequirements` | Australian content %, era distribution | Yes | - |
| `genre_definitions` | `List[GenreDefinition]` | All genres with metadata | Yes | Min 1 genre |
| `version` | `str` | Document version/hash | Yes | SHA-256 hash |
| `loaded_at` | `datetime` | When document was parsed | Yes | ISO 8601 format |

#### Relationships
- **Has Many**: `ProgrammingStructure` (Monday-Friday, Weekend Saturday, Weekend Sunday)
- **Has One**: `RotationStrategy`
- **Has One**: `ContentRequirements`

#### State Transitions
```
UNLOCKED → LOCKED (on generation start)
LOCKED → UNLOCKED (on generation complete/error)
```

#### Python Dataclass

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
from pathlib import Path
import hashlib

@dataclass
class StationIdentityDocument:
    """Station programming guide - single source of truth for playlist generation."""

    document_path: Path
    programming_structures: List['ProgrammingStructure']
    rotation_strategy: 'RotationStrategy'
    content_requirements: 'ContentRequirements'
    genre_definitions: List['GenreDefinition']
    version: str
    loaded_at: datetime
    lock_id: Optional[str] = None
    lock_timestamp: Optional[datetime] = None
    locked_by: Optional[str] = None

    @classmethod
    def from_file(cls, path: Path) -> 'StationIdentityDocument':
        """Load and parse station-identity.md file."""
        with open(path, 'r') as f:
            content = f.read()

        version = hashlib.sha256(content.encode()).hexdigest()
        # Parse markdown content into structured data
        # ... parsing logic ...

        return cls(
            document_path=path,
            version=version,
            loaded_at=datetime.now(),
            # ... parsed fields ...
        )

    def acquire_lock(self, session_id: str) -> bool:
        """Acquire exclusive lock on document."""
        if self.lock_id is not None:
            return False  # Already locked

        import uuid
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
        """Validate document structure and content."""
        errors = []

        if not self.programming_structures:
            errors.append("At least one programming structure required")

        if self.content_requirements.australian_content_min < 0.30:
            errors.append("Australian content minimum must be >= 30%")

        return errors
```

---

### 2. Daypart Specification

Time-bound programming segment with specific musical and content requirements.

#### Fields

| Field | Type | Description | Required | Validation |
|-------|------|-------------|----------|------------|
| `id` | `str` | Unique identifier | Yes | UUID v4 format |
| `name` | `str` | Display name (e.g., "Morning Drive: Production Call") | Yes | 1-100 chars |
| `schedule_type` | `ScheduleType` | WEEKDAY, SATURDAY, SUNDAY | Yes | Enum value |
| `time_start` | `time` | Start time (e.g., 06:00) | Yes | HH:MM format |
| `time_end` | `time` | End time (e.g., 10:00) | Yes | HH:MM, must be > time_start |
| `duration_hours` | `float` | Calculated duration in hours | Yes | Calculated from time range |
| `target_demographic` | `str` | Target audience description | Yes | - |
| `bpm_progression` | `List[BPMRange]` | BPM ranges over daypart duration | Yes | Min 1 range |
| `genre_mix` | `Dict[str, float]` | Genre → percentage mapping | Yes | Sum must equal 1.0 ±0.01 |
| `era_distribution` | `Dict[str, float]` | Era → percentage mapping | Yes | Sum must equal 1.0 ±0.01 |
| `mood_guidelines` | `List[str]` | Mood/energy descriptors | Yes | - |
| `mood_exclusions` | `List[str]` | Moods to avoid | No | - |
| `content_focus` | `str` | Programming content description | Yes | - |
| `rotation_percentages` | `Dict[str, float]` | Rotation category → % mapping | Yes | - |
| `tracks_per_hour` | `tuple[int, int]` | Min/max tracks per hour | Yes | min > 0, max >= min |
| `specialty_constraints` | `Optional[SpecialtyConstraint]` | Special programming rules | No | - |

#### Relationships
- **Belongs To**: `ProgrammingStructure`
- **Has Many**: `BPMRange`
- **Generates**: `PlaylistSpecification`

#### Validation Rules
- `time_end` must be after `time_start`
- `genre_mix` percentages must sum to 1.0 (±0.01 tolerance)
- `era_distribution` percentages must sum to 1.0 (±0.01 tolerance)
- `bpm_progression` must cover entire daypart duration
- `tracks_per_hour` min must be > 0

#### Python Dataclass

```python
from dataclasses import dataclass, field
from datetime import time
from typing import Dict, List, Optional, Tuple
from enum import Enum

class ScheduleType(Enum):
    WEEKDAY = "weekday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"

@dataclass
class BPMRange:
    """BPM range for a time segment within daypart."""
    time_start: time
    time_end: time
    bpm_min: int
    bpm_max: int

    def validate(self) -> List[str]:
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
    parameters: Dict[str, any]

@dataclass
class DaypartSpecification:
    """Time-bound programming segment with musical requirements."""

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

    def calculate_target_track_count(self) -> Tuple[int, int]:
        """Calculate min/max tracks needed for this daypart."""
        min_tracks = int(self.duration_hours * self.tracks_per_hour[0])
        max_tracks = int(self.duration_hours * self.tracks_per_hour[1])
        return (min_tracks, max_tracks)

    def get_bpm_range_at_time(self, at_time: time) -> Optional[BPMRange]:
        """Get BPM range for specific time within daypart."""
        for bpm_range in self.bpm_progression:
            if bpm_range.time_start <= at_time < bpm_range.time_end:
                return bpm_range
        return None

    def validate(self) -> List[str]:
        """Validate daypart specification."""
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
```

---

### 3. Playlist Specification

Generated from daypart specification, contains all selection criteria for AI/ML.

#### Fields

| Field | Type | Description | Required | Validation |
|-------|------|-------------|----------|------------|
| `id` | `str` | Unique identifier | Yes | UUID v4 format |
| `name` | `str` | Generated playlist name | Yes | Based on daypart + date |
| `source_daypart_id` | `str` | Reference to source daypart | Yes | Valid daypart ID |
| `generation_date` | `date` | Date this playlist is for | Yes | ISO 8601 date |
| `target_track_count_min` | `int` | Minimum tracks needed | Yes | > 0 |
| `target_track_count_max` | `int` | Maximum tracks needed | Yes | >= min |
| `track_selection_criteria` | `TrackSelectionCriteria` | All selection constraints | Yes | - |
| `cost_budget_allocated` | `Optional[Decimal]` | Allocated cost budget | No | > 0 if set |
| `created_at` | `datetime` | When specification was created | Yes | ISO 8601 format |

#### Relationships
- **Belongs To**: `DaypartSpecification` (via `source_daypart_id`)
- **Has One**: `TrackSelectionCriteria`
- **Generates**: `Playlist`

#### Python Dataclass

```python
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
import uuid

@dataclass
class PlaylistSpecification:
    """Generated specification for playlist creation."""

    id: str
    name: str
    source_daypart_id: str
    generation_date: date
    target_track_count_min: int
    target_track_count_max: int
    track_selection_criteria: 'TrackSelectionCriteria'
    created_at: datetime
    cost_budget_allocated: Optional[Decimal] = None

    @classmethod
    def from_daypart(
        cls,
        daypart: DaypartSpecification,
        generation_date: date,
        cost_budget: Optional[Decimal] = None
    ) -> 'PlaylistSpecification':
        """Create playlist specification from daypart."""
        min_tracks, max_tracks = daypart.calculate_target_track_count()

        name = f"{daypart.name} - {generation_date.isoformat()}"

        criteria = TrackSelectionCriteria.from_daypart(daypart)

        return cls(
            id=str(uuid.uuid4()),
            name=name,
            source_daypart_id=daypart.id,
            generation_date=generation_date,
            target_track_count_min=min_tracks,
            target_track_count_max=max_tracks,
            track_selection_criteria=criteria,
            created_at=datetime.now(),
            cost_budget_allocated=cost_budget
        )

    def validate(self) -> List[str]:
        """Validate playlist specification."""
        errors = []

        if self.target_track_count_min <= 0:
            errors.append("Minimum track count must be > 0")

        if self.target_track_count_max < self.target_track_count_min:
            errors.append("Maximum track count must be >= minimum")

        if self.cost_budget_allocated is not None and self.cost_budget_allocated <= 0:
            errors.append("Cost budget must be > 0 if set")

        errors.extend(self.track_selection_criteria.validate())

        return errors
```

---

### 4. Track Selection Criteria

Constraints and preferences derived from daypart specification, used by AI/ML to select tracks.

#### Fields

| Field | Type | Description | Required | Validation |
|-------|------|-------------|----------|------------|
| `bpm_ranges` | `List[BPMRange]` | BPM requirements over time | Yes | Min 1 range |
| `genre_mix` | `Dict[str, GenreCriteria]` | Genre → criteria mapping | Yes | Percentages sum to 1.0 |
| `era_distribution` | `Dict[str, EraCriteria]` | Era → criteria mapping | Yes | Percentages sum to 1.0 |
| `australian_content_min` | `float` | Minimum Australian % | Yes | 0.30-1.0 |
| `energy_flow_requirements` | `List[str]` | Energy progression descriptors | Yes | - |
| `mood_filters_include` | `List[str]` | Required moods | No | - |
| `mood_filters_exclude` | `List[str]` | Excluded moods | No | - |
| `rotation_distribution` | `Dict[str, float]` | Rotation category → % | Yes | - |
| `no_repeat_window_hours` | `float` | Hours before track can repeat | Yes | >= 0 |
| `specialty_constraints` | `Optional[SpecialtyConstraint]` | Special rules | No | - |
| `tolerance_bpm` | `int` | BPM tolerance in progressive relaxation | Yes | Default: 10 |
| `tolerance_genre_percent` | `float` | Genre % tolerance | Yes | Default: 0.10 |
| `tolerance_era_percent` | `float` | Era % tolerance | Yes | Default: 0.10 |

#### Relationships
- **Belongs To**: `PlaylistSpecification`
- **Uses**: `BPMRange`, `GenreCriteria`, `EraCriteria`

#### Python Dataclass

```python
from dataclasses import dataclass, field
from typing import Dict, List, Optional

@dataclass
class GenreCriteria:
    """Genre selection criteria with tolerance."""
    target_percentage: float  # 0.0-1.0
    tolerance: float = 0.10  # ±10% default

    @property
    def min_percentage(self) -> float:
        return max(0.0, self.target_percentage - self.tolerance)

    @property
    def max_percentage(self) -> float:
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
        return max(0.0, self.target_percentage - self.tolerance)

    @property
    def max_percentage(self) -> float:
        return min(1.0, self.target_percentage + self.tolerance)

@dataclass
class TrackSelectionCriteria:
    """Complete set of constraints for AI/ML track selection."""

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
    specialty_constraints: Optional[SpecialtyConstraint] = None

    @classmethod
    def from_daypart(cls, daypart: DaypartSpecification) -> 'TrackSelectionCriteria':
        """Create selection criteria from daypart specification."""

        # Convert genre mix to GenreCriteria
        genre_mix = {
            genre: GenreCriteria(target_percentage=pct)
            for genre, pct in daypart.genre_mix.items()
        }

        # Convert era distribution to EraCriteria
        from datetime import datetime
        current_year = datetime.now().year

        era_mapping = {
            "Current": (current_year - 2, current_year),
            "Recent": (current_year - 5, current_year - 2),
            "Modern Classics": (current_year - 10, current_year - 5),
            "Throwbacks": (current_year - 20, current_year - 10),
        }

        era_distribution = {
            era: EraCriteria(
                era_name=era,
                min_year=era_mapping[era][0],
                max_year=era_mapping[era][1],
                target_percentage=pct
            )
            for era, pct in daypart.era_distribution.items()
        }

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
        """Validate criteria."""
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
```

---

### 5. Selected Track

Individual track chosen by AI/ML for inclusion in playlist.

#### Fields

| Field | Type | Description | Required | Validation |
|-------|------|-------------|----------|------------|
| `track_id` | `str` | Subsonic/Emby track identifier | Yes | - |
| `title` | `str` | Track title | Yes | - |
| `artist` | `str` | Artist name | Yes | - |
| `album` | `str` | Album name | Yes | - |
| `bpm` | `Optional[int]` | Beats per minute | No | 60-200 if set |
| `genre` | `Optional[str]` | Primary genre | No | - |
| `year` | `Optional[int]` | Release year | No | 1900-current |
| `country` | `Optional[str]` | Artist country (ISO 3166-1) | No | - |
| `duration_seconds` | `int` | Track duration | Yes | > 0 |
| `is_australian` | `bool` | Whether artist is Australian | Yes | - |
| `rotation_category` | `str` | Power/Medium/Light/Recurrent/Library | Yes | Valid category |
| `position_in_playlist` | `int` | 0-indexed position | Yes | >= 0 |
| `selection_reasoning` | `str` | AI explanation for selection | Yes | Min 50 chars |
| `validation_status` | `ValidationStatus` | Pass/Fail/Warning | Yes | Enum value |
| `validation_notes` | `List[str]` | Validation issues if any | No | - |
| `metadata_source` | `str` | Where metadata came from | Yes | "library", "lastfm", "aubio" |

#### Relationships
- **Belongs To**: `Playlist`
- **References**: External track in Subsonic/Emby
- **Has One**: `ValidationStatus`

#### State Transitions
```
PROPOSED → VALIDATED → ACCEPTED
PROPOSED → VALIDATED → REJECTED
```

#### Python Dataclass

```python
from dataclasses import dataclass, field
from typing import Optional, List
from enum import Enum

class ValidationStatus(Enum):
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"

@dataclass
class SelectedTrack:
    """Track selected by AI/ML for playlist inclusion."""

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
        """Validate track against selection criteria."""
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
        """Convert to M3U playlist entry."""
        return f"#EXTINF:{self.duration_seconds},{self.artist} - {self.title}\n{self.track_id}"
```

---

### 6. Playlist

Complete generated playlist with all selected tracks.

#### Fields

| Field | Type | Description | Required | Validation |
|-------|------|-------------|----------|------------|
| `id` | `str` | Unique identifier | Yes | UUID v4 format |
| `name` | `str` | Playlist name | Yes | From specification |
| `specification_id` | `str` | Reference to specification | Yes | Valid spec ID |
| `tracks` | `List[SelectedTrack]` | All selected tracks in order | Yes | Min 1 track |
| `validation_result` | `ValidationResult` | Compliance assessment | Yes | - |
| `created_at` | `datetime` | When playlist was generated | Yes | ISO 8601 format |
| `cost_actual` | `Decimal` | Actual LLM API cost | Yes | >= 0 |
| `generation_time_seconds` | `float` | Time to generate | Yes | >= 0 |
| `constraint_relaxations` | `List[ConstraintRelaxation]` | Progressive relaxations applied | No | - |

#### Relationships
- **Belongs To**: `PlaylistSpecification` (via `specification_id`)
- **Has Many**: `SelectedTrack`
- **Has One**: `ValidationResult`

#### State Transitions
```
GENERATING → VALIDATING → COMPLETED
GENERATING → FAILED
```

#### Python Dataclass

```python
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import List
import uuid

@dataclass
class ConstraintRelaxation:
    """Record of progressive constraint relaxation."""
    step: int
    constraint_type: str  # "bpm", "genre", "era"
    original_value: str
    relaxed_value: str
    reason: str
    timestamp: datetime

@dataclass
class Playlist:
    """Complete generated playlist."""

    id: str
    name: str
    specification_id: str
    tracks: List[SelectedTrack]
    validation_result: 'ValidationResult'
    created_at: datetime
    cost_actual: Decimal
    generation_time_seconds: float
    constraint_relaxations: List[ConstraintRelaxation] = field(default_factory=list)

    @classmethod
    def create(cls, specification: PlaylistSpecification) -> 'Playlist':
        """Initialize new playlist from specification."""
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
        """Add track to playlist."""
        track.position_in_playlist = len(self.tracks)
        self.tracks.append(track)

    def calculate_australian_percentage(self) -> float:
        """Calculate percentage of Australian tracks."""
        if not self.tracks:
            return 0.0
        australian_count = sum(1 for t in self.tracks if t.is_australian)
        return australian_count / len(self.tracks)

    def calculate_genre_distribution(self) -> Dict[str, float]:
        """Calculate actual genre distribution."""
        if not self.tracks:
            return {}

        genre_counts = {}
        for track in self.tracks:
            if track.genre:
                genre_counts[track.genre] = genre_counts.get(track.genre, 0) + 1

        total = len(self.tracks)
        return {genre: count / total for genre, count in genre_counts.items()}

    def calculate_era_distribution(self) -> Dict[str, float]:
        """Calculate actual era distribution."""
        if not self.tracks:
            return {}

        from datetime import datetime
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
        """Export playlist to M3U format."""
        lines = ["#EXTM3U"]
        lines.append(f"#PLAYLIST:{self.name}")

        for track in sorted(self.tracks, key=lambda t: t.position_in_playlist):
            lines.append(track.to_m3u_entry())

        return "\n".join(lines)

    def validate(self) -> List[str]:
        """Validate playlist structure."""
        errors = []

        if not self.tracks:
            errors.append("Playlist must contain at least 1 track")

        # Check for position gaps
        positions = sorted([t.position_in_playlist for t in self.tracks])
        if positions != list(range(len(positions))):
            errors.append("Track positions must be sequential starting at 0")

        return errors
```

---

### 7. Validation Result

Assessment of playlist compliance with station identity requirements.

#### Fields

| Field | Type | Description | Required | Validation |
|-------|------|-------------|----------|------------|
| `playlist_id` | `str` | Reference to playlist | Yes | Valid playlist ID |
| `overall_status` | `ValidationStatus` | Pass/Fail/Warning | Yes | Enum value |
| `constraint_scores` | `Dict[str, ConstraintScore]` | Score per constraint type | Yes | - |
| `flow_quality_metrics` | `FlowQualityMetrics` | BPM variance, energy progression | Yes | - |
| `gap_analysis` | `List[str]` | Identified deficiencies | No | - |
| `compliance_percentage` | `float` | Overall compliance score | Yes | 0.0-1.0 |
| `validated_at` | `datetime` | When validation ran | Yes | ISO 8601 format |

#### Relationships
- **Belongs To**: `Playlist` (via `playlist_id`)
- **Has Many**: `ConstraintScore`
- **Has One**: `FlowQualityMetrics`

#### Python Dataclass

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List

@dataclass
class ConstraintScore:
    """Score for individual constraint compliance."""
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
        """Calculate compliance score."""
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

@dataclass
class FlowQualityMetrics:
    """Quality metrics for playlist flow."""
    bpm_variance: float  # Standard deviation of BPM
    bpm_progression_coherence: float  # 0.0-1.0, how well BPM follows progression
    energy_consistency: float  # 0.0-1.0
    genre_diversity_index: float  # 0.0-1.0, Shannon entropy

    def calculate_overall_quality(self) -> float:
        """Calculate overall flow quality score."""
        # Lower BPM variance is better
        bpm_score = max(0, 1 - (self.bpm_variance / 30))  # Normalize to 0-1

        # Average the metrics
        return (
            bpm_score * 0.25 +
            self.bpm_progression_coherence * 0.25 +
            self.energy_consistency * 0.25 +
            self.genre_diversity_index * 0.25
        )

@dataclass
class ValidationResult:
    """Complete validation assessment of playlist."""

    playlist_id: str
    overall_status: ValidationStatus
    constraint_scores: Dict[str, ConstraintScore]
    flow_quality_metrics: FlowQualityMetrics
    compliance_percentage: float
    validated_at: datetime
    gap_analysis: List[str] = field(default_factory=list)

    @classmethod
    def validate_playlist(
        cls,
        playlist: Playlist,
        criteria: TrackSelectionCriteria
    ) -> 'ValidationResult':
        """Perform complete validation of playlist against criteria."""

        constraint_scores = {}
        gap_analysis = []

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
        import statistics
        bpm_variance = statistics.stdev(bpms) if len(bpms) > 1 else 0.0

        # Calculate genre diversity (Shannon entropy)
        import math
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
```

---

### 8. Decision Log

Audit trail of AI/ML selection process for transparency and debugging.

#### Fields

| Field | Type | Description | Required | Validation |
|-------|------|-------------|----------|------------|
| `id` | `str` | Unique log entry identifier | Yes | UUID v4 format |
| `playlist_id` | `str` | Reference to playlist | Yes | Valid playlist ID |
| `decision_type` | `DecisionType` | track_selection, validation, error, relaxation | Yes | Enum value |
| `timestamp` | `datetime` | When decision was made | Yes | ISO 8601 format |
| `decision_data` | `Dict[str, any]` | Type-specific decision data | Yes | - |
| `cost_incurred` | `Decimal` | LLM cost for this decision | Yes | >= 0 |
| `execution_time_ms` | `int` | Time taken in milliseconds | Yes | >= 0 |

#### Relationships
- **Belongs To**: `Playlist` (via `playlist_id`)

#### Python Dataclass

```python
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any
from enum import Enum
import uuid

class DecisionType(Enum):
    TRACK_SELECTION = "track_selection"
    VALIDATION = "validation"
    ERROR = "error"
    RELAXATION = "relaxation"
    METADATA_RETRIEVAL = "metadata_retrieval"

@dataclass
class DecisionLog:
    """Audit trail entry for AI/ML decision."""

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
        """Create log entry for track selection."""
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
        """Create log entry for constraint relaxation."""
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
        """Create log entry for error."""
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
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "playlist_id": self.playlist_id,
            "decision_type": self.decision_type.value,
            "timestamp": self.timestamp.isoformat(),
            "decision_data": self.decision_data,
            "cost_incurred": str(self.cost_incurred),
            "execution_time_ms": self.execution_time_ms
        }
```

---

## Entity Relationship Diagram

```
┌─────────────────────────────────┐
│ StationIdentityDocument         │
│ - lock_id                       │
│ - programming_structures []     │
│ - rotation_strategy             │
│ - content_requirements          │
└─────────────┬───────────────────┘
              │
              │ has many
              ▼
┌─────────────────────────────────┐
│ DaypartSpecification            │
│ - schedule_type                 │
│ - time_start/end                │
│ - bpm_progression []            │
│ - genre_mix {}                  │
│ - era_distribution {}           │
└─────────────┬───────────────────┘
              │
              │ generates
              ▼
┌─────────────────────────────────┐
│ PlaylistSpecification           │
│ - target_track_count_min/max    │
│ - track_selection_criteria      │
│ - cost_budget_allocated         │
└─────────────┬───────────────────┘
              │
              │ creates
              ▼
┌─────────────────────────────────┐
│ Playlist                        │
│ - tracks []                     │
│ - validation_result             │
│ - cost_actual                   │
│ - constraint_relaxations []     │
└─────────────┬───────────────────┘
              │
              ├── has many ────────┐
              │                    │
              ▼                    ▼
┌──────────────────────┐   ┌─────────────────┐
│ SelectedTrack        │   │ ValidationResult│
│ - selection_reasoning│   │ - constraint_   │
│ - validation_status  │   │   scores {}     │
│ - metadata_source    │   │ - flow_quality_ │
└──────────────────────┘   │   metrics       │
                           └─────────────────┘

┌─────────────────────────────────┐
│ DecisionLog                     │
│ - decision_type                 │
│ - decision_data {}              │
│ - cost_incurred                 │
└─────────────────────────────────┘
       │
       │ belongs to (many)
       └──────────────────────► Playlist
```

---

## Supporting Entities

### ProgrammingStructure

```python
from enum import Enum

class ScheduleType(Enum):
    WEEKDAY = "weekday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"

@dataclass
class ProgrammingStructure:
    """Weekly programming structure (Monday-Friday, Weekend)."""
    schedule_type: ScheduleType
    dayparts: List[DaypartSpecification]
```

### RotationStrategy

```python
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
```

### ContentRequirements

```python
@dataclass
class ContentRequirements:
    """Station-wide content requirements."""
    australian_content_min: float  # 0.30 minimum
    australian_content_target: float  # 0.30-0.35
```

### GenreDefinition

```python
@dataclass
class GenreDefinition:
    """Genre definition with metadata."""
    name: str
    description: str
    parent_genre: Optional[str]
    typical_bpm_range: Tuple[int, int]
```

---

## Summary

This data model provides:

1. **8 Core Entities** with complete field definitions and validation
2. **Python dataclasses** ready for implementation
3. **Relationship mappings** between entities
4. **State transition diagrams** where applicable
5. **Validation methods** for data integrity
6. **Helper methods** for common operations
7. **Type safety** with enums and type hints

The model supports all 31 functional requirements from the specification and enables:
- Lock-based concurrency control (FR-031)
- Progressive constraint relaxation (FR-028)
- Complete audit trails (FR-018, FR-027)
- Cost tracking (FR-009, FR-030)
- Metadata enhancement (FR-029)
- Playlist validation (FR-022, FR-023, FR-025, FR-026)

All entities are implementation-ready with proper Python typing for immediate use in the refactored playlist generation system.
