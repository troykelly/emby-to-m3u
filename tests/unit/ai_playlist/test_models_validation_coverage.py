"""Coverage tests for models/validation.py missing lines.

Targets:
- Lines 24-31: Fallback ValidationStatus enum
- Lines 188-261: validate_playlist class method
- Lines 287-307: format_summary method
- Lines 331-339: ConstraintScores validation
- Lines 357-368: FlowMetrics validation
"""
import pytest
import uuid
from datetime import datetime, date
from decimal import Decimal

from src.ai_playlist.models import (
    ValidationResult,
    ValidationStatus,
    TrackSelectionCriteria,
    BPMRange,
    GenreCriteria,
    EraCriteria,
    Playlist,
    SelectedTrack,
    PlaylistSpecification
)
from src.ai_playlist.models.validation import (
    ConstraintScore,
    FlowQualityMetrics,
    ConstraintScores,
    FlowMetrics
)
from datetime import time


@pytest.fixture
def sample_criteria():
    """Create sample track selection criteria."""
    bpm_range = BPMRange(
        time_start=time(6, 0),
        time_end=time(10, 0),
        bpm_min=90,
        bpm_max=130
    )

    return TrackSelectionCriteria(
        bpm_ranges=[bpm_range],
        genre_mix={
            "Rock": GenreCriteria(target_percentage=0.5, tolerance=0.10),
            "Pop": GenreCriteria(target_percentage=0.3, tolerance=0.10)
        },
        era_distribution={
            "Current": EraCriteria(
                era_name="Current",
                min_year=2020,
                max_year=2025,
                target_percentage=0.6,
                tolerance=0.10
            )
        },
        australian_content_min=0.30,
        energy_flow_requirements=["Energetic"],
        rotation_distribution={"Power": 0.6, "Medium": 0.4},
        no_repeat_window_hours=24.0
    )


@pytest.fixture
def sample_tracks():
    """Create sample selected tracks."""
    return [
        SelectedTrack(
            track_id=f"track-{i}",
            title=f"Song {i}",
            artist="Australian Artist" if i % 3 == 0 else "International Artist",
            album="Album",
            duration_seconds=180,
            is_australian=i % 3 == 0,
            rotation_category="Power" if i % 2 == 0 else "Medium",
            position_in_playlist=i,
            selection_reasoning="Test",
            validation_status=ValidationStatus.PASS,
            metadata_source="test",
            bpm=100 + (i * 5),
            genre="Rock" if i % 2 == 0 else "Pop",
            year=2023,
            country="AU" if i % 3 == 0 else "US"
        )
        for i in range(10)
    ]


@pytest.fixture
def sample_playlist(sample_tracks, sample_criteria):
    """Create sample playlist."""
    spec_id = str(uuid.uuid4())

    spec = PlaylistSpecification(
        id=spec_id,
        name="Monday_MorningDrive_0600_1000",
        source_daypart_id=str(uuid.uuid4()),
        generation_date=date.today(),
        target_track_count_min=8,
        target_track_count_max=12,
        target_duration_minutes=240,
        track_selection_criteria=sample_criteria,
        created_at=datetime.now()
    )

    return Playlist(
        id=spec_id,
        name="Monday_MorningDrive_0600_1000",
        specification_id=spec_id,
        tracks=sample_tracks,
        validation_result=None,
        created_at=datetime.now(),
        cost_actual=Decimal("0.50"),
        generation_time_seconds=5.0
    )


