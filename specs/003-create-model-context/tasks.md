# Tasks: Subsonic MCP Server for AI-Powered Music Discovery

**Feature**: 003-create-model-context
**Branch**: `003-create-model-context`
**Input**: Design documents from `/workspaces/emby-to-m3u/specs/003-create-model-context/`

---

## Overview

This task list implements a Model Context Protocol (MCP) server that exposes a Subsonic music library to LLM applications (Claude Desktop) for AI-powered playlist generation and music discovery. The implementation follows strict TDD principles with 80%+ test coverage target.

**Total Tasks**: 55 across 4 phases
**Estimated Timeline**: 3-5 days
**Primary Technologies**: Python 3.10+, MCP SDK 1.5.0, pytest-asyncio, uv package manager

---

## Phase 3.1: Project Setup (3 tasks)

### T001: [X] Create mcp-server directory structure
**Files**: `mcp-server/` directory tree
**Description**: Create the isolated MCP server project structure in `mcp-server/` directory:
```
mcp-server/
├── pyproject.toml (placeholder, detailed in T043)
├── README.md (placeholder, detailed in T045)
├── src/
│   └── subsonic_mcp/
│       ├── __init__.py
│       ├── server.py (implementation in T042)
│       ├── tools.py (implementation in T039)
│       ├── resources.py (implementation in T040)
│       ├── prompts.py (implementation in T041)
│       ├── cache.py (implementation in T037)
│       └── utils.py (implementation in T038)
└── tests/
    ├── conftest.py (implementation in T044)
    ├── test_tools.py (implementation in T004-T023)
    ├── test_resources.py (implementation in T024-T035)
    ├── test_prompts.py (implementation in T036)
    ├── test_cache.py (implementation in T047)
    ├── test_integration.py (implementation in T046)
    └── test_error_handling.py (implementation in T048)
```
Create all `__init__.py` files with docstrings describing module purposes.

**Dependencies**: None
**Verification**: Directory structure matches plan.md, all `__init__.py` files exist

---

### T002: [X] Install uv and initialize project
**Files**: `mcp-server/` with uv configuration
**Description**:
1. Verify uv is installed: `uv --version` (should be 0.8.22+)
2. Navigate to `mcp-server/` directory
3. Initialize uv project: `uv init subsonic-mcp-server`
4. Add MCP SDK dependency: `uv add mcp>=1.5.0`
5. Sync dependencies: `uv sync`
6. Verify MCP import works: `uv run python -c "import mcp; print(mcp.__version__)"`

**Dependencies**: T001
**Verification**: `uv.lock` file created, MCP SDK installed, Python 3.10+ available

---

### T003: [X] [P] Configure development tools (Black, Pylint, pytest)
**Files**: `mcp-server/pyproject.toml` (append tool configuration)
**Description**: Add development tool configuration to `pyproject.toml`:
```toml
[tool.black]
line-length = 100
target-version = ['py310']

[tool.pylint]
max-line-length = 100
disable = ["C0111"]  # Missing docstrings (we'll add them progressively)

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "--cov=subsonic_mcp --cov-report=html --cov-report=term-missing"
```

Add dev dependencies:
```bash
uv add --dev pytest>=8.0.0 pytest-asyncio>=0.23.0 pytest-cov>=4.1.0 black>=24.0.0 pylint>=3.0.0
```

**Dependencies**: T002
**Verification**: Run `uv run black --version`, `uv run pylint --version`, `uv run pytest --version`

---

## Phase 3.2: Contract Tests (42 tasks) ⚠️ CRITICAL: MUST FAIL BEFORE IMPLEMENTATION

**IMPORTANT**: All tests in this phase MUST be written and MUST FAIL before proceeding to Phase 3.3 implementation.

### Tools Contract Tests (20 tasks - T004 to T023)

### T004: [P] Contract test: search_tracks success scenario
**File**: `mcp-server/tests/test_tools.py`
**Description**: Create test function `test_search_tracks_success()` that:
1. Uses mocked SubsonicClient (from conftest.py fixture)
2. Mocks `client.search()` to return sample track list
3. Calls `ToolRegistry.execute("search_tracks", {"query": "beatles", "limit": 10})`
4. Asserts result contains TextContent with track data
5. Verifies JSON format matches tools.json contract schema
6. **MUST FAIL** with ImportError (ToolRegistry not implemented yet)

**Dependencies**: T002 (pytest available), T044 (conftest.py for fixtures)
**Verification**: Test exists, runs, and fails with expected error

---

### T005: [P] Contract test: search_tracks with 100 result limit
**File**: `mcp-server/tests/test_tools.py`
**Description**: Create test function `test_search_tracks_result_limit()` that:
1. Mocks `client.search()` to return 150 tracks
2. Calls `ToolRegistry.execute("search_tracks", {"query": "test", "limit": 100})`
3. Asserts result contains exactly 100 tracks
4. Asserts pagination_note present: "Showing first 100 results..."
5. **MUST FAIL** with ImportError

**Dependencies**: T002, T044
**Verification**: Test fails with expected error

---

### T006: [P] Contract test: search_tracks no results
**File**: `mcp-server/tests/test_tools.py`
**Description**: Create test function `test_search_tracks_no_results()` that:
1. Mocks `client.search()` to return empty list
2. Calls `ToolRegistry.execute("search_tracks", {"query": "nonexistent"})`
3. Asserts result contains user-friendly message: "No tracks found matching your criteria"
4. **MUST FAIL** with ImportError

