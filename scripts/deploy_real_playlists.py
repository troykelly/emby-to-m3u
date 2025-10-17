#!/usr/bin/env python3
"""
Deploy REAL AI Playlist Generation System

This script generates 42 playlists (7 dayparts x 6 days) using REAL AI with:
- GPT-5 with tool calling for track selection
- Dynamic track discovery from Subsonic library
- Full AzuraCast integration with track upload and linking
- Station-identity.md constraint enforcement
- $10.00 total budget across all playlists
"""

import asyncio
import sys
import os
import logging
from pathlib import Path
from datetime import date, timedelta
from decimal import Decimal

# Add project root to path and change directory
project_root = Path(__file__).parent.parent.absolute()
os.chdir(str(project_root))  # Change to project root
sys.path.insert(0, str(project_root / "src"))

# Now import after path is set
from ai_playlist.config import AIPlaylistConfig
from ai_playlist.batch_executor import BatchPlaylistGenerator
from ai_playlist.document_parser import DocumentParser
from ai_playlist.workflow import save_playlist_file, sync_to_azuracast
from subsonic.client import SubsonicClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(project_root / "logs" / "playlist_deployment.log")
    ]
)
logger = logging.getLogger(__name__)


async def test_single_playlist():
    """Test with ONE playlist first to verify system works."""
    logger.info("=" * 80)
    logger.info("TEST MODE: Generating SINGLE playlist to verify system")
    logger.info("=" * 80)

    # 1. Load configuration
    logger.info("Step 1: Loading configuration from environment...")
    config = AIPlaylistConfig.from_environment()
    logger.info(f"✓ Configuration loaded: {config}")

    # 2. Connect to Subsonic
    logger.info("Step 2: Connecting to Subsonic server...")
    subsonic_client = SubsonicClient(config.to_subsonic_config())
    ping_result = subsonic_client.ping()
    if not ping_result:
        raise ConnectionError("Failed to connect to Subsonic server")
    logger.info("✓ Subsonic server connected")

    # 3. Load station identity
    logger.info("Step 3: Loading station-identity.md...")
    parser = DocumentParser()
    station_identity_path = project_root / "station-identity.md"
    station_identity = parser.load_document(station_identity_path)
    logger.info(f"✓ Loaded station identity from: {station_identity.document_path}")

    # 4. Get weekday dayparts
    logger.info("Step 4: Extracting weekday dayparts...")
    weekday_structure = next(
        (s for s in station_identity.programming_structures if s.schedule_type.value == "weekday"),
        None
    )
    if not weekday_structure:
        raise ValueError("No weekday programming structure found")

    dayparts = weekday_structure.dayparts
    logger.info(f"✓ Found {len(dayparts)} dayparts: {[dp.name for dp in dayparts]}")

    # 5. Select FIRST daypart for testing
    test_daypart = dayparts[0]
    logger.info(f"✓ Testing with daypart: {test_daypart.name}")

    # 6. Initialize batch generator
    logger.info("Step 5: Initializing batch playlist generator...")
    batch_generator = BatchPlaylistGenerator(
        openai_api_key=config.openai_api_key,
        subsonic_client=subsonic_client,
        total_budget=0.50,  # $0.50 for test
        allocation_strategy='dynamic',
        budget_mode='hard',
        timeout_seconds=2700  # 45 minutes for GPT-5
    )
    logger.info("✓ Batch generator initialized")

    # 7. Generate SINGLE playlist
    logger.info("Step 6: Generating REAL playlist with AI (this may take several minutes)...")
    generation_date = date.today()
    playlists = await batch_generator.generate_batch(
        dayparts=[test_daypart],
        generation_date=generation_date
    )

    if not playlists:
        raise RuntimeError("No playlists generated!")

    playlist = playlists[0]
    logger.info(f"✓ Generated playlist: {playlist.name}")
    logger.info(f"  - Tracks: {len(playlist.tracks)}")
    logger.info(f"  - Cost: ${playlist.cost_actual:.6f}")
    logger.info(f"  - Validation: {playlist.validation_result.overall_status.value}")
    logger.info(f"  - Compliance: {playlist.validation_result.compliance_percentage * 100:.1f}%")

    # 8. Save to file
    logger.info("Step 7: Saving playlist file...")
    output_dir = project_root / "playlists" / "test"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = save_playlist_file(playlist, output_dir)
    logger.info(f"✓ Saved to: {output_file}")

    # 9. Sync to AzuraCast
    logger.info("Step 8: Syncing to AzuraCast...")
    sync_results = await sync_to_azuracast([playlist])

    azuracast_id = sync_results.get(playlist.name)
    if azuracast_id:
        logger.info(f"✓ Synced to AzuraCast - Playlist ID: {azuracast_id}")
        logger.info(f"  - Check AzuraCast UI to verify tracks appear in playlist")
    else:
        logger.error("✗ Failed to sync to AzuraCast")
        return False

    logger.info("=" * 80)
    logger.info("TEST SUCCESSFUL!")
    logger.info(f"Playlist '{playlist.name}' created with {len(playlist.tracks)} tracks")
    logger.info(f"AzuraCast Playlist ID: {azuracast_id}")
    logger.info("=" * 80)

    return True


