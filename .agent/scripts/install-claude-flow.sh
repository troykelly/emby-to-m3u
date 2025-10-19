#!/bin/bash

# Aperim Template - Install Claude-Flow Script
# Installs claude-flow@alpha globally with native bindings for ARM64 compatibility

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

echo -e "${BLUE}Aperim Template: Installing Claude-Flow...${NC}"

# Ensure tools directory exists for configuration
mkdir -p "$PROJECT_ROOT/.agent/tools"

# Detect architecture for ARM-specific handling
ARCH=$(uname -m)
echo -e "${BLUE}Detected architecture: $ARCH${NC}"

# Setup pnpm global bin directory if not configured
echo -e "${BLUE}Checking pnpm global configuration...${NC}"
if ! pnpm config get global-bin-dir >/dev/null 2>&1 || [ "$(pnpm config get global-bin-dir)" = "undefined" ]; then
    echo -e "${YELLOW}⚠️  pnpm global bin directory not configured${NC}"
    echo -e "${BLUE}Setting up pnpm global directories...${NC}"

    # Set up pnpm home directory
    PNPM_HOME="${HOME}/.local/share/pnpm"
    mkdir -p "$PNPM_HOME/bin"

    # Configure pnpm
    pnpm config set global-bin-dir "$PNPM_HOME/bin" --location=global
    pnpm config set global-dir "$PNPM_HOME/global" --location=global

    # Add to PATH for this session
    export PATH="$PNPM_HOME/bin:$PATH"

    echo -e "${GREEN}✅ pnpm global directories configured${NC}"
    echo -e "${BLUE}Global bin: $PNPM_HOME/bin${NC}"
else
    echo -e "${GREEN}✅ pnpm global configuration exists${NC}"
    PNPM_BIN_DIR=$(pnpm config get global-bin-dir)
    # Ensure it's in PATH for this session
    if [[ ":$PATH:" != *":$PNPM_BIN_DIR:"* ]]; then
        export PATH="$PNPM_BIN_DIR:$PATH"
    fi
fi

# Check if claude-flow is already installed globally
echo -e "${BLUE}Checking Claude-Flow installation...${NC}"
if command -v claude-flow >/dev/null 2>&1; then
    echo -e "${GREEN}✅ Claude-Flow is already installed globally${NC}"
    VERSION=$(claude-flow --version 2>/dev/null || echo "unknown")
    echo -e "${BLUE}Version: $VERSION${NC}"
    # Don't exit here - continue to initialization check below
