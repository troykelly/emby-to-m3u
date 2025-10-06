#!/bin/bash

# Aperim Template - Start Claude-Flow Hive-Mind Script
# Starts hive-mind with appropriate configuration

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
# Claude-Flow now uses npx, no local directory needed
HIVE_INFO_FILE="$PROJECT_ROOT/.agent/temp/hive-mind-info.json"

# Ensure temp directory exists
mkdir -p "$(dirname "$HIVE_INFO_FILE")"

echo -e "${BLUE}Aperim Template: Starting Claude-Flow Hive-Mind...${NC}"

# Default values
OBJECTIVE=""
AGENTS=5
STRATEGY="hierarchical"
NAMESPACE="aperim-template"
CLAUDE_INTEGRATION=false
FORCE_START=false
BACKGROUND=false

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS] [OBJECTIVE]"
    echo ""
    echo "Start Claude-Flow hive-mind for the Aperim template project"
    echo ""
    echo "Options:"
    echo "  --agents, -a NUMBER     Number of agents to spawn (default: 5)"
    echo "  --strategy, -s TYPE     Coordination strategy: hierarchical|mesh|adaptive (default: hierarchical)"
    echo "  --namespace, -n NAME    Memory namespace (default: aperim-template)"
    echo "  --claude                Enable Claude Code integration"
    echo "  --force                 Force start even if already running"
    echo "  --background, -b        Run in background"
    echo "  --help, -h              Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 'Build a FastAPI application'"
    echo "  $0 --agents 10 --strategy mesh 'Create microservices architecture'"
    echo "  $0 --claude --background 'Develop user authentication system'"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --agents|-a)
            AGENTS="$2"
            shift 2
            ;;
        --strategy|-s)
            STRATEGY="$2"
            shift 2
            ;;
        --namespace|-n)
            NAMESPACE="$2"
            shift 2
            ;;
        --claude)
            CLAUDE_INTEGRATION=true
            shift
            ;;
        --force)
            FORCE_START=true
            shift
            ;;
        --background|-b)
            BACKGROUND=true
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
            OBJECTIVE="$1"
            shift
            ;;
    esac
done

# Check if Claude-Flow is available
if ! npx --yes claude-flow@alpha --version >/dev/null 2>&1; then
    echo -e "${RED}❌ Claude-Flow not available${NC}"
    echo -e "${BLUE}Run: ./.agent/scripts/install-claude-flow.sh${NC}"
    exit 1
fi

# Check if hive-mind is already running
if [ -f "$HIVE_INFO_FILE" ] && [ "$FORCE_START" = false ]; then
    SESSION_ID=$(jq -r '.sessionId // empty' "$HIVE_INFO_FILE" 2>/dev/null || echo "")
    if [ -n "$SESSION_ID" ]; then
        echo -e "${YELLOW}Hive-mind already running with session ID: $SESSION_ID${NC}"
        echo -e "${BLUE}Use --force to restart or run: ./.agent/scripts/status-hive-mind.sh${NC}"
        exit 0
    fi
fi

# Validate strategy
case $STRATEGY in
    hierarchical|mesh|adaptive)
        ;;
    *)
        echo -e "${RED}❌ Invalid strategy: $STRATEGY${NC}"
        echo -e "${BLUE}Valid strategies: hierarchical, mesh, adaptive${NC}"
        exit 1
        ;;
esac

# Change to project root directory (where .claude-flow.json should be)
cd "$PROJECT_ROOT"

# Prepare command (use --yes to avoid interactive prompt)
HIVE_CMD=(npx --yes claude-flow@alpha hive-mind spawn)

# Add objective if provided
if [ -n "$OBJECTIVE" ]; then
    HIVE_CMD+=("$OBJECTIVE")
else
    HIVE_CMD+=("Aperim template development assistance")
fi

# Add options
HIVE_CMD+=(--agents "$AGENTS")
HIVE_CMD+=(--namespace "$NAMESPACE")

