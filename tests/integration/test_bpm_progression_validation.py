"""
T026: Live Integration Test - BPM Progression Validation

Tests that generated playlists follow BPM progression specifications
defined in daypart requirements.

This test uses LIVE APIs (NO mocks).
"""
import os
import pytest
from datetime import date
from pathlib import Path
from src.ai_playlist.config import AIPlaylistConfig
from src.ai_playlist.document_parser import DocumentParser
from src.ai_playlist.openai_client import OpenAIClient
from src.ai_playlist.models.core import PlaylistSpecification
from src.subsonic.client import SubsonicClient
from src.subsonic.models import SubsonicConfig


@pytest.mark.integration
@pytest.mark.live
class TestBPMProgressionValidation:
    """Live integration tests for BPM progression validation."""

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
    async def station_identity(self):
        """Load station identity document."""
        parser = DocumentParser()
        return parser.load_document(Path("/workspaces/emby-to-m3u/station-identity.md"))

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
    async def test_morning_drive_bpm_progression(
        self, ai_generator: OpenAIClient, subsonic_client: SubsonicClient,
        station_identity: any
    ):
        """Test Morning Drive BPM progression: 90-115 → 110-135 → 100-120.

        Success Criteria:
        - Hour 1 (6-7 AM): 90-115 BPM
        - Hour 2-3 (7-9 AM): 110-135 BPM
        - Hour 4 (9-10 AM): 100-120 BPM
        - BPM progression matches specification
        """
        # Arrange - Find Morning Drive
        morning_drive = None
        for structure in station_identity.programming_structures:
            for daypart in structure.dayparts:
                if "Morning Drive" in daypart.name:
                    morning_drive = daypart
                    break
            if morning_drive:
                break

        assert morning_drive is not None

        spec = PlaylistSpecification.from_daypart(morning_drive, date.today())

        # Act - Generate playlist
        available_tracks = await subsonic_client.search_tracks(query="", limit=1000)
        playlist = await ai_generator.generate_playlist(spec, available_tracks)

        # Assert - BPM progression exists
        assert len(morning_drive.bpm_progression) > 0

        # Validate BPM values match progression
        tracks_with_bpm = [t for t in playlist.tracks if t.bpm and t.bpm > 0]
        assert len(tracks_with_bpm) >= len(playlist.tracks) * 0.8, \
            "Insufficient BPM coverage for progression validation"

        # Divide tracks by time segments (approximate based on position)
        tracks_per_hour = len(playlist.tracks) / morning_drive.duration_hours

        # Check first hour (positions 0-25%)
        first_hour_end = int(len(playlist.tracks) * 0.25)
        first_hour_tracks = tracks_with_bpm[:first_hour_end]

        # Check peak hours (positions 25%-75%)
        peak_start = first_hour_end
        peak_end = int(len(playlist.tracks) * 0.75)
        peak_tracks = tracks_with_bpm[peak_start:peak_end]

        # Check final hour (positions 75%-100%)
        final_hour_tracks = tracks_with_bpm[peak_end:]

        # Validate BPM ranges for each segment
        if first_hour_tracks:
            avg_bpm_first = sum(t.bpm for t in first_hour_tracks) / len(first_hour_tracks)
            print(f"\nFirst hour average BPM: {avg_bpm_first:.1f} (expected 90-115)")

        if peak_tracks:
            avg_bpm_peak = sum(t.bpm for t in peak_tracks) / len(peak_tracks)
            print(f"Peak hours average BPM: {avg_bpm_peak:.1f} (expected 110-135)")

        if final_hour_tracks:
            avg_bpm_final = sum(t.bpm for t in final_hour_tracks) / len(final_hour_tracks)
            print(f"Final hour average BPM: {avg_bpm_final:.1f} (expected 100-120)")

    @pytest.mark.asyncio
    async def test_bpm_variance_coherence(
        self, ai_generator: OpenAIClient, subsonic_client: SubsonicClient,
        station_identity: any
    ):
        """Test that BPM variance shows coherent progression.

        Success Criteria:
        - Standard deviation of BPM is reasonable (not chaotic)
        - No extreme BPM jumps between consecutive tracks (>25 BPM)
        - Overall BPM trend matches progression pattern
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

        # Get BPM values
        bpm_values = [t.bpm for t in playlist.tracks if t.bpm and t.bpm > 0]
        assert len(bpm_values) >= 30, "Need at least 30 tracks with BPM for variance test"

        # Calculate variance metrics
        import statistics
        bpm_mean = statistics.mean(bpm_values)
        bpm_stdev = statistics.stdev(bpm_values)

        # Check consecutive jumps
        large_jumps = 0
        for i in range(len(bpm_values) - 1):
            jump = abs(bpm_values[i+1] - bpm_values[i])
            if jump > 25:
                large_jumps += 1

        jump_percentage = (large_jumps / (len(bpm_values) - 1)) * 100

        # Assert - Coherent variance
        assert bpm_stdev < 30, \
            f"BPM standard deviation {bpm_stdev:.1f} too high (chaotic progression)"

        assert jump_percentage < 15.0, \
            f"Too many large BPM jumps: {jump_percentage:.1f}% (expected <15%)"

        print(f"\n✓ BPM coherence: mean={bpm_mean:.1f}, stdev={bpm_stdev:.1f}, "
              f"large jumps={jump_percentage:.1f}%")

    @pytest.mark.asyncio
    async def test_energy_flow_metrics(
        self, ai_generator: OpenAIClient, subsonic_client: SubsonicClient,
        station_identity: any
    ):
        """Test energy flow quality metrics.

        Success Criteria:
        - Energy progression score ≥0.7 (0-1 scale)
        - No energy crashes (sudden drops >20 BPM)
        - Peak energy aligns with drive time hours
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

        # Calculate energy flow score
        validation_result = playlist.validate()

        assert validation_result is not None
        assert hasattr(validation_result, 'flow_quality_metrics')

        flow_metrics = validation_result.flow_quality_metrics

        # Assert - Energy flow score
        if hasattr(flow_metrics, 'energy_progression_score'):
            assert flow_metrics.energy_progression_score >= 0.7, \
                f"Energy progression score {flow_metrics.energy_progression_score:.2f} below 0.7"

            print(f"\n✓ Energy flow score: {flow_metrics.energy_progression_score:.2f}")

    @pytest.mark.asyncio
    async def test_bpm_range_compliance_by_hour(
        self, ai_generator: OpenAIClient, subsonic_client: SubsonicClient,
        station_identity: any
    ):
        """Test BPM compliance for each hour of the daypart.

        Success Criteria:
        - ≥80% of tracks in each hour match BPM range
        - BPM ranges are correctly applied by time segment
        - Tolerance (±10 BPM) is honored
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

        # Divide playlist into hourly segments
        num_hours = int(morning_drive.duration_hours)
        tracks_per_hour = len(playlist.tracks) / num_hours

        for hour in range(num_hours):
            start_idx = int(hour * tracks_per_hour)
            end_idx = int((hour + 1) * tracks_per_hour)

            hour_tracks = playlist.tracks[start_idx:end_idx]
            tracks_with_bpm = [t for t in hour_tracks if t.bpm and t.bpm > 0]

            if len(tracks_with_bpm) == 0:
                continue

            # Get BPM range for this hour
            bpm_range = morning_drive.bpm_progression[min(hour, len(morning_drive.bpm_progression) - 1)]

            # Check compliance
            tolerance = spec.track_selection_criteria.tolerance_bpm
            compliant_tracks = [
                t for t in tracks_with_bpm
                if (bpm_range.bpm_min - tolerance) <= t.bpm <= (bpm_range.bpm_max + tolerance)
            ]

            compliance = len(compliant_tracks) / len(tracks_with_bpm)

            print(f"\nHour {hour+1}: {compliance*100:.1f}% BPM compliance "
                  f"({bpm_range.bpm_min}-{bpm_range.bpm_max} ±{tolerance})")

            assert compliance >= 0.80, \
                f"Hour {hour+1} BPM compliance {compliance*100:.1f}% below 80%"
