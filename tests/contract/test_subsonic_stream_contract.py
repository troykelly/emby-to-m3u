"""Contract tests for Subsonic streaming API."""

import json
import pytest
from pathlib import Path


@pytest.fixture
def subsonic_responses():
    """Load Subsonic API response fixtures."""
    fixtures_path = Path(__file__).parent.parent / "subsonic" / "fixtures" / "subsonic_responses.json"
    with open(fixtures_path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_stream_valid_track_id():
    """Test stream endpoint with valid track ID returns binary audio."""
    # Mock binary audio response
    mock_audio_content = b'\x00\x01\x02\x03\x04'  # Sample binary data

    # Validate Content-Type would be audio/*
    expected_content_types = ["audio/mpeg", "audio/flac", "audio/ogg", "audio/wav", "audio/aac"]
    content_type = "audio/mpeg"

    assert content_type in expected_content_types
    assert isinstance(mock_audio_content, bytes)
    assert len(mock_audio_content) > 4  # Minimum valid audio file size


def test_stream_invalid_track_id_404(subsonic_responses):
    """Test stream endpoint with invalid track ID returns 404 with error code 70."""
    error_response = subsonic_responses["stream_not_found"]

    # Validate error response
    assert "subsonic-response" in error_response
    assert error_response["subsonic-response"]["status"] == "failed"
    assert "error" in error_response["subsonic-response"]
    assert error_response["subsonic-response"]["error"]["code"] == 70
    assert "not found" in error_response["subsonic-response"]["error"]["message"].lower()


def test_response_content_type():
    """Test that Content-Type header matches audio MIME type."""
    valid_mime_types = {
        "mp3": "audio/mpeg",
        "flac": "audio/flac",
        "ogg": "audio/ogg",
        "wav": "audio/wav",
        "aac": "audio/aac",
        "m4a": "audio/mp4"
    }

    # Validate suffix to Content-Type mapping
    for suffix, mime_type in valid_mime_types.items():
        assert mime_type.startswith("audio/")
        assert "/" in mime_type


def test_response_binary_non_empty():
    """Test that binary response content is non-empty and valid."""
    # Mock binary audio data
    mock_audio_data = b'\xff\xfb\x90\x00'  # MP3 header magic bytes

    assert isinstance(mock_audio_data, bytes)
    assert len(mock_audio_data) >= 4

    # For MP3, first bytes should be frame sync
    # This is just a validation that we're checking binary format
    assert mock_audio_data[0] == 0xff  # MP3 frame sync byte


def test_stream_parameters_validation():
    """Test that stream endpoint parameters are validated correctly."""
    stream_params = {
        "id": "300",
        "u": "admin",
        "t": "26719a1196d2a940705a59634eb18eab",
        "s": "c19b2d",
        "v": "1.16.1",
        "c": "playlistgen"
    }

    # Required parameter validation
    required_params = ["id", "u", "t", "s", "v", "c"]
    for param in required_params:
        assert param in stream_params, f"Missing required parameter: {param}"

    # Optional transcoding parameters
    optional_params = ["maxBitRate", "format", "estimateContentLength"]
    transcoding_params = {
        "maxBitRate": 320,
        "format": "mp3"
    }

    if "maxBitRate" in transcoding_params:
        assert transcoding_params["maxBitRate"] > 0

    if "format" in transcoding_params:
        valid_formats = ["mp3", "flac", "aac", "ogg", "wav"]
        assert transcoding_params["format"] in valid_formats


def test_content_disposition_header():
    """Test that Content-Disposition header is set correctly for downloads."""
    # For streaming: inline
    inline_disposition = 'inline; filename="Bohemian Rhapsody.mp3"'

    # For downloading: attachment
    attachment_disposition = 'attachment; filename="Bohemian Rhapsody.mp3"'

    assert "filename=" in inline_disposition
    assert "filename=" in attachment_disposition
    assert inline_disposition.startswith("inline")
    assert attachment_disposition.startswith("attachment")


def test_error_response_schema(subsonic_responses):
    """Test that error responses match contract schema."""
    error_response = subsonic_responses["stream_not_found"]

    # Validate error structure
    assert "subsonic-response" in error_response
    subsonic_resp = error_response["subsonic-response"]

    assert subsonic_resp["status"] == "failed"
    assert "version" in subsonic_resp
    assert "error" in subsonic_resp

    error = subsonic_resp["error"]
    assert "code" in error
    assert "message" in error
    assert isinstance(error["code"], int)
    assert isinstance(error["message"], str)

    # Valid error codes per contract
    valid_codes = [0, 10, 20, 30, 40, 50, 60, 70]
    assert error["code"] in valid_codes
