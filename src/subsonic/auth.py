"""Subsonic API authentication implementation.

This module implements token-based authentication for Subsonic-compatible APIs
using MD5 salt+hash method as specified in the Subsonic API documentation.

Authentication Flow:
    1. Generate cryptographically secure random salt (16 hex characters)
    2. Concatenate password + salt
    3. Calculate MD5 hash of concatenated string
    4. Return token (MD5 hash), salt, and username

Example:
    >>> from subsonic.models import SubsonicConfig
    >>> from subsonic.auth import generate_token
    >>>
    >>> config = SubsonicConfig(
    ...     url="https://music.example.com",
    ...     username="admin",
    ...     password="sesame"
    ... )
    >>> auth_token = generate_token(config)
    >>> print(auth_token.to_auth_params())
    {'u': 'admin', 't': '26719a...', 's': 'c19b2d...'}

Security Notes:
    - Never transmit plaintext passwords over the network
    - Salt is regenerated for each authentication to prevent replay attacks
    - MD5 is used per Subsonic spec (not for cryptographic security, but obfuscation)
    - Tokens should be regenerated periodically for security
"""

import hashlib
import secrets
from datetime import datetime, timezone
from typing import Optional

from .models import SubsonicAuthToken, SubsonicConfig


def generate_token(
    config: SubsonicConfig, salt: Optional[str] = None
) -> Optional[SubsonicAuthToken]:
    """Generate Subsonic authentication token using MD5 salt+hash method.

    This function implements the Subsonic API authentication specification:
    - Generates a random 16-character hexadecimal salt (if not provided)
    - Computes token as MD5(password + salt)
    - Returns SubsonicAuthToken with username, token, salt, and timestamp
    - Returns None if using API key authentication (OpenSubsonic)

    The token can be used in API requests via query parameters:
        u={username}&t={token}&s={salt}&v={api_version}&c={client_name}

    Args:
        config: Subsonic configuration containing username and password or API key
        salt: Optional pre-generated salt (16 hex chars). If None, generates new salt.
              Primarily for testing purposes - production should use auto-generated salt.

    Returns:
        SubsonicAuthToken containing:
            - token: MD5 hash (32 hex chars, lowercase)
            - salt: Random salt string (16 hex chars)
            - username: Username from config
            - created_at: UTC timestamp when token was created
            - expires_at: None (tokens don't expire by default)
        Or None if using API key authentication (OpenSubsonic)

    Raises:
        ValueError: If config is invalid (handled by SubsonicConfig validation)

    Example:
        >>> config = SubsonicConfig(
        ...     url="https://music.example.com",
        ...     username="admin",
        ...     password="sesame"
        ... )
        >>> token = generate_token(config)
        >>> print(f"Token: {token.token}")
        Token: 26719a1196d2a940705a59634eb18eab
        >>> print(f"Salt: {token.salt}")
        Salt: c19b2d4e8f1a3b5d
        >>> params = token.to_auth_params()
        >>> print(params)
        {'u': 'admin', 't': '26719a...', 's': 'c19b2d...'}

    Notes:
        - Salt is 16 hexadecimal characters (8 bytes from secrets.token_hex)
        - Token is 32 hexadecimal characters (MD5 hash output)
        - Each call with salt=None generates a unique token (different salt)
        - Tokens should be regenerated per-request for maximum security
        - Returns None if using API key authentication (config.api_key is set)
    """
    # If using API key authentication (OpenSubsonic), no token needed
    if config.api_key:
        return None

    # Generate cryptographically secure random salt if not provided
    # Using secrets.token_hex(8) produces 16 hex characters (8 bytes * 2 hex/byte)
    if salt is None:
        salt = secrets.token_hex(8)

    # Subsonic token algorithm: MD5(password + salt)
    # Concatenate password and salt as per Subsonic API specification
    token_input = f"{config.password}{salt}"

    # Calculate MD5 hash and get hexadecimal digest (32 lowercase hex chars)
    token = hashlib.md5(token_input.encode("utf-8")).hexdigest()

    # Create authentication token object with current UTC timestamp
    return SubsonicAuthToken(
        token=token,
        salt=salt,
        username=config.username,
        created_at=datetime.now(timezone.utc),
        expires_at=None,  # Tokens don't expire by default
    )


def verify_token(config: SubsonicConfig, token: str, salt: str) -> bool:
    """Verify that a token matches the expected MD5(password + salt).

    This is primarily used for testing and validation. In production,
    the server verifies tokens, not the client.

    Args:
        config: Subsonic configuration with password
        token: Token to verify (32 hex chars)
        salt: Salt used to generate token (16 hex chars)

    Returns:
        True if token matches MD5(password + salt), False otherwise

    Example:
        >>> config = SubsonicConfig(
        ...     url="https://music.example.com",
        ...     username="admin",
        ...     password="sesame"
        ... )
        >>> auth = generate_token(config, salt="c19b2d")
        >>> verify_token(config, auth.token, auth.salt)
        True
        >>> verify_token(config, "invalid", auth.salt)
        False
    """
    expected_token = hashlib.md5(f"{config.password}{salt}".encode("utf-8")).hexdigest()
    return token == expected_token


def create_auth_params(
    auth_token: SubsonicAuthToken,
    api_version: str = "1.16.1",
    client_name: str = "playlistgen",
    response_format: str = "json",
) -> dict:
    """Create complete authentication query parameters for Subsonic API requests.

    Combines authentication token with API metadata to create the full set of
    query parameters required by the Subsonic API specification.

    Args:
        auth_token: Authentication token from generate_token()
        api_version: Subsonic API version (default: "1.16.1")
        client_name: Client application identifier (default: "playlistgen")
        response_format: Response format - "json" or "xml" (default: "json")

    Returns:
        Dictionary of query parameters containing:
            - u: username
            - t: authentication token
            - s: salt
            - v: API version
            - c: client name
            - f: response format

    Example:
        >>> config = SubsonicConfig(
        ...     url="https://music.example.com",
        ...     username="admin",
        ...     password="sesame"
        ... )
        >>> token = generate_token(config)
        >>> params = create_auth_params(token)
        >>> print(params)
        {'u': 'admin', 't': '26719a...', 's': 'c19b2d...',
         'v': '1.16.1', 'c': 'playlistgen', 'f': 'json'}

    Notes:
        - All parameters are required by Subsonic API specification
        - Response format must be "json" or "xml"
        - Client name helps server identify application for logging
    """
    return {
        **auth_token.to_auth_params(),
        "v": api_version,
        "c": client_name,
        "f": response_format,
    }
