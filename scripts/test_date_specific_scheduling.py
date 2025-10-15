#!/usr/bin/env python3
"""Test date-specific playlist scheduling to ensure non-recurring schedules."""

import logging
import sys
from pathlib import Path
from datetime import datetime

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.azuracast.main import AzuraCastSync
from src.logger import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


def test_date_specific_schedule():
    """Test scheduling a playlist for a specific date only (non-recurring)."""
    logger.info("="*80)
    logger.info("TESTING DATE-SPECIFIC PLAYLIST SCHEDULING")
    logger.info("="*80)

    # Initialize AzuraCast client
    azuracast = AzuraCastSync()

    # Test with "The Session - 2025-10-14" (Tuesday)
    playlist_name = "The Session - 2025-10-14"

    # Extract date from playlist name
    parts = playlist_name.rsplit(" - ", 1)
    if len(parts) != 2:
        logger.error(f"Invalid playlist name format: '{playlist_name}'")
        return False

    daypart_name = parts[0]
    date_str = parts[1]

    # Parse date to get day of week
    try:
        playlist_date = datetime.strptime(date_str, "%Y-%m-%d")
        day_of_week = playlist_date.weekday()  # 0=Monday, 6=Sunday

        # Convert to AzuraCast format (0=Sunday, 1=Monday, ..., 6=Saturday)
        azuracast_day = (day_of_week + 1) % 7

        day_names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
        logger.info(f"\nPlaylist: {playlist_name}")
        logger.info(f"  Date: {date_str} ({day_names[azuracast_day]})")
        logger.info(f"  Day of week: {azuracast_day} (AzuraCast format)")

    except ValueError as e:
        logger.error(f"Invalid date format: {date_str} - {e}")
        return False

    # Schedule configuration for "The Session" (10:00-15:00, weekdays)
    start_time = "10:00"
    end_time = "15:00"

    logger.info(f"  Time range: {start_time} - {end_time}")
    logger.info(f"  Start date: {date_str}")
    logger.info(f"  End date: {date_str}")
    logger.info("\n🎯 KEY TEST: start_date == end_date should make this NON-RECURRING")

    # Attempt to schedule with date-specific parameters
    success = azuracast.schedule_playlist(
        playlist_name=playlist_name,
        start_time=start_time,
        end_time=end_time,
        days=[azuracast_day],  # Tuesday only
        start_date=date_str,   # 2025-10-14
        end_date=date_str      # Same date = non-recurring
    )

    if success:
        logger.info("\n✅ SUCCESS: Date-specific scheduling test passed")
        logger.info(f"   '{playlist_name}' is now scheduled for:")
        logger.info(f"   - Date: {date_str} ({day_names[azuracast_day]} ONLY)")
        logger.info(f"   - Time: {start_time}-{end_time}")
        logger.info(f"   - Recurring: NO (start_date == end_date)")
        logger.info("\n📋 VERIFICATION STEPS:")
        logger.info("   1. Log into AzuraCast web interface")
        logger.info("   2. Navigate to Playlists")
        logger.info(f"   3. Open '{playlist_name}'")
        logger.info("   4. Check the 'Schedule' tab - you should see:")
        logger.info(f"      - Start Date: {date_str}")
        logger.info(f"      - End Date: {date_str}")
        logger.info(f"      - Time: {start_time} - {end_time}")
        logger.info(f"      - Day: {day_names[azuracast_day]}")
        logger.info("   5. Verify it does NOT appear on future Tuesdays")
        return True
    else:
        logger.error("\n❌ FAILURE: Date-specific scheduling test failed")
        logger.error("   Check the error messages above for details")
        return False


if __name__ == "__main__":
    try:
        success = test_date_specific_schedule()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"Test failed with exception: {e}", exc_info=True)
        sys.exit(1)
