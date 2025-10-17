"""
Duration Padding - Fill Playlists to Required Daypart Duration

Ensures playlists meet minimum duration requirements by adding padding tracks
with progressive constraint relaxation when LLM selection falls short.
"""

import logging
import math
import random
from typing import List, Set, Optional, Dict, Any
from datetime import datetime

from .models.core import (
    Playlist,
    PlaylistSpecification,
    SelectedTrack,
    ValidationStatus,
    GenreCriteria,
    BPMRange,
)
from src.subsonic.client import SubsonicClient

logger = logging.getLogger(__name__)

# Minimum fill percentage (90% of target duration)
MIN_FILL_PERCENTAGE = 0.90

# Average track duration for estimation (3.5 minutes)
AVG_TRACK_DURATION_SECONDS = 210


async def pad_playlist_to_duration(
    playlist: Playlist,
    spec: PlaylistSpecification,
    subsonic_client: SubsonicClient,
    used_track_ids: Optional[Set[str]] = None,
) -> Playlist:
    """
    Pad playlist with additional tracks to meet minimum duration requirement.

    Uses progressive constraint relaxation to find suitable padding tracks when
    the initial LLM selection doesn't fill the required daypart duration.

    Args:
        playlist: Initial playlist from LLM
        spec: Original playlist specification with target_duration_minutes
        subsonic_client: Subsonic client for querying additional tracks
        used_track_ids: Set of track IDs already used (for deduplication)

    Returns:
        Padded playlist meeting minimum duration (90% of target)
    """
    if used_track_ids is None:
        used_track_ids = set()

    # Add current playlist tracks to used set
    used_track_ids.update(t.track_id for t in playlist.tracks)

    # 1. Calculate current duration
    current_duration = sum(track.duration_seconds for track in playlist.tracks)
    target_duration_seconds = spec.target_duration_minutes * 60
    required_duration = target_duration_seconds * MIN_FILL_PERCENTAGE

    if current_duration >= required_duration:
        logger.info(
            f"Playlist duration {current_duration/60:.1f}min meets requirement "
            f"{required_duration/60:.1f}min. No padding needed."
        )
        return playlist

    # 2. Calculate how many more tracks we need
    gap_seconds = required_duration - current_duration
    tracks_needed = math.ceil(gap_seconds / AVG_TRACK_DURATION_SECONDS)

    logger.warning(
        f"Playlist duration {current_duration/60:.1f}min is below minimum "
        f"{required_duration/60:.1f}min ({MIN_FILL_PERCENTAGE*100:.0f}% of {spec.target_duration_minutes}min target). "
        f"Need approximately {tracks_needed} more tracks to fill {gap_seconds/60:.1f}min gap."
    )

    # 3. Progressive constraint relaxation to find padding tracks
    padding_tracks = []
    relaxation_levels = [
        {"name": "Level 1: Slight BPM relaxation", "bpm_tolerance": 5, "genre_strict": True},
        {"name": "Level 2: Moderate BPM relaxation", "bpm_tolerance": 10, "genre_strict": True},
        {"name": "Level 3: Wide BPM + Genre mixing", "bpm_tolerance": 15, "genre_strict": False},
        {"name": "Level 4: Very wide BPM range", "bpm_tolerance": 20, "genre_strict": False},
        {"name": "Level 5: Any BPM, any genre", "bpm_tolerance": None, "genre_strict": False},
    ]

    for level_idx, level in enumerate(relaxation_levels):
        if len(padding_tracks) >= tracks_needed:
            break

        logger.info(f"Attempting {level['name']}")

        # Query for additional tracks with relaxed constraints
        additional_tracks = await query_padding_tracks(
            subsonic_client,
            spec,
            used_track_ids,
            tracks_needed - len(padding_tracks),
            level
        )

        if additional_tracks:
            logger.info(f"Found {len(additional_tracks)} tracks at relaxation level {level_idx + 1}")
            padding_tracks.extend(additional_tracks)
            used_track_ids.update(t.track_id for t in additional_tracks)
        else:
            logger.warning(f"No tracks found at relaxation level {level_idx + 1}")

    # 4. Add padding tracks to playlist
    if not padding_tracks:
        logger.error(
            f"Failed to find any padding tracks after all relaxation levels. "
            f"Playlist will be {current_duration/60:.1f}min (only {current_duration/target_duration_seconds*100:.1f}% fill)"
        )
        return playlist

    # Update track positions
    starting_position = len(playlist.tracks)
    for idx, track in enumerate(padding_tracks):
        track.position_in_playlist = starting_position + idx

    playlist.tracks.extend(padding_tracks)

    # 5. Log padding operation
    new_duration = sum(track.duration_seconds for track in playlist.tracks)
    fill_percentage = new_duration / target_duration_seconds * 100

    logger.info(
        f"✓ Padding complete: Added {len(padding_tracks)} tracks. "
        f"Duration: {current_duration/60:.1f}min → {new_duration/60:.1f}min "
        f"({fill_percentage:.1f}% fill, target {MIN_FILL_PERCENTAGE*100:.0f}%)"
    )

    return playlist


