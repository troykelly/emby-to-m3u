# Tasks: Main Application Integration - Wire Phase 4.9 APIs

**Feature Branch**: `005-refactor-core-playlist`
**Created**: 2025-10-07
**Purpose**: Integrate Phase 4.9 orchestration APIs (generate_playlist, generate_batch, budget_allocation) into main application workflow
**Dependencies**: Phase 4.9 complete (T083-T085), all components individually verified

---

## Context

Phase 4.9 successfully implemented all orchestration APIs:
- ✅ OpenAIClient.generate_playlist() - Main playlist orchestrator (~200 lines)
- ✅ BatchPlaylistGenerator.generate_batch() - Multi-daypart batch generation (~130 lines)
- ✅ BatchPlaylistGenerator.calculate_budget_allocation() - Budget distribution (~60 lines)

**Problem**: These APIs are NOT wired into `src/ai_playlist/main.py`, which means:
- CLI cannot generate playlists end-to-end
- workflow.py uses outdated function-based APIs instead of Phase 4.9 methods
- Document parsing returns wrong type (StationIdentityDocument vs dayparts list)
- Missing Subsonic track fetching in main workflow

**End-to-End Test Verified**: Created `/tmp/test_end_to_end_playlist.py` successfully demonstrates:
1. Parse station-identity.md → StationIdentityDocument
2. Extract dayparts from programming structures
3. Connect to Subsonic and fetch 500 tracks
4. Initialize BatchPlaylistGenerator with budget
5. Generate 2 playlists (19 and 36 tracks each, $0.0044 total)
6. All components work together correctly

**Goal**: Wire Phase 4.9 APIs into main.py so `python -m src.ai_playlist --input station-identity.md --output playlists/` works end-to-end.

---

## Phase 5.1: Main Workflow Integration (6 tasks)

### T086 [P] Update main.py to use StationIdentityDocument API correctly

**Problem**: Line 106 calls `parse_programming_document(content)` expecting list of dayparts, but function returns `StationIdentityDocument` object

**Current Code** (`src/ai_playlist/main.py` lines 100-125):
```python
content = load_programming_document(input_file)
dayparts = parse_programming_document(content)  # ❌ Returns StationIdentityDocument, not list
logger.info("Parsed %d dayparts from document", len(dayparts))  # ❌ Will fail
```

**Required Fix**:
```python
from pathlib import Path
from .document_parser import DocumentParser

# Parse station identity document (returns StationIdentityDocument)
parser = DocumentParser()
station_identity = parser.load_document(Path(input_file))

# Extract dayparts from programming structures
weekday_structure = next(
    (s for s in station_identity.programming_structures if s.schedule_type.value == "weekday"),
    None
)
if not weekday_structure:
    raise ValueError("No weekday programming structure found")

dayparts = weekday_structure.dayparts
logger.info("Parsed %d weekday dayparts from document", len(dayparts))
```

**Files Modified**:
- `src/ai_playlist/main.py` (lines 100-125)

**Success Criteria**:
- Station identity parses without error
- Dayparts list correctly extracted
- All daypart objects have required fields (name, time_start, time_end, genre_mix, etc.)

**Dependencies**: None

**Estimated Time**: 30 minutes

---

### T087 [P] Add Subsonic track fetching to main workflow

**Problem**: Main workflow never fetches available tracks from Subsonic - cannot generate playlists without track library

**Current Code**: Missing entirely (workflow jumps from specs to batch_track_selection)

**Required Implementation** (`src/ai_playlist/main.py` after line 130):
```python
# Step 4.5: Connect to Subsonic and fetch available tracks
logger.info("Step 4.5: Fetching available tracks from Subsonic...")
from .config import get_subsonic_config
from src.subsonic.client import SubsonicClient

subsonic_config = get_subsonic_config()
subsonic_client = SubsonicClient(subsonic_config)

# Verify connection
ping_result = subsonic_client.ping()
if not ping_result:
    raise ConnectionError("Failed to connect to Subsonic server")

# Fetch all available tracks (limit to reasonable number)
available_tracks = subsonic_client.search_tracks(query="", limit=1000)
logger.info("Fetched %d available tracks from Subsonic", len(available_tracks))

if len(available_tracks) < 100:
    logger.warning("Very few tracks available (%d) - playlists may be limited", len(available_tracks))
```

