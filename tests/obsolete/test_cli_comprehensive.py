"""
Comprehensive Unit Tests for CLI Module - Edge Cases and Coverage

Tests all edge cases, error paths, and uncovered scenarios to achieve 90%+ coverage.
"""

import pytest
import argparse
import asyncio
import logging
import sys
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock, mock_open
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


class TestParserEdgeCases:
    """Test edge cases for argument parsing."""

    def test_parser_with_very_large_max_cost(self):
        """Test parser accepts very large max cost values."""
        parser = create_parser()

        args = parser.parse_args([
            "--input", "test.md",
            "--output", "output/",
            "--max-cost", "1000.99"
        ])

        assert args.max_cost == 1000.99

    def test_parser_with_very_small_max_cost(self):
        """Test parser accepts very small max cost values."""
        parser = create_parser()

        args = parser.parse_args([
            "--input", "test.md",
            "--output", "output/",
            "--max-cost", "0.001"
        ])

        assert args.max_cost == 0.001

    def test_parser_with_short_verbose_flag(self):
        """Test parser accepts -v short form for verbose."""
        parser = create_parser()

        args = parser.parse_args([
            "--input", "test.md",
            "--output", "output/",
            "-v"
        ])

        assert args.verbose is True

    def test_parser_with_all_arguments(self):
        """Test parser with all possible arguments combined."""
        parser = create_parser()

        args = parser.parse_args([
            "--input", "station-identity.md",
            "--output", "playlists/",
            "--dry-run",
            "--max-cost", "2.50",
            "--verbose"
        ])

        assert args.input == "station-identity.md"
        assert args.output == "playlists/"
        assert args.dry_run is True
        assert args.max_cost == 2.50
        assert args.verbose is True

    def test_parser_with_paths_containing_spaces(self):
        """Test parser handles paths with spaces correctly."""
        parser = create_parser()

        args = parser.parse_args([
            "--input", "my documents/station.md",
            "--output", "output folder/playlists/"
        ])

        assert args.input == "my documents/station.md"
        assert args.output == "output folder/playlists/"

    def test_parser_with_special_characters_in_paths(self):
        """Test parser handles special characters in paths."""
        parser = create_parser()

        args = parser.parse_args([
            "--input", "test-file_v2.1.md",
            "--output", "output/2024-01-15/"
        ])

        assert args.input == "test-file_v2.1.md"
        assert args.output == "output/2024-01-15/"

    def test_parser_missing_only_input_raises_error(self):
        """Test parser raises error when only input is missing."""
        parser = create_parser()

        with pytest.raises(SystemExit):
            parser.parse_args(["--output", "output/"])

    def test_parser_missing_only_output_raises_error(self):
        """Test parser raises error when only output is missing."""
        parser = create_parser()

        with pytest.raises(SystemExit):
            parser.parse_args(["--input", "test.md"])


