#!/bin/bash
# Monitor complete end-to-end deployment progress

LOG_FILE="/workspaces/emby-to-m3u/logs/e2e_complete.log"
REPORT_FILE="/workspaces/emby-to-m3u/logs/e2e_deployment_report.txt"

echo "===== DEPLOYMENT MONITORING ====="
echo "Started: $(date)"
echo ""

# Check if process is running
if ps aux | grep -q "[c]omplete_e2e_test.py"; then
    echo "✅ Deployment process is RUNNING"
else
    echo "⚠️  Deployment process NOT FOUND"
fi

echo ""
echo "===== PROGRESS SUMMARY ====="

# Count playlists generated
PLAYLISTS_GENERATED=$(grep -c "Completed daypart" "$LOG_FILE" 2>/dev/null || echo "0")
echo "Playlists generated: $PLAYLISTS_GENERATED/42"

# Check current step
CURRENT_STEP=$(grep -E "STEP [0-9]:" "$LOG_FILE" | tail -1)
echo "Current step: $CURRENT_STEP"

# Check for errors
ERROR_COUNT=$(grep -c "ERROR:" "$LOG_FILE" 2>/dev/null || echo "0")
echo "Errors encountered: $ERROR_COUNT"

# Show last few important lines
echo ""
echo "===== RECENT ACTIVITY (Last 20 lines) ====="
grep -E "(INFO.*:|WARNING:|ERROR:|✓|🤖|Processing|Completed)" "$LOG_FILE" 2>/dev/null | tail -20 || echo "No activity yet"

echo ""
echo "===== FINAL REPORT ====="
if [ -f "$REPORT_FILE" ]; then
    echo "✅ Final report available at: $REPORT_FILE"
    echo ""
    cat "$REPORT_FILE"
else
    echo "⏳ Final report not yet generated (deployment still in progress)"
fi

echo ""
echo "Ended: $(date)"
