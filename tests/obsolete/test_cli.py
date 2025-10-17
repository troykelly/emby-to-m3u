"""
Unit Tests for CLI Module

Tests argument parsing, validation, display functions, and main entry point.
"""

import pytest
import argparse
import asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from io import StringIO

from src.ai_playlist.cli import (
    create_parser,
    validate_arguments,
    display_progress_header,
    display_progress_update,
    display_summary,
    display_error,
    async_main,
    main
)
from src.ai_playlist.exceptions import (
    ParseError,
    ValidationError,
    CostExceededError,
    MCPToolError,
    APIError
)


class TestCreateParser:
    """Test suite for argument parser creation."""

    def test_creates_parser_with_correct_program_name(self):
        """Test parser is created with correct program name."""
        parser = create_parser()

        assert parser.prog == "python -m src.ai_playlist"

    def test_parser_has_required_arguments(self):
        """Test parser includes required --input and --output arguments."""
        parser = create_parser()

        # Parse with required args should succeed
        args = parser.parse_args(["--input", "test.md", "--output", "output/"])

        assert args.input == "test.md"
        assert args.output == "output/"

    def test_parser_missing_required_args_raises_error(self):
        """Test parser raises error when required args are missing."""
        parser = create_parser()

        with pytest.raises(SystemExit):
            parser.parse_args([])  # No arguments

    def test_parser_has_optional_arguments(self):
        """Test parser includes optional arguments."""
        parser = create_parser()

        args = parser.parse_args([
            "--input", "test.md",
            "--output", "output/",
            "--dry-run",
            "--max-cost", "1.0",
            "--verbose"
        ])

        assert args.dry_run is True
        assert args.max_cost == 1.0
        assert args.verbose is True

    def test_parser_default_values(self):
        """Test parser applies correct default values."""
        parser = create_parser()

        args = parser.parse_args(["--input", "test.md", "--output", "output/"])

        assert args.dry_run is False
        assert args.max_cost == 0.50
        assert args.verbose is False

    def test_parser_version_argument(self):
        """Test parser includes version argument."""
        parser = create_parser()

        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["--version"])

        assert exc_info.value.code == 0


class TestValidateArguments:
    """Test suite for argument validation."""

    def test_validate_with_valid_file(self, tmp_path):
        """Test validation succeeds with valid input file."""
        input_file = tmp_path / "test.md"
        input_file.write_text("# Test content")
        output_dir = tmp_path / "output"

        args = argparse.Namespace(
            input=str(input_file),
            output=str(output_dir),
            max_cost=0.50
        )

        # Should not raise
        validate_arguments(args)

        # Output directory should be created
        assert output_dir.exists()

    def test_validate_missing_input_file_raises_error(self, tmp_path):
        """Test validation raises ValueError for missing input file."""
        args = argparse.Namespace(
            input=str(tmp_path / "nonexistent.md"),
            output=str(tmp_path / "output"),
            max_cost=0.50
        )

        with pytest.raises(ValueError, match="Input file not found"):
            validate_arguments(args)

    def test_validate_input_is_directory_raises_error(self, tmp_path):
        """Test validation raises ValueError when input is a directory."""
        input_dir = tmp_path / "input_dir"
        input_dir.mkdir()

        args = argparse.Namespace(
            input=str(input_dir),
            output=str(tmp_path / "output"),
            max_cost=0.50
        )

        with pytest.raises(ValueError, match="not a file"):
            validate_arguments(args)

    def test_validate_negative_max_cost_raises_error(self, tmp_path):
        """Test validation raises ValueError for negative max cost."""
        input_file = tmp_path / "test.md"
        input_file.write_text("# Test")

        args = argparse.Namespace(
            input=str(input_file),
            output=str(tmp_path / "output"),
            max_cost=-1.0
        )

        with pytest.raises(ValueError, match="Max cost must be > 0"):
            validate_arguments(args)

    def test_validate_zero_max_cost_raises_error(self, tmp_path):
        """Test validation raises ValueError for zero max cost."""
        input_file = tmp_path / "test.md"
        input_file.write_text("# Test")

        args = argparse.Namespace(
            input=str(input_file),
            output=str(tmp_path / "output"),
            max_cost=0.0
        )

        with pytest.raises(ValueError, match="Max cost must be > 0"):
            validate_arguments(args)

    def test_validate_creates_output_directory(self, tmp_path):
        """Test validation creates output directory if it doesn't exist."""
        input_file = tmp_path / "test.md"
        input_file.write_text("# Test")
        output_dir = tmp_path / "nested" / "output"

        args = argparse.Namespace(
            input=str(input_file),
            output=str(output_dir),
            max_cost=0.50
        )

        validate_arguments(args)

        assert output_dir.exists()
        assert output_dir.is_dir()


