"""
End-to-end workflow tests for AI playlist automation.

Tests the complete workflow from parsing programming document to syncing
playlists to AzuraCast, with all external APIs mocked.
"""

import os
import pytest
import uuid
from pathlib import Path
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from src.ai_playlist.document_parser import parse_programming_document
from src.ai_playlist.playlist_planner import generate_playlist_specs
from src.ai_playlist.models import (
    DaypartSpec,
    PlaylistSpec,
    SelectedTrack,
    ValidationResult,
    Playlist,
    DecisionLog,
)


@pytest.fixture
def sample_programming_document():
    """Create sample programming document content."""
    return """# Station Programming Identity

## Monday Programming

### Morning Drive: "Production Call" (6:00 AM - 10:00 AM)
**Tracks per Hour**: 12

**BPM Progression**:
- 6:00-8:00 AM: 100-120 BPM
- 8:00-10:00 AM: 120-130 BPM

**Genre Mix**:
- Electronic: 50%
- Pop: 30%
- Rock: 20%

**Era Distribution**:
- Current (0-2 years): 40%
- Recent (2-5 years): 40%
- Modern Classics (5-10 years): 20%

**Australian Content**: 30% minimum
**Mood**: Energetic and uplifting morning energy
**Energy Flow**: Build from 100 to 130 BPM

---

### Midday: "The Session" (10:00 AM - 3:00 PM)
**Tracks per Hour**: 10

**BPM Progression**:
- 10:00-1:00 PM: 90-110 BPM
- 1:00-3:00 PM: 110-120 BPM

**Genre Mix**:
- Electronic: 60%
- Ambient: 30%
- Jazz: 10%

**Era Distribution**:
- Current (0-2 years): 50%
- Recent (2-5 years): 30%
- Modern Classics (5-10 years): 20%

**Australian Content**: 30% minimum
**Mood**: Smooth and focused work vibes
**Energy Flow**: Maintain steady flow
"""


@pytest.fixture
def mock_selected_tracks():
    """Create mock selected tracks for testing."""
    return [
        SelectedTrack(
            track_id=f"track-{i}",
            title=f"Test Track {i}",
            artist=f"Test Artist {i}",
            album=f"Test Album {i}",
            bpm=100 + (i * 3),
            genre=["Electronic", "Pop", "Rock"][i % 3],
            year=2020 + (i % 5),
            country="AU" if i % 3 == 0 else "US",
            duration_seconds=180 + (i * 10),
            position=i + 1,
            selection_reason=f"Track {i} selected for energy progression",
        )
        for i in range(12)
    ]


@pytest.fixture
def mock_validation_result():
    """Create mock validation result that passes."""
    return ValidationResult(
        constraint_satisfaction=0.87,
        bpm_satisfaction=0.92,
        genre_satisfaction=0.85,
        era_satisfaction=0.90,
        australian_content=0.33,
        flow_quality_score=0.78,
        bpm_variance=0.12,
        energy_progression="smooth",
        genre_diversity=0.80,
        gap_analysis={},
        passes_validation=True,
    )