# Add strategy-specific options
case $STRATEGY in
    mesh)
        HIVE_CMD+=(--topology mesh --max-agents "$AGENTS")
        ;;
    adaptive)
        HIVE_CMD+=(--topology adaptive --auto-scale)
        ;;
    *)
        HIVE_CMD+=(--topology hierarchical)
        ;;
esac

# Add Claude integration if requested
if [ "$CLAUDE_INTEGRATION" = true ]; then
    HIVE_CMD+=(--claude)
fi

echo -e "${BLUE}Starting hive-mind with configuration:${NC}"
echo -e "${BLUE}  Strategy: $STRATEGY${NC}"
echo -e "${BLUE}  Agents: $AGENTS${NC}"
echo -e "${BLUE}  Namespace: $NAMESPACE${NC}"
echo -e "${BLUE}  Claude Integration: $CLAUDE_INTEGRATION${NC}"
echo -e "${BLUE}  Objective: ${OBJECTIVE:-'Aperim template development assistance'}${NC}"
echo ""

# Execute command
echo -e "${BLUE}Executing: ${HIVE_CMD[*]}${NC}"

if [ "$BACKGROUND" = true ]; then
    echo -e "${BLUE}Starting in background...${NC}"
    
    # Create log file for background process
    LOG_FILE="$PROJECT_ROOT/.agent/temp/hive-mind.log"
    
    # Start in background and capture process info
    nohup "${HIVE_CMD[@]}" > "$LOG_FILE" 2>&1 &
    HIVE_PID=$!
    
    # Wait a moment to see if process starts successfully
    sleep 2
    
    if kill -0 "$HIVE_PID" 2>/dev/null; then
        # Generate session ID (simplified)
        SESSION_ID="hive-$(date +%s)-$HIVE_PID"
        
        # Store hive-mind information
        cat > "$HIVE_INFO_FILE" << EOF
{
    "sessionId": "$SESSION_ID",
    "pid": $HIVE_PID,
    "strategy": "$STRATEGY",
    "agents": $AGENTS,
    "namespace": "$NAMESPACE",
    "claudeIntegration": $CLAUDE_INTEGRATION,
    "objective": "${OBJECTIVE:-'Aperim template development assistance'}",
    "startedAt": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "logFile": "$LOG_FILE",
    "status": "running",
    "workingDirectory": "$PROJECT_ROOT"
}
EOF
        
        echo -e "${GREEN}✅ Hive-mind started successfully in background${NC}"
        echo -e "${BLUE}Session ID: $SESSION_ID${NC}"
        echo -e "${BLUE}PID: $HIVE_PID${NC}"
        echo -e "${BLUE}Log file: $LOG_FILE${NC}"
        echo ""
        echo -e "${YELLOW}Management commands:${NC}"
        echo -e "${BLUE}  Status: ./.agent/scripts/status-hive-mind.sh${NC}"
        echo -e "${BLUE}  Send message: ./.agent/scripts/message-hive-mind.sh 'your message'${NC}"
        echo -e "${BLUE}  Stop: ./.agent/scripts/stop-hive-mind.sh${NC}"
        
    else
        echo -e "${RED}❌ Failed to start hive-mind${NC}"
        echo -e "${BLUE}Check log file: $LOG_FILE${NC}"
        exit 1
    fi
    
else
    echo -e "${BLUE}Starting in foreground (use Ctrl+C to stop)...${NC}"
    
    # Store basic info for foreground process
    cat > "$HIVE_INFO_FILE" << EOF
{
    "sessionId": "foreground-$(date +%s)",
    "strategy": "$STRATEGY",
    "agents": $AGENTS,
    "namespace": "$NAMESPACE",
    "claudeIntegration": $CLAUDE_INTEGRATION,
    "objective": "${OBJECTIVE:-'Aperim template development assistance'}",
    "startedAt": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "status": "foreground",
    "workingDirectory": "$PROJECT_ROOT"
}
EOF
    
    # Execute in foreground
    exec "${HIVE_CMD[@]}"
fi

cd "$PROJECT_ROOT"