"""
T023: Live Integration Test - AI Playlist Generation

Tests generating a single playlist using OpenAI API with actual track data
from Subsonic and validates all constraints are met.

This test uses LIVE APIs (NO mocks).

NOTE: These tests are currently skipped due to missing high-level API implementation.
Required implementation:
1. OpenAIClient.generate_playlist(specification, available_tracks) -> Playlist
2. SubsonicClient async wrapper or search_tracks() method
3. Integration orchestrator that ties together Subsonic + OpenAI + validation
"""
import os
import pytest
from datetime import date
from pathlib import Path
from src.ai_playlist.config import AIPlaylistConfig
from src.ai_playlist.document_parser import DocumentParser
from src.ai_playlist.openai_client import OpenAIClient
from src.ai_playlist.models.core import PlaylistSpecification, Playlist
from src.subsonic.client import SubsonicClient
from src.subsonic.models import SubsonicConfig


# Skip all tests in this class until high-level API is implemented
pytestmark = [
    pytest.mark.integration,
    pytest.mark.live,
    pytest.mark.skip(
        reason="High-level API not implemented. Need: OpenAIClient.generate_playlist(), "
               "SubsonicClient.search_tracks(), and async support. See T070 for details."
    )
]


@pytest.mark.integration
@pytest.mark.live
class TestAIPlaylistGeneration:
    """Live integration tests for AI-powered playlist generation."""

    @pytest.fixture
    def skip_if_no_env(self):
        """Skip test if required environment variables are missing."""
        required = ['SUBSONIC_URL', 'SUBSONIC_USER', 'SUBSONIC_PASSWORD', 'OPENAI_KEY']
        missing = [var for var in required if not os.getenv(var)]

        if missing:
            pytest.skip(
                f"Required environment variables missing: {', '.join(missing)}"
            )

    @pytest.fixture
    async def config(self, skip_if_no_env) -> AIPlaylistConfig:
        """Load configuration from environment variables."""
        return AIPlaylistConfig.from_environment()

    @pytest.fixture
    async def station_identity(self) -> any:
        """Load station identity document."""
        parser = DocumentParser()
        doc = parser.load_document(Path("/workspaces/emby-to-m3u/station-identity.md"))
        return doc

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
    async def test_generate_morning_drive_playlist(
        self, ai_generator: OpenAIClient, subsonic_client: SubsonicClient,
        station_identity: any
    ):
        """Test generating Morning Drive: Production Call playlist.

        Success Criteria:
        - Playlist generated successfully
        - 48-56 tracks (12-14 per hour × 4 hours)
        - Australian content ≥30%
        - Genre/era distributions within ±10%
        """
        # Arrange - Find Morning Drive daypart
        morning_drive = None
        for structure in station_identity.programming_structures:
            for daypart in structure.dayparts:
                if "Morning Drive" in daypart.name or "Production Call" in daypart.name:
                    morning_drive = daypart
                    break
            if morning_drive:
                break

        assert morning_drive is not None, "Morning Drive daypart not found"

        # Create playlist specification
        spec = PlaylistSpecification.from_daypart(
            daypart=morning_drive,
            generation_date=date.today()
        )

        # Act - Generate playlist
        available_tracks = await subsonic_client.search_tracks(query="", limit=1000)

        playlist = await ai_generator.generate_playlist(
            specification=spec,
            available_tracks=available_tracks
        )

        # Assert - Playlist generated
        assert playlist is not None
        assert isinstance(playlist, Playlist)

        # Assert - Track count in range
        track_count = len(playlist.tracks)
        assert 48 <= track_count <= 56, \
            f"Expected 48-56 tracks, got {track_count}"

        # Assert - Australian content ≥30%
        australian_percentage = playlist.calculate_australian_percentage()
        assert australian_percentage >= 0.30, \
            f"Australian content {australian_percentage*100:.1f}% below 30% minimum"

        print(f"\n✓ Playlist generated: {track_count} tracks, {australian_percentage*100:.1f}% Australian")

    @pytest.mark.asyncio
    async def test_validate_ai_selection_reasoning(
        self, ai_generator: OpenAIClient, subsonic_client: SubsonicClient,
        station_identity: any
    ):
        """Test that AI provides reasoning for each track selection.

        Success Criteria:
        - Each track has selection_reasoning field
        - Reasoning is ≥50 characters
        - Reasoning explains why track fits criteria
        """
        # Arrange - Get Morning Drive
        morning_drive = None
        for structure in station_identity.programming_structures:
            for daypart in structure.dayparts:
                if "Morning Drive" in daypart.name:
                    morning_drive = daypart
                    break
            if morning_drive:
                break

        spec = PlaylistSpecification.from_daypart(morning_drive, date.today())

        # Act - Generate playlist (smaller for faster test)
        spec.target_track_count_min = 10
        spec.target_track_count_max = 15

        available_tracks = await subsonic_client.search_tracks(query="", limit=500)
        playlist = await ai_generator.generate_playlist(spec, available_tracks)

        # Assert - All tracks have reasoning
        for track in playlist.tracks:
            assert hasattr(track, 'selection_reasoning')
            assert track.selection_reasoning is not None
            assert len(track.selection_reasoning) >= 50, \
                f"Track '{track.title}' reasoning too short: '{track.selection_reasoning}'"

        print(f"\n✓ All {len(playlist.tracks)} tracks have detailed reasoning")

    @pytest.mark.asyncio
    async def test_validate_genre_distribution(
        self, ai_generator: OpenAIClient, subsonic_client: SubsonicClient,
        station_identity: any
    ):
        """Test that genre distribution matches target ±10%.

        Success Criteria:
        - Genre mix calculated correctly
        - Each genre within ±10% of target
        - All target genres represented
        """
        # Arrange
        morning_drive = None
        for structure in station_identity.programming_structures:
            for daypart in structure.dayparts:
                if "Morning Drive" in daypart.name:
                    morning_drive = daypart
                    break
            if morning_drive:
                break

        spec = PlaylistSpecification.from_daypart(morning_drive, date.today())

        # Act - Generate playlist
        available_tracks = await subsonic_client.search_tracks(query="", limit=1000)
        playlist = await ai_generator.generate_playlist(spec, available_tracks)

        # Calculate actual genre distribution
        actual_distribution = playlist.calculate_genre_distribution()

        # Assert - Genre distribution within tolerances
        for genre, target_criteria in morning_drive.genre_mix.items():
            target = target_criteria.target_percentage
            tolerance = target_criteria.tolerance

            actual = actual_distribution.get(genre, 0.0)

            min_allowed = target - tolerance
            max_allowed = target + tolerance

            assert min_allowed <= actual <= max_allowed, \
                f"Genre '{genre}': actual {actual*100:.1f}% outside range " \
                f"{min_allowed*100:.1f}%-{max_allowed*100:.1f}% (target {target*100:.1f}%)"

        print(f"\n✓ Genre distribution within ±10% tolerance")

    @pytest.mark.asyncio
    async def test_validate_era_distribution(
        self, ai_generator: OpenAIClient, subsonic_client: SubsonicClient,
        station_identity: any
    ):
        """Test that era distribution matches target ±10%.

        Success Criteria:
        - Era mix calculated correctly
        - Each era within ±10% of target
        - All target eras represented
        """
        # Arrange
        morning_drive = None
        for structure in station_identity.programming_structures:
            for daypart in structure.dayparts:
                if "Morning Drive" in daypart.name:
                    morning_drive = daypart
                    break
            if morning_drive:
                break

        spec = PlaylistSpecification.from_daypart(morning_drive, date.today())

        # Act
        available_tracks = await subsonic_client.search_tracks(query="", limit=1000)
        playlist = await ai_generator.generate_playlist(spec, available_tracks)

        # Calculate actual era distribution
        actual_distribution = playlist.calculate_era_distribution()

        # Assert - Era distribution within tolerances
        for era, target_criteria in morning_drive.era_distribution.items():
            target = target_criteria.target_percentage
            tolerance = target_criteria.tolerance

            actual = actual_distribution.get(era, 0.0)

            min_allowed = target - tolerance
            max_allowed = target + tolerance

            assert min_allowed <= actual <= max_allowed, \
                f"Era '{era}': actual {actual*100:.1f}% outside range " \
                f"{min_allowed*100:.1f}%-{max_allowed*100:.1f}% (target {target*100:.1f}%)"

        print(f"\n✓ Era distribution within ±10% tolerance")

    @pytest.mark.asyncio
    async def test_validate_bpm_progression_coherence(
        self, ai_generator: OpenAIClient, subsonic_client: SubsonicClient,
        station_identity: any
    ):
        """Test that BPM progression follows daypart specification.

        Success Criteria:
        - BPM values follow progression pattern
        - No jarring BPM jumps (>20 BPM between consecutive tracks)
        - Energy flow is coherent
        """
        # Arrange
        morning_drive = None
        for structure in station_identity.programming_structures:
            for daypart in structure.dayparts:
                if "Morning Drive" in daypart.name:
                    morning_drive = daypart
                    break
            if morning_drive:
                break

        spec = PlaylistSpecification.from_daypart(morning_drive, date.today())

        # Act
        available_tracks = await subsonic_client.search_tracks(query="", limit=1000)
        playlist = await ai_generator.generate_playlist(spec, available_tracks)

        # Validate BPM progression
        bpm_values = [track.bpm for track in playlist.tracks if track.bpm]

        assert len(bpm_values) > 0, "No tracks have BPM values"

        # Check for smooth transitions
        large_jumps = 0
        for i in range(len(bpm_values) - 1):
            bpm_diff = abs(bpm_values[i+1] - bpm_values[i])
            if bpm_diff > 20:
                large_jumps += 1

        jump_percentage = (large_jumps / (len(bpm_values) - 1)) * 100

        assert jump_percentage < 10.0, \
            f"Too many large BPM jumps: {jump_percentage:.1f}% (expected <10%)"

        print(f"\n✓ BPM progression is coherent ({jump_percentage:.1f}% large jumps)")

    @pytest.mark.asyncio
    async def test_playlist_validation_status(
        self, ai_generator: OpenAIClient, subsonic_client: SubsonicClient,
        station_identity: any
    ):
        """Test that generated playlist passes validation.

        Success Criteria:
        - Playlist validates successfully
        - Validation result is PASS (≥95% compliance)
        - No critical validation errors
        """
        # Arrange
        morning_drive = None
        for structure in station_identity.programming_structures:
            for daypart in structure.dayparts:
                if "Morning Drive" in daypart.name:
                    morning_drive = daypart
                    break
            if morning_drive:
                break

        spec = PlaylistSpecification.from_daypart(morning_drive, date.today())

        # Act
        available_tracks = await subsonic_client.search_tracks(query="", limit=1000)
        playlist = await ai_generator.generate_playlist(spec, available_tracks)

        # Validate playlist
        validation_result = playlist.validate()

        # Assert
        assert validation_result is not None
        assert validation_result.overall_status == "PASS" or validation_result.overall_status == "WARNING"
        assert validation_result.compliance_percentage >= 0.95, \
            f"Compliance {validation_result.compliance_percentage*100:.1f}% below 95%"

        print(f"\n✓ Playlist validation: {validation_result.overall_status} "
              f"({validation_result.compliance_percentage*100:.1f}% compliance)")

    @pytest.mark.asyncio
    async def test_track_metadata_completeness(
        self, ai_generator: OpenAIClient, subsonic_client: SubsonicClient,
        station_identity: any
    ):
        """Test that all selected tracks have complete metadata.

        Success Criteria:
        - All tracks have: title, artist, album, duration, genre, year
        - BPM available for ≥80% of tracks
        - Country information for Australian tracks
        """
        # Arrange
        morning_drive = None
        for structure in station_identity.programming_structures:
            for daypart in structure.dayparts:
                if "Morning Drive" in daypart.name:
                    morning_drive = daypart
                    break
            if morning_drive:
                break

        spec = PlaylistSpecification.from_daypart(morning_drive, date.today())
        spec.target_track_count_min = 20
        spec.target_track_count_max = 25

        # Act
        available_tracks = await subsonic_client.search_tracks(query="", limit=1000)
        playlist = await ai_generator.generate_playlist(spec, available_tracks)

        # Assert - Core metadata present
        for track in playlist.tracks:
            assert track.title and len(track.title) > 0
            assert track.artist and len(track.artist) > 0
            assert track.duration_seconds > 0

        # Assert - BPM coverage
        tracks_with_bpm = [t for t in playlist.tracks if t.bpm and t.bpm > 0]
        bpm_coverage = len(tracks_with_bpm) / len(playlist.tracks)

        assert bpm_coverage >= 0.80, \
            f"BPM coverage {bpm_coverage*100:.1f}% below 80%"

        print(f"\n✓ Track metadata complete (BPM: {bpm_coverage*100:.1f}%)")

    @pytest.mark.asyncio
    async def test_cost_tracking(
        self, ai_generator: OpenAIClient, subsonic_client: SubsonicClient,
        station_identity: any
    ):
        """Test that generation cost is tracked.

        Success Criteria:
        - Cost is calculated and recorded
        - Cost is reasonable (< $0.50 for single playlist)
        - Token usage is logged
        """
        # Arrange
        morning_drive = None
        for structure in station_identity.programming_structures:
            for daypart in structure.dayparts:
                if "Morning Drive" in daypart.name:
                    morning_drive = daypart
                    break
            if morning_drive:
                break

        spec = PlaylistSpecification.from_daypart(morning_drive, date.today())
        spec.target_track_count_min = 15
        spec.target_track_count_max = 20

        # Act
        available_tracks = await subsonic_client.search_tracks(query="", limit=500)
        playlist = await ai_generator.generate_playlist(spec, available_tracks)

        # Assert - Cost tracked
        assert playlist.cost_actual is not None
        assert playlist.cost_actual > 0

        # Assert - Cost is reasonable
        from decimal import Decimal
        assert playlist.cost_actual < Decimal("0.50"), \
            f"Single playlist cost ${playlist.cost_actual} seems high (expected <$0.50)"

        print(f"\n✓ Generation cost: ${playlist.cost_actual:.4f}")
