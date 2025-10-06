#!/bin/bash

# Aperim Template - Agent Tools Environment
# Source this file to add agent tools to PATH

export APERIM_TOOLS_DIR="/home/vscode/.local/bin"
export PATH="$APERIM_TOOLS_DIR:$PATH"

# Tool aliases
alias claude='/home/vscode/.local/bin/claude'
alias codex='/home/vscode/.local/bin/codex'
alias opencode='/home/vscode/.local/bin/opencode'

echo "🤖 Aperim agent tools loaded"
echo "Available tools: claude, codex, opencode"
echo "Tools directory: $APERIM_TOOLS_DIR"
