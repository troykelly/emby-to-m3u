# src/replaygain/main.py

import subprocess
import logging
from io import BytesIO
from typing import Tuple, Optional
from mutagen import File as MutagenFile
from mutagen.id3 import ID3, TXXX, ID3NoHeaderError
from mutagen.flac import FLAC
from mutagen.oggopus import OggOpus
from tqdm import tqdm

logger = logging.getLogger(__name__)

def calculate_replaygain(file_like: BytesIO, file_format: str) -> Tuple[float, float]:
    """Calculate ReplayGain values for an audio file using ffmpeg.

    Args:
        file_like: A file-like object representing the audio content.
        file_format: The format of the audio file (e.g., 'mp3', 'flac', 'opus').

    Returns:
        A tuple containing the gain (in dB) and peak values.
    """
    command = [
        "ffmpeg",
        "-i", "pipe:0",
        "-af", "replaygain",
        "-f", "null", "-"
    ]

    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = process.communicate(input=file_like.getbuffer())

    gain = None
    peak = None

    for line in err.decode('utf-8').split('\n'):
        if "track_gain" in line:
            gain = float(line.split('=')[-1].strip().split()[0])
        elif "track_peak" in line:
            peak = float(line.split('=')[-1].strip().split()[0])

    if gain is None or peak is None:
        raise RuntimeError("ReplayGain calculation failed or could not be parsed.")

    return gain, peak

def apply_replaygain(file_like: BytesIO, gain: float, peak: float, file_format: str, r128_track_gain: Optional[int] = None, r128_album_gain: Optional[int] = None) -> bytes:
    """Apply ReplayGain metadata to an audio file.

    Args:
        file_like: A file-like object representing the audio content.
        gain: The ReplayGain track gain value in dB.
        peak: The ReplayGain track peak value.
        file_format: The format of the audio file (e.g., 'mp3', 'flac', 'opus').
        r128_track_gain: R128 track gain for Opus files.
        r128_album_gain: R128 album gain for Opus files.

    Returns:
        bytes: The updated file content with ReplayGain metadata.
    """
    file_like.seek(0)
    audio_file = MutagenFile(file_like, easy=True)

    if not audio_file:
        raise RuntimeError("Failed to load audio file with mutagen.")

    if file_format == "mp3":
        if not audio_file.tags:
            audio_file.add_tags()

        # Remove existing ReplayGain tags if they exist to prevent conflicts
        existing_gain_tags = audio_file.tags.getall("TXXX:replaygain_track_gain")
        existing_peak_tags = audio_file.tags.getall("TXXX:replaygain_track_peak")

        for tag in existing_gain_tags:
            audio_file.tags.delall(tag.FrameID)
        for tag in existing_peak_tags:
            audio_file.tags.delall(tag.FrameID)

        gain_tag = TXXX(encoding=3, desc="replaygain_track_gain", text=f"{gain:.2f} dB")
        peak_tag = TXXX(encoding=3, desc="replaygain_track_peak", text=f"{peak:.6f}")
        audio_file.tags.add(gain_tag)
        audio_file.tags.add(peak_tag)
    elif file_format == "flac":
        audio_file["replaygain_track_gain"] = f"{gain:.2f} dB"
        audio_file["replaygain_track_peak"] = f"{peak:.6f}"
    elif file_format == "opus" and r128_track_gain is not None and r128_album_gain is not None:
        audio_file["R128_TRACK_GAIN"] = str(r128_track_gain)
        audio_file["R128_ALBUM_GAIN"] = str(r128_album_gain)
    else:
        raise NotImplementedError(f"ReplayGain application for {file_format} not implemented.")

    updated_content = BytesIO()
    audio_file.save(updated_content)
    updated_content.seek(0)  # Ensure the pointer is at the start after saving
    # Log file size of updated content
    logger.debug(f"Post replaygain application file size: {len(updated_content.getvalue())} bytes")
    return updated_content.getvalue()

def process_replaygain(file_content: bytes, file_format: str) -> bytes:
    """Process ReplayGain for a given audio file content.

    Args:
        file_content: The binary content of the audio file.
        file_format: The format of the audio file.

    Returns:
        bytes: The binary content of the audio file with ReplayGain metadata.
    """
    file_like = BytesIO(file_content)

    if file_format == 'opus':
        with tqdm(total=100, desc="Analyzing replaygain metadata", unit="%") as pbar:
            pbar.update(25)

            gain, peak = calculate_replaygain(file_like, file_format)
            r128_track_gain = int((gain - 1.0) * 256)
            r128_album_gain = r128_track_gain
            
            pbar.set_description(f"Track R128 gain: {r128_track_gain}")

            pbar.update(50)

            updated_content = apply_replaygain(file_like, gain, peak, file_format, r128_track_gain, r128_album_gain)
            pbar.update(25)
    else:
        with tqdm(total=100, desc="Analyzing replaygain metadata", unit="%") as pbar:
            pbar.update(25)

            gain, peak = calculate_replaygain(file_like, file_format)
            pbar.set_description(f"Track gain: {gain}")
            pbar.update(50)

            updated_content = apply_replaygain(file_like, gain, peak, file_format)
            pbar.update(25)

    return updated_content

def has_replaygain_metadata(content: BytesIO, file_format: str) -> bool:
    """Check if the file content has ReplayGain metadata.

    Args:
        content: The binary content of the audio file.
        file_format: The format of the audio file.

    Returns:
        bool: True if ReplayGain metadata is present, False otherwise.
    """
    content.seek(0)
    audio_file = MutagenFile(content, easy=True)

    def log_replaygain_metadata(tags: dict, metadata_keys: list) -> bool:
        """Logs and checks for the presence of ReplayGain metadata.

        Args:
            tags: Audio file tags.
            metadata_keys: List of ReplayGain metadata keys.

        Returns:
            bool: True if ReplayGain metadata is found, False otherwise.
        """
        has_metadata = False
        for key in metadata_keys:
            if key in tags:
                logger.debug(f"Found ReplayGain metadata: {key} = {tags[key]}")
                has_metadata = True
        return has_metadata

    if isinstance(audio_file, ID3):
        metadata_keys = ["replaygain_track_gain", "replaygain_track_peak"]
        return log_replaygain_metadata(audio_file, metadata_keys)

    elif isinstance(audio_file, FLAC):
        metadata_keys = ["replaygain_track_gain", "replaygain_track_peak"]
        return log_replaygain_metadata(audio_file.tags, metadata_keys)

    elif isinstance(audio_file, OggOpus):
        metadata_keys = ["R128_TRACK_GAIN", "R128_ALBUM_GAIN"]
        return log_replaygain_metadata(audio_file, metadata_keys)

    return False