else
    # Install claude-flow@alpha globally with pnpm
    # This compiles native bindings (like better-sqlite3) for the local architecture
    echo -e "${BLUE}Installing Claude-Flow globally with pnpm...${NC}"
    echo -e "${YELLOW}This may take a moment on first installation (compiling native bindings)...${NC}"

    if [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then
        echo -e "${YELLOW}⚠️  ARM64 detected - compiling native bindings for better-sqlite3...${NC}"
    fi

    # Install globally using pnpm (compiles native modules for current architecture)
    # Allow build scripts first
    echo -e "${BLUE}Configuring build script permissions...${NC}"
    pnpm config set enable-pre-post-scripts true --location=global

    if pnpm add -g claude-flow@alpha 2>&1; then
        echo -e "${GREEN}✅ Claude-Flow installed globally successfully${NC}"

        # On ARM64, pnpm may block build scripts even with config enabled
        # Manually compile better-sqlite3 for ARM64
        if [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then
            echo -e "${BLUE}Compiling better-sqlite3 native bindings for ARM64...${NC}"

            # Find the better-sqlite3 package in pnpm's global store
            BETTER_SQLITE_PATH=$(find /home/$USER/.local/share/pnpm/global -name "better-sqlite3" -type d | grep "node_modules/better-sqlite3$" | head -1)

            if [ -n "$BETTER_SQLITE_PATH" ]; then
                echo -e "${BLUE}Found better-sqlite3 at: $BETTER_SQLITE_PATH${NC}"
                cd "$BETTER_SQLITE_PATH"

                # Run the build script
                if npm run install 2>&1 | grep -q "gyp info ok"; then
                    echo -e "${GREEN}✅ Native bindings compiled successfully${NC}"

                    # Verify the binary was created
                    if [ -f "build/Release/better_sqlite3.node" ]; then
                        echo -e "${GREEN}✅ Verified: build/Release/better_sqlite3.node exists${NC}"
                        BINARY_SIZE=$(du -h "build/Release/better_sqlite3.node" | cut -f1)
                        echo -e "${BLUE}Binary size: $BINARY_SIZE${NC}"
                    else
                        echo -e "${YELLOW}⚠️  Binary not found, will use JSON fallback${NC}"
                    fi
                else
                    echo -e "${YELLOW}⚠️  Build may have failed, checking for binary...${NC}"
                    [ -f "build/Release/better_sqlite3.node" ] && echo -e "${GREEN}✅ Binary exists${NC}" || echo -e "${YELLOW}⚠️  Will use JSON fallback${NC}"
                fi

                cd "$PROJECT_ROOT"
            else
                echo -e "${YELLOW}⚠️  Could not locate better-sqlite3 package${NC}"
                echo -e "${YELLOW}⚠️  SQLite will not be available (JSON fallback)${NC}"
            fi
        fi

        # Verify installation
        if command -v claude-flow >/dev/null 2>&1; then
            VERSION=$(claude-flow --version 2>/dev/null || echo "unknown")
            echo -e "${BLUE}Installed version: $VERSION${NC}"
        else
            echo -e "${RED}❌ Installation succeeded but claude-flow not found in PATH${NC}"
            echo -e "${YELLOW}Refreshing PATH and checking again...${NC}"

            # Reload pnpm bin directory
            PNPM_BIN_DIR=$(pnpm config get global-bin-dir)
            export PATH="$PNPM_BIN_DIR:$PATH"

            if command -v claude-flow >/dev/null 2>&1; then
                echo -e "${GREEN}✅ Found claude-flow after PATH refresh${NC}"
                VERSION=$(claude-flow --version 2>/dev/null || echo "unknown")
                echo -e "${BLUE}Version: $VERSION${NC}"
            else
                echo -e "${YELLOW}⚠️  Add this to your shell profile (~/.bashrc or ~/.zshrc):${NC}"
                echo -e "${BLUE}export PATH=\"$PNPM_BIN_DIR:\$PATH\"${NC}"
            fi
        fi
    else
        echo -e "${RED}❌ Failed to install Claude-Flow globally${NC}"
        echo -e "${YELLOW}Error details printed above. Common issues:${NC}"
        echo -e "${BLUE}1. Node.js version mismatch (requires Node 18+)${NC}"
        echo -e "${BLUE}2. Permissions issue (try without sudo)${NC}"
        echo -e "${BLUE}3. Network connectivity${NC}"
        echo -e "${YELLOW}Falling back to npx (may have ARM64 SQLite issues)...${NC}"
    fi
fi

# All installation is done above, now continue to configuration

# Create configuration directory
mkdir -p "$PROJECT_ROOT/.agent/configs/claude-flow"

# Create basic configuration
cat > "$PROJECT_ROOT/.agent/configs/claude-flow/config.json" << EOF
{
    "version": "2.0.0-alpha",
    "installation": {
        "method": "pnpm-global",
        "architecture": "$ARCH",
        "installedAt": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
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
    # Run init with actual error checking using global installation
    INIT_CMD="claude-flow"
    # Fallback to npx if global command not available
    if ! command -v claude-flow >/dev/null 2>&1; then
        echo -e "${YELLOW}⚠️  Global claude-flow not found, using npx fallback...${NC}"
        INIT_CMD="npx --yes claude-flow@alpha"
    fi

    if $INIT_CMD init --force 2>&1; then
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
if command -v claude-flow >/dev/null 2>&1; then
    echo -e "${BLUE}Method: Global installation (pnpm)${NC}"
    echo -e "${BLUE}Location: $(which claude-flow)${NC}"

    # Add PATH to shell profiles automatically
    PNPM_BIN_DIR=$(pnpm config get global-bin-dir 2>/dev/null)
    if [ -n "$PNPM_BIN_DIR" ] && [ "$PNPM_BIN_DIR" != "undefined" ]; then
        # Add to .bashrc if it exists and PATH not already configured
        if [ -f "$HOME/.bashrc" ] && ! grep -q "pnpm/bin" "$HOME/.bashrc" 2>/dev/null; then
            echo "" >> "$HOME/.bashrc"
            echo "# Added by claude-flow installation" >> "$HOME/.bashrc"
            echo "export PATH=\"$PNPM_BIN_DIR:\$PATH\"" >> "$HOME/.bashrc"
            echo -e "${GREEN}✅ Added PATH to ~/.bashrc${NC}"
        fi

        # Add to .zshrc if it exists and PATH not already configured
        if [ -f "$HOME/.zshrc" ] && ! grep -q "pnpm/bin" "$HOME/.zshrc" 2>/dev/null; then
            echo "" >> "$HOME/.zshrc"
            echo "# Added by claude-flow installation" >> "$HOME/.zshrc"
            echo "export PATH=\"$PNPM_BIN_DIR:\$PATH\"" >> "$HOME/.zshrc"
            echo -e "${GREEN}✅ Added PATH to ~/.zshrc${NC}"
        fi

        echo ""
        echo -e "${YELLOW}💡 PATH configured for future shells${NC}"
        echo -e "${BLUE}Current session PATH already includes: $PNPM_BIN_DIR${NC}"
    fi
else
    echo -e "${BLUE}Method: NPX fallback (may have ARM64 SQLite limitations)${NC}"
fi
echo -e "${BLUE}Configuration: $PROJECT_ROOT/.agent/configs/claude-flow/config.json${NC}"
echo ""
echo -e "${YELLOW}Usage:${NC}"
if command -v claude-flow >/dev/null 2>&1; then
    echo -e "${BLUE}  claude-flow --help${NC}"
    echo -e "${BLUE}  claude-flow hive-mind spawn \"My Project\"${NC}"
else
    echo -e "${BLUE}  npx --yes claude-flow@alpha --help${NC}"
    echo -e "${BLUE}  npx --yes claude-flow@alpha hive-mind spawn \"My Project\"${NC}"
fi
echo ""
echo -e "${GREEN}Next steps:${NC}"
echo -e "${BLUE}  1. Run: ./.agent/scripts/start-hive-mind.sh${NC}"
echo -e "${BLUE}  2. Or use GitHub automation: ./.agent/scripts/github-issue-selector.sh --repo owner/repo${NC}"