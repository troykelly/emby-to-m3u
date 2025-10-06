#!/usr/bin/env python3
"""
Demonstration: Complete workflow of selecting, downloading, and uploading a track
from Subsonic to AzuraCast with all metadata and ReplayGain intact.

This script demonstrates:
1. Selecting a random track from Subsonic
2. Downloading the track with all metadata
3. Verifying ReplayGain and metadata preservation
4. Uploading to AzuraCast
5. Verifying the upload
"""

import os
import sys
from pathlib import Path
from io import BytesIO
import json
from typing import Dict, Any, Optional
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from subsonic.client import SubsonicClient
from subsonic.models import SubsonicConfig, SubsonicTrack
from azuracast.main import AzuraCastSync
from replaygain.main import has_replaygain_metadata

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def print_separator(title: str = ""):
    """Print a visual separator."""
    width = 80
    if title:
        print(f"\n{'=' * width}")
        print(f"{title.center(width)}")
        print(f"{'=' * width}\n")
    else:
        print(f"{'=' * width}")


def print_metadata(label: str, data: Dict[str, Any], indent: int = 0):
    """Print metadata in a formatted way."""
    indent_str = "  " * indent
    print(f"{indent_str}{label}:")
    for key, value in data.items():
        if isinstance(value, dict):
            print(f"{indent_str}  {key}:")
            for k, v in value.items():
                print(f"{indent_str}    {k}: {v}")
        elif isinstance(value, list):
            print(f"{indent_str}  {key}: [{len(value)} items]")
        else:
            print(f"{indent_str}  {key}: {value}")


def step_1_select_track() -> Optional[SubsonicTrack]:
    """Step 1: Select a random track from Subsonic."""
    print_separator("STEP 1: SELECT TRACK FROM SUBSONIC")

    # Initialize Subsonic client
    config = SubsonicConfig(
        url=os.getenv("SUBSONIC_URL", ""),
        username=os.getenv("SUBSONIC_USER", ""),
        password=os.getenv("SUBSONIC_PASSWORD", ""),
        api_version="1.16.1",
        client_name="emby-to-m3u-demo"
    )

    print(f"📡 Connecting to Subsonic server: {config.url}")

    with SubsonicClient(config) as client:
        # Test connection
        if not client.ping():
            logger.error("Failed to connect to Subsonic server")
            return None

        print(f"✅ Connected to Subsonic server")
        print(f"   OpenSubsonic: {client.opensubsonic}")
        if client.opensubsonic:
            print(f"   Version: {client.opensubsonic_version}")

        # Get a random track
        print(f"\n🎲 Fetching a random track...")
        tracks = client.get_random_songs(size=1)

        if not tracks:
            logger.error("No tracks returned from Subsonic")
            return None

        track = tracks[0]

        print(f"\n🎵 Selected Track:")
        print(f"   Title:  {track.title}")
        print(f"   Artist: {track.artist}")
        print(f"   Album:  {track.album}")
        print(f"   ID:     {track.id}")
        print(f"   Format: {track.suffix}")
        print(f"   Size:   {track.size} bytes" if track.size else "   Size:   Unknown")
        print(f"   Duration: {track.duration}s" if track.duration else "   Duration: Unknown")

        if track.musicBrainzId:
            print(f"   MusicBrainz ID: {track.musicBrainzId}")

        if track.genre:
            print(f"   Genre: {track.genre}")

        if track.year:
            print(f"   Year: {track.year}")

        return track


def step_2_download_track(client: SubsonicClient, track: SubsonicTrack) -> bytes:
    """Step 2: Download the track from Subsonic."""
    print_separator("STEP 2: DOWNLOAD TRACK WITH METADATA")

    print(f"⬇️  Downloading track '{track.title}' by '{track.artist}'...")
    print(f"   Track ID: {track.id}")
    print(f"   Using download endpoint (preserves original format)")

    # Download using the download endpoint to get original file
    audio_data = client.download_track(track.id)

    print(f"\n✅ Download complete!")
    print(f"   Downloaded: {len(audio_data)} bytes ({len(audio_data) / 1024 / 1024:.2f} MB)")
    print(f"   Format: {track.suffix}")

    return audio_data


