# Quick Start Guide
## Subsonic MCP Server for Claude Desktop

**Feature**: 003-create-model-context
**Date**: 2025-10-06

---

## Prerequisites

- Python 3.10+ installed
- Claude Desktop installed
- Subsonic or OpenSubsonic server running and accessible
- Valid Subsonic credentials (username + password)

---

## Installation

### 1. Install uv Package Manager (One-Time Setup)

```bash
# macOS and Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Verify installation
uv --version  # Should show 0.8.22 or later
```

### 2. Set Up MCP Server

```bash
# Navigate to repository root
cd /workspaces/emby-to-m3u

# Create MCP server directory structure
mkdir -p mcp-server
cd mcp-server

# Initialize uv project
uv init subsonic-mcp-server
cd subsonic-mcp-server

# Install MCP SDK
uv add mcp>=1.5.0

# Add project dependency (parent directory with SubsonicClient)
# This will be configured in pyproject.toml

# Sync dependencies
uv sync
```

### 3. Configure Environment Variables

Create `.env` file in `mcp-server/` directory:

```bash
# Subsonic Server Configuration
SUBSONIC_URL=http://localhost:4040
SUBSONIC_USER=admin
SUBSONIC_PASSWORD=your-password-here

# Optional: MCP Server Settings
MCP_LOG_LEVEL=INFO
```

---

## Claude Desktop Configuration

### 1. Locate Configuration File

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
**Linux**: `~/.config/Claude/claude_desktop_config.json`

### 2. Add MCP Server Configuration

Edit `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "subsonic": {
      "command": "uv",
      "args": [
        "--directory",
        "/workspaces/emby-to-m3u/mcp-server",
        "run",
        "python",
        "-m",
        "subsonic_mcp.server"
      ],
      "env": {
        "SUBSONIC_URL": "http://localhost:4040",
        "SUBSONIC_USER": "admin",
        "SUBSONIC_PASSWORD": "your-password-here"
      }
    }
  }
}
```

**Important**: Replace `/workspaces/emby-to-m3u/mcp-server` with the absolute path to your mcp-server directory.

### 3. Restart Claude Desktop

Quit and relaunch Claude Desktop to load the new MCP server configuration.

---

## Verification

### 1. Check Server Status in Claude Desktop

Open Claude Desktop and type:

```
Can you see the subsonic MCP server?
```

Claude should respond confirming the server is available and list available tools/resources.

### 2. Test Basic Search

```
Search for tracks by "Beatles" in my music library
```

Expected response: List of Beatles tracks with metadata (title, artist, album, streaming URL).

### 3. Test Library Analysis

```
Analyze my music library and show me statistics
```

Expected response: Library stats including total tracks, artists, albums, genres.

### 4. Test Playlist Generation

```
Create a relaxing evening playlist with 15-20 tracks
```

Expected response: Curated playlist with track selection reasoning and streaming URLs.

---

## Usage Examples

### Example 1: Music Discovery

**User**: "What are my top 5 genres by track count?"

**Expected Flow**:
1. Claude calls `get_genres` tool
2. Retrieves genre list with track counts
3. Sorts by track count (descending)
4. Returns top 5 genres with percentages

**Sample Output**:
```
Your top 5 genres by track count:

1. Rock - 2,450 tracks (35%)
2. Pop - 1,820 tracks (26%)
3. Jazz - 980 tracks (14%)
4. Electronic - 720 tracks (10%)
5. Classical - 630 tracks (9%)
```

### Example 2: Similar Track Discovery

**User**: "Find tracks similar to Pink Floyd"

**Expected Flow**:
1. Claude calls `search_similar` tool with query="Pink Floyd"
2. Subsonic returns progressive rock, psychedelic rock tracks
3. Results formatted with artist, album, year

**Sample Output**:
```
Tracks similar to Pink Floyd:

1. Echoes - Pink Floyd (Meddle, 1971)
2. In the Court of the Crimson King - King Crimson (1969)
3. Starless - King Crimson (Red, 1974)
4. Close to the Edge - Yes (1972)
5. Supper's Ready - Genesis (Foxtrot, 1972)
...
```

### Example 3: Mood-Based Playlist

**User**: "Create an energetic workout playlist, 45 minutes"

**Expected Flow**:
1. Claude uses `mood_playlist` prompt with mood="energetic", duration=45
2. Searches library for high-energy tracks using `search_tracks` and `get_tracks_by_genre`
3. Filters by tempo, genre (rock, electronic, hip-hop)
4. Arranges tracks for workout flow (warm-up → peak → cool-down)
5. Returns playlist with streaming URLs

**Sample Output**:
```
Energetic Workout Playlist (45 minutes):

Warm-Up (5 min):
1. Lose Yourself - Eminem (3:26)
2. Titanium - David Guetta ft. Sia (3:45)

Peak Intensity (30 min):
3. Seven Nation Army - The White Stripes (3:52)
4. Sabotage - Beastie Boys (2:58)
5. Killing in the Name - Rage Against the Machine (5:14)
...

Cool-Down (10 min):
18. Don't Stop Believin' - Journey (4:10)
19. Mr. Brightside - The Killers (3:42)

Total: 45:12 | 19 tracks
[Streaming URLs ready for playback]
```

