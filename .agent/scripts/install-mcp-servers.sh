#!/bin/bash

# Aperim Template - Install MCP Servers Script
# Safely installs MCP servers for Claude and Codex without duplicates

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

echo -e "${BLUE}Aperim Template: Installing MCP Servers...${NC}"
echo ""

# Function to check if an MCP server is already installed
is_mcp_installed() {
    local tool="$1"
    local server_name="$2"
    local scope="${3:-user}"

    # Check if the tool exists
    if ! command -v "$tool" &> /dev/null; then
        echo -e "${YELLOW}⚠️  $tool not found, skipping MCP checks${NC}"
        return 1
    fi

    # List MCPs and check if server exists
    # Using CI=true to avoid interactive prompts
    # Note: Use conditional --scope parameter (codex doesn't support it)
    local mcp_list
    if mcp_list=$(CI=true "$tool" mcp list ${scope:+--scope "$scope"} 2>/dev/null); then
        # Check multiple patterns: quoted name, unquoted name, or as a key
        if echo "$mcp_list" | grep -qE "(\"$server_name\"|^$server_name:|  $server_name:)"; then
            return 0  # Already installed
        fi
    fi

    return 1  # Not installed
}

# Function to safely add MCP server
add_mcp_server() {
    local tool="$1"
    local server_name="$2"
    local scope="$3"
    shift 3
    local command_args=("$@")

    echo -e "${BLUE}Checking $tool MCP: $server_name...${NC}"

    # Check if tool exists
    if ! command -v "$tool" &> /dev/null; then
        echo -e "${YELLOW}⚠️  $tool not installed, skipping $server_name${NC}"
        return 1
    fi

    # Check if MCP already installed
    if is_mcp_installed "$tool" "$server_name" "$scope"; then
        echo -e "${GREEN}✅ $server_name already installed for $tool${NC}"
        return 0
    fi

    # Install MCP
    echo -e "${BLUE}Installing $server_name for $tool...${NC}"

    # Build the full command
    local full_command="CI=true $tool mcp add \"$server_name\" --scope \"$scope\""

    # Add command arguments
    if [ ${#command_args[@]} -gt 0 ]; then
        full_command="$full_command ${command_args[*]}"
    fi

    # Execute the command
    if eval "$full_command" 2>&1 | tee /tmp/mcp-install.log; then
        # Check the log for "already exists" message first (this is success!)
        if grep -qi "already exists\|already installed" /tmp/mcp-install.log; then
            echo -e "${GREEN}✅ $server_name already exists for $tool${NC}"
            return 0
        fi

        # Check if installation was successful
        if is_mcp_installed "$tool" "$server_name" "$scope"; then
            echo -e "${GREEN}✅ $server_name installed successfully for $tool${NC}"
            return 0
        else
            echo -e "${YELLOW}⚠️  $server_name installation unclear, check manually${NC}"
            return 1
        fi
    else
        # Command failed - check if it's because it already exists
        if grep -qi "already exists\|already installed" /tmp/mcp-install.log; then
            echo -e "${GREEN}✅ $server_name already exists for $tool${NC}"
            return 0
        else
            echo -e "${RED}❌ Failed to install $server_name for $tool${NC}"
            return 1
        fi
    fi
}

# MCP servers to install
declare -A MCP_SERVERS=(
    ["puppeteer"]='--env "PUPPETEER_LAUNCH_OPTIONS={\"headless\":true,\"args\":[\"--no-sandbox\",\"--disable-setuid-sandbox\"]}" -- pnpm dlx @modelcontextprotocol/server-puppeteer@latest'
    ["playwright"]='-- pnpm dlx "@executeautomation/playwright-mcp-server@latest"'
    ["memory"]='-- pnpm dlx "@modelcontextprotocol/server-memory"'
    ["sequential-thinking"]='-- pnpm dlx "@modelcontextprotocol/server-sequential-thinking"'
    ["fetch"]='-- docker run -i --rm --init --pull=always mcp/fetch'
    ["calculator"]='-- uvx mcp-server-calculator'
    ["git"]='-- uvx mcp-server-git'
    ["time"]='-- uvx mcp-server-time'
)

# Install MCPs for Claude
echo -e "${BLUE}=== Installing MCP Servers for Claude ===${NC}"
echo ""

CLAUDE_INSTALLED=0
CLAUDE_TOTAL=0

for server_name in "${!MCP_SERVERS[@]}"; do
    CLAUDE_TOTAL=$((CLAUDE_TOTAL + 1))

    # Get the command arguments for this server
    command_args="${MCP_SERVERS[$server_name]}"

    # Add MCP server
    if add_mcp_server "claude" "$server_name" "user" $command_args; then
        CLAUDE_INSTALLED=$((CLAUDE_INSTALLED + 1))
    fi

    echo ""
done

# Install MCPs for Codex
echo -e "${BLUE}=== Installing MCP Servers for Codex ===${NC}"
echo ""

CODEX_INSTALLED=0
CODEX_TOTAL=0

for server_name in "${!MCP_SERVERS[@]}"; do
    CODEX_TOTAL=$((CODEX_TOTAL + 1))

    echo -e "${BLUE}Checking codex MCP: $server_name...${NC}"

    # Check if codex is installed
    if ! command -v "codex" &> /dev/null; then
        echo -e "${YELLOW}⚠️  codex not installed, skipping $server_name${NC}"
        echo ""
        continue
    fi

    # Extract the command and environment variables
    full_command="${MCP_SERVERS[$server_name]}"

    # Remove leading "-- " or "--env ... -- " prefix
    if [[ "$full_command" =~ ^--env[[:space:]]+(.*)[[:space:]]--[[:space:]]+(.*) ]]; then
        # Has environment variable
        env_var="${BASH_REMATCH[1]}"
        command_part="${BASH_REMATCH[2]}"
        has_env=true
    else
        # No environment variable, just remove leading "--"
        command_part="${full_command#-- }"
        has_env=false
    fi

    echo -e "${BLUE}Installing $server_name for codex...${NC}"

    # Build the codex mcp add command
    # Syntax: codex mcp add [--env KEY=VALUE] [command tokens...] <name>
    if [ "$has_env" = true ]; then
        # With environment variable
        if CI=true codex mcp add --env "$env_var" $command_part "$server_name" 2>&1 | tee /tmp/mcp-install-codex.log; then
            echo -e "${GREEN}✅ $server_name installed for codex${NC}"
            CODEX_INSTALLED=$((CODEX_INSTALLED + 1))
        else
            if grep -qi "already exists\|already added\|already configured" /tmp/mcp-install-codex.log 2>/dev/null; then
                echo -e "${GREEN}✅ $server_name already exists for codex${NC}"
                CODEX_INSTALLED=$((CODEX_INSTALLED + 1))
            else
                echo -e "${YELLOW}⚠️  $server_name installation failed for codex${NC}"
                cat /tmp/mcp-install-codex.log | head -3
            fi
        fi
    else
        # Without environment variable - command tokens can be multiple words
        if CI=true codex mcp add $command_part "$server_name" 2>&1 | tee /tmp/mcp-install-codex.log; then
            echo -e "${GREEN}✅ $server_name installed for codex${NC}"
            CODEX_INSTALLED=$((CODEX_INSTALLED + 1))
        else
            if grep -qi "already exists\|already added\|already configured" /tmp/mcp-install-codex.log 2>/dev/null; then
                echo -e "${GREEN}✅ $server_name already exists for codex${NC}"
                CODEX_INSTALLED=$((CODEX_INSTALLED + 1))
            else
                echo -e "${YELLOW}⚠️  $server_name installation failed for codex${NC}"
                cat /tmp/mcp-install-codex.log | head -3
            fi
        fi
    fi

    echo ""
done

# Cleanup codex log
rm -f /tmp/mcp-install-codex.log

# Summary
echo -e "${BLUE}=== MCP Installation Summary ===${NC}"
echo ""
echo -e "${BLUE}Claude MCPs: $CLAUDE_INSTALLED/$CLAUDE_TOTAL installed${NC}"
echo -e "${BLUE}Codex MCPs: $CODEX_INSTALLED/$CODEX_TOTAL installed${NC}"
echo ""

if [ $CLAUDE_INSTALLED -gt 0 ] || [ $CODEX_INSTALLED -gt 0 ]; then
    echo -e "${GREEN}🚀 MCP servers installation completed${NC}"
    echo ""
    echo -e "${YELLOW}Installed MCPs:${NC}"

    # List installed MCPs
    if command -v claude &> /dev/null; then
        echo -e "${BLUE}Claude:${NC}"
        CI=true claude mcp list --scope user 2>/dev/null | grep -E "^\s*-" || echo "  (none)"
    fi

    if command -v codex &> /dev/null; then
        echo -e "${BLUE}Codex:${NC}"
        CI=true codex mcp list 2>/dev/null | grep -E "^\s*-" || echo "  (none)"
    fi
else
    echo -e "${YELLOW}⚠️  No MCP servers were installed${NC}"
    echo -e "${BLUE}This may be because:${NC}"
    echo -e "${BLUE}  - claude or codex are not installed${NC}"
    echo -e "${BLUE}  - All MCPs are already installed${NC}"
    echo -e "${BLUE}  - Network connectivity issues${NC}"
fi

echo ""
echo -e "${GREEN}✅ MCP installation script completed${NC}"

# Cleanup
rm -f /tmp/mcp-install.log
