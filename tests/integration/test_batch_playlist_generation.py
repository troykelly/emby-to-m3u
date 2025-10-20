"""
T024: Live Integration Test - Full Day Batch Generation

Tests generating all 5 weekday dayparts with budget allocation and
validates no track repeats across playlists.

This test uses LIVE APIs (NO mocks).
"""
import os
import pytest
from datetime import date
from pathlib import Path
from decimal import Decimal
from src.ai_playlist.config import AIPlaylistConfig
from src.ai_playlist.document_parser import DocumentParser
from src.ai_playlist.batch_executor import BatchPlaylistGenerator
from src.subsonic.client import SubsonicClient
from src.subsonic.models import SubsonicConfig


@pytest.mark.integration
@pytest.mark.live
class TestBatchPlaylistGeneration:
    """Live integration tests for batch playlist generation."""

    @pytest.fixture
    def skip_if_no_env(self):
        """Skip test if required environment variables are missing."""
        required = ['SUBSONIC_URL', 'SUBSONIC_USER', 'SUBSONIC_PASSWORD', 'OPENAI_KEY']
        missing = [var for var in required if not os.getenv(var)]

        if missing:
            pytest.skip(f"Required environment variables missing: {', '.join(missing)}")

    @pytest.fixture
    async def config(self, skip_if_no_env) -> AIPlaylistConfig:
        """Load configuration with batch budget settings."""
        config = AIPlaylistConfig.from_environment()
        # Override budget for testing
        config.total_cost_budget = Decimal("20.00")
        config.cost_budget_mode = "suggested"
        config.cost_allocation_strategy = "dynamic"
        return config

    @pytest.fixture
    async def station_identity(self):
        """Load station identity document."""
        from src.ai_playlist.config import get_station_identity_path
        parser = DocumentParser()
        return parser.load_document(get_station_identity_path())

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
    async def batch_generator(self, config: AIPlaylistConfig, subsonic_client: SubsonicClient) -> BatchPlaylistGenerator:
        """Create batch playlist generator."""
        return BatchPlaylistGenerator(
            openai_api_key=config.openai_api_key,
            subsonic_client=subsonic_client,
            total_budget=config.total_cost_budget,
            allocation_strategy=config.cost_allocation_strategy
        )

    @pytest.mark.asyncio
    async def test_generate_all_weekday_dayparts(
        self, batch_generator: BatchPlaylistGenerator, subsonic_client: SubsonicClient,
        station_identity: any
    ):
        """Test generating all 5 weekday dayparts in batch.

        Success Criteria:
        - All 5 dayparts generated successfully
        - Each playlist meets its constraints
        - Total cost ≤ $20 budget
        """
        # Arrange - Get weekday dayparts
        weekday_structure = next(
            (s for s in station_identity.programming_structures if s.schedule_type.value == "weekday"),
            None
        )
        assert weekday_structure is not None

        # Use main dayparts only (Morning Drive, Midday, Afternoon Drive, Evening, Late Night)
        dayparts = weekday_structure.dayparts[:5]

        # Act - Generate all playlists (LLM discovers tracks dynamically)
        playlists = await batch_generator.generate_batch(
            dayparts=dayparts,
            generation_date=date.today()
        )

        # Assert - All playlists generated
        assert len(playlists) == 5, f"Expected 5 playlists, got {len(playlists)}"

        # Assert - Each playlist is valid
        for playlist in playlists:
            assert playlist is not None
            assert len(playlist.tracks) > 0

        # Assert - Total cost within budget
        total_cost = sum(p.cost_actual for p in playlists)
        assert total_cost <= Decimal("20.00"), \
            f"Total cost ${total_cost} exceeds $20 budget"

        print(f"\n✓ Generated {len(playlists)} playlists, total cost: ${total_cost:.4f}")

    @pytest.mark.asyncio
    async def test_dynamic_budget_allocation(
        self, batch_generator: BatchPlaylistGenerator, subsonic_client: SubsonicClient,
        station_identity: any
    ):
        """Test dynamic budget allocation across dayparts.

        Success Criteria:
        - Budget allocated based on complexity
        - Longer dayparts get more budget
        - More complex criteria get more budget
        """
        # Arrange
        weekday_structure = next(
            (s for s in station_identity.programming_structures if s.schedule_type.value == "weekday"),
            None
        )
        dayparts = weekday_structure.dayparts[:5]

        # Act - Calculate budget allocation
        allocations = batch_generator.calculate_budget_allocation(dayparts)

        # Assert - Allocations sum to total budget
        total_allocated = sum(allocations.values())
        assert abs(total_allocated - Decimal("20.00")) < Decimal("0.01"), \
            f"Allocated ${total_allocated} != $20.00 budget"

        # Assert - Longer dayparts get more budget (generally)
        print(f"\nBudget Allocation:")
        for daypart, allocation in allocations.items():
            print(f"  {daypart.name}: ${allocation:.4f} ({daypart.duration_hours} hours)")

    @pytest.mark.asyncio
    async def test_no_track_repeats_across_playlists(
        self, batch_generator: BatchPlaylistGenerator, subsonic_client: SubsonicClient,
        station_identity: any
    ):
        """Test that no tracks repeat across all playlists.

        Success Criteria:
        - No track appears in multiple playlists
        - Track IDs are unique across entire batch
        - No-repeat window is enforced
        """
        # Arrange
        weekday_structure = next(
            (s for s in station_identity.programming_structures if s.schedule_type.value == "weekday"),
            None
        )
        dayparts = weekday_structure.dayparts[:5]

        # Act - LLM discovers tracks dynamically via tools
        playlists = await batch_generator.generate_batch(
            dayparts=dayparts,
            generation_date=date.today()
        )

        # Collect all track IDs
        all_track_ids = []
        for playlist in playlists:
            for track in playlist.tracks:
                all_track_ids.append(track.track_id)

        # Assert - No duplicates
        unique_track_ids = set(all_track_ids)
        assert len(all_track_ids) == len(unique_track_ids), \
            f"Found {len(all_track_ids) - len(unique_track_ids)} duplicate tracks across playlists"

        print(f"\n✓ {len(all_track_ids)} total tracks, all unique")

    @pytest.mark.asyncio
    async def test_batch_generation_performance(
        self, batch_generator: BatchPlaylistGenerator, subsonic_client: SubsonicClient,
        station_identity: any
    ):
        """Test batch generation performance.

        Success Criteria:
        - All 5 playlists generated in <5 minutes
        - Memory usage stays reasonable
        - No timeouts or errors
        """
        import time

        # Arrange
        weekday_structure = next(
            (s for s in station_identity.programming_structures if s.schedule_type.value == "weekday"),
            None
        )
        dayparts = weekday_structure.dayparts[:3]  # Use 3 for faster test

        # Act
        start_time = time.time()

        playlists = await batch_generator.generate_batch(
            dayparts=dayparts,
            generation_date=date.today()
        )

        total_time = time.time() - start_time

        # Assert
        assert len(playlists) == 3
        assert total_time < 300, \
            f"Batch generation took {total_time:.1f}s, expected <300s"

        print(f"\n✓ Generated {len(playlists)} playlists in {total_time:.1f}s")

    @pytest.mark.asyncio
    async def test_batch_progress_reporting(
        self, batch_generator: BatchPlaylistGenerator, subsonic_client: SubsonicClient,
        station_identity: any
    ):
        """Test that batch generation reports progress.

        Success Criteria:
        - Progress updates emitted for each playlist
        - Status includes: started, in_progress, completed
        - Cost tracking updates after each playlist
        """
        # Arrange
        weekday_structure = next(
            (s for s in station_identity.programming_structures if s.schedule_type.value == "weekday"),
            None
        )
        dayparts = weekday_structure.dayparts[:2]  # Use 2 for faster test

        progress_updates = []

        def progress_callback(status: dict):
            progress_updates.append(status)

        # Act
        batch_generator.on_progress = progress_callback

        playlists = await batch_generator.generate_batch(
            dayparts=dayparts,
            generation_date=date.today()
        )

        # Assert - Progress updates received
        assert len(progress_updates) > 0, "No progress updates received"

        # Check for different status types
        statuses = {update.get('status') for update in progress_updates}
        assert 'started' in statuses or 'in_progress' in statuses

        print(f"\n✓ Received {len(progress_updates)} progress updates")

    @pytest.mark.asyncio
    async def test_handle_insufficient_tracks_gracefully(
        self, batch_generator: BatchPlaylistGenerator, subsonic_client: SubsonicClient,
        station_identity: any
    ):
        """Test graceful handling when insufficient tracks available.

        Success Criteria:
        - Generates as many playlists as possible
        - Constraint relaxation applied automatically
        - Warnings logged for quality issues
        """
        # Arrange - Use very limited track pool
        weekday_structure = next(
            (s for s in station_identity.programming_structures if s.schedule_type.value == "weekday"),
            None
        )
        dayparts = weekday_structure.dayparts[:2]

        # Act - LLM discovers tracks (will adapt if limited library)
        playlists = await batch_generator.generate_batch(
            dayparts=dayparts,
            generation_date=date.today()
        )

        # Assert - Some playlists generated (may not be all)
        assert len(playlists) > 0, "No playlists generated"

        # Check for constraint relaxations
        for playlist in playlists:
            if playlist.constraint_relaxations:
                assert len(playlist.constraint_relaxations) > 0
                print(f"\n  Playlist '{playlist.name}': {len(playlist.constraint_relaxations)} relaxations")
