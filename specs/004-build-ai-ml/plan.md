
# Implementation Plan: AI-Powered Radio Playlist Automation

**Branch**: `004-build-ai-ml` | **Date**: 2025-10-06 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/workspaces/emby-to-m3u/specs/004-build-ai-ml/spec.md`

## Execution Flow (/plan command scope)
```
1. Load feature spec from Input path
   → If not found: ERROR "No feature spec at {path}"
2. Fill Technical Context (scan for NEEDS CLARIFICATION)
   → Detect Project Type from file system structure or context (web=frontend+backend, mobile=app+api)
   → Set Structure Decision based on project type
3. Fill the Constitution Check section based on the content of the constitution document.
4. Evaluate Constitution Check section below
   → If violations exist: Document in Complexity Tracking
   → If no justification possible: ERROR "Simplify approach first"
   → Update Progress Tracking: Initial Constitution Check
5. Execute Phase 0 → research.md
   → If NEEDS CLARIFICATION remain: ERROR "Resolve unknowns"
6. Execute Phase 1 → contracts, data-model.md, quickstart.md, agent-specific template file (e.g., `CLAUDE.md` for Claude Code, `.github/copilot-instructions.md` for GitHub Copilot, `GEMINI.md` for Gemini CLI, `QWEN.md` for Qwen Code, or `AGENTS.md` for all other agents).
7. Re-evaluate Constitution Check section
   → If new violations: Refactor design, return to Phase 1
   → Update Progress Tracking: Post-Design Constitution Check
