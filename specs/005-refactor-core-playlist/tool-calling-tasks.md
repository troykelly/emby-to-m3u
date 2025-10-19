# Tasks: Enable LLM Tool Calling for Dynamic Music Discovery

**Feature**: Phase 5.2 - Replace Static Track Lists with Dynamic Tool-Based Discovery
**Created**: 2025-10-07
**Parent Feature**: 005-refactor-core-playlist

## Context

**Current Problem**: The system fetches 10,000 tracks upfront and passes them in the LLM prompt. This:
- Wastes tokens on static data
- Prevents LLM from discovering new music
- Can't adapt to daily library changes
- Doesn't leverage the "art" of music curation

**Solution**: Implement OpenAI function calling to let the LLM dynamically query the Subsonic library using tools:
- `search_tracks`: Search for specific songs/artists
- `search_tracks_by_genre`: Find tracks in genres
- `get_available_genres`: Discover available genres
- `get_newly_added_tracks`: Find recent additions
- `browse_artists`: Explore available artists
- `get_artist_tracks`: Get songs by specific artist

**Expected Behavior After Refactor**:
```python
# Before: Static pre-fetch
available_tracks = await subsonic.search_tracks_async("", limit=10000)
playlist = await generate_playlist(spec, available_tracks)

# After: Dynamic discovery
playlist = await generate_playlist(spec, subsonic_client)
# LLM internally calls:
# 1. get_available_genres() -> ["Rock", "Pop", "Electronic"]
# 2. search_tracks_by_genre(["Rock"], limit=50)
# 3. get_newly_added_tracks(limit=20)
# 4. search_tracks("australian artists", limit=30)
# 5. Selects best tracks from tool results
```

---

## Phase 5.2.1: Core Tool Infrastructure (Prerequisites)

### T094 [P] Create SubsonicTools wrapper with tool definitions
**File**: `/workspaces/emby-to-m3u/src/ai_playlist/subsonic_tools.py` ✅ **COMPLETED**
**Status**: COMPLETE - File already created with 6 tool definitions
**Description**:
- ✅ Define OpenAI function calling schemas for 6 Subsonic tools
- ✅ Implement `execute_tool()` method to dispatch tool calls
- ✅ Wrap SubsonicClient methods with proper error handling
- ✅ Return structured JSON results for LLM consumption

**Success Criteria**:
- ✅ Tool definitions follow OpenAI function calling schema
- ✅ All 6 tools implemented: search_tracks, search_tracks_by_genre, get_available_genres, get_newly_added_tracks, browse_artists, get_artist_tracks
- ✅ execute_tool() method handles all tool names
- ✅ Returns JSON-serializable results

**Estimated Time**: Complete (already done)

---

### T095 Update OpenAIClient to support tool calling with execution loop
**File**: `/workspaces/emby-to-m3u/src/ai_playlist/openai_client.py`
**Status**: PENDING - Major changes required
**Description**:
Refactor `OpenAIClient.call_llm()` to implement proper OpenAI function calling:

1. **Add `subsonic_tools` parameter** to `call_llm()`:
   ```python
   async def call_llm(
       self,
       request: LLMTrackSelectionRequest,
       subsonic_tools: SubsonicTools
   ) -> LLMTrackSelectionResponse:
   ```

2. **Pass tools to OpenAI API**:
   ```python
   completion_kwargs = {
       "model": self.model,
       "messages": messages,
       "tools": subsonic_tools.get_tool_definitions(),
       "tool_choice": "auto"  # Let LLM decide when to use tools
   }
   ```

3. **Implement tool execution loop** (multi-turn conversation):
   ```python
   import json

   response = await self.client.chat.completions.create(**completion_kwargs)
   message = response.choices[0].message

   # Continue conversation while LLM wants to call tools
   while message.tool_calls:
       # Add assistant message with tool calls
       messages.append({
           "role": "assistant",
           "content": message.content,
           "tool_calls": message.tool_calls
       })

       # Execute each tool call
       for tool_call in message.tool_calls:
           tool_name = tool_call.function.name
           arguments = json.loads(tool_call.function.arguments)

           logger.info(f"Executing tool: {tool_name} with args: {arguments}")

           try:
               result = await subsonic_tools.execute_tool(tool_name, arguments)
               result_str = json.dumps(result)
           except Exception as e:
               logger.error(f"Tool execution failed: {e}")
               result_str = json.dumps({"error": str(e)})

           # Add tool result message
           messages.append({
               "role": "tool",
               "tool_call_id": tool_call.id,
               "content": result_str
           })

       # Continue conversation with tool results
       response = await self.client.chat.completions.create(**completion_kwargs)
       message = response.choices[0].message

   # Final message has the track selection
   ```

