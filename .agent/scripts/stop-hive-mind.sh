#!/bin/bash

# Aperim Template - Stop Claude-Flow Hive-Mind Script
# Gracefully stops hive-mind processes and cleans up

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
HIVE_INFO_FILE="$PROJECT_ROOT/.agent/temp/hive-mind-info.json"

echo -e "${BLUE}Aperim Template: Stopping Claude-Flow Hive-Mind...${NC}"

# Default options
FORCE_STOP=false
SAVE_STATE=true

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Stop Claude-Flow hive-mind"
    echo ""
    echo "Options:"
    echo "  --force, -f         Force stop (kill processes immediately)"
    echo "  --no-save           Don't save hive-mind state"
    echo "  --help, -h          Show this help message"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --force|-f)
            FORCE_STOP=true
            shift
            ;;
        --no-save)
            SAVE_STATE=false
            shift
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
            echo -e "${RED}Unexpected argument: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Check if hive-mind info exists
if [ ! -f "$HIVE_INFO_FILE" ]; then
    echo -e "${YELLOW}No hive-mind info found. Checking for running processes...${NC}"
    
    # Look for claude-flow processes
    CLAUDE_PIDS=$(pgrep -f "claude-flow.*hive-mind" || echo "")
    
    if [ -n "$CLAUDE_PIDS" ]; then
        echo -e "${BLUE}Found claude-flow hive-mind processes: $CLAUDE_PIDS${NC}"
        if [ "$FORCE_STOP" = true ]; then
            echo -e "${YELLOW}Force stopping found processes...${NC}"
            echo "$CLAUDE_PIDS" | xargs kill -9 2>/dev/null || echo -e "${YELLOW}Some processes may have already stopped${NC}"
            echo -e "${GREEN}✅ Processes stopped${NC}"
        else
            echo -e "${BLUE}Use --force to stop these processes${NC}"
        fi
    else
        echo -e "${GREEN}No claude-flow hive-mind processes found${NC}"
    fi
    
    exit 0
fi

# Read hive-mind information
SESSION_ID=$(jq -r '.sessionId // empty' "$HIVE_INFO_FILE" 2>/dev/null || echo "")
PID=$(jq -r '.pid // empty' "$HIVE_INFO_FILE" 2>/dev/null || echo "")
STATUS=$(jq -r '.status // empty' "$HIVE_INFO_FILE" 2>/dev/null || echo "")
NAMESPACE=$(jq -r '.namespace // empty' "$HIVE_INFO_FILE" 2>/dev/null || echo "")

echo -e "${BLUE}Found hive-mind session: $SESSION_ID${NC}"

if [ "$STATUS" = "foreground" ]; then
    echo -e "${YELLOW}Hive-mind was running in foreground mode${NC}"
    echo -e "${BLUE}If still running, stop with Ctrl+C in the terminal${NC}"
    rm -f "$HIVE_INFO_FILE"
    exit 0
fi

# Check if process is still running
if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
    echo -e "${BLUE}Process $PID is running${NC}"
    
    if [ "$FORCE_STOP" = true ]; then
        echo -e "${YELLOW}Force stopping hive-mind (PID: $PID)...${NC}"
        kill -9 "$PID" 2>/dev/null || echo -e "${YELLOW}Process may have already stopped${NC}"
    else
        echo -e "${BLUE}Gracefully stopping hive-mind (PID: $PID)...${NC}"
        
        # Try graceful shutdown first
        kill -TERM "$PID" 2>/dev/null || {
            echo -e "${YELLOW}Could not send TERM signal, trying KILL...${NC}"
            kill -9 "$PID" 2>/dev/null || echo -e "${YELLOW}Process may have already stopped${NC}"
        }
        
        # Wait for process to stop
        WAIT_COUNT=0
        while kill -0 "$PID" 2>/dev/null && [ $WAIT_COUNT -lt 10 ]; do
            echo -e "${BLUE}Waiting for process to stop... ($((WAIT_COUNT + 1))/10)${NC}"
            sleep 1
            WAIT_COUNT=$((WAIT_COUNT + 1))
        done
        
        # Force kill if still running
        if kill -0 "$PID" 2>/dev/null; then
            echo -e "${YELLOW}Process still running, force stopping...${NC}"
            kill -9 "$PID" 2>/dev/null || echo -e "${YELLOW}Process may have already stopped${NC}"
        fi
    fi
    
    echo -e "${GREEN}✅ Process stopped${NC}"
else
    echo -e "${YELLOW}Process $PID is not running${NC}"
fi

# Save state if requested
if [ "$SAVE_STATE" = true ] && [ -n "$NAMESPACE" ]; then
    echo -e "${BLUE}Saving hive-mind state...${NC}"
    
    CLAUDE_FLOW_DIR="$PROJECT_ROOT/.agent/tools/claude-flow"
    if [ -d "$CLAUDE_FLOW_DIR" ]; then
        cd "$CLAUDE_FLOW_DIR"
        
        # Try to export memory/state
        echo -e "${BLUE}Attempting to save memory state for namespace: $NAMESPACE${NC}"
        
        # Create state backup directory
        STATE_DIR="$PROJECT_ROOT/.agent/temp/hive-state-$(date +%Y%m%d-%H%M%S)"
        mkdir -p "$STATE_DIR"
        
        # Try to export using claude-flow memory commands
        if npx --yes claude-flow@alpha memory export "$STATE_DIR/memory-backup.json" --namespace "$NAMESPACE" 2>/dev/null; then
            echo -e "${GREEN}✅ Memory state saved to: $STATE_DIR/memory-backup.json${NC}"
        else
            echo -e "${YELLOW}Could not export memory state (may not be supported)${NC}"
        fi
        
        # Save session info
        cp "$HIVE_INFO_FILE" "$STATE_DIR/session-info.json" 2>/dev/null || echo -e "${YELLOW}Could not copy session info${NC}"
        
        cd "$PROJECT_ROOT"
    fi
fi

# Look for any remaining claude-flow processes
echo -e "${BLUE}Checking for remaining claude-flow processes...${NC}"
REMAINING_PIDS=$(pgrep -f "claude-flow.*hive-mind" || echo "")

if [ -n "$REMAINING_PIDS" ]; then
    echo -e "${YELLOW}Found remaining claude-flow processes: $REMAINING_PIDS${NC}"
    if [ "$FORCE_STOP" = true ]; then
        echo -e "${YELLOW}Stopping remaining processes...${NC}"
        echo "$REMAINING_PIDS" | xargs kill -9 2>/dev/null || echo -e "${YELLOW}Some processes may have already stopped${NC}"
    else
        echo -e "${BLUE}Use --force to stop these processes${NC}"
    fi
fi

# Clean up info file
rm -f "$HIVE_INFO_FILE"

echo -e "${GREEN}🛑 Hive-mind stopped successfully${NC}"

# Check for any .hive-mind or .swarm directories that might need cleanup
if [ -d "$PROJECT_ROOT/.hive-mind" ]; then
    echo -e "${BLUE}Hive-mind data directory exists: .hive-mind/${NC}"
fi

if [ -d "$PROJECT_ROOT/.swarm" ]; then
    echo -e "${BLUE}Swarm data directory exists: .swarm/${NC}"
fi

echo -e "${YELLOW}To restart hive-mind, run: ./.agent/scripts/start-hive-mind.sh${NC}"