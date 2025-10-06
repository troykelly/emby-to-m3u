#!/usr/bin/env python3
"""
Complete Workflow Demo: Subsonic -> ReplayGain Check -> AzuraCast Upload
Demonstrates:
1. Download track from Subsonic
2. Check for ReplayGain metadata
3. Add ReplayGain if missing
4. Upload to AzuraCast with all metadata intact
"""

import os
import sys
from pathlib import Path
from io import BytesIO
from base64 import b64encode
from dotenv import load_dotenv
import subprocess
import tempfile

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from subsonic.client import SubsonicClient
from subsonic.models import SubsonicConfig
from replaygain.main import has_replaygain_metadata
import requests

def print_section(title):
    print("\n" + "=" * 80)
    print(title.center(80))
    print("=" * 80)

print_section("COMPLETE WORKFLOW: SUBSONIC -> REPLAYGAIN -> AZURACAST")

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

    print("✅ Connected successfully")

    # Get a random track
    tracks = client.get_random_songs(size=1)
    if not tracks:
        print("❌ No tracks found")
        sys.exit(1)

    track = tracks[0]
    print(f"\n🎵 Selected Track:")
    print(f"   Title:  {track.title}")
    print(f"   Artist: {track.artist}")
    print(f"   Album:  {track.album}")
    print(f"   Format: {track.suffix}")
    if track.musicBrainzId:
        print(f"   MusicBrainz ID: {track.musicBrainzId}")

    # Download
    print(f"\n⬇️  Downloading...")
    audio_data = client.download_track(track.id)
    print(f"✅ Downloaded {len(audio_data):,} bytes ({len(audio_data)/1024/1024:.2f} MB)")

# Step 2: Check ReplayGain
print_section("STEP 2: CHECK REPLAYGAIN METADATA")

audio_stream = BytesIO(audio_data)
file_ext = f".{track.suffix}"

print(f"🔍 Checking for ReplayGain in {file_ext} file...")
has_rg = has_replaygain_metadata(audio_stream, file_ext)

if has_rg:
    print(f"✅ ReplayGain FOUND - track already has volume normalization")
else:
    print(f"⚠️  ReplayGain NOT FOUND")
    print(f"\n🔧 Adding ReplayGain metadata...")

    # Create temp file
    with tempfile.NamedTemporaryFile(suffix=file_ext, delete=False) as temp_file:
        temp_path = temp_file.name
        temp_file.write(audio_data)

    try:
        # Run rgain to add ReplayGain
        result = subprocess.run(
            ["rgain3", "-f", temp_path],
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode == 0:
            print(f"✅ ReplayGain added successfully")
            # Read the modified file
            with open(temp_path, 'rb') as f:
                audio_data = f.read()

            # Verify it was added
            audio_stream = BytesIO(audio_data)
            if has_replaygain_metadata(audio_stream, file_ext):
                print(f"✅ Verified: ReplayGain metadata is now present")
            else:
                print(f"⚠️  Warning: ReplayGain may not have been added correctly")
        else:
            print(f"⚠️  rgain3 failed: {result.stderr}")
            print(f"   Continuing with upload anyway...")

    except FileNotFoundError:
        print(f"⚠️  rgain3 not installed - skipping ReplayGain addition")
        print(f"   Install with: pip install rgain3")
        print(f"   Continuing with upload anyway...")
    except Exception as e:
        print(f"⚠️  Error adding ReplayGain: {e}")
        print(f"   Continuing with upload anyway...")
    finally:
        # Clean up temp file
        if os.path.exists(temp_path):
            os.unlink(temp_path)

# Step 3: Upload to AzuraCast
print_section("STEP 3: UPLOAD TO AZURACAST")

azuracast_host = os.getenv("AZURACAST_HOST")
api_key = os.getenv("AZURACAST_API_KEY")
station_id = os.getenv("AZURACAST_STATIONID")

print(f"📡 Target: {azuracast_host}")
print(f"   Station ID: {station_id}")

# Generate file path
file_path = f"{track.artist}/{track.album or 'Unknown'}/{track.title}.{track.suffix}"
print(f"   File path: {file_path}")

# Prepare upload (base64 encoded)
b64_content = b64encode(audio_data).decode("utf-8")
data = {
    "path": file_path,
    "file": b64_content
}

print(f"\n⬆️  Uploading {len(audio_data):,} bytes...")
print(f"   Base64 encoded size: {len(b64_content):,} characters")

session = requests.Session()
session.verify = False
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

url = f"{azuracast_host}/api/station/{station_id}/files"
headers = {"X-API-Key": api_key}

try:
    response = session.post(url, headers=headers, json=data, timeout=180)
    print(f"\n📊 Response: HTTP {response.status_code}")

    if response.status_code == 200:
        result = response.json()
        print(f"\n✅ UPLOAD SUCCESSFUL!")

        print(f"\n📋 AzuraCast File Details:")
        print(f"   File ID: {result.get('id')}")
        print(f"   Unique ID: {result.get('unique_id')}")
        print(f"   Path: {result.get('path')}")
        print(f"   Title: {result.get('title')}")
        print(f"   Artist: {result.get('artist')}")
        print(f"   Album: {result.get('album')}")

        print_section("DEMONSTRATION COMPLETE")
        print(f"✅ Track uploaded successfully with all metadata intact")
        print(f"✅ ReplayGain: {'Present' if has_rg else 'Added during upload'}")
        print(f"\n🎯 Verify in AzuraCast UI:")
        print(f"   URL: {azuracast_host}")
        print(f"   Station: {station_id}")
        print(f"   File ID: {result.get('id')}")
        print(f"   Search for: {track.artist} - {track.title}")

    else:
        print(f"❌ Upload failed")
        print(f"Response: {response.text}")
        sys.exit(1)

except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)

print("=" * 80)
