"""
Backward compatibility module for ai_playlist.core.

This module provides backward compatibility aliases for code that imports from
ai_playlist.core.models. The actual models have been moved to ai_playlist.models
as part of the refactoring to improve code organization.

Legacy imports (still supported):
    from ai_playlist.core.models import StationIdentityDocument
    from ai_playlist.core.models import ValidationResult

New imports (preferred):
    from ai_playlist.models.core import StationIdentityDocument
    from ai_playlist.models.validation import ValidationResult
"""

# Import all models from the new locations
from ..models.core import (
    # Enumerations
    ScheduleType,
    ValidationStatus,
    DecisionType,
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
    # Core entities
    StationIdentityDocument,
    DaypartSpecification,
    TrackSelectionCriteria,
    PlaylistSpecification,
    SelectedTrack,
    ConstraintRelaxation,
    Playlist,
    DecisionLog,
)

from ..models.validation import (
    ConstraintScore,
    FlowQualityMetrics,
    ValidationResult,
    # Legacy classes
    ConstraintScores,
    FlowMetrics,
)

__all__ = [
    # Core models
    "StationIdentityDocument",
    "DaypartSpecification",
    "PlaylistSpecification",
    "TrackSelectionCriteria",
    "SelectedTrack",
    "Playlist",
    "DecisionLog",
    "ConstraintRelaxation",
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
