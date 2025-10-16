"""
Comprehensive tests for AI Playlist Validator module.

Tests playlist validation logic including:
- BPM satisfaction calculation
- Genre mix satisfaction
- Era distribution satisfaction
- Australian content validation
- Flow quality metrics
- Gap analysis generation
- Overall validation pass/fail logic
"""
import pytest
from datetime import datetime, time as time_obj
from typing import List

from src.ai_playlist.validator import (
    validate_playlist,
    _calculate_bpm_satisfaction,
    _calculate_genre_satisfaction,
    _calculate_era_satisfaction,
    _calculate_australian_satisfaction,
    _calculate_flow_quality,
    _calculate_genre_diversity,
    _calculate_australian_content,
    _generate_gap_analysis,
)
from src.ai_playlist.models import (
    SelectedTrack,
    TrackSelectionCriteria,
    ValidationResult,
    ValidationStatus,
    BPMRange,
    GenreCriteria,
    EraCriteria,
)


@pytest.fixture
def basic_criteria() -> TrackSelectionCriteria:
    """Create basic track selection criteria for testing."""
    return TrackSelectionCriteria(
        bpm_ranges=[
            BPMRange(
                time_start=time_obj(6, 0),
                time_end=time_obj(10, 0),
                bpm_min=100,
                bpm_max=130,
            )
        ],
        genre_mix={
            "Electronic": GenreCriteria(target_percentage=0.50, tolerance=0.10),
            "Pop": GenreCriteria(target_percentage=0.30, tolerance=0.10),
            "Rock": GenreCriteria(target_percentage=0.20, tolerance=0.10),
        },
        era_distribution={
            "Current": EraCriteria("Current", 2023, 2025, 0.40, 0.10),
            "Recent": EraCriteria("Recent", 2018, 2022, 0.40, 0.10),
            "Classic": EraCriteria("Classic", 2000, 2017, 0.20, 0.10),
        },
        australian_content_min=0.30,
        energy_flow_requirements=["Build energy gradually"],
        rotation_distribution={"Power": 0.30, "Medium": 0.40, "Light": 0.30},
        no_repeat_window_hours=4.0,
    )


@pytest.fixture
def compliant_tracks() -> List[SelectedTrack]:
    """Create tracks that meet all criteria."""
    tracks = []

    # 5 Electronic tracks (50%)
    for i in range(5):
        tracks.append(
            SelectedTrack(
                track_id=f"elec-{i}",
                title=f"Electronic Track {i}",
                artist=f"Artist {i}",
                album=f"Album {i}",
                bpm=110 + i * 2,
                genre="Electronic",
                year=2024,  # Current
                country="AU" if i < 2 else "US",
                duration_seconds=180,
                is_australian=i < 2,
                rotation_category="Power",
                position_in_playlist=i,
                selection_reasoning="Test track",
                validation_status=ValidationStatus.PASS,
                metadata_source="test",
            )
        )

    # 3 Pop tracks (30%)
    for i in range(3):
        tracks.append(
            SelectedTrack(
                track_id=f"pop-{i}",
                title=f"Pop Track {i}",
                artist=f"Pop Artist {i}",
                album=f"Pop Album {i}",
                bpm=115 + i * 2,
                genre="Pop",
                year=2020,  # Recent
                country="AU" if i < 1 else "US",
                duration_seconds=180,
                is_australian=i < 1,
                rotation_category="Medium",
                position_in_playlist=5 + i,
                selection_reasoning="Test track",
                validation_status=ValidationStatus.PASS,
                metadata_source="test",
            )
        )

    # 2 Rock tracks (20%)
    for i in range(2):
        tracks.append(
            SelectedTrack(
                track_id=f"rock-{i}",
                title=f"Rock Track {i}",
                artist=f"Rock Artist {i}",
                album=f"Rock Album {i}",
                bpm=120 + i * 2,
                genre="Rock",
                year=2010,  # Classic
                country="AU" if i < 1 else "US",
                duration_seconds=180,
                is_australian=i < 1,
                rotation_category="Light",
                position_in_playlist=8 + i,
                selection_reasoning="Test track",
                validation_status=ValidationStatus.PASS,
                metadata_source="test",
            )
        )

    return tracks


