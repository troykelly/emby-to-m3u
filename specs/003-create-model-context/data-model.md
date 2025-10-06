# Data Model & Entities
## Subsonic MCP Server

**Feature**: 003-create-model-context
**Date**: 2025-10-06
**Phase**: Phase 1 - Design

---

## Entity Diagram

```
┌─────────────────────┐
│   MCPServer         │
│ ─────────────────── │
│ - subsonic_client   │ ───┐
│ - tool_registry     │    │
│ - resource_registry │    │  Wraps (no duplication)
│ - prompt_registry   │    │
│ - cache_manager     │    │
└─────────────────────┘    │
           │               │
           │ uses          │
           ▼               │
┌─────────────────────┐    │
│  ToolRegistry       │    │
│ ─────────────────── │    │
│ - tools: dict       │    │
│ + get_all()         │    │
│ + execute()         │    │
└─────────────────────┘    │
           │               │
┌─────────────────────┐    │
│ ResourceRegistry    │    │
│ ─────────────────── │    │
│ - resources: dict   │    │
│ + get_all()         │    │
│ + read()            │    │
└─────────────────────┘    │
           │               │
┌─────────────────────┐    │
│  PromptRegistry     │    │
│ ─────────────────── │    │
│ - prompts: dict     │    │
│ + get_all()         │    │
│ + get()             │    │
└─────────────────────┘    │
           │               │
           │ all use       │
           ▼               ▼
┌──────────────────────────────┐
│  SubsonicClient (existing)   │
│ ──────────────────────────── │
│ - config: SubsonicConfig     │
│ - client: httpx.Client       │
│ + search()                   │
│ + get_artists()              │
│ + get_albums()               │
│ + get_genres()               │
│ + get_track()                │
│ + stream()                   │
└──────────────────────────────┘
           │
           │ uses
           ▼
┌──────────────────────────────┐
│  CacheManager               │
│ ──────────────────────────── │
│ - cache: Dict[str, Entry]   │
│ - response_times: deque     │
│ - default_ttl: int (300s)   │
│ + get()                     │
│ + set()                     │
│ + should_throttle()         │
└──────────────────────────────┘
```

---

## 1. MCP Server Entity

### MCPServer (LibraryMCPServer)

**Purpose**: Main server class that initializes MCP protocol handlers and manages component lifecycle.

**Attributes**:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `server` | `mcp.server.Server` | Yes | MCP SDK server instance |
| `subsonic_client` | `SubsonicClient` | Yes | Injected Subsonic API client |
| `tool_registry` | `ToolRegistry` | Yes | Manages 10 MCP tools |
| `resource_registry` | `ResourceRegistry` | Yes | Manages 6 MCP resources |
| `prompt_registry` | `PromptRegistry` | Yes | Manages 5 MCP prompts |
| `cache_manager` | `CacheManager` | Yes | In-memory cache with TTL |

**Methods**:
- `__init__(config: SubsonicConfig)`: Initialize with Subsonic config
- `async run()`: Start MCP server with stdio transport
- `_register_handlers()`: Register tool/resource/prompt handlers

**Validation Rules**:
- Subsonic connection must be validated at startup
- Environment variables (SUBSONIC_URL, USER, PASSWORD) must be present
- Fail fast if authentication fails

**State Transitions**:
```
[INIT] → Validate Config → Authenticate Subsonic → [READY] → Handle Requests → [SHUTDOWN]
         ↓                 ↓
         ERROR ────────────┘
```

---

## 2. Tool Registry Entity

### ToolRegistry

**Purpose**: Manages 10 MCP tools for music library operations.

**Attributes**:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `client` | `SubsonicClient` | Yes | Injected Subsonic client |
| `tools` | `dict[str, types.Tool]` | Yes | Tool definitions (name → Tool) |

**Tool Definitions** (10 total):

1. **search_tracks**
   - Input: `query: str, limit: int (1-100, default 20)`
   - Output: List of tracks with metadata
   - Validation: Query non-empty, limit ≤100

2. **get_track_info**
   - Input: `track_id: str`
   - Output: Detailed track metadata
   - Validation: track_id non-empty

3. **get_artists**
   - Input: None
   - Output: List of all artists
   - Caching: 5-minute TTL

4. **get_artist_albums**
   - Input: `artist_id: str`
   - Output: Albums for artist
   - Validation: artist_id non-empty

5. **get_album_tracks**
   - Input: `album_id: str`
   - Output: Tracks for album
   - Validation: album_id non-empty

6. **search_similar**
   - Input: `query: str, limit: int (1-100, default 20)`
   - Output: Similar tracks by artist/genre
   - Validation: Query non-empty, limit ≤100

7. **get_genres**
   - Input: None
   - Output: List of genres with track counts
   - Caching: 5-minute TTL

8. **get_tracks_by_genre**
   - Input: `genre: str, limit: int (1-100, default 20)`
   - Output: Tracks filtered by genre
   - Validation: Genre non-empty, limit ≤100

9. **analyze_library**
   - Input: None
   - Output: Library statistics (total tracks, artists, albums, genres)
   - Caching: 5-minute TTL

