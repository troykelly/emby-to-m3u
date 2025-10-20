"""
Integration test for complete AI playlist automation CLI workflow.

Tests the complete workflow from document parsing through playlist generation and file saving.
"""
import pytest
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
import asyncio
from decimal import Decimal

# Skip if no OpenAI key available
pytestmark = pytest.mark.skipif(
    not os.getenv('OPENAI_KEY'),
    reason="OPENAI_KEY not set - skipping integration test"
)


@pytest.mark.asyncio
async def test_main_workflow_end_to_end(tmp_path):
    """Test complete CLI workflow end-to-end."""
    from src.ai_playlist.main import run_automation
    from src.ai_playlist.config import get_station_identity_path

    # Setup test paths
    station_identity_path = get_station_identity_path()
    output_dir = tmp_path / "playlists"

    # Run automation with dry-run mode (skip AzuraCast sync)
    result = await run_automation(
        input_file=str(station_identity_path),
        output_dir=str(output_dir),
        max_cost_usd=5.0,  # Small budget for testing
        dry_run=True  # Skip AzuraCast sync
    )

    # Verify result structure
    assert "playlist_count" in result
    assert "success_count" in result
    assert "failed_count" in result
    assert "total_cost" in result
    assert "total_time" in result
    assert "output_files" in result
    assert "decision_log" in result

    # Verify at least some playlists were generated
    assert result["playlist_count"] > 0, "No playlists generated"
    assert result["success_count"] > 0, "No successful playlists"

    # Verify cost is within budget
    assert result["total_cost"] <= 5.0, f"Cost ${result['total_cost']:.4f} exceeded budget $5.00"

    # Verify output files were created
    assert len(result["output_files"]) > 0, "No output files created"
    for output_file in result["output_files"]:
        assert Path(output_file).exists(), f"Output file not found: {output_file}"

    # Verify decision log was created
    assert Path(result["decision_log"]).exists(), "Decision log not created"

    print(f"\n✅ Integration test PASSED:")
    print(f"   Playlists: {result['playlist_count']} total, {result['success_count']} successful")
    print(f"   Cost: ${result['total_cost']:.4f}")
    print(f"   Time: {result['total_time']:.1f}s")
    print(f"   Output files: {len(result['output_files'])}")


@pytest.mark.asyncio
async def test_document_parsing_integration():
    """Test document parsing returns correct structure."""
    from src.ai_playlist.document_parser import DocumentParser
    from src.ai_playlist.config import get_station_identity_path

    station_identity_path = get_station_identity_path()

    parser = DocumentParser()
    station_identity = parser.load_document(station_identity_path)

    # Verify station identity structure
    assert station_identity.document_path
    assert len(station_identity.programming_structures) > 0

    # Verify weekday structure exists
    weekday_structure = next(
        (s for s in station_identity.programming_structures if s.schedule_type.value == "weekday"),
        None
    )
    assert weekday_structure is not None, "No weekday programming structure found"
    assert len(weekday_structure.dayparts) > 0, "No dayparts found"

    print(f"\n✅ Document parsing integration test PASSED:")
    print(f"   Document: {station_identity.document_path}")
    print(f"   Programming structures: {len(station_identity.programming_structures)}")
    print(f"   Weekday dayparts: {len(weekday_structure.dayparts)}")


@pytest.mark.asyncio
async def test_subsonic_integration():
    """Test Subsonic connection and track fetching."""
    from src.ai_playlist.config import AIPlaylistConfig
    from src.subsonic.client import SubsonicClient

    # Load config from environment
    config = AIPlaylistConfig.from_environment()

    # Create Subsonic client
    subsonic_client = SubsonicClient(config.to_subsonic_config())

    # Test connection
    ping_result = subsonic_client.ping()
    assert ping_result, "Subsonic ping failed"

    # Test async search (used by LLM tools)
    tracks = await subsonic_client.search_tracks_async(query="", limit=100)
    assert len(tracks) > 0, "No tracks found in Subsonic library"

    # Test genres (used by LLM tools)
    genres = await subsonic_client.get_genres_async()
    assert len(genres) > 0, "No genres found in Subsonic library"

    print(f"\n✅ Subsonic integration test PASSED:")
    print(f"   Server: {config.subsonic_url}")
    print(f"   Tracks available: {len(tracks)}")
    print(f"   Genres available: {len(genres)}")


@pytest.mark.asyncio
async def test_batch_generation_integration(tmp_path):
    """Test batch playlist generation with reduced track counts."""
    from src.ai_playlist.document_parser import DocumentParser
    from src.ai_playlist.batch_executor import BatchPlaylistGenerator
    from src.ai_playlist.config import AIPlaylistConfig, get_station_identity_path
    from src.subsonic.client import SubsonicClient
    from datetime import date

    # Parse station identity
    station_identity_path = get_station_identity_path()
    parser = DocumentParser()
    station_identity = parser.load_document(station_identity_path)

    # Get weekday dayparts
    weekday_structure = next(
        (s for s in station_identity.programming_structures if s.schedule_type.value == "weekday"),
        None
    )
    dayparts = weekday_structure.dayparts[:2]  # Test with first 2 dayparts only

    # Reduce target track counts for faster testing
    for dp in dayparts:
        dp.target_track_count_min = 5
        dp.target_track_count_max = 10

    # Get Subsonic client for dynamic track discovery
    config = AIPlaylistConfig.from_environment()
    subsonic_client = SubsonicClient(config.to_subsonic_config())

    # Initialize batch generator with subsonic client
    batch_generator = BatchPlaylistGenerator(
        openai_api_key=config.openai_api_key,
        subsonic_client=subsonic_client,
        total_budget=2.0,  # Small budget for testing
        allocation_strategy="dynamic",
        budget_mode="suggested",
        timeout_seconds=90
    )

    # Generate playlists (LLM discovers tracks dynamically)
    playlists = await batch_generator.generate_batch(
        dayparts=dayparts,
        generation_date=date.today()
    )

    # Verify results
    assert len(playlists) == len(dayparts), f"Expected {len(dayparts)} playlists, got {len(playlists)}"

    for playlist in playlists:
        assert len(playlist.tracks) > 0, f"Playlist {playlist.name} has no tracks"
        assert playlist.cost_actual > 0, f"Playlist {playlist.name} has no cost recorded"
        assert playlist.validation_result is not None, f"Playlist {playlist.name} has no validation result"

    total_cost = sum(float(p.cost_actual) for p in playlists)

    print(f"\n✅ Batch generation integration test PASSED:")
    print(f"   Playlists generated: {len(playlists)}")
    print(f"   Total tracks: {sum(len(p.tracks) for p in playlists)}")
    print(f"   Total cost: ${total_cost:.4f}")


if __name__ == "__main__":
    # Run tests directly
    pytest.main([__file__, "-v", "-s"])
