#!/bin/bash

# Aperim Template - Install Agent Tools Script
# Installs claude-code, codex, opencode, and spec-kit CLI tools

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
# Use system-appropriate tools directory
if [[ -n "${HOME:-}" ]]; then
    TOOLS_DIR="$HOME/.local/bin"
elif [[ -w "/usr/local/bin" ]]; then
    TOOLS_DIR="/usr/local/bin"
else
    # Fallback to project-local (gitignored)
    TOOLS_DIR="$PROJECT_ROOT/.agent/tools/bin"
fi

echo -e "${BLUE}Aperim Template: Installing Agent Tools...${NC}"
echo -e "${BLUE}📁 Installing to: $TOOLS_DIR${NC}"

# Ensure tools directory exists
mkdir -p "$TOOLS_DIR"

# Detect architecture
ARCH=$(uname -m)
case $ARCH in
    x86_64)
        ARCH_NAME="x64"
        ;;
    arm64|aarch64)
        ARCH_NAME="arm64"
        ;;
    *)
        echo -e "${RED}❌ Unsupported architecture: $ARCH${NC}"
        exit 1
        ;;
esac

# Detect OS
OS=$(uname -s)
case $OS in
    Darwin)
        OS_NAME="macos"
        ;;
    Linux)
        OS_NAME="linux"
        ;;
    *)
        echo -e "${RED}❌ Unsupported operating system: $OS${NC}"
        exit 1
        ;;
esac

echo -e "${BLUE}Detected platform: $OS_NAME-$ARCH_NAME${NC}"

# Function to download and install a tool
install_tool() {
    local tool_name="$1"
    local download_url="$2"
    local executable_name="$3"
    
    echo -e "${BLUE}Installing $tool_name...${NC}"
    
    local temp_file="/tmp/${tool_name}-installer"
    local target_file="$TOOLS_DIR/$executable_name"
    
    # Download the tool
    echo -e "${BLUE}  Downloading from: $download_url${NC}"
    if ! curl -L -o "$temp_file" "$download_url"; then
        echo -e "${RED}❌ Failed to download $tool_name${NC}"
        return 1
    fi
    
    # Make executable and move to tools directory
    chmod +x "$temp_file"
    mv "$temp_file" "$target_file"
    
    # Verify installation
    if [ -f "$target_file" ] && [ -x "$target_file" ]; then
        echo -e "${GREEN}✅ $tool_name installed successfully${NC}"
        
        # Test the tool
        if "$target_file" --version >/dev/null 2>&1 || "$target_file" version >/dev/null 2>&1 || "$target_file" --help >/dev/null 2>&1; then
            echo -e "${GREEN}✅ $tool_name is working${NC}"
        else
            echo -e "${YELLOW}⚠️  $tool_name installed but may not be working properly${NC}"
        fi
        
        return 0
    else
        echo -e "${RED}❌ Failed to install $tool_name${NC}"
        return 1
    fi
}

# Install Claude-Code CLI
echo -e "${BLUE}=== Installing Claude-Code CLI ===${NC}"

# Use official Claude-Code installer that handles architecture detection
echo -e "${BLUE}Installing Claude-Code using official installer...${NC}"
if curl -fsSL https://claude.ai/install.sh | bash; then
    echo -e "${GREEN}✅ Claude-Code installed successfully${NC}"
    
    # Verify installation
    if command -v claude &> /dev/null; then
        VERSION=$(claude --version 2>/dev/null || echo "unknown")
        echo -e "${BLUE}Claude-Code version: $VERSION${NC}"
        
        # Get the actual path of claude
        CLAUDE_PATH=$(which claude)
        CLAUDE_REAL=$(readlink -f "$CLAUDE_PATH" 2>/dev/null || echo "$CLAUDE_PATH")
        
        # Only create symlink if it wouldn't be circular
        if [ "$CLAUDE_REAL" != "$TOOLS_DIR/claude" ] && [ "$CLAUDE_PATH" != "$TOOLS_DIR/claude" ]; then
            ln -sf "$CLAUDE_REAL" "$TOOLS_DIR/claude" 2>/dev/null || echo -e "${YELLOW}Could not create symlink${NC}"
        else
            echo -e "${GREEN}✅ Claude already available in $TOOLS_DIR${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️  Claude-Code installed but not in PATH${NC}"
        # Check if it's in ~/.local/bin
        if [ -f "$HOME/.local/bin/claude" ] && [ "$HOME/.local/bin" != "$TOOLS_DIR" ]; then
            echo -e "${BLUE}Found Claude-Code in ~/.local/bin${NC}"
            CLAUDE_REAL=$(readlink -f "$HOME/.local/bin/claude" 2>/dev/null || echo "$HOME/.local/bin/claude")
            ln -sf "$CLAUDE_REAL" "$TOOLS_DIR/claude"
            echo -e "${GREEN}✅ Created symlink to tools directory${NC}"
        fi
    fi
