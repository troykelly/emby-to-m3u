"""Coverage tests for decision_logger.py missing lines.

Targets lines 184 and 228: edge cases in from_json and count_logs.
"""
import pytest
from pathlib import Path
from datetime import datetime

from src.ai_playlist.decision_logger import DecisionLogger, DecisionLog, DecisionType


class TestDecisionLoggerEdgeCases:
    """Test edge cases to complete coverage."""

    def test_from_json_invalid_decision_type(self, tmp_path):
        """Test from_json raises ValueError for invalid decision_type (line 184)."""
        # Arrange
        logger = DecisionLogger(log_dir=tmp_path)
        log_file = tmp_path / "decisions_test.jsonl"

        # Write log with invalid decision_type directly to JSONL file
        invalid_json = '{"id": "test-id", "playlist_id": "test-playlist", "decision_type": "INVALID_TYPE", "timestamp": "2025-10-17T10:00:00", "decision_data": {}, "cost_incurred": "0.00", "execution_time_ms": 0}'
        log_file.write_text(invalid_json + "\n")

        # Act & Assert - Should raise ValueError when reading (line 184 is hit inside the wrapper)
        with pytest.raises(ValueError, match="Invalid decision log entry at line 1.*Invalid decision_type in log: INVALID_TYPE"):
            logger.read_decisions(log_file=log_file)

    def test_count_decisions_nonexistent_file(self, tmp_path):
        """Test count_decisions returns 0 for nonexistent file (line 228)."""
        # Arrange
        logger = DecisionLogger(log_dir=tmp_path)
        nonexistent_file = tmp_path / "does_not_exist.jsonl"

        # Act
        count = logger.count_decisions(log_file=nonexistent_file)

        # Assert
        assert count == 0

    def test_count_decisions_with_existing_file(self, tmp_path):
        """Test count_decisions counts lines in existing file."""
        # Arrange
        logger = DecisionLogger(log_dir=tmp_path)

        # Write 3 log entries using log_decision
        decision_data = {
            "decision_type": "track_selection",
            "playlist_name": "Test Playlist",
            "criteria": {},
            "selected_tracks": [],
            "validation_result": None,
            "metadata": {"llm_cost": "0.01", "execution_time_ms": 100}
        }

        logger.log_decision(**decision_data)
        logger.log_decision(**decision_data)
        logger.log_decision(**decision_data)

        # Act
        count = logger.count_decisions()

        # Assert
        assert count == 3
