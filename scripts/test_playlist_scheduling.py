#!/usr/bin/env python3
"""Test playlist scheduling functionality with existing After Hours playlist."""

import logging
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.azuracast.main import AzuraCastSync
from src.logger import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


def test_schedule_after_hours():
    """Test scheduling the After Hours - 2025-10-09 playlist."""
    logger.info("="*80)
    logger.info("TESTING PLAYLIST SCHEDULING FUNCTIONALITY")
    logger.info("="*80)

    # Initialize AzuraCast client
    azuracast = AzuraCastSync()

    # Test playlist name
    playlist_name = "After Hours - 2025-10-09"

    # Schedule configuration for After Hours (19:00-00:00, Mon-Fri)
    start_time = "19:00"
    end_time = "00:00"  # Midnight
    days = [1, 2, 3, 4, 5]  # Monday-Friday

    logger.info(f"\nScheduling playlist: {playlist_name}")
    logger.info(f"  Time range: {start_time} - {end_time}")
    logger.info(f"  Days: {days} (1=Mon, 2=Tue, 3=Wed, 4=Thu, 5=Fri)")

    # Attempt to schedule
    success = azuracast.schedule_playlist(
        playlist_name=playlist_name,
        start_time=start_time,
        end_time=end_time,
        days=days
    )

    if success:
        logger.info("\n✅ SUCCESS: Playlist scheduling test passed")
        logger.info(f"   '{playlist_name}' is now scheduled for {start_time}-{end_time}")
        logger.info("\n📋 NEXT STEPS:")
        logger.info("   1. Log into AzuraCast web interface")
        logger.info("   2. Navigate to Playlists")
        logger.info(f"   3. Open '{playlist_name}'")
        logger.info("   4. Check the 'Schedule' tab - you should see:")
        logger.info(f"      - Start: {start_time}")
        logger.info(f"      - End: {end_time}")
        logger.info("      - Days: Mon, Tue, Wed, Thu, Fri")
        return True
    else:
        logger.error("\n❌ FAILURE: Playlist scheduling test failed")
        logger.error("   Check the error messages above for details")
        return False


if __name__ == "__main__":
    try:
        success = test_schedule_after_hours()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"Test failed with exception: {e}", exc_info=True)
        sys.exit(1)