def step_3_verify_metadata(audio_data: bytes, track: SubsonicTrack):
    """Step 3: Verify ReplayGain and metadata in downloaded file."""
    print_separator("STEP 3: VERIFY METADATA & REPLAYGAIN")

    # Create BytesIO object for metadata extraction
    audio_stream = BytesIO(audio_data)
    file_extension = f".{track.suffix}"

    print(f"🔍 Checking for ReplayGain metadata in {file_extension} file...")

    # Check ReplayGain
    has_rg = has_replaygain_metadata(audio_stream, file_extension)

    if has_rg:
        print(f"✅ ReplayGain metadata FOUND in audio file!")
        print(f"   This file has volume normalization metadata")
        print(f"   AzuraCast will preserve these tags on upload")
    else:
        print(f"⚠️  ReplayGain metadata NOT found in audio file")
        print(f"   File will be uploaded without ReplayGain tags")

    # Try to extract more metadata using mutagen if available
    try:
        from mutagen import File as MutagenFile
        audio_stream.seek(0)
        audio_file = MutagenFile(audio_stream)

        if audio_file and audio_file.tags:
            print(f"\n📋 ID3 Tags found:")
            tag_count = 0
            for key, value in audio_file.tags.items():
                if tag_count < 10:  # Limit output
                    print(f"   {key}: {value}")
                    tag_count += 1

            if tag_count == 10:
                print(f"   ... and more tags")
        else:
            print(f"\n📋 No ID3 tags available (may be AAC/ALAC format)")
    except ImportError:
        print(f"\n📋 mutagen not available for detailed tag inspection")
    except Exception as e:
        print(f"\n⚠️  Could not extract detailed tags: {e}")

    return has_rg


def step_4_upload_to_azuracast(audio_data: bytes, track: SubsonicTrack) -> Optional[str]:
    """Step 4: Upload track to AzuraCast."""
    print_separator("STEP 4: UPLOAD TO AZURACAST")

    # Initialize AzuraCast client
    azuracast = AzuraCastSync()

    print(f"📡 Connecting to AzuraCast: {azuracast.host}")
    print(f"   Station ID: {azuracast.station_id}")

    # Generate file path
    track_dict = {
        "AlbumArtist": track.artist,
        "Album": track.album,
        "Name": track.title,
        "ProductionYear": track.year or "Unknown",
        "ParentIndexNumber": track.discNumber or 1,
        "IndexNumber": track.track or 1,
        "Path": f"dummy.{track.suffix}"
    }

    file_path = azuracast.generate_file_path(track_dict)
    print(f"\n📁 Generated file path: {file_path}")

    # Check if file already exists
    print(f"\n🔍 Checking if track already exists in AzuraCast...")
    known_tracks = azuracast.get_known_tracks()
    print(f"   Found {len(known_tracks)} existing tracks in AzuraCast")

    exists = azuracast.check_file_in_azuracast(known_tracks, track_dict)

    if exists:
        file_id = track_dict.get("azuracast_file_id")
        print(f"✅ Track already exists in AzuraCast!")
        print(f"   AzuraCast File ID: {file_id}")
        return file_id

    # Upload the file
    print(f"\n⬆️  Uploading track to AzuraCast...")
    print(f"   File size: {len(audio_data)} bytes ({len(audio_data) / 1024 / 1024:.2f} MB)")

    try:
        upload_response = azuracast.upload_file_to_azuracast(audio_data, file_path)

        if upload_response and "id" in upload_response:
            file_id = upload_response["id"]
            print(f"\n✅ Upload successful!")
            print(f"   AzuraCast File ID: {file_id}")
            print(f"   Unique ID: {upload_response.get('unique_id', 'N/A')}")

            return file_id
        else:
            logger.error("Upload failed - no ID in response")
            return None
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        return None


