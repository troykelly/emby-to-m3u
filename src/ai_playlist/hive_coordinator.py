"""
Claude Flow Hive Coordinator - Multi-Agent Playlist Automation

Orchestrates parser, planner, and selector agents via Claude Flow memory namespace.
Implements mesh topology for peer-to-peer coordination across batch track selection.

**T027 Implementation**: spawn_playlist_agents() function for agent coordination.
"""

import logging
from typing import List
from .models import PlaylistSpec

logger = logging.getLogger(__name__)


def spawn_playlist_agents(specs: List[PlaylistSpec]) -> None:
    """
    Spawn coordinated agents for playlist generation workflow.

    Agents communicate via Claude Flow memory namespace 'ai-playlist/':
    - Parser agent: Parse station-identity.md → DaypartSpecs
    - Planner agent: Generate PlaylistSpecs from DaypartSpecs
    - Selector agents: Parallel track selection (one per playlist)

    Args:
        specs: List of PlaylistSpec objects to process

    Workflow:
        1. Parser agent reads station-identity.md and stores daypart analysis
        2. Planner agent generates PlaylistSpecs from parsed dayparts
        3. Selector agents execute parallel track selection (mesh coordination)
        4. All agents use memory namespace 'ai-playlist/' for shared context

    Memory Keys Used:
        - ai-playlist/station-identity-analysis: Programming document structure
        - ai-playlist/playlist-naming-schema: Naming convention rules
        - ai-playlist/llm-workflow-requirements: LLM integration patterns
        - ai-playlist/constraint-relaxation-rules: Constraint hierarchy
        - ai-playlist/validation-thresholds: Quality requirements
        - ai-playlist/parser/dayparts: Parsed daypart specifications
        - ai-playlist/planner/specs: Generated playlist specifications
        - ai-playlist/selector/{playlist_id}/progress: Track selection progress

    Note:
        This function defines the coordination strategy. Actual agent execution
        happens via Claude Code's Task tool or batch_executor.py for parallel
        track selection. See CLAUDE.md for execution patterns.
    """
    logger.info(f"Spawning hive coordination for {len(specs)} playlists via ai-playlist/ namespace")

    # Agent coordination architecture (see CLAUDE.md for execution pattern):
    #
    # [Parser Agent] → ai-playlist/parser/dayparts
    #         ↓
    # [Planner Agent] → ai-playlist/planner/specs
    #         ↓
    # [Selector Agent 1] ←→ [Selector Agent 2] ←→ ... ←→ [Selector Agent N]
    #         ↓                    ↓                            ↓
    # ai-playlist/selector/    ai-playlist/selector/    ai-playlist/selector/
    #    {spec_1_id}/            {spec_2_id}/            {spec_n_id}/

    # Phase 1: Document Parser Agent
    # Responsibility: Parse plain-language station-identity.md into structured DaypartSpecs
    # Memory writes: ai-playlist/parser/dayparts
    # Depends on: ai-playlist/station-identity-analysis (reference data)
    logger.debug("Phase 1: Document parser agent - parses station-identity.md")

    # Phase 2: Playlist Planner Agent
    # Responsibility: Generate PlaylistSpec objects from DaypartSpecs
    # Memory reads: ai-playlist/parser/dayparts
    # Memory writes: ai-playlist/planner/specs
    # Depends on: ai-playlist/playlist-naming-schema (naming rules)
    logger.debug("Phase 2: Playlist planner agent - generates playlist specifications")

    # Phase 3: Track Selector Agents (Parallel Execution)
    # Responsibility: LLM-based track selection with constraint satisfaction
    # Memory reads: ai-playlist/llm-workflow-requirements, constraint-relaxation-rules
    # Memory writes: ai-playlist/selector/{playlist_id}/progress
    # Coordination: Mesh topology for peer-to-peer communication
    # Parallelism: Up to 10 concurrent selector agents (see batch_executor.py)
    logger.debug(f"Phase 3: Track selector agents - {len(specs)} parallel tasks via mesh topology")

    for i, spec in enumerate(specs, start=1):
        logger.debug(
            f"  Selector agent {i}/{len(specs)}: playlist_id={spec.id}, "
            f"name={spec.name}, tracks_needed={spec.target_duration_minutes // 3}"
        )

    # Hive coordination complete - agent execution happens via:
    # - Claude Code Task tool for sequential operations (parser, planner)
    # - batch_executor.py for parallel track selection (up to 10 concurrent)
    logger.info(
        "Hive coordination strategy defined. Execute via Task tool (CLAUDE.md) "
        "or batch_executor.execute_batch_selection()"
    )
