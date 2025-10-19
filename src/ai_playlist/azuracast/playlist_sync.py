"""
AzuraCast Playlist Sync - T037

Sync M3U playlists to AzuraCast with dry-run support and schedule configuration.

Success Criteria (T027, T028):
- Upload tracks to AzuraCast
- Create/update playlists
- Configure schedules
- Dry-run mode support
- Verification by re-fetching
"""

import httpx
from typing import List, Dict, Optional, Any
from pathlib import Path
from dataclasses import dataclass
import logging

from src.ai_playlist.models.core import Playlist, SelectedTrack

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    """Result of playlist sync operation."""
    success: bool
    playlist_id: Optional[str]
    tracks_uploaded: int
    schedule_configured: bool
    verification_passed: bool
    errors: List[str]
    dry_run: bool


class AzuraCastPlaylistSync:
    """Sync playlists to AzuraCast station."""

    def __init__(
        self,
        host: str,
        api_key: str,
        station_id: str,
        timeout: int = 30
    ):
        """Initialize AzuraCast sync client.

        Args:
            host: AzuraCast host URL
            api_key: API key for authentication
            station_id: Station ID
            timeout: Request timeout in seconds
        """
        self.host = host.rstrip('/')
        self.api_key = api_key
        self.station_id = station_id
        self.timeout = timeout

        self.headers = {
            'X-API-Key': api_key,
            'Content-Type': 'application/json'
        }

    async def sync_playlist(
        self,
        playlist: Playlist,
        m3u_path: Path,
        schedule: Optional[Dict[str, Any]] = None,
        dry_run: bool = False
    ) -> SyncResult:
        """Sync playlist to AzuraCast.

        Args:
            playlist: Playlist to sync
            m3u_path: Path to M3U file
            schedule: Schedule configuration (optional)
            dry_run: If True, validate without making changes

        Returns:
            SyncResult with operation details
        """
        errors = []
        tracks_uploaded = 0
        schedule_configured = False
        verification_passed = False
        azuracast_playlist_id = None

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Step 1: Create or update playlist
                if not dry_run:
                    azuracast_playlist_id = await self._create_or_update_playlist(
                        client,
                        playlist
                    )
                else:
                    logger.info(f"DRY RUN: Would create playlist '{playlist.name}'")
                    azuracast_playlist_id = "dry_run_playlist_id"

                # Step 2: Upload tracks
                if not dry_run:
                    tracks_uploaded = await self._upload_tracks(
                        client,
                        azuracast_playlist_id,
                        playlist.tracks
                    )
                else:
                    logger.info(
                        f"DRY RUN: Would upload {len(playlist.tracks)} tracks"
                    )
                    tracks_uploaded = len(playlist.tracks)

                # Step 3: Configure schedule
                if schedule and not dry_run:
                    schedule_configured = await self._configure_schedule(
                        client,
                        azuracast_playlist_id,
                        schedule
                    )
                elif schedule and dry_run:
                    logger.info(f"DRY RUN: Would configure schedule: {schedule}")
                    schedule_configured = True

                # Step 4: Verify
                if not dry_run:
                    verification_passed = await self._verify_playlist(
                        client,
                        azuracast_playlist_id,
                        playlist
                    )
                else:
                    logger.info("DRY RUN: Skipping verification")
                    verification_passed = True

        except Exception as e:
            logger.error(f"Sync failed: {e}")
            errors.append(str(e))

        return SyncResult(
            success=len(errors) == 0,
            playlist_id=azuracast_playlist_id,
            tracks_uploaded=tracks_uploaded,
            schedule_configured=schedule_configured,
            verification_passed=verification_passed,
            errors=errors,
            dry_run=dry_run
        )

    async def _create_or_update_playlist(
        self,
        client: httpx.AsyncClient,
        playlist: Playlist
    ) -> str:
        """Create or update playlist in AzuraCast.

        Returns:
            Playlist ID
        """
        # Check if playlist exists
        url = f"{self.host}/api/station/{self.station_id}/playlists"
        response = await client.get(url, headers=self.headers)
        response.raise_for_status()

        existing_playlists = response.json()
        existing = next(
            (p for p in existing_playlists if p['name'] == playlist.name),
            None
        )

        if existing:
            # Update existing playlist
            playlist_id = existing['id']
            update_url = f"{self.host}/api/station/{self.station_id}/playlist/{playlist_id}"
            update_data = {
                "name": playlist.name,
                "is_enabled": True
            }
            response = await client.put(update_url, headers=self.headers, json=update_data)
            response.raise_for_status()
            logger.info(f"Updated existing playlist: {playlist.name} (ID: {playlist_id})")
        else:
            # Create new playlist
            create_data = {
                "name": playlist.name,
                "is_enabled": True,
                "type": "default"
            }
            response = await client.post(url, headers=self.headers, json=create_data)
            response.raise_for_status()
            result = response.json()
            playlist_id = result['id']
            logger.info(f"Created new playlist: {playlist.name} (ID: {playlist_id})")

        return str(playlist_id)

    async def _upload_tracks(
        self,
        client: httpx.AsyncClient,
        playlist_id: str,
        tracks: List[SelectedTrack]
    ) -> int:
        """Upload tracks to playlist.

        Returns:
            Number of tracks uploaded
        """
        uploaded = 0

        for track in tracks:
            try:
                # Add track to playlist
                url = f"{self.host}/api/station/{self.station_id}/playlist/{playlist_id}/items"
                data = {
                    "media_id": track.track_id,
                    "weight": 1
                }
                response = await client.post(url, headers=self.headers, json=data)
                response.raise_for_status()
                uploaded += 1

            except Exception as e:
                logger.error(f"Failed to upload track {track.track_id}: {e}")

        logger.info(f"Uploaded {uploaded}/{len(tracks)} tracks")
        return uploaded

    async def _configure_schedule(
        self,
        client: httpx.AsyncClient,
        playlist_id: str,
        schedule: Dict[str, Any]
    ) -> bool:
        """Configure playlist schedule.

        Args:
            client: HTTP client
            playlist_id: Playlist ID
            schedule: Schedule configuration
                {
                    "days": [1, 2, 3, 4, 5],  # Mon-Fri
                    "start_time": "06:00",
                    "end_time": "10:00"
                }

        Returns:
            True if successful
        """
        try:
            url = f"{self.host}/api/station/{self.station_id}/playlist/{playlist_id}/schedule"
            data = {
                "days": schedule.get("days", []),
                "start_time": schedule.get("start_time"),
                "end_time": schedule.get("end_time")
            }
            response = await client.put(url, headers=self.headers, json=data)
            response.raise_for_status()
            logger.info(f"Configured schedule for playlist {playlist_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to configure schedule: {e}")
            return False

    async def _verify_playlist(
        self,
        client: httpx.AsyncClient,
        playlist_id: str,
        original_playlist: Playlist
    ) -> bool:
        """Verify playlist by re-fetching and comparing.

        Returns:
            True if verification passed
        """
        try:
            # Fetch playlist from AzuraCast
            url = f"{self.host}/api/station/{self.station_id}/playlist/{playlist_id}"
            response = await client.get(url, headers=self.headers)
            response.raise_for_status()

            fetched = response.json()

            # Verify track count
            if len(fetched.get('items', [])) != len(original_playlist.tracks):
                logger.error(
                    f"Track count mismatch: {len(fetched.get('items', []))} "
                    f"vs {len(original_playlist.tracks)}"
                )
                return False

            logger.info(f"Verification passed for playlist {playlist_id}")
            return True

        except Exception as e:
            logger.error(f"Verification failed: {e}")
            return False

    async def list_playlists(self) -> List[Dict[str, Any]]:
        """List all playlists on station.

        Returns:
            List of playlist dictionaries
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            url = f"{self.host}/api/station/{self.station_id}/playlists"
            response = await client.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()

    async def delete_playlist(self, playlist_id: str) -> bool:
        """Delete a playlist.

        Args:
            playlist_id: Playlist ID to delete

        Returns:
            True if successful
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                url = f"{self.host}/api/station/{self.station_id}/playlist/{playlist_id}"
                response = await client.delete(url, headers=self.headers)
                response.raise_for_status()
                logger.info(f"Deleted playlist {playlist_id}")
                return True

        except Exception as e:
            logger.error(f"Failed to delete playlist: {e}")
            return False