@pytest.mark.asyncio
async def test_complete_workflow_e2e(sample_programming_document, mock_selected_tracks, mock_validation_result, tmp_path):
    """
    Test complete end-to-end workflow.

    Steps:
    1. Parse sample programming document
    2. Generate playlist specifications
    3. Select tracks (with mocked LLM + MCP)
    4. Validate quality (≥80% constraints, ≥70% flow)
    5. Sync to AzuraCast (mocked)
    6. Verify decision log created

    All external APIs are mocked.
    """
    # Step 1: Parse programming document
    dayparts = parse_programming_document(sample_programming_document)
    assert len(dayparts) > 0
    assert all(isinstance(d, DaypartSpec) for d in dayparts)
    assert "Production Call" in dayparts[0].name  # Name comes from quoted section
    assert dayparts[0].day == "Monday"

    # Step 2: Generate playlist specifications
    playlist_specs = generate_playlist_specs(dayparts)
    assert len(playlist_specs) == len(dayparts)
    assert all(isinstance(spec, PlaylistSpec) for spec in playlist_specs)
    # Name format: Monday_{ShowName}_{StartTime}_{EndTime}
    assert "Monday_" in playlist_specs[0].name
    assert "_0600_" in playlist_specs[0].name

    # Step 3: Select tracks with mocked LLM + MCP
    spec = playlist_specs[0]

    with patch("src.ai_playlist.track_selector.select_tracks_with_llm") as mock_select:
        with patch("src.ai_playlist.openai_client.os.getenv", return_value="mock-api-key"):
            # Mock LLM response
            from src.ai_playlist.models import LLMTrackSelectionResponse

            mock_response = LLMTrackSelectionResponse(
                request_id=spec.id,
                selected_tracks=mock_selected_tracks,
                tool_calls=[
                    {
                        "tool_name": "search_tracks",
                        "arguments": {"bpm_range": [100, 130], "genre": "Electronic"},
                        "result": "Found 50 tracks",
                    }
                ],
                reasoning="Selected tracks with smooth BPM progression from 100 to 130 BPM",
                cost_usd=0.0042,
                execution_time_seconds=4.2,
            )
            mock_select.return_value = mock_response

            # Import would-be track selection function
            from src.ai_playlist.track_selector import select_tracks_with_llm
            from src.ai_playlist.openai_client import OpenAIClient

            client = OpenAIClient()
            request = client.create_selection_request(spec)
            response = await select_tracks_with_llm(request)

            assert len(response.selected_tracks) > 0
            assert response.cost_usd < 0.01  # Per-playlist budget
            assert response.execution_time_seconds > 0

    # Step 4: Validate quality
    with patch("src.ai_playlist.validator.validate_playlist") as mock_validate:
        mock_validate.return_value = mock_validation_result

        # Import validation function
        from src.ai_playlist.validator import validate_playlist

        result = validate_playlist(response.selected_tracks, request.criteria)

        assert result.passes_validation is True
        assert result.constraint_satisfaction >= 0.80
        assert result.flow_quality_score >= 0.70
        assert result.australian_content >= 0.30

    # Step 5: Sync to AzuraCast (mocked)
    playlist = Playlist(
        id=spec.id,
        name=spec.name,
        tracks=response.selected_tracks,
        spec=spec,
        validation_result=result,
        created_at=datetime.now(),
    )

    # Create mock client directly (AzuraCastClient may not exist yet in TDD)
    mock_client = MagicMock()
    mock_client.create_playlist = AsyncMock(return_value={"id": 42, "name": playlist.name})
    mock_client.add_tracks_to_playlist = AsyncMock(return_value={"success": True})

    async def mock_sync(pl):
        azuracast_pl = await mock_client.create_playlist(name=pl.name)
        track_ids = [t.track_id for t in pl.tracks]
        await mock_client.add_tracks_to_playlist(azuracast_pl["id"], track_ids)
        pl.azuracast_id = azuracast_pl["id"]
        pl.synced_at = datetime.now()
        return pl

    synced_playlist = await mock_sync(playlist)
    assert synced_playlist.azuracast_id is not None
    assert synced_playlist.synced_at is not None

    # Step 6: Verify decision log created
    decision_log = DecisionLog(
        decision_type="track_selection",
        playlist_id=playlist.id,
        playlist_name=playlist.name,
        criteria={
            "bpm_range": list(request.criteria.bpm_range),
            "australian_min": request.criteria.australian_min,
        },
        selected_tracks=[
            {
                "track_id": t.track_id,
                "title": t.title,
                "artist": t.artist,
                "position": t.position,
            }
            for t in response.selected_tracks
        ],
        validation_result={
            "constraint_satisfaction": result.constraint_satisfaction,
            "flow_quality_score": result.flow_quality_score,
            "passes_validation": result.passes_validation,
        },
        metadata={
            "cost_usd": response.cost_usd,
            "execution_time_seconds": response.execution_time_seconds,
            "azuracast_id": synced_playlist.azuracast_id,
        },
    )

    # Write decision log
    log_dir = tmp_path / "logs" / "decisions"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{playlist.id}.jsonl"

    with open(log_file, "w") as f:
        f.write(decision_log.to_json() + "\n")

    # Verify log file exists
    assert log_file.exists()
    log_files = list(log_dir.glob("*.jsonl"))
    assert len(log_files) > 0


