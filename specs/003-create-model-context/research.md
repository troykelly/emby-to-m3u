# Research & Technology Decisions
## Subsonic MCP Server Implementation

**Feature**: 003-create-model-context
**Date**: 2025-10-06
**Research Phase**: Phase 0

---

## 1. MCP Python SDK 1.5.0 Integration

### Decision: Use Official MCP Python SDK 1.5.0 with stdio Transport

**Rationale**:
- **Official SDK**: MCP Python SDK 1.5.0 is the official Anthropic-maintained implementation
- **Stdio Transport**: Best suited for local Claude Desktop integration (no network overhead)
- **Type Safety**: SDK provides fully typed interfaces for tools, resources, and prompts
- **Protocol Compliance**: Ensures compatibility with MCP specification 2025-06-18

**Implementation Pattern**:
```python
from mcp.server import Server
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types

# Server initialization with stdio transport
async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
    await server.run(read_stream, write_stream, init_options)
```

**Alternatives Considered**:
- **SSE Transport**: Requires HTTP server setup, unnecessary for local-only Claude Desktop
- **Custom Protocol**: High maintenance burden, poor ecosystem compatibility
- **MCP SDK 1.4.x**: Missing latest features (enhanced error handling, improved notifications)

**Key Resources**:
- MCP Implementation Guide: `/workspaces/emby-to-m3u/mcp-implementation-guide.md`
- SDK Documentation: https://github.com/modelcontextprotocol/python-sdk
- Specification: https://spec.modelcontextprotocol.io/specification/2025-06-18

---

## 2. Registry Pattern Architecture

### Decision: Implement ToolRegistry, ResourceRegistry, PromptRegistry Pattern

**Rationale**:
- **Separation of Concerns**: Each registry manages its domain (tools, resources, prompts)
- **Testability**: Registries can be tested in isolation with mocked SubsonicClient
- **Maintainability**: Adding new tools/resources/prompts is straightforward
- **MCP Best Practice**: Aligns with SDK examples and community patterns

**Structure**:
```python
# tools.py
class ToolRegistry:
    def __init__(self, subsonic_client: SubsonicClient):
        self.client = subsonic_client
        self.tools = self._define_tools()

    def get_all(self) -> list[types.Tool]:
        return list(self.tools.values())

    async def execute(self, name: str, args: dict) -> list[types.TextContent]:
        handler = getattr(self, f"_handle_{name}")
        return await handler(args)

# Similar pattern for resources.py and prompts.py
```

**Alternatives Considered**:
- **Monolithic Server Class**: Would violate 500-line module limit, hard to test
- **Functional Approach**: Less organized, harder to manage state and dependencies
- **Plugin Architecture**: Overengineered for 10 tools, adds unnecessary complexity

**Benefits**:
- Clear file organization (<500 lines per module)
- Easy to mock for unit tests
- Simple to extend with new functionality
- Follows mcp-implementation-guide.md patterns

---

## 3. Wrapping Existing SubsonicClient

### Decision: Import and Inject SubsonicClient (No Code Duplication)

**Rationale**:
- **DRY Principle**: Reuse existing, tested SubsonicClient implementation
- **Consistency**: Same authentication, error handling, and API interaction logic
- **Maintainability**: Single source of truth for Subsonic API integration
- **Dependency Injection**: SubsonicClient injected into registries for testability

**Integration Pattern**:
```python
# mcp-server/src/subsonic_mcp/server.py
from src.subsonic.client import SubsonicClient
from src.subsonic.models import SubsonicConfig

class LibraryMCPServer:
    def __init__(self, config: SubsonicConfig):
        self.subsonic_client = SubsonicClient(config)
        self.tool_registry = ToolRegistry(self.subsonic_client)
        self.resource_registry = ResourceRegistry(self.subsonic_client)
        self.prompt_registry = PromptRegistry(self.subsonic_client)
```

**Existing Architecture Leveraged**:
- `SubsonicClient` from `/workspaces/emby-to-m3u/src/subsonic/client.py`
  - HTTP client with connection pooling (httpx)
  - Token-based authentication (MD5 salt+hash)
  - Comprehensive error handling (typed exceptions)
  - Rate limiting support (optional)
  - OpenSubsonic detection

- `SubsonicConfig` from `/workspaces/emby-to-m3u/src/subsonic/models.py`
  - URL, username, password configuration
  - Environment variable support

- `SubsonicTrack` model with full metadata
  - Title, artist, album, genre, year, duration, bitrate
  - Streaming URL generation

