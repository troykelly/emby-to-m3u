#!/bin/bash

# Aperim Template - GitHub Issue Selector Script
# Orchestrates autonomous GitHub workflow: selects issues, runs issue worker, then PR worker

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

echo -e "${BLUE}🤖 Aperim Template: Autonomous GitHub Workflow Orchestrator${NC}"

# Default values
DRY_RUN=false
CONTINUOUS=false
CYCLE_DELAY=300  # 5 minutes between cycles
MAX_CYCLES=0     # 0 = infinite
WORK_ISSUES=true
WORK_PRS=true

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Orchestrates autonomous GitHub workflow for the current repository:"
    echo "1. Works on highest priority issues → creates PRs"
    echo "2. Works on open PRs → gets them mergeable"
    echo "3. Repeats until no work remains"
    echo ""
    echo "Options:"
    echo "  --dry-run              Show what would be done without making changes"
    echo "  --continuous, -c       Run continuously until stopped"
    echo "  --cycles, -n NUMBER    Maximum cycles to run (default: 1, 0=infinite)"
    echo "  --delay, -d SECONDS    Delay between cycles in continuous mode (default: 300)"
    echo "  --issues-only         Only work on issues, skip PR processing"
    echo "  --prs-only            Only work on PRs, skip issue processing"
    echo "  --help, -h             Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                     # Run one complete cycle"
    echo "  $0 --continuous       # Run until manually stopped"
    echo "  $0 --cycles 5         # Run exactly 5 cycles"
    echo "  $0 --issues-only      # Only process issues"
    echo "  $0 --dry-run          # Preview what would be done"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --continuous|-c)
            CONTINUOUS=true
            MAX_CYCLES=0
            shift
            ;;
        --cycles|-n)
            MAX_CYCLES="$2"
            shift 2
            ;;
        --delay|-d)
            CYCLE_DELAY="$2"
            shift 2
            ;;
        --issues-only)
            WORK_ISSUES=true
            WORK_PRS=false
            shift
            ;;
        --prs-only)
            WORK_ISSUES=false
            WORK_PRS=true
            shift
            ;;
        --help|-h)
            show_usage
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            show_usage
            exit 1
            ;;
    esac
done

# Auto-detect repository from git remote
detect_repository() {
    if [ ! -d "$PROJECT_ROOT/.git" ]; then
        echo -e "${RED}❌ Not in a git repository${NC}"
        exit 1
    fi
    
    cd "$PROJECT_ROOT"
    
    # Get the remote URL and extract owner/repo
    REMOTE_URL=$(git remote get-url origin 2>/dev/null || echo "")
    
    if [ -z "$REMOTE_URL" ]; then
        echo -e "${RED}❌ No git remote 'origin' found${NC}"
        exit 1
    fi
    
    # Extract owner/repo from various URL formats
    if [[ $REMOTE_URL =~ github\.com[:/]([^/]+)/([^/]+)(\.git)?$ ]]; then
        REPO_OWNER="${BASH_REMATCH[1]}"
        REPO_NAME="${BASH_REMATCH[2]}"
        REPO_NAME="${REPO_NAME%.git}"  # Remove .git suffix if present
        REPOSITORY="$REPO_OWNER/$REPO_NAME"
    else
        echo -e "${RED}❌ Could not parse GitHub repository from remote URL: $REMOTE_URL${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✅ Detected repository: $REPOSITORY${NC}"
}

# Check if there's work to do
check_work_available() {
    local has_issues=false
    local has_prs=false
    
    if [ "$WORK_ISSUES" = true ]; then
        local issue_count
        issue_count=$(gh issue list --repo "$REPOSITORY" --state open --json number --jq 'length' 2>/dev/null || echo "0")
        if [ "$issue_count" -gt 0 ]; then
            echo -e "${BLUE}📋 Found $issue_count open issues${NC}"
            has_issues=true
        fi
    fi
    
    if [ "$WORK_PRS" = true ]; then
        local pr_count
        pr_count=$(gh pr list --repo "$REPOSITORY" --state open --json number --jq 'length' 2>/dev/null || echo "0")
        if [ "$pr_count" -gt 0 ]; then
            echo -e "${BLUE}🔀 Found $pr_count open PRs${NC}"
            has_prs=true
        fi
    fi
    
    if [ "$has_issues" = true ] || [ "$has_prs" = true ]; then
        return 0  # Work available
    else
        return 1  # No work
    fi
}

