#!/bin/bash

# Aperim Template - Install Claude Skills and Marketplaces Script
# Installs official Anthropic skills and Superpowers marketplace for Claude Code

set -uo pipefail

# Colours for output (Australian spelling)
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Colour

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo -e "${BLUE}Aperim Template: Installing Claude Skills and Marketplaces...${NC}"
echo ""

# Check if claude command is available
if ! command -v claude &> /dev/null; then
    echo -e "${RED}❌ Claude Code CLI not found${NC}"
    echo -e "${YELLOW}Please install Claude Code first using install-agent-tools.sh${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Claude Code CLI found${NC}"
CLAUDE_VERSION=$(claude --version 2>/dev/null || echo "unknown")
echo -e "${BLUE}Version: $CLAUDE_VERSION${NC}"
echo ""

# Function to add marketplace if not already added
add_marketplace() {
    local marketplace_source="$1"
    local marketplace_name="$2"

    echo -e "${BLUE}Checking marketplace: $marketplace_name...${NC}"

    # List marketplaces and check if already added
    if claude plugin marketplace list 2>/dev/null | grep -qi "$marketplace_name"; then
        echo -e "${GREEN}✅ $marketplace_name marketplace already configured${NC}"
        return 0
    fi

    # Add marketplace
    echo -e "${BLUE}Adding $marketplace_name marketplace from $marketplace_source...${NC}"
    if claude plugin marketplace add "$marketplace_source" 2>&1 | tee /tmp/marketplace-add.log; then
        # Verify it was added
        if claude plugin marketplace list 2>/dev/null | grep -qi "$marketplace_name"; then
            echo -e "${GREEN}✅ $marketplace_name marketplace added successfully${NC}"
            return 0
        else
            echo -e "${YELLOW}⚠️  Marketplace add command succeeded but marketplace not found in list${NC}"
            return 1
        fi
    else
        # Check if error is due to already existing
        if grep -qi "already exists\|already added" /tmp/marketplace-add.log; then
            echo -e "${GREEN}✅ $marketplace_name marketplace already exists${NC}"
            return 0
        else
            echo -e "${RED}❌ Failed to add $marketplace_name marketplace${NC}"
            return 1
        fi
    fi
}

# Function to install plugin from marketplace
install_plugin() {
    local plugin_name="$1"
    local marketplace_ref="$2"  # e.g., "superpowers@superpowers-marketplace"

    echo -e "${BLUE}Installing plugin: $plugin_name...${NC}"

    # Try to install the plugin
    if claude plugin install "$marketplace_ref" 2>&1 | tee /tmp/plugin-install.log; then
        echo -e "${GREEN}✅ $plugin_name installed successfully${NC}"
        return 0
    else
        # Check if already installed
        if grep -qi "already installed" /tmp/plugin-install.log; then
            echo -e "${GREEN}✅ $plugin_name already installed${NC}"
            return 0
        else
            echo -e "${RED}❌ Failed to install $plugin_name${NC}"
            cat /tmp/plugin-install.log
            return 1
        fi
    fi
}

# Counters for summary
MARKETPLACES_ADDED=0
PLUGINS_INSTALLED=0

echo -e "${YELLOW}=== Adding Marketplaces ===${NC}"
echo ""

# Add Superpowers Marketplace
if add_marketplace "obra/superpowers-marketplace" "superpowers-marketplace"; then
    MARKETPLACES_ADDED=$((MARKETPLACES_ADDED + 1))
fi
echo ""

# Add Anthropic Skills Marketplace
if add_marketplace "anthropics/skills" "skills"; then
    MARKETPLACES_ADDED=$((MARKETPLACES_ADDED + 1))
fi
echo ""

# Update all marketplaces to get latest content
echo -e "${BLUE}Updating all marketplaces...${NC}"
if claude plugin marketplace update 2>/dev/null; then
    echo -e "${GREEN}✅ Marketplaces updated${NC}"
else
    echo -e "${YELLOW}⚠️  Marketplace update may have failed (non-critical)${NC}"
fi
echo ""

echo -e "${YELLOW}=== Installing Plugins ===${NC}"
echo ""

# Install Superpowers plugin (entire plugin suite)
echo -e "${BLUE}Installing Superpowers plugin (comprehensive development workflow tools)...${NC}"
if install_plugin "superpowers" "superpowers@superpowers-marketplace"; then
    PLUGINS_INSTALLED=$((PLUGINS_INSTALLED + 1))
fi
echo ""

# Note: Anthropic skills are typically used individually as needed,
# not installed as plugins. They are activated via the Skill tool when needed.
echo -e "${BLUE}Note: Anthropic skills from the skills marketplace are available${NC}"
echo -e "${BLUE}      via the Skill tool and don't need individual installation.${NC}"
echo -e "${BLUE}      They will be available automatically in Claude sessions.${NC}"
echo ""

# List available skills from Anthropic marketplace
echo -e "${BLUE}Checking available skills from Anthropic marketplace...${NC}"
if claude plugin marketplace list 2>/dev/null | grep -q "skills"; then
    echo -e "${GREEN}✅ Anthropic skills marketplace is configured${NC}"
    echo -e "${BLUE}Skills are accessed using the Skill tool during Claude sessions${NC}"
fi
echo ""

echo -e "${YELLOW}=== Installation Summary ===${NC}"
echo ""
echo -e "${BLUE}Marketplaces added: $MARKETPLACES_ADDED/2${NC}"
echo -e "${BLUE}Plugins installed: $PLUGINS_INSTALLED/1${NC}"
echo ""

# List all configured marketplaces
echo -e "${BLUE}Configured marketplaces:${NC}"
if claude plugin marketplace list 2>/dev/null; then
    echo ""
else
    echo -e "${YELLOW}⚠️  Could not list marketplaces${NC}"
fi

# Cleanup temp files
rm -f /tmp/marketplace-add.log /tmp/plugin-install.log

if [ $MARKETPLACES_ADDED -ge 1 ] || [ $PLUGINS_INSTALLED -ge 1 ]; then
    echo -e "${GREEN}🚀 Skills and marketplaces installation completed${NC}"
    echo ""
    echo -e "${YELLOW}Available features:${NC}"
    echo -e "${BLUE}  • Superpowers: Advanced workflow tools including TDD, brainstorming, debugging${NC}"
    echo -e "${BLUE}  • Anthropic Skills: Official skills for various tasks (used via Skill tool)${NC}"
    echo ""
    echo -e "${YELLOW}Usage:${NC}"
    echo -e "${BLUE}  • Superpowers are automatically available in Claude sessions${NC}"
    echo -e "${BLUE}  • Skills are invoked with: Skill tool in Claude sessions${NC}"
    exit 0
else
    echo -e "${YELLOW}⚠️  No new marketplaces or plugins were added${NC}"
    echo -e "${BLUE}This may indicate they are already installed${NC}"
    exit 0
fi