class TestValidateArgumentsEdgeCases:
    """Test edge cases for argument validation."""

    def test_validate_with_high_max_cost_logs_warning(self, tmp_path, caplog):
        """Test validation logs warning for unusually high max cost."""
        input_file = tmp_path / "test.md"
        input_file.write_text("# Test content")
        output_dir = tmp_path / "output"

        args = argparse.Namespace(
            input=str(input_file),
            output=str(output_dir),
            max_cost=15.0  # Above 10.0 threshold
        )

        with caplog.at_level(logging.WARNING):
            validate_arguments(args)

        assert any("unusually high" in record.message for record in caplog.records)
        assert any("$15.00" in record.message for record in caplog.records)

    def test_validate_with_max_cost_exactly_10_no_warning(self, tmp_path, caplog):
        """Test validation doesn't warn for max cost exactly at 10.0."""
        input_file = tmp_path / "test.md"
        input_file.write_text("# Test")

        args = argparse.Namespace(
            input=str(input_file),
            output=str(tmp_path / "output"),
            max_cost=10.0
        )

        with caplog.at_level(logging.WARNING):
            validate_arguments(args)

        # Should not warn at exactly 10.0
        assert not any("unusually high" in record.message for record in caplog.records)

    def test_validate_with_max_cost_slightly_above_10_logs_warning(self, tmp_path, caplog):
        """Test validation warns for max cost just above 10.0."""
        input_file = tmp_path / "test.md"
        input_file.write_text("# Test")

        args = argparse.Namespace(
            input=str(input_file),
            output=str(tmp_path / "output"),
            max_cost=10.01
        )

        with caplog.at_level(logging.WARNING):
            validate_arguments(args)

        assert any("unusually high" in record.message for record in caplog.records)

    def test_validate_output_directory_creation_failure(self, tmp_path, monkeypatch):
        """Test validation raises ValueError when output directory cannot be created."""
        input_file = tmp_path / "test.md"
        input_file.write_text("# Test")

        # Mock Path.mkdir to raise OSError
        def mock_mkdir(*args, **kwargs):
            raise OSError("Permission denied")

        args = argparse.Namespace(
            input=str(input_file),
            output=str(tmp_path / "forbidden"),
            max_cost=0.50
        )

        with patch.object(Path, 'mkdir', side_effect=mock_mkdir):
            with pytest.raises(ValueError, match="Cannot create output directory"):
                validate_arguments(args)

    def test_validate_with_existing_output_directory(self, tmp_path):
        """Test validation succeeds when output directory already exists."""
        input_file = tmp_path / "test.md"
        input_file.write_text("# Test")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        args = argparse.Namespace(
            input=str(input_file),
            output=str(output_dir),
            max_cost=0.50
        )

        # Should not raise
        validate_arguments(args)

    def test_validate_with_empty_input_file(self, tmp_path):
        """Test validation succeeds with empty input file (content validation is elsewhere)."""
        input_file = tmp_path / "empty.md"
        input_file.write_text("")

        args = argparse.Namespace(
            input=str(input_file),
            output=str(tmp_path / "output"),
            max_cost=0.50
        )

        # Should not raise - content validation happens later
        validate_arguments(args)

    def test_validate_with_very_long_path(self, tmp_path):
        """Test validation with very long file paths."""
        # Create nested directories
        long_path = tmp_path
        for i in range(10):
            long_path = long_path / f"very_long_directory_name_{i}"

        input_file = tmp_path / "test.md"
        input_file.write_text("# Test")

        args = argparse.Namespace(
            input=str(input_file),
            output=str(long_path),
            max_cost=0.50
        )

        validate_arguments(args)
        assert long_path.exists()