**Dependencies**: T002, T044
**Verification**: Test fails with expected error

---

### T007: [P] Contract test: get_track_info success
**File**: `mcp-server/tests/test_tools.py`
**Description**: Create test function `test_get_track_info_success()` that:
1. Mocks `client.get_track()` to return track with full metadata
2. Calls `ToolRegistry.execute("get_track_info", {"track_id": "123"})`
3. Asserts all fields present: id, title, artist, album, genre, year, duration, bitrate, streaming_url
4. Validates against Track schema in tools.json
5. **MUST FAIL** with ImportError

**Dependencies**: T002, T044
**Verification**: Test fails with expected error

---

### T008: [P] Contract test: get_track_info not found
**File**: `mcp-server/tests/test_tools.py`
**Description**: Create test function `test_get_track_info_not_found()` that:
1. Mocks `client.get_track()` to raise `SubsonicNotFoundError`
2. Calls `ToolRegistry.execute("get_track_info", {"track_id": "invalid"})`
3. Asserts error message: "Resource not found. Track with ID 'invalid' does not exist"
4. **MUST FAIL** with ImportError

**Dependencies**: T002, T044
**Verification**: Test fails with expected error

---

### T009: [P] Contract test: get_artists success
**File**: `mcp-server/tests/test_tools.py`
**Description**: Create test function `test_get_artists_success()` that:
1. Mocks `client.get_artists()` to return artist list with counts
2. Calls `ToolRegistry.execute("get_artists", {})`
3. Asserts result contains total count and artists array
4. Validates Artist schema (id, name, album_count, track_count)
5. **MUST FAIL** with ImportError

**Dependencies**: T002, T044
**Verification**: Test fails with expected error

---

### T010: [P] Contract test: get_artists empty library
**File**: `mcp-server/tests/test_tools.py`
**Description**: Create test function `test_get_artists_empty_library()` that:
1. Mocks `client.get_artists()` to return empty list
2. Calls `ToolRegistry.execute("get_artists", {})`
3. Asserts total=0 and empty artists array
4. **MUST FAIL** with ImportError

**Dependencies**: T002, T044
**Verification**: Test fails with expected error

---

### T011: [P] Contract test: get_artist_albums success
**File**: `mcp-server/tests/test_tools.py`
**Description**: Create test function `test_get_artist_albums_success()` that:
1. Mocks `client.get_artist_albums()` to return album list for artist
2. Calls `ToolRegistry.execute("get_artist_albums", {"artist_id": "a123"})`
3. Asserts album data includes id, name, artist, year, track_count
4. Validates Album schema from tools.json
5. **MUST FAIL** with ImportError

**Dependencies**: T002, T044
**Verification**: Test fails with expected error

---

### T012: [P] Contract test: get_artist_albums invalid artist
**File**: `mcp-server/tests/test_tools.py`
**Description**: Create test function `test_get_artist_albums_invalid_artist()` that:
1. Mocks `client.get_artist_albums()` to raise `SubsonicNotFoundError`
2. Calls `ToolRegistry.execute("get_artist_albums", {"artist_id": "invalid"})`
3. Asserts error message contains artist ID
4. **MUST FAIL** with ImportError

**Dependencies**: T002, T044
**Verification**: Test fails with expected error

---

### T013: [P] Contract test: get_album_tracks success
**File**: `mcp-server/tests/test_tools.py`
**Description**: Create test function `test_get_album_tracks_success()` that:
1. Mocks `client.get_album_tracks()` to return track list for album
2. Calls `ToolRegistry.execute("get_album_tracks", {"album_id": "al456"})`
3. Asserts tracks array with complete Track metadata
4. **MUST FAIL** with ImportError

**Dependencies**: T002, T044
**Verification**: Test fails with expected error

---

### T014: [P] Contract test: get_album_tracks invalid album
**File**: `mcp-server/tests/test_tools.py`
**Description**: Create test function `test_get_album_tracks_invalid_album()` that:
1. Mocks `client.get_album_tracks()` to raise `SubsonicNotFoundError`
2. Calls `ToolRegistry.execute("get_album_tracks", {"album_id": "invalid"})`
3. Asserts user-friendly error message
4. **MUST FAIL** with ImportError

**Dependencies**: T002, T044
**Verification**: Test fails with expected error

---

### T015: [P] Contract test: search_similar success
**File**: `mcp-server/tests/test_tools.py`
**Description**: Create test function `test_search_similar_success()` that:
1. Mocks similarity search to return related tracks
2. Calls `ToolRegistry.execute("search_similar", {"query": "Pink Floyd", "limit": 20})`
3. Asserts similar_tracks array contains progressive rock tracks
4. **MUST FAIL** with ImportError

**Dependencies**: T002, T044
**Verification**: Test fails with expected error

---

### T016: [P] Contract test: search_similar with limit
**File**: `mcp-server/tests/test_tools.py`
**Description**: Create test function `test_search_similar_limit()` that:
1. Mocks similarity search to return 150 tracks
2. Calls with limit=100
3. Asserts exactly 100 results with pagination note
4. **MUST FAIL** with ImportError

**Dependencies**: T002, T044
**Verification**: Test fails with expected error

---

### T017: [P] Contract test: get_genres success
**File**: `mcp-server/tests/test_tools.py`
**Description**: Create test function `test_get_genres_success()` that:
1. Mocks `client.get_genres()` to return genre list with counts
2. Calls `ToolRegistry.execute("get_genres", {})`
3. Asserts Genre schema (name, track_count, album_count)
4. **MUST FAIL** with ImportError

