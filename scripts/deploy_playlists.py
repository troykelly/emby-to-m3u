#!/usr/bin/env python3
"""
Complete End-to-End AI Playlist Automation System
Production Deployment - All 7 Steps Required for Success

This script performs the complete workflow:
1. Parse station-identity.md for daypart definitions
2. Generate AI playlists using GPT-5 with tool calling
3. Upload tracks to AzuraCast with duplicate detection
4. Create playlists in AzuraCast
5. Link tracks in AI-determined order
6. Schedule playlists with daypart timing
7. Verify complete deployment
"""

import asyncio
import sys
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any

# Import all required modules - works both as script and module
try:
    from src.ai_playlist.config import AIPlaylistConfig, get_station_identity_path
    from src.ai_playlist.document_parser import DocumentParser
    from src.ai_playlist.batch_executor import BatchPlaylistGenerator
    from src.ai_playlist.workflow import save_playlist_file
    from src.ai_playlist.models.core import Playlist, SelectedTrack
    from src.subsonic.client import SubsonicClient
    from src.azuracast.main import AzuraCastSync
except ModuleNotFoundError:
    # Running as script, add parent directory to path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from src.ai_playlist.config import AIPlaylistConfig, get_station_identity_path
    from src.ai_playlist.document_parser import DocumentParser
    from src.ai_playlist.batch_executor import BatchPlaylistGenerator
    from src.ai_playlist.workflow import save_playlist_file
    from src.ai_playlist.models.core import Playlist, SelectedTrack
    from src.subsonic.client import SubsonicClient
    from src.azuracast.main import AzuraCastSync

logger = logging.getLogger(__name__)


# Daypart to time range mapping from station-identity.md
DAYPART_SCHEDULE = {
    "Production Call": {"start_time": "06:00", "end_time": "10:00", "days": [1, 2, 3, 4, 5]},
    "The Session": {"start_time": "10:00", "end_time": "15:00", "days": [1, 2, 3, 4, 5]},
    "The Commute": {"start_time": "15:00", "end_time": "19:00", "days": [1, 2, 3, 4, 5]},
    "After Hours": {"start_time": "19:00", "end_time": "00:00", "days": [1, 2, 3, 4, 5]},
    "The Creative Shift": {"start_time": "00:00", "end_time": "06:00", "days": [1, 2, 3, 4, 5]},
    # Weekend programming (days 0=Sunday, 6=Saturday)
    "Weekend Morning": {"start_time": "08:00", "end_time": "12:00", "days": [0, 6]},
    "Weekend Afternoon": {"start_time": "12:00", "end_time": "18:00", "days": [0, 6]},
    "Weekend Evening": {"start_time": "18:00", "end_time": "00:00", "days": [0, 6]},
}


class DeploymentMetrics:
    """Track deployment progress and metrics"""

    def __init__(self):
        self.start_time = datetime.now()
        self.dayparts_parsed = 0
        self.playlists_generated = 0
        self.tracks_uploaded = 0
        self.playlists_created = 0
        self.playlists_linked = 0
        self.playlists_scheduled = 0
        self.total_cost = 0.0
        self.errors = []

    def report(self) -> str:
        """Generate final deployment report"""
        duration = datetime.now() - self.start_time

        report = f"""
{'='*80}
COMPLETE END-TO-END DEPLOYMENT REPORT
{'='*80}

Execution Time: {duration}
Start: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}
End: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

STEP 1: PARSE STATION IDENTITY
   Dayparts Parsed: {self.dayparts_parsed}

STEP 2: GENERATE AI PLAYLISTS
   Playlists Generated: {self.playlists_generated}/42
   Total AI Cost: ${self.total_cost:.2f}

STEP 3: UPLOAD TRACKS
   Tracks Uploaded: {self.tracks_uploaded}

STEP 4: CREATE PLAYLISTS
   Playlists Created: {self.playlists_created}

STEP 5: LINK TRACKS
   Playlists Linked: {self.playlists_linked}

STEP 6: SCHEDULE PLAYLISTS
   Playlists Scheduled: {self.playlists_scheduled}

STEP 7: VERIFICATION
   Status: {'✅ SUCCESS' if self.is_complete() else '❌ FAILURE'}
   Expected Playlists: 42
   Actual Playlists: {self.playlists_generated}

ERRORS: {len(self.errors)}
"""
        if self.errors:
            report += "\nError Details:\n"
            for i, error in enumerate(self.errors, 1):
                report += f"   {i}. {error}\n"

        report += f"\n{'='*80}\n"
        return report

    def is_complete(self) -> bool:
        """Check if deployment completed successfully"""
        return (
            self.playlists_generated == 42 and
            self.playlists_created == 42 and
            self.playlists_linked == 42 and
            self.playlists_scheduled == 42 and
            len(self.errors) == 0
        )


