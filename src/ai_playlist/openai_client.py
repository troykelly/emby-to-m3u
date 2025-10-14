"""
OpenAI Client for AI Playlist Generation - Phase 1 Implementation

Implements LLM-driven track selection using OpenAI GPT-5 with MCP tool integration.
Handles request creation, token estimation, and async LLM calls with cost tracking.
"""

import os
import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from decimal import Decimal
import tiktoken

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion

from .models import (
    PlaylistSpec,
    PlaylistSpecification,
    LLMTrackSelectionRequest,
    LLMTrackSelectionResponse,
    SelectedTrack,
    TrackSelectionCriteria,
    Playlist,
    ValidationResult,
)
from .cost_manager import CostManager, BudgetExceededError
from .validator import validate_playlist
from .decision_logger import DecisionLogger
from .subsonic_tools import SubsonicTools
from src.subsonic.client import SubsonicClient

logger = logging.getLogger(__name__)

# T110: Timeout constants
DEFAULT_PER_TOOL_TIMEOUT_SECONDS = 10
DEFAULT_TOTAL_TIMEOUT_SECONDS = 120
MAX_TOOL_TIMEOUT_SECONDS = 30


class OpenAIClient:
    """OpenAI client for AI playlist generation with MCP tool integration."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        per_tool_timeout_seconds: float = DEFAULT_PER_TOOL_TIMEOUT_SECONDS
    ):
        """
        Initialize OpenAI client.

        Args:
            api_key: OpenAI API key. If None, reads from OPENAI_API_KEY or OPENAI_KEY env var.
            model: Model name to use. If None, reads from OPENAI_MODEL env var (default: "gpt-5").
            per_tool_timeout_seconds: Timeout for individual tool calls (default 10s)

        Raises:
            ValueError: If API key is not provided or found in environment, or timeout invalid
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY or OPENAI_KEY must be provided or set in environment")

        # T110: Validate timeout
        if per_tool_timeout_seconds <= 0:
            raise ValueError("per_tool_timeout_seconds must be positive")
        if per_tool_timeout_seconds > MAX_TOOL_TIMEOUT_SECONDS:
            raise ValueError(f"per_tool_timeout_seconds cannot exceed {MAX_TOOL_TIMEOUT_SECONDS}s")

        self.client = AsyncOpenAI(api_key=self.api_key)
        # Allow model override via parameter or environment variable
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-5")
        self.per_tool_timeout_seconds = per_tool_timeout_seconds

        # Get appropriate encoding for the model
        try:
            self.encoding = tiktoken.encoding_for_model(self.model)
        except KeyError:
            # Fallback to o200k_base for unknown models (GPT-5 uses o200k_base)
            logger.warning(f"Model '{self.model}' not found in tiktoken, using o200k_base encoding")
            self.encoding = tiktoken.get_encoding("o200k_base")

        # Cost per token for GPT-5 (as of 2025-08)
        # Source: https://openai.com/api/pricing/
        self.cost_per_input_token = 0.00000125  # $1.25 per 1M tokens
        self.cost_per_output_token = 0.00001000  # $10.00 per 1M tokens

    def _build_system_prompt(self, subsonic_tools) -> str:
        """
        Build comprehensive system prompt explaining role, tools, and process.

        Args:
            subsonic_tools: SubsonicTools instance with tool definitions

        Returns:
            Detailed system prompt string
        """
        tool_descriptions = []
        for tool in subsonic_tools.get_tool_definitions():
            func = tool["function"]
            tool_descriptions.append(
                f"- **{func['name']}**: {func['description']}"
            )

        tools_doc = "\n".join(tool_descriptions)

        return f"""You are an expert radio playlist curator for a broadcast radio station.

**YOUR ROLE:**
You create playlists for specific dayparts (time blocks) that meet strict broadcast requirements including genre mix, BPM progression, era distribution, energy flow, and Australian content quotas.

**CRITICAL CONTEXT - Limited Music Library:**
- You are working with a CURATED, PRE-APPROVED music library
- This library contains ONLY tracks approved for broadcast on this specific radio station
- You CANNOT assume any artist, album, or track exists
- The library may be LIMITED in certain genres, eras, or BPM ranges
- ALWAYS work with what is AVAILABLE rather than what you wish existed

**YOUR TOOLS - Music Discovery:**
You have access to these tools to explore the music library:

{tools_doc}

**HOW TOOLS WORK:**
1. **Tool Calls**: When you call a tool, you'll receive a response with track data
2. **Response Format**: Tools return JSON with track details (id, title, artist, album, genre, bpm, year, duration)
3. **Empty Results**: If a tool returns 0 tracks, try different search terms or a different tool
4. **Suggestions**: Empty results include suggestions for alternative approaches

**EXPECTED WORKFLOW:**
1. **PHASE 1 - Discovery** (3-10 tool calls):
   - Call get_available_genres() first to see what genres exist in the library
   - Use search_tracks_by_genre() for each required genre
   - Use search_tracks() for specific styles/moods if needed
   - Use browse_artists() to ensure artist diversity
   - Gather 2-3x more candidates than your target

2. **PHASE 2 - Final Submission** (submit_playlist tool):
   - Review all discovered tracks from Phase 1
   - Select tracks that BEST MATCH the requirements (even if imperfect)
   - Order tracks for smooth energy/BPM transitions
   - CALL THE submit_playlist TOOL with your selected track IDs and reasoning
   - This is the ONLY valid way to complete playlist generation

**CRITICAL RULES:**
- NEVER return an empty selection - always select the best available tracks
- If the library is limited, select what IS available that best approximates requirements
- Prioritize having a playlist over perfect constraint matching
- Stop exploring after 5-10 tool calls and CALL submit_playlist
- You MUST use the submit_playlist tool - do NOT return JSON in message content

**FINAL SUBMISSION:**
When you finish exploring, CALL THE submit_playlist TOOL with:
- selected_track_ids: Array of track IDs in playback order
- reasoning: Brief explanation of selection strategy and constraint trade-offs

Example:
submit_playlist({{
    "selected_track_ids": ["track-id-1", "track-id-2", "track-id-3", ...],
    "reasoning": "Selected 20 tracks blending Rock (60%) and Alternative (40%) from 1990s-2010s with BPM 120-140. Prioritized Australian artists where available. Minor compromise on exact BPM targets due to library limitations."
}})
"""

    def create_selection_request(self, spec: PlaylistSpec, used_track_ids: Optional[set] = None) -> LLMTrackSelectionRequest:
        """
        Create LLM track selection request from playlist specification.

        Args:
            spec: Playlist specification with daypart and criteria.
            used_track_ids: Optional set of track IDs already used (to exclude).

        Returns:
            LLMTrackSelectionRequest ready for LLM call.
        """
        # Use target track count from spec
        target_track_count = spec.target_track_count_max

        # Build prompt template with all constraints
        prompt_template = self._build_prompt_template(spec, used_track_ids)

        return LLMTrackSelectionRequest(
            playlist_id=spec.id,
            criteria=spec.track_selection_criteria,
            target_track_count=target_track_count,
            mcp_tools=["search_tracks", "get_genres", "search_similar", "analyze_library"],
            prompt_template=prompt_template,
            max_cost_usd=0.01,  # $0.01 per playlist
            timeout_seconds=getattr(self, 'timeout_seconds', 30),  # Use instance timeout if set
        )

    def _build_prompt_template(self, spec: PlaylistSpec, used_track_ids: Optional[set] = None) -> str:
        """
        Build detailed prompt template for LLM track selection.

        Args:
            spec: Playlist specification with all constraints.
            used_track_ids: Optional set of track IDs to exclude.

        Returns:
            Formatted prompt string.
        """
        criteria = spec.track_selection_criteria

        # Add used track IDs to exclusion list if provided
        if used_track_ids:
            if criteria.excluded_track_ids:
                criteria.excluded_track_ids.update(used_track_ids)
            else:
                criteria.excluded_track_ids = used_track_ids

        # Format BPM range from bpm_ranges
        if criteria.bpm_ranges:
            bpm_min = min(r.bpm_min for r in criteria.bpm_ranges)
            bpm_max = max(r.bpm_max for r in criteria.bpm_ranges)
            bpm_range_str = f"{bpm_min}-{bpm_max} BPM"
        else:
            bpm_range_str = "No BPM constraints"

        # Format genre mix
        # Handle both GenreCriteria objects and raw percentages
        from .models.core import GenreCriteria as GenreCriteriaClass
        genre_mix_parts = []
        for genre, criteria_obj in criteria.genre_mix.items():
            if isinstance(criteria_obj, GenreCriteriaClass):
                # It's a GenreCriteria object
                genre_mix_parts.append(
                    f"{genre}: {criteria_obj.min_percentage*100:.0f}-{criteria_obj.max_percentage*100:.0f}%"
                )
            else:
                # It's a raw percentage (float)
                genre_mix_parts.append(f"{genre}: {criteria_obj*100:.0f}%")
        genre_mix_str = ", ".join(genre_mix_parts)

        # Format era distribution
        # Handle both EraCriteria objects and raw percentages
        from .models.core import EraCriteria as EraCriteriaClass
        era_dist_parts = []
        for era, criteria_obj in criteria.era_distribution.items():
            if isinstance(criteria_obj, EraCriteriaClass):
                # It's an EraCriteria object
                era_dist_parts.append(
                    f"{era}: {criteria_obj.min_percentage*100:.0f}-{criteria_obj.max_percentage*100:.0f}%"
                )
            else:
                # It's a raw percentage (float)
                era_dist_parts.append(f"{era}: {criteria_obj*100:.0f}%")
        era_dist_str = ", ".join(era_dist_parts)

        # Format Australian content requirement
        australian_str = f"{criteria.australian_content_min*100:.0f}% minimum"

        # Format mood and energy requirements
        mood_include_str = ", ".join(criteria.mood_filters_include) if criteria.mood_filters_include else "No specific mood requirements"
        mood_exclude_str = ", ".join(criteria.mood_filters_exclude) if criteria.mood_filters_exclude else "None"
        energy_flow_str = ", ".join(criteria.energy_flow_requirements) if criteria.energy_flow_requirements else "Natural progression"

        # Target track count
        target_count = spec.target_track_count_max

        prompt = f"""Create playlist: "{spec.name}"

**STATION CONTEXT & DAYPART IDENTITY:**
This playlist is for a broadcast radio station daypart (time block).
- **Daypart Name**: {spec.name}
- **Broadcast Date**: {spec.generation_date.strftime('%A, %B %d, %Y')}
- **Track Count**: {spec.target_track_count_min}-{spec.target_track_count_max} tracks required

**CRITICAL: Limited Music Library**
You are selecting from a CURATED, PRE-APPROVED music library for broadcast.
- The library contains ONLY tracks approved for this radio station
- You CANNOT assume any specific artist, album, or track exists
- The library may be LIMITED in certain genres, eras, or BPM ranges
- If you cannot find enough tracks matching ALL criteria, select the BEST AVAILABLE tracks
- ALWAYS prioritize track availability over perfect constraint matching

**MUSIC SELECTION REQUIREMENTS:**
All requirements below are FLEXIBLE - prioritize track availability over perfect matching.

**1. GENRE MIX** (approximate these percentages):
{genre_mix_str}

**2. ERA DISTRIBUTION** (balance across these eras):
{era_dist_str}

**3. BPM & ENERGY PROGRESSION**:
- BPM Range: {bpm_range_str}
- Energy Flow: {energy_flow_str}
- Create smooth transitions between tracks (no jarring BPM jumps)

**4. MOOD & VIBE**:
- Include these moods: {mood_include_str}
- Exclude these moods: {mood_exclude_str}

**5. AUSTRALIAN CONTENT QUOTA**:
- Target: {australian_str} (FLEXIBLE - use whatever Australian artists are available in library)
- If NO Australian artists found in library, proceed with best available international tracks
- Do NOT keep searching if library has no Australian content

**6. TRACK EXCLUSIONS**:
- Already used today (exclude): {", ".join(list(criteria.excluded_track_ids)[:10]) + ("..." if len(criteria.excluded_track_ids) > 10 else "") if criteria.excluded_track_ids else "None"}

**CRITICAL: Two-Phase Process**

**PHASE 1: Discovery (use tools to explore library)**
1. Call get_available_genres() to see available genres
2. Use search_tracks_by_genre() for each required genre
3. Use search_tracks() for specific artists/styles if needed
4. You should make 3-8 tool calls total to gather candidates

**PHASE 2: Final Submission (CALL submit_playlist tool)**
Once you have discovered candidates (even if less than {target_count * 2}):
1. Review ALL discovered tracks from your tool calls
2. Select the BEST AVAILABLE tracks (target {target_count}, but accept {spec.target_track_count_min}+ if library is limited)
3. Order tracks for smooth BPM/energy transitions
4. Ensure genre diversity when possible (don't cluster same genres)
5. Balance eras when possible
6. Include Australian content ONLY if available (NOT required - library may have none)
7. Exclude any tracks in exclusion list: {", ".join(criteria.excluded_track_ids) if criteria.excluded_track_ids else "None"}

**IMPORTANT - Selection Strategy:**
- If library is LIMITED: Select whatever tracks ARE available that best approximate the criteria
- NEVER submit an empty selection - ALWAYS select the best available tracks even if imperfect
- Stop exploring after 5-10 tool calls and CALL THE submit_playlist TOOL
- You MUST use the submit_playlist tool - this is the ONLY way to complete

**YOU MUST COMPLETE BOTH PHASES:**
1. First: Explore library with tools (3-8 tool calls to gather candidates)
2. Then: CALL submit_playlist tool with your selected track IDs

Example tool call:
submit_playlist({{
    "selected_track_ids": ["track-123", "track-456", "track-789", ...],
    "reasoning": "Selected {target_count} tracks blending required genres with BPM {bpm_range_str}. Prioritized available tracks over perfect constraint matching due to library limitations."
}})

DO NOT end the conversation without CALLING the submit_playlist tool. The system will fail if you don't use this tool.
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
        self, request: LLMTrackSelectionRequest, subsonic_tools: SubsonicTools
    ) -> LLMTrackSelectionResponse:
        """
        Call OpenAI LLM with tool calling support for dynamic track discovery.

        Implements multi-turn conversation loop where the LLM can:
        1. Call Subsonic tools to discover tracks dynamically
        2. Receive tool results and continue reasoning
        3. Make additional tool calls as needed
        4. Finally provide track selections

        Args:
            request: LLM track selection request.
            subsonic_tools: SubsonicTools instance for executing tool calls.

        Returns:
            LLMTrackSelectionResponse with selected tracks and tool usage metadata.

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
            # Prepare initial messages with comprehensive system prompt
            messages = [
                {
                    "role": "system",
                    "content": self._build_system_prompt(subsonic_tools),
                },
                {"role": "user", "content": request.prompt_template},
            ]

            # Prepare base completion kwargs with tools
            # T113: Use submit_playlist tool with strict: True for structured output enforcement
            # Start with tool_choice="auto" to allow discovery, then switch to requiring submit_playlist
            completion_kwargs = {
                "model": self.model,
                "tools": subsonic_tools.get_tool_definitions(),
                "tool_choice": "auto",  # Will change to required after discovery phase
            }

            # GPT-5 and O1 models have different parameter requirements
            if "gpt-5" in self.model.lower() or "o1" in self.model.lower():
                # Cap at 16000 for models with 16384 limit
                max_tokens = min(request.target_track_count * 250, 16000)
                completion_kwargs["max_completion_tokens"] = max_tokens
                # GPT-5 only supports temperature=1 (default), so don't set it
            else:
                # Cap at 16000 for models like gpt-4o-mini (16384 limit)
                max_tokens = min(request.target_track_count * 250, 16000)
                completion_kwargs["max_tokens"] = max_tokens
                completion_kwargs["temperature"] = 0.7  # Balance creativity with consistency

            # Track tool usage across conversation turns
            tool_calls_data: List[Dict[str, Any]] = []
            total_tool_calls = 0
            total_prompt_tokens = 0
            total_completion_tokens = 0

            # T110: Track timing metrics
            total_tool_time = 0.0
            total_llm_time = 0.0
            tool_timeouts_count = 0
            slowest_tool = {"name": None, "duration": 0.0}

            # Multi-turn conversation loop for tool execution
            # T109: Increased from 10 to 15 for complex playlists
            # T113: Increased to 50 - cost budget is the real safety constraint
            max_iterations = 100  # Increased from 50 to handle large exclusion lists
            iteration = 0

            # T109: Track efficiency for early stopping
            tracks_found_history: List[int] = []
            no_progress_threshold = 3  # Stop if no progress for 3 iterations

            # T115: Track unique discovered track IDs across all tool calls
            discovered_track_ids: set = set()

            while iteration < max_iterations:
                iteration += 1

                # T113: Check total elapsed time (not per-call timeout)
                elapsed_time = (datetime.now() - start_time).total_seconds()
                if elapsed_time > request.timeout_seconds:
                    logger.error(
                        f"Total conversation time ({elapsed_time:.1f}s) exceeded timeout "
                        f"({request.timeout_seconds}s) at iteration {iteration}"
                    )
                    raise TimeoutError(
                        f"LLM conversation exceeded total timeout of {request.timeout_seconds}s "
                        f"after {iteration} iterations"
                    )

                logger.debug(f"LLM conversation turn {iteration}/{max_iterations} (elapsed: {elapsed_time:.1f}s)")

                # T109: Warn when approaching iteration limit (80%)
                if iteration >= int(max_iterations * 0.8):
                    logger.warning(
                        f"Approaching iteration limit: {iteration}/{max_iterations} calls used. "
                        "This is unusual - check if LLM is stuck in a loop."
                    )

                # T113: Log tool definitions on first iteration
                if iteration == 1:
                    logger.debug(f"Available tools: {[t['function']['name'] for t in completion_kwargs['tools']]}")
                    logger.debug(f"Using submit_playlist tool for structured final output")

                # T115: After 5+ iterations of discovery with enough tracks, require submit_playlist tool
                # Only force submission if we have at least the minimum tracks (0.9x target as buffer)
                min_tracks_needed = int(request.target_track_count * 0.9)

                # Force submission after 10+ iterations even if limited library (safety fallback)
                if iteration >= 10 and total_tool_calls >= 5:
                    logger.warning(
                        f"Iteration {iteration}: Forcing submit_playlist after extensive discovery "
                        f"({len(discovered_track_ids)} tracks found, {total_tool_calls} tool calls)"
                    )
                    completion_kwargs["tool_choice"] = {
                        "type": "function",
                        "function": {"name": "submit_playlist"}
                    }
                # Standard path: force after 5+ iterations if we have enough tracks
                elif iteration >= 5 and total_tool_calls >= 3 and len(discovered_track_ids) >= min_tracks_needed:
                    logger.info(
                        f"Iteration {iteration}: Requiring submit_playlist tool to finalize selection "
                        f"({len(discovered_track_ids)} discovered tracks >= {min_tracks_needed} minimum)"
                    )
                    completion_kwargs["tool_choice"] = {
                        "type": "function",
                        "function": {"name": "submit_playlist"}
                    }
                elif iteration >= 5 and total_tool_calls >= 3:
                    logger.warning(
                        f"Iteration {iteration}: Not enough tracks discovered yet "
                        f"({len(discovered_track_ids)} < {min_tracks_needed} minimum). Continuing discovery phase."
                    )

                    # T116: Fallback strategy - if we're at iteration 5+ with insufficient tracks,
                    # inject a fallback search for safe genres (Pop/Rock/Current year)
                    # LOWERED from 15 to 5 to trigger earlier when library is very limited
                    if iteration >= 5 and len(discovered_track_ids) < min_tracks_needed:
                        logger.warning(
                            f"Iteration {iteration}: Injecting fallback search for safe genres "
                            f"(Pop/Rock from current year) to ensure minimum tracks"
                        )
                        # Add system message suggesting fallback
                        messages.append({
                            "role": "system",
                            "content": (
                                f"FALLBACK STRATEGY ACTIVATED: You have only discovered {len(discovered_track_ids)} tracks "
                                f"but need at least {min_tracks_needed}. The library may be limited or heavily filtered by exclusions. "
                                "IMMEDIATELY search for safe fallback tracks using these strategies:\n"
                                "1. search_tracks_by_genre(['Pop', 'Rock', 'Dance-Pop']) - broad popular genres\n"
                                "2. search_tracks(query='2025') - recent/current year tracks\n"
                                "3. search_tracks(query='') - random tracks from library\n"
                                "Once you have enough tracks (even if they don't perfectly match original criteria), "
                                "call submit_playlist with the BEST AVAILABLE tracks."
                            )
                        })

                # T110: Make API call with timing (no per-call timeout)
                llm_start_time = datetime.now()
                completion_kwargs["messages"] = messages  # type: ignore[arg-type]
                response: ChatCompletion = await self.client.chat.completions.create(**completion_kwargs)
                llm_duration = (datetime.now() - llm_start_time).total_seconds()
                total_llm_time += llm_duration

                logger.debug(f"LLM call took {llm_duration:.1f}s")

                # Track token usage
                if response.usage:
                    total_prompt_tokens += response.usage.prompt_tokens
                    total_completion_tokens += response.usage.completion_tokens

                # Extract response
                choice = response.choices[0]
                message = choice.message

                # T113: Debug logging for response structure
                logger.debug(f"Iteration {iteration}: finish_reason={choice.finish_reason}")
                logger.debug(f"Message has tool_calls: {bool(message.tool_calls)}")
                logger.debug(f"Message content length: {len(message.content or '')}")
                logger.debug(f"Message refusal: {getattr(message, 'refusal', None)}")

                # T116: Check if LLM hit context length limit - auto-submit discovered tracks
                if choice.finish_reason == 'length':
                    logger.warning(
                        f"CONTEXT LENGTH LIMIT HIT at iteration {iteration}! "
                        f"Discovered {len(discovered_track_ids)} tracks (need {min_tracks_needed} minimum). "
                        f"AUTO-SUBMITTING best available tracks."
                    )

                    # If we have enough tracks, auto-submit them
                    if len(discovered_track_ids) >= min_tracks_needed:
                        # Select tracks up to target count and convert to SelectedTrack objects
                        from .models.llm import SelectedTrack

                        # Build track metadata lookup from tool call results
                        track_metadata_map = {}
                        for tool_call in tool_calls_data:
                            if "result" in tool_call and isinstance(tool_call["result"], dict):
                                if "tracks" in tool_call["result"]:
                                    for track_data in tool_call["result"]["tracks"]:
                                        track_id = track_data.get("id")
                                        if track_id:
                                            track_metadata_map[track_id] = track_data

                        selected_track_objs = []
                        for position, track_id in enumerate(list(discovered_track_ids)[:request.target_track_count], start=1):
                            # Fetch metadata from tool call results
                            track_data = track_metadata_map.get(track_id, {})
                            selected_track_objs.append(SelectedTrack(
                                track_id=track_id,
                                position=position,
                                title=track_data.get("title", "Unknown"),
                                artist=track_data.get("artist", "Unknown"),
                                album=track_data.get("album", "Unknown Album"),
                                genre=track_data.get("genre", "Unknown"),
                                year=track_data.get("year", 2025),
                                bpm=track_data.get("bpm"),
                                duration_seconds=track_data.get("duration_seconds", 180),
                                country=track_data.get("country"),
                                selection_reason="Auto-selected due to context length limit"
                            ))

                        logger.info(
                            f"Context limit reached - auto-submitting {len(selected_track_objs)} "
                            f"discovered tracks (from {len(discovered_track_ids)} available)"
                        )

                        # Build response with discovered tracks
                        actual_cost = (
                            total_prompt_tokens * self.cost_per_input_token
                            + total_completion_tokens * self.cost_per_output_token
                        )
                        execution_time = (datetime.now() - start_time).total_seconds()
                        efficiency = (len(selected_track_objs) / total_tool_calls * 100) if total_tool_calls > 0 else 0

                        response_obj = LLMTrackSelectionResponse(
                            request_id=request.playlist_id,
                            selected_tracks=selected_track_objs,
                            tool_calls=tool_calls_data,
                            reasoning="Context limit reached during discovery. Auto-submitted best available tracks from library search.",
                            cost_usd=actual_cost,
                            execution_time_seconds=execution_time,
                        )

                        # Add metadata
                        if hasattr(response_obj, '__dict__'):
                            response_obj.__dict__.update({
                                "tool_calls_used": total_tool_calls,
                                "iterations_used": iteration,
                                "efficiency_percent": efficiency,
                                "stopped_early": True,
                                "stop_reason": "context_length_limit",
                                "total_tool_time_seconds": round(total_tool_time, 2),
                                "total_llm_time_seconds": round(total_llm_time, 2),
                                "tool_timeouts_count": tool_timeouts_count,
                                "slowest_tool": slowest_tool if slowest_tool["name"] else None,
                            })

                        return response_obj

                    else:
                        # Not enough tracks - inject fallback message
                        logger.error(
                            f"Only {len(discovered_track_ids)} tracks discovered (need {min_tracks_needed}). "
                            f"Triggering FALLBACK STRATEGY."
                        )
                        messages.append({
                            "role": "system",
                            "content": (
                                f"🚨 CRITICAL: CONTEXT LENGTH LIMIT REACHED! You MUST submit now.\n\n"
                                f"You have discovered {len(discovered_track_ids)} tracks. "
                                f"IMMEDIATELY call submit_playlist with these tracks. "
                                f"Do NOT search for more tracks. Do NOT continue discovery.\n\n"
                                f"Call: submit_playlist({{'selected_track_ids': [list of IDs from discovered tracks], "
                                f"'reasoning': 'Context limit reached, submitting available tracks'}})"
                            )
                        })
                        # Continue loop to give LLM one more chance to submit
                        continue

                # Check if LLM wants to call tools
                if message.tool_calls:
                    logger.info(f"LLM requested {len(message.tool_calls)} tool calls")

                    # Add assistant message with tool_calls to conversation
                    messages.append({
                        "role": "assistant",
                        "content": message.content,
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments
                                }
                            }
                            for tc in message.tool_calls
                        ]
                    })

                    # Execute each tool call
                    for tool_call in message.tool_calls:
                        total_tool_calls += 1
                        tool_name = tool_call.function.name

                        # Parse arguments (they come as JSON string)
                        try:
                            arguments = json.loads(tool_call.function.arguments)
                        except json.JSONDecodeError as e:
                            logger.error(f"Failed to parse tool arguments: {e}")
                            arguments = {}

                        logger.info(f"Executing tool: {tool_name} with args: {arguments}")

                        # T110: Execute tool with timeout
                        tool_start_time = datetime.now()
                        try:
                            tool_result = await asyncio.wait_for(
                                subsonic_tools.execute_tool(tool_name, arguments),
                                timeout=self.per_tool_timeout_seconds
                            )
                            tool_duration = (datetime.now() - tool_start_time).total_seconds()
                            result_str = json.dumps(tool_result)
                            logger.info(f"Tool {tool_name} completed in {tool_duration:.2f}s, returned {len(result_str)} chars")

                        except asyncio.TimeoutError:
                            tool_duration = (datetime.now() - tool_start_time).total_seconds()
                            tool_timeouts_count += 1
                            logger.warning(
                                f"Tool {tool_name} exceeded timeout ({self.per_tool_timeout_seconds}s) "
                                f"after {tool_duration:.2f}s. Returning error to LLM."
                            )
                            tool_result = {
                                "error": "timeout",
                                "message": f"Tool {tool_name} exceeded {self.per_tool_timeout_seconds}s timeout",
                                "suggestion": "Try simplifying the query or reducing the limit parameter"
                            }
                            result_str = json.dumps(tool_result)

                        except Exception as e:
                            tool_duration = (datetime.now() - tool_start_time).total_seconds()
                            logger.error(f"Tool {tool_name} execution failed after {tool_duration:.2f}s: {e}")
                            tool_result = {
                                "error": "execution_failed",
                                "message": str(e),
                                "suggestion": "Check tool arguments or try a different approach"
                            }
                            result_str = json.dumps(tool_result)

                        # T110: Track timing metrics
                        total_tool_time += tool_duration
                        if tool_duration > slowest_tool["duration"]:
                            slowest_tool = {"name": tool_name, "duration": tool_duration}

                        # Record tool call for response metadata
                        tool_calls_data.append({
                            "tool_name": tool_name,
                            "arguments": arguments,
                            "result": tool_result,
                        })

                        # T115: Track discovered track IDs from search tools
                        if tool_name in ["search_tracks", "search_tracks_by_genre", "get_newly_added_tracks", "get_artist_tracks"]:
                            if isinstance(tool_result, dict) and "tracks" in tool_result:
                                for track in tool_result["tracks"]:
                                    if isinstance(track, dict) and "id" in track:
                                        discovered_track_ids.add(track["id"])
                                logger.debug(f"Discovered {len(tool_result['tracks'])} tracks, total unique: {len(discovered_track_ids)}")

                        # T113: Check if this is the submit_playlist tool (signals completion)
                        # Only accept if status is "playlist_submitted" (not "rejected")
                        if tool_name == "submit_playlist":
                            if tool_result.get("status") == "playlist_submitted":
                                logger.info(
                                    f"LLM submitted playlist via tool call: "
                                    f"{len(tool_result.get('selected_track_ids', []))} tracks"
                                )
                            elif tool_result.get("status") == "rejected":
                                logger.warning(
                                    f"Playlist submission rejected: {tool_result.get('message', 'Unknown reason')}. "
                                    "LLM will retry with valid track IDs."
                                )
                                # Add rejection message to conversation and continue loop
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": tool_call.id,
                                    "content": json.dumps(tool_result)
                                })
                                # Continue to next iteration - don't process this as completion
                                continue
                            else:
                                logger.warning(f"Unexpected submit_playlist status: {tool_result.get('status')}")
                                # Continue conversation
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": tool_call.id,
                                    "content": json.dumps(tool_result)
                                })
                                continue

                            # Extract tracks from tool result (only reached if status == "playlist_submitted")
                            selected_track_ids = tool_result.get("selected_track_ids", [])
                            reasoning = tool_result.get("reasoning", "No reasoning provided")

                            # Calculate actual cost
                            actual_cost = (
                                total_prompt_tokens * self.cost_per_input_token
                                + total_completion_tokens * self.cost_per_output_token
                            )

                            # Calculate execution time
                            execution_time = (datetime.now() - start_time).total_seconds()

                            # Calculate efficiency metrics
                            efficiency = (len(selected_track_ids) / total_tool_calls * 100) if total_tool_calls > 0 else 0

                            logger.info(
                                f"LLM call completed for playlist {request.playlist_id}: "
                                f"{len(selected_track_ids)} tracks selected, "
                                f"{total_tool_calls} tool calls ({iteration} iterations), "
                                f"efficiency: {efficiency:.1f}%, "
                                f"${actual_cost:.6f} cost, "
                                f"{execution_time:.2f}s execution time"
                            )

                            # Build and return response
                            response_obj = LLMTrackSelectionResponse(
                                request_id=request.playlist_id,
                                selected_tracks=selected_track_ids,
                                tool_calls=tool_calls_data,
                                reasoning=reasoning[:2000],  # Limit to 2000 chars
                                cost_usd=actual_cost,
                                execution_time_seconds=execution_time,
                            )

                            # Add metadata
                            if hasattr(response_obj, '__dict__'):
                                response_obj.__dict__.update({
                                    "tool_calls_used": total_tool_calls,
                                    "iterations_used": iteration,
                                    "efficiency_percent": efficiency,
                                    "stopped_early": False,  # Completed via submit_playlist
                                    "total_tool_time_seconds": round(total_tool_time, 2),
                                    "total_llm_time_seconds": round(total_llm_time, 2),
                                    "tool_timeouts_count": tool_timeouts_count,
                                    "slowest_tool": slowest_tool if slowest_tool["name"] else None,
                                })

                            return response_obj

                        # Add tool result message to conversation (for non-submit_playlist tools)
                        # submit_playlist rejected/unknown status already handled above with continue
                        if tool_name != "submit_playlist":
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": result_str
                            })

                    # T109: Track progress for early stopping
                    # Count tracks found in this iteration (rough estimate from tool results)
                    tracks_this_iter = sum(
                        tc["result"].get("count", 0)
                        for tc in tool_calls_data[-len(message.tool_calls):]
                        if isinstance(tc.get("result"), dict)
                    )
                    tracks_found_history.append(tracks_this_iter)

                    # T109: Early stopping if no progress for N iterations
                    if len(tracks_found_history) >= no_progress_threshold:
                        recent_progress = tracks_found_history[-no_progress_threshold:]
                        if all(count == 0 for count in recent_progress):
                            logger.warning(
                                f"No progress in last {no_progress_threshold} iterations. "
                                f"Stopping early at iteration {iteration}/{max_iterations}."
                            )
                            # Break to final response parsing
                            break

                    # Continue conversation loop to let LLM process tool results
                    continue

                else:
                    # No more tool calls - LLM has finished
                    logger.info(f"LLM conversation complete after {iteration} turns, {total_tool_calls} tool calls")

                    # BUGFIX: Check if we have a submit_playlist attempt in tool_calls_data
                    # If the last submit_playlist was rejected, we should provide helpful error
                    last_submit = None
                    for tc in reversed(tool_calls_data):
                        if tc.get("tool_name") == "submit_playlist":
                            last_submit = tc
                            break

                    if last_submit and last_submit.get("result", {}).get("status") == "rejected":
                        error_msg = last_submit["result"].get("message", "Unknown rejection reason")
                        logger.error(
                            f"LLM's last submit_playlist attempt was rejected: {error_msg}. "
                            f"No valid playlist was submitted."
                        )
                        raise ValueError(
                            f"Playlist generation failed: LLM's submit_playlist was rejected - {error_msg}"
                        )

                    # Parse selected tracks from final response
                    selected_tracks = self._parse_tracks_from_response(
                        message.content or "", request.target_track_count
                    )

                    # Calculate actual cost including all conversation turns
                    actual_cost = (
                        total_prompt_tokens * self.cost_per_input_token
                        + total_completion_tokens * self.cost_per_output_token
                    )

                    # Calculate execution time
                    execution_time = (datetime.now() - start_time).total_seconds()

                    # T109: Calculate efficiency metrics
                    efficiency = (len(selected_tracks) / total_tool_calls * 100) if total_tool_calls > 0 else 0
                    stopped_early = iteration < max_iterations and len(tracks_found_history) >= no_progress_threshold

                    logger.info(
                        f"LLM call completed for playlist {request.playlist_id}: "
                        f"{len(selected_tracks)} tracks selected, "
                        f"{total_tool_calls} tool calls ({iteration} iterations), "
                        f"efficiency: {efficiency:.1f}%, "
                        f"${actual_cost:.6f} cost, "
                        f"{execution_time:.2f}s execution time"
                        + (" [STOPPED EARLY]" if stopped_early else "")
                    )

                    # T109: Add metadata to response for monitoring
                    response_obj = LLMTrackSelectionResponse(
                        request_id=request.playlist_id,
                        selected_tracks=selected_tracks,
                        tool_calls=tool_calls_data,
                        reasoning=(message.content or "No reasoning provided")[:2000],  # Limit to 2000 chars
                        cost_usd=actual_cost,
                        execution_time_seconds=execution_time,
                    )

                    # Add T109 + T110 metadata (if response object supports it via dict assignment)
                    if hasattr(response_obj, '__dict__'):
                        response_obj.__dict__.update({
                            "tool_calls_used": total_tool_calls,
                            "iterations_used": iteration,
                            "efficiency_percent": efficiency,
                            "stopped_early": stopped_early,
                            # T110: Timing metrics
                            "total_tool_time_seconds": round(total_tool_time, 2),
                            "total_llm_time_seconds": round(total_llm_time, 2),
                            "tool_timeouts_count": tool_timeouts_count,
                            "slowest_tool": slowest_tool if slowest_tool["name"] else None,
                        })

                    return response_obj

            # If we hit max iterations without finishing
            logger.warning(f"LLM conversation hit max iterations ({max_iterations})")
            raise Exception(f"LLM conversation exceeded maximum iterations ({max_iterations})")


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

    def _parse_track_selection_response(self, content: str) -> Dict[str, Any]:
        """
        T108: Parse track selection response with JSON-first approach.

        Attempts JSON parsing first, falls back to regex if JSON parsing fails.

        Args:
            content: LLM response content

        Returns:
            Dict with:
                - track_ids: List[str] - Track IDs selected
                - reasoning: str - LLM's reasoning (optional)
                - parse_method: str - "json" or "regex_fallback"
                - original_content_snippet: str - First 200 chars (for debugging)
        """
        import re
        import json

        result = {
            "track_ids": [],
            "reasoning": "",
            "parse_method": "unknown",
            "original_content_snippet": content[:200] if content else ""
        }

        # Strategy 1: Try JSON parsing first
        try:
            # Remove markdown code fences if present
            json_content = content
            json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', content, re.DOTALL)
            if json_match:
                json_content = json_match.group(1).strip()

            # Parse JSON
            data = json.loads(json_content)

            # Extract track IDs (handle both "selected_track_ids" and variations)
            track_ids = data.get("selected_track_ids") or data.get("track_ids") or data.get("tracks") or []

            # Coerce to strings and deduplicate
            track_ids = [str(tid) for tid in track_ids if tid is not None]
            track_ids = list(dict.fromkeys(track_ids))  # Deduplicate while preserving order

            result["track_ids"] = track_ids
            result["reasoning"] = data.get("reasoning", "")
            result["parse_method"] = "json"

            logger.debug(f"JSON parsing successful: {len(track_ids)} tracks found")
            return result

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.debug(f"JSON parsing failed: {e}, falling back to regex")

        # Strategy 2: Regex fallback for legacy format
        track_ids = []

        # Pattern 1: Look for "Track ID: <id>"
        track_id_pattern = re.compile(r'Track\s+ID[:\s]+["\']?(\S+?)["\']?(?:\s|$)', re.IGNORECASE)

        # Pattern 2: Look for numbered list with IDs
        numbered_pattern = re.compile(r'^\s*\d+\.\s*(?:Track\s+ID[:\s]+)?["\']?(\S+?)["\']?', re.IGNORECASE)

        # Pattern 3: Look for just IDs at start of lines
        id_only_pattern = re.compile(r'^\s*([a-zA-Z0-9-]+)\s*[-:\|]')

        for line in content.split('\n'):
            match = track_id_pattern.search(line)
            if not match:
                match = numbered_pattern.match(line)
            if not match:
                match = id_only_pattern.match(line)

            if match:
                track_id = match.group(1).strip('"\'')
                track_ids.append(track_id)

        # Deduplicate
        track_ids = list(dict.fromkeys(track_ids))

        result["track_ids"] = track_ids
        result["reasoning"] = content[:500]  # Use first 500 chars as reasoning
        result["parse_method"] = "regex_fallback"

        logger.debug(f"Regex parsing: {len(track_ids)} tracks found")
        return result

    def _parse_tracks_from_response(self, content: str, target_count: int) -> List[SelectedTrack]:
        """
        Parse selected tracks from LLM response content.

        Uses _parse_track_selection_response for JSON/regex parsing,
        then enriches track data from tool call results.

        Args:
            content: LLM response content.
            target_count: Expected number of tracks.

        Returns:
            List of SelectedTrack objects.
        """
        from .models.llm import SelectedTrack

        # T108: Use new JSON-first parsing
        parsed = self._parse_track_selection_response(content)
        track_ids = parsed["track_ids"]

        if not track_ids:
            logger.warning(f"No track IDs found in LLM response (method: {parsed['parse_method']})")
            return []

        logger.info(f"Parsed {len(track_ids)} track IDs using {parsed['parse_method']} method")

        # Enrich track data - for now, create basic SelectedTrack objects
        # In the future, we could look up full metadata from tool call results
        tracks = []
        for position, track_id in enumerate(track_ids, start=1):
            track = SelectedTrack(
                track_id=track_id,
                position=position,
                title="Unknown",  # Will be enriched later
                artist="Unknown",
                album="Unknown Album",
                genre="Unknown",
                year=2024,
                bpm=None,
                duration_seconds=180,
                country=None,
                selection_reason=parsed["reasoning"][:200] if parsed["reasoning"] else "Selected by LLM"
            )
            tracks.append(track)

            if len(tracks) >= target_count:
                break

        logger.info(f"Parsed {len(tracks)} tracks from LLM response (target: {target_count})")

        if len(tracks) == 0:
            logger.warning(
                "Failed to parse any tracks from LLM response. "
                "Response content preview: " + content[:500]
            )

        return tracks

    async def generate_playlist(
        self,
        spec: PlaylistSpecification,
        subsonic_client: SubsonicClient,
        cost_manager: Optional[CostManager] = None,
        decision_logger: Optional[DecisionLogger] = None,
        used_track_ids: Optional[set] = None,
    ) -> Playlist:
        """
        Main orchestrator method for playlist generation.

        Orchestrates the complete playlist generation workflow:
        1. Extract track selection criteria from spec
        2. Create SubsonicTools instance from client
        3. Call LLM to select tracks (with tool execution loop)
        4. Create SelectedTrack objects from LLM response
        5. Validate playlist
        6. Track costs
        7. Log decisions
        8. Handle errors and budget constraints

        Args:
            spec: Playlist specification with criteria and constraints
            subsonic_client: Configured SubsonicClient for tool execution
            cost_manager: Optional cost manager (creates new if None)
            decision_logger: Optional decision logger (creates new if None)

        Returns:
            Complete Playlist object with tracks, validation, and metadata

        Raises:
            BudgetExceededError: If hard budget limit is exceeded
            TimeoutError: If LLM call exceeds timeout
            Exception: If LLM call or validation fails
        """
        start_time = datetime.now()

        # Initialize cost manager and decision logger if not provided
        if cost_manager is None:
            cost_manager = CostManager(
                total_budget=spec.cost_budget_allocated or Decimal("25.00"),
                budget_mode="hard",  # Default to hard mode for safety
                allocation_strategy="equal"
            )

        if decision_logger is None:
            decision_logger = DecisionLogger()

        logger.info(
            f"Starting playlist generation for '{spec.name}' "
            f"(target: {spec.target_track_count_min}-{spec.target_track_count_max} tracks)"
        )

        try:
            # 1. Create SubsonicTools instance from client
            subsonic_tools = SubsonicTools(subsonic_client)
            logger.info("Created SubsonicTools instance for LLM tool calling")

            # 2. Create LLM track selection request from spec (with exclusion list)
            request = self.create_selection_request(spec, used_track_ids)

            # 3. Estimate and check cost before calling LLM
            estimated_cost = self.estimate_cost(request)
            logger.info(f"Estimated LLM cost: ${estimated_cost:.6f}")

            # Check if we have budget for this request
            if cost_manager.budget_mode.value == "hard":
                remaining_budget = cost_manager.get_remaining_budget()
                if Decimal(str(estimated_cost)) > remaining_budget:
                    raise BudgetExceededError(
                        f"Estimated cost ${estimated_cost:.6f} exceeds remaining budget ${remaining_budget:.2f}"
                    )

            # 4. Call LLM to select tracks (with SubsonicTools for dynamic querying)
            llm_response = await self.call_llm(request, subsonic_tools)

            # 5. Record actual cost
            actual_cost = Decimal(str(llm_response.cost_usd))
            try:
                cost_manager.record_cost(actual_cost, spec.id)
                logger.info(f"Recorded cost: ${actual_cost:.6f}")
            except BudgetExceededError as e:
                # In hard mode, this will be raised
                if cost_manager.budget_mode.value == "hard":
                    logger.error(f"Budget exceeded during generation: {e}")
                    raise
                # In suggested mode, just log warning
                logger.warning(f"Budget exceeded (suggested mode): {e}")

            # 6. Convert LLM response tracks to SelectedTrack objects with proper format
            # Map from LLM response format to core.SelectedTrack format
            from .models.core import SelectedTrack as CoreSelectedTrack
            from .models.core import ValidationStatus
            from .models.core import Playlist as CorePlaylist  # Import early for padding

            # T113: Build track metadata lookup from tool call results
            # When submit_playlist is used, selected_tracks is a list of track IDs (strings)
            # We need to fetch metadata from the tool_calls_data
            track_metadata_map = {}
            for tool_call in llm_response.tool_calls:
                if "result" in tool_call and "tracks" in tool_call.get("result", {}):
                    for track_data in tool_call["result"]["tracks"]:
                        track_id = track_data.get("id")
                        if track_id:
                            track_metadata_map[track_id] = track_data

            selected_tracks: List[CoreSelectedTrack] = []
            for idx, llm_track in enumerate(llm_response.selected_tracks):
                # T113: Handle both string IDs (from submit_playlist) and objects (old path)
                if isinstance(llm_track, str):
                    # Track ID string from submit_playlist tool
                    track_id = llm_track
                    # Fetch metadata from tool call results
                    track_data = track_metadata_map.get(track_id, {})
                    core_track = CoreSelectedTrack(
                        track_id=track_id,
                        title=track_data.get("title", "Unknown"),
                        artist=track_data.get("artist", "Unknown"),
                        album=track_data.get("album", "Unknown Album"),
                        duration_seconds=track_data.get("duration_seconds", 180),
                        is_australian=False,  # TODO: Determine from artist metadata
                        rotation_category="Medium",
                        position_in_playlist=idx,
                        selection_reasoning=llm_response.reasoning[:200] if hasattr(llm_response, 'reasoning') else "Selected by LLM",
                        validation_status=ValidationStatus.PASS,
                        metadata_source="subsonic_tools",
                        bpm=track_data.get("bpm"),
                        genre=track_data.get("genre", "Unknown"),
                        year=track_data.get("year", 2024),
                    )
                else:
                    # Old path: full track object with attributes
                    core_track = CoreSelectedTrack(
                        track_id=llm_track.track_id,
                        title=llm_track.title,
                        artist=llm_track.artist,
                        album=llm_track.album,
                        duration_seconds=llm_track.duration_seconds,
                        is_australian=(llm_track.country or "").upper() == "AU",
                        rotation_category="Medium",  # Default rotation category
                        position_in_playlist=idx,
                        selection_reasoning=llm_track.selection_reason,
                        validation_status=ValidationStatus.PASS,  # Will be updated by validator
                        metadata_source="llm",
                        bpm=llm_track.bpm,
                    genre=llm_track.genre,
                    year=llm_track.year,
                    country=llm_track.country,
                    validation_notes=[]
                )
                selected_tracks.append(core_track)

            logger.info(f"Converted {len(selected_tracks)} LLM tracks to SelectedTrack objects")

            # 6.5. Check duration and pad if necessary
            current_duration = sum(t.duration_seconds for t in selected_tracks)
            target_duration_minutes = spec.target_duration_minutes
            required_duration = target_duration_minutes * 60 * 0.90  # 90% minimum

            if current_duration < required_duration:
                logger.warning(
                    f"Playlist duration {current_duration/60:.1f}min is below minimum "
                    f"{required_duration/60:.1f}min. Padding with additional tracks..."
                )

                # Import padding function
                from .duration_padding import pad_playlist_to_duration

                # Create temporary playlist for padding
                temp_playlist = CorePlaylist(
                    id=spec.id,
                    name=spec.name,
                    specification_id=spec.id,
                    tracks=selected_tracks,
                    validation_result=None,  # Not validated yet
                    created_at=datetime.now(),
                    cost_actual=Decimal("0"),
                    generation_time_seconds=0,
                    constraint_relaxations=[]
                )

                # Pad playlist
                padded_playlist = await pad_playlist_to_duration(
                    temp_playlist,
                    spec,
                    subsonic_client,
                    used_track_ids or set()
                )

                # Update selected_tracks with padded version
                selected_tracks = padded_playlist.tracks
                logger.info(f"Playlist padded to {len(selected_tracks)} tracks")

            # 7. Validate playlist
            validation_result = validate_playlist(selected_tracks, spec.track_selection_criteria)

            logger.info(
                f"Validation result: {validation_result.overall_status.value}, "
                f"compliance: {validation_result.compliance_percentage:.1%}"
            )

            # 8. Log decision
            try:
                decision_logger.log_decision(
                    decision_type="track_selection",
                    playlist_name=spec.name,
                    criteria={
                        "bpm_ranges": str(spec.track_selection_criteria.bpm_ranges),
                        "genre_mix": str(spec.track_selection_criteria.genre_mix),
                        "era_distribution": str(spec.track_selection_criteria.era_distribution),
                        "australian_min": str(spec.track_selection_criteria.australian_content_min),
                    },
                    selected_tracks=[
                        {
                            "track_id": t.track_id,
                            "title": t.title,
                            "artist": t.artist,
                            "bpm": str(t.bpm) if t.bpm else "None",
                            "genre": t.genre or "None",
                        }
                        for t in selected_tracks
                    ],
                    validation_result={
                        "overall_status": validation_result.overall_status.value,
                        "compliance": validation_result.compliance_percentage,
                    },
                    metadata={
                        "playlist_id": spec.id,
                        "llm_cost": str(actual_cost),
                        "execution_time_ms": int(llm_response.execution_time_seconds * 1000),
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to log decision: {e}")

            # 9. Calculate execution time
            execution_time = (datetime.now() - start_time).total_seconds()

            # 10. Create and return Playlist object (using core.Playlist)
            # CorePlaylist already imported at top of function

            playlist = CorePlaylist(
                id=spec.id,
                name=spec.name,
                specification_id=spec.id,
                tracks=selected_tracks,
                validation_result=validation_result,
                created_at=datetime.now(),
                cost_actual=actual_cost,
                generation_time_seconds=execution_time,
                constraint_relaxations=[]  # No relaxations in initial implementation
            )

            logger.info(
                f"Playlist generation complete: {len(selected_tracks)} tracks, "
                f"${actual_cost:.6f} cost, {execution_time:.2f}s execution time"
            )

            return playlist

        except BudgetExceededError:
            # Re-raise budget errors
            raise

        except TimeoutError:
            # Re-raise timeout errors
            raise

        except Exception as e:
            # Log error and re-raise
            logger.error(f"Playlist generation failed: {e}", exc_info=True)

            # Try to log error decision
            try:
                if decision_logger:
                    import traceback
                    decision_logger.log_decision(
                        decision_type="error",
                        playlist_name=spec.name,
                        criteria={},
                        selected_tracks=[],
                        validation_result={},
                        metadata={
                            "playlist_id": spec.id,
                            "error_message": str(e),
                            "error_type": type(e).__name__,
                            "traceback": traceback.format_exc(),
                        }
                    )
            except Exception as log_error:
                logger.warning(f"Failed to log error: {log_error}")

            raise


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
