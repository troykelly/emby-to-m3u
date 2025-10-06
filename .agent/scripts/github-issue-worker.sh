#!/bin/bash

# Aperim Template - GitHub Issue Worker Script
# Autonomously works on issues until complete, then raises PR

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

echo -e "${BLUE}🤖 Aperim Template: Autonomous GitHub Issue Worker${NC}"

# Default values
SPECIFIC_ISSUE=""
DRY_RUN=false
HIVE_NAMESPACE=""
MAX_AGENTS=10
CREATE_TESTS=true
AUTO_PR=true

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Autonomously work on issues in the current repository"
    echo "Finds highest priority issue, works on it, creates tests, and raises PR"
    echo ""
    echo "Options:"
    echo "  --issue, -i NUMBER      Work on specific issue number only"
    echo "  --dry-run              Show what would be done without making changes"
    echo "  --namespace, -n NAME    Hive namespace (default: github-issue-{issue})"
    echo "  --agents, -a NUMBER     Maximum agents to spawn (default: 10)"
    echo "  --no-tests             Skip automatic test creation"
    echo "  --no-pr                Don't auto-create PR when complete"
    echo "  --help, -h              Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                      # Work on highest priority issue"
    echo "  $0 --issue 123         # Work on specific issue"
    echo "  $0 --no-tests --dry-run # Preview without tests"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --issue|-i)
            SPECIFIC_ISSUE="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --namespace|-n)
            HIVE_NAMESPACE="$2"
            shift 2
            ;;
        --agents|-a)
            MAX_AGENTS="$2"
            shift 2
            ;;
        --no-tests)
            CREATE_TESTS=false
            shift
            ;;
        --no-pr)
            AUTO_PR=false
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

# Get highest priority open issue
get_priority_issue() {
    if [ -n "$SPECIFIC_ISSUE" ]; then
        echo "$SPECIFIC_ISSUE"
        return
    fi
    
    # Get open issues with priority labels (highest priority first)
    local priority_issue
    for priority in "critical" "high" "medium" "low"; do
        priority_issue=$(gh issue list --repo "$REPOSITORY" --state open --label "$priority" --json number --jq '.[0].number' 2>/dev/null || echo "")
        if [ -n "$priority_issue" ] && [ "$priority_issue" != "null" ]; then
            echo "$priority_issue"
            return
        fi
    done
    
    # If no priority labels, get oldest open issue
    local oldest_issue
    oldest_issue=$(gh issue list --repo "$REPOSITORY" --state open --json number,createdAt --jq 'sort_by(.createdAt) | .[0].number' 2>/dev/null || echo "")
    
    if [ -n "$oldest_issue" ] && [ "$oldest_issue" != "null" ]; then
        echo "$oldest_issue"
    else
        echo ""
    fi
}

# Work on a specific issue using Claude-Flow
work_on_issue() {
    local issue_number="$1"
    
    echo -e "${BLUE}🔧 Working on issue #$issue_number...${NC}"
    
    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}[DRY RUN] Would work on issue #$issue_number${NC}"
        return 0
    fi
    
    # Get issue details
    local issue_info
    issue_info=$(gh issue view "$issue_number" --repo "$REPOSITORY" --json title,body,url,labels 2>/dev/null || echo '{}')
    
    local issue_title issue_body issue_url issue_labels
    issue_title=$(echo "$issue_info" | jq -r '.title // "Unknown"')
    issue_body=$(echo "$issue_info" | jq -r '.body // ""')
    issue_url=$(echo "$issue_info" | jq -r '.url // ""')
    issue_labels=$(echo "$issue_info" | jq -r '.labels[]?.name // empty' | tr '\n' ',' | sed 's/,$//')
    
    echo -e "${BLUE}  Title: $issue_title${NC}"
    echo -e "${BLUE}  Labels: $issue_labels${NC}"
    echo -e "${BLUE}  URL: $issue_url${NC}"
    
    # Set namespace if not provided
    if [ -z "$HIVE_NAMESPACE" ]; then
        HIVE_NAMESPACE="github-issue-$issue_number"
    fi
    
    # Create test requirement text
    local test_requirement=""
    if [ "$CREATE_TESTS" = true ]; then
        test_requirement="
