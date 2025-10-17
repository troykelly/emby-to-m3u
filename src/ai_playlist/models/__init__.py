"""
AI Playlist Models Package.

This package contains all dataclasses and enumerations for the AI/ML-powered
playlist generation system.

Core Entities:
    - StationIdentityDocument: Authoritative programming guide with file locking
    - DaypartSpecification: Time-bound programming segments
    - PlaylistSpecification: Generated playlist specification
    - TrackSelectionCriteria: Complete selection constraints
    - SelectedTrack: Individual selected track
    - Playlist: Complete generated playlist
    - ConstraintRelaxation: Progressive relaxation record
    - DecisionLog: Audit trail entry

Validation:
    - ValidationResult: Complete validation assessment
    - ConstraintScore: Individual constraint score
    - FlowQualityMetrics: Flow quality measurements

Supporting Types:
    - BPMRange, GenreCriteria, EraCriteria
    - ProgrammingStructure, RotationStrategy, ContentRequirements
    - ScheduleType, ValidationStatus, DecisionType (Enums)
"""

# Core entity imports
from .core import (
    # Enumerations
    ScheduleType,
    ValidationStatus,
    DecisionType,

    # Supporting dataclasses
    BPMRange,
    SpecialtyConstraint,
    GenreCriteria,
    EraCriteria,
    ProgrammingStructure,
    RotationCategory,
    RotationStrategy,
    ContentRequirements,
    GenreDefinition,

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

# Validation imports
from .validation import (
    ConstraintScore,
    FlowQualityMetrics,
    ValidationResult,
    # Legacy classes for backward compatibility
    ConstraintScores,
    FlowMetrics,
)

# LLM-specific imports
from .llm import (
    LLMTrackSelectionRequest,
    LLMTrackSelectionResponse,
)

# Backward compatibility aliases
PlaylistSpec = PlaylistSpecification
DaypartSpec = DaypartSpecification

__all__ = [
    # Enumerations
    "ScheduleType",
    "ValidationStatus",
    "DecisionType",

    # Supporting dataclasses
    "BPMRange",
    "SpecialtyConstraint",
    "GenreCriteria",
    "EraCriteria",
    "ProgrammingStructure",
    "RotationCategory",
    "RotationStrategy",
    "ContentRequirements",
    "GenreDefinition",

    # Core entities
    "StationIdentityDocument",
    "DaypartSpecification",
    "TrackSelectionCriteria",
    "PlaylistSpecification",
    "SelectedTrack",
    "ConstraintRelaxation",
    "Playlist",
    "DecisionLog",

    # Validation
    "ConstraintScore",
    "FlowQualityMetrics",
    "ValidationResult",

    # LLM types
    "LLMTrackSelectionRequest",
    "LLMTrackSelectionResponse",

    # Legacy (backward compatibility)
    "ConstraintScores",
    "FlowMetrics",
    "PlaylistSpec",
    "DaypartSpec",
]
