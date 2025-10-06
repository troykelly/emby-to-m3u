#!/bin/bash

# Aperim Template - Stop Headless Devcontainer Script
# Uses official devcontainer CLI for proper cleanup

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

echo -e "${BLUE}Aperim Template: Stopping headless devcontainer...${NC}"

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

# Parse command line arguments
FORCE_STOP=false
REMOVE_CONTAINER=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --force|-f)
            FORCE_STOP=true
            shift
            ;;
        --remove|-r)
            REMOVE_CONTAINER=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  --force, -f     Force stop the container (kill instead of graceful shutdown)"
            echo "  --remove, -r    Remove the container after stopping"
            echo "  --help, -h      Show this help message"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Change to project root
cd "$PROJECT_ROOT"

# Check if container info exists
if [ ! -f "$CONTAINER_INFO_FILE" ]; then
    echo -e "${YELLOW}No container info found. Attempting to find devcontainer by label...${NC}"
    
    # Try to find container by devcontainer label
    CONTAINER_ID=$(docker ps --filter "label=devcontainer.local_folder=$PROJECT_ROOT" --format "{{.ID}}" | head -1)
    
    if [ -z "$CONTAINER_ID" ]; then
        echo -e "${YELLOW}No running devcontainer found for this project.${NC}"
        
        # Check for any stopped containers
        STOPPED_CONTAINER=$(docker ps -a --filter "label=devcontainer.local_folder=$PROJECT_ROOT" --format "{{.ID}}" | head -1)
        if [ -n "$STOPPED_CONTAINER" ]; then
            echo -e "${BLUE}Found stopped devcontainer: $STOPPED_CONTAINER${NC}"
            if [ "$REMOVE_CONTAINER" = true ]; then
                echo -e "${BLUE}Removing stopped container...${NC}"
                docker rm "$STOPPED_CONTAINER"
                echo -e "${GREEN}✅ Stopped container removed${NC}"
            fi
        fi
        exit 0
    fi
else
    # Read container ID from info file
    CONTAINER_ID=$(jq -r '.containerId // empty' "$CONTAINER_INFO_FILE" 2>/dev/null || echo "")
    
    if [ -z "$CONTAINER_ID" ]; then
        echo -e "${RED}❌ Invalid container info file${NC}"
        rm -f "$CONTAINER_INFO_FILE"
        exit 1
    fi
fi

echo -e "${BLUE}Found container ID: $CONTAINER_ID${NC}"

# Check if container is actually running
if ! docker ps -q --filter "id=$CONTAINER_ID" | grep -q .; then
    echo -e "${YELLOW}Container $CONTAINER_ID is not running${NC}"
    
    # Check if it exists but is stopped
    if docker ps -a -q --filter "id=$CONTAINER_ID" | grep -q .; then
        echo -e "${BLUE}Container exists but is stopped${NC}"
        if [ "$REMOVE_CONTAINER" = true ]; then
            echo -e "${BLUE}Removing stopped container...${NC}"
            docker rm "$CONTAINER_ID"
            echo -e "${GREEN}✅ Container removed${NC}"
        fi
    else
        echo -e "${YELLOW}Container no longer exists${NC}"
    fi
    
    # Clean up container info file
    rm -f "$CONTAINER_INFO_FILE"
    exit 0
fi

# Stop the container
echo -e "${BLUE}Stopping devcontainer...${NC}"

if [ "$FORCE_STOP" = true ]; then
    echo -e "${YELLOW}Force stopping container...${NC}"
    docker kill "$CONTAINER_ID" >/dev/null 2>&1 || {
        echo -e "${RED}❌ Failed to force stop container${NC}"
        exit 1
    }
else
    echo -e "${BLUE}Gracefully stopping container (timeout: 30s)...${NC}"
    docker stop --time 30 "$CONTAINER_ID" >/dev/null 2>&1 || {
        echo -e "${YELLOW}Graceful stop failed, force stopping...${NC}"
        docker kill "$CONTAINER_ID" >/dev/null 2>&1 || {
            echo -e "${RED}❌ Failed to stop container${NC}"
            exit 1
        }
    }
fi

echo -e "${GREEN}✅ Container stopped successfully${NC}"

# Remove container if requested
if [ "$REMOVE_CONTAINER" = true ]; then
    echo -e "${BLUE}Removing container...${NC}"
    docker rm "$CONTAINER_ID" >/dev/null 2>&1 || {
        echo -e "${RED}❌ Failed to remove container${NC}"
        exit 1
    }
    echo -e "${GREEN}✅ Container removed${NC}"
fi

# Clean up container info file
rm -f "$CONTAINER_INFO_FILE"

# Also try to stop any related compose services
if [ -f "$PROJECT_ROOT/.devcontainer/docker-compose.yml" ]; then
    echo -e "${BLUE}Stopping related compose services...${NC}"
    docker-compose -f "$PROJECT_ROOT/.devcontainer/docker-compose.yml" down >/dev/null 2>&1 || {
        echo -e "${YELLOW}Could not stop compose services (may not be running)${NC}"
    }
fi

echo -e "${GREEN}🛑 Devcontainer stopped successfully${NC}"

# Show status of any remaining containers
REMAINING=$(docker ps --filter "label=devcontainer.local_folder=$PROJECT_ROOT" --format "{{.ID}}" | wc -l)
if [ "$REMAINING" -gt 0 ]; then
    echo -e "${YELLOW}⚠️  $REMAINING related container(s) still running${NC}"
    docker ps --filter "label=devcontainer.local_folder=$PROJECT_ROOT" --format "table {{.ID}}\t{{.Image}}\t{{.Status}}"
fi