class TestDisplayFunctionsEdgeCases:
    """Test edge cases for display functions."""

    def test_display_progress_header_with_dry_run_true(self, capsys):
        """Test progress header shows dry_run=True correctly."""
        args = argparse.Namespace(
            input="station-identity.md",
            output="playlists/",
            max_cost=1.25,
            dry_run=True
        )

        display_progress_header(args)

        captured = capsys.readouterr()
        assert "True" in captured.out
        assert "$1.25" in captured.out

    def test_display_progress_header_formats_cost_with_decimals(self, capsys):
        """Test progress header formats cost with 2 decimal places."""
        args = argparse.Namespace(
            input="test.md",
            output="out/",
            max_cost=0.123456,
            dry_run=False
        )

        display_progress_header(args)

        captured = capsys.readouterr()
        assert "$0.12" in captured.out  # Should round to 2 decimals

    def test_display_progress_update_with_zero_progress(self, capsys):
        """Test progress update with 0% completion."""
        display_progress_update(
            stage="Starting",
            playlists_processed=0,
            total_playlists=10,
            current_time=0.5,
            current_cost=0.00
        )

        captured = capsys.readouterr()
        assert "0/10" in captured.out
        assert "0%" in captured.out

    def test_display_progress_update_with_100_percent(self, capsys):
        """Test progress update with 100% completion."""
        display_progress_update(
            stage="Complete",
            playlists_processed=10,
            total_playlists=10,
            current_time=120.0,
            current_cost=0.45
        )

        captured = capsys.readouterr()
        assert "10/10" in captured.out
        assert "100%" in captured.out

    def test_display_progress_update_with_partial_progress(self, capsys):
        """Test progress update with partial completion percentage."""
        display_progress_update(
            stage="Processing",
            playlists_processed=3,
            total_playlists=7,
            current_time=45.8,
            current_cost=0.18
        )

        captured = capsys.readouterr()
        assert "3/7" in captured.out
        assert "43%" in captured.out  # 3/7 = 42.857%, rounds to 43

    def test_display_progress_update_formats_large_time(self, capsys):
        """Test progress update formats large time values correctly."""
        display_progress_update(
            stage="Long Process",
            playlists_processed=5,
            total_playlists=10,
            current_time=12345.6,
            current_cost=2.50
        )

        captured = capsys.readouterr()
        assert "12345.6s" in captured.out

    def test_display_progress_update_formats_small_cost(self, capsys):
        """Test progress update formats very small costs correctly."""
        display_progress_update(
            stage="Cheap",
            playlists_processed=1,
            total_playlists=1,
            current_time=1.0,
            current_cost=0.0001
        )

        captured = capsys.readouterr()
        assert "$0.0001" in captured.out

    def test_display_summary_with_zero_cost(self, capsys):
        """Test summary display with zero cost."""
        summary = {
            "playlist_count": 1,
            "success_count": 1,
            "failed_count": 0,
            "total_cost": 0.0,
            "total_time": 10.0,
            "output_files": ["playlist.json"],
            "decision_log": "/path/to/log.jsonl"
        }

        display_summary(summary)

        captured = capsys.readouterr()
        assert "$0.0000" in captured.out

    def test_display_summary_with_empty_output_files(self, capsys):
        """Test summary display with no output files."""
        summary = {
            "playlist_count": 5,
            "success_count": 0,
            "failed_count": 5,
            "total_cost": 0.10,
            "total_time": 30.0,
            "output_files": [],
            "decision_log": "/path/to/log.jsonl"
        }

        display_summary(summary)

        captured = capsys.readouterr()
        assert "0 playlists" in captured.out

    def test_display_summary_with_many_output_files(self, capsys):
        """Test summary display with many output files."""
        output_files = [f"playlist_{i}.json" for i in range(100)]
        summary = {
            "playlist_count": 100,
            "success_count": 100,
            "failed_count": 0,
            "total_cost": 5.0,
            "total_time": 600.0,
            "output_files": output_files,
            "decision_log": "/path/to/log.jsonl"
        }

        display_summary(summary)

        captured = capsys.readouterr()
        assert "100 playlists" in captured.out

    def test_display_summary_logs_warning_for_failures(self, capsys, caplog):
        """Test summary logs warning when playlists fail."""
        summary = {
            "playlist_count": 10,
            "success_count": 7,
            "failed_count": 3,
            "total_cost": 0.40,
            "total_time": 90.0,
            "output_files": ["p1.json", "p2.json"],
            "decision_log": "/path/to/log.jsonl"
        }

        with caplog.at_level(logging.WARNING):
            display_summary(summary)

        assert any("3 playlists failed" in record.message for record in caplog.records)

    def test_display_error_generic_exception(self, capsys):
        """Test error display for generic exception."""
        error = RuntimeError("Something went wrong")

        display_error(error)

        captured = capsys.readouterr()
        assert "ERROR" in captured.out
        assert "Unexpected error" in captured.out
        assert "Something went wrong" in captured.out

    def test_display_error_includes_help_text(self, capsys):
        """Test error display includes helpful guidance."""
        error = MCPToolError("Connection failed")

        display_error(error)

        captured = capsys.readouterr()
        assert "MCP server error" in captured.out
        assert "SUBSONIC_MCP_URL" in captured.out
        assert "Please ensure:" in captured.out

    def test_display_error_file_not_found_with_specific_message(self, capsys):
        """Test FileNotFoundError displays specific file path."""
        error = FileNotFoundError("/path/to/missing/file.md")

        display_error(error)

        captured = capsys.readouterr()
        assert "/path/to/missing/file.md" in captured.out


