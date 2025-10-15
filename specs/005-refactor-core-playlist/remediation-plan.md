# Implementation Plan: Tool Calling Remediation - Production Readiness

**Branch**: `005-refactor-core-playlist` | **Date**: 2025-10-07 | **Spec**: [remediation-tasks.md](./remediation-tasks.md)
**Input**: Remediation tasks from `/workspaces/emby-to-m3u/specs/005-refactor-core-playlist/remediation-tasks.md`
**Prerequisites**: T094-T102 complete (tool calling infrastructure implemented)

## Execution Flow (/plan command scope)
```
✅ 1. Load remediation tasks from Input path
✅ 2. Fill Technical Context (based on existing implementation)
✅ 3. Fill Constitution Check section
✅ 4. Evaluate Constitution Check → Proceed
✅ 5. Execute Phase 0 → Analysis of existing implementation issues
✅ 6. Execute Phase 1 → Test design (T104-T107)
✅ 7. Re-evaluate Constitution Check → PASS
✅ 8. Plan Phase 2 → Implementation fixes (T108-T111)
✅ 9. READY for /implement command
```

**STATUS**: Plan complete, ready for remediation implementation

---

## Summary

Remediate 4 critical production issues in the tool calling refactor (T094-T102) to ensure production readiness:
1. **LLM Response Parsing**: Replace fragile regex parsing with robust JSON parsing
2. **Iteration Limits**: Increase from 10→15, add adaptive early stopping
3. **Timeout Handling**: Add per-tool (10s) and total timeouts with graceful degradation
4. **Error Recovery**: Implement fallback strategies and structured error responses

**Key Change**: Transform proof-of-concept tool calling infrastructure into production-ready system with comprehensive error handling, performance optimization, and validation.

---

## Technical Context

**Language/Version**: Python 3.13
**Primary Dependencies**:
- OpenAI SDK (function calling, multi-turn conversations) - EXISTING
- Subsonic/Emby API client (async track queries) - EXISTING
- tiktoken (token counting) - EXISTING
- pytest + pytest-asyncio (TDD with real APIs) - EXISTING

**Storage**:
- File-based: station-identity.md, M3U playlists, JSON metadata, decision logs
- MCP memory: features/tool-calling-refactor/* (architecture, progress, validation)
- No database required (stateless generation)

**Testing**:
- pytest with 90% coverage requirement
- NEW: T104-T107 edge case tests (JSON parsing, timeouts, errors)
- Integration tests with REAL Subsonic + OpenAI endpoints
- Tool calling traces with performance metrics

**Target Platform**: Linux server (production), Docker-compatible, GitHub Actions CI/CD

**Project Type**: Single project (Python CLI with library modules)

**Performance Goals**:
- Playlist generation: <5 minutes per daypart (with tool calls + error handling)
- Tool execution: <10s per Subsonic query (NEW timeout)
- Total batch: <30 minutes for 6-daypart full broadcast day
- Error recovery: <2s overhead per failure

**Constraints**:
- OpenAI API cost: $0.01-0.05 per playlist (existing target)
- Tool call depth: 10→15 max iterations (INCREASED)
- Memory: <500MB for batch generation
- Timeout: 120s total per playlist (NEW)

**Scale/Scope**:
- 6 dayparts per broadcast day
- 10-70 tracks per daypart
- 100K+ track library (Subsonic)
- 3-15 tool calls per playlist (typical range)
- Daily regeneration with production SLA

---

## Constitution Check
*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### ✅ PASS - All Gates Satisfied

**I. Claude Flow Hive-Mind Architecture**:
- ✅ Multi-file remediation uses Claude Flow coordination
- ✅ Feature namespace: `features/tool-calling-refactor/remediation`
- ✅ Agents: `tester` (T104-T107), `backend-dev` (T108-T111), `perf-analyzer` (T114)
- ✅ MCP memory usage: Remediation progress, test results, benchmarks in `features/tool-calling-refactor/remediation/*`
- ✅ BatchTool: T104-T107 parallel (tests), T115-T117 parallel (docs)
- ✅ Truth verification: Real-world testing with production-like scenarios

**II. Multi-Agent Coordination**:
- ✅ Tester: T104-T107 (edge case tests), T112 (integration), T113 (manual validation)
- ✅ Backend dev: T108-T111 (implementation fixes)
- ✅ Performance analyzer: T114 (benchmarking)
- ✅ Namespace: `features/tool-calling-refactor/remediation/tests`, `features/tool-calling-refactor/remediation/implementation`

**III. Test-Driven Development (TDD)**:
- ✅ 90% coverage maintained (new tests increase coverage)
- ✅ Tests BEFORE implementation: T104-T107 → T108-T111
- ✅ Tests MUST FAIL initially (capturing current issues)
- ✅ Real endpoint testing: T106 (timeouts), T107 (errors)

**IV. Code Quality Standards**:
- ✅ Type hints throughout (existing)
- ✅ Docstrings for remediation methods
- ✅ Error handling with typed exceptions
- ✅ Logging at INFO/DEBUG for timeout/error scenarios

**V. Source-Agnostic Architecture**:
- ✅ No Subsonic-specific logic in LLM client (SubsonicTools abstraction)
- ✅ Generic error recovery patterns
- ✅ Pluggable timeout strategies

**VI. AI-Enhanced Playlist Generation**:
- ✅ Tool calling infrastructure complete (T094-T102)
- ✅ Remediation improves robustness without changing AI approach
- ✅ JSON parsing enables structured AI responses

**VII. Security & Deployment**:
- ✅ No secrets in code (environment variables)
- ✅ Error messages don't leak sensitive data
- ✅ Timeouts prevent DoS from slow queries

---

## Project Structure

### Documentation (this remediation)
```
specs/005-refactor-core-playlist/
├── plan.md                      # Original feature plan (T094-T102)
├── remediation-tasks.md         # This remediation tasks (T103-T117)
├── remediation-plan.md          # This file
├── tool-calling-tasks.md        # Original tasks (T094-T102 complete)
└── docs/
    ├── tool-calling-validation-checklist.md  # T102 output (UPDATE: T115)
    └── tool-calling-monitoring.md            # T117 output (NEW)
```

### Source Code (modified files)
```
src/ai_playlist/
├── openai_client.py             # T108, T109, T110, T111 (JSON parsing, timeouts, errors)
├── subsonic_tools.py            # T110, T111 (per-tool timeouts, error recovery)
└── batch_executor.py            # No changes (uses updated openai_client)

tests/integration/
├── test_tool_calling.py         # T105 (UPDATE: iteration limits)
├── test_llm_response_parsing.py # T104 (NEW: JSON parsing tests)
├── test_tool_calling_timeouts.py # T106 (NEW: timeout tests)
└── test_tool_error_handling.py  # T107 (NEW: error recovery tests)

tests/performance/
└── test_tool_calling_benchmark.py # T114 (NEW: performance benchmarks)
```

**Structure Decision**: Single project structure. All remediation work in existing `src/ai_playlist/` and `tests/` directories. New test files for edge cases, updates to existing `openai_client.py` and `subsonic_tools.py`.

---

## Phase 0: Analysis & Research

**Objective**: Analyze existing tool calling implementation (T094-T102) to identify specific failure modes requiring remediation.

### Issue Analysis

**1. LLM Response Parsing (T104, T108)**
- **Current State**: Regex-based parsing in `_parse_tracks_from_response()` (lines 463-560)
- **Problem**: Fragile patterns like `Track ID: <id>`, `Position: <number>`, may miss tracks
- **Research Needed**:
  - OpenAI structured outputs best practices
  - JSON schema validation approaches
  - Error recovery for malformed responses
- **Decision**: Use JSON array format with strict validation
- **Rationale**: Structured data eliminates ambiguity, enables schema validation, integrates with OpenAI's structured outputs (if available)
- **Alternatives Considered**: XML (too verbose), YAML (parsing complexity)

**2. Tool Call Iteration Limits (T105, T109)**
- **Current State**: Hard limit of 10 iterations in `call_llm()` (line 327)
- **Problem**: Complex playlists (5 genres, 3 eras, BPM progression) may need 12-15 calls
- **Research Needed**:
  - Analyze tool call patterns from existing logs (if available)
  - Determine optimal max_iterations based on complexity
  - Early stopping heuristics
- **Decision**: Increase to 15, add efficiency tracking, early stop if no progress
- **Rationale**: Balances flexibility with cost control, prevents infinite loops while allowing complex requirements
- **Alternatives Considered**: Dynamic limits based on spec complexity (too unpredictable), no limit (unsafe)

**3. Timeout Handling (T106, T110)**
- **Current State**: Overall timeout via `asyncio.wait_for()`, no per-tool timeouts
- **Problem**: Single slow Subsonic query hangs entire generation (e.g., `get_newly_added_tracks` timeout)
- **Research Needed**:
  - Subsonic API latency patterns (p50, p95, p99)
  - Retry strategies for transient failures
  - Partial result handling
- **Decision**: 10s per tool call, 120s total, exponential backoff retry (2 attempts)
- **Rationale**: Reasonable balance between slow queries and legitimate processing time
- **Alternatives Considered**: 5s per tool (too aggressive), no retries (ignores transient failures)

**4. Error Recovery (T107, T111)**
- **Current State**: Tool execution failures raise exceptions, crash generation
- **Problem**: Subsonic 500 error or network failure aborts entire batch
- **Research Needed**:
  - Common Subsonic error scenarios
  - Fallback tool selection strategies
  - Structured error format for LLM consumption
- **Decision**: Return structured errors with fallback suggestions, LLM continues conversation
- **Rationale**: Graceful degradation maintains partial functionality, LLM can adapt strategy
- **Alternatives Considered**: Fail-fast (too brittle), silent failures (hides issues)

**Output**: `/workspaces/emby-to-m3u/specs/005-refactor-core-playlist/research-remediation.md`

---

## Phase 1: Design & Contracts

*Prerequisites: Phase 0 analysis complete*

### Test Design (T104-T107)

**T104: JSON Parsing Tests**
- File: `tests/integration/test_llm_response_parsing.py` (NEW)
- Contracts:
  ```python
  def test_json_array_parsing():
      # LLM returns: [{"track_id": "123", "title": "Song", "artist": "Artist", ...}]
      # Expected: List[SelectedTrack] with validated fields

  def test_malformed_json_recovery():
      # LLM returns: Partial JSON or markdown-wrapped JSON
      # Expected: Raise clear error with retry suggestion

  def test_missing_required_fields():
      # LLM returns: JSON missing "track_id"
      # Expected: ValidationError with specific field
  ```

**T105: Iteration Limit Tests**
- File: `tests/integration/test_tool_calling.py` (UPDATE)
- New test methods:
  ```python
  def test_complex_playlist_within_15_iterations():
      # Spec: 5 genres, 3 eras, BPM progression
      # Expected: Completes in <15 tool calls

  def test_early_stopping_on_no_progress():
      # Mock: Last 3 calls return empty results
      # Expected: Stop early, return partial results

  def test_iteration_limit_warning_at_80_percent():
      # Tool calls: 12/15 used
      # Expected: Log warning "approaching limit"
  ```

**T106: Timeout Tests**
- File: `tests/integration/test_tool_calling_timeouts.py` (NEW)
- Contracts:
  ```python
  def test_per_tool_timeout_10_seconds():
      # Mock: search_tracks takes 12s
      # Expected: TimeoutError after 10s

  def test_total_timeout_120_seconds():
      # Mock: 10 tool calls × 11s each = 110s (OK), 11 calls × 11s = 121s (fail)
      # Expected: TimeoutError after 120s total

  def test_partial_results_on_timeout():
      # Mock: Timeout after finding 5/10 tracks
      # Expected: Return Playlist with 5 tracks + metadata indicating partial
  ```

**T107: Error Recovery Tests**
- File: `tests/integration/test_tool_error_handling.py` (NEW)
- Contracts:
  ```python
  def test_search_tracks_failure_tries_alternative():
      # Mock: search_tracks returns error
      # Expected: LLM receives structured error, tries browse_artists

  def test_all_tools_fail_returns_informative_error():
      # Mock: All tools return errors
      # Expected: Clear error message (not crash), suggests manual intervention

  def test_invalid_tool_result_validation():
      # Mock: Tool returns non-numeric track_id
      # Expected: Validation error, tool result rejected
  ```

### Implementation Contracts

**T108: JSON Parsing Implementation**
- File: `src/ai_playlist/openai_client.py`
- Changes:
  - `_build_prompt_template()`: Update output format section to request JSON array
  - `_parse_tracks_from_response()`: Replace regex with `json.loads()` + Pydantic validation
  - Add `_validate_track_json()`: Schema validation for each track object
- Contract:
  ```python
  def _parse_tracks_from_response(self, content: str, target_count: int) -> List[SelectedTrack]:
      """
      Parse JSON array of tracks from LLM response.

      Expected format:
      [
        {"track_id": "123", "title": "Song", "artist": "Artist", "reason": "..."},
        ...
      ]

      Raises:
          json.JSONDecodeError: If response is not valid JSON
          ValidationError: If required fields missing or invalid
      """
  ```

**T109: Adaptive Iteration Limits**
- File: `src/ai_playlist/openai_client.py`
- Changes:
  - Add `max_iterations` parameter (default 15)
  - Track efficiency: `new_tracks_per_call = len(current_tracks) - len(previous_tracks)`
  - Early stop if `new_tracks_per_call == 0` for last 3 calls
  - Log warning at 80% (12/15 calls)
- Contract:
  ```python
  async def call_llm(
      self,
      request: LLMTrackSelectionRequest,
      subsonic_tools: SubsonicTools,
      max_iterations: int = 15  # INCREASED from 10
  ) -> LLMTrackSelectionResponse:
      """
      Multi-turn LLM conversation with adaptive early stopping.

      Returns:
          LLMTrackSelectionResponse with metadata:
          {
            "tool_calls_used": int,
            "efficiency": float,  # tracks_per_call
            "stopped_early": bool
          }
      """
  ```

**T110: Timeout Handling**
- Files: `src/ai_playlist/subsonic_tools.py`, `src/ai_playlist/openai_client.py`
- Changes:
  - Wrap each `execute_tool()` with `asyncio.wait_for(timeout=10.0)`
  - Add retry logic: `for attempt in range(2)` with exponential backoff
  - Track total elapsed time in `call_llm()`, raise TimeoutError if >120s
  - Save partial results to MCP memory before timeout
- Contracts:
  ```python
  async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
      """
      Execute tool with 10s timeout and retry logic.

      Raises:
          TimeoutError: If tool execution exceeds 10s after 2 attempts

      Returns partial results if timeout during multi-item query.
      """
  ```

**T111: Error Recovery**
- Files: `src/ai_playlist/subsonic_tools.py`, `src/ai_playlist/openai_client.py`
- Changes:
  - Add structured error responses in `execute_tool()`:
    ```python
    {
      "error": "search_tracks failed: ConnectionError",
      "fallback_suggested": "browse_artists",
      "tracks": [],  # Empty but valid structure
      "error_code": "SUBSONIC_UNAVAILABLE"
    }
    ```
  - Update system prompt to include error handling instructions
  - Validate tool results before returning (check track_id format, required fields)
  - Log all errors to decision logger
- Contract:
  ```python
  async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
      """
      Execute tool with comprehensive error handling.

      Never raises exceptions. Returns structured error response on failure.

      Returns:
          On success: {"tracks": [...], "count": N}
          On failure: {"error": "...", "fallback_suggested": "...", "tracks": [], "error_code": "..."}
      """
  ```

### Agent File Update

Per constitution requirement, update `CLAUDE.md` incrementally:
```bash
.specify/scripts/bash/update-agent-context.sh claude
```

Updates:
- Recent changes: Tool calling remediation (T103-T117)
- New tech: JSON schema validation, adaptive iteration control
- Key patterns: Structured error responses, graceful degradation

**Output**: Updated `/workspaces/emby-to-m3u/CLAUDE.md` (O(1) operation, <150 lines)

---

## Phase 2: Task Planning Approach
*This section describes remediation tasks - already complete in remediation-tasks.md*

**Task Generation Strategy**: Already complete in `remediation-tasks.md` (T103-T117)

**Tasks Summary**:
- T103: Baseline testing (5 min)
- T104-T107: Edge case tests [P] (2-3 hours parallel)
- T108-T111: Implementation fixes (4-5 hours sequential)
- T112-T114: Integration & benchmarking (2 hours)
- T115-T117: Documentation [P] (1 hour parallel)

**Total**: 9-11 hours with parallelization

**Ordering**:
- TDD: Tests (T104-T107) before implementation (T108-T111)
- Sequential: T108-T111 (same files, conflict risk)
- Parallel: T104-T107 (different files), T115-T117 (different files)

**IMPORTANT**: Tasks already defined in `remediation-tasks.md`, ready for `/implement` command

---

## Phase 3+: Future Implementation
*These phases are beyond the scope of the /plan command*

**Phase 3**: Task execution (T103-T117 in remediation-tasks.md)
**Phase 4**: Production validation (T113 manual verification + T114 benchmarking)
**Phase 5**: Monitoring setup (T117 production monitoring guide)

---

## Complexity Tracking
*No constitutional violations - remediation fits within existing architecture*

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| N/A | N/A | N/A |

**Justification**: Remediation work stays within single-project architecture, uses existing patterns, requires no new external dependencies beyond what T094-T102 established.

---

## Progress Tracking
*This checklist is updated during execution flow*

**Phase Status**:
- [x] Phase 0: Analysis complete (Issue identification in remediation-tasks.md)
- [x] Phase 1: Test design complete (T104-T107 contracts defined)
- [x] Phase 2: Task planning complete (remediation-tasks.md)
- [ ] Phase 3: Tasks executed (T103-T117)
- [ ] Phase 4: Production validation passed (T113, T114)
- [ ] Phase 5: Monitoring operational (T117)

**Gate Status**:
- [x] Initial Constitution Check: PASS
- [x] Post-Design Constitution Check: PASS
- [x] All unknowns resolved (no NEEDS CLARIFICATION)
- [x] Complexity deviations documented (none)

**Remediation Readiness**:
- [x] T094-T102 complete (tool calling infrastructure)
- [x] Issues identified (4 critical production blockers)
- [x] Tests designed (T104-T107)
- [x] Implementation contracts defined (T108-T111)
- [ ] Tests passing (T112)
- [ ] Production validated (T113)
- [ ] Benchmarks acceptable (T114)

---

**NEXT STEP**: Execute `/implement` command with remediation-tasks.md to begin TDD cycle (T103→T104-T107→T108-T111→T112-T114→T115-T117)

---
*Based on Constitution v1.0.0 - See `.specify/memory/constitution.md`*
*Builds on: tool-calling-tasks.md (T094-T102) + plan.md (original feature)*
