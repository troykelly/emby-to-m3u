"""
Validation and decision logging models for AI Playlist.

This module contains dataclasses for playlist validation results
and decision audit logging.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List
import uuid
import json


@dataclass
class ConstraintScores:
    """Constraint satisfaction scores (0.0-1.0)."""

    constraint_satisfaction: float
    bpm_satisfaction: float
    genre_satisfaction: float
    era_satisfaction: float
    australian_content: float

    def __post_init__(self) -> None:
        """Validate all scores are in range 0.0-1.0."""
        for field_name, field_value in [
            ("constraint_satisfaction", self.constraint_satisfaction),
            ("bpm_satisfaction", self.bpm_satisfaction),
            ("genre_satisfaction", self.genre_satisfaction),
            ("era_satisfaction", self.era_satisfaction),
            ("australian_content", self.australian_content),
        ]:
            if not 0.0 <= field_value <= 1.0:
                raise ValueError(f"{field_name} must be 0.0-1.0")


@dataclass
class FlowMetrics:
    """Flow quality metrics for playlist."""

    flow_quality_score: float
    bpm_variance: float
    energy_progression: str
    genre_diversity: float

    def __post_init__(self) -> None:
        """Validate flow metrics."""
        if not 0.0 <= self.flow_quality_score <= 1.0:
            raise ValueError("flow_quality_score must be 0.0-1.0")

        if self.bpm_variance < 0:
            raise ValueError("BPM variance must be ≥ 0")

        valid_progressions = ["smooth", "choppy", "monotone"]
        if self.energy_progression not in valid_progressions:
            raise ValueError(f"Energy progression must be one of {valid_progressions}")

        if not 0.0 <= self.genre_diversity <= 1.0:
            raise ValueError("genre_diversity must be 0.0-1.0")


@dataclass
class ValidationResult:
    """Quality assessment of generated playlist."""

    constraint_scores: ConstraintScores
    flow_metrics: FlowMetrics
    gap_analysis: Dict[str, str]
    passes_validation: bool

    def __post_init__(self) -> None:
        """Validate validation result constraints."""
        # Gap analysis validation
        if not isinstance(self.gap_analysis, dict):
            raise ValueError("Gap analysis must be a dict")

        # Passes validation consistency
        expected = (
            self.constraint_scores.constraint_satisfaction >= 0.80
            and self.flow_metrics.flow_quality_score >= 0.70
        )
        if self.passes_validation != expected:
            raise ValueError(
                f"passes_validation ({self.passes_validation}) inconsistent with "
                f"thresholds (constraint: {self.constraint_scores.constraint_satisfaction}, "
                f"flow: {self.flow_metrics.flow_quality_score})"
            )

    def is_valid(self) -> bool:
        """Check if validation passed."""
        return self.passes_validation


@dataclass
class DecisionLog:
    """Audit trail for playlist generation decisions (indefinite retention)."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)
    decision_type: str = ""
    playlist_id: str = ""
    playlist_name: str = ""
    criteria: Dict[str, Any] = field(default_factory=dict)
    selected_tracks: List[Dict[str, Any]] = field(default_factory=list)
    validation_result: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate decision log constraints."""
        # ID validation
        try:
            uuid.UUID(self.id, version=4)
        except ValueError as exc:
            raise ValueError("ID must be valid UUID4") from exc

        # Timestamp validation
        if self.timestamp > datetime.now():
            raise ValueError("Timestamp cannot be in future")

        # Decision type validation
        valid_types = ["track_selection", "constraint_relaxation", "validation", "sync"]
        if self.decision_type not in valid_types:
            raise ValueError(f"Decision type must be one of {valid_types}")

        # Playlist ID validation
        try:
            uuid.UUID(self.playlist_id, version=4)
        except ValueError as exc:
            raise ValueError("Playlist ID must be valid UUID4") from exc

        # Playlist name validation
        if not self.playlist_name:
            raise ValueError("Playlist name must be non-empty")

        # JSON serialization validation
        for field_name, field_value in [
            ("criteria", self.criteria),
            ("selected_tracks", self.selected_tracks),
            ("validation_result", self.validation_result),
            ("metadata", self.metadata),
        ]:
            try:
                json.dumps(field_value)
            except (TypeError, ValueError) as e:
                raise ValueError(f"{field_name} must be JSON-serializable: {e}") from e

    def to_json(self) -> str:
        """Serialize decision log to JSON string."""
        return json.dumps(
            {
                "id": self.id,
                "timestamp": self.timestamp.isoformat(),
                "decision_type": self.decision_type,
                "playlist_id": self.playlist_id,
                "playlist_name": self.playlist_name,
                "criteria": self.criteria,
                "selected_tracks": self.selected_tracks,
                "validation_result": self.validation_result,
                "metadata": self.metadata,
            }
        )

    @classmethod
    def from_json(cls, json_str: str) -> "DecisionLog":
        """Deserialize decision log from JSON string."""
        data = json.loads(json_str)
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)
