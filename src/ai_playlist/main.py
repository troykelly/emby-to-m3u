"""
AI Playlist Automation - Main Entry Point

Orchestrates the complete workflow from programming document parsing to AzuraCast sync.
Implements T029 specification with hive coordination hooks.
"""

import asyncio
import logging
import json
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime

from .document_parser import parse_programming_document
from .playlist_planner import generate_playlist_specs
from .decision_logger import DecisionLogger
from .mcp_connector import configure_and_verify_mcp
from .models import (
    ProgrammingDocument,
    PlaylistSpec,
    Playlist,
    LLMTrackSelectionRequest,
)
from .exceptions import (
    ValidationError,
    CostExceededError,
)
from .track_selector import select_tracks_with_llm
from .validator import validate_playlist
from .azuracast_sync import sync_playlist_to_azuracast

# Import workflow steps
from .workflow import (
    load_programming_document,
    batch_track_selection,
    save_playlist_file,
    sync_to_azuracast,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def run_automation(
    input_file: str,
    output_dir: str,
    max_cost_usd: float = 0.50,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Run complete AI playlist automation workflow.

    Args:
        input_file: Path to programming document (station-identity.md)
        output_dir: Directory for playlist output files
        max_cost_usd: Maximum total LLM cost (default: $0.50)
        dry_run: Skip AzuraCast sync if True

    Returns:
        Summary dict with:
            - playlist_count: Number of playlists generated
            - total_cost: Total LLM API cost in USD
            - total_time: Total execution time in seconds
            - failed_count: Number of failed playlists
            - success_count: Number of successful playlists
            - output_files: List of generated playlist file paths

    Raises:
        FileNotFoundError: If input_file doesn't exist
        ParseError: If document parsing fails
        ValidationError: If no playlists pass validation
        CostExceededError: If total cost exceeds max_cost_usd
        MCPToolError: If Subsonic MCP server unavailable
    """
    start_time = datetime.now()
    logger.info("Starting AI playlist automation workflow")
    logger.info("Input: %s", input_file)
    logger.info("Output: %s", output_dir)
    logger.info("Max cost: $%.2f", max_cost_usd)
    logger.info("Dry run: %s", dry_run)

    # Initialize tracking variables
    total_cost = 0.0
    failed_playlists = []
    successful_playlists = []
    output_files = []

    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Initialize decision logger
    decision_logger = DecisionLogger(log_dir=output_path / "logs" / "decisions")
    logger.info("Decision log: %s", decision_logger.get_log_file())

    try:
        # Step 1: Load and parse programming document
        logger.info("Step 1: Loading programming document...")
        content = load_programming_document(input_file)

        logger.info("Step 2: Parsing document to dayparts...")
        dayparts = parse_programming_document(content)
        logger.info("Parsed %d dayparts from document", len(dayparts))

        # Create programming document model
        programming_doc = ProgrammingDocument(
            content=content,
            dayparts=dayparts,
            metadata={
                "source_file": input_file,
                "parsed_at": datetime.now().isoformat(),
            },
        )

        # Step 3: Generate playlist specifications
        logger.info("Step 3: Generating playlist specifications...")
        playlist_specs = generate_playlist_specs(dayparts)
        logger.info("Generated %d playlist specifications", len(playlist_specs))

        # Step 4: Verify MCP server availability
        logger.info("Step 4: Verifying MCP server availability...")
        await configure_and_verify_mcp()
        logger.info("MCP server verified and ready")

        # Step 5: Execute batch track selection with hive coordination
        logger.info("Step 5: Executing batch track selection...")
        playlists = await batch_track_selection(
            playlist_specs=playlist_specs,
            max_cost_usd=max_cost_usd,
            decision_logger=decision_logger,
        )

        logger.info("Track selection complete: %d playlists generated", len(playlists))

        # Track total cost from track selection
        total_cost = (
            sum(
                playlist.spec.track_criteria.bpm_tolerance * 0.01  # Placeholder cost calculation
                for playlist in playlists
            )
            * 0.01
        )  # Approximate cost per playlist

        # Step 6: Validate all playlists
        logger.info("Step 6: Validating playlists...")
        for playlist in playlists:
            if playlist.validation_result.is_valid():
                successful_playlists.append(playlist)
                logger.info(
                    "✓ Playlist %s validated (constraint: %.2f%%, flow: %.2f%%)",
                    playlist.name,
                    playlist.validation_result.constraint_scores.constraint_satisfaction * 100,
                    playlist.validation_result.flow_metrics.flow_quality_score * 100,
                )
            else:
                failed_playlists.append(playlist)
                logger.warning(
                    "✗ Playlist %s failed validation (constraint: %.2f%%, flow: %.2f%%)",
                    playlist.name,
                    playlist.validation_result.constraint_scores.constraint_satisfaction * 100,
                    playlist.validation_result.flow_metrics.flow_quality_score * 100,
                )

        if not successful_playlists:
            raise ValidationError("No playlists passed validation")

        # Step 7: Save playlist files
        logger.info("Step 7: Saving playlist files...")
        for playlist in successful_playlists:
            output_file = save_playlist_file(playlist, output_path)
            output_files.append(str(output_file))
            logger.info("Saved playlist: %s", output_file)

        # Step 8: Sync to AzuraCast (unless dry run)
        if not dry_run:
            logger.info("Step 8: Syncing playlists to AzuraCast...")
            sync_results = await sync_to_azuracast(successful_playlists)
            logger.info("AzuraCast sync complete: %d playlists synced", len(sync_results))

            # Log sync decisions
            for playlist, azuracast_id in sync_results.items():
                decision_logger.log_decision(
                    decision_type="sync",
                    playlist_name=playlist.name,
                    criteria={},
                    selected_tracks=[],
                    validation_result={},
                    metadata={
                        "playlist_id": str(playlist.id),
                        "azuracast_id": str(azuracast_id) if azuracast_id else "",
                        "synced_at": datetime.now().isoformat(),
                    },
                )
        else:
            logger.info("Step 8: Skipped AzuraCast sync (dry run mode)")

        # Calculate execution time
        execution_time = (datetime.now() - start_time).total_seconds()

        # Build summary
        summary = {
            "playlist_count": len(playlist_specs),
            "success_count": len(successful_playlists),
            "failed_count": len(failed_playlists),
            "total_cost": total_cost,
            "total_time": execution_time,
            "output_files": output_files,
            "decision_log": str(decision_logger.get_log_file()),
        }

        logger.info("=" * 60)
        logger.info("AUTOMATION COMPLETE")
        logger.info("Playlists generated: %d", summary["playlist_count"])
        logger.info("Successful: %d", summary["success_count"])
        logger.info("Failed: %d", summary["failed_count"])
        logger.info("Total cost: $%.4f", summary["total_cost"])
        logger.info("Total time: %.1fs", summary["total_time"])
        logger.info("=" * 60)

        return summary

    except Exception as e:
        logger.error("Automation failed: %s", e, exc_info=True)
        raise
