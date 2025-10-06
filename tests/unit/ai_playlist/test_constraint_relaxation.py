"""
Unit Tests for Constraint Relaxation (T031)

Tests the TrackSelectionCriteria relaxation methods to ensure gradual
constraint loosening while maintaining non-negotiable Australian content.

Test Coverage:
- BPM relaxation with ±10 increments
- Genre relaxation with ±5% tolerance
- Era relaxation with ±5% tolerance
- Australian minimum preservation (30% non-negotiable)
- Maximum 3 iterations constraint
- Edge cases (boundary values, extreme ranges)
"""

import pytest
from src.ai_playlist.models import TrackSelectionCriteria


class TestBPMRelaxation:
    """Test BPM range relaxation with ±10 increments."""

    def test_relax_bpm_default_increment(self):
        """Should expand BPM range by ±10 with default increment."""
        criteria = TrackSelectionCriteria(
            bpm_range=(90, 135),
            genre_mix={"Rock": (0.4, 0.6)},
            era_distribution={"Current": (0.3, 0.5)},
            australian_min=0.30,
            energy_flow="uplifting progression",
        )

        relaxed = criteria.relax_bpm()

        assert relaxed.bpm_range == (80, 145)
        assert relaxed.bpm_tolerance == criteria.bpm_tolerance
        # Verify other constraints preserved
        assert relaxed.genre_mix == criteria.genre_mix
        assert relaxed.era_distribution == criteria.era_distribution
        assert relaxed.australian_min == criteria.australian_min
        assert relaxed.energy_flow == criteria.energy_flow

    def test_relax_bpm_custom_increment(self):
        """Should expand BPM range by custom increment."""
        criteria = TrackSelectionCriteria(
            bpm_range=(100, 140),
            genre_mix={"Pop": (0.5, 0.7)},
            era_distribution={"Recent": (0.4, 0.6)},
            australian_min=0.30,
            energy_flow="steady energy",
        )

        relaxed = criteria.relax_bpm(increment=20)

        assert relaxed.bpm_range == (80, 160)

    def test_relax_bpm_boundary_lower_limit(self):
        """Should clamp BPM minimum at 0, but validation will reject values <= 0."""
        criteria = TrackSelectionCriteria(
            bpm_range=(15, 120),
            genre_mix={"Ambient": (0.6, 0.8)},
            era_distribution={"Classic": (0.2, 0.4)},
            australian_min=0.30,
            energy_flow="calm progression",
        )

        relaxed = criteria.relax_bpm()

        assert relaxed.bpm_range == (5, 130)  # Min reduced by 10

        # Relaxing again would create (0, 140) which violates validation (BPM must be > 0)
        # This is expected - relax_bpm() allows creating invalid criteria that fail validation
        # In practice, the generator would check validation and stop before using invalid criteria
        # We test that attempting to create such criteria raises ValueError as expected
        with pytest.raises(ValueError, match="BPM range values must be > 0"):
            relaxed.relax_bpm()  # Would create (0, 140), which fails validation

    def test_relax_bpm_boundary_upper_limit(self):
        """Should not allow BPM maximum above 300."""
        criteria = TrackSelectionCriteria(
            bpm_range=(280, 295),
            genre_mix={"Electronic": (0.5, 0.7)},
            era_distribution={"Current": (0.6, 0.8)},
            australian_min=0.30,
            energy_flow="high energy",
        )

        relaxed = criteria.relax_bpm()

        assert relaxed.bpm_range == (270, 300)  # Max clamped to 300

    def test_relax_bpm_both_boundaries(self):
        """Should clamp both boundaries if exceeded."""
        criteria = TrackSelectionCriteria(
            bpm_range=(15, 292),
            genre_mix={"Dance": (0.4, 0.6)},
            era_distribution={"Recent": (0.3, 0.5)},
            australian_min=0.30,
            energy_flow="varied energy",
        )

        relaxed = criteria.relax_bpm()

        # (15-10, 292+10) = (5, 300) after clamping
        assert relaxed.bpm_range[1] == 300
        assert relaxed.bpm_range[0] >= 0

    def test_relax_bpm_multiple_iterations(self):
        """Should support multiple relaxation iterations."""
        criteria = TrackSelectionCriteria(
            bpm_range=(90, 130),
            genre_mix={"Rock": (0.5, 0.7)},
            era_distribution={"Classic": (0.3, 0.5)},
            australian_min=0.30,
            energy_flow="gradual build",
        )

        # Iteration 1: (90, 130) -> (80, 140)
        relaxed1 = criteria.relax_bpm()
        assert relaxed1.bpm_range == (80, 140)

        # Iteration 2: (80, 140) -> (70, 150)
        relaxed2 = relaxed1.relax_bpm()
        assert relaxed2.bpm_range == (70, 150)

        # Iteration 3: (70, 150) -> (60, 160)
        relaxed3 = relaxed2.relax_bpm()
        assert relaxed3.bpm_range == (60, 160)

    def test_relax_bpm_preserves_excluded_tracks(self):
        """Should preserve excluded track IDs list."""
        criteria = TrackSelectionCriteria(
            bpm_range=(100, 140),
            genre_mix={"Pop": (0.5, 0.7)},
            era_distribution={"Current": (0.4, 0.6)},
            australian_min=0.30,
            energy_flow="upbeat flow",
            excluded_track_ids=["track1", "track2", "track3"],
        )

        relaxed = criteria.relax_bpm()

        assert relaxed.excluded_track_ids == ["track1", "track2", "track3"]