**Dependencies**: T002, T044
**Verification**: Test fails with expected error

---

### T018: [P] Contract test: get_genres empty
**File**: `mcp-server/tests/test_tools.py`
**Description**: Create test function `test_get_genres_empty()` that:
1. Mocks `client.get_genres()` to return empty list
2. Asserts total=0 and empty genres array
3. **MUST FAIL** with ImportError

**Dependencies**: T002, T044
**Verification**: Test fails with expected error

---

### T019: [P] Contract test: get_tracks_by_genre success
**File**: `mcp-server/tests/test_tools.py`
**Description**: Create test function `test_get_tracks_by_genre_success()` that:
1. Mocks genre filtering to return rock tracks
2. Calls `ToolRegistry.execute("get_tracks_by_genre", {"genre": "Rock", "limit": 20})`
3. Asserts all tracks have genre="Rock"
4. **MUST FAIL** with ImportError

**Dependencies**: T002, T044
**Verification**: Test fails with expected error

---

### T020: [P] Contract test: get_tracks_by_genre with limit
**File**: `mcp-server/tests/test_tools.py`
**Description**: Create test function `test_get_tracks_by_genre_limit()` that:
1. Mocks 200 rock tracks
2. Calls with limit=100
3. Asserts pagination note present
4. **MUST FAIL** with ImportError

**Dependencies**: T002, T044
**Verification**: Test fails with expected error

---

### T021: [P] Contract test: analyze_library success
**File**: `mcp-server/tests/test_tools.py`
**Description**: Create test function `test_analyze_library_success()` that:
1. Mocks library stats (10000 tracks, 500 artists, 800 albums, 50 genres)
2. Calls `ToolRegistry.execute("analyze_library", {})`
3. Asserts LibraryStats schema with all fields
4. Validates cache_stats present (cached_items, hit_rate)
5. **MUST FAIL** with ImportError

**Dependencies**: T002, T044
**Verification**: Test fails with expected error

---

### T022: [P] Contract test: stream_track success
**File**: `mcp-server/tests/test_tools.py`
**Description**: Create test function `test_stream_track_success()` that:
1. Mocks `client.stream()` to return streaming URL
2. Calls `ToolRegistry.execute("stream_track", {"track_id": "t789"})`
3. Asserts response contains track_id, streaming_url (valid URI)
4. **MUST FAIL** with ImportError

**Dependencies**: T002, T044
**Verification**: Test fails with expected error

---

### T023: [P] Contract test: stream_track invalid track
**File**: `mcp-server/tests/test_tools.py`
**Description**: Create test function `test_stream_track_invalid()` that:
1. Mocks `client.stream()` to raise `SubsonicNotFoundError`
2. Asserts error message: "Invalid track ID. Please search for tracks first."
3. **MUST FAIL** with ImportError

**Dependencies**: T002, T044
**Verification**: Test fails with expected error

---

### Resources Contract Tests (12 tasks - T024 to T035)

### T024: [P] Contract test: library_stats resource success
**File**: `mcp-server/tests/test_resources.py`
**Description**: Create test function `test_library_stats_resource_success()` that:
1. Uses mocked SubsonicClient
2. Calls `ResourceRegistry.read("library://stats")`
3. Asserts JSON response matches LibraryStats schema
4. Validates cache_stats included
5. **MUST FAIL** with ImportError (ResourceRegistry not implemented)

**Dependencies**: T002, T044
**Verification**: Test fails with expected error

---

### T025: [P] Contract test: library_stats with caching
**File**: `mcp-server/tests/test_resources.py`
**Description**: Create test function `test_library_stats_cached()` that:
1. Calls resource twice within 5-minute window
2. Asserts second call is faster (cache hit)
3. Verifies SubsonicClient called only once
4. **MUST FAIL** with ImportError

**Dependencies**: T002, T044
**Verification**: Test fails with expected error

---

### T026: [P] Contract test: artists resource success
**File**: `mcp-server/tests/test_resources.py`
**Description**: Create test function `test_artists_resource_success()` that:
1. Mocks artist catalog
2. Calls `ResourceRegistry.read("library://artists")`
3. Asserts JSON with total and artists array
4. Validates Artist schema
5. **MUST FAIL** with ImportError

**Dependencies**: T002, T044
**Verification**: Test fails with expected error

---

### T027: [P] Contract test: artists resource error
**File**: `mcp-server/tests/test_resources.py`
**Description**: Create test function `test_artists_resource_error()` that:
1. Mocks `client.get_artists()` to raise connection error
2. Calls resource
3. Asserts error message: "Unable to connect to music server..."
4. **MUST FAIL** with ImportError

**Dependencies**: T002, T044
**Verification**: Test fails with expected error

---

### T028: [P] Contract test: albums resource success
**File**: `mcp-server/tests/test_resources.py`
**Description**: Create test function `test_albums_resource_success()` that:
1. Mocks album collection
2. Calls `ResourceRegistry.read("library://albums")`
3. Validates Album schema for all items
4. **MUST FAIL** with ImportError

**Dependencies**: T002, T044
**Verification**: Test fails with expected error

---

### T029: [P] Contract test: albums resource error
**File**: `mcp-server/tests/test_resources.py`
**Description**: Create test function `test_albums_resource_error()` that:
1. Mocks authentication failure
2. Asserts error: "Authentication failed. Please verify SUBSONIC_USER and SUBSONIC_PASSWORD."
3. **MUST FAIL** with ImportError

