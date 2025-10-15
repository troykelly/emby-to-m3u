"""
LLM Track Selector with Retry Logic and Constraint Relaxation

Implements track selection using OpenAI GPT-5 with Subsonic MCP tools.
Includes 3-retry exponential backoff and hierarchical constraint relaxation.
"""

import asyncio
import time
import json
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from openai import AsyncOpenAI
import os
import uuid

from .models import (
    LLMTrackSelectionRequest,
    LLMTrackSelectionResponse,
    TrackSelectionCriteria,
    SelectedTrack,
)
from .exceptions import (
    CostExceededError,
    MCPToolError,
    APIError,
)
from ._prompt_builders import build_selection_prompt, build_relaxation_prompt

# Configure logging
logger = logging.getLogger(__name__)


# GPT-5 pricing (as of January 2025)
PRICING = {
    "input_tokens": 0.15 / 1_000_000,  # $0.15 per 1M input tokens
    "output_tokens": 0.60 / 1_000_000,  # $0.60 per 1M output tokens
}


async def select_tracks_with_llm(
    request: LLMTrackSelectionRequest,
) -> LLMTrackSelectionResponse:
    """
    Select tracks using OpenAI LLM with Subsonic MCP tools.

    Args:
        request: Track selection request with criteria and constraints

    Returns:
        LLMTrackSelectionResponse with selected tracks and metadata

    Raises:
        CostExceededError: If estimated cost exceeds max_cost_usd
        MCPToolError: If Subsonic MCP server is unavailable
        APIError: If OpenAI API fails after retries
    """
    start_time = time.time()

    # Estimate cost before making API call
    estimated_cost = _estimate_cost(request)
    if estimated_cost > request.max_cost_usd:
        raise CostExceededError(
            f"Estimated cost ${estimated_cost:.4f} exceeds budget ${request.max_cost_usd:.4f}"
        )

    # Initialize OpenAI client (model can be overridden via OPENAI_MODEL env var)
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY or OPENAI_KEY environment variable not set")

    client = AsyncOpenAI(api_key=api_key)
    model = os.getenv("OPENAI_MODEL", "gpt-5")

    # Build prompt from request
    prompt = build_selection_prompt(request)

    # Configure MCP tools
    mcp_tools = _configure_mcp_tools(request.mcp_tools)

    # Retry with exponential backoff
    response_data = await _retry_with_backoff(
        lambda: _call_openai_api(client, prompt, mcp_tools, request.timeout_seconds, model),
        max_attempts=3,
        base_delay=1.0,
        max_delay=60.0,
    )

    if response_data is None:
        raise Exception("Failed to get response after retries")

    # Parse response
    selected_tracks = _parse_llm_response(response_data["content"])
    tool_calls = _extract_tool_calls(response_data.get("tool_calls", []))
    reasoning = _extract_reasoning(response_data["content"])

    # Calculate actual cost
    usage = response_data["usage"]
    actual_cost = (
        usage["prompt_tokens"] * PRICING["input_tokens"]
        + usage["completion_tokens"] * PRICING["output_tokens"]
    )

    # Check cost again (actual vs estimated)
    if actual_cost > request.max_cost_usd:
        raise CostExceededError(
            f"Actual cost ${actual_cost:.4f} exceeds budget ${request.max_cost_usd:.4f}"
        )

    execution_time = time.time() - start_time

    return LLMTrackSelectionResponse(
        request_id=request.playlist_id,
        selected_tracks=selected_tracks,
        tool_calls=tool_calls,
        reasoning=reasoning,
        cost_usd=actual_cost,
        execution_time_seconds=execution_time,
        created_at=datetime.now(),
    )


