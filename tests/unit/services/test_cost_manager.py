"""
Unit tests for CostManagerService.

Tests cover:
- Hard vs suggested budget modes
- Dynamic vs equal allocation strategies
- Token tracking with tiktoken
- Budget enforcement and warnings
- Cost reporting and analytics
- Per-agent tracking
"""

import os
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from ai_playlist.services.cost_manager import (
    CostManagerService,
    BudgetMode,
    AllocationStrategy,
    BudgetExceededError,
    CostRecord,
)


class TestCostRecord:
    """Test CostRecord dataclass."""

    def test_cost_record_creation(self):
        """Test creating a cost record."""
        record = CostRecord(
            timestamp="2024-01-01T00:00:00",
            agent_id="agent-1",
            model="gpt-4",
            input_tokens=1000,
            output_tokens=500,
            total_tokens=1500,
            cost_usd=0.045,
            operation="test_operation"
        )

        assert record.agent_id == "agent-1"
        assert record.model == "gpt-4"
        assert record.total_tokens == 1500
        assert record.cost_usd == 0.045

    def test_cost_record_to_dict(self):
        """Test converting cost record to dictionary."""
        record = CostRecord(
            timestamp="2024-01-01T00:00:00",
            agent_id="agent-1",
            model="gpt-4",
            input_tokens=1000,
            output_tokens=500,
            total_tokens=1500,
            cost_usd=0.045,
            operation="test"
        )

        data = record.to_dict()

        assert isinstance(data, dict)
        assert data["agent_id"] == "agent-1"
        assert data["total_tokens"] == 1500

    def test_cost_record_from_dict(self):
        """Test creating cost record from dictionary."""
        data = {
            "timestamp": "2024-01-01T00:00:00",
            "agent_id": "agent-1",
            "model": "gpt-4",
            "input_tokens": 1000,
            "output_tokens": 500,
            "total_tokens": 1500,
            "cost_usd": 0.045,
            "operation": "test"
        }

        record = CostRecord.from_dict(data)

        assert record.agent_id == "agent-1"
        assert record.cost_usd == 0.045


class TestCostManagerInit:
    """Test CostManagerService initialization."""

    def test_init_default(self):
        """Test initialization with defaults."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cost_log = Path(tmp_dir) / "cost.jsonl"

            manager = CostManagerService(cost_log=str(cost_log))

            assert manager.total_budget_usd == 10.0
            assert manager.mode == BudgetMode.SUGGESTED
            assert manager.allocation_strategy == AllocationStrategy.EQUAL
            assert manager.cost_log == cost_log

    def test_init_custom_params(self):
        """Test initialization with custom parameters."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cost_log = Path(tmp_dir) / "cost.jsonl"

            manager = CostManagerService(
                total_budget_usd=50.0,
                mode=BudgetMode.HARD,
                allocation_strategy=AllocationStrategy.DYNAMIC,
                cost_log=str(cost_log),
                agent_weights={"agent-1": 2.0, "agent-2": 1.0}
            )

            assert manager.total_budget_usd == 50.0
            assert manager.mode == BudgetMode.HARD
            assert manager.allocation_strategy == AllocationStrategy.DYNAMIC
            assert manager.agent_weights == {"agent-1": 2.0, "agent-2": 1.0}

    def test_init_creates_cost_log_directory(self):
        """Test cost log directory is created."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cost_log = Path(tmp_dir) / "nested" / "dirs" / "cost.jsonl"

            manager = CostManagerService(cost_log=str(cost_log))

            assert cost_log.parent.exists()


class TestBudgetAllocation:
    """Test budget allocation strategies."""

    def test_equal_allocation(self):
        """Test equal budget allocation."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cost_log = Path(tmp_dir) / "cost.jsonl"

            manager = CostManagerService(
                total_budget_usd=10.0,
                allocation_strategy=AllocationStrategy.EQUAL,
                cost_log=str(cost_log)
            )

            agent_ids = ["agent-1", "agent-2", "agent-3"]
            manager.allocate_budgets(agent_ids)

            # Each agent should get equal share
            for agent_id in agent_ids:
                assert manager._agent_budgets[agent_id] == pytest.approx(10.0 / 3)

    def test_dynamic_allocation(self):
        """Test dynamic weighted allocation."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cost_log = Path(tmp_dir) / "cost.jsonl"

            manager = CostManagerService(
                total_budget_usd=10.0,
                allocation_strategy=AllocationStrategy.DYNAMIC,
                agent_weights={"agent-1": 3.0, "agent-2": 2.0, "agent-3": 1.0},
                cost_log=str(cost_log)
            )

            agent_ids = ["agent-1", "agent-2", "agent-3"]
            manager.allocate_budgets(agent_ids)

            # Total weights = 6.0
            # agent-1: 3/6 * 10 = 5.0
            # agent-2: 2/6 * 10 = 3.333
            # agent-3: 1/6 * 10 = 1.667
            assert manager._agent_budgets["agent-1"] == pytest.approx(5.0)
            assert manager._agent_budgets["agent-2"] == pytest.approx(10.0 * 2 / 6)
            assert manager._agent_budgets["agent-3"] == pytest.approx(10.0 * 1 / 6)

    def test_dynamic_allocation_default_weights(self):
        """Test dynamic allocation with default weights."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cost_log = Path(tmp_dir) / "cost.jsonl"

            manager = CostManagerService(
                total_budget_usd=10.0,
                allocation_strategy=AllocationStrategy.DYNAMIC,
                cost_log=str(cost_log)
            )

            # No weights specified - should use 1.0 for all
            agent_ids = ["agent-1", "agent-2"]
            manager.allocate_budgets(agent_ids)

            # With default weights, should be equal
            assert manager._agent_budgets["agent-1"] == pytest.approx(5.0)
            assert manager._agent_budgets["agent-2"] == pytest.approx(5.0)


