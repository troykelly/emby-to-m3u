#!/bin/bash

# Aperim Template - Create Repository from Template Script
# Creates a new repository in the aperim organization from this template

set -euo pipefail

# Colours for output (Australian spelling)
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Colour

# Function to show usage
show_usage() {
    echo "Usage: $0 <repository-name> [description]"
    echo ""
    echo "Create a new repository in the aperim organization from claude-flow-template"
    echo ""
    echo "Arguments:"
    echo "  repository-name    Name for the new repository (required)"
    echo "  description        Description for the repository (optional)"
    echo ""
    echo "Environment:"
    echo "  GITHUB_TOKEN       GitHub token with repo and org permissions (required)"
    echo ""
    echo "Examples:"
    echo "  $0 my-new-project"
    echo "  $0 game-project 'A fun browser-based game'"
    echo "  GITHUB_TOKEN=ghp_xxx $0 api-service 'REST API service'"
}

# Check arguments
if [ $# -eq 0 ]; then
    echo -e "${RED}❌ Repository name is required${NC}"
    echo ""
    show_usage
    exit 1
fi

if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    show_usage
    exit 0
fi

REPO_NAME="$1"
DESCRIPTION="${2:-Repository created from aperim claude-flow-template}"

echo -e "${BLUE}🚀 Creating repository in aperim organization...${NC}"
echo -e "${BLUE}Repository: aperim/$REPO_NAME${NC}"
echo -e "${BLUE}Description: $DESCRIPTION${NC}"
echo ""

# Check if GitHub CLI is available
if ! command -v gh &> /dev/null; then
    echo -e "${RED}❌ GitHub CLI (gh) is not installed${NC}"
    echo -e "${BLUE}Install with: brew install gh${NC}"
    exit 1
fi

# Check for GitHub token
if [ -z "${GITHUB_TOKEN:-}" ]; then
    echo -e "${RED}❌ GITHUB_TOKEN environment variable is required${NC}"
    echo -e "${BLUE}Set your token: export GITHUB_TOKEN=ghp_...${NC}"
    exit 1
fi

# Validate repository name
if [[ ! "$REPO_NAME" =~ ^[a-zA-Z0-9._-]+$ ]]; then
    echo -e "${RED}❌ Invalid repository name: $REPO_NAME${NC}"
    echo -e "${BLUE}Repository names can only contain letters, numbers, dots, hyphens, and underscores${NC}"
    exit 1
fi

# Check if repository already exists
echo -e "${BLUE}Checking if repository already exists...${NC}"
if gh api repos/aperim/"$REPO_NAME" >/dev/null 2>&1; then
    echo -e "${RED}❌ Repository aperim/$REPO_NAME already exists${NC}"
    exit 1
fi

# Create repository from template
echo -e "${BLUE}Creating repository from template...${NC}"
RESPONSE=$(gh api repos/aperim/claude-flow-template/generate --method POST \
    --field name="$REPO_NAME" \
    --field owner="aperim" \
    --field description="$DESCRIPTION" \
    --field private=true \
    --field include_all_branches=false 2>&1)

if [ $? -eq 0 ]; then
    REPO_URL=$(echo "$RESPONSE" | jq -r '.html_url' 2>/dev/null || echo "https://github.com/aperim/$REPO_NAME")
    
    echo -e "${GREEN}✅ Repository created successfully!${NC}"
    echo ""
    echo -e "${BLUE}Repository URL: $REPO_URL${NC}"
    echo -e "${BLUE}Clone command: git clone https://github.com/aperim/$REPO_NAME.git${NC}"
    echo ""
    echo -e "${YELLOW}Next steps:${NC}"
    echo -e "${BLUE}1. Clone the repository: git clone https://github.com/aperim/$REPO_NAME.git${NC}"
    echo -e "${BLUE}2. Navigate to directory: cd $REPO_NAME${NC}"
    echo -e "${BLUE}3. Copy environment: cp .env.example .env${NC}"
    echo -e "${BLUE}4. Initialize setup: ./.agent/scripts/init-repository.sh${NC}"
    
else
    echo -e "${RED}❌ Failed to create repository${NC}"
    echo -e "${YELLOW}Error response:${NC}"
    echo "$RESPONSE"
    exit 1
fi