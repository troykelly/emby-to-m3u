#!/bin/bash
# Wrapper script to run deployment with correct PYTHONPATH

cd /workspaces/emby-to-m3u
export PYTHONPATH="/workspaces/emby-to-m3u/src:/workspaces/emby-to-m3u:$PYTHONPATH"

# Run the deployment
python3 scripts/deploy_real_playlists.py "$@"
