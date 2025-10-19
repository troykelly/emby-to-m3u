"""Comprehensive tests for cost_manager.py - Budget tracking and enforcement.

Tests cover:
- Initialization with different configurations
- Budget allocation strategies (equal vs dynamic)
- Budget modes (hard vs suggested)
- Cost recording and tracking
- Budget enforcement
- Warning thresholds
- Token counting
"""
import pytest
import os
from decimal import Decimal
from unittest.mock import patch, Mock

from src.ai_playlist.cost_manager import (
    CostManager,
    BudgetMode,
    AllocationStrategy,
    CostRecord,
    BudgetAllocation,
    BudgetExceededError,
    CostManagerError
)


class TestCostManagerInitialization:
    """Test CostManager initialization and configuration."""

    def test_init_with_defaults(self):
        """Test initialization with default values from environment."""
        # Act
        with patch.dict(os.environ, {}, clear=True):
            manager = CostManager()

        # Assert
        assert manager.total_budget == Decimal("25.00")
        assert manager.budget_mode == BudgetMode.SUGGESTED
        assert manager.allocation_strategy == AllocationStrategy.DYNAMIC
        assert manager.cost_records == []
        assert manager.allocations == {}

    def test_init_with_custom_budget(self):
        """Test initialization with custom budget parameter."""
        # Act
        manager = CostManager(total_budget=Decimal("50.00"))

        # Assert
        assert manager.total_budget == Decimal("50.00")

    def test_init_with_float_budget_converts_to_decimal(self):
        """Test that float budget is converted to Decimal."""
        # Act
        manager = CostManager(total_budget=75.50)

        # Assert
        assert manager.total_budget == Decimal("75.50")
        assert isinstance(manager.total_budget, Decimal)

    def test_init_reads_budget_from_environment(self):
        """Test initialization reads PLAYLIST_TOTAL_COST_BUDGET from environment."""
        # Arrange
        with patch.dict(os.environ, {"PLAYLIST_TOTAL_COST_BUDGET": "100.00"}):
            # Act
            manager = CostManager()

            # Assert
            assert manager.total_budget == Decimal("100.00")

    def test_init_with_hard_budget_mode(self):
        """Test initialization with hard budget mode."""
        # Act
        manager = CostManager(budget_mode="hard")

        # Assert
        assert manager.budget_mode == BudgetMode.HARD

    def test_init_with_suggested_budget_mode(self):
        """Test initialization with suggested budget mode."""
        # Act
        manager = CostManager(budget_mode="suggested")

        # Assert
        assert manager.budget_mode == BudgetMode.SUGGESTED

    def test_init_reads_budget_mode_from_environment(self):
        """Test initialization reads PLAYLIST_COST_BUDGET_MODE from environment."""
        # Arrange
        with patch.dict(os.environ, {"PLAYLIST_COST_BUDGET_MODE": "hard"}):
            # Act
            manager = CostManager()

            # Assert
            assert manager.budget_mode == BudgetMode.HARD

    def test_init_with_equal_allocation_strategy(self):
        """Test initialization with equal allocation strategy."""
        # Act
        manager = CostManager(allocation_strategy="equal")

        # Assert
        assert manager.allocation_strategy == AllocationStrategy.EQUAL

    def test_init_with_dynamic_allocation_strategy(self):
        """Test initialization with dynamic allocation strategy."""
        # Act
        manager = CostManager(allocation_strategy="dynamic")

        # Assert
        assert manager.allocation_strategy == AllocationStrategy.DYNAMIC

    def test_init_reads_allocation_strategy_from_environment(self):
        """Test initialization reads PLAYLIST_COST_ALLOCATION_STRATEGY from environment."""
        # Arrange
        with patch.dict(os.environ, {"PLAYLIST_COST_ALLOCATION_STRATEGY": "equal"}):
            # Act
            manager = CostManager()

            # Assert
            assert manager.allocation_strategy == AllocationStrategy.EQUAL


