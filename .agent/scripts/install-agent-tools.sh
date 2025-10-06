#!/bin/bash

# Aperim Template - Install Agent Tools Script
# Installs claude-code, codex, and opencode CLI binaries

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
    
    # Construct download URL based on platform (using actual asset naming from GitHub)
    if [ "$OS_NAME" = "linux" ]; then
        # Detect libc type - Alpine and similar use musl, most others use glibc
        if [ -f /etc/alpine-release ] || ldd --version 2>&1 | grep -q musl; then
            # Alpine Linux or musl-based system
            if [ "$ARCH_NAME" = "arm64" ]; then
                CODEX_BINARY_NAME="codex-aarch64-unknown-linux-musl"
            else
                CODEX_BINARY_NAME="codex-x86_64-unknown-linux-musl"
            fi
        else
            # Standard glibc-based system (Debian, Ubuntu, RHEL, etc.)
            if [ "$ARCH_NAME" = "arm64" ]; then
                CODEX_BINARY_NAME="codex-aarch64-unknown-linux-gnu"
            else
                CODEX_BINARY_NAME="codex-x86_64-unknown-linux-gnu"
            fi
        fi
    elif [ "$OS_NAME" = "macos" ]; then
        if [ "$ARCH_NAME" = "arm64" ]; then
            CODEX_BINARY_NAME="codex-aarch64-apple-darwin"
        else
            CODEX_BINARY_NAME="codex-x86_64-apple-darwin"
        fi
    else
        echo -e "${RED}❌ Unsupported platform for Codex: $OS_NAME-$ARCH_NAME${NC}"
        continue
    fi
    
    CODEX_URL="https://github.com/openai/codex/releases/download/$CODEX_TAG/$CODEX_BINARY_NAME.tar.gz"
    
    echo -e "${BLUE}Downloading: $CODEX_URL${NC}"
    
    # Download and install
    TEMP_DIR="/tmp/codex-install"
    mkdir -p "$TEMP_DIR"
    
    if curl -fsSL -o "$TEMP_DIR/codex.tar.gz" "$CODEX_URL"; then
        # Check if we actually downloaded a valid file using portable wc command
        if [ -f "$TEMP_DIR/codex.tar.gz" ]; then
            FILE_SIZE=$(wc -c < "$TEMP_DIR/codex.tar.gz" | tr -d ' ')
            if [ "$FILE_SIZE" -lt 1000 ]; then
                echo -e "${RED}❌ Downloaded file too small ($FILE_SIZE bytes), likely a redirect error${NC}"
                rm -rf "$TEMP_DIR"
            else
                cd "$TEMP_DIR"
                # Extract and show any errors for debugging
                echo -e "${BLUE}Extracting Codex archive...${NC}"
                if tar -xzf codex.tar.gz; then
                    # List extracted files for debugging
                    echo -e "${BLUE}Extracted files:${NC}"
                    ls -la
                    
                    # Find the extracted binary - exclude tar/zip files and look for executable
                    EXTRACTED_BINARY=$(find . -name "codex*" -type f ! -name "*.tar.gz" ! -name "*.zip" 2>/dev/null | head -1)
                    
                    if [ -n "$EXTRACTED_BINARY" ]; then
                        echo -e "${BLUE}Found binary: $EXTRACTED_BINARY${NC}"
                        # Move to tools directory and rename to codex
                        mv "$EXTRACTED_BINARY" "$TOOLS_DIR/codex"
                        chmod +x "$TOOLS_DIR/codex"
                        echo -e "${GREEN}✅ Codex CLI installed successfully${NC}"
                        
                        # Verify installation
                        if "$TOOLS_DIR/codex" --version >/dev/null 2>&1; then
                            VERSION=$("$TOOLS_DIR/codex" --version 2>/dev/null || echo "unknown")
                            echo -e "${BLUE}Codex version: $VERSION${NC}"
                        fi
                    else
                        echo -e "${RED}❌ Could not find Codex binary in archive${NC}"
                    fi
                else
                    echo -e "${RED}❌ Failed to extract Codex archive${NC}"
                    echo -e "${YELLOW}Tar error output above may help diagnose the issue${NC}"
                fi
                
                # Cleanup
                rm -rf "$TEMP_DIR"
            fi
        else
            echo -e "${RED}❌ Download failed - file not created${NC}"
            rm -rf "$TEMP_DIR"
        fi
    else
        echo -e "${RED}❌ Failed to download Codex CLI${NC}"
        rm -rf "$TEMP_DIR"
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
if TMPDIR="$OPENCODE_TEMP" curl -fsSL https://opencode.ai/install | bash; then
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

echo "🤖 Aperim agent tools loaded"
echo "Available tools: claude, codex, opencode"
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

for tool in "claude" "codex" "opencode"; do
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