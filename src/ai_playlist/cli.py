"""
AI Playlist CLI - Command Line Interface

Implements T030 specification with argparse-based CLI for playlist automation.
"""

import argparse
import asyncio
import sys
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Any

from .main import run_automation
from .exceptions import (
    ParseError,
    ValidationError,
    CostExceededError,
    MCPToolError,
    APIError,
)

# Configure logging format
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)


def create_parser() -> argparse.ArgumentParser:
    """
    Create argument parser for CLI.

    Returns:
        Configured ArgumentParser instance
    """
    parser = argparse.ArgumentParser(
        prog="python -m src.ai_playlist",
        description="AI-powered radio playlist automation system",
        epilog="Example: python -m src.ai_playlist --input docs/station-identity.md --output playlists/",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Required arguments
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        metavar="FILE",
        help="Path to programming document (station-identity.md)",
    )

    parser.add_argument(
        "--output",
        type=str,
        required=True,
        metavar="DIR",
        help="Directory for playlist output files",
    )

    # Optional arguments
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip AzuraCast sync (generate playlists only)",
    )

    parser.add_argument(
        "--max-cost",
        type=float,
        default=0.50,
        metavar="USD",
        help="Maximum total LLM cost in USD (default: 0.50)",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose debug logging",
    )

    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 1.0.0",
    )

    return parser


def validate_arguments(args: argparse.Namespace) -> None:
    """
    Validate CLI arguments.

    Args:
        args: Parsed arguments

    Raises:
        ValueError: If arguments are invalid
    """
    # Validate input file exists
    input_path = Path(args.input)
    if not input_path.exists():
        raise ValueError(f"Input file not found: {args.input}")

    if not input_path.is_file():
        raise ValueError(f"Input path is not a file: {args.input}")

    # Validate max cost
    if args.max_cost <= 0:
        raise ValueError(f"Max cost must be > 0 (got: ${args.max_cost})")

    if args.max_cost > 10.0:
        logger.warning(
            f"Max cost ${args.max_cost:.2f} is unusually high. "
            f"Typical automation costs $0.10-$0.50"
        )

    # Validate output directory is writable (create if doesn't exist)
    output_path = Path(args.output)
    try:
        output_path.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise ValueError(f"Cannot create output directory {args.output}: {e}")


def display_progress_header(args: argparse.Namespace) -> None:
    """
    Display CLI header with configuration.

    Args:
        args: Parsed arguments
    """
    print()
    print("=" * 70)
    print("AI PLAYLIST AUTOMATION")
    print("=" * 70)
    print(f"Input document:  {args.input}")
    print(f"Output directory: {args.output}")
    print(f"Max cost:        ${args.max_cost:.2f}")
    print(f"Dry run:         {args.dry_run}")
    print(f"Started:         {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print()


def display_progress_update(
    stage: str,
    playlists_processed: int,
    total_playlists: int,
    current_time: float,
    current_cost: float,
) -> None:
    """
    Display progress update during execution.

    Args:
        stage: Current processing stage
        playlists_processed: Number of playlists processed
        total_playlists: Total number of playlists
        current_time: Current execution time in seconds
        current_cost: Current total cost in USD
    """
    if total_playlists > 0:
        progress_pct = (playlists_processed / total_playlists) * 100
        print(
            f"[{stage}] Progress: {playlists_processed}/{total_playlists} "
            f"({progress_pct:.0f}%) | Time: {current_time:.1f}s | Cost: ${current_cost:.4f}"
        )
    else:
        print(f"[{stage}] Time: {current_time:.1f}s | Cost: ${current_cost:.4f}")


def display_summary(summary: dict[str, Any]) -> None:
    """
    Display execution summary.

    Args:
        summary: Summary dict from run_automation()
    """
    print()
    print("=" * 70)
    print("EXECUTION SUMMARY")
    print("=" * 70)
    print(f"Total playlists:     {summary['playlist_count']}")
    print(f"Successful:          {summary['success_count']}")
    print(f"Failed:              {summary['failed_count']}")
    print(f"Total cost:          ${summary['total_cost']:.4f}")
    print(f"Total time:          {summary['total_time']:.1f}s")
    print()
    print(f"Output files:        {len(summary['output_files'])} playlists")
    print(f"Decision log:        {summary['decision_log']}")
    print("=" * 70)
    print()

    if summary["failed_count"] > 0:
        logger.warning(
            f"{summary['failed_count']} playlists failed validation. "
            f"Check decision log for details."
        )


def display_error(error: Exception) -> None:
    """
    Display error message with appropriate context.

    Args:
        error: Exception that occurred
    """
    print()
    print("=" * 70)
    print("ERROR")
    print("=" * 70)

    if isinstance(error, FileNotFoundError):
        print(f"File not found: {error}")
        print()
        print("Please check that the input file path is correct.")

    elif isinstance(error, ParseError):
        print(f"Document parsing failed: {error}")
        print()
        print("Please check that the programming document is valid markdown")
        print("with properly formatted daypart specifications.")

    elif isinstance(error, ValidationError):
        print(f"Validation failed: {error}")
        print()
        print("No playlists passed quality validation.")
        print("Try adjusting constraints or check the decision log for details.")

    elif isinstance(error, CostExceededError):
        print(f"Cost exceeded: {error}")
        print()
        print("Consider increasing --max-cost or reducing the number of playlists.")

    elif isinstance(error, MCPToolError):
        print(f"MCP server error: {error}")
        print()
        print("Please ensure:")
        print("1. SUBSONIC_MCP_URL environment variable is set")
        print("2. Subsonic MCP server is running and accessible")
        print("3. Required tools (search_tracks, get_genres, etc.) are available")

    elif isinstance(error, APIError):
        print(f"API error: {error}")
        print()
        print("Please ensure:")
        print("1. OPENAI_API_KEY environment variable is set")
        print("2. OpenAI API is accessible")
        print("3. API key has sufficient credits")

    else:
        print(f"Unexpected error: {error}")
        print()
        print("Please check the logs for more details.")

    print("=" * 70)
    print()


async def async_main(args: argparse.Namespace) -> int:
    """
    Async main function.

    Args:
        args: Parsed CLI arguments

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        # Validate arguments
        validate_arguments(args)

        # Display header
        display_progress_header(args)

        # Run automation
        summary = await run_automation(
            input_file=args.input,
            output_dir=args.output,
            max_cost_usd=args.max_cost,
            dry_run=args.dry_run,
        )

        # Display summary
        display_summary(summary)

        # Return success if at least one playlist succeeded
        if summary["success_count"] > 0:
            return 0
        else:
            logger.error("No playlists generated successfully")
            return 1

    except Exception as e:
        display_error(e)
        if args.verbose:
            logger.exception("Detailed error traceback:")
        return 1


def main() -> int:
    """
    Main CLI entry point.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    # Parse arguments
    parser = create_parser()
    args = parser.parse_args()

    # Configure logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Run async main
    try:
        exit_code = asyncio.run(async_main(args))
        return exit_code
    except KeyboardInterrupt:
        print()
        print("=" * 70)
        print("INTERRUPTED")
        print("=" * 70)
        print("Automation cancelled by user")
        print("=" * 70)
        print()
        return 1
    except Exception as e:
        logger.exception("Fatal error in CLI")
        return 1


if __name__ == "__main__":
    sys.exit(main())
