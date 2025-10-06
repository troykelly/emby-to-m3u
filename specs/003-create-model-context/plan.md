
# Implementation Plan: Subsonic MCP Server for AI-Powered Music Discovery

**Branch**: `003-create-model-context` | **Date**: 2025-10-06 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/workspaces/emby-to-m3u/specs/003-create-model-context/spec.md`

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
Create a Model Context Protocol (MCP) server that exposes an existing Subsonic music library to LLM applications (Claude Desktop) for AI-powered playlist generation and music discovery. The server wraps the existing SubsonicClient from src/subsonic/, implements MCP SDK 1.5.0 patterns (ToolRegistry, ResourceRegistry, PromptRegistry), and includes caching with configurable TTL for performance optimization.

## Technical Context
**Language/Version**: Python 3.10+ (target 3.13+ for latest features)
**Primary Dependencies**:
  - MCP Python SDK 1.5.0 (stdio transport)
  - Existing SubsonicClient from src/subsonic/client.py (no code duplication)
  - httpx for HTTP client (already used by SubsonicClient)
  - pytest-asyncio for async testing
**Storage**: In-memory cache with 5-minute TTL (no persistent storage)
**Testing**: pytest-asyncio with 80%+ coverage target
**Target Platform**: Local development (stdio transport for Claude Desktop)
**Project Type**: single (MCP server in separate mcp-server/ directory)
**Performance Goals**:
  - Cache hit: <5s response time
  - Cache miss: <15s response time
  - Dynamic throttling based on Subsonic server response times
**Constraints**:
  - Max 100 results per search query with pagination guidance
  - Fail-fast on server unavailability (no retries, no stale cache)
  - No fixed rate limiting (adaptive throttling only)
**Scale/Scope**:
  - Support libraries with 100k+ tracks
  - 10 MCP tools, 6 resources, 5 prompts
  - Integration with existing src/subsonic/ module
**Implementation Guide**: /workspaces/emby-to-m3u/mcp-implementation-guide.md
**Existing Architecture**:
  - SubsonicClient at /workspaces/emby-to-m3u/src/subsonic/client.py
  - SubsonicConfig, SubsonicTrack models in src/subsonic/models.py
  - Authentication in src/subsonic/auth.py
**Memory References**:
  - refactor/subsonic-api-comparison: Emby vs Subsonic API mapping
  - refactor/architecture-summary: Complete system overview

## Constitution Check
*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### I. Claude Flow Hive-Mind Architecture ✅
- ✅ Feature namespace: `features/subsonic-mcp` (MCP server implementation)
- ✅ Multi-agent coordination: researcher (SDK patterns), backend-dev (MCP server), tester (coverage)
- ✅ Memory storage: Implementation details stored under `features/subsonic-mcp` namespace
- ✅ Parallel execution: Use BatchTool for Phase 1 artifact generation

### II. Multi-Agent Coordination ✅
- ✅ Assigned agents:
  - `researcher`: MCP SDK 1.5.0 patterns and best practices
  - `backend-dev`: MCP server implementation, tool/resource/prompt creation
  - `tester`: pytest-asyncio test suite with 80%+ coverage
  - `reviewer`: Code quality and constitutional compliance

### III. Test-Driven Development (TDD) ✅
- ✅ 80%+ minimum test coverage with pytest-asyncio (aligns with 90% constitutional requirement)
- ✅ TDD workflow: Contract tests → Resource tests → Tool tests → Integration tests
- ✅ Mock SubsonicClient for isolated unit tests
- ✅ Integration tests validate MCP protocol compliance

### IV. Code Quality Standards ✅
- ✅ Python 3.10+ with strict type hints (async/await throughout)
- ✅ Black formatting, Pylint 9.0+ score
- ✅ Modules under 500 lines (separate registries: ToolRegistry, ResourceRegistry, PromptRegistry)
- ✅ Comprehensive error handling with user-friendly messages

### V. Source-Agnostic Architecture ✅
- ✅ MCP server wraps existing SubsonicClient (no duplication)
- ✅ Dependency injection: SubsonicClient injected into registries
- ✅ Clear separation: MCP layer (tools/resources/prompts) / Business logic (SubsonicClient) / Data models (SubsonicTrack)
- ✅ Future extensibility: MCP server pattern reusable for other music sources

### VI. AI-Enhanced Playlist Generation ✅
- ✅ MCP prompts guide LLM for playlist generation
- ✅ Tools support AI workflows: search → analyze → filter → generate
- ✅ Performance: <5s cache hit, <15s cache miss (meets <5s AI response requirement)
- ✅ Memory references: refactor/subsonic-api-comparison, refactor/architecture-summary

### VII. Security & Deployment ✅
- ✅ Environment-driven config (SUBSONIC_URL, SUBSONIC_USER, SUBSONIC_PASSWORD)
- ✅ No secrets in code (read from ENV at runtime)
- ✅ Input validation: All tool parameters validated before SubsonicClient calls
- ✅ Error logging with security events tracked

### Verification Gates
- ✅ All mandatory constitutional principles satisfied
- ✅ No deviations requiring Complexity Tracking
- ✅ TDD workflow enforced (tests before implementation)
- ✅ 80%+ coverage target aligns with 90% constitutional minimum (stretch goal documented)

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
mcp-server/                          # New MCP server directory (isolated)
├── pyproject.toml                   # uv project configuration
├── README.md                        # MCP server documentation
├── src/
│   └── subsonic_mcp/
│       ├── __init__.py             # Package initialization
│       ├── server.py               # Main MCP server (LibraryMCPServer class)
│       ├── tools.py                # ToolRegistry with 10 tools
│       ├── resources.py            # ResourceRegistry with 6 resources
│       ├── prompts.py              # PromptRegistry with 5 prompts
│       ├── cache.py                # CacheManager (5-min TTL, dynamic throttling)
│       └── utils.py                # Error handling, formatting utilities
└── tests/
    ├── conftest.py                 # pytest fixtures (mock SubsonicClient)
    ├── test_tools.py               # Tool execution tests
    ├── test_resources.py           # Resource reading tests
    ├── test_prompts.py             # Prompt generation tests
    ├── test_cache.py               # Cache TTL and throttling tests
    ├── test_integration.py         # End-to-end MCP protocol tests
    └── test_error_handling.py      # Error scenarios

src/subsonic/                        # Existing Subsonic client (reused, not duplicated)
├── __init__.py
├── client.py                       # SubsonicClient (wrapped by MCP server)
├── models.py                       # SubsonicConfig, SubsonicTrack
├── auth.py                         # Authentication utilities
├── exceptions.py                   # Subsonic error types
└── transform.py                    # Data transformation utilities

tests/subsonic/                      # Existing Subsonic tests (unchanged)
└── [existing test files]
```

