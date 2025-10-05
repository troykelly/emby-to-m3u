"""Subsonic API client module for music library access."""

__version__ = "1.0.0"

from .auth import create_auth_params, generate_token, verify_token
from .client import SubsonicClient
from .exceptions import (
    ClientVersionTooOldError,
    ServerVersionTooOldError,
    SubsonicAuthenticationError,
    SubsonicAuthorizationError,
    SubsonicError,
    SubsonicNotFoundError,
    SubsonicParameterError,
    SubsonicTrialError,
    SubsonicVersionError,
    TokenAuthenticationNotSupportedError,
)
from .models import (
    SubsonicAlbum,
    SubsonicArtist,
    SubsonicAuthToken,
    SubsonicConfig,
    SubsonicTrack,
)

__all__ = [
    # Client
    "SubsonicClient",
    # Models
    "SubsonicConfig",
    "SubsonicAuthToken",
    "SubsonicTrack",
    "SubsonicArtist",
    "SubsonicAlbum",
    # Authentication
    "generate_token",
    "verify_token",
    "create_auth_params",
    # Exceptions
    "SubsonicError",
    "SubsonicAuthenticationError",
    "TokenAuthenticationNotSupportedError",
    "ClientVersionTooOldError",
    "ServerVersionTooOldError",
    "SubsonicAuthorizationError",
    "SubsonicNotFoundError",
    "SubsonicParameterError",
    "SubsonicTrialError",
    "SubsonicVersionError",
]