class TestGenreRelaxation:
    """Test genre tolerance relaxation with ±5% increments."""

    def test_relax_genre_default_tolerance(self):
        """Should increase genre tolerance by 5%."""
        criteria = TrackSelectionCriteria(
            bpm_range=(90, 140),
            genre_mix={
                "Rock": (0.40, 0.60),
                "Pop": (0.20, 0.30),
                "Jazz": (0.10, 0.15),
            },
            genre_tolerance=0.05,
            era_distribution={"Current": (0.3, 0.5)},
            australian_min=0.30,
            energy_flow="balanced mix",
        )

        relaxed = criteria.relax_genre()

        # Genre ranges expanded by ±5% (use approximate comparison for floats)
        assert abs(relaxed.genre_mix["Rock"][0] - 0.35) < 0.01
        assert abs(relaxed.genre_mix["Rock"][1] - 0.65) < 0.01
        assert abs(relaxed.genre_mix["Pop"][0] - 0.15) < 0.01
        assert abs(relaxed.genre_mix["Pop"][1] - 0.35) < 0.01
        assert abs(relaxed.genre_mix["Jazz"][0] - 0.05) < 0.01
        assert abs(relaxed.genre_mix["Jazz"][1] - 0.20) < 0.01
        # Tolerance increased by 5%
        assert abs(relaxed.genre_tolerance - 0.10) < 0.01

    def test_relax_genre_custom_tolerance(self):
        """Should increase genre tolerance by custom amount."""
        criteria = TrackSelectionCriteria(
            bpm_range=(90, 140),
            genre_mix={"Rock": (0.50, 0.70)},
            genre_tolerance=0.05,
            era_distribution={"Recent": (0.4, 0.6)},
            australian_min=0.30,
            energy_flow="rock focus",
        )

        relaxed = criteria.relax_genre(tolerance=0.10)

        assert abs(relaxed.genre_mix["Rock"][0] - 0.40) < 0.01
        assert abs(relaxed.genre_mix["Rock"][1] - 0.80) < 0.01
        assert abs(relaxed.genre_tolerance - 0.15) < 0.01

    def test_relax_genre_boundary_lower_limit(self):
        """Should not allow genre percentages below 0.0."""
        criteria = TrackSelectionCriteria(
            bpm_range=(90, 140),
            genre_mix={"Indie": (0.02, 0.10)},
            genre_tolerance=0.05,
            era_distribution={"Current": (0.3, 0.5)},
            australian_min=0.30,
            energy_flow="indie vibes",
        )

        relaxed = criteria.relax_genre()

        assert relaxed.genre_mix["Indie"][0] == 0.0  # Min clamped to 0.0
        assert abs(relaxed.genre_mix["Indie"][1] - 0.15) < 0.01

    def test_relax_genre_boundary_upper_limit(self):
        """Should not allow genre percentages above 1.0."""
        criteria = TrackSelectionCriteria(
            bpm_range=(90, 140),
            genre_mix={"Electronic": (0.90, 0.98)},
            genre_tolerance=0.05,
            era_distribution={"Current": (0.5, 0.7)},
            australian_min=0.30,
            energy_flow="electronic dominance",
        )

        relaxed = criteria.relax_genre()

        assert relaxed.genre_mix["Electronic"] == (0.85, 1.0)  # Max clamped to 1.0

    def test_relax_genre_tolerance_cap(self):
        """Should not allow genre tolerance above 0.20."""
        criteria = TrackSelectionCriteria(
            bpm_range=(90, 140),
            genre_mix={"Pop": (0.40, 0.60)},
            genre_tolerance=0.18,
            era_distribution={"Recent": (0.3, 0.5)},
            australian_min=0.30,
            energy_flow="pop mix",
        )

        relaxed = criteria.relax_genre()

        assert relaxed.genre_tolerance == 0.20  # Capped at max

    def test_relax_genre_multiple_iterations(self):
        """Should support multiple genre relaxation iterations."""
        criteria = TrackSelectionCriteria(
            bpm_range=(90, 140),
            genre_mix={"Rock": (0.50, 0.60)},
            genre_tolerance=0.05,
            era_distribution={"Classic": (0.3, 0.5)},
            australian_min=0.30,
            energy_flow="classic rock",
        )

        # Iteration 1: Rock (0.50, 0.60) -> (0.45, 0.65)
        relaxed1 = criteria.relax_genre()
        assert abs(relaxed1.genre_mix["Rock"][0] - 0.45) < 0.01
        assert abs(relaxed1.genre_mix["Rock"][1] - 0.65) < 0.01
        assert abs(relaxed1.genre_tolerance - 0.10) < 0.01

        # Iteration 2: Rock (0.45, 0.65) -> (0.40, 0.70)
        relaxed2 = relaxed1.relax_genre()
        assert abs(relaxed2.genre_mix["Rock"][0] - 0.40) < 0.01
        assert abs(relaxed2.genre_mix["Rock"][1] - 0.70) < 0.01
        assert abs(relaxed2.genre_tolerance - 0.15) < 0.01

        # Iteration 3: Rock (0.40, 0.70) -> (0.35, 0.75)
        relaxed3 = relaxed2.relax_genre()
        assert abs(relaxed3.genre_mix["Rock"][0] - 0.35) < 0.01
        assert abs(relaxed3.genre_mix["Rock"][1] - 0.75) < 0.01
        assert abs(relaxed3.genre_tolerance - 0.20) < 0.01  # Capped


