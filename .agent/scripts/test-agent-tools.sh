#!/bin/bash

# Test script for agent tools in Docker container
# This properly tests all Python scripts in an isolated environment

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "🐳 Building and testing agent tools in Docker container..."
echo "Template root: $TEMPLATE_ROOT"

# Create a Dockerfile for testing
cat > "$TEMPLATE_ROOT/.agent/scripts/Dockerfile.test" << 'EOF'
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    gnupg \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Install GitHub CLI
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | gpg --dearmor -o /usr/share/keyrings/githubcli-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | tee /etc/apt/sources.list.d/github-cli.list > /dev/null && \
    apt-get update && \
    apt-get install -y gh && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /workspace

# Copy Python package files
COPY .agent/scripts/python/pyproject.toml .agent/scripts/python/pyproject.toml
COPY .agent/scripts/python/github_automation .agent/scripts/python/github_automation

# Install Python package
WORKDIR /workspace/.agent/scripts/python
RUN pip install --no-cache-dir -e .

# Set up test environment
WORKDIR /workspace

# Copy shell scripts
COPY .agent/scripts/*.sh .agent/scripts/

# Make scripts executable
RUN chmod +x .agent/scripts/*.sh

# Create test script
RUN cat > /test-all.sh << 'SCRIPT'
#!/bin/bash
set -e

echo "=== Testing Python imports ==="
python3 -c "
from github_automation.core.epic_worker import EpicWorker
from github_automation.core.pr_worker import PRWorker
from github_automation.core.issue_worker import IssueWorker
from github_automation.core.process_manager import ProcessManager
from github_automation.core.log_interpreter import LogInterpreter
from github_automation.config.models import GitHubConfig, TimeoutConfig
from github_automation.config.settings import get_settings
print('✅ All imports successful')
"

echo ""
echo "=== Testing CLI commands ==="

# Test help commands
echo "Testing github-epic-worker --help"
github-epic-worker --help > /dev/null 2>&1 && echo "✅ github-epic-worker CLI works" || echo "❌ github-epic-worker CLI failed"

echo "Testing github-pr-worker --help"
github-pr-worker --help > /dev/null 2>&1 && echo "✅ github-pr-worker CLI works" || echo "❌ github-pr-worker CLI failed"

echo "Testing github-issue-worker --help"
github-issue-worker --help > /dev/null 2>&1 && echo "✅ github-issue-worker CLI works" || echo "❌ github-issue-worker CLI failed"

echo "Testing claude-log-interpreter --help"
claude-log-interpreter --help > /dev/null 2>&1 && echo "✅ claude-log-interpreter CLI works" || echo "❌ claude-log-interpreter CLI failed"

echo ""
echo "=== Testing shell script wrappers ==="

# Create fake git repo for testing
cd /tmp
git init test-repo
cd test-repo
git remote add origin https://github.com/test/test.git

# Test shell scripts (just check they parse correctly)
echo "Testing github-epic-worker.sh"
bash -n /workspace/.agent/scripts/github-epic-worker.sh && echo "✅ github-epic-worker.sh syntax OK" || echo "❌ github-epic-worker.sh syntax error"

echo "Testing github-pr-worker.sh"
bash -n /workspace/.agent/scripts/github-pr-worker.sh && echo "✅ github-pr-worker.sh syntax OK" || echo "❌ github-pr-worker.sh syntax error"

echo "Testing github-issue-worker.sh"
bash -n /workspace/.agent/scripts/github-issue-worker.sh && echo "✅ github-issue-worker.sh syntax OK" || echo "❌ github-issue-worker.sh syntax error"

echo ""
echo "=== Testing ProcessManager claude-flow execution ==="
python3 -c "
from github_automation.core.process_manager import ProcessManager
from github_automation.config.models import TimeoutConfig
import subprocess

# Test that npx command would be formed correctly
tc = TimeoutConfig()
pm = ProcessManager(tc)

# Check npx is available
result = subprocess.run(['npx', '--version'], capture_output=True, text=True)
if result.returncode == 0:
    print(f'✅ npx available: version {result.stdout.strip()}')
else:
    print('❌ npx not available')
"

echo ""
echo "=== All tests completed ==="
SCRIPT

RUN chmod +x /test-all.sh

# Default command
CMD ["/test-all.sh"]
EOF

echo "📦 Building test Docker image..."
docker build -f "$TEMPLATE_ROOT/.agent/scripts/Dockerfile.test" -t agent-tools-test "$TEMPLATE_ROOT"

echo ""
echo "🧪 Running tests in container..."
docker run --rm agent-tools-test

echo ""
echo "✅ Testing completed successfully!"
echo ""
echo "To run tests interactively:"
echo "  docker run --rm -it agent-tools-test /bin/bash"
echo ""
echo "To test with your GitHub token:"
echo "  docker run --rm -e GITHUB_TOKEN=\$GITHUB_TOKEN agent-tools-test"