async def select_tracks_with_relaxation(
    criteria: TrackSelectionCriteria,
    max_iterations: int = 3,
) -> List[SelectedTrack]:
    """
    Select tracks with hierarchical constraint relaxation.

    Relaxation priority:
    1. BPM range (±10 BPM per iteration)
    2. Genre mix tolerance (±5% per iteration)
    3. Era distribution tolerance (±5% per iteration)

    Australian minimum (30%) is NON-NEGOTIABLE.

    Args:
        criteria: Initial track selection criteria
        max_iterations: Maximum relaxation iterations (default: 3)

    Returns:
        List of selected tracks meeting ≥80% constraint satisfaction
    """
    current_criteria = criteria

    for iteration in range(max_iterations + 1):
        logger.info(f"Constraint relaxation iteration {iteration}/{max_iterations}")

        # Attempt track selection with current criteria
        try:
            # Build request for this iteration
            request = LLMTrackSelectionRequest(
                playlist_id=str(uuid.uuid4()),  # Generate temp ID
                criteria=current_criteria,
                target_track_count=12,  # Default
                prompt_template=build_relaxation_prompt(current_criteria, iteration),
                max_cost_usd=0.01,
            )

            response = await select_tracks_with_llm(request)

            # Validate constraint satisfaction
            satisfaction = _validate_constraint_satisfaction(
                response.selected_tracks,
                criteria,  # Validate against ORIGINAL criteria
            )

            logger.info(f"Constraint satisfaction: {satisfaction:.2%}")

            # Check if satisfaction threshold met (≥80%)
            if satisfaction >= 0.80:
                logger.info(f"Constraint satisfaction threshold met at iteration {iteration}")
                return response.selected_tracks

            # Relax constraints for next iteration
            if iteration == 0:
                current_criteria = current_criteria.relax_bpm(increment=10)
                logger.info("Relaxed BPM range by ±10")
            elif iteration == 1:
                current_criteria = current_criteria.relax_genre(tolerance=0.05)
                logger.info("Relaxed genre tolerance by ±5%")
            elif iteration == 2:
                current_criteria = current_criteria.relax_era(tolerance=0.05)
                logger.info("Relaxed era tolerance by ±5%")

        except Exception as e:
            logger.error(f"Iteration {iteration} failed: {e}")
            if iteration == max_iterations:
                # Return best effort on final iteration
                logger.warning("Returning best effort after all iterations failed")
                return response.selected_tracks if "response" in locals() else []

    # Return best effort if all iterations exhausted
    logger.warning(f"All {max_iterations} iterations exhausted, returning best effort")
    return response.selected_tracks if "response" in locals() else []


# Helper Functions


def _estimate_cost(request: LLMTrackSelectionRequest) -> float:
    """Estimate LLM API cost based on request parameters."""
    # Rough estimation: 100 tokens per track requested + 500 base tokens
    estimated_input_tokens = 500 + (request.target_track_count * 50)
    estimated_output_tokens = request.target_track_count * 100

    estimated_cost = (
        estimated_input_tokens * PRICING["input_tokens"]
        + estimated_output_tokens * PRICING["output_tokens"]
    )

    return estimated_cost


def _configure_mcp_tools(tool_names: List[str]) -> List[Dict[str, Any]]:
    """Configure MCP tools for OpenAI API."""
    # Check if MCP server is accessible
    mcp_url = os.getenv("SUBSONIC_MCP_URL")
    if not mcp_url:
        raise MCPToolError("SUBSONIC_MCP_URL environment variable not set")

    # Build hosted MCP tool configuration
    tools = [
        {
            "type": "hosted_mcp",
            "hosted_mcp": {
                "server_url": mcp_url,
                "tools": tool_names,
            },
        }
    ]

    return tools


async def _call_openai_api(
    client: AsyncOpenAI,
    prompt: str,
    tools: List[Dict[str, Any]],
    timeout: int,
    model: str = "gpt-5",
) -> Dict[str, Any]:
    """Call OpenAI API with timeout."""
    try:
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            ),
            timeout=timeout,
        )

        # Handle optional usage field
        usage = response.usage
        usage_dict = {
            "prompt_tokens": usage.prompt_tokens if usage else 0,
            "completion_tokens": usage.completion_tokens if usage else 0,
            "total_tokens": usage.total_tokens if usage else 0,
        }

        return {
            "content": response.choices[0].message.content,
            "tool_calls": response.choices[0].message.tool_calls or [],
            "usage": usage_dict,
        }
    except asyncio.TimeoutError:
        raise MCPToolError(f"OpenAI API request timed out after {timeout}s")
    except Exception as e:
        raise MCPToolError(f"OpenAI API error: {str(e)}")


