# Tasks: Robust AzuraCast File Deduplication and Selective Upload

**Input**: Design documents from `/workspaces/emby-to-m3u/specs/002-fix-azuracast-duplicate/`
**Prerequisites**: plan.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅, quickstart.md ✅

## Execution Flow (main)
```
1. Load plan.md from feature directory → ✅ Tech stack: Python 3.13+, pytest, requests
2. Load optional design documents:
   → data-model.md: 4 entities extracted → 4 model tasks
   → contracts/: 3 files → 9 contract test tasks
   → quickstart.md: 10 test phases → 6 integration test tasks
3. Generate tasks by category:
   → Setup: 3 tasks (structure, dependencies, environment)
   → Tests: 15 tasks (contract + integration + unit)
   → Core: 12 tasks (models + normalization + detection + cache)
   → Integration: 6 tasks (refactor AzuraCastSync, rate limiting, logging)
   → Polish: 4 tasks (performance, documentation, validation)
4. Apply task rules:
   → Different files = mark [P] for parallel (25 tasks)
   → Same file = sequential (15 tasks)
   → Tests before implementation (TDD) → 15 test tasks before 12 impl tasks
5. Number tasks sequentially (T001-T040)
6. Generate dependency graph → Tests block implementation
7. Create parallel execution examples → 5 batches of [P] tasks
8. Validate task completeness:
   → All 9 contracts have tests ✅
   → All 4 entities have models ✅
   → All detection strategies implemented ✅
9. Return: SUCCESS (40 tasks ready for execution)
```

## Format: `[ID] [P?] Description`
- **[P]**: Can run in parallel (different files, no dependencies)
- Include exact file paths in descriptions
- TDD order: Tests before implementation

## Path Conventions
Single project structure (from plan.md):
- **Source**: `/workspaces/emby-to-m3u/src/`
- **Tests**: `/workspaces/emby-to-m3u/tests/`
- **Docs**: `/workspaces/emby-to-m3u/specs/002-fix-azuracast-duplicate/`

---

## Phase 3.1: Setup (3 tasks)

- [X] **T001** Create directory structure for new modules and tests
  - Create `/workspaces/emby-to-m3u/src/azuracast/models.py` (empty)
  - Create `/workspaces/emby-to-m3u/src/azuracast/normalization.py` (empty)
  - Create `/workspaces/emby-to-m3u/src/azuracast/detection.py` (empty)
  - Create `/workspaces/emby-to-m3u/src/azuracast/cache.py` (empty)
  - Create `/workspaces/emby-to-m3u/tests/unit/` directory
  - Create `/workspaces/emby-to-m3u/tests/contract/` directory
  - Create `/workspaces/emby-to-m3u/tests/integration/` directory

- [X] **T002** Verify Python dependencies and add new test dependencies
  - Check `requirements.txt` has: `requests`, `tqdm`
  - Add to `requirements-dev.txt`: `pytest>=7.4.0`, `pytest-mock>=3.11.0`, `pytest-cov>=4.1.0`
  - No additional runtime dependencies needed (stdlib-only approach from research.md)

- [X] **T003** [P] Configure environment variables for testing
  - Create `.env.test` template with required variables:
    - `SUBSONIC_HOST`, `SUBSONIC_USER`, `SUBSONIC_PASSWORD`
    - `AZURACAST_HOST`, `AZURACAST_API_KEY`, `AZURACAST_STATION_ID`
    - `AZURACAST_FORCE_REUPLOAD=false`
    - `AZURACAST_LEGACY_DETECTION=false`
    - `AZURACAST_CACHE_TTL=300`
    - `AZURACAST_SKIP_REPLAYGAIN_CHECK=false`
  - Add `.env.test` to `.gitignore` if not already present

---

## Phase 3.2: Tests First (TDD) ⚠️ MUST COMPLETE BEFORE 3.3

**CRITICAL: These tests MUST be written and MUST FAIL before ANY implementation**

### Contract Tests (9 tasks - from contracts/)

- [X] **T004** [P] Contract test: normalize_string() in `/workspaces/emby-to-m3u/tests/contract/test_normalization.py`
  - Test cases from `contracts/normalization.md`:
    - Whitespace stripping: `"  The Beatles  "` → `"the beatles"`
    - Lowercase conversion: `"Pink Floyd"` → `"pink floyd"`
    - Special char normalization: `"Björk"` → `"bjork"`
    - Multiple space collapse: `"Led  Zeppelin"` → `"led zeppelin"`
    - Empty string handling: `""` → `""`
    - Unicode normalization: `"Sigur Rós"` → `"sigur ros"`
  - Assert all test cases FAIL (function not implemented yet)

