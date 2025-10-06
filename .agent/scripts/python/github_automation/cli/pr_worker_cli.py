"""Command-line interface for GitHub PR worker."""

import sys
from pathlib import Path

import click
from rich.console import Console

from ..config.settings import get_settings
from ..config.models import GitHubConfig
from ..core.exceptions import ConfigurationError
from ..core.pr_worker import PRWorker

console = Console()


def validate_pr_number(pr: int) -> int:
    """Validate PR number for security."""
    if pr is not None:
        if not isinstance(pr, int):
            raise click.BadParameter("PR number must be an integer")
        if pr < 1 or pr > 999999:
            raise click.BadParameter("PR number must be between 1 and 999999")
    return pr


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
    "--pr",
    "-p",
    type=int,
    callback=lambda ctx, param, value: validate_pr_number(value),
    help="Specific PR number to process"
)
@click.option(
    "--auto-merge/--no-auto-merge",
    default=True,
    help="Enable automatic merging when ready"
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
    default="github-pr-worker",
    help="Namespace for hive-mind instances"
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
    pr: int,
    auto_merge: bool,
    max_agents: int,
    namespace: str,
    config: Path,
    dry_run: bool,
    verbose: bool
):
    """GitHub PR Worker - Automated pull request processing with Claude-Flow."""
    try:
        # Load settings
        settings = get_settings(config_file=config)
        
        # Override with CLI arguments
        github_config = GitHubConfig(
            repository=repo,
            hive_namespace=namespace,
            max_agents=max_agents,
            auto_merge=auto_merge,
            dry_run=dry_run
        )
        
        # Create and run worker
        worker = PRWorker(github_config)
        
        console.print(f"[bold green]Starting PR Worker for {repo}[/bold green]")
        if pr:
            console.print(f"[yellow]Processing PR #{pr}[/yellow]")
        else:
            console.print("[yellow]Processing all open PRs[/yellow]")
            
        worker.run(pr_number=pr)
        
        console.print("[bold green]PR Worker completed successfully[/bold green]")
        
    except ConfigurationError as e:
        console.print(f"[bold red]Configuration Error:[/bold red] {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]PR Worker interrupted by user[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"[bold red]Unexpected Error:[/bold red] {e}")
        if verbose:
            console.print_exception()
        sys.exit(1)


if __name__ == "__main__":
    main()