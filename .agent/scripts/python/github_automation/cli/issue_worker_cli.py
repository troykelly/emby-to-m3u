"""Command-line interface for GitHub Issue worker."""

import sys
from pathlib import Path

import click
from rich.console import Console

from ..config.settings import get_settings
from ..config.models import GitHubConfig
from ..core.exceptions import ConfigurationError
from ..core.issue_worker import IssueWorker

console = Console()


def validate_issue_number(issue: int) -> int:
    """Validate issue number for security."""
    if issue is not None:
        if not isinstance(issue, int):
            raise click.BadParameter("Issue number must be an integer")
        if issue < 1 or issue > 999999:
            raise click.BadParameter("Issue number must be between 1 and 999999")
    return issue


def validate_config_path(config: str) -> Path:
    """Validate configuration file path for security."""
    if config is None:
        return None
    
    try:
        config_path = Path(config).resolve()
    except Exception as e:
        raise click.BadParameter(f"Invalid config path: {e}")
    
    if not config_path.exists():
        raise click.BadParameter(f"Config file does not exist: {config}")
    if not config_path.is_file():
        raise click.BadParameter(f"Config path is not a file: {config}")
    if not config_path.suffix in [".json", ".yaml", ".yml", ".toml"]:
        raise click.BadParameter("Config file must be .json, .yaml, .yml, or .toml")
    
    return config_path


@click.command()
@click.option(
    "--repo",
    "-r",
    required=True,
    help="GitHub repository in OWNER/REPO format"
)
@click.option(
    "--issue",
    "-i",
    type=int,
    callback=lambda ctx, param, value: validate_issue_number(value),
    help="Specific issue number to process"
)
@click.option(
    "--max-agents",
    "-m",
    type=click.IntRange(1, 50),
    default=10,
    help="Maximum number of agents to spawn"
)
@click.option(
    "--namespace",
    "-n",
    default="github-issue-worker",
    help="Namespace for hive-mind instances"
)
@click.option(
    "--require-tests/--no-require-tests",
    default=True,
    help="Require comprehensive tests for implementations"
)
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True),
    callback=lambda ctx, param, value: validate_config_path(value),
    help="Path to configuration file"
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Run in dry-run mode without making changes"
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose output"
)
def main(
    repo: str,
    issue: int,
    max_agents: int,
    namespace: str,
    require_tests: bool,
    config: Path,
    dry_run: bool,
    verbose: bool
):
    """GitHub Issue Worker - Automated issue implementation with Claude-Flow."""
    try:
        # Load settings
        settings = get_settings(config_file=config)
        
        # Override with CLI arguments
        github_config = GitHubConfig(
            repository=repo,
            hive_namespace=namespace,
            max_agents=max_agents,
            require_tests=require_tests,
            dry_run=dry_run
        )
        
        # Create and run worker
        worker = IssueWorker(github_config)
        
        console.print(f"[bold green]Starting Issue Worker for {repo}[/bold green]")
        if issue:
            console.print(f"[yellow]Processing Issue #{issue}[/yellow]")
        else:
            console.print("[yellow]Processing all open issues by priority[/yellow]")
            
        worker.run(issue_number=issue)
        
        console.print("[bold green]Issue Worker completed successfully[/bold green]")
        
    except ConfigurationError as e:
        console.print(f"[bold red]Configuration Error:[/bold red] {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Issue Worker interrupted by user[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"[bold red]Unexpected Error:[/bold red] {e}")
        if verbose:
            console.print_exception()
        sys.exit(1)


if __name__ == "__main__":
    main()