# Station Identity Path Environment Variable Design

**Date:** 2025-10-20
**Status:** Approved
**Implementation Branch:** TBD

## Problem Statement

The `station-identity.md` file path is currently hardcoded in multiple locations throughout the codebase:
- CLI requires `--input` as a required argument
- Scripts have hardcoded paths like `project_root / "station-identity.md"`
- Integration tests use absolute paths like `/workspaces/emby-to-m3u/station-identity.md`
- Shell scripts reference `$WORKSPACE/station-identity.md`

This creates several issues:
1. Docker containers can't easily use different mount paths
2. Tests can't easily swap between fixtures and real config
3. Configuration pattern is inconsistent with other env vars (OPENAI_KEY, SUBSONIC_URL)

## Goals

1. **Docker Flexibility**: Allow containers to use different paths without CLI changes
2. **Testing Convenience**: Enable tests to easily swap between test fixtures and real config
3. **Configuration Consistency**: Match the pattern of other environment variables

## Design

### Architecture: Hybrid Config Module + Backward Compatibility

Create a centralized configuration module with smart defaults, update the CLI to use it, and gradually migrate scripts/tests. This allows:
- Centralized configuration logic
- Incremental migration of existing code
- Immediate benefits for scripts and Docker
- Backward compatibility during transition

### Configuration Precedence

The system will resolve the station identity path using this precedence:

```
1. Explicit path parameter (CLI --input argument)
   ↓ (if not provided)
2. STATION_IDENTITY_PATH environment variable
   ↓ (if not set)
3. Default path based on environment:
   - Docker: /app/station-identity.md
   - Local dev: ./station-identity.md
```

This follows the principle: **Explicit > Environment > Default**

### Core Components

#### 1. Configuration Module (`src/ai_playlist/config.py`)

**New function:**
```python
def get_station_identity_path(explicit_path: Optional[str] = None) -> Path:
    """
    Get station identity file path with precedence handling.

    Precedence:
    1. explicit_path parameter (from CLI --input)
    2. STATION_IDENTITY_PATH environment variable
    3. Default: /app/station-identity.md (Docker) or ./station-identity.md (local)

    Args:
        explicit_path: Explicit path provided (e.g., from CLI argument)

    Returns:
        Path: Resolved path to station-identity.md

    Raises:
        FileNotFoundError: If resolved path doesn't exist
    """
```

**Features:**
- Handles absolute and relative paths
- Validates file exists with clear error messages
- Detects Docker environment (checks for `/app` directory)
- Returns `pathlib.Path` object for consistency

#### 2. CLI Updates (`src/ai_playlist/cli.py`)

**Changes:**
- Make `--input` argument **optional** instead of required
- Update argument help text to mention environment variable
- Call `get_station_identity_path(args.input)` to resolve path
- Update example in epilog

**Before:**
```python
parser.add_argument(
    "--input",
    type=str,
    required=True,  # ← Remove required
    help="Path to programming document (station-identity.md)",
)
```

**After:**
```python
parser.add_argument(
    "--input",
    type=str,
    required=False,  # ← Now optional
    help="Path to programming document (station-identity.md). "
         "Defaults to STATION_IDENTITY_PATH env var or ./station-identity.md",
)
```

#### 3. Python Scripts Migration

**Scripts to update:**
- `scripts/deploy_playlists.py` (line 151)
- `scripts/deploy_real_playlists.py` (lines 67, 167)
- `scripts/generate_full_week.py` (lines 169-178)

**Pattern:**
```python
# Before
station_identity_path = Path(__file__).parent.parent / "station-identity.md"

# After
from src.ai_playlist.config import get_station_identity_path
station_identity_path = get_station_identity_path()
```

#### 4. Integration Tests Migration

**Tests to update:**
- `tests/integration/test_main_workflow.py`
- `tests/integration/test_ai_playlist_generation.py`
- `tests/integration/test_batch_playlist_generation.py`
- `tests/integration/test_bpm_progression_validation.py`
- `tests/integration/test_cost_budget_hard_limit.py`
- `tests/integration/test_cost_budget_warning_mode.py`
- `tests/integration/test_station_identity_parsing.py`

**Pattern:**
```python
# Before
station_identity_path = Path("/workspaces/emby-to-m3u/station-identity.md")

# After
from src.ai_playlist.config import get_station_identity_path
station_identity_path = get_station_identity_path()

# Or in tests that need fixtures:
# Set environment variable in test setup
os.environ["STATION_IDENTITY_PATH"] = str(fixtures_dir / "sample_station_identity.md")
station_identity_path = get_station_identity_path()
```

