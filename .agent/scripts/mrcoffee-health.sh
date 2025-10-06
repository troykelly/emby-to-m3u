#!/bin/bash

# MrCoffee Service Health Check for Agents
# Provides service status information for AI agents

set -euo pipefail

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🏥 MrCoffee Service Health for Agents${NC}"
echo "========================================"

# Check if docker-compose is available
if ! command -v docker-compose >/dev/null 2>&1; then
    echo -e "${RED}❌ Docker Compose not available${NC}"
    exit 1
fi

# Check core services
services=("postgres:PostgreSQL" "redis:Redis" "kafka:Kafka")

for service_info in "${services[@]}"; do
    service=$(echo "$service_info" | cut -d':' -f1)
    name=$(echo "$service_info" | cut -d':' -f2)

    if docker-compose ps "$service" 2>/dev/null | grep -q "Up"; then
        echo -e "${GREEN}✅ $name ($service) - Running${NC}"
    else
        echo -e "${RED}❌ $name ($service) - Not running${NC}"
    fi
done

# Quick connectivity tests
echo ""
echo -e "${BLUE}🔗 Connectivity Tests${NC}"

# PostgreSQL
if PGPASSWORD=postgres psql -h localhost -U postgres -d mrcoffee_dev -c "SELECT 1;" >/dev/null 2>&1; then
    echo -e "${GREEN}✅ PostgreSQL - Connected${NC}"
else
    echo -e "${RED}❌ PostgreSQL - Connection failed${NC}"
fi

# Redis
if redis-cli -h localhost ping >/dev/null 2>&1; then
    echo -e "${GREEN}✅ Redis - Connected${NC}"
else
    echo -e "${RED}❌ Redis - Connection failed${NC}"
fi

# Quick start command
echo ""
echo -e "${YELLOW}💡 To start services: make dev-core${NC}"