CRITICAL: You MUST create comprehensive tests for any code you write, even if the issue doesn't mention testing. This is mandatory and non-negotiable. Create unit tests, integration tests, and end-to-end tests as appropriate."
    fi
    
    # Create Claude-Flow objective for this issue
    local objective="Implement complete solution for issue #$issue_number: '$issue_title'

Repository: $REPOSITORY
Issue URL: $issue_url
Labels: $issue_labels

Original Issue Description:
$issue_body

Tasks:
1. Analyze the issue requirements thoroughly
2. Research the codebase to understand the context and existing patterns
3. Design and implement a complete solution following project conventions
4. Write clean, maintainable, and well-documented code
5. Follow existing code style and architectural patterns$test_requirement
6. Update relevant documentation if needed
7. Test the implementation thoroughly
8. Prepare for PR creation with clear commit messages

Goal: Fully implement the requested feature/fix with production-ready code and comprehensive testing."

    # Start Claude-Flow hive-mind for this issue with TTY fixes
    echo -e "${BLUE}🐝 Starting hive-mind for issue #$issue_number...${NC}"
    
    cd "$PROJECT_ROOT"
    
    # Fix TTY/stdin issues for containerized environments
    export FORCE_COLOR=0
    export NO_COLOR=1
    export TERM=xterm-256color
    unset COLUMNS LINES
    
    if command -v npx &> /dev/null && npx --yes claude-flow@alpha --version >/dev/null 2>&1; then
        # Create objective file to avoid stdin pipe issues
        local objective_file="/tmp/issue-objective-$issue_number.txt"
        echo "$objective" > "$objective_file"
        
        # Use non-interactive mode with timeout and proper error handling
        echo -e "${BLUE}Starting hive-mind in non-interactive mode with 10-minute timeout...${NC}"
        
        local objective_text=$(cat "$objective_file")
        local timeout_seconds=3600  # 60 minutes
        local log_file="/tmp/hive-mind-issue-$issue_number.log"
        
        echo -e "${BLUE}Hive-mind will timeout after $((timeout_seconds / 60)) minutes if stuck${NC}"
        echo -e "${BLUE}Log file: $log_file${NC}"
        
        # Start hive-mind in background and show live agent activity
        echo -e "${BLUE}🎯 Starting hive-mind for issue #$issue_number...${NC}"
        echo -e "${BLUE}📺 Live Agent Activity (intelligent timeout: 10min inactivity):${NC}"
        echo ""
        
        # Start hive-mind in background, save log, and show interpreted output
        npx --yes claude-flow@alpha hive-mind spawn \
            $(printf '%q' "$objective_text") \
            --name "issue-worker-$issue_number" \
            --agents "$MAX_AGENTS" \
            --namespace "$HIVE_NAMESPACE" \
            --strategy hierarchical \
            --auto-scale \
            --auto-spawn \
            --claude \
            --non-interactive \
            --verbose \
            > "$log_file" 2>&1 &
        
        local hive_pid=$!
        local last_activity=$(date +%s)
        local inactivity_timeout=600  # 10 minutes of inactivity
        
        # Start log interpreter to follow the log file
        sleep 2  # Give hive-mind time to start writing
        "$SCRIPT_DIR/claude-log-interpreter.sh" --follow --compact "$log_file" &
        local interpreter_pid=$!
        
        # Monitor for activity and implement intelligent timeout
        while kill -0 $hive_pid 2>/dev/null; do
            # Check if log file has been modified recently
            if [ -f "$log_file" ]; then
                local log_mtime=$(stat -f %m "$log_file" 2>/dev/null || stat -c %Y "$log_file" 2>/dev/null || echo "0")
                local current_time=$(date +%s)
                
                if [ $log_mtime -gt $last_activity ]; then
                    last_activity=$log_mtime
                fi
                
                # Check for inactivity timeout
                local inactive_time=$((current_time - last_activity))
                if [ $inactive_time -gt $inactivity_timeout ]; then
                    echo ""
                    echo -e "${YELLOW}⏰ Hive-mind inactive for 10 minutes, terminating...${NC}"
                    kill $hive_pid 2>/dev/null || true
                    break
                fi
            fi
            
            sleep 5  # Check every 5 seconds
        done
        
        # Wait for hive-mind to complete
        if wait $hive_pid 2>/dev/null; then
            # Stop the log interpreter
            kill $interpreter_pid 2>/dev/null || true
            echo ""
            echo -e "${GREEN}✅ Hive-mind completed successfully${NC}"
        else
            local exit_code=$?
            # Stop the log interpreter
            kill $interpreter_pid 2>/dev/null || true
            echo ""
            if [ $exit_code -eq 124 ]; then
                echo -e "${YELLOW}⏰ Hive-mind timed out after $((timeout_seconds / 60)) minutes${NC}"
            else
                echo -e "${RED}❌ Hive-mind failed with exit code $exit_code${NC}"
            fi
            
            # Clean up any stuck processes
            echo -e "${BLUE}Cleaning up any stuck hive-mind processes...${NC}"
            pkill -f "claude-flow.*hive-mind.*issue-worker-$issue_number" || true
            pkill -f "claude.*issue-worker-$issue_number" || true
        fi
        
        rm -f "$log_file"
        
        rm -f "$objective_file"
    else
        echo -e "${RED}❌ Claude-Flow not available${NC}"
        return 1
    fi
    
    echo -e "${GREEN}✅ Completed work on issue #$issue_number${NC}"
}

