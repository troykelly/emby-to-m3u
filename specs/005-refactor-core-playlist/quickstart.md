# Quickstart Guide: AI/ML Playlist Generation Live Testing

**Feature**: 005-refactor-core-playlist
**Created**: 2025-10-06
**Purpose**: Live testing against actual Subsonic/Emby endpoints with environment credentials

---

## Prerequisites

### 1. Environment Variables

**CRITICAL**: This system uses environment variables directly, NOT `.env` files. All credentials must be available in the shell environment.

```bash
# Required environment variables
export SUBSONIC_URL="<your-subsonic-url>"
export SUBSONIC_USER="<your-username>"
export SUBSONIC_PASSWORD="<your-password>"
export OPENAI_API_KEY="<your-openai-key>"
export AZURACAST_HOST="<your-azuracast-host>"
export AZURACAST_API_KEY="<your-azuracast-api-key>"
export AZURACAST_STATION_ID="<your-station-id>"

# Optional: Cost control configuration (FR-009, FR-030)
export PLAYLIST_COST_BUDGET_MODE="suggested"  # or "hard"
export PLAYLIST_COST_ALLOCATION_STRATEGY="dynamic"  # or "equal"
export PLAYLIST_TOTAL_COST_BUDGET="10.00"  # Decimal dollars

# Optional: Last.fm for metadata enhancement (FR-029)
export LASTFM_API_KEY="<your-lastfm-key>"

# Verify environment variables are set
echo "Subsonic URL: $SUBSONIC_URL"
echo "OpenAI API Key: ${OPENAI_API_KEY:0:10}..."
echo "AzuraCast Host: $AZURACAST_HOST"
```

### 2. Install Dependencies

```bash
# Install Python dependencies
cd /workspaces/emby-to-m3u
pip install -r requirements.txt

# Install aubio-tools for BPM analysis fallback (FR-029)
sudo apt-get update && sudo apt-get install -y aubio-tools

# Verify installations
python -c "import openai; print('OpenAI SDK installed')"
aubio --version
```

### 3. Verify Station Identity Document

```bash
# Station identity document must exist
ls -lh /workspaces/emby-to-m3u/station-identity.md

# View first 50 lines to confirm structure
head -n 50 /workspaces/emby-to-m3u/station-identity.md
```

---

## Test 1: Load and Parse Station Identity

**Objective**: Validate station-identity.md parsing and daypart extraction (FR-001 to FR-004)

```bash
# Run station identity parser
python -m src.ai_playlist.cli station-identity load \
  --path /workspaces/emby-to-m3u/station-identity.md \
  --validate

# Expected output:
# ✓ Station identity loaded successfully
# ✓ Version: <SHA-256 hash>
# ✓ Programming structures: 3 (Weekday, Saturday, Sunday)
# ✓ Total dayparts: 18
# ✓ Validation: PASSED
#
# Dayparts extracted:
# - Morning Drive: Production Call (06:00-10:00, Weekday)
# - Midday: The Session (10:00-15:00, Weekday)
# - Afternoon Drive: The Commute (15:00-19:00, Weekday)
# ... (more dayparts)
```

### Success Criteria
- Document loads without errors
- All dayparts extracted with correct time ranges
- BPM progressions parsed correctly
- Genre mix percentages sum to 1.0 (±0.01)
- Era distribution percentages sum to 1.0 (±0.01)
- Australian content minimum set to 0.30

---

## Test 2: Query Live Subsonic Endpoint

**Objective**: Verify connectivity to music library and metadata retrieval (FR-010, FR-029)

```bash
# Test Subsonic connection
python -m src.ai_playlist.cli tracks test-connection

# Expected output:
# ✓ Connected to Subsonic: <server-name>
# ✓ Total tracks in library: 15,432
# ✓ Australian tracks identified: 4,628 (30.0%)
# ✓ Tracks with BPM metadata: 12,856 (83.3%)
# ✓ Tracks missing BPM: 2,576 (16.7%)

# Search for tracks matching Morning Drive criteria
python -m src.ai_playlist.cli tracks search \
  --daypart "Morning Drive: Production Call" \
  --limit 50 \
  --output /tmp/morning-drive-candidates.json

# Expected output:
# ✓ Searching for tracks matching criteria:
#   - BPM: 90-135 (progressive)
#   - Genres: Contemporary Alternative (25%), Electronic/Downtempo (20%), ...
#   - Australian content: minimum 30%
#   - Era: Current 40%, Recent 35%, Modern Classics 20%, Throwbacks 5%
#
# ✓ Found 1,247 matching tracks
# ✓ Sample: 50 tracks saved to /tmp/morning-drive-candidates.json
# ✓ Search completed in 2.3 seconds
```