10. **stream_track**
    - Input: `track_id: str`
    - Output: Streaming URL for playback
    - Validation: track_id non-empty

**Methods**:
- `get_all() → list[types.Tool]`: Return all tool definitions
- `async execute(name: str, args: dict) → list[types.TextContent]`: Execute tool by name

**Error Handling**:
- Invalid tool name → `ValueError("Unknown tool: {name}")`
- Invalid arguments → User-friendly message with correction guidance
- Subsonic errors → Mapped to user-friendly messages

---

## 3. Resource Registry Entity

### ResourceRegistry

**Purpose**: Manages 6 MCP resources for library exploration.

**Attributes**:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `client` | `SubsonicClient` | Yes | Injected Subsonic client |
| `resources` | `dict[str, types.Resource]` | Yes | Resource definitions |

**Resource Definitions** (6 total):

1. **library_stats** (`library://stats`)
   - MIME: `application/json`
   - Data: Total tracks, artists, albums, genres, library size
   - Caching: 5-minute TTL

2. **artists** (`library://artists`)
   - MIME: `application/json`
   - Data: Complete artist catalog
   - Caching: 5-minute TTL

3. **albums** (`library://albums`)
   - MIME: `application/json`
   - Data: Album collection with metadata
   - Caching: 5-minute TTL

4. **genres** (`library://genres`)
   - MIME: `application/json`
   - Data: Genre taxonomy with track counts
   - Caching: 5-minute TTL

5. **playlists** (`library://playlists`)
   - MIME: `application/json`
   - Data: User-created playlists with track details
   - Caching: 2-minute TTL (more dynamic)

6. **recent_tracks** (`library://recent`)
   - MIME: `application/json`
   - Data: Recently added or modified tracks
   - Caching: 1-minute TTL (highly dynamic)

**Methods**:
- `get_all() → list[types.Resource]`: Return all resource definitions
- `async read(uri: str) → str`: Read resource by URI

**URI Pattern**:
- Static: `library://{resource_name}`
- Template support for future: `library://playlist/{playlist_id}`

---

## 4. Prompt Registry Entity

### PromptRegistry

**Purpose**: Manages 5 predefined prompts for common music tasks.

**Attributes**:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `client` | `SubsonicClient` | Yes | Injected Subsonic client |
| `prompts` | `dict[str, types.Prompt]` | Yes | Prompt definitions |

**Prompt Definitions** (5 total):

1. **mood_playlist**
   - Arguments: `mood: str (required), duration: int (optional, minutes)`
   - Purpose: Generate mood-based playlists
   - Template: Search criteria, flow arrangement, track selection

2. **music_discovery**
   - Arguments: `favorite_artists: str (required), genres: str (optional)`
   - Purpose: Discover new music based on preferences
   - Template: Similar artist search, cross-genre exploration

3. **listening_analysis**
   - Arguments: `analysis_type: str (required: genre_distribution | artist_diversity | decade_breakdown)`
   - Purpose: Analyze listening patterns and library composition
   - Template: Statistical breakdown, visualization, insights

4. **smart_playlist**
   - Arguments: `criteria: str (required), max_tracks: int (optional, default 50)`
   - Purpose: Rules-based playlist generation
   - Template: Filter logic, sorting strategy, deduplication

5. **library_curation**
   - Arguments: `task: str (required: duplicates | missing_metadata | quality_issues)`
   - Purpose: Organize and clean music library
   - Template: Issue detection, fix recommendations

**Methods**:
- `get_all() → list[types.Prompt]`: Return all prompt definitions
- `async get(name: str, args: dict) → types.GetPromptResult`: Generate prompt with arguments

**Prompt Structure**:
```python
types.GetPromptResult(
    description="...",
    messages=[
        types.PromptMessage(
            role="user",
            content=types.TextContent(type="text", text="...")
        )
    ]
)
```

---

## 5. Cache Manager Entity

### CacheManager

**Purpose**: In-memory caching with TTL and dynamic throttling.

**Attributes**:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `cache` | `dict[str, CacheEntry]` | Yes | Key-value cache storage |
| `default_ttl` | `int` | Yes | Default TTL (300s = 5 min) |
| `response_times` | `deque` | Yes | Sliding window for throttling (max 100) |

**CacheEntry (Dataclass)**:
| Field | Type | Description |
|-------|------|-------------|
| `data` | `Any` | Cached data (JSON serializable) |
| `timestamp` | `datetime` | Creation timestamp |
| `ttl_seconds` | `int` | Time-to-live in seconds |

**Methods**:
- `async get(key: str) → Optional[Any]`: Retrieve from cache (None if expired/missing)
- `async set(key: str, data: Any, ttl: Optional[int])`: Store in cache with TTL
- `update_response_time(duration: float)`: Track Subsonic response time
- `should_throttle() → bool`: Check if throttling needed (avg time > 2s)
- `clear_expired()`: Remove expired entries (optional cleanup)

