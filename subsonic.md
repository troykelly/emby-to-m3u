# Comprehensive Subsonic API Documentation for LLM Coding Agents

## Table of Contents
1. [Overview of Subsonic API](#1-overview-of-subsonic-api)
2. [Authentication](#2-authentication)
3. [Core Endpoints for Music Library Access](#3-core-endpoints-for-music-library-access)
4. [File Download/Streaming](#4-file-downloadstreaming)
5. [Practical Implementation Details](#5-practical-implementation-details)
6. [Code Examples](#6-code-examples)
7. [Important Links and References](#7-important-links-and-references)

---

## 1. Overview of Subsonic API

### What is Subsonic?

**Subsonic** is a personal media streaming server that enables users to stream their own music collections from anywhere. It's a self-hosted solution providing complete control over media with features including:
- Cross-platform support (Windows, Mac, Linux, mobile devices)
- Podcast receiver and Chromecast support
- On-the-fly transcoding and downsampling
- Comprehensive REST API for third-party development

### What is the Subsonic API?

The **Subsonic API** is an open REST API allowing anyone to build programs that interact with Subsonic servers. All Subsonic-compatible apps use this API for:
- Streaming music and video
- Browsing media collections
- Searching across libraries
- Creating and managing playlists
- Scrobbling to Last.fm and ListenBrainz
- Managing user accounts

### Version Compatibility and Navidrome Support

**Current API Version:** 1.16.1 (final version of official Subsonic API)

**Navidrome Support:**
- Implements Subsonic API v1.16.1
- Includes OpenSubsonic extensions
- Music-focused (no video support)
- Actively maintained open-source alternative

**Version Compatibility Rules:**
- Backward compatible if and only if:
  - Major version is the same
  - Client minor version ≤ server minor version
- Example: Server with API 2.2 supports clients 2.0, 2.1, 2.2, but NOT 1.x, 2.3+, or 3.x

### General Architecture and Endpoint Structure

**REST-Style Design:**
- Methods called via HTTP GET/POST requests
- Responses in XML or JSON format
- All responses UTF-8 encoded
- Conform to subsonic-rest-api.xsd schema

**Base URL Pattern:**
```
http://your-server/rest/{method}.view
```

**Example URLs:**
```
http://your-server/rest/ping.view?u=joe&p=sesame&v=1.16.1&c=myapp&f=json
http://your-server/rest/getArtists.view?u=joe&t=26719a1196d2a940705a59634eb18eab&s=c19b2d&v=1.16.1&c=myapp&f=json
```

### Two Browsing Paradigms

**1. File Structure Browsing (Legacy):**
- Follows actual file system organization
- Methods: `getIndexes`, `getMusicDirectory`, `search2`, `getAlbumList`
- Hierarchy: MusicFolder → Directory → Subdirectory → Files

**2. ID3 Tag Browsing (Recommended, API ≥1.8.0):**
- Uses metadata embedded in audio files
- Methods: `getArtists`, `getArtist`, `getAlbum`, `getSong`, `search3`, `getAlbumList2`
- Hierarchy: Artist → Album → Song
- More accurate for properly tagged libraries
- **This is the recommended approach for modern implementations**

### Core Data Models

**Artist:**
- ID, name, album count, cover art
- Represents musical artist
- Can be browsed by file structure or ID3 tags

**Album:**
- ID, name, artist, year, genre, cover art, song list
- Contains duration, song count, created/changed dates
- User ratings and play counts

**Song/Track:**
- Basic: ID, title, artist, album, track number
- Media: duration, bitRate, size, suffix, contentType
- Metadata: year, genre, cover art
- User-specific: starred, userRating, averageRating, playCount

**Playlist:**
- ID, name, comment, owner, public flag, song count, duration
- User-created or system-generated collections
- Supports sharing and add/remove operations

**MusicFolder:**
- Top-level organizational unit
- Represents physical directories containing media
- Used for multi-library support and access control

---

## 2. Authentication

### Authentication Methods Overview

The Subsonic API has evolved through three authentication methods:

1. **Legacy Password Authentication** (API ≤1.12.0) - Deprecated, insecure
2. **Token + Salt Authentication** (API ≥1.13.0) - Traditional recommended method
3. **API Key Authentication** (OpenSubsonic) - Modern, most secure

### Method 1: Token + Salt Authentication (Recommended for Subsonic API 1.13.0+)

**This is the standard authentication method you should implement.**

#### How It Works:
1. Generate a random salt (minimum 6 characters, recommended 10+)
2. Calculate token: `token = md5(password + salt)`
3. Send both `t` (token) and `s` (salt) parameters

#### Required Parameters:
- **u** (username): The username
- **t** (token): MD5 hash of password + salt
- **s** (salt): Random string (minimum 6 characters)
- **v** (version): API version (e.g., "1.16.1")
- **c** (client): Client application name
- **f** (format): Response format - "xml", "json", or "jsonp" (optional)

#### Token Calculation Example:
```
Password: sesame
Salt: c19b2d
Token: md5("sesamec19b2d") = 26719a1196d2a940705a59634eb18eab
```

#### Complete Request URL:
```
http://your-server/rest/ping.view?u=joe&t=26719a1196d2a940705a59634eb18eab&s=c19b2d&v=1.16.1&c=myapp&f=json
```

#### Salt Generation (Shell):
```bash
# Generate random salt
SALT=$(openssl rand -hex 10)

# Calculate token
PASSWORD="mypassword"
TOKEN=$(echo -n "${PASSWORD}${SALT}" | md5sum | awk '{ print $1 }')

# Make request
curl "http://server/rest/ping.view?u=username&t=${TOKEN}&s=${SALT}&v=1.16.1&c=myapp&f=json"
```

#### Important Notes:
- Generate a **new salt for every request** (don't reuse salts)
- MD5 function returns 32-byte ASCII hexadecimal (lowercase)
- Strings must be UTF-8 encoded
- **Always use HTTPS in production** - token+salt provides no real security over HTTP

### Method 2: API Key Authentication (OpenSubsonic Extension)

**Most secure method, use when available.**

#### Required Parameters:
- **apiKey**: Server-generated authentication token
- **v** (version): API version
- **c** (client): Client application name
- **f** (format): Response format (optional)

#### Example URL:
```
http://your-server/rest/ping.view?apiKey=43504ab81e2bfae1a7691fe3fc738fdf55ada2757e36f14bcf13d&v=1.16.1&c=myapp&f=json
```

#### Important:
- When using `apiKey`, do NOT provide the `u` (username) parameter
- Including both results in error 43 (Multiple conflicting authentication mechanisms)
- API keys are generated and managed by the server
- Check server support via `getOpenSubsonicExtensions` endpoint

### Method 3: Legacy Password Authentication (Not Recommended)

**Only use if connecting to old servers (API ≤1.12.0).**

#### Clear Text:
```
http://your-server/rest/ping.view?u=joe&p=sesame&v=1.12.0&c=myapp
```

#### Hex-Encoded:
```
http://your-server/rest/ping.view?u=joe&p=enc:736573616d65&v=1.12.0&c=myapp
```

**Security Warning:** Both methods send passwords in easily reversible format. Only use over HTTPS.

### Security Best Practices

1. **Always Use HTTPS**
   - Most critical security measure
   - Without HTTPS, all authentication methods send credentials in plain text
   - Use TLS 1.2 or higher

2. **Prefer API Key When Available**
   - Check for OpenSubsonic support
   - Generate unique API keys per client/device
   - Revoke keys when devices are compromised

3. **For Token + Salt:**
   - Generate truly random salts using cryptographically secure RNG
   - Use salt length of 10+ characters (20+ recommended)
   - **Never reuse salts** - generate new salt for each request
   - URL encode all parameters

4. **Server Configuration (Navidrome Example):**
   - Change default password encryption key
   - Implement rate limiting
   - Use reverse proxy authentication when possible

### Authentication Error Codes

| Code | Description |
|------|-------------|
| 40 | Wrong username or password |
| 41 | Token authentication not supported for LDAP users |
| 42 | Provided authentication mechanism not supported |
| 43 | Multiple conflicting authentication mechanisms |
| 44 | Invalid API key |

### LDAP Incompatibility

**Important:** Token-based authentication does NOT work with LDAP users (error 41). For LDAP users, you must use:
- Password-based authentication, or
- API key authentication (if supported)

---

## 3. Core Endpoints for Music Library Access

### Required Parameters for All Endpoints

Every endpoint requires these authentication and version parameters:
- **u** (username) + **t** (token) + **s** (salt), OR
- **apiKey**, OR  
- **u** + **p** (password) for legacy
- **v** (version): API version (e.g., "1.16.1")
- **c** (client): Client application name
- **f** (format): Optional - "xml", "json", or "jsonp"

### 3.1 Browsing Endpoints

#### getMusicFolders
Returns all configured top-level music folders/libraries.

**URL:** `/rest/getMusicFolders.view`  
**Since:** 1.0.0  
**Parameters:** None (only common authentication parameters)  
**Use Case:** Get list of available music libraries for filtering queries

**Response Structure:**
```json
{
  "subsonic-response": {
    "status": "ok",
    "version": "1.16.1",
    "musicFolders": {
      "musicFolder": [
        { "id": 1, "name": "Music" },
        { "id": 2, "name": "Audiobooks" }
      ]
    }
  }
}
```

#### getArtists (ID3 - Recommended)
Returns all artists organized by ID3 tags.

**URL:** `/rest/getArtists.view`  
**Since:** 1.8.0  
**Parameters:**
- **musicFolderId** (Optional): Filter to specific music folder ID

**Use Case:** Primary method for browsing artists in modern apps

**Response Structure:**
```json
{
  "subsonic-response": {
    "status": "ok",
    "version": "1.16.1",
    "artists": {
      "index": [
        {
          "name": "A",
          "artist": [
            {
              "id": "ar-1",
              "name": "ABBA",
              "albumCount": 5,
              "coverArt": "ar-1"
            }
          ]
        }
      ]
    }
  }
}
```

#### getArtist (ID3 - Recommended)
Returns artist details with list of albums.

**URL:** `/rest/getArtist.view`  
**Since:** 1.8.0  
**Parameters:**
- **id** (Required): Artist ID

**Use Case:** Artist detail page, get artist's albums

**Response Structure:**
```json
{
  "subsonic-response": {
    "status": "ok",
    "version": "1.16.1",
    "artist": {
      "id": "ar-1",
      "name": "Pink Floyd",
      "albumCount": 15,
      "coverArt": "ar-1",
      "album": [
        {
          "id": "al-1",
          "name": "Dark Side of the Moon",
          "artist": "Pink Floyd",
          "artistId": "ar-1",
          "coverArt": "al-1",
          "songCount": 10,
          "duration": 2593,
          "created": "2023-01-15T10:30:00",
          "year": 1973,
          "genre": "Progressive Rock"
        }
      ]
    }
  }
}
```

#### getAlbum (ID3 - Recommended)
Returns album details including complete track list.

**URL:** `/rest/getAlbum.view`  
**Since:** 1.8.0  
**Parameters:**
- **id** (Required): Album ID

**Use Case:** Album detail page, get album tracks for download

**Response Structure:**
```json
{
  "subsonic-response": {
    "status": "ok",
    "version": "1.16.1",
    "album": {
      "id": "al-1",
      "name": "Dark Side of the Moon",
      "artist": "Pink Floyd",
      "artistId": "ar-1",
      "coverArt": "al-1",
      "songCount": 10,
      "duration": 2593,
      "playCount": 156,
      "created": "2023-01-15T10:30:00",
      "year": 1973,
      "genre": "Progressive Rock",
      "song": [
        {
          "id": "tr-1",
          "parent": "al-1",
          "title": "Speak to Me",
          "album": "Dark Side of the Moon",
          "albumId": "al-1",
          "artist": "Pink Floyd",
          "artistId": "ar-1",
          "track": 1,
          "year": 1973,
          "genre": "Progressive Rock",
          "coverArt": "al-1",
          "size": 2841234,
          "contentType": "audio/mpeg",
          "suffix": "mp3",
          "duration": 68,
          "bitRate": 320,
          "path": "Pink Floyd/Dark Side of the Moon/01 - Speak to Me.mp3"
        }
      ]
    }
  }
}
```

**Critical Song/Track Fields for Download:**
- **id**: Unique identifier (use for download endpoint)
- **title**: Song title
- **artist**: Artist name
- **album**: Album name
- **track**: Track number
- **suffix**: File extension (mp3, flac, ogg, etc.)
- **contentType**: MIME type
- **bitRate**: Original bitrate in Kbps
- **size**: File size in bytes
- **duration**: Length in seconds
- **path**: File path (simulated in Navidrome)

#### getSong
Returns details for a specific song.

**URL:** `/rest/getSong.view`  
**Since:** 1.8.0  
**Parameters:**
- **id** (Required): Song ID

**Use Case:** Get individual track details

### 3.2 Search Endpoints

#### search3 (ID3 - Recommended)
Search for artists, albums, and songs organized by ID3 tags.

**URL:** `/rest/search3.view`  
**Since:** 1.8.0  
**Parameters:**
- **query** (Required): Search query string
- **artistCount** (Optional, Default: 20): Max artists to return
- **artistOffset** (Optional, Default: 0): Artist result offset for pagination
- **albumCount** (Optional, Default: 20): Max albums to return
- **albumOffset** (Optional, Default: 0): Album result offset
- **songCount** (Optional, Default: 20): Max songs to return
- **songOffset** (Optional, Default: 0): Song result offset
- **musicFolderId** (Optional, Since 1.12.0): Filter to specific music folder

**Use Case:** Universal search with pagination support

**Response Structure:**
```json
{
  "subsonic-response": {
    "status": "ok",
    "version": "1.16.1",
    "searchResult3": {
      "artist": [...],
      "album": [...],
      "song": [...]
    }
  }
}
```

**Note:** Navidrome does NOT support Lucene queries - only simple auto-complete queries.

### 3.3 Album List Endpoints

#### getAlbumList2 (ID3 - Recommended)
Returns album lists by various criteria organized by ID3 tags.

**URL:** `/rest/getAlbumList2.view`  
**Since:** 1.8.0  
**Parameters:**
- **type** (Required): List type
  - "random" - Random albums
  - "newest" - Newest albums
  - "highest" - Highest rated
  - "frequent" - Most frequently played
  - "recent" - Recently played
  - "alphabeticalByName" - Sorted by album name
  - "alphabeticalByArtist" - Sorted by artist name (Since 1.10.1)
  - "starred" - Starred/favorited albums (Since 1.10.1)
  - "byYear" - Albums in year range (Since 1.10.1)
  - "byGenre" - Albums in genre (Since 1.10.1)
- **size** (Optional, Default: 10, Max: 500): Number of albums
- **offset** (Optional, Default: 0): List offset for pagination
- **fromYear** (Required if type=byYear): Start year
- **toYear** (Required if type=byYear): End year
- **genre** (Required if type=byGenre): Genre name
- **musicFolderId** (Optional, Since 1.12.0): Filter to music folder

**Use Case:** Discovery features, home screen album lists

#### getRandomSongs
Returns random songs matching criteria.

**URL:** `/rest/getRandomSongs.view`  
**Since:** 1.2.0  
**Parameters:**
- **size** (Optional, Default: 10, Max: 500): Number of songs
- **genre** (Optional): Filter by genre
- **fromYear** (Optional): Min year
- **toYear** (Optional): Max year
- **musicFolderId** (Optional): Filter to music folder

**Use Case:** Radio mode, shuffle features

### 3.4 Metadata Endpoints

#### getGenres
Returns all genres in the library.

**URL:** `/rest/getGenres.view`  
**Since:** 1.9.0  
**Parameters:** None

**Response Structure:**
```json
{
  "subsonic-response": {
    "status": "ok",
    "version": "1.16.1",
    "genres": {
      "genre": [
        { "name": "Rock", "songCount": 1523, "albumCount": 156 },
        { "name": "Jazz", "songCount": 845, "albumCount": 92 }
      ]
    }
  }
}
```

#### getCoverArt
Returns cover art image for songs, albums, or artists.

**URL:** `/rest/getCoverArt.view`  
**Since:** 1.0.0  
**Parameters:**
- **id** (Required): Song, album, or artist ID
- **size** (Optional): Scale image to this size in pixels

**Response:** Binary image data (JPEG or PNG)

**Use Case:** Display album/artist artwork

**Example URLs:**
```
# Original size
http://server/rest/getCoverArt.view?u=user&t=token&s=salt&v=1.16.0&c=app&id=al-123

# Scaled to 300x300
http://server/rest/getCoverArt.view?u=user&t=token&s=salt&v=1.16.0&c=app&id=al-123&size=300
```

#### getArtistInfo2 (ID3 - Recommended)
Returns artist information from Last.fm (biography, images, similar artists).

**URL:** `/rest/getArtistInfo2.view`  
**Since:** 1.11.0  
**Parameters:**
- **id** (Required): Artist ID
- **count** (Optional, Default: 20): Max similar artists
- **includeNotPresent** (Optional, Default: false): Include similar artists not in library

**Response Fields:**
- biography, musicBrainzId, lastFmUrl
- smallImageUrl, mediumImageUrl, largeImageUrl
- Similar artists array

**Note:** Requires Last.fm API configuration on server.

#### getAlbumInfo2 (ID3 - Recommended)
Returns album information from Last.fm.

**URL:** `/rest/getAlbumInfo2.view`  
**Since:** 1.14.0  
**Parameters:**
- **id** (Required): Album ID

**Response Fields:**
- notes, musicBrainzId, lastFmUrl
- smallImageUrl, mediumImageUrl, largeImageUrl

### 3.5 Playlist Endpoints

#### getPlaylists
Returns all playlists user can access.

**URL:** `/rest/getPlaylists.view`  
**Since:** 1.0.0  
**Parameters:**
- **username** (Optional, Since 1.8.0): Get specific user's playlists (admin only)

**Response Structure:**
```json
{
  "subsonic-response": {
    "status": "ok",
    "version": "1.16.1",
    "playlists": {
      "playlist": [
        {
          "id": "pl-1",
          "name": "My Favorites",
          "comment": "Best songs",
          "owner": "admin",
          "public": false,
          "songCount": 45,
          "duration": 12458,
          "created": "2023-01-15T10:30:00",
          "changed": "2023-02-20T15:45:00",
          "coverArt": "pl-1"
        }
      ]
    }
  }
}
```

#### getPlaylist
Returns playlist with full track listing.

**URL:** `/rest/getPlaylist.view`  
**Since:** 1.0.0  
**Parameters:**
- **id** (Required): Playlist ID

**Response:** Playlist object with nested song entries

#### createPlaylist
Creates or updates a playlist.

**URL:** `/rest/createPlaylist.view`  
**Since:** 1.2.0  
**Parameters:**
- **playlistId** (Required if updating): Playlist ID
- **name** (Required if creating): Playlist name
- **songId** (Optional, Multiple allowed): Song IDs to add

**Response:** Since 1.14.0 returns the playlist, earlier versions return empty response

#### updatePlaylist
Updates playlist metadata and contents.

**URL:** `/rest/updatePlaylist.view`  
**Since:** 1.8.0  
**Parameters:**
- **playlistId** (Required): Playlist ID
- **name** (Optional): New name
- **comment** (Optional): New comment
- **public** (Optional): true/false visibility
- **songIdToAdd** (Optional, Multiple allowed): Songs to add
- **songIndexToRemove** (Optional, Multiple allowed): Song positions to remove

#### deletePlaylist
Deletes a playlist.

**URL:** `/rest/deletePlaylist.view`  
**Since:** 1.2.0  
**Parameters:**
- **id** (Required): Playlist ID

### 3.6 Library Scanning Endpoints

#### getScanStatus
Returns current media library scan status.

**URL:** `/rest/getScanStatus.view`  
**Since:** 1.15.0  
**Parameters:** None

**Response:**
```json
{
  "subsonic-response": {
    "status": "ok",
    "version": "1.16.1",
    "scanStatus": {
      "scanning": false,
      "count": 0
    }
  }
}
```

#### startScan
Initiates media library rescan.

**URL:** `/rest/startScan.view`  
**Since:** 1.15.0  
**Parameters:** None

**Use Case:** Trigger library updates after adding files

### 3.7 Favorites/Starred Endpoints

#### getStarred2 (ID3 - Recommended)
Returns starred songs, albums, and artists organized by ID3 tags.

**URL:** `/rest/getStarred2.view`  
**Since:** 1.8.0  
**Parameters:**
- **musicFolderId** (Optional, Since 1.12.0): Filter to music folder

#### star
Stars (favorites) songs, albums, or artists.

**URL:** `/rest/star.view`  
**Since:** 1.8.0  
**Parameters:**
- **id** (Optional, Multiple allowed): File/folder IDs to star
- **albumId** (Optional, Multiple allowed): Album IDs (ID3)
- **artistId** (Optional, Multiple allowed): Artist IDs (ID3)

#### unstar
Unstars items.

**URL:** `/rest/unstar.view`  
**Since:** 1.8.0  
**Parameters:** Same as star

#### setRating
Sets rating for a song/album/artist.

**URL:** `/rest/setRating.view`  
**Since:** 1.6.0  
**Parameters:**
- **id** (Required): Item ID
- **rating** (Required): 1-5, or 0 to remove rating

#### scrobble
Registers playback (updates play count, Last.fm scrobble).

**URL:** `/rest/scrobble.view`  
**Since:** 1.5.0  
**Parameters:**
- **id** (Required, Multiple allowed since 1.8.0): Song IDs
- **time** (Optional, Since 1.8.0): Playback timestamp (milliseconds since 1970)
- **submission** (Optional): true/false for Last.fm submission

**Important for Navidrome:** Navidrome does NOT mark songs as played by calls to `stream`. Only marks as played when `scrobble` is called with `submission=true`.

---

## 4. File Download/Streaming

**This section is critical for downloading music files to upload to AzuraCast.**

### 4.1 download Endpoint (Recommended for Original Files)

**This is the primary endpoint you should use for downloading music files.**

**URL:** `/rest/download.view`  
**Since:** 1.0.0  
**Purpose:** Downloads the original media file WITHOUT any transcoding or downsampling

#### Parameters:
- **id** (Required): String uniquely identifying the file to download (obtained from `getAlbum`, `getSong`, etc.)

#### Response:
- **Success:** Binary audio data (exact original file)
- **Error:** XML document (HTTP Content-Type starts with "text/xml")

#### Example URL:
```
http://your-server/rest/download.view?u=username&t=token&s=salt&v=1.16.0&c=myapp&id=tr-12345
```

#### Key Differences from stream:
- `download` returns the **original file** exactly as stored on the server
- NO transcoding or modification
- NO quality loss
- Same bitrate, sample rate, and format as original
- **This is the recommended method for downloading files for re-upload to AzuraCast**

#### Navidrome Extension:
- Also accepts IDs for Albums, Artists, and Playlists (returns ZIP archive)
- Can also accept transcoding options similar to `stream` if needed

### 4.2 stream Endpoint (Alternative with Transcoding Control)

**URL:** `/rest/stream.view`  
**Since:** 1.0.0  
**Purpose:** Streams media files with optional transcoding/downsampling

#### Parameters:
- **id** (Required): String uniquely identifying the file to stream
- **maxBitRate** (Optional, Since 1.2.0): Max bitrate in Kbps (0 = unlimited)
  - Legal values: 0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320
- **format** (Optional, Since 1.6.0): Target format - "mp3", "ogg", "opus", "aac", "m4a", "flac"
  - **"raw"** (Since 1.9.0): Disables transcoding, returns original file
- **estimateContentLength** (Optional, Default: false, Since 1.8.0): Set Content-Length header for transcoded media

#### Getting Original Quality Audio:
To download **without transcoding** using the stream endpoint:
```
http://your-server/rest/stream.view?u=username&t=token&s=salt&v=1.16.0&c=myapp&id=tr-12345&format=raw
```

**The `format=raw` parameter (since API 1.9.0) disables all transcoding and returns the original file.**

#### Example URLs:

**Stream with transcoding to MP3 at 192kbps:**
```
http://server/rest/stream.view?u=user&t=token&s=salt&v=1.16.0&c=app&id=tr-12345&format=mp3&maxBitRate=192
```

**Stream original quality (no transcoding):**
```
http://server/rest/stream.view?u=user&t=token&s=salt&v=1.16.0&c=app&id=tr-12345&format=raw
```

### 4.3 Transcoding Behavior

**With `download` endpoint:**
- No transcoding ever occurs
- Always returns exact original file

**With `stream` endpoint:**
- Without `format` parameter: May use server's default transcoding
- With `format=raw`: No transcoding (same as download)
- With specific `format`: Transcodes to that format if configured

### 4.4 Supported Audio Formats

The Subsonic API supports:
- **Lossy:** MP3, AAC, OGG Vorbis, WMA, M4A, Opus
- **Lossless:** FLAC, APE (Monkey's Audio), Musepack, WavPack, Shorten, TTA, ALAC
- **Hi-Res:** DFF, DSF, AOB, DVD-A ISO, SACD ISO (with transcoders)

### 4.5 Complete Workflow for Downloading Music to AzuraCast

#### Step 1: Browse Music Library

Get all artists:
```
GET /rest/getArtists.view?u=user&t=token&s=salt&v=1.16.1&c=azuracast-importer&f=json
```

Get specific artist's albums:
```
GET /rest/getArtist.view?id=ar-123&u=user&t=token&s=salt&v=1.16.1&c=azuracast-importer&f=json
```

Get album with tracks:
```
GET /rest/getAlbum.view?id=al-456&u=user&t=token&s=salt&v=1.16.1&c=azuracast-importer&f=json
```

#### Step 2: Extract Song IDs and Metadata

From the `getAlbum` response, extract for each song:
- **id**: Use for download
- **title**: Song title
- **artist**: Artist name
- **album**: Album name
- **track**: Track number
- **year**: Release year
- **genre**: Genre
- **duration**: Length in seconds
- **bitRate**: Original bitrate
- **suffix**: File extension (mp3, flac, ogg, etc.)
- **contentType**: MIME type
- **size**: File size in bytes
- **path**: File path (simulated in Navidrome)

#### Step 3: Download Each Song

**Recommended approach - use download endpoint:**
```
GET /rest/download.view?u=user&t=token&s=salt&v=1.16.0&c=azuracast-importer&id=tr-789
```

**Alternative - use stream with raw format:**
```
GET /rest/stream.view?u=user&t=token&s=salt&v=1.16.0&c=azuracast-importer&id=tr-789&format=raw
```

#### Step 4: Download Cover Art

```
GET /rest/getCoverArt.view?u=user&t=token&s=salt&v=1.16.0&c=azuracast-importer&id=al-456
```

#### Step 5: Save Files

Save the binary response to disk with appropriate file extension from the song metadata (`suffix` field).

### 4.6 Detecting Errors vs Binary Data

Check the HTTP response Content-Type header:
- If starts with "text/xml" or "application/json" → Error occurred, parse for error details
- Otherwise → Binary audio/image data

Example error response when song not found:
```json
{
  "subsonic-response": {
    "status": "failed",
    "version": "1.16.1",
    "error": {
      "code": 70,
      "message": "The requested data was not found"
    }
  }
}
```

### 4.7 Best Practices for Downloading

1. **Use the `download` endpoint** - Guarantees original file without modification
2. **Preserve file metadata** - Capture all metadata fields for proper organization
3. **Handle different audio formats** - Server may have FLAC, MP3, OGG, etc.
4. **Check Content-Type** - Detect errors vs binary data
5. **Implement retry logic** - Handle network failures gracefully
6. **Rate limit requests** - Be respectful of server resources
7. **Batch downloads intelligently** - Download albums, then artists, in organized manner

---

## 5. Practical Implementation Details

### 5.1 Response Formats

**Supported Formats:**
- **XML** (default) - Conforms to subsonic-rest-api.xsd schema
- **JSON** (Since 1.4.0) - Recommended for modern apps
- **JSONP** (Since 1.6.0) - For cross-domain requests

**Specify Format:**
Use the `f` parameter:
- `f=xml` - XML response (default)
- `f=json` - JSON response (recommended)
- `f=jsonp&callback=myFunction` - JSONP response

### 5.2 Response Structure

**Successful Response (JSON):**
```json
{
  "subsonic-response": {
    "status": "ok",
    "version": "1.16.1",
    "type": "navidrome",
    "serverVersion": "0.49.3",
    "openSubsonic": true
  }
}
```

**Successful Response (XML):**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<subsonic-response xmlns="http://subsonic.org/restapi" status="ok" version="1.16.1">
</subsonic-response>
```

**Error Response (JSON):**
```json
{
  "subsonic-response": {
    "status": "failed",
    "version": "1.16.1",
    "type": "navidrome",
    "serverVersion": "0.49.3",
    "openSubsonic": true,
    "error": {
      "code": 40,
      "message": "Wrong username or password"
    }
  }
}
```

### 5.3 Error Handling

**Complete Error Code Reference:**

| Code | Description | Resolution |
|------|-------------|------------|
| 0 | Generic error | Check server logs |
| 10 | Required parameter missing | Add missing parameter |
| 20 | Client version too old | Upgrade client API version |
| 30 | Server version too old | Upgrade server |
| 40 | Wrong username/password | Check credentials |
| 41 | Token auth not supported for LDAP | Use password or API key auth |
| 42 | Auth mechanism not supported | Try different auth method |
| 43 | Multiple conflicting auth mechanisms | Use only one auth method |
| 44 | Invalid API key | Check or regenerate API key |
| 50 | User not authorized | Check user permissions |
| 60 | Trial period expired | Upgrade to Premium (original Subsonic) |
| 70 | Data not found | Check that ID exists |

**Error Handling Best Practices:**
1. Always check `status` field in response
2. Parse `error.code` and `error.message` fields
3. Implement specific handling for common errors (40, 70)
4. Log unexpected errors for debugging
5. Provide user-friendly error messages

### 5.4 Rate Limiting

**Important:** The Subsonic API specification does NOT define rate limits. Rate limiting is implementation-specific:

- Original Subsonic: No documented limits
- Navidrome: Has auth request rate limiting (configurable)
- Airsonic: No documented limits
- **Best Practice:** Implement client-side rate limiting to be respectful:
  - Limit to 10-20 requests per second
  - Use connection pooling
  - Implement exponential backoff on errors

### 5.5 Pagination

**Endpoints Supporting Pagination:**
- `getAlbumList` / `getAlbumList2`
- `search2` / `search3`
- `getSongsByGenre`
- `getRandomSongs`

**Pagination Parameters:**
- **size** / **count**: Number of results per page (max usually 500)
- **offset**: Starting position (0-based)

**Pagination Example:**
```python
# Page 1 (first 100 albums)
GET /rest/getAlbumList2.view?type=newest&size=100&offset=0&...

# Page 2 (next 100 albums)
GET /rest/getAlbumList2.view?type=newest&size=100&offset=100&...

# Page 3 (next 100 albums)
GET /rest/getAlbumList2.view?type=newest&size=100&offset=200&...
```

**Search Pagination:**
```python
GET /rest/search3.view?query=rock&artistCount=20&artistOffset=0&albumCount=20&albumOffset=0&songCount=20&songOffset=0&...
```

**Note:** Standard API doesn't return total count. Continue pagination until empty results.

### 5.6 Common Gotchas and Compatibility Issues

#### 1. ID Type Inconsistency (CRITICAL)
**Issue:** Some servers (like Navidrome) use string IDs (MD5 hashes or UUIDs), not integers.  
**Solution:** Always treat IDs as strings. Never convert to integers.

```python
# CORRECT
album_id = "a1b2c3d4e5f6"
album = get_album(id=album_id)

# WRONG
album_id = int("12345")  # Breaks with hash IDs
```

#### 2. Mixing ID3 and File Structure Methods
**Issue:** Using methods from different organizational paradigms causes confusion.  
**Solution:** Stick to ID3-based methods (v1.8.0+) exclusively:

**Use these (ID3-based):**
- `getArtists()`, `getArtist()`, `getAlbum()`, `getSong()`
- `search3()`
- `getAlbumList2()`
- `getStarred2()`

**Avoid these (file-structure based):**
- `getIndexes()`, `getMusicDirectory()`
- `search2()`
- `getAlbumList()`
- `getStarred()`

#### 3. LDAP Token Authentication
**Issue:** Token authentication fails for LDAP users (error 41).  
**Solution:** Use password-based or API key authentication for LDAP users.

#### 4. Navidrome Path Simulation
**Issue:** Navidrome returns simulated paths based on tags, not actual file paths.  
**Example:**
- API returns: `Neil Young & Crazy Horse/Greendale/Grandpa's Interview.flac`
- Actual path: `Neil Young/Greendale/07. Neil Young & Crazy Horse - Grandpa's Interview.flac`

**Solution:** Don't rely on `path` field for actual file location. Use IDs for all operations.

#### 5. List vs Dict Return Values
**Issue:** Some endpoints return dict for single result, list for multiple results.  
**Solution:** Normalize to list:

```python
result = get_playlists()
playlists = result.get('playlists', {}).get('playlist', [])

# Normalize to list
if isinstance(playlists, dict):
    playlists = [playlists]

for playlist in playlists:
    print(playlist['name'])
```

#### 6. JSON vs XML Error Responses
**Issue:** Some servers return XML errors even when `f=json` is specified.  
**Solution:** Handle both XML and JSON error responses.

#### 7. Scrobbling Behavior (Navidrome)
**Issue:** Navidrome does NOT mark songs as played on `stream` calls.  
**Solution:** Explicitly call `scrobble` with `submission=true` to mark as played.

### 5.7 URL Encoding

Always URL-encode request parameters, especially:
- Passwords with special characters
- Salts with special characters
- Search queries
- Any user-supplied data

Most HTTP libraries handle this automatically, but if constructing URLs manually:
```python
from urllib.parse import quote
username = "user@example.com"
encoded = quote(username)  # "user%40example.com"
```

---

## 6. Code Examples

### 6.1 Python Examples

#### Using py-sonic Library

**Installation:**
```bash
pip install py-sonic
```

**Basic Connection and Authentication:**
```python
#!/usr/bin/env python3
import libsonic

# Create connection (token auth is automatic)
conn = libsonic.Connection(
    'https://music.example.com',
    'myuser',
    'secretpass',
    port=443
)

# Test connection
if conn.ping():
    print("Connection successful!")
```

**Browse Artists, Albums, and Songs:**
```python
# Get all artists
artists_response = conn.getArtists()
artists = artists_response['artists']['index']

# Get specific artist's albums
artist_response = conn.getArtist('ar-123')
artist = artist_response['artist']
albums = artist.get('album', [])

# Get album with tracks
album_response = conn.getAlbum('al-456')
album = album_response['album']
songs = album.get('song', [])

for song in songs:
    print(f"{song['track']:02d}. {song['title']} - {song['duration']}s")
```

**Search for Music:**
```python
# Search with pagination
results = conn.search3(
    query='Pink Floyd',
    artistCount=10,
    albumCount=10,
    songCount=20
)

artists = results['searchResult3'].get('artist', [])
albums = results['searchResult3'].get('album', [])
songs = results['searchResult3'].get('song', [])
```

**Get Album Lists:**
```python
# Get newest albums
albums = conn.getAlbumList2(
    ltype='newest',
    size=20,
    offset=0
)

# Get albums by year
albums = conn.getAlbumList2(
    ltype='byYear',
    fromYear=1970,
    toYear=1979,
    size=50
)

# Get albums by genre
albums = conn.getAlbumList2(
    ltype='byGenre',
    genre='Rock',
    size=100
)
```

**Complete Download Implementation:**
```python
import libsonic
import hashlib
import random
import string
import requests
import os

class SubsonicDownloader:
    def __init__(self, server_url, username, password):
        self.server_url = server_url
        self.username = username
        self.password = password
        self.api_version = '1.16.1'
        self.client_name = 'azuracast-importer'
        
    def _generate_token(self):
        """Generate salt and token for authentication."""
        salt = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
        token = hashlib.md5(f"{self.password}{salt}".encode()).hexdigest()
        return token, salt
    
    def _build_url(self, endpoint, **params):
        """Build authenticated URL."""
        token, salt = self._generate_token()
        
        base_params = {
            'u': self.username,
            't': token,
            's': salt,
            'v': self.api_version,
            'c': self.client_name,
            'f': 'json'
        }
        base_params.update(params)
        
        url = f"{self.server_url}/rest/{endpoint}.view"
        return url, base_params
    
    def get_all_artists(self):
        """Get all artists."""
        url, params = self._build_url('getArtists')
        response = requests.get(url, params=params)
        data = response.json()
        
        if data['subsonic-response']['status'] == 'failed':
            raise Exception(data['subsonic-response']['error']['message'])
        
        return data['subsonic-response']['artists']['index']
    
    def get_artist_albums(self, artist_id):
        """Get albums for an artist."""
        url, params = self._build_url('getArtist', id=artist_id)
        response = requests.get(url, params=params)
        data = response.json()
        
        if data['subsonic-response']['status'] == 'failed':
            raise Exception(data['subsonic-response']['error']['message'])
        
        return data['subsonic-response']['artist'].get('album', [])
    
    def get_album_songs(self, album_id):
        """Get songs for an album."""
        url, params = self._build_url('getAlbum', id=album_id)
        response = requests.get(url, params=params)
        data = response.json()
        
        if data['subsonic-response']['status'] == 'failed':
            raise Exception(data['subsonic-response']['error']['message'])
        
        album = data['subsonic-response']['album']
        return album.get('song', [])
    
    def download_song(self, song_id, output_path):
        """Download a song to a file."""
        url, params = self._build_url('download', id=song_id)
        response = requests.get(url, params=params, stream=True)
        
        # Check if error (XML/JSON response instead of binary)
        content_type = response.headers.get('Content-Type', '')
        if content_type.startswith('text/xml') or content_type.startswith('application/json'):
            raise Exception(f"Error downloading song {song_id}")
        
        # Write binary data to file
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        return True
    
    def download_cover_art(self, item_id, output_path, size=None):
        """Download cover art."""
        params = {'id': item_id}
        if size:
            params['size'] = size
        
        url, params = self._build_url('getCoverArt', **params)
        response = requests.get(url, params=params)
        
        with open(output_path, 'wb') as f:
            f.write(response.content)
        
        return True
    
    def download_album(self, album_id, output_dir):
        """Download entire album."""
        # Get album info
        songs = self.get_album_songs(album_id)
        
        if not songs:
            print(f"No songs found for album {album_id}")
            return
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # Download cover art
        cover_path = os.path.join(output_dir, 'cover.jpg')
        try:
            self.download_cover_art(album_id, cover_path, size=500)
            print(f"Downloaded cover art")
        except Exception as e:
            print(f"Error downloading cover art: {e}")
        
        # Download each song
        for song in songs:
            song_id = song['id']
            track = song.get('track', 0)
            title = song['title']
            suffix = song.get('suffix', 'mp3')
            
            filename = f"{track:02d} - {title}.{suffix}"
            # Sanitize filename
            filename = "".join(c for c in filename if c.isalnum() or c in (' ', '-', '_', '.')).rstrip()
            
            output_path = os.path.join(output_dir, filename)
            
            try:
                print(f"Downloading: {filename}")
                self.download_song(song_id, output_path)
                print(f"  ✓ Downloaded {song['size']} bytes")
            except Exception as e:
                print(f"  ✗ Error: {e}")

# Usage
downloader = SubsonicDownloader(
    'https://music.example.com',
    'myuser',
    'mypassword'
)

# Download specific album
downloader.download_album('al-456', '/output/Pink Floyd - Dark Side of the Moon')

# Or download all music from all artists
artists = downloader.get_all_artists()
for index in artists:
    for artist in index.get('artist', []):
        artist_name = artist['name']
        albums = downloader.get_artist_albums(artist['id'])
        
        for album in albums:
            album_name = album['name']
            output_dir = f"/output/{artist_name}/{album_name}"
            print(f"\n=== Downloading {artist_name} - {album_name} ===")
            downloader.download_album(album['id'], output_dir)
```

**Error Handling:**
```python
from libsonic.errors import *

try:
    result = conn.getAlbum(id='invalid-id')
except DataNotFoundError as e:
    print(f"Album not found: {e}")
except CredentialError as e:
    print(f"Authentication failed: {e}")
except ParameterError as e:
    print(f"Missing parameter: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

### 6.2 JavaScript/Node.js Examples

#### Using subsonic-api Library

**Installation:**
```bash
npm install subsonic-api
```

**Basic Connection and Authentication:**
```javascript
import { SubsonicAPI } from "subsonic-api";

const api = new SubsonicAPI({
  url: "https://music.example.com",
  auth: {
    username: "myuser",
    password: "mypassword",
  },
});

// Test connection
const pingResult = await api.ping();
console.log("Connection successful!");
```

**Browse and Search:**
```javascript
// Get all artists
const { artists } = await api.getArtists();

// Get artist albums
const { artist } = await api.getArtist({ id: "ar-123" });
const albums = artist.album;

// Get album with tracks
const { album } = await api.getAlbum({ id: "al-456" });
const songs = album.song;

// Search
const results = await api.search3({
  query: "Pink Floyd",
  artistCount: 10,
  albumCount: 10,
  songCount: 20
});
```

**Download Implementation:**
```javascript
import { SubsonicAPI } from "subsonic-api";
import fs from "fs";
import path from "path";
import crypto from "crypto";

class SubsonicDownloader {
  constructor(url, username, password) {
    this.api = new SubsonicAPI({
      url: url,
      auth: { username, password }
    });
    
    this.url = url;
    this.username = username;
    this.password = password;
  }
  
  generateToken() {
    const salt = crypto.randomBytes(12).toString('hex');
    const token = crypto.createHash('md5')
      .update(this.password + salt)
      .digest('hex');
    return { token, salt };
  }
  
  buildDownloadUrl(songId) {
    const { token, salt } = this.generateToken();
    const params = new URLSearchParams({
      u: this.username,
      t: token,
      s: salt,
      v: '1.16.1',
      c: 'azuracast-importer',
      id: songId
    });
    
    return `${this.url}/rest/download.view?${params.toString()}`;
  }
  
  async downloadSong(songId, outputPath) {
    const url = this.buildDownloadUrl(songId);
    const response = await fetch(url);
    
    // Check for errors
    const contentType = response.headers.get('content-type');
    if (contentType?.startsWith('text/xml') || contentType?.startsWith('application/json')) {
      throw new Error(`Error downloading song ${songId}`);
    }
    
    // Save to file
    const buffer = await response.arrayBuffer();
    fs.writeFileSync(outputPath, Buffer.from(buffer));
    
    return true;
  }
  
  async downloadAlbum(albumId, outputDir) {
    // Get album info
    const { album } = await this.api.getAlbum({ id: albumId });
    const songs = album.song || [];
    
    if (songs.length === 0) {
      console.log(`No songs found for album ${albumId}`);
      return;
    }
    
    // Create output directory
    fs.mkdirSync(outputDir, { recursive: true });
    
    // Download cover art
    const coverUrl = this.buildDownloadUrl(albumId).replace('download', 'getCoverArt');
    try {
      const coverResponse = await fetch(coverUrl);
      const coverBuffer = await coverResponse.arrayBuffer();
      fs.writeFileSync(path.join(outputDir, 'cover.jpg'), Buffer.from(coverBuffer));
      console.log('Downloaded cover art');
    } catch (e) {
      console.error('Error downloading cover art:', e.message);
    }
    
    // Download each song
    for (const song of songs) {
      const track = song.track || 0;
      const title = song.title;
      const suffix = song.suffix || 'mp3';
      
      const filename = `${String(track).padStart(2, '0')} - ${title}.${suffix}`
        .replace(/[^a-zA-Z0-9 \-_.]/g, '');
      
      const outputPath = path.join(outputDir, filename);
      
      try {
        console.log(`Downloading: ${filename}`);
        await this.downloadSong(song.id, outputPath);
        console.log(`  ✓ Downloaded ${song.size} bytes`);
      } catch (e) {
        console.error(`  ✗ Error: ${e.message}`);
      }
    }
  }
}

// Usage
const downloader = new SubsonicDownloader(
  'https://music.example.com',
  'myuser',
  'mypassword'
);

await downloader.downloadAlbum('al-456', '/output/Pink Floyd - Dark Side of the Moon');
```

**Error Handling:**
```javascript
try {
  const album = await api.getAlbum({ id: "invalid" });
} catch (error) {
  if (error.response?.error) {
    const { code, message } = error.response.error;
    console.error(`Subsonic error ${code}: ${message}`);
  } else {
    console.error(`Network error: ${error.message}`);
  }
}
```

### 6.3 Manual Token Generation Examples

**Shell/Bash:**
```bash
#!/bin/bash

SERVER='https://music.example.com'
USERNAME='myuser'
PASSWORD='mypassword'
CLIENT='azuracast-importer'
API_VERSION='1.16.1'

# Generate salt and token
SALT=$(openssl rand -hex 10)
TOKEN=$(echo -n "${PASSWORD}${SALT}" | md5sum | awk '{ print $1 }')

# Make request
curl "${SERVER}/rest/ping.view?u=${USERNAME}&t=${TOKEN}&s=${SALT}&v=${API_VERSION}&c=${CLIENT}&f=json"
```

**Python (without library):**
```python
import hashlib
import random
import string
import requests

def generate_auth():
    password = "mypassword"
    salt = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
    token = hashlib.md5(f"{password}{salt}".encode()).hexdigest()
    return token, salt

token, salt = generate_auth()

params = {
    'u': 'myuser',
    't': token,
    's': salt,
    'v': '1.16.1',
    'c': 'myapp',
    'f': 'json'
}

response = requests.get('https://music.example.com/rest/ping.view', params=params)
print(response.json())
```

---

## 7. Important Links and References

### Official Documentation

**Subsonic API:**
- Official Subsonic API Specification: https://www.subsonic.org/pages/api.jsp
- Official Subsonic Website: https://www.subsonic.org

**OpenSubsonic:**
- OpenSubsonic API Documentation: https://opensubsonic.netlify.app/
- OpenSubsonic GitHub: https://github.com/opensubsonic/opensubsonic.github.io

**Navidrome:**
- Navidrome Subsonic API Documentation: https://www.navidrome.org/docs/developers/subsonic-api/
- Navidrome GitHub: https://github.com/navidrome/navidrome
- Navidrome Official Website: https://www.navidrome.org

### Alternative Subsonic Server Implementations

- **Airsonic:** https://airsonic.github.io/
- **Airsonic-Advanced:** https://github.com/airsonic-advanced/airsonic-advanced
- **Gonic:** https://github.com/sentriz/gonic
- **Funkwhale:** https://funkwhale.audio/
- **Supysonic:** https://github.com/spl0k/supysonic

### Client Libraries

**Python:**
- py-sonic: https://github.com/crustymonkey/py-sonic
- py-opensonic: https://github.com/khers/py-opensonic

**JavaScript/TypeScript:**
- subsonic-api: https://github.com/explodingcamera/subsonic-api

**Go:**
- go-subsonic: https://github.com/delucks/go-subsonic

### Testing Resources

**Public Demo Servers:**
- Navidrome Demo: https://demo.navidrome.org (username: demo, password: demo)
- Subsonic Official Demo: http://demo.subsonic.org

### Additional Resources

- Subsonic API XSD Schema: http://subsonic.org/pages/inc/api/schema/subsonic-rest-api-1.16.1.xsd
- Subsonic Forums: https://www.subsonic.org/forum/
- OpenSubsonic Discussions: https://github.com/opensubsonic/opensubsonic.github.io/discussions

---

## Summary for LLM Implementation

### Critical Implementation Points:

1. **Use ID3-based endpoints** (getArtists, getArtist, getAlbum, search3, getAlbumList2) - available since API 1.8.0

2. **Implement token-based authentication** (API 1.13.0+):
   - Generate random salt for each request
   - Calculate MD5 token: `md5(password + salt)`
   - Always use HTTPS in production

3. **For downloading music files to AzuraCast:**
   - Use `download` endpoint for original files (recommended)
   - Alternative: `stream` endpoint with `format=raw` parameter
   - Never use `stream` without `format=raw` if you want originals

4. **Always treat IDs as strings** - Navidrome uses MD5 hashes/UUIDs, not integers

5. **Check response status** - Parse `subsonic-response.status` and handle errors appropriately

6. **Preserve metadata** - Capture title, artist, album, track, year, genre, bitRate, suffix, etc.

7. **Handle pagination** - Use size/offset parameters for large result sets

8. **Implement proper error handling** - Check Content-Type for binary vs error responses

9. **For Navidrome specifically:**
   - Supports API v1.16.1 with OpenSubsonic extensions
   - No video support (music-only)
   - Does NOT mark plays on `stream` - must call `scrobble`
   - Returns simulated paths, not actual file paths

10. **Request format:** Prefer JSON (`f=json`) for easier parsing

This documentation provides everything needed to implement a complete Subsonic API client for migrating music from Subsonic/Navidrome to AzuraCast, including authentication, browsing, searching, metadata retrieval, and file downloading.