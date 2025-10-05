# Integration Tests for AzuraCast Duplicate Detection

This directory contains live integration tests for the AzuraCast duplicate detection feature (Phase 3.2).

## Overview

These tests verify the duplicate detection system against **actual live servers**:
- **Subsonic server** (or compatible: Navidrome, Airsonic, etc.)
- **AzuraCast server** with API access

⚠️ **WARNING**: These tests will upload and delete actual files on your AzuraCast server. Use a test station or dedicated environment.

## Test Coverage

### T013-T014: Upload and Duplicate Detection (`test_azuracast_live.py`)
- Initial upload of 10 tracks to AzuraCast
- Duplicate detection on second run (0 uploads expected)
- API connectivity validation
- File list retrieval

### T015: Metadata Normalization (`test_normalization_live.py`)
- "The" prefix removal (The Beatles → Beatles)
- feat./ft. notation normalization
- Special character handling (AC/DC → AC-DC)
- Case-insensitive matching
- MusicBrainz ID priority

### T016: ReplayGain Preservation (`test_replaygain_live.py`)
- Track with ReplayGain NOT re-uploaded
- Original ReplayGain values preserved
- ReplayGain detection across formats (MP3, FLAC, OGG, M4A)
- Partial ReplayGain metadata handling

### T017: Performance Benchmarks (`test_performance_live.py`)
- 100-track duplicate detection in <5 seconds
- Cache hit performance (<2 seconds)
- Cache miss performance (<5 seconds)
- Memory usage validation
- API call efficiency
- Scalability testing (10, 50, 100, 200, 500 tracks)

### T018: Subsonic Connectivity (`test_subsonic_live.py`)
- Server connectivity and authentication
- Playlist retrieval
- Track metadata completeness
- Audio file download
- Metadata diversity analysis

## Prerequisites

### 1. Environment Setup

Create a `.env` file in the project root with your server credentials:

```bash
# Required - Subsonic Server
SUBSONIC_HOST=https://your-subsonic-server.com
SUBSONIC_USER=your_username
SUBSONIC_PASSWORD=your_password
SUBSONIC_PLAYLIST_NAME=TestPlaylist_DuplicateDetection

# Required - AzuraCast Server
AZURACAST_HOST=https://your-azuracast-server.com
AZURACAST_API_KEY=your_api_key_here
AZURACAST_STATION_ID=1

# Optional - Test Configuration
TEST_TRACK_COUNT=10
LOG_LEVEL=INFO
```

### 2. Subsonic Test Playlist

Create a playlist named `TestPlaylist_DuplicateDetection` (or your configured name) with at least 10 diverse tracks:

**Required Track Variations** (for normalization testing):
1. Artist with "The" prefix (e.g., "The Beatles - Hey Jude")
2. Artist with "feat." notation (e.g., "Daft Punk feat. Pharrell Williams")
3. Special characters in title (e.g., "AC/DC - Back In Black")
4. Title with parentheses (e.g., "Song Name (Live Version)")
5. Track with MusicBrainz ID present
6. Track WITHOUT MusicBrainz ID
7. Artist with ampersand (e.g., "Simon & Garfunkel")
8. Multi-word artist (case sensitivity test)
9. Track with ReplayGain metadata
10. Track with forward slash in title (e.g., "Artist/Track")

### 3. AzuraCast Permissions

Ensure your API key has permissions for:
- File upload
- File deletion
- File listing
- Playlist management

## Running the Tests

### Run All Integration Tests

```bash
pytest tests/integration/ -m integration --no-cov
```

### Run Specific Test Suites

```bash
# T013-T014: Upload and duplicate detection
pytest tests/integration/test_azuracast_live.py -v --no-cov

# T015: Normalization
pytest tests/integration/test_normalization_live.py -v --no-cov

# T016: ReplayGain
pytest tests/integration/test_replaygain_live.py -v --no-cov

# T017: Performance (slow)
pytest tests/integration/test_performance_live.py -v --no-cov -m slow

# T018: Subsonic connectivity
pytest tests/integration/test_subsonic_live.py -v --no-cov
```

### Run Without Slow Tests

```bash
pytest tests/integration/ -m "integration and not slow" --no-cov
```

### Skip Tests if Servers Not Configured

Tests will automatically skip if environment variables are not set:

```bash
pytest tests/integration/ --no-cov
# Output: SKIPPED [X] Subsonic server not configured (SUBSONIC_HOST not set)
```

### Run Cleanup Only

```bash
pytest tests/integration/test_azuracast_live.py::test_manual_cleanup -m cleanup --no-cov
```

## Test Markers

- `@pytest.mark.integration` - Requires live servers
- `@pytest.mark.slow` - Long-running test (>5 seconds)
- `@pytest.mark.cleanup` - Cleanup operation only

### Deselect Markers

```bash
# Skip slow tests
pytest tests/integration/ -m "not slow" --no-cov

# Skip integration tests (run unit tests only)
pytest -m "not integration" --no-cov
```

## Expected Results

### Successful Test Run

```
tests/integration/test_azuracast_live.py::test_azuracast_api_connectivity PASSED
tests/integration/test_azuracast_live.py::test_t013_initial_upload PASSED
tests/integration/test_azuracast_live.py::test_t014_duplicate_detection PASSED

tests/integration/test_subsonic_live.py::test_t018_subsonic_connectivity PASSED
tests/integration/test_subsonic_live.py::test_subsonic_get_playlists PASSED

======================== X passed, Y skipped in Z.ZZs =========================
```

### Tests Skipped (No Servers)

