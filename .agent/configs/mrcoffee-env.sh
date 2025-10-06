#!/bin/bash

# MrCoffee Agent Environment Configuration
# Integrates existing agent tools with MrCoffee infrastructure

# MrCoffee Infrastructure Endpoints
export MRCOFFEE_DATABASE_URL="${DATABASE_URL:-postgresql://postgres:postgres@postgres:5432/mrcoffee_dev}"
export MRCOFFEE_REDIS_URL="${REDIS_URL:-redis://redis:6379}"
export MRCOFFEE_KAFKA_BROKERS="${KAFKA_BROKERS:-kafka:9092}"

# Development Services
export MRCOFFEE_API_GATEWAY="http://localhost:8000"
export MRCOFFEE_AUTH_SERVICE="http://localhost:3001"
export MRCOFFEE_EVENT_ROUTER="http://localhost:3002"
export MRCOFFEE_SITE_MANAGEMENT="http://localhost:3003"

# Development Tools
export MRCOFFEE_KAFKA_UI="http://localhost:8080"
export MRCOFFEE_REDIS_INSIGHT="http://localhost:8001"
export MRCOFFEE_STORYBOOK="http://localhost:6006"

# Agent Tool Paths (preserve existing)
export AGENT_TOOLS_DIR="${AGENT_TOOLS_DIR:-$HOME/.local/bin}"
export AGENT_SCRIPTS_DIR="$(dirname "${BASH_SOURCE[0]}")/../scripts"
export AGENT_CONFIGS_DIR="$(dirname "${BASH_SOURCE[0]}")/../configs"

# MrCoffee specific paths
export MRCOFFEE_APPS_DIR="$PWD/apps"
export MRCOFFEE_SERVICES_DIR="$PWD/services"
export MRCOFFEE_PACKAGES_DIR="$PWD/packages"
export MRCOFFEE_INFRASTRUCTURE_DIR="$PWD/infrastructure"

# Load existing agent environment if it exists
if [ -f "$AGENT_CONFIGS_DIR/agent-tools-env.sh" ]; then
    source "$AGENT_CONFIGS_DIR/agent-tools-env.sh"
fi

# Development shortcuts
alias mc-psql='psql $MRCOFFEE_DATABASE_URL'
alias mc-redis='redis-cli -u $MRCOFFEE_REDIS_URL'
alias mc-kafka-topics='docker-compose exec kafka kafka-topics --bootstrap-server localhost:9092 --list'

# Agent shortcuts with MrCoffee context
alias agent-status='echo "Agent Tools Status:"; command -v claude-code && echo "✅ claude-code" || echo "❌ claude-code"; command -v codex && echo "✅ codex" || echo "❌ codex"; command -v opencode && echo "✅ opencode" || echo "❌ opencode"'

echo "🔗 MrCoffee agent environment loaded"
