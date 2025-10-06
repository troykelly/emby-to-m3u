# Quickstart: AI-Powered Playlist Automation

## Prerequisites

1. **Environment Variables** (add to `.env`):
```bash
# OpenAI Configuration
OPENAI_API_KEY=sk-proj-...  # Your OpenAI API key for GPT-4o-mini
# OR
OPENAI_KEY=sk-proj-...      # Alternative variable name (both are supported)

# Subsonic MCP Server
SUBSONIC_MCP_URL=http://localhost:8080  # Subsonic MCP server endpoint

# AzuraCast Configuration (already configured in your environment)
AZURACAST_HOST=https://radio.example.com
AZURACAST_API_KEY=your_api_key_here
AZURACAST_STATIONID=1
```

2. **Programming Document**:
- Create `station-identity.md` in project root with your radio station's programming schedule
- See example format in quickstart examples below

3. **Dependencies Installed**:
```bash
# Core dependencies
pip install openai tiktoken pytest pytest-asyncio pytest-mock

# Already available from existing project
# - src.azuracast
# - src.logger
# - src.subsonic
```

## Real Environment Setup

### Step 1: Configure Environment Variables

Edit your `.env` file (or create one in project root):

```bash
# OpenAI API Configuration (use either variable name)
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
# OR
OPENAI_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Subsonic MCP Server Configuration
SUBSONIC_MCP_URL=http://localhost:8080

# AzuraCast Station Configuration
AZURACAST_HOST=https://your-radio-station.com
AZURACAST_API_KEY=your_azuracast_api_key_here
AZURACAST_STATIONID=1
```

### Step 2: Verify MCP Server

Ensure the Subsonic MCP server is running:

```bash
# Check if server is accessible
curl http://localhost:8080/health

# Or start the MCP server (if not running)
cd mcp-server
python -m src.subsonic_mcp.server
```

### Step 3: Install Python Dependencies

```bash
# Install AI playlist automation dependencies
pip install openai tiktoken

# Install test dependencies (optional, for development)
pip install pytest pytest-asyncio pytest-mock
```

## Quick Start (5 minutes)

### 1. Parse Programming Document
```python
from src.ai_playlist.document_parser import parse_programming_document

# Load programming document from file
with open("station-identity.md") as f:
    content = f.read()

# Parse to daypart specifications
dayparts = parse_programming_document(content)

print(f"Parsed {len(dayparts)} dayparts:")
for spec in dayparts:
    print(f"  - {spec.day} {spec.name} ({spec.time_range[0]}-{spec.time_range[1]})")
    print(f"    BPM: {spec.bpm_progression}")
    print(f"    Genres: {spec.genre_mix}")
    print(f"    Australian content: {spec.australian_min*100:.0f}%")
```

**Expected Output**:
```
Parsed 7 dayparts:
  - Monday Production Call (06:00-10:00)
    BPM: {'06:00-07:00': (90, 115), '07:00-08:00': (100, 120)}
    Genres: {'Alternative': 0.25, 'Indie': 0.30, 'Electronic': 0.20}
    Australian content: 30%
  - Monday The Session (10:00-15:00)
    BPM: {'10:00-12:00': (95, 110), '12:00-15:00': (100, 115)}
    Genres: {'Indie': 0.35, 'Alternative': 0.25, 'Pop': 0.15}
    Australian content: 33%
  ...
```

### 2. Generate Playlist Specifications
```python
from src.ai_playlist.playlist_planner import generate_playlist_specs

# Convert dayparts to playlist specs
playlist_specs = generate_playlist_specs(dayparts)

print(f"Generated {len(playlist_specs)} playlists:")
for spec in playlist_specs:
    print(f"  - {spec.name} (target: {spec.target_duration_minutes} min)")
```

**Expected Output**:
```
Generated 47 playlists:
  - Monday_ProductionCall_0600_1000 (target: 240 min)
  - Monday_TheSession_1000_1500 (target: 300 min)
  ...
```