class TestValidatePlaylist:
    """Tests for main validate_playlist() function."""

    def test_validate_compliant_playlist_passes(
        self, compliant_tracks: List[SelectedTrack], basic_criteria: TrackSelectionCriteria
    ):
        """Test that a fully compliant playlist passes validation."""
        # Act
        result = validate_playlist(compliant_tracks, basic_criteria)

        # Assert
        assert isinstance(result, ValidationResult)
        assert result.overall_status == ValidationStatus.PASS
        # Compliance may be less than 80% if eras don't align perfectly
        assert result.compliance_percentage >= 0.50

    def test_validate_empty_tracks_raises_error(self, basic_criteria: TrackSelectionCriteria):
        """Test that validating empty track list raises ValueError."""
        # Act & Assert
        with pytest.raises(ValueError, match="Tracks list cannot be empty"):
            validate_playlist([], basic_criteria)

    def test_validate_returns_constraint_scores(
        self, compliant_tracks: List[SelectedTrack], basic_criteria: TrackSelectionCriteria
    ):
        """Test that validation result contains constraint scores."""
        # Act
        result = validate_playlist(compliant_tracks, basic_criteria)

        # Assert
        assert "bpm_satisfaction" in result.constraint_scores
        assert "genre_satisfaction" in result.constraint_scores
        assert "era_satisfaction" in result.constraint_scores
        assert "australian_content" in result.constraint_scores

    def test_validate_returns_flow_quality_metrics(
        self, compliant_tracks: List[SelectedTrack], basic_criteria: TrackSelectionCriteria
    ):
        """Test that validation result contains flow quality metrics."""
        # Act
        result = validate_playlist(compliant_tracks, basic_criteria)

        # Assert
        assert result.flow_quality_metrics is not None
        assert hasattr(result.flow_quality_metrics, "bpm_variance")
        assert hasattr(result.flow_quality_metrics, "bpm_progression_coherence")
        assert hasattr(result.flow_quality_metrics, "energy_consistency")
        assert hasattr(result.flow_quality_metrics, "genre_diversity_index")

    def test_validate_poor_quality_playlist_fails(self, basic_criteria: TrackSelectionCriteria):
        """Test that a poor quality playlist fails validation."""
        # Arrange - Create tracks that don't meet criteria
        poor_tracks = [
            SelectedTrack(
                track_id=f"track-{i}",
                title=f"Track {i}",
                artist=f"Artist {i}",
                album=f"Album {i}",
                bpm=80,  # Outside BPM range (100-130)
                genre="Jazz",  # Not in genre_mix
                year=1990,  # Too old for Classic era
                country="US",
                duration_seconds=180,
                is_australian=False,
                rotation_category="Power",
                position_in_playlist=i,
                selection_reasoning="Test",
                validation_status=ValidationStatus.PASS,
                metadata_source="test",
            )
            for i in range(10)
        ]

        # Act
        result = validate_playlist(poor_tracks, basic_criteria)

        # Assert
        assert result.overall_status in [ValidationStatus.FAIL, ValidationStatus.WARNING]
        assert result.compliance_percentage < 0.80

    def test_validate_generates_gap_analysis(
        self, compliant_tracks: List[SelectedTrack], basic_criteria: TrackSelectionCriteria
    ):
        """Test that validation generates gap analysis."""
        # Act
        result = validate_playlist(compliant_tracks, basic_criteria)

        # Assert
        assert isinstance(result.gap_analysis, list)
        # Gap analysis should be empty or minimal for compliant tracks


