#!/bin/bash
# Quick status check for monitoring progress

if [ -f /tmp/monitor_log.txt ]; then
    echo "=== Current Monitor Status ==="
    tail -20 /tmp/monitor_log.txt
    echo ""
    echo "=== Playlist Files ==="
    find /tmp/pipeline_fix_test -name "*.m3u8" 2>/dev/null | wc -l
    echo "files found"
else
    echo "Monitor not yet started or log file missing"
fi
