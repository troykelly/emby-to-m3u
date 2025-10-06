#!/bin/bash

# Aperim Template - Start Headless Devcontainer Script
# Uses official devcontainer CLI for proper headless operation

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

# Ensure temp directory exists
mkdir -p "$(dirname "$CONTAINER_INFO_FILE")"

echo -e "${BLUE}Aperim Template: Starting headless devcontainer...${NC}"

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

# Check if container is already running
if [ -f "$CONTAINER_INFO_FILE" ]; then
    CONTAINER_ID=$(jq -r '.containerId // empty' "$CONTAINER_INFO_FILE" 2>/dev/null || echo "")
    if [ -n "$CONTAINER_ID" ] && docker ps -q --filter "id=$CONTAINER_ID" | grep -q .; then
        echo -e "${YELLOW}Devcontainer is already running with ID: $CONTAINER_ID${NC}"
        echo -e "${BLUE}Container info:${NC}"
        jq '.' "$CONTAINER_INFO_FILE" 2>/dev/null || echo "Invalid container info file"
        exit 0
    else
        echo -e "${YELLOW}Removing stale container info...${NC}"
        rm -f "$CONTAINER_INFO_FILE"
    fi
fi

# Start the devcontainer using official CLI
echo -e "${BLUE}Starting devcontainer with compose setup...${NC}"

# Use devcontainer up command for proper headless operation
RESULT=$($DEVCONTAINER_CMD up --workspace-folder "$PROJECT_ROOT" --remove-existing-container 2>&1)
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✅ Devcontainer started successfully${NC}"
    
    # Extract container information from devcontainer CLI output
    # The devcontainer CLI should provide container details
    CONTAINER_ID=$(docker ps --filter "label=devcontainer.local_folder=$PROJECT_ROOT" --format "{{.ID}}" | head -1)
    
    if [ -n "$CONTAINER_ID" ]; then
        # Store container information for management
        CONTAINER_INFO=$(docker inspect "$CONTAINER_ID" | jq '.[0]' 2>/dev/null || echo '{}')
        
        # Create container info file
        cat > "$CONTAINER_INFO_FILE" << EOF
{
    "containerId": "$CONTAINER_ID",
    "projectRoot": "$PROJECT_ROOT",
    "startedAt": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "status": "running",
    "ports": $(docker port "$CONTAINER_ID" | jq -R 'split(" -> ") | {port: .[0], host: .[1]}' | jq -s '.' 2>/dev/null || echo '[]'),
    "containerInfo": $CONTAINER_INFO
}
EOF
        
        echo -e "${GREEN}Container ID: $CONTAINER_ID${NC}"
        echo -e "${BLUE}Container info saved to: $CONTAINER_INFO_FILE${NC}"
        
        # Show port mappings
        echo -e "${BLUE}Port mappings:${NC}"
        docker port "$CONTAINER_ID" || echo "No port mappings found"
        
        # Test container responsiveness
        echo -e "${BLUE}Testing container responsiveness...${NC}"
        if docker exec "$CONTAINER_ID" echo "Container is responsive" >/dev/null 2>&1; then
            echo -e "${GREEN}✅ Container is responding to commands${NC}"
        else
            echo -e "${YELLOW}⚠️  Container may still be initialising${NC}"
        fi
        
        echo -e "${GREEN}🚀 Devcontainer is ready for headless operation${NC}"
        echo -e "${BLUE}Use './agent/scripts/exec-devcontainer.sh <command>' to execute commands${NC}"
        echo -e "${BLUE}Use './agent/scripts/stop-devcontainer.sh' to stop the container${NC}"
        
    else
        echo -e "${RED}❌ Could not determine container ID${NC}"
        echo -e "${YELLOW}Devcontainer CLI output:${NC}"
        echo "$RESULT"
        exit 1
    fi
else
    echo -e "${RED}❌ Failed to start devcontainer${NC}"
    echo -e "${YELLOW}Error output:${NC}"
    echo "$RESULT"
    exit $EXIT_CODE
fi