### Success Criteria
- Connection to Subsonic succeeds
- Track metadata contains: title, artist, album, duration, country
- BPM metadata available for 80%+ of tracks
- Australian tracks identified correctly (30%+ of library)
- Search results match daypart criteria

---

## Test 3: Enhance Missing Metadata with Last.fm/aubio

**Objective**: Validate metadata enhancement pipeline (FR-029)

```bash
# Find tracks with missing BPM
python -m src.ai_playlist.cli tracks find-missing-metadata \
  --field bpm \
  --limit 10 \
  --output /tmp/missing-bpm.json

# Enhance metadata using Last.fm
python -m src.ai_playlist.cli tracks enhance \
  --input /tmp/missing-bpm.json \
  --source lastfm \
  --cache

# Expected output:
# ✓ Enhancing metadata for 10 tracks...
# ✓ Last.fm API: 8/10 tracks enhanced
# ✗ Last.fm API: 2/10 tracks not found
# ✓ Falling back to aubio for 2 tracks...
# ✓ aubio analysis: 2/2 tracks analyzed
# ✓ Total enhanced: 10/10 (100%)
# ✓ Metadata cached permanently

# Test aubio directly on audio file
python -m src.ai_playlist.cli tracks analyze-audio \
  --track-id <subsonic-track-id> \
  --features bpm,key,energy

# Expected output:
# ✓ Analyzing audio file: /music/Artist/Album/Track.mp3
# ✓ BPM detected: 124
# ✓ Key: A minor
# ✓ Energy: 0.78
# ✓ Analysis completed in 8.2 seconds
# ✓ Metadata cached
```

### Success Criteria
- Last.fm API successfully retrieves BPM for 70%+ of tracks
- aubio fallback successfully analyzes remaining tracks
- All enhanced metadata is permanently cached
- Cache is reused on subsequent queries

---

## Test 4: Generate Single Playlist (Morning Drive)

**Objective**: Generate complete playlist using AI/ML track selection (FR-005 to FR-009)

```bash
# Generate playlist for Morning Drive: Production Call
python -m src.ai_playlist.cli playlist generate \
  --daypart "Morning Drive: Production Call" \
  --date 2025-10-07 \
  --cost-budget 5.00 \
  --budget-mode suggested \
  --output /tmp/playlists/

# Expected output:
# ✓ Loading station identity...
# ✓ Acquiring lock on station-identity.md...
# ✓ Lock acquired: <lock-id>
# ✓ Parsing daypart: Morning Drive: Production Call (06:00-10:00)
# ✓ Target track count: 48-56 (12-14 per hour × 4 hours)
#
# ✓ Querying Subsonic for candidate tracks...
# ✓ Found 1,247 candidates
#
# ✓ Starting AI/ML track selection...
#   → LLM: Selecting tracks for 06:00-07:00 (BPM 90-115)...
#   → Selected 13 tracks (cost: $0.42, time: 3.2s)
#   → LLM: Selecting tracks for 07:00-09:00 (BPM 110-135)...
#   → Selected 27 tracks (cost: $0.89, time: 6.8s)
#   → LLM: Selecting tracks for 09:00-10:00 (BPM 100-120)...
#   → Selected 12 tracks (cost: $0.38, time: 2.9s)
#
# ✓ Total tracks selected: 52
# ✓ Total cost: $1.69 (budget: $5.00, 33.8% utilized)
# ✓ Generation time: 15.4 seconds
#
# ✓ Validating playlist against station identity criteria...
#   → Australian content: 31.2% (target: 30.0%) ✓
#   → Genre distribution: 95.8% compliant ✓
#   → Era distribution: 93.4% compliant ✓
#   → BPM progression: 98.2% coherence ✓
#   → Energy flow: consistent ✓
#
# ✓ Validation: PASSED (compliance: 96.8%)
# ✓ Playlist saved: /tmp/playlists/morning-drive-2025-10-07.m3u
# ✓ Metadata saved: /tmp/playlists/morning-drive-2025-10-07.json
# ✓ Decision log: /tmp/playlists/morning-drive-2025-10-07-decisions.json
# ✓ Releasing lock on station-identity.md...
```