- [X] **T005** [P] Contract test: normalize_artist() in `/workspaces/emby-to-m3u/tests/contract/test_normalization.py`
  - Test cases from `contracts/normalization.md`:
    - "The" prefix: `"The Beatles"` → `"beatles"`
    - "The" mid-string: `"The The"` → `"the the"` (only leading "The")
    - Featuring variants: `"Artist feat. Guest"` → `"artist guest"` (remove feat/ft/featuring)
    - Multiple artists: `"Artist1 & Artist2"` → `"artist1 artist2"` (normalize separators)
    - Edge cases: `"The"` → `""`, `"feat."` → `""`
  - Assert all test cases FAIL

- [X] **T006** [P] Contract test: build_track_fingerprint() in `/workspaces/emby-to-m3u/tests/contract/test_normalization.py`
  - Test cases:
    - Standard track: `{"artist": "The Beatles", "album": "Abbey Road", "title": "Come Together"}` → `"beatles|abbey road|come together"`
    - Missing fields handled gracefully
    - Special characters normalized in fingerprint
    - Consistent output for equivalent inputs
  - Assert all test cases FAIL

- [X] **T007** [P] Contract test: check_file_exists_by_musicbrainz() in `/workspaces/emby-to-m3u/tests/contract/test_duplicate_detection.py`
  - Test cases from `contracts/duplicate-detection.md`:
    - Exact MBID match returns azuracast_file_id
    - No MBID in track returns None
    - No MBID in known_tracks returns None
    - Multiple tracks with same MBID (error case)
    - Empty known_tracks list returns None
  - Assert all test cases FAIL

- [X] **T008** [P] Contract test: check_file_exists_by_metadata() in `/workspaces/emby-to-m3u/tests/contract/test_duplicate_detection.py`
  - Test cases:
    - Exact fingerprint match returns azuracast_file_id
    - Duration tolerance: ±5 seconds logs warning but matches
    - Duration difference >5 seconds returns None
    - Fingerprint mismatch returns None
    - Case insensitive matching works
    - "The" prefix variations match
  - Assert all test cases FAIL

- [X] **T009** [P] Contract test: check_file_in_azuracast() (multi-strategy) in `/workspaces/emby-to-m3u/tests/contract/test_duplicate_detection.py`
  - Test cases:
    - Strategy priority: MBID > metadata > file_path
    - Returns UploadDecision with correct strategy_used
    - Source duplicates detected (multiple source tracks → same AzuraCast track)
    - Fallback behavior when all strategies fail
    - Logging includes strategy used and reason
  - Assert all test cases FAIL

- [X] **T010** [P] Contract test: should_skip_replaygain_conflict() in `/workspaces/emby-to-m3u/tests/contract/test_upload_decision.py`
  - Test cases from `contracts/upload-decision.md`:
    - AzuraCast has ReplayGain, source has different values → True (skip)
    - AzuraCast has ReplayGain, source has no ReplayGain → True (skip)
    - AzuraCast has no ReplayGain, source has ReplayGain → False (upload)
    - Neither has ReplayGain → False (upload for other reasons)
  - Assert all test cases FAIL

- [X] **T011** [P] Contract test: get_cached_known_tracks() in `/workspaces/emby-to-m3u/tests/contract/test_upload_decision.py`
  - Test cases:
    - First call fetches from API (cache miss)
    - Second call within TTL returns cached data (cache hit)
    - Call after TTL expiry re-fetches from API
    - Cache invalidation works correctly
    - Thread-safety (single-threaded sync process, no locks needed)
  - Assert all test cases FAIL

- [X] **T012** [P] Contract test: Rate limit exponential backoff in `/workspaces/emby-to-m3u/tests/contract/test_rate_limiting.py`
  - Test cases from FR-033 (specification):
    - 429 status code triggers retry with backoff
    - Exponential increase: 1.5s, 3s, 6s, 12s, 24s, 48s (with jitter)
    - Respect Retry-After header if present
    - Max retries reached → raise exception
    - Successful retry continues processing
  - Assert all test cases FAIL

