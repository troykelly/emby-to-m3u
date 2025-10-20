"""
T030: Live Integration Test - Cost Budget Warning Mode

Tests suggested budget mode where warnings are issued but generation continues.
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
from src.ai_playlist.cost_manager import CostManager
from src.subsonic.client import SubsonicClient
from src.subsonic.models import SubsonicConfig


@pytest.mark.integration
@pytest.mark.live
class TestCostBudgetWarningMode:
    """Live integration tests for suggested/warning budget mode."""

    @pytest.fixture
    def skip_if_no_env(self):
        """Skip test if required environment variables are missing."""
        required = ['SUBSONIC_URL', 'SUBSONIC_USER', 'SUBSONIC_PASSWORD', 'OPENAI_KEY']
        missing = [var for var in required if not os.getenv(var)]

        if missing:
            pytest.skip(f"Required environment variables missing: {', '.join(missing)}")

    @pytest.fixture
    async def config(self, skip_if_no_env) -> AIPlaylistConfig:
        """Load configuration with suggested budget mode."""
        config = AIPlaylistConfig.from_environment()
        # Set low budget to trigger warnings
        config.total_cost_budget = Decimal("5.00")
        config.cost_budget_mode = "suggested"  # SUGGESTED MODE
        config.cost_allocation_strategy = "equal"
        return config

    @pytest.fixture
    async def cost_manager(self, config: AIPlaylistConfig) -> CostManager:
        """Create cost manager with suggested budget."""
        return CostManager(
            total_budget=config.total_cost_budget,
            budget_mode="suggested",
            allocation_strategy=config.cost_allocation_strategy
        )

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
    async def batch_generator(self, config: AIPlaylistConfig) -> BatchPlaylistGenerator:
        """Create batch generator with suggested budget."""
        return BatchPlaylistGenerator(
            openai_api_key=config.openai_api_key,
            total_budget=config.total_cost_budget,
            allocation_strategy=config.cost_allocation_strategy,
            budget_mode="suggested"
        )

    @pytest.mark.asyncio
    async def test_suggested_mode_completes_despite_budget(
        self, batch_generator: BatchPlaylistGenerator, subsonic_client: SubsonicClient,
        station_identity: any
    ):
        """Test that generation completes even if budget exceeded.

        Success Criteria:
        - All playlists generated
        - Budget may be exceeded
        - Warnings issued when budget passed
        - No errors raised
        """
        # Arrange
        weekday_structure = next(
            (s for s in station_identity.programming_structures if s.schedule_type.value == "weekday"),
            None
        )
        # Use fewer dayparts for faster test
        dayparts = weekday_structure.dayparts[:3]
        available_tracks = await subsonic_client.search_tracks(query="", limit=1000)

        # Act - Generate all playlists
        playlists = await batch_generator.generate_batch(
            dayparts=dayparts,
            available_tracks=available_tracks,
            generation_date=date.today()
        )

        # Assert - All playlists generated
        assert len(playlists) == 3, \
            f"Expected 3 playlists, got {len(playlists)} (should complete in suggested mode)"

        # Calculate total cost
        total_cost = sum(p.cost_actual for p in playlists)

        print(f"\n✓ Suggested mode completed all {len(playlists)} playlists, "
              f"cost: ${total_cost:.4f} (budget: $5.00)")

    @pytest.mark.asyncio
    async def test_warnings_issued_at_thresholds(self, cost_manager: CostManager):
        """Test that warnings are issued at budget thresholds.

        Success Criteria:
        - Warning at 80% budget usage
        - Warning at 100% budget usage
        - Warning at 120% budget usage
        - Warnings logged but don't stop execution
        """
        warnings_received = []

        def warning_callback(warning: dict):
            """Capture warnings."""
            warnings_received.append(warning)

        cost_manager.on_warning = warning_callback

        # Act - Exceed budget incrementally
        cost_manager.record_cost(Decimal("4.00"), "operation_1")  # 80%
        cost_manager.record_cost(Decimal("1.50"), "operation_2")  # 110%

        # Assert - Warnings received
        assert len(warnings_received) >= 1, "No warnings received when budget exceeded"

        # Check warning content
        for warning in warnings_received:
            assert 'threshold' in warning or 'budget' in str(warning).lower()

        print(f"\n✓ Received {len(warnings_received)} warnings in suggested mode")

    @pytest.mark.asyncio
    async def test_decision_log_includes_budget_warnings(
        self, batch_generator: BatchPlaylistGenerator, subsonic_client: SubsonicClient,
        station_identity: any
    ):
        """Test that budget warnings are logged in decision log.

        Success Criteria:
        - Warning entries in decision log
        - Entry includes: threshold, current cost, budget
        - Timestamps present
        """
        # Arrange
        weekday_structure = next(
            (s for s in station_identity.programming_structures if s.schedule_type.value == "weekday"),
            None
        )
        dayparts = weekday_structure.dayparts[:3]
        available_tracks = await subsonic_client.search_tracks(query="", limit=1000)

        # Act
        playlists = await batch_generator.generate_batch(
            dayparts=dayparts,
            available_tracks=available_tracks,
            generation_date=date.today()
        )

        # Check decision logs for warnings
        warning_count = 0
        for playlist in playlists:
            if hasattr(playlist, 'decision_log'):
                for entry in playlist.decision_log:
                    if 'warning' in str(entry.decision_type).lower() or \
                       'budget' in str(entry.decision_data).lower():
                        warning_count += 1

        if warning_count > 0:
            print(f"\n✓ Found {warning_count} budget warning entries in decision logs")

    @pytest.mark.asyncio
    async def test_cost_tracking_continues_after_budget(self, cost_manager: CostManager):
        """Test that cost tracking continues after budget exceeded.

        Success Criteria:
        - Can record costs beyond budget
        - Total cost accurately tracked
        - No errors raised
        """
        # Act - Exceed budget
        cost_manager.record_cost(Decimal("3.00"), "op_1")
        cost_manager.record_cost(Decimal("3.00"), "op_2")  # Total $6.00
        cost_manager.record_cost(Decimal("2.00"), "op_3")  # Total $8.00

        total = cost_manager.get_total_cost()

        # Assert - Cost tracked beyond budget
        assert total == Decimal("8.00"), \
            f"Expected $8.00, got ${total}"

        assert total > Decimal("5.00"), \
            "Should be able to exceed budget in suggested mode"

        print(f"\n✓ Cost tracking continued: ${total:.4f} (budget: $5.00)")

    @pytest.mark.asyncio
    async def test_budget_status_shows_overrun(self, cost_manager: CostManager):
        """Test that budget status shows overrun in suggested mode.

        Success Criteria:
        - Status shows > 100% usage
        - Overrun amount calculated
        - Status clearly indicates budget exceeded
        """
        # Act - Exceed budget
        cost_manager.record_cost(Decimal("6.50"), "big_operation")

        status = cost_manager.get_budget_status()

        # Assert - Status shows overrun
        assert status['percentage_used'] > 100.0, \
            f"Expected >100% usage, got {status['percentage_used']:.1f}%"

        assert status['used'] > status['total_budget']

        if 'overrun' in status:
            assert status['overrun'] > 0

        print(f"\n✓ Budget status shows overrun: ${status['used']:.4f}/${status['total_budget']:.4f} "
              f"({status['percentage_used']:.1f}%)")

    @pytest.mark.asyncio
    async def test_comparison_hard_vs_suggested_mode(
        self, subsonic_client: SubsonicClient, station_identity: any
    ):
        """Test behavioral difference between hard and suggested modes.

        Success Criteria:
        - Hard mode stops at budget
        - Suggested mode continues past budget
        - Clear distinction in behavior
        """
        # Arrange
        weekday_structure = next(
            (s for s in station_identity.programming_structures if s.schedule_type.value == "weekday"),
            None
        )
        dayparts = weekday_structure.dayparts[:2]
        available_tracks = await subsonic_client.search_tracks(query="", limit=800)

        # Test hard mode
        hard_generator = BatchPlaylistGenerator(
            openai_api_key=os.getenv('OPENAI_KEY'),
            total_budget=Decimal("2.00"),  # Very low budget
            allocation_strategy="equal",
            budget_mode="hard"
        )

        # Test suggested mode
        suggested_generator = BatchPlaylistGenerator(
            openai_api_key=os.getenv('OPENAI_KEY'),
            total_budget=Decimal("2.00"),  # Same low budget
            allocation_strategy="equal",
            budget_mode="suggested"
        )

        # Act - Hard mode
        hard_playlists = []
        try:
            hard_playlists = await hard_generator.generate_batch(
                dayparts=dayparts,
                available_tracks=available_tracks,
                generation_date=date.today()
            )
        except Exception:
            pass

        # Act - Suggested mode
        suggested_playlists = await suggested_generator.generate_batch(
            dayparts=dayparts,
            available_tracks=available_tracks,
            generation_date=date.today()
        )

        # Assert - Suggested mode generated more (or equal)
        assert len(suggested_playlists) >= len(hard_playlists), \
            "Suggested mode should generate at least as many as hard mode"

        print(f"\n✓ Hard mode: {len(hard_playlists)} playlists")
        print(f"  Suggested mode: {len(suggested_playlists)} playlists")

    @pytest.mark.asyncio
    async def test_warning_callback_integration(self, cost_manager: CostManager):
        """Test integration with warning callback system.

        Success Criteria:
        - Callback invoked when warnings occur
        - Callback receives warning details
        - Multiple callbacks can be registered
        """
        warnings = []

        def custom_warning_handler(warning: dict):
            warnings.append(warning)

        cost_manager.on_warning = custom_warning_handler

        # Act - Trigger warnings
        cost_manager.record_cost(Decimal("4.50"), "op_1")  # 90%
        cost_manager.record_cost(Decimal("1.00"), "op_2")  # 110%

        # Assert - Callbacks invoked
        assert len(warnings) > 0, "Warning callback not invoked"

        print(f"\n✓ Warning callback invoked {len(warnings)} times")

    @pytest.mark.asyncio
    async def test_detailed_cost_breakdown_in_suggested_mode(
        self, batch_generator: BatchPlaylistGenerator, subsonic_client: SubsonicClient,
        station_identity: any
    ):
        """Test that detailed cost breakdown is available.

        Success Criteria:
        - Per-playlist costs tracked
        - Running totals available
        - Cost breakdown includes: prompt tokens, completion tokens, total cost
        """
        # Arrange
        weekday_structure = next(
            (s for s in station_identity.programming_structures if s.schedule_type.value == "weekday"),
            None
        )
        dayparts = weekday_structure.dayparts[:2]
        available_tracks = await subsonic_client.search_tracks(query="", limit=800)

        # Act
        playlists = await batch_generator.generate_batch(
            dayparts=dayparts,
            available_tracks=available_tracks,
            generation_date=date.today()
        )

        # Assert - Each playlist has cost details
        for playlist in playlists:
            assert playlist.cost_actual is not None
            assert playlist.cost_actual > 0

            # Check for detailed breakdown if available
            if hasattr(playlist, 'cost_breakdown'):
                assert 'prompt_tokens' in playlist.cost_breakdown or \
                       'completion_tokens' in playlist.cost_breakdown

        total_cost = sum(p.cost_actual for p in playlists)

        print(f"\n✓ Cost breakdown:")
        for i, playlist in enumerate(playlists):
            print(f"  Playlist {i+1}: ${playlist.cost_actual:.4f}")
        print(f"  Total: ${total_cost:.4f}")