# Run issue worker
run_issue_worker() {
    echo -e "${BLUE}🔧 Running issue worker...${NC}"
    
    local issue_worker="$SCRIPT_DIR/github-issue-worker.sh"
    if [ ! -x "$issue_worker" ]; then
        echo -e "${RED}❌ Issue worker script not found or not executable: $issue_worker${NC}"
        return 1
    fi
    
    local args=()
    if [ "$DRY_RUN" = true ]; then
        args+=(--dry-run)
    fi
    
    # Run the issue worker
    if "$issue_worker" "${args[@]}"; then
        echo -e "${GREEN}✅ Issue worker completed successfully${NC}"
        return 0
    else
        local exit_code=$?
        if [ $exit_code -eq 0 ]; then
            echo -e "${BLUE}ℹ️  Issue worker completed (no issues to process)${NC}"
            return 0
        else
            echo -e "${YELLOW}⚠️  Issue worker completed with status $exit_code${NC}"
            return 1
        fi
    fi
}

# Run PR worker
run_pr_worker() {
    echo -e "${BLUE}🔀 Running PR worker...${NC}"
    
    local pr_worker="$SCRIPT_DIR/github-pr-worker.sh"
    if [ ! -x "$pr_worker" ]; then
        echo -e "${RED}❌ PR worker script not found or not executable: $pr_worker${NC}"
        return 1
    fi
    
    local args=()
    if [ "$DRY_RUN" = true ]; then
        args+=(--dry-run)
    fi
    
    # Run the PR worker
    if "$pr_worker" "${args[@]}"; then
        echo -e "${GREEN}✅ PR worker completed successfully${NC}"
        return 0
    else
        local exit_code=$?
        if [ $exit_code -eq 0 ]; then
            echo -e "${BLUE}ℹ️  PR worker completed (no PRs to process)${NC}"
            return 0
        else
            echo -e "${YELLOW}⚠️  PR worker completed with status $exit_code${NC}"
            return 1
        fi
    fi
}

# Run one complete cycle
run_cycle() {
    local cycle_num="$1"
    
    echo -e "${BLUE}🔄 Starting cycle #$cycle_num${NC}"
    
    # Check if there's any work to do
    if ! check_work_available; then
        echo -e "${GREEN}🎉 No work available - repository is clean!${NC}"
        return 2  # Special return code for "no work"
    fi
    
    local work_done=false
    
    # Step 1: Work on issues (creates PRs)
    if [ "$WORK_ISSUES" = true ]; then
        echo -e "${BLUE}📋 Phase 1: Processing issues...${NC}"
        if run_issue_worker; then
            work_done=true
        fi
    fi
    
    # Step 2: Work on PRs (gets them mergeable)
    if [ "$WORK_PRS" = true ]; then
        echo -e "${BLUE}🔀 Phase 2: Processing PRs...${NC}"
        if run_pr_worker; then
            work_done=true
        fi
    fi
    
    if [ "$work_done" = true ]; then
        echo -e "${GREEN}✅ Cycle #$cycle_num completed with work done${NC}"
        return 0
    else
        echo -e "${YELLOW}⚠️  Cycle #$cycle_num completed but no work was done${NC}"
        return 1
    fi
}