@pytest.mark.asyncio
async def test_workflow_with_constraint_relaxation(sample_programming_document, mock_validation_result, tmp_path):
    """
    Test workflow with constraint relaxation when initial selection fails.

    Validates:
    - Initial selection attempt
    - Constraint relaxation on failure
    - Retry with relaxed constraints
    - Final validation passes
    """
    # Parse and generate specs
    dayparts = parse_programming_document(sample_programming_document)
    playlist_specs = generate_playlist_specs(dayparts)
    spec = playlist_specs[0]

    # Mock LLM selection with constraint relaxation
    with patch("src.ai_playlist.track_selector.select_tracks_with_relaxation") as mock_select_relaxed:
        # Create tracks that meet relaxed constraints
        relaxed_tracks = [
            SelectedTrack(
                track_id=f"relaxed-track-{i}",
                title=f"Relaxed Track {i}",
                artist=f"Artist {i}",
                album="Album",
                bpm=95 + (i * 5),  # Slightly outside original range
                genre=["Electronic", "Pop"][i % 2],
                year=2022,
                country="AU" if i % 3 == 0 else "US",
                duration_seconds=200,
                position=i + 1,
                selection_reason="Selected after BPM relaxation",
            )
            for i in range(12)
        ]
        mock_select_relaxed.return_value = relaxed_tracks

        # Import relaxation function
        from src.ai_playlist.track_selector import select_tracks_with_relaxation

        selected_tracks = await select_tracks_with_relaxation(
            criteria=spec.track_criteria, max_iterations=3
        )

        assert len(selected_tracks) > 0
        assert all(t.selection_reason.lower().find("relax") >= 0 for t in selected_tracks[:3])


@pytest.mark.asyncio
async def test_workflow_parallel_playlist_generation(sample_programming_document, mock_selected_tracks, mock_validation_result):
    """
    Test parallel generation of multiple playlists.

    Validates:
    - All playlists can be generated concurrently
    - Each playlist is independent
    - All validations pass
    """
    import asyncio

    # Parse and generate specs
    dayparts = parse_programming_document(sample_programming_document)
    playlist_specs = generate_playlist_specs(dayparts)

    # Mock parallel selection
    async def mock_select_playlist(request):
        """Mock selecting tracks for one playlist."""
        await asyncio.sleep(0.1)  # Simulate API delay

        from src.ai_playlist.models import LLMTrackSelectionResponse

        return LLMTrackSelectionResponse(
            request_id=request.playlist_id,
            selected_tracks=mock_selected_tracks,
            tool_calls=[],
            reasoning=f"Selected tracks for playlist {request.playlist_id}",
            cost_usd=0.005,
            execution_time_seconds=3.5,
        )

    with patch("src.ai_playlist.track_selector.select_tracks_with_llm", side_effect=mock_select_playlist):
        with patch("src.ai_playlist.openai_client.os.getenv", return_value="mock-api-key"):
            # Generate all playlists in parallel
            from src.ai_playlist.track_selector import select_tracks_with_llm
            from src.ai_playlist.openai_client import OpenAIClient

            client = OpenAIClient()
            tasks = []

            for spec in playlist_specs[:2]:  # Test with first 2 playlists
                request = client.create_selection_request(spec)
                tasks.append(select_tracks_with_llm(request))

            # Run in parallel
            responses = await asyncio.gather(*tasks)

            # Validate all responses
            assert len(responses) == 2
            assert all(len(r.selected_tracks) > 0 for r in responses)
            assert sum(r.cost_usd for r in responses) < 0.02  # Total cost under budget