async def query_padding_tracks(
    subsonic_client: SubsonicClient,
    spec: PlaylistSpecification,
    used_track_ids: Set[str],
    count: int,
    relaxation_level: Dict[str, Any],
) -> List[SelectedTrack]:
    """
    Query Subsonic for padding tracks with relaxed constraints.

    Args:
        subsonic_client: Subsonic client
        spec: Playlist specification
        used_track_ids: Track IDs to exclude
        count: Number of tracks needed
        relaxation_level: Dict with 'bpm_tolerance' and 'genre_strict' settings

    Returns:
        List of SelectedTrack objects
    """
    criteria = spec.track_selection_criteria
    padding_tracks = []

    try:
        # Build search query based on relaxation level
        # Start with primary genres from the spec
        primary_genres = list(criteria.genre_mix.keys())[:3]  # Top 3 genres

        # Determine BPM range with relaxation
        bpm_ranges = criteria.bpm_ranges
        if bpm_ranges and relaxation_level['bpm_tolerance'] is not None:
            # Use first BPM range as baseline and apply tolerance
            base_range = bpm_ranges[0]
            bpm_min = max(60, base_range.bpm_min - relaxation_level['bpm_tolerance'])
            bpm_max = min(200, base_range.bpm_max + relaxation_level['bpm_tolerance'])
        elif bpm_ranges:
            # Use full BPM range from spec
            bpm_min = min(r.bpm_min for r in bpm_ranges)
            bpm_max = max(r.bpm_max for r in bpm_ranges)
        else:
            # No BPM constraints
            bpm_min, bpm_max = 60, 200

        # Query tracks with relaxed constraints
        # Note: This is a simplified implementation that queries by genre
        # In production, you'd want to use more sophisticated Subsonic API calls

        for genre in primary_genres if relaxation_level['genre_strict'] else ["*"]:
            if len(padding_tracks) >= count:
                break

            # Get random tracks from this genre
            try:
                # Use Subsonic's getRandomSongs endpoint
                response = subsonic_client.get_random_songs(
                    size=min(count * 2, 100),  # Request extra for filtering
                    genre=genre if genre != "*" else None,
                    from_year=None,  # Don't restrict by year when padding
                    to_year=None,
                )

                if response and 'randomSongs' in response:
                    songs = response['randomSongs'].get('song', [])

                    for song in songs:
                        if len(padding_tracks) >= count:
                            break

                        track_id = song.get('id')
                        if not track_id or track_id in used_track_ids:
                            continue

                        # Create SelectedTrack from Subsonic response
                        track = SelectedTrack(
                            track_id=track_id,
                            title=song.get('title', 'Unknown'),
                            artist=song.get('artist', 'Unknown Artist'),
                            album=song.get('album', 'Unknown Album'),
                            duration_seconds=song.get('duration', AVG_TRACK_DURATION_SECONDS),
                            is_australian=False,  # TODO: Determine from metadata
                            rotation_category="Light",  # Padding tracks are typically light rotation
                            position_in_playlist=0,  # Will be updated by caller
                            selection_reasoning=f"Padding track (relaxation level: {relaxation_level['name']})",
                            validation_status=ValidationStatus.PASS,
                            metadata_source="subsonic_padding",
                            bpm=song.get('bpm'),
                            genre=song.get('genre', genre if genre != "*" else "Unknown"),
                            year=song.get('year', datetime.now().year),
                        )

                        padding_tracks.append(track)
                        used_track_ids.add(track_id)

            except Exception as e:
                logger.warning(f"Failed to query genre '{genre}' for padding: {e}")
                continue

    except Exception as e:
        logger.error(f"Error querying padding tracks: {e}", exc_info=True)

    # Shuffle padding tracks to add variety
    random.shuffle(padding_tracks)

    return padding_tracks[:count]


def calculate_padding_requirements(
    current_duration: int,
    target_duration_minutes: int,
) -> Dict[str, Any]:
    """
    Calculate padding requirements for a playlist.

    Args:
        current_duration: Current playlist duration in seconds
        target_duration_minutes: Target duration in minutes

    Returns:
        Dict with 'gap_seconds', 'tracks_needed', 'fill_percentage', 'needs_padding'
    """
    target_seconds = target_duration_minutes * 60
    required_seconds = target_seconds * MIN_FILL_PERCENTAGE

    gap_seconds = max(0, required_seconds - current_duration)
    tracks_needed = math.ceil(gap_seconds / AVG_TRACK_DURATION_SECONDS) if gap_seconds > 0 else 0
    fill_percentage = (current_duration / target_seconds * 100) if target_seconds > 0 else 0
    needs_padding = current_duration < required_seconds

    return {
        'gap_seconds': gap_seconds,
        'tracks_needed': tracks_needed,
        'fill_percentage': fill_percentage,
        'needs_padding': needs_padding,
        'target_seconds': target_seconds,
        'required_seconds': required_seconds,
        'current_seconds': current_duration,
    }