class TestDisplayFunctions:
    """Test suite for display/output functions."""

    def test_display_progress_header(self, capsys, tmp_path):
        """Test progress header displays correctly."""
        args = argparse.Namespace(
            input="test.md",
            output="output/",
            max_cost=0.50,
            dry_run=False
        )

        display_progress_header(args)

        captured = capsys.readouterr()
        assert "AI PLAYLIST AUTOMATION" in captured.out
        assert "test.md" in captured.out
        assert "$0.50" in captured.out
        assert "False" in captured.out

    def test_display_progress_update_with_playlists(self, capsys):
        """Test progress update displays correctly."""
        display_progress_update(
            stage="Track Selection",
            playlists_processed=5,
            total_playlists=10,
            current_time=30.5,
            current_cost=0.12
        )

        captured = capsys.readouterr()
        assert "Track Selection" in captured.out
        assert "5/10" in captured.out
        assert "50%" in captured.out
        assert "30.5s" in captured.out
        assert "$0.1200" in captured.out

    def test_display_progress_update_no_playlists(self, capsys):
        """Test progress update without playlist count."""
        display_progress_update(
            stage="Parsing",
            playlists_processed=0,
            total_playlists=0,
            current_time=5.2,
            current_cost=0.00
        )

        captured = capsys.readouterr()
        assert "Parsing" in captured.out
        assert "5.2s" in captured.out
        assert "$0.0000" in captured.out

    def test_display_summary(self, capsys):
        """Test summary displays all key metrics."""
        summary = {
            "playlist_count": 10,
            "success_count": 8,
            "failed_count": 2,
            "total_cost": 0.35,
            "total_time": 120.5,
            "output_files": ["playlist1.json", "playlist2.json"],
            "decision_log": "/path/to/log.jsonl"
        }

        display_summary(summary)

        captured = capsys.readouterr()
        assert "EXECUTION SUMMARY" in captured.out
        assert "10" in captured.out  # Total playlists
        assert "8" in captured.out   # Successful
        assert "2" in captured.out   # Failed
        assert "$0.3500" in captured.out
        assert "120.5s" in captured.out

    def test_display_error_file_not_found(self, capsys):
        """Test error display for FileNotFoundError."""
        error = FileNotFoundError("test.md not found")

        display_error(error)

        captured = capsys.readouterr()
        assert "ERROR" in captured.out
        assert "File not found" in captured.out

    def test_display_error_parse_error(self, capsys):
        """Test error display for ParseError."""
        error = ParseError("Failed to parse document")

        display_error(error)

        captured = capsys.readouterr()
        assert "ERROR" in captured.out
        assert "Document parsing failed" in captured.out

    def test_display_error_validation_error(self, capsys):
        """Test error display for ValidationError."""
        error = ValidationError("No playlists passed validation")

        display_error(error)

        captured = capsys.readouterr()
        assert "ERROR" in captured.out
        assert "Validation failed" in captured.out

    def test_display_error_cost_exceeded(self, capsys):
        """Test error display for CostExceededError."""
        error = CostExceededError("Cost exceeded $0.50")

        display_error(error)

        captured = capsys.readouterr()
        assert "ERROR" in captured.out
        assert "Cost exceeded" in captured.out

    def test_display_error_mcp_tool_error(self, capsys):
        """Test error display for MCPToolError."""
        error = MCPToolError("MCP server unavailable")

        display_error(error)

        captured = capsys.readouterr()
        assert "ERROR" in captured.out
        assert "MCP server error" in captured.out
        assert "SUBSONIC_MCP_URL" in captured.out

    def test_display_error_api_error(self, capsys):
        """Test error display for APIError."""
        error = APIError("OpenAI API error")

        display_error(error)

        captured = capsys.readouterr()
        assert "ERROR" in captured.out
        assert "API error" in captured.out
        assert "OPENAI_API_KEY" in captured.out


