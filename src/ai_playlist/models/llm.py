"""
LLM-related data models for AI Playlist - Requests, responses, and track data.

This module contains dataclasses for LLM track selection requests and responses,
selected tracks, and final playlists.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid

from .core import TrackSelectionCriteria, PlaylistSpec
from .validation import ValidationResult
from ._validation_helpers import validate_playlist_name


@dataclass
class LLMTrackSelectionRequest:
    """Request payload for OpenAI LLM track selection via MCP."""

    playlist_id: str
    criteria: TrackSelectionCriteria
    target_track_count: int
    mcp_tools: List[str] = field(
        default_factory=lambda: [
            "search_tracks",
            "get_genres",
            "search_similar",
            "analyze_library",
        ]
    )
    prompt_template: str = ""
    max_cost_usd: float = 0.01
    timeout_seconds: int = 30

    def __post_init__(self) -> None:
        """Validate LLM track selection request constraints."""
        # Playlist ID validation
        try:
            uuid.UUID(self.playlist_id, version=4)
        except ValueError as exc:
            raise ValueError("Playlist ID must be valid UUID4") from exc

        # Target track count validation
        if not 0 < self.target_track_count <= 1000:
            raise ValueError("Target track count must be > 0 and ≤ 1000")

        # MCP tools validation
        if not self.mcp_tools:
            raise ValueError("MCP tools must be non-empty")

        # Prompt template validation (optional - can be auto-generated)
        # No validation needed - empty string is valid

        # Cost validation
        if not 0 < self.max_cost_usd <= 0.50:
            raise ValueError("Max cost must be > 0 and ≤ 0.50")

        # Timeout validation
        if not 0 < self.timeout_seconds <= 300:
            raise ValueError("Timeout must be > 0 and ≤ 300")


@dataclass
class SelectedTrack:
    """Track selected by LLM with metadata for validation."""

    track_id: str
    title: str
    artist: str
    album: str
    bpm: Optional[int]
    genre: Optional[str]
    year: Optional[int]
    country: Optional[str]
    duration_seconds: int
    position: int
    selection_reason: str

    def __post_init__(self) -> None:
        """Validate selected track constraints."""
        # ID validation
        if not self.track_id:
            raise ValueError("Track ID must be non-empty")

        # Text field validation
        for field_name, field_value in [
            ("title", self.title),
            ("artist", self.artist),
            ("album", self.album),
        ]:
            if not field_value or len(field_value) > 200:
                raise ValueError(f"{field_name} must be non-empty and max 200 chars")

        # BPM validation
        if self.bpm is not None and (self.bpm <= 0 or self.bpm > 300):
            raise ValueError("BPM must be > 0 and ≤ 300")

        # Genre validation
        if self.genre is not None and (not self.genre or len(self.genre) > 50):
            raise ValueError("Genre must be non-empty and max 50 chars")

        # Year validation
        current_year = datetime.now().year
        if self.year is not None and not 1900 <= self.year <= current_year + 1:
            raise ValueError(f"Year must be 1900-{current_year + 1}")

        # Duration validation
        if self.duration_seconds <= 0:
            raise ValueError("Duration must be > 0")

        # Position validation
        if self.position <= 0:
            raise ValueError("Position must be > 0")

        # Selection reason validation
        if not self.selection_reason or len(self.selection_reason) > 500:
            raise ValueError("Selection reason must be non-empty and max 500 chars")


@dataclass
class LLMTrackSelectionResponse:
    """Response from OpenAI LLM with selected tracks and metadata."""

    request_id: str
    selected_tracks: List[SelectedTrack]
    tool_calls: List[Dict[str, Any]]
    reasoning: str
    cost_usd: float
    execution_time_seconds: float
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        """Validate LLM track selection response constraints."""
        # Request ID validation
        try:
            uuid.UUID(self.request_id, version=4)
        except ValueError as exc:
            raise ValueError("Request ID must be valid UUID4") from exc

        # Selected tracks validation
        if not self.selected_tracks:
            raise ValueError("Selected tracks must be non-empty")

        # Tool calls validation
        for tool_call in self.tool_calls:
            if not all(key in tool_call for key in ["tool_name", "arguments", "result"]):
                raise ValueError("Tool call must have tool_name, arguments, result")

        # Reasoning validation
        if not self.reasoning or len(self.reasoning) > 2000:
            raise ValueError("Reasoning must be non-empty and max 2000 chars")

        # Cost validation
        if self.cost_usd < 0:
            raise ValueError("Cost must be ≥ 0")

        # Execution time validation
        if self.execution_time_seconds < 0:
            raise ValueError("Execution time must be ≥ 0")

        # Created at validation
        if self.created_at > datetime.now():
            raise ValueError("Created at cannot be in future")


@dataclass
class Playlist:
    """Final validated playlist ready for AzuraCast sync."""

    id: str
    name: str
    tracks: List[SelectedTrack]
    spec: PlaylistSpec
    validation_result: ValidationResult
    created_at: datetime = field(default_factory=datetime.now)
    synced_at: Optional[datetime] = None
    azuracast_id: Optional[int] = None

    def __post_init__(self) -> None:
        """Validate playlist constraints."""
        # ID validation
        try:
            uuid.UUID(self.id, version=4)
        except ValueError as exc:
            raise ValueError("ID must be valid UUID4") from exc

        # ID consistency with spec
        if self.id != self.spec.id:
            raise ValueError("Playlist ID must match PlaylistSpec ID")

        # Name validation (schema: {Day}_{ShowName}_{StartTime}_{EndTime})
        validate_playlist_name(self.name)

        # Tracks validation
        if not self.tracks:
            raise ValueError("Tracks must be non-empty")

        # Validation result must pass
        if not self.validation_result.is_valid():
            raise ValueError(
                f"ValidationResult must pass (constraint: "
                f"{self.validation_result.constraint_scores.constraint_satisfaction}, "
                f"flow: {self.validation_result.flow_metrics.flow_quality_score})"
            )

        # Created at validation
        if self.created_at > datetime.now():
            raise ValueError("Created at cannot be in future")

        # Synced at validation
        if self.synced_at is not None and self.synced_at < self.created_at:
            raise ValueError("Synced at must be ≥ created at")

        # AzuraCast ID validation
        if self.azuracast_id is not None and self.azuracast_id <= 0:
            raise ValueError("AzuraCast ID must be > 0")