### Integration Tests (6 tasks - from quickstart.md)

- [X] **T013** [P] Integration test: Initial upload workflow in `/workspaces/emby-to-m3u/tests/integration/test_azuracast_live.py`
  - **LIVE SERVER TEST** (uses environment AzuraCast instance)
  - Setup: Create test playlist with 10 tracks (diverse metadata)
  - Execute: Run sync command
  - Assert: All 10 tracks uploaded successfully
  - Assert: AzuraCast API confirms file IDs assigned
  - Cleanup: Delete uploaded tracks from AzuraCast
  - **Note**: Test must FAIL initially (implementation not complete)

- [X] **T014** [P] Integration test: Second run duplicate detection in `/workspaces/emby-to-m3u/tests/integration/test_azuracast_live.py`
  - **LIVE SERVER TEST**
  - Prerequisites: T013 uploaded 10 tracks
  - Execute: Run sync command again with same playlist
  - Assert: 0 tracks uploaded (100% duplicate detection - FR-029)
  - Assert: Log shows "10 of 10 tracks already in AzuraCast"
  - Assert: Each skip shows reason "duplicate - identical metadata"
  - Cleanup: Delete test tracks
  - **Note**: Test must FAIL initially

- [X] **T015** [P] Integration test: Metadata normalization variations in `/workspaces/emby-to-m3u/tests/integration/test_normalization_live.py`
  - **LIVE SERVER TEST**
  - Setup: Upload track "The Beatles - Abbey Road - Come Together"
  - Modify: Change source metadata to "Beatles - Abbey Road - Come Together" (remove "The")
  - Execute: Run sync command
  - Assert: 0 tracks uploaded (normalization matched - FR-004)
  - Repeat with: "Artist feat. Guest" → "Artist ft. Guest" (FR-005)
  - Assert: All variations matched correctly
  - Cleanup: Delete test tracks
  - **Note**: Test must FAIL initially

- [X] **T016** [P] Integration test: ReplayGain preservation in `/workspaces/emby-to-m3u/tests/integration/test_replaygain_live.py`
  - **LIVE SERVER TEST**
  - Setup: Upload track WITH ReplayGain to AzuraCast
  - Modify: Change source track ReplayGain values (different gain)
  - Execute: Run sync command
  - Assert: Track NOT re-uploaded (FR-011 - existing ReplayGain preserved)
  - Assert: Log shows "skip - has ReplayGain metadata"
  - Cleanup: Delete test track
  - **Note**: Test must FAIL initially

- [X] **T017** [P] Integration test: Performance benchmark (100 tracks) in `/workspaces/emby-to-m3u/tests/integration/test_performance_live.py`
  - **LIVE SERVER TEST**
  - Setup: Prepare 100-track test playlist in AzuraCast
  - Execute: Run sync with all tracks already present
  - Measure: Duplicate detection time
  - Assert: Detection completes in <5 seconds (FR-019)
  - Calculate: Tracks per second throughput (target: >20/sec)
  - Cleanup: Delete test tracks
  - **Note**: Test must FAIL initially (performance target not met)

- [X] **T018** [P] Integration test: Subsonic server connection in `/workspaces/emby-to-m3u/tests/integration/test_subsonic_live.py`
  - **LIVE SERVER TEST** (uses environment Subsonic instance)
  - Test: Connect to Subsonic API and fetch test playlist
  - Assert: Metadata includes MusicBrainz IDs when available
  - Assert: Track metadata properly formatted for normalization
  - Test: Fetch track audio stream for upload simulation
  - **Note**: Validates Subsonic integration is working

---

## Phase 3.3: Core Implementation (ONLY after tests are failing)

### Data Models (4 tasks - from data-model.md)

- [X] **T019** [P] Implement NormalizedMetadata dataclass in `/workspaces/emby-to-m3u/src/azuracast/models.py`
  - Frozen dataclass with fields: `artist`, `album`, `title`, `duration_seconds`, `musicbrainz_id`
  - Implement `fingerprint()` method: returns `"artist|album|title"`
  - Add type hints for all fields
  - Add docstrings explaining normalization contract
  - **Validates**: T004-T006 contract tests now pass

- [X] **T020** [P] Implement DetectionStrategy enum in `/workspaces/emby-to-m3u/src/azuracast/models.py`
  - Enum values: `MUSICBRAINZ_ID`, `NORMALIZED_METADATA`, `FILE_PATH`, `NONE`
  - Used for audit trail in UploadDecision
  - **Validates**: T009 contract test now passes