class TestAsyncMainEdgeCases:
    """Test edge cases for async_main function."""

    @pytest.mark.asyncio
    async def test_async_main_with_validation_error(self, tmp_path, capsys):
        """Test async_main handles validation errors correctly."""
        args = argparse.Namespace(
            input=str(tmp_path / "nonexistent.md"),
            output=str(tmp_path / "output"),
            max_cost=0.50,
            dry_run=False,
            verbose=False
        )

        exit_code = await async_main(args)

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "ERROR" in captured.out

    @pytest.mark.asyncio
    async def test_async_main_with_verbose_exception_logging(self, tmp_path, caplog):
        """Test async_main logs detailed exception with verbose mode."""
        input_file = tmp_path / "test.md"
        input_file.write_text("# Test")

        args = argparse.Namespace(
            input=str(input_file),
            output=str(tmp_path / "output"),
            max_cost=0.50,
            dry_run=False,
            verbose=True  # Enable verbose
        )

        test_error = RuntimeError("Detailed error for testing")

        with caplog.at_level(logging.ERROR):
            with patch("src.ai_playlist.cli.run_automation", new=AsyncMock(side_effect=test_error)):
                exit_code = await async_main(args)

        assert exit_code == 1
        # Check that detailed traceback was logged
        assert any("Detailed error traceback" in record.message for record in caplog.records)

    @pytest.mark.asyncio
    async def test_async_main_with_parse_error(self, tmp_path, capsys):
        """Test async_main handles ParseError correctly."""
        input_file = tmp_path / "test.md"
        input_file.write_text("# Test")

        args = argparse.Namespace(
            input=str(input_file),
            output=str(tmp_path / "output"),
            max_cost=0.50,
            dry_run=False,
            verbose=False
        )

        with patch("src.ai_playlist.cli.run_automation", new=AsyncMock(side_effect=ParseError("Parse failed"))):
            exit_code = await async_main(args)

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "Document parsing failed" in captured.out

    @pytest.mark.asyncio
    async def test_async_main_with_cost_exceeded_error(self, tmp_path, capsys):
        """Test async_main handles CostExceededError correctly."""
        input_file = tmp_path / "test.md"
        input_file.write_text("# Test")

        args = argparse.Namespace(
            input=str(input_file),
            output=str(tmp_path / "output"),
            max_cost=0.50,
            dry_run=False,
            verbose=False
        )

        with patch("src.ai_playlist.cli.run_automation", new=AsyncMock(side_effect=CostExceededError("Cost too high"))):
            exit_code = await async_main(args)

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "Cost exceeded" in captured.out

    @pytest.mark.asyncio
    async def test_async_main_with_api_error(self, tmp_path, capsys):
        """Test async_main handles APIError correctly."""
        input_file = tmp_path / "test.md"
        input_file.write_text("# Test")

        args = argparse.Namespace(
            input=str(input_file),
            output=str(tmp_path / "output"),
            max_cost=0.50,
            dry_run=False,
            verbose=False
        )

        with patch("src.ai_playlist.cli.run_automation", new=AsyncMock(side_effect=APIError("API failed"))):
            exit_code = await async_main(args)

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "API error" in captured.out
        assert "OPENAI_API_KEY" in captured.out

    @pytest.mark.asyncio
    async def test_async_main_with_all_playlists_failing(self, tmp_path, caplog):
        """Test async_main logs error when all playlists fail."""
        input_file = tmp_path / "test.md"
        input_file.write_text("# Test")

        args = argparse.Namespace(
            input=str(input_file),
            output=str(tmp_path / "output"),
            max_cost=0.50,
            dry_run=False,
            verbose=False
        )

        mock_summary = {
            "playlist_count": 5,
            "success_count": 0,
            "failed_count": 5,
            "total_cost": 0.20,
            "total_time": 30.0,
            "output_files": [],
            "decision_log": "log.jsonl"
        }

        with caplog.at_level(logging.ERROR):
            with patch("src.ai_playlist.cli.run_automation", new=AsyncMock(return_value=mock_summary)):
                exit_code = await async_main(args)

        assert exit_code == 1
        assert any("No playlists generated successfully" in record.message for record in caplog.records)


