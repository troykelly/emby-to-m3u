#!/bin/bash

# Aperim Template - GitHub PR Worker Script
# Autonomously works through open PRs to resolve issues and get them to mergeable state

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

echo -e "${BLUE}🤖 Aperim Template: Autonomous GitHub PR Worker${NC}"

# Default values
SPECIFIC_PR=""
DRY_RUN=false
HIVE_NAMESPACE="github-pr-worker"
MAX_AGENTS=8
MERGE_WAIT_MINUTES=60
CHECK_INTERVAL_MINUTES=5

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Autonomously work through ALL open PRs in the current repository"
    echo "Finds oldest PR first, works to make it mergeable, then moves to next"
    echo ""
    echo "Options:"
    echo "  --pr, -p NUMBER         Work on specific PR number only"
    echo "  --dry-run              Show what would be done without making changes"
    echo "  --namespace, -n NAME    Hive namespace (default: github-pr-worker)"
    echo "  --agents, -a NUMBER     Maximum agents to spawn (default: 8)"
    echo "  --wait, -w MINUTES      Minutes to wait for user merge (default: 60)"
    echo "  --interval, -i MINUTES  Check interval for merge status (default: 5)"
    echo "  --help, -h              Show this help message"
    echo ""
    echo "Environment Variables:"
    echo "  GITHUB_USER_PAT         Personal Access Token for auto-merge capability"
    echo ""
    echo "Examples:"
    echo "  $0                      # Work on all PRs automatically"
    echo "  $0 --pr 123            # Work on specific PR only"
    echo "  $0 --dry-run           # Show what would be done"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --pr|-p)
            SPECIFIC_PR="$2"
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
        --wait|-w)
            MERGE_WAIT_MINUTES="$2"
            shift 2
            ;;
        --interval|-i)
            CHECK_INTERVAL_MINUTES="$2"
            shift 2
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

# Get list of open PRs (oldest first)
get_open_prs() {
    if [ -n "$SPECIFIC_PR" ]; then
        echo "$SPECIFIC_PR"
        return
    fi
    
    # Use GitHub CLI to get open PRs sorted by creation date (oldest first)
    local prs
    prs=$(gh pr list --repo "$REPOSITORY" --state open --json number,createdAt --jq 'sort_by(.createdAt) | .[].number' 2>/dev/null) || {
        echo -e "${RED}❌ Failed to fetch PRs. Make sure you have 'gh' CLI installed and authenticated${NC}" >&2
        exit 1
    }
    
    # Return the PRs (could be empty if no PRs exist)
    echo "$prs"
}

# Check if PR is ready to merge
is_pr_ready_to_merge() {
    local pr_number="$1"
    
    # Get PR status using GitHub CLI
    local status_info
    status_info=$(gh pr view "$pr_number" --repo "$REPOSITORY" --json state,mergeable,statusCheckRollup,mergeStateStatus 2>/dev/null || echo '{}')
    
    local state mergeable merge_state_status ci_all_success
    state=$(echo "$status_info" | jq -r '.state // "UNKNOWN"')
    mergeable=$(echo "$status_info" | jq -r '.mergeable // "UNKNOWN"')
    merge_state_status=$(echo "$status_info" | jq -r '.mergeStateStatus // "UNKNOWN"')
    
    # Check if ALL CI checks are successful - this is the ONLY way to be truly ready
    # We need to check for both failed AND pending checks
    local failed_checks pending_checks
    failed_checks=$(echo "$status_info" | jq -r '.statusCheckRollup | map(select(.conclusion == "FAILURE" or .conclusion == "CANCELLED" or .conclusion == "TIMED_OUT" or .conclusion == "ACTION_REQUIRED")) | length')
    pending_checks=$(echo "$status_info" | jq -r '.statusCheckRollup | map(select(.status == "PENDING" or .status == "IN_PROGRESS" or .status == "QUEUED" or .conclusion == null)) | length')
    
    if [[ "$failed_checks" = "0" && "$pending_checks" = "0" ]]; then
        ci_all_success="SUCCESS"
    elif [ "$pending_checks" != "0" ]; then
        ci_all_success="PENDING"
    else
        ci_all_success="FAILED"
    fi
    
    # Output status to stderr so it doesn't interfere with return value
    echo -e "${BLUE}  PR State: $state, Mergeable: $mergeable, MergeState: $merge_state_status, CI: $ci_all_success${NC}" >&2
    
    # PR is ready ONLY if it's open, mergeable, merge state is clean/has_hooks, AND all CI checks pass
    # UNSTABLE, DIRTY, or BLOCKED merge states mean it's NOT ready
    if [[ "$state" == "OPEN" && "$mergeable" == "MERGEABLE" && \
          ("$merge_state_status" == "CLEAN" || "$merge_state_status" == "HAS_HOOKS") && \
          "$ci_all_success" == "SUCCESS" ]]; then
        return 0
    else
        return 1
    fi
}