async def deploy_full_week():
    """Deploy full 42 playlists (7 dayparts x 6 days)."""
    logger.info("=" * 80)
    logger.info("FULL DEPLOYMENT: Generating 42 playlists for Monday-Saturday")
    logger.info("=" * 80)

    # 1. Load configuration
    logger.info("Step 1: Loading configuration from environment...")
    config = AIPlaylistConfig.from_environment()
    logger.info(f"✓ Configuration loaded")

    # 2. Connect to Subsonic
    logger.info("Step 2: Connecting to Subsonic server...")
    subsonic_client = SubsonicClient(config.to_subsonic_config())
    ping_result = subsonic_client.ping()
    if not ping_result:
        raise ConnectionError("Failed to connect to Subsonic server")
    logger.info("✓ Subsonic server connected")

    # 3. Load station identity
    logger.info("Step 3: Loading station-identity.md...")
    parser = DocumentParser()
    station_identity_path = project_root / "station-identity.md"
    station_identity = parser.load_document(station_identity_path)
    logger.info(f"✓ Loaded station identity")

    # 4. Get weekday dayparts
    logger.info("Step 4: Extracting weekday dayparts...")
    weekday_structure = next(
        (s for s in station_identity.programming_structures if s.schedule_type.value == "weekday"),
        None
    )
    if not weekday_structure:
        raise ValueError("No weekday programming structure found")

    dayparts = weekday_structure.dayparts
    logger.info(f"✓ Found {len(dayparts)} dayparts")

    # 5. Initialize batch generator with $10 budget
    logger.info("Step 5: Initializing batch generator ($10.00 budget)...")
    batch_generator = BatchPlaylistGenerator(
        openai_api_key=config.openai_api_key,
        subsonic_client=subsonic_client,
        total_budget=10.00,  # $10.00 total budget
        allocation_strategy='dynamic',
        budget_mode='hard',  # Hard limit - stop if exceeded
        timeout_seconds=2700  # 45 minutes per playlist
    )
    logger.info("✓ Batch generator initialized")

    # 6. Generate playlists for each day (Monday-Saturday)
    logger.info("Step 6: Generating playlists for 6 days...")
    output_dir = project_root / "playlists" / "production"
    output_dir.mkdir(parents=True, exist_ok=True)

    all_playlists = []
    total_cost = Decimal("0.00")

    for day_offset in range(6):  # Monday-Saturday
        generation_date = date.today() + timedelta(days=day_offset)
        day_name = generation_date.strftime("%A")

        logger.info(f"\n{'=' * 80}")
        logger.info(f"Generating playlists for {day_name} ({generation_date})")
        logger.info(f"{'=' * 80}")

        # Generate all dayparts for this day
        day_playlists = await batch_generator.generate_batch(
            dayparts=dayparts,
            generation_date=generation_date
        )

        # Track cost
        day_cost = sum(p.cost_actual for p in day_playlists)
        total_cost += day_cost

        logger.info(f"✓ Generated {len(day_playlists)} playlists for {day_name}")
        logger.info(f"  - Day cost: ${day_cost:.4f}")
        logger.info(f"  - Total cost so far: ${total_cost:.4f} / $10.00")

        # Save playlists to files
        for playlist in day_playlists:
            output_file = save_playlist_file(playlist, output_dir)
            logger.info(f"  - Saved: {output_file.name}")

        all_playlists.extend(day_playlists)

    logger.info(f"\n{'=' * 80}")
    logger.info("Step 7: Syncing ALL playlists to AzuraCast...")
    logger.info(f"{'=' * 80}")

    # 7. Sync all playlists to AzuraCast
    sync_results = await sync_to_azuracast(all_playlists)

    successful_syncs = sum(1 for azid in sync_results.values() if azid is not None)
    failed_syncs = len(all_playlists) - successful_syncs

    logger.info(f"\n{'=' * 80}")
    logger.info("DEPLOYMENT COMPLETE!")
    logger.info(f"{'=' * 80}")
    logger.info(f"Total playlists generated: {len(all_playlists)}")
    logger.info(f"Successfully synced to AzuraCast: {successful_syncs}")
    logger.info(f"Failed syncs: {failed_syncs}")
    logger.info(f"Total cost: ${total_cost:.4f} / $10.00")
    logger.info(f"Budget remaining: ${Decimal('10.00') - total_cost:.4f}")
    logger.info(f"{'=' * 80}")

    # Print detailed sync results
    logger.info("\nDetailed sync results:")
    for playlist_name, azuracast_id in sync_results.items():
        if azuracast_id:
            logger.info(f"  ✓ {playlist_name}: AzuraCast ID {azuracast_id}")
        else:
            logger.error(f"  ✗ {playlist_name}: FAILED")

    return successful_syncs == len(all_playlists)


async def main():
    """Main entry point."""
    # Create logs directory
    (project_root / "logs").mkdir(exist_ok=True)

    # Check if we should run test or full deployment
    mode = sys.argv[1] if len(sys.argv) > 1 else "test"

    try:
        if mode == "test":
            logger.info("Running in TEST mode (single playlist)")
            success = await test_single_playlist()
            if success:
                logger.info("\n" + "=" * 80)
                logger.info("TEST PASSED! Ready for full deployment.")
                logger.info("Run with 'python deploy_real_playlists.py full' to deploy all 42 playlists")
                logger.info("=" * 80)
                sys.exit(0)
            else:
                logger.error("TEST FAILED!")
                sys.exit(1)

        elif mode == "full":
            logger.info("Running FULL deployment (42 playlists)")
            success = await deploy_full_week()
            sys.exit(0 if success else 1)

        else:
            logger.error(f"Unknown mode: {mode}")
            logger.info("Usage: python deploy_real_playlists.py [test|full]")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Deployment failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