class TestCostTracking:
    """Test cost tracking functionality."""

    def test_track_usage_basic(self):
        """Test basic cost tracking."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cost_log = Path(tmp_dir) / "cost.jsonl"

            manager = CostManagerService(cost_log=str(cost_log))

            cost = manager.track_usage(
                agent_id="agent-1",
                model="gpt-4",
                input_tokens=1000,
                output_tokens=500,
                operation="test"
            )

            # GPT-4: $0.03/1k input, $0.06/1k output
            # Cost = (1000/1000 * 0.03) + (500/1000 * 0.06) = 0.03 + 0.03 = 0.06
            assert cost == pytest.approx(0.06)

            # Verify tracking
            assert manager.get_total_spent() == pytest.approx(0.06)
            assert manager.get_agent_spent("agent-1") == pytest.approx(0.06)

    def test_track_usage_multiple_operations(self):
        """Test tracking multiple operations."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cost_log = Path(tmp_dir) / "cost.jsonl"

            manager = CostManagerService(cost_log=str(cost_log))

            # Track 3 operations
            manager.track_usage("agent-1", "gpt-4", 1000, 500)
            manager.track_usage("agent-1", "gpt-4", 2000, 1000)
            manager.track_usage("agent-2", "gpt-4", 500, 250)

            # Total: (1000+500)*0.03/1k + (2000+1000)*0.06/1k + (500+250)*0.03/1k
            total = manager.get_total_spent()
            assert total > 0

            # agent-1 should have more spent than agent-2
            assert manager.get_agent_spent("agent-1") > manager.get_agent_spent("agent-2")

    def test_track_usage_different_models(self):
        """Test tracking with different models."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cost_log = Path(tmp_dir) / "cost.jsonl"

            manager = CostManagerService(cost_log=str(cost_log))

            # GPT-4: More expensive
            cost_gpt4 = manager.track_usage("agent-1", "gpt-4", 1000, 1000)

            # GPT-3.5-turbo: Cheaper
            cost_gpt35 = manager.track_usage("agent-2", "gpt-3.5-turbo", 1000, 1000)

            # GPT-4 should cost more
            assert cost_gpt4 > cost_gpt35

    def test_track_usage_saves_to_log(self):
        """Test usage is saved to log file."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cost_log = Path(tmp_dir) / "cost.jsonl"

            manager = CostManagerService(cost_log=str(cost_log))

            manager.track_usage("agent-1", "gpt-4", 1000, 500, "operation-1")
            manager.track_usage("agent-2", "gpt-4", 2000, 1000, "operation-2")

            # Verify log file
            assert cost_log.exists()

            lines = cost_log.read_text().strip().split("\n")
            assert len(lines) == 2

            # Parse first record
            record = json.loads(lines[0])
            assert record["agent_id"] == "agent-1"
            assert record["operation"] == "operation-1"

    def test_load_cost_history(self):
        """Test loading existing cost history."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cost_log = Path(tmp_dir) / "cost.jsonl"

            # Create log with existing records
            record1 = CostRecord(
                timestamp="2024-01-01T00:00:00",
                agent_id="agent-1",
                model="gpt-4",
                input_tokens=1000,
                output_tokens=500,
                total_tokens=1500,
                cost_usd=0.06,
                operation="test"
            )

            with open(cost_log, "w") as f:
                f.write(json.dumps(record1.to_dict()) + "\n")

            # Create manager - should load history
            manager = CostManagerService(cost_log=str(cost_log))

            assert manager.get_total_spent() == pytest.approx(0.06)
            assert manager.get_agent_spent("agent-1") == pytest.approx(0.06)


class TestBudgetEnforcement:
    """Test budget enforcement."""

    def test_hard_mode_raises_on_exceeded(self):
        """Test hard mode raises error when budget exceeded."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cost_log = Path(tmp_dir) / "cost.jsonl"

            manager = CostManagerService(
                total_budget_usd=0.10,  # Very small budget
                mode=BudgetMode.HARD,
                cost_log=str(cost_log)
            )

            # First operation should succeed
            manager.track_usage("agent-1", "gpt-4", 1000, 500)

            # Second operation should exceed budget
            with pytest.raises(BudgetExceededError, match="Total budget exceeded"):
                manager.track_usage("agent-1", "gpt-4", 2000, 1000)

    def test_suggested_mode_allows_exceeded(self, capsys):
        """Test suggested mode allows exceeding budget with warning."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cost_log = Path(tmp_dir) / "cost.jsonl"

            manager = CostManagerService(
                total_budget_usd=0.05,
                mode=BudgetMode.SUGGESTED,
                cost_log=str(cost_log)
            )

            # Exceed budget - should warn but not raise
            manager.track_usage("agent-1", "gpt-4", 1000, 500)
            manager.track_usage("agent-1", "gpt-4", 1000, 500)

            # Should have warning in output
            captured = capsys.readouterr()
            assert "WARNING" in captured.out
            assert "budget exceeded" in captured.out.lower()

    def test_agent_budget_enforcement_hard(self):
        """Test per-agent budget enforcement in hard mode."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cost_log = Path(tmp_dir) / "cost.jsonl"

            manager = CostManagerService(
                total_budget_usd=10.0,
                mode=BudgetMode.HARD,
                cost_log=str(cost_log)
            )

            # Allocate budgets
            manager.allocate_budgets(["agent-1", "agent-2"])

            # agent-1 gets $5 budget
            # Try to exceed it
            with pytest.raises(BudgetExceededError, match="Agent agent-1 budget exceeded"):
                # Each call costs ~$0.06, so ~84 calls = $5
                for _ in range(100):
                    manager.track_usage("agent-1", "gpt-4", 1000, 500)

    def test_warning_at_80_percent(self, capsys):
        """Test warning at 80% budget threshold."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cost_log = Path(tmp_dir) / "cost.jsonl"

            manager = CostManagerService(
                total_budget_usd=0.10,
                mode=BudgetMode.SUGGESTED,
                cost_log=str(cost_log)
            )

            # Use exactly 80% of budget
            # Each operation costs $0.06, so need $0.08 total
            manager.track_usage("agent-1", "gpt-4", 1000, 500)  # $0.06

            # Next operation should trigger 80% warning
            manager.track_usage("agent-1", "gpt-4", 500, 250)  # +$0.03 = $0.09 (90%)

            captured = capsys.readouterr()
            assert "80% of budget used" in captured.out


class TestCostReporting:
    """Test cost reporting and analytics."""

    def test_get_total_spent(self):
        """Test getting total spent amount."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cost_log = Path(tmp_dir) / "cost.jsonl"

            manager = CostManagerService(cost_log=str(cost_log))

            assert manager.get_total_spent() == 0.0

            manager.track_usage("agent-1", "gpt-4", 1000, 500)
            manager.track_usage("agent-2", "gpt-4", 2000, 1000)

            total = manager.get_total_spent()
            assert total > 0
            assert total == pytest.approx(0.06 + 0.12)

    def test_get_agent_spent(self):
        """Test getting per-agent spending."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cost_log = Path(tmp_dir) / "cost.jsonl"

            manager = CostManagerService(cost_log=str(cost_log))

            manager.track_usage("agent-1", "gpt-4", 1000, 500)
            manager.track_usage("agent-2", "gpt-4", 2000, 1000)

            assert manager.get_agent_spent("agent-1") == pytest.approx(0.06)
            assert manager.get_agent_spent("agent-2") == pytest.approx(0.12)
            assert manager.get_agent_spent("agent-3") == 0.0  # Unknown agent

    def test_get_remaining_budget(self):
        """Test getting remaining budget."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cost_log = Path(tmp_dir) / "cost.jsonl"

            manager = CostManagerService(
                total_budget_usd=1.0,
                cost_log=str(cost_log)
            )

            assert manager.get_remaining_budget() == 1.0

            manager.track_usage("agent-1", "gpt-4", 1000, 500)

            remaining = manager.get_remaining_budget()
            assert remaining == pytest.approx(1.0 - 0.06)

    def test_get_agent_remaining(self):
        """Test getting per-agent remaining budget."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cost_log = Path(tmp_dir) / "cost.jsonl"

            manager = CostManagerService(
                total_budget_usd=10.0,
                cost_log=str(cost_log)
            )

            manager.allocate_budgets(["agent-1", "agent-2"])

            # Each agent gets $5
            assert manager.get_agent_remaining("agent-1") == pytest.approx(5.0)

            manager.track_usage("agent-1", "gpt-4", 1000, 500)

            assert manager.get_agent_remaining("agent-1") == pytest.approx(5.0 - 0.06)
            assert manager.get_agent_remaining("agent-2") == pytest.approx(5.0)

    def test_get_agent_remaining_no_limit(self):
        """Test agent with no budget limit."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cost_log = Path(tmp_dir) / "cost.jsonl"

            manager = CostManagerService(cost_log=str(cost_log))

            # No budgets allocated
            assert manager.get_agent_remaining("agent-1") == float('inf')

    def test_get_cost_summary(self):
        """Test comprehensive cost summary."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cost_log = Path(tmp_dir) / "cost.jsonl"

            manager = CostManagerService(
                total_budget_usd=10.0,
                mode=BudgetMode.HARD,
                allocation_strategy=AllocationStrategy.EQUAL,
                cost_log=str(cost_log)
            )

            manager.allocate_budgets(["agent-1", "agent-2"])
            manager.track_usage("agent-1", "gpt-4", 1000, 500)
            manager.track_usage("agent-2", "gpt-3.5-turbo", 2000, 1000)

            summary = manager.get_cost_summary()

            assert summary["total_budget_usd"] == 10.0
            assert summary["total_spent_usd"] > 0
            assert summary["remaining_usd"] < 10.0
            assert summary["budget_used_percent"] > 0
            assert summary["mode"] == "hard"
            assert summary["allocation_strategy"] == "equal"
            assert "agent-1" in summary["agent_spending"]
            assert "agent-2" in summary["agent_spending"]
            assert summary["total_operations"] == 2
            assert summary["total_tokens"] == 4500


class TestTokenEstimation:
    """Test token estimation functionality."""

    @patch('tiktoken.encoding_for_model')
    def test_estimate_tokens(self, mock_encoding):
        """Test token estimation with tiktoken."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cost_log = Path(tmp_dir) / "cost.jsonl"
            manager = CostManagerService(cost_log=str(cost_log))

            # Mock tiktoken encoding
            mock_enc = MagicMock()
            mock_enc.encode.return_value = [1, 2, 3, 4, 5]  # 5 tokens
            mock_encoding.return_value = mock_enc

            tokens = manager.estimate_tokens("Hello world", "gpt-4")

            assert tokens == 5
            mock_encoding.assert_called_once_with("gpt-4")

    def test_estimate_tokens_fallback(self):
        """Test token estimation fallback without tiktoken."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cost_log = Path(tmp_dir) / "cost.jsonl"
            manager = CostManagerService(cost_log=str(cost_log))

            with patch('tiktoken.encoding_for_model', side_effect=Exception()):
                # Should fall back to character count / 4
                text = "a" * 100
                tokens = manager.estimate_tokens(text, "gpt-4")

                assert tokens == 25  # 100 / 4

    def test_can_afford(self):
        """Test checking if operation is affordable."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cost_log = Path(tmp_dir) / "cost.jsonl"

            manager = CostManagerService(
                total_budget_usd=1.0,
                cost_log=str(cost_log)
            )

            # Small operation should be affordable
            assert manager.can_afford(1000, "gpt-4") is True

            # Huge operation should not be affordable
            assert manager.can_afford(1000000, "gpt-4") is False

    def test_can_afford_after_spending(self):
        """Test affordability check after spending."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cost_log = Path(tmp_dir) / "cost.jsonl"

            manager = CostManagerService(
                total_budget_usd=0.20,
                cost_log=str(cost_log)
            )

            # Initially affordable
            assert manager.can_afford(2000, "gpt-4") is True

            # Spend most of budget
            manager.track_usage("agent-1", "gpt-4", 1000, 500)
            manager.track_usage("agent-1", "gpt-4", 1000, 500)

            # Now not affordable
            assert manager.can_afford(2000, "gpt-4") is False


class TestCostManagerReset:
    """Test reset functionality."""

    def test_reset(self):
        """Test resetting cost tracking."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cost_log = Path(tmp_dir) / "cost.jsonl"

            manager = CostManagerService(cost_log=str(cost_log))

            # Track some usage
            manager.allocate_budgets(["agent-1"])
            manager.track_usage("agent-1", "gpt-4", 1000, 500)

            assert manager.get_total_spent() > 0
            assert len(manager._agent_budgets) > 0

            # Reset
            manager.reset()

            assert manager.get_total_spent() == 0.0
            assert len(manager._agent_budgets) == 0
            assert len(manager._cost_records) == 0

            # Log file should still exist
            assert cost_log.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
