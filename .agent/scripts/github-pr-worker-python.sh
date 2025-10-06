#!/bin/bash

# Aperim Template - GitHub PR Worker (Python Implementation)
# Secure wrapper script that calls the Python implementation

set -euo pipefail

# Colors for output (Australian spelling)
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m' # No Colour

# Function to safely print colored output
safe_echo() {
    local color="$1"
    local message="$2"
    # Sanitize message to prevent injection
    local clean_message="${message//[^a-zA-Z0-9 ._-]/}"
    printf "%b%s%b\n" "$color" "$clean_message" "$NC"
}

# Function to validate directory path
validate_directory() {
    local dir_path="$1"
    local dir_name="$2"
    
    # Check if path exists and is a directory
    if [[ ! -d "$dir_path" ]]; then
        safe_echo "$RED" "❌ $dir_name not found at $dir_path"
        return 1
    fi
    
    # Check if path is within expected bounds (basic security check)
    local resolved_path
    resolved_path="$(realpath "$dir_path" 2>/dev/null)" || {
        safe_echo "$RED" "❌ Cannot resolve $dir_name path: $dir_path"
        return 1
    }
    
    # Ensure path doesn't contain suspicious patterns
    if [[ "$resolved_path" =~ \.\./|\.\.\\ ]]; then
        safe_echo "$RED" "❌ Invalid path detected: $dir_path"
        return 1
    fi
    
    echo "$resolved_path"
}

# Function to validate Python executable
validate_python() {
    local python_cmd="$1"
    
    # Check if Python executable exists and is executable
    if ! command -v "$python_cmd" &> /dev/null; then
        safe_echo "$RED" "❌ Python executable not found: $python_cmd"
        return 1
    fi
    
    # Verify it's actually Python
    if ! "$python_cmd" -c "import sys; print(sys.version_info)" &> /dev/null; then
        safe_echo "$RED" "❌ Invalid Python executable: $python_cmd"
        return 1
    fi
    
    return 0
}

# Get and validate script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)" || {
    safe_echo "$RED" "❌ Cannot determine script directory"
    exit 1
}

# Validate and set Python directory
PYTHON_DIR=$(validate_directory "$SCRIPT_DIR/python" "Python implementation directory") || {
    safe_echo "$YELLOW" "💡 Make sure you're in a devcontainer with Python dependencies installed"
    exit 1
}

# Display header
safe_echo "$BLUE" "🤖 Aperim Template: GitHub PR Worker (Python)"

# Validate Python directory structure
AUTOMATION_DIR="$PYTHON_DIR/github_automation"
if ! validate_directory "$AUTOMATION_DIR" "GitHub automation package" &> /dev/null; then
    safe_echo "$RED" "❌ Python implementation not found at $PYTHON_DIR"
    safe_echo "$YELLOW" "💡 Make sure you're in a devcontainer with Python dependencies installed"
    exit 1
fi

# Validate Python executable
if ! validate_python "python3"; then
    safe_echo "$RED" "❌ Python 3 not available"
    exit 1
fi

# Securely change to Python directory
cd "$PYTHON_DIR" || {
    safe_echo "$RED" "❌ Cannot change to Python directory: $PYTHON_DIR"
    exit 1
}

# Function to safely install package
install_package() {
    local package_manager="$1"
    
    case "$package_manager" in
        "uv")
            if command -v uv &> /dev/null; then
                safe_echo "$YELLOW" "⚠️  Installing with uv..."
                uv pip install -e . --quiet --system || {
                    safe_echo "$RED" "❌ Failed to install with uv"
                    return 1
                }
            else
                return 1
            fi
            ;;
        "pip")
            if command -v pip &> /dev/null; then
                safe_echo "$YELLOW" "⚠️  Installing with pip..."
                pip install -e . --quiet || {
                    safe_echo "$RED" "❌ Failed to install with pip"
                    return 1
                }
            else
                return 1
            fi
            ;;
        *)
            return 1
            ;;
    esac
}

# Check if we can import the module safely
if ! python3 -c "import sys; sys.path.insert(0, '.'); import github_automation" 2>/dev/null; then
    safe_echo "$YELLOW" "⚠️  Installing Python package in development mode..."
    
    # Try installation methods in order of preference
    if ! install_package "uv" && ! install_package "pip"; then
        safe_echo "$RED" "❌ No Python package manager found (pip or uv)"
        exit 1
    fi
    
    # Verify installation worked
    if ! python3 -c "import github_automation" 2>/dev/null; then
        safe_echo "$RED" "❌ Package installation failed"
        exit 1
    fi
fi

# Function to validate and sanitize arguments
validate_args() {
    local args=("$@")
    local clean_args=()
    
    for arg in "${args[@]}"; do
        # Basic sanitization - remove potentially dangerous characters
        if [[ "$arg" =~ [;&|`$] ]]; then
            safe_echo "$RED" "❌ Invalid argument detected: $arg"
            exit 1
        fi
        clean_args+=("$arg")
    done
    
    printf '%s\n' "${clean_args[@]}"
}

# Validate command line arguments
mapfile -t CLEAN_ARGS < <(validate_args "$@")

# Call the Python implementation with validated arguments
safe_echo "$BLUE" "🚀 Starting Python GitHub PR Worker..."
exec python3 -m github_automation.cli.pr_worker_cli "${CLEAN_ARGS[@]}"