**Caching Strategy**:
- **Artists/Genres/Stats**: 5-minute TTL (static data)
- **Playlists**: 2-minute TTL (semi-dynamic)
- **Recent Tracks**: 1-minute TTL (highly dynamic)
- **Search Results**: 5-minute TTL, keyed by query hash

**Dynamic Throttling Logic**:
```python
def should_throttle(self) -> bool:
    if len(self.response_times) < 10:
        return False  # Need more data
    avg_time = sum(self.response_times) / len(self.response_times)
    return avg_time > 2.0  # Throttle if avg > 2s
```

**State Transitions**:
```
[EMPTY] → Set(key, data, TTL) → [CACHED] → Get(key) → [HIT]
                                     ↓
                                   Expire
                                     ↓
                                  [MISS] → Set(key, data, TTL) → [CACHED]
```

---

## 6. Existing Entities (Reused, Not Duplicated)

### SubsonicClient (from src/subsonic/client.py)

**Attributes**:
| Field | Type | Description |
|-------|------|-------------|
| `config` | `SubsonicConfig` | Server URL, credentials |
| `client` | `httpx.Client` | HTTP client with pooling |
| `opensubsonic` | `bool` | OpenSubsonic server detection |
| `rate_limit` | `Optional[int]` | Requests per second (optional) |

**Key Methods Used by MCP Server**:
- `search(query: str, artist: str, album: str, limit: int) → list[dict]`
- `get_artists() → list[dict]`
- `get_albums() → list[dict]`
- `get_genres() → list[dict]`
- `get_track(track_id: str) → dict`
- `stream(track_id: str) → str` (returns streaming URL)

---

### SubsonicConfig (from src/subsonic/models.py)

**Attributes**:
| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `url` | `str` | Yes | Valid HTTP/HTTPS URL |
| `username` | `str` | Yes | Non-empty |
| `password` | `str` | Yes | Non-empty (MD5 hashed for auth) |

**Environment Mapping**:
- `url` ← `SUBSONIC_URL`
- `username` ← `SUBSONIC_USER`
- `password` ← `SUBSONIC_PASSWORD`

---

### SubsonicTrack (from src/subsonic/models.py)

**Attributes**:
| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Unique track identifier |
| `title` | `str` | Track title |
| `artist` | `str` | Artist name |
| `album` | `str` | Album name |
| `genre` | `Optional[str]` | Genre classification |
| `year` | `Optional[int]` | Release year |
| `duration` | `Optional[int]` | Duration in seconds |
| `bitrate` | `Optional[int]` | Audio bitrate (kbps) |
| `streaming_url` | `str` | Playback URL |

**Usage in MCP Server**:
- Tool outputs format SubsonicTrack data as JSON
- Resources return lists of SubsonicTrack entities
- Prompts reference track metadata for LLM context

---

## Entity Relationships

### Composition
- `MCPServer` **has-a** `ToolRegistry`
- `MCPServer` **has-a** `ResourceRegistry`
- `MCPServer` **has-a** `PromptRegistry`
- `MCPServer` **has-a** `CacheManager`

### Dependency Injection
- `ToolRegistry` **uses** `SubsonicClient` (injected)
- `ResourceRegistry` **uses** `SubsonicClient` (injected)
- `PromptRegistry` **uses** `SubsonicClient` (injected)

### Data Flow
```
LLM Request → MCPServer → ToolRegistry → SubsonicClient → Subsonic API
                   ↓                            ↓
              CacheManager ←───────────────────┘
                   ↓
              Response with cached/fresh data
```

---

## Validation Summary

### Input Validation Rules
| Entity | Field | Rule |
|--------|-------|------|
| ToolRegistry | `query` | Non-empty string |
| ToolRegistry | `limit` | Integer 1-100 |
| ToolRegistry | `track_id` | Non-empty string |
| ToolRegistry | `artist_id` | Non-empty string |
| ToolRegistry | `album_id` | Non-empty string |
| SubsonicConfig | `url` | Valid HTTP/HTTPS URL |
| SubsonicConfig | `username` | Non-empty string |
| SubsonicConfig | `password` | Non-empty string |

### State Validation
- `MCPServer` must authenticate before accepting requests
- `CacheManager` must check TTL before returning cached data
- All tools must validate arguments before calling SubsonicClient

---

## Constitutional Alignment

### Module Size Compliance ✅
- `server.py`: ~200 lines (server class + handlers)
- `tools.py`: ~400 lines (10 tools × ~40 lines each)
- `resources.py`: ~250 lines (6 resources × ~40 lines each)
- `prompts.py`: ~300 lines (5 prompts × ~60 lines each)
- `cache.py`: ~150 lines (cache logic + throttling)
- `utils.py`: ~100 lines (error handling helpers)

**Total: ~1400 lines across 6 modules (all <500 lines) ✅**

### Data Model Best Practices ✅
- Dataclasses for structured data (CacheEntry)
- Dependency injection for testability
- Clear separation of concerns (registries, cache, client)
- No code duplication (reuse SubsonicClient)

---

**Data model complete. Ready for contract generation (Phase 1 continued).**
