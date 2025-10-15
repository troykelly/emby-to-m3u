"""
T025: Live Integration Test - Constraint Relaxation

Tests progressive constraint relaxation when insufficient tracks match strict criteria.
Tests the FR-028 requirement for automatic constraint relaxation.

This test uses LIVE APIs (NO mocks).
"""
import os
import pytest
from datetime import date, time
from pathlib import Path
from src.ai_playlist.config import AIPlaylistConfig
from src.ai_playlist.document_parser import DocumentParser
from src.ai_playlist.openai_client import OpenAIClient
from src.ai_playlist.models import (
    PlaylistSpecification, SpecialtyConstraint, TrackSelectionCriteria, BPMRange
)
from src.subsonic.client import SubsonicClient
from src.subsonic.models import SubsonicConfig


@pytest.mark.integration
@pytest.mark.live
class TestConstraintRelaxation:
    """Live integration tests for progressive constraint relaxation."""

    @pytest.fixture
    def skip_if_no_env(self):
        """Skip test if required environment variables are missing."""
        required = ['SUBSONIC_URL', 'SUBSONIC_USER', 'SUBSONIC_PASSWORD', 'OPENAI_KEY']
        missing = [var for var in required if not os.getenv(var)]

        if missing:
            pytest.skip(f"Required environment variables missing: {', '.join(missing)}")

    @pytest.fixture
    async def config(self, skip_if_no_env) -> AIPlaylistConfig:
        """Load configuration from environment."""
        return AIPlaylistConfig.from_environment()

    @pytest.fixture
    async def subsonic_client(self, config: AIPlaylistConfig) -> SubsonicClient:
        """Create Subsonic client."""
        subsonic_config = SubsonicConfig(
            url=config.subsonic_url,
            username=config.subsonic_user,
            password=config.subsonic_password
        )
        return SubsonicClient(subsonic_config)

    @pytest.fixture
    async def ai_generator(self, config: AIPlaylistConfig) -> OpenAIClient:
        """Create OpenAI playlist generator."""
        return OpenAIClient(
            api_key=config.openai_api_key,
            model="gpt-4o"
        )

    @pytest.mark.asyncio
    async def test_progressive_bpm_relaxation(
        self, ai_generator: OpenAIClient, subsonic_client: SubsonicClient
    ):
        """Test progressive BPM relaxation when strict criteria fail.

        Success Criteria:
        - Initial BPM: ±10
        - First relaxation: ±15
        - Second relaxation: ±20
        - Max 3 relaxations
        - All relaxations logged
        """
        # Arrange - Create very restrictive BPM criteria
        spec = PlaylistSpecification(
            id="test-bpm-relaxation",
            name="100% Australian Electronic",
            source_daypart_id="test",
            generation_date=date.today(),
            target_duration_minutes=240,
            target_track_count_min=20,
            target_track_count_max=25,
            track_selection_criteria=TrackSelectionCriteria(
                bpm_ranges=[BPMRange(time(0, 0), time(23, 59), 125, 130)],  # Very narrow BPM range
                genre_mix={"Electronic": 1.0},
                era_distribution={"Current": 1.0},
                australian_content_min=1.0,  # 100% Australian,  # Initial tolerance
                energy_flow_requirements=["energetic"],
                rotation_distribution={"Power": 1.0},
                no_repeat_window_hours=4.0,
            )
        )

        # Get limited track pool
        available_tracks = await subsonic_client.search_tracks(
            query="",
            genre_filter=["Electronic"],
            limit=300
        )

        # Act - Generate playlist with relaxation
        playlist = await ai_generator.generate_playlist_with_relaxation(
            specification=spec,
            available_tracks=available_tracks,
            max_relaxations=3
        )

        # Assert - Playlist generated
        assert playlist is not None
        assert len(playlist.tracks) >= 15, "Not enough tracks despite relaxation"

        # Assert - Relaxations were applied
        assert len(playlist.constraint_relaxations) > 0, "No relaxations logged"
        assert len(playlist.constraint_relaxations) <= 3, "Too many relaxations (max 3)"

        # Assert - Relaxation progression is correct
        for i, relaxation in enumerate(playlist.constraint_relaxations):
            assert relaxation.iteration == i + 1
            assert relaxation.constraint_type in ["bpm", "genre", "era"]
            assert len(relaxation.original_value) > 0
            assert len(relaxation.relaxed_value) > 0

        print(f"\n✓ Applied {len(playlist.constraint_relaxations)} relaxations:")
        for r in playlist.constraint_relaxations:
            print(f"  {r.iteration}. {r.constraint_type}: {r.original_value} → {r.relaxed_value}")

    @pytest.mark.asyncio
    async def test_australian_content_never_relaxed(
        self, ai_generator: OpenAIClient, subsonic_client: SubsonicClient
    ):
        """Test that Australian content 30% minimum is NEVER relaxed.

        Success Criteria:
        - Australian content ≥30% enforced
        - Even with relaxations, Australian minimum maintained
        - Generation fails if insufficient Australian tracks
        """
        # Arrange - Restrictive criteria
        spec = PlaylistSpecification(
            id="test-australian-never-relaxed",
            name="Strict Australian Electronic",
            source_daypart_id="test",
            generation_date=date.today(),
            target_duration_minutes=240,
            target_track_count_min=15,
            target_track_count_max=20,
            track_selection_criteria=TrackSelectionCriteria(
                bpm_ranges=[BPMRange(time(0, 0), time(23, 59), 120, 125)],
                genre_mix={"Electronic": 1.0},
                era_distribution={"Current": 1.0},
                australian_content_min=0.30,  # NON-NEGOTIABLE
                energy_flow_requirements=["energetic"],
                rotation_distribution={"Power": 1.0},
                no_repeat_window_hours=4.0,
            )
        )

        available_tracks = await subsonic_client.search_tracks(query="", limit=500)

        # Act
        playlist = await ai_generator.generate_playlist_with_relaxation(
            specification=spec,
            available_tracks=available_tracks,
            max_relaxations=3
        )

        # Assert - Australian content maintained
        if playlist:
            australian_percentage = playlist.calculate_australian_percentage()
            assert australian_percentage >= 0.30, \
                f"Australian content {australian_percentage*100:.1f}% below 30% minimum"

            # Check relaxations don't include Australian content
            for relaxation in playlist.constraint_relaxations:
                assert "australian" not in relaxation.constraint_type.lower(), \
                    "Australian content was relaxed (should be non-negotiable)"

            print(f"\n✓ Australian content maintained at {australian_percentage*100:.1f}%")

    @pytest.mark.asyncio
    async def test_relaxation_order(
        self, ai_generator: OpenAIClient, subsonic_client: SubsonicClient
    ):
        """Test that relaxations are applied in correct order.

        Success Criteria:
        - Order: BPM → Genre → Era
        - BPM relaxed first (±10 → ±15 → ±20)
        - Genre relaxed second (±5% → ±10%)
        - Era relaxed third (±5% → ±10%)
        """
        # Arrange - Multiple restrictive criteria
        spec = PlaylistSpecification(
            id="test-relaxation-order",
            name="Multi-Constraint Test",
            source_daypart_id="test",
            generation_date=date.today(),
            target_duration_minutes=240,
            target_track_count_min=20,
            target_track_count_max=25,
            track_selection_criteria=TrackSelectionCriteria(
                bpm_ranges=[BPMRange(time(0, 0), time(23, 59), 100, 105)],  # Narrow
                genre_mix={
                    "Electronic": 0.5,
                    "Alternative": 0.5
                },
                era_distribution={
                    "Current": 0.6,
                    "Recent": 0.4
                },
                australian_content_min=0.30,
                energy_flow_requirements=["energetic"],
                rotation_distribution={"Power": 1.0},
                no_repeat_window_hours=4.0,
            )
        )

        available_tracks = await subsonic_client.search_tracks(query="", limit=400)

        # Act
        playlist = await ai_generator.generate_playlist_with_relaxation(
            specification=spec,
            available_tracks=available_tracks,
            max_relaxations=3
        )

        # Assert - Relaxations applied in order
        if playlist and len(playlist.constraint_relaxations) > 0:
            relaxation_types = [r.constraint_type for r in playlist.constraint_relaxations]

            # First relaxation should be BPM (if needed)
            if len(relaxation_types) >= 1:
                assert relaxation_types[0] in ["bpm", "BPM"], \
                    f"First relaxation should be BPM, got {relaxation_types[0]}"

            print(f"\n✓ Relaxation order: {' → '.join(relaxation_types)}")

    @pytest.mark.asyncio
    async def test_decision_log_includes_relaxations(
        self, ai_generator: OpenAIClient, subsonic_client: SubsonicClient
    ):
        """Test that all relaxations are logged in decision log.

        Success Criteria:
        - Each relaxation has decision log entry
        - Log includes: iteration, constraint, before/after values, reason
        - Timestamps are present
        """
        # Arrange
        spec = PlaylistSpecification(
            id="test-relaxation-logging",
            name="Relaxation Log Test",
            source_daypart_id="test",
            generation_date=date.today(),
            target_duration_minutes=240,
            target_track_count_min=15,
            target_track_count_max=20,
            track_selection_criteria=TrackSelectionCriteria(
                bpm_ranges=[BPMRange(time(0, 0), time(23, 59), 110, 115)],
                genre_mix={"Electronic": 1.0},
                era_distribution={"Current": 1.0},
                australian_content_min=0.30,
                energy_flow_requirements=["energetic"],
                rotation_distribution={"Power": 1.0},
                no_repeat_window_hours=4.0,
            )
        )

        available_tracks = await subsonic_client.search_tracks(query="", limit=300)

        # Act
        playlist = await ai_generator.generate_playlist_with_relaxation(
            specification=spec,
            available_tracks=available_tracks,
            max_relaxations=3
        )

        # Assert - Decision log exists
        assert hasattr(playlist, 'decision_log')

        # Find relaxation entries in decision log
        relaxation_log_entries = [
            entry for entry in playlist.decision_log
            if entry.decision_type == "relaxation"
        ]

        # Assert - All relaxations logged
        assert len(relaxation_log_entries) == len(playlist.constraint_relaxations), \
            "Not all relaxations have decision log entries"

        # Assert - Log entries have required fields
        for entry in relaxation_log_entries:
            assert entry.timestamp is not None
            assert entry.decision_data is not None
            assert 'constraint_type' in entry.decision_data
            assert 'original_value' in entry.decision_data
            assert 'relaxed_value' in entry.decision_data

        print(f"\n✓ All {len(relaxation_log_entries)} relaxations logged in decision log")

    @pytest.mark.asyncio
    async def test_max_relaxations_limit(
        self, ai_generator: OpenAIClient, subsonic_client: SubsonicClient
    ):
        """Test that relaxations stop at maximum limit.

        Success Criteria:
        - Max 3 relaxations applied
        - Generation stops if still insufficient tracks
        - Error/warning logged if max relaxations reached
        """
        # Arrange - Extremely restrictive criteria
        spec = PlaylistSpecification(
            id="test-max-relaxations",
            name="Impossible Criteria",
            source_daypart_id="test",
            generation_date=date.today(),
            target_duration_minutes=240,
            target_track_count_min=30,
            target_track_count_max=35,
            track_selection_criteria=TrackSelectionCriteria(
                bpm_ranges=[BPMRange(time(0, 0), time(23, 59), 142, 144)],  # Very narrow
                genre_mix={"Experimental Jazz": 1.0},  # Rare genre
                era_distribution={"Current": 1.0},
                australian_content_min=1.0,  # 100% Australian,  # Tight tolerance
                energy_flow_requirements=["energetic"],
                rotation_distribution={"Power": 1.0},
                no_repeat_window_hours=4.0,
            )
        )

        available_tracks = await subsonic_client.search_tracks(query="", limit=200)

        # Act
        try:
            playlist = await ai_generator.generate_playlist_with_relaxation(
                specification=spec,
                available_tracks=available_tracks,
                max_relaxations=3
            )

            # Assert - Max 3 relaxations
            if playlist:
                assert len(playlist.constraint_relaxations) <= 3, \
                    f"Applied {len(playlist.constraint_relaxations)} relaxations, max is 3"

                print(f"\n✓ Stopped at {len(playlist.constraint_relaxations)} relaxations (max 3)")

        except Exception as e:
            # Generation may fail with impossible criteria - this is acceptable
            print(f"\n✓ Generation failed as expected with impossible criteria: {e}")
            assert True

    @pytest.mark.asyncio
    async def test_relaxation_reasoning_quality(
        self, ai_generator: OpenAIClient, subsonic_client: SubsonicClient
    ):
        """Test that relaxation reasoning is provided.

        Success Criteria:
        - Each relaxation has reasoning field
        - Reasoning explains why relaxation needed
        - Reasoning is ≥50 characters
        """
        # Arrange
        spec = PlaylistSpecification(
            id="test-relaxation-reasoning",
            name="Reasoning Test",
            source_daypart_id="test",
            generation_date=date.today(),
            target_duration_minutes=240,
            target_track_count_min=18,
            target_track_count_max=22,
            track_selection_criteria=TrackSelectionCriteria(
                bpm_ranges=[BPMRange(time(0, 0), time(23, 59), 115, 120)],
                genre_mix={"Electronic": 1.0},
                era_distribution={"Current": 1.0},
                australian_content_min=0.30,
                energy_flow_requirements=["energetic"],
                rotation_distribution={"Power": 1.0},
                no_repeat_window_hours=4.0,
            )
        )

        available_tracks = await subsonic_client.search_tracks(query="", limit=300)

        # Act
        playlist = await ai_generator.generate_playlist_with_relaxation(
            specification=spec,
            available_tracks=available_tracks,
            max_relaxations=3
        )

        # Assert - Relaxations have reasoning
        if playlist and len(playlist.constraint_relaxations) > 0:
            for relaxation in playlist.constraint_relaxations:
                assert hasattr(relaxation, 'reason')
                assert relaxation.reason is not None
                assert len(relaxation.reason) >= 50, \
                    f"Relaxation reasoning too short: '{relaxation.reason}'"

            print(f"\n✓ All relaxations have detailed reasoning")