class TestEraRelaxation:
    """Test era tolerance relaxation with ±5% increments."""

    def test_relax_era_default_tolerance(self):
        """Should increase era tolerance by 5%."""
        criteria = TrackSelectionCriteria(
            bpm_range=(90, 140),
            genre_mix={"Rock": (0.5, 0.7)},
            era_distribution={
                "Current": (0.30, 0.40),
                "Recent": (0.40, 0.50),
                "Classic": (0.10, 0.20),
            },
            era_tolerance=0.05,
            australian_min=0.30,
            energy_flow="era mix",
        )

        relaxed = criteria.relax_era()

        # Era ranges expanded by ±5% (use approximate comparison)
        assert abs(relaxed.era_distribution["Current"][0] - 0.25) < 0.01
        assert abs(relaxed.era_distribution["Current"][1] - 0.45) < 0.01
        assert abs(relaxed.era_distribution["Recent"][0] - 0.35) < 0.01
        assert abs(relaxed.era_distribution["Recent"][1] - 0.55) < 0.01
        assert abs(relaxed.era_distribution["Classic"][0] - 0.05) < 0.01
        assert abs(relaxed.era_distribution["Classic"][1] - 0.25) < 0.01
        # Tolerance increased by 5%
        assert abs(relaxed.era_tolerance - 0.10) < 0.01

    def test_relax_era_custom_tolerance(self):
        """Should increase era tolerance by custom amount."""
        criteria = TrackSelectionCriteria(
            bpm_range=(90, 140),
            genre_mix={"Pop": (0.5, 0.7)},
            era_distribution={"Current": (0.60, 0.80)},
            era_tolerance=0.05,
            australian_min=0.30,
            energy_flow="current hits",
        )

        relaxed = criteria.relax_era(tolerance=0.10)

        assert abs(relaxed.era_distribution["Current"][0] - 0.50) < 0.01
        assert abs(relaxed.era_distribution["Current"][1] - 0.90) < 0.01
        assert abs(relaxed.era_tolerance - 0.15) < 0.01

    def test_relax_era_boundary_lower_limit(self):
        """Should not allow era percentages below 0.0."""
        criteria = TrackSelectionCriteria(
            bpm_range=(90, 140),
            genre_mix={"Jazz": (0.5, 0.7)},
            era_distribution={"Classic": (0.03, 0.15)},
            era_tolerance=0.05,
            australian_min=0.30,
            energy_flow="classic jazz",
        )

        relaxed = criteria.relax_era()

        assert relaxed.era_distribution["Classic"] == (0.0, 0.20)  # Min clamped to 0.0

    def test_relax_era_boundary_upper_limit(self):
        """Should not allow era percentages above 1.0."""
        criteria = TrackSelectionCriteria(
            bpm_range=(90, 140),
            genre_mix={"Pop": (0.5, 0.7)},
            era_distribution={"Current": (0.92, 0.98)},
            era_tolerance=0.05,
            australian_min=0.30,
            energy_flow="all current",
        )

        relaxed = criteria.relax_era()

        assert relaxed.era_distribution["Current"] == (0.87, 1.0)  # Max clamped to 1.0

    def test_relax_era_tolerance_cap(self):
        """Should not allow era tolerance above 0.20."""
        criteria = TrackSelectionCriteria(
            bpm_range=(90, 140),
            genre_mix={"Rock": (0.5, 0.7)},
            era_distribution={"Recent": (0.40, 0.60)},
            era_tolerance=0.17,
            australian_min=0.30,
            energy_flow="recent rock",
        )

        relaxed = criteria.relax_era()

        assert relaxed.era_tolerance == 0.20  # Capped at max

    def test_relax_era_multiple_iterations(self):
        """Should support multiple era relaxation iterations."""
        criteria = TrackSelectionCriteria(
            bpm_range=(90, 140),
            genre_mix={"Pop": (0.5, 0.7)},
            era_distribution={"Current": (0.50, 0.60)},
            era_tolerance=0.05,
            australian_min=0.30,
            energy_flow="current pop",
        )

        # Iteration 1: Current (0.50, 0.60) -> (0.45, 0.65)
        relaxed1 = criteria.relax_era()
        assert abs(relaxed1.era_distribution["Current"][0] - 0.45) < 0.01
        assert abs(relaxed1.era_distribution["Current"][1] - 0.65) < 0.01
        assert abs(relaxed1.era_tolerance - 0.10) < 0.01

        # Iteration 2: Current (0.45, 0.65) -> (0.40, 0.70)
        relaxed2 = relaxed1.relax_era()
        assert abs(relaxed2.era_distribution["Current"][0] - 0.40) < 0.01
        assert abs(relaxed2.era_distribution["Current"][1] - 0.70) < 0.01
        assert abs(relaxed2.era_tolerance - 0.15) < 0.01

        # Iteration 3: Current (0.40, 0.70) -> (0.35, 0.75)
        relaxed3 = relaxed2.relax_era()
        assert abs(relaxed3.era_distribution["Current"][0] - 0.35) < 0.01
        assert abs(relaxed3.era_distribution["Current"][1] - 0.75) < 0.01
        assert abs(relaxed3.era_tolerance - 0.20) < 0.01  # Capped


