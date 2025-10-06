#!/bin/bash

# Aperim Template - Execute Commands in Headless Devcontainer Script
# Uses devcontainer CLI for proper command execution

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
CONTAINER_INFO_FILE="$PROJECT_ROOT/.agent/temp/container-info.json"

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS] <command> [arguments...]"
    echo ""
    echo "Execute commands in the running devcontainer"
    echo ""
    echo "Options:"
    echo "  --interactive, -i    Run in interactive mode (allocate TTY)"
    echo "  --user, -u USER      Run as specific user (default: vscode)"
    echo "  --workdir, -w DIR    Set working directory (default: /workspaces)"
    echo "  --env, -e VAR=VALUE  Set environment variable"
    echo "  --help, -h           Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 'echo Hello World'"
    echo "  $0 --interactive bash"
    echo "  $0 --user root 'apt-get update'"
    echo "  $0 --workdir /tmp 'ls -la'"
    echo "  $0 --env 'DEBUG=true' 'python app.py'"
}

# Default options
INTERACTIVE=false
USER="vscode"
WORKDIR="/workspaces"
ENV_VARS=()

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --interactive|-i)
            INTERACTIVE=true
            shift
            ;;
        --user|-u)
            USER="$2"
            shift 2
            ;;
        --workdir|-w)
            WORKDIR="$2"
            shift 2
            ;;
        --env|-e)
            ENV_VARS+=("$2")
            shift 2
            ;;
        --help|-h)
            show_usage
            exit 0
            ;;
        -*)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
        *)
            break
            ;;
    esac
done

# Check if command is provided
if [ $# -eq 0 ]; then
    echo -e "${RED}❌ No command specified${NC}"
    echo ""
    show_usage
    exit 1
fi

# The command is everything remaining
COMMAND="$*"

echo -e "${BLUE}Aperim Template: Executing command in devcontainer...${NC}"
echo -e "${BLUE}Command: ${YELLOW}$COMMAND${NC}"

# Check if devcontainer CLI is installed
DEVCONTAINER_CMD=""
if command -v devcontainer &> /dev/null; then
    DEVCONTAINER_CMD="devcontainer"
    echo -e "${GREEN}✅ devcontainer CLI found${NC}"
else
    echo -e "${YELLOW}Installing devcontainer CLI...${NC}"
    
    # Try different installation methods
    if command -v pnpm &> /dev/null; then
        echo -e "${BLUE}Using pnpm for installation...${NC}"
        if pnpm add -g @devcontainers/cli --yes; then
            DEVCONTAINER_CMD="devcontainer"
        fi
    elif [ "$EUID" -eq 0 ]; then
        # Running as root
        if pnpm add -g @devcontainers/cli --yes; then
            DEVCONTAINER_CMD="devcontainer"
        fi
    else
        # Try with sudo, if available and user permits
        echo -e "${YELLOW}Attempting to install devcontainer CLI with elevated permissions...${NC}"
        if sudo -n true 2>/dev/null; then
            if sudo pnpm add -g @devcontainers/cli --yes; then
                DEVCONTAINER_CMD="devcontainer"
            fi
        fi
    fi
    
    # Fall back to npx if global installation failed
    if [ -z "$DEVCONTAINER_CMD" ]; then
        echo -e "${BLUE}Using npx for devcontainer commands...${NC}"
        DEVCONTAINER_CMD="npx @devcontainers/cli"
    fi
fi

# Verify devcontainer CLI version
echo -e "${BLUE}Using devcontainer CLI: $DEVCONTAINER_CMD${NC}"
VERSION_OUTPUT=$($DEVCONTAINER_CMD --version 2>/dev/null || echo "unknown")
echo -e "${BLUE}Version: $VERSION_OUTPUT${NC}"

# Change to project root
cd "$PROJECT_ROOT"

# Build devcontainer exec command
EXEC_CMD=($DEVCONTAINER_CMD exec)

# Add working directory to the devcontainer config
EXEC_CMD+=(--workspace-folder "$PROJECT_ROOT")

# Add user if not default
if [ "$USER" != "vscode" ]; then
    EXEC_CMD+=(--user-env-probe loginInteractiveShell)
    # Note: devcontainer exec doesn't have --user flag, it uses the configured user
fi

# Add environment variables using --remote-env
if [ ${#ENV_VARS[@]} -gt 0 ]; then
    for env_var in "${ENV_VARS[@]}"; do
        EXEC_CMD+=(--remote-env "$env_var")
    done
fi

# Add the command as separate arguments
if [ "$WORKDIR" != "/workspaces" ]; then
    # If custom working directory, wrap in cd command
    EXEC_CMD+=(bash -c "cd $WORKDIR && $COMMAND")
else
    # Use the command directly
    EXEC_CMD+=(bash -c "$COMMAND")
fi

# Execute the command
echo -e "${BLUE}Executing: ${EXEC_CMD[*]}${NC}"
echo ""

# Store exit code
set +e
"${EXEC_CMD[@]}"
EXIT_CODE=$?
set -e

# Show result
if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ Command executed successfully${NC}"
else
    echo ""
    echo -e "${RED}❌ Command failed with exit code: $EXIT_CODE${NC}"
fi

exit $EXIT_CODE