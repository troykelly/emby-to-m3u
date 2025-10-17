# Tasks: Tool Calling Remediation - LLM Response Parsing & Robustness

**Input**: Design documents from `/workspaces/emby-to-m3u/specs/005-refactor-core-playlist/`
**Prerequisites**: plan.md, tool-calling-tasks.md (T094-T102 complete)
**Context**: Tool calling infrastructure complete but needs robustness improvements for production use

## Execution Flow
```
1. Load plan.md and tool-calling-tasks.md
2. Identify remediation needs:
   → LLM response parsing robustness
   → Tool call iteration limits
   → Timeout handling for multi-turn conversations
   → Error recovery for tool execution failures
3. Generate remediation tasks in TDD order:
   → Tests first (validate failure modes)
   → Implementation (fix issues)
   → Integration (end-to-end validation)
4. Apply parallel execution where possible
5. Validate: All production edge cases covered
```

## Format: `[ID] [P?] Description`
- **[P]**: Can run in parallel (different files, no dependencies)
- All paths are absolute from `/workspaces/emby-to-m3u/`

---

## Phase R1: Setup & Validation

- [ ] **T103** Run existing tool calling test to establish baseline
  - **File**: `tests/integration/test_tool_calling.py`
  - **Command**: `python -m pytest tests/integration/test_tool_calling.py::TestToolCallingWorkflow::test_llm_uses_tools_to_discover_tracks -v -s`
  - **Success Criteria**: Understand current failure modes (if any)
  - **Dependencies**: None

---

## Phase R2: Tests First (TDD) - Validate Failure Modes

**CRITICAL: These tests capture edge cases that will fail with current implementation**

- [ ] **T104 [P]** Test LLM returns track IDs in JSON format (strict parsing)
  - **File**: `tests/integration/test_llm_response_parsing.py` (NEW)
  - **Purpose**: Validate structured JSON response parsing instead of regex
  - **Test Cases**:
    - LLM returns valid JSON array of track objects
    - LLM returns track IDs with full metadata
    - Parser handles missing fields gracefully
    - Parser validates track ID format (numeric strings)
  - **Expected**: FAIL (current regex parser won't handle JSON)
  - **Dependencies**: None

- [ ] **T105 [P]** Test tool call iteration limits with complex playlists
  - **File**: `tests/integration/test_tool_calling.py` (UPDATE)
  - **Purpose**: Validate max_iterations (10) is sufficient for production
  - **Test Cases**:
    - Complex playlist (5 genres, 3 eras, BPM progression) completes in <10 calls
    - If exceeds 10 calls, system degrades gracefully (returns partial results)
    - Log warning when approaching iteration limit (8+ calls)
  - **Expected**: MAY FAIL (10 iterations might not be enough)
  - **Dependencies**: None

- [ ] **T106 [P]** Test timeout handling for slow tool execution
  - **File**: `tests/integration/test_tool_calling_timeouts.py` (NEW)
  - **Purpose**: Validate system handles slow Subsonic queries
  - **Test Cases**:
    - Single tool call timeout (>5s) raises TimeoutError
    - Overall playlist generation timeout (>120s) raises TimeoutError
    - Partial results saved if timeout occurs mid-generation
    - Retry logic for transient Subsonic failures
  - **Expected**: FAIL (no timeout handling for individual tool calls)
  - **Dependencies**: None

- [ ] **T107 [P]** Test tool execution error recovery
  - **File**: `tests/integration/test_tool_error_handling.py` (NEW)
  - **Purpose**: Validate graceful degradation when tools fail
  - **Test Cases**:
    - `search_tracks()` returns empty → LLM tries alternative tools
    - `get_available_genres()` fails → LLM falls back to broad search
    - All tools fail → System returns informative error (not crash)
    - Tool returns invalid data → Parser validates and rejects
  - **Expected**: FAIL (no error recovery, system will crash)
  - **Dependencies**: None

---

## Phase R3: Core Implementation - Fix Issues

**ONLY after tests are written and failing**

- [ ] **T108** Replace regex parsing with structured JSON response
  - **File**: `src/ai_playlist/openai_client.py`
  - **Changes**:
    - Update `_build_prompt_template()` lines 185-194 to request JSON array format:
      ```
      **Output Format:**
      After exploring with tools, return ONLY a JSON array (no markdown):
      [
        {"track_id": "123", "title": "Song", "artist": "Artist", "reason": "..."},
        ...
      ]
      ```
    - Rewrite `_parse_tracks_from_response()` lines 463-560 to parse JSON instead of regex
    - Add JSON validation with `json.loads()` + try/except
    - Validate required fields: track_id, title, artist
    - Handle malformed JSON with detailed error messages
  - **Testing**: T104 should now PASS
  - **Dependencies**: T104 (test must fail first)

- [ ] **T109** Implement adaptive iteration limits with early stopping
  - **File**: `src/ai_playlist/openai_client.py`
  - **Changes**:
    - Add `adaptive_max_iterations` parameter to `call_llm()` (default: 15, increased from 10)
    - Track tool call efficiency: if last 3 calls returned no new tracks, stop early
    - Log warning at 80% of max_iterations (e.g., "8/10 calls used, consider simplifying criteria")
    - Add metadata to response: `{"tool_calls_used": N, "efficiency": X%}`
  - **Testing**: T105 should now PASS
  - **Dependencies**: T105 (test must fail first)

- [ ] **T110** Add per-tool and total timeouts with graceful degradation
  - **File**: `src/ai_playlist/subsonic_tools.py`
  - **Changes**:
    - Wrap each `execute_tool()` call with `asyncio.wait_for(timeout=10.0)` (10s per tool)
    - Add retry logic for transient failures (max 2 retries with exponential backoff)
    - Return partial results if timeout occurs (e.g., 5/10 tracks found)
    - Log tool execution times for performance monitoring
  - **File**: `src/ai_playlist/openai_client.py`
  - **Changes**:
    - Update `call_llm()` to track total elapsed time
    - Raise TimeoutError if total time exceeds `request.timeout_seconds`
    - Save partial state to MCP memory before raising timeout
  - **Testing**: T106 should now PASS
  - **Dependencies**: T106 (test must fail first)

- [ ] **T111** Implement tool execution error recovery and fallbacks
  - **File**: `src/ai_playlist/subsonic_tools.py`
  - **Changes**:
    - Add `try/except` around all Subsonic API calls in `execute_tool()`
    - Return structured error responses (not exceptions):
      ```python
      {"error": "search_tracks failed", "fallback_suggested": "browse_artists", "tracks": []}
      ```
    - Validate tool results before returning (check track IDs are numeric, required fields present)
    - Log all tool errors to decision logger for debugging
  - **File**: `src/ai_playlist/openai_client.py`
  - **Changes**:
    - Update system prompt to include error handling instructions:
      ```
      If a tool returns an error, try an alternative approach.
      If all tools fail, return your best guess with available information.
      ```
    - Parse error responses from tools and continue conversation (don't crash)
  - **Testing**: T107 should now PASS
  - **Dependencies**: T107 (test must fail first)

---

## Phase R4: Integration & Validation

- [ ] **T112** Run full integration test suite with remediation fixes
  - **Files**: All tests in `tests/integration/`
  - **Command**: `python -m pytest tests/integration/ -v -s --tb=short`
  - **Success Criteria**:
    - All tests pass (T103-T107, original tests)
    - No regressions in existing functionality
    - Tool calling works end-to-end with production-like scenarios
  - **Dependencies**: T108-T111 (all fixes implemented)

- [ ] **T113** Manual verification with full station identity (20 playlists)
  - **File**: Manual testing
  - **Command**: `python -m src.ai_playlist --input station-identity.md --output /tmp/playlists-production-test --max-cost 5.00 --dry-run`
  - **Success Criteria**:
    - All 6 dayparts generated successfully
    - Logs show tool calls (3-15 per playlist)
    - No timeouts or crashes
    - Playlists meet all constraints
    - Total cost <$5.00
    - M3U files created with valid tracks
  - **Validation Checklist**: Use `/workspaces/emby-to-m3u/docs/tool-calling-validation-checklist.md`
  - **Dependencies**: T112 (all tests passing)

- [ ] **T114** Performance benchmarking: tool calling vs original approach
  - **File**: `tests/performance/test_tool_calling_benchmark.py` (NEW)
  - **Purpose**: Measure performance impact of tool calling
  - **Metrics**:
    - Time per playlist: <5 minutes (target)
    - Cost per playlist: $0.01-0.05 (within budget)
    - Tool calls per playlist: 3-15 (reasonable)
    - Success rate: >95% (production ready)
  - **Compare**: Tool calling vs original 10K-track pre-fetch (if data available)
  - **Dependencies**: T113 (manual verification complete)

---

## Phase R5: Documentation & Polish

- [ ] **T115 [P]** Update tool-calling-validation-checklist.md with new tests
  - **File**: `docs/tool-calling-validation-checklist.md`
  - **Updates**:
    - Add T104-T107 test commands to validation steps
    - Document JSON response format requirements
    - Add troubleshooting section for timeout errors
    - Add performance benchmarking results from T114
  - **Dependencies**: T114 (benchmarks complete)

- [ ] **T116 [P]** Update MCP memory with remediation results
  - **Command**:
    ```bash
    npx claude-flow@alpha memory store "features/tool-calling-refactor/remediation" \
      "Remediation complete: JSON parsing, adaptive iterations, timeouts, error recovery implemented. All tests passing. Production ready."
    ```
  - **Dependencies**: T113 (validation complete)

- [ ] **T117 [P]** Create production monitoring guide
  - **File**: `docs/tool-calling-monitoring.md` (NEW)
  - **Content**:
    - How to monitor tool call metrics in production
    - Alert thresholds (>15 calls, >3min per playlist, >90% iteration limit)
    - Common issues and resolutions
    - Performance optimization tips
  - **Dependencies**: T114 (benchmarks complete)

---

## Dependencies Graph

```
Setup:
T103 (baseline) → [blocks nothing, run first]

Tests (Parallel):
T104, T105, T106, T107 [P] → [all block corresponding implementations]

Implementation (Sequential - same file):
T104 → T108 (JSON parsing)
T105 → T109 (adaptive iterations)
T106 → T110 (timeouts)
T107 → T111 (error recovery)

Integration (Sequential):
T108, T109, T110, T111 → T112 (full test suite)
T112 → T113 (manual verification)
T113 → T114 (benchmarking)

Documentation (Parallel):
T114 → T115, T116, T117 [P]
```

---

## Parallel Execution Examples

**Tests Phase (T104-T107):**
```bash
# Launch all test creation tasks in parallel (different files)
Task("Create JSON parsing test", "...", "tester")
Task("Create iteration limit test", "...", "tester")
Task("Create timeout test", "...", "tester")
Task("Create error handling test", "...", "tester")
```

**Documentation Phase (T115-T117):**
```bash
# Launch all documentation tasks in parallel (different files)
Task("Update validation checklist", "...", "tester")
Task("Store MCP memory", "...", "memory-coordinator")
Task("Create monitoring guide", "...", "tester")
```

---

## Validation Checklist

- [x] All T094-T102 tasks complete (prerequisite)
- [ ] T104-T107 tests written and FAILING
- [ ] T108-T111 implementations fix failing tests
- [ ] T112 full test suite passes
- [ ] T113 manual verification with real data successful
- [ ] T114 performance benchmarks acceptable
- [ ] T115-T117 documentation updated

---

## Success Criteria

**Production Ready When:**
1. All tests pass (100% pass rate on T104-T107, T112)
2. Manual verification generates 6 dayparts without errors (T113)
3. Performance benchmarks meet targets (T114):
   - Time: <5 minutes per playlist
   - Cost: <$5.00 for 6 playlists
   - Success rate: >95%
4. Documentation complete (T115-T117)

**Known Acceptable Warnings:**
- Tool call count 10-15 (adaptive limit working)
- Individual tool timeouts <5% (transient network issues)
- Partial results on timeout (graceful degradation working)

---

## Notes

- **TDD Critical**: Tests T104-T107 MUST fail before implementing T108-T111
- **Parallel Safe**: T104-T107 are different files, can run in parallel
- **Sequential Required**: T108-T111 all modify `openai_client.py` and `subsonic_tools.py`, must run sequentially
- **Real APIs Required**: All tests use actual OpenAI + Subsonic endpoints (no mocking for tool calling validation)
- **MCP Memory**: Store progress after T108-T111, T113, final summary after T116

---

## Estimated Time

- T103 (baseline): 5 minutes
- T104-T107 (tests): 2-3 hours (parallel)
- T108-T111 (implementation): 4-5 hours (sequential)
- T112 (integration): 30 minutes
- T113 (manual verification): 20-30 minutes
- T114 (benchmarking): 1 hour
- T115-T117 (documentation): 1 hour (parallel)

**Total**: ~9-11 hours (with parallelization)