class TestAustralianMinimumPreservation:
    """Test that Australian minimum is never relaxed."""

    def test_australian_min_preserved_bpm_relaxation(self):
        """Australian minimum should remain unchanged after BPM relaxation."""
        criteria = TrackSelectionCriteria(
            bpm_range=(90, 140),
            genre_mix={"Rock": (0.5, 0.7)},
            era_distribution={"Current": (0.4, 0.6)},
            australian_min=0.30,
            energy_flow="aussie rock",
        )

        relaxed = criteria.relax_bpm()

        assert relaxed.australian_min == 0.30

    def test_australian_min_preserved_genre_relaxation(self):
        """Australian minimum should remain unchanged after genre relaxation."""
        criteria = TrackSelectionCriteria(
            bpm_range=(90, 140),
            genre_mix={"Pop": (0.5, 0.7)},
            era_distribution={"Recent": (0.4, 0.6)},
            australian_min=0.30,
            energy_flow="aussie pop",
        )

        relaxed = criteria.relax_genre()

        assert relaxed.australian_min == 0.30

    def test_australian_min_preserved_era_relaxation(self):
        """Australian minimum should remain unchanged after era relaxation."""
        criteria = TrackSelectionCriteria(
            bpm_range=(90, 140),
            genre_mix={"Rock": (0.5, 0.7)},
            era_distribution={"Classic": (0.4, 0.6)},
            australian_min=0.30,
            energy_flow="classic aussie",
        )

        relaxed = criteria.relax_era()

        assert relaxed.australian_min == 0.30

    def test_australian_min_preserved_multiple_relaxations(self):
        """Australian minimum should remain unchanged across all relaxation types."""
        criteria = TrackSelectionCriteria(
            bpm_range=(90, 140),
            genre_mix={"Rock": (0.5, 0.7)},
            era_distribution={"Current": (0.4, 0.6)},
            australian_min=0.30,
            energy_flow="diverse mix",
        )

        relaxed = criteria.relax_bpm().relax_genre().relax_era()

        assert relaxed.australian_min == 0.30

    def test_australian_min_custom_value_preserved(self):
        """Custom Australian minimum values should also be preserved."""
        criteria = TrackSelectionCriteria(
            bpm_range=(90, 140),
            genre_mix={"Rock": (0.5, 0.7)},
            era_distribution={"Current": (0.4, 0.6)},
            australian_min=0.40,  # Higher than default
            energy_flow="aussie focus",
        )

        relaxed = criteria.relax_bpm().relax_genre().relax_era()

        assert relaxed.australian_min == 0.40


