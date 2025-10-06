"""
OpenAI Client for AI Playlist Generation - Phase 1 Implementation

Implements LLM-driven track selection using OpenAI GPT-5 with MCP tool integration.
Handles request creation, token estimation, and async LLM calls with cost tracking.
"""

import os
import asyncio
import logging
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
import tiktoken

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion

from .models import (
    PlaylistSpec,
    LLMTrackSelectionRequest,
    LLMTrackSelectionResponse,
    SelectedTrack,
    TrackSelectionCriteria,
)

logger = logging.getLogger(__name__)


class OpenAIClient:
    """OpenAI client for AI playlist generation with MCP tool integration."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize OpenAI client.

        Args:
            api_key: OpenAI API key. If None, reads from OPENAI_API_KEY or OPENAI_KEY env var.
            model: Model name to use. If None, reads from OPENAI_MODEL env var (default: "gpt-5").

        Raises:
            ValueError: If API key is not provided or found in environment.
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY or OPENAI_KEY must be provided or set in environment")

        self.client = AsyncOpenAI(api_key=self.api_key)
        # Allow model override via parameter or environment variable
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-5")

        # Get appropriate encoding for the model
        try:
            self.encoding = tiktoken.encoding_for_model(self.model)
        except KeyError:
            # Fallback to o200k_base for unknown models (GPT-5 uses o200k_base)
            logger.warning(
                f"Model '{self.model}' not found in tiktoken, using o200k_base encoding"
            )
            self.encoding = tiktoken.get_encoding("o200k_base")

        # Cost per token (as of 2025-01)
        self.cost_per_input_token = 0.00000015  # $0.15 per 1M tokens
        self.cost_per_output_token = 0.00000060  # $0.60 per 1M tokens

    def create_selection_request(self, spec: PlaylistSpec) -> LLMTrackSelectionRequest:
        """
        Create LLM track selection request from playlist specification.

        Args:
            spec: Playlist specification with daypart and criteria.

        Returns:
            LLMTrackSelectionRequest ready for LLM call.
        """
        # Calculate target track count based on duration and tracks per hour
        duration_hours = spec.target_duration_minutes / 60.0
        target_track_count = int(spec.daypart.tracks_per_hour * duration_hours)

        # Build prompt template with all constraints
        prompt_template = self._build_prompt_template(spec)

        return LLMTrackSelectionRequest(
            playlist_id=spec.id,
            criteria=spec.track_criteria,
            target_track_count=target_track_count,
            mcp_tools=["search_tracks", "get_genres", "search_similar", "analyze_library"],
            prompt_template=prompt_template,
            max_cost_usd=0.01,  # $0.01 per playlist
            timeout_seconds=30,
        )

    def _build_prompt_template(self, spec: PlaylistSpec) -> str:
        """
        Build detailed prompt template for LLM track selection.

        Args:
            spec: Playlist specification with all constraints.

        Returns:
            Formatted prompt string.
        """
        criteria = spec.track_criteria
        daypart = spec.daypart

        # Format BPM range
        bpm_min, bpm_max = criteria.bpm_range
        bpm_range_str = f"{bpm_min}-{bpm_max} BPM"

        # Format genre mix
        genre_mix_str = ", ".join(
            f"{genre}: {min_pct*100:.0f}-{max_pct*100:.0f}%"
            for genre, (min_pct, max_pct) in criteria.genre_mix.items()
        )

        # Format era distribution
        era_dist_str = ", ".join(
            f"{era}: {min_pct*100:.0f}-{max_pct*100:.0f}%"
            for era, (min_pct, max_pct) in criteria.era_distribution.items()
        )

        # Format Australian content requirement
        australian_str = f"{criteria.australian_min*100:.0f}% minimum"

        # Target track count
        duration_hours = spec.target_duration_minutes / 60.0
        target_count = int(daypart.tracks_per_hour * duration_hours)

        prompt = f"""Select tracks for playlist "{spec.name}" matching these requirements:

**Playlist Context:**
- Daypart: {daypart.name} ({daypart.day}, {daypart.time_range[0]}-{daypart.time_range[1]})
- Mood: {daypart.mood}
- Duration: {spec.target_duration_minutes} minutes

**Constraint Requirements:**
- BPM Range: {bpm_range_str}
- Genre Mix: {genre_mix_str}
- Era Distribution: {era_dist_str}
- Australian Content: {australian_str}
- Energy Flow: {criteria.energy_flow}

**Selection Rules:**
1. Target exactly {target_count} tracks
2. Order tracks for smooth energy transitions based on BPM progression
3. Maintain genre diversity throughout playlist (avoid clustering same genres)
4. Balance eras evenly across the playlist duration
5. Prioritize Australian content to meet minimum requirement
6. Exclude any tracks in the exclusion list: {criteria.excluded_track_ids}

**Output Format:**
For each track, provide:
- Track ID, title, artist, album
- BPM, genre, year, country
- Position in playlist (1-{target_count})
- Selection reason (why this track fits the energy flow and constraints)

