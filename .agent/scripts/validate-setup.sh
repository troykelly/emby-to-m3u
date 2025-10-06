#!/bin/bash

# Aperim Template - Setup Validation Script
# Tests all installed tools and configuration

set -euo pipefail

# Colours for output (Australian spelling)
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Colour

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo -e "${BLUE}🔍 Aperim Template: Validating Setup...${NC}"
echo ""

# Counters
TESTS_TOTAL=0
TESTS_PASSED=0
TESTS_FAILED=0

# Function to run a test
run_test() {
    local test_name="$1"
    local test_command="$2"
    
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    echo -n -e "${BLUE}Testing $test_name...${NC} "
    
    if eval "$test_command" >/dev/null 2>&1; then
        echo -e "${GREEN}✅${NC}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        echo -e "${RED}❌${NC}"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

# Function to check file exists
check_file() {
    local file_path="$1"
    local description="$2"
    
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    echo -n -e "${BLUE}Checking $description...${NC} "
    
    if [ -f "$file_path" ]; then
        echo -e "${GREEN}✅${NC}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        echo -e "${RED}❌${NC} (not found: $file_path)"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

# Function to check directory exists
check_directory() {
    local dir_path="$1"
    local description="$2"
    
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    echo -n -e "${BLUE}Checking $description...${NC} "
    
    if [ -d "$dir_path" ]; then
        echo -e "${GREEN}✅${NC}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        echo -e "${RED}❌${NC} (not found: $dir_path)"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

echo -e "${YELLOW}=== Repository Structure ===${NC}"

# Check core directories
check_directory "$PROJECT_ROOT/.agent" ".agent directory"
check_directory "$PROJECT_ROOT/.agent/scripts" ".agent/scripts directory"
check_directory "$PROJECT_ROOT/.agent/configs" ".agent/configs directory"
check_directory "$PROJECT_ROOT/.agent/tools" ".agent/tools directory"
check_directory "$PROJECT_ROOT/.devcontainer" ".devcontainer directory"

# Check core files
check_file "$PROJECT_ROOT/.gitignore" ".gitignore file"
check_file "$PROJECT_ROOT/.gitattributes" ".gitattributes file"
check_file "$PROJECT_ROOT/.env.example" ".env.example file"

echo ""
echo -e "${YELLOW}=== Devcontainer Configuration ===${NC}"

# Check devcontainer files
check_file "$PROJECT_ROOT/.devcontainer/devcontainer.json" "devcontainer.json"
check_file "$PROJECT_ROOT/.devcontainer/docker-compose.yml" "docker-compose.yml"
check_file "$PROJECT_ROOT/.devcontainer/docker/Dockerfile" "Dockerfile"

echo ""
echo -e "${YELLOW}=== Management Scripts ===${NC}"

# Check management scripts
SCRIPTS=(
    "start-devcontainer.sh"
    "stop-devcontainer.sh"
    "exec-devcontainer.sh"
    "install-claude-flow.sh"
    "start-hive-mind.sh"
    "stop-hive-mind.sh"
    "install-agent-tools.sh"
    "init-repository.sh"
    "validate-setup.sh"
)

for script in "${SCRIPTS[@]}"; do
    check_file "$PROJECT_ROOT/.agent/scripts/$script" "$script"
    if [ -f "$PROJECT_ROOT/.agent/scripts/$script" ]; then
        run_test "$script executable" "test -x '$PROJECT_ROOT/.agent/scripts/$script'"
    fi
done

echo ""
echo -e "${YELLOW}=== System Tools ===${NC}"

# Check system tools
run_test "Git" "git --version"
run_test "Docker" "docker --version"
run_test "Docker Compose" "docker-compose --version"

# Check if we're in a container environment
if [ -f "/.dockerenv" ] || grep -q "container=docker" /proc/1/environ 2>/dev/null; then
    echo -e "${BLUE}Running inside container environment${NC}"
    
    # Container-specific tests
    run_test "Python" "python3 --version"
    run_test "Node.js" "node --version"
    run_test "npm" "npm --version"
    
    # Check if pnpm is available
    if command -v pnpm &> /dev/null; then
        run_test "pnpm" "pnpm --version"
    fi
    
    # Check if TypeScript is available
    if command -v tsc &> /dev/null; then
        run_test "TypeScript" "tsc --version"
    fi
    
    # Check if uv is available
    if command -v uv &> /dev/null; then
        run_test "uv package manager" "uv --version"
    fi
else
    echo -e "${BLUE}Running outside container (host environment)${NC}"
fi

echo ""
echo -e "${YELLOW}=== Claude-Flow Installation ===${NC}"

# Check Claude-Flow npx cache availability
run_test "Claude-Flow availability" "npx --yes claude-flow@alpha --version"

# Check if repository is initialized
if [ -f "$PROJECT_ROOT/.claude-flow.json" ]; then
    echo -e "${GREEN}✅ Claude-Flow repository initialized${NC}"
else
    echo -e "${YELLOW}⚠️  Claude-Flow repository not initialized (missing .claude-flow.json)${NC}"
fi

echo ""
echo -e "${YELLOW}=== Environment Configuration ===${NC}"

# Check environment configuration
if [ -f "$PROJECT_ROOT/.env" ]; then
    echo -e "${GREEN}✅ .env file exists${NC}"
    
    # Check for critical environment variables
    if grep -q "CLAUDE_CODE_OAUTH_TOKEN=REDACTED" "$PROJECT_ROOT/.env"; then
        echo -e "${YELLOW}⚠️  CLAUDE_CODE_OAUTH_TOKEN still set to REDACTED${NC}"
    fi
    
    if grep -q "GITHUB_TOKEN=REDACTED" "$PROJECT_ROOT/.env"; then
        echo -e "${YELLOW}⚠️  GITHUB_TOKEN still set to REDACTED${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  .env file not found (use .env.example as template)${NC}"
fi

echo ""
echo -e "${YELLOW}=== Agent Tools ===${NC}"

# Check agent tools
# Check for tools in multiple locations
TOOLS_LOCATIONS=(
    "$HOME/.local/bin"
    "/usr/local/bin"
    "$PROJECT_ROOT/.agent/tools/bin"
)

# Function to find tools directory
find_tools_dir() {
    for dir in "${TOOLS_LOCATIONS[@]}"; do
        if [[ -d "$dir" ]]; then
            echo "$dir"
            return 0
        fi
    done
    echo "$PROJECT_ROOT/.agent/tools/bin"  # fallback
}

TOOLS_DIR=$(find_tools_dir)
if [ -d "$TOOLS_DIR" ]; then
    for tool in "claude" "codex" "opencode"; do
        if [ -f "$TOOLS_DIR/$tool" ]; then
            echo -e "${GREEN}✅ $tool binary found${NC}"
        else
            echo -e "${YELLOW}⚠️  $tool binary not found${NC}"
        fi
    done
else
    echo -e "${YELLOW}⚠️  Agent tools bin directory not found${NC}"
fi

# Check environment script
check_file "$PROJECT_ROOT/.agent/configs/agent-tools-env.sh" "Agent tools environment script"

echo ""
echo -e "${YELLOW}=== Network Connectivity ===${NC}"

# Test network connectivity (if not in restricted environment)
if command -v curl &> /dev/null; then
    run_test "GitHub connectivity" "curl -s --connect-timeout 5 https://api.github.com/zen"
    run_test "npm registry connectivity" "curl -s --connect-timeout 5 https://registry.npmjs.org/"
else
    echo -e "${YELLOW}⚠️  curl not available, skipping network tests${NC}"
fi

echo ""
echo -e "${YELLOW}=== Summary ===${NC}"

echo -e "${BLUE}Total tests: $TESTS_TOTAL${NC}"
echo -e "${GREEN}Passed: $TESTS_PASSED${NC}"
echo -e "${RED}Failed: $TESTS_FAILED${NC}"

if [ $TESTS_FAILED -eq 0 ]; then
    echo ""
    echo -e "${GREEN}🎉 All tests passed! Setup validation successful.${NC}"
    echo ""
    echo -e "${BLUE}Next steps:${NC}"
    echo -e "${BLUE}1. Update .env with actual credentials${NC}"
    echo -e "${BLUE}2. Start development environment${NC}"
    echo -e "${BLUE}3. Begin development with agent assistance${NC}"
    exit 0
else
    echo ""
    echo -e "${YELLOW}⚠️  Some tests failed. Please review the issues above.${NC}"
    echo ""
    echo -e "${BLUE}Common solutions:${NC}"
    echo -e "${BLUE}1. Run ./.agent/scripts/init-repository.sh again${NC}"
    echo -e "${BLUE}2. Check network connectivity${NC}"
    echo -e "${BLUE}3. Verify Docker is running${NC}"
    echo -e "${BLUE}4. Review .agent/docs/ for troubleshooting${NC}"
    exit 1
fi