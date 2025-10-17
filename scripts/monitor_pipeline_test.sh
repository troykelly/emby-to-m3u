#!/bin/bash
# Autonomous Pipeline Test Monitor
# Monitors test execution and reports results

LOG_FILE="/tmp/pipeline_fix.log"
TEST_DIR="/tmp/pipeline_fix_test"
MONITOR_LOG="/tmp/monitor_log.txt"
MAX_CHECKS=15
CHECK_INTERVAL=120

echo "=== Pipeline Test Monitor Started ===" > "$MONITOR_LOG"
echo "Start time: $(date)" >> "$MONITOR_LOG"
echo "" >> "$MONITOR_LOG"

# Function to check test status
check_test_status() {
    local check_num=$1
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    echo "[$timestamp] Check $check_num/$MAX_CHECKS" >> "$MONITOR_LOG"

    # Check for playlist files
    if [ -d "$TEST_DIR" ]; then
        local playlist_count=$(find "$TEST_DIR" -name "*.m3u8" 2>/dev/null | wc -l)
        echo "  Playlists created: $playlist_count" >> "$MONITOR_LOG"

        if [ $playlist_count -gt 0 ]; then
            echo "  ✅ SUCCESS: Playlists are being created!" >> "$MONITOR_LOG"
            echo "" >> "$MONITOR_LOG"
            ls -lh "$TEST_DIR"/*.m3u8 >> "$MONITOR_LOG" 2>/dev/null
            return 0
        fi
    else
        echo "  Test directory not yet created" >> "$MONITOR_LOG"
    fi

    # Check for errors in log
    if [ -f "$LOG_FILE" ]; then
        local error_count=$(grep -i "error\|exception\|traceback" "$LOG_FILE" 2>/dev/null | wc -l)
        if [ $error_count -gt 0 ]; then
            echo "  ⚠️  Detected $error_count errors in log" >> "$MONITOR_LOG"
        fi

        local last_line=$(tail -1 "$LOG_FILE" 2>/dev/null)
        echo "  Last log: $last_line" >> "$MONITOR_LOG"
    fi

    echo "" >> "$MONITOR_LOG"
    return 1
}

# Main monitoring loop
for i in $(seq 1 $MAX_CHECKS); do
    check_test_status $i

    if [ $? -eq 0 ]; then
        echo "=== TEST SUCCESSFUL ===" >> "$MONITOR_LOG"
        echo "End time: $(date)" >> "$MONITOR_LOG"

        # Store success in memory
        npx claude-flow@alpha hooks notify --message "Pipeline test SUCCESS - playlists created" >> "$MONITOR_LOG" 2>&1

        cat "$MONITOR_LOG"
        exit 0
    fi

    # Don't sleep on last check
    if [ $i -lt $MAX_CHECKS ]; then
        sleep $CHECK_INTERVAL
    fi
done

# Test failed - extract errors
echo "=== TEST FAILED ===" >> "$MONITOR_LOG"
echo "End time: $(date)" >> "$MONITOR_LOG"
echo "" >> "$MONITOR_LOG"

if [ -f "$LOG_FILE" ]; then
    echo "=== ERROR SUMMARY ===" >> "$MONITOR_LOG"
    grep -i "error\|exception\|traceback" "$LOG_FILE" | tail -20 >> "$MONITOR_LOG" 2>/dev/null
    echo "" >> "$MONITOR_LOG"
    echo "=== LAST 50 LOG LINES ===" >> "$MONITOR_LOG"
    tail -50 "$LOG_FILE" >> "$MONITOR_LOG" 2>/dev/null
fi

# Store failure in memory
npx claude-flow@alpha hooks notify --message "Pipeline test FAILED - no playlists after 30 minutes" >> "$MONITOR_LOG" 2>&1

cat "$MONITOR_LOG"
exit 1