# Work on a specific PR using Claude-Flow
work_on_pr() {
    local pr_number="$1"
    
    echo -e "${BLUE}🔧 Working on PR #$pr_number...${NC}"
    
    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}[DRY RUN] Would work on PR #$pr_number${NC}"
        return 0
    fi
    
    # Get PR details
    local pr_info
    pr_info=$(gh pr view "$pr_number" --repo "$REPOSITORY" --json title,body,url 2>/dev/null || echo '{}')
    
    local pr_title pr_body pr_url
    pr_title=$(echo "$pr_info" | jq -r '.title // "Unknown"')
    pr_body=$(echo "$pr_info" | jq -r '.body // ""')
    pr_url=$(echo "$pr_info" | jq -r '.url // ""')
    
    echo -e "${BLUE}  Title: $pr_title${NC}"
    echo -e "${BLUE}  URL: $pr_url${NC}"
    
    # Create Claude-Flow objective for this PR
    local objective="Resolve all issues in PR #$pr_number: '$pr_title'. 
    
Repository: $REPOSITORY
PR URL: $pr_url

Tasks:
1. Analyze the PR and identify any CI failures, review comments, or merge conflicts
2. Fix any failing tests or CI issues
3. Address all review comments systematically
4. Resolve any merge conflicts with the target branch
5. Ensure code follows project conventions and best practices
6. Update documentation if needed
7. Verify all status checks pass

Goal: Get this PR to a fully mergeable state with all checks green."

    # Start Claude-Flow hive-mind for this PR
    echo -e "${BLUE}🐝 Starting hive-mind for PR #$pr_number...${NC}"
    
    cd "$PROJECT_ROOT"
    
    # Fix TTY/stdin issues for containerized environments
    export FORCE_COLOR=0
    export NO_COLOR=1
    export TERM=xterm-256color
    unset COLUMNS LINES
    
    if command -v npx &> /dev/null && npx --yes claude-flow@alpha --version >/dev/null 2>&1; then
        echo -e "${BLUE}Starting hive-mind with TTY fixes...${NC}"
        
        # Create a properly formatted objective file to avoid stdin issues
        local objective_file="/tmp/pr-objective-$pr_number.txt"
        cat > "$objective_file" << 'EOF'
Resolve all issues in PR #$pr_number: '$pr_title'

Repository: $REPOSITORY
PR URL: $pr_url

Tasks:
1. Analyze the PR and identify any CI failures, review comments, or merge conflicts
2. Fix any failing tests or CI issues
3. Address all review comments systematically
4. Resolve any merge conflicts with the target branch
5. Ensure code follows project conventions and best practices
6. Update documentation if needed
7. Verify all status checks pass

