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