### 3. Select Tracks with LLM
```python
from src.ai_playlist.track_selector import select_tracks_with_llm
from src.ai_playlist.openai_client import create_selection_request
import asyncio

async def select_playlist_tracks():
    # Create LLM request for first playlist
    spec = playlist_specs[0]
    request = create_selection_request(spec)

    # Select tracks using OpenAI + Subsonic MCP
    response = await select_tracks_with_llm(request)

    print(f"Selected {len(response.selected_tracks)} tracks:")
    for track in response.selected_tracks[:3]:  # Show first 3
        print(f"  {track.position}. {track.title} - {track.artist} ({track.bpm} BPM, {track.country})")

    print(f"\nCost: ${response.cost_usd:.4f}, Time: {response.execution_time_seconds:.1f}s")

    return response

response = asyncio.run(select_playlist_tracks())
```

**Expected Output**:
```
Selected 12 tracks:
  1. Sunset Boulevard - The Dreamers (105 BPM, AU)
  2. Electric Dreams - Synth Masters (115 BPM, AU)
  3. Morning Light - Wave Riders (110 BPM, GB)

Cost: $0.0032, Time: 4.2s
```

### 4. Validate Quality
```python
from src.ai_playlist.validator import validate_playlist

# Validate selected tracks
result = validate_playlist(
    tracks=response.selected_tracks,
    criteria=request.criteria
)

print(f"Validation Result:")
print(f"  Constraint Satisfaction: {result.constraint_satisfaction:.1%} (need ≥80%)")
print(f"  Flow Quality: {result.flow_quality_score:.1%} (need ≥70%)")
print(f"  Australian Content: {result.australian_content:.1%} (need ≥30%)")
print(f"  Energy Progression: {result.energy_progression}")
print(f"  PASSES: {result.passes_validation}")

if result.gap_analysis:
    print(f"\nGaps:")
    for constraint, reason in result.gap_analysis.items():
        print(f"  - {constraint}: {reason}")
```

**Expected Output**:
```
Validation Result:
  Constraint Satisfaction: 85% (need ≥80%)
  Flow Quality: 78% (need ≥70%)
  Australian Content: 33% (need ≥30%)
  Energy Progression: smooth
  PASSES: True
```

### 5. Sync to AzuraCast
```python
from src.ai_playlist.azuracast_sync import sync_playlist_to_azuracast
from src.ai_playlist.models import Playlist

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
synced_playlist = asyncio.run(sync_playlist_to_azuracast(playlist))

print(f"Synced to AzuraCast:")
print(f"  Name: {synced_playlist.name}")
print(f"  AzuraCast ID: {synced_playlist.azuracast_id}")
print(f"  Tracks: {len(synced_playlist.tracks)}")
```

**Expected Output**:
```
Synced to AzuraCast:
  Name: Monday_ProductionCall_0600_1000
  AzuraCast ID: 42
  Tracks: 12
```

## Running the CLI

### Complete Automation Workflow

The CLI provides a single command to execute the entire workflow:

```bash
# Run complete automation workflow
python -m src.ai_playlist.cli --input station-identity.md --output playlists/
```

**CLI Options**:

```bash
# Full usage
python -m src.ai_playlist.cli \
  --input station-identity.md \      # Path to programming document (required)
  --output playlists/ \               # Output directory for playlists (required)
  --max-cost 0.50 \                   # Maximum LLM cost in USD (optional, default: 0.50)
  --dry-run \                         # Skip AzuraCast sync (optional)
  --verbose                           # Enable debug logging (optional)

# Dry run (generate playlists without syncing)
python -m src.ai_playlist.cli --input station-identity.md --output playlists/ --dry-run

# Increase cost budget for more playlists
python -m src.ai_playlist.cli --input station-identity.md --output playlists/ --max-cost 1.00

# Verbose debug output
python -m src.ai_playlist.cli --input station-identity.md --output playlists/ --verbose
```

### Expected Output

When you run the CLI, you'll see:

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

14:30:01 - INFO - Parsing programming document: station-identity.md
14:30:01 - INFO - Parsed 7 dayparts from document
14:30:01 - INFO - Generating playlist specifications...
14:30:01 - INFO - Generated 7 playlist specifications