Goal: Get this PR to a fully mergeable state with all checks green.
EOF
        
        # Replace variables in the file
        sed -i "s/\$pr_number/$pr_number/g" "$objective_file"
        sed -i "s/\$pr_title/$pr_title/g" "$objective_file"
        sed -i "s|\$REPOSITORY|$REPOSITORY|g" "$objective_file"
        sed -i "s|\$pr_url|$pr_url|g" "$objective_file"
        
        # Use non-interactive mode with timeout and proper error handling
        echo -e "${BLUE}Starting hive-mind in non-interactive mode with 10-minute timeout...${NC}"
        
        # Read objective and properly escape it for shell
        local objective_text=$(cat "$objective_file")
        
        # Set up timeout and logging
        local timeout_seconds=18000  # 5 hours - complex tasks can take hours
        local log_file="/tmp/hive-mind-pr-$pr_number.log"
        
        echo -e "${BLUE}Hive-mind will timeout after $((timeout_seconds / 60)) minutes if stuck${NC}"
        echo -e "${BLUE}Log file: $log_file${NC}"
        
        # Start hive-mind in background and show live agent activity
        echo -e "${BLUE}🎯 Starting hive-mind for PR #$pr_number...${NC}"
        echo -e "${BLUE}📺 Live Agent Activity (intelligent timeout: 10min inactivity):${NC}"
        echo ""
        
        # Start hive-mind in background, save log, and show interpreted output
        npx --yes claude-flow@alpha hive-mind spawn \
            $(printf '%q' "$objective_text") \
            --name "pr-worker-$pr_number" \
            --agents "$MAX_AGENTS" \
            --namespace "$HIVE_NAMESPACE-pr-$pr_number" \
            --strategy hierarchical \
            --auto-scale \
            --auto-spawn \
            --claude \
            --non-interactive \
            --verbose \
            > "$log_file" 2>&1 &
        
        local hive_pid=$!
        local last_activity=$(date +%s)
        # Ensure last_activity is a valid number
        if ! [[ "$last_activity" =~ ^[0-9]+$ ]]; then
            last_activity="0"
        fi
        local inactivity_timeout=600  # 10 minutes of inactivity
        
        # Start log interpreter to follow the log file
        sleep 2  # Give hive-mind time to start writing
        "$SCRIPT_DIR/claude-log-interpreter.sh" --follow --compact "$log_file" &
        local interpreter_pid=$!
        
        # Monitor for activity and implement intelligent timeout
        while kill -0 $hive_pid 2>/dev/null; do
            # Check if log file has been modified recently
            if [ -f "$log_file" ]; then
                local log_mtime
                if command -v stat >/dev/null 2>&1; then
                    # Try different stat formats depending on OS
                    if stat -f %m "$log_file" >/dev/null 2>&1; then
                        log_mtime=$(stat -f %m "$log_file" 2>/dev/null | head -1)
                    elif stat -c %Y "$log_file" >/dev/null 2>&1; then
                        log_mtime=$(stat -c %Y "$log_file" 2>/dev/null | head -1)
                    else
                        log_mtime="0"
                    fi
                else
                    log_mtime="0"
                fi
                
                # Ensure log_mtime is a valid number
                if ! [[ "$log_mtime" =~ ^[0-9]+$ ]]; then
                    log_mtime="0"
                fi
                local current_time=$(date +%s)
                
                if [ "$log_mtime" -gt "$last_activity" ]; then
                    last_activity=$log_mtime
                fi
                
                # Check for inactivity timeout (10 minutes with no log updates)
                local inactive_time=$((current_time - last_activity))
                if [ $inactive_time -gt $inactivity_timeout ]; then
                    echo ""
                    echo -e "${YELLOW}⏰ Hive-mind inactive for 10 minutes, terminating...${NC}"
                    kill -TERM $hive_pid 2>/dev/null || true
                    break
                fi
            fi
            
            sleep 5  # Check every 5 seconds
        done
        
        # Wait for hive-mind to complete
        wait $hive_pid 2>/dev/null
        local exit_code=$?
        
        # Stop the log interpreter
        kill $interpreter_pid 2>/dev/null || true
        echo ""
        
        if [ $exit_code -eq 0 ]; then
            echo -e "${GREEN}✅ Hive-mind completed successfully${NC}"
        elif [ $exit_code -eq 143 ]; then
            # SIGTERM - normal termination after completion detection
            echo -e "${GREEN}✅ Hive-mind work completed (terminated gracefully)${NC}"
        elif [ $exit_code -eq 124 ]; then
            echo -e "${YELLOW}⏰ Hive-mind timed out after $((timeout_seconds / 60)) minutes${NC}"
        else
            echo -e "${RED}❌ Hive-mind failed with exit code $exit_code${NC}"
            
            # Clean up any stuck processes
            echo -e "${BLUE}Cleaning up any stuck hive-mind processes...${NC}"
            pkill -f "claude-flow.*hive-mind.*pr-worker-$pr_number" || true
            pkill -f "claude.*pr-worker-$pr_number" || true
        fi
        
        # Always cleanup log file
        rm -f "$log_file"
        
        # Cleanup
        rm -f "$objective_file"
        
    else
        echo -e "${RED}❌ Claude-Flow not available${NC}"
        return 1
    fi
    
    echo -e "${GREEN}✅ Completed work on PR #$pr_number${NC}"
}