- [X] **T021** [P] Implement UploadDecision dataclass in `/workspaces/emby-to-m3u/src/azuracast/models.py`
  - Frozen dataclass with fields: `should_upload`, `reason`, `strategy_used`, `azuracast_file_id`
  - Implement `log_message()` method for formatted INFO-level logging
  - **Validates**: T007-T010 contract tests now pass

- [X] **T022** [P] Implement KnownTracksCache dataclass in `/workspaces/emby-to-m3u/src/azuracast/models.py`
  - Fields: `tracks`, `fetched_at`, `ttl_seconds` (default 300)
  - Methods: `is_expired()`, `get_tracks()`, `refresh()`, `invalidate()`
  - **Validates**: T011 contract test now passes

### Normalization Functions (3 tasks - from contracts/normalization.md)

- [X] **T023** [P] Implement normalize_string() in `/workspaces/emby-to-m3u/src/azuracast/normalization.py`
  - Strip whitespace, convert to lowercase
  - Normalize Unicode characters using `unicodedata.normalize('NFKD', ...)`
  - Remove/normalize special characters (keep spaces)
  - Collapse multiple spaces to single space
  - **Dependencies**: Python stdlib only (unicodedata, re)
  - **Validates**: T004 contract test now passes

- [X] **T024** [P] Implement normalize_artist() in `/workspaces/emby-to-m3u/src/azuracast/normalization.py`
  - Call `normalize_string()` first
  - Handle "The" prefix: remove if at start (not mid-string)
  - Remove featuring notation: "feat.", "ft.", "featuring"
  - Normalize artist separators: "&", "and", "," → single space
  - **Dependencies**: T023 (normalize_string)
  - **Validates**: T005 contract test now passes

- [X] **T025** [P] Implement build_track_fingerprint() in `/workspaces/emby-to-m3u/src/azuracast/normalization.py`
  - Extract artist, album, title from track dict
  - Normalize each field using `normalize_artist()` and `normalize_string()`
  - Return format: `"artist|album|title"`
  - Handle missing fields gracefully (use empty string)
  - **Dependencies**: T023, T024
  - **Validates**: T006 contract test now passes

### Detection Strategies (3 tasks - from contracts/duplicate-detection.md)

- [X] **T026** [P] Implement check_file_exists_by_musicbrainz() in `/workspaces/emby-to-m3u/src/azuracast/detection.py`
  - Build MBID index from known_tracks for O(1) lookup (performance optimization)
  - Check if track has `musicbrainz_id` field
  - Look up MBID in index
  - Return azuracast_file_id if match found, None otherwise
  - Log warning if multiple tracks have same MBID
  - **Dependencies**: T019 (NormalizedMetadata model)
  - **Validates**: T007 contract test now passes

- [X] **T027** [P] Implement check_file_exists_by_metadata() in `/workspaces/emby-to-m3u/src/azuracast/detection.py`
  - Build fingerprint index from known_tracks for O(1) lookup
  - Generate fingerprint for source track using `build_track_fingerprint()`
  - Look up fingerprint in index
  - If match: validate duration within ±5 seconds (FR-009)
  - Log warning if duration difference >5 seconds but <10 seconds
  - Return azuracast_file_id if match, None otherwise
  - **Dependencies**: T025 (build_track_fingerprint)
  - **Validates**: T008 contract test now passes

- [X] **T028** Implement check_file_in_azuracast() multi-strategy detection in `/workspaces/emby-to-m3u/src/azuracast/detection.py`
  - **NOT [P]**: Integrates T026 and T027 in same file
  - Strategy order: MBID (T026) → Metadata (T027) → File Path (future)
  - Detect source duplicates: track when multiple source tracks match same AzuraCast ID (FR-032)
  - Return UploadDecision with strategy_used and reason
  - Handle ReplayGain conflicts using T029
  - **Dependencies**: T026, T027, T021 (UploadDecision), T029 (ReplayGain check)
  - **Validates**: T009 contract test now passes

### Upload Decision Logic (2 tasks - from contracts/upload-decision.md)

