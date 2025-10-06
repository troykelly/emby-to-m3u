# Subsonic MCP Server

Model Context Protocol (MCP) server that exposes Subsonic/OpenSubsonic music libraries to AI applications like Claude Desktop, enabling intelligent playlist generation and music discovery.

## Features

- **10 MCP Tools** for music operations:
  - `search_tracks` - Search for tracks by title, artist, or album
  - `get_track_info` - Get detailed track metadata
  - `get_artists` - List all artists in library
  - `get_artist_albums` - Get albums for specific artist
  - `get_album_tracks` - Get tracks for specific album
  - `search_similar` - Find similar tracks by artist/genre
  - `get_genres` - List all genres with counts
  - `get_tracks_by_genre` - Filter tracks by genre
  - `analyze_library` - Get library-wide statistics
  - `stream_track` - Generate streaming URLs

- **6 MCP Resources** for library exploration:
  - `library://stats` - Complete library statistics (5-min cache)
  - `library://artists` - Artist catalog (5-min cache)
  - `library://albums` - Album collection (5-min cache)
  - `library://genres` - Genre taxonomy (5-min cache)
  - `library://playlists` - User playlists (2-min cache)
  - `library://recent` - Recently added tracks (1-min cache)

- **5 MCP Prompts** for AI workflows:
  - `mood_playlist` - Generate mood-based playlists
  - `music_discovery` - Discover new music
  - `listening_analysis` - Analyze listening patterns
  - `smart_playlist` - Create rules-based playlists
  - `library_curation` - Find duplicates, missing metadata, quality issues

## Installation

### Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) package manager
- Subsonic or OpenSubsonic-compatible music server

### Setup

1. Install dependencies:
```bash
uv sync
```

2. Configure environment variables:
```bash
export SUBSONIC_URL="https://your-music-server.com"
export SUBSONIC_USER="your-username"
export SUBSONIC_PASSWORD="your-password"
```

## Claude Desktop Integration

Add to your Claude Desktop configuration (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "subsonic": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/emby-to-m3u/mcp-server",
        "run",
        "subsonic-mcp"
      ],
      "env": {
        "SUBSONIC_URL": "https://your-music-server.com",
        "SUBSONIC_USER": "your-username",
        "SUBSONIC_PASSWORD": "your-password"
      }
    }
  }
}
```

Restart Claude Desktop to activate the server.

## Usage Examples

### In Claude Desktop

**Generate a mood playlist:**
```
Create a relaxing 60-minute playlist using my Subsonic library
```

**Discover new music:**
```
Find music similar to Pink Floyd and Led Zeppelin in my library
```

**Analyze your library:**
```
Analyze the genre distribution in my music collection
```

**Find quality issues:**
```
Find tracks with low bitrate or missing metadata
```

## Development

### Run Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=subsonic_mcp --cov-report=html

# Run specific test file
uv run pytest tests/test_tools.py -v
```

### Code Quality

```bash
# Format code
uv run black src/ tests/

# Lint code
uv run pylint src/subsonic_mcp/
```

## Architecture

- **cache.py** - In-memory caching with TTL and dynamic throttling
- **tools.py** - 10 MCP tools for music operations
- **resources.py** - 6 MCP resources for library exploration
- **prompts.py** - 5 MCP prompts for AI workflows
- **server.py** - Main MCP server with stdio transport
- **utils.py** - Error handling utilities

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SUBSONIC_URL` | Yes | Subsonic server URL |
| `SUBSONIC_USER` | Yes | Username for authentication |
| `SUBSONIC_PASSWORD` | Yes | Password for authentication |

### Caching

Default cache TTLs:
- Library stats, artists, albums, genres: 5 minutes
- Playlists: 2 minutes
- Recent tracks: 1 minute

Cache automatically throttles requests when server response times exceed 2 seconds.

## Contributing

This MCP server is part of the [emby-to-m3u](https://github.com/troykelly/emby-to-m3u) project. Contributions welcome!

## License

MIT License - See LICENSE file for details
