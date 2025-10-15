"""
LLM API cost management service.

Tracks and manages costs for OpenAI API calls:
- Token usage tracking using tiktoken
- Budget enforcement (hard limits and soft warnings)
- Dynamic vs equal cost allocation strategies
- Per-agent cost tracking
- Cost reporting and analytics

Supports two budget modes:
- HARD: Strict enforcement, raises error when budget exceeded
- SUGGESTED: Soft limits, logs warnings but allows continuation
"""

import os
import json
from pathlib import Path
from typing import Optional, Dict, Any, Literal
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum


class BudgetMode(Enum):
    """Budget enforcement mode."""
    HARD = "hard"  # Strict enforcement
    SUGGESTED = "suggested"  # Soft warnings


class AllocationStrategy(Enum):
    """Cost allocation strategy."""
    EQUAL = "equal"  # Equal budget for all agents
    DYNAMIC = "dynamic"  # Weighted by agent priority/complexity


class BudgetExceededError(Exception):
    """Raised when hard budget limit is exceeded."""
    pass


@dataclass
class CostRecord:
    """Record of API cost for a single operation."""
    timestamp: str
    agent_id: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float
    operation: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CostRecord":
        """Create from dictionary."""
        return cls(**data)


class CostManagerService:
    """
    Service for tracking and managing LLM API costs.

    Features:
    - Real-time cost tracking with tiktoken
    - Hard/soft budget limits
    - Per-agent budget allocation
    - Cost analytics and reporting
    - Persistent cost history

    Example:
        >>> manager = CostManagerService(
        ...     total_budget_usd=10.0,
        ...     mode=BudgetMode.HARD,
        ...     allocation_strategy=AllocationStrategy.DYNAMIC
        ... )
        >>> manager.track_usage("agent-1", "gpt-4", 1000, 500)
        >>> print(f"Spent: ${manager.get_total_spent():.2f}")
    """

    # Pricing per 1K tokens (as of 2024)
    PRICING = {
        "gpt-4": {"input": 0.03, "output": 0.06},
        "gpt-4-turbo": {"input": 0.01, "output": 0.03},
        "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
        "gpt-4o": {"input": 0.005, "output": 0.015},
        "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    }

    def __init__(
        self,
        total_budget_usd: float = 10.0,
        mode: BudgetMode = BudgetMode.SUGGESTED,
        allocation_strategy: AllocationStrategy = AllocationStrategy.EQUAL,
        cost_log: Optional[str] = None,
        agent_weights: Optional[Dict[str, float]] = None
    ):
        """
        Initialize cost manager.

        Args:
            total_budget_usd: Total budget in USD
            mode: Budget enforcement mode (HARD or SUGGESTED)
            allocation_strategy: How to allocate budget among agents
            cost_log: Path to cost log file (default: ~/.ai_playlist/cost_log.jsonl)
            agent_weights: Weights for dynamic allocation (agent_id -> weight)
        """
        self.total_budget_usd = total_budget_usd
        self.mode = mode
        self.allocation_strategy = allocation_strategy
        self.agent_weights = agent_weights or {}

        if cost_log is None:
            cost_dir = Path.home() / ".ai_playlist"
            cost_dir.mkdir(exist_ok=True)
            cost_log = str(cost_dir / "cost_log.jsonl")

        self.cost_log = Path(cost_log)
        self.cost_log.parent.mkdir(parents=True, exist_ok=True)

        # In-memory tracking
        self._cost_records: list[CostRecord] = []
        self._agent_budgets: Dict[str, float] = {}
        self._agent_spent: Dict[str, float] = {}

        # Load existing cost history
        self._load_cost_history()

    def _load_cost_history(self):
        """Load cost history from log file."""
        if not self.cost_log.exists():
            return

        with open(self.cost_log, "r") as f:
            for line in f:
                try:
                    record = CostRecord.from_dict(json.loads(line.strip()))
                    self._cost_records.append(record)

                    # Update agent spent totals
                    agent_id = record.agent_id
                    self._agent_spent[agent_id] = (
                        self._agent_spent.get(agent_id, 0.0) + record.cost_usd
                    )
                except (json.JSONDecodeError, TypeError):
                    continue

    def allocate_budgets(self, agent_ids: list[str]):
        """
        Allocate budgets to agents based on strategy.

        Args:
            agent_ids: List of agent IDs to allocate budgets to
        """
        if self.allocation_strategy == AllocationStrategy.EQUAL:
            # Equal budget for all agents
            budget_per_agent = self.total_budget_usd / len(agent_ids)
            self._agent_budgets = {
                agent_id: budget_per_agent for agent_id in agent_ids
            }

        else:  # DYNAMIC
            # Weighted allocation based on agent weights
            total_weight = sum(
                self.agent_weights.get(agent_id, 1.0) for agent_id in agent_ids
            )

            self._agent_budgets = {
                agent_id: (
                    self.total_budget_usd *
                    self.agent_weights.get(agent_id, 1.0) / total_weight
                )
                for agent_id in agent_ids
            }

    def track_usage(
        self,
        agent_id: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        operation: str = "unknown"
    ) -> float:
        """
        Track API usage and calculate cost.

        Args:
            agent_id: Agent identifier
            model: Model name (e.g., "gpt-4")
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            operation: Description of operation

        Returns:
            Cost in USD for this operation

        Raises:
            BudgetExceededError: If hard budget limit exceeded
        """
        # Calculate cost
        pricing = self.PRICING.get(model, self.PRICING["gpt-4"])
        cost = (
            (input_tokens / 1000) * pricing["input"] +
            (output_tokens / 1000) * pricing["output"]
        )

        # Create cost record
        record = CostRecord(
            timestamp=datetime.now().isoformat(),
            agent_id=agent_id,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            cost_usd=cost,
            operation=operation
        )

        # Update tracking
        self._cost_records.append(record)
        self._agent_spent[agent_id] = self._agent_spent.get(agent_id, 0.0) + cost

        # Save to log
        with open(self.cost_log, "a") as f:
            f.write(json.dumps(record.to_dict()) + "\n")

        # Check budget limits
        self._check_budget(agent_id, cost)

        return cost

    def _check_budget(self, agent_id: str, new_cost: float):
        """Check if budget limits are exceeded."""
        total_spent = self.get_total_spent()
        agent_spent = self._agent_spent.get(agent_id, 0.0)

        # Check total budget
        if total_spent > self.total_budget_usd:
            message = (
                f"Total budget exceeded: ${total_spent:.2f} / ${self.total_budget_usd:.2f}"
            )
            if self.mode == BudgetMode.HARD:
                raise BudgetExceededError(message)
            else:
                print(f"⚠️  WARNING: {message}")

        # Check agent budget
        if agent_id in self._agent_budgets:
            agent_budget = self._agent_budgets[agent_id]
            if agent_spent > agent_budget:
                message = (
                    f"Agent {agent_id} budget exceeded: "
                    f"${agent_spent:.2f} / ${agent_budget:.2f}"
                )
                if self.mode == BudgetMode.HARD:
                    raise BudgetExceededError(message)
                else:
                    print(f"⚠️  WARNING: {message}")

        # Warn at 80% threshold
        if total_spent > 0.8 * self.total_budget_usd:
            remaining = self.total_budget_usd - total_spent
            print(
                f"⚠️  WARNING: 80% of budget used. "
                f"Remaining: ${remaining:.2f}"
            )

    def get_total_spent(self) -> float:
        """Get total amount spent across all agents."""
        return sum(self._agent_spent.values())

    def get_agent_spent(self, agent_id: str) -> float:
        """Get amount spent by specific agent."""
        return self._agent_spent.get(agent_id, 0.0)

    def get_remaining_budget(self) -> float:
        """Get remaining total budget."""
        return max(0.0, self.total_budget_usd - self.get_total_spent())

    def get_agent_remaining(self, agent_id: str) -> float:
        """Get remaining budget for specific agent."""
        if agent_id not in self._agent_budgets:
            return float('inf')  # No limit

        spent = self._agent_spent.get(agent_id, 0.0)
        return max(0.0, self._agent_budgets[agent_id] - spent)

    def get_cost_summary(self) -> Dict[str, Any]:
        """Get comprehensive cost summary."""
        total_spent = self.get_total_spent()

        return {
            "total_budget_usd": self.total_budget_usd,
            "total_spent_usd": total_spent,
            "remaining_usd": self.get_remaining_budget(),
            "budget_used_percent": (total_spent / self.total_budget_usd * 100),
            "mode": self.mode.value,
            "allocation_strategy": self.allocation_strategy.value,
            "agent_spending": {
                agent_id: {
                    "spent_usd": spent,
                    "budget_usd": self._agent_budgets.get(agent_id),
                    "remaining_usd": self.get_agent_remaining(agent_id)
                }
                for agent_id, spent in self._agent_spent.items()
            },
            "total_operations": len(self._cost_records),
            "total_tokens": sum(r.total_tokens for r in self._cost_records)
        }

    def estimate_tokens(self, text: str, model: str = "gpt-4") -> int:
        """
        Estimate token count for text using tiktoken.

        Args:
            text: Text to estimate
            model: Model name for encoding

        Returns:
            Estimated token count
        """
        try:
            import tiktoken

            encoding = tiktoken.encoding_for_model(model)
            return len(encoding.encode(text))
        except Exception:
            # Fallback: rough estimate of 4 characters per token
            return len(text) // 4

    def can_afford(self, estimated_tokens: int, model: str = "gpt-4") -> bool:
        """
        Check if operation is affordable within budget.

        Args:
            estimated_tokens: Estimated total tokens
            model: Model name

        Returns:
            True if operation is affordable
        """
        pricing = self.PRICING.get(model, self.PRICING["gpt-4"])
        # Assume 50/50 split for input/output
        estimated_cost = (
            (estimated_tokens / 2 / 1000) * pricing["input"] +
            (estimated_tokens / 2 / 1000) * pricing["output"]
        )

        return estimated_cost <= self.get_remaining_budget()

    def reset(self):
        """Reset all cost tracking (keeps history file)."""
        self._cost_records = []
        self._agent_budgets = {}
        self._agent_spent = {}