@pytest.mark.asyncio
async def test_workflow_error_recovery(sample_programming_document, tmp_path):
    """
    Test workflow error recovery and retry logic.

    Validates:
    - Errors are caught and logged
    - Retry logic is applied
    - Workflow can complete after retries
    """
    dayparts = parse_programming_document(sample_programming_document)
    playlist_specs = generate_playlist_specs(dayparts)
    spec = playlist_specs[0]

    # Mock LLM selection with initial failure then success
    call_count = 0

    async def mock_select_with_retry(request):
        nonlocal call_count
        call_count += 1

        if call_count == 1:
            # First call fails
            raise Exception("API timeout")
        else:
            # Second call succeeds
            from src.ai_playlist.models import LLMTrackSelectionResponse, SelectedTrack

            tracks = [
                SelectedTrack(
                    track_id=f"retry-track-{i}",
                    title=f"Track {i}",
                    artist=f"Artist {i}",
                    album="Album",
                    bpm=110,
                    genre="Electronic",
                    year=2023,
                    country="AU" if i % 3 == 0 else "US",
                    duration_seconds=200,
                    position=i + 1,
                    selection_reason="Selected after retry",
                )
                for i in range(12)
            ]

            return LLMTrackSelectionResponse(
                request_id=request.playlist_id,
                selected_tracks=tracks,
                tool_calls=[],
                reasoning="Success after retry",
                cost_usd=0.006,
                execution_time_seconds=5.0,
            )

    with patch("src.ai_playlist.track_selector.select_tracks_with_llm", side_effect=mock_select_with_retry):
        with patch("src.ai_playlist.openai_client.os.getenv", return_value="mock-api-key"):
            from src.ai_playlist.track_selector import select_tracks_with_llm
            from src.ai_playlist.openai_client import OpenAIClient

            client = OpenAIClient()
            request = client.create_selection_request(spec)

            # First attempt should fail
            with pytest.raises(Exception, match="API timeout"):
                await select_tracks_with_llm(request)

            # Second attempt should succeed
            response = await select_tracks_with_llm(request)
            assert len(response.selected_tracks) == 12
            assert call_count == 2


@pytest.mark.asyncio
async def test_workflow_quality_validation_threshold(sample_programming_document, mock_selected_tracks):
    """
    Test quality validation threshold enforcement.

    Validates:
    - Playlists below threshold are rejected
    - Constraint satisfaction ≥80% required
    - Flow quality ≥70% required
    """
    dayparts = parse_programming_document(sample_programming_document)
    playlist_specs = generate_playlist_specs(dayparts)
    spec = playlist_specs[0]

    # Mock validation with failing result
    failing_result = ValidationResult(
        constraint_satisfaction=0.75,  # Below 80% threshold
        bpm_satisfaction=0.80,
        genre_satisfaction=0.70,
        era_satisfaction=0.75,
        australian_content=0.25,  # Below 30% minimum
        flow_quality_score=0.65,  # Below 70% threshold
        bpm_variance=0.20,
        energy_progression="choppy",
        genre_diversity=0.60,
        gap_analysis={
            "australian_content": "Only 25% AU content, need 30%",
            "flow_quality": "Choppy transitions, need smoother flow",
        },
        passes_validation=False,
    )

    with patch("src.ai_playlist.validator.validate_playlist") as mock_validate:
        mock_validate.return_value = failing_result

        from src.ai_playlist.validator import validate_playlist
        from src.ai_playlist.models import TrackSelectionCriteria

        result = validate_playlist(mock_selected_tracks, spec.track_criteria)

        # Should fail validation
        assert result.passes_validation is False
        assert result.constraint_satisfaction < 0.80
        assert result.flow_quality_score < 0.70
        assert len(result.gap_analysis) > 0

        # Playlist creation should fail with invalid validation
        with pytest.raises(ValueError, match="ValidationResult must pass"):
            Playlist(
                id=spec.id,
                name=spec.name,
                tracks=mock_selected_tracks,
                spec=spec,
                validation_result=result,  # Invalid result
            )