### Success Criteria
- Playlist contains 48-56 tracks (12-14 per hour × 4 hours)
- Australian content ≥ 30%
- Genre distribution within ±10% of targets
- Era distribution within ±10% of targets
- BPM progression follows daypart specification
- All tracks have AI selection reasoning (min 50 chars)
- Total cost < budget (or warning if suggested mode)
- M3U file is valid and contains all tracks
- Decision log contains complete audit trail

---

## Test 5: Generate Full Day Programming (Batch)

**Objective**: Generate multiple playlists with shared cost budget (FR-009, FR-030)

```bash
# Generate all weekday playlists
python -m src.ai_playlist.cli playlist batch-generate \
  --schedule weekday \
  --date 2025-10-07 \
  --total-budget 20.00 \
  --budget-mode hard \
  --allocation-strategy dynamic \
  --output /tmp/playlists/full-day/

# Expected output:
# ✓ Loading station identity...
# ✓ Acquiring lock on station-identity.md...
# ✓ Found 5 weekday dayparts:
#   1. Morning Drive: Production Call (06:00-10:00)
#   2. Midday: The Session (10:00-15:00)
#   3. Afternoon Drive: The Commute (15:00-19:00)
#   4. Evening: After Hours (19:00-00:00)
#   5. Late Night/Overnight: The Creative Shift (00:00-06:00)
#
# ✓ Total cost budget: $20.00
# ✓ Budget mode: HARD (generation stops if exceeded)
# ✓ Allocation strategy: DYNAMIC (based on complexity)
#
# ✓ Calculating budget allocation...
#   → Morning Drive: $4.20 (21.0% - high complexity)
#   → Midday: $5.60 (28.0% - highest complexity, 5 hours)
#   → Afternoon Drive: $4.00 (20.0% - high complexity)
#   → Evening: $4.20 (21.0% - specialty shows)
#   → Late Night: $2.00 (10.0% - low complexity, voice-tracked)
#
# ✓ Generating playlists...
#   [1/5] Morning Drive: $3.87 / $4.20 allocated ✓
#   [2/5] Midday: $5.12 / $5.60 allocated ✓
#   [3/5] Afternoon Drive: $3.95 / $4.00 allocated ✓
#   [4/5] Evening: $4.18 / $4.20 allocated ✓
#   [5/5] Late Night: $1.82 / $2.00 allocated ✓
#
# ✓ Batch generation complete!
#   → Total playlists: 5/5 successful
#   → Total cost: $18.94 / $20.00 (94.7% utilized)
#   → Total tracks: 243
#   → Total duration: 16 hours 42 minutes
#   → Generation time: 78.3 seconds
#
# ✓ Releasing lock on station-identity.md...
# ✓ All playlists saved to /tmp/playlists/full-day/
```

### Success Criteria
- All 5 weekday playlists generated successfully
- Total cost ≤ budget ($20.00 in hard mode)
- Dynamic allocation adjusts per playlist complexity
- Each playlist meets validation criteria (≥80% compliance)
- Combined duration covers 24-hour broadcast day
- No track repeats across all playlists (no-repeat enforcement)

---

## Test 6: Constraint Relaxation (Insufficient Tracks)

**Objective**: Validate progressive constraint relaxation (FR-028)

