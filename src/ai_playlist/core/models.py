"""
Backward compatibility module for ai_playlist.core.models.

This module re-exports all models from ai_playlist.models to maintain backward
compatibility with code that imports from ai_playlist.core.models.

The models have been reorganized as follows:
- Core data models: ai_playlist.models.core
- Validation models: ai_playlist.models.validation

This file will be maintained for backward compatibility but new code should
import directly from ai_playlist.models.
"""

# Re-export all core models
from ..models.core import (
    # Core entity classes
    StationIdentityDocument,
    DaypartSpecification,
    PlaylistSpecification,
    TrackSelectionCriteria,
    SelectedTrack,
    Playlist,
    DecisionLog,
    ConstraintRelaxation,
    # Supporting dataclasses
    BPMRange,
    GenreCriteria,
    EraCriteria,
    ProgrammingStructure,
    RotationCategory,
    RotationStrategy,
    ContentRequirements,
    GenreDefinition,
    SpecialtyConstraint,
    # Enumerations
    ScheduleType,
    ValidationStatus,
    DecisionType,
)

# Re-export all validation models
from ..models.validation import (
    ValidationResult,
    ConstraintScore,
    FlowQualityMetrics,
    ConstraintScores,
    FlowMetrics,
)

# Define what gets exported with "from ai_playlist.core.models import *"
__all__ = [
    # Core entity classes
    "StationIdentityDocument",
    "DaypartSpecification",
    "PlaylistSpecification",
    "TrackSelectionCriteria",
    "SelectedTrack",
    "Playlist",
    "DecisionLog",
    "ConstraintRelaxation",
    # Supporting dataclasses
    "BPMRange",
    "GenreCriteria",
    "EraCriteria",
    "ProgrammingStructure",
    "RotationCategory",
    "RotationStrategy",
    "ContentRequirements",
    "GenreDefinition",
    "SpecialtyConstraint",
    # Enumerations
    "ScheduleType",
    "ValidationStatus",
    "DecisionType",
    # Validation models
    "ValidationResult",
    "ConstraintScore",
    "FlowQualityMetrics",
    "ConstraintScores",
    "FlowMetrics",
]