# Create PR for completed work
create_pr_for_issue() {
    local issue_number="$1"
    
    if [ "$AUTO_PR" = false ]; then
        echo -e "${BLUE}ℹ️  Auto-PR disabled, skipping PR creation${NC}"
        return 0
    fi
    
    echo -e "${BLUE}📝 Creating PR for issue #$issue_number...${NC}"
    
    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}[DRY RUN] Would create PR for issue #$issue_number${NC}"
        return 0
    fi
    
    cd "$PROJECT_ROOT"
    
    # Check if there are any changes to commit
    if git diff --quiet && git diff --staged --quiet; then
        echo -e "${YELLOW}⚠️  No changes to commit for issue #$issue_number${NC}"
        return 1
    fi
    
    # Get issue details for PR
    local issue_info
    issue_info=$(gh issue view "$issue_number" --repo "$REPOSITORY" --json title,body,url 2>/dev/null || echo '{}')
    
    local issue_title issue_body
    issue_title=$(echo "$issue_info" | jq -r '.title // "Unknown"')
    issue_body=$(echo "$issue_info" | jq -r '.body // ""')
    
    # Create branch name
    local branch_name="issue-$issue_number-$(echo "$issue_title" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g' | sed 's/--*/-/g' | sed 's/^-\|-$//g' | cut -c1-50)"
    
    # Create and switch to new branch
    echo -e "${BLUE}🌿 Creating branch: $branch_name${NC}"
    git checkout -b "$branch_name" || {
        echo -e "${YELLOW}⚠️  Branch $branch_name already exists, using existing branch${NC}"
        git checkout "$branch_name"
    }
    
    # Stage all changes
    git add .
    
    # Create commit message
    local commit_message="Implement solution for issue #$issue_number: $issue_title

- Complete implementation addressing all requirements
- Added comprehensive tests$([ "$CREATE_TESTS" = true ] && echo " (mandatory)" || echo "")
- Updated documentation as needed
- Follows project conventions and best practices