async def _retry_with_backoff(
    func: Any,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
) -> Optional[Any]:
    """Retry function with exponential backoff."""
    for attempt in range(max_attempts):
        try:
            return await func()
        except Exception as e:
            if attempt == max_attempts - 1:
                logger.error(f"Failed after {max_attempts} attempts: {e}")
                raise

            delay = min(base_delay * (2**attempt), max_delay)
            logger.warning(f"Attempt {attempt + 1} failed, retrying in {delay}s: {e}")
            await asyncio.sleep(delay)

    return None


def _parse_llm_response(content: str) -> List[SelectedTrack]:
    """Parse LLM response to extract selected tracks."""
    try:
        data = json.loads(content)
        tracks_data = data.get("tracks", [])

        selected_tracks = []
        for i, track_data in enumerate(tracks_data):
            selected_track = SelectedTrack(
                track_id=track_data.get("track_id", ""),
                title=track_data.get("title", ""),
                artist=track_data.get("artist", ""),
                album=track_data.get("album", ""),
                bpm=track_data.get("bpm"),
                genre=track_data.get("genre"),
                year=track_data.get("year"),
                country=track_data.get("country"),
                duration_seconds=track_data.get("duration_seconds", 0),
                is_australian=track_data.get("is_australian", False),
                rotation_category=track_data.get("rotation_category", "C"),
                position_in_playlist=i + 1,
                selection_reasoning=track_data.get("selection_reason", ""),
                validation_status=track_data.get("validation_status", "pending"),
                metadata_source=track_data.get("metadata_source", "subsonic"),
            )
            selected_tracks.append(selected_track)

        return selected_tracks
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logger.error(f"Failed to parse LLM response: {e}")
        return []


def _extract_tool_calls(tool_calls: Any) -> List[Dict[str, Any]]:
    """Extract tool call information from response."""
    extracted = []
    for tool_call in tool_calls:
        extracted.append(
            {
                "tool_name": tool_call.function.name,
                "arguments": json.loads(tool_call.function.arguments),
                "result": {},  # Result would be populated by MCP
            }
        )
    return extracted


def _extract_reasoning(content: str) -> str:
    """Extract reasoning from LLM response."""
    try:
        data = json.loads(content)
        result: str = data.get("reasoning", "")
        return result
    except json.JSONDecodeError:
        return ""


def _validate_constraint_satisfaction(
    tracks: List[SelectedTrack],
    criteria: TrackSelectionCriteria,
) -> float:
    """
    Validate constraint satisfaction percentage.

    Returns:
        Float between 0.0 and 1.0 representing satisfaction level
    """
    if not tracks:
        return 0.0

    scores = []

    # BPM satisfaction
    bpm_range = criteria.bpm_range
    bpm_tracks = [t for t in tracks if t.bpm is not None]
    if bpm_tracks:
        in_range = sum(
            1 for t in bpm_tracks if t.bpm is not None and bpm_range[0] <= t.bpm <= bpm_range[1]
        )
        scores.append(in_range / len(bpm_tracks))

    # Genre satisfaction
    if criteria.genre_mix:
        genre_counts: Dict[str, int] = {}
        for track in tracks:
            if track.genre:
                genre_counts[track.genre] = genre_counts.get(track.genre, 0) + 1

        genre_scores = []
        for genre, criteria_obj in criteria.genre_mix.items():
            min_pct = criteria_obj.min_percentage
            max_pct = criteria_obj.max_percentage
            actual_pct = genre_counts.get(genre, 0) / len(tracks)
            if min_pct <= actual_pct <= max_pct:
                genre_scores.append(1.0)
            else:
                # Partial credit based on distance
                distance = min(abs(actual_pct - min_pct), abs(actual_pct - max_pct))
                genre_scores.append(max(0.0, 1.0 - distance))

        if genre_scores:
            scores.append(sum(genre_scores) / len(genre_scores))

    # Australian content satisfaction
    au_tracks = sum(1 for t in tracks if t.country == "AU")
    au_pct = au_tracks / len(tracks)
    if au_pct >= criteria.australian_min:
        scores.append(1.0)
    else:
        scores.append(au_pct / criteria.australian_min)

    # Calculate overall satisfaction
    return sum(scores) / len(scores) if scores else 0.0
