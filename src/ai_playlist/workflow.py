"""
AI Playlist Workflow Steps - Extracted from main.py

This module contains the individual workflow step functions for playlist automation,
separated from the main orchestration logic for better modularity.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime
import json

from .track_selector import select_tracks_with_llm
from .validator import validate_playlist
from .decision_logger import DecisionLogger
from .azuracast_sync import sync_playlist_to_azuracast, AzuraCastPlaylistSyncError
from .models import (
    PlaylistSpec,
    LLMTrackSelectionRequest,
    Playlist,
)
from .exceptions import CostExceededError

logger = logging.getLogger(__name__)


def load_programming_document(file_path: str) -> str:
    """
    Load programming document content from file.

    Args:
        file_path: Path to programming document

    Returns:
        Document content as string

    Raises:
        FileNotFoundError: If file doesn't exist
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Programming document not found: {file_path}")

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    if not content or not content.strip():
        raise ValueError(f"Programming document is empty: {file_path}")

    return content


async def batch_track_selection(
    playlist_specs: List[PlaylistSpec],
    max_cost_usd: float,
    decision_logger: DecisionLogger,
) -> List[Playlist]:
    """
    Execute batch track selection for all playlists using hive coordination.

    Args:
        playlist_specs: List of playlist specifications
        max_cost_usd: Maximum total cost for all playlists
        decision_logger: Logger for decision audit trail

    Returns:
        List of validated playlists

    Raises:
        CostExceededError: If total cost exceeds max_cost_usd
    """
    playlists = []
    total_cost = 0.0
    cost_per_playlist = max_cost_usd / len(playlist_specs)

    logger.info("Batch track selection: %d playlists", len(playlist_specs))
    logger.info("Budget per playlist: $%.4f", cost_per_playlist)

    for i, spec in enumerate(playlist_specs, 1):
        logger.info("Processing playlist %d/%d: %s", i, len(playlist_specs), spec.name)

        try:
            # Calculate target track count based on duration and tracks per hour
            duration_hours = spec.target_duration_minutes / 60.0
            target_track_count = int(spec.daypart.tracks_per_hour * duration_hours)

            # Build LLM track selection request
            request = LLMTrackSelectionRequest(
                playlist_id=spec.id,
                criteria=spec.track_criteria,
                target_track_count=target_track_count,
                max_cost_usd=cost_per_playlist,
                timeout_seconds=60,
            )

            # Execute track selection with LLM
            response = await select_tracks_with_llm(request)

            # Track cost
            total_cost += response.cost_usd
            if total_cost > max_cost_usd:
                raise CostExceededError(
                    f"Total cost ${total_cost:.4f} exceeds budget ${max_cost_usd:.4f}"
                )

            logger.info(
                f"Selected {len(response.selected_tracks)} tracks "
                f"(cost: ${response.cost_usd:.4f}, time: {response.execution_time_seconds:.1f}s)"
            )

            # Validate playlist
            validation_result = validate_playlist(
                tracks=response.selected_tracks,
                criteria=spec.track_criteria,
            )

            # Create playlist object
            playlist = Playlist(
                id=spec.id,
                name=spec.name,
                tracks=response.selected_tracks,
                spec=spec,
                validation_result=validation_result,
                created_at=datetime.now(),
            )

            playlists.append(playlist)

            # Log decision
            decision_logger.log_decision(
                decision_type="track_selection",
                playlist_name=spec.name,
                criteria=serialize_criteria(spec.track_criteria),
                selected_tracks=serialize_tracks(response.selected_tracks),
                validation_result=serialize_validation(validation_result),
                metadata={
                    "playlist_id": spec.id,
                    "cost_usd": str(response.cost_usd),
                    "execution_time_seconds": str(response.execution_time_seconds),
                    "target_track_count": str(target_track_count),
                    "actual_track_count": str(len(response.selected_tracks)),
                    "reasoning": response.reasoning,
                },
            )

        except Exception as e:
            logger.error("Failed to process playlist %s: %s", spec.name, e)
            # Log failure decision
            decision_logger.log_decision(
                decision_type="track_selection",
                playlist_name=spec.name,
                criteria=serialize_criteria(spec.track_criteria),
                selected_tracks=[],
                validation_result={},
                metadata={
                    "playlist_id": spec.id,
                    "error": str(e),
                    "failed_at": datetime.now().isoformat(),
                },
            )
            raise

    logger.info("Batch track selection complete: total cost $%.4f", total_cost)
    return playlists


