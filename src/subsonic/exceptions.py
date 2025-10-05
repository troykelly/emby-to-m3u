"""Exception classes for Subsonic API client."""


class SubsonicError(Exception):
    """Base exception for all Subsonic API errors.

    Attributes:
        code: Subsonic error code
        message: Error message from server
    """

    def __init__(self, code: int, message: str):
        """Initialize Subsonic error.

        Args:
            code: Subsonic error code (0, 10, 20, 30, 40, 50, 60, 70)
            message: Human-readable error message
        """
        self.code = code
        self.message = message
        super().__init__(f"Subsonic Error {code}: {message}")


class SubsonicAuthenticationError(SubsonicError):
    """Authentication failed (error codes 40, 41).

    Raised when username/password is incorrect or token auth is not supported.
    """

    pass


class TokenAuthenticationNotSupportedError(SubsonicError):
    """Token authentication not supported (code 42)."""

    pass


class ClientVersionTooOldError(SubsonicError):
    """Client must upgrade (code 43)."""

    pass


class ServerVersionTooOldError(SubsonicError):
    """Server must upgrade (code 44)."""

    pass


class SubsonicAuthorizationError(SubsonicError):
    """User not authorized for requested action (error code 50).

    Raised when user lacks permissions for the requested resource.
    """

    pass


class SubsonicNotFoundError(SubsonicError):
    """Requested resource not found (error code 70).

    Raised when track, album, or other resource does not exist.
    """

    pass


class SubsonicVersionError(SubsonicError):
    """API version incompatibility (error codes 20, 30).

    Raised when client or server version is incompatible.
    """

    pass


class SubsonicParameterError(SubsonicError):
    """Required parameter missing (error code 10).

    Raised when a required API parameter is not provided.
    """

    pass


class SubsonicTrialError(SubsonicError):
    """Trial period expired (error code 60).

    Raised when server trial period has ended.
    """

    pass