```bash
# Generate specialty playlist with restrictive criteria
# (e.g., Wednesday Australian Spotlight with limited Australian electronic tracks)
python -m src.ai_playlist.cli playlist generate \
  --daypart "Evening: After Hours" \
  --date 2025-10-09 \
  --specialty "100% Australian Electronic" \
  --max-relaxation-steps 3 \
  --output /tmp/playlists/

# Expected output:
# ✓ Loading station identity...
# ✓ Parsing daypart: Evening: After Hours (19:00-00:00)
# ✓ Specialty constraint: 100% Australian Electronic
# ✓ Target track count: 40-50
#
# ✓ Querying Subsonic for candidate tracks...
# ✗ Found only 18 matching tracks (need 40-50)
#
# ⚠ Insufficient tracks, applying progressive relaxation...
#
# → Relaxation Step 1: Expand BPM range ±10 BPM
#   ✓ Original: 100-130 BPM
#   ✓ Relaxed: 90-140 BPM
#   ✓ Found 12 additional tracks (total: 30)
#   ✗ Still insufficient
#
# → Relaxation Step 2: Expand BPM range ±15 BPM
#   ✓ Original: 100-130 BPM
#   ✓ Relaxed: 85-145 BPM
#   ✓ Found 8 additional tracks (total: 38)
#   ✗ Still insufficient
#
# → Relaxation Step 3: Relax genre constraint (allow related genres)
#   ✓ Original: 100% Electronic
#   ✓ Relaxed: Electronic (80%) + Downtempo/Ambient (20%)
#   ✓ Found 14 additional tracks (total: 52)
#   ✓ Sufficient tracks found!
#
# ✓ All relaxations logged in decision log
# ✓ Generating playlist with relaxed constraints...
# ✓ Playlist generated: 48 tracks
# ✓ Constraint relaxations applied: 3 steps
```

### Success Criteria
- Progressive relaxation applied in correct order (BPM ±10, ±15, then genre)
- Each relaxation step logged in decision log with reasoning
- Relaxation stops when sufficient tracks found
- Final playlist still meets core requirements (100% Australian)
- All relaxations documented in playlist metadata

---

## Test 7: Playlist Validation Against Station Identity

**Objective**: Comprehensive validation of compliance (FR-022, FR-023, FR-025, FR-026)

```bash
# Validate previously generated playlist
python -m src.ai_playlist.cli playlist validate \
  --playlist-id <playlist-id> \
  --detailed \
  --output /tmp/validation-report.json

# Expected output:
# ✓ Loading playlist: Morning Drive: Production Call - 2025-10-07
# ✓ Loading station identity criteria...
#
# === CONSTRAINT COMPLIANCE ===
#
# Australian Content:
#   ✓ Target: 30.0% minimum
#   ✓ Actual: 31.2% (16/52 tracks)
#   ✓ Status: PASS
#
# Genre Distribution:
#   ✓ Contemporary Alternative: 26.9% (target: 25.0% ±10%) PASS
#   ✓ Electronic/Downtempo: 19.2% (target: 20.0% ±10%) PASS
#   ✓ Quality Pop/R&B: 21.2% (target: 20.0% ±10%) PASS
#   ✓ Global Sounds: 13.5% (target: 15.0% ±10%) PASS
#   ✓ Contemporary Jazz: 11.5% (target: 10.0% ±10%) PASS
#   → Overall compliance: 96.2% PASS
#
# Era Distribution:
#   ✓ Current (2023-2025): 40.4% (target: 40.0% ±10%) PASS
#   ✓ Recent (2020-2022): 34.6% (target: 35.0% ±10%) PASS
#   ✓ Modern Classics (2015-2019): 21.2% (target: 20.0% ±10%) PASS
#   ✓ Throwbacks (2005-2014): 3.8% (target: 5.0% ±10%) PASS
#   → Overall compliance: 94.8% PASS
#
# === FLOW QUALITY METRICS ===
#
# BPM Progression:
#   ✓ BPM variance: 12.3 (standard deviation)
#   ✓ Progression coherence: 98.2%
#   ✓ 06:00-07:00: avg 102 BPM (target: 90-115) ✓
#   ✓ 07:00-09:00: avg 122 BPM (target: 110-135) ✓
#   ✓ 09:00-10:00: avg 108 BPM (target: 100-120) ✓
#
# Energy Consistency: 92.1%
# Genre Diversity Index: 0.78 (normalized Shannon entropy)
# Overall Quality Score: 91.4%
#
# === OVERALL VALIDATION ===
# ✓ Status: PASS
# ✓ Compliance: 96.8%
# ✓ Validation saved to /tmp/validation-report.json
```

### Success Criteria
- Overall compliance ≥ 80% (WARNING), ≥ 95% (PASS)
- All hard constraints met (Australian content ≥ 30%)
- Soft constraints within tolerance (±10%)
- Flow quality metrics calculated correctly
- Validation report contains actionable gap analysis

---

## Test 8: AzuraCast Sync (Dry Run)

**Objective**: Test AzuraCast integration without actual sync (FR-016)

