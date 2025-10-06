# Phase 1: Data Model

## Core Entities

### 1. ProgrammingDocument
**Purpose**: Represents parsed plain-language radio programming strategy

**Fields**:
- `content`: str - Raw markdown content from station-identity.md
- `dayparts`: List[DaypartSpec] - Extracted daypart specifications
- `metadata`: dict - Document metadata (station name, version, last updated)

**Validation Rules**:
- Content must not be empty
- Must contain at least one valid daypart
- Daypart time ranges must not overlap

**State Transitions**: Immutable (parsed once)

---

### 2. DaypartSpec
**Purpose**: Structured specification for a radio programming time block

**Fields**:
- `name`: str - Daypart name (e.g., "Production Call", "The Session")
- `day`: str - Day of week ("Monday" | "Tuesday" | ... | "Saturday" | "Sunday")
- `time_range`: tuple[str, str] - Start and end times ("06:00", "10:00")
- `bpm_progression`: dict[str, tuple[int, int]] - Time slot → BPM range mapping
  - Example: {"06:00-07:00": (90, 115), "07:00-09:00": (110, 135)}
- `genre_mix`: dict[str, float] - Genre → percentage mapping
  - Example: {"Alternative": 0.25, "Electronic": 0.20, "Quality Pop": 0.20}
- `era_distribution`: dict[str, float] - Era → percentage mapping
  - Example: {"Current (0-2 years)": 0.40, "Recent (2-5 years)": 0.35}
- `australian_min`: float - Minimum Australian content percentage (0.30 = 30%)
- `mood`: str - Mood/energy description (e.g., "energetic", "contemplative")
- `tracks_per_hour`: int - Estimated tracks per hour for duration calculation

**Validation Rules**:
- name: non-empty, max 100 chars
- day: must be valid day of week
- time_range: valid 24-hour format, start < end
- bpm_progression: all BPM values > 0, ranges within time_range
- genre_mix: percentages sum to ≤ 1.0, all values 0.0-1.0
- era_distribution: percentages sum to ≤ 1.0, all values 0.0-1.0
- australian_min: 0.0 ≤ value ≤ 1.0
- mood: non-empty, max 200 chars
- tracks_per_hour: > 0

**Relationships**:
- Belongs to one ProgrammingDocument
- Generates one PlaylistSpec

---

### 3. PlaylistSpec
**Purpose**: Generated playlist specification ready for track selection

**Fields**:
- `id`: str - UUID for tracking
- `name`: str - Playlist name using schema "{Day}_{ShowName}_{StartTime}_{EndTime}"
  - Example: "Monday_ProductionCall_0600_1000"
- `daypart`: DaypartSpec - Source daypart specification
- `target_duration_minutes`: int - Calculated from time_range and tracks_per_hour
- `track_criteria`: TrackSelectionCriteria - Consolidated selection criteria
- `created_at`: datetime - Generation timestamp

**Validation Rules**:
- id: valid UUID4
- name: matches schema pattern, unique within execution
- daypart: must be valid DaypartSpec
- target_duration_minutes: > 0
- track_criteria: must be valid TrackSelectionCriteria
- created_at: not in future

**Relationships**:
- Derived from one DaypartSpec
- Used by one TrackSelectionCriteria
- Produces one Playlist (after track selection)

---

### 4. TrackSelectionCriteria
**Purpose**: Multi-dimensional constraint set for LLM track selection

**Fields**:
- `bpm_range`: tuple[int, int] - BPM constraints (min, max)
- `bpm_tolerance`: int - Relaxation increment (default: 10)
- `genre_mix`: dict[str, tuple[float, float]] - Genre → (min%, max%) mapping
  - Example: {"Alternative": (0.20, 0.30), "Electronic": (0.15, 0.25)}
- `genre_tolerance`: float - Relaxation tolerance (default: 0.05)
- `era_distribution`: dict[str, tuple[float, float]] - Era → (min%, max%) mapping
- `era_tolerance`: float - Relaxation tolerance (default: 0.05)
- `australian_min`: float - Minimum Australian content (NON-NEGOTIABLE)
- `energy_flow`: str - Energy progression description for LLM
  - Example: "Start moderate, build to peak at hour 2, wind down"
- `excluded_track_ids`: List[str] - Tracks to exclude (avoid repeats)

**Validation Rules**:
- bpm_range: min > 0, max > min, both ≤ 300
- bpm_tolerance: > 0, ≤ 50
- genre_mix: all ranges valid (min ≤ max), sum of mins ≤ 1.0
- genre_tolerance: 0.0 ≤ value ≤ 0.20
- era_distribution: all ranges valid, sum of mins ≤ 1.0
- era_tolerance: 0.0 ≤ value ≤ 0.20
- australian_min: 0.0 ≤ value ≤ 1.0
- energy_flow: non-empty, max 500 chars
- excluded_track_ids: all valid track IDs