- [X] **T029** [P] Implement should_skip_replaygain_conflict() in `/workspaces/emby-to-m3u/src/azuracast/detection.py`
  - Check if azuracast_track has ReplayGain metadata (any gain value present)
  - If present: return True (skip upload, preserve existing - FR-011)
  - If not present but source has ReplayGain: return False (upload needed - FR-013)
  - Neither has ReplayGain: return False (upload for other reasons)
  - **Dependencies**: None (standalone function)
  - **Validates**: T010 contract test now passes

- [X] **T030** Implement get_cached_known_tracks() in `/workspaces/emby-to-m3u/src/azuracast/cache.py`
  - **NOT [P]**: Modifies AzuraCastSync class state
  - Class-level cache variable: `_known_tracks_cache: Optional[KnownTracksCache] = None`
  - Check if cache exists and not expired
  - If cache valid: return cached tracks (FR-017)
  - If cache invalid/missing: fetch from `get_known_tracks()` API (FR-016)
  - Store in cache with current timestamp
  - **Dependencies**: T022 (KnownTracksCache model)
  - **Validates**: T011 contract test now passes

---

## Phase 3.4: Integration (6 tasks)

- [X] **T031** Refactor AzuraCastSync.__init__() to initialize cache in `/workspaces/emby-to-m3u/src/azuracast/main.py`
  - **NOT [P]**: Modifies existing main.py file
  - Add `_known_tracks_cache: Optional[KnownTracksCache] = None` class variable
  - Add `_cache_ttl: int` from environment variable `AZURACAST_CACHE_TTL` (default 300)
  - Add `_force_reupload: bool` from `AZURACAST_FORCE_REUPLOAD` (default False)
  - Add `_legacy_detection: bool` from `AZURACAST_LEGACY_DETECTION` (default False)
  - **Dependencies**: T022 (KnownTracksCache)

- [X] **T032** Refactor check_file_in_azuracast() to use new detection logic in `/workspaces/emby-to-m3u/src/azuracast/main.py`
  - **NOT [P]**: Same file as T031
  - Replace existing exact string matching (lines 164-193)
  - Call `get_cached_known_tracks()` instead of direct API call
  - Call new `check_file_in_azuracast()` from detection.py (T028)
  - Handle legacy detection mode fallback (if enabled)
  - Return UploadDecision instead of boolean
  - Update callers to use UploadDecision.should_upload
  - **Dependencies**: T028 (multi-strategy detection), T030 (cache), T031

- [X] **T033** Add rate limit handling to _perform_request() in `/workspaces/emby-to-m3u/src/azuracast/main.py`
  - **NOT [P]**: Same file as T031, T032
  - Add 429 status code handling in retry loop
  - Implement exponential backoff with jitter: base=1.5s, max=80s
  - Respect Retry-After header if present in response
  - Log rate limit events at WARNING level
  - Max 6 retry attempts before failure
  - **Dependencies**: T031 (config changes)
  - **Validates**: T012 contract test now passes

- [X] **T034** Update upload_playlist() to show progress reporting in `/workspaces/emby-to-m3u/src/azuracast/main.py`
  - **NOT [P]**: Same file as T031-T033
  - Pre-fetch known tracks once using `get_cached_known_tracks()`
  - Count tracks needing upload before starting (FR-021)
  - Display "X of Y tracks need upload" message
  - Log skip reason for each duplicate (FR-022)
  - Generate summary report at end: uploaded/skipped/errors (FR-023)
  - **Dependencies**: T030 (cache), T032 (new detection)

- [X] **T035** Configure INFO-level logging for duplicate decisions in `/workspaces/emby-to-m3u/src/azuracast/main.py`
  - **NOT [P]**: Same file as T031-T034
  - Update logger calls to use INFO level for duplicate decisions (FR-030)
  - Include strategy used in log messages
  - Include skip reasons in structured format
  - Add debug-level logging for normalization steps
  - **Dependencies**: T032 (detection with UploadDecision)

- [X] **T036** Add configuration validation and defaults in `/workspaces/emby-to-m3u/src/azuracast/main.py`
  - **NOT [P]**: Same file as T031-T035
  - Validate AZURACAST_CACHE_TTL is integer >0 (default 300)
  - Validate boolean environment variables (true/false/1/0)
  - Log configuration values at startup (INFO level)
  - Document all 4 new environment variables in docstrings
  - **Dependencies**: T031 (config setup)

---

## Phase 3.5: Polish (4 tasks)