class TestValidatePlaylistMethod:
    """Test ValidationResult.validate_playlist class method (lines 188-261)."""

    def test_validate_playlist_complete_flow(self, sample_playlist, sample_criteria):
        """Test complete validation flow including all constraint checks."""
        # Act
        result = ValidationResult.validate_playlist(
            playlist=sample_playlist,
            criteria=sample_criteria
        )

        # Assert
        assert isinstance(result, ValidationResult)
        assert result.playlist_id == sample_playlist.id
        assert result.overall_status in [ValidationStatus.PASS, ValidationStatus.WARNING, ValidationStatus.FAIL]
        assert 0.0 <= result.compliance_percentage <= 1.0
        assert result.flow_quality_metrics is not None
        assert isinstance(result.constraint_scores, dict)
        assert 'australian_content' in result.constraint_scores

    def test_validate_playlist_with_low_australian_content(self, sample_playlist, sample_criteria):
        """Test validation detects low Australian content and adds gap analysis."""
        # Arrange - modify tracks to have low Australian content
        for track in sample_playlist.tracks:
            track.is_australian = False
            track.country = "US"

        # Act
        result = ValidationResult.validate_playlist(
            playlist=sample_playlist,
            criteria=sample_criteria
        )

        # Assert - should have gap analysis for Australian content
        assert len(result.gap_analysis) > 0
        assert any("Australian content" in gap for gap in result.gap_analysis)
        assert not result.constraint_scores['australian_content'].is_compliant

    def test_validate_playlist_genre_distribution(self, sample_playlist, sample_criteria):
        """Test validation checks genre distribution."""
        # Act
        result = ValidationResult.validate_playlist(
            playlist=sample_playlist,
            criteria=sample_criteria
        )

        # Assert - should have genre constraint scores
        assert 'genre_Rock' in result.constraint_scores
        assert 'genre_Pop' in result.constraint_scores

    def test_validate_playlist_era_distribution(self, sample_playlist, sample_criteria):
        """Test validation checks era distribution."""
        # Act
        result = ValidationResult.validate_playlist(
            playlist=sample_playlist,
            criteria=sample_criteria
        )

        # Assert - should have era constraint scores
        assert 'era_Current' in result.constraint_scores

    def test_validate_playlist_flow_metrics_calculation(self, sample_playlist, sample_criteria):
        """Test that flow quality metrics are calculated."""
        # Act
        result = ValidationResult.validate_playlist(
            playlist=sample_playlist,
            criteria=sample_criteria
        )

        # Assert
        assert result.flow_quality_metrics.bpm_variance >= 0.0
        assert 0.0 <= result.flow_quality_metrics.genre_diversity_index <= 1.0


class TestGetSummaryMethod:
    """Test ValidationResult.get_summary method (lines 287-307)."""

    def test_get_summary_with_passing_validation(self):
        """Test format_summary for passing validation."""
        # Arrange
        metrics = FlowQualityMetrics(
            bpm_variance=5.0,
            bpm_progression_coherence=0.90,
            energy_consistency=0.85,
            genre_diversity_index=0.75
        )

        result = ValidationResult(
            playlist_id=str(uuid.uuid4()),
            overall_status=ValidationStatus.PASS,
            constraint_scores={},
            flow_quality_metrics=metrics,
            compliance_percentage=0.96,
            validated_at=datetime.now(),
            gap_analysis=[]
        )

        # Act
        summary = result.get_summary()

        # Assert
        assert "✓" in summary
        assert "PASS" in summary
        assert "96.0%" in summary
        assert "No issues found" in summary

    def test_get_summary_with_failing_validation(self):
        """Test get_summary for failing validation with issues."""
        # Arrange
        metrics = FlowQualityMetrics(
            bpm_variance=5.0,
            bpm_progression_coherence=0.90,
            energy_consistency=0.85,
            genre_diversity_index=0.75
        )

        result = ValidationResult(
            playlist_id=str(uuid.uuid4()),
            overall_status=ValidationStatus.FAIL,
            constraint_scores={},
            flow_quality_metrics=metrics,
            compliance_percentage=0.65,
            validated_at=datetime.now(),
            gap_analysis=["Australian content 25.0% below minimum 30.0%"]
        )

        # Act
        summary = result.get_summary()

        # Assert
        assert "✗" in summary
        assert "FAIL" in summary
        assert "65.0%" in summary
        assert "Issues:" in summary
        assert "Australian content" in summary

    def test_get_summary_with_warning(self):
        """Test get_summary for warning status."""
        # Arrange
        metrics = FlowQualityMetrics(
            bpm_variance=5.0,
            bpm_progression_coherence=0.90,
            energy_consistency=0.85,
            genre_diversity_index=0.75
        )

        result = ValidationResult(
            playlist_id=str(uuid.uuid4()),
            overall_status=ValidationStatus.WARNING,
            constraint_scores={},
            flow_quality_metrics=metrics,
            compliance_percentage=0.85,
            validated_at=datetime.now(),
            gap_analysis=["Genre distribution slightly off"]
        )

        # Act
        summary = result.get_summary()

        # Assert
        assert "⚠" in summary
        assert "WARNING" in summary