**Alternatives Considered**:
- **Direct HTTP Calls**: Duplicate logic, lose error handling, authentication complexity
- **Async Wrapper**: Unnecessary - can use asyncio.to_thread() for sync client calls
- **Fork SubsonicClient**: Maintenance nightmare, diverging implementations

---

## 4. Caching Strategy with Configurable TTL

### Decision: In-Memory Cache with 5-Minute TTL + Dynamic Throttling

**Rationale**:
- **Performance**: <5s response time for cache hits (requirement met)
- **Server Protection**: Reduces load on Subsonic server
- **Simplicity**: No persistent storage needed (MCP server is stateless process)
- **Constitutional Alignment**: No database complexity, meets performance goals

**Implementation**:
```python
# cache.py
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
import asyncio

@dataclass
class CacheEntry:
    data: Any
    timestamp: datetime
    ttl_seconds: int = 300  # 5 minutes

class CacheManager:
    def __init__(self, default_ttl: int = 300):
        self.cache: Dict[str, CacheEntry] = {}
        self.default_ttl = default_ttl
        self.response_times = deque(maxlen=100)  # Sliding window for throttling

    async def get(self, key: str) -> Optional[Any]:
        entry = self.cache.get(key)
        if entry and (datetime.now() - entry.timestamp) < timedelta(seconds=entry.ttl_seconds):
            return entry.data
        return None

    async def set(self, key: str, data: Any, ttl: Optional[int] = None):
        self.cache[key] = CacheEntry(
            data=data,
            timestamp=datetime.now(),
            ttl_seconds=ttl or self.default_ttl
        )

    def update_response_time(self, duration: float):
        self.response_times.append(duration)

    def should_throttle(self) -> bool:
        if len(self.response_times) < 10:
            return False
        avg_time = sum(self.response_times) / len(self.response_times)
        return avg_time > 2.0  # Throttle if avg response time > 2s
```

**Cached Data Types** (5-min TTL):
- Library statistics (total tracks, artists, albums, genres)
- Artist list (changes infrequently)
- Genre list (static metadata)
- Search results (by query hash)

**Dynamic Throttling** (FR-041, FR-042, FR-043):
- Track Subsonic server response times in sliding window (last 100 requests)
- Calculate average response time
- When avg > 2s: Slow down request rate (sleep between requests)
- When avg < 1s: Allow faster concurrent requests
- No fixed rate limit (FR-047) - adaptive only

**Alternatives Considered**:
- **Redis Cache**: Overengineered for single-process MCP server, adds deployment complexity
- **No Caching**: Violates performance requirements, overloads Subsonic server
- **Longer TTL (30+ min)**: Stale data risk, conflicts with fail-fast requirement (FR-044)
- **Fixed Rate Limiting**: Rejected per FR-047, use dynamic throttling instead

---

## 5. Error Handling with User-Friendly Messages

### Decision: Multi-Layer Error Handling with Custom Exception Mapping

**Rationale**:
- **User Experience**: LLMs receive clear, actionable error messages
- **Debugging**: Detailed logs for troubleshooting (separate from user messages)
- **Robustness**: Graceful degradation, no MCP server crashes
- **Constitutional Requirement**: Comprehensive error handling (Section IV)

**Error Handling Layers**:

1. **SubsonicClient Exceptions** (already implemented):
   - `SubsonicAuthenticationError`: Invalid credentials
   - `SubsonicNotFoundError`: Track/artist/album not found
   - `SubsonicParameterError`: Invalid API parameters
   - `SubsonicError`: Generic Subsonic API error

2. **MCP Server Exception Mapping**:
```python
# utils.py
class MCPError(Exception):
    """Base exception for MCP server errors"""
    pass

async def safe_tool_execution(tool_name: str, handler: callable, args: dict):
    try:
        result = await handler(args)
        return [types.TextContent(type="text", text=result)]
    except SubsonicAuthenticationError as e:
        logger.error(f"Auth failed in {tool_name}: {e}")
        return [types.TextContent(
            type="text",
            text="Authentication failed. Please verify SUBSONIC_USER and SUBSONIC_PASSWORD."
        )]
    except SubsonicNotFoundError as e:
        logger.error(f"Not found in {tool_name}: {e}")
        return [types.TextContent(
            type="text",
            text=f"Resource not found. {str(e)}"
        )]
    except httpx.ConnectError as e:
        logger.error(f"Connection failed in {tool_name}: {e}")
        return [types.TextContent(
            type="text",
            text="Unable to connect to music server. Please check your server status and try again."
        )]
    except Exception as e:
        logger.exception(f"Unexpected error in {tool_name}")
        return [types.TextContent(
            type="text",
            text=f"An unexpected error occurred: {str(e)}"
        )]
```

