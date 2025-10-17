"""
Cost budget management and token tracking for AI playlist generation.

Manages API costs with configurable budget enforcement:
- Hard mode: Stop generation when budget exceeded
- Suggested mode: Warn but continue when budget exceeded

Supports allocation strategies:
- Dynamic: Allocate by playlist complexity (track count, constraints)
- Equal: Split budget evenly across playlists

FR-009: Cost budget enforcement
FR-030: Budget allocation strategies
"""

import os
import logging
from typing import Optional, Dict, List, Tuple, Callable
from enum import Enum
from dataclasses import dataclass, field
from decimal import Decimal
import tiktoken

logger = logging.getLogger(__name__)


class BudgetMode(Enum):
    """Budget enforcement mode."""
    HARD = "hard"  # Stop generation on budget exceed
    SUGGESTED = "suggested"  # Warn but continue on budget exceed


class AllocationStrategy(Enum):
    """Budget allocation strategy."""
    DYNAMIC = "dynamic"  # Allocate by complexity
    EQUAL = "equal"  # Split evenly


@dataclass
class CostRecord:
    """Record of API cost for a single operation."""
    operation_id: str
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal
    model: str = "gpt-4o"
    timestamp: Optional[str] = None


@dataclass
class BudgetAllocation:
    """Budget allocation for a playlist."""
    playlist_id: str
    allocated_budget: Decimal
    spent: Decimal = Decimal("0.0")
    remaining: Decimal = field(init=False)

    def __post_init__(self):
        self.remaining = self.allocated_budget - self.spent


class CostManagerError(Exception):
    """Base exception for cost management errors."""
    pass


class BudgetExceededError(CostManagerError):
    """Raised when hard budget limit is exceeded."""
    pass