- [X] **T037** [P] Unit tests for edge cases in `/workspaces/emby-to-m3u/tests/unit/test_edge_cases.py`
  - Empty artist/album/title handling
  - Malformed Unicode in metadata
  - Very long strings (>1000 chars) in normalization
  - Cache expiration edge cases (exactly at TTL boundary)
  - Concurrent source duplicates (3+ tracks → same AzuraCast track)
  - **Dependencies**: T023-T030 (all core implementations)

- [X] **T038** [P] Performance validation: 1000 track benchmark in `/workspaces/emby-to-m3u/tests/integration/test_performance_1000.py`
  - **LIVE SERVER TEST** (extended benchmark)
  - Setup: 1000-track test library in AzuraCast
  - Execute: Full duplicate detection run
  - Assert: Completes in <30 seconds (FR-020)
  - Measure: Cache hit rate (should be 100% after first fetch)
  - Measure: Memory usage (<10MB for cache)
  - **Dependencies**: T030 (cache), T032 (detection)

- [X] **T039** [P] Update documentation in `/workspaces/emby-to-m3u/specs/002-fix-azuracast-duplicate/`
  - Add implementation summary to plan.md
  - Document all 4 new environment variables in README
  - Add migration guide for existing users (legacy mode)
  - Document performance benchmarks achieved
  - Add troubleshooting section for common issues
  - **Dependencies**: T038 (performance validated)

- [X] **T040** Run full quickstart.md validation workflow
  - **NOT [P]**: Sequential validation workflow
  - Execute all 10 phases from quickstart.md against live servers
  - Verify all 30+ success criteria pass
  - Document actual performance metrics achieved
  - Generate final test report
  - **Dependencies**: ALL previous tasks (T001-T039)

---

## Dependencies Graph

```
Setup (T001-T003) → All other tasks

Tests (T004-T018) → Implementation (T019-T036)
  └─ Must FAIL before implementation starts

Models (T019-T022) → Detection & Cache (T023-T030)
  ├─ T019 (NormalizedMetadata) → T026 (MBID detection)
  ├─ T020 (DetectionStrategy) → T009 (contract test)
  ├─ T021 (UploadDecision) → T028 (multi-strategy)
  └─ T022 (KnownTracksCache) → T030 (caching)

Normalization (T023-T025) → Detection (T026-T028)
  ├─ T023 (normalize_string) → T024, T025
  ├─ T024 (normalize_artist) → T025
  └─ T025 (fingerprint) → T027, T028

Detection (T026-T028) + Cache (T030) → Integration (T031-T036)
  └─ All implement in main.py sequentially (T031→T032→T033→T034→T035→T036)

Integration (T031-T036) → Polish (T037-T040)
  └─ T038 (1000 track benchmark) → T039 (docs) → T040 (final validation)
```

---

## Parallel Execution Batches

### Batch 1: Setup (can run in parallel with test writing)
```bash
# T001 and T003 in parallel:
Task("Create directory structure", "...", "coder")
Task("Configure environment variables", "...", "coder")
```

### Batch 2: Contract Tests (all different files, fully parallel)
```bash
# T004-T012 all in parallel:
Task("Contract test normalize_string()", "tests/contract/test_normalization.py", "tester")
Task("Contract test normalize_artist()", "tests/contract/test_normalization.py", "tester")
Task("Contract test build_track_fingerprint()", "tests/contract/test_normalization.py", "tester")
Task("Contract test check_file_exists_by_musicbrainz()", "tests/contract/test_duplicate_detection.py", "tester")
Task("Contract test check_file_exists_by_metadata()", "tests/contract/test_duplicate_detection.py", "tester")
Task("Contract test check_file_in_azuracast()", "tests/contract/test_duplicate_detection.py", "tester")
Task("Contract test should_skip_replaygain_conflict()", "tests/contract/test_upload_decision.py", "tester")
Task("Contract test get_cached_known_tracks()", "tests/contract/test_upload_decision.py", "tester")
Task("Contract test rate limit backoff", "tests/contract/test_rate_limiting.py", "tester")
```

### Batch 3: Integration Tests (all different files, fully parallel)
```bash
# T013-T018 all in parallel:
Task("Integration test: Initial upload", "tests/integration/test_azuracast_live.py", "tester")
Task("Integration test: Duplicate detection", "tests/integration/test_azuracast_live.py", "tester")
Task("Integration test: Normalization", "tests/integration/test_normalization_live.py", "tester")
Task("Integration test: ReplayGain", "tests/integration/test_replaygain_live.py", "tester")
Task("Integration test: Performance 100", "tests/integration/test_performance_live.py", "tester")
Task("Integration test: Subsonic", "tests/integration/test_subsonic_live.py", "tester")
```