**Add Helper to config.py**:
```python
def get_subsonic_config():
    """Get SubsonicConfig from environment variables."""
    from src.subsonic.models import SubsonicConfig
    return SubsonicConfig(
        url=os.environ['SUBSONIC_URL'],
        username=os.environ['SUBSONIC_USER'],
        password=os.environ['SUBSONIC_PASSWORD']
    )
```

**Files Modified**:
- `src/ai_playlist/main.py` (after line 130, before batch_track_selection)
- `src/ai_playlist/config.py` (add get_subsonic_config helper)

**Success Criteria**:
- Subsonic connection succeeds
- At least 100 tracks fetched
- Tracks have required fields (id, title, artist, genre, year)

**Dependencies**: None

**Estimated Time**: 1 hour

---

### T088 [P] Replace batch_track_selection() with BatchPlaylistGenerator.generate_batch()

**Problem**: Workflow uses old `batch_track_selection()` function instead of Phase 4.9 `BatchPlaylistGenerator.generate_batch()` method

**Current Code** (`src/ai_playlist/main.py` lines 132-140):
```python
playlists = await batch_track_selection(
    playlist_specs=playlist_specs,
    max_cost_usd=max_cost_usd,
    decision_logger=decision_logger,
)
```

**Required Replacement**:
```python
# Initialize batch generator with OpenAI key and budget
from .batch_executor import BatchPlaylistGenerator
from datetime import date
import os

batch_generator = BatchPlaylistGenerator(
    openai_api_key=os.environ['OPENAI_KEY'],
    total_budget=max_cost_usd,
    allocation_strategy="dynamic",
    budget_mode="suggested",
    timeout_seconds=90  # Longer timeout for real LLM calls
)

# Set fast model for production (gpt-4o-mini instead of gpt-5)
os.environ['OPENAI_MODEL'] = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')

# Generate all playlists in batch
logger.info("Step 5: Executing batch track selection...")
playlists = await batch_generator.generate_batch(
    dayparts=dayparts,  # From T086
    available_tracks=available_tracks,  # From T087
    generation_date=date.today()
)

logger.info("Track selection complete: %d playlists generated", len(playlists))
```

**Remove Old API**:
- Remove imports of `batch_track_selection` from workflow.py
- Update workflow.py to export only the new methods if needed

**Files Modified**:
- `src/ai_playlist/main.py` (lines 132-140)
- `src/ai_playlist/workflow.py` (remove old batch_track_selection if it conflicts)

**Success Criteria**:
- BatchPlaylistGenerator initializes correctly
- generate_batch() returns list of Playlist objects
- Each playlist has tracks, validation_result, cost_actual

**Dependencies**: T086 (dayparts), T087 (available_tracks)

**Estimated Time**: 1 hour

---

### T089 Fix playlist validation to use new ValidationResult API

**Problem**: Line 154 calls `playlist.validation_result.is_valid()` but ValidationResult has `overall_status` enum, not `is_valid()` method

**Current Code** (`src/ai_playlist/main.py` lines 152-170):
```python
for playlist in playlists:
    if playlist.validation_result.is_valid():  # ❌ No is_valid() method
        successful_playlists.append(playlist)
```

**Required Fix**:
```python
from .models.validation import ValidationStatus

for playlist in playlists:
    status = playlist.validation_result.overall_status

    if status == ValidationStatus.PASS:
        successful_playlists.append(playlist)
        logger.info(
            "✓ Playlist %s validated (status: PASS, compliance: %.1f%%)",
            playlist.name,
            playlist.validation_result.compliance_percentage * 100
        )
    elif status == ValidationStatus.WARNING:
        successful_playlists.append(playlist)  # Accept warnings
        logger.warning(
            "⚠ Playlist %s validated with warnings (compliance: %.1f%%)",
            playlist.name,
            playlist.validation_result.compliance_percentage * 100
        )
    else:  # FAIL
        failed_playlists.append(playlist)
        logger.error(
            "✗ Playlist %s failed validation (compliance: %.1f%%)",
            playlist.name,
            playlist.validation_result.compliance_percentage * 100
        )
```

**Files Modified**:
- `src/ai_playlist/main.py` (lines 152-170)

**Success Criteria**:
- Validation logic uses correct API
- Warnings accepted as successful
- Failed playlists properly logged

**Dependencies**: T088 (playlists must exist)

**Estimated Time**: 30 minutes

---

### T090 Fix cost calculation to use actual Playlist.cost_actual

**Problem**: Lines 143-149 use placeholder cost calculation instead of actual LLM costs from playlists

