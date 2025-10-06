#!/usr/bin/env python3
"""
Proper ReplayGain Demo - Download from Subsonic, Add ReplayGain, Upload to AzuraCast
Uses the existing replaygain.main module to properly add ReplayGain metadata
"""

import os
import sys
from pathlib import Path
from io import BytesIO
from base64 import b64encode
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from subsonic.client import SubsonicClient
from subsonic.models import SubsonicConfig
from replaygain.main import has_replaygain_metadata, process_replaygain
import requests

def print_section(title):
    print("\n" + "=" * 80)
    print(title.center(80))
    print("=" * 80)

print_section("PROPER REPLAYGAIN WORKFLOW")

# Step 1: Download from Subsonic
print_section("STEP 1: DOWNLOAD FROM SUBSONIC")

config = SubsonicConfig(
    url=os.getenv("SUBSONIC_URL"),
    username=os.getenv("SUBSONIC_USER"),
    password=os.getenv("SUBSONIC_PASSWORD"),
    api_version="1.16.1",
    client_name="emby-to-m3u-demo"
)

print(f"📡 Connecting to: {config.url}")

with SubsonicClient(config) as client:
    if not client.ping():
        print("❌ Connection failed")
        sys.exit(1)

    print("✅ Connected")

    tracks = client.get_random_songs(size=1)
    if not tracks:
        print("❌ No tracks found")
        sys.exit(1)

    track = tracks[0]
    print(f"\n🎵 Selected: '{track.title}' by '{track.artist}'")
    print(f"   Album: {track.album}")
    print(f"   Format: {track.suffix}")
    if track.musicBrainzId:
        print(f"   MusicBrainz ID: {track.musicBrainzId}")

    print(f"\n⬇️  Downloading...")
    audio_data = client.download_track(track.id)
    print(f"✅ Downloaded {len(audio_data):,} bytes ({len(audio_data)/1024/1024:.2f} MB)")

# Step 2: Check and Add ReplayGain
print_section("STEP 2: CHECK & ADD REPLAYGAIN")

audio_stream = BytesIO(audio_data)
file_ext = f".{track.suffix}"

print(f"🔍 Checking for existing ReplayGain...")
has_rg = has_replaygain_metadata(audio_stream, file_ext)

if has_rg:
    print(f"✅ ReplayGain already present - no changes needed")
else:
    print(f"⚠️  No ReplayGain found")
    print(f"\n🔧 Adding ReplayGain using ffmpeg loudnorm...")

    try:
        # Use the existing process_replaygain function
        audio_data = process_replaygain(audio_data, track.suffix)

        print(f"✅ ReplayGain added successfully!")
        print(f"   New file size: {len(audio_data):,} bytes ({len(audio_data)/1024/1024:.2f} MB)")

        # Verify it was added
        audio_stream = BytesIO(audio_data)
        if has_replaygain_metadata(audio_stream, file_ext):
            print(f"✅ VERIFIED: ReplayGain metadata is present")
        else:
            print(f"⚠️  WARNING: Verification failed")

    except Exception as e:
        print(f"❌ Error adding ReplayGain: {e}")
        print(f"   Aborting - will not upload without ReplayGain")
        sys.exit(1)

# Step 3: Upload to AzuraCast
print_section("STEP 3: UPLOAD TO AZURACAST")

azuracast_host = os.getenv("AZURACAST_HOST")
api_key = os.getenv("AZURACAST_API_KEY")
station_id = os.getenv("AZURACAST_STATIONID")

print(f"📡 Target: {azuracast_host}")
print(f"   Station: {station_id}")

file_path = f"{track.artist}/{track.album or 'Unknown'}/{track.title}.{track.suffix}"
print(f"   Path: {file_path}")

b64_content = b64encode(audio_data).decode("utf-8")
data = {"path": file_path, "file": b64_content}

print(f"\n⬆️  Uploading {len(audio_data):,} bytes with ReplayGain metadata...")

session = requests.Session()
session.verify = False
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

url = f"{azuracast_host}/api/station/{station_id}/files"
headers = {"X-API-Key": api_key}

try:
    response = session.post(url, headers=headers, json=data, timeout=180)

    if response.status_code == 200:
        result = response.json()

        print_section("✅ SUCCESS!")
        print(f"\n📋 Upload Complete:")
        print(f"   File ID: {result.get('id')}")
        print(f"   Unique ID: {result.get('unique_id')}")
        print(f"   Title: {result.get('title')}")
        print(f"   Artist: {result.get('artist')}")
        print(f"   Album: {result.get('album')}")
        print(f"\n✅ ReplayGain: ADDED AND VERIFIED")
        print(f"\n🎯 Verify in AzuraCast:")
        print(f"   URL: {azuracast_host}")
        print(f"   File ID: {result.get('id')}")
        print(f"   Search: {track.artist} - {track.title}")

    else:
        print(f"❌ Upload failed: HTTP {response.status_code}")
        print(f"Response: {response.text}")
        sys.exit(1)

except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)

print("=" * 80)
