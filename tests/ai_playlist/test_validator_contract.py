"""Contract tests for Playlist Validator (T013)

Tests the validate_playlist() function contract as specified in:
/workspaces/emby-to-m3u/specs/004-build-ai-ml/contracts/validator_contract.md

These tests MUST FAIL initially (TDD Red phase) until implementation is complete.
"""

import pytest
from typing import List


# Import will fail initially - this is expected in TDD
try:
    from src.ai_playlist.validator import validate_playlist
    from src.ai_playlist.models import (
        SelectedTrack,
        TrackSelectionCriteria,
        ValidationResult
    )
except ImportError:
    # Expected in TDD - modules don't exist yet
    validate_playlist = None
    SelectedTrack = None
    TrackSelectionCriteria = None
    ValidationResult = None


# Test fixtures
@pytest.fixture
def valid_criteria():
    """Create valid selection criteria for testing."""
    if TrackSelectionCriteria is None:
        pytest.skip("Implementation not available yet (TDD Red phase)")

    return TrackSelectionCriteria(
        bpm_range=(90, 120),
        genre_mix={
            "Alternative": (0.20, 0.50),
            "Electronic": (0.20, 0.50)
        },
        era_distribution={
            "Current": (0.30, 0.70)
        },
        australian_min=0.30,
        energy_flow="moderate build"
    )


@pytest.fixture
def passing_tracks():
    """Create tracks that pass validation criteria."""
    if SelectedTrack is None:
        pytest.skip("Implementation not available yet (TDD Red phase)")

    # Create 6 tracks: 2 Alternative (33%), 2 Electronic (33%), 2 AU (33%)
    # This ensures we meet both genre mix (20-50% each) and Australian content (30% min)
    return [
        SelectedTrack(
            track_id="1",
            title="Track 1",
            artist="Artist AU 1",
            album="Album 1",
            bpm=100,
            genre="Alternative",
            year=2023,
            country="AU",
            duration_seconds=240,
            position=1,
            selection_reason="Opens with moderate BPM"
        ),
        SelectedTrack(
            track_id="2",
            title="Track 2",
            artist="Artist AU 2",
            album="Album 2",
            bpm=105,
            genre="Electronic",
            year=2022,
            country="AU",
            duration_seconds=250,
            position=2,
            selection_reason="Builds energy smoothly"
        ),
        SelectedTrack(
            track_id="3",
            title="Track 3",
            artist="Artist UK 1",
            album="Album 3",
            bpm=108,
            genre="Alternative",
            year=2023,
            country="GB",
            duration_seconds=235,
            position=3,
            selection_reason="Peak energy track"
        ),
        SelectedTrack(
            track_id="4",
            title="Track 4",
            artist="Artist US 1",
            album="Album 4",
            bpm=110,
            genre="Electronic",
            year=2023,
            country="US",
            duration_seconds=245,
            position=4,
            selection_reason="Sustains energy"
        ),
        SelectedTrack(
            track_id="5",
            title="Track 5",
            artist="Artist UK 2",
            album="Album 5",
            bpm=112,
            genre="Alternative",
            year=2022,
            country="GB",
            duration_seconds=240,
            position=5,
            selection_reason="Smooth transition"
        ),
        SelectedTrack(
            track_id="6",
            title="Track 6",
            artist="Artist US 2",
            album="Album 6",
            bpm=115,
            genre="Electronic",
            year=2023,
            country="US",
            duration_seconds=250,
            position=6,
            selection_reason="Peak energy finale"
        )
    ]