```bash
# Dry-run sync to AzuraCast
python -m src.ai_playlist.cli azuracast sync \
  --playlist-id <playlist-id> \
  --azuracast-name "Morning Drive - Oct 7" \
  --dry-run \
  --schedule-start "06:00" \
  --schedule-end "10:00" \
  --days-of-week 0,1,2,3,4

# Expected output:
# ✓ Loading playlist: Morning Drive: Production Call - 2025-10-07
# ✓ Connecting to AzuraCast: <host>
# ✓ AzuraCast version: 0.19.5
# ✓ Station: Production City Radio (ID: <station-id>)
#
# === DRY RUN MODE (no actual sync) ===
#
# ✓ Would create playlist: "Morning Drive - Oct 7"
# ✓ Would schedule: Monday-Friday, 06:00-10:00
# ✓ Would sync 52 tracks:
#   1. Tame Impala - The Less I Know The Better (185s)
#   2. Bonobo - Kerala (324s)
#   3. ... (50 more tracks)
#
# ✓ Total duration: 3h 58m 42s
# ✓ Estimated sync time: ~45 seconds
#
# ✓ Dry run complete. No changes made to AzuraCast.
# ✓ To perform actual sync, remove --dry-run flag.
```

### Success Criteria
- AzuraCast connection successful
- Playlist structure validated
- Schedule configuration correct
- Track list complete and in order
- No actual changes made to AzuraCast

---

## Test 9: AzuraCast Live Sync

**Objective**: Actual sync to AzuraCast (FR-016)

```bash
# LIVE sync to AzuraCast
python -m src.ai_playlist.cli azuracast sync \
  --playlist-id <playlist-id> \
  --azuracast-name "Morning Drive - Oct 7" \
  --schedule-start "06:00" \
  --schedule-end "10:00" \
  --days-of-week 0,1,2,3,4 \
  --replace-existing

# Expected output:
# ✓ Loading playlist: Morning Drive: Production Call - 2025-10-07
# ✓ Connecting to AzuraCast...
# ✓ Connected to station: Production City Radio
#
# ⚠ LIVE SYNC MODE - Changes will be made to AzuraCast
#
# ✓ Creating playlist: "Morning Drive - Oct 7"
# ✓ Playlist created: ID 42
# ✓ Uploading tracks to AzuraCast...
#   → [1/52] Tame Impala - The Less I Know The Better ✓
#   → [2/52] Bonobo - Kerala ✓
#   → ... (progress bar)
#   → [52/52] complete
#
# ✓ Tracks synced: 52/52 (100%)
# ✓ Configuring schedule: Monday-Friday, 06:00-10:00
# ✓ Schedule saved
#
# ✓ Sync complete!
#   → AzuraCast Playlist ID: 42
#   → Tracks synced: 52
#   → Sync duration: 43.2 seconds
#   → Playlist URL: https://<host>/admin/playlists/42
#
# ✓ Verification: Re-fetching playlist from AzuraCast...
# ✓ Verified: 52 tracks in AzuraCast playlist match source
```

### Success Criteria
- All 52 tracks successfully uploaded to AzuraCast
- Schedule configuration saved correctly
- Playlist enabled and active
- Verification confirms track order and content
- AzuraCast UI shows playlist correctly

---

## Test 10: Cost Tracking and Budget Enforcement

**Objective**: Validate cost control mechanisms (FR-009, FR-030)