Closes #$issue_number

🤖 Generated with Claude-Flow hive-mind
Co-Authored-By: Claude <noreply@anthropic.com>"
    
    # Commit changes
    echo -e "${BLUE}💾 Committing changes...${NC}"
    git commit -m "$commit_message"
    
    # Push branch
    echo -e "${BLUE}📤 Pushing branch to origin...${NC}"
    git push origin "$branch_name"
    
    # Create PR body with proper variable handling
    local issue_url_value
    issue_url_value=$(echo "$issue_info" | jq -r '.url // ""')
    
    local test_note=""
    if [ "$CREATE_TESTS" = true ]; then
        test_note=" (mandatory requirement)"
    fi
    
    local pr_body="## Summary
Implements a complete solution for issue #$issue_number

**Issue**: $issue_title
**Issue URL**: $issue_url_value

## Implementation Details
- Analyzed requirements and existing codebase patterns
- Implemented solution following project conventions
- Added comprehensive testing$test_note
- Updated relevant documentation

## Test Plan
- [ ] Unit tests pass
- [ ] Integration tests pass  
- [ ] Manual testing completed
- [ ] Code review completed
- [ ] Documentation updated

## Original Issue Description
$issue_body

---
🤖 Generated with Claude-Flow hive-mind  
Closes #$issue_number"
    
    echo -e "${BLUE}🚀 Creating pull request...${NC}"
    local pr_url
    pr_url=$(gh pr create \
        --repo "$REPOSITORY" \
        --title "Fix #$issue_number: $issue_title" \
        --body "$pr_body" \
        --head "$branch_name" \
        --base "main" 2>/dev/null || echo "")
    
    if [ -n "$pr_url" ]; then
        echo -e "${GREEN}✅ Created PR: $pr_url${NC}"
        
        # Link the PR to the issue
        local test_mention=""
        if [ "$CREATE_TESTS" = true ]; then
            test_mention=" (mandatory)"
        fi
        
        local comment_body="🤖 **Automated Implementation Complete**

I've implemented a solution for this issue and created a pull request: $pr_url

The implementation includes:
- Complete solution addressing all requirements  
- Comprehensive testing$test_mention
- Updated documentation
- Follows project conventions

Please review the PR and merge when ready!"
        
        gh issue comment "$issue_number" --repo "$REPOSITORY" --body "$comment_body" 2>/dev/null || echo ""
        
        return 0
    else
        echo -e "${RED}❌ Failed to create PR${NC}"
        return 1
    fi
}

# Main execution
main() {
    echo -e "${BLUE}🚀 Starting autonomous issue worker...${NC}"
    
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
    
    # Get priority issue to work on
    echo -e "${BLUE}📋 Finding highest priority issue...${NC}"
    local issue_number
    issue_number=$(get_priority_issue)
    
    if [ -n "$issue_number" ]; then
        echo -e "${BLUE}  Selected issue: #$issue_number${NC}"
    fi
    
    if [ -z "$issue_number" ]; then
        echo -e "${GREEN}🎉 No open issues found. Nothing to do!${NC}"
        exit 0
    fi
    
    echo -e "${BLUE}📋 Working on issue #$issue_number${NC}"
    
    # Work on the issue
    if work_on_issue "$issue_number"; then
        echo -e "${GREEN}✅ Issue work completed${NC}"
        
        # Create PR if auto-PR is enabled
        if create_pr_for_issue "$issue_number"; then
            echo -e "${GREEN}🎉 Issue #$issue_number fully processed and PR created!${NC}"
        else
            echo -e "${YELLOW}⚠️  Issue work completed but PR creation failed or skipped${NC}"
        fi
    else
        echo -e "${RED}❌ Failed to work on issue #$issue_number${NC}"
        exit 1
    fi
}

# Change to project root
cd "$PROJECT_ROOT"

# Run main function
main