else
    echo -e "${RED}❌ Claude-Code installation failed${NC}"
fi

# Install Codex CLI
echo -e "${BLUE}=== Installing Codex CLI ===${NC}"

# Get latest Codex release from GitHub API
echo -e "${BLUE}Fetching latest Codex release info...${NC}"
CODEX_RELEASE_JSON=$(curl -s https://api.github.com/repos/openai/codex/releases/latest)
CODEX_TAG=$(echo "$CODEX_RELEASE_JSON" | grep '"tag_name"' | cut -d'"' -f4)

if [ -z "$CODEX_TAG" ]; then
    echo -e "${RED}❌ Could not fetch Codex release info${NC}"
else
    echo -e "${BLUE}Latest Codex release: $CODEX_TAG${NC}"
    
    # Determine which binary variants to try based on platform
    # For Linux, we'll try both gnu (preferred for performance) and musl (better compatibility)
    # For macOS, only darwin binaries are available
    CODEX_BINARY_VARIANTS=()

    if [ "$OS_NAME" = "linux" ]; then
        # For Linux, set up both gnu and musl variants to try
        if [ "$ARCH_NAME" = "arm64" ]; then
            CODEX_BINARY_VARIANTS=("codex-aarch64-unknown-linux-gnu" "codex-aarch64-unknown-linux-musl")
        else
            CODEX_BINARY_VARIANTS=("codex-x86_64-unknown-linux-gnu" "codex-x86_64-unknown-linux-musl")
        fi
    elif [ "$OS_NAME" = "macos" ]; then
        # For macOS, only darwin binaries available
        if [ "$ARCH_NAME" = "arm64" ]; then
            CODEX_BINARY_VARIANTS=("codex-aarch64-apple-darwin")
        else
            CODEX_BINARY_VARIANTS=("codex-x86_64-apple-darwin")
        fi
    else
        echo -e "${RED}❌ Unsupported platform for Codex: $OS_NAME-$ARCH_NAME${NC}"
        continue
    fi

    # Try each variant until one works
    CODEX_INSTALLED=false
    for CODEX_BINARY_BASE in "${CODEX_BINARY_VARIANTS[@]}"; do
        # Skip if already installed from a previous variant
        if [ "$CODEX_INSTALLED" = true ]; then
            break
        fi

        CODEX_URL="https://github.com/openai/codex/releases/download/$CODEX_TAG/${CODEX_BINARY_BASE}.tar.gz"
        echo -e "${BLUE}Trying: $CODEX_BINARY_BASE${NC}"
        echo -e "${BLUE}Downloading: $CODEX_URL${NC}"

        # Download and install
        TEMP_DIR="/tmp/codex-install-$$"
        mkdir -p "$TEMP_DIR"

        if curl -fsSL -o "$TEMP_DIR/codex.tar.gz" "$CODEX_URL"; then
            # Check if we actually downloaded a valid file using portable wc command
            if [ -f "$TEMP_DIR/codex.tar.gz" ]; then
                FILE_SIZE=$(wc -c < "$TEMP_DIR/codex.tar.gz" | tr -d ' ')
                if [ "$FILE_SIZE" -lt 1000 ]; then
                    echo -e "${YELLOW}⚠️  Downloaded file too small ($FILE_SIZE bytes), trying next variant...${NC}"
                    rm -rf "$TEMP_DIR"
                    continue
                fi

                # Extract in temp dir (use subshell to preserve working directory)
                echo -e "${BLUE}Extracting Codex archive...${NC}"
                (cd "$TEMP_DIR" && tar -xzf codex.tar.gz) 2>/dev/null

                if [ $? -eq 0 ]; then
                    # The archive contains a binary with the platform-specific name
                    EXTRACTED_BINARY="$TEMP_DIR/$CODEX_BINARY_BASE"

                    # Check if the expected binary exists
                    if [ -f "$EXTRACTED_BINARY" ]; then
                        echo -e "${BLUE}Found binary: $CODEX_BINARY_BASE${NC}"

                        # Verify it's actually a binary (not a text file/redirect error)
                        if file "$EXTRACTED_BINARY" | grep -qi "executable\|binary"; then
                            # Test if the binary can run (check for GLIBC compatibility)
                            if "$EXTRACTED_BINARY" --help >/dev/null 2>&1; then
                                # Binary works! Install it
                                mv "$EXTRACTED_BINARY" "$TOOLS_DIR/codex"
                                chmod +x "$TOOLS_DIR/codex"
                                echo -e "${GREEN}✅ Codex CLI installed successfully (variant: ${CODEX_BINARY_BASE})${NC}"

                                # Verify installation
                                if "$TOOLS_DIR/codex" --version >/dev/null 2>&1; then
                                    VERSION=$("$TOOLS_DIR/codex" --version 2>/dev/null || echo "unknown")
                                    echo -e "${BLUE}Codex version: $VERSION${NC}"
                                fi

                                CODEX_INSTALLED=true
                                rm -rf "$TEMP_DIR"
                                break
                            else
                                # Binary doesn't work (likely GLIBC incompatibility), try next variant
                                echo -e "${YELLOW}⚠️  Binary incompatible with system (likely GLIBC version), trying next variant...${NC}"
                                rm -rf "$TEMP_DIR"
                                continue
                            fi
                        else
                            echo -e "${YELLOW}⚠️  Extracted file is not a valid binary, trying next variant...${NC}"
                            rm -rf "$TEMP_DIR"
                            continue
                        fi
                    else
                        echo -e "${YELLOW}⚠️  Could not find expected binary, trying next variant...${NC}"
                        rm -rf "$TEMP_DIR"
                        continue
                    fi
                else
                    echo -e "${YELLOW}⚠️  Failed to extract archive, trying next variant...${NC}"
                    rm -rf "$TEMP_DIR"
                    continue
                fi
            else
                echo -e "${YELLOW}⚠️  Download failed, trying next variant...${NC}"
                rm -rf "$TEMP_DIR"
                continue
            fi
        else
            echo -e "${YELLOW}⚠️  Failed to download, trying next variant...${NC}"
            rm -rf "$TEMP_DIR"
            continue
        fi
    done

    # Check if installation succeeded
    if [ "$CODEX_INSTALLED" != true ]; then
        echo -e "${RED}❌ Failed to install Codex CLI - tried all available variants${NC}"
        echo -e "${YELLOW}Variants tried: ${CODEX_BINARY_VARIANTS[*]}${NC}"
    fi
fi

# Install OpenCode
echo -e "${BLUE}=== Installing OpenCode ===${NC}"

# Use official OpenCode installer from opencode.ai with better error handling
echo -e "${BLUE}Installing OpenCode using official installer...${NC}"

# Create a temporary directory in a known-good location
OPENCODE_TEMP="/tmp/opencode-install-$$"
mkdir -p "$OPENCODE_TEMP"
cd "$OPENCODE_TEMP"

# Try the official installer with explicit temp directory - disable error exit for this section
set +e
# Export PATH additions before running installer
export PATH="$HOME/.local/bin:$PATH"
if TMPDIR="$OPENCODE_TEMP" curl -fsSL https://opencode.ai/install | bash; then
    # Refresh PATH from installer updates
    export PATH="$HOME/.local/bin:$PATH"
    # Give installer time to complete file operations
    sleep 2
    echo -e "${GREEN}✅ OpenCode installed successfully${NC}"
    
    # Try to find OpenCode in the PATH that was just updated
    # Note: We can't reliably source .zshrc from bash, so we'll check known locations
    # The installer typically adds it to ~/.local/bin
    export PATH="$HOME/.local/bin:$PATH"
    
    # Verify installation and find the binary
    if command -v opencode &> /dev/null; then
        # Get version safely
        VERSION="unknown"
        opencode --version &>/dev/null && VERSION=$(opencode --version 2>/dev/null | head -1) || true
        echo -e "${BLUE}OpenCode version: $VERSION${NC}"
        
        # Create symlink in tools directory
        OPENCODE_PATH=$(which opencode 2>/dev/null || true)
        if [ -n "$OPENCODE_PATH" ]; then
            ln -sf "$OPENCODE_PATH" "$TOOLS_DIR/opencode" 2>/dev/null || echo -e "${YELLOW}Could not create symlink${NC}"
        fi
    else
        # Check common installation locations including ~/.local/bin
        for path in "$HOME/.local/bin/opencode" "$HOME/bin/opencode" "$HOME/.config/opencode/bin/opencode"; do
            if [ -f "$path" ] && [ -x "$path" ]; then
                echo -e "${BLUE}Found OpenCode at: $path${NC}"
                ln -sf "$path" "$TOOLS_DIR/opencode"
                echo -e "${GREEN}✅ Created symlink to tools directory${NC}"
                # Also add to PATH if needed
                if [ "$TOOLS_DIR" != "$(dirname "$path")" ]; then
                    export PATH="$(dirname "$path"):$PATH"
                fi
                # Get version safely
                VERSION="unknown"
                "$path" --version &>/dev/null && VERSION=$("$path" --version 2>/dev/null | head -1) || true
                echo -e "${BLUE}OpenCode version: $VERSION${NC}"
                break
            fi
        done
    fi
else
    echo -e "${YELLOW}Official installer failed, trying manual installation...${NC}"
    
    # Manual installation as fallback
    echo -e "${BLUE}Attempting manual installation...${NC}"
    
    # Try npm installation as fallback
    if command -v npm &> /dev/null; then
        echo -e "${BLUE}Trying npm installation...${NC}"
        if npm install -g opencode-ai --silent; then
            echo -e "${GREEN}✅ OpenCode installed via npm${NC}"
            
            # Find and symlink the binary
            if command -v opencode &> /dev/null; then
                ln -sf "$(which opencode)" "$TOOLS_DIR/opencode" 2>/dev/null || true
            fi
        else
            echo -e "${RED}❌ npm installation also failed${NC}"
        fi
    else
        echo -e "${RED}❌ OpenCode installation failed - no npm available for fallback${NC}"
    fi
fi
set -e

# Cleanup temp directory
rm -rf "$OPENCODE_TEMP"

# Return to project root
cd "$PROJECT_ROOT"

# Install spec-kit CLI
echo -e "${BLUE}=== Installing spec-kit CLI ===${NC}"

# spec-kit can be installed via multiple methods:
# 1. npm (preferred for Node.js environments)
# 2. uvx (Python tool installer)
# 3. bun (if available)
# We'll try methods in order of preference

SPECKIT_INSTALLED=false

# Method 1: Try npm installation (most reliable when it works)
# Note: @spec-kit/cli may have workspace dependency issues
if command -v npm &> /dev/null; then
    echo -e "${BLUE}Trying npm installation...${NC}"
    # Capture stderr to check for workspace errors (with timeout to avoid hangs)
    NPM_ERROR=$(timeout 30 npm install -g @spec-kit/cli 2>&1 >/dev/null || true)
    NPM_EXIT_CODE=$?
    if [ $NPM_EXIT_CODE -eq 0 ]; then
        echo -e "${GREEN}✅ spec-kit installed successfully via npm${NC}"

        # Verify installation (spec-kit doesn't support --version, use --help)
        if command -v specify &> /dev/null; then
            if specify --help >/dev/null 2>&1; then
                echo -e "${BLUE}spec-kit CLI ready${NC}"

                # Create symlink in tools directory if not already there
                SPECIFY_PATH=$(which specify)
                if [ -n "$SPECIFY_PATH" ] && [ "$SPECIFY_PATH" != "$TOOLS_DIR/specify" ]; then
                    ln -sf "$SPECIFY_PATH" "$TOOLS_DIR/specify" 2>/dev/null || true
                fi
                SPECKIT_INSTALLED=true
            fi
        else
            echo -e "${YELLOW}⚠️  spec-kit installed but not found in PATH${NC}"
            # Check common npm global bin locations
            for path in "$HOME/.npm-global/bin/specify" "$(npm root -g)/../bin/specify" "/usr/local/bin/specify"; do
                if [ -f "$path" ] && [ -x "$path" ]; then
                    echo -e "${BLUE}Found spec-kit at: $path${NC}"
                    ln -sf "$path" "$TOOLS_DIR/specify"
                    echo -e "${GREEN}✅ Created symlink to tools directory${NC}"
                    SPECKIT_INSTALLED=true
                    break
                fi
            done
        fi
    elif [ $NPM_EXIT_CODE -eq 124 ]; then
        echo -e "${YELLOW}⚠️  npm installation timed out, trying alternative methods...${NC}"
    else
        # Check if it's a workspace dependency issue
        if echo "$NPM_ERROR" | grep -q "EUNSUPPORTEDPROTOCOL\|workspace:"; then
            echo -e "${YELLOW}⚠️  npm package has workspace dependencies, trying alternative methods...${NC}"
        else
            echo -e "${YELLOW}⚠️  npm installation failed, trying alternative methods...${NC}"
        fi
    fi
fi

# Method 2: Try uvx installation (recommended for spec-kit)
if [ "$SPECKIT_INSTALLED" != true ] && command -v uvx &> /dev/null; then
    echo -e "${BLUE}Installing spec-kit via uvx (recommended method)...${NC}"

    # uvx can install from git repository - test with --help since --version isn't supported
    if uvx --from git+https://github.com/github/spec-kit.git specify --help >/dev/null 2>&1; then
        echo -e "${GREEN}✅ spec-kit available via uvx${NC}"

        # Create wrapper script since uvx runs commands differently
        cat > "$TOOLS_DIR/specify" << 'EOF'
#!/bin/bash
# spec-kit wrapper for uvx installation
exec uvx --from git+https://github.com/github/spec-kit.git specify "$@"
EOF
        chmod +x "$TOOLS_DIR/specify"

        # Test the wrapper
        if "$TOOLS_DIR/specify" --help >/dev/null 2>&1; then
            echo -e "${GREEN}✅ spec-kit wrapper created successfully${NC}"
            echo -e "${BLUE}spec-kit CLI ready (GitHub Spec Kit)${NC}"
            SPECKIT_INSTALLED=true
        else
            echo -e "${RED}❌ Failed to create spec-kit wrapper${NC}"
            rm -f "$TOOLS_DIR/specify"
        fi
    else
        echo -e "${YELLOW}⚠️  uvx installation failed, trying alternative methods...${NC}"
    fi
fi

# Method 3: Try bun installation (if available)
if [ "$SPECKIT_INSTALLED" != true ] && command -v bun &> /dev/null; then
    echo -e "${BLUE}Installing spec-kit via bun...${NC}"
    if bun install -g @spec-kit/cli 2>/dev/null; then
        echo -e "${GREEN}✅ spec-kit installed successfully via bun${NC}"

        # Verify installation (use --help since --version isn't supported)
        if command -v specify &> /dev/null; then
            if specify --help >/dev/null 2>&1; then
                echo -e "${BLUE}spec-kit CLI ready${NC}"

                # Create symlink
                SPECIFY_PATH=$(which specify)
                if [ -n "$SPECIFY_PATH" ] && [ "$SPECIFY_PATH" != "$TOOLS_DIR/specify" ]; then
                    ln -sf "$SPECIFY_PATH" "$TOOLS_DIR/specify" 2>/dev/null || true
                fi
                SPECKIT_INSTALLED=true
            fi
        fi
    else
        echo -e "${YELLOW}⚠️  bun installation failed${NC}"
    fi
fi

# Check final installation status
if [ "$SPECKIT_INSTALLED" != true ]; then
    echo -e "${RED}❌ Failed to install spec-kit CLI${NC}"
    echo -e "${YELLOW}Please install manually using one of these methods:${NC}"
    echo -e "${BLUE}  - npm: npm install -g @spec-kit/cli${NC}"
    echo -e "${BLUE}  - uvx: uvx --from git+https://github.com/github/spec-kit.git specify init <project>${NC}"
    echo -e "${BLUE}  - bun: bun install -g @spec-kit/cli${NC}"
fi

# Create wrapper scripts for easy access
echo -e "${BLUE}Creating wrapper scripts...${NC}"

# Create a script to add tools to PATH
cat > "$PROJECT_ROOT/.agent/configs/agent-tools-env.sh" << EOF
#!/bin/bash

# Aperim Template - Agent Tools Environment
# Source this file to add agent tools to PATH

export APERIM_TOOLS_DIR="$TOOLS_DIR"
export PATH="\$APERIM_TOOLS_DIR:\$PATH"

# Tool aliases
alias claude='$TOOLS_DIR/claude'
alias codex='$TOOLS_DIR/codex'
alias opencode='$TOOLS_DIR/opencode'
alias specify='$TOOLS_DIR/specify'

echo "🤖 Aperim agent tools loaded"
echo "Available tools: claude, codex, opencode, specify"
echo "Tools directory: \$APERIM_TOOLS_DIR"
EOF

chmod +x "$PROJECT_ROOT/.agent/configs/agent-tools-env.sh"

# Create individual tool configuration scripts
mkdir -p "$PROJECT_ROOT/.agent/configs/tools"

# Claude configuration template
cat > "$PROJECT_ROOT/.agent/configs/tools/claude-config.sh" << 'EOF'
#!/bin/bash

# Claude-Code Configuration for Aperim Template

if [ -z "$CLAUDE_CODE_OAUTH_TOKEN" ]; then
    echo "❌ CLAUDE_CODE_OAUTH_TOKEN environment variable not set"
    echo "Please set your Claude OAuth token in .env file"
    exit 1
fi

echo "🤖 Configuring Claude-Code..."

# Configure Claude authentication
export CLAUDE_API_KEY="$CLAUDE_CODE_OAUTH_TOKEN"

# Test authentication
if claude --version >/dev/null 2>&1; then
    echo "✅ Claude-Code is working"
    claude --version
else
    echo "❌ Claude-Code configuration failed"
    exit 1
fi
EOF

chmod +x "$PROJECT_ROOT/.agent/configs/tools/claude-config.sh"

# Summary
echo -e "${BLUE}=== Installation Summary ===${NC}"

TOOLS_INSTALLED=0
TOOLS_TOTAL=0

for tool in "claude" "codex" "opencode" "specify"; do
    TOOLS_TOTAL=$((TOOLS_TOTAL + 1))
    if [ -f "$TOOLS_DIR/$tool" ]; then
        echo -e "${GREEN}✅ $tool${NC}"
        TOOLS_INSTALLED=$((TOOLS_INSTALLED + 1))
    else
        echo -e "${RED}❌ $tool${NC}"
    fi
done

echo ""
echo -e "${BLUE}Tools installed: $TOOLS_INSTALLED/$TOOLS_TOTAL${NC}"
echo -e "${BLUE}Tools directory: $TOOLS_DIR${NC}"
echo -e "${BLUE}Environment script: $PROJECT_ROOT/.agent/configs/agent-tools-env.sh${NC}"
echo ""

if [ $TOOLS_INSTALLED -gt 0 ]; then
    echo -e "${GREEN}🚀 Agent tools installation completed${NC}"
    echo ""
    echo -e "${YELLOW}To use the tools:${NC}"
    echo -e "${BLUE}  1. Source environment: source .agent/configs/agent-tools-env.sh${NC}"
    echo -e "${BLUE}  2. Configure Claude: .agent/configs/tools/claude-config.sh${NC}"
    echo -e "${BLUE}  3. Set up authentication tokens in .env file${NC}"
else
    echo -e "${YELLOW}⚠️  No tools were successfully installed${NC}"
    echo -e "${BLUE}You may need to install tools manually or check network connectivity${NC}"
fi