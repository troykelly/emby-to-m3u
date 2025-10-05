# Quickstart: Subsonic API Integration

**Feature**: Subsonic API Integration for Music Library Access
**Branch**: `001-build-subsonic-api`
**Date**: 2025-10-05

## Purpose

This quickstart guide provides step-by-step validation for the Subsonic API integration. It serves as both a manual test procedure and acceptance criteria for the feature implementation.

## Prerequisites

- ✅ Subsonic-compatible server (Navidrome, Airsonic, or Gonic) running and accessible
- ✅ Valid Subsonic credentials (username and password)
- ✅ Python 3.13+ installed
- ✅ Application dependencies installed (`pip install -r requirements.txt`)
- ✅ Docker (optional, for containerized testing)

## Configuration

### Environment Variables

Create or update `.env` file with Subsonic configuration:

```bash
# Subsonic Configuration (replaces Emby when present)
SUBSONIC_URL=https://music.example.com
SUBSONIC_USER=admin
SUBSONIC_PASSWORD=your_password_here
SUBSONIC_CLIENT_NAME=playlistgen  # Optional, defaults to "playlistgen"
SUBSONIC_API_VERSION=1.16.1        # Optional, defaults to "1.16.1"

# Existing Configuration (for backward compatibility testing)
# EMBY_SERVER_URL=https://emby.example.com
# EMBY_API_KEY=your_emby_key

# Logging Configuration
M3U_LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
```

**Important**: When `SUBSONIC_URL` is set, the application will use Subsonic exclusively and ignore any Emby configuration.

---

## Validation Steps

### Step 1: Verify Environment Configuration

**Action**: Check that environment variables are correctly loaded.

```bash
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print('SUBSONIC_URL:', os.getenv('SUBSONIC_URL')); print('SUBSONIC_USER:', os.getenv('SUBSONIC_USER'))"
```

**Expected Output**:
```
SUBSONIC_URL: https://music.example.com
SUBSONIC_USER: admin
```

**✅ Success Criteria**: Both variables are non-empty and correct.

---

### Step 2: Test Authentication

**Action**: Run the application and verify successful authentication.

```bash
python src/main.py
```

**Expected Log Output**:
```
INFO - Subsonic URL configured: https://music.example.com
INFO - Attempting Subsonic authentication for user: admin
INFO - Subsonic authentication successful (API version: 1.16.1)
```

**✅ Success Criteria**:
- No authentication errors
- Log shows "Subsonic authentication successful"
- Application doesn't fall back to Emby

**❌ Failure Scenarios**:
- `ERROR - Subsonic authentication failed: Wrong username or password` → Check credentials
- `ERROR - Failed to connect to Subsonic server` → Check server URL and network
- `ERROR - Subsonic API version incompatible` → Check server API version

---

### Step 3: Verify Library Fetch

**Action**: Allow application to fetch complete music library.

**Expected Log Output** (with M3U_LOG_LEVEL=INFO):
```
INFO - Fetching music library from Subsonic...
INFO - Fetched page 1: 500 tracks (offset 0)
INFO - Fetched page 2: 500 tracks (offset 500)
INFO - Fetched page 3: 324 tracks (offset 1000)
INFO - Library fetch complete: 1324 total tracks
INFO - Duplicate tracks discarded: 15
INFO - Unique tracks added to playlist manager: 1309
```

**✅ Success Criteria**:
- All tracks fetched successfully (pagination automatic)
- Duplicate tracks detected and discarded
- Final track count matches expected library size
- Fetch completes without timeout errors

**Performance Validation**:
```bash
time python src/main.py
```

For 5000 tracks: Should complete in < 60 seconds (83.3 tracks/sec minimum)

---

### Step 4: Verify Playlist Generation

**Action**: Check that M3U playlists are generated with Subsonic tracks.

**Expected File Output** (in `output/` or configured directory):
```
output/
├── genres/
│   ├── rock.m3u
│   ├── jazz.m3u
│   └── classical.m3u
├── artists/
│   ├── queen.m3u
│   └── beatles.m3u
├── albums/
│   └── abbey_road.m3u
└── years/
    ├── 1975.m3u
    └── 1969.m3u
```

**Sample M3U Content** (`output/genres/rock.m3u`):
```m3u
#EXTM3U
#EXTINF:354,Queen - Bohemian Rhapsody
https://music.example.com/rest/stream?id=300&u=admin&t=xxx&s=yyy&v=1.16.1&c=playlistgen
#EXTINF:207,The Beatles - Come Together
https://music.example.com/rest/stream?id=450&u=admin&t=xxx&s=yyy&v=1.16.1&c=playlistgen
```

**✅ Success Criteria**:
- M3U files generated for all categories (genres, artists, albums, years)
- Playlist entries contain Subsonic stream URLs (not Emby URLs)
- Stream URLs include authentication parameters (u, t, s)
- Track metadata displayed correctly in #EXTINF lines

---

### Step 5: Test Source Precedence (Subsonic over Emby)

