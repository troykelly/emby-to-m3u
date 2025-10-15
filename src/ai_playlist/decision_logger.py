"""
Decision Logger - Indefinite Audit Trail for AI Playlist Generation

Implements JSONL-based logging system for playlist generation decisions with
indefinite retention per FR-014 specification.

Storage Format: JSON Lines (JSONL) - one DecisionLog entry per line
Retention Policy: Indefinite (never rotate or delete)
File Naming: decisions_{timestamp}.jsonl per execution
"""

import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
from decimal import Decimal
from .models.core import DecisionLog, DecisionType


class DecisionLogger:
    """
    Manages indefinite audit logging of playlist generation decisions.

    Creates one JSONL file per execution with append-only writes.
    Never rotates or deletes log files (indefinite retention).
    """

    def __init__(self, log_dir: Path = Path("logs/decisions")):
        """
        Initialize decision logger with log directory.

        Args:
            log_dir: Directory for decision log files (default: logs/decisions)

        Creates log directory if it doesn't exist.
        Creates new JSONL file per execution: decisions_{timestamp}.jsonl
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Create new log file per execution with ISO 8601 timestamp
        # Include microseconds to ensure unique filenames
        timestamp = datetime.now().strftime("%Y%m%dT%H%M%S%f")
        self.log_file = self.log_dir / f"decisions_{timestamp}.jsonl"

        # Initialize empty log file
        self.log_file.touch(exist_ok=True)

    def log_decision(
        self,
        decision_type: str,
        playlist_name: str,
        criteria: dict[str, str],
        selected_tracks: list[dict[str, str]],
        validation_result: dict[str, str],
        metadata: Optional[dict[str, str]] = None,
    ) -> None:
        """
        Log a playlist generation decision to JSONL file.

        Args:
            decision_type: Type of decision ("track_selection" | "constraint_relaxation" | "validation" | "sync")
            playlist_name: Playlist name for readability
            criteria: Serialized TrackSelectionCriteria (original or relaxed)
            selected_tracks: List of serialized SelectedTrack objects
            validation_result: Serialized ValidationResult
            metadata: Additional context (LLM cost, execution time, relaxation steps, errors)

        Creates DecisionLog instance and appends one JSON line to log file.
        Never rotates or deletes (indefinite retention per FR-014).

        Raises:
            ValueError: If decision_type is invalid or data is not JSON-serializable
            IOError: If log file cannot be written
        """
        # Extract playlist_id from metadata or criteria, or use a generated UUID
        playlist_id = None
        if metadata:
            playlist_id = metadata.get("playlist_id")
        if not playlist_id:
            # Try to extract from criteria
            playlist_id = criteria.get("playlist_id")
        if not playlist_id:
            # Generate a valid UUID4
            import uuid

            playlist_id = str(uuid.uuid4())

        # Map string decision_type to DecisionType enum
        decision_type_map = {
            "track_selection": DecisionType.TRACK_SELECTION,
            "constraint_relaxation": DecisionType.RELAXATION,
            "validation": DecisionType.VALIDATION,
            "sync": DecisionType.METADATA_RETRIEVAL,
            "error": DecisionType.ERROR
        }

        dt_enum = decision_type_map.get(decision_type.lower())
        if not dt_enum:
            raise ValueError(f"Invalid decision_type: {decision_type}")

        # Extract cost and execution time from metadata
        cost = Decimal(metadata.get("llm_cost", "0.00")) if metadata else Decimal("0.00")
        execution_time = int(metadata.get("execution_time_ms", 0)) if metadata else 0

        # Build decision_data from all the provided data
        decision_data = {
            "playlist_name": playlist_name,
            "criteria": criteria,
            "selected_tracks": selected_tracks,
            "validation_result": validation_result,
            "metadata": metadata or {}
        }

        # Create DecisionLog instance using proper signature
        decision_log = DecisionLog(
            id=str(__import__('uuid').uuid4()),
            playlist_id=playlist_id,
            decision_type=dt_enum,
            timestamp=datetime.now(),
            decision_data=decision_data,
            cost_incurred=cost,
            execution_time_ms=execution_time
        )

        # Serialize to JSON (one line) using to_dict()
        json_line = json.dumps(decision_log.to_dict())

        # Append to JSONL file (append-only, never rotate)
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json_line + "\n")

    def get_log_file(self) -> Path:
        """
        Get current log file path.

        Returns:
            Path: Path to current JSONL log file
        """
        return self.log_file

    def read_decisions(self, log_file: Optional[Path] = None) -> List[DecisionLog]:
        """
        Read and parse decisions from JSONL log file.

        Args:
            log_file: Optional specific log file to read (default: current log file)

        Returns:
            List[DecisionLog]: Parsed decision log entries

        Raises:
            FileNotFoundError: If log file doesn't exist
            json.JSONDecodeError: If log file contains invalid JSON
            ValueError: If log entries fail DecisionLog validation
        """
        target_file = log_file if log_file else self.log_file

        if not target_file.exists():
            raise FileNotFoundError(f"Log file not found: {target_file}")

        decisions = []
        with open(target_file, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, start=1):
                line = line.strip()
                if not line:  # Skip empty lines
                    continue

                try:
                    # Parse JSON and reconstruct DecisionLog
                    data = json.loads(line)

                    # Map string decision_type back to enum
                    decision_type_str = data.get("decision_type", "")
                    decision_type_map = {
                        "track_selection": DecisionType.TRACK_SELECTION,
                        "relaxation": DecisionType.RELAXATION,
                        "validation": DecisionType.VALIDATION,
                        "metadata_retrieval": DecisionType.METADATA_RETRIEVAL,
                        "error": DecisionType.ERROR
                    }
                    dt_enum = decision_type_map.get(decision_type_str.lower())
                    if not dt_enum:
                        raise ValueError(f"Invalid decision_type in log: {decision_type_str}")

                    # Parse timestamp
                    timestamp = datetime.fromisoformat(data.get("timestamp", datetime.now().isoformat()))

                    # Reconstruct DecisionLog
                    decision = DecisionLog(
                        id=data.get("id", ""),
                        playlist_id=data.get("playlist_id", ""),
                        decision_type=dt_enum,
                        timestamp=timestamp,
                        decision_data=data.get("decision_data", {}),
                        cost_incurred=Decimal(data.get("cost_incurred", "0.00")),
                        execution_time_ms=int(data.get("execution_time_ms", 0))
                    )
                    decisions.append(decision)
                except (json.JSONDecodeError, ValueError) as e:
                    raise ValueError(f"Invalid decision log entry at line {line_num}: {e}") from e

        return decisions

    def list_log_files(self) -> List[Path]:
        """
        List all decision log files in log directory.

        Returns:
            List[Path]: Sorted list of JSONL log files (oldest first)
        """
        log_files = sorted(self.log_dir.glob("decisions_*.jsonl"))
        return log_files

    def count_decisions(self, log_file: Optional[Path] = None) -> int:
        """
        Count number of decisions in log file.

        Args:
            log_file: Optional specific log file to count (default: current log file)

        Returns:
            int: Number of decision entries in log file
        """
        target_file = log_file if log_file else self.log_file

        if not target_file.exists():
            return 0

        with open(target_file, "r", encoding="utf-8") as f:
            return sum(1 for line in f if line.strip())
