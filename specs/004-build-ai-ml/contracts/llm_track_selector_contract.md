# LLM Track Selector Contract

## select_tracks_with_llm()

**Purpose**: Use OpenAI LLM with Subsonic MCP tools to select tracks matching criteria

### Input
```python
async def select_tracks_with_llm(
    request: LLMTrackSelectionRequest
) -> LLMTrackSelectionResponse
```

**Parameters**:
- `request`: LLMTrackSelectionRequest - Selection request with criteria and constraints

**Preconditions**:
- OpenAI API key configured
- Subsonic MCP server accessible
- request.criteria is valid
- request.max_cost_usd > 0

### Output

**Return Type**: `LLMTrackSelectionResponse`

**Success Response**:
```python
LLMTrackSelectionResponse(
    request_id="550e8400-e29b-41d4-a716-446655440000",
    selected_tracks=[
        SelectedTrack(
            track_id="12345",
            title="Sunset Boulevard",
            artist="The Dreamers",
            album="Night Vibes",
            bpm=105,
            genre="Alternative",
            year=2023,
            country="AU",
            duration_seconds=245,
            position=1,
            selection_reason="Opens with moderate BPM (105), Australian artist, current era, fits alternative genre requirement"
        ),
        SelectedTrack(
            track_id="12346",
            title="Electric Dreams",
            artist="Synth Masters",
            album="Digital Waves",
            bpm=115,
            genre="Electronic",
            year=2022,
            country="AU",
            duration_seconds=280,
            position=2,
            selection_reason="Builds energy with increased BPM (115), Australian electronic artist, smooth transition from track 1"
        ),
        # ... more tracks
    ],
    tool_calls=[
        {
            "tool_name": "search_tracks",
            "arguments": {"genre": "Alternative", "bpm_range": "90-115", "country": "AU"},
            "result": {"tracks": [...], "count": 50}
        },
        {
            "tool_name": "get_genres",
            "arguments": {},
            "result": {"genres": ["Alternative", "Electronic", ...]}
        }
    ],
    reasoning="Selected 12 tracks following energy progression: moderate start (90-105 BPM) transitioning to energetic peak (110-135 BPM), then gentle wind-down (100-120 BPM). Genre mix achieved: Alternative 25%, Electronic 20%, maintaining 33% Australian content throughout. Era distribution: 40% current releases, smooth tempo transitions with average ±8 BPM variance.",
    cost_usd=0.003,
    execution_time_seconds=4.2,
    created_at=datetime(2025, 10, 6, 10, 30, 0)
)
```

**Error Cases**:
- `APIError`: OpenAI API failure or timeout
- `CostExceededError`: Estimated cost exceeds max_cost_usd
- `MCPToolError`: Subsonic MCP tool unavailable or error
- `ValidationError`: Selected tracks fail criteria validation

### Contract Tests

**Test 1: Successful Track Selection**
```python
@pytest.mark.asyncio
async def test_select_tracks_success():
    request = LLMTrackSelectionRequest(
        playlist_id="550e8400-e29b-41d4-a716-446655440000",
        criteria=TrackSelectionCriteria(
            bpm_range=(90, 135),
            genre_mix={"Alternative": (0.20, 0.30), "Electronic": (0.15, 0.25)},
            era_distribution={"Current": (0.35, 0.45)},
            australian_min=0.30,
            energy_flow="moderate start, build to peak, wind down"
        ),
        target_track_count=12,
        mcp_tools=["search_tracks", "get_genres"],
        max_cost_usd=0.01
    )

    response = await select_tracks_with_llm(request)

    assert response.request_id == request.playlist_id
    assert len(response.selected_tracks) == 12
    assert response.cost_usd <= request.max_cost_usd
    assert response.execution_time_seconds > 0
    assert len(response.tool_calls) > 0
    assert response.reasoning != ""

    # Verify track ordering
    for i, track in enumerate(response.selected_tracks):
        assert track.position == i + 1
```

**Test 2: Cost Exceeded**
```python
@pytest.mark.asyncio
async def test_cost_exceeded():
    request = LLMTrackSelectionRequest(
        playlist_id="550e8400-e29b-41d4-a716-446655440000",
        criteria=valid_criteria,
        target_track_count=100,  # Large request
        max_cost_usd=0.001  # Very low limit
    )

    with pytest.raises(CostExceededError):
        await select_tracks_with_llm(request)
```

**Test 3: MCP Tool Unavailable**
```python
@pytest.mark.asyncio
async def test_mcp_tool_error(mock_mcp_unavailable):
    request = LLMTrackSelectionRequest(
        playlist_id="550e8400-e29b-41d4-a716-446655440000",
        criteria=valid_criteria,
        mcp_tools=["search_tracks"]
    )

    with pytest.raises(MCPToolError, match="Subsonic MCP server unavailable"):
        await select_tracks_with_llm(request)
```

**Test 4: Retry on Transient Failure**
```python
@pytest.mark.asyncio
async def test_retry_on_transient_failure(mock_openai_transient_error):
    request = LLMTrackSelectionRequest(
        playlist_id="550e8400-e29b-41d4-a716-446655440000",
        criteria=valid_criteria
    )

    # Should retry 3 times with exponential backoff
    response = await select_tracks_with_llm(request)

    assert mock_openai_transient_error.call_count == 3  # 1 initial + 2 retries
    assert response is not None  # Eventually succeeds
```

### Prompt Template

```
Select tracks for {playlist_name} ({daypart}) matching these criteria:

**BPM Requirements:**
- Range: {bpm_min}-{bpm_max} BPM
- Progression: {energy_flow}

**Genre Mix:**
{genre_requirements}

**Era Distribution:**
{era_requirements}

**Australian Content:**
- Minimum: {australian_min}% of tracks MUST be from Australian artists

**Target:**
- {track_count} tracks
- Ordered for smooth energy flow and tempo transitions

**Instructions:**
1. Use search_tracks MCP tool to find candidates matching BPM and genre
2. Use get_genres to verify available genres
3. Use search_similar to find tracks with compatible musical characteristics
4. Ensure Australian content minimum is met
5. Order tracks for optimal energy progression and tempo transitions
6. Provide reasoning for each selection

**Output Format:**
Return a list of {track_count} tracks with: track_id, title, artist, album, bpm, genre, year, country, duration_seconds, selection_reason
```

### Implementation Notes

- Use OpenAI Responses API with HostedMCPTool
- Model: gpt-5 for enhanced performance
- Implement token usage tracking for cost estimation
- Apply 3-retry exponential backoff for API errors
- Validate all selected tracks meet minimum criteria
- Log all LLM interactions to DecisionLog