class CostManager:
    """
    Manages API costs and budget enforcement for playlist generation.

    Tracks token usage, calculates costs, and enforces budget limits based on
    configured mode (hard/suggested) and allocation strategy (dynamic/equal).

    Attributes:
        total_budget: Total budget in USD
        budget_mode: Budget enforcement mode (hard/suggested)
        allocation_strategy: Budget allocation strategy (dynamic/equal)
        cost_records: List of all cost records
        allocations: Budget allocations per playlist
    """

    # GPT-4o pricing (as of Jan 2025)
    PRICING = {
        "gpt-4o": {
            "input": Decimal("0.15") / 1_000_000,  # $0.15 per 1M tokens
            "output": Decimal("0.60") / 1_000_000   # $0.60 per 1M tokens
        },
        "gpt-4o-mini": {
            "input": Decimal("0.075") / 1_000_000,  # $0.075 per 1M tokens
            "output": Decimal("0.30") / 1_000_000   # $0.30 per 1M tokens
        }
    }

    def __init__(
        self,
        total_budget: Optional[Decimal] = None,
        budget_mode: Optional[str] = None,
        allocation_strategy: Optional[str] = None
    ):
        """
        Initialize cost manager.

        Reads configuration from environment if not provided:
        - PLAYLIST_TOTAL_COST_BUDGET (default: 25.00)
        - PLAYLIST_COST_BUDGET_MODE (default: suggested)
        - PLAYLIST_COST_ALLOCATION_STRATEGY (default: dynamic)

        Args:
            total_budget: Total budget in USD (as Decimal)
            budget_mode: Budget mode ("hard" or "suggested")
            allocation_strategy: Allocation strategy ("dynamic" or "equal")
        """
        # Read from environment with defaults
        if total_budget is None:
            total_budget = Decimal(os.getenv("PLAYLIST_TOTAL_COST_BUDGET", "25.00"))
        elif not isinstance(total_budget, Decimal):
            total_budget = Decimal(str(total_budget))

        self.total_budget = total_budget

        budget_mode_str = (
            budget_mode or os.getenv("PLAYLIST_COST_BUDGET_MODE", "suggested")
        ).lower()
        self.budget_mode = BudgetMode(budget_mode_str)

        allocation_str = (
            allocation_strategy or
            os.getenv("PLAYLIST_COST_ALLOCATION_STRATEGY", "dynamic")
        ).lower()
        self.allocation_strategy = AllocationStrategy(allocation_str)

        # State tracking
        self.cost_records: List[CostRecord] = []
        self.allocations: Dict[str, BudgetAllocation] = {}

        # Warning callback for suggested mode
        self.on_warning: Optional[Callable[[Dict], None]] = None

        # Warning thresholds
        self._warning_thresholds = [Decimal("0.80"), Decimal("1.00"), Decimal("1.20")]
        self._warnings_issued: set = set()

        # Token encoder for counting
        self.encoder = tiktoken.encoding_for_model("gpt-4o")

        logger.info(
            f"Initialized CostManager: budget=${self.total_budget:.2f}, "
            f"mode={self.budget_mode.value}, strategy={self.allocation_strategy.value}"
        )

    def allocate_budgets(
        self,
        playlist_specs: List[Tuple[str, Dict]]
    ) -> Dict[str, float]:
        """
        Allocate budgets to playlists based on strategy.

        Args:
            playlist_specs: List of (playlist_id, spec_dict) tuples
                spec_dict should contain: target_track_count, constraints, etc.

        Returns:
            Dictionary mapping playlist_id to allocated budget

        Raises:
            ValueError: If playlist_specs is empty
        """
        if not playlist_specs:
            raise ValueError("playlist_specs cannot be empty")

        if self.allocation_strategy == AllocationStrategy.EQUAL:
            return self._allocate_equal(playlist_specs)
        else:
            return self._allocate_dynamic(playlist_specs)

    def _allocate_equal(
        self,
        playlist_specs: List[Tuple[str, Dict]]
    ) -> Dict[str, Decimal]:
        """Allocate budget equally across playlists."""
        budget_per_playlist = self.total_budget / len(playlist_specs)

        allocations = {}
        for playlist_id, _ in playlist_specs:
            allocation = BudgetAllocation(
                playlist_id=playlist_id,
                allocated_budget=budget_per_playlist
            )
            self.allocations[playlist_id] = allocation
            allocations[playlist_id] = budget_per_playlist

            logger.debug(
                f"Equal allocation for {playlist_id}: ${budget_per_playlist:.2f}"
            )

        return allocations

    def allocate_budget_equal(self, count: int) -> List[Decimal]:
        """
        Allocate budget equally across a number of playlists.

        Args:
            count: Number of playlists to allocate for

        Returns:
            List of Decimal budget amounts (one per playlist)
        """
        budget_per_playlist = self.total_budget / count
        return [budget_per_playlist] * count

    def _allocate_dynamic(
        self,
        playlist_specs: List[Tuple[str, Dict]]
    ) -> Dict[str, Decimal]:
        """Allocate budget dynamically based on complexity."""
        # Calculate complexity scores
        complexities = []
        for playlist_id, spec in playlist_specs:
            complexity = self._calculate_complexity(spec)
            complexities.append((playlist_id, Decimal(str(complexity))))

        total_complexity = sum(c for _, c in complexities)

        # Allocate proportionally
        allocations = {}
        for playlist_id, complexity in complexities:
            proportion = complexity / total_complexity
            allocated = self.total_budget * proportion

            allocation = BudgetAllocation(
                playlist_id=playlist_id,
                allocated_budget=allocated
            )
            self.allocations[playlist_id] = allocation
            allocations[playlist_id] = allocated

            logger.debug(
                f"Dynamic allocation for {playlist_id}: ${allocated:.2f} "
                f"(complexity={complexity:.2f})"
            )

        return allocations

    def _calculate_complexity(self, spec: Dict) -> float:
        """
        Calculate playlist complexity score for dynamic allocation.

        Factors:
        - Target track count (more tracks = higher cost)
        - Number of constraints (more constraints = more AI iterations)
        - Specialty requirements (tighter constraints = higher cost)

        Args:
            spec: Playlist specification dictionary

        Returns:
            Complexity score (1.0 = baseline)
        """
        # Base complexity from track count
        target_count = spec.get("target_track_count_max", 50)
        complexity = target_count / 50.0  # Normalize to 50 tracks = 1.0

        # Constraint complexity
        constraints = spec.get("track_selection_criteria", {})

        # BPM constraints (tight ranges = higher complexity)
        bpm_ranges = constraints.get("bpm_ranges", [])
        if bpm_ranges:
            avg_range = sum(r["max"] - r["min"] for r in bpm_ranges) / len(bpm_ranges)
            if avg_range < 20:
                complexity *= 1.3  # Very tight BPM = 30% more complex

        # Genre mix complexity (more genres = more iterations)
        genre_mix = constraints.get("genre_mix", {})
        if len(genre_mix) > 5:
            complexity *= 1.2

        # Specialty constraints
        specialty = constraints.get("specialty_constraints", {})
        if specialty:
            complexity *= 1.5  # Specialty playlists are more complex

        return max(complexity, 0.5)  # Minimum 0.5x complexity

    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text using tiktoken.

        Args:
            text: Text to count tokens for

        Returns:
            Number of tokens
        """
        return len(self.encoder.encode(text))

    def calculate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        model: str = "gpt-4o"
    ) -> Decimal:
        """
        Calculate cost for token usage.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            model: Model name (default: gpt-4o)

        Returns:
            Cost in USD as Decimal
        """
        pricing = self.PRICING.get(model, self.PRICING["gpt-4o"])

        input_cost = Decimal(input_tokens) * pricing["input"]
        output_cost = Decimal(output_tokens) * pricing["output"]

        return input_cost + output_cost

    def record_cost(
        self,
        cost_or_operation_id: any,
        input_tokens_or_playlist_id: any = None,
        output_tokens: Optional[int] = None,
        model: str = "gpt-4o",
        playlist_id: Optional[str] = None
    ) -> CostRecord:
        """
        Record cost for an operation and check budget.

        Supports two call signatures:
        1. record_cost(cost: Decimal, playlist_id: str)  # Direct cost recording
        2. record_cost(operation_id: str, input_tokens: int, output_tokens: int, ...)  # Token-based

        Args:
            cost_or_operation_id: Either a Decimal cost amount or operation ID string
            input_tokens_or_playlist_id: Either number of input tokens or playlist ID
            output_tokens: Number of output tokens (token-based signature only)
            model: Model name
            playlist_id: Associated playlist ID (token-based signature only)

        Returns:
            CostRecord object

        Raises:
            BudgetExceededError: If hard budget exceeded
        """
        # Detect which signature is being used
        if isinstance(cost_or_operation_id, (Decimal, float, int)) and \
           isinstance(input_tokens_or_playlist_id, str) and \
           output_tokens is None:
            # Signature: record_cost(cost: Decimal, playlist_id: str)
            cost = Decimal(str(cost_or_operation_id))
            playlist_id = input_tokens_or_playlist_id
            operation_id = f"direct-cost-{len(self.cost_records)}"
            input_tokens = 0
            output_tokens_val = 0
        else:
            # Signature: record_cost(operation_id, input_tokens, output_tokens, ...)
            operation_id = str(cost_or_operation_id)
            input_tokens = int(input_tokens_or_playlist_id)
            output_tokens_val = int(output_tokens) if output_tokens is not None else 0
            cost = self.calculate_cost(input_tokens, output_tokens_val, model)

        # Check budget BEFORE recording cost (for hard mode)
        if self.budget_mode == BudgetMode.HARD:
            total_spent = self.get_total_spent()
            if total_spent + cost > self.total_budget:
                raise BudgetExceededError(
                    f"Total budget would be exceeded: "
                    f"current=${total_spent:.2f}, "
                    f"new_cost=${cost:.2f}, "
                    f"budget=${self.total_budget:.2f}"
                )

        record = CostRecord(
            operation_id=operation_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens_val,
            cost_usd=cost,
            model=model
        )

        self.cost_records.append(record)

        # Update allocation if playlist specified
        if playlist_id and playlist_id in self.allocations:
            allocation = self.allocations[playlist_id]
            allocation.spent += cost

            logger.debug(
                f"Cost recorded for {playlist_id}: ${cost:.4f} "
                f"(remaining: ${allocation.remaining:.4f})"
            )

            # Check allocation budget
            if allocation.remaining < 0:
                if self.budget_mode == BudgetMode.HARD:
                    raise BudgetExceededError(
                        f"Budget exceeded for {playlist_id}: "
                        f"allocated=${allocation.allocated_budget:.2f}, "
                        f"spent=${allocation.spent:.2f}"
                    )
                else:
                    logger.warning(
                        f"Budget exceeded for {playlist_id} (suggested mode): "
                        f"allocated=${allocation.allocated_budget:.2f}, "
                        f"spent=${allocation.spent:.2f}"
                    )

        # Check total budget
        total_spent = self.get_total_spent()
        remaining = self.total_budget - total_spent

        # Check warning thresholds (for suggested mode)
        if self.budget_mode == BudgetMode.SUGGESTED:
            percentage_used = total_spent / self.total_budget
            for threshold in self._warning_thresholds:
                threshold_key = str(threshold)
                if percentage_used >= threshold and threshold_key not in self._warnings_issued:
                    self._warnings_issued.add(threshold_key)
                    warning_data = {
                        'threshold': float(threshold * 100),
                        'budget': float(self.total_budget),
                        'spent': float(total_spent),
                        'remaining': float(remaining),
                        'percentage_used': float(percentage_used * 100)
                    }
                    if self.on_warning:
                        self.on_warning(warning_data)
                    logger.warning(
                        f"Budget warning: {warning_data['percentage_used']:.1f}% of budget used "
                        f"(${total_spent:.2f}/${self.total_budget:.2f})"
                    )

        if remaining < 0:
            if self.budget_mode == BudgetMode.HARD:
                raise BudgetExceededError(
                    f"Total budget exceeded: "
                    f"budget=${self.total_budget:.2f}, "
                    f"spent=${total_spent:.2f}"
                )
            else:
                logger.warning(
                    f"Total budget exceeded (suggested mode): "
                    f"budget=${self.total_budget:.2f}, "
                    f"spent=${total_spent:.2f}"
                )

        return record

    def get_total_spent(self) -> Decimal:
        """
        Get total cost spent across all operations.

        Returns:
            Total cost in USD as Decimal
        """
        return sum(r.cost_usd for r in self.cost_records) if self.cost_records else Decimal("0.0")

    def get_total_cost(self) -> Decimal:
        """
        Get total cost spent (alias for get_total_spent).

        Returns:
            Total cost in USD as Decimal
        """
        return self.get_total_spent()

    def get_remaining_budget(self) -> Decimal:
        """
        Get remaining budget.

        Returns:
            Remaining budget in USD as Decimal
        """
        return self.total_budget - self.get_total_spent()

    def get_budget_status(self) -> Dict:
        """
        Get comprehensive budget status.

        Returns:
            Dictionary with budget status including:
            - total_budget: Total budget amount
            - used: Amount spent so far
            - remaining: Amount remaining
            - percentage_used: Percentage of budget used
            - overrun: Amount over budget (if exceeded, otherwise 0)
        """
        total_spent = self.get_total_spent()
        remaining = self.get_remaining_budget()
        percentage_used = (total_spent / self.total_budget * 100) if self.total_budget > 0 else Decimal("0.0")
        overrun = max(Decimal("0.0"), total_spent - self.total_budget)

        return {
            'total_budget': self.total_budget,
            'used': total_spent,
            'remaining': remaining,
            'percentage_used': float(percentage_used),
            'overrun': overrun
        }

    def get_allocation_status(self, playlist_id: str) -> Optional[BudgetAllocation]:
        """
        Get budget allocation status for playlist.

        Args:
            playlist_id: Playlist identifier

        Returns:
            BudgetAllocation object or None if not allocated
        """
        return self.allocations.get(playlist_id)

    def get_cost_summary(self) -> Dict:
        """
        Get summary of all costs and allocations.

        Returns:
            Dictionary with cost summary statistics
        """
        return {
            "total_budget": self.total_budget,
            "total_spent": self.get_total_spent(),
            "remaining": self.get_remaining_budget(),
            "budget_mode": self.budget_mode.value,
            "allocation_strategy": self.allocation_strategy.value,
            "num_operations": len(self.cost_records),
            "allocations": {
                pid: {
                    "allocated": alloc.allocated_budget,
                    "spent": alloc.spent,
                    "remaining": alloc.remaining
                }
                for pid, alloc in self.allocations.items()
            }
        }


def test_cost_manager():
    """Test cost manager functionality."""
    # Test equal allocation
    manager = CostManager(total_budget=10.0, allocation_strategy="equal")

    specs = [
        ("playlist_1", {"target_track_count_max": 50}),
        ("playlist_2", {"target_track_count_max": 50})
    ]

    allocations = manager.allocate_budgets(specs)
    assert allocations["playlist_1"] == 5.0, "Equal allocation should be $5.00 each"
    assert allocations["playlist_2"] == 5.0, "Equal allocation should be $5.00 each"

    # Test cost recording
    record = manager.record_cost(
        operation_id="test_op",
        input_tokens=1000,
        output_tokens=500,
        playlist_id="playlist_1"
    )

    assert record.cost_usd > 0, "Cost should be calculated"
    assert manager.get_total_spent() > 0, "Total spent should be tracked"

    # Test budget warning (suggested mode)
    try:
        # Record excessive cost
        for i in range(100):
            manager.record_cost(
                operation_id=f"op_{i}",
                input_tokens=10000,
                output_tokens=5000,
                playlist_id="playlist_1"
            )
    except BudgetExceededError:
        assert False, "Suggested mode should not raise exception"

    print("✓ Cost manager test passed")


if __name__ == "__main__":
    test_cost_manager()
