"""
Pytest fixtures for data model unit tests.

This module provides reusable test data and fixtures for all model tests.
"""

import pytest
from datetime import datetime, date, time
from decimal import Decimal
from pathlib import Path
from typing import Dict, List

from src.ai_playlist.models import (
    # Enumerations
    ScheduleType,
    ValidationStatus,
    DecisionType,
    # Supporting dataclasses
    BPMRange,
    GenreCriteria,
    EraCriteria,
    SpecialtyConstraint,
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
    # Validation
    ConstraintScore,
    FlowQualityMetrics,
    ValidationResult,
    # Legacy
    ConstraintScores,
    FlowMetrics,
)


@pytest.fixture
def valid_bpm_range() -> BPMRange:
    """Valid BPM range."""
    return BPMRange(
        time_start=time(6, 0),
        time_end=time(10, 0),
        bpm_min=120,
        bpm_max=140,
    )


@pytest.fixture
def valid_genre_criteria() -> GenreCriteria:
    """Valid genre criteria."""
    return GenreCriteria(
        target_percentage=0.40,
        tolerance=0.10,
    )


@pytest.fixture
def valid_era_criteria() -> EraCriteria:
    """Valid era criteria."""
    return EraCriteria(
        era_name="Current",
        min_year=2023,
        max_year=2025,
        target_percentage=0.30,
        tolerance=0.10,
    )


@pytest.fixture
def valid_rotation_category() -> RotationCategory:
    """Valid rotation category."""
    return RotationCategory(
        name="Power",
        spins_per_week=30,
        lifecycle_weeks=4,
    )


@pytest.fixture
def valid_rotation_strategy(valid_rotation_category) -> RotationStrategy:
    """Valid rotation strategy."""
    return RotationStrategy(
        categories={"Power": valid_rotation_category}
    )


@pytest.fixture
def valid_content_requirements() -> ContentRequirements:
    """Valid content requirements."""
    return ContentRequirements(
        australian_content_min=0.30,
        australian_content_target=0.35,
    )


@pytest.fixture
def valid_daypart_spec(valid_bpm_range) -> DaypartSpecification:
    """Valid DaypartSpecification."""
    return DaypartSpecification(
        id="daypart-001",
        name="Morning Drive: Production Call",
        schedule_type=ScheduleType.WEEKDAY,
        time_start=time(6, 0),
        time_end=time(10, 0),
        duration_hours=4.0,
        target_demographic="25-54 working professionals",
        bpm_progression=[valid_bpm_range],
        genre_mix={"Rock": 0.40, "Pop": 0.30, "Alternative": 0.30},
        era_distribution={"Current": 0.30, "Recent": 0.40, "Modern Classics": 0.30},
        mood_guidelines=["energetic", "uplifting"],
        content_focus="High-energy morning drive",
        rotation_percentages={"Power": 0.30, "Medium": 0.40, "Light": 0.30},
        tracks_per_hour=(10, 12),
    )


@pytest.fixture
def valid_track_criteria(valid_bpm_range) -> TrackSelectionCriteria:
    """Valid TrackSelectionCriteria."""
    return TrackSelectionCriteria(
        bpm_ranges=[valid_bpm_range],
        genre_mix={
            "Rock": GenreCriteria(target_percentage=0.40, tolerance=0.10),
            "Pop": GenreCriteria(target_percentage=0.30, tolerance=0.10),
        },
        era_distribution={
            "Current": EraCriteria("Current", 2023, 2025, 0.30, 0.10),
            "Recent": EraCriteria("Recent", 2018, 2022, 0.40, 0.10),
        },
        australian_content_min=0.30,
        energy_flow_requirements=["energetic", "uplifting"],
        rotation_distribution={"Power": 0.30, "Medium": 0.40},
        no_repeat_window_hours=4.0,
    )


@pytest.fixture
def valid_playlist_spec(valid_daypart_spec, valid_track_criteria) -> PlaylistSpecification:
    """Valid PlaylistSpecification."""
    return PlaylistSpecification(
        id="playlist-spec-001",
        name="Morning Drive: Production Call - 2025-01-15",
        source_daypart_id=valid_daypart_spec.id,
        generation_date=date(2025, 1, 15),
        target_track_count_min=40,
        target_track_count_max=48,
        track_selection_criteria=valid_track_criteria,
        created_at=datetime.now(),
        cost_budget_allocated=Decimal("0.50"),
    )


@pytest.fixture
def valid_selected_track() -> SelectedTrack:
    """Valid SelectedTrack."""
    return SelectedTrack(
        track_id="track-123",
        title="Test Song",
        artist="Test Artist",
        album="Test Album",
        duration_seconds=240,
        is_australian=True,
        rotation_category="Power",
        position_in_playlist=0,
        selection_reasoning="Matches BPM and genre criteria",
        validation_status=ValidationStatus.PASS,
        metadata_source="subsonic",
        bpm=128,
        genre="Rock",
        year=2024,
        country="AU",
    )


@pytest.fixture
def valid_playlist(valid_playlist_spec, valid_selected_track) -> Playlist:
    """Valid Playlist."""
    playlist = Playlist.create(valid_playlist_spec)
    playlist.add_track(valid_selected_track)
    playlist.cost_actual = Decimal("0.05")
    playlist.generation_time_seconds = 5.5
    return playlist


@pytest.fixture
def valid_constraint_score() -> ConstraintScore:
    """Valid ConstraintScore."""
    return ConstraintScore.calculate(
        name="Australian Content",
        target=0.30,
        actual=0.35,
        tolerance=0.10,
    )


@pytest.fixture
def valid_flow_metrics() -> FlowQualityMetrics:
    """Valid FlowQualityMetrics."""
    return FlowQualityMetrics(
        bpm_variance=8.5,
        bpm_progression_coherence=0.85,
        energy_consistency=0.90,
        genre_diversity_index=0.75,
    )


@pytest.fixture
def valid_constraint_relaxation() -> ConstraintRelaxation:
    """Valid ConstraintRelaxation."""
    return ConstraintRelaxation(
        step=1,
        constraint_type="bpm",
        original_value="120-140",
        relaxed_value="110-150",
        reason="Insufficient tracks in target range",
        timestamp=datetime.now(),
    )


@pytest.fixture
def valid_decision_log(valid_selected_track) -> DecisionLog:
    """Valid DecisionLog."""
    return DecisionLog.log_track_selection(
        playlist_id="playlist-001",
        track=valid_selected_track,
        criteria_matched=["bpm", "genre", "australian"],
        cost=Decimal("0.002"),
        execution_time_ms=150,
    )
