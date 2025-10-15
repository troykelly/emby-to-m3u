#!/usr/bin/env python3
"""Sync M3U playlists containing Subsonic track IDs to AzuraCast.

This script:
1. Reads M3U playlist files from playlists/ directory
2. Extracts Subsonic track IDs from the M3U files
3. Retrieves full track metadata from Subsonic
4. Downloads audio files from Subsonic
5. Uploads files to AzuraCast (with duplicate detection)
6. Creates/updates playlists in AzuraCast
7. Links uploaded tracks to their respective playlists

Usage:
    python scripts/sync_m3u_to_azuracast.py [--playlist-name "After Hours - 2025-10-09"]
    python scripts/sync_m3u_to_azuracast.py --all
"""

import argparse
import logging
import os
import sys
from base64 import b64encode
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional

from tqdm import tqdm

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.azuracast.main import AzuraCastSync
from src.logger import setup_logging
from src.subsonic.client import SubsonicClient
from src.subsonic.models import SubsonicConfig, SubsonicTrack

setup_logging()
logger = logging.getLogger(__name__)


class M3UPlaylistSync:
    """Syncs M3U playlists with Subsonic track IDs to AzuraCast."""

    def __init__(self):
        """Initialize Subsonic and AzuraCast clients."""
        # Check required environment variables
        subsonic_url = os.getenv("SUBSONIC_URL")
        subsonic_username = os.getenv("SUBSONIC_USER")
        subsonic_password = os.getenv("SUBSONIC_PASSWORD")
        subsonic_api_key = os.getenv("SUBSONIC_API_KEY")

        if not subsonic_url:
            raise ValueError(
                "SUBSONIC_URL environment variable is required. "
                "Set it to your Subsonic/Navidrome server URL (e.g., https://music.example.com)"
            )

        if not subsonic_username:
            raise ValueError(
                "SUBSONIC_USER environment variable is required. "
                "Set it to your Subsonic/Navidrome username"
            )

        if not subsonic_password and not subsonic_api_key:
            raise ValueError(
                "Either SUBSONIC_PASSWORD or SUBSONIC_API_KEY environment variable is required. "
                "Set one of these for authentication"
            )

        # Initialize Subsonic client
        subsonic_config = SubsonicConfig(
            url=subsonic_url,
            username=subsonic_username,
            password=subsonic_password,
            api_key=subsonic_api_key,
        )
        self.subsonic = SubsonicClient(subsonic_config)

        # Test Subsonic connection
        try:
            self.subsonic.ping()
            logger.info("Subsonic connection successful")
        except Exception as e:
            logger.error(f"Failed to connect to Subsonic: {e}")
            raise

        # Initialize AzuraCast client
        self.azuracast = AzuraCastSync()
        logger.info("AzuraCast client initialized")

        # Track cache to avoid duplicate downloads
        self._track_cache: Dict[str, SubsonicTrack] = {}
        self._uploaded_files: Dict[str, str] = {}  # subsonic_id -> azuracast_file_id

    def parse_m3u_file(self, m3u_path: Path) -> List[Dict[str, str]]:
        """Parse M3U file to extract track IDs and metadata.

        Args:
            m3u_path: Path to M3U file

        Returns:
            List of dicts with track_id, title, artist, duration
        """
        tracks = []
        current_extinf = None

        with open(m3u_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("#EXTINF:"):
                    # Parse: #EXTINF:221,Mike Posner - Beautiful Day (Acoustic)
                    parts = line[8:].split(",", 1)
                    duration = int(parts[0]) if parts[0].isdigit() else 0
                    title_artist = parts[1] if len(parts) > 1 else "Unknown"

                    # Try to split artist - title
                    if " - " in title_artist:
                        artist, title = title_artist.split(" - ", 1)
                    else:
                        artist = "Unknown Artist"
                        title = title_artist

                    current_extinf = {
                        "duration": duration,
                        "artist": artist,
                        "title": title,
                    }
                elif line and not line.startswith("#"):
                    # This is the track ID line
                    if current_extinf:
                        current_extinf["track_id"] = line
                        tracks.append(current_extinf)
                        current_extinf = None

        logger.info(f"Parsed {len(tracks)} tracks from {m3u_path.name}")
        return tracks

    def get_subsonic_track(self, track_id: str) -> Optional[SubsonicTrack]:
        """Get track metadata from Subsonic.

        Args:
            track_id: Subsonic track ID

        Returns:
            SubsonicTrack object or None if not found
        """
        # Check cache first
        if track_id in self._track_cache:
            return self._track_cache[track_id]

        try:
            logger.debug(f"Fetching metadata for track {track_id}")

            # Use getSong endpoint to get full track metadata
            track = self.subsonic.get_song(track_id)

            if track:
                # Cache the track
                self._track_cache[track_id] = track
                logger.info(f"Retrieved track: {track.artist} - {track.title}")
                return track
            else:
                logger.warning(f"Track {track_id} not found in Subsonic")
                return None

        except Exception as e:
            logger.error(f"Error retrieving track {track_id}: {e}")
            return None

    def download_subsonic_track(self, track_id: str) -> Optional[bytes]:
        """Download audio file from Subsonic.

        Args:
            track_id: Subsonic track ID

        Returns:
            Audio file bytes or None if download failed
        """
        try:
            logger.debug(f"Downloading track {track_id} from Subsonic")
            audio_data = self.subsonic.download_track(track_id)
            logger.info(f"Downloaded {len(audio_data)} bytes for track {track_id}")
            return audio_data
        except Exception as e:
            logger.error(f"Failed to download track {track_id}: {e}")
            return None

    def upload_to_azuracast(
        self,
        track_id: str,
        audio_data: bytes,
        metadata: Dict[str, str],
        pbar: tqdm,
    ) -> Optional[str]:
        """Upload track to AzuraCast.

        Args:
            track_id: Subsonic track ID
            audio_data: Audio file bytes
            metadata: Track metadata dict
            pbar: Progress bar

        Returns:
            AzuraCast file ID or None if upload failed
        """
        # Check if already uploaded
        if track_id in self._uploaded_files:
            logger.debug(f"Track {track_id} already uploaded")
            return self._uploaded_files[track_id]

        try:
            artist = metadata.get("artist", "Unknown Artist")
            title = metadata.get("title", "Unknown Title")
            album = metadata.get("album", "Unknown Album")

            pbar.set_description(f"Uploading '{title}' by '{artist}'")

            # Generate file path for AzuraCast
            # Format: Artist/Album/Track.ext
            file_ext = ".mp3"  # Default extension
            if "suffix" in metadata:
                file_ext = f".{metadata['suffix']}"

            file_path = f"{artist}/{album}/{title}{file_ext}"

            # Check for duplicates in AzuraCast
            known_tracks = self.azuracast.get_known_tracks()

            # Create a pseudo-track dict for duplicate detection
            pseudo_track = {
                "AlbumArtist": artist,
                "Album": album,
                "Name": title,
                "azuracast_file_id": None,
            }

            if not self.azuracast.check_file_in_azuracast(known_tracks, pseudo_track):
                # Upload the file
                upload_response = self.azuracast.upload_file_to_azuracast(
                    audio_data, file_path
                )
                azuracast_file_id = upload_response.get("id")

                if azuracast_file_id:
                    logger.info(f"Uploaded track '{title}' to AzuraCast (ID: {azuracast_file_id})")
                    self._uploaded_files[track_id] = azuracast_file_id
                    return azuracast_file_id
                else:
                    logger.error(f"Upload response missing 'id' for track '{title}'")
                    return None
            else:
                # Track already exists
                azuracast_file_id = pseudo_track.get("azuracast_file_id")
                logger.info(f"Track '{title}' already exists in AzuraCast (ID: {azuracast_file_id})")
                self._uploaded_files[track_id] = azuracast_file_id
                return azuracast_file_id

        except Exception as e:
            logger.error(f"Failed to upload track {track_id}: {e}")
            return None

    def sync_playlist(self, m3u_path: Path, test_mode: bool = False) -> bool:
        """Sync a single M3U playlist to AzuraCast.

        Args:
            m3u_path: Path to M3U file
            test_mode: If True, only process first 10 tracks

        Returns:
            True if sync was successful
        """
        playlist_name = m3u_path.stem
        logger.info(f"Syncing playlist: {playlist_name}")

        # Parse M3U file
        tracks = self.parse_m3u_file(m3u_path)
        if not tracks:
            logger.warning(f"No tracks found in {m3u_path}")
            return False

        # Test mode: only process first 10 tracks
        if test_mode:
            logger.info("TEST MODE: Processing only first 10 tracks")
            tracks = tracks[:10]

        # Process tracks
        azuracast_track_ids = []

        with tqdm(total=len(tracks), desc=f"Processing {playlist_name}", unit="track") as pbar:
            for track_meta in tracks:
                track_id = track_meta["track_id"]

                try:
                    # Get full track metadata from Subsonic
                    pbar.set_description(f"Fetching {track_meta['title']}")
                    subsonic_track = self.get_subsonic_track(track_id)

                    if not subsonic_track:
                        logger.warning(f"Skipping track {track_id} - metadata not found")
                        pbar.update(1)
                        continue

                    # Download from Subsonic
                    pbar.set_description(f"Downloading {subsonic_track.title}")
                    audio_data = self.download_subsonic_track(track_id)

                    if not audio_data:
                        logger.warning(f"Skipping track {track_id} - download failed")
                        pbar.update(1)
                        continue

                    # Prepare metadata for upload
                    metadata = {
                        "artist": subsonic_track.artist,
                        "title": subsonic_track.title,
                        "album": subsonic_track.album,
                        "suffix": subsonic_track.suffix,
                        "duration": subsonic_track.duration,
                    }

                    # Upload to AzuraCast
                    azuracast_file_id = self.upload_to_azuracast(
                        track_id, audio_data, metadata, pbar
                    )

                    if azuracast_file_id:
                        azuracast_track_ids.append(azuracast_file_id)
                    else:
                        logger.warning(f"Skipping track {track_id} - upload failed")

                except Exception as e:
                    logger.error(f"Error processing track {track_id}: {e}")

                finally:
                    pbar.update(1)

        # Create/update playlist in AzuraCast
        logger.info(f"Linking {len(azuracast_track_ids)} tracks to playlist '{playlist_name}'")

        try:
            # Clear existing playlist
            self.azuracast.clear_playlist_by_name(playlist_name)

            # Get or create playlist
            playlist_info = self.azuracast.get_playlist(playlist_name)
            if not playlist_info:
                logger.info(f"Creating new playlist: {playlist_name}")
                playlist_info = self.azuracast.create_playlist(playlist_name)

            if not playlist_info:
                logger.error(f"Failed to create/get playlist '{playlist_name}'")
                return False

            playlist_id = playlist_info["id"]

            # Add tracks to playlist
            with tqdm(total=len(azuracast_track_ids), desc=f"Linking tracks to {playlist_name}", unit="track") as pbar:
                for file_id in azuracast_track_ids:
                    try:
                        self.azuracast.add_to_playlist(file_id, playlist_id)
                        pbar.update(1)
                    except Exception as e:
                        logger.error(f"Failed to link track {file_id} to playlist: {e}")

            logger.info(f"✓ Successfully synced playlist '{playlist_name}' with {len(azuracast_track_ids)} tracks")
            return True

        except Exception as e:
            logger.error(f"Failed to sync playlist '{playlist_name}': {e}")
            return False

    def sync_all_playlists(self, test_mode: bool = False):
        """Sync all M3U playlists from playlists/ directory.

        Args:
            test_mode: If True, only process first 10 tracks per playlist
        """
        playlists_dir = project_root / "playlists"
        m3u_files = sorted(playlists_dir.glob("*.m3u"))

        if not m3u_files:
            logger.warning(f"No M3U files found in {playlists_dir}")
            return

        logger.info(f"Found {len(m3u_files)} playlists to sync")

        success_count = 0
        fail_count = 0

        for m3u_file in m3u_files:
            try:
                if self.sync_playlist(m3u_file, test_mode=test_mode):
                    success_count += 1
                else:
                    fail_count += 1
            except Exception as e:
                logger.error(f"Error syncing {m3u_file.name}: {e}")
                fail_count += 1

        logger.info(f"\n{'='*60}")
        logger.info(f"SYNC COMPLETE: {success_count} succeeded, {fail_count} failed")
        logger.info(f"{'='*60}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Sync M3U playlists with Subsonic track IDs to AzuraCast"
    )
    parser.add_argument(
        "--playlist-name",
        type=str,
        help="Sync only the specified playlist (e.g., 'After Hours - 2025-10-09')",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Sync all playlists in playlists/ directory",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test mode: only process first 10 tracks per playlist",
    )

    args = parser.parse_args()

    try:
        syncer = M3UPlaylistSync()

        if args.playlist_name:
            # Sync specific playlist
            m3u_path = project_root / "playlists" / f"{args.playlist_name}.m3u"
            if not m3u_path.exists():
                logger.error(f"Playlist file not found: {m3u_path}")
                sys.exit(1)

            syncer.sync_playlist(m3u_path, test_mode=args.test)

        elif args.all:
            # Sync all playlists
            syncer.sync_all_playlists(test_mode=args.test)

        else:
            # Default: sync After Hours as test
            logger.info("No arguments provided. Syncing 'After Hours - 2025-10-09' as test...")
            m3u_path = project_root / "playlists" / "After Hours - 2025-10-09.m3u"
            if m3u_path.exists():
                syncer.sync_playlist(m3u_path, test_mode=True)
            else:
                logger.error(f"Default test playlist not found: {m3u_path}")
                parser.print_help()
                sys.exit(1)

    except KeyboardInterrupt:
        logger.info("\nSync interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Sync failed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        # Clean up
        if "syncer" in locals():
            syncer.subsonic.close()


if __name__ == "__main__":
    main()