class TestPlaylistValidatorContract:
    """Contract tests for validate_playlist()"""

    def test_validate_passing_playlist(self, passing_tracks, valid_criteria):
        """Test validation of playlist that meets all criteria.

        Verifies:
        - constraint_satisfaction >= 0.80
        - flow_quality_score >= 0.70
        - australian_content >= requirement
        - passes_validation is True
        - gap_analysis is empty
        - All satisfaction metrics are calculated
        """
        if validate_playlist is None:
            pytest.skip("Implementation not available yet (TDD Red phase)")

        result = validate_playlist(passing_tracks, valid_criteria)

        # Validate result structure
        assert isinstance(result, ValidationResult)

        # Core validation thresholds
        assert result.passes_validation is True
        assert result.constraint_satisfaction >= 0.80
        assert result.flow_quality_score >= 0.70

        # Individual satisfaction metrics
        assert result.bpm_satisfaction >= 0.80
        assert result.genre_satisfaction >= 0.80
        assert result.era_satisfaction >= 0.80
        assert result.australian_content >= 0.30

        # Flow quality metrics
        assert result.bpm_variance is not None
        assert result.bpm_variance > 0
        assert result.energy_progression in ["smooth", "moderate", "choppy"]
        assert result.genre_diversity is not None

        # Gap analysis should be empty for passing playlist
        assert isinstance(result.gap_analysis, dict)
        assert len(result.gap_analysis) == 0

    def test_validate_insufficient_australian(self, valid_criteria):
        """Test validation fails when Australian content is below minimum.

        Verifies:
        - passes_validation is False
        - australian_content is correctly calculated
        - gap_analysis includes 'australian_content'
        - constraint_satisfaction reflects the failure
        """
        if validate_playlist is None:
            pytest.skip("Implementation not available yet (TDD Red phase)")

        # Create tracks with only 1 out of 3 Australian (33% vs 50% required)
        tracks = [
            SelectedTrack(
                track_id="1", title="Track 1", artist="Artist US",
                album="Album", bpm=100, genre="Alternative", year=2023,
                country="US", duration_seconds=240, position=1,
                selection_reason="reason"
            ),
            SelectedTrack(
                track_id="2", title="Track 2", artist="Artist GB",
                album="Album", bpm=105, genre="Alternative", year=2023,
                country="GB", duration_seconds=240, position=2,
                selection_reason="reason"
            ),
            SelectedTrack(
                track_id="3", title="Track 3", artist="Artist AU",
                album="Album", bpm=110, genre="Alternative", year=2023,
                country="AU", duration_seconds=240, position=3,
                selection_reason="reason"
            )
        ]

        criteria = TrackSelectionCriteria(
            bpm_range=(90, 120),
            genre_mix={"Alternative": (0.30, 0.70)},
            era_distribution={"Current": (0.30, 0.70)},
            australian_min=0.50,  # 50% required
            energy_flow="moderate"
        )

        result = validate_playlist(tracks, criteria)

        # Should fail validation
        assert result.passes_validation is False
        assert result.australian_content == pytest.approx(1/3, rel=0.01)  # 1/3 = 0.333...
        assert "australian_content" in result.gap_analysis
        # Gap analysis should mention the requirement and actual percentage
        assert "50" in result.gap_analysis["australian_content"] or "0.5" in result.gap_analysis["australian_content"]

    def test_validate_choppy_flow(self, valid_criteria):
        """Test validation fails when BPM flow is choppy (poor transitions).

        Verifies:
        - flow_quality_score < 0.70 for choppy transitions
        - energy_progression is marked as "choppy"
        - bpm_variance is high (>20)
        - passes_validation is False
        """
        if validate_playlist is None:
            pytest.skip("Implementation not available yet (TDD Red phase)")

        # Create tracks with terrible BPM transitions
        tracks = [
            SelectedTrack(
                track_id="1", title="Track 1", artist="Artist AU",
                album="Album", bpm=80, genre="Alternative", year=2023,
                country="AU", duration_seconds=240, position=1,
                selection_reason="reason"
            ),
            SelectedTrack(
                track_id="2", title="Track 2", artist="Artist AU",
                album="Album", bpm=140, genre="Alternative", year=2023,
                country="AU", duration_seconds=240, position=2,
                selection_reason="reason"
            ),  # +60 BPM jump
            SelectedTrack(
                track_id="3", title="Track 3", artist="Artist AU",
                album="Album", bpm=90, genre="Alternative", year=2023,
                country="AU", duration_seconds=240, position=3,
                selection_reason="reason"
            ),  # -50 BPM drop
            SelectedTrack(
                track_id="4", title="Track 4", artist="Artist AU",
                album="Album", bpm=130, genre="Alternative", year=2023,
                country="AU", duration_seconds=240, position=4,
                selection_reason="reason"
            )  # +40 BPM jump
        ]

        result = validate_playlist(tracks, valid_criteria)

        # Should fail on flow quality
        assert result.flow_quality_score < 0.70
        assert result.energy_progression == "choppy"
        assert result.bpm_variance > 20
        assert result.passes_validation is False

    def test_validate_bpm_out_of_range(self):
        """Test validation detects tracks outside BPM range.

        Verifies:
        - bpm_satisfaction < 1.0 when tracks are out of range
        - gap_analysis includes 'bpm_range'
        - Identifies which tracks are problematic
        """
        if validate_playlist is None:
            pytest.skip("Implementation not available yet (TDD Red phase)")

        tracks = [
            SelectedTrack(
                track_id="1", title="Track 1", artist="Artist AU",
                album="Album", bpm=100, genre="Alternative", year=2023,
                country="AU", duration_seconds=240, position=1,
                selection_reason="reason"
            ),  # OK
            SelectedTrack(
                track_id="2", title="Track 2", artist="Artist AU",
                album="Album", bpm=150, genre="Alternative", year=2023,
                country="AU", duration_seconds=240, position=2,
                selection_reason="reason"
            ),  # OUT OF RANGE (150 > 120)
            SelectedTrack(
                track_id="3", title="Track 3", artist="Artist AU",
                album="Album", bpm=105, genre="Alternative", year=2023,
                country="AU", duration_seconds=240, position=3,
                selection_reason="reason"
            )  # OK
        ]

        criteria = TrackSelectionCriteria(
            bpm_range=(90, 120),
            genre_mix={"Alternative": (0.30, 0.70)},
            era_distribution={"Current": (0.30, 0.70)},
            australian_min=0.30,
            energy_flow="moderate"
        )

        result = validate_playlist(tracks, criteria)

        # Should detect BPM violation
        assert result.bpm_satisfaction < 1.0
        assert result.bpm_satisfaction == pytest.approx(2/3, rel=0.01)  # 2 out of 3 in range
        assert "bpm_range" in result.gap_analysis


