#!/usr/bin/env python3
"""
AI Playlist Generation - Main Entry Point

Complete end-to-end AI playlist deployment using Subsonic/Navidrome and AzuraCast.

Usage:
    python -m src.ai_playlist.main
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# Import and run the deployment script
from scripts.deploy_playlists import main

if __name__ == "__main__":
    main()
