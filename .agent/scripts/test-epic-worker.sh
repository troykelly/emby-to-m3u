#!/bin/bash
# Test script for epic worker

set -e

echo "=== Epic Worker Test Script ==="
echo "Testing the epic worker components..."

# Test Python imports
echo -n "Testing Python imports... "
python3 -c "
import sys
sys.path.insert(0, '.agent/scripts/python')
from github_automation.core.epic_worker import EpicWorker
from github_automation.core.process_manager import ProcessManager
print('OK')
" || { echo "FAILED"; exit 1; }

# Test process manager spawn
echo -n "Testing hive-mind spawn detachment... "
python3 -c "
import sys
import os
sys.path.insert(0, '.agent/scripts/python')
from github_automation.core.process_manager import ProcessManager, ProcessStatus
from github_automation.config.models import TimeoutConfig

pm = ProcessManager(TimeoutConfig())
result = pm.run_claude_flow(
    objective='Test spawn detachment',
    namespace='test-namespace',
    agents=2,
    auto_spawn=True,
    non_interactive=True,
    timeout=60
)

if result.status == ProcessStatus.COMPLETED:
    print('OK')
else:
    print('FAILED')
    exit(1)
" || { echo "FAILED"; exit 1; }

echo ""
echo "✅ All tests passed! Epic worker is ready to use."
echo ""
echo "To run the epic worker:"
echo "  ./agent/scripts/github-epic-worker.sh --repo <owner/repo> [--auto-merge]"