**Relationships**:
- Belongs to one PlaylistSpec
- Used in LLMTrackSelectionRequest
- Can be relaxed to create RelaxedCriteria

---

### 5. LLMTrackSelectionRequest
**Purpose**: Request payload for OpenAI LLM track selection via MCP

**Fields**:
- `playlist_id`: str - PlaylistSpec UUID
- `criteria`: TrackSelectionCriteria - Selection constraints
- `target_track_count`: int - Calculated from duration / avg track length
- `mcp_tools`: List[str] - Subsonic MCP tools to use
  - Default: ["search_tracks", "get_genres", "search_similar", "analyze_library"]
- `prompt_template`: str - LLM prompt with placeholder substitution
- `max_cost_usd`: float - Cost limit for this request (default: 0.01)
- `timeout_seconds`: int - Request timeout (default: 30)

**Validation Rules**:
- playlist_id: valid UUID
- criteria: valid TrackSelectionCriteria
- target_track_count: > 0, ≤ 1000
- mcp_tools: non-empty, all valid tool names
- prompt_template: contains required placeholders
- max_cost_usd: > 0, ≤ 0.50
- timeout_seconds: > 0, ≤ 300

**Relationships**:
- References one PlaylistSpec
- Uses one TrackSelectionCriteria
- Produces one LLMTrackSelectionResponse

---

### 6. LLMTrackSelectionResponse
**Purpose**: Response from OpenAI LLM with selected tracks and metadata

**Fields**:
- `request_id`: str - Original request playlist_id
- `selected_tracks`: List[SelectedTrack] - Ordered list of selected tracks
- `tool_calls`: List[dict] - MCP tool invocations made by LLM
- `reasoning`: str - LLM explanation for selections
- `cost_usd`: float - Actual API cost incurred
- `execution_time_seconds`: float - Total processing time
- `created_at`: datetime - Response timestamp

**Validation Rules**:
- request_id: valid UUID
- selected_tracks: non-empty, all valid SelectedTrack objects
- tool_calls: list of dicts with required keys (tool_name, arguments, result)
- reasoning: non-empty, max 2000 chars
- cost_usd: ≥ 0
- execution_time_seconds: ≥ 0
- created_at: not in future

**Relationships**:
- Corresponds to one LLMTrackSelectionRequest
- Contains multiple SelectedTrack objects
- Used to create Playlist

---

### 7. SelectedTrack
**Purpose**: Track selected by LLM with metadata for validation

**Fields**:
- `track_id`: str - Subsonic/Emby track ID
- `title`: str - Track title
- `artist`: str - Artist name
- `album`: str - Album name
- `bpm`: int - Beats per minute
- `genre`: str - Primary genre
- `year`: int - Release year
- `country`: str - Country of origin (for Australian content validation)
- `duration_seconds`: int - Track duration
- `position`: int - Position in playlist (1-based)
- `selection_reason`: str - LLM reasoning for this track

**Validation Rules**:
- track_id: non-empty
- title, artist, album: non-empty, max 200 chars each
- bpm: > 0, ≤ 300 (or null if unavailable)
- genre: non-empty, max 50 chars (or null if unavailable)
- year: 1900 ≤ value ≤ current year + 1 (or null)
- country: valid ISO country code or null
- duration_seconds: > 0
- position: > 0
- selection_reason: non-empty, max 500 chars

**Relationships**:
- Part of one LLMTrackSelectionResponse
- Maps to existing Track entity in Track model
- Included in Playlist after validation

---

### 8. Playlist
**Purpose**: Final validated playlist ready for AzuraCast sync

**Fields**:
- `id`: str - UUID (same as PlaylistSpec.id)
- `name`: str - Playlist name (from PlaylistSpec)
- `tracks`: List[SelectedTrack] - Validated and ordered tracks
- `spec`: PlaylistSpec - Original specification
- `validation_result`: ValidationResult - Quality validation outcome
- `created_at`: datetime - Creation timestamp
- `synced_at`: datetime | None - AzuraCast sync timestamp
- `azuracast_id`: int | None - AzuraCast playlist ID after sync

**Validation Rules**:
- id: valid UUID, matches spec.id
- name: matches PlaylistSpec naming schema
- tracks: non-empty, all valid SelectedTrack objects
- spec: valid PlaylistSpec
- validation_result: must pass (is_valid() == True)
- created_at: not in future
- synced_at: None or ≥ created_at
- azuracast_id: None or > 0

**Relationships**:
- One-to-one with PlaylistSpec
- Contains multiple SelectedTrack objects
- Has one ValidationResult
- Maps to AzuraCast playlist entity (external)

---

### 9. ValidationResult
**Purpose**: Quality assessment of generated playlist

