# src/replaygain/main.py

import io
import os
import tempfile
import subprocess
from pydub import AudioSegment
from mutagen import File as MutagenFile
from mutagen.id3 import ID3, TXXX
from mutagen.flac import FLAC
from io import BytesIO
from typing import Tuple
from tqdm import tqdm

def calculate_replaygain(file_path: str) -> Tuple[float, float]:
    """Calculate ReplayGain values for an audio file using ffmpeg.

    Args:
        file_path: Path to the audio file.

    Returns:
        A tuple containing the gain (in dB) and peak values.
    """
    command = [
        "ffmpeg",
        "-i", file_path,
        "-af", "replaygain",
        "-f", "null", "-"
    ]

    result = subprocess.run(command, stderr=subprocess.PIPE, text=True)
    output = result.stderr

    gain = None
    peak = None

    for line in output.split("\n"):
        if "track gain" in line.lower():
            gain = float([s for s in line.split() if s.replace('.', '', 1).isdigit()][-1])
        elif "track peak" in line.lower():
            peak = float([s for s in line.split() if s.replace('.', '', 1).isdigit()][-1])

    if gain is None or peak is None:
        raise RuntimeError("ReplayGain calculation failed or could not be parsed.")

    return gain, peak

def apply_replaygain(file_path: str, gain: float, peak: float) -> None:
    """Apply ReplayGain metadata to an audio file.

    Args:
        file_path: The path to the audio file.
        gain: The ReplayGain track gain value in dB.
        peak: The ReplayGain track peak value.
    """
    audio_file = MutagenFile(file_path, easy=True)
    if audio_file is None:
        raise RuntimeError("Failed to load audio file with mutagen.")

    # Add ReplayGain metadata
    if file_path.lower().endswith(".mp3"):
        if not isinstance(audio_file, ID3):
            audio_file.add_tags()
        audio_file.tags.add(TXXX(encoding=3, desc="replaygain_track_gain", text=str(gain)))
        audio_file.tags.add(TXXX(encoding=3, desc="replaygain_track_peak", text=str(peak)))
    elif file_path.lower().endswith(".flac"):
        audio_file = FLAC(file_path)
        audio_file["replaygain_track_gain"] = str(gain)
        audio_file["replaygain_track_peak"] = str(peak)
    else:
        raise NotImplementedError(f"ReplayGain application for {file_path} not implemented.")

    audio_file.save()

def process_replaygain(file_content: bytes, file_format: str) -> bytes:
    """Process ReplayGain for a given audio file content.

    Args:
        file_content: The binary content of the audio file.
        file_format: The format of the audio file.

    Returns:
        bytes: The binary content of the audio file with ReplayGain metadata.
    """
    with tqdm(total=100, desc="Analysing replaygain metadata", unit="%") as pbar:
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_format}") as temp_audio_file:
            temp_audio_file.write(file_content)
            temp_audio_path = temp_audio_file.name
            
        pbar.update(25)

        gain, peak = calculate_replaygain(temp_audio_path)
        apply_replaygain(temp_audio_path, gain, peak)
        
        pbar.update(75)

        with open(temp_audio_path, "rb") as f:
            updated_content = f.read()
            
        pbar.update(95)

        os.remove(temp_audio_path)  # Clean up temporary file
        pbar.update(100)

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

    if isinstance(audio_file, ID3):
        return any(tag in audio_file for tag in ["TXXX:replaygain_track_gain", "TXXX:replaygain_track_peak"])
    elif isinstance(audio_file, FLAC):
        return any(tag in audio_file for tag in ["replaygain_track_gain", "replaygain_track_peak"])

    return False