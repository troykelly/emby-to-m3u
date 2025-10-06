# AI Playlist Automation - API Reference

Comprehensive API documentation for the AI-powered radio playlist automation system.

## Table of Contents

- [Document Parser](#document-parser)
- [Playlist Planner](#playlist-planner)
- [OpenAI Client](#openai-client)
- [Track Selector](#track-selector)
- [Validator](#validator)
- [AzuraCast Sync](#azuracast-sync)
- [Decision Logger](#decision-logger)
- [CLI](#command-line-interface)
- [Data Models](#data-models)
- [Error Handling](#error-handling)

---

## Document Parser

Module: `src.ai_playlist.document_parser`

Parses plain-language programming documents into structured daypart specifications.

### Functions

#### `parse_programming_document(content: str) -> List[DaypartSpec]`

Parse programming document markdown into structured daypart specifications.

**Parameters**:
- `content` (str): Raw markdown content from station-identity.md

**Returns**:
- `List[DaypartSpec]`: List of parsed daypart specifications

**Raises**:
- `ValueError`: If content is empty or invalid
- `ParseError`: If markdown structure cannot be parsed
- `ValidationError`: If extracted data fails validation (BPM > 300, genre sum > 100%, etc.)

**Example**:
```python
from src.ai_playlist.document_parser import parse_programming_document

# Load document
with open("station-identity.md") as f:
    content = f.read()

# Parse dayparts
dayparts = parse_programming_document(content)

for daypart in dayparts:
    print(f"{daypart.name}: {daypart.time_range}")
    print(f"  BPM: {daypart.bpm_progression}")
    print(f"  Genres: {daypart.genre_mix}")
    print(f"  Australian: {daypart.australian_min*100:.0f}%")
```

**Document Format**:

```markdown
## Monday Programming

### Morning Drive: "Production Call" (6:00 AM - 10:00 AM)

BPM Progression:
- 6:00-7:00 AM: 90-115 BPM
- 7:00-8:00 AM: 100-120 BPM

Genre Mix:
- Alternative: 25%
- Indie: 30%
- Electronic: 20%

Era Mix:
- Current (last 2 years): 40%
- Recent (2-5 years): 30%

Australian Content: 30% minimum

Mood: Energetic morning drive
```

---

## Playlist Planner

Module: `src.ai_playlist.playlist_planner`

Generates playlist specifications from daypart specifications.

### Functions

#### `generate_playlist_specs(dayparts: List[DaypartSpec]) -> List[PlaylistSpec]`

Convert daypart specifications into concrete playlist specifications.

**Parameters**:
- `dayparts` (List[DaypartSpec]): List of daypart specifications

**Returns**:
- `List[PlaylistSpec]`: Playlist specifications ready for track selection

**Raises**:
- `ValueError`: If dayparts list is empty or contains invalid specs

**Example**:
```python
from src.ai_playlist.playlist_planner import generate_playlist_specs

# Generate specs from parsed dayparts
playlist_specs = generate_playlist_specs(dayparts)

for spec in playlist_specs:
    print(f"Playlist: {spec.name}")
    print(f"  Duration: {spec.target_duration_minutes} minutes")
    print(f"  BPM Range: {spec.track_criteria.bpm_range}")
    print(f"  Genres: {spec.track_criteria.genre_mix}")
```

**Naming Convention**:

Playlists are named using the schema: `{Day}_{ShowName}_{StartTime}_{EndTime}`

Examples:
- `Monday_ProductionCall_0600_1000`
- `Saturday_TheSession_1400_1800`

**Track Criteria Generation**:

The planner automatically generates `TrackSelectionCriteria` with:
- Genre percentages converted to (min%, max%) ranges with ±5% tolerance
- Era distributions converted to (min%, max%) ranges with ±5% tolerance
- BPM range extracted from progression (overall min/max)
- BPM tolerance set to 10
- Australian minimum preserved from daypart

---

## OpenAI Client

Module: `src.ai_playlist.openai_client`

Handles LLM interactions for track selection using OpenAI GPT-4o-mini.

### Classes

#### `OpenAIClient`

OpenAI client for AI playlist generation with MCP tool integration.

**Constructor**:
```python
OpenAIClient(api_key: Optional[str] = None)
```

**Parameters**:
- `api_key` (Optional[str]): OpenAI API key. If None, reads from `OPENAI_API_KEY` env var

**Raises**:
- `ValueError`: If API key not provided or found in environment

**Attributes**:
- `model`: str = "gpt-5"
- `cost_per_input_token`: float = 0.00000015 ($0.15 per 1M tokens)
- `cost_per_output_token`: float = 0.00000060 ($0.60 per 1M tokens)

### Methods

#### `create_selection_request(spec: PlaylistSpec) -> LLMTrackSelectionRequest`

Create LLM track selection request from playlist specification.

**Parameters**:
- `spec` (PlaylistSpec): Playlist specification with daypart and criteria

**Returns**:
- `LLMTrackSelectionRequest`: Request ready for LLM call

**Example**:
```python
from src.ai_playlist.openai_client import OpenAIClient

client = OpenAIClient()
request = client.create_selection_request(playlist_spec)

print(f"Target tracks: {request.target_track_count}")
print(f"Max cost: ${request.max_cost_usd:.4f}")
print(f"Prompt:\n{request.prompt_template}")
```

#### `estimate_tokens(request: LLMTrackSelectionRequest) -> int`

Estimate token count for LLM request.

**Parameters**:
- `request` (LLMTrackSelectionRequest): Request to estimate

**Returns**:
- `int`: Estimated total token count (input + expected output)

**Example**:
```python
tokens = client.estimate_tokens(request)
print(f"Estimated tokens: {tokens}")
```

#### `estimate_cost(request: LLMTrackSelectionRequest) -> float`

Estimate cost for LLM request.

**Parameters**:
- `request` (LLMTrackSelectionRequest): Request to estimate

**Returns**:
- `float`: Estimated cost in USD

**Example**:
```python
cost = client.estimate_cost(request)
print(f"Estimated cost: ${cost:.6f}")
```

#### `async call_llm(request: LLMTrackSelectionRequest, mcp_tools: Dict) -> LLMTrackSelectionResponse`

Call OpenAI LLM with MCP tool integration for track selection.

**Parameters**:
- `request` (LLMTrackSelectionRequest): Track selection request
- `mcp_tools` (Dict): MCP tool configuration from mcp_connector

**Returns**:
- `LLMTrackSelectionResponse`: Response with selected tracks and metadata

**Raises**:
- `ValueError`: If request validation fails
- `TimeoutError`: If LLM call exceeds timeout
- `Exception`: If LLM call fails after retries

**Example**:
```python
import asyncio
from src.ai_playlist.mcp_connector import get_mcp_tools

async def select_tracks():
    client = OpenAIClient()
    request = client.create_selection_request(playlist_spec)
    mcp_tools = get_mcp_tools()

    response = await client.call_llm(request, mcp_tools)

    print(f"Selected {len(response.selected_tracks)} tracks")
    print(f"Cost: ${response.cost_usd:.6f}")
    print(f"Time: {response.execution_time_seconds:.2f}s")

    return response

response = asyncio.run(select_tracks())
```

### Singleton Access

#### `get_client() -> OpenAIClient`

Get singleton OpenAI client instance.

**Returns**:
- `OpenAIClient`: Shared client instance

**Example**:
```python
from src.ai_playlist.openai_client import get_client

client = get_client()  # Reuses same instance across calls
```

---

## Track Selector

Module: `src.ai_playlist.track_selector`

Implements track selection with retry logic and constraint relaxation.

### Functions

#### `async select_tracks_with_llm(request: LLMTrackSelectionRequest) -> LLMTrackSelectionResponse`

Select tracks using OpenAI LLM with Subsonic MCP tools.

**Parameters**:
- `request` (LLMTrackSelectionRequest): Track selection request with criteria

**Returns**:
- `LLMTrackSelectionResponse`: Response with selected tracks and metadata

**Raises**:
- `CostExceededError`: If estimated or actual cost exceeds max_cost_usd
- `MCPToolError`: If Subsonic MCP server is unavailable
- `APIError`: If OpenAI API fails after 3 retries with exponential backoff

**Example**:
```python
import asyncio
from src.ai_playlist.track_selector import select_tracks_with_llm
from src.ai_playlist.openai_client import get_client

async def select_playlist_tracks():
    client = get_client()
    request = client.create_selection_request(playlist_spec)

    # Select tracks with retry logic
    response = await select_tracks_with_llm(request)

    for track in response.selected_tracks:
        print(f"{track.position}. {track.title} - {track.artist}")
        print(f"   BPM: {track.bpm}, Genre: {track.genre}, Country: {track.country}")
        print(f"   Reason: {track.selection_reason}\n")

    return response

response = asyncio.run(select_playlist_tracks())
```

**Retry Behavior**:
- 3 attempts with exponential backoff (1s, 2s, 4s delays)
- Maximum delay capped at 60 seconds
- Logs warnings on retry, raises exception after final failure

**Cost Validation**:
- Checks estimated cost before API call
- Validates actual cost after response
- Raises `CostExceededError` if budget exceeded

#### `async select_tracks_with_relaxation(criteria: TrackSelectionCriteria, max_iterations: int = 3) -> List[SelectedTrack]`

Select tracks with hierarchical constraint relaxation.

**Parameters**:
- `criteria` (TrackSelectionCriteria): Initial track selection criteria
- `max_iterations` (int): Maximum relaxation iterations (default: 3)

**Returns**:
- `List[SelectedTrack]`: Selected tracks meeting ≥80% constraint satisfaction

**Relaxation Priority**:
1. **Iteration 0**: Strict criteria (no relaxation)
2. **Iteration 1**: BPM range ±10
3. **Iteration 2**: Genre tolerance ±5%
4. **Iteration 3**: Era tolerance ±5%

**Australian content minimum (30%) is NEVER relaxed.**

**Example**:
```python
import asyncio
from src.ai_playlist.track_selector import select_tracks_with_relaxation

async def select_with_fallback():
    criteria = TrackSelectionCriteria(
        bpm_range=(90, 120),
        genre_mix={
            "Alternative": (0.20, 0.30),
            "Indie": (0.25, 0.35)
        },
        australian_min=0.30
    )

    # Will relax constraints if needed to meet 80% satisfaction
    tracks = await select_tracks_with_relaxation(criteria, max_iterations=3)

    print(f"Selected {len(tracks)} tracks with constraint relaxation")
    return tracks

tracks = asyncio.run(select_with_fallback())
```

---

## Validator

Module: `src.ai_playlist.validator`

Validates generated playlists against quality standards.

### Functions

#### `validate_playlist(tracks: List[SelectedTrack], criteria: TrackSelectionCriteria) -> ValidationResult`

Validate generated playlist meets quality standards.

**Parameters**:
- `tracks` (List[SelectedTrack]): List of selected tracks in order
- `criteria` (TrackSelectionCriteria): Original selection criteria

**Returns**:
- `ValidationResult`: Validation metrics and pass/fail status

**Raises**:
- `ValueError`: If tracks list is empty

**Validation Thresholds**:
- **Constraint satisfaction**: ≥ 0.80 (80%)
- **Flow quality score**: ≥ 0.70 (70%)

**Metrics Calculated**:
1. **BPM satisfaction**: Percentage of tracks within BPM range
2. **Genre satisfaction**: Percentage of genre requirements met
3. **Era satisfaction**: Percentage of era requirements met
4. **Australian satisfaction**: Ratio of actual/required Australian content
5. **Flow quality**: Based on BPM variance between consecutive tracks
6. **Genre diversity**: Simpson's diversity index

**Example**:
```python
from src.ai_playlist.validator import validate_playlist

# Validate selected tracks
result = validate_playlist(
    tracks=response.selected_tracks,
    criteria=request.criteria
)

print(f"Constraint Satisfaction: {result.constraint_satisfaction:.1%}")
print(f"  BPM: {result.bpm_satisfaction:.1%}")
print(f"  Genre: {result.genre_satisfaction:.1%}")
print(f"  Era: {result.era_satisfaction:.1%}")
print(f"  Australian: {result.australian_content:.1%}")

print(f"\nFlow Quality: {result.flow_quality_score:.1%}")
print(f"  BPM Variance: {result.bpm_variance:.1f}")
print(f"  Energy: {result.energy_progression}")
print(f"  Diversity: {result.genre_diversity:.1%}")

print(f"\nValidation: {'PASSED' if result.passes_validation else 'FAILED'}")

if result.gap_analysis:
    print("\nGaps:")
    for constraint, reason in result.gap_analysis.items():
        print(f"  - {constraint}: {reason}")
```

**Energy Progression Classification**:
- **"smooth"**: Average BPM variance < 10
- **"moderate"**: Average BPM variance 10-20
- **"choppy"**: Average BPM variance > 20

---

## AzuraCast Sync

Module: `src.ai_playlist.azuracast_sync`

Synchronizes AI-generated playlists to AzuraCast.

### Functions

#### `async sync_playlist_to_azuracast(playlist: Playlist) -> Playlist`

Synchronizes an AI-generated playlist to AzuraCast.

**Parameters**:
- `playlist` (Playlist): Validated playlist object with tracks to sync

**Returns**:
- `Playlist`: Updated playlist object with `synced_at` and `azuracast_id` set

**Raises**:
- `AzuraCastPlaylistSyncError`: If sync fails after retries
- `ValueError`: If playlist validation fails or required env vars missing

**Required Environment Variables**:
- `AZURACAST_HOST`: AzuraCast instance URL
- `AZURACAST_API_KEY`: API key for authentication
- `AZURACAST_STATIONID`: Target station ID

**Sync Behavior** (FR-005: Update existing playlists):
1. Search for existing playlist by name
2. If found: Empty existing playlist tracks
3. If not found: Create new playlist
4. Upload tracks with duplicate detection
5. Add uploaded tracks to playlist
6. Set `synced_at` and `azuracast_id` on success

**Example**:
```python
import asyncio
from datetime import datetime
from src.ai_playlist.azuracast_sync import sync_playlist_to_azuracast
from src.ai_playlist.models import Playlist

async def sync_to_azuracast():
    # Create validated playlist
    playlist = Playlist(
        id=spec.id,
        name=spec.name,
        tracks=response.selected_tracks,
        spec=spec,
        validation_result=result,
        created_at=datetime.now()
    )

    # Sync to AzuraCast
    synced_playlist = await sync_playlist_to_azuracast(playlist)

    print(f"Synced: {synced_playlist.name}")
    print(f"  AzuraCast ID: {synced_playlist.azuracast_id}")
    print(f"  Synced at: {synced_playlist.synced_at.isoformat()}")
    print(f"  Tracks: {len(synced_playlist.tracks)}")

    return synced_playlist

synced = asyncio.run(sync_to_azuracast())
```

**Duplicate Detection**:

The sync process uses the existing `AzuraCastSync` client which includes:
- Track normalization (artist, album, title)
- Fuzzy matching for near-duplicates
- Skip upload if duplicate found
- Reuse existing AzuraCast file IDs

---

## Decision Logger

Module: `src.ai_playlist.decision_logger`

Implements indefinite audit logging of playlist generation decisions.

### Classes

#### `DecisionLogger`

Manages indefinite audit logging of playlist generation decisions.

**Constructor**:
```python
DecisionLogger(log_dir: Path = Path("logs/decisions"))
```

**Parameters**:
- `log_dir` (Path): Directory for decision log files (default: `logs/decisions`)

**Behavior**:
- Creates log directory if it doesn't exist
- Creates new JSONL file per execution: `decisions_{timestamp}.jsonl`
- Never rotates or deletes log files (indefinite retention per FR-014)

**Example**:
```python
from pathlib import Path
from src.ai_playlist.decision_logger import DecisionLogger

# Initialize logger
logger = DecisionLogger(log_dir=Path("logs/decisions"))

print(f"Logging to: {logger.get_log_file()}")
```

### Methods

#### `log_decision(decision_type: str, playlist_name: str, criteria: dict, selected_tracks: list, validation_result: dict, metadata: dict = None) -> None`

Log a playlist generation decision to JSONL file.

**Parameters**:
- `decision_type` (str): Type of decision ("track_selection" | "constraint_relaxation" | "validation" | "sync")
- `playlist_name` (str): Playlist name for readability
- `criteria` (dict): Serialized TrackSelectionCriteria (original or relaxed)
- `selected_tracks` (list): List of serialized SelectedTrack objects
- `validation_result` (dict): Serialized ValidationResult
- `metadata` (dict): Additional context (LLM cost, execution time, relaxation steps, errors)

**Raises**:
- `ValueError`: If decision_type is invalid or data is not JSON-serializable
- `IOError`: If log file cannot be written

**Example**:
```python
# Log track selection decision
logger.log_decision(
    decision_type="track_selection",
    playlist_name="Monday_ProductionCall_0600_1000",
    criteria={
        "bpm_range": [90, 120],
        "genre_mix": {"Alternative": [0.20, 0.30]},
        "australian_min": 0.30
    },
    selected_tracks=[
        {
            "track_id": "123",
            "title": "Song Title",
            "artist": "Artist Name",
            "bpm": 105,
            "country": "AU"
        }
    ],
    validation_result={
        "constraint_satisfaction": 0.85,
        "flow_quality_score": 0.78,
        "passes_validation": True
    },
    metadata={
        "playlist_id": "550e8400-e29b-41d4-a716-446655440000",
        "llm_cost_usd": 0.0032,
        "execution_time_seconds": 4.2,
        "relaxation_iterations": 0
    }
)
```

#### `get_log_file() -> Path`

Get current log file path.

**Returns**:
- `Path`: Path to current JSONL log file

**Example**:
```python
log_file = logger.get_log_file()
print(f"Current log: {log_file}")
# Output: Current log: logs/decisions/decisions_20251006T143000123456.jsonl
```

#### `read_decisions(log_file: Path = None) -> List[DecisionLog]`

Read and parse decisions from JSONL log file.

**Parameters**:
- `log_file` (Path): Optional specific log file to read (default: current log file)

**Returns**:
- `List[DecisionLog]`: Parsed decision log entries

**Raises**:
- `FileNotFoundError`: If log file doesn't exist
- `json.JSONDecodeError`: If log file contains invalid JSON
- `ValueError`: If log entries fail DecisionLog validation

**Example**:
```python
# Read decisions from current log
decisions = logger.read_decisions()

for decision in decisions:
    print(f"{decision.decision_type}: {decision.playlist_name}")
    print(f"  Cost: ${decision.metadata.get('llm_cost_usd', 0):.4f}")
    print(f"  Validation: {decision.validation_result.get('passes_validation')}")

# Read from specific log file
old_decisions = logger.read_decisions(
    log_file=Path("logs/decisions/decisions_20251005T120000000000.jsonl")
)
```

#### `list_log_files() -> List[Path]`

List all decision log files in log directory.

**Returns**:
- `List[Path]`: Sorted list of JSONL log files (oldest first)

**Example**:
```python
log_files = logger.list_log_files()

print(f"Found {len(log_files)} log files:")
for log_file in log_files:
    count = logger.count_decisions(log_file)
    print(f"  {log_file.name}: {count} decisions")
```

#### `count_decisions(log_file: Path = None) -> int`

Count number of decisions in log file.

**Parameters**:
- `log_file` (Path): Optional specific log file to count (default: current log file)

**Returns**:
- `int`: Number of decision entries in log file

**Example**:
```python
count = logger.count_decisions()
print(f"Current log has {count} decisions")
```

---

## Command Line Interface

Module: `src.ai_playlist.cli`

Command-line interface for playlist automation.

### Entry Point

```bash
python -m src.ai_playlist.cli [OPTIONS]
```

### Arguments

**Required**:
- `--input FILE`: Path to programming document (station-identity.md)
- `--output DIR`: Directory for playlist output files

**Optional**:
- `--dry-run`: Skip AzuraCast sync (generate playlists only)
- `--max-cost USD`: Maximum total LLM cost in USD (default: 0.50)
- `--verbose, -v`: Enable verbose debug logging
- `--version`: Show version and exit

### Examples

```bash
# Basic usage
python -m src.ai_playlist.cli --input station-identity.md --output playlists/

# Dry run (no AzuraCast sync)
python -m src.ai_playlist.cli --input station-identity.md --output playlists/ --dry-run

# Increase budget
python -m src.ai_playlist.cli --input station-identity.md --output playlists/ --max-cost 1.00

# Verbose logging
python -m src.ai_playlist.cli --input station-identity.md --output playlists/ --verbose
```

### Exit Codes

- `0`: Success (at least one playlist generated)
- `1`: Failure (no playlists generated or error occurred)

### Progress Display

The CLI displays real-time progress:

```
======================================================================
AI PLAYLIST AUTOMATION
======================================================================
Input document:  station-identity.md
Output directory: playlists/
Max cost:        $0.50
Dry run:         False
Started:         2025-10-06 14:30:00
======================================================================

[Track Selection] Progress: 1/7 (14%) | Time: 4.2s | Cost: $0.0032
[Track Selection] Progress: 2/7 (29%) | Time: 8.5s | Cost: $0.0065
...

======================================================================
EXECUTION SUMMARY
======================================================================
Total playlists:     7
Successful:          7
Failed:              0
Total cost:          $0.0230
Total time:          45.2s

Output files:        7 playlists
Decision log:        logs/decisions/decisions_20251006T143000123456.jsonl
======================================================================
```

---

## Data Models

Module: `src.ai_playlist.models`

Core dataclasses for the AI playlist system.

### Key Models

#### `DaypartSpec`

Structured specification for a radio programming time block.

**Fields**:
- `name` (str): Daypart name (max 100 chars)
- `day` (str): Day of week (Monday-Sunday)
- `time_range` (Tuple[str, str]): Start/end time in 24-hour format ("HH:MM")
- `bpm_progression` (Dict[str, Tuple[int, int]]): Time slot → (min BPM, max BPM)
- `genre_mix` (Dict[str, float]): Genre → percentage (0.0-1.0)
- `era_distribution` (Dict[str, float]): Era → percentage (0.0-1.0)
- `australian_min` (float): Minimum Australian content (0.0-1.0)
- `mood` (str): Energy/mood description (max 200 chars)
- `tracks_per_hour` (int): Target tracks per hour

#### `PlaylistSpec`

Generated playlist specification ready for track selection.

**Fields**:
- `id` (str): UUID4 identifier
- `name` (str): Playlist name ({Day}_{ShowName}_{StartTime}_{EndTime})
- `daypart` (DaypartSpec): Source daypart specification
- `target_duration_minutes` (int): Target playlist duration
- `track_criteria` (TrackSelectionCriteria): Selection criteria
- `created_at` (datetime): Creation timestamp

#### `TrackSelectionCriteria`

Multi-dimensional constraint set for LLM track selection.

**Fields**:
- `bpm_range` (Tuple[int, int]): (min BPM, max BPM)
- `bpm_tolerance` (int): BPM tolerance (default: 10)
- `genre_mix` (Dict[str, Tuple[float, float]]): Genre → (min%, max%)
- `genre_tolerance` (float): Genre tolerance (default: 0.05)
- `era_distribution` (Dict[str, Tuple[float, float]]): Era → (min%, max%)
- `era_tolerance` (float): Era tolerance (default: 0.05)
- `australian_min` (float): Minimum Australian content
- `energy_flow` (str): Energy flow description
- `excluded_track_ids` (List[str]): Tracks to exclude

**Methods**:
- `relax_bpm(increment: int = 10)`: Create relaxed criteria with expanded BPM range
- `relax_genre(tolerance: float = 0.05)`: Create relaxed criteria with expanded genre tolerance
- `relax_era(tolerance: float = 0.05)`: Create relaxed criteria with expanded era tolerance

#### `SelectedTrack`

Track selected by LLM with metadata for validation.

**Fields**:
- `track_id` (str): Unique track identifier
- `title` (str): Track title
- `artist` (str): Artist name
- `album` (str): Album name
- `bpm` (Optional[int]): Beats per minute
- `genre` (Optional[str]): Music genre
- `year` (Optional[int]): Release year
- `country` (Optional[str]): Artist country code
- `duration_seconds` (int): Track duration
- `position` (int): Position in playlist
- `selection_reason` (str): Why this track was selected

#### `ValidationResult`

Quality assessment of generated playlist.

**Fields**:
- `constraint_satisfaction` (float): Overall constraint satisfaction (0.0-1.0)
- `bpm_satisfaction` (float): BPM constraint satisfaction (0.0-1.0)
- `genre_satisfaction` (float): Genre constraint satisfaction (0.0-1.0)
- `era_satisfaction` (float): Era constraint satisfaction (0.0-1.0)
- `australian_content` (float): Actual Australian content percentage (0.0-1.0)
- `flow_quality_score` (float): Flow quality score (0.0-1.0)
- `bpm_variance` (float): Average BPM variance between tracks
- `energy_progression` (str): Energy progression classification ("smooth" | "moderate" | "choppy")
- `genre_diversity` (float): Simpson's diversity index (0.0-1.0)
- `gap_analysis` (Dict[str, str]): Constraint → explanation for unmet criteria
- `passes_validation` (bool): True if constraint ≥ 80% AND flow ≥ 70%

**Methods**:
- `is_valid()`: Returns `passes_validation` boolean

#### `Playlist`

Final validated playlist ready for AzuraCast sync.

**Fields**:
- `id` (str): UUID4 identifier (must match spec.id)
- `name` (str): Playlist name
- `tracks` (List[SelectedTrack]): Selected tracks in order
- `spec` (PlaylistSpec): Source playlist specification
- `validation_result` (ValidationResult): Validation results (must pass)
- `created_at` (datetime): Creation timestamp
- `synced_at` (Optional[datetime]): AzuraCast sync timestamp
- `azuracast_id` (Optional[int]): AzuraCast playlist ID

#### `DecisionLog`

Audit trail for playlist generation decisions.

**Fields**:
- `id` (str): UUID4 identifier
- `timestamp` (datetime): Decision timestamp
- `decision_type` (str): Type of decision ("track_selection" | "constraint_relaxation" | "validation" | "sync")
- `playlist_id` (str): Playlist UUID4
- `playlist_name` (str): Playlist name
- `criteria` (Dict): Serialized TrackSelectionCriteria
- `selected_tracks` (List[Dict]): Serialized SelectedTrack objects
- `validation_result` (Dict): Serialized ValidationResult
- `metadata` (Dict): Additional context

**Methods**:
- `to_json()`: Serialize to JSON string
- `from_json(json_str)`: Deserialize from JSON string (class method)

---

## Error Handling

Module: `src.ai_playlist.exceptions`

Custom exceptions for the AI playlist system.

### Exception Hierarchy

```
Exception
├── ParseError              # Document parsing failures
├── ValidationError         # Data validation failures
├── CostExceededError       # LLM cost budget exceeded
├── MCPToolError            # MCP server/tool errors
├── APIError                # OpenAI API errors
└── AzuraCastPlaylistSyncError  # AzuraCast sync failures
```

### Exception Usage

```python
from src.ai_playlist.exceptions import (
    ParseError,
    ValidationError,
    CostExceededError,
    MCPToolError,
    APIError,
)

try:
    # Parse document
    dayparts = parse_programming_document(content)

    # Generate specs
    specs = generate_playlist_specs(dayparts)

    # Select tracks
    response = await select_tracks_with_llm(request)

except ParseError as e:
    print(f"Document parsing failed: {e}")
    print("Check markdown structure and daypart headers")

except ValidationError as e:
    print(f"Validation failed: {e}")
    print("Check BPM ranges, genre percentages, time formats")

except CostExceededError as e:
    print(f"Budget exceeded: {e}")
    print("Increase --max-cost or reduce playlist count")

except MCPToolError as e:
    print(f"MCP server error: {e}")
    print("Verify SUBSONIC_MCP_URL and server availability")

except APIError as e:
    print(f"OpenAI API error: {e}")
    print("Check OPENAI_API_KEY and API status")
```

### Best Practices

1. **Always catch specific exceptions** rather than generic `Exception`
2. **Log exceptions** with full context for debugging
3. **Provide actionable error messages** to users
4. **Use try/except/finally** for resource cleanup (file handles, connections)
5. **Re-raise exceptions** after logging when appropriate

```python
import logging

logger = logging.getLogger(__name__)

try:
    result = await select_tracks_with_llm(request)
except CostExceededError as e:
    logger.error(f"Cost budget exceeded: {e}", exc_info=True)
    # Handle gracefully - maybe reduce track count
    raise
except MCPToolError as e:
    logger.warning(f"MCP tools unavailable: {e}")
    # Retry with fallback
    result = await select_tracks_without_mcp(request)
```

---

## Complete Workflow Example

Here's a complete example tying all components together:

```python
import asyncio
from pathlib import Path
from datetime import datetime

from src.ai_playlist.document_parser import parse_programming_document
from src.ai_playlist.playlist_planner import generate_playlist_specs
from src.ai_playlist.openai_client import get_client
from src.ai_playlist.track_selector import select_tracks_with_llm
from src.ai_playlist.validator import validate_playlist
from src.ai_playlist.azuracast_sync import sync_playlist_to_azuracast
from src.ai_playlist.decision_logger import DecisionLogger
from src.ai_playlist.models import Playlist

async def generate_playlists(input_file: str, output_dir: str):
    """Generate playlists from programming document."""

    # Initialize decision logger
    logger = DecisionLogger(log_dir=Path("logs/decisions"))

    # 1. Parse programming document
    print("Parsing programming document...")
    with open(input_file) as f:
        content = f.read()

    dayparts = parse_programming_document(content)
    print(f"Parsed {len(dayparts)} dayparts")

    # 2. Generate playlist specifications
    print("Generating playlist specifications...")
    playlist_specs = generate_playlist_specs(dayparts)
    print(f"Generated {len(playlist_specs)} playlist specs")

    # 3. Initialize OpenAI client
    client = get_client()

    # 4. Process each playlist
    successful_playlists = []

    for i, spec in enumerate(playlist_specs, 1):
        print(f"\n[{i}/{len(playlist_specs)}] Processing {spec.name}...")

        try:
            # Create LLM request
            request = client.create_selection_request(spec)

            # Select tracks
            print(f"  Selecting tracks (target: {request.target_track_count})...")
            response = await select_tracks_with_llm(request)
            print(f"  Selected {len(response.selected_tracks)} tracks")
            print(f"  Cost: ${response.cost_usd:.6f}, Time: {response.execution_time_seconds:.2f}s")

            # Validate playlist
            print(f"  Validating...")
            validation_result = validate_playlist(
                tracks=response.selected_tracks,
                criteria=request.criteria
            )

            print(f"  Constraint satisfaction: {validation_result.constraint_satisfaction:.1%}")
            print(f"  Flow quality: {validation_result.flow_quality_score:.1%}")
            print(f"  Validation: {'PASSED' if validation_result.passes_validation else 'FAILED'}")

            # Log decision
            logger.log_decision(
                decision_type="track_selection",
                playlist_name=spec.name,
                criteria={
                    "bpm_range": list(request.criteria.bpm_range),
                    "genre_mix": {k: list(v) for k, v in request.criteria.genre_mix.items()},
                    "australian_min": request.criteria.australian_min,
                },
                selected_tracks=[
                    {
                        "track_id": t.track_id,
                        "title": t.title,
                        "artist": t.artist,
                        "bpm": t.bpm,
                        "country": t.country,
                    }
                    for t in response.selected_tracks
                ],
                validation_result={
                    "constraint_satisfaction": validation_result.constraint_satisfaction,
                    "flow_quality_score": validation_result.flow_quality_score,
                    "passes_validation": validation_result.passes_validation,
                },
                metadata={
                    "playlist_id": spec.id,
                    "llm_cost_usd": response.cost_usd,
                    "execution_time_seconds": response.execution_time_seconds,
                }
            )

            if validation_result.passes_validation:
                # Create playlist object
                playlist = Playlist(
                    id=spec.id,
                    name=spec.name,
                    tracks=response.selected_tracks,
                    spec=spec,
                    validation_result=validation_result,
                    created_at=datetime.now()
                )

                # Sync to AzuraCast
                print(f"  Syncing to AzuraCast...")
                synced_playlist = await sync_playlist_to_azuracast(playlist)
                print(f"  Synced (AzuraCast ID: {synced_playlist.azuracast_id})")

                successful_playlists.append(synced_playlist)
            else:
                print(f"  Skipped sync (validation failed)")

        except Exception as e:
            print(f"  ERROR: {e}")
            continue

    # 5. Summary
    print(f"\n{'='*70}")
    print(f"SUMMARY")
    print(f"{'='*70}")
    print(f"Total playlists: {len(playlist_specs)}")
    print(f"Successful: {len(successful_playlists)}")
    print(f"Failed: {len(playlist_specs) - len(successful_playlists)}")
    print(f"Decision log: {logger.get_log_file()}")
    print(f"{'='*70}")

    return successful_playlists

# Run automation
if __name__ == "__main__":
    playlists = asyncio.run(generate_playlists(
        input_file="station-identity.md",
        output_dir="playlists/"
    ))
```

---

## Additional Resources

- **Specification**: `/workspaces/emby-to-m3u/specs/004-build-ai-ml/`
- **Tests**: `/workspaces/emby-to-m3u/tests/ai_playlist/`
- **Source Code**: `/workspaces/emby-to-m3u/src/ai_playlist/`
- **Decision Logs**: `/workspaces/emby-to-m3u/logs/decisions/`

---

**Last Updated**: 2025-10-06
**Version**: 1.0.0