def save_playlist_file(playlist: Playlist, output_dir: Path) -> Path:
    """
    Save playlist to JSON file.

    Args:
        playlist: Playlist to save
        output_dir: Output directory

    Returns:
        Path to saved file
    """
    output_file = output_dir / f"{playlist.name}.json"

    playlist_data = {
        "id": playlist.id,
        "name": playlist.name,
        "created_at": playlist.created_at.isoformat(),
        "tracks": [
            {
                "position": track.position,
                "track_id": track.track_id,
                "title": track.title,
                "artist": track.artist,
                "album": track.album,
                "bpm": track.bpm,
                "genre": track.genre,
                "year": track.year,
                "country": track.country,
                "duration_seconds": track.duration_seconds,
                "selection_reason": track.selection_reason,
            }
            for track in playlist.tracks
        ],
        "validation": {
            "constraint_scores": {
                "constraint_satisfaction": playlist.validation_result.constraint_scores.constraint_satisfaction,
                "bpm_satisfaction": playlist.validation_result.constraint_scores.bpm_satisfaction,
                "genre_satisfaction": playlist.validation_result.constraint_scores.genre_satisfaction,
                "era_satisfaction": playlist.validation_result.constraint_scores.era_satisfaction,
                "australian_content": playlist.validation_result.constraint_scores.australian_content,
            },
            "flow_metrics": {
                "flow_quality_score": playlist.validation_result.flow_metrics.flow_quality_score,
                "bpm_variance": playlist.validation_result.flow_metrics.bpm_variance,
                "energy_progression": playlist.validation_result.flow_metrics.energy_progression,
                "genre_diversity": playlist.validation_result.flow_metrics.genre_diversity,
            },
            "gap_analysis": playlist.validation_result.gap_analysis,
            "passes_validation": playlist.validation_result.passes_validation,
        },
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(playlist_data, f, indent=2, ensure_ascii=False)

    return output_file


async def sync_to_azuracast(playlists: List[Playlist]) -> Dict[Playlist, Optional[int]]:
    """
    Sync playlists to AzuraCast.

    Args:
        playlists: List of validated playlists to sync

    Returns:
        Dict mapping Playlist to AzuraCast playlist ID (or None if sync failed)

    Raises:
        AzuraCastPlaylistSyncError: If sync fails for any playlist
    """
    sync_results: Dict[Playlist, Optional[int]] = {}
    failed_syncs = []

    for playlist in playlists:
        try:
            # Sync playlist to AzuraCast
            synced_playlist = await sync_playlist_to_azuracast(playlist)

            # Record result
            sync_results[playlist] = synced_playlist.azuracast_id
            logger.info(f"✓ Synced {playlist.name} -> AzuraCast ID {synced_playlist.azuracast_id}")

        except AzuraCastPlaylistSyncError as e:
            logger.error(f"✗ Failed to sync {playlist.name}: {e}")
            failed_syncs.append((playlist, str(e)))

        except Exception as e:
            logger.error(f"✗ Unexpected error syncing {playlist.name}: {e}")
            failed_syncs.append((playlist, str(e)))

    # Log summary
    if failed_syncs:
        logger.warning(
            f"AzuraCast sync completed with {len(failed_syncs)} failures "
            f"out of {len(playlists)} playlists"
        )
        for playlist, error in failed_syncs:
            logger.warning(f"  - {playlist.name}: {error}")
    else:
        logger.info(f"All {len(playlists)} playlists synced successfully")

    return sync_results


# Serialization helpers for decision logging


def serialize_criteria(criteria: Any) -> Dict[str, Any]:
    """Serialize TrackSelectionCriteria to dict."""
    return {
        "bpm_range": criteria.bpm_range,
        "bpm_tolerance": criteria.bpm_tolerance,
        "genre_mix": criteria.genre_mix,
        "genre_tolerance": criteria.genre_tolerance,
        "era_distribution": criteria.era_distribution,
        "era_tolerance": criteria.era_tolerance,
        "australian_min": criteria.australian_min,
        "energy_flow": criteria.energy_flow,
    }


def serialize_tracks(tracks: Any) -> List[Dict[str, Any]]:
    """Serialize list of SelectedTrack to list of dicts."""
    return [
        {
            "track_id": track.track_id,
            "title": track.title,
            "artist": track.artist,
            "album": track.album,
            "bpm": track.bpm,
            "genre": track.genre,
            "year": track.year,
            "country": track.country,
            "duration_seconds": track.duration_seconds,
            "position": track.position,
            "selection_reason": track.selection_reason,
        }
        for track in tracks
    ]


def serialize_validation(validation: Any) -> Dict[str, Any]:
    """Serialize ValidationResult to dict."""
    return {
        "constraint_scores": {
            "constraint_satisfaction": validation.constraint_scores.constraint_satisfaction,
            "bpm_satisfaction": validation.constraint_scores.bpm_satisfaction,
            "genre_satisfaction": validation.constraint_scores.genre_satisfaction,
            "era_satisfaction": validation.constraint_scores.era_satisfaction,
            "australian_content": validation.constraint_scores.australian_content,
        },
        "flow_metrics": {
            "flow_quality_score": validation.flow_metrics.flow_quality_score,
            "bpm_variance": validation.flow_metrics.bpm_variance,
            "energy_progression": validation.flow_metrics.energy_progression,
            "genre_diversity": validation.flow_metrics.genre_diversity,
        },
        "gap_analysis": validation.gap_analysis,
        "passes_validation": validation.passes_validation,
    }
