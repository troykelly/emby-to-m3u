"""
Unit Tests for DecisionLogger - Indefinite Audit Trail

Tests JSONL format correctness, file creation, append-only behavior,
cost/timing tracking, and log retrieval with filtering.

Coverage: 10 comprehensive tests for decision_logger.py (T060)
Target: 90% code coverage
"""

import json
from decimal import Decimal

import pytest

from src.ai_playlist.decision_logger import DecisionLogger
from src.ai_playlist.models.core import DecisionLog, DecisionType


# pylint: disable=too-many-public-methods
class TestDecisionLogger:
    """Test suite for DecisionLogger class - 10 comprehensive tests."""

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
    def sample_track_selection_data(self):
        """Sample track selection decision log data."""
        return {
            "decision_type": "track_selection",
            "playlist_name": "Monday_ProductionCall_0600_1000",
            "criteria": {
                "playlist_id": "550e8400-e29b-41d4-a716-446655440000",
                "bpm_range": [90, 115],
                "genre_mix": {"Alternative": 0.25, "Electronic": 0.20},
                "era_distribution": {"Current": 0.40, "Recent": 0.35},
                "australian_min": 0.30,
            },
            "selected_tracks": [
                {
                    "track_id": "track_123",
                    "title": "Example Track",
                    "artist": "Example Artist",
                    "bpm": 105,
                    "genre": "Alternative",
                },
                {
                    "track_id": "track_456",
                    "title": "Another Track",
                    "artist": "Another Artist",
                    "bpm": 110,
                    "genre": "Electronic",
                },
            ],
            "validation_result": {
                "constraint_satisfaction": 0.85,
                "flow_quality_score": 0.78,
                "passes_validation": True,
            },
            "metadata": {
                "playlist_id": "550e8400-e29b-41d4-a716-446655440000",
                "llm_cost": "0.0025",
                "execution_time_ms": 3500,
                "relaxation_steps": 0,
            },
        }

    @pytest.fixture
    def sample_relaxation_data(self):
        """Sample constraint relaxation decision log data."""
        return {
            "decision_type": "constraint_relaxation",
            "playlist_name": "Tuesday_Breakfast_0600_0900",
            "criteria": {
                "playlist_id": "550e8400-e29b-41d4-a716-446655440001",
                "bpm_range": [85, 120],  # Relaxed from [90, 115]
                "genre_mix": {"Alternative": 0.30, "Electronic": 0.25},
            },
            "selected_tracks": [],
            "validation_result": {"relaxation_step": 1},
            "metadata": {
                "playlist_id": "550e8400-e29b-41d4-a716-446655440001",
                "llm_cost": "0.0015",
                "execution_time_ms": 2000,
                "relaxation_reason": "Insufficient tracks in BPM range",
            },
        }

    # =========================================================================
    # Test Group 1: JSONL Log File Creation (2 tests)
    # =========================================================================

    def test_init_creates_log_directory_if_not_exists(self, temp_log_dir):
        """Test 1: Verify log directory is created during initialization."""
        # Arrange: Ensure directory doesn't exist
        assert not temp_log_dir.exists()

        # Act: Initialize logger
        logger = DecisionLogger(log_dir=temp_log_dir)

        # Assert: Directory created
        assert temp_log_dir.exists()
        assert temp_log_dir.is_dir()
        # Log file created
        log_file = logger.get_log_file()
        assert log_file.exists()

    def test_init_creates_log_file_with_timestamp(self, logger):
        """Test 2: Verify log file is created with ISO 8601 timestamp."""
        # Act: Get log file path
        log_file = logger.get_log_file()

        # Assert: File exists with correct naming
        assert log_file.exists()
        assert log_file.suffix == ".jsonl"
        assert log_file.name.startswith("decisions_")

        # Extract and validate timestamp format
        # Pattern: decisions_YYYYMMDDTHHMMSS{microseconds}.jsonl
        timestamp_str = log_file.stem.replace("decisions_", "")
        assert len(timestamp_str) == 21  # YYYYMMDDTHHMMSS (15) + T (1) + microseconds (6)
        assert "T" in timestamp_str

        # Verify date and time parts are numeric
        date_part, time_part = timestamp_str.split("T")
        assert date_part.isdigit()
        assert time_part.isdigit()

    # =========================================================================
    # Test Group 2: Decision Logging (4 tests)
    # =========================================================================

    def test_log_track_selection_decision(self, logger, sample_track_selection_data):
        """Test 3: Verify track selection decisions are logged correctly."""
        # Act: Log track selection decision
        logger.log_decision(**sample_track_selection_data)

        # Assert: Decision logged with correct type
        decisions = logger.read_decisions()
        assert len(decisions) == 1

        decision = decisions[0]
        assert isinstance(decision, DecisionLog)
        assert decision.decision_type == DecisionType.TRACK_SELECTION
        assert decision.playlist_id == "550e8400-e29b-41d4-a716-446655440000"

        # Verify decision_data structure
        assert "playlist_name" in decision.decision_data
        assert decision.decision_data["playlist_name"] == "Monday_ProductionCall_0600_1000"
        assert "criteria" in decision.decision_data
        assert "selected_tracks" in decision.decision_data
        assert len(decision.decision_data["selected_tracks"]) == 2

    def test_log_constraint_relaxation_decision(self, logger, sample_relaxation_data):
        """Test 4: Verify constraint relaxation decisions are logged correctly."""
        # Act: Log constraint relaxation decision
        logger.log_decision(**sample_relaxation_data)

        # Assert: Decision logged with RELAXATION type
        decisions = logger.read_decisions()
        assert len(decisions) == 1

        decision = decisions[0]
        assert decision.decision_type == DecisionType.RELAXATION
        assert decision.playlist_id == "550e8400-e29b-41d4-a716-446655440001"

        # Verify relaxation-specific metadata
        assert "relaxation_reason" in decision.decision_data["metadata"]

    def test_log_error_decision(self, logger):
        """Test 5: Verify error decisions are logged correctly."""
        # Arrange: Error decision data
        error_data = {
            "decision_type": "error",
            "playlist_name": "Wednesday_Error_Test",
            "criteria": {"playlist_id": "550e8400-e29b-41d4-a716-446655440002"},
            "selected_tracks": [],
            "validation_result": {"error": "LLM API timeout"},
            "metadata": {
                "playlist_id": "550e8400-e29b-41d4-a716-446655440002",
                "llm_cost": "0.0000",
                "execution_time_ms": 5000,
                "error_type": "TimeoutError",
                "error_message": "LLM API request timed out after 5s",
            },
        }

        # Act: Log error decision
        logger.log_decision(**error_data)

        # Assert: Error logged with ERROR type
        decisions = logger.read_decisions()
        assert len(decisions) == 1

        decision = decisions[0]
        assert decision.decision_type == DecisionType.ERROR
        assert "error_message" in decision.decision_data["metadata"]

    def test_jsonl_format_verification(self, logger, sample_track_selection_data):
        """Test 6: Verify JSONL format - one JSON object per line."""
        # Act: Log multiple decisions
        for i in range(3):
            sample_track_selection_data["playlist_name"] = f"Playlist_{i}"
            logger.log_decision(**sample_track_selection_data)

        # Assert: Raw file has 3 lines of valid JSON
        with open(logger.get_log_file(), "r", encoding="utf-8") as f:
            lines = f.readlines()

        assert len(lines) == 3

        # Verify each line is valid JSON
        for line in lines:
            entry = json.loads(line)
            assert isinstance(entry, dict)
            assert "id" in entry
            assert "playlist_id" in entry
            assert "decision_type" in entry
            assert "timestamp" in entry
            assert "decision_data" in entry
            assert "cost_incurred" in entry
            assert "execution_time_ms" in entry

    # =========================================================================
    # Test Group 3: Cost and Timing Tracking (2 tests)
    # =========================================================================

    def test_track_llm_api_cost_per_decision(self, logger, sample_track_selection_data):
        """Test 7: Verify LLM API cost is tracked per decision."""
        # Act: Log decision with specific cost
        sample_track_selection_data["metadata"]["llm_cost"] = "0.0042"
        logger.log_decision(**sample_track_selection_data)

        # Assert: Cost tracked correctly
        decisions = logger.read_decisions()
        assert len(decisions) == 1

        decision = decisions[0]
        assert decision.cost_incurred == Decimal("0.0042")

        # Verify cost is stored as string in JSON (Decimal serialization)
        with open(logger.get_log_file(), "r", encoding="utf-8") as f:
            raw_entry = json.loads(f.readline())
            assert raw_entry["cost_incurred"] == "0.0042"

    def test_track_execution_time_per_decision(self, logger, sample_track_selection_data):
        """Test 8: Verify execution time is tracked in milliseconds."""
        # Act: Log decision with specific execution time
        sample_track_selection_data["metadata"]["execution_time_ms"] = 4250
        logger.log_decision(**sample_track_selection_data)

        # Assert: Execution time tracked correctly
        decisions = logger.read_decisions()
        assert len(decisions) == 1

        decision = decisions[0]
        assert decision.execution_time_ms == 4250

        # Verify multiple decisions with different execution times
        sample_track_selection_data["metadata"]["execution_time_ms"] = 1500
        logger.log_decision(**sample_track_selection_data)

        decisions = logger.read_decisions()
        assert decisions[0].execution_time_ms == 4250
        assert decisions[1].execution_time_ms == 1500

    # =========================================================================
    # Test Group 4: Log Retrieval and Filtering (2 tests)
    # =========================================================================

    def test_read_all_decisions_from_log(
        self, logger, sample_track_selection_data, sample_relaxation_data
    ):
        """Test 9: Verify reading all decisions from log file."""
        # Arrange: Log multiple decision types
        logger.log_decision(**sample_track_selection_data)
        logger.log_decision(**sample_relaxation_data)

        # Add validation decision
        validation_data = sample_track_selection_data.copy()
        validation_data["decision_type"] = "validation"
        validation_data["metadata"]["playlist_id"] = "550e8400-e29b-41d4-a716-446655440003"
        logger.log_decision(**validation_data)

        # Act: Read all decisions
        decisions = logger.read_decisions()

        # Assert: All decisions retrieved
        assert len(decisions) == 3

        # Verify decision types
        decision_types = [d.decision_type for d in decisions]
        assert DecisionType.TRACK_SELECTION in decision_types
        assert DecisionType.RELAXATION in decision_types
        assert DecisionType.VALIDATION in decision_types

        # Verify chronological order
        for i in range(len(decisions) - 1):
            assert decisions[i].timestamp <= decisions[i + 1].timestamp

    def test_filter_decisions_by_type_and_playlist(
        self, logger, sample_track_selection_data, sample_relaxation_data
    ):
        """Test 10: Verify filtering decisions by decision type and playlist name."""
        # Arrange: Log decisions for different playlists and types
        # Playlist 1: Track selections
        sample_track_selection_data["playlist_name"] = "Monday_Morning"
        logger.log_decision(**sample_track_selection_data)
        logger.log_decision(**sample_track_selection_data)

        # Playlist 2: Relaxation
        sample_relaxation_data["playlist_name"] = "Tuesday_Morning"
        logger.log_decision(**sample_relaxation_data)

        # Playlist 1: Another track selection
        sample_track_selection_data["playlist_name"] = "Monday_Morning"
        logger.log_decision(**sample_track_selection_data)

        # Act: Read all decisions
        all_decisions = logger.read_decisions()
        assert len(all_decisions) == 4

        # Filter by decision type
        track_selections = [
            d for d in all_decisions if d.decision_type == DecisionType.TRACK_SELECTION
        ]
        relaxations = [
            d for d in all_decisions if d.decision_type == DecisionType.RELAXATION
        ]

        # Assert: Filtering works correctly
        assert len(track_selections) == 3
        assert len(relaxations) == 1

        # Filter by playlist name
        monday_decisions = [
            d
            for d in all_decisions
            if d.decision_data.get("playlist_name") == "Monday_Morning"
        ]
        tuesday_decisions = [
            d
            for d in all_decisions
            if d.decision_data.get("playlist_name") == "Tuesday_Morning"
        ]

        assert len(monday_decisions) == 3
        assert len(tuesday_decisions) == 1

        # Combined filter: Track selections for Monday
        monday_selections = [
            d
            for d in all_decisions
            if d.decision_type == DecisionType.TRACK_SELECTION
            and d.decision_data.get("playlist_name") == "Monday_Morning"
        ]
        assert len(monday_selections) == 3

    # =========================================================================
    # Additional Edge Cases and Validation Tests
    # =========================================================================

    def test_invalid_decision_type_raises_error(self, logger, sample_track_selection_data):
        """Test that invalid decision_type raises ValueError."""
        # Arrange: Invalid decision type
        sample_track_selection_data["decision_type"] = "invalid_type"

        # Act & Assert: Should raise ValueError
        with pytest.raises(ValueError, match="Invalid decision_type"):
            logger.log_decision(**sample_track_selection_data)

    def test_append_only_behavior_no_rotation(self, logger, sample_track_selection_data):
        """Test that log file uses append-only writes (no rotation)."""
        # Arrange: Get initial log file
        initial_log_file = logger.get_log_file()

        # Act: Log many decisions
        for _ in range(50):
            logger.log_decision(**sample_track_selection_data)

        # Assert: Same log file used
        assert logger.get_log_file() == initial_log_file

        # All entries preserved
        decisions = logger.read_decisions()
        assert len(decisions) == 50

    def test_read_decisions_handles_empty_lines(self, logger, sample_track_selection_data):
        """Test that read_decisions skips empty lines."""
        # Arrange: Log decision, add empty lines, log another
        logger.log_decision(**sample_track_selection_data)

        with open(logger.get_log_file(), "a", encoding="utf-8") as f:
            f.write("\n")
            f.write("   \n")

        logger.log_decision(**sample_track_selection_data)

        # Act: Read decisions
        decisions = logger.read_decisions()

        # Assert: Empty lines skipped
        assert len(decisions) == 2

    def test_read_decisions_invalid_json_raises_error(self, logger):
        """Test that invalid JSON raises ValueError."""
        # Arrange: Write invalid JSON
        with open(logger.get_log_file(), "w", encoding="utf-8") as f:
            f.write("invalid json line\n")

        # Act & Assert: Should raise ValueError
        with pytest.raises(ValueError, match="Invalid decision log entry"):
            logger.read_decisions()

    def test_read_decisions_nonexistent_file_raises_error(self, logger):
        """Test that reading nonexistent file raises FileNotFoundError."""
        # Arrange: Nonexistent file path
        nonexistent_file = logger.log_dir / "nonexistent.jsonl"

        # Act & Assert: Should raise FileNotFoundError
        with pytest.raises(FileNotFoundError, match="Log file not found"):
            logger.read_decisions(log_file=nonexistent_file)

    def test_metadata_optional_generates_uuid(self, logger, sample_track_selection_data):
        """Test that metadata is optional and UUID is generated if missing."""
        # Arrange: Remove metadata but keep playlist_id in criteria
        sample_track_selection_data.pop("metadata")

        # Act: Log decision
        logger.log_decision(**sample_track_selection_data)

        # Assert: Decision logged with generated UUID and zero cost/time
        decisions = logger.read_decisions()
        assert len(decisions) == 1

        decision = decisions[0]
        assert decision.playlist_id == "550e8400-e29b-41d4-a716-446655440000"
        assert decision.cost_incurred == Decimal("0.00")
        assert decision.execution_time_ms == 0

    def test_playlist_id_generated_when_missing(self, logger, sample_track_selection_data):
        """Test that UUID is auto-generated when playlist_id is missing entirely."""
        import uuid as uuid_module

        # Arrange: Remove metadata AND playlist_id from criteria
        sample_track_selection_data.pop("metadata")
        sample_track_selection_data["criteria"].pop("playlist_id")

        # Act: Log decision
        logger.log_decision(**sample_track_selection_data)

        # Assert: Decision logged with auto-generated UUID
        decisions = logger.read_decisions()
        assert len(decisions) == 1

        decision = decisions[0]
        # Verify it's a valid UUID format
        try:
            uuid_module.UUID(decision.playlist_id)
            assert True  # Valid UUID
        except ValueError:
            assert False, f"Invalid UUID: {decision.playlist_id}"

        assert decision.cost_incurred == Decimal("0.00")
        assert decision.execution_time_ms == 0

    def test_list_log_files_returns_sorted_list(self, temp_log_dir, sample_track_selection_data):
        """Test that list_log_files returns all log files sorted."""
        import time

        # Arrange: Create multiple log files
        for _ in range(3):
            temp_logger = DecisionLogger(log_dir=temp_log_dir)
            temp_logger.log_decision(**sample_track_selection_data)
            time.sleep(0.01)  # Ensure different timestamps

        # Act: List log files
        logger = DecisionLogger(log_dir=temp_log_dir)
        log_files = logger.list_log_files()

        # Assert: All files listed and sorted
        assert len(log_files) == 4  # 3 created + current logger
        # Verify sorted order (oldest first)
        for i in range(len(log_files) - 1):
            assert log_files[i].name <= log_files[i + 1].name

    def test_count_decisions(self, logger, sample_track_selection_data):
        """Test that count_decisions returns correct count."""
        # Arrange: Empty log
        assert logger.count_decisions() == 0

        # Act: Log decisions
        for _ in range(7):
            logger.log_decision(**sample_track_selection_data)

        # Assert: Correct count
        assert logger.count_decisions() == 7

    def test_unicode_handling(self, logger, sample_track_selection_data):
        """Test that logger handles Unicode characters correctly."""
        # Arrange: Add Unicode characters
        sample_track_selection_data["playlist_name"] = "Monday_Café_0600_1000 🎵"
        sample_track_selection_data["selected_tracks"][0]["title"] = "Track with émojis 🎶"

        # Act: Log decision
        logger.log_decision(**sample_track_selection_data)

        # Assert: Unicode preserved
        decisions = logger.read_decisions()
        assert len(decisions) == 1
        assert decisions[0].decision_data["playlist_name"] == "Monday_Café_0600_1000 🎵"
        assert "émojis" in decisions[0].decision_data["selected_tracks"][0]["title"]