**Current Code**:
```python
total_cost = (
    sum(
        playlist.spec.track_criteria.bpm_tolerance * 0.01  # ❌ Wrong calculation
        for playlist in playlists
    )
    * 0.01
)
```

**Required Fix**:
```python
# Calculate actual total cost from playlists
total_cost = float(sum(playlist.cost_actual for playlist in playlists))

logger.info(
    "Total generation cost: $%.4f / $%.2f budget (%.1f%% utilized)",
    total_cost,
    max_cost_usd,
    (total_cost / max_cost_usd) * 100 if max_cost_usd > 0 else 0
)
```

**Files Modified**:
- `src/ai_playlist/main.py` (lines 143-149)

**Success Criteria**:
- Cost calculated from actual LLM API costs
- Budget utilization percentage logged
- Decimal precision maintained

**Dependencies**: T088 (playlists must have cost_actual)

**Estimated Time**: 15 minutes

---

### T091 Update save_playlist_file() to handle Playlist objects correctly

**Problem**: save_playlist_file() may expect different format than Phase 4.9 Playlist objects

**Investigation Required**:
1. Read `src/ai_playlist/workflow.py` save_playlist_file() implementation
2. Check if it handles Playlist dataclass correctly
3. Verify M3U export uses playlist.to_m3u() method
4. Ensure JSON metadata export includes all Phase 4.9 fields

**Expected Implementation**:
```python
def save_playlist_file(playlist: Playlist, output_path: Path) -> Path:
    """Save playlist to M3U file with JSON metadata."""
    from datetime import datetime
    import json

    # Generate filename from playlist name
    safe_name = playlist.name.lower().replace(" ", "-").replace(":", "")
    m3u_file = output_path / f"{safe_name}.m3u"
    json_file = output_path / f"{safe_name}.json"

    # Export M3U playlist
    with open(m3u_file, 'w') as f:
        f.write(playlist.to_m3u())

    # Export JSON metadata
    metadata = {
        "id": playlist.id,
        "name": playlist.name,
        "tracks": [
            {
                "track_id": track.track_id,
                "position": track.position_in_playlist,
                "title": track.title,
                "artist": track.artist,
                "album": track.album,
                "duration_seconds": track.duration_seconds,
                "selection_reason": track.selection_reasoning
            }
            for track in playlist.tracks
        ],
        "validation": {
            "status": playlist.validation_result.overall_status.value,
            "compliance_percentage": playlist.validation_result.compliance_percentage,
            "gap_analysis": playlist.validation_result.gap_analysis
        },
        "cost_actual": str(playlist.cost_actual),
        "generation_time_seconds": playlist.generation_time_seconds,
        "created_at": playlist.created_at.isoformat()
    }

    with open(json_file, 'w') as f:
        json.dump(metadata, f, indent=2)

    return m3u_file
```

**Files Modified**:
- `src/ai_playlist/workflow.py` (save_playlist_file function)
- `src/ai_playlist/main.py` (verify usage at line 177)

**Success Criteria**:
- M3U files generated correctly
- JSON metadata contains all Phase 4.9 fields
- Files saved to output directory
- No serialization errors

**Dependencies**: T088 (Playlist objects), T089 (validation)

**Estimated Time**: 1-2 hours

---

## Phase 5.2: CLI Verification (2 tasks)

### T092 Create integration test for complete CLI workflow

**Purpose**: Verify end-to-end CLI execution with minimal test data

**Test File**: `tests/integration/test_cli_e2e.py`

**Test Implementation**:
```python
import pytest
import tempfile
from pathlib import Path
from src.ai_playlist.main import run_automation

@pytest.mark.asyncio
async def test_cli_full_workflow_minimal():
    """Test complete CLI workflow with 2 dayparts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)

        # Run automation
        summary = await run_automation(
            input_file="/workspaces/emby-to-m3u/station-identity.md",
            output_dir=str(output_dir),
            max_cost_usd=5.0,
            dry_run=True  # Don't actually sync to AzuraCast
        )

        # Verify summary
        assert summary['playlist_count'] >= 1
        assert summary['success_count'] >= 1
        assert summary['total_cost'] <= 5.0
        assert len(summary['output_files']) >= 1

        # Verify files exist
        m3u_files = list(output_dir.glob("*.m3u"))
        assert len(m3u_files) >= 1, "No M3U files generated"

        json_files = list(output_dir.glob("*.json"))
        assert len(json_files) >= 1, "No JSON metadata files generated"

@pytest.mark.asyncio
async def test_cli_workflow_with_azuracast_sync():
    """Test complete workflow including AzuraCast sync."""
    # Similar to above but with dry_run=False
    # Verify sync_results in summary
    pass
```