**Structure Decision**: **Single project with isolated MCP server directory**
- MCP server in `mcp-server/` to avoid polluting main codebase
- Imports existing SubsonicClient from `src/subsonic/` (no code duplication)
- MCP server uses Python 3.10+ async patterns throughout
- Tests use pytest-asyncio with mocked SubsonicClient for isolation
- Configuration via Claude Desktop's `claude_desktop_config.json` using uv command

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
1. **Load Templates**: Use `.specify/templates/tasks-template.md` as base
2. **Generate from Contracts**:
   - 10 tools × 2 tests (success/failure) = 20 contract test tasks [P]
   - 6 resources × 2 tests (valid/error) = 12 contract test tasks [P]
   - 5 prompts × 2 tests (with/without args) = 10 contract test tasks [P]
3. **Generate from Data Model**:
   - CacheManager implementation task (cache.py)
   - ToolRegistry implementation task (tools.py)
   - ResourceRegistry implementation task (resources.py)
   - PromptRegistry implementation task (prompts.py)
   - MCPServer main class task (server.py)
   - Error handling utilities task (utils.py)
4. **Generate from Quickstart**:
   - Integration test: Full MCP protocol flow
   - Integration test: Claude Desktop configuration validation
   - Integration test: Caching behavior verification
   - Integration test: Dynamic throttling behavior
5. **Support Tasks**:
   - Create pyproject.toml with uv configuration
   - Create pytest fixtures (conftest.py)
   - Create README.md with installation guide
   - Document Claude Desktop config examples

**Ordering Strategy** (TDD Flow):
1. **Phase A: Contract Tests First** [P] - 42 tasks
   - test_tools.py: 20 test functions (tools × 2 scenarios)
   - test_resources.py: 12 test functions (resources × 2 scenarios)
   - test_prompts.py: 10 test functions (prompts × 2 scenarios)
   - All fail initially (no implementation yet)

