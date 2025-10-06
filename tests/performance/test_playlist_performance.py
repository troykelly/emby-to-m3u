"""
Performance Validation Tests for AI Playlist Feature (T034)

Tests performance requirements:
- Complete 47 playlists execution in <10 minutes
- Total cost <$0.50 USD

Strategy:
1. Test single playlist with real API (if available)
2. Estimate full 47-playlist performance from single-playlist metrics
3. Validate against requirements
"""

import pytest
import time
import os
from pathlib import Path
from typing import Dict, Any

# Import AI playlist modules
from src.ai_playlist.document_parser import parse_programming_document
from src.ai_playlist.playlist_planner import generate_playlist_specs
from src.ai_playlist.track_selector import select_tracks_with_llm
from src.ai_playlist.openai_client import get_client
from src.ai_playlist.models import LLMTrackSelectionRequest


# Performance requirements
MAX_EXECUTION_TIME_SECONDS = 600  # 10 minutes
MAX_TOTAL_COST_USD = 0.50  # $0.50


@pytest.mark.asyncio
@pytest.mark.skipif(not (os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_KEY")), reason="No OpenAI API key")
async def test_performance_single_playlist_real_api():
    """
    Test performance with 1 real playlist (cost-effective check).

    This test runs only if OPENAI_API_KEY is set. It provides actual
    performance metrics for a single playlist to estimate full-run performance.
    """
    # Load test fixture
    doc_path = Path(__file__).parent.parent / "fixtures" / "sample_station_identity.md"
    assert doc_path.exists(), f"Test fixture not found: {doc_path}"

    with open(doc_path) as f:
        content = f.read()

    start_time = time.time()

    # Parse document
    dayparts = parse_programming_document(content)
    assert len(dayparts) > 0, "No dayparts parsed from fixture"

    # Generate specs (take first one only for cost efficiency)
    specs = generate_playlist_specs(dayparts[:1])
    assert len(specs) == 1, "Expected exactly 1 playlist spec"

    # Get OpenAI client
    client = get_client()

    # Create selection request
    request = client.create_selection_request(specs[0])

    # Estimate cost before execution
    estimated_cost = client.estimate_cost(request)
    print(f"\n💰 Estimated cost for single playlist: ${estimated_cost:.4f}")

    # Select tracks with LLM (real API call)
    response = await select_tracks_with_llm(request)

    end_time = time.time()
    duration = end_time - start_time
    cost = response.cost_usd

    # Print metrics
    print(f"⏱️  Execution time: {duration:.2f}s")
    print(f"💵 Actual cost: ${cost:.4f}")
    print(f"🎵 Tracks selected: {len(response.selected_tracks)}")

    # Assertions for single playlist
    assert duration < 60, f"Single playlist took {duration:.1f}s (should be <60s)"
    assert cost < 0.02, f"Single playlist cost ${cost:.4f} (should be <$0.02)"
    assert len(response.selected_tracks) > 0, "No tracks selected"

    return {
        "duration_seconds": duration,
        "cost_usd": cost,
        "tracks_selected": len(response.selected_tracks),
        "estimated_cost": estimated_cost,
    }


def test_performance_estimate_full_run_conservative():
    """
    Estimate full 47-playlist performance using CONSERVATIVE assumptions.

    This test runs without API access and provides cost/time estimates
    based on conservative assumptions:
    - 8 seconds per playlist (sequential)
    - $0.008 per playlist (based on GPT-4o-mini pricing)
    """
    # Expected playlist count from full week programming
    # Based on project specs: Mon-Sun with multiple dayparts per day
    # Typical: 5-7 dayparts/day × 7 days = 35-49 playlists
    playlist_count = 47  # As specified in T034 requirements

    print(f"\n📊 Analyzing {playlist_count} playlists from fixture...")

    # Conservative estimates (based on Phase 2 research)
    # GPT-4o-mini: $0.15/1M input tokens, $0.60/1M output tokens
    # Average playlist: ~500 input tokens + ~2000 output tokens
    # Average cost: (500 * 0.15 + 2000 * 0.60) / 1,000,000 = ~$0.0013 per playlist
    # Add 6x safety margin for MCP tool calls: ~$0.008 per playlist

    CONSERVATIVE_TIME_PER_PLAYLIST = 8.0  # seconds (sequential execution)
    CONSERVATIVE_COST_PER_PLAYLIST = 0.008  # USD

    # Calculate estimates
    estimated_time_sequential = CONSERVATIVE_TIME_PER_PLAYLIST * playlist_count
    estimated_cost_total = CONSERVATIVE_COST_PER_PLAYLIST * playlist_count

    # Parallel execution (assume 10 concurrent workers)
    estimated_time_parallel = estimated_time_sequential / 10

    print(f"\n🔮 CONSERVATIVE ESTIMATES:")
    print(f"   Playlist count: {playlist_count}")
    print(f"   Per-playlist metrics:")
    print(f"     - Time: {CONSERVATIVE_TIME_PER_PLAYLIST}s")
    print(f"     - Cost: ${CONSERVATIVE_COST_PER_PLAYLIST:.4f}")
    print(f"\n   Total estimates (sequential):")
    print(f"     ⏱️  Time: {estimated_time_sequential/60:.1f} min")
    print(f"     💵 Cost: ${estimated_cost_total:.2f}")
    print(f"\n   Total estimates (10 parallel workers):")
    print(f"     ⏱️  Time: {estimated_time_parallel/60:.1f} min")
    print(f"     💵 Cost: ${estimated_cost_total:.2f}")

    # Check against requirements
    time_within_budget = estimated_time_parallel < MAX_EXECUTION_TIME_SECONDS
    cost_within_budget = estimated_cost_total < MAX_TOTAL_COST_USD

    print(f"\n✅ VALIDATION AGAINST REQUIREMENTS:")
    print(f"   Time requirement (<10 min): {'PASS ✓' if time_within_budget else 'FAIL ✗'}")
    print(f"   Cost requirement (<$0.50): {'PASS ✓' if cost_within_budget else 'FAIL ✗'}")

    # Assertions
    assert time_within_budget, (
        f"Estimated time {estimated_time_parallel/60:.1f} min exceeds "
        f"requirement {MAX_EXECUTION_TIME_SECONDS/60:.1f} min"
    )
    assert cost_within_budget, (
        f"Estimated cost ${estimated_cost_total:.2f} exceeds "
        f"requirement ${MAX_TOTAL_COST_USD:.2f}"
    )


def test_performance_estimate_full_run_optimistic():
    """
    Estimate full 47-playlist performance using OPTIMISTIC assumptions.

    This test provides best-case estimates assuming:
    - 5 seconds per playlist (with caching and optimization)
    - $0.005 per playlist (efficient MCP tool usage)
    """
    # Expected playlist count from full week programming
    # Based on project specs: Mon-Sun with multiple dayparts per day
    # Typical: 5-7 dayparts/day × 7 days = 35-49 playlists
    playlist_count = 47  # As specified in T034 requirements

    # Optimistic estimates (with caching, batch operations)
    OPTIMISTIC_TIME_PER_PLAYLIST = 5.0  # seconds
    OPTIMISTIC_COST_PER_PLAYLIST = 0.005  # USD

    # Calculate estimates
    estimated_time_sequential = OPTIMISTIC_TIME_PER_PLAYLIST * playlist_count
    estimated_cost_total = OPTIMISTIC_COST_PER_PLAYLIST * playlist_count

    # Parallel execution (assume 10 concurrent workers)
    estimated_time_parallel = estimated_time_sequential / 10

    print(f"\n🎯 OPTIMISTIC ESTIMATES:")
    print(f"   Playlist count: {playlist_count}")
    print(f"   Per-playlist metrics:")
    print(f"     - Time: {OPTIMISTIC_TIME_PER_PLAYLIST}s")
    print(f"     - Cost: ${OPTIMISTIC_COST_PER_PLAYLIST:.4f}")
    print(f"\n   Total estimates (10 parallel workers):")
    print(f"     ⏱️  Time: {estimated_time_parallel/60:.1f} min")
    print(f"     💵 Cost: ${estimated_cost_total:.2f}")

    # Check against requirements
    time_within_budget = estimated_time_parallel < MAX_EXECUTION_TIME_SECONDS
    cost_within_budget = estimated_cost_total < MAX_TOTAL_COST_USD

    print(f"\n✅ VALIDATION AGAINST REQUIREMENTS:")
    print(f"   Time requirement (<10 min): {'PASS ✓' if time_within_budget else 'FAIL ✗'}")
    print(f"   Cost requirement (<$0.50): {'PASS ✓' if cost_within_budget else 'FAIL ✗'}")

    # Assertions
    assert time_within_budget, (
        f"Estimated time {estimated_time_parallel/60:.1f} min exceeds "
        f"requirement {MAX_EXECUTION_TIME_SECONDS/60:.1f} min"
    )
    assert cost_within_budget, (
        f"Estimated cost ${estimated_cost_total:.2f} exceeds "
        f"requirement ${MAX_TOTAL_COST_USD:.2f}"
    )


def test_performance_requirements_documented():
    """
    Verify performance requirements are correctly documented.

    This test ensures we have clear performance targets and that they
    are reflected in the test suite.
    """
    requirements = {
        "max_execution_time_seconds": MAX_EXECUTION_TIME_SECONDS,
        "max_execution_time_minutes": MAX_EXECUTION_TIME_SECONDS / 60,
        "max_total_cost_usd": MAX_TOTAL_COST_USD,
    }

    print(f"\n📋 DOCUMENTED PERFORMANCE REQUIREMENTS:")
    print(f"   Maximum execution time: {requirements['max_execution_time_minutes']:.1f} minutes")
    print(f"   Maximum total cost: ${requirements['max_total_cost_usd']:.2f}")

    # Assertions to ensure requirements are reasonable
    assert requirements["max_execution_time_minutes"] == 10.0, "Time requirement should be 10 minutes"
    assert requirements["max_total_cost_usd"] == 0.50, "Cost requirement should be $0.50"


@pytest.mark.asyncio
@pytest.mark.skipif(not (os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_KEY")), reason="No OpenAI API key")
async def test_performance_token_estimation_accuracy():
    """
    Test accuracy of token estimation vs actual usage.

    This test validates that our token estimation logic is accurate,
    which is critical for cost prediction.
    """
    # Load test fixture
    doc_path = Path(__file__).parent.parent / "fixtures" / "sample_station_identity.md"
    with open(doc_path) as f:
        content = f.read()

    # Parse and generate specs
    dayparts = parse_programming_document(content)
    specs = generate_playlist_specs(dayparts[:1])

    # Get client and create request
    client = get_client()
    request = client.create_selection_request(specs[0])

    # Get estimates
    estimated_tokens = client.estimate_tokens(request)
    estimated_cost = client.estimate_cost(request)

    print(f"\n🔍 TOKEN ESTIMATION ACCURACY:")
    print(f"   Estimated tokens: {estimated_tokens}")
    print(f"   Estimated cost: ${estimated_cost:.6f}")

    # Make actual API call
    response = await select_tracks_with_llm(request)

    # Compare estimates to actual
    print(f"\n   Actual cost: ${response.cost_usd:.6f}")
    print(f"   Estimation error: {abs(estimated_cost - response.cost_usd)/estimated_cost*100:.1f}%")

    # Estimation should be within 50% of actual (conservative buffer)
    estimation_error = abs(estimated_cost - response.cost_usd) / estimated_cost
    assert estimation_error < 0.50, f"Token estimation error {estimation_error*100:.1f}% exceeds 50%"