### Batch 4: Models (all in same file, but independent dataclasses - can parallelize)
```bash
# T019-T022 all in parallel:
Task("Implement NormalizedMetadata", "src/azuracast/models.py", "coder")
Task("Implement DetectionStrategy", "src/azuracast/models.py", "coder")
Task("Implement UploadDecision", "src/azuracast/models.py", "coder")
Task("Implement KnownTracksCache", "src/azuracast/models.py", "coder")
```

### Batch 5: Normalization & Detection (different files, parallel groups)
```bash
# T023-T025 (normalization.py) in parallel:
Task("Implement normalize_string()", "src/azuracast/normalization.py", "coder")
Task("Implement normalize_artist()", "src/azuracast/normalization.py", "coder")
Task("Implement build_track_fingerprint()", "src/azuracast/normalization.py", "coder")

# THEN T026-T029 (detection.py) in parallel:
Task("Implement check_file_exists_by_musicbrainz()", "src/azuracast/detection.py", "coder")
Task("Implement check_file_exists_by_metadata()", "src/azuracast/detection.py", "coder")
Task("Implement should_skip_replaygain_conflict()", "src/azuracast/detection.py", "coder")
# T028 waits for T026, T027
```

### Batch 6: Cache (separate file)
```bash
# T030 standalone:
Task("Implement get_cached_known_tracks()", "src/azuracast/cache.py", "coder")
```

### Batch 7: Integration (SEQUENTIAL - all modify main.py)
```bash
# T031-T036 MUST run in order (same file):
1. T031: Initialize cache
2. T032: Refactor detection
3. T033: Add rate limiting
4. T034: Progress reporting
5. T035: Logging configuration
6. T036: Config validation
```

### Batch 8: Polish (parallel where possible)
```bash
# T037-T039 in parallel:
Task("Unit tests for edge cases", "tests/unit/test_edge_cases.py", "tester")
Task("Performance 1000 track benchmark", "tests/integration/test_performance_1000.py", "tester")
Task("Update documentation", "specs/002-fix-azuracast-duplicate/", "reviewer")

# T040 LAST (sequential):
Task("Run full quickstart validation", "...", "tester")
```

---

## Validation Checklist
*GATE: Verify before marking tasks complete*

- [x] All contracts have corresponding tests (9 contracts → 9 test tasks T004-T012) ✅
- [x] All entities have model tasks (4 entities → 4 model tasks T019-T022) ✅
- [x] All tests come before implementation (T004-T018 before T019-T040) ✅
- [x] Parallel tasks truly independent (verified file paths) ✅
- [x] Each task specifies exact file path ✅
- [x] No task modifies same file as another [P] task ✅
- [x] TDD workflow enforced (tests MUST FAIL before implementation) ✅
- [x] Live server testing included (T013-T018, T038, T040) ✅
- [x] Performance benchmarks included (T017, T038) ✅
- [x] All FR requirements covered by tasks ✅

---

## Notes

- **[P] tasks**: 25 tasks can run in parallel (different files, no dependencies)
- **Sequential tasks**: 15 tasks must run in order (same file or dependency chain)
- **TDD Critical**: Verify ALL contract/integration tests FAIL before starting T019
- **Live Server Tests**: T013-T018, T038, T040 require environment servers configured
- **Performance Targets**: T017 (<5s/100 tracks), T038 (<30s/1000 tracks)
- **Zero New Dependencies**: All stdlib implementation (from research.md)
- **Commit Strategy**: Commit after each task completion
- **Test Coverage Goal**: 90% minimum (pytest-cov)

## Total Tasks: 40
- Setup: 3 tasks
- Tests: 15 tasks (9 contract + 6 integration)
- Models: 4 tasks
- Normalization: 3 tasks
- Detection: 4 tasks (3 strategies + 1 integration)
- Cache: 1 task
- Integration: 6 tasks (main.py refactoring)
- Polish: 4 tasks

**Estimated Duration**: 2-3 days for full implementation and validation
**Critical Path**: T001→T004-T018→T019-T022→T023-T030→T031-T036→T037-T040