4. **Track tool usage in response**:
   - Count number of tool calls made
   - Log which tools were used
   - Include in DecisionLogger output

5. **Update cost calculation**:
   - Account for multi-turn conversation tokens
   - Track cumulative usage across all API calls

**Success Criteria**:
- ✅ Tools parameter added to API call
- ✅ Tool execution loop handles multi-turn conversations
- ✅ Tool results properly formatted for LLM
- ✅ Cost tracking includes all conversation turns
- ✅ Logs show tool usage (names, arguments, results)

**Estimated Time**: 2-3 hours

---

### T096 Update OpenAIClient.generate_playlist() to use SubsonicTools
**File**: `/workspaces/emby-to-m3u/src/ai_playlist/openai_client.py`
**Status**: PENDING - Signature changes required
**Description**:
Refactor the high-level orchestration method to pass SubsonicTools instead of available_tracks:

1. **Change method signature**:
   ```python
   # BEFORE:
   async def generate_playlist(
       self,
       spec: PlaylistSpec,
       available_tracks: List[SubsonicTrack],
       used_track_ids: Optional[Set[str]] = None
   ) -> Playlist:

   # AFTER:
   async def generate_playlist(
       self,
       spec: PlaylistSpec,
       subsonic_client: SubsonicClient,
       used_track_ids: Optional[Set[str]] = None
   ) -> Playlist:
   ```

2. **Create SubsonicTools instance**:
   ```python
   from .subsonic_tools import SubsonicTools

   subsonic_tools = SubsonicTools(subsonic_client)
   ```

3. **Update create_selection_request() call**:
   ```python
   # Remove available_tracks parameter
   request = self.create_selection_request(spec)
   ```

4. **Pass tools to call_llm()**:
   ```python
   llm_response = await self.call_llm(request, subsonic_tools)
   ```

5. **Remove available_tracks from prompt**:
   - Delete `_build_prompt_template()` code that includes track listings
   - Keep only the constraint specifications
   - Add tool usage guidance

**Success Criteria**:
- ✅ Method signature updated (no available_tracks)
- ✅ SubsonicTools instance created from client
- ✅ Tools passed to call_llm()
- ✅ Prompt no longer includes static track list

**Estimated Time**: 1 hour

---

### T097 Update LLM prompts to encourage tool-based discovery
**File**: `/workspaces/emby-to-m3u/src/ai_playlist/openai_client.py` (method `_build_prompt_template`)
**Status**: PENDING - Prompt rewrite needed
**Description**:
Rewrite the system and user prompts to guide the LLM to actively explore the library:

**New System Prompt**:
```python
system_prompt = """You are an expert radio playlist curator with access to a dynamic music library.

IMPORTANT: You must actively DISCOVER what tracks are available by using the provided tools. The library changes daily, so you cannot rely on pre-existing knowledge.

Your tools:
- search_tracks(query, limit): Search for specific songs, artists, or albums
- search_tracks_by_genre(genres, limit): Find tracks in specific genres
- get_available_genres(): Discover all available genres in the library
- get_newly_added_tracks(limit, genre): Find recently added music (may include songs outside your training data)
- browse_artists(genre, limit): Explore available artists
- get_artist_tracks(artist_name, limit): Get songs by a specific artist

Strategy for playlist generation:
1. Understand the requirements (genre mix, era distribution, BPM range, Australian content)
2. Explore what's available using get_available_genres() and browse_artists()
3. Search for tracks that match criteria using search_tracks_by_genre()
4. Consider newly added tracks with get_newly_added_tracks()
5. Select tracks that satisfy all constraints AND create good energy flow
6. Avoid repeating track IDs from the excluded list

Remember: The library is LIVE. Always discover tracks using tools before selecting."""
```

**New User Prompt Template**:
```python
def _build_prompt_template(self, spec: PlaylistSpec) -> str:
    prompt = f"""Generate a playlist with the following requirements:

**Playlist Name**: {spec.name}
**Target Tracks**: {spec.target_track_count_max} songs
**Duration**: {spec.target_duration_minutes} minutes

**Constraints**:
- BPM Range: {bpm_range_str}
- Genre Mix: {genre_mix_str}
- Era Distribution: {era_dist_str}
- Australian Content: {australian_str} minimum

**Excluded Track IDs** (do NOT select these):
{excluded_ids_list}

**Your Task**:
1. Use the provided tools to discover what tracks are available
2. Search for tracks matching the genre and era requirements
3. Verify tracks meet BPM and Australian content requirements
4. Select {spec.target_track_count_max} tracks that satisfy ALL constraints
5. Ensure good energy flow (gradual BPM changes, genre transitions)

**Output Format**:
For each selected track, provide:
Track ID: <id>
Position: <number>
Title: "<title>" by "<artist>"
BPM: <bpm>
Genre: <genre>
Year: <year>
Reason: <brief explanation of why this track was selected>

Begin by exploring the library with your tools."""

    return prompt
```