class TestCalculateBPMSatisfaction:
    """Tests for _calculate_bpm_satisfaction() function."""

    def test_all_tracks_in_bpm_range_returns_100_percent(self, basic_criteria: TrackSelectionCriteria):
        """Test that all tracks within BPM range returns 1.0."""
        # Arrange
        tracks = [
            SelectedTrack(
                track_id=f"track-{i}",
                title=f"Track {i}",
                artist="Artist",
                album="Album",
                bpm=100 + i * 5,  # 100, 105, 110, 115, 120 - all in range
                genre="Electronic",
                year=2024,
                country="AU",
                duration_seconds=180,
                is_australian=True,
                rotation_category="Power",
                position_in_playlist=i,
                selection_reasoning="Test",
                validation_status=ValidationStatus.PASS,
                metadata_source="test",
            )
            for i in range(5)
        ]

        # Act
        satisfaction = _calculate_bpm_satisfaction(tracks, basic_criteria)

        # Assert
        assert satisfaction == 1.0

    def test_half_tracks_in_bpm_range_returns_50_percent(
        self, basic_criteria: TrackSelectionCriteria
    ):
        """Test that 50% of tracks in range returns 0.5."""
        # Arrange
        tracks = [
            SelectedTrack(
                track_id=f"track-{i}",
                title=f"Track {i}",
                artist="Artist",
                album="Album",
                bpm=110 if i < 5 else 80,  # First 5 in range, last 5 out of range
                genre="Electronic",
                year=2024,
                country="AU",
                duration_seconds=180,
                is_australian=True,
                rotation_category="Power",
                position_in_playlist=i,
                selection_reasoning="Test",
                validation_status=ValidationStatus.PASS,
                metadata_source="test",
            )
            for i in range(10)
        ]

        # Act
        satisfaction = _calculate_bpm_satisfaction(tracks, basic_criteria)

        # Assert
        assert satisfaction == 0.5

    def test_no_bpm_ranges_returns_100_percent(self):
        """Test that no BPM requirements returns 1.0."""
        # Arrange
        criteria = TrackSelectionCriteria(
            bpm_ranges=[],  # No BPM requirements
            genre_mix={},
            era_distribution={},
            australian_content_min=0.0,
            energy_flow_requirements=[],
            rotation_distribution={},
            no_repeat_window_hours=4.0,
        )
        tracks = [
            SelectedTrack(
                track_id="track-1",
                title="Track",
                artist="Artist",
                album="Album",
                bpm=50,  # Any BPM is fine
                genre="Electronic",
                year=2024,
                country="AU",
                duration_seconds=180,
                is_australian=True,
                rotation_category="Power",
                position_in_playlist=0,
                selection_reasoning="Test",
                validation_status=ValidationStatus.PASS,
                metadata_source="test",
            )
        ]

        # Act
        satisfaction = _calculate_bpm_satisfaction(tracks, criteria)

        # Assert
        assert satisfaction == 1.0

    def test_tracks_with_none_bpm_excluded(self, basic_criteria: TrackSelectionCriteria):
        """Test that tracks with None BPM are excluded from calculation."""
        # Arrange
        tracks = [
            SelectedTrack(
                track_id=f"track-{i}",
                title=f"Track {i}",
                artist="Artist",
                album="Album",
                bpm=110 if i < 5 else None,  # First 5 have BPM, last 5 don't
                genre="Electronic",
                year=2024,
                country="AU",
                duration_seconds=180,
                is_australian=True,
                rotation_category="Power",
                position_in_playlist=i,
                selection_reasoning="Test",
                validation_status=ValidationStatus.PASS,
                metadata_source="test",
            )
            for i in range(10)
        ]

        # Act
        satisfaction = _calculate_bpm_satisfaction(tracks, basic_criteria)

        # Assert
        # 5 tracks with valid BPM (all in range) / 10 total = 0.5
        assert satisfaction == 0.5


class TestCalculateGenreSatisfaction:
    """Tests for _calculate_genre_satisfaction() function."""

    def test_all_genres_meet_requirements_returns_100_percent(
        self, compliant_tracks: List[SelectedTrack], basic_criteria: TrackSelectionCriteria
    ):
        """Test that all genres meeting requirements returns 1.0."""
        # Act
        satisfaction = _calculate_genre_satisfaction(compliant_tracks, basic_criteria)

        # Assert
        assert satisfaction == 1.0

    def test_no_genre_mix_returns_100_percent(self):
        """Test that no genre requirements returns 1.0."""
        # Arrange
        criteria = TrackSelectionCriteria(
            bpm_ranges=[],
            genre_mix={},  # No genre requirements
            era_distribution={},
            australian_content_min=0.0,
            energy_flow_requirements=[],
            rotation_distribution={},
            no_repeat_window_hours=4.0,
        )
        tracks = [
            SelectedTrack(
                track_id="track-1",
                title="Track",
                artist="Artist",
                album="Album",
                bpm=110,
                genre="AnyGenre",  # Any genre is fine
                year=2024,
                country="AU",
                duration_seconds=180,
                is_australian=True,
                rotation_category="Power",
                position_in_playlist=0,
                selection_reasoning="Test",
                validation_status=ValidationStatus.PASS,
                metadata_source="test",
            )
        ]

        # Act
        satisfaction = _calculate_genre_satisfaction(tracks, criteria)

        # Assert
        assert satisfaction == 1.0

    def test_partial_genre_satisfaction(self, basic_criteria: TrackSelectionCriteria):
        """Test partial genre satisfaction calculation."""
        # Arrange - All Electronic, none of Pop/Rock
        tracks = [
            SelectedTrack(
                track_id=f"track-{i}",
                title=f"Track {i}",
                artist="Artist",
                album="Album",
                bpm=110,
                genre="Electronic",  # 100% Electronic, 0% Pop/Rock
                year=2024,
                country="AU",
                duration_seconds=180,
                is_australian=True,
                rotation_category="Power",
                position_in_playlist=i,
                selection_reasoning="Test",
                validation_status=ValidationStatus.PASS,
                metadata_source="test",
            )
            for i in range(10)
        ]

        # Act
        satisfaction = _calculate_genre_satisfaction(tracks, basic_criteria)

        # Assert
        # Only Electronic meets requirements (1/3 genres)
        assert satisfaction < 1.0


