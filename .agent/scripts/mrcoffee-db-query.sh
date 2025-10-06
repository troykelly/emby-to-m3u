#!/bin/bash

# MrCoffee Database Query Helper for Agents
# Provides easy database access for AI agents

set -euo pipefail

# Usage function
usage() {
    echo "Usage: $0 [query]"
    echo ""
    echo "Examples:"
    echo "  $0 'SELECT current_database();'"
    echo "  $0 'SHOW TABLES;'"
    echo "  $0 '\\dt'"  # Show tables
    echo "  $0 '\\dn'"  # Show schemas
}

# Check if query provided
if [ $# -eq 0 ]; then
    usage
    exit 1
fi

query="$1"

# Execute query
PGPASSWORD=postgres psql -h localhost -U postgres -d mrcoffee_dev -c "$query"