#### 5. Shell Scripts Updates

**File:** `scripts/autonomous_pipeline_coordinator.sh`

**Update line 130-136:**
```bash
# Before
if [[ ! -f "$WORKSPACE/station-identity.md" ]]; then
    log "ERROR: station-identity.md not found"
    exit 1
fi

# After
STATION_IDENTITY="${STATION_IDENTITY_PATH:-$WORKSPACE/station-identity.md}"
if [[ ! -f "$STATION_IDENTITY" ]]; then
    log "ERROR: station-identity.md not found at $STATION_IDENTITY"
    exit 1
fi
```

#### 6. Documentation Updates

**File:** `docs/environment-variables.md`

Add new section after Subsonic configuration:

```markdown
## Station Identity Configuration

### STATION_IDENTITY_PATH (Optional)
- **Description**: Path to station identity markdown file
- **Format**: Absolute or relative file path
- **Default**:
  - Docker: `/app/station-identity.md`
  - Local: `./station-identity.md`
- **Example**: `STATION_IDENTITY_PATH=/config/my-station.md`
- **Notes**:
  - CLI `--input` argument takes precedence if provided
  - Useful for Docker volume mounts at custom paths
  - Enables test fixtures without code changes
```

**File:** `.env.example`

Add line:
```bash
# Station Identity (optional - defaults to ./station-identity.md)
STATION_IDENTITY_PATH=./station-identity.md
```

## Implementation Strategy

### Phase 1: Core Infrastructure (Required for PR)
1. Create `src/ai_playlist/config.py` with `get_station_identity_path()`
2. Write comprehensive tests for config module
3. Update CLI to use config module (make --input optional)
4. Update documentation (environment-variables.md, .env.example)

### Phase 2: Python Scripts Migration (Required for PR)
5. Update `scripts/deploy_playlists.py`
6. Update `scripts/deploy_real_playlists.py`
7. Update `scripts/generate_full_week.py`

### Phase 3: Integration Tests (Required for PR)
8. Update all integration tests to use config module
9. Verify tests still pass with environment variable

### Phase 4: Shell Scripts (Required for PR)
10. Update `scripts/autonomous_pipeline_coordinator.sh`

### Phase 5: Validation (Required for PR)
11. Test Docker build with default path
12. Test Docker run with custom STATION_IDENTITY_PATH
13. Test CLI with no args (should use env var or default)
14. Test CLI with --input (should override env var)
15. Verify all integration tests pass

## Testing Plan

### Unit Tests (`tests/unit/test_config.py`)
- Test precedence: explicit > env var > default
- Test Docker environment detection
- Test relative vs absolute paths
- Test file not found error handling
- Test environment variable validation

### Integration Tests
- Verify existing integration tests work with config module
- Add test with STATION_IDENTITY_PATH set to fixture file
- Verify CLI --input still overrides environment variable

### Docker Tests
- Build with default path (should use station-identity.example.md copied to station-identity.md)
- Run with `-e STATION_IDENTITY_PATH=/custom/path.md` (should use custom path)
- Run with volume mount and custom env var

## Success Criteria

1. ✅ `STATION_IDENTITY_PATH` environment variable works in all contexts
2. ✅ CLI `--input` argument still works and takes precedence
3. ✅ Default path works in Docker (`/app/station-identity.md`)
4. ✅ Default path works locally (`./station-identity.md`)
5. ✅ All integration tests pass
6. ✅ Documentation is complete and accurate
7. ✅ No breaking changes to existing workflows

## Backward Compatibility

This design maintains full backward compatibility:
- Existing CLI usage with `--input` continues to work unchanged
- Scripts can be migrated incrementally (old hardcoded paths still work)
- Docker containers work with default path (no changes needed)
- Tests continue to work during migration

## Security Considerations

- Path validation prevents directory traversal attacks
- File existence check prevents crashes from missing files
- Clear error messages help users diagnose configuration issues
- No secrets stored in environment variable (just a file path)

## Future Enhancements (Out of Scope)

- Support for multiple station identity files (multi-station support)
- URL support (fetch station identity from remote source)
- Hot reload when file changes
- Schema validation of station identity content

## References

- Current hardcoded paths: grep results from initial investigation
- Environment variable pattern: `docs/environment-variables.md`
- Docker configuration: `Dockerfile` line 28
- CLI implementation: `src/ai_playlist/cli.py`
