"""
AzuraCast Playlist Synchronization

Syncs AI-generated playlists to AzuraCast with create/update logic and duplicate detection.
Implements FR-005 (Update existing playlists) and T021 (AzuraCast sync).
"""

import os
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from src.ai_playlist.models import Playlist, SelectedTrack
from src.azuracast.main import AzuraCastSync
from src.logger import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


class AzuraCastPlaylistSyncError(Exception):
    """Raised when AzuraCast playlist synchronization fails."""

    pass


async def sync_playlist_to_azuracast(playlist: Playlist) -> Playlist:
    """
    Synchronizes an AI-generated playlist to AzuraCast.

    Implements FR-005 (Update existing playlists):
    - Searches for existing playlist by name
    - Updates existing playlist with new tracks
    - Creates new playlist if not exists
    - Uploads tracks with duplicate detection
    - Sets synced_at and azuracast_id on success

    Args:
        playlist: Validated Playlist object with tracks to sync

    Returns:
        Updated Playlist object with synced_at and azuracast_id set

    Raises:
        AzuraCastPlaylistSyncError: If sync fails after retries
        ValueError: If playlist validation fails
    """
    # Validate environment variables
    host = os.getenv("AZURACAST_HOST")
    api_key = os.getenv("AZURACAST_API_KEY")
    station_id = os.getenv("AZURACAST_STATIONID")

    if not all([host, api_key, station_id]):
        missing = []
        if not host:
            missing.append("AZURACAST_HOST")
        if not api_key:
            missing.append("AZURACAST_API_KEY")
        if not station_id:
            missing.append("AZURACAST_STATIONID")
        raise AzuraCastPlaylistSyncError(
            f"Missing required environment variables: {', '.join(missing)}"
        )

    # Initialize AzuraCast client (reusing existing client)
    client = AzuraCastSync()

    logger.info(
        f"Starting AzuraCast sync for playlist '{playlist.name}' "
        f"with {len(playlist.tracks)} tracks"
    )

    try:
        # Step 1: Check if playlist exists in AzuraCast
        existing_playlist = client.get_playlist(playlist.name)

        if existing_playlist:
            logger.info(
                f"Found existing playlist '{playlist.name}' " f"(ID: {existing_playlist['id']})"
            )
            playlist_id = existing_playlist["id"]

            # Empty existing playlist before adding new tracks (FR-005)
            if not client.empty_playlist(playlist_id):
                raise AzuraCastPlaylistSyncError(
                    f"Failed to empty existing playlist '{playlist.name}' " f"(ID: {playlist_id})"
                )
            logger.debug(f"Emptied existing playlist '{playlist.name}'")
        else:
            logger.info(f"Playlist '{playlist.name}' not found, creating new")
            created_playlist = client.create_playlist(playlist.name)

            if not created_playlist:
                raise AzuraCastPlaylistSyncError(f"Failed to create playlist '{playlist.name}'")

            playlist_id = created_playlist["id"]
            logger.info(f"Created new playlist '{playlist.name}' (ID: {playlist_id})")

        # Step 2: Convert SelectedTrack objects to Track-compatible dicts for upload
        tracks_for_upload = _convert_selected_tracks_to_dict(playlist.tracks)

        # Step 3: Upload tracks to AzuraCast (with duplicate detection)
        upload_success = client.upload_playlist(tracks_for_upload)

        if not upload_success:
            raise AzuraCastPlaylistSyncError(
                f"Failed to upload tracks for playlist '{playlist.name}'"
            )

        # Step 4: Add uploaded tracks to playlist
        added_count = 0
        failed_count = 0

        for track_dict in tracks_for_upload:
            azuracast_file_id = track_dict.get("azuracast_file_id")

            if not azuracast_file_id:
                logger.warning(
                    f"Track '{track_dict.get('Name', 'Unknown')}' "
                    f"has no AzuraCast file ID, skipping"
                )
                failed_count += 1
                continue

            if client.add_to_playlist(azuracast_file_id, playlist_id):
                added_count += 1
            else:
                logger.warning(
                    f"Failed to add track '{track_dict.get('Name', 'Unknown')}' "
                    f"to playlist '{playlist.name}'"
                )
                failed_count += 1

        logger.info(
            f"Playlist sync complete: {added_count} tracks added, "
            f"{failed_count} failed for '{playlist.name}'"
        )

        # Step 5: Update playlist object with sync metadata
        playlist.synced_at = datetime.now()
        playlist.azuracast_id = playlist_id

        logger.info(
            f"Successfully synced playlist '{playlist.name}' "
            f"(ID: {playlist_id}) at {playlist.synced_at.isoformat()}"
        )

        return playlist

    except Exception as e:
        logger.error(f"AzuraCast sync failed for playlist '{playlist.name}': {e}", exc_info=True)
        raise AzuraCastPlaylistSyncError(
            f"Failed to sync playlist '{playlist.name}': {str(e)}"
        ) from e


def _convert_selected_tracks_to_dict(selected_tracks: List[SelectedTrack]) -> List[Dict[str, Any]]:
    """
    Converts SelectedTrack dataclass objects to Track-compatible dictionaries.

    The AzuraCast client expects Track objects with specific keys.
    This function maps SelectedTrack fields to the expected format.

    Args:
        selected_tracks: List of SelectedTrack objects

    Returns:
        List of dictionaries compatible with AzuraCast client
    """
    track_dicts = []

    for track in selected_tracks:
        # Map SelectedTrack fields to Track dictionary keys
        track_dict = {
            "Id": track.track_id,
            "Name": track.title,
            "AlbumArtist": track.artist,
            "Album": track.album,
            "ProductionYear": track.year if track.year else "Unknown Year",
            "Path": f"/music/{track.artist}/{track.album}/{track.title}",  # Placeholder
            "ParentIndexNumber": 1,  # Default disk number
            "IndexNumber": track.position,
            # Additional metadata for duplicate detection
            "artist": track.artist,
            "album": track.album,
            "title": track.title,
        }

        track_dicts.append(track_dict)

    logger.debug(f"Converted {len(selected_tracks)} SelectedTrack objects to dicts")
    return track_dicts
