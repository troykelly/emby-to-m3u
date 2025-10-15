#!/bin/bash
# Autonomous monitoring script for full week playlist generation
# Runs in loop, checks progress, stores in memory, reports only when complete

MAX_CHECKS=300  # 300 checks × 60s = 5 hours max
CHECK_INTERVAL=60  # Check every 60 seconds
EXPECTED_PLAYLISTS=42

echo "=== AUTONOMOUS MONITORING STARTED ==="
echo "Expected playlists: $EXPECTED_PLAYLISTS"
echo "Check interval: ${CHECK_INTERVAL}s"
echo "Max runtime: $((MAX_CHECKS * CHECK_INTERVAL / 3600)) hours"

for ((i=1; i<=MAX_CHECKS; i++)); do
    echo ""
    echo "Check $i/$MAX_CHECKS at $(date '+%H:%M:%S')"

    # Count generated playlists
    PLAYLIST_COUNT=$(ls -1 /workspaces/emby-to-m3u/playlists/*.m3u8 2>/dev/null | wc -l)

    # Check if process still running
    PROCESS_COUNT=$(ps aux | grep -E "generate_full_week" | grep -v grep | wc -l)

    # Check log files for errors
    ERROR_COUNT=$(find /workspaces/emby-to-m3u/playlists/logs -name "*.log" -type f -exec grep -i "error\|fatal\|exception" {} \; 2>/dev/null | wc -l)

    echo "Status: $PLAYLIST_COUNT/$EXPECTED_PLAYLISTS playlists | Process: $PROCESS_COUNT | Errors: $ERROR_COUNT"

    # Store in memory
    npx claude-flow@alpha memory store "production-week-hive/monitor/check-$i" "{\"check\":$i,\"playlists\":$PLAYLIST_COUNT,\"process_running\":$PROCESS_COUNT,\"errors\":$ERROR_COUNT,\"timestamp\":\"$(date -Iseconds)\"}" --namespace "swarm" &>/dev/null

    # Check completion conditions
    if [ "$PLAYLIST_COUNT" -eq "$EXPECTED_PLAYLISTS" ]; then
        echo ""
        echo "✓ SUCCESS: All $EXPECTED_PLAYLISTS playlists generated!"
        npx claude-flow@alpha memory store "production-week-hive/coordinator/final-status" "{\"status\":\"success\",\"playlists\":$PLAYLIST_COUNT,\"checks\":$i,\"timestamp\":\"$(date -Iseconds)\"}" --namespace "swarm"
        exit 0
    fi

    # Check if process died prematurely
    if [ "$PROCESS_COUNT" -eq 0 ] && [ "$PLAYLIST_COUNT" -lt "$EXPECTED_PLAYLISTS" ]; then
        echo ""
        echo "✗ FAILURE: Process stopped with only $PLAYLIST_COUNT/$EXPECTED_PLAYLISTS playlists"
        npx claude-flow@alpha memory store "production-week-hive/coordinator/final-status" "{\"status\":\"failed\",\"playlists\":$PLAYLIST_COUNT,\"reason\":\"process_stopped\",\"timestamp\":\"$(date -Iseconds)\"}" --namespace "swarm"
        exit 1
    fi

    # Check for too many errors
    if [ "$ERROR_COUNT" -gt 20 ]; then
        echo ""
        echo "⚠ WARNING: High error count ($ERROR_COUNT), may need investigation"
    fi

    # Wait before next check
    sleep $CHECK_INTERVAL
done

# Max checks exceeded
echo ""
echo "⚠ TIMEOUT: Max monitoring time exceeded"
echo "Generated: $PLAYLIST_COUNT/$EXPECTED_PLAYLISTS playlists"
npx claude-flow@alpha memory store "production-week-hive/coordinator/final-status" "{\"status\":\"timeout\",\"playlists\":$PLAYLIST_COUNT,\"checks\":$MAX_CHECKS,\"timestamp\":\"$(date -Iseconds)\"}" --namespace "swarm"
exit 2
