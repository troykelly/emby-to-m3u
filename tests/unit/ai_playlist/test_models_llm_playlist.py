"""Coverage tests for models/llm.py Playlist class (lines 184-218).

Tests the Playlist validation logic in __post_init__.
"""
import pytest
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from src.ai_playlist.models.llm import Playlist, SelectedTrack
from src.ai_playlist.models import (
    PlaylistSpecification,
    TrackSelectionCriteria,
    ValidationResult,
    ValidationStatus
)
from datetime import date


@pytest.fixture
def sample_spec():
    """Create sample playlist specification."""
    criteria = TrackSelectionCriteria(
        bpm_ranges=[],
        genre_mix={},
        era_distribution={},
        australian_content_min=0.30,
        energy_flow_requirements=[],
        rotation_distribution={},
        no_repeat_window_hours=24.0
    )

    return PlaylistSpecification(
        id=str(uuid.uuid4()),
        name="Monday_MorningDrive_0600_1000",
        source_daypart_id=str(uuid.uuid4()),
        generation_date=date.today(),
        target_track_count_min=10,
        target_track_count_max=15,
        target_duration_minutes=240,
        track_selection_criteria=criteria,
        created_at=datetime.now()
    )


@pytest.fixture
def sample_track():
    """Create sample selected track."""
    return SelectedTrack(
        track_id="test-123",
        title="Test Song",
        artist="Test Artist",
        album="Test Album",
        bpm=120,
        genre="Rock",
        year=2023,
        country="AU",
        duration_seconds=180,
        position=1,
        selection_reason="Test reason"
    )


@pytest.fixture
def passing_validation():
    """Create passing validation result."""
    from src.ai_playlist.models.validation import FlowQualityMetrics

    metrics = FlowQualityMetrics(
        bpm_variance=5.0,
        bpm_progression_coherence=0.90,
        energy_consistency=0.85,
        genre_diversity_index=0.75
    )

    return ValidationResult(
        playlist_id=str(uuid.uuid4()),
        overall_status=ValidationStatus.PASS,
        constraint_scores={},
        flow_quality_metrics=metrics,
        compliance_percentage=0.95,
        validated_at=datetime.now(),
        gap_analysis=[]
    )


class TestPlaylistValidation:
    """Test Playlist __post_init__ validation (lines 184-218)."""

    def test_invalid_uuid_raises_error(self, sample_spec, sample_track, passing_validation):
        """Test that invalid UUID raises ValueError (lines 184-187)."""
        # Act & Assert
        with pytest.raises(ValueError, match="ID must be valid UUID4"):
            Playlist(
                id="not-a-uuid",
                name="Monday_MorningDrive_0600_1000",
                tracks=[sample_track],
                spec=sample_spec,
                validation_result=passing_validation
            )

    def test_id_spec_mismatch_raises_error(self, sample_spec, sample_track, passing_validation):
        """Test that ID mismatch with spec raises error (lines 190-191)."""
        # Arrange - different IDs
        playlist_id = str(uuid.uuid4())

        # Act & Assert
        with pytest.raises(ValueError, match="Playlist ID must match PlaylistSpec ID"):
            Playlist(
                id=playlist_id,  # Different from spec.id
                name="Monday_MorningDrive_0600_1000",
                tracks=[sample_track],
                spec=sample_spec,
                validation_result=passing_validation
            )

    def test_empty_tracks_raises_error(self, sample_spec, passing_validation):
        """Test that empty tracks raises error (lines 197-198)."""
        # Act & Assert
        with pytest.raises(ValueError, match="Tracks must be non-empty"):
            Playlist(
                id=sample_spec.id,
                name="Monday_MorningDrive_0600_1000",
                tracks=[],  # Empty
                spec=sample_spec,
                validation_result=passing_validation
            )

    def test_failed_validation_raises_error(self, sample_spec, sample_track):
        """Test that failed validation raises error (lines 201-206)."""
        # Arrange - failing validation
        from src.ai_playlist.models.validation import FlowQualityMetrics

        metrics = FlowQualityMetrics(
            bpm_variance=5.0,
            bpm_progression_coherence=0.90,
            energy_consistency=0.85,
            genre_diversity_index=0.75
        )

        failing_validation = ValidationResult(
            playlist_id=str(uuid.uuid4()),
            overall_status=ValidationStatus.FAIL,
            constraint_scores={},
            flow_quality_metrics=metrics,
            compliance_percentage=0.60,
            validated_at=datetime.now(),
            gap_analysis=[]
        )

        # Act & Assert
        with pytest.raises(ValueError, match="ValidationResult must pass"):
            Playlist(
                id=sample_spec.id,
                name="Monday_MorningDrive_0600_1000",
                tracks=[sample_track],
                spec=sample_spec,
                validation_result=failing_validation
            )

    def test_future_created_at_raises_error(self, sample_spec, sample_track, passing_validation):
        """Test that future created_at raises error (lines 209-210)."""
        # Arrange - future datetime
        future_time = datetime.now() + timedelta(hours=1)

        # Act & Assert
        with pytest.raises(ValueError, match="Created at cannot be in future"):
            Playlist(
                id=sample_spec.id,
                name="Monday_MorningDrive_0600_1000",
                tracks=[sample_track],
                spec=sample_spec,
                validation_result=passing_validation,
                created_at=future_time
            )

    def test_synced_before_created_raises_error(self, sample_spec, sample_track, passing_validation):
        """Test that synced_at < created_at raises error (lines 213-214)."""
        # Arrange
        created = datetime.now()
        synced = created - timedelta(hours=1)  # Before created

        # Act & Assert
        with pytest.raises(ValueError, match="Synced at must be ≥ created at"):
            Playlist(
                id=sample_spec.id,
                name="Monday_MorningDrive_0600_1000",
                tracks=[sample_track],
                spec=sample_spec,
                validation_result=passing_validation,
                created_at=created,
                synced_at=synced
            )

    def test_invalid_azuracast_id_raises_error(self, sample_spec, sample_track, passing_validation):
        """Test that invalid AzuraCast ID raises error (lines 217-218)."""
        # Act & Assert
        with pytest.raises(ValueError, match="AzuraCast ID must be > 0"):
            Playlist(
                id=sample_spec.id,
                name="Monday_MorningDrive_0600_1000",
                tracks=[sample_track],
                spec=sample_spec,
                validation_result=passing_validation,
                azuracast_id=0  # Invalid
            )

    def test_valid_playlist_passes(self, sample_spec, sample_track, passing_validation):
        """Test that valid playlist is created successfully."""
        # Act
        playlist = Playlist(
            id=sample_spec.id,
            name="Monday_MorningDrive_0600_1000",
            tracks=[sample_track],
            spec=sample_spec,
            validation_result=passing_validation
        )

        # Assert
        assert playlist.id == sample_spec.id
        assert len(playlist.tracks) == 1