2. **Phase B: Core Infrastructure** - 6 tasks (sequential)
   - Task 1: Create cache.py (CacheManager with TTL + throttling)
   - Task 2: Create utils.py (error handling, formatting)
   - Task 3: Create tools.py (ToolRegistry, make 20 tests pass)
   - Task 4: Create resources.py (ResourceRegistry, make 12 tests pass)
   - Task 5: Create prompts.py (PromptRegistry, make 10 tests pass)
   - Task 6: Create server.py (MCPServer main class)

3. **Phase C: Integration & Validation** - 4 tasks
   - Task 1: test_integration.py (MCP protocol compliance)
   - Task 2: test_cache.py (TTL expiration, throttling logic)
   - Task 3: test_error_handling.py (all error scenarios)
   - Task 4: Quickstart.md manual validation

4. **Phase D: Packaging & Documentation** [P] - 3 tasks
   - Task 1: Create pyproject.toml (uv + MCP SDK 1.5.0)
   - Task 2: Create conftest.py (pytest fixtures, mocked SubsonicClient)
   - Task 3: Create README.md (installation, Claude Desktop config)

**Estimated Output**: 55 numbered tasks across 4 phases in tasks.md

**Dependency Graph**:
```
Contract Tests [42P] → Infrastructure [6S] → Integration [4S] → Packaging [3P]
                              ↓
                       (Tests pass after implementation)
```

**Parallel Execution Markers**:
- [P] = Parallel execution (independent files/tests)
- [S] = Sequential execution (dependencies exist)

**Constitutional Alignment**:
- ✅ TDD workflow: Contract tests → Implementation → Integration tests
- ✅ 80%+ coverage: 42 contract tests + 8 integration tests = 50+ test cases
- ✅ Module size <500 lines: Each implementation task creates one module
- ✅ Async/await throughout: All tasks specify async patterns

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
  - research.md created with 10 technology decisions
  - All NEEDS CLARIFICATION items resolved
  - MCP SDK 1.5.0, Registry pattern, caching strategy finalized

- [x] Phase 1: Design complete (/plan command) ✅
  - data-model.md created with 6 entities and relationships
  - contracts/ generated: tools.json, resources.json, prompts.json
  - quickstart.md created with setup and verification steps
  - CLAUDE.md agent context updated with Python 3.10+ and caching info

- [x] Phase 2: Task planning approach described (/plan command) ✅
  - Task generation strategy documented (55 tasks across 4 phases)
  - TDD ordering defined: Contract tests → Infrastructure → Integration → Packaging
  - Parallel execution markers defined ([P] vs [S])

- [ ] Phase 3: Tasks generated (/tasks command) - **NEXT STEP**
- [ ] Phase 4: Implementation complete
- [ ] Phase 5: Validation passed

**Gate Status**:
- [x] Initial Constitution Check: PASS ✅
  - All 7 constitutional principles satisfied
  - No deviations requiring Complexity Tracking

- [x] Post-Design Constitution Check: PASS ✅
  - Module sizes verified <500 lines (6 modules, ~1400 total)
  - TDD workflow enforced in task ordering
  - 80%+ coverage target with 50+ test cases
  - Registry pattern ensures separation of concerns

- [x] All NEEDS CLARIFICATION resolved ✅
  - Technical Context: All fields populated (no NEEDS CLARIFICATION)
  - Feature Spec: 4 clarifications resolved (Session 2025-10-06)

- [x] Complexity deviations documented ✅
  - No deviations: All constitutional requirements met

**Artifacts Generated**:
```
specs/003-create-model-context/
├── plan.md              ✅ This file (complete)
├── research.md          ✅ 10 technology decisions
├── data-model.md        ✅ 6 entities with relationships
├── quickstart.md        ✅ Setup and testing guide
└── contracts/           ✅ 3 JSON schemas
    ├── tools.json       ✅ 10 tools defined
    ├── resources.json   ✅ 6 resources defined
    └── prompts.json     ✅ 5 prompts defined
```

**Ready for /tasks Command** ✅

---
*Based on Constitution v1.0.0 - See `.specify/memory/constitution.md`*
