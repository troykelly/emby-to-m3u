# src/replaygain/main.py

import subprocess
import logging
from io import BytesIO
from typing import Tuple, Optional
from mutagen import File as MutagenFile
from mutagen.id3 import ID3, TXXX
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

def ffmpeg_process(input_bytes, cmd):
    # Start the FFmpeg process
    proc = subprocess.Popen(
        cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    # Pass the input data and get the output
    output, error = proc.communicate(input=input_bytes)
    if proc.returncode != 0:
        raise Exception("FFmpeg error: " + error.decode('utf-8'))
    return BytesIO(output)

def apply_replaygain(
    file_like: BytesIO,
    gain: float,
    peak: float,
    file_format: str,
    r128_track_gain: Optional[int] = None,
    r128_album_gain: Optional[int] = None
) -> bytes:
    """Apply ReplayGain metadata to an audio file using FFmpeg and return as BytesIO.

    This function processes an audio file provided as a BytesIO object, applies
    ReplayGain and R128 gain metadata, and returns the modified audio data as a
    BytesIO object. It uses FFmpeg for processing and ensures the integrity and
    correctness of the output.

    Args:
        file_like (BytesIO): The audio file data.
        gain (float): ReplayGain track gain to set (in dB).
        peak (float): ReplayGain track peak to set.
        file_format (str): Format of the audio file ('mp3', 'flac', 'opus', etc.).
        r128_track_gain (Optional[int]): Optional R128 track gain.
        r128_album_gain (Optional[int]): Optional R128 album gain.

    Returns:
        BytesIO: The modified audio file data as a BytesIO object.

    Raises:
        Exception: If FFmpeg processing fails.
    """
    logger.debug("Starting to apply ReplayGain and R128 gain metadata...")

    # Construct metadata command parts
    metadata_cmd = [
        '-metadata', f'replaygain_track_gain={gain} dB',
        '-metadata', f'replaygain_track_peak={peak}'
    ]

    if r128_track_gain is not None:
        metadata_cmd.extend(['-metadata', f'R128_TRACK_GAIN={r128_track_gain}'])

    if r128_album_gain is not None:
        metadata_cmd.extend(['-metadata', f'R128_ALBUM_GAIN={r128_album_gain}'])

    # Extra options for MP3 to ensure compatibility
    extra_opts = []
    if file_format.lower() == 'mp3':
        extra_opts = ['-id3v2_version', '3', '-write_id3v1', '1']

    # FFmpeg command setup
    ffmpeg_cmd = [
        'ffmpeg', '-hide_banner', '-y',
        '-i', '-',  # Input from stdin
        '-c', 'copy',  # Copy the codec settings to avoid re-encoding
        '-map_metadata', '0',  # Preserve all metadata not explicitly changed
    ] + extra_opts + metadata_cmd + [
        '-f', file_format,  # Output format
        '-'  # Output to stdout
    ]

    process = subprocess.Popen(
        ffmpeg_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    output, error = process.communicate(input=file_like.getvalue())

    if process.returncode != 0:
        logger.error(f"FFmpeg error: {error.decode()}")
        raise Exception(f"FFmpeg error: {error.decode()}")

    return output

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
        gain, peak = calculate_replaygain(file_like, file_format)
        r128_track_gain = int((gain - 1.0) * 256)
        r128_album_gain = r128_track_gain


        try:
            updated_content = apply_replaygain(file_like, gain, peak, file_format, r128_track_gain, r128_album_gain)
        except Exception as e:
            logger.error(f"Failed to apply ReplayGain metadata: {e}")
            updated_content = file_content
    else:
        gain, peak = calculate_replaygain(file_like, file_format)
        try:
            updated_content = apply_replaygain(file_like, gain, peak, file_format)
        except Exception as e:
            logger.error(f"Failed to apply ReplayGain metadata: {e}")
            updated_content = file_content

    final_size = len(updated_content)
    logger.debug(f"Final post-replaygain file size: {final_size} bytes")

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
    try:
        audio_file = MutagenFile(content, easy=True)
    except Exception as e:
        logger.error(f"Error reading file with Mutagen: {e}")
        return False

    if audio_file is None:
        logger.error("Unsupported file format or corrupted file.")
        return False

    def log_replaygain_metadata(tags, metadata_keys):
        """Logs and checks for the presence of ReplayGain metadata."""
        has_metadata = False
        for key in metadata_keys:
            if key in tags:
                logger.debug(f"Found ReplayGain metadata: {key} = {tags[key]}")
                has_metadata = True
        return has_metadata

    metadata_keys = {
        "mp3": ["replaygain_track_gain", "replaygain_track_peak"],
        "flac": ["replaygain_track_gain", "replaygain_track_peak"],
        "opus": ["R128_TRACK_GAIN", "R128_ALBUM_GAIN"]
    }.get(file_format.lower(), [])

    return log_replaygain_metadata(audio_file, metadata_keys)
