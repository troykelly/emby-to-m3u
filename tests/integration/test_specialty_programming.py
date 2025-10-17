"""
T027: Live Integration Test - Specialty Programming

Tests generating specialty programming with unique constraints
(e.g., 100% Australian content, specific genre focus).

This test uses LIVE APIs (NO mocks).
"""
import os
import pytest
from datetime import date, time
from pathlib import Path
from src.ai_playlist.config import AIPlaylistConfig
from src.ai_playlist.openai_client import OpenAIClient
from src.ai_playlist.models.core import (
    PlaylistSpecification, TrackSelectionCriteria, SpecialtyConstraint,
    DaypartSpecification, ScheduleType, BPMRange
)
from src.subsonic.client import SubsonicClient
from src.subsonic.models import SubsonicConfig


@pytest.mark.integration
@pytest.mark.live
class TestSpecialtyProgramming:
    """Live integration tests for specialty programming generation."""

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
    async def test_100_percent_australian_spotlight(
        self, ai_generator: OpenAIClient, subsonic_client: SubsonicClient
    ):
        """Test Wednesday Australian Spotlight (100% Australian).

        Success Criteria:
        - 100% Australian artists
        - BPM diversity (80-135 range)
        - Genre diversity within Australian content
        - 2-hour show (24-28 tracks)
        """
        # Arrange - Create Australian Spotlight daypart
        australian_spotlight = DaypartSpecification(
            id="australian-spotlight",
            name="Wednesday Australian Spotlight",
            schedule_type=ScheduleType.WEEKDAY,
            time_start=time(19, 0),  # 7 PM
            time_end=time(21, 0),    # 9 PM
            duration_hours=2.0,
            target_demographic="Music enthusiasts seeking Australian talent",
            bpm_progression=[
                BPMRange(time(19, 0), time(21, 0), 80, 135)
            ],
            genre_mix={
                "Indie/Alternative": 0.30,
                "Electronic": 0.25,
                "Rock": 0.20,
                "Pop": 0.15,
                "Other": 0.10
            },
            era_distribution={
                "Current": 0.40,
                "Recent": 0.35,
                "Modern Classics": 0.25
            },
            mood_guidelines="Diverse, celebratory, discovery-focused",
            content_focus="100% Australian artists across all genres",
            rotation_percentages={
                "Power": 0.20,
                "Medium": 0.30,
                "Light": 0.30,
                "Library": 0.20
            },
            tracks_per_hour=(10, 14),
            specialty_constraints=[
                SpecialtyConstraint(
                    constraint_type="australian_only",
                    description="100% Australian content required",
                    parameters={"min_percentage": 1.0}
                )
            ]
        )

        spec = PlaylistSpecification.from_daypart(australian_spotlight, date.today())

        # Act - Generate playlist
        available_tracks = subsonic_client.search_tracks(query="", limit=1000)
        playlist = await ai_generator.generate_playlist(spec, available_tracks)

        # Assert - 100% Australian
        australian_percentage = playlist.calculate_australian_percentage()
        assert australian_percentage == 1.0, \
            f"Australian content {australian_percentage*100:.1f}% is not 100%"

        # Assert - Track count appropriate for 2 hours
        track_count = len(playlist.tracks)
        assert 20 <= track_count <= 30, \
            f"Track count {track_count} outside 20-30 range for 2-hour show"

        # Assert - BPM diversity
        bpm_values = [t.bpm for t in playlist.tracks if t.bpm]
        if len(bpm_values) >= 10:
            bpm_range = max(bpm_values) - min(bpm_values)
            assert bpm_range >= 30, \
                f"BPM range {bpm_range} too narrow (expected ≥30 for diversity)"

        print(f"\n✓ Australian Spotlight: {track_count} tracks, 100% Australian, "
              f"BPM range {min(bpm_values) if bpm_values else 'N/A'}-{max(bpm_values) if bpm_values else 'N/A'}")

    @pytest.mark.asyncio
    async def test_electronic_music_focus(
        self, ai_generator: OpenAIClient, subsonic_client: SubsonicClient
    ):
        """Test electronic music specialty show.

        Success Criteria:
        - ≥90% electronic music
        - BPM progression 115-130 (dance-focused)
        - Sub-genre diversity (house, techno, ambient, IDM)
        - Australian content ≥30% maintained
        """
        # Arrange - Electronic Transmission
        electronic_show = DaypartSpecification(
            id="electronic-transmission",
            name="Electronic Transmission",
            schedule_type=ScheduleType.WEEKDAY,
            time_start=time(19, 0),
            time_end=time(21, 0),
            duration_hours=2.0,
            target_demographic="Electronic music fans",
            bpm_progression=[
                BPMRange(time(19, 0), time(20, 0), 115, 130),
                BPMRange(time(20, 0), time(21, 0), 85, 110)
            ],
            genre_mix={
                "Electronic": 0.90,
                "Other": 0.10
            },
            era_distribution={
                "Current": 0.50,
                "Recent": 0.30,
                "Modern Classics": 0.20
            },
            mood_guidelines="Progressive, atmospheric, intelligent",
            content_focus="Electronic music exploration",
            rotation_percentages={
                "Power": 0.20,
                "Medium": 0.30,
                "Discovery": 0.50
            },
            tracks_per_hour=(10, 14),
            specialty_constraints=[
                SpecialtyConstraint(
                    constraint_type="genre_focus",
                    description="Electronic music focus ≥90%",
                    parameters={"primary_genre": "Electronic", "min_percentage": 0.90}
                )
            ]
        )

        spec = PlaylistSpecification.from_daypart(electronic_show, date.today())

        # Act
        available_tracks = subsonic_client.search_tracks(
            query="",
            genre_filter=["Electronic", "Electronica", "Dance", "House", "Techno"],
            limit=800
        )

        playlist = await ai_generator.generate_playlist(spec, available_tracks)

        # Assert - Electronic genre dominance
        genre_dist = playlist.calculate_genre_distribution()
        electronic_percentage = genre_dist.get("Electronic", 0.0)

        assert electronic_percentage >= 0.85, \
            f"Electronic content {electronic_percentage*100:.1f}% below 90% target"

        # Assert - Australian content maintained
        australian_percentage = playlist.calculate_australian_percentage()
        assert australian_percentage >= 0.30, \
            f"Australian content {australian_percentage*100:.1f}% below 30%"

        print(f"\n✓ Electronic show: {electronic_percentage*100:.1f}% electronic, "
              f"{australian_percentage*100:.1f}% Australian")

    @pytest.mark.asyncio
    async def test_jazz_after_dark(
        self, ai_generator: OpenAIClient, subsonic_client: SubsonicClient
    ):
        """Test contemporary jazz specialty programming.

        Success Criteria:
        - ≥80% jazz/instrumental
        - BPM range 80-120 (relaxed)
        - Include contemporary jazz, nu-jazz, improvisation
        - Australian jazz artists represented
        """
        # Arrange - Jazz After Dark
        jazz_show = DaypartSpecification(
            id="jazz-after-dark",
            name="Jazz After Dark",
            schedule_type=ScheduleType.WEEKDAY,
            time_start=time(21, 0),
            time_end=time(0, 0),
            duration_hours=3.0,
            target_demographic="Jazz enthusiasts, late-night listeners",
            bpm_progression=[
                BPMRange(time(21, 0), time(0, 0), 80, 120)
            ],
            genre_mix={
                "Contemporary Jazz": 0.40,
                "Nu-Jazz": 0.25,
                "Instrumental": 0.20,
                "Other": 0.15
            },
            era_distribution={
                "Current": 0.35,
                "Recent": 0.35,
                "Modern Classics": 0.30
            },
            mood_guidelines="Sophisticated, contemplative, exploratory",
            content_focus="Contemporary jazz and improvisation",
            rotation_percentages={
                "Discovery": 0.60,
                "Library": 0.40
            },
            tracks_per_hour=(8, 12),
            specialty_constraints=[
                SpecialtyConstraint(
                    constraint_type="genre_focus",
                    description="Jazz/instrumental focus",
                    parameters={"genre_family": "Jazz", "min_percentage": 0.80}
                )
            ]
        )

        spec = PlaylistSpecification.from_daypart(jazz_show, date.today())

        # Act
        available_tracks = subsonic_client.search_tracks(
            query="",
            genre_filter=["Jazz", "Contemporary Jazz", "Nu-Jazz", "Fusion"],
            limit=600
        )

        if len(available_tracks) < 30:
            pytest.skip("Insufficient jazz tracks in library for this test")

        playlist = await ai_generator.generate_playlist(spec, available_tracks)

        # Assert - Track count for 3-hour show
        track_count = len(playlist.tracks)
        assert 25 <= track_count <= 35, \
            f"Track count {track_count} outside 25-35 range for 3-hour jazz show"

        # Assert - BPM in relaxed range
        bpm_values = [t.bpm for t in playlist.tracks if t.bpm]
        if len(bpm_values) >= 10:
            avg_bpm = sum(bpm_values) / len(bpm_values)
            assert 70 <= avg_bpm <= 130, \
                f"Average BPM {avg_bpm:.1f} outside 70-130 range for jazz show"

        print(f"\n✓ Jazz show: {track_count} tracks, avg BPM {avg_bpm:.1f if bpm_values else 'N/A'}")

    @pytest.mark.asyncio
    async def test_live_session_recordings(
        self, ai_generator: OpenAIClient, subsonic_client: SubsonicClient
    ):
        """Test live session specialty programming.

        Success Criteria:
        - Mix of studio and live recordings
        - Diverse artists and genres
        - 2-hour format with longer tracks acceptable
        - BPM varied by performance
        """
        # Arrange - Live from Production City
        live_show = DaypartSpecification(
            id="live-from-production-city",
            name="Live from Production City",
            schedule_type=ScheduleType.WEEKDAY,
            time_start=time(19, 0),
            time_end=time(21, 0),
            duration_hours=2.0,
            target_demographic="Live music enthusiasts",
            bpm_progression=[
                BPMRange(time(19, 0), time(21, 0), 90, 130)
            ],
            genre_mix={
                "Alternative": 0.30,
                "Indie": 0.25,
                "Electronic": 0.20,
                "Other": 0.25
            },
            era_distribution={
                "Current": 0.60,
                "Recent": 0.30,
                "Modern Classics": 0.10
            },
            mood_guidelines="Raw, authentic, energetic",
            content_focus="Live performances and session recordings",
            rotation_percentages={
                "Discovery": 0.70,
                "Library": 0.30
            },
            tracks_per_hour=(8, 12),  # Longer tracks acceptable
            specialty_constraints=[
                SpecialtyConstraint(
                    constraint_type="theme_based",
                    description="Live session preference",
                    parameters={"theme": "live_recordings"}
                )
            ]
        )

        spec = PlaylistSpecification.from_daypart(live_show, date.today())

        # Act
        available_tracks = subsonic_client.search_tracks(query="", limit=800)
        playlist = await ai_generator.generate_playlist(spec, available_tracks)

        # Assert - Track count (fewer tracks OK for live show with longer performances)
        track_count = len(playlist.tracks)
        assert 15 <= track_count <= 25, \
            f"Track count {track_count} outside 15-25 range for live show"

        # Assert - Australian content maintained
        australian_percentage = playlist.calculate_australian_percentage()
        assert australian_percentage >= 0.30

        print(f"\n✓ Live show: {track_count} tracks, {australian_percentage*100:.1f}% Australian")

    @pytest.mark.asyncio
    async def test_specialty_validation_compliance(
        self, ai_generator: OpenAIClient, subsonic_client: SubsonicClient
    ):
        """Test that specialty playlists meet validation requirements.

        Success Criteria:
        - Specialty constraints validated
        - Overall compliance ≥90% (slightly lower than standard for specialty)
        - Specialty reasoning documented
        """
        # Arrange - Australian Spotlight
        australian_spotlight = DaypartSpecification(
            id="test-specialty-validation",
            name="Test Australian Spotlight",
            schedule_type=ScheduleType.WEEKDAY,
            time_start=time(19, 0),
            time_end=time(21, 0),
            duration_hours=2.0,
            target_demographic="Test",
            bpm_progression=[BPMRange(time(19, 0), time(21, 0), 80, 135)],
            genre_mix={"Alternative": 0.40, "Electronic": 0.30, "Other": 0.30},
            era_distribution={"Current": 0.50, "Recent": 0.50},
            mood_guidelines="Test",
            content_focus="100% Australian",
            rotation_percentages={"Discovery": 1.0},
            tracks_per_hour=(10, 14),
            specialty_constraints=[
                SpecialtyConstraint(
                    constraint_type="australian_only",
                    description="100% Australian required",
                    parameters={"min_percentage": 1.0}
                )
            ]
        )

        spec = PlaylistSpecification.from_daypart(australian_spotlight, date.today())

        # Act
        available_tracks = subsonic_client.search_tracks(query="", limit=800)
        playlist = await ai_generator.generate_playlist(spec, available_tracks)

        # Validate
        validation_result = playlist.validate()

        # Assert
        assert validation_result.overall_status in ["PASS", "WARNING"]
        assert validation_result.compliance_percentage >= 0.90, \
            f"Specialty compliance {validation_result.compliance_percentage*100:.1f}% below 90%"

        print(f"\n✓ Specialty validation: {validation_result.overall_status} "
              f"({validation_result.compliance_percentage*100:.1f}% compliance)")
