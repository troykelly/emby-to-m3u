"""
Unit Tests for DecisionLogger - Indefinite Audit Trail

Tests JSONL format correctness, file creation, append-only behavior,
required fields validation, and indefinite retention guarantees.
"""

import json
import pytest
from pathlib import Path
from datetime import datetime
from src.ai_playlist.decision_logger import DecisionLogger
from src.ai_playlist.models import DecisionLog


class TestDecisionLogger:
    """Test suite for DecisionLogger class."""

    @pytest.fixture
    def temp_log_dir(self, tmp_path):
        """Create temporary log directory for testing."""
        log_dir = tmp_path / "test_logs"
        return log_dir

    @pytest.fixture
    def logger(self, temp_log_dir):
        """Create DecisionLogger instance with temporary directory."""
        return DecisionLogger(log_dir=temp_log_dir)

    @pytest.fixture
    def sample_decision_data(self):
        """Sample decision log data for testing."""
        return {
            "decision_type": "track_selection",
            "playlist_name": "Monday_ProductionCall_0600_1000",
            "criteria": {
                "bpm_range": [90, 115],
                "genre_mix": {"Alternative": [0.20, 0.30], "Electronic": [0.15, 0.25]},
                "era_distribution": {"Current": [0.35, 0.45], "Recent": [0.30, 0.40]},
                "australian_min": 0.30,
                "energy_flow": "Start moderate, build to peak",
            },
            "selected_tracks": [
                {
                    "track_id": "123",
                    "title": "Example Track",
                    "artist": "Example Artist",
                    "bpm": 105,
                    "genre": "Alternative",
                    "position": 1,
                },
                {
                    "track_id": "456",
                    "title": "Another Track",
                    "artist": "Another Artist",
                    "bpm": 110,
                    "genre": "Electronic",
                    "position": 2,
                },
            ],
            "validation_result": {
                "constraint_satisfaction": 0.85,
                "flow_quality_score": 0.78,
                "bpm_satisfaction": 0.90,
                "genre_satisfaction": 0.82,
                "era_satisfaction": 0.88,
                "australian_content": 0.32,
                "passes_validation": True,
            },
            "metadata": {
                "playlist_id": "550e8400-e29b-41d4-a716-446655440000",
                "llm_cost": 0.002,
                "execution_time": 3.5,
                "relaxation_steps": 0,
            },
        }

    def test_init_creates_log_directory(self, temp_log_dir):
        """Test that logger initialization creates log directory."""
        assert not temp_log_dir.exists()

        logger = DecisionLogger(log_dir=temp_log_dir)

        assert temp_log_dir.exists()
        assert temp_log_dir.is_dir()

    def test_init_creates_log_file(self, logger):
        """Test that logger initialization creates JSONL log file."""
        log_file = logger.get_log_file()

        assert log_file.exists()
        assert log_file.suffix == ".jsonl"
        assert log_file.name.startswith("decisions_")

    def test_log_file_naming_convention(self, logger):
        """Test that log file follows naming convention: decisions_{timestamp}.jsonl"""
        log_file = logger.get_log_file()

        # Pattern: decisions_YYYYMMDDTHHMMSS{microseconds}.jsonl
        assert log_file.name.startswith("decisions_")
        assert log_file.suffix == ".jsonl"

        # Extract timestamp portion
        timestamp_str = log_file.stem.replace("decisions_", "")
        # Format: YYYYMMDDTHHMMSS{microseconds} - contains 'T' separator
        assert len(timestamp_str) == 21  # YYYYMMDDTHHMMSS (15) + T (1) + microseconds (6) = 21
        assert "T" in timestamp_str

        # Verify date and time parts are numeric
        date_part, time_part = timestamp_str.split("T")
        assert date_part.isdigit()
        assert time_part.isdigit()

    def test_log_decision_creates_valid_jsonl_entry(self, logger, sample_decision_data):
        """Test that log_decision writes valid JSONL format."""
        logger.log_decision(**sample_decision_data)

        # Read raw file content
        with open(logger.get_log_file(), "r") as f:
            lines = f.readlines()

        assert len(lines) == 1

        # Validate JSON format
        entry = json.loads(lines[0])
        assert "id" in entry
        assert "timestamp" in entry
        assert entry["decision_type"] == "track_selection"
        assert entry["playlist_name"] == "Monday_ProductionCall_0600_1000"

    def test_log_decision_all_required_fields_present(self, logger, sample_decision_data):
        """Test that logged decision contains all required fields."""
        logger.log_decision(**sample_decision_data)

        decisions = logger.read_decisions()
        assert len(decisions) == 1

        decision = decisions[0]

        # Required fields from DecisionLog dataclass
        assert decision.id is not None
        assert decision.timestamp is not None
        assert decision.decision_type == "track_selection"
        assert decision.playlist_id is not None
        assert decision.playlist_name == "Monday_ProductionCall_0600_1000"
        assert decision.criteria == sample_decision_data["criteria"]
        assert decision.selected_tracks == sample_decision_data["selected_tracks"]
        assert decision.validation_result == sample_decision_data["validation_result"]
        assert decision.metadata == sample_decision_data["metadata"]

    def test_log_decision_append_only_behavior(self, logger, sample_decision_data):
        """Test that multiple log_decision calls append to same file."""
        # Log three decisions
        logger.log_decision(**sample_decision_data)

        sample_decision_data["decision_type"] = "constraint_relaxation"
        logger.log_decision(**sample_decision_data)

        sample_decision_data["decision_type"] = "validation"
        logger.log_decision(**sample_decision_data)

        # Verify all entries are in same file
        decisions = logger.read_decisions()
        assert len(decisions) == 3

        # Verify decision types
        assert decisions[0].decision_type == "track_selection"
        assert decisions[1].decision_type == "constraint_relaxation"
        assert decisions[2].decision_type == "validation"

    def test_log_decision_preserves_order(self, logger, sample_decision_data):
        """Test that decisions are logged in chronological order."""
        timestamps = []

        for i in range(5):
            sample_decision_data["playlist_name"] = f"Playlist_{i}"
            logger.log_decision(**sample_decision_data)
            timestamps.append(datetime.now())

        decisions = logger.read_decisions()

        # Verify chronological order
        for i in range(len(decisions) - 1):
            assert decisions[i].timestamp <= decisions[i + 1].timestamp

    def test_log_decision_invalid_decision_type_raises_error(self, logger, sample_decision_data):
        """Test that invalid decision_type raises ValueError."""
        sample_decision_data["decision_type"] = "invalid_type"

        with pytest.raises(ValueError, match="Decision type must be one of"):
            logger.log_decision(**sample_decision_data)

    def test_log_decision_non_serializable_data_raises_error(self, logger, sample_decision_data):
        """Test that non-JSON-serializable data raises ValueError."""
        # Add non-serializable object
        sample_decision_data["metadata"]["invalid"] = lambda x: x

        with pytest.raises(ValueError, match="must be JSON-serializable"):
            logger.log_decision(**sample_decision_data)

    def test_read_decisions_empty_file(self, logger):
        """Test that read_decisions returns empty list for new log file."""
        decisions = logger.read_decisions()
        assert decisions == []

    def test_read_decisions_parses_all_entries(self, logger, sample_decision_data):
        """Test that read_decisions parses all JSONL entries."""
        # Log multiple decisions
        for i in range(10):
            sample_decision_data["playlist_name"] = f"Playlist_{i}"
            logger.log_decision(**sample_decision_data)

        decisions = logger.read_decisions()
        assert len(decisions) == 10

        # Verify all are DecisionLog instances
        for decision in decisions:
            assert isinstance(decision, DecisionLog)

    def test_read_decisions_from_specific_file(self, temp_log_dir, sample_decision_data):
        """Test that read_decisions can read from specific log file."""
        import time

        # Create two separate loggers (different log files)
        logger1 = DecisionLogger(log_dir=temp_log_dir)
        logger1.log_decision(**sample_decision_data)

        # Small delay to ensure different timestamps
        time.sleep(0.01)

        logger2 = DecisionLogger(log_dir=temp_log_dir)
        sample_decision_data["decision_type"] = "validation"
        logger2.log_decision(**sample_decision_data)

        # Verify different log files
        assert logger1.get_log_file() != logger2.get_log_file()

        # Read from logger1's file
        decisions1 = logger2.read_decisions(log_file=logger1.get_log_file())
        assert len(decisions1) == 1
        assert decisions1[0].decision_type == "track_selection"

        # Read from logger2's file
        decisions2 = logger2.read_decisions()
        assert len(decisions2) == 1
        assert decisions2[0].decision_type == "validation"

    def test_read_decisions_handles_empty_lines(self, logger, sample_decision_data):
        """Test that read_decisions skips empty lines in JSONL file."""
        logger.log_decision(**sample_decision_data)

        # Manually add empty lines
        with open(logger.get_log_file(), "a") as f:
            f.write("\n")
            f.write("   \n")

        logger.log_decision(**sample_decision_data)

        decisions = logger.read_decisions()
        assert len(decisions) == 2  # Should skip empty lines

    def test_read_decisions_invalid_json_raises_error(self, logger):
        """Test that invalid JSON in log file raises ValueError."""
        # Write invalid JSON
        with open(logger.get_log_file(), "w") as f:
            f.write("invalid json line\n")

        with pytest.raises(ValueError, match="Invalid decision log entry"):
            logger.read_decisions()

    def test_read_decisions_nonexistent_file_raises_error(self, logger):
        """Test that reading nonexistent log file raises FileNotFoundError."""
        nonexistent_file = logger.log_dir / "nonexistent.jsonl"

        with pytest.raises(FileNotFoundError, match="Log file not found"):
            logger.read_decisions(log_file=nonexistent_file)

    def test_indefinite_retention_no_rotation(self, logger, sample_decision_data):
        """Test that log files are never rotated (indefinite retention)."""
        initial_log_file = logger.get_log_file()

        # Log many decisions
        for i in range(100):
            logger.log_decision(**sample_decision_data)

        # Verify same log file is used
        assert logger.get_log_file() == initial_log_file

        # Verify all entries preserved
        decisions = logger.read_decisions()
        assert len(decisions) == 100

    def test_indefinite_retention_no_deletion(self, temp_log_dir, sample_decision_data):
        """Test that old log files are never deleted."""
        import time

        # Create multiple log files over time
        log_files = []

        for i in range(5):
            logger = DecisionLogger(log_dir=temp_log_dir)
            logger.log_decision(**sample_decision_data)
            log_files.append(logger.get_log_file())
            # Small delay to ensure different microsecond timestamps
            time.sleep(0.01)

        # Verify all log files still exist
        for log_file in log_files:
            assert log_file.exists()

        # Verify all log files are different
        assert len(set(log_files)) == 5

    def test_list_log_files(self, temp_log_dir, sample_decision_data):
        """Test that list_log_files returns all decision log files."""
        import time

        # Create multiple log files
        for i in range(3):
            logger = DecisionLogger(log_dir=temp_log_dir)
            logger.log_decision(**sample_decision_data)
            time.sleep(0.01)

        logger = DecisionLogger(log_dir=temp_log_dir)
        log_files = logger.list_log_files()

        assert len(log_files) == 4  # 3 + current

        # Verify sorted order (oldest first)
        for i in range(len(log_files) - 1):
            assert log_files[i].name <= log_files[i + 1].name

    def test_count_decisions(self, logger, sample_decision_data):
        """Test that count_decisions returns correct count."""
        assert logger.count_decisions() == 0

        # Log decisions
        for i in range(7):
            logger.log_decision(**sample_decision_data)

        assert logger.count_decisions() == 7

    def test_count_decisions_specific_file(self, temp_log_dir, sample_decision_data):
        """Test that count_decisions can count specific log file."""
        import time

        logger1 = DecisionLogger(log_dir=temp_log_dir)
        logger1.log_decision(**sample_decision_data)
        logger1.log_decision(**sample_decision_data)

        time.sleep(0.01)

        logger2 = DecisionLogger(log_dir=temp_log_dir)
        logger2.log_decision(**sample_decision_data)

        # Verify different log files
        assert logger1.get_log_file() != logger2.get_log_file()

        assert logger2.count_decisions(log_file=logger1.get_log_file()) == 2
        assert logger2.count_decisions() == 1

    def test_count_decisions_nonexistent_file(self, logger):
        """Test that count_decisions returns 0 for nonexistent file."""
        nonexistent_file = logger.log_dir / "nonexistent.jsonl"
        assert logger.count_decisions(log_file=nonexistent_file) == 0

    def test_decision_type_validation(self, logger, sample_decision_data):
        """Test that all valid decision types are accepted."""
        valid_types = ["track_selection", "constraint_relaxation", "validation", "sync"]

        for decision_type in valid_types:
            sample_decision_data["decision_type"] = decision_type
            logger.log_decision(**sample_decision_data)

        decisions = logger.read_decisions()
        assert len(decisions) == 4

        logged_types = [d.decision_type for d in decisions]
        assert set(logged_types) == set(valid_types)

    def test_metadata_optional(self, logger, sample_decision_data):
        """Test that metadata parameter is optional."""
        sample_decision_data.pop("metadata")
        # Add playlist_id to criteria so it can be extracted
        sample_decision_data["criteria"]["playlist_id"] = "550e8400-e29b-41d4-a716-446655440000"

        logger.log_decision(**sample_decision_data)

        decisions = logger.read_decisions()
        assert len(decisions) == 1
        assert decisions[0].metadata == {}

    def test_jsonl_format_one_entry_per_line(self, logger, sample_decision_data):
        """Test that JSONL format has exactly one JSON object per line."""
        # Log multiple decisions
        for i in range(5):
            logger.log_decision(**sample_decision_data)

        # Read raw file
        with open(logger.get_log_file(), "r") as f:
            lines = f.readlines()

        # Verify line count
        assert len(lines) == 5

        # Verify each line is valid JSON
        for line in lines:
            entry = json.loads(line)
            assert isinstance(entry, dict)
            assert "id" in entry
            assert "timestamp" in entry

    def test_concurrent_logging_safety(self, logger, sample_decision_data):
        """Test that concurrent log_decision calls don't corrupt file."""
        # Simulate rapid logging (testing file append safety)
        for i in range(50):
            logger.log_decision(**sample_decision_data)

        # Verify all entries are valid
        decisions = logger.read_decisions()
        assert len(decisions) == 50

        # Verify no corruption
        for decision in decisions:
            assert isinstance(decision, DecisionLog)
            assert decision.decision_type == "track_selection"

    def test_unicode_handling(self, logger, sample_decision_data):
        """Test that logger handles Unicode characters correctly."""
        sample_decision_data["playlist_name"] = "Monday_Café_0600_1000 🎵"
        sample_decision_data["selected_tracks"][0]["title"] = "Track with émojis 🎶"

        logger.log_decision(**sample_decision_data)

        decisions = logger.read_decisions()
        assert len(decisions) == 1
        assert decisions[0].playlist_name == "Monday_Café_0600_1000 🎵"
        assert "émojis" in decisions[0].selected_tracks[0]["title"]

    def test_large_decision_log(self, logger, sample_decision_data):
        """Test that logger handles large decision entries."""
        # Create large selected_tracks list
        large_tracks = []
        for i in range(100):
            large_tracks.append({
                "track_id": f"track_{i}",
                "title": f"Track {i}",
                "artist": f"Artist {i}",
                "bpm": 100 + i,
                "genre": "Alternative",
                "position": i + 1,
            })

        sample_decision_data["selected_tracks"] = large_tracks

        logger.log_decision(**sample_decision_data)

        decisions = logger.read_decisions()
        assert len(decisions) == 1
        assert len(decisions[0].selected_tracks) == 100