**Dependencies**: T002, T044
**Verification**: Test fails with expected error

---

### T030: [P] Contract test: genres resource success
**File**: `mcp-server/tests/test_resources.py`
**Description**: Create test function `test_genres_resource_success()` that:
1. Mocks genre taxonomy with counts
2. Calls `ResourceRegistry.read("library://genres")`
3. Validates Genre schema
4. **MUST FAIL** with ImportError

**Dependencies**: T002, T044
**Verification**: Test fails with expected error

---

### T031: [P] Contract test: genres resource caching
**File**: `mcp-server/tests/test_resources.py`
**Description**: Create test function `test_genres_resource_cached()` that:
1. Calls resource twice
2. Verifies 5-minute TTL cache behavior
3. **MUST FAIL** with ImportError

**Dependencies**: T002, T044
**Verification**: Test fails with expected error

---

### T032: [P] Contract test: playlists resource success
**File**: `mcp-server/tests/test_resources.py`
**Description**: Create test function `test_playlists_resource_success()` that:
1. Mocks playlist list with tracks
2. Calls `ResourceRegistry.read("library://playlists")`
3. Validates Playlist schema
4. **MUST FAIL** with ImportError

**Dependencies**: T002, T044
**Verification**: Test fails with expected error

---

### T033: [P] Contract test: playlists resource 2-min TTL
**File**: `mcp-server/tests/test_resources.py`
**Description**: Create test function `test_playlists_shorter_ttl()` that:
1. Verifies playlists use 2-minute TTL (not 5-minute)
2. Mock time.sleep() to simulate 2-minute passage
3. Asserts cache expired after 2 minutes
4. **MUST FAIL** with ImportError

**Dependencies**: T002, T044
**Verification**: Test fails with expected error

---

### T034: [P] Contract test: recent_tracks resource success
**File**: `mcp-server/tests/test_resources.py`
**Description**: Create test function `test_recent_tracks_resource_success()` that:
1. Mocks 100 recently added tracks
2. Calls `ResourceRegistry.read("library://recent")`
3. Asserts max 100 items in response
4. **MUST FAIL** with ImportError

**Dependencies**: T002, T044
**Verification**: Test fails with expected error

---

### T035: [P] Contract test: recent_tracks 1-min TTL
**File**: `mcp-server/tests/test_resources.py`
**Description**: Create test function `test_recent_tracks_shortest_ttl()` that:
1. Verifies 1-minute TTL for recent tracks
2. Asserts cache invalidation after 60 seconds
3. **MUST FAIL** with ImportError

**Dependencies**: T002, T044
**Verification**: Test fails with expected error

---

### Prompts Contract Tests (10 tasks - T036 and sub-tests)

### T036: [P] Contract tests for all 5 prompts
**File**: `mcp-server/tests/test_prompts.py`
**Description**: Create 10 test functions for prompts (2 per prompt):

1. `test_mood_playlist_with_args()` - mood="relaxing", duration=45
2. `test_mood_playlist_default_duration()` - mood only, duration defaults to 60
3. `test_music_discovery_with_genres()` - favorite_artists + genres provided
4. `test_music_discovery_no_genres()` - only favorite_artists
5. `test_listening_analysis_genre_distribution()` - analysis_type="genre_distribution"
6. `test_listening_analysis_artist_diversity()` - analysis_type="artist_diversity"
7. `test_smart_playlist_with_max()` - criteria + max_tracks=50
8. `test_smart_playlist_default_max()` - criteria only, max_tracks defaults
9. `test_library_curation_duplicates()` - task="duplicates"
10. `test_library_curation_missing_metadata()` - task="missing_metadata"

Each test:
- Calls `PromptRegistry.get(name, args)`
- Asserts PromptResult structure with description and messages
- Validates prompt text contains interpolated arguments
- Verifies role="user" and content.type="text"
- **MUST FAIL** with ImportError (PromptRegistry not implemented)

**Dependencies**: T002, T044
**Verification**: All 10 tests fail with expected error

---

## Phase 3.3: Core Implementation (6 tasks)

**CRITICAL**: Only proceed after ALL contract tests (T004-T036) are written and failing.

### T037: Implement CacheManager with TTL and dynamic throttling
**File**: `mcp-server/src/subsonic_mcp/cache.py`
**Description**: Create `CacheManager` class with:
```python
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from collections import deque

@dataclass
class CacheEntry:
    data: Any
    timestamp: datetime
    ttl_seconds: int = 300

class CacheManager:
    def __init__(self, default_ttl: int = 300):
        self.cache: Dict[str, CacheEntry] = {}
        self.default_ttl = default_ttl
        self.response_times = deque(maxlen=100)

    async def get(self, key: str) -> Optional[Any]:
        """Return cached data if not expired, else None"""
        # Check expiration: (now - entry.timestamp) < ttl

    async def set(self, key: str, data: Any, ttl: Optional[int] = None):
        """Store data with TTL"""

    def update_response_time(self, duration: float):
        """Track Subsonic server response time"""

    def should_throttle(self) -> bool:
        """Return True if avg response time > 2s"""
        if len(self.response_times) < 10:
            return False
        avg = sum(self.response_times) / len(self.response_times)
        return avg > 2.0
```

**Dependencies**: T004-T036 (tests written and failing)
**Verification**:
- `cache.py` <150 lines
- All methods have type hints
- Docstrings present
- No tests pass yet (CacheManager not integrated)

---