def step_5_verify_upload(file_id: str, track: SubsonicTrack):
    """Step 5: Verify the upload in AzuraCast."""
    print_separator("STEP 5: VERIFY UPLOAD IN AZURACAST")

    azuracast = AzuraCastSync()

    print(f"🔍 Fetching uploaded file metadata from AzuraCast...")
    print(f"   File ID: {file_id}")

    try:
        # Get file details from AzuraCast
        endpoint = f"/station/{azuracast.station_id}/file/{file_id}"
        response = azuracast._perform_request("GET", endpoint)

        if response.status_code == 200:
            file_data = response.json()

            print(f"\n✅ File found in AzuraCast!")
            print(f"\n📋 AzuraCast File Metadata:")
            print(f"   Title:  {file_data.get('title', 'N/A')}")
            print(f"   Artist: {file_data.get('artist', 'N/A')}")
            print(f"   Album:  {file_data.get('album', 'N/A')}")
            print(f"   Path:   {file_data.get('path', 'N/A')}")
            print(f"   Length: {file_data.get('length', 'N/A')}s")

            # Check for custom fields (MusicBrainz, ReplayGain, etc.)
            if "custom_fields" in file_data and file_data["custom_fields"]:
                print(f"\n📌 Custom Fields:")
                for key, value in file_data["custom_fields"].items():
                    print(f"   {key}: {value}")

            # Check for ReplayGain
            rg_track = file_data.get("replaygain_track_gain")
            rg_album = file_data.get("replaygain_album_gain")

            if rg_track or rg_album:
                print(f"\n🔊 ReplayGain Values:")
                if rg_track:
                    print(f"   Track Gain: {rg_track} dB")
                if rg_album:
                    print(f"   Album Gain: {rg_album} dB")
                print(f"   ✅ ReplayGain metadata preserved!")
            else:
                print(f"\n⚠️  No ReplayGain metadata in AzuraCast file")

            # Compare with Subsonic metadata
            print(f"\n🔄 Metadata Comparison:")
            print(f"   Title Match:  {'✅' if file_data.get('title') == track.title else '❌'}")
            print(f"   Artist Match: {'✅' if file_data.get('artist') == track.artist else '❌'}")
            print(f"   Album Match:  {'✅' if file_data.get('album') == track.album else '❌'}")

            return True
        else:
            logger.error(f"Failed to fetch file metadata: HTTP {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"Failed to verify upload: {e}")
        return False


def main():
    """Run the complete demonstration."""
    print_separator("TRACK WORKFLOW DEMONSTRATION")
    print("This demo shows the complete flow from Subsonic to AzuraCast")
    print("with metadata and ReplayGain preservation.")

    # Step 1: Select track
    track = step_1_select_track()
    if not track:
        print("\n❌ Failed to select track. Exiting.")
        return 1

    # Step 2: Download track
    config = SubsonicConfig(
        url=os.getenv("SUBSONIC_URL", ""),
        username=os.getenv("SUBSONIC_USER", ""),
        password=os.getenv("SUBSONIC_PASSWORD", ""),
        api_version="1.16.1",
        client_name="emby-to-m3u-demo"
    )

    with SubsonicClient(config) as client:
        audio_data = step_2_download_track(client, track)
        if not audio_data:
            print("\n❌ Failed to download track. Exiting.")
            return 1

        # Step 3: Verify metadata
        has_rg = step_3_verify_metadata(audio_data, track)

        # Step 4: Upload to AzuraCast
        file_id = step_4_upload_to_azuracast(audio_data, track)
        if not file_id:
            print("\n❌ Failed to upload track. Exiting.")
            return 1

        # Step 5: Verify upload
        success = step_5_verify_upload(file_id, track)

        # Final summary
        print_separator("DEMONSTRATION COMPLETE")

        if success:
            print("✅ All steps completed successfully!")
            print(f"\n📊 Summary:")
            print(f"   Track: '{track.title}' by '{track.artist}'")
            print(f"   Subsonic ID: {track.id}")
            print(f"   AzuraCast ID: {file_id}")
            print(f"   ReplayGain: {'Present' if has_rg else 'Not present'}")
            print(f"\n🎯 You can now verify the upload in the AzuraCast UI:")
            print(f"   URL: {os.getenv('AZURACAST_HOST')}")
            print(f"   Station ID: {os.getenv('AZURACAST_STATIONID')}")
            print(f"   File ID: {file_id}")
            return 0
        else:
            print("❌ Verification failed. Check logs for details.")
            return 1


if __name__ == "__main__":
    sys.exit(main())