class TestMaxThreeIterations:
    """Test best-effort fallback after 3 relaxation iterations."""

    def test_three_bpm_iterations_scenario(self):
        """Should allow exactly 3 BPM relaxation iterations."""
        criteria = TrackSelectionCriteria(
            bpm_range=(90, 130),
            genre_mix={"Rock": (0.5, 0.7)},
            era_distribution={"Current": (0.4, 0.6)},
            australian_min=0.30,
            energy_flow="moderate energy",
        )

        # Simulate 3 iterations
        iteration1 = criteria.relax_bpm()  # (80, 140)
        iteration2 = iteration1.relax_bpm()  # (70, 150)
        iteration3 = iteration2.relax_bpm()  # (60, 160)

        assert iteration1.bpm_range == (80, 140)
        assert iteration2.bpm_range == (70, 150)
        assert iteration3.bpm_range == (60, 160)

    def test_three_genre_iterations_scenario(self):
        """Should allow exactly 3 genre relaxation iterations."""
        criteria = TrackSelectionCriteria(
            bpm_range=(90, 140),
            genre_mix={"Rock": (0.50, 0.60)},
            genre_tolerance=0.05,
            era_distribution={"Current": (0.4, 0.6)},
            australian_min=0.30,
            energy_flow="rock focus",
        )

        # Simulate 3 iterations
        iteration1 = criteria.relax_genre()  # (0.45, 0.65), tol=0.10
        iteration2 = iteration1.relax_genre()  # (0.40, 0.70), tol=0.15
        iteration3 = iteration2.relax_genre()  # (0.35, 0.75), tol=0.20

        assert abs(iteration1.genre_mix["Rock"][0] - 0.45) < 0.01
        assert abs(iteration1.genre_mix["Rock"][1] - 0.65) < 0.01
        assert abs(iteration2.genre_mix["Rock"][0] - 0.40) < 0.01
        assert abs(iteration2.genre_mix["Rock"][1] - 0.70) < 0.01
        assert abs(iteration3.genre_mix["Rock"][0] - 0.35) < 0.01
        assert abs(iteration3.genre_mix["Rock"][1] - 0.75) < 0.01

    def test_three_era_iterations_scenario(self):
        """Should allow exactly 3 era relaxation iterations."""
        criteria = TrackSelectionCriteria(
            bpm_range=(90, 140),
            genre_mix={"Pop": (0.5, 0.7)},
            era_distribution={"Current": (0.50, 0.60)},
            era_tolerance=0.05,
            australian_min=0.30,
            energy_flow="current hits",
        )

        # Simulate 3 iterations
        iteration1 = criteria.relax_era()  # (0.45, 0.65), tol=0.10
        iteration2 = iteration1.relax_era()  # (0.40, 0.70), tol=0.15
        iteration3 = iteration2.relax_era()  # (0.35, 0.75), tol=0.20

        assert abs(iteration1.era_distribution["Current"][0] - 0.45) < 0.01
        assert abs(iteration1.era_distribution["Current"][1] - 0.65) < 0.01
        assert abs(iteration2.era_distribution["Current"][0] - 0.40) < 0.01
        assert abs(iteration2.era_distribution["Current"][1] - 0.70) < 0.01
        assert abs(iteration3.era_distribution["Current"][0] - 0.35) < 0.01
        assert abs(iteration3.era_distribution["Current"][1] - 0.75) < 0.01

    def test_mixed_iterations_scenario(self):
        """Should support 3 iterations across different relaxation types."""
        criteria = TrackSelectionCriteria(
            bpm_range=(100, 130),
            genre_mix={"Rock": (0.50, 0.60)},
            era_distribution={"Current": (0.40, 0.50)},
            genre_tolerance=0.05,
            era_tolerance=0.05,
            australian_min=0.30,
            energy_flow="balanced",
        )

        # Iteration 1: Relax BPM
        iteration1 = criteria.relax_bpm()
        assert iteration1.bpm_range == (90, 140)

        # Iteration 2: Relax Genre
        iteration2 = iteration1.relax_genre()
        assert abs(iteration2.genre_mix["Rock"][0] - 0.45) < 0.01
        assert abs(iteration2.genre_mix["Rock"][1] - 0.65) < 0.01

        # Iteration 3: Relax Era
        iteration3 = iteration2.relax_era()
        assert abs(iteration3.era_distribution["Current"][0] - 0.35) < 0.01
        assert abs(iteration3.era_distribution["Current"][1] - 0.55) < 0.01

        # All original non-relaxed constraints preserved
        assert iteration3.australian_min == 0.30