3. **Fail-Fast on Server Unavailability** (FR-044, FR-045, FR-046):
   - No retries when Subsonic server is down
   - No exponential backoff
   - Immediate error return with clear message
   - Never return stale cached data on server failure

**User-Friendly Error Messages**:
- "Authentication failed. Please verify SUBSONIC_USER and SUBSONIC_PASSWORD in your configuration."
- "Unable to connect to music server. Please check your server status and try again."
- "No tracks found matching your criteria. Try broadening your search terms."
- "Invalid track ID. Please search for tracks first."
- "Showing first 100 results. Narrow your search by artist, genre, or year for more specific results."

**Alternatives Considered**:
- **Generic Error Messages**: Poor UX, users don't know how to fix issues
- **Retry Logic**: Conflicts with fail-fast requirement (FR-044)
- **Stale Cache on Error**: Conflicts with no-stale-data requirement (FR-045)

---

## 6. Testing Strategy with pytest-asyncio

### Decision: pytest-asyncio with 80%+ Coverage and Mocked SubsonicClient

**Rationale**:
- **Async Support**: pytest-asyncio handles async/await test functions
- **Isolation**: Mock SubsonicClient to avoid real Subsonic server dependency
- **Coverage**: 80% minimum (constitutional 90% as stretch goal)
- **TDD Workflow**: Tests written before implementation

**Test Organization**:
```
tests/
├── conftest.py                 # Shared fixtures (mock SubsonicClient, sample data)
├── test_tools.py               # ToolRegistry: 10 tools × 2 scenarios = 20 tests
├── test_resources.py           # ResourceRegistry: 6 resources × 2 scenarios = 12 tests
├── test_prompts.py             # PromptRegistry: 5 prompts × 2 scenarios = 10 tests
├── test_cache.py               # Cache TTL, invalidation, throttling: 8 tests
├── test_integration.py         # End-to-end MCP protocol: 6 tests
└── test_error_handling.py      # Error scenarios: 10 tests
```

**Mock Pattern**:
```python
# conftest.py
import pytest
from unittest.mock import AsyncMock
from src.subsonic.client import SubsonicClient

@pytest.fixture
def mock_subsonic_client():
    client = AsyncMock(spec=SubsonicClient)
    client.search.return_value = [
        {"id": "1", "title": "Track 1", "artist": "Artist 1"}
    ]
    client.get_artists.return_value = [
        {"id": "a1", "name": "Artist 1"}
    ]
    return client

@pytest.fixture
def tool_registry(mock_subsonic_client):
    from subsonic_mcp.tools import ToolRegistry
    return ToolRegistry(mock_subsonic_client)
```

**Test Example**:
```python
# test_tools.py
@pytest.mark.asyncio
async def test_search_tracks_success(tool_registry):
    result = await tool_registry.execute("search_tracks", {
        "query": "test",
        "limit": 10
    })
    assert len(result) == 1
    assert "Track 1" in result[0].text

@pytest.mark.asyncio
async def test_search_tracks_no_results(tool_registry, mock_subsonic_client):
    mock_subsonic_client.search.return_value = []
    result = await tool_registry.execute("search_tracks", {
        "query": "nonexistent"
    })
    assert "No tracks found" in result[0].text
```

**Coverage Requirements**:
- **80% minimum**: All core logic paths covered
- **90% stretch goal**: Include edge cases, error branches
- **pytest-cov**: `pytest --cov=subsonic_mcp --cov-report=html`

**Alternatives Considered**:
- **Integration Tests Only**: Fragile, requires real Subsonic server
- **unittest.mock**: Less ergonomic for async code than pytest-asyncio
- **VCR.py**: Overkill for this use case, mocking is sufficient

---

## 7. Claude Desktop Integration

### Decision: uv Package Manager with stdio Transport Configuration

**Rationale**:
- **Modern Tooling**: uv is Rust-based, faster than pip (constitutional best practice)
- **Isolated Environment**: uv manages dependencies without global pollution
- **Claude Desktop Compatible**: stdio transport works seamlessly with Claude Desktop config

**Installation**:
```bash
# Install uv (one-time setup)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create MCP server project
cd /workspaces/emby-to-m3u/mcp-server
uv init subsonic-mcp-server
uv add mcp>=1.5.0
uv sync
```

