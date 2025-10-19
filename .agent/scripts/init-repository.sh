#!/bin/bash

# Aperim Template - Repository Initialisation Script
# Runs all configuration scripts in proper order

set -uo pipefail
# Don't use -e (exit on error) since some sub-scripts may have non-critical failures
# We want to continue and report all issues, not fail on first error

# Colours for output (Australian spelling)
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Colour

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo -e "${BLUE}🚀 Aperim Template: Initialising Repository...${NC}"
echo -e "${BLUE}Project Root: $PROJECT_ROOT${NC}"
echo ""

# Change to project root
cd "$PROJECT_ROOT"

# Create necessary directories
echo -e "${BLUE}📁 Creating directory structure...${NC}"
mkdir -p .agent/temp .agent/logs .agent/cache logs

# Set up Git configuration
echo -e "${BLUE}🔧 Configuring Git...${NC}"
git config --local core.autocrlf input
git config --local init.defaultBranch main

# Verify environment file
echo -e "${BLUE}🔧 Checking environment configuration...${NC}"
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo -e "${YELLOW}Creating .env from .env.example...${NC}"
        cp .env.example .env
        echo -e "${YELLOW}⚠️  Please update .env with your actual credentials${NC}"
    else
        echo -e "${YELLOW}⚠️  No .env.example found${NC}"
    fi
else
    echo -e "${GREEN}✅ .env file exists${NC}"
fi

# Install and initialize Claude-Flow (the script handles everything including init)
echo -e "${BLUE}🤖 Installing Claude-Flow...${NC}"
if [ -x "$SCRIPT_DIR/install-claude-flow.sh" ]; then
    "$SCRIPT_DIR/install-claude-flow.sh"
else
    echo -e "${YELLOW}⚠️  install-claude-flow.sh not found or not executable${NC}"
fi

# Verify Claude-Flow initialization
if [ -f ".claude-flow.json" ]; then
    echo -e "${GREEN}✅ Claude-Flow configuration verified${NC}"
else
    echo -e "${YELLOW}⚠️  Claude-Flow configuration file not found, some features may not work${NC}"
fi

# Install Agent Tools
echo -e "${BLUE}🛠️  Installing Agent Tools...${NC}"
if [ -x "$SCRIPT_DIR/install-agent-tools.sh" ]; then
    "$SCRIPT_DIR/install-agent-tools.sh"
else
    echo -e "${YELLOW}⚠️  install-agent-tools.sh not found or not executable${NC}"
fi

# Install MCP Servers
echo -e "${BLUE}🔌 Installing MCP Servers...${NC}"
if [ -x "$SCRIPT_DIR/install-mcp-servers.sh" ]; then
    "$SCRIPT_DIR/install-mcp-servers.sh"
else
    echo -e "${YELLOW}⚠️  install-mcp-servers.sh not found or not executable${NC}"
fi

# Install Claude Skills and Marketplaces
echo -e "${BLUE}🎓 Installing Claude Skills and Marketplaces...${NC}"
if [ -x "$SCRIPT_DIR/install-claude-skills.sh" ]; then
    "$SCRIPT_DIR/install-claude-skills.sh" || echo -e "${YELLOW}⚠️  Skills installation had some issues (non-critical)${NC}"
else
    echo -e "${YELLOW}⚠️  install-claude-skills.sh not found or not executable${NC}"
fi

# Source agent tools environment
echo -e "${BLUE}🔧 Setting up tool environment...${NC}"
if [ -f ".agent/configs/agent-tools-env.sh" ]; then
    source .agent/configs/agent-tools-env.sh
    echo -e "${GREEN}✅ Agent tools environment loaded${NC}"
else
    echo -e "${YELLOW}⚠️  agent-tools-env.sh not found${NC}"
fi

# Run validation
echo -e "${BLUE}✅ Running validation...${NC}"
if [ -x "$SCRIPT_DIR/validate-setup.sh" ]; then
    # Don't fail if validation finds issues, just report them
    "$SCRIPT_DIR/validate-setup.sh" || echo -e "${YELLOW}⚠️  Some validation checks failed (non-critical, review output above)${NC}"
else
    echo -e "${YELLOW}⚠️  validate-setup.sh not found, skipping validation${NC}"
fi

# Set proper permissions on all scripts
echo -e "${BLUE}🔧 Setting script permissions...${NC}"
find .agent/scripts -name "*.sh" -type f -exec chmod +x {} \;

echo ""
echo -e "${GREEN}🎉 Repository initialisation completed!${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo -e "${BLUE}1. Update .env with your actual credentials${NC}"
echo -e "${BLUE}2. Start devcontainer: ./.agent/scripts/start-devcontainer.sh${NC}"
echo -e "${BLUE}3. Start Claude-Flow hive-mind: ./.agent/scripts/start-hive-mind.sh${NC}"
echo -e "${BLUE}4. Begin development with agent assistance!${NC}"
echo ""
echo -e "${BLUE}📚 Documentation available in .agent/docs/${NC}"
echo -e "${BLUE}🔧 Scripts available in .agent/scripts/${NC}"
echo -e "${BLUE}⚙️  Configuration in .agent/configs/${NC}"