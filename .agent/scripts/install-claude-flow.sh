#!/bin/bash

# Aperim Template - Install Claude-Flow Script  
# Warms up npx cache for claude-flow@alpha without polluting the project

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

echo -e "${BLUE}Aperim Template: Preparing Claude-Flow...${NC}"

# Ensure tools directory exists for configuration
mkdir -p "$PROJECT_ROOT/.agent/tools"

# Check if claude-flow is already cached by testing a quick command
echo -e "${BLUE}Checking Claude-Flow availability...${NC}"
if npx --yes claude-flow@alpha --version >/dev/null 2>&1; then
    echo -e "${GREEN}✅ Claude-Flow is already cached and ready${NC}"
    VERSION=$(npx --yes claude-flow@alpha --version 2>/dev/null || echo "unknown")
    echo -e "${BLUE}Version: $VERSION${NC}"
    # Don't exit here - continue to initialization check below
else
    # Warm up the npx cache with claude-flow@alpha
    echo -e "${BLUE}Warming up Claude-Flow cache (this downloads once for fast future use)...${NC}"
    echo -e "${YELLOW}This may take a moment on first run...${NC}"
    
    # Download and cache claude-flow@alpha by running a simple command
    if npx --yes claude-flow@alpha --help >/dev/null 2>&1; then
        echo -e "${GREEN}✅ Claude-Flow cache warmed successfully${NC}"
        
        # Get version info
        VERSION=$(npx --yes claude-flow@alpha --version 2>/dev/null || echo "unknown")
        echo -e "${BLUE}Cached version: $VERSION${NC}"
    else
        echo -e "${RED}❌ Failed to cache Claude-Flow${NC}"
        echo -e "${YELLOW}You may need to install it manually later${NC}"
    fi
fi

# All cache warming is done above, now continue to configuration

# Create configuration directory
mkdir -p "$PROJECT_ROOT/.agent/configs/claude-flow"

# Create basic configuration
cat > "$PROJECT_ROOT/.agent/configs/claude-flow/config.json" << EOF
{
    "version": "2.0.0-alpha",
    "installation": {
        "method": "npx-cache",
        "cachedAt": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    },
    "features": {
        "hiveMind": true,
        "swarm": true,
        "neuralPatterns": true,
        "memoryPersistence": true,
        "hooks": true
    },
    "defaults": {
        "coordination": "hierarchical",
        "memoryNamespace": "aperim-template",
        "agents": {
            "max": 10,
            "defaultTypes": ["coder", "reviewer", "tester", "planner", "researcher"]
        }
    }
}
EOF

cd "$PROJECT_ROOT"

# Initialize Claude-Flow repository if needed
echo -e "${BLUE}🔧 Initializing Claude-Flow for repository...${NC}"
if [ ! -f ".claude-flow.json" ]; then
    echo -e "${BLUE}Running claude-flow init for first-time setup...${NC}"
    # Run init with actual error checking
    if npx --yes claude-flow@alpha init --force 2>&1; then
        if [ -f ".claude-flow.json" ]; then
            echo -e "${GREEN}✅ Claude-Flow repository initialized successfully${NC}"
        else
            echo -e "${YELLOW}⚠️  Claude-Flow init completed but .claude-flow.json not created${NC}"
            echo -e "${BLUE}Creating default .claude-flow.json...${NC}"
            # Create a default .claude-flow.json
            cat > ".claude-flow.json" << 'FLOWEOF'
{
  "version": "2.0.0",
  "type": "project",
  "name": "${PWD##*/}",
  "description": "Aperim Template Project",
  "settings": {
    "coordination": "hierarchical",
    "memoryNamespace": "aperim-${PWD##*/}",
    "agents": {
      "maxAgents": 10,
      "defaultTypes": ["coder", "reviewer", "tester", "planner", "researcher"]
    },
    "features": {
      "hiveMind": true,
      "swarm": true,
      "neuralPatterns": true,
      "memoryPersistence": true
    }
  },
  "hooks": {
    "preInstall": ".agent/scripts/validate-setup.sh",
    "postInstall": "echo '✅ Claude-Flow installed'"
  }
}
FLOWEOF
            echo -e "${GREEN}✅ Created default .claude-flow.json${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️  Claude-Flow init command failed, creating default config...${NC}"
        # Create a minimal .claude-flow.json
        cat > ".claude-flow.json" << 'FLOWEOF'
{
  "version": "2.0.0",
  "type": "project",
  "name": "${PWD##*/}",
  "description": "Aperim Template Project",
  "settings": {
    "coordination": "hierarchical",
    "memoryNamespace": "aperim-${PWD##*/}",
    "agents": {
      "maxAgents": 10,
      "defaultTypes": ["coder", "reviewer", "tester", "planner", "researcher"]
    },
    "features": {
      "hiveMind": true,
      "swarm": true,
      "neuralPatterns": true,
      "memoryPersistence": true
    }
  }
}
FLOWEOF
        echo -e "${GREEN}✅ Created fallback .claude-flow.json${NC}"
    fi
else
    echo -e "${GREEN}✅ Claude-Flow already initialized${NC}"
fi

echo -e "${GREEN}🚀 Claude-Flow ready for use!${NC}"
echo -e "${BLUE}Method: NPX cache (no local installation)${NC}"
echo -e "${BLUE}Configuration: $PROJECT_ROOT/.agent/configs/claude-flow/config.json${NC}"
echo ""
echo -e "${YELLOW}Usage:${NC}"
echo -e "${BLUE}  npx --yes claude-flow@alpha --help${NC}"
echo -e "${BLUE}  npx --yes claude-flow@alpha hive-mind spawn \"My Project\"${NC}"
echo ""
echo -e "${GREEN}Next steps:${NC}"
echo -e "${BLUE}  1. Run: ./.agent/scripts/start-hive-mind.sh${NC}"
echo -e "${BLUE}  2. Or use GitHub automation: ./.agent/scripts/github-issue-selector.sh --repo owner/repo${NC}"