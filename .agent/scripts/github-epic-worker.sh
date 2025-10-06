#!/bin/bash

# Aperim Template - GitHub Epic Worker Script (Python wrapper)
# Intelligently works through epics and issues with Claude-powered prioritization

set -euo pipefail

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_DIR="$SCRIPT_DIR/python"

# Save current directory to detect repo
ORIGINAL_DIR="$(pwd)"

# Check if Python package exists
if [ ! -d "$PYTHON_DIR/github_automation" ]; then
    echo "Error: Python github_automation package not found at $PYTHON_DIR/github_automation"
    exit 1
fi

# Check Python availability
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required but not installed"
    exit 1
fi

# Auto-detect repository if --repo not provided
# Check for --repo or -r as a standalone argument (not part of another word)
has_repo=false
for arg in "$@"; do
    if [[ "$arg" == "--repo" ]] || [[ "$arg" == "-r" ]]; then
        has_repo=true
        break
    fi
done

# Function to run the epic worker with restart logic
run_epic_worker() {
    local max_restarts=10
    local restart_count=0
    local exit_code=0
    
    while [ $restart_count -lt $max_restarts ]; do
        if [ $restart_count -gt 0 ]; then
            echo "🔄 Restarting epic worker (attempt $((restart_count + 1))/$max_restarts)..."
            sleep 10  # Brief pause before restart
        fi
        
        # Run the epic worker
        if [ "$has_repo" = false ]; then
            python3 -m github_automation.cli.epic_worker_cli --repo "$REPO" "$@"
            exit_code=$?
        else
            python3 -m github_automation.cli.epic_worker_cli "$@"
            exit_code=$?
        fi
        
        # Check exit code
        if [ $exit_code -eq 0 ]; then
            echo "✅ Epic worker completed successfully"
            break
        elif [ $exit_code -eq 130 ] || [ $exit_code -eq 143 ]; then
            echo "⚠️ Epic worker interrupted by user"
            break
        else
            echo "❌ Epic worker crashed with exit code $exit_code"
            restart_count=$((restart_count + 1))
            
            # Kill any orphaned claude-flow processes
            pkill -f "claude-flow" 2>/dev/null || true
            pkill -f "claude --" 2>/dev/null || true
            
            # Clean up any temporary files
            rm -f /tmp/claude-flow-*.log 2>/dev/null || true
        fi
    done
    
    if [ $restart_count -eq $max_restarts ]; then
        echo "❌ Epic worker failed after $max_restarts restart attempts"
        exit 1
    fi
    
    exit $exit_code
}

if [ "$has_repo" = false ]; then
    # Get the GitHub repository from git remote in the original directory
    REPO=$(git -C "$ORIGINAL_DIR" remote get-url origin 2>/dev/null | sed -E 's#.*/([^/]+/[^/]+)\.git#\1#' | sed 's#github.com:##' | sed 's#.*github.com/##')
    
    if [ -z "$REPO" ]; then
        echo "Error: Could not auto-detect repository. Please provide --repo OWNER/REPO"
        exit 1
    fi
    
    echo "Auto-detected repository: $REPO"
fi

# Change to Python directory so imports work
cd "$PYTHON_DIR"

# Run with restart logic
run_epic_worker