class TestConstraintScoresValidation:
    """Test ConstraintScores validation (lines 331-339)."""

    def test_valid_constraint_scores(self):
        """Test creating ConstraintScores with valid values."""
        # Act
        scores = ConstraintScores(
            constraint_satisfaction=0.95,
            bpm_satisfaction=0.90,
            genre_satisfaction=0.85,
            era_satisfaction=0.88,
            australian_content=0.92
        )

        # Assert
        assert scores.constraint_satisfaction == 0.95

    def test_constraint_satisfaction_out_of_range_raises_error(self):
        """Test that constraint_satisfaction > 1.0 raises ValueError."""
        # Act & Assert
        with pytest.raises(ValueError, match="constraint_satisfaction must be 0.0-1.0"):
            ConstraintScores(
                constraint_satisfaction=1.5,
                bpm_satisfaction=0.90,
                genre_satisfaction=0.85,
                era_satisfaction=0.88,
                australian_content=0.92
            )

    def test_negative_bpm_satisfaction_raises_error(self):
        """Test that negative bpm_satisfaction raises ValueError."""
        # Act & Assert
        with pytest.raises(ValueError, match="bpm_satisfaction must be 0.0-1.0"):
            ConstraintScores(
                constraint_satisfaction=0.95,
                bpm_satisfaction=-0.1,
                genre_satisfaction=0.85,
                era_satisfaction=0.88,
                australian_content=0.92
            )


class TestFlowMetricsValidation:
    """Test FlowMetrics validation (lines 357-368)."""

    def test_valid_flow_metrics(self):
        """Test creating FlowMetrics with valid values."""
        # Act
        metrics = FlowMetrics(
            flow_quality_score=0.85,
            bpm_variance=10.5,
            energy_progression="smooth",
            genre_diversity=0.75
        )

        # Assert
        assert metrics.flow_quality_score == 0.85

    def test_flow_quality_score_out_of_range_raises_error(self):
        """Test that flow_quality_score > 1.0 raises ValueError (line 358)."""
        # Act & Assert
        with pytest.raises(ValueError, match="flow_quality_score must be 0.0-1.0"):
            FlowMetrics(
                flow_quality_score=1.2,
                bpm_variance=10.5,
                energy_progression="smooth",
                genre_diversity=0.75
            )

    def test_negative_bpm_variance_raises_error(self):
        """Test that negative bpm_variance raises ValueError (line 361)."""
        # Act & Assert
        with pytest.raises(ValueError, match="BPM variance must be ≥ 0"):
            FlowMetrics(
                flow_quality_score=0.85,
                bpm_variance=-5.0,
                energy_progression="smooth",
                genre_diversity=0.75
            )

    def test_invalid_energy_progression_raises_error(self):
        """Test that invalid energy_progression raises ValueError (lines 364-365)."""
        # Act & Assert
        with pytest.raises(ValueError, match="Energy progression must be one of"):
            FlowMetrics(
                flow_quality_score=0.85,
                bpm_variance=10.5,
                energy_progression="invalid",
                genre_diversity=0.75
            )

    def test_genre_diversity_out_of_range_raises_error(self):
        """Test that genre_diversity > 1.0 raises ValueError (line 368)."""
        # Act & Assert
        with pytest.raises(ValueError, match="genre_diversity must be 0.0-1.0"):
            FlowMetrics(
                flow_quality_score=0.85,
                bpm_variance=10.5,
                energy_progression="smooth",
                genre_diversity=1.5
            )