8. Plan Phase 2 → Describe task generation approach (DO NOT create tasks.md)
9. STOP - Ready for /tasks command
```

**IMPORTANT**: The /plan command STOPS at step 7. Phases 2-4 are executed by other commands:
- Phase 2: /tasks command creates tasks.md
- Phase 3-4: Implementation execution (manual or via tools)

## Summary
Build an AI/ML agent system that parses plain-language radio programming documents (station-identity.md), generates playlist specifications, uses LLM with MCP tools (Subsonic) to select tracks meeting complex criteria (BPM, genre mix, era distribution, Australian content 30%+), and syncs to AzuraCast. System must complete fully automated in <10 minutes at <$0.50 cost with 80%+ constraint satisfaction and verified flow quality.

## Technical Context
**Language/Version**: Python 3.13+ (existing codebase standard)
**Primary Dependencies**:
- OpenAI GPT-4o-mini (Responses API with HostedMCPTool)
- Subsonic MCP server (track search/metadata)
- Existing: AzuraCast client, Subsonic client, Track model
- Claude Flow hive-mind coordination (MANDATORY per constitution)
**Storage**:
- JSON/structured logs for decisions (indefinite retention per FR-014)
- Existing AzuraCast PostgreSQL for playlists
- File-based: station-identity.md input
**Testing**: pytest with 90% coverage minimum (per constitution)
**Target Platform**: Linux server (Docker containerized per constitution)
**Project Type**: single (extends existing monolith at src/)
**Performance Goals**:
- Parse + generate + select + sync: <10 minutes total
- LLM API cost: <$0.50 per execution
- Track selection quality: ≥80% constraint satisfaction
**Constraints**:
- Fully automated (no user approval per FR-011)
- Retry with exponential backoff (3 attempts per FR-013)
- Australian content 30% minimum (non-negotiable per FR-009)
- Constraint relaxation priority: BPM→Genre→Era (per clarifications)
**Scale/Scope**:
- Dynamic playlist count based on programming document
- Example: 47 playlists for Production City Radio
- Multi-agent coordination via Claude Flow hive-mind
- Integration: Use hive memory (MCP) for reference data storage

## Constitution Check
*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### I. Claude Flow Hive-Mind Architecture
- [x] Multi-agent coordination planned (document parser, playlist planner, track selector agents)
- [x] Feature namespace: `ai-playlist/` for memory storage
- [x] Minimum 3 specialized agents: parser, planner, selector
- [x] Specifications stored in Claude Flow memory under `ai-playlist/` namespace
- [x] BatchTool usage planned for parallel track selection
- [x] 95% truth verification threshold maintained
- [x] Task implementation: `npx claude-flow@alpha swarm "Execute tasks in parallel" --claude`

### II. Multi-Agent Coordination
- [x] Agent assignments defined:
  - `ml-developer` + `backend-dev`: AI playlist generation
  - `backend-dev` + `code-analyzer`: Document parser, playlist planner
  - `tester` + `reviewer`: Testing & QA
  - `researcher`: LLM integration patterns
- [x] Namespace structure:
  - `ai-playlist/document-parser`: Programming doc parsing logic
  - `ai-playlist/playlist-spec`: Playlist specification generation
  - `ai-playlist/track-selector`: LLM-based track selection
  - `ai-playlist/azuracast-sync`: AzuraCast synchronization
  - `ai-playlist/validation`: Quality validation logic

### III. Test-Driven Development (TDD)
- [x] 90% minimum coverage requirement acknowledged
- [x] Unit tests planned for all business logic (parser, planner, validator)
- [x] Integration tests planned for OpenAI API + Subsonic MCP
- [x] E2E test planned for complete workflow (parse→generate→select→sync)
- [x] External services mocked (OpenAI, Subsonic MCP, AzuraCast)
- [x] Test fixtures: sample station-identity.md, mock track metadata
- [x] TDD workflow: Write tests first, implement to pass

### IV. Code Quality Standards
- [x] Python 3.13+ with strict type hints
- [x] Black formatting (line length 100)
- [x] Pylint score 9.0+ target
- [x] Modules under 500 lines
- [x] Dataclasses for data models (PlaylistSpec, TrackCriteria, ValidationResult)
- [x] Async/await for OpenAI API, Subsonic MCP, AzuraCast API calls
- [x] Retry logic with exponential backoff (3 attempts per FR-013)
- [x] Timeout limits for all external APIs
- [x] Comprehensive error handling and logging

### V. Source-Agnostic Architecture
- [x] Extends existing source-agnostic design (Emby/Subsonic already supported)
- [x] Uses existing Track model and Subsonic client
- [x] Factory pattern already in place for API client selection
- [x] Dependency injection for testability
- [x] Separation: Document parser / Playlist logic / Track selection / Sync

### VI. AI-Enhanced Playlist Generation
- [x] Integrates with existing playlist management (AzuraCast sync)
- [x] LLM integration via OpenAI Responses API + HostedMCPTool (secure)
- [x] AI recommendations explainable via decision logs (FR-014)
- [x] Performance: <10 minutes total (FR-007), <$0.50 cost (FR-008)
- [x] Training data documented in Claude Flow memory
- [x] Model decisions logged indefinitely (FR-014)

### VII. Security & Deployment
- [x] Environment-driven config (OpenAI API key, Subsonic MCP endpoint)
- [x] No secrets in code (12-factor methodology)
- [x] All security events logged (API failures, validation errors)
- [x] Input validation for programming document parsing
- [x] Docker containerization (extends existing setup)
- [x] Health check endpoints (existing /health)
- [x] Graceful shutdown handling (SIGTERM)

### Constitutional Compliance Status
✅ **PASS** - All constitutional requirements satisfied. No deviations required.

## Project Structure

### Documentation (this feature)
```
specs/[###-feature]/
├── plan.md              # This file (/plan command output)
├── research.md          # Phase 0 output (/plan command)
├── data-model.md        # Phase 1 output (/plan command)
├── quickstart.md        # Phase 1 output (/plan command)
├── contracts/           # Phase 1 output (/plan command)
└── tasks.md             # Phase 2 output (/tasks command - NOT created by /plan)
```

### Source Code (repository root)
```
src/
├── ai_playlist/              # NEW: AI playlist automation
│   ├── __init__.py
│   ├── document_parser.py    # Parse station-identity.md
│   ├── playlist_planner.py   # Generate playlist specifications
│   ├── openai_client.py      # OpenAI Responses API integration
│   ├── mcp_connector.py      # Subsonic MCP tool integration
│   ├── track_selector.py     # LLM-based track selection
│   ├── azuracast_sync.py     # AzuraCast playlist synchronization
│   └── validator.py          # Quality validation (80%+ constraint satisfaction)
├── azuracast/                # EXISTING: AzuraCast client
│   └── main.py              # Reuse for playlist sync
├── subsonic/                 # EXISTING: Subsonic client
│   └── client.py            # Reuse for MCP tool integration
├── track/                    # EXISTING: Track model
│   └── main.py              # Reuse for track metadata
└── models/                   # EXISTING: Data models
    └── (extend with playlist specs)

tests/
├── ai_playlist/              # NEW: AI playlist tests
│   ├── test_document_parser.py
│   ├── test_playlist_planner.py
│   ├── test_openai_client.py
│   ├── test_track_selector.py
│   ├── test_validator.py
│   └── test_e2e_workflow.py  # E2E: parse→generate→select→sync
├── fixtures/                 # Test data
│   ├── sample_station_identity.md
│   └── mock_track_metadata.json
├── contract/                 # Contract tests
│   ├── test_openai_api.py   # OpenAI Responses API contracts
│   └── test_subsonic_mcp.py # Subsonic MCP tool contracts
├── integration/              # Integration tests
│   ├── test_openai_integration.py
│   ├── test_subsonic_mcp_integration.py
│   └── test_azuracast_sync.py
└── unit/                     # Unit tests (90%+ coverage)
    └── ai_playlist/
```

**Structure Decision**: Single project structure (Option 1). Extends existing monolith at `src/` with new `ai_playlist/` module. Reuses existing clients (AzuraCast, Subsonic, Track model) to maintain source-agnostic architecture. Test structure mirrors source with comprehensive coverage (unit, integration, contract, E2E).

## Phase 0: Outline & Research
1. **Extract unknowns from Technical Context** above:
   - For each NEEDS CLARIFICATION → research task
   - For each dependency → best practices task
   - For each integration → patterns task

2. **Generate and dispatch research agents**:
   ```
   For each unknown in Technical Context:
     Task: "Research {unknown} for {feature context}"
   For each technology choice:
     Task: "Find best practices for {tech} in {domain}"
   ```

3. **Consolidate findings** in `research.md` using format:
   - Decision: [what was chosen]
   - Rationale: [why chosen]
   - Alternatives considered: [what else evaluated]

**Output**: research.md with all NEEDS CLARIFICATION resolved

## Phase 1: Design & Contracts
*Prerequisites: research.md complete*

1. **Extract entities from feature spec** → `data-model.md`:
   - Entity name, fields, relationships
   - Validation rules from requirements
   - State transitions if applicable

2. **Generate API contracts** from functional requirements:
   - For each user action → endpoint
   - Use standard REST/GraphQL patterns
   - Output OpenAPI/GraphQL schema to `/contracts/`

3. **Generate contract tests** from contracts:
   - One test file per endpoint
   - Assert request/response schemas
   - Tests must fail (no implementation yet)

4. **Extract test scenarios** from user stories:
   - Each story → integration test scenario
   - Quickstart test = story validation steps

5. **Update agent file incrementally** (O(1) operation):
   - Run `.specify/scripts/bash/update-agent-context.sh claude`
     **IMPORTANT**: Execute it exactly as specified above. Do not add or remove any arguments.
   - If exists: Add only NEW tech from current plan
   - Preserve manual additions between markers
   - Update recent changes (keep last 3)
   - Keep under 150 lines for token efficiency
   - Output to repository root

**Output**: data-model.md, /contracts/*, failing tests, quickstart.md, agent-specific file

## Phase 2: Task Planning Approach
*This section describes what the /tasks command will do - DO NOT execute during /plan*

**Task Generation Strategy**:
1. **From data-model.md**: Generate model creation tasks for each entity
   - ProgrammingDocument, DaypartSpec, PlaylistSpec, TrackSelectionCriteria
   - LLMTrackSelectionRequest/Response, SelectedTrack, Playlist
   - ValidationResult, DecisionLog
   - All with Python dataclasses + type hints + validation

2. **From contracts/**: Generate contract test tasks (TDD - tests first)
   - `test_document_parser_contract.py` → document_parser.py
   - `test_llm_track_selector_contract.py` → track_selector.py
   - `test_validator_contract.py` → validator.py

3. **From quickstart.md**: Generate integration test tasks
   - `test_e2e_workflow.py` → complete parse→generate→select→sync flow
   - `test_openai_integration.py` → OpenAI API + MCP tools
   - `test_azuracast_sync.py` → AzuraCast playlist creation/update

4. **Implementation tasks** (to make tests pass):
   - Document parser (regex + LLM hybrid)
   - Playlist planner (daypart → spec conversion)
   - OpenAI client (Responses API + HostedMCPTool)
   - MCP connector (Subsonic tool integration)
   - Track selector (LLM-based selection with constraint relaxation)
   - Validator (80% constraint + 70% flow quality)
   - AzuraCast sync (reuse existing client)
   - Decision logger (JSONL append-only)

5. **Claude Flow Hive Integration** (per constitution + user requirement):
   - Store reference data in hive memory under `ai-playlist/` namespace
   - Multi-agent task orchestration (parser, planner, selector agents)
   - BatchTool for parallel track selection across playlists
   - Memory coordination for shared context

**Ordering Strategy**:
- **Phase 1: Models** [P] - All dataclasses can be created in parallel
- **Phase 2: Contract Tests** [P] - Tests before implementation (TDD)
- **Phase 3: Core Implementation** - Sequential dependencies:
  1. Document parser (no dependencies)
  2. Playlist planner (depends on parser)
  3. OpenAI client + MCP connector (independent)
  4. Track selector (depends on OpenAI + MCP)
  5. Validator (depends on track selector)
  6. AzuraCast sync (depends on validator)
  7. Decision logger (used by all)
- **Phase 4: Integration Tests** - After implementation complete
- **Phase 5: E2E + Hive Setup** - Final validation + hive memory setup

**Hive-Specific Tasks**:
1. Store programming analysis in memory: `ai-playlist/station-identity-analysis`
2. Store playlist naming schema: `ai-playlist/playlist-naming-schema`
3. Store LLM workflow patterns: `ai-playlist/llm-workflow-requirements`
4. Store constraint relaxation rules: `ai-playlist/constraint-relaxation-rules`
5. Store validation thresholds: `ai-playlist/validation-thresholds`
6. Configure agent coordination topology (mesh for parallel track selection)
7. Implement BatchTool parallelization for 47 playlists

**Estimated Output**: 35-40 numbered, ordered tasks in tasks.md

**IMPORTANT**: This phase is executed by the /tasks command, NOT by /plan

## Phase 3+: Future Implementation
*These phases are beyond the scope of the /plan command*

**Phase 3**: Task execution (/tasks command creates tasks.md)  
**Phase 4**: Implementation (execute tasks.md following constitutional principles)  
**Phase 5**: Validation (run tests, execute quickstart.md, performance validation)

## Complexity Tracking
*Fill ONLY if Constitution Check has violations that must be justified*

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |


## Progress Tracking
*This checklist is updated during execution flow*

**Phase Status**:
- [x] Phase 0: Research complete (/plan command) ✅
- [x] Phase 1: Design complete (/plan command) ✅
- [x] Phase 2: Task planning complete (/plan command - approach described) ✅
- [x] Phase 3: Tasks generated (/tasks command) ✅ - **40 tasks ready**
- [ ] Phase 4: Implementation complete - **NEXT STEP**
- [ ] Phase 5: Validation passed

**Gate Status**:
- [x] Initial Constitution Check: PASS ✅
- [x] Post-Design Constitution Check: PASS ✅
- [x] All NEEDS CLARIFICATION resolved ✅
- [x] Complexity deviations documented: NONE (no deviations) ✅

**Artifacts Generated**:
- [x] `/specs/004-build-ai-ml/plan.md` (this file)
- [x] `/specs/004-build-ai-ml/research.md` (Phase 0)
- [x] `/specs/004-build-ai-ml/data-model.md` (Phase 1)
- [x] `/specs/004-build-ai-ml/quickstart.md` (Phase 1)
- [x] `/specs/004-build-ai-ml/contracts/document_parser_contract.md` (Phase 1)
- [x] `/specs/004-build-ai-ml/contracts/llm_track_selector_contract.md` (Phase 1)
- [x] `/specs/004-build-ai-ml/contracts/validator_contract.md` (Phase 1)
- [x] `/specs/004-build-ai-ml/tasks.md` (Phase 3 - 40 implementation tasks)
- [x] `/workspaces/emby-to-m3u/CLAUDE.md` (agent context updated)

**Ready for implementation** 🚀

---
*Based on Constitution v1.0.0 - See `.specify/memory/constitution.md`*
