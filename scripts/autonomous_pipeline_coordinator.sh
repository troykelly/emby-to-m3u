#!/bin/bash
# Autonomous Pipeline Fix-Test-Loop Coordinator
# Manages iterative fixing until all 42 playlists sync to AzuraCast

set -euo pipefail

WORKSPACE="/workspaces/emby-to-m3u"
LOG_DIR="$WORKSPACE/logs"
PLAYLIST_DIR="$WORKSPACE/playlists"
SESSION_ID="pipeline-fix-loop-$(date +%s)"
MAX_ITERATIONS=5
CHECK_INTERVAL=120  # 2 minutes for test results
STATUS_INTERVAL=300 # 5 minutes for fix status

# Initialize logging
mkdir -p "$LOG_DIR"
MAIN_LOG="$LOG_DIR/coordinator_${SESSION_ID}.log"
PIPELINE_LOG="$LOG_DIR/pipeline_fix.log"
FULL_WEEK_LOG="$LOG_DIR/full_week.log"
STATUS_FILE="$LOG_DIR/coordinator_status.json"

# Logging function
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" | tee -a "$MAIN_LOG"
}

# Initialize session
initialize_session() {
    log "Initializing autonomous coordination session: $SESSION_ID"

    # Restore previous session context
    npx claude-flow@alpha hooks session-restore --session-id "$SESSION_ID" 2>&1 | tee -a "$MAIN_LOG" || true

    # Initialize status tracking
    cat > "$STATUS_FILE" <<EOF
{
  "session_id": "$SESSION_ID",
  "started_at": "$(date -Iseconds)",
  "status": "initializing",
  "iteration": 0,
  "max_iterations": $MAX_ITERATIONS,
  "playlists_synced": 0,
  "target_playlists": 42,
  "last_error": null,
  "agents": {
    "coder": "idle",
    "tester": "idle",
    "coordinator": "active"
  }
}
EOF

    # Store in swarm memory
    npx claude-flow@alpha hooks post-edit \
        --file "$STATUS_FILE" \
        --memory-key "swarm/coordinator/status" 2>&1 | tee -a "$MAIN_LOG" || true

    log "Session initialized successfully"
}

# Update status in memory
update_status() {
    local iteration=$1
    local status=$2
    local error_msg="${3:-null}"
    local playlists_synced="${4:-0}"

    cat > "$STATUS_FILE" <<EOF
{
  "session_id": "$SESSION_ID",
  "updated_at": "$(date -Iseconds)",
  "status": "$status",
  "iteration": $iteration,
  "max_iterations": $MAX_ITERATIONS,
  "playlists_synced": $playlists_synced,
  "target_playlists": 42,
  "last_error": $error_msg,
  "agents": {
    "coder": "active",
    "tester": "monitoring",
    "coordinator": "coordinating"
  }
}
EOF

    npx claude-flow@alpha hooks post-edit \
        --file "$STATUS_FILE" \
        --memory-key "swarm/coordinator/status" 2>&1 | tee -a "$MAIN_LOG" || true
}

# Check test results
check_test_results() {
    if [[ ! -f "$PIPELINE_LOG" ]]; then
        log "No pipeline log found yet, waiting..."
        return 1
    fi

    if grep -q "SUCCESS" "$PIPELINE_LOG"; then
        log "✓ Pipeline tests PASSED"
        return 0
    elif grep -q "FAILURE\|ERROR\|Traceback" "$PIPELINE_LOG"; then
        log "✗ Pipeline tests FAILED"
        return 2
    else
        log "Tests still running..."
        return 1
    fi
}

# Extract error details
extract_error() {
    if [[ -f "$PIPELINE_LOG" ]]; then
        tail -100 "$PIPELINE_LOG" | grep -A20 "ERROR\|Traceback\|FAILED" | head -50 || echo "No specific error found"
    else
        echo "No log file available"
    fi
}

# Notify agents via hooks
notify_agents() {
    local message="$1"
    log "Notifying agents: $message"
    npx claude-flow@alpha hooks notify --message "$message" 2>&1 | tee -a "$MAIN_LOG" || true
}