**Claude Desktop Configuration**:
```json
{
  "mcpServers": {
    "subsonic": {
      "command": "uv",
      "args": [
        "--directory",
        "/workspaces/emby-to-m3u/mcp-server",
        "run",
        "python",
        "-m",
        "subsonic_mcp.server"
      ],
      "env": {
        "SUBSONIC_URL": "http://localhost:4040",
        "SUBSONIC_USER": "admin",
        "SUBSONIC_PASSWORD": "secret"
      }
    }
  }
}
```

**Platform-Specific Config Paths**:
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- Linux: `~/.config/Claude/claude_desktop_config.json`

**Alternatives Considered**:
- **pip/venv**: Slower, more manual setup, less modern
- **Docker**: Overengineered for local-only stdio transport
- **System Python**: Dependency conflicts, poor isolation

---

## 8. Performance Optimization

### Decision: Multi-Layer Performance Strategy

**Strategies**:

1. **5-Minute Cache TTL** (FR-009, FR-010, FR-011):
   - Artists, genres, library stats cached
   - Search results cached by query hash
   - Automatic invalidation after 5 minutes

2. **Dynamic Throttling** (FR-041, FR-042, FR-043):
   - Monitor Subsonic response times (sliding window)
   - Increase concurrency when server is fast
   - Decrease concurrency when server slows down
   - No fixed rate limit (FR-047)

3. **Result Limiting** (FR-039, FR-040):
   - Max 100 tracks per search query
   - Clear pagination guidance when limit reached
   - Instruct users to refine searches (artist, genre, year filters)

4. **Connection Pooling** (from SubsonicClient):
   - httpx with 100 max connections
   - 20 keepalive connections
   - HTTP/2 support for multiplexing

**Performance Targets**:
- Cache hit: <5s response time ✅
- Cache miss: <15s response time ✅
- Dynamic throttling prevents server overload ✅

**Monitoring**:
```python
import time

async def execute_with_metrics(func, *args):
    start = time.time()
    result = await func(*args)
    duration = time.time() - start
    cache_manager.update_response_time(duration)
    logger.info(f"Request took {duration:.2f}s")
    return result
```

---

## 9. Memory and Architecture References

### Decision: Leverage Existing Claude Flow Memory

**Memory Keys Used**:
- `refactor/subsonic-api-comparison`: Emby vs Subsonic API mapping
  - Use for understanding Subsonic API patterns
  - Reference for tool design decisions

- `refactor/architecture-summary`: Complete system overview
  - Understand existing project architecture
  - Ensure MCP server aligns with overall design

**How to Access**:
```bash
# Read memory during implementation
npx claude-flow@alpha hooks session-restore --session-id "features/subsonic-mcp"

# Store implementation decisions
npx claude-flow@alpha hooks post-edit \
  --file "mcp-server/src/subsonic_mcp/server.py" \
  --memory-key "features/subsonic-mcp/server-design"
```

**Alternatives Considered**:
- **Start from Scratch**: Lose valuable architectural context
- **Manual Documentation**: Duplicate information, poor reusability

---

## 10. Development Workflow

### Decision: TDD with Constitutional Compliance

**Workflow**:
1. **Write Contract Tests** (Phase 1):
   - Define tool input/output schemas
   - Write failing tests for expected behavior

2. **Implement Tools** (Phase 3):
   - Make contract tests pass
   - Keep modules <500 lines

3. **Integration Tests** (Phase 3):
   - Test MCP protocol compliance
   - Validate tool/resource/prompt interactions

4. **Code Review** (Phase 4):
   - Pylint score 9.0+ required
   - Black formatting enforced
   - Type hints validated

**Constitutional Checkpoints**:
- ✅ 80%+ test coverage (pytest-cov)
- ✅ Modules <500 lines (separate registries)
- ✅ Async/await throughout (Python 3.10+)
- ✅ Environment-based configuration (no secrets in code)

---

## Summary

All technology decisions are finalized:
- ✅ MCP Python SDK 1.5.0 with stdio transport
- ✅ Registry pattern (ToolRegistry, ResourceRegistry, PromptRegistry)
- ✅ Wrap existing SubsonicClient (no duplication)
- ✅ In-memory cache with 5-min TTL + dynamic throttling
- ✅ Comprehensive error handling with user-friendly messages
- ✅ pytest-asyncio with 80%+ coverage
- ✅ uv package manager + Claude Desktop config
- ✅ Performance optimization (caching, throttling, result limiting)
- ✅ Leverage Claude Flow memory references

**No NEEDS CLARIFICATION items remain. Ready for Phase 1: Design & Contracts.**
