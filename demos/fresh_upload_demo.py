#!/usr/bin/env python3
"""
Fresh Upload Demo - Force upload a new track to AzuraCast
Bypasses duplicate detection to ensure actual file upload
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from subsonic.client import SubsonicClient
from subsonic.models import SubsonicConfig
import requests

print("=" * 80)
print("FRESH UPLOAD TO AZURACAST - BYPASSING DUPLICATE DETECTION".center(80))
print("=" * 80)

# Step 1: Get a random track from Subsonic
config = SubsonicConfig(
    url=os.getenv("SUBSONIC_URL"),
    username=os.getenv("SUBSONIC_USER"),
    password=os.getenv("SUBSONIC_PASSWORD"),
    api_version="1.16.1",
    client_name="emby-to-m3u-demo"
)

print("\n📡 Connecting to Subsonic...")
with SubsonicClient(config) as client:
    if not client.ping():
        print("❌ Failed to connect")
        sys.exit(1)

    print("✅ Connected to Subsonic")

    # Get random track
    tracks = client.get_random_songs(size=1)
    if not tracks:
        print("❌ No tracks found")
        sys.exit(1)

    track = tracks[0]
    print(f"\n🎵 Selected: '{track.title}' by '{track.artist}'")
    print(f"   Album: {track.album}")
    print(f"   Format: {track.suffix}")
    print(f"   MusicBrainz ID: {track.musicBrainzId}")

    # Download track
    print(f"\n⬇️  Downloading track...")
    audio_data = client.download_track(track.id)
    print(f"✅ Downloaded {len(audio_data):,} bytes ({len(audio_data)/1024/1024:.2f} MB)")

# Step 2: Upload directly to AzuraCast API
azuracast_host = os.getenv("AZURACAST_HOST")
api_key = os.getenv("AZURACAST_API_KEY")
station_id = os.getenv("AZURACAST_STATIONID")

print(f"\n📡 Uploading to AzuraCast: {azuracast_host}")
print(f"   Station ID: {station_id}")

# Generate path for the file
file_path = f"{track.artist}/{track.album or 'Unknown'}/{track.title}.{track.suffix}"
print(f"   Target path: {file_path}")

# Prepare upload
url = f"{azuracast_host}/api/station/{station_id}/files"
headers = {"X-API-Key": api_key}

# AzuraCast expects 'file_data' as the file field name
files = {
    'file_data': (file_path, audio_data, f"audio/{track.suffix}")
}

print(f"\n⬆️  Uploading file...")

session = requests.Session()
session.verify = False
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    response = session.post(url, headers=headers, files=files, timeout=120)
    print(f"\n📊 Response Status: {response.status_code}")

    if response.status_code == 200:
        result = response.json()
        print(f"✅ Upload successful!")
        print(f"\n📋 AzuraCast Response:")
        print(f"   File ID: {result.get('id')}")
        print(f"   Unique ID: {result.get('unique_id')}")
        print(f"   Path: {result.get('path')}")
        print(f"   Title: {result.get('title')}")
        print(f"   Artist: {result.get('artist')}")
        print(f"   Album: {result.get('album')}")

        print(f"\n🎯 Verify in AzuraCast UI:")
        print(f"   URL: {azuracast_host}")
        print(f"   Station: {station_id}")
        print(f"   File ID: {result.get('id')}")
        print(f"   Search for: {track.artist} - {track.title}")
    else:
        print(f"❌ Upload failed")
        print(f"Response: {response.text}")
except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "=" * 80)
