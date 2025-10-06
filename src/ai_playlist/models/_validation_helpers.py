"""
Shared validation helpers for models.

This module contains common validation functions used across multiple model classes.
"""

import re


def validate_playlist_name(name: str) -> None:
    """
    Validate playlist name matches schema: {Day}_{ShowName}_{StartTime}_{EndTime}.

    Args:
        name: Playlist name to validate

    Raises:
        ValueError: If name doesn't match expected schema
    """
    name_pattern = re.compile(
        r"^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)_" r"[A-Za-z0-9]+_\d{4}_\d{4}$"
    )
    if not name_pattern.match(name):
        raise ValueError("Name must match schema: {Day}_{ShowName}_{StartTime}_{EndTime}")