```
tests/integration/test_azuracast_live.py::test_azuracast_api_connectivity SKIPPED
tests/integration/test_subsonic_live.py::test_t018_subsonic_connectivity SKIPPED

Reason: Subsonic server not configured (SUBSONIC_HOST not set)
```

## Cleanup

Tests are designed to clean up after themselves:

1. **Automatic cleanup**: The `cleanup_uploaded_files` fixture deletes uploaded tracks after module tests complete
2. **Manual cleanup**: Run the cleanup test if needed:
   ```bash
   pytest tests/integration/test_azuracast_live.py::test_manual_cleanup -m cleanup --no-cov
   ```

## Performance Expectations

| Test | Expected Time | Success Criteria |
|------|---------------|------------------|
| T013: Initial upload (10 tracks) | ~2-3 minutes | All tracks uploaded |
| T014: Duplicate detection (10 tracks) | <2 seconds (cache hit) | 0 uploads |
| T015: Normalization tests | <5 seconds | All rules pass |
| T016: ReplayGain tests | <10 seconds | Values preserved |
| T017: 100-track performance | <5 seconds | >20 tracks/s throughput |
| T018: Subsonic connectivity | <5 seconds | All metadata present |

## Troubleshooting

### Tests Fail with "Connection refused"

**Issue**: Cannot connect to Subsonic or AzuraCast server

**Solutions**:
- Verify server URLs in `.env` are correct and accessible
- Check firewall/network connectivity
- Test with `curl`:
  ```bash
  curl "${SUBSONIC_HOST}/rest/ping"
  curl -H "X-API-Key: ${AZURACAST_API_KEY}" "${AZURACAST_HOST}/api/station/${AZURACAST_STATION_ID}"
  ```

### Tests Fail with "Authentication failed"

**Issue**: Invalid credentials

**Solutions**:
- Verify username/password for Subsonic
- Verify API key for AzuraCast
- Check that user has required permissions

### Tests Fail with "Playlist not found"

**Issue**: Test playlist doesn't exist

**Solutions**:
- Create playlist in Subsonic with name matching `SUBSONIC_PLAYLIST_NAME`
- Ensure playlist has at least 10 tracks
- Verify playlist is accessible to the configured user

### Duplicate Detection Not Working

**Issue**: Tracks re-uploaded on second run

**Solutions**:
- Check logs for "duplicate - identical metadata" messages
- Verify cache is working: `ls -la ~/.cache/emby-to-m3u/`
- Clear cache and retry: `rm -rf ~/.cache/emby-to-m3u/`
- Enable debug logging: `LOG_LEVEL=DEBUG pytest ...`

### Performance Tests Too Slow

**Issue**: Tests exceed time limits

**Solutions**:
- Check network latency to servers: `ping ${AZURACAST_HOST}`
- Verify cache is being utilized (check logs for API call counts)
- Consider using local/LAN servers for faster tests
- Increase timeout limits for remote servers

## CI/CD Integration

To run integration tests in CI/CD pipelines:

### GitHub Actions Example

```yaml
name: Integration Tests

on: [push, pull_request]

jobs:
  integration:
    runs-on: ubuntu-latest
    if: ${{ github.event_name == 'pull_request' }}

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.13'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Create .env file
        env:
          SUBSONIC_HOST: ${{ secrets.SUBSONIC_HOST }}
          SUBSONIC_USER: ${{ secrets.SUBSONIC_USER }}
          SUBSONIC_PASSWORD: ${{ secrets.SUBSONIC_PASSWORD }}
          AZURACAST_HOST: ${{ secrets.AZURACAST_HOST }}
          AZURACAST_API_KEY: ${{ secrets.AZURACAST_API_KEY }}
          AZURACAST_STATION_ID: ${{ secrets.AZURACAST_STATION_ID }}
        run: |
          echo "SUBSONIC_HOST=${SUBSONIC_HOST}" >> .env
          echo "SUBSONIC_USER=${SUBSONIC_USER}" >> .env
          echo "SUBSONIC_PASSWORD=${SUBSONIC_PASSWORD}" >> .env
          echo "AZURACAST_HOST=${AZURACAST_HOST}" >> .env
          echo "AZURACAST_API_KEY=${AZURACAST_API_KEY}" >> .env
          echo "AZURACAST_STATION_ID=${AZURACAST_STATION_ID}" >> .env

      - name: Run integration tests
        run: pytest tests/integration/ -m integration --no-cov -v
```

### Skip in CI if Secrets Not Available

```bash
# Tests will auto-skip if environment not configured
pytest tests/integration/ -m integration --no-cov
```

## Development Notes

### Adding New Integration Tests

1. Create test file in `tests/integration/`
2. Add `@pytest.mark.integration` decorator
3. Use `skip_if_no_servers` fixture
4. Document expected behavior and success criteria
5. Add cleanup logic if uploading files

### Test Isolation

- Use session-scoped fixtures for server connections
- Module-scoped cleanup for uploaded files
- Function-scoped tests for individual validations

### Performance Testing

- Mark slow tests with `@pytest.mark.slow`
- Use `@pytest.mark.parametrize` for scalability tests
- Document performance expectations in test docstrings

## References

- [Quickstart Test Workflow](../../specs/002-fix-azuracast-duplicate/quickstart.md)
- [Phase 3.2 Specification](../../specs/002-fix-azuracast-duplicate/)
- [Subsonic API Documentation](http://www.subsonic.org/pages/api.jsp)
- [AzuraCast API Documentation](https://www.azuracast.com/docs/developers/apis/)