### Example 4: Library Curation

**User**: "Find tracks with missing metadata in my library"

**Expected Flow**:
1. Claude uses `library_curation` prompt with task="missing_metadata"
2. Calls `get_artists`, `analyze_library` to survey library
3. Identifies tracks with null genre, year, or album
4. Returns list of tracks needing metadata

**Sample Output**:
```
Tracks with missing metadata (23 found):

Missing Genre (12 tracks):
1. Unknown Track - Various Artists (Album: Unknown)
2. Track 03 - Unknown (Album: Untitled)
...

Missing Year (8 tracks):
1. Song Title - Artist Name (Album: Album Name)
...

Missing Album (3 tracks):
1. Single Track - Solo Artist
...

Recommendation: Use a metadata service (MusicBrainz, Discogs) to fill missing fields.
```

---

## Troubleshooting

### Server Not Appearing in Claude Desktop

**Symptoms**: Claude Desktop doesn't list the subsonic MCP server.

**Solutions**:
1. Check `claude_desktop_config.json` syntax (valid JSON)
2. Verify absolute path to `mcp-server/` directory
3. Check logs: `~/Library/Logs/Claude/mcp-server-subsonic.log` (macOS)
4. Restart Claude Desktop after config changes

### Authentication Failed

**Symptoms**: Error message "Authentication failed. Please verify SUBSONIC_USER and SUBSONIC_PASSWORD."

**Solutions**:
1. Verify credentials in `claude_desktop_config.json` `env` section
2. Test credentials directly: `curl -u user:pass http://localhost:4040/rest/ping.view?v=1.16.1&c=test&f=json`
3. Check Subsonic server is running: `curl http://localhost:4040/rest/ping.view`

### Connection Timeout

**Symptoms**: Error message "Unable to connect to music server. Please check your server status and try again."

**Solutions**:
1. Verify `SUBSONIC_URL` is correct and accessible
2. Check firewall/network settings allow connection to Subsonic server
3. Test direct connection: `curl http://localhost:4040/rest/ping.view`
4. Ensure Subsonic server is running and responding

### No Search Results

**Symptoms**: "No tracks found matching your criteria."

**Solutions**:
1. Verify library is populated (check with `analyze_library` tool)
2. Try broader search terms
3. Check Subsonic server indexing status (may need to re-index library)

### Result Truncation

**Symptoms**: "Showing first 100 results. Narrow your search..."

**Explanation**: Search results are limited to 100 tracks (FR-039, FR-040).

**Solutions**:
1. Refine search with artist filter: "Search for 'love' by Beatles"
2. Add genre filter: "Search for 'rock' tracks from 1970s"
3. Use year range: "Search for 'dance' tracks from 2010-2020"

---

## Performance Tips

### Cache Hit Optimization

- Frequently accessed data (artists, genres, stats) is cached for 5 minutes
- Repeated queries within 5 minutes return instantly (<5s)
- Cache miss (first query or expired) may take up to 15s

### Dynamic Throttling

- System monitors Subsonic server response times
- Automatically adjusts request rate based on server performance
- No manual rate limiting configuration needed

### Large Library Performance

- For libraries with 100k+ tracks, use filters (artist, genre, year)
- Avoid open-ended searches like "search for 'the'"
- Use specific queries: "search for 'the beatles abbey road'"

---

## Testing Checklist

Use this checklist to validate the MCP server setup:

- [ ] **Installation**: uv installed and `uv --version` works
- [ ] **Configuration**: `claude_desktop_config.json` updated with correct paths
- [ ] **Environment**: SUBSONIC_URL, USER, PASSWORD set correctly
- [ ] **Claude Desktop**: Server appears in available MCP servers list
- [ ] **Basic Search**: Can search for tracks by query
- [ ] **Tool Execution**: All 10 tools execute without errors
- [ ] **Resource Access**: All 6 resources return data
- [ ] **Prompt Usage**: All 5 prompts generate valid templates
- [ ] **Caching**: Second request for same data returns faster
- [ ] **Error Handling**: Invalid inputs return user-friendly errors
- [ ] **Large Results**: Queries with 100+ results show pagination guidance

---

## Next Steps

After successful setup:

1. **Explore Prompts**: Try all 5 predefined prompts (mood_playlist, music_discovery, etc.)
2. **Test Tools**: Execute each of the 10 tools with various inputs
3. **Monitor Performance**: Observe cache hit rates and response times
4. **Advanced Queries**: Combine multiple tools for complex music discovery tasks
5. **Customize**: Modify prompts in `prompts.py` for personalized workflows

---

## Support Resources

- **MCP Implementation Guide**: `/workspaces/emby-to-m3u/mcp-implementation-guide.md`
- **Feature Spec**: `/workspaces/emby-to-m3u/specs/003-create-model-context/spec.md`
- **Data Model**: `/workspaces/emby-to-m3u/specs/003-create-model-context/data-model.md`
- **Contracts**: `/workspaces/emby-to-m3u/specs/003-create-model-context/contracts/`
- **MCP SDK Docs**: https://github.com/modelcontextprotocol/python-sdk
- **Subsonic API Docs**: http://www.subsonic.org/pages/api.jsp

---

**Quickstart validation complete. MCP server ready for development and testing.**
