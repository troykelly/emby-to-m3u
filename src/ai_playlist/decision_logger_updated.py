"""
Decision Logger with Relaxation Tracking - T035

Logs all track selection decisions, constraint relaxations, costs, and execution times.

Success Criteria (T023, T025):
- Log track selections with AI reasoning
- Log constraint relaxations with before/after values
- Log cost and execution time for each decision
- Write logs to JSONL file per playlist
"""

import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from decimal import Decimal
import logging

from src.ai_playlist.models.core import (
    DecisionLog,
    DecisionType,
    SelectedTrack,
    ConstraintRelaxation
)

logger = logging.getLogger(__name__)


class DecisionLogger:
    """Logs playlist generation decisions to JSONL files."""

    def __init__(self, output_dir: Path):
        """Initialize decision logger.

        Args:
            output_dir: Directory for decision log files
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def log_track_selection(
        self,
        playlist_id: str,
        track: SelectedTrack,
        reasoning: str,
        cost_incurred: Optional[Decimal] = None,
        execution_time_ms: Optional[int] = None
    ) -> DecisionLog:
        """Log a track selection decision.

        Args:
            playlist_id: Playlist identifier
            track: Selected track
            reasoning: AI reasoning for selection
            cost_incurred: API cost for this decision
            execution_time_ms: Time taken in milliseconds

        Returns:
            DecisionLog entry
        """
        entry = DecisionLog(
            id=f"track_sel_{track.track_id}",
            playlist_id=playlist_id,
            decision_type=DecisionType.TRACK_SELECTION,
            timestamp=datetime.now(),
            decision_data={
                "track_id": track.track_id,
                "title": track.title,
                "artist": track.artist,
                "bpm": track.bpm,
                "genre": track.genre,
                "year": track.year,
                "is_australian": track.is_australian,
                "reasoning": reasoning,
                "position": track.position_in_playlist
            },
            cost_incurred=cost_incurred,
            execution_time_ms=execution_time_ms
        )

        self._write_entry(entry)
        return entry

    def log_constraint_relaxation(
        self,
        playlist_id: str,
        relaxation: ConstraintRelaxation,
        cost_incurred: Optional[Decimal] = None,
        execution_time_ms: Optional[int] = None
    ) -> DecisionLog:
        """Log a constraint relaxation decision.

        Args:
            playlist_id: Playlist identifier
            relaxation: Relaxation that was applied
            cost_incurred: API cost for this decision
            execution_time_ms: Time taken in milliseconds

        Returns:
            DecisionLog entry
        """
        entry = DecisionLog(
            id=f"relax_{playlist_id}_{relaxation.iteration}",
            playlist_id=playlist_id,
            decision_type=DecisionType.RELAXATION,
            timestamp=datetime.now(),
            decision_data={
                "iteration": relaxation.iteration,
                "constraint_type": relaxation.constraint_type,
                "original_value": relaxation.original_value,
                "relaxed_value": relaxation.relaxed_value,
                "reason": relaxation.reason
            },
            cost_incurred=cost_incurred,
            execution_time_ms=execution_time_ms
        )

        self._write_entry(entry)
        return entry

    def log_validation(
        self,
        playlist_id: str,
        validation_result: Dict[str, Any],
        cost_incurred: Optional[Decimal] = None,
        execution_time_ms: Optional[int] = None
    ) -> DecisionLog:
        """Log a validation decision.

        Args:
            playlist_id: Playlist identifier
            validation_result: Validation results
            cost_incurred: API cost for this decision
            execution_time_ms: Time taken in milliseconds

        Returns:
            DecisionLog entry
        """
        entry = DecisionLog(
            id=f"valid_{playlist_id}",
            playlist_id=playlist_id,
            decision_type=DecisionType.VALIDATION,
            timestamp=datetime.now(),
            decision_data=validation_result,
            cost_incurred=cost_incurred,
            execution_time_ms=execution_time_ms
        )

        self._write_entry(entry)
        return entry

    def log_error(
        self,
        playlist_id: str,
        error_message: str,
        error_details: Optional[Dict[str, Any]] = None,
        execution_time_ms: Optional[int] = None
    ) -> DecisionLog:
        """Log an error decision.

        Args:
            playlist_id: Playlist identifier
            error_message: Error message
            error_details: Additional error details
            execution_time_ms: Time taken in milliseconds

        Returns:
            DecisionLog entry
        """
        entry = DecisionLog(
            id=f"error_{playlist_id}_{datetime.now().timestamp()}",
            playlist_id=playlist_id,
            decision_type=DecisionType.ERROR,
            timestamp=datetime.now(),
            decision_data={
                "error_message": error_message,
                "error_details": error_details or {}
            },
            cost_incurred=None,
            execution_time_ms=execution_time_ms
        )

        self._write_entry(entry)
        return entry

    def log_metadata_retrieval(
        self,
        playlist_id: str,
        track_id: str,
        source: str,
        metadata: Dict[str, Any],
        cost_incurred: Optional[Decimal] = None,
        execution_time_ms: Optional[int] = None
    ) -> DecisionLog:
        """Log metadata retrieval decision.

        Args:
            playlist_id: Playlist identifier
            track_id: Track identifier
            source: Metadata source (Last.fm, aubio, etc.)
            metadata: Retrieved metadata
            cost_incurred: API cost for this decision
            execution_time_ms: Time taken in milliseconds

        Returns:
            DecisionLog entry
        """
        entry = DecisionLog(
            id=f"metadata_{track_id}",
            playlist_id=playlist_id,
            decision_type=DecisionType.METADATA_RETRIEVAL,
            timestamp=datetime.now(),
            decision_data={
                "track_id": track_id,
                "source": source,
                "metadata": metadata
            },
            cost_incurred=cost_incurred,
            execution_time_ms=execution_time_ms
        )

        self._write_entry(entry)
        return entry

    def _write_entry(self, entry: DecisionLog) -> None:
        """Write decision log entry to JSONL file.

        Args:
            entry: DecisionLog entry to write
        """
        log_file = self.output_dir / f"{entry.playlist_id}_decisions.jsonl"

        # Convert entry to dict
        entry_dict = entry.to_dict()

        # Convert Decimal to float for JSON serialization
        if entry_dict.get('cost_incurred'):
            entry_dict['cost_incurred'] = float(entry_dict['cost_incurred'])

        # Append to JSONL file
        with open(log_file, 'a', encoding='utf-8') as f:
            json.dump(entry_dict, f)
            f.write('\n')

        logger.debug(f"Logged {entry.decision_type.value} decision for {entry.playlist_id}")

    def read_decisions(self, playlist_id: str) -> List[DecisionLog]:
        """Read all decision log entries for a playlist.

        Args:
            playlist_id: Playlist identifier

        Returns:
            List of DecisionLog entries
        """
        log_file = self.output_dir / f"{playlist_id}_decisions.jsonl"

        if not log_file.exists():
            return []

        entries = []

        with open(log_file, 'r', encoding='utf-8') as f:
            for line in f:
                data = json.loads(line.strip())
                # Convert back to DecisionLog
                entries.append(DecisionLog(
                    id=data['id'],
                    playlist_id=data['playlist_id'],
                    decision_type=DecisionType(data['decision_type']),
                    timestamp=datetime.fromisoformat(data['timestamp']),
                    decision_data=data['decision_data'],
                    cost_incurred=Decimal(str(data.get('cost_incurred', 0))),
                    execution_time_ms=data.get('execution_time_ms')
                ))

        return entries

    def calculate_total_cost(self, playlist_id: str) -> Decimal:
        """Calculate total cost for all decisions in a playlist.

        Args:
            playlist_id: Playlist identifier

        Returns:
            Total cost as Decimal
        """
        entries = self.read_decisions(playlist_id)
        total = sum(
            (e.cost_incurred or Decimal('0')) for e in entries
        )
        return total

    def calculate_total_time(self, playlist_id: str) -> int:
        """Calculate total execution time for all decisions in a playlist.

        Args:
            playlist_id: Playlist identifier

        Returns:
            Total time in milliseconds
        """
        entries = self.read_decisions(playlist_id)
        total = sum(
            (e.execution_time_ms or 0) for e in entries
        )
        return total