```bash
# Test hard budget limit enforcement
python -m src.ai_playlist.cli playlist batch-generate \
  --schedule weekday \
  --date 2025-10-08 \
  --total-budget 5.00 \
  --budget-mode hard \
  --allocation-strategy equal \
  --output /tmp/playlists/budget-test/

# Expected output:
# ✓ Loading station identity...
# ✓ Found 5 weekday dayparts
# ✓ Total cost budget: $5.00 (HARD limit)
# ✓ Allocation strategy: EQUAL ($1.00 per playlist)
#
# ✓ Generating playlists...
#   [1/5] Morning Drive: $0.98 / $1.00 ✓
#   [2/5] Midday: $1.02 / $1.00 ⚠ OVER BUDGET
#
# ✗ ERROR: Cost budget exceeded in HARD mode
#   → Budget: $5.00
#   → Spent: $1.98
#   → Playlist 2 exceeded allocation: $1.02 / $1.00
#
# ✓ Playlists completed: 1/5
# ✓ Playlists failed: 4/5 (budget exceeded)
# ✓ Partial results saved to /tmp/playlists/budget-test/

# Test suggested budget (warning mode)
python -m src.ai_playlist.cli playlist batch-generate \
  --schedule weekday \
  --date 2025-10-08 \
  --total-budget 5.00 \
  --budget-mode suggested \
  --allocation-strategy dynamic \
  --output /tmp/playlists/budget-test-2/

# Expected output:
# ✓ Total cost budget: $5.00 (SUGGESTED - warnings only)
# ✓ Allocation strategy: DYNAMIC
#
# ✓ Generating playlists...
#   [1/5] Morning Drive: $0.87 / $1.05 ✓
#   [2/5] Midday: $1.42 / $1.40 ⚠ Over allocation (+$0.02)
#   [3/5] Afternoon Drive: $0.95 / $1.00 ✓
#   [4/5] Evening: $1.18 / $1.05 ⚠ Over allocation (+$0.13)
#   [5/5] Late Night: $0.52 / $0.50 ⚠ Over allocation (+$0.02)
#
# ⚠ WARNING: Total cost $4.94 / $5.00 (within budget)
# ⚠ WARNING: 3 playlists exceeded individual allocations (suggested mode)
#
# ✓ All playlists completed successfully
# ✓ Total cost: $4.94 / $5.00 (98.8% utilized)
```

### Success Criteria
- Hard mode stops generation when budget exceeded
- Suggested mode generates all playlists with warnings
- Dynamic allocation adjusts based on playlist complexity
- Equal allocation distributes budget evenly
- All costs tracked accurately in decision logs

---

## Test 11: Complete End-to-End Workflow

**Objective**: Full workflow from station identity to AzuraCast sync

```bash
# Complete workflow for single day
python -m src.ai_playlist.cli workflow full-day \
  --schedule weekday \
  --date 2025-10-10 \
  --total-budget 25.00 \
  --budget-mode suggested \
  --azuracast-sync \
  --output /tmp/playlists/2025-10-10/

# Expected output:
# === STEP 1: Load Station Identity ===
# ✓ Loaded: /workspaces/emby-to-m3u/station-identity.md
# ✓ Version: <hash>
# ✓ Lock acquired
#
# === STEP 2: Generate Playlists ===
# ✓ Generating 5 weekday playlists...
#   [1/5] Morning Drive: 52 tracks, $3.87, 96.8% compliant ✓
#   [2/5] Midday: 75 tracks, $5.42, 94.2% compliant ✓
#   [3/5] Afternoon Drive: 48 tracks, $3.95, 97.1% compliant ✓
#   [4/5] Evening: 42 tracks, $4.18, 91.3% compliant ⚠
#   [5/5] Late Night: 84 tracks, $1.82, 88.9% compliant ⚠
#
# ✓ Total tracks: 301
# ✓ Total cost: $19.24 / $25.00 (77.0% utilized)
#
# === STEP 3: Validate All Playlists ===
# ✓ Validation complete: 3 PASS, 2 WARNING, 0 FAIL
# ✓ Overall compliance: 93.7%
#
# === STEP 4: Sync to AzuraCast ===
# ✓ Syncing 5 playlists to AzuraCast...
#   [1/5] Morning Drive - Oct 10 → Playlist ID 43 ✓
#   [2/5] Midday Session - Oct 10 → Playlist ID 44 ✓
#   [3/5] Afternoon Drive - Oct 10 → Playlist ID 45 ✓
#   [4/5] After Hours - Oct 10 → Playlist ID 46 ✓
#   [5/5] Creative Shift - Oct 10 → Playlist ID 47 ✓
#
# ✓ All playlists synced successfully (301 tracks)
#
# === STEP 5: Generate Reports ===
# ✓ Markdown report: /tmp/playlists/2025-10-10/report.md
# ✓ PDF report: /tmp/playlists/2025-10-10/report.pdf
# ✓ Decision logs: /tmp/playlists/2025-10-10/decisions/
#
# === WORKFLOW COMPLETE ===
# ✓ Lock released
# ✓ Total execution time: 142.8 seconds
# ✓ All artifacts saved to /tmp/playlists/2025-10-10/
```

### Success Criteria
- All 5 playlists generated and validated
- All playlists synced to AzuraCast
- Complete audit trail in decision logs
- Reports generated (Markdown + PDF)
- No errors, warnings acceptable
- Total time < 5 minutes

---

## Expected Outputs

### File Structure