# Launch full week generation
launch_full_week() {
    log "🚀 Launching full week playlist generation"

    if [[ ! -f "$WORKSPACE/station-identity.md" ]]; then
        log "ERROR: station-identity.md not found"
        return 1
    fi

    python "$WORKSPACE/scripts/generate_full_week.py" \
        --input "$WORKSPACE/station-identity.md" \
        --output "$PLAYLIST_DIR" \
        --max-cost 10.0 > "$FULL_WEEK_LOG" 2>&1 &

    local pid=$!
    echo "$pid" > "$LOG_DIR/full_week_pid.txt"
    log "Full week generation started with PID: $pid"

    notify_agents "Full week generation launched (PID: $pid)"
    return 0
}

# Main coordination loop
main() {
    initialize_session

    local iteration=1

    while [[ $iteration -le $MAX_ITERATIONS ]]; do
        log "========== Iteration $iteration/$MAX_ITERATIONS =========="

        update_status "$iteration" "testing" "null" 0
        notify_agents "Starting iteration $iteration - waiting for test results"

        # Wait for test completion with periodic checks
        local elapsed=0
        local timeout=600  # 10 minutes max wait per iteration

        while [[ $elapsed -lt $timeout ]]; do
            check_test_results
            local result=$?

            if [[ $result -eq 0 ]]; then
                # SUCCESS - launch full week
                log "✓✓✓ PIPELINE TESTS PASSED ✓✓✓"
                update_status "$iteration" "success" "null" 0

                if launch_full_week; then
                    update_status "$iteration" "generating" "null" 0
                    log "Full week generation in progress - monitoring..."

                    # Monitor full week generation
                    while kill -0 $(cat "$LOG_DIR/full_week_pid.txt" 2>/dev/null || echo 0) 2>/dev/null; do
                        sleep 30
                        local synced=$(grep -c "Successfully synced" "$FULL_WEEK_LOG" 2>/dev/null || echo 0)
                        log "Progress: $synced playlists synced"
                        update_status "$iteration" "generating" "null" "$synced"
                    done

                    # Check final results
                    local final_synced=$(grep -c "Successfully synced" "$FULL_WEEK_LOG" 2>/dev/null || echo 0)
                    log "Final result: $final_synced/42 playlists synced"

                    if [[ $final_synced -eq 42 ]]; then
                        log "🎉🎉🎉 ALL 42 PLAYLISTS SYNCED SUCCESSFULLY 🎉🎉🎉"
                        update_status "$iteration" "completed" "null" "$final_synced"
                        npx claude-flow@alpha hooks session-end --export-metrics true 2>&1 | tee -a "$MAIN_LOG"
                        exit 0
                    else
                        log "⚠ Partial success: $final_synced/42 playlists synced"
                        update_status "$iteration" "partial" "\"Incomplete sync: $final_synced/42\"" "$final_synced"
                    fi
                fi
                break

            elif [[ $result -eq 2 ]]; then
                # FAILURE - extract error and continue loop
                log "✗✗✗ PIPELINE TESTS FAILED ✗✗✗"
                local error_details=$(extract_error | jq -Rs .)
                update_status "$iteration" "failed" "$error_details" 0
                notify_agents "Iteration $iteration failed - check logs for details"
                break

            else
                # STILL RUNNING
                sleep "$CHECK_INTERVAL"
                elapsed=$((elapsed + CHECK_INTERVAL))
                log "Waiting for tests... (${elapsed}s elapsed)"
            fi
        done

        if [[ $elapsed -ge $timeout ]]; then
            log "⏱ Iteration $iteration timed out"
            update_status "$iteration" "timeout" "\"Test execution timeout\"" 0
            notify_agents "Iteration $iteration timed out - moving to next iteration"
        fi

        iteration=$((iteration + 1))

        # Reset pipeline log for next iteration
        if [[ $iteration -le $MAX_ITERATIONS ]]; then
            mv "$PIPELINE_LOG" "${PIPELINE_LOG}.iter$((iteration-1))" 2>/dev/null || true
            log "Prepared for next iteration"
            sleep 5
        fi
    done

    log "❌ Max iterations ($MAX_ITERATIONS) exhausted"
    update_status "$MAX_ITERATIONS" "exhausted" "\"Maximum iterations reached\"" 0
    notify_agents "Coordination complete - max iterations exhausted"
    npx claude-flow@alpha hooks session-end --export-metrics true 2>&1 | tee -a "$MAIN_LOG"
    exit 1
}

# Run main coordination
main