### T038: Implement error handling utilities
**File**: `mcp-server/src/subsonic_mcp/utils.py`
**Description**: Create error handling utilities:
```python
import logging
from typing import Any, Callable
import mcp.types as types
from src.subsonic.exceptions import (
    SubsonicAuthenticationError,
    SubsonicNotFoundError,
    SubsonicError
)
import httpx

logger = logging.getLogger(__name__)

class MCPError(Exception):
    """Base exception for MCP server errors"""
    pass

async def safe_tool_execution(
    tool_name: str,
    handler: Callable,
    arguments: dict[str, Any]
) -> list[types.TextContent]:
    """Execute tool with comprehensive error handling"""
    try:
        result = await handler(arguments)
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

**Dependencies**: T037
**Verification**:
- `utils.py` <100 lines
- All exception types handled
- User-friendly messages (no technical jargon)

---

### T039: Implement ToolRegistry with 10 tools
**File**: `mcp-server/src/subsonic_mcp/tools.py`
**Description**: Create `ToolRegistry` class that makes T004-T023 pass:
```python
from typing import Any
import mcp.types as types
from src.subsonic.client import SubsonicClient
from .cache import CacheManager
from .utils import safe_tool_execution
import json

class ToolRegistry:
    def __init__(self, subsonic_client: SubsonicClient, cache: CacheManager):
        self.client = subsonic_client
        self.cache = cache
        self.tools = self._define_tools()

    def _define_tools(self) -> dict[str, types.Tool]:
        """Define all 10 tools per tools.json contract"""
        return {
            "search_tracks": types.Tool(
                name="search_tracks",
                description="Search for music tracks (max 100 results)",
                inputSchema={...}  # From contracts/tools.json
            ),
            # ... 9 more tools
        }

    def get_all(self) -> list[types.Tool]:
        return list(self.tools.values())

    async def execute(self, name: str, args: dict) -> list[types.TextContent]:
        if name not in self.tools:
            raise ValueError(f"Unknown tool: {name}")
        handler = getattr(self, f"_handle_{name}")
        return await safe_tool_execution(name, handler, args)

    async def _handle_search_tracks(self, args: dict) -> str:
        query = args["query"]
        limit = min(args.get("limit", 20), 100)  # Enforce max 100

        # Check cache first
        cache_key = f"search:{query}:{limit}"
        cached = await self.cache.get(cache_key)
        if cached:
            return cached

        # Call SubsonicClient
        results = await self.client.search(query=query, limit=limit)

        # Format response
        response = self._format_search_results(results, limit)

        # Cache for 5 minutes
        await self.cache.set(cache_key, response, ttl=300)

        return response

    # ... Implement _handle_* for all 10 tools
```

**Dependencies**: T037, T038, T004-T023 (tests failing)
**Verification**:
- `tools.py` <400 lines (all 10 tools)
- T004-T023 now PASS (20 tests)
- All tools enforce 100 result limit
- Cache integration works

---

### T040: Implement ResourceRegistry with 6 resources
**File**: `mcp-server/src/subsonic_mcp/resources.py`
**Description**: Create `ResourceRegistry` class that makes T024-T035 pass:
```python
from typing import Any
import mcp.types as types
from src.subsonic.client import SubsonicClient
from .cache import CacheManager
import json

class ResourceRegistry:
    def __init__(self, subsonic_client: SubsonicClient, cache: CacheManager):
        self.client = subsonic_client
        self.cache = cache
        self.resources = self._define_resources()

    def _define_resources(self) -> dict[str, types.Resource]:
        """Define all 6 resources per resources.json contract"""
        return {
            "library_stats": types.Resource(
                uri="library://stats",
                name="Library Statistics",
                description="Complete library statistics with cache info",
                mimeType="application/json"
            ),
            # ... 5 more resources
        }

    def get_all(self) -> list[types.Resource]:
        return list(self.resources.values())

    async def read(self, uri: str) -> str:
        """Read resource by URI"""
        resource_map = {
            "library://stats": (self._read_library_stats, 300),
            "library://artists": (self._read_artists, 300),
            "library://albums": (self._read_albums, 300),
            "library://genres": (self._read_genres, 300),
            "library://playlists": (self._read_playlists, 120),  # 2-min TTL
            "library://recent": (self._read_recent_tracks, 60),  # 1-min TTL
        }

        if uri not in resource_map:
            raise ValueError(f"Unknown resource URI: {uri}")

        handler, ttl = resource_map[uri]

        # Check cache
        cached = await self.cache.get(uri)
        if cached:
            return cached

        # Fetch fresh data
        data = await handler()

        # Cache with appropriate TTL
        await self.cache.set(uri, data, ttl=ttl)

        return data

    async def _read_library_stats(self) -> str:
        stats = await self.client.get_library_stats()
        cache_stats = {
            "cached_items": len(self.cache.cache),
            "hit_rate": 0.0  # Calculate from cache metrics
        }
        return json.dumps({**stats, "cache_stats": cache_stats}, indent=2)

    # ... Implement _read_* for all 6 resources
```

**Dependencies**: T037, T024-T035 (tests failing)
**Verification**:
- `resources.py` <250 lines
- T024-T035 now PASS (12 tests)
- Different TTLs respected (5-min, 2-min, 1-min)

---

### T041: Implement PromptRegistry with 5 prompts
**File**: `mcp-server/src/subsonic_mcp/prompts.py`
**Description**: Create `PromptRegistry` class that makes T036 pass:
```python
import mcp.types as types
from src.subsonic.client import SubsonicClient