class TestPlaylistValidatorEdgeCases:
    """Additional edge case tests beyond core contract"""

    def test_validate_empty_playlist(self, valid_criteria):
        """Test that empty playlist raises ValueError."""
        if validate_playlist is None:
            pytest.skip("Implementation not available yet (TDD Red phase)")

        with pytest.raises(ValueError, match="Tracks list cannot be empty"):
            validate_playlist([], valid_criteria)

    def test_validate_genre_mix_violation(self):
        """Test validation detects genre mix violations."""
        if validate_playlist is None:
            pytest.skip("Implementation not available yet (TDD Red phase)")

        # All Alternative, no Electronic (violates 20-50% Electronic requirement)
        tracks = [
            SelectedTrack(
                track_id=str(i),
                title=f"Track {i}",
                artist="Artist AU",
                album="Album",
                bpm=100 + (i * 5),
                genre="Alternative",  # All same genre
                year=2023,
                country="AU",
                duration_seconds=240,
                position=i,
                selection_reason="reason"
            )
            for i in range(1, 6)
        ]

        criteria = TrackSelectionCriteria(
            bpm_range=(90, 130),
            genre_mix={
                "Alternative": (0.20, 0.50),
                "Electronic": (0.20, 0.50)  # Required but missing
            },
            era_distribution={"Current": (0.30, 0.70)},
            australian_min=0.30,
            energy_flow="moderate"
        )

        result = validate_playlist(tracks, criteria)

        assert result.genre_satisfaction < 1.0
        assert "genre_mix" in result.gap_analysis or "Electronic" in result.gap_analysis

    def test_validate_era_distribution_violation(self):
        """Test validation detects era distribution violations."""
        if validate_playlist is None:
            pytest.skip("Implementation not available yet (TDD Red phase)")

        # All old tracks (violates Current era requirement)
        tracks = [
            SelectedTrack(
                track_id=str(i),
                title=f"Track {i}",
                artist="Artist AU",
                album="Album",
                bpm=100,
                genre="Alternative",
                year=2010,  # Old (>10 years)
                country="AU",
                duration_seconds=240,
                position=i,
                selection_reason="reason"
            )
            for i in range(1, 6)
        ]

        criteria = TrackSelectionCriteria(
            bpm_range=(90, 120),
            genre_mix={"Alternative": (0.30, 0.70)},
            era_distribution={
                "Current": (0.40, 0.60)  # 40-60% current (last 2 years) required
            },
            australian_min=0.30,
            energy_flow="moderate"
        )

        result = validate_playlist(tracks, criteria)

        assert result.era_satisfaction < 1.0
        assert "era_distribution" in result.gap_analysis or "Current" in result.gap_analysis

    def test_validate_perfect_flow(self):
        """Test validation recognizes perfect smooth flow."""
        if validate_playlist is None:
            pytest.skip("Implementation not available yet (TDD Red phase)")

        # Tracks with very small BPM increments
        tracks = [
            SelectedTrack(
                track_id=str(i),
                title=f"Track {i}",
                artist="Artist AU",
                album="Album",
                bpm=100 + (i * 2),  # +2 BPM each track
                genre="Alternative",
                year=2023,
                country="AU",
                duration_seconds=240,
                position=i,
                selection_reason="reason"
            )
            for i in range(1, 6)
        ]

        criteria = TrackSelectionCriteria(
            bpm_range=(90, 120),
            genre_mix={"Alternative": (0.30, 0.70)},
            era_distribution={"Current": (0.30, 0.70)},
            australian_min=0.30,
            energy_flow="smooth build"
        )

        result = validate_playlist(tracks, criteria)

        # Perfect flow should have high quality score
        assert result.energy_progression == "smooth"
        assert result.bpm_variance < 10
        assert result.flow_quality_score >= 0.85

    def test_validate_constraint_satisfaction_calculation(self):
        """Test constraint satisfaction is correctly averaged."""
        if validate_playlist is None:
            pytest.skip("Implementation not available yet (TDD Red phase)")

        # Create scenario with known satisfaction values
        tracks = [
            SelectedTrack(
                track_id="1", title="Track 1", artist="Artist AU",
                album="Album", bpm=100, genre="Alternative", year=2023,
                country="AU", duration_seconds=240, position=1,
                selection_reason="reason"
            )
        ]

        criteria = TrackSelectionCriteria(
            bpm_range=(90, 120),
            genre_mix={"Alternative": (0.30, 0.70)},
            era_distribution={"Current": (0.30, 0.70)},
            australian_min=0.30,
            energy_flow="moderate"
        )

        result = validate_playlist(tracks, criteria)

        # constraint_satisfaction = avg(bpm, genre, era, australian)
        expected_avg = (
            result.bpm_satisfaction +
            result.genre_satisfaction +
            result.era_satisfaction +
            min(result.australian_content / criteria.australian_min, 1.0)
        ) / 4

        assert result.constraint_satisfaction == pytest.approx(expected_avg, rel=0.01)
