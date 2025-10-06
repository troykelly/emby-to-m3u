"""Command-line interface for Claude log interpreter."""

import re
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console

from ..core.log_interpreter import LogInterpreter
from ..config.settings import get_settings
from ..core.exceptions import ConfigurationError


def validate_session_id(session: str) -> str:
    """Validate session ID for security."""
    if session is None:
        return None
    
    if not isinstance(session, str):
        raise click.BadParameter("Session ID must be a string")
    
    # Validate format (alphanumeric, hyphens, underscores only)
    if not re.match(r'^[a-zA-Z0-9_-]{1,64}$', session):
        raise click.BadParameter("Session ID contains invalid characters or is too long")
    
    return session


def validate_config_path(config: str) -> Path:
    """Validate configuration file path for security."""
    if config is None:
        return None
    
    try:
        config_path = Path(config).resolve()
    except Exception as e:
        raise click.BadParameter(f"Invalid config path: {e}")
    
    # Security checks
    if not config_path.exists():
        raise click.BadParameter(f"Config file does not exist: {config_path}")
    if not config_path.is_file():
        raise click.BadParameter(f"Config path is not a file: {config_path}")
    
    # Check file is readable
    try:
        with open(config_path, 'r') as f:
            f.read(1)
    except PermissionError:
        raise click.BadParameter(f"Config file not readable: {config_path}")
    except Exception as e:
        raise click.BadParameter(f"Config file error: {e}")
    
    return config_path


def validate_log_file(log_file: str) -> Path:
    """Validate log file path for security."""
    if log_file is None:
        return None
    
    try:
        log_path = Path(log_file).resolve()
    except Exception as e:
        raise click.BadParameter(f"Invalid log file path: {e}")
    
    # If file exists, check it's readable
    if log_path.exists():
        if not log_path.is_file():
            raise click.BadParameter(f"Log path is not a file: {log_path}")
        
        try:
            with open(log_path, 'r') as f:
                f.read(1)
        except PermissionError:
            raise click.BadParameter(f"Log file not readable: {log_path}")
        except Exception as e:
            raise click.BadParameter(f"Log file error: {e}")
    
    return log_path


@click.command()
@click.argument(
    'log_file', 
    type=click.Path(exists=False, path_type=Path), 
    required=False,
    callback=lambda ctx, param, value: validate_log_file(value)
)
@click.option('--follow', '-f', is_flag=True, help='Follow log file like tail -f')
@click.option('--filter', 'filter_type', type=click.Choice(['assistant', 'user', 'tool_use', 'tool_result']), 
              help='Filter by message type')
@click.option(
    '--session', 
    help='Filter by session ID',
    callback=lambda ctx, param, value: validate_session_id(value)
)
@click.option('--compact', is_flag=True, help='Use compact one-line format')
@click.option(
    '--config', 
    type=click.Path(exists=True, path_type=Path), 
    help='Configuration file path',
    callback=lambda ctx, param, value: validate_config_path(value)
)
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')
def main(
    log_file: Optional[Path],
    follow: bool,
    filter_type: Optional[str],
    session: Optional[str],
    compact: bool,
    config: Optional[Path],
    verbose: bool
):
    """
    Interpret Claude JSON logs and display them in human-readable format.
    
    If no LOG_FILE is provided, reads from stdin.
    """
    console = Console(stderr=True)
    
    try:
        # Load settings with validated config
        if config:
            settings = get_settings(config)
        else:
            settings = get_settings()
        
        if verbose:
            settings.verbose = True
        
        # Create interpreter
        interpreter = LogInterpreter(console)
        
        # Show header
        console.print("[blue]🎯 Claude Log Interpreter v1.0[/blue]")
        
        if filter_type:
            console.print(f"[blue]🔍 Filtering: {filter_type} messages[/blue]")
        if session:
            # Display session safely (already validated)
            console.print(f"[blue]🎯 Session: {session}[/blue]")
        if compact:
            console.print("[blue]📦 Compact mode enabled[/blue]")
        
        console.print()
        
        if log_file:
            # Process file with validated path
            if follow:
                interpreter.follow_file(log_file, compact, filter_type, session)
            else:
                interpreter.process_file(log_file, compact, filter_type, session)
        else:
            # Read from stdin securely
            if sys.stdin.isatty():
                console.print("[red]❌ No log file specified and no input piped[/red]", err=True)
                console.print("[yellow]💡 Usage: claude-log-interpreter <file> or pipe input[/yellow]", err=True)
                sys.exit(1)
            
            console.print("[blue]📥 Processing logs from stdin...[/blue]")
            console.print()
            
            # Process stdin with safety limits
            line_count = 0
            max_lines = 100000  # Prevent memory exhaustion
            
            for line in sys.stdin:
                line_count += 1
                if line_count > max_lines:
                    console.print(f"[yellow]⚠️  Reached maximum line limit ({max_lines}), stopping[/yellow]", err=True)
                    break
                
                try:
                    message = interpreter.parse_message(line)
                    if message and interpreter._should_display(message, filter_type, session):
                        formatted = interpreter.format_message(message, compact)
                        console.print(formatted)
                        if not compact:
                            console.print()
                except Exception as parse_error:
                    if verbose:
                        console.print(f"[yellow]⚠️  Failed to parse line {line_count}: {parse_error}[/yellow]", err=True)
                    # Continue processing other lines
                    continue
                        
    except KeyboardInterrupt:
        console.print("\n[yellow]👋 Interrupted by user[/yellow]")
        sys.exit(0)
    except ConfigurationError as e:
        console.print(f"[red]❌ Configuration error: {e}[/red]", err=True)
        sys.exit(1)
    except Exception as e:
        # Sanitize error message
        error_msg = str(e)
        if len(error_msg) > 200:
            error_msg = error_msg[:200] + "..."
        
        console.print(f"[red]❌ Error: {error_msg}[/red]", err=True)
        if verbose:
            console.print_exception()
        sys.exit(1)


if __name__ == "__main__":
    main()