```
/tmp/playlists/
└── 2025-10-10/
    ├── morning-drive-2025-10-10.m3u                    # M3U playlist
    ├── morning-drive-2025-10-10.json                   # Playlist metadata
    ├── morning-drive-2025-10-10-decisions.json         # Decision log
    ├── midday-session-2025-10-10.m3u
    ├── midday-session-2025-10-10.json
    ├── midday-session-2025-10-10-decisions.json
    ├── ... (remaining playlists)
    ├── report.md                                        # Markdown report
    ├── report.pdf                                       # PDF report
    └── decisions/
        ├── morning-drive-decisions.json
        ├── midday-session-decisions.json
        └── ... (all decision logs)
```

### Sample M3U Output

```m3u
#EXTM3U
#PLAYLIST:Morning Drive: Production Call - 2025-10-10

#EXTINF:185,Tame Impala - The Less I Know The Better
subsonic:track:67890

#EXTINF:324,Bonobo - Kerala
subsonic:track:67891

#EXTINF:241,Hiatus Kaiyote - Nakamarra
subsonic:track:67892

... (49 more tracks)
```

### Sample Validation Report JSON

```json
{
  "playlist_id": "550e8400-e29b-41d4-a716-446655440000",
  "playlist_name": "Morning Drive: Production Call - 2025-10-10",
  "overall_status": "pass",
  "compliance_percentage": 0.968,
  "validated_at": "2025-10-06T10:42:15Z",
  "constraint_scores": {
    "australian_content": {
      "constraint_name": "Australian Content",
      "target_value": 0.30,
      "actual_value": 0.312,
      "tolerance": 0.0,
      "is_compliant": true,
      "deviation_percentage": 0.04
    },
    "genre_Contemporary Alternative": {
      "constraint_name": "Genre: Contemporary Alternative",
      "target_value": 0.25,
      "actual_value": 0.269,
      "tolerance": 0.10,
      "is_compliant": true,
      "deviation_percentage": 0.076
    }
  },
  "flow_quality_metrics": {
    "bpm_variance": 12.3,
    "bpm_progression_coherence": 0.982,
    "energy_consistency": 0.921,
    "genre_diversity_index": 0.78,
    "overall_quality_score": 0.914
  },
  "gap_analysis": []
}
```

---

## Troubleshooting

### Issue: Subsonic connection fails

```bash
# Test connection manually
curl -u "$SUBSONIC_USER:$SUBSONIC_PASSWORD" \
  "$SUBSONIC_URL/rest/ping?v=1.16.1&c=playlist-test&f=json"

# Check credentials
echo "User: $SUBSONIC_USER"
echo "URL: $SUBSONIC_URL"
```

### Issue: Last.fm metadata enhancement fails

```bash
# Verify Last.fm API key
curl "http://ws.audioscrobbler.com/2.0/?method=track.getInfo&api_key=$LASTFM_API_KEY&artist=Tame%20Impala&track=The%20Less%20I%20Know%20The%20Better&format=json"

# Fall back to aubio
aubio track "/path/to/audio/file.mp3"
```

### Issue: Cost budget exceeded unexpectedly

```bash
# Check decision log for cost breakdown
python -m src.ai_playlist.cli playlist decision-log \
  --playlist-id <id> \
  --cost-summary

# Adjust budget allocation
export PLAYLIST_TOTAL_COST_BUDGET="30.00"
```

### Issue: AzuraCast sync fails

```bash
# Verify AzuraCast credentials
python -m src.ai_playlist.cli azuracast verify

# Check station ID
export AZURACAST_STATION_ID="1"
```

---

## Summary

This quickstart guide provides comprehensive live testing coverage for:

1. **Station Identity Parsing** (FR-001 to FR-004, FR-031)
2. **Music Library Integration** (FR-010, FR-011)
3. **Metadata Enhancement** (FR-029)
4. **AI/ML Playlist Generation** (FR-005 to FR-009)
5. **Constraint Relaxation** (FR-028)
6. **Cost Controls** (FR-009, FR-030)
7. **Validation** (FR-020 to FR-023, FR-025, FR-026)
8. **AzuraCast Sync** (FR-016)
9. **Decision Logging** (FR-018, FR-027)
10. **Complete Workflows** (All FRs integrated)

All tests use **live environment credentials** and **actual Subsonic/Emby endpoints** as required by the specification.