@pytest.mark.asyncio
class TestAsyncMain:
    """Test suite for async_main function."""

    async def test_async_main_success(self, tmp_path):
        """Test async_main succeeds with valid inputs."""
        input_file = tmp_path / "test.md"
        input_file.write_text("# Test content")
        output_dir = tmp_path / "output"

        args = argparse.Namespace(
            input=str(input_file),
            output=str(output_dir),
            max_cost=0.50,
            dry_run=True,
            verbose=False
        )

        mock_summary = {
            "playlist_count": 5,
            "success_count": 5,
            "failed_count": 0,
            "total_cost": 0.25,
            "total_time": 60.0,
            "output_files": ["playlist1.json"],
            "decision_log": "log.jsonl"
        }

        with patch("src.ai_playlist.cli.run_automation", new=AsyncMock(return_value=mock_summary)):
            exit_code = await async_main(args)

        assert exit_code == 0

    async def test_async_main_no_successful_playlists(self, tmp_path):
        """Test async_main returns 1 when no playlists succeed."""
        input_file = tmp_path / "test.md"
        input_file.write_text("# Test")

        args = argparse.Namespace(
            input=str(input_file),
            output=str(tmp_path / "output"),
            max_cost=0.50,
            dry_run=True,
            verbose=False
        )

        mock_summary = {
            "playlist_count": 5,
            "success_count": 0,  # No successes
            "failed_count": 5,
            "total_cost": 0.25,
            "total_time": 60.0,
            "output_files": [],
            "decision_log": "log.jsonl"
        }

        with patch("src.ai_playlist.cli.run_automation", new=AsyncMock(return_value=mock_summary)):
            exit_code = await async_main(args)

        assert exit_code == 1

    async def test_async_main_handles_exception(self, tmp_path):
        """Test async_main returns 1 on exception."""
        input_file = tmp_path / "test.md"
        input_file.write_text("# Test")

        args = argparse.Namespace(
            input=str(input_file),
            output=str(tmp_path / "output"),
            max_cost=0.50,
            dry_run=True,
            verbose=False
        )

        with patch("src.ai_playlist.cli.run_automation", new=AsyncMock(side_effect=Exception("Test error"))):
            exit_code = await async_main(args)

        assert exit_code == 1


class TestMain:
    """Test suite for main entry point."""

    def test_main_parses_arguments(self, tmp_path):
        """Test main parses command line arguments."""
        input_file = tmp_path / "test.md"
        input_file.write_text("# Test")

        mock_summary = {
            "playlist_count": 1,
            "success_count": 1,
            "failed_count": 0,
            "total_cost": 0.10,
            "total_time": 30.0,
            "output_files": ["playlist.json"],
            "decision_log": "log.jsonl"
        }

        with patch("sys.argv", ["cli.py", "--input", str(input_file), "--output", str(tmp_path / "output")]):
            with patch("src.ai_playlist.cli.run_automation", new=AsyncMock(return_value=mock_summary)):
                exit_code = main()

        assert exit_code == 0

    def test_main_handles_keyboard_interrupt(self, tmp_path):
        """Test main handles KeyboardInterrupt gracefully."""
        input_file = tmp_path / "test.md"
        input_file.write_text("# Test")

        with patch("sys.argv", ["cli.py", "--input", str(input_file), "--output", str(tmp_path / "output")]):
            with patch("src.ai_playlist.cli.async_main", side_effect=KeyboardInterrupt()):
                with patch("asyncio.run", side_effect=KeyboardInterrupt()):
                    exit_code = main()

        assert exit_code == 1

    def test_main_sets_verbose_logging(self, tmp_path):
        """Test main sets debug logging when --verbose is used."""
        input_file = tmp_path / "test.md"
        input_file.write_text("# Test")

        mock_summary = {
            "playlist_count": 1,
            "success_count": 1,
            "failed_count": 0,
            "total_cost": 0.10,
            "total_time": 30.0,
            "output_files": ["playlist.json"],
            "decision_log": "log.jsonl"
        }

        with patch("sys.argv", ["cli.py", "--input", str(input_file), "--output", str(tmp_path / "output"), "--verbose"]):
            with patch("src.ai_playlist.cli.run_automation", new=AsyncMock(return_value=mock_summary)):
                with patch("logging.getLogger") as mock_logger:
                    exit_code = main()

        assert exit_code == 0