# Main execution
main() {
    echo -e "${BLUE}🚀 Starting autonomous GitHub workflow orchestrator...${NC}"
    
    # Detect repository
    detect_repository
    
    # Check for GitHub CLI
    if ! command -v gh &> /dev/null; then
        echo -e "${RED}❌ GitHub CLI (gh) is required but not installed${NC}"
        exit 1
    fi
    
    # Check GitHub CLI authentication
    if ! gh auth status >/dev/null 2>&1; then
        echo -e "${RED}❌ GitHub CLI not authenticated. Run 'gh auth login'${NC}"
        exit 1
    fi
    
    # Check worker scripts exist
    local issue_worker="$SCRIPT_DIR/github-issue-worker.sh"
    local pr_worker="$SCRIPT_DIR/github-pr-worker.sh"
    
    if [ "$WORK_ISSUES" = true ] && [ ! -x "$issue_worker" ]; then
        echo -e "${RED}❌ Issue worker script not found: $issue_worker${NC}"
        exit 1
    fi
    
    if [ "$WORK_PRS" = true ] && [ ! -x "$pr_worker" ]; then
        echo -e "${RED}❌ PR worker script not found: $pr_worker${NC}"
        exit 1
    fi
    
    echo -e "${BLUE}⚙️  Configuration:${NC}"
    echo -e "${BLUE}  Work on issues: $WORK_ISSUES${NC}"
    echo -e "${BLUE}  Work on PRs: $WORK_PRS${NC}"
    echo -e "${BLUE}  Continuous mode: $CONTINUOUS${NC}"
    echo -e "${BLUE}  Max cycles: $([ $MAX_CYCLES -eq 0 ] && echo "infinite" || echo $MAX_CYCLES)${NC}"
    echo -e "${BLUE}  Cycle delay: $CYCLE_DELAY seconds${NC}"
    echo -e "${BLUE}  Dry run: $DRY_RUN${NC}"
    echo ""
    
    # Run cycles
    local cycle_count=0
    local total_work_done=false
    
    while true; do
        cycle_count=$((cycle_count + 1))
        
        # Check if we've reached max cycles
        if [ $MAX_CYCLES -gt 0 ] && [ $cycle_count -gt $MAX_CYCLES ]; then
            echo -e "${BLUE}🛑 Reached maximum cycles ($MAX_CYCLES)${NC}"
            break
        fi
        
        # Run the cycle
        run_cycle $cycle_count
        local cycle_result=$?
        
        case $cycle_result in
            0)
                # Work was done
                total_work_done=true
                ;;
            1)
                # Cycle completed but no work done
                echo -e "${YELLOW}⚠️  No work completed in this cycle${NC}"
                ;;
            2)
                # No work available
                echo -e "${GREEN}🎉 Repository is clean - no more work to do!${NC}"
                break
                ;;
        esac
        
        # If not in continuous mode and we're not at max cycles, exit after one cycle
        if [ "$CONTINUOUS" = false ] && [ $MAX_CYCLES -eq 0 ]; then
            break
        fi
        
        # If in continuous mode, wait before next cycle
        if [ "$CONTINUOUS" = true ] || ([ $MAX_CYCLES -gt 0 ] && [ $cycle_count -lt $MAX_CYCLES ]); then
            echo -e "${BLUE}⏳ Waiting $CYCLE_DELAY seconds before next cycle...${NC}"
            sleep $CYCLE_DELAY
        fi
    done
    
    echo -e "${BLUE}📊 Summary:${NC}"
    echo -e "${BLUE}  Total cycles: $cycle_count${NC}"
    echo -e "${BLUE}  Work completed: $total_work_done${NC}"
    
    if [ "$total_work_done" = true ]; then
        echo -e "${GREEN}🎉 Orchestrator completed successfully with work done!${NC}"
        exit 0
    else
        echo -e "${BLUE}ℹ️  Orchestrator completed - no work was needed${NC}"
        exit 0
    fi
}

# Handle interruption gracefully
trap 'echo -e "\n${YELLOW}🛑 Orchestrator interrupted by user${NC}"; exit 130' INT TERM

# Change to project root
cd "$PROJECT_ROOT"

# Run main function
main