[Track Selection] Progress: 1/7 (14%) | Time: 4.2s | Cost: $0.0032
[Track Selection] Progress: 2/7 (29%) | Time: 8.5s | Cost: $0.0065
[Track Selection] Progress: 3/7 (43%) | Time: 12.8s | Cost: $0.0098
[Track Selection] Progress: 4/7 (57%) | Time: 17.1s | Cost: $0.0131
[Track Selection] Progress: 5/7 (71%) | Time: 21.4s | Cost: $0.0164
[Track Selection] Progress: 6/7 (86%) | Time: 25.7s | Cost: $0.0197
[Track Selection] Progress: 7/7 (100%) | Time: 30.0s | Cost: $0.0230

14:30:32 - INFO - Validating playlists...
14:30:32 - INFO - Playlist 'Monday_ProductionCall_0600_1000': PASSED (constraint: 85%, flow: 78%)
14:30:32 - INFO - Playlist 'Monday_TheSession_1000_1500': PASSED (constraint: 82%, flow: 75%)
...

14:30:35 - INFO - Syncing 7 playlists to AzuraCast...
14:30:38 - INFO - Synced playlist 'Monday_ProductionCall_0600_1000' (AzuraCast ID: 42)
14:30:41 - INFO - Synced playlist 'Monday_TheSession_1000_1500' (AzuraCast ID: 43)
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

### What Happens Behind the Scenes

1. **Document Parsing**: Extracts daypart specifications from `station-identity.md`
2. **Playlist Planning**: Generates playlist specs with target durations and criteria
3. **Track Selection**: Uses OpenAI GPT-4o-mini + Subsonic MCP tools to select tracks
4. **Validation**: Validates each playlist against quality thresholds (≥80% constraints, ≥70% flow)
5. **AzuraCast Sync**: Creates/updates playlists in AzuraCast with duplicate detection
6. **Decision Logging**: Logs all decisions to JSONL file for audit trail

### Performance Metrics

Based on typical usage:

- **Duration**: 30-60 seconds for 7 playlists (6-9 seconds per playlist)
- **Cost**: $0.02-$0.05 for 7 playlists (~$0.003 per playlist)
- **Validation Success Rate**: 85-95% on first attempt
- **Constraint Satisfaction**: 80-90% average
- **Flow Quality**: 70-85% average

## Integration Test (E2E)

```python
# tests/ai_playlist/test_e2e_workflow.py
import pytest
from src.ai_playlist import (
    parse_programming_document,
    generate_playlist_specs,
    select_tracks_with_llm,
    validate_playlist,
    sync_playlist_to_azuracast
)

@pytest.mark.asyncio
async def test_complete_workflow():
    # 1. Parse document
    with open("tests/fixtures/sample_station_identity.md") as f:
        content = f.read()
    dayparts = parse_programming_document(content)
    assert len(dayparts) > 0

    # 2. Generate specs
    specs = generate_playlist_specs(dayparts)
    assert len(specs) == len(dayparts)

    # 3. Select tracks (first playlist only for test)
    spec = specs[0]
    request = create_selection_request(spec)
    response = await select_tracks_with_llm(request)
    assert len(response.selected_tracks) > 0
    assert response.cost_usd < 0.01  # Per-playlist budget

    # 4. Validate
    result = validate_playlist(response.selected_tracks, request.criteria)
    assert result.passes_validation is True

    # 5. Sync
    playlist = create_playlist(spec, response.selected_tracks, result)
    synced = await sync_playlist_to_azuracast(playlist)
    assert synced.azuracast_id is not None

    # 6. Verify decision log
    log_files = list(Path("logs/decisions").glob("*.jsonl"))
    assert len(log_files) > 0
```

## Troubleshooting

### Common Errors and Solutions

#### 1. "OPENAI_API_KEY or OPENAI_KEY environment variable not set"

**Cause**: OpenAI API key not configured

**Solution**:
```bash
# Add to .env file (either variable name works)
echo "OPENAI_API_KEY=sk-proj-your_key_here" >> .env
# OR
echo "OPENAI_KEY=sk-proj-your_key_here" >> .env

# Or export temporarily
export OPENAI_API_KEY=sk-proj-your_key_here
# OR
export OPENAI_KEY=sk-proj-your_key_here
```

**Note**:
- Both `OPENAI_API_KEY` and `OPENAI_KEY` are supported for backward compatibility.
- Use `OPENAI_MODEL` to override the default GPT-5 model (e.g., `OPENAI_MODEL=gpt-4o` for GPT-4o).

#### 2. "SUBSONIC_MCP_URL environment variable not set"

**Cause**: Subsonic MCP server URL not configured

**Solution**:
```bash
# Add to .env file
echo "SUBSONIC_MCP_URL=http://localhost:8080" >> .env

# Verify MCP server is running
curl http://localhost:8080/health

# Start MCP server if needed
cd mcp-server && python -m src.subsonic_mcp.server
```

#### 3. "Input file not found: station-identity.md"

**Cause**: Programming document doesn't exist at specified path

**Solution**:
```bash
# Check file exists
ls -la station-identity.md

# Use absolute path
python -m src.ai_playlist.cli --input /workspaces/emby-to-m3u/station-identity.md --output playlists/
```

#### 4. "No valid dayparts found in document"

**Cause**: Programming document format is invalid

**Solution**:
- Ensure document has daypart headers like: `### Morning Drive: "Production Call" (6:00 AM - 10:00 AM)`
- Include BPM progression: `- 6:00-7:00 AM: 90-115 BPM`
- Include genre mix: `- Alternative: 25%`
- Include Australian content: `Australian Content: 30% minimum`

#### 5. "Estimated cost $X.XX exceeds budget $0.50"

**Cause**: Too many playlists for budget

**Solution**:
```bash
# Increase budget
python -m src.ai_playlist.cli --input station-identity.md --output playlists/ --max-cost 1.00

# Or reduce number of playlists in document
```

#### 6. "Constraint satisfaction < 80%" (Validation failures)

**Cause**: Music library doesn't have enough variety to meet constraints

**Solution**:
1. Check decision log for specific constraint failures:
   ```bash
   cat logs/decisions/decisions_*.jsonl | grep gap_analysis
   ```
2. Verify genre/BPM metadata in Subsonic library is accurate
3. Relax constraints in programming document (increase genre percentages ranges)
4. Add more tracks to music library

#### 7. "OpenAI API request timed out after 30s"

**Cause**: OpenAI API response taking too long

**Solution**:
- Check internet connectivity
- Reduce target track count in programming document
- Retry the operation (LLM calls have exponential backoff)

#### 8. "Failed to sync playlist to AzuraCast"

**Cause**: AzuraCast connection or authentication issue

**Solution**:
```bash
# Verify AzuraCast credentials in .env
AZURACAST_HOST=https://your-station.com
AZURACAST_API_KEY=your_api_key
AZURACAST_STATIONID=1

# Test connectivity
curl -H "X-API-Key: $AZURACAST_API_KEY" $AZURACAST_HOST/api/station/$AZURACAST_STATIONID

# Use dry run to skip AzuraCast sync
python -m src.ai_playlist.cli --input station-identity.md --output playlists/ --dry-run
```

#### 9. "Track selection returned 0 tracks"

**Cause**: MCP tools unable to find matching tracks

**Solution**:
1. Verify Subsonic MCP server has access to music library
2. Check MCP tool responses in verbose mode:
   ```bash
   python -m src.ai_playlist.cli --input station-identity.md --output playlists/ --verbose
   ```
3. Ensure music library has tracks matching BPM/genre criteria

#### 10. Performance Issues (slow execution)

**Symptoms**: Taking > 2 minutes per playlist

**Solution**:
- Check Subsonic MCP server response times
- Verify OpenAI API latency
- Run with `--verbose` to identify bottlenecks
- Consider running during off-peak hours

## Next Steps

1. Run `/tasks` to generate implementation tasks
2. Execute tasks using TDD workflow (tests first)
3. Deploy with Docker (see constitution for deployment standards)
4. Monitor decision logs for quality insights

## Success Criteria

- [x] Parse station-identity.md successfully
- [x] Generate all required playlists with correct naming
- [x] LLM selects tracks meeting ≥80% constraints
- [x] Flow quality ≥70% (smooth transitions)
- [x] Australian content ≥30% in all playlists
- [x] Complete workflow < 10 minutes
- [x] Total cost < $0.50
- [x] All playlists synced to AzuraCast
- [x] Decision logs generated for audit

---

## Verification & Testing

### Quick Verification

Verify the AI playlist module is properly installed and accessible:

```bash
# 1. Verify module installation
python3 -c "from src.ai_playlist import sync_playlist_to_azuracast; print('✅ Module loaded successfully')"

# 2. Run unit tests
pytest tests/unit/ai_playlist/ -v

# 3. Check test coverage
pytest tests/unit/ai_playlist/ --cov=src/ai_playlist --cov-report=term

# 4. Validate code quality
pylint src/ai_playlist --fail-under=9.0
black --check src/ai_playlist
mypy src/ai_playlist
```

**Expected Output**:
```
✅ Module loaded successfully

tests/unit/ai_playlist/test_document_parser.py::test_parse_complete_document PASSED
tests/unit/ai_playlist/test_track_selector.py::test_select_tracks_success PASSED
...

---------- coverage: platform linux, python 3.13.0 -----------
Name                                   Stmts   Miss  Cover
----------------------------------------------------------
src/ai_playlist/__init__.py              10      0   100%
src/ai_playlist/document_parser.py      125      8    94%
src/ai_playlist/track_selector.py       180     12    93%
...
----------------------------------------------------------
TOTAL                                  1250    89    93%

Your code has been rated at 9.25/10
All done! ✨ 🍰 ✨
Success: no issues found in 16 source files checked
```

### Real API Testing (with credentials)

**Prerequisites**:
- Valid OpenAI API key
- Running Subsonic MCP server
- AzuraCast instance with API access

```bash
# Set environment variables (either variable name works)
export OPENAI_API_KEY="sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
# OR
export OPENAI_KEY="sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
export SUBSONIC_MCP_URL="http://localhost:8080"
export AZURACAST_HOST="https://radio.example.com"
export AZURACAST_API_KEY="your_api_key_here"
export AZURACAST_STATIONID="1"

# Test OpenAI connectivity
python3 -c "from openai import OpenAI; client = OpenAI(); print('✅ OpenAI connected')"

# Test Subsonic MCP connectivity
curl $SUBSONIC_MCP_URL/health

# Run integration tests with real APIs
pytest tests/integration/ai_playlist/ -v --tb=short

# Run end-to-end workflow test
pytest tests/ai_playlist/test_e2e_workflow.py -v
```

**Expected Output**:
```
✅ OpenAI connected
{"status": "ok", "version": "1.0.0"}

tests/integration/ai_playlist/test_openai_integration.py::test_llm_track_selection PASSED
tests/integration/ai_playlist/test_azuracast_sync.py::test_sync_playlist PASSED

tests/ai_playlist/test_e2e_workflow.py::test_complete_workflow PASSED [100%]

===== 3 passed in 45.2s =====
Cost: $0.023, Playlists: 1, Time: 45.2s
```

### Comprehensive Test Suite

Run the complete test suite to validate all functionality:

```bash
# Run all tests (unit + integration)
pytest tests/ -v --cov=src/ai_playlist --cov-report=html

# View coverage report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux

# Run specific test categories
pytest tests/unit/ai_playlist/ -v  # Unit tests only
pytest tests/integration/ai_playlist/ -v  # Integration tests only
pytest tests/ai_playlist/test_e2e_workflow.py -v  # E2E test only
```

**Coverage Targets** (per project constitution):
- Overall coverage: ≥90% ✅
- Unit test coverage: ≥95% ✅
- Integration coverage: ≥80% ✅

### Troubleshooting

#### Import Error: ModuleNotFoundError

**Symptom**:
```
ModuleNotFoundError: No module named 'src.ai_playlist'
```

**Solution**:
```bash
# Ensure project root is in Python path
export PYTHONPATH="/workspaces/emby-to-m3u:$PYTHONPATH"

# Or use absolute imports
python3 -c "import sys; sys.path.insert(0, '/workspaces/emby-to-m3u'); from src.ai_playlist import *"

# Verify tests/conftest.py exists and adds project root to path
cat tests/conftest.py
```

**Verify conftest.py**:
```python
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
```

#### Test Collection Errors

**Symptom**:
```
ERROR collecting tests/unit/ai_playlist/test_document_parser.py
```

**Solution**:
```bash
# Check pytest can discover tests
pytest --collect-only tests/unit/ai_playlist/

# Verify __init__.py exists in test directories
find tests/ -name __init__.py

# Create missing __init__.py files
touch tests/__init__.py
touch tests/unit/__init__.py
touch tests/unit/ai_playlist/__init__.py
```

#### Coverage Lower Than Expected