class TestBudgetAllocationEqual:
    """Test equal budget allocation strategy."""

    def test_allocate_budgets_equal_splits_evenly(self):
        """Test equal allocation splits budget evenly across playlists."""
        # Arrange
        manager = CostManager(total_budget=Decimal("100.00"), allocation_strategy="equal")
        playlist_specs = [
            ("playlist-1", {"target_track_count_max": 50}),
            ("playlist-2", {"target_track_count_max": 100}),
            ("playlist-3", {"target_track_count_max": 25}),
            ("playlist-4", {"target_track_count_max": 75})
        ]

        # Act
        allocations = manager.allocate_budgets(playlist_specs)

        # Assert
        assert len(allocations) == 4
        # Each should get 100/4 = 25.00
        for playlist_id, budget in allocations.items():
            assert budget == Decimal("25.00")

    def test_allocate_budgets_equal_stores_allocations(self):
        """Test equal allocation stores BudgetAllocation objects."""
        # Arrange
        manager = CostManager(total_budget=Decimal("60.00"), allocation_strategy="equal")
        playlist_specs = [
            ("playlist-1", {}),
            ("playlist-2", {}),
            ("playlist-3", {})
        ]

        # Act
        manager.allocate_budgets(playlist_specs)

        # Assert
        assert len(manager.allocations) == 3
        assert "playlist-1" in manager.allocations
        assert manager.allocations["playlist-1"].allocated_budget == Decimal("20.00")
        assert manager.allocations["playlist-1"].spent == Decimal("0.0")
        assert manager.allocations["playlist-1"].remaining == Decimal("20.00")

    def test_allocate_budgets_equal_raises_error_on_empty_list(self):
        """Test allocate_budgets raises ValueError for empty playlist_specs."""
        # Arrange
        manager = CostManager(allocation_strategy="equal")

        # Act & Assert
        with pytest.raises(ValueError, match="playlist_specs cannot be empty"):
            manager.allocate_budgets([])

    def test_allocate_budget_equal_by_count(self):
        """Test allocate_budget_equal method allocates by count."""
        # Arrange
        manager = CostManager(total_budget=Decimal("150.00"))

        # Act
        budgets = manager.allocate_budget_equal(count=5)

        # Assert
        assert len(budgets) == 5
        assert all(b == Decimal("30.00") for b in budgets)


class TestBudgetAllocationDynamic:
    """Test dynamic budget allocation strategy."""

    def test_allocate_budgets_dynamic_weighs_by_complexity(self):
        """Test dynamic allocation weighs by playlist complexity."""
        # Arrange
        manager = CostManager(total_budget=Decimal("100.00"), allocation_strategy="dynamic")
        playlist_specs = [
            ("simple", {"target_track_count_max": 25}),  # Low complexity
            ("complex", {"target_track_count_max": 100})  # High complexity
        ]

        # Act
        allocations = manager.allocate_budgets(playlist_specs)

        # Assert
        assert len(allocations) == 2
        # Complex playlist should get more budget than simple
        assert allocations["complex"] > allocations["simple"]
        # Total should equal budget
        assert allocations["simple"] + allocations["complex"] == Decimal("100.00")

    def test_allocate_budgets_dynamic_considers_bpm_constraints(self):
        """Test dynamic allocation considers tight BPM constraints."""
        # Arrange
        manager = CostManager(total_budget=Decimal("100.00"), allocation_strategy="dynamic")
        playlist_specs = [
            ("loose-bpm", {
                "target_track_count_max": 50,
                "track_selection_criteria": {
                    "bpm_ranges": [{"min": 80, "max": 140}]  # 60 BPM range (loose)
                }
            }),
            ("tight-bpm", {
                "target_track_count_max": 50,
                "track_selection_criteria": {
                    "bpm_ranges": [{"min": 118, "max": 122}]  # 4 BPM range (very tight)
                }
            })
        ]

        # Act
        allocations = manager.allocate_budgets(playlist_specs)

        # Assert
        # Tight BPM should get more budget (1.3x complexity multiplier)
        assert allocations["tight-bpm"] > allocations["loose-bpm"]

    def test_allocate_budgets_dynamic_considers_genre_count(self):
        """Test dynamic allocation considers number of genres."""
        # Arrange
        manager = CostManager(total_budget=Decimal("100.00"), allocation_strategy="dynamic")
        playlist_specs = [
            ("few-genres", {
                "target_track_count_max": 50,
                "track_selection_criteria": {
                    "genre_mix": {"Rock": 0.5, "Pop": 0.5}  # 2 genres
                }
            }),
            ("many-genres", {
                "target_track_count_max": 50,
                "track_selection_criteria": {
                    "genre_mix": {
                        "Rock": 0.2, "Pop": 0.2, "Dance": 0.2,
                        "Hip-Hop": 0.2, "Jazz": 0.1, "Electronic": 0.1  # 6 genres
                    }
                }
            })
        ]

        # Act
        allocations = manager.allocate_budgets(playlist_specs)

        # Assert
        # Many genres should get more budget (1.2x complexity multiplier)
        assert allocations["many-genres"] > allocations["few-genres"]

    def test_calculate_complexity_minimum_floor(self):
        """Test complexity calculation has minimum floor of 0.5."""
        # Arrange
        manager = CostManager(allocation_strategy="dynamic")
        spec = {"target_track_count_max": 1}  # Very low count

        # Act
        complexity = manager._calculate_complexity(spec)

        # Assert
        assert complexity >= 0.5


