#!/usr/bin/env python3
"""CLI for Epic Worker - Intelligent epic/issue prioritization and autonomous completion."""

import argparse
import logging
import os
import sys
from pathlib import Path

from ..config.models import GitHubConfig
from ..core.epic_worker import EpicWorker
from ..core.logging_setup import get_logger

logger = get_logger(__name__)


def validate_repository(repo: str) -> str:
    """Validate repository format."""
    if not repo or "/" not in repo:
        raise argparse.ArgumentTypeError(
            f"Invalid repository format: {repo}. Use OWNER/REPO format."
        )
    
    parts = repo.split("/")
    if len(parts) != 2 or not all(parts):
        raise argparse.ArgumentTypeError(
            f"Invalid repository format: {repo}. Use OWNER/REPO format."
        )
    
    # Basic validation for allowed characters
    import re
    if not re.match(r'^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$', repo):
        raise argparse.ArgumentTypeError(
            f"Repository contains invalid characters: {repo}"
        )
    
    return repo


def validate_positive_int(value: str, name: str) -> int:
    """Validate positive integer."""
    try:
        int_value = int(value)
        if int_value <= 0:
            raise argparse.ArgumentTypeError(
                f"{name} must be a positive integer, got: {value}"
            )
        return int_value
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"{name} must be a valid integer, got: {value}"
        )


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Autonomously work through GitHub epics and issues with intelligent prioritization",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --repo aperim/telegram-mcp
  %(prog)s --repo aperim/telegram-mcp --agents 15 --no-merge
  %(prog)s --repo aperim/project --namespace custom-worker
"""
    )
    
    parser.add_argument(
        "--repo", "-r",
        type=validate_repository,
        required=True,
        help="Target repository (OWNER/REPO format)"
    )
    
    parser.add_argument(
        "--namespace", "-n",
        type=str,
        default="epic-worker",
        help="Hive namespace (default: epic-worker)"
    )
    
    parser.add_argument(
        "--agents", "-a",
        type=lambda x: validate_positive_int(x, "agents"),
        default=10,
        help="Maximum agents to spawn (default: 10)"
    )
    
    parser.add_argument(
        "--no-merge",
        action="store_true",
        help="Don't auto-merge PRs (wait for manual review)"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    # Set up logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        # Create configuration
        config = GitHubConfig(
            repository=args.repo,
            hive_namespace=args.namespace,
            max_agents=args.agents,
            auto_merge=not args.no_merge,
            dry_run=args.dry_run
        )
        
        logger.info("🎯 Aperim Template: Autonomous Epic Worker")
        logger.info("Repository: %s", config.repository)
        logger.info("Auto-merge: %s", config.auto_merge)
        logger.info("Max agents: %d", config.max_agents)
        
        if args.dry_run:
            logger.info("DRY RUN MODE - No changes will be made")
        
        # Run epic worker
        worker = EpicWorker(config)
        worker.run()
        
    except KeyboardInterrupt:
        logger.info("\nEpic worker interrupted by user")
        sys.exit(0)
    except Exception as e:
        # Safely format error message to avoid Rich markup issues
        error_msg = str(e).replace('[', '\\[').replace(']', '\\]')
        logger.error(f"Epic worker failed: {error_msg}")
        if args.verbose:
            logger.exception("Full error details:")
        sys.exit(1)


if __name__ == "__main__":
    main()