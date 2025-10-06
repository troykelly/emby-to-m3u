"""
AI Playlist Data Models - Modular Package Structure

This package provides all data models for LLM-driven playlist automation
organized into focused submodules for maintainability (<500 lines each).

Modules:
    - core: Programming documents, dayparts, playlist specs, and criteria
    - llm: LLM requests, responses, tracks, and playlists
    - validation: Validation results and decision logging
"""

# Import all models from submodules for backward compatibility
from .core import (
    ProgrammingDocument,
    DaypartSpec,
    PlaylistSpec,
    TrackSelectionCriteria,
)

from .llm import (
    LLMTrackSelectionRequest,
    LLMTrackSelectionResponse,
    SelectedTrack,
    Playlist,
)

from .validation import (
    ValidationResult,
    DecisionLog,
)

# Export all models at package level
__all__ = [
    # Core models
    "ProgrammingDocument",
    "DaypartSpec",
    "PlaylistSpec",
    "TrackSelectionCriteria",
    # LLM models
    "LLMTrackSelectionRequest",
    "LLMTrackSelectionResponse",
    "SelectedTrack",
    "Playlist",
    # Validation models
    "ValidationResult",
    "DecisionLog",
]
