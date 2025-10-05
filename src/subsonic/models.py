"""Data models for Subsonic API integration."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


@dataclass
class SubsonicConfig:
    """Configuration for connecting to a Subsonic-compatible server.

    Attributes:
        url: Base server URL (e.g., "https://music.example.com")
        username: Subsonic username
        password: Subsonic password (hashed before transmission)
        api_key: Optional API key for OpenSubsonic servers (alternative to password)
        client_name: Client identifier for API requests
        api_version: Subsonic API version
    """

    url: str
    username: str
    password: Optional[str] = None
    api_key: Optional[str] = None
    client_name: str = "playlistgen"
    api_version: str = "1.16.1"

    def __post_init__(self):
        """Validate configuration on initialization."""
        if not self.url or not self.url.startswith(("http://", "https://")):
            raise ValueError("url must be a valid HTTP/HTTPS URL")
        if not self.username:
            raise ValueError("username is required")

        # Either password or API key must be provided
        if not self.password and not self.api_key:
            raise ValueError("Either password or api_key must be provided")

        # Warn about insecure HTTP connections
        if not self.url.startswith('https://'):
            import warnings
            warnings.warn(
                "Using HTTP instead of HTTPS for Subsonic connection. "
                "Credentials will be transmitted insecurely.",
                UserWarning,
                stacklevel=2
            )


@dataclass
class SubsonicAuthToken:
    """Authentication token for Subsonic API using MD5 salt+hash method.

    Attributes:
        token: MD5(password + salt)
        salt: Random salt string
        username: Username for this token
        created_at: Token creation timestamp
        expires_at: Optional expiry timestamp
    """

    token: str
    salt: str
    username: str
    created_at: datetime
    expires_at: Optional[datetime] = None

    def is_expired(self) -> bool:
        """Check if token has expired.

        Returns:
            True if expired, False otherwise
        """
        if self.expires_at is None:
            return False  # No expiry set
        return datetime.now(timezone.utc) > self.expires_at

    def to_auth_params(self) -> dict:
        """Convert to authentication query parameters.

        Returns:
            Dict with u (username), t (token), s (salt)
        """
        return {"u": self.username, "t": self.token, "s": self.salt}


@dataclass
class SubsonicTrack:
    """Raw track metadata from Subsonic API response.

    Attributes:
        id: Unique track identifier
        title: Track title
        artist: Artist name
        album: Album name
        duration: Duration in seconds
        path: File path on server
        suffix: File extension
        created: Creation timestamp (ISO format)
        parent: Parent directory/album ID for navigation (optional)
        albumId: Album ID for ID3 navigation (optional)
        artistId: Artist ID for ID3 navigation (optional)
        isDir: Distinguish directories from files (default: False)
        isVideo: Filter video content (default: False)
        type: Content type - "music", "podcast", "audiobook" (optional)
        genre: Genre (optional)
        track: Track number (optional)
        discNumber: Disc number (optional)
        year: Release year (optional)
        musicBrainzId: MusicBrainz track ID (optional)
        coverArt: Cover art ID (optional)
        size: File size in bytes (optional)
        bitRate: Bitrate in kbps (optional)
        contentType: MIME type (optional)
    """

    # Required fields
    id: str
    title: str
    artist: str
    album: str
    duration: int
    path: str
    suffix: str
    created: str

    # NEW: Critical fields for ID3 browsing (P0)
    parent: Optional[str] = None       # Parent directory/album ID for navigation
    albumId: Optional[str] = None      # Album ID for ID3 navigation
    artistId: Optional[str] = None     # Artist ID for ID3 navigation

    # NEW: Type discrimination (P0)
    isDir: bool = False                # Distinguish directories from files
    isVideo: bool = False              # Filter video content
    type: Optional[str] = None         # "music", "podcast", "audiobook"

    # Optional fields
    genre: Optional[str] = None
    track: Optional[int] = None
    discNumber: Optional[int] = None
    year: Optional[int] = None
    musicBrainzId: Optional[str] = None
    coverArt: Optional[str] = None
    size: Optional[int] = None
    bitRate: Optional[int] = None
    contentType: Optional[str] = None


@dataclass
class SubsonicArtist:
    """Artist metadata from getArtist/getArtists.

    Attributes:
        id: Unique artist identifier
        name: Artist name
        albumCount: Number of albums by this artist
        coverArt: Cover art ID (optional)
        artistImageUrl: Artist image URL (optional)
        starred: ISO datetime if favorited (optional)
    """

    id: str
    name: str
    albumCount: int
    coverArt: Optional[str] = None
    artistImageUrl: Optional[str] = None
    starred: Optional[str] = None


@dataclass
class SubsonicAlbum:
    """Album metadata from getAlbum.

    Attributes:
        id: Unique album identifier
        name: Album name
        artist: Artist name
        artistId: Artist ID
        songCount: Number of songs in album
        duration: Total duration in seconds
        created: Creation timestamp (ISO format)
        coverArt: Cover art ID (optional)
        playCount: Play count (optional)
        year: Release year (optional)
        genre: Genre (optional)
        starred: ISO datetime if favorited (optional)
    """

    id: str
    name: str
    artist: str
    artistId: str
    songCount: int
    duration: int
    created: str
    coverArt: Optional[str] = None
    playCount: Optional[int] = None
    year: Optional[int] = None
    genre: Optional[str] = None
    starred: Optional[str] = None