# Wait for merge or auto-merge if possible
wait_and_merge() {
    local pr_number="$1"
    local start_time=$(date +%s)
    local wait_seconds=$((MERGE_WAIT_MINUTES * 60))
    local check_seconds=$((CHECK_INTERVAL_MINUTES * 60))
    
    echo -e "${BLUE}⏳ Waiting up to $MERGE_WAIT_MINUTES minutes for PR #$pr_number to be merged...${NC}"
    
    while true; do
        local current_time=$(date +%s)
        local elapsed=$((current_time - start_time))
        
        # Check if PR is merged
        local pr_state
        pr_state=$(gh pr view "$pr_number" --repo "$REPOSITORY" --json state --jq '.state' 2>/dev/null || echo "UNKNOWN")
        
        if [ "$pr_state" = "MERGED" ]; then
            echo -e "${GREEN}✅ PR #$pr_number has been merged!${NC}"
            return 0
        elif [ "$pr_state" = "CLOSED" ]; then
            echo -e "${YELLOW}⚠️  PR #$pr_number has been closed without merging${NC}"
            return 1
        fi
        
        # Check if we've waited long enough
        if [ $elapsed -ge $wait_seconds ]; then
            echo -e "${YELLOW}⏰ Wait time exceeded for PR #$pr_number${NC}"
            
            # Try auto-merge if GITHUB_USER_PAT is available
            if [ -n "${GITHUB_USER_PAT:-}" ] && is_pr_ready_to_merge "$pr_number"; then
                echo -e "${BLUE}🔄 Attempting auto-merge with GITHUB_USER_PAT...${NC}"
                
                if [ "$DRY_RUN" = true ]; then
                    echo -e "${YELLOW}[DRY RUN] Would auto-merge PR #$pr_number${NC}"
                else
                    # Set the GitHub token and try to merge
                    GITHUB_TOKEN="$GITHUB_USER_PAT" gh pr merge "$pr_number" --repo "$REPOSITORY" --merge --delete-branch 2>/dev/null && {
                        echo -e "${GREEN}✅ Auto-merged PR #$pr_number${NC}"
                        return 0
                    } || {
                        echo -e "${YELLOW}⚠️  Auto-merge failed for PR #$pr_number${NC}"
                    }
                fi
            else
                echo -e "${YELLOW}⚠️  Cannot auto-merge: GITHUB_USER_PAT not set or PR not ready${NC}"
            fi
            
            return 1
        fi
        
        # Show progress
        local remaining=$((wait_seconds - elapsed))
        local remaining_minutes=$((remaining / 60))
        echo -e "${BLUE}⏳ Waiting... $remaining_minutes minutes remaining${NC}"
        
        # Wait for next check
        sleep $check_seconds
    done
}

# Main execution
main() {
    echo -e "${BLUE}🚀 Starting autonomous PR worker...${NC}"
    
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
    
    # Get list of open PRs
    echo -e "${BLUE}📋 Fetching open PRs...${NC}"
    local prs
    prs=$(get_open_prs)
    
    if [ -z "$prs" ]; then
        echo -e "${GREEN}🎉 No open PRs found. Nothing to do!${NC}"
        exit 0
    fi
    
    # Count non-empty PR numbers
    local pr_count=0
    while IFS= read -r pr_number; do
        [ -n "$pr_number" ] && pr_count=$((pr_count + 1))
    done <<< "$prs"
    
    echo -e "${BLUE}📋 Found PRs to work on: $pr_count${NC}"
    
    # Work through each PR
    local processed=0
    while IFS= read -r pr_number; do
        [ -z "$pr_number" ] && continue
        
        echo -e "${BLUE}📝 Processing PR #$pr_number...${NC}"
        
        # Check if already ready to merge
        if is_pr_ready_to_merge "$pr_number"; then
            echo -e "${GREEN}✅ PR #$pr_number is already ready to merge!${NC}"
            wait_and_merge "$pr_number"
        else
            # Work on the PR
            if work_on_pr "$pr_number"; then
                # Check if it's now ready
                if is_pr_ready_to_merge "$pr_number"; then
                    echo -e "${GREEN}✅ PR #$pr_number is now ready to merge!${NC}"
                    wait_and_merge "$pr_number"
                else
                    echo -e "${YELLOW}⚠️  PR #$pr_number still needs work${NC}"
                fi
            else
                echo -e "${RED}❌ Failed to work on PR #$pr_number${NC}"
            fi
        fi
        
        processed=$((processed + 1))
        echo -e "${BLUE}📊 Processed $processed PR(s)${NC}"
        
        # If working on specific PR, exit after processing it
        if [ -n "$SPECIFIC_PR" ]; then
            break
        fi
        
    done <<< "$prs"
    
    echo -e "${GREEN}🎉 Autonomous PR worker completed! Processed $processed PR(s)${NC}"
}

# Change to project root
cd "$PROJECT_ROOT"

# Run main function
main