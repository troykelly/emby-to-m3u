# Tasks Updated - Phase 4 Remediation Plan

**Date**: 2025-10-07
**Action**: Added 25 new remediation tasks (T044-T068)
**Total Tasks**: Now 68 tasks (up from 43)

---

## What Was Added

### Phase 4: Remediation & Production Readiness (25 new tasks)

All remediation tasks based on the deployment readiness assessment findings:

#### Phase 4.1: Critical Import Fixes (6 tasks - T044 to T049)
**Blocker #1: Import Architecture** - 2 hours estimated

- T044: Fix missing backward compatibility exports in models package
- T045: Fix import paths in test files using legacy class names
- T046: Create backward compatibility wrapper for BatchPlaylistGenerator
- T047: Fix subsonic.models Track vs SubsonicTrack naming
- T048: Verify all integration tests can collect without errors
- T049: Run quick smoke test on corrected imports

**Impact**: Unblocks 172 integration tests, fixes 15 E0603 Pylint errors

---

#### Phase 4.2: Constructor Signature Fixes (8 tasks - T050 to T057)
**Blocker #2: Constructor Signatures** - 6 hours estimated

- T050: Fix ValidationResult constructor calls in validator.py (7 errors)
- T051: Fix ValidationResult constructor calls in batch_executor.py (26 errors)
- T052: Fix ConstraintScore constructor calls in validator_new.py (20 errors)
- T053: Fix SelectedTrack constructor calls in batch_executor.py (5 errors)
- T054: Fix Playlist constructor calls in batch_executor.py (3 errors)
- T055: Fix remaining constructor errors in workflow.py (15 errors)
- T056: Fix remaining constructor errors in decision_logger.py (10 errors)
- T057: Verify all E-errors resolved and Pylint score ≥9.0

**Impact**: Resolves 148 critical E-errors, achieves Pylint 9.0/10

---

#### Phase 4.3: Unit Test Coverage (7 tasks - T058 to T064)
**Blocker #3: Coverage Gap** - 16 hours estimated

- T058: Create comprehensive validator.py unit tests (14 tests)
- T059: Create comprehensive workflow.py unit tests (20 tests)
- T060: Create comprehensive decision_logger.py unit tests (10 tests)
- T061: Create comprehensive exporters.py unit tests (12 tests)
- T062: Create comprehensive azuracast/playlist_sync.py unit tests (15 tests)
- T063: Expand openai_client.py unit tests to achieve 90% coverage (30 tests)
- T064: Verify overall test coverage ≥90%

**Impact**: Adds 101 new unit tests, achieves 90% coverage target

---

#### Phase 4.4: Integration Test Execution (3 tasks - T065 to T067)
**Blocker #4: Integration Tests** - 4 hours estimated

- T065: Execute integration tests against live endpoints (172 tests)
- T066: Implement remaining contract tests (GREEN phase) (66 tests)
- T067: Run full end-to-end workflow test

**Impact**: Validates all workflows against live endpoints, completes TDD cycle

---

#### Phase 4.5: Deployment Preparation (1 task - T068)

- T068: Create deployment runbook and production checklist

**Impact**: Production-ready deployment documentation

---

## Task Dependencies & Critical Path

### Sequential Flow:
1. **Phase 4.1** (Import Fixes) → Must complete first to unblock tests
2. **Phase 4.2** (Constructor Fixes) → Must complete to achieve Pylint 9.0+
3. **Phase 4.3** (Unit Tests) → Can run in parallel after Phase 4.2
4. **Phase 4.4** (Integration Tests) → Depends on Phases 4.1 and 4.2
5. **Phase 4.5** (Deployment) → Depends on all previous phases

### Parallel Opportunities:

**Within Phase 4.1** (after T044 completes):
```bash
# Run T045, T046, T047 in parallel
Task("coder", "Fix T045: Update 7 test files", "coder")
Task("coder", "Fix T046: Verify wrapper", "coder")
Task("coder", "Fix T047: Fix Track import", "coder")
```

**Within Phase 4.2**:
```bash
# Run T055, T056 in parallel
Task("coder", "Fix T055: workflow.py", "coder")
Task("coder", "Fix T056: decision_logger.py", "coder")
```

**Within Phase 4.3** (all can run in parallel):
```bash
# Run all 5 test creation tasks in parallel
Task("tester", "Create T058: validator tests", "tester")
Task("tester", "Create T059: workflow tests", "tester")
Task("tester", "Create T060: decision_logger tests", "tester")
Task("tester", "Create T061: exporters tests", "tester")
Task("tester", "Create T062: playlist_sync tests", "tester")
```

---

## Estimated Timeline

**Total Estimated Time**: 38 working hours (5 business days)

### Day 1 (8 hours): Phase 4.1 + Phase 4.2
- Fix all import architecture issues (2 hours)
- Resolve all 148 constructor signature E-errors (6 hours)
- **Deliverable**: Pylint score ≥9.0/10, all tests collectable

### Day 2 (8 hours): Phase 4.3 Part 1
- Create validator.py unit tests (2 hours)
- Create workflow.py unit tests (3 hours)
- Create openai_client.py additional tests (3 hours)
- **Deliverable**: ~70% coverage

### Day 3 (8 hours): Phase 4.3 Part 2
- Create decision_logger.py unit tests (2 hours)
- Create exporters.py unit tests (2 hours)
- Create playlist_sync.py unit tests (3 hours)
- Run coverage validation (1 hour)
- **Deliverable**: ≥90% coverage

### Day 4 (12 hours): Phase 4.4
- Execute all 172 integration tests (4 hours)
- Fix runtime failures (4 hours)
- Implement 66 contract tests (3 hours)
- Run E2E workflow test (1 hour)
- **Deliverable**: All tests passing

### Day 5 (2 hours): Phase 4.5
- Create deployment runbook (1 hour)
- Final production checklist (1 hour)
- **Deliverable**: Production ready ✅

---

## Success Criteria

### Phase 4 Completion Checklist:
- [ ] Pylint score ≥9.0/10
- [ ] Zero E-errors
- [ ] Test coverage ≥90%
- [ ] All 490 unit tests passing
- [ ] All 172 integration tests passing
- [ ] All 136 contract tests passing
- [ ] Deployment runbook complete
- [ ] Smoke tests passing

---

## What Hasn't Changed

**Phase 3 tasks (T001-T043)**: All remain complete and marked with [x]

The original implementation is functionally complete. Phase 4 focuses solely on quality assurance, validation, and production readiness.

---

## Files Modified

1. **`/workspaces/emby-to-m3u/specs/005-refactor-core-playlist/tasks.md`**
   - Added Phase 4 with 25 new tasks
   - Updated summary to show 68 total tasks
   - Added parallel execution examples
   - Updated critical path documentation

---

## Next Steps

To begin Phase 4 remediation:

```bash
# Start with Phase 4.1 critical import fixes
/implement

# Or target specific phase
/implement phase 4.1

# Or run specific tasks
/implement T044 T045 T046
```

---

**Report Generated**: 2025-10-07
**Tasks File**: `/workspaces/emby-to-m3u/specs/005-refactor-core-playlist/tasks.md`
**Status**: Ready for Phase 4 execution