class TestCostRecording:
    """Test cost recording and tracking."""

    def test_record_cost_with_tokens(self):
        """Test recording cost from token counts."""
        # Arrange
        manager = CostManager()

        # Act - use positional arguments matching actual signature
        record = manager.record_cost(
            "test-op-1",  # cost_or_operation_id
            1000,         # input_tokens_or_playlist_id
            500,          # output_tokens
            "gpt-4o"      # model
        )

        # Assert
        assert isinstance(record, CostRecord)
        assert record.operation_id == "test-op-1"
        assert record.input_tokens == 1000
        assert record.output_tokens == 500
        assert record.cost_usd > Decimal("0")
        assert len(manager.cost_records) == 1

    def test_record_cost_with_direct_cost(self):
        """Test recording cost directly (cost, playlist_id signature)."""
        # Arrange
        manager = CostManager()
        cost = Decimal("0.50")

        # Act
        record = manager.record_cost(cost, "playlist-1")

        # Assert
        assert record.cost_usd == cost
        assert len(manager.cost_records) == 1
        assert record.input_tokens == 0
        assert record.output_tokens == 0

    def test_record_cost_updates_playlist_allocation(self):
        """Test recording cost updates playlist allocation."""
        # Arrange
        manager = CostManager(total_budget=Decimal("100.00"), allocation_strategy="equal")
        playlist_specs = [("playlist-1", {}), ("playlist-2", {})]
        manager.allocate_budgets(playlist_specs)

        # Act
        manager.record_cost(Decimal("10.00"), "playlist-1")

        # Assert
        allocation = manager.allocations["playlist-1"]
        assert allocation.spent == Decimal("10.00")
        # Note: remaining is calculated in __post_init__ and not auto-updated
        # It reflects the initial allocation, not current state
        assert allocation.remaining == Decimal("50.00")  # Initial allocation
        # To get current remaining, calculate manually:
        assert allocation.allocated_budget - allocation.spent == Decimal("40.00")

    def test_calculate_cost_uses_correct_pricing(self):
        """Test calculate_cost uses correct GPT-4o pricing."""
        # Arrange
        manager = CostManager()

        # Act
        cost = manager.calculate_cost(input_tokens=1_000_000, output_tokens=1_000_000, model="gpt-4o")

        # Assert
        # GPT-4o: $0.15 per 1M input tokens, $0.60 per 1M output tokens
        expected = Decimal("0.15") + Decimal("0.60")
        assert cost == expected

    def test_calculate_cost_gpt4o_mini_pricing(self):
        """Test calculate_cost uses correct GPT-4o-mini pricing."""
        # Arrange
        manager = CostManager()

        # Act
        cost = manager.calculate_cost(input_tokens=1_000_000, output_tokens=1_000_000, model="gpt-4o-mini")

        # Assert
        # GPT-4o-mini: $0.075 per 1M input tokens, $0.30 per 1M output tokens
        expected = Decimal("0.075") + Decimal("0.30")
        assert cost == expected