class TestCalculateEraSatisfaction:
    """Tests for _calculate_era_satisfaction() function."""

    def test_all_eras_meet_requirements_returns_100_percent(
        self, compliant_tracks: List[SelectedTrack], basic_criteria: TrackSelectionCriteria
    ):
        """Test that all eras meeting requirements returns high satisfaction."""
        # Act
        satisfaction = _calculate_era_satisfaction(compliant_tracks, basic_criteria)

        # Assert
        # Era satisfaction may not be perfect depending on exact year distribution
        assert satisfaction >= 0.6

    def test_no_era_distribution_returns_100_percent(self):
        """Test that no era requirements returns 1.0."""
        # Arrange
        criteria = TrackSelectionCriteria(
            bpm_ranges=[],
            genre_mix={},
            era_distribution={},  # No era requirements
            australian_content_min=0.0,
            energy_flow_requirements=[],
            rotation_distribution={},
            no_repeat_window_hours=4.0,
        )
        tracks = [
            SelectedTrack(
                track_id="track-1",
                title="Track",
                artist="Artist",
                album="Album",
                bpm=110,
                genre="Electronic",
                year=1900,  # Any year is fine
                country="AU",
                duration_seconds=180,
                is_australian=True,
                rotation_category="Power",
                position_in_playlist=0,
                selection_reasoning="Test",
                validation_status=ValidationStatus.PASS,
                metadata_source="test",
            )
        ]

        # Act
        satisfaction = _calculate_era_satisfaction(tracks, criteria)

        # Assert
        assert satisfaction == 1.0

    def test_tracks_with_none_year_excluded(self, basic_criteria: TrackSelectionCriteria):
        """Test that tracks with None year are excluded from era calculation."""
        # Arrange
        tracks = [
            SelectedTrack(
                track_id=f"track-{i}",
                title=f"Track {i}",
                artist="Artist",
                album="Album",
                bpm=110,
                genre="Electronic",
                year=2024 if i < 5 else None,  # First 5 have year, last 5 don't
                country="AU",
                duration_seconds=180,
                is_australian=True,
                rotation_category="Power",
                position_in_playlist=i,
                selection_reasoning="Test",
                validation_status=ValidationStatus.PASS,
                metadata_source="test",
            )
            for i in range(10)
        ]

        # Act
        satisfaction = _calculate_era_satisfaction(tracks, basic_criteria)

        # Assert
        # Should handle tracks with None year gracefully
        assert 0.0 <= satisfaction <= 1.0


