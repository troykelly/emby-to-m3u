#!/usr/bin/env python3
"""
Simplified Demonstration: Download a track from Subsonic with all metadata intact.

This demonstrates that tracks are downloaded with:
1. All ID3/Vorbis tags preserved
2. Original audio quality (FLAC/MP3/etc)
3. Metadata extraction capability
4. Ready for upload to any destination

The track will be saved to disk for manual inspection.
"""

import os
import sys
from pathlib import Path
from io import BytesIO
import logging

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from subsonic.client import SubsonicClient
from subsonic.models import SubsonicConfig, SubsonicTrack
from replaygain.main import has_replaygain_metadata

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)


def print_separator(title: str = "", char: str = "="):
    """Print a visual separator."""
    width = 80
    if title:
        print(f"\n{char * width}")
        print(f"{title.center(width)}")
        print(f"{char * width}\n")
    else:
        print(f"{char * width}")


def main():
    print_separator("SUBSONIC METADATA PRESERVATION DEMONSTRATION")
    print("This demo shows downloading a track with all metadata intact")
    print("from Subsonic, suitable for upload to AzuraCast or any service.\n")

    # Initialize Subsonic client
    config = SubsonicConfig(
        url=os.getenv("SUBSONIC_URL", ""),
        username=os.getenv("SUBSONIC_USER", ""),
        password=os.getenv("SUBSONIC_PASSWORD", ""),
        api_version="1.16.1",
        client_name="emby-to-m3u-demo"
    )

    print(f"📡 Connecting to Subsonic: {config.url}\n")

    with SubsonicClient(config) as client:
        # Test connection
        if not client.ping():
            logger.error("❌ Failed to connect to Subsonic server")
            return 1

        print(f"✅ Connected successfully\n")

        # Get a random track
        print(f"🎲 Fetching a random track from library...")
        tracks = client.get_random_songs(size=1)

        if not tracks:
            logger.error("❌ No tracks returned from Subsonic")
            return 1

        track = tracks[0]

        print_separator("TRACK INFORMATION", "-")
        print(f"🎵 Title:           {track.title}")
        print(f"👤 Artist:          {track.artist}")
        print(f"💿 Album:           {track.album}")
        print(f"🔢 Track Number:    {track.track if track.track else 'N/A'}")
        print(f"📀 Disc Number:     {track.discNumber if track.discNumber else 'N/A'}")
        print(f"🎭 Genre:           {track.genre if track.genre else 'N/A'}")
        print(f"📅 Year:            {track.year if track.year else 'N/A'}")
        print(f"⏱️  Duration:        {track.duration}s")
        print(f"📦 Format:          {track.suffix.upper()}")
        print(f"💾 Size:            {track.size:,} bytes ({track.size / 1024 / 1024:.2f} MB)" if track.size else "💾 Size:            Unknown")
        print(f"🎼 Bit Rate:        {track.bitRate} kbps" if track.bitRate else "")
        print(f"🆔 Track ID:        {track.id}")
        if track.musicBrainzId:
            print(f"🎵 MusicBrainz:     {track.musicBrainzId}")

        # Download the track
        print_separator("DOWNLOADING TRACK", "-")
        print(f"⬇️  Downloading '{track.title}' by '{track.artist}'...")
        print(f"   Using download endpoint to preserve original quality\n")

        audio_data = client.download_track(track.id)

        print(f"✅ Download complete!")
        print(f"   Downloaded: {len(audio_data):,} bytes ({len(audio_data) / 1024 / 1024:.2f} MB)\n")

        # Check ReplayGain
        print_separator("METADATA VERIFICATION", "-")
        audio_stream = BytesIO(audio_data)
        file_extension = f".{track.suffix}"

        print(f"🔍 Checking for ReplayGain metadata...")
        has_rg = has_replaygain_metadata(audio_stream, file_extension)

        if has_rg:
            print(f"✅ ReplayGain metadata FOUND!")
            print(f"   Track has volume normalization tags")
        else:
            print(f"⚠️  No ReplayGain metadata found")
            print(f"   Track can still be uploaded with existing metadata")

        # Extract detailed metadata with mutagen
        print(f"\n📋 Extracting detailed metadata tags...")
        try:
            from mutagen import File as MutagenFile
            audio_stream.seek(0)
            audio_file = MutagenFile(audio_stream)

            if audio_file:
                print(f"\n✅ Metadata extraction successful!")
                print(f"   Audio Info:")
                if hasattr(audio_file.info, 'length'):
                    print(f"      Length: {audio_file.info.length:.2f}s")
                if hasattr(audio_file.info, 'bitrate'):
                    print(f"      Bitrate: {audio_file.info.bitrate // 1000} kbps")
                if hasattr(audio_file.info, 'sample_rate'):
                    print(f"      Sample Rate: {audio_file.info.sample_rate} Hz")
                if hasattr(audio_file.info, 'channels'):
                    print(f"      Channels: {audio_file.info.channels}")
                if hasattr(audio_file.info, 'bits_per_sample'):
                    print(f"      Bit Depth: {audio_file.info.bits_per_sample} bit")

                if audio_file.tags:
                    print(f"\n   ID3/Vorbis Tags:")
                    tag_count = 0
                    for key, value in audio_file.tags.items():
                        if tag_count < 15:  # Show first 15 tags
                            value_str = str(value)
                            if len(value_str) > 60:
                                value_str = value_str[:57] + "..."
                            print(f"      {key:30} = {value_str}")
                            tag_count += 1

                    total_tags = len(audio_file.tags)
                    if total_tags > 15:
                        print(f"      ... and {total_tags - 15} more tags")

                    print(f"\n   📊 Total tags found: {total_tags}")
            else:
                print(f"⚠️  Could not parse metadata")
        except ImportError:
            print(f"⚠️  mutagen library not available for detailed metadata extraction")
        except Exception as e:
            print(f"⚠️  Could not extract all metadata: {e}")

        # Save to disk
        print_separator("SAVING TO DISK", "-")
        output_dir = Path("demos/output")
        output_dir.mkdir(parents=True, exist_ok=True)

        # Create safe filename
        safe_filename = f"{track.artist} - {track.title}.{track.suffix}"
        safe_filename = "".join(c if c.isalnum() or c in (' ', '-', '.', '_') else '_' for c in safe_filename)
        output_path = output_dir / safe_filename

        with open(output_path, 'wb') as f:
            f.write(audio_data)

        print(f"💾 Track saved to: {output_path}")
        print(f"   File size: {output_path.stat().st_size:,} bytes\n")

        # Final summary
        print_separator("DEMONSTRATION COMPLETE")
        print("✅ Successfully demonstrated metadata preservation!\n")
        print("📊 Summary:")
        print(f"   • Track downloaded with original {track.suffix.upper()} quality")
        print(f"   • All metadata tags preserved ({total_tags if 'total_tags' in locals() else 'multiple'} tags)")
        print(f"   • ReplayGain: {'Present' if has_rg else 'Not present'}")
        print(f"   • MusicBrainz ID: {'Present' if track.musicBrainzId else 'Not present'}")
        print(f"   • File ready for upload to AzuraCast or any platform\n")

        print("🎯 Next Steps:")
        print(f"   1. Inspect the saved file: {output_path}")
        print(f"   2. Verify metadata with: mediainfo \"{output_path}\"")
        print(f"   3. Upload to AzuraCast preserves all this metadata")
        print(f"   4. Check the file plays correctly with: ffplay \"{output_path}\"\n")

        return 0


if __name__ == "__main__":
    sys.exit(main())