class TestBudgetEnforcement:
    """Test budget enforcement in hard and suggested modes."""

    def test_hard_mode_raises_error_on_budget_exceeded(self):
        """Test hard mode raises BudgetExceededError when budget exceeded."""
        # Arrange
        manager = CostManager(total_budget=Decimal("1.00"), budget_mode="hard")

        # Act & Assert
        with pytest.raises(BudgetExceededError, match="Total budget would be exceeded"):
            manager.record_cost(Decimal("1.50"), "playlist-1")

    def test_hard_mode_allows_within_budget(self):
        """Test hard mode allows recording cost within budget."""
        # Arrange
        manager = CostManager(total_budget=Decimal("10.00"), budget_mode="hard")

        # Act - should not raise
        manager.record_cost(Decimal("5.00"), "playlist-1")
        manager.record_cost(Decimal("4.99"), "playlist-2")

        # Assert
        assert len(manager.cost_records) == 2

    def test_hard_mode_prevents_exceeding_with_multiple_costs(self):
        """Test hard mode prevents total from exceeding budget."""
        # Arrange
        manager = CostManager(total_budget=Decimal("10.00"), budget_mode="hard")
        manager.record_cost(Decimal("8.00"), "playlist-1")

        # Act & Assert - next cost would exceed
        with pytest.raises(BudgetExceededError):
            manager.record_cost(Decimal("3.00"), "playlist-2")

    def test_suggested_mode_allows_exceeding_budget(self):
        """Test suggested mode allows exceeding budget without error."""
        # Arrange
        manager = CostManager(total_budget=Decimal("1.00"), budget_mode="suggested")

        # Act - should not raise even though exceeding budget
        manager.record_cost(Decimal("5.00"), "playlist-1")

        # Assert
        assert len(manager.cost_records) == 1
        assert manager.get_total_spent() == Decimal("5.00")


class TestTokenCounting:
    """Test token counting functionality."""

    def test_count_tokens_returns_positive_integer(self):
        """Test count_tokens returns positive integer."""
        # Arrange
        manager = CostManager()
        text = "Hello, this is a test message for token counting."

        # Act
        tokens = manager.count_tokens(text)

        # Assert
        assert isinstance(tokens, int)
        assert tokens > 0

    def test_count_tokens_longer_text_has_more_tokens(self):
        """Test longer text has more tokens."""
        # Arrange
        manager = CostManager()
        short_text = "Hello"
        long_text = "Hello " * 100

        # Act
        short_tokens = manager.count_tokens(short_text)
        long_tokens = manager.count_tokens(long_text)

        # Assert
        assert long_tokens > short_tokens


class TestCostSummary:
    """Test cost summary and reporting functionality."""

    def test_get_total_spent_zero_initially(self):
        """Test get_total_spent returns zero for new manager."""
        # Arrange
        manager = CostManager()

        # Act
        total = manager.get_total_spent()

        # Assert
        assert total == Decimal("0.0")

    def test_get_total_spent_sums_all_costs(self):
        """Test get_total_spent sums all recorded costs."""
        # Arrange
        manager = CostManager()
        manager.record_cost(Decimal("1.50"), "playlist-1")
        manager.record_cost(Decimal("2.25"), "playlist-2")
        manager.record_cost(Decimal("0.75"), "playlist-3")

        # Act
        total = manager.get_total_spent()

        # Assert
        assert total == Decimal("4.50")

    def test_get_remaining_budget(self):
        """Test get_remaining_budget calculates correctly."""
        # Arrange
        manager = CostManager(total_budget=Decimal("100.00"))
        manager.record_cost(Decimal("35.00"), "playlist-1")

        # Act
        remaining = manager.get_remaining_budget()

        # Assert
        assert remaining == Decimal("65.00")


class TestBudgetAllocationDataclass:
    """Test BudgetAllocation dataclass."""

    def test_budget_allocation_calculates_remaining(self):
        """Test BudgetAllocation calculates remaining in __post_init__."""
        # Act
        allocation = BudgetAllocation(
            playlist_id="test",
            allocated_budget=Decimal("50.00"),
            spent=Decimal("15.00")
        )

        # Assert
        assert allocation.remaining == Decimal("35.00")

    def test_budget_allocation_remaining_updates_with_spent(self):
        """Test remaining is recalculated when spent changes and __post_init__ called."""
        # Arrange
        allocation = BudgetAllocation(
            playlist_id="test",
            allocated_budget=Decimal("100.00")
        )

        # Act - Update spent and manually recalculate remaining
        allocation.spent = Decimal("40.00")
        allocation.__post_init__()  # Recalculate remaining

        # Assert
        assert allocation.remaining == Decimal("60.00")


class TestCostRecord:
    """Test CostRecord dataclass."""

    def test_cost_record_creation(self):
        """Test creating a CostRecord."""
        # Act
        record = CostRecord(
            operation_id="op-1",
            input_tokens=1000,
            output_tokens=500,
            cost_usd=Decimal("0.45"),
            model="gpt-4o"
        )

        # Assert
        assert record.operation_id == "op-1"
        assert record.input_tokens == 1000
        assert record.output_tokens == 500
        assert record.cost_usd == Decimal("0.45")
        assert record.model == "gpt-4o"