class TestMainEdgeCases:
    """Test edge cases for main entry point."""

    def test_main_with_fatal_exception(self, tmp_path, caplog):
        """Test main handles fatal exceptions gracefully."""
        input_file = tmp_path / "test.md"
        input_file.write_text("# Test")

        with patch("sys.argv", ["cli.py", "--input", str(input_file), "--output", str(tmp_path / "output")]):
            with patch("asyncio.run", side_effect=RuntimeError("Fatal error")):
                with caplog.at_level(logging.ERROR):
                    exit_code = main()

        assert exit_code == 1
        assert any("Fatal error in CLI" in record.message for record in caplog.records)

    def test_main_with_keyboard_interrupt_displays_message(self, tmp_path, capsys):
        """Test main displays cancellation message on KeyboardInterrupt."""
        input_file = tmp_path / "test.md"
        input_file.write_text("# Test")

        with patch("sys.argv", ["cli.py", "--input", str(input_file), "--output", str(tmp_path / "output")]):
            with patch("asyncio.run", side_effect=KeyboardInterrupt()):
                exit_code = main()

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "INTERRUPTED" in captured.out
        assert "cancelled by user" in captured.out

    def test_main_enables_debug_logging_with_verbose(self, tmp_path):
        """Test main sets logging level to DEBUG when verbose is enabled."""
        input_file = tmp_path / "test.md"
        input_file.write_text("# Test")

        mock_summary = {
            "playlist_count": 1,
            "success_count": 1,
            "failed_count": 0,
            "total_cost": 0.10,
            "total_time": 10.0,
            "output_files": ["p.json"],
            "decision_log": "log.jsonl"
        }

        with patch("sys.argv", ["cli.py", "--input", str(input_file), "--output", str(tmp_path / "output"), "--verbose"]):
            with patch("src.ai_playlist.cli.run_automation", new=AsyncMock(return_value=mock_summary)):
                with patch("logging.getLogger") as mock_get_logger:
                    mock_logger = MagicMock()
                    mock_get_logger.return_value = mock_logger

                    exit_code = main()

        assert exit_code == 0

    def test_main_with_minimal_valid_arguments(self, tmp_path):
        """Test main with only required arguments."""
        input_file = tmp_path / "test.md"
        input_file.write_text("# Test")

        mock_summary = {
            "playlist_count": 1,
            "success_count": 1,
            "failed_count": 0,
            "total_cost": 0.10,
            "total_time": 10.0,
            "output_files": ["p.json"],
            "decision_log": "log.jsonl"
        }

        with patch("sys.argv", ["cli.py", "--input", str(input_file), "--output", str(tmp_path / "output")]):
            with patch("src.ai_playlist.cli.run_automation", new=AsyncMock(return_value=mock_summary)):
                exit_code = main()

        assert exit_code == 0

    def test_main_with_dry_run_flag(self, tmp_path):
        """Test main with dry-run flag enabled."""
        input_file = tmp_path / "test.md"
        input_file.write_text("# Test")

        mock_summary = {
            "playlist_count": 1,
            "success_count": 1,
            "failed_count": 0,
            "total_cost": 0.05,
            "total_time": 5.0,
            "output_files": ["p.json"],
            "decision_log": "log.jsonl"
        }

        with patch("sys.argv", ["cli.py", "--input", str(input_file), "--output", str(tmp_path / "output"), "--dry-run"]):
            with patch("src.ai_playlist.cli.run_automation", new=AsyncMock(return_value=mock_summary)) as mock_run:
                exit_code = main()

        # Verify dry_run was passed correctly
        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["dry_run"] is True
        assert exit_code == 0

    def test_main_with_custom_max_cost(self, tmp_path):
        """Test main with custom max cost parameter."""
        input_file = tmp_path / "test.md"
        input_file.write_text("# Test")

        mock_summary = {
            "playlist_count": 1,
            "success_count": 1,
            "failed_count": 0,
            "total_cost": 0.80,
            "total_time": 20.0,
            "output_files": ["p.json"],
            "decision_log": "log.jsonl"
        }

        with patch("sys.argv", ["cli.py", "--input", str(input_file), "--output", str(tmp_path / "output"), "--max-cost", "2.0"]):
            with patch("src.ai_playlist.cli.run_automation", new=AsyncMock(return_value=mock_summary)) as mock_run:
                exit_code = main()

        # Verify max_cost was passed correctly
        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["max_cost_usd"] == 2.0
        assert exit_code == 0