**Fields**:
- `constraint_satisfaction`: float - Overall constraint match (0.0-1.0)
- `bpm_satisfaction`: float - BPM criteria match (0.0-1.0)
- `genre_satisfaction`: float - Genre mix match (0.0-1.0)
- `era_satisfaction`: float - Era distribution match (0.0-1.0)
- `australian_content`: float - Actual Australian content percentage
- `flow_quality_score`: float - Energy/tempo transition smoothness (0.0-1.0)
- `bpm_variance`: float - Average BPM change between adjacent tracks
- `energy_progression`: str - "smooth" | "choppy" | "monotone"
- `genre_diversity`: float - Genre variety metric (0.0-1.0)
- `gap_analysis`: dict[str, str] - Constraint → explanation for unmet criteria
- `passes_validation`: bool - True if constraint_satisfaction ≥ 0.80 AND flow_quality_score ≥ 0.70

**Validation Rules**:
- All float fields: 0.0 ≤ value ≤ 1.0
- energy_progression: one of allowed values
- gap_analysis: dict with string keys and values
- passes_validation: consistent with threshold calculations

**Relationships**:
- One-to-one with Playlist
- Derived from Playlist.tracks and Playlist.spec.track_criteria

---

### 10. DecisionLog
**Purpose**: Audit trail for playlist generation decisions (indefinite retention)

**Fields**:
- `id`: str - UUID for log entry
- `timestamp`: datetime - When decision was made
- `decision_type`: str - "track_selection" | "constraint_relaxation" | "validation" | "sync"
- `playlist_id`: str - Associated playlist UUID
- `playlist_name`: str - Playlist name for readability
- `criteria`: dict - Serialized TrackSelectionCriteria (original or relaxed)
- `selected_tracks`: List[dict] - Serialized SelectedTrack objects
- `validation_result`: dict - Serialized ValidationResult
- `metadata`: dict - Additional context (LLM cost, execution time, relaxation steps, errors)

**Validation Rules**:
- id: valid UUID
- timestamp: not in future
- decision_type: one of allowed values
- playlist_id: valid UUID
- playlist_name: non-empty
- criteria, selected_tracks, validation_result: valid JSON-serializable dicts
- metadata: valid JSON-serializable dict

**Storage Format**: JSON Lines (JSONL) - one entry per line in append-only log file

**Relationships**:
- References Playlist by playlist_id
- Independent entity for audit/replay purposes

---

## Entity Relationships Diagram

```
ProgrammingDocument (1) ──> (N) DaypartSpec
                                     │
                                     ↓
                             (1) PlaylistSpec
                                     │
                                     ↓
                          TrackSelectionCriteria ──> LLMTrackSelectionRequest
                                                              │
                                                              ↓
                                                   LLMTrackSelectionResponse
                                                              │
                                                              ↓
                                                      (N) SelectedTrack
                                                              │
                                                              ↓
                             (1) Playlist ←──────────────────┘
                                     │
                                     ├──> ValidationResult
                                     │
                                     └──> DecisionLog
                                               │
                                               └──> [Indefinite Storage]
```

## Data Flow

1. **Document Parsing**: ProgrammingDocument → DaypartSpec (N)
2. **Spec Generation**: DaypartSpec → PlaylistSpec → TrackSelectionCriteria
3. **Track Selection**: TrackSelectionCriteria → LLMRequest → LLMResponse → SelectedTrack (N)
4. **Validation**: SelectedTrack (N) → ValidationResult
5. **Playlist Creation**: SelectedTrack (N) + ValidationResult → Playlist
6. **Sync**: Playlist → AzuraCast (external)
7. **Audit**: All steps → DecisionLog → Indefinite storage

## Constraint Relaxation State Machine

```
InitialCriteria (strict)
    │
    ↓ (if insufficient tracks)
BPMRelaxed (+10 BPM tolerance)
    │
    ↓ (if still insufficient)
GenreRelaxed (+5% genre tolerance)
    │
    ↓ (if still insufficient)
EraRelaxed (+5% era tolerance)
    │
    ↓ (always maintain)
AustralianMinimum (30% NON-NEGOTIABLE)
```

## Validation Rules Summary

| Entity | Key Constraints |
|--------|----------------|
| DaypartSpec | Time ranges non-overlapping, percentages sum ≤ 1.0 |
| PlaylistSpec | Name follows schema, unique per execution |
| TrackSelectionCriteria | Australian min NON-NEGOTIABLE, all tolerances ≤ 20% |
| SelectedTrack | Country required for Australian validation |
| Playlist | ValidationResult.passes_validation MUST be True |
| ValidationResult | constraint_satisfaction ≥ 0.80, flow_quality ≥ 0.70 |
| DecisionLog | Append-only, never deleted (indefinite retention) |

## Implementation Notes

- All entities use Python dataclasses with type hints
- Validation implemented via `__post_init__` or separate validator functions
- JSON serialization for DecisionLog storage
- Async/await for all external API interactions (OpenAI, Subsonic MCP, AzuraCast)
- Immutable entities where possible (ProgrammingDocument, DaypartSpec, ValidationResult)