**Action**: Configure both Subsonic and Emby, verify Subsonic takes precedence.

**Configuration** (`.env`):
```bash
# Both sources configured
SUBSONIC_URL=https://music.example.com
SUBSONIC_USER=admin
SUBSONIC_PASSWORD=subsonic_password

EMBY_SERVER_URL=https://emby.example.com
EMBY_API_KEY=emby_api_key
```

**Expected Log Output**:
```
INFO - Subsonic URL configured: https://music.example.com
INFO - Emby configuration detected but will be ignored (Subsonic takes precedence)
INFO - Using Subsonic as exclusive music source
INFO - Subsonic authentication successful
INFO - Fetching music library from Subsonic...
```

**✅ Success Criteria**:
- Application uses Subsonic exclusively
- Emby configuration ignored (logged but not used)
- No Emby API calls made

---

### Step 6: Test Backward Compatibility (Emby Fallback)

**Action**: Remove Subsonic configuration, verify Emby fallback works.

**Configuration** (`.env`):
```bash
# Subsonic NOT configured
# SUBSONIC_URL=
# SUBSONIC_USER=
# SUBSONIC_PASSWORD=

# Emby configured
EMBY_SERVER_URL=https://emby.example.com
EMBY_API_KEY=emby_api_key
```

**Expected Log Output**:
```
INFO - Subsonic URL not configured
INFO - Falling back to Emby as music source
INFO - Using Emby server: https://emby.example.com
INFO - Fetching music library from Emby...
```

**✅ Success Criteria**:
- Application falls back to Emby when Subsonic not configured
- Existing Emby integration continues working
- M3U playlists generated with Emby URLs

---

### Step 7: Test Error Handling (Wrong Credentials)

**Action**: Provide incorrect credentials, verify clear error message.

**Configuration** (`.env`):
```bash
SUBSONIC_URL=https://music.example.com
SUBSONIC_USER=admin
SUBSONIC_PASSWORD=wrong_password
```

**Expected Log Output**:
```
ERROR - Subsonic authentication failed: Wrong username or password (error code 40)
ERROR - Failed to authenticate with Subsonic after 3 retry attempts
ERROR - Application cannot proceed without valid authentication
```

**✅ Success Criteria**:
- Clear error message displayed (not generic "connection failed")
- Retry attempts logged (up to 3 retries)
- Application exits gracefully (no crash)
- No partial/incomplete playlists generated

---

### Step 8: Test Network Failure Handling

**Action**: Simulate network failure during library fetch (disconnect network mid-fetch or use invalid URL).

**Configuration** (`.env`):
```bash
SUBSONIC_URL=https://unreachable.example.com
SUBSONIC_USER=admin
SUBSONIC_PASSWORD=password
```

**Expected Log Output**:
```
INFO - Fetching music library from Subsonic...
INFO - Fetched page 1: 500 tracks (offset 0)
ERROR - Network error during library fetch: Connection timeout
INFO - Retry attempt 1 of 3 (exponential backoff: 2s)
ERROR - Network error during library fetch: Connection timeout
INFO - Retry attempt 2 of 3 (exponential backoff: 4s)
ERROR - Network error during library fetch: Connection timeout
INFO - Retry attempt 3 of 3 (exponential backoff: 8s)
ERROR - Maximum retries exceeded, discarding partial data (500 tracks)
ERROR - Library fetch failed, no playlists will be generated
```

**✅ Success Criteria**:
- Exponential backoff retry logic executed (1, 2, 4, 8 seconds)
- Partial data discarded (no corrupt playlists)
- Clear error message with reason
- Application exits gracefully

---

### Step 9: Test Logging Verbosity (M3U_LOG_LEVEL)

**Action**: Test different log levels to verify observability.

**Configuration** (`.env` with DEBUG level):
```bash
M3U_LOG_LEVEL=DEBUG
SUBSONIC_URL=https://music.example.com
SUBSONIC_USER=admin
SUBSONIC_PASSWORD=password
```

**Expected Log Output** (DEBUG level):
```
DEBUG - Generating random salt for authentication: c19b2d
DEBUG - Computing MD5 token: password='***', salt='c19b2d'
DEBUG - Authentication request: GET /rest/ping?u=admin&t=xxx&s=c19b2d...
INFO  - Subsonic authentication successful (API version: 1.16.1)
DEBUG - Library fetch request: GET /rest/getSongs?offset=0&size=500...
DEBUG - Received 500 tracks in response
DEBUG - Transforming Subsonic track 'Bohemian Rhapsody' (ID: 300)
DEBUG - Genre transformation: 'Rock' → ['Rock']
DEBUG - Duration transformation: 354 seconds → 3540000000 ticks
INFO  - Fetched page 1: 500 tracks (offset 0)
```

**Expected Log Output** (INFO level - default):
```
INFO - Subsonic authentication successful (API version: 1.16.1)
INFO - Fetching music library from Subsonic...
INFO - Fetched page 1: 500 tracks (offset 0)
INFO - Library fetch complete: 500 total tracks
```