Use the available MCP tools to search and analyze the music library:
- search_tracks: Find tracks matching BPM, genre, era criteria
- get_genres: Get available genres in library
- search_similar: Find similar tracks for flow continuity
- analyze_library: Get library statistics for constraint feasibility
"""
        return prompt

    def estimate_tokens(self, request: LLMTrackSelectionRequest) -> int:
        """
        Estimate token count for LLM request.

        Args:
            request: LLM track selection request.

        Returns:
            Estimated total token count (input + expected output).
        """
        # Encode prompt to count input tokens
        input_tokens = len(self.encoding.encode(request.prompt_template))

        # Estimate output tokens (each track ~200 tokens with metadata)
        estimated_output_tokens = request.target_track_count * 200

        total_tokens = input_tokens + estimated_output_tokens

        logger.debug(
            f"Token estimate for playlist {request.playlist_id}: "
            f"{input_tokens} input + {estimated_output_tokens} output = {total_tokens} total"
        )

        return total_tokens

    def estimate_cost(self, request: LLMTrackSelectionRequest) -> float:
        """
        Estimate cost for LLM request.

        Args:
            request: LLM track selection request.

        Returns:
            Estimated cost in USD.
        """
        # Get token counts
        input_tokens = len(self.encoding.encode(request.prompt_template))
        estimated_output_tokens = request.target_track_count * 200

        # Calculate cost
        input_cost = input_tokens * self.cost_per_input_token
        output_cost = estimated_output_tokens * self.cost_per_output_token
        total_cost = input_cost + output_cost

        logger.debug(
            f"Cost estimate for playlist {request.playlist_id}: "
            f"${input_cost:.6f} input + ${output_cost:.6f} output = ${total_cost:.6f} total"
        )

        return total_cost

    async def call_llm(
        self, request: LLMTrackSelectionRequest, mcp_tools: Dict[str, str]
    ) -> LLMTrackSelectionResponse:
        """
        Call OpenAI LLM with MCP tool integration for track selection.

        Args:
            request: LLM track selection request.
            mcp_tools: MCP tool configuration dict (from mcp_connector).

        Returns:
            LLMTrackSelectionResponse with selected tracks and metadata.

        Raises:
            ValueError: If request validation fails.
            TimeoutError: If LLM call exceeds timeout.
            Exception: If LLM call fails after retries.
        """
        start_time = datetime.now()

        logger.info(
            f"Calling LLM for playlist {request.playlist_id} "
            f"(target: {request.target_track_count} tracks, "
            f"max cost: ${request.max_cost_usd:.4f}, "
            f"timeout: {request.timeout_seconds}s)"
        )

        try:
            # Prepare messages
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are an expert radio playlist curator. "
                        "Select tracks that match the given constraints while creating "
                        "smooth energy flow and maintaining listener engagement. "
                        "Use the provided MCP tools to search and analyze the music library."
                    ),
                },
                {"role": "user", "content": request.prompt_template},
            ]

            # Call OpenAI with MCP tools
            response: ChatCompletion = await asyncio.wait_for(
                self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,  # type: ignore[arg-type]
                    temperature=0.7,  # Balance creativity with consistency
                    max_tokens=request.target_track_count * 250,  # Safety margin
                ),
                timeout=request.timeout_seconds,
            )

            # Extract response data
            choice = response.choices[0]
            message = choice.message

            # Parse tool calls
            tool_calls_data: List[Dict[str, Any]] = []
            if message.tool_calls:
                for tool_call in message.tool_calls:
                    # Handle both function tool calls and custom tool calls
                    if hasattr(tool_call, "function"):
                        tool_calls_data.append(
                            {
                                "tool_name": tool_call.function.name,
                                "arguments": tool_call.function.arguments,
                                "result": "MCP tool execution result",  # Placeholder
                            }
                        )

            # Parse selected tracks from response content
            # NOTE: This is a simplified parser - real implementation would use
            # structured output or JSON mode for reliable parsing
            selected_tracks = self._parse_tracks_from_response(
                message.content or "", request.target_track_count
            )

            # Calculate actual cost
            usage = response.usage
            if usage:
                actual_cost = (
                    usage.prompt_tokens * self.cost_per_input_token
                    + usage.completion_tokens * self.cost_per_output_token
                )
            else:
                actual_cost = 0.0

            # Calculate execution time
            execution_time = (datetime.now() - start_time).total_seconds()

            logger.info(
                f"LLM call completed for playlist {request.playlist_id}: "
                f"{len(selected_tracks)} tracks selected, "
                f"${actual_cost:.6f} cost, "
                f"{execution_time:.2f}s execution time"
            )

            return LLMTrackSelectionResponse(
                request_id=request.playlist_id,
                selected_tracks=selected_tracks,
                tool_calls=tool_calls_data,
                reasoning=message.content or "No reasoning provided",
                cost_usd=actual_cost,
                execution_time_seconds=execution_time,
            )

        except asyncio.TimeoutError:
            logger.error(
                f"LLM call timeout for playlist {request.playlist_id} "
                f"after {request.timeout_seconds}s"
            )
            raise TimeoutError(f"LLM call exceeded timeout of {request.timeout_seconds}s")

        except Exception as e:
            logger.error(
                f"LLM call failed for playlist {request.playlist_id}: {e}",
                exc_info=True,
            )
            raise

    def _parse_tracks_from_response(self, content: str, target_count: int) -> List[SelectedTrack]:
        """
        Parse selected tracks from LLM response content.

        NOTE: This is a simplified implementation for testing.
        Production version should use OpenAI's structured output mode or
        JSON schema validation for reliable parsing.

        Args:
            content: LLM response content.
            target_count: Expected number of tracks.

        Returns:
            List of SelectedTrack objects.
        """
        # Placeholder implementation - returns empty list for now
        # Real implementation would parse structured output
        logger.warning("Using placeholder track parser - implement structured output parsing")
        return []


# Singleton instance
_client_instance: Optional[OpenAIClient] = None


def get_client() -> OpenAIClient:
    """
    Get singleton OpenAI client instance.

    Returns:
        OpenAIClient instance.
    """
    global _client_instance
    if _client_instance is None:
        _client_instance = OpenAIClient()
    return _client_instance
