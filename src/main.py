#!/usr/bin/env python3
"""
AI Playlist Generation Entry Point with Cron Support

This script runs the AI-powered playlist generation system with optional
cron scheduling. It replaces the legacy Emby-based playlist generation.

Environment Variables:
- M3U_CRON: Cron expression for running the script periodically (optional).
- OPENAI_API_KEY: OpenAI API key for GPT-4
- SUBSONIC_URL: Subsonic/Navidrome server URL
- SUBSONIC_USERNAME: Subsonic username
- SUBSONIC_PASSWORD: Subsonic password
- AZURACAST_HOST: AzuraCast server URL
- AZURACAST_API_KEY: AzuraCast API key
- AZURACAST_STATIONID: AzuraCast station ID
- TZ: Timezone (optional, defaults to Etc/UTC)

Usage:
# Run once immediately:
$ python src/main.py

# Run on schedule (cron expression):
$ M3U_CRON="0 1 * * 6" python src/main.py  # Saturday at 1am

Author: Troy Kelly
Date: 15 October 2025
"""

import os
import sys
import signal
import logging
from datetime import datetime
from croniter import croniter
from time import sleep

from logger import setup_logging

# Set up logging
setup_logging()
logger = logging.getLogger(__name__)

VERSION = "__VERSION__"  # <-- This will be replaced during the release process


def handle_exception(exc_type, exc_value, exc_traceback):
    """Handle uncaught exceptions"""
    if issubclass(exc_type, KeyboardInterrupt):
        # Allow the default exception handler for KeyboardInterrupt
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logger.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))


def handle_signal(signum, frame):
    """Handle termination signals"""
    logger.critical(f"Received signal {signum}. Exiting.")
    sys.exit(1)


def run_ai_playlist_generation() -> None:
    """
    Run the complete AI playlist generation workflow.

    This imports and runs the deployment script that:
    1. Parses station-identity.md for daypart definitions
    2. Generates AI playlists using GPT-4 with tool calling
    3. Uploads tracks to AzuraCast with duplicate detection
    4. Creates playlists in AzuraCast
    5. Links tracks in AI-determined order
    6. Schedules playlists with daypart timing
    7. Verifies complete deployment
    """
    logger.info("Starting AI playlist generation workflow")

    try:
        # Import the deployment script
        import asyncio
        from pathlib import Path

        # Import deployment functions
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        from deploy_playlists import complete_end_to_end, DeploymentMetrics

        # Run the complete end-to-end deployment
        logger.info("="*80)
        logger.info("COMPLETE END-TO-END AI PLAYLIST AUTOMATION SYSTEM")
        logger.info("Production Deployment - All 6 Steps Required")
        logger.info("="*80)

        metrics = asyncio.run(complete_end_to_end())

        # Generate and save report
        report = metrics.report()
        logger.info(report)

        # Save report to file
        report_path = Path("logs/e2e_deployment_report.txt")
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report)

        logger.info(f"Report saved to: {report_path}")

        if metrics.is_complete():
            logger.info("✅ AI playlist generation completed successfully")
        else:
            logger.error("❌ AI playlist generation incomplete - check logs for errors")

    except Exception as e:
        logger.error(f"AI playlist generation failed: {e}", exc_info=True)
        raise


def cron_schedule(cron_expression: str) -> None:
    """
    Schedule the job based on the cron expression.

    Args:
        cron_expression: The cron expression for scheduling (e.g., "0 1 * * 6" for Saturday 1am)
    """
    logger.info(f"Scheduling AI playlist generation with cron expression: {cron_expression}")

    while True:
        now = datetime.now()
        iter = croniter(cron_expression, now)
        next_run = iter.get_next(datetime)
        delay = (next_run - now).total_seconds()

        logger.info(f"Next run scheduled at {next_run} (in {delay:.0f} seconds)")
        sleep(delay)

        logger.info("Running scheduled AI playlist generation")
        try:
            run_ai_playlist_generation()
            logger.info("Scheduled job execution completed")
        except Exception as e:
            logger.error(f"Scheduled job failed: {e}", exc_info=True)


if __name__ == "__main__":
    # Install exception handler for uncaught exceptions
    sys.excepthook = handle_exception

    # Register signal handlers
    signals_to_catch = [signal.SIGINT, signal.SIGTERM, signal.SIGHUP, signal.SIGQUIT]

    for sig in signals_to_catch:
        signal.signal(sig, handle_signal)

    try:
        if VERSION != "__VERSION__":
            logger.info(f"AI Playlist Generator Version {VERSION}")

        cron_expression = os.getenv("M3U_CRON")

        if cron_expression:
            try:
                # Validate cron expression
                croniter(cron_expression)
                logger.info("Cron expression is valid.")
                cron_schedule(cron_expression)
            except (ValueError, TypeError):
                logger.error(f"Invalid cron expression: {cron_expression}")
                sys.exit(1)
        else:
            # Run once immediately
            logger.info("No cron expression set - running AI playlist generation once")
            run_ai_playlist_generation()

    except Exception as e:
        logger.error("Exception in main execution block:", exc_info=True)
        sys.exit(1)