**Expected Log Output** (ERROR level):
```
(Only errors shown - no INFO or DEBUG messages)
```

**✅ Success Criteria**:
- DEBUG: Shows detailed API requests, transformations, internal operations
- INFO: Shows key milestones (auth, fetch progress, completion)
- ERROR: Shows only fatal errors
- Log level respected throughout application

---

### Step 10: Test Performance (5000 Tracks in <60 Seconds)

**Action**: Run against library with 5000+ tracks, measure fetch time.

**Command**:
```bash
time python src/main.py
```

**Expected Output**:
```
INFO - Fetching music library from Subsonic...
INFO - Fetched page 1: 500 tracks (offset 0)
INFO - Fetched page 2: 500 tracks (offset 500)
...
INFO - Fetched page 10: 500 tracks (offset 4500)
INFO - Library fetch complete: 5000 total tracks
INFO - Processing time: 48.3 seconds

real    0m48.342s
user    0m12.456s
sys     0m2.123s
```

**✅ Success Criteria**:
- 5000 tracks fetched in < 60 seconds (target: 48-55 seconds)
- Throughput > 83.3 tracks/second
- Memory usage < 100MB per instance
- No timeout errors during pagination

**Performance Benchmarks**:
- 1000 tracks: < 12 seconds
- 5000 tracks: < 60 seconds
- 10000 tracks: < 120 seconds

---

## Integration Validation

### Test with Last.fm Integration

If Last.fm is configured, verify that track scrobbling still works with Subsonic tracks.

**Expected Behavior**:
- Track metadata from Subsonic used for Last.fm scrobbling
- Artist, album, track name correctly submitted to Last.fm
- No errors related to missing Emby metadata

---

### Test with AzuraCast Integration

If AzuraCast is configured, verify that track upload still works with Subsonic tracks.

**Expected Behavior**:
- Tracks downloaded from Subsonic using stream endpoint
- Audio files uploaded to AzuraCast successfully
- Metadata preserved in AzuraCast library

---

### Test with ReplayGain Processing

Verify that ReplayGain analysis works with Subsonic-sourced tracks.

**Expected Behavior**:
- Tracks downloaded from Subsonic for ReplayGain analysis
- ReplayGain metadata computed and applied
- Modified tracks maintain audio quality

---

## Acceptance Criteria Summary

| Test | Criteria | Status |
|------|----------|--------|
| 1. Environment Configuration | SUBSONIC_URL and SUBSONIC_USER loaded correctly | ☐ |
| 2. Authentication | Successful auth with correct credentials | ☐ |
| 3. Library Fetch | All tracks fetched with pagination | ☐ |
| 4. Playlist Generation | M3U files generated with Subsonic URLs | ☐ |
| 5. Source Precedence | Subsonic takes precedence over Emby | ☐ |
| 6. Backward Compatibility | Emby fallback works when Subsonic not configured | ☐ |
| 7. Error Handling | Clear error message for wrong credentials | ☐ |
| 8. Network Failure | Retry logic + partial data discard | ☐ |
| 9. Logging Verbosity | M3U_LOG_LEVEL respected (DEBUG/INFO/ERROR) | ☐ |
| 10. Performance | 5000 tracks in < 60 seconds | ☐ |

**All criteria must pass for feature acceptance.**

---

## Troubleshooting

### Common Issues

**Issue**: `ModuleNotFoundError: No module named 'httpx'`
**Solution**: Install dependencies: `pip install -r requirements.txt`

**Issue**: `ERROR - Subsonic API version incompatible`
**Solution**: Check server API version, update `SUBSONIC_API_VERSION` in `.env`

**Issue**: `ERROR - SSL certificate verification failed`
**Solution**: For testing, can disable SSL verification (NOT for production):
```python
# In SubsonicClient initialization
client = httpx.Client(verify=False)  # Development only!
```

**Issue**: Slow library fetch (>60s for 5000 tracks)
**Solution**:
- Check network latency to Subsonic server
- Verify server performance (CPU, disk I/O)
- Consider increasing concurrent requests in client

**Issue**: Duplicate tracks not being detected
**Solution**:
- Verify metadata comparison logic in `is_duplicate()`
- Check that track title, artist, and album are correctly populated

---

## Next Steps

After successful quickstart validation:

1. ✅ Run full test suite: `pytest tests/ -v --cov=src/subsonic --cov-report=term`
2. ✅ Verify code coverage ≥ 90%: `pytest --cov=src/subsonic --cov-report=html`
3. ✅ Run Pylint: `pylint src/subsonic/ --fail-under=9.0`
4. ✅ Run type checking: `mypy src/subsonic/ --strict`
5. ✅ Performance regression tests: `pytest tests/performance/ -v`
6. ✅ Integration tests against real Subsonic server: `pytest tests/integration/ -v`

**Feature Ready for Production**: All quickstart steps pass + test suite passes + constitutional compliance verified.
