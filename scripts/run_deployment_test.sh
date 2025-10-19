#!/bin/bash
# Run deployment test with proper logging and monitoring

set -e

PROJECT_ROOT="/workspaces/emby-to-m3u"
LOG_DIR="$PROJECT_ROOT/logs"
LOG_FILE="$LOG_DIR/deployment_$(date +%Y%m%d_%H%M%S).log"

# Create logs directory
mkdir -p "$LOG_DIR"

echo "======================================================================"
echo "AI Playlist Deployment Test - $(date)"
echo "======================================================================"
echo ""
echo "Log file: $LOG_FILE"
echo ""
echo "This will:"
echo "  1. Generate ONE real playlist using GPT-5"
echo "  2. Upload tracks to AzuraCast"
echo "  3. Create playlist in AzuraCast"
echo "  4. Link tracks to playlist"
echo ""
echo "Expected duration: 5-10 minutes"
echo "======================================================================"
echo ""

# Run deployment test
cd "$PROJECT_ROOT"
python scripts/deploy_real_playlists.py test 2>&1 | tee "$LOG_FILE"

# Show summary
echo ""
echo "======================================================================"
echo "Test complete! Check log for details: $LOG_FILE"
echo "======================================================================"