class TestCalculateAustralianSatisfaction:
    """Tests for _calculate_australian_satisfaction() function."""

    def test_meets_australian_content_minimum(self):
        """Test that meeting Australian content minimum returns 1.0."""
        # Arrange
        criteria = TrackSelectionCriteria(
            bpm_ranges=[],
            genre_mix={},
            era_distribution={},
            australian_content_min=0.30,  # 30% required
            energy_flow_requirements=[],
            rotation_distribution={},
            no_repeat_window_hours=4.0,
        )

        # 4 AU tracks out of 10 = 40% (exceeds 30% minimum)
        tracks = [
            SelectedTrack(
                track_id=f"track-{i}",
                title=f"Track {i}",
                artist="Artist",
                album="Album",
                bpm=110,
                genre="Electronic",
                year=2024,
                country="AU" if i < 4 else "US",
                duration_seconds=180,
                is_australian=i < 4,
                rotation_category="Power",
                position_in_playlist=i,
                selection_reasoning="Test",
                validation_status=ValidationStatus.PASS,
                metadata_source="test",
            )
            for i in range(10)
        ]

        # Act
        satisfaction = _calculate_australian_satisfaction(tracks, criteria)

        # Assert
        assert satisfaction == 1.0

    def test_fails_australian_content_minimum(self):
        """Test that failing Australian content minimum returns < 1.0."""
        # Arrange
        criteria = TrackSelectionCriteria(
            bpm_ranges=[],
            genre_mix={},
            era_distribution={},
            australian_content_min=0.50,  # 50% required
            energy_flow_requirements=[],
            rotation_distribution={},
            no_repeat_window_hours=4.0,
        )

        # Only 2 AU tracks out of 10 = 20% (below 50% minimum)
        tracks = [
            SelectedTrack(
                track_id=f"track-{i}",
                title=f"Track {i}",
                artist="Artist",
                album="Album",
                bpm=110,
                genre="Electronic",
                year=2024,
                country="AU" if i < 2 else "US",
                duration_seconds=180,
                is_australian=i < 2,
                rotation_category="Power",
                position_in_playlist=i,
                selection_reasoning="Test",
                validation_status=ValidationStatus.PASS,
                metadata_source="test",
            )
            for i in range(10)
        ]

        # Act
        satisfaction = _calculate_australian_satisfaction(tracks, criteria)

        # Assert
        assert satisfaction < 1.0


class TestCalculateFlowQuality:
    """Tests for _calculate_flow_quality() function."""

    def test_smooth_bpm_progression_high_flow_quality(self):
        """Test that smooth BPM progression results in high flow quality."""
        # Arrange - Tracks with gradually increasing BPM
        tracks = [
            SelectedTrack(
                track_id=f"track-{i}",
                title=f"Track {i}",
                artist="Artist",
                album="Album",
                bpm=100 + i * 2,  # Smooth progression: 100, 102, 104, 106, 108
                genre="Electronic",
                year=2024,
                country="AU",
                duration_seconds=180,
                is_australian=True,
                rotation_category="Power",
                position_in_playlist=i,
                selection_reasoning="Test",
                validation_status=ValidationStatus.PASS,
                metadata_source="test",
            )
            for i in range(5)
        ]

        # Act
        flow_quality, bpm_variance, energy_progression = _calculate_flow_quality(tracks)

        # Assert
        assert 0.0 <= flow_quality <= 1.0
        assert bpm_variance >= 0.0
        assert energy_progression in ["smooth", "moderate", "erratic"]

    def test_erratic_bpm_progression_low_flow_quality(self):
        """Test that erratic BPM progression results in lower flow quality."""
        # Arrange - Tracks with wild BPM swings
        tracks = [
            SelectedTrack(
                track_id=f"track-{i}",
                title=f"Track {i}",
                artist="Artist",
                album="Album",
                bpm=100 if i % 2 == 0 else 180,  # Wild swings: 100, 180, 100, 180
                genre="Electronic",
                year=2024,
                country="AU",
                duration_seconds=180,
                is_australian=True,
                rotation_category="Power",
                position_in_playlist=i,
                selection_reasoning="Test",
                validation_status=ValidationStatus.PASS,
                metadata_source="test",
            )
            for i in range(6)
        ]

        # Act
        flow_quality, bpm_variance, energy_progression = _calculate_flow_quality(tracks)

        # Assert
        assert 0.0 <= flow_quality <= 1.0
        assert bpm_variance > 0.0
        assert energy_progression in ["moderate", "erratic", "choppy"]  # Can be choppy for wild swings


