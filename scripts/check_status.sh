#!/bin/bash
# Quick status check script - run anytime to see progress

echo "════════════════════════════════════════════════════════════"
echo "  FULL WEEK PLAYLIST GENERATION STATUS"
echo "════════════════════════════════════════════════════════════"
echo ""

# Check processes
echo "📊 PROCESSES:"
GENERATOR_PID=$(ps aux | grep "generate_full_week" | grep -v grep | awk '{print $2}' | head -1)
MONITOR_PID=$(ps aux | grep "monitor_generation" | grep -v grep | awk '{print $2}' | head -1)

if [ -n "$GENERATOR_PID" ]; then
    echo "  ✓ Generator: Running (PID: $GENERATOR_PID)"
else
    echo "  ✗ Generator: Not running"
fi

if [ -n "$MONITOR_PID" ]; then
    echo "  ✓ Monitor: Running (PID: $MONITOR_PID)"
else
    echo "  ✗ Monitor: Not running"
fi

echo ""

# Count playlists
echo "📁 PLAYLISTS GENERATED:"
PLAYLIST_COUNT=$(ls -1 /workspaces/emby-to-m3u/playlists/*.m3u8 2>/dev/null | wc -l)
EXPECTED=42

echo "  $PLAYLIST_COUNT / $EXPECTED playlists"
if [ "$PLAYLIST_COUNT" -gt 0 ]; then
    echo ""
    echo "  Recent files:"
    ls -lht /workspaces/emby-to-m3u/playlists/*.m3u8 2>/dev/null | head -5 | awk '{print "    " $9 " (" $6 " " $7 ")"}'
fi

echo ""

# Check logs
echo "📝 LOGS:"
if [ -f /workspaces/emby-to-m3u/logs/monitor.log ]; then
    echo "  Monitor log:"
    tail -5 /workspaces/emby-to-m3u/logs/monitor.log | sed 's/^/    /'
fi

echo ""

# Memory status
echo "💾 MEMORY STATUS:"
npx claude-flow@alpha memory retrieve "production-week-hive/coordinator/status" --namespace "swarm" 2>/dev/null | grep -E "status|playlists|day" | sed 's/^/  /'

echo ""
echo "════════════════════════════════════════════════════════════"

# Return exit code based on status
if [ "$PLAYLIST_COUNT" -eq "$EXPECTED" ]; then
    echo "✓ COMPLETE: All playlists generated!"
    exit 0
elif [ -n "$GENERATOR_PID" ]; then
    echo "⏳ IN PROGRESS: Generation continuing..."
    exit 2
else
    echo "⚠ STOPPED: Generator not running"
    exit 1
fi