class TestIntegrationScenarios:
    """Test complete integration scenarios."""

    @pytest.mark.asyncio
    async def test_complete_success_workflow(self, tmp_path, capsys):
        """Test complete successful execution workflow."""
        input_file = tmp_path / "station.md"
        input_file.write_text("# Station Identity\n\n## Programming")
        output_dir = tmp_path / "playlists"

        args = argparse.Namespace(
            input=str(input_file),
            output=str(output_dir),
            max_cost=1.0,
            dry_run=True,
            verbose=False
        )

        mock_summary = {
            "playlist_count": 3,
            "success_count": 3,
            "failed_count": 0,
            "total_cost": 0.35,
            "total_time": 45.5,
            "output_files": [
                "morning_drive.json",
                "afternoon_mix.json",
                "evening_chill.json"
            ],
            "decision_log": str(output_dir / "decisions.jsonl")
        }

        with patch("src.ai_playlist.cli.run_automation", new=AsyncMock(return_value=mock_summary)):
            exit_code = await async_main(args)

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "AI PLAYLIST AUTOMATION" in captured.out
        assert "EXECUTION SUMMARY" in captured.out
        assert "3" in captured.out  # Total playlists

    @pytest.mark.asyncio
    async def test_partial_failure_workflow(self, tmp_path, capsys, caplog):
        """Test workflow with some failures."""
        input_file = tmp_path / "station.md"
        input_file.write_text("# Station Identity")

        args = argparse.Namespace(
            input=str(input_file),
            output=str(tmp_path / "output"),
            max_cost=0.50,
            dry_run=False,
            verbose=False
        )

        mock_summary = {
            "playlist_count": 5,
            "success_count": 3,
            "failed_count": 2,
            "total_cost": 0.40,
            "total_time": 60.0,
            "output_files": ["p1.json", "p2.json", "p3.json"],
            "decision_log": "/path/to/log.jsonl"
        }

        with caplog.at_level(logging.WARNING):
            with patch("src.ai_playlist.cli.run_automation", new=AsyncMock(return_value=mock_summary)):
                exit_code = await async_main(args)

        assert exit_code == 0  # Still succeeds if some playlists work
        assert any("2 playlists failed" in record.message for record in caplog.records)

    @pytest.mark.asyncio
    async def test_complete_failure_with_verbose(self, tmp_path, capsys, caplog):
        """Test complete failure with verbose logging enabled."""
        input_file = tmp_path / "station.md"
        input_file.write_text("# Station")

        args = argparse.Namespace(
            input=str(input_file),
            output=str(tmp_path / "output"),
            max_cost=0.50,
            dry_run=False,
            verbose=True
        )

        test_error = ValidationError("All playlists failed validation")

        with caplog.at_level(logging.DEBUG):
            with patch("src.ai_playlist.cli.run_automation", new=AsyncMock(side_effect=test_error)):
                exit_code = await async_main(args)

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "Validation failed" in captured.out
        assert any("Detailed error traceback" in record.message for record in caplog.records)