**Success Criteria**:
- ✅ System prompt emphasizes active discovery
- ✅ Lists all 6 available tools with descriptions
- ✅ User prompt provides clear strategy
- ✅ Removed static track listings
- ✅ Encourages tool usage before selection

**Estimated Time**: 1 hour

---

## Phase 5.2.2: Integration Layer Updates

### T098 Remove available_tracks from BatchPlaylistGenerator
**File**: `/workspaces/emby-to-m3u/src/ai_playlist/batch_executor.py`
**Status**: PENDING
**Description**:
Update `BatchPlaylistGenerator.generate_batch()` to not require pre-fetched tracks:

1. **Update method signature**:
   ```python
   # BEFORE:
   async def generate_batch(
       self,
       dayparts: List[DaypartSpecification],
       available_tracks: List[SubsonicTrack],
       generation_date: date,
       on_progress: Optional[Callable] = None
   ) -> List[Playlist]:

   # AFTER:
   async def generate_batch(
       self,
       dayparts: List[DaypartSpecification],
       subsonic_client: SubsonicClient,
       generation_date: date,
       on_progress: Optional[Callable] = None
   ) -> List[Playlist]:
   ```

2. **Store subsonic_client as instance variable**:
   ```python
   def __init__(self, openai_api_key: str, subsonic_client: SubsonicClient, ...):
       self.subsonic_client = subsonic_client
       # ...
   ```

3. **Pass subsonic_client to generate_playlist()**:
   ```python
   # Inside generate_batch() loop:
   playlist = await ai_client.generate_playlist(
       spec,
       self.subsonic_client,  # Changed from available_tracks
       used_track_ids=used_track_ids
   )
   ```

4. **Remove track filtering logic**:
   - Delete code that filters available_tracks by used_track_ids
   - LLM will handle exclusion via prompt

**Success Criteria**:
- ✅ Method signature updated
- ✅ subsonic_client passed to generate_playlist()
- ✅ No references to available_tracks
- ✅ All tests updated

**Estimated Time**: 1 hour

---

### T099 Remove bulk track fetching from main.py
**File**: `/workspaces/emby-to-m3u/src/ai_playlist/main.py`
**Status**: PENDING
**Description**:
Remove the 10,000-track pre-fetch and update workflow to pass SubsonicClient:

1. **Delete bulk fetch code** (lines ~135-138):
   ```python
   # DELETE THIS:
   logger.info("Fetching available tracks from library...")
   available_tracks = await subsonic_client.search_tracks_async(query="", limit=10000)
   logger.info("✓ Fetched %d available tracks from Subsonic", len(available_tracks))
   ```

2. **Update BatchPlaylistGenerator initialization**:
   ```python
   batch_generator = BatchPlaylistGenerator(
       openai_api_key=config.openai_api_key,
       subsonic_client=subsonic_client,  # NEW: pass client
       total_budget=float(config.total_cost_budget),
       allocation_strategy=config.cost_allocation_strategy,
       budget_mode=config.cost_budget_mode,
       timeout_seconds=90
   )
   ```

3. **Update generate_batch() call**:
   ```python
   # BEFORE:
   playlists = await batch_generator.generate_batch(
       dayparts=dayparts,
       available_tracks=available_tracks,  # DELETE THIS
       generation_date=date.today()
   )

   # AFTER:
   playlists = await batch_generator.generate_batch(
       dayparts=dayparts,
       subsonic_client=subsonic_client,  # Pass client instead
       generation_date=date.today()
   )
   ```

4. **Update log messages**:
   - Change "Fetched X tracks" to "Connected to Subsonic (dynamic discovery enabled)"

**Success Criteria**:
- ✅ No bulk track fetching
- ✅ SubsonicClient passed to batch generator
- ✅ generate_batch() receives client, not tracks
- ✅ Logs reflect dynamic discovery model

**Estimated Time**: 30 minutes

---

## Phase 5.2.3: Testing & Validation

### T100 [P] Update integration tests for tool-based workflow
**File**: `/workspaces/emby-to-m3u/tests/integration/test_main_workflow.py`
**Status**: PENDING
**Description**:
Update all integration tests to reflect the new tool-calling architecture:

1. **Remove available_tracks from test fixtures**:
   ```python
   # DELETE:
   available_tracks = await subsonic_client.search_tracks_async(query="", limit=500)
   ```

2. **Update batch_generation_integration test**:
   ```python
   playlists = await batch_generator.generate_batch(
       dayparts=dayparts,
       subsonic_client=subsonic_client,  # Changed
       generation_date=date.today()
   )
   ```

3. **Add tool usage assertions**:
   ```python
   # Verify LLM made tool calls
   assert playlist.metadata.get("tool_calls_count", 0) > 0, "LLM did not use any tools"
   assert "search_tracks" in playlist.metadata.get("tools_used", []), "LLM did not search for tracks"
   ```

4. **Update mock responses** (if using mocks):
   - Mock SubsonicTools.execute_tool() responses
   - Provide realistic tool results

**Success Criteria**:
- ✅ All tests updated to new API
- ✅ Tests verify tool usage
- ✅ No references to available_tracks
- ✅ All tests pass

**Estimated Time**: 2 hours

---

### T101 [P] Create end-to-end test with tool call tracing
**File**: `/workspaces/emby-to-m3u/tests/integration/test_tool_calling.py` (NEW FILE)
**Status**: PENDING
**Description**:
Create comprehensive test that validates the complete tool-calling workflow:

```python
import pytest
import os
from pathlib import Path
from datetime import date

pytestmark = pytest.mark.skipif(
    not os.getenv('OPENAI_KEY'),
    reason="OPENAI_KEY not set"
)

@pytest.mark.asyncio
async def test_llm_tool_calling_workflow():
    """Test that LLM actively discovers tracks using tools."""
    from src.ai_playlist.document_parser import DocumentParser
    from src.ai_playlist.batch_executor import BatchPlaylistGenerator
    from src.ai_playlist.config import AIPlaylistConfig
    from src.subsonic.client import SubsonicClient

    # Setup
    config = AIPlaylistConfig.from_environment()
    subsonic_client = SubsonicClient(config.to_subsonic_config())

    # Parse station identity (get first 2 dayparts only)
    parser = DocumentParser()
    station_identity = parser.load_document(
        Path("/workspaces/emby-to-m3u/station-identity.md")
    )
    weekday = next(
        s for s in station_identity.programming_structures
        if s.schedule_type.value == "weekday"
    )
    dayparts = weekday.dayparts[:2]

    # Reduce track counts for faster testing
    for dp in dayparts:
        dp.target_track_count_min = 5
        dp.target_track_count_max = 10

    # Create batch generator with tool support
    batch_generator = BatchPlaylistGenerator(
        openai_api_key=config.openai_api_key,
        subsonic_client=subsonic_client,  # Pass client
        total_budget=2.0,
        allocation_strategy="dynamic",
        budget_mode="suggested",
        timeout_seconds=120  # Longer timeout for tool calls
    )

    # Generate playlists
    playlists = await batch_generator.generate_batch(
        dayparts=dayparts,
        subsonic_client=subsonic_client,
        generation_date=date.today()
    )

    # Assertions
    assert len(playlists) == 2, "Should generate 2 playlists"

    for playlist in playlists:
        # Verify tracks were selected
        assert len(playlist.tracks) > 0, f"Playlist {playlist.name} has no tracks"

        # Verify tool usage metadata
        metadata = playlist.metadata if hasattr(playlist, 'metadata') else {}
        tool_calls_count = metadata.get("tool_calls_count", 0)
        tools_used = metadata.get("tools_used", [])

        assert tool_calls_count > 0, (
            f"Playlist {playlist.name}: LLM made no tool calls "
            f"(should have used Subsonic tools to discover tracks)"
        )

        print(f"\n📊 Playlist: {playlist.name}")
        print(f"   Tracks selected: {len(playlist.tracks)}")
        print(f"   Tool calls made: {tool_calls_count}")
        print(f"   Tools used: {', '.join(tools_used)}")
        print(f"   Cost: ${playlist.cost_actual}")

        # Verify expected tools were used
        expected_tools = ["search_tracks", "get_available_genres"]
        for expected_tool in expected_tools:
            assert expected_tool in tools_used, (
                f"Playlist {playlist.name}: Expected LLM to use {expected_tool}, "
                f"but tools used were: {tools_used}"
            )

    print(f"\n✅ Tool calling workflow test PASSED")
    print(f"   Total cost: ${sum(float(p.cost_actual) for p in playlists):.4f}")
```