**Success Criteria**:
- Test passes with minimal data (1-2 playlists)
- All files generated correctly
- Summary dict has correct structure

**Dependencies**: T086-T091 (all main.py fixes)

**Estimated Time**: 1 hour

---

### T093 Manual CLI test with full station identity

**Purpose**: Verify CLI works with complete station-identity.md (all 6 weekday dayparts)

**Manual Test Commands**:
```bash
# Set environment variables
export SUBSONIC_URL="<url>"
export SUBSONIC_USER="<user>"
export SUBSONIC_PASSWORD="<password>"
export OPENAI_KEY="<key>"
export OPENAI_MODEL="gpt-4o-mini"  # Use fast model

# Run CLI for weekday playlists
python -m src.ai_playlist \
  --input /workspaces/emby-to-m3u/station-identity.md \
  --output /tmp/playlists/test-run \
  --max-cost 20.00 \
  --dry-run \
  --verbose

# Verify outputs
ls -lh /tmp/playlists/test-run/*.m3u
ls -lh /tmp/playlists/test-run/*.json
ls -lh /tmp/playlists/test-run/logs/decisions/

# Check one playlist
head -50 /tmp/playlists/test-run/*.m3u | head -20
cat /tmp/playlists/test-run/*.json | jq '.validation'
```

**Verification Checklist**:
- [ ] CLI runs without errors
- [ ] All weekday dayparts generate playlists
- [ ] M3U files valid format
- [ ] JSON metadata complete
- [ ] Decision logs created
- [ ] Cost within budget
- [ ] Validation status makes sense

**Success Criteria**:
- Manual test completes successfully
- All verification points pass
- No critical errors in logs

**Dependencies**: T086-T092

**Estimated Time**: 1 hour (includes debugging)

---

## Summary

**Total Tasks**: 8 tasks (6 integration + 2 verification)
**Estimated Time**: 8-10 hours total
**Critical Path**: T086 → T087 → T088 → T089/T090/T091 → T092 → T093

**Parallel Opportunities**:
- T089, T090, T091 can run in parallel after T088 completes

**Success Criteria**:
- ✅ `python -m src.ai_playlist --input station-identity.md --output playlists/` generates complete playlists
- ✅ All Phase 4.9 APIs integrated into main workflow
- ✅ Document parsing returns correct type
- ✅ Subsonic tracks fetched before generation
- ✅ Batch generator uses new API
- ✅ Validation uses correct enum
- ✅ Cost calculated from actual LLM costs
- ✅ Files saved in correct format
- ✅ CLI integration test passes
- ✅ Manual CLI test succeeds

**Expected Output After Integration**:
```bash
$ python -m src.ai_playlist --input station-identity.md --output playlists/ --max-cost 20.00 --dry-run

===============================================================================
AI PLAYLIST AUTOMATION
===============================================================================
Input document:  /workspaces/emby-to-m3u/station-identity.md
Output directory: playlists/
Max cost:        $20.00
Dry run:         True
Started:         2025-10-07 15:30:00
===============================================================================

✓ Loading station identity...
✓ Parsed 6 weekday dayparts from document
✓ Fetching available tracks from Subsonic...
✓ Fetched 1,247 available tracks
✓ Initializing batch playlist generator...
✓ Generating 6 playlists...
  [1/6] Morning Drive: 52 tracks, $3.87, PASS (96.8% compliance) ✓
  [2/6] Midday: 75 tracks, $5.42, PASS (94.2% compliance) ✓
  [3/6] Afternoon Drive: 48 tracks, $3.95, PASS (97.1% compliance) ✓
  [4/6] Evening: 42 tracks, $4.18, WARNING (91.3% compliance) ⚠
  [5/6] Late Night: 84 tracks, $1.82, WARNING (88.9% compliance) ⚠
  [6/6] Overnight: 72 tracks, $0.98, PASS (93.4% compliance) ✓

✓ Total playlists: 6
✓ Successful: 6
✓ Failed: 0
✓ Total cost: $20.22 ($20.00 budget, 101.1% utilized - suggested mode)
✓ Total time: 142.8 seconds
✓ Output files: 6 playlists saved
✓ Decision log: playlists/logs/decisions/

===============================================================================
✅ EXECUTION SUMMARY
===============================================================================
```