async def complete_end_to_end() -> DeploymentMetrics:
    """
    Execute complete end-to-end AI playlist automation workflow

    Returns:
        DeploymentMetrics: Complete deployment metrics and status
    """
    metrics = DeploymentMetrics()

    try:
        # ========================================================================
        # STEP 1: Parse station-identity.md
        # ========================================================================
        logger.info("="*80)
        logger.info("STEP 1: PARSING STATION IDENTITY DOCUMENT")
        logger.info("="*80)

        parser = DocumentParser()
        # Use config module to resolve station identity path
        station_identity_path = get_station_identity_path()
        station_identity = parser.load_document(station_identity_path)

        # Get weekday programming structure
        weekday_structure = next(
            (s for s in station_identity.programming_structures
             if s.schedule_type.value == "weekday"),
            None
        )

        if not weekday_structure:
            error = "No weekday programming structure found in station-identity.md"
            logger.error(error)
            metrics.errors.append(error)
            return metrics

        dayparts = weekday_structure.dayparts
        metrics.dayparts_parsed = len(dayparts)

        logger.info(f"✓ Parsed {len(dayparts)} dayparts from station-identity.md")
        logger.info(f"  Expected playlists: 7 days × {len(dayparts)} dayparts = {7 * len(dayparts)}")

        # ========================================================================
        # STEP 2: Initialize clients and generate AI playlists
        # ========================================================================
        logger.info("\n" + "="*80)
        logger.info("STEP 2: INITIALIZING CLIENTS AND GENERATING AI PLAYLISTS")
        logger.info("="*80)

        config = AIPlaylistConfig.from_environment()
        subsonic = SubsonicClient(config.to_subsonic_config())
        azuracast = AzuraCastSync()

        # Initialize batch generator with $10 budget
        batch_generator = BatchPlaylistGenerator(
            openai_api_key=config.openai_api_key,
            subsonic_client=subsonic,
            total_budget=10.0,
            allocation_strategy='dynamic',
            timeout_seconds=2700  # 45 minutes per batch
        )

        all_playlists: List[GeneratedPlaylist] = []
        today = datetime.now().date()

        # Generate playlists for 7 days starting from tomorrow
        # This ensures fresh content and allows the cron to run any day of the week
        # Example: If run Sunday 4am, generates Mon-Sun. If run Tuesday 1am, generates Wed-Tue.
        for day_offset in range(1, 8):  # Changed from range(7) to range(1, 8)
            generation_date = today + timedelta(days=day_offset)
            day_name = generation_date.strftime('%A')

            logger.info(f"\n🤖 Generating AI playlists for {day_name}, {generation_date}")
            logger.info(f"   Day {day_offset}/7 | Dayparts: {len(dayparts)}")

            try:
                day_playlists = await batch_generator.generate_batch(
                    dayparts=dayparts,
                    generation_date=generation_date
                )

                # Save M3U files
                playlists_dir = Path("/workspaces/emby-to-m3u/playlists")
                playlists_dir.mkdir(parents=True, exist_ok=True)

                for playlist in day_playlists:
                    save_playlist_file(playlist, playlists_dir)
                    all_playlists.append(playlist)
                    metrics.playlists_generated += 1

                logger.info(f"✓ Generated {len(day_playlists)} playlists for {day_name}")
                logger.info(f"  Total progress: {metrics.playlists_generated}/42 playlists")

            except Exception as e:
                error = f"Failed to generate playlists for {day_name}: {str(e)}"
                logger.error(error)
                metrics.errors.append(error)
                continue

        # Calculate total cost from generated playlists
        metrics.total_cost = sum(float(p.cost_actual) for p in all_playlists)

        logger.info(f"\n✓ STEP 2 COMPLETE: Generated {len(all_playlists)} playlists")
        logger.info(f"  Total AI Cost: ${metrics.total_cost:.2f}")

        if len(all_playlists) != 42:
            error = f"Expected 42 playlists, generated {len(all_playlists)}"
            logger.warning(error)
            metrics.errors.append(error)

        # ========================================================================
        # STEP 3, 4, 5: Upload tracks, create playlists, link tracks
        # ========================================================================
        logger.info("\n" + "="*80)
        logger.info("STEPS 3-5: UPLOADING TRACKS AND CREATING AZURACAST PLAYLISTS")
        logger.info("="*80)

        for i, playlist in enumerate(all_playlists, 1):
            logger.info(f"\n[{i}/{len(all_playlists)}] Processing: {playlist.name}")

            try:
                # Convert SelectedTrack objects to dict format for AzuraCast
                track_list = []
                for track in playlist.tracks:
                    track_dict = {
                        "Name": track.title,
                        "AlbumArtist": track.artist,
                        "Album": track.album,
                        "subsonic_id": track.track_id,
                        "Duration": track.duration_seconds
                    }
                    track_list.append(track_dict)

                logger.info(f"  Tracks to upload: {len(track_list)}")

                # STEP 3: Upload all tracks (with duplicate detection)
                azuracast.upload_playlist(track_list)
                metrics.tracks_uploaded += len(track_list)
                logger.info(f"  ✓ Uploaded tracks (duplicates handled)")

                # STEP 4: Create/clear playlist in AzuraCast
                azuracast.clear_playlist_by_name(playlist.name)
                playlist_info = azuracast.get_playlist(playlist.name)

                if not playlist_info:
                    playlist_info = azuracast.create_playlist(playlist.name)
                    logger.info(f"  ✓ Created playlist in AzuraCast")
                else:
                    logger.info(f"  ✓ Cleared existing playlist")

                metrics.playlists_created += 1

                # STEP 5: Link tracks in AI-determined order
                linked_count = 0
                for track_dict in track_list:
                    if "azuracast_file_id" in track_dict:
                        azuracast.add_to_playlist(
                            track_dict["azuracast_file_id"],
                            playlist_info["id"]
                        )
                        linked_count += 1

                metrics.playlists_linked += 1
                logger.info(f"  ✓ Linked {linked_count} tracks in correct order")

                # STEP 6: Schedule playlist with daypart timing
                # Extract daypart name and date from playlist name (format: "Daypart Name - YYYY-MM-DD")
                parts = playlist.name.rsplit(" - ", 1)
                if len(parts) != 2:
                    logger.warning(f"  ⚠ Invalid playlist name format: '{playlist.name}'")
                    continue

                daypart_name = parts[0]
                date_str = parts[1]

                # Parse the date to get the day of week
                try:
                    playlist_date = datetime.strptime(date_str, "%Y-%m-%d")
                    day_of_week = playlist_date.weekday()  # 0=Monday, 6=Sunday

                    # Convert to AzuraCast format (0=Sunday, 1=Monday, ..., 6=Saturday)
                    azuracast_day = (day_of_week + 1) % 7

                except ValueError as e:
                    logger.error(f"  ✗ Invalid date format in playlist name: {date_str} - {e}")
                    continue

                if daypart_name in DAYPART_SCHEDULE:
                    schedule_config = DAYPART_SCHEDULE[daypart_name]

                    # Schedule for ONLY this specific date, not recurring
                    # Set start_date and end_date to the same date for non-recurring schedule
                    success = azuracast.schedule_playlist(
                        playlist.name,
                        start_time=schedule_config["start_time"],
                        end_time=schedule_config["end_time"],
                        days=[azuracast_day],  # Single day only!
                        start_date=date_str,   # YYYY-MM-DD format
                        end_date=date_str      # Same date = play only once
                    )

                    if success:
                        metrics.playlists_scheduled += 1
                        day_names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
                        logger.info(
                            f"  ✓ Scheduled for {day_names[azuracast_day]} {date_str} "
                            f"{schedule_config['start_time']}-{schedule_config['end_time']}"
                        )
                    else:
                        error = f"Failed to schedule playlist '{playlist.name}'"
                        logger.error(error)
                        metrics.errors.append(error)
                else:
                    logger.warning(f"  ⚠ No schedule mapping for daypart '{daypart_name}'")

            except Exception as e:
                error = f"Failed to process playlist '{playlist.name}': {str(e)}"
                logger.error(error)
                metrics.errors.append(error)
                continue

        # ========================================================================
        # STEP 7: Verification
        # ========================================================================
        logger.info("\n" + "="*80)
        logger.info("STEP 7: VERIFICATION")
        logger.info("="*80)

        logger.info(f"Playlists generated: {metrics.playlists_generated}/42")
        logger.info(f"Tracks uploaded: {metrics.tracks_uploaded}")
        logger.info(f"Playlists created: {metrics.playlists_created}/42")
        logger.info(f"Playlists linked: {metrics.playlists_linked}/42")
        logger.info(f"Playlists scheduled: {metrics.playlists_scheduled}/42")

        if metrics.is_complete():
            logger.info("\n🎉 COMPLETE END-TO-END SUCCESS")
        else:
            logger.error("\n❌ DEPLOYMENT FAILED - NOT ALL STEPS COMPLETED")

    except Exception as e:
        error = f"Critical deployment error: {str(e)}"
        logger.error(error)
        metrics.errors.append(error)

    return metrics


def main():
    """Main entry point for deployment"""
    logger.info("="*80)
    logger.info("COMPLETE END-TO-END AI PLAYLIST AUTOMATION SYSTEM")
    logger.info("Production Deployment - All 6 Steps Required")
    logger.info("="*80)

    # Run deployment
    metrics = asyncio.run(complete_end_to_end())

    # Generate and save report
    report = metrics.report()
    logger.info(report)

    # Save report to file
    report_path = Path("/workspaces/emby-to-m3u/logs/e2e_deployment_report.txt")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report)

    logger.info(f"Report saved to: {report_path}")

    # Exit with appropriate code
    sys.exit(0 if metrics.is_complete() else 1)


if __name__ == "__main__":
    main()