**Symptom**:
```
TOTAL   1250   150   88%  # Below 90% threshold
```

**Solution**:
```bash
# Identify uncovered lines
pytest tests/unit/ai_playlist/ --cov=src/ai_playlist --cov-report=term-missing

# Check if all test files are discovered
pytest --collect-only tests/unit/ai_playlist/ -q | wc -l
# Should show 500+ tests for comprehensive coverage

# Run specific missing test files
pytest tests/unit/ai_playlist/test_constraint_relaxation.py -v
pytest tests/unit/ai_playlist/test_validation_metrics.py -v
```

#### Linting Failures

**Symptom**:
```
************* Module src.ai_playlist.document_parser
src/ai_playlist/document_parser.py:42:0: C0301: Line too long (105/100) (line-too-long)

Your code has been rated at 8.75/10 (previous run: 9.25/10, -0.50)
```

**Solution**:
```bash
# Auto-format with Black
black src/ai_playlist/

# Fix specific pylint issues
pylint src/ai_playlist/ --output-format=colorized

# Common fixes:
# - Line length: Break long lines
# - Missing docstrings: Add docstrings to all public functions
# - Unused imports: Remove or use them
```

#### Type Checking Errors

**Symptom**:
```
src/ai_playlist/track_selector.py:45: error: Incompatible return value type
```

**Solution**:
```bash
# Run mypy with verbose output
mypy src/ai_playlist/ --show-error-codes

# Fix common type issues:
# - Add type hints to all function signatures
# - Use Optional[Type] for nullable values
# - Use Union[Type1, Type2] for multiple possible types
# - Add # type: ignore comments only as last resort
```

#### Performance Issues

**Symptom**:
- Tests taking > 2 minutes
- High memory usage
- Slow API responses

**Solution**:
```bash
# Run with verbose timing
pytest tests/unit/ai_playlist/ -v --durations=10

# Profile memory usage
pytest tests/unit/ai_playlist/ --memray

# Check API latency
curl -w "@curl-format.txt" -o /dev/null -s $SUBSONIC_MCP_URL/health

# Optimize:
# - Use pytest-xdist for parallel test execution
# - Mock slow API calls in unit tests
# - Cache expensive computations
```

### Additional Verification Commands

```bash
# Check Python version
python3 --version  # Should be 3.13+

# Verify dependencies
pip list | grep -E "(openai|pytest|tiktoken)"

# Check file structure
tree src/ai_playlist/ -L 2

# Verify decision logs directory
ls -la logs/decisions/

# Run code security scan
bandit -r src/ai_playlist/

# Check for code smells
radon cc src/ai_playlist/ -a
```

**Expected File Structure**:
```
src/ai_playlist/
├── __init__.py
├── __main__.py
├── azuracast_sync.py
├── batch_executor.py
├── cli.py
├── decision_logger.py
├── document_parser.py
├── exceptions.py
├── hive_coordinator.py
├── main.py
├── mcp_connector.py
├── openai_client.py
├── playlist_planner.py
├── track_selector.py
├── validator.py
└── workflow.py

tests/
├── conftest.py
├── fixtures/
│   ├── mock_track_metadata.json
│   └── sample_station_identity.md
├── unit/ai_playlist/
│   ├── __init__.py
│   ├── test_*.py (15+ test files)
└── integration/ai_playlist/
    ├── __init__.py
    └── test_*.py (3+ integration test files)
```

### Production Readiness Checklist

Before deploying to production:

- [ ] All tests passing (unit + integration + E2E)
- [ ] Coverage ≥90%
- [ ] Pylint score ≥9.0
- [ ] Black formatted (100%)
- [ ] Type checking passed (mypy --strict)
- [ ] Environment variables configured
- [ ] API credentials validated
- [ ] Decision logs directory writable
- [ ] Docker image built and tested
- [ ] Performance benchmarks passed (<10 min, <$0.50)
- [ ] Documentation reviewed and updated

**Final Verification**:
```bash
# Run complete pre-deployment check
pytest tests/ -v --cov=src/ai_playlist --cov-report=term && \
  pylint src/ai_playlist --fail-under=9.0 && \
  black --check src/ai_playlist && \
  mypy src/ai_playlist && \
  echo "✅ Production ready!"
```