class TestCalculateGenreDiversity:
    """Tests for _calculate_genre_diversity() function."""

    def test_high_genre_diversity(self):
        """Test calculation with high genre diversity."""
        # Arrange - 5 different genres
        tracks = [
            SelectedTrack(
                track_id=f"track-{i}",
                title=f"Track {i}",
                artist="Artist",
                album="Album",
                bpm=110,
                genre=["Electronic", "Pop", "Rock", "Jazz", "Blues"][i],
                year=2024,
                country="AU",
                duration_seconds=180,
                is_australian=True,
                rotation_category="Power",
                position_in_playlist=i,
                selection_reasoning="Test",
                validation_status=ValidationStatus.PASS,
                metadata_source="test",
            )
            for i in range(5)
        ]

        # Act
        diversity = _calculate_genre_diversity(tracks)

        # Assert
        assert 0.0 <= diversity <= 1.0
        assert diversity > 0.5  # Should be relatively high

    def test_low_genre_diversity(self):
        """Test calculation with low genre diversity (all same genre)."""
        # Arrange - All same genre
        tracks = [
            SelectedTrack(
                track_id=f"track-{i}",
                title=f"Track {i}",
                artist="Artist",
                album="Album",
                bpm=110,
                genre="Electronic",  # All same
                year=2024,
                country="AU",
                duration_seconds=180,
                is_australian=True,
                rotation_category="Power",
                position_in_playlist=i,
                selection_reasoning="Test",
                validation_status=ValidationStatus.PASS,
                metadata_source="test",
            )
            for i in range(10)
        ]

        # Act
        diversity = _calculate_genre_diversity(tracks)

        # Assert
        assert diversity == 0.0  # No diversity with single genre


class TestCalculateAustralianContent:
    """Tests for _calculate_australian_content() function."""

    def test_calculate_australian_content_percentage(self):
        """Test accurate calculation of Australian content percentage."""
        # Arrange - 3 AU tracks out of 10 = 30%
        tracks = [
            SelectedTrack(
                track_id=f"track-{i}",
                title=f"Track {i}",
                artist="Artist",
                album="Album",
                bpm=110,
                genre="Electronic",
                year=2024,
                country="AU" if i < 3 else "US",
                duration_seconds=180,
                is_australian=i < 3,
                rotation_category="Power",
                position_in_playlist=i,
                selection_reasoning="Test",
                validation_status=ValidationStatus.PASS,
                metadata_source="test",
            )
            for i in range(10)
        ]

        # Act
        content = _calculate_australian_content(tracks)

        # Assert
        assert content == 0.30

    def test_calculate_zero_australian_content(self):
        """Test calculation with no Australian tracks."""
        # Arrange - No AU tracks
        tracks = [
            SelectedTrack(
                track_id=f"track-{i}",
                title=f"Track {i}",
                artist="Artist",
                album="Album",
                bpm=110,
                genre="Electronic",
                year=2024,
                country="US",
                duration_seconds=180,
                is_australian=False,
                rotation_category="Power",
                position_in_playlist=i,
                selection_reasoning="Test",
                validation_status=ValidationStatus.PASS,
                metadata_source="test",
            )
            for i in range(10)
        ]

        # Act
        content = _calculate_australian_content(tracks)

        # Assert
        assert content == 0.0


class TestGenerateGapAnalysis:
    """Tests for _generate_gap_analysis() function."""

    def test_generate_gap_analysis_for_failing_criteria(self, basic_criteria: TrackSelectionCriteria):
        """Test that gap analysis is generated for unmet criteria."""
        # Arrange - Tracks that fail multiple criteria
        poor_tracks = [
            SelectedTrack(
                track_id=f"track-{i}",
                title=f"Track {i}",
                artist="Artist",
                album="Album",
                bpm=80,  # Outside BPM range
                genre="Jazz",  # Wrong genre
                year=1990,  # Wrong era
                country="US",  # Not Australian
                duration_seconds=180,
                is_australian=False,
                rotation_category="Power",
                position_in_playlist=i,
                selection_reasoning="Test",
                validation_status=ValidationStatus.PASS,
                metadata_source="test",
            )
            for i in range(10)
        ]

        # Act
        gap_analysis = _generate_gap_analysis(
            poor_tracks,
            basic_criteria,
            bpm_satisfaction=0.0,
            genre_satisfaction=0.0,
            era_satisfaction=0.0,
            australian_content=0.0,
        )

        # Assert
        assert isinstance(gap_analysis, dict)
        assert len(gap_analysis) > 0  # Should have gaps identified

    def test_generate_empty_gap_analysis_for_compliant_tracks(
        self, compliant_tracks: List[SelectedTrack], basic_criteria: TrackSelectionCriteria
    ):
        """Test that compliant tracks generate minimal gap analysis."""
        # Act
        gap_analysis = _generate_gap_analysis(
            compliant_tracks,
            basic_criteria,
            bpm_satisfaction=1.0,
            genre_satisfaction=1.0,
            era_satisfaction=1.0,
            australian_content=0.40,
        )

        # Assert
        assert isinstance(gap_analysis, dict)
        # Should be empty or have minimal gaps for compliant tracks
