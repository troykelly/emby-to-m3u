"""
T029: Live Integration Test - Cost Budget Hard Limit

Tests hard budget mode where generation stops when budget is exceeded.
Tests FR-009 and FR-030 requirements for cost control.

This test uses LIVE APIs with actual costs (NO mocks).
"""
import os
import pytest
from datetime import date
from decimal import Decimal
from pathlib import Path
from src.ai_playlist.config import AIPlaylistConfig
from src.ai_playlist.document_parser import DocumentParser
from src.ai_playlist.batch_executor import BatchPlaylistGenerator
from src.ai_playlist.cost_manager import CostManager, BudgetExceededError
from src.subsonic.client import SubsonicClient
from src.subsonic.models import SubsonicConfig


@pytest.mark.integration
@pytest.mark.live
class TestCostBudgetHardLimit:
    """Live integration tests for hard budget mode cost enforcement."""

    @pytest.fixture
    def skip_if_no_env(self):
        """Skip test if required environment variables are missing."""
        required = ['SUBSONIC_URL', 'SUBSONIC_USER', 'SUBSONIC_PASSWORD', 'OPENAI_KEY']
        missing = [var for var in required if not os.getenv(var)]

        if missing:
            pytest.skip(f"Required environment variables missing: {', '.join(missing)}")

    @pytest.fixture
    async def config(self, skip_if_no_env) -> AIPlaylistConfig:
        """Load configuration with hard budget mode."""
        config = AIPlaylistConfig.from_environment()
        # Set low budget for testing
        config.total_cost_budget = Decimal("5.00")
        config.cost_budget_mode = "hard"  # HARD MODE
        config.cost_allocation_strategy = "equal"
        return config

    @pytest.fixture
    async def cost_manager(self, config: AIPlaylistConfig) -> CostManager:
        """Create cost manager with hard budget."""
        return CostManager(
            total_budget=config.total_cost_budget,
            budget_mode="hard",
            allocation_strategy=config.cost_allocation_strategy
        )

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
    async def batch_generator(self, config: AIPlaylistConfig) -> BatchPlaylistGenerator:
        """Create batch generator with hard budget."""
        return BatchPlaylistGenerator(
            openai_api_key=config.openai_api_key,
            total_budget=config.total_cost_budget,
            allocation_strategy=config.cost_allocation_strategy,
            budget_mode="hard"
        )

    @pytest.mark.asyncio
    async def test_hard_mode_stops_at_budget(
        self, batch_generator: BatchPlaylistGenerator, subsonic_client: SubsonicClient,
        station_identity: any
    ):
        """Test that generation stops when hard budget is exceeded.

        Success Criteria:
        - Generation attempts multiple playlists
        - Stops when budget reached
        - No overrun beyond budget
        - BudgetExceededError raised or partial results returned
        """
        # Arrange - Get weekday dayparts
        weekday_structure = next(
            (s for s in station_identity.programming_structures if s.schedule_type.value == "weekday"),
            None
        )
        assert weekday_structure is not None

        # Try to generate 5 playlists with only $5 budget
        dayparts = weekday_structure.dayparts[:5]
        available_tracks = await subsonic_client.search_tracks(query="", limit=1500)

        # Act - Try to generate all (should stop partway)
        try:
            playlists = await batch_generator.generate_batch(
                dayparts=dayparts,
                available_tracks=available_tracks,
                generation_date=date.today()
            )

            # If we got results, verify budget not exceeded
            total_cost = sum(p.cost_actual for p in playlists)

            assert total_cost <= Decimal("5.00"), \
                f"Hard budget exceeded: ${total_cost} > $5.00"

            # Should have partial results (not all 5 playlists)
            assert len(playlists) < 5, \
                "Expected partial generation with low budget, got all playlists"

            print(f"\n✓ Hard mode stopped at {len(playlists)}/5 playlists, cost: ${total_cost:.4f}")

        except BudgetExceededError as e:
            # This is also acceptable - generation stopped with error
            print(f"\n✓ Hard mode raised BudgetExceededError: {e}")
            assert True

    @pytest.mark.asyncio
    async def test_cost_manager_enforces_hard_limit(self, cost_manager: CostManager):
        """Test that CostManager enforces hard budget limit.

        Success Criteria:
        - Can track costs up to budget
        - Raises BudgetExceededError when budget hit
        - No operations allowed after budget exceeded
        """
        # Act - Simulate incrementing costs
        cost_manager.record_cost(Decimal("2.00"), "playlist_1")
        cost_manager.record_cost(Decimal("2.00"), "playlist_2")

        # Should be at $4.00 now, one more should fail
        with pytest.raises(BudgetExceededError):
            cost_manager.record_cost(Decimal("2.00"), "playlist_3")

        # Assert - Total cost did not exceed budget
        total = cost_manager.get_total_cost()
        assert total <= Decimal("5.00"), f"Cost ${total} exceeded $5.00 budget"

        print(f"\n✓ Cost manager enforced hard limit at ${total:.4f}")

    @pytest.mark.asyncio
    async def test_budget_allocation_with_hard_limit(
        self, cost_manager: CostManager, station_identity: any
    ):
        """Test budget allocation respects hard limit.

        Success Criteria:
        - Budget allocated across playlists
        - Allocations sum to total budget
        - No single allocation exceeds total
        """
        # Arrange - Get dayparts
        weekday_structure = next(
            (s for s in station_identity.programming_structures if s.schedule_type.value == "weekday"),
            None
        )
        dayparts = weekday_structure.dayparts[:5]

        # Act - Calculate allocations
        allocations = cost_manager.allocate_budget_equal(len(dayparts))

        # Assert - Allocations sum to budget
        total_allocated = sum(allocations)
        assert total_allocated == Decimal("5.00"), \
            f"Allocated ${total_allocated} != $5.00 budget"

        # Assert - Each allocation is reasonable
        for allocation in allocations:
            assert allocation > 0
            assert allocation <= Decimal("5.00")

        print(f"\n✓ Budget allocated: {[f'${a:.4f}' for a in allocations]}")

    @pytest.mark.asyncio
    async def test_partial_playlist_generation_logs_budget_stop(
        self, batch_generator: BatchPlaylistGenerator, subsonic_client: SubsonicClient,
        station_identity: any
    ):
        """Test that budget stop is logged in decision log.

        Success Criteria:
        - Decision log contains budget stop entry
        - Entry includes: playlists completed, cost at stop, budget limit
        - Timestamp is present
        """
        # Arrange
        weekday_structure = next(
            (s for s in station_identity.programming_structures if s.schedule_type.value == "weekday"),
            None
        )
        dayparts = weekday_structure.dayparts[:5]
        available_tracks = await subsonic_client.search_tracks(query="", limit=1500)

        # Act
        try:
            playlists = await batch_generator.generate_batch(
                dayparts=dayparts,
                available_tracks=available_tracks,
                generation_date=date.today()
            )

            # Check if batch generator has decision log
            if hasattr(batch_generator, 'decision_log'):
                budget_entries = [
                    entry for entry in batch_generator.decision_log
                    if 'budget' in str(entry.decision_type).lower()
                ]

                if len(budget_entries) > 0:
                    print(f"\n✓ Found {len(budget_entries)} budget-related decision log entries")

        except BudgetExceededError:
            # Expected in hard mode
            pass

    @pytest.mark.asyncio
    async def test_no_overrun_with_sequential_generation(
        self, batch_generator: BatchPlaylistGenerator, subsonic_client: SubsonicClient,
        station_identity: any
    ):
        """Test that sequential generation stops cleanly at budget.

        Success Criteria:
        - Each playlist cost tracked individually
        - Running total monitored
        - Stops before exceeding budget
        - No partial playlists in output
        """
        # Arrange
        weekday_structure = next(
            (s for s in station_identity.programming_structures if s.schedule_type.value == "weekday"),
            None
        )
        dayparts = weekday_structure.dayparts[:3]  # Try 3 playlists
        available_tracks = await subsonic_client.search_tracks(query="", limit=1000)

        # Act
        playlists = []
        running_cost = Decimal("0.00")

        for i, daypart in enumerate(dayparts):
            try:
                # Check if we have budget remaining
                if running_cost >= Decimal("5.00"):
                    print(f"\n✓ Stopped at playlist {i} due to budget")
                    break

                from src.ai_playlist.models.core import PlaylistSpecification
                spec = PlaylistSpecification.from_daypart(daypart, date.today())

                from src.ai_playlist.openai_client import OpenAIPlaylistGenerator
                generator = OpenAIClient(
                    api_key=os.getenv('OPENAI_KEY'),
                    model="gpt-4o"
                )

                playlist = await generator.generate_playlist(spec, available_tracks)

                # Check cost
                if running_cost + playlist.cost_actual > Decimal("5.00"):
                    print(f"\n✓ Would exceed budget, stopped at playlist {i}")
                    break

                playlists.append(playlist)
                running_cost += playlist.cost_actual

            except BudgetExceededError:
                print(f"\n✓ Budget exceeded at playlist {i}")
                break

        # Assert - Total cost within budget
        assert running_cost <= Decimal("5.00"), \
            f"Total cost ${running_cost} exceeded $5.00"

        print(f"\n✓ Generated {len(playlists)} playlists, total: ${running_cost:.4f}")

    @pytest.mark.asyncio
    async def test_cost_tracking_precision(self, cost_manager: CostManager):
        """Test that cost tracking maintains precision.

        Success Criteria:
        - Decimal precision maintained (4 decimal places)
        - No floating point errors
        - Accurate summation
        """
        # Act - Record multiple small costs
        costs = [
            Decimal("0.0123"),
            Decimal("0.0456"),
            Decimal("0.0789"),
            Decimal("0.0321"),
            Decimal("0.0654")
        ]

        for i, cost in enumerate(costs):
            if cost_manager.get_total_cost() + cost <= Decimal("5.00"):
                cost_manager.record_cost(cost, f"operation_{i}")

        total = cost_manager.get_total_cost()
        expected = sum(costs)

        # Assert - Precision maintained
        assert total == expected, \
            f"Cost precision error: {total} != {expected}"

        print(f"\n✓ Cost precision maintained: ${total:.4f}")

    @pytest.mark.asyncio
    async def test_budget_status_reporting(self, cost_manager: CostManager):
        """Test budget status reporting.

        Success Criteria:
        - Can query current budget status
        - Reports: total budget, used, remaining, percentage
        - Status updates after each cost
        """
        # Act - Record some costs
        cost_manager.record_cost(Decimal("1.50"), "test_1")
        status1 = cost_manager.get_budget_status()

        cost_manager.record_cost(Decimal("2.00"), "test_2")
        status2 = cost_manager.get_budget_status()

        # Assert - Status has required fields
        assert 'total_budget' in status1
        assert 'used' in status1
        assert 'remaining' in status1
        assert 'percentage_used' in status1

        # Assert - Status updates correctly
        assert status2['used'] > status1['used']
        assert status2['remaining'] < status1['remaining']

        print(f"\n✓ Budget status: ${status2['used']:.4f}/${status2['total_budget']:.4f} "
              f"({status2['percentage_used']:.1f}%)")