**Success Criteria**:
- ✅ Test creates playlists using only SubsonicClient
- ✅ Verifies LLM made tool calls (tool_calls_count > 0)
- ✅ Checks specific tools were used (search_tracks, get_available_genres)
- ✅ Validates track selection succeeded
- ✅ Logs tool usage for debugging

**Estimated Time**: 2 hours

---

### T102 Manual verification with full station identity
**File**: Manual testing (no code changes)
**Status**: PENDING
**Description**:
Run complete workflow with full station identity to verify tool-based discovery:

**Test Command**:
```bash
python -m src.ai_playlist \
  --input station-identity.md \
  --output /tmp/playlists-tool-test \
  --max-cost 10.00 \
  --dry-run
```

**Verification Checklist**:
- [ ] No errors about "available_tracks not found"
- [ ] Logs show "Connected to Subsonic (dynamic discovery enabled)"
- [ ] Logs show tool calls being made: "Executing tool: search_tracks with args: ..."
- [ ] Multiple tool calls per playlist (3-10 expected)
- [ ] Playlists generated successfully (6 weekday dayparts)
- [ ] M3U files created with tracks
- [ ] JSON metadata includes tool usage statistics
- [ ] Total cost within budget
- [ ] Generation time reasonable (<5 min per playlist)

**Expected Log Output**:
```
INFO - Connected to Subsonic (dynamic discovery enabled)
INFO - Step 4: Initializing batch playlist generator...
INFO - Step 5: Generating playlists for 6 dayparts...
INFO - Executing tool: get_available_genres with args: {}
INFO - Executing tool: search_tracks_by_genre with args: {'genres': ['Rock', 'Pop'], 'limit': 50}
INFO - Executing tool: get_newly_added_tracks with args: {'limit': 20}
INFO - Executing tool: search_tracks with args: {'query': 'australian', 'limit': 30}
INFO - LLM call completed: 19 tracks selected, tool_calls=4
...
```

**Success Criteria**:
- ✅ All playlists generated without errors
- ✅ Tool calls visible in logs
- ✅ Multiple tools used per playlist
- ✅ Output files created correctly
- ✅ Performance acceptable

**Estimated Time**: 1 hour

---

## Dependencies

### Sequential Flow:
1. **T094** (SubsonicTools) → Must complete first (✅ DONE)
2. **T095** (OpenAIClient.call_llm tool loop) → Depends on T094
3. **T096** (OpenAIClient.generate_playlist) → Depends on T095
4. **T097** (Prompt updates) → Can run parallel with T096 but must use same prompts
5. **T098** (BatchPlaylistGenerator) → Depends on T096
6. **T099** (main.py) → Depends on T098
7. **T100, T101** (Tests) → Depend on T095-T099 complete
8. **T102** (Manual verification) → Depends on ALL tasks complete

### Parallel Opportunities:
- ✅ T094 already complete (run first)
- T095, T097 can be worked on concurrently (different methods)
- T100, T101 can run in parallel after core refactor

---

## Parallel Execution Examples

**Phase 1 - Core Implementation (after T094)**:
```bash
# Launch T095 and T097 together:
Task("tool-calling-specialist", "Implement tool execution loop in OpenAIClient.call_llm() per T095", "coder")
Task("prompt-engineer", "Rewrite LLM prompts to encourage tool usage per T097", "coder")
```

**Phase 2 - Integration Updates (after T095, T097)**:
```bash
# Sequential (same files, dependencies):
# T096 → T098 → T099
```

**Phase 3 - Testing (after T099)**:
```bash
# Launch T100 and T101 together:
Task("test-updater", "Update existing integration tests per T100", "tester")
Task("test-creator", "Create new tool calling test per T101", "tester")
```

---

## Summary

**Total Tasks**: 9 (T094-T102)
- ✅ **Complete**: 1 (T094 - SubsonicTools)
- **Pending**: 8 (T095-T102)

**Estimated Total Time**: 12-15 hours

**Critical Path**: T094 ✅ → T095 (3h) → T096 (1h) → T098 (1h) → T099 (0.5h) → T100 (2h) → T102 (1h) = ~8.5 hours minimum

**Benefits After Completion**:
1. ✅ LLM actively discovers tracks (adaptive to library changes)
2. ✅ Efficient token usage (no 10,000-track dumps)
3. ✅ Intelligent curation (explores genres, artists, new releases)
4. ✅ Scalable (works with any library size)
5. ✅ Future-proof (adapts to new music daily)

**Risk Mitigation**:
- T095 is the most complex (tool execution loop) - allocate extra time
- T100-T102 provide comprehensive validation
- Manual verification (T102) catches integration issues