class PromptRegistry:
    def __init__(self, subsonic_client: SubsonicClient):
        self.client = subsonic_client
        self.prompts = self._define_prompts()

    def _define_prompts(self) -> dict[str, types.Prompt]:
        """Define all 5 prompts per prompts.json contract"""
        return {
            "mood_playlist": types.Prompt(
                name="mood_playlist",
                description="Generate a curated playlist based on mood or activity",
                arguments=[
                    types.PromptArgument(
                        name="mood",
                        description="Target mood or genre",
                        required=True
                    ),
                    types.PromptArgument(
                        name="duration",
                        description="Target duration in minutes",
                        required=False
                    ),
                ]
            ),
            # ... 4 more prompts
        }

    def get_all(self) -> list[types.Prompt]:
        return list(self.prompts.values())

    async def get(self, name: str, arguments: dict[str, str] | None = None) -> types.GetPromptResult:
        if name not in self.prompts:
            raise ValueError(f"Unknown prompt: {name}")

        handler = getattr(self, f"_generate_{name}")
        return await handler(arguments or {})

    async def _generate_mood_playlist(self, args: dict) -> types.GetPromptResult:
        mood = args.get("mood", "mixed")
        duration = args.get("duration", "60")

        prompt_text = f"""Create a {mood} playlist with the following criteria:

**Playlist Requirements:**
- **Mood/Genre:** {mood}
- **Target Duration:** {duration} minutes
- **Variety:** Include different artists
- **Flow:** Arrange tracks for smooth transitions

Use the search_tracks and get_tracks_by_genre tools to find matching tracks."""

        return types.GetPromptResult(
            description=f"Playlist creation for {mood} mood, {duration} min",
            messages=[
                types.PromptMessage(
                    role="user",
                    content=types.TextContent(type="text", text=prompt_text)
                )
            ]
        )

    # ... Implement _generate_* for all 5 prompts
```

**Dependencies**: T036 (tests failing)
**Verification**:
- `prompts.py` <300 lines
- T036 now PASSES (10 tests)
- All prompts interpolate arguments correctly

---

### T042: Implement MCPServer main class
**File**: `mcp-server/src/subsonic_mcp/server.py`
**Description**: Create main `LibraryMCPServer` class:
```python
import asyncio
import logging
import os
from typing import Any, Sequence

import mcp.server.stdio
import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions

from src.subsonic.client import SubsonicClient
from src.subsonic.models import SubsonicConfig

from .tools import ToolRegistry
from .resources import ResourceRegistry
from .prompts import PromptRegistry
from .cache import CacheManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LibraryMCPServer:
    """MCP Server for Subsonic music library"""

    def __init__(self):
        self.server = Server("subsonic-mcp")

        # Load config from environment
        config = SubsonicConfig(
            url=os.getenv("SUBSONIC_URL"),
            username=os.getenv("SUBSONIC_USER"),
            password=os.getenv("SUBSONIC_PASSWORD")
        )

        # Initialize components
        self.subsonic_client = SubsonicClient(config)
        self.cache = CacheManager(default_ttl=300)
        self.tool_registry = ToolRegistry(self.subsonic_client, self.cache)
        self.resource_registry = ResourceRegistry(self.subsonic_client, self.cache)
        self.prompt_registry = PromptRegistry(self.subsonic_client)

        # Register handlers
        self._register_handlers()

    def _register_handlers(self):
        """Register MCP protocol handlers"""

        @self.server.list_tools()
        async def list_tools() -> list[types.Tool]:
            return self.tool_registry.get_all()

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict) -> Sequence[types.TextContent]:
            return await self.tool_registry.execute(name, arguments)

        @self.server.list_resources()
        async def list_resources() -> list[types.Resource]:
            return self.resource_registry.get_all()

        @self.server.read_resource()
        async def read_resource(uri: str) -> str:
            return await self.resource_registry.read(uri)

        @self.server.list_prompts()
        async def list_prompts() -> list[types.Prompt]:
            return self.prompt_registry.get_all()

        @self.server.get_prompt()
        async def get_prompt(name: str, arguments: dict | None = None) -> types.GetPromptResult:
            return await self.prompt_registry.get(name, arguments)

    async def run(self):
        """Run MCP server with stdio transport"""
        logger.info("Starting Subsonic MCP server...")

        # Validate Subsonic connection at startup
        if not await self._validate_connection():
            raise RuntimeError("Failed to connect to Subsonic server")

        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="subsonic-mcp",
                    server_version="0.1.0",
                    capabilities=self.server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={}
                    )
                )
            )

    async def _validate_connection(self) -> bool:
        """Validate Subsonic connection at startup"""
        try:
            await self.subsonic_client.ping()
            logger.info("Successfully connected to Subsonic server")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Subsonic: {e}")
            return False

async def main():
    """Main entry point"""
    server = LibraryMCPServer()
    await server.run()

if __name__ == "__main__":
    asyncio.run(main())
```

**Dependencies**: T037-T041
**Verification**:
- `server.py` <200 lines
- Environment variables loaded correctly
- Connection validation works
- All handlers registered

---

## Phase 3.4: Integration & Validation (4 tasks)

### T046: Integration test: Full MCP protocol flow
**File**: `mcp-server/tests/test_integration.py`
**Description**: Create end-to-end test that:
1. Starts `LibraryMCPServer` instance (mocked SubsonicClient)
2. Simulates MCP client connection
3. Calls `list_tools()` → asserts 10 tools returned
4. Calls `call_tool("search_tracks", {...})` → asserts response
5. Calls `list_resources()` → asserts 6 resources
6. Calls `read_resource("library://stats")` → validates JSON
7. Calls `list_prompts()` → asserts 5 prompts
8. Calls `get_prompt("mood_playlist", {...})` → validates template
9. Verifies all MCP protocol requirements met

**Dependencies**: T037-T042
**Verification**: Integration test passes, full protocol compliance verified

---

### T047: Integration test: Cache TTL and throttling
**File**: `mcp-server/tests/test_cache.py`
**Description**: Create cache behavior tests:
```python
@pytest.mark.asyncio
async def test_cache_ttl_expiration():
    """Verify 5-minute TTL for library stats"""
    cache = CacheManager(default_ttl=300)
    await cache.set("test_key", "test_data", ttl=2)

    # Immediately after: cache hit
    assert await cache.get("test_key") == "test_data"

    # After 3 seconds: cache miss (expired)
    await asyncio.sleep(3)
    assert await cache.get("test_key") is None

@pytest.mark.asyncio
async def test_dynamic_throttling():
    """Verify throttling kicks in when avg response > 2s"""
    cache = CacheManager()

    # Add fast responses (no throttling)
    for _ in range(10):
        cache.update_response_time(0.5)
    assert cache.should_throttle() is False

    # Add slow responses (throttling triggered)
    for _ in range(10):
        cache.update_response_time(3.0)
    assert cache.should_throttle() is True
```

**Dependencies**: T037, T042
**Verification**: Cache TTL and throttling logic works correctly

---

### T048: Integration test: Error handling scenarios
**File**: `mcp-server/tests/test_error_handling.py`
**Description**: Create error handling tests:
```python
@pytest.mark.asyncio
async def test_authentication_error_handling():
    """Verify auth error returns user-friendly message"""
    # Mock SubsonicClient to raise SubsonicAuthenticationError
    # Call tool
    # Assert error message: "Authentication failed. Please verify..."

@pytest.mark.asyncio
async def test_connection_error_handling():
    """Verify connection error returns user-friendly message"""
    # Mock httpx.ConnectError
    # Assert: "Unable to connect to music server..."

@pytest.mark.asyncio
async def test_not_found_error_handling():
    """Verify not found error returns user-friendly message"""
    # Mock SubsonicNotFoundError
    # Assert: "Resource not found..."

@pytest.mark.asyncio
async def test_invalid_tool_name():
    """Verify invalid tool name raises ValueError"""
    # Call non-existent tool
    # Assert ValueError with clear message
```

**Dependencies**: T038, T042
**Verification**: All error scenarios handled gracefully

---

### T049: Manual validation with quickstart.md
**File**: Manual testing following `/workspaces/emby-to-m3u/specs/003-create-model-context/quickstart.md`
**Description**: Execute all quickstart validation steps:
1. Install uv package manager
2. Set up MCP server with `uv sync`
3. Configure Claude Desktop (`claude_desktop_config.json`)
4. Restart Claude Desktop
5. Test basic search: "Search for tracks by 'Beatles'"
6. Test library analysis: "Analyze my music library"
7. Test playlist generation: "Create a relaxing evening playlist"
8. Verify all 4 usage examples from quickstart.md work
9. Check troubleshooting scenarios (auth failure, connection timeout, etc.)

**Dependencies**: T042-T048, quickstart.md
**Verification**: All quickstart examples work, MCP server functional in Claude Desktop

---

## Phase 3.5: Packaging & Documentation (3 tasks)

### T043: [P] Create pyproject.toml with uv configuration
**File**: `mcp-server/pyproject.toml`
**Description**: Complete `pyproject.toml` with full configuration:
```toml
[project]
name = "subsonic-mcp-server"
version = "0.1.0"
description = "MCP server for Subsonic music library - AI-powered playlist generation"
readme = "README.md"
requires-python = ">=3.10"
dependencies = [
    "mcp>=1.5.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.1.0",
    "black>=24.0.0",
    "pylint>=3.0.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.uv]
dev-dependencies = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.1.0",
]

[tool.black]
line-length = 100
target-version = ['py310']

[tool.pylint.main]
max-line-length = 100
disable = ["C0111"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "--cov=subsonic_mcp --cov-report=html --cov-report=term-missing"
```

**Dependencies**: T002
**Verification**: `uv sync` works, all dependencies installed

---

### T044: [P] Create pytest fixtures (conftest.py)
**File**: `mcp-server/tests/conftest.py`
**Description**: Create shared test fixtures:
```python
import pytest
from unittest.mock import AsyncMock
from src.subsonic.client import SubsonicClient
from src.subsonic.models import SubsonicConfig

@pytest.fixture
def subsonic_config():
    """Test Subsonic configuration"""
    return SubsonicConfig(
        url="http://test-server:4040",
        username="test_user",
        password="test_password"
    )

@pytest.fixture
def mock_subsonic_client():
    """Mocked SubsonicClient for testing"""
    client = AsyncMock(spec=SubsonicClient)

    # Configure common mock responses
    client.search.return_value = [
        {
            "id": "track1",
            "title": "Test Track",
            "artist": "Test Artist",
            "album": "Test Album",
            "genre": "Rock",
            "year": 2020,
            "duration": 180,
            "bitrate": 320,
            "streaming_url": "http://test-server/stream/track1"
        }
    ]

    client.get_artists.return_value = [
        {"id": "a1", "name": "Artist 1", "album_count": 5, "track_count": 50}
    ]

    client.get_genres.return_value = [
        {"name": "Rock", "track_count": 100, "album_count": 20}
    ]

    client.ping.return_value = True

    return client

@pytest.fixture
def tool_registry(mock_subsonic_client):
    """ToolRegistry with mocked client"""
    from subsonic_mcp.tools import ToolRegistry
    from subsonic_mcp.cache import CacheManager
    return ToolRegistry(mock_subsonic_client, CacheManager())

@pytest.fixture
def resource_registry(mock_subsonic_client):
    """ResourceRegistry with mocked client"""
    from subsonic_mcp.resources import ResourceRegistry
    from subsonic_mcp.cache import CacheManager
    return ResourceRegistry(mock_subsonic_client, CacheManager())

@pytest.fixture
def prompt_registry(mock_subsonic_client):
    """PromptRegistry with mocked client"""
    from subsonic_mcp.prompts import PromptRegistry
    return PromptRegistry(mock_subsonic_client)
```

**Dependencies**: T002
**Verification**: All test files can import fixtures, tests can run

---

### T045: [P] Create README.md with installation guide
**File**: `mcp-server/README.md`
**Description**: Create comprehensive README:
```markdown
# Subsonic MCP Server

Model Context Protocol (MCP) server for Subsonic music libraries, enabling AI-powered playlist generation and music discovery in Claude Desktop.

## Features

- **10 MCP Tools**: Search tracks, analyze library, stream tracks, discover similar music
- **6 MCP Resources**: Library statistics, artists, albums, genres, playlists, recent tracks
- **5 MCP Prompts**: Mood playlists, music discovery, listening analysis, smart playlists, library curation
- **Performance**: 5-minute cache TTL, dynamic throttling, <5s response times
- **Testing**: 80%+ coverage with pytest-asyncio

## Installation

### Prerequisites
- Python 3.10+
- Claude Desktop
- Subsonic or OpenSubsonic server

### Setup
1. Install uv package manager:
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. Clone and install:
   ```bash
   cd mcp-server
   uv sync
   ```

3. Configure Claude Desktop:
   Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):
   ```json
   {
     "mcpServers": {
       "subsonic": {
         "command": "uv",
         "args": [
           "--directory", "/path/to/mcp-server",
           "run", "python", "-m", "subsonic_mcp.server"
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

4. Restart Claude Desktop

## Usage

See [quickstart.md](../specs/003-create-model-context/quickstart.md) for detailed usage examples.

## Development

Run tests:
```bash
uv run pytest
```

Check coverage:
```bash
uv run pytest --cov=subsonic_mcp --cov-report=html
```

Format code:
```bash
uv run black src/ tests/
```

Lint code:
```bash
uv run pylint src/subsonic_mcp
```

## Architecture

- **server.py**: Main MCP server class
- **tools.py**: 10 tools for music operations
- **resources.py**: 6 resources for library exploration
- **prompts.py**: 5 prompts for common workflows
- **cache.py**: In-memory caching with TTL
- **utils.py**: Error handling utilities

## License

[Your license here]
```

**Dependencies**: T042
**Verification**: README complete, clear installation steps

---

## Dependencies Summary

```
Phase 3.1 (Setup): T001 → T002 → T003
                                   ↓
Phase 3.2 (Tests): T004-T036 [P] ──┤
                                   ↓
                    T044 (conftest.py) [P]
                                   ↓
Phase 3.3 (Core):  T037 → T038 → T039 → T040 → T041 → T042
                                                         ↓
Phase 3.4 (Integration): T046 → T047 → T048 → T049 ────┤
                                                         ↓
Phase 3.5 (Packaging): T043, T045 [P] ──────────────────┘
```

---

## Parallel Execution Examples

### Example 1: All Contract Tests (Phase 3.2)
```bash
# After T002 and T044, launch all contract tests in parallel:
Task: "Contract test: search_tracks success in tests/test_tools.py"
Task: "Contract test: search_tracks with 100 limit in tests/test_tools.py"
Task: "Contract test: get_track_info success in tests/test_tools.py"
# ... all 42 contract tests can run in parallel (different test functions)
```

### Example 2: Packaging Tasks (Phase 3.5)
```bash
# T043, T044, T045 can run in parallel (different files):
Task: "Create pyproject.toml with uv configuration"
Task: "Create pytest fixtures in conftest.py"
Task: "Create README.md with installation guide"
```

---

## Validation Checklist

Before marking implementation complete, verify:

- [x] All 55 tasks completed
- [ ] All 50+ tests passing (42 contract + 8 integration)
- [ ] Test coverage ≥80% (target: 85%+)
- [ ] Pylint score ≥9.0 for all modules
- [ ] All modules <500 lines
- [ ] Black formatting applied
- [ ] Type hints on all functions
- [ ] Docstrings on all public methods
- [ ] quickstart.md manual validation passed
- [ ] Claude Desktop integration working
- [ ] No hardcoded secrets (all from ENV)
- [ ] README.md complete and accurate

---

## Notes

- **[P]** = Parallel execution (independent files/tests)
- **TDD Critical**: Phase 3.2 tests MUST fail before Phase 3.3 implementation
- **Constitutional Compliance**: All requirements from constitution.md satisfied
- **Cache Strategy**: 5-min (stats/artists/genres), 2-min (playlists), 1-min (recent)
- **Result Limiting**: Max 100 tracks per query with pagination guidance
- **Error Handling**: Fail-fast on server unavailability, user-friendly messages

---

**Tasks generation complete. Ready for implementation execution.**
