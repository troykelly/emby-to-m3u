# AzuraCast Duplicate Detection - Quickstart Test Workflow

## Overview

This workflow validates the AzuraCast duplicate detection feature end-to-end using **LIVE servers**. Uploading and deleting test files is **PERMITTED and EXPECTED**.

**Duration**: ~15-20 minutes
**Test Type**: Live integration testing (no mocks)

---

## 1. Prerequisites

### Environment Variables

Create `.env` file in project root:

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

### Validation Commands

```bash
# Verify Subsonic connectivity
curl -u "${SUBSONIC_USER}:${SUBSONIC_PASSWORD}" \
  "${SUBSONIC_HOST}/rest/ping?v=1.16.1&c=test&f=json"

# Verify AzuraCast connectivity
curl -H "X-API-Key: ${AZURACAST_API_KEY}" \
  "${AZURACAST_HOST}/api/station/${AZURACAST_STATION_ID}"

# Check Python environment
python --version  # Should be 3.13+
pip install -r requirements.txt
```

### Required Access

- ✅ Subsonic server with test library containing 10+ tracks
- ✅ AzuraCast server with test station (can be existing or dedicated)
- ✅ Write permissions to upload/delete files in AzuraCast
- ✅ Python 3.13+ with all dependencies installed

---

## 2. Setup Phase

### Create Test Playlist in Subsonic

Create playlist with **10 diverse tracks** to test metadata normalization:

**Required Track Variations**:
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

### Document Expected Metadata

```bash
# Export playlist metadata for reference
python -c "
from emby_to_m3u.services.subsonic import SubsonicService
import json

subsonic = SubsonicService()
tracks = subsonic.get_playlist_tracks('${SUBSONIC_PLAYLIST_NAME}')

metadata = [{
    'title': t['title'],
    'artist': t['artist'],
    'album': t.get('album'),
    'musicbrainz_id': t.get('musicBrainzId')
} for t in tracks]

with open('test_metadata_expected.json', 'w') as f:
    json.dump(metadata, f, indent=2)

print(f'Documented {len(metadata)} tracks')
"
```

---

## 3. Initial Upload Test

### Run First Sync

```bash
# Measure upload time
time python -m emby_to_m3u.services.azuracast sync \
  --playlist "${SUBSONIC_PLAYLIST_NAME}" \
  --station "${AZURACAST_STATION_ID}" \
  --verbose

# Expected output:
# ✅ "Fetching playlist: TestPlaylist_DuplicateDetection"
# ✅ "Found 10 tracks in playlist"
# ✅ "0 of 10 tracks already in AzuraCast (cache miss - fetching from API)"
# ✅ "Uploading 10 tracks..."
# ✅ "Upload complete: 10/10 successful"
```

### Verification Commands

```bash
# Verify all tracks uploaded
curl -H "X-API-Key: ${AZURACAST_API_KEY}" \
  "${AZURACAST_HOST}/api/station/${AZURACAST_STATION_ID}/files" | \
  jq '.[] | {id, title, artist}' | tee azuracast_files_initial.json

# Count uploaded files
UPLOADED_COUNT=$(curl -s -H "X-API-Key: ${AZURACAST_API_KEY}" \
  "${AZURACAST_HOST}/api/station/${AZURACAST_STATION_ID}/files" | \
  jq '. | length')

echo "Uploaded files: ${UPLOADED_COUNT}"
# Expected: 10

# Record upload metrics
echo "Initial upload completed at $(date)" >> test_metrics.log
echo "Tracks uploaded: ${UPLOADED_COUNT}" >> test_metrics.log
```

### Success Criteria

- [ ] All 10 tracks uploaded successfully
- [ ] AzuraCast API returns 10 file IDs
- [ ] Upload time recorded in `test_metrics.log`
- [ ] No upload errors in console output

---

## 4. Duplicate Detection Test (Core Feature)

### Run Second Sync (Same Playlist)

```bash
# This should detect ALL tracks as duplicates
time python -m emby_to_m3u.services.azuracast sync \
  --playlist "${SUBSONIC_PLAYLIST_NAME}" \
  --station "${AZURACAST_STATION_ID}" \
  --verbose 2>&1 | tee duplicate_detection.log

# Expected output:
# ✅ "10 of 10 tracks already in AzuraCast (cache hit)"
# ✅ "0 of 10 tracks need upload"
# ✅ "Skipping 'Track Name' - duplicate - identical metadata"
# (repeated for all 10 tracks)
```

### Assertion Verification

```bash
# Verify zero uploads
grep -c "Uploading" duplicate_detection.log
# Expected: 0

# Verify duplicate detection count
grep "already in AzuraCast" duplicate_detection.log
# Expected: "10 of 10 tracks already in AzuraCast"

# Verify skip reasons
grep -c "duplicate - identical metadata" duplicate_detection.log
# Expected: 10

# Count API calls (should use cache)
grep -c "Fetching from AzuraCast API" duplicate_detection.log
# Expected: 0 (cache hit) or 1 (cache refresh)
```

### Performance Metrics

```bash
# Extract detection time
DETECTION_TIME=$(grep "real" duplicate_detection.log | awk '{print $2}')
echo "Duplicate detection time: ${DETECTION_TIME}" >> test_metrics.log

# Verify performance target
# Target: <2 seconds for 10 tracks (cache hit)
# Target: <5 seconds for 10 tracks (cache miss)
```

### Success Criteria

- [ ] **CRITICAL**: 0 tracks uploaded on second run
- [ ] **CRITICAL**: Log shows "10 of 10 tracks already in AzuraCast"
- [ ] **CRITICAL**: All 10 tracks show skip reason "duplicate - identical metadata"
- [ ] Detection completes in <5 seconds
- [ ] Cache utilized (0 or 1 API calls, not 10)

---

## 5. Metadata Normalization Test

### Modify Subsonic Metadata

Update playlist tracks with normalized variations:

**Test Cases**:
```bash
# Case 1: "The" prefix removal
# Original: "The Beatles - Hey Jude"
# Modified: "Beatles - Hey Jude"
# Expected: Still detected as duplicate

# Case 2: feat./ft. normalization
# Original: "Daft Punk feat. Pharrell Williams"
# Modified: "Daft Punk ft. Pharrell Williams"
# Expected: Still detected as duplicate

# Case 3: Special character normalization
# Original: "AC/DC - Back In Black"
# Modified: "AC-DC - Back In Black"
# Expected: Still detected as duplicate

# Case 4: Case insensitivity
# Original: "Simon & Garfunkel"
# Modified: "SIMON & GARFUNKEL"
# Expected: Still detected as duplicate
```

### Run Normalization Test

```bash
# After modifying metadata in Subsonic
python -m emby_to_m3u.services.azuracast sync \
  --playlist "${SUBSONIC_PLAYLIST_NAME}" \
  --station "${AZURACAST_STATION_ID}" \
  --verbose 2>&1 | tee normalization_test.log

# Expected output:
# ✅ "Normalized 'The Beatles' -> 'Beatles' for matching"
# ✅ "Normalized 'feat.' -> 'ft.' for matching"
# ✅ "10 of 10 tracks matched after normalization"
# ✅ "0 of 10 tracks need upload"
```

### Verification Commands

```bash
# Verify normalization rules applied
grep -i "normalized" normalization_test.log | head -5

# Expected patterns:
# - "The" prefix removed
# - "feat." converted to "ft."
# - Special characters normalized
# - Case-insensitive matching

# Verify zero uploads despite metadata changes
grep "need upload" normalization_test.log
# Expected: "0 of 10 tracks need upload"
```

### Success Criteria

- [ ] "The Beatles" → "Beatles" matched as duplicate
- [ ] "feat." → "ft." matched as duplicate
- [ ] Special characters normalized and matched
- [ ] Case-insensitive matching working
- [ ] **0 tracks uploaded** despite metadata variations
- [ ] Log explicitly shows normalization steps

---

## 6. ReplayGain Preservation Test

### Setup ReplayGain Test

```bash
# Identify track with ReplayGain in Subsonic
python -c "
from emby_to_m3u.services.subsonic import SubsonicService

subsonic = SubsonicService()
tracks = subsonic.get_playlist_tracks('${SUBSONIC_PLAYLIST_NAME}')

rg_track = next((t for t in tracks if 'replayGain' in t), None)
if rg_track:
    print(f\"ReplayGain track: {rg_track['title']}\")
    print(f\"ReplayGain value: {rg_track['replayGain']}\")
else:
    print(\"WARNING: No ReplayGain track found\")
"
```

### Modify ReplayGain Values

```bash
# In Subsonic, modify the ReplayGain value for the test track
# Example: Change from -6.5 dB to -7.0 dB

# Run sync
python -m emby_to_m3u.services.azuracast sync \
  --playlist "${SUBSONIC_PLAYLIST_NAME}" \
  --station "${AZURACAST_STATION_ID}" \
  --verbose 2>&1 | tee replaygain_test.log
```

### Verification

```bash
# Verify track NOT re-uploaded
grep "has ReplayGain metadata" replaygain_test.log
# Expected: "Skipping 'Track Name' - has ReplayGain metadata, preserving existing"

# Verify AzuraCast still has original ReplayGain
curl -H "X-API-Key: ${AZURACAST_API_KEY}" \
  "${AZURACAST_HOST}/api/station/${AZURACAST_STATION_ID}/file/{file_id}" | \
  jq '.replaygain_track_gain'
# Expected: Original value (e.g., -6.5), NOT modified value (-7.0)
```

### Success Criteria

- [ ] Track with ReplayGain NOT re-uploaded
- [ ] Log shows "skip - has ReplayGain metadata"
- [ ] AzuraCast preserves original ReplayGain value
- [ ] Modified source ReplayGain ignored

---

## 7. Performance Benchmark Test

### Prepare Large Test Dataset

```bash
# Create larger playlist (100 tracks) in Subsonic
# Name: TestPlaylist_Performance100

# Upload all tracks to AzuraCast (first run)
time python -m emby_to_m3u.services.azuracast sync \
  --playlist "TestPlaylist_Performance100" \
  --station "${AZURACAST_STATION_ID}" \
  --verbose 2>&1 | tee performance_initial.log
```

### Run Performance Benchmark

```bash
# Measure duplicate detection for 100 tracks
time python -m emby_to_m3u.services.azuracast sync \
  --playlist "TestPlaylist_Performance100" \
  --station "${AZURACAST_STATION_ID}" \
  --verbose 2>&1 | tee performance_benchmark.log

# Extract timing
PERF_TIME=$(grep "real" performance_benchmark.log | awk '{print $2}')
echo "100-track duplicate detection: ${PERF_TIME}" >> test_metrics.log
```

### Calculate Throughput

```bash
# Parse timing (assumes format like "0m2.345s")
SECONDS=$(echo ${PERF_TIME} | sed 's/0m//;s/s//')
THROUGHPUT=$(echo "scale=2; 100 / ${SECONDS}" | bc)

echo "Throughput: ${THROUGHPUT} tracks/second" >> test_metrics.log

# Performance targets:
# - Cache hit: >50 tracks/second (100 tracks in <2s)
# - Cache miss: >20 tracks/second (100 tracks in <5s)
```

### Success Criteria

- [ ] 100-track duplicate detection completes in <5 seconds
- [ ] Throughput >20 tracks/second
- [ ] Cache utilized (minimal API calls)
- [ ] No memory/performance issues at scale

---

## 8. Cleanup Phase

### Delete Test Tracks from AzuraCast

```bash
# List all test files
curl -H "X-API-Key: ${AZURACAST_API_KEY}" \
  "${AZURACAST_HOST}/api/station/${AZURACAST_STATION_ID}/files" | \
  jq -r '.[] | .id' > files_to_delete.txt

# Delete each file
while read FILE_ID; do
  curl -X DELETE \
    -H "X-API-Key: ${AZURACAST_API_KEY}" \
    "${AZURACAST_HOST}/api/station/${AZURACAST_STATION_ID}/file/${FILE_ID}"
  echo "Deleted file ID: ${FILE_ID}"
done < files_to_delete.txt

# Verify cleanup
REMAINING=$(curl -s -H "X-API-Key: ${AZURACAST_API_KEY}" \
  "${AZURACAST_HOST}/api/station/${AZURACAST_STATION_ID}/files" | \
  jq '. | length')

echo "Remaining files: ${REMAINING}"
# Expected: 0 (if dedicated test station)
```

### Remove Test Playlists from Subsonic

```bash
# Via Subsonic web UI:
# 1. Navigate to Playlists
# 2. Delete "TestPlaylist_DuplicateDetection"
# 3. Delete "TestPlaylist_Performance100" (if created)

# Or via API:
curl -u "${SUBSONIC_USER}:${SUBSONIC_PASSWORD}" \
  "${SUBSONIC_HOST}/rest/deletePlaylist?id=PLAYLIST_ID&v=1.16.1&c=cleanup&f=json"
```

### Success Criteria

- [ ] All test tracks deleted from AzuraCast
- [ ] Station returns to clean state (or pre-test state)
- [ ] Test playlists removed from Subsonic
- [ ] Test artifacts cleaned up (`*.log`, `*.json` files)

---

## 9. Success Criteria Checklist

### Core Functionality
- [ ] **Initial upload**: 10/10 tracks uploaded successfully
- [ ] **Duplicate detection**: 0/10 tracks uploaded on second run (100% detection)
- [ ] **Cache efficiency**: 0 or 1 API calls on duplicate detection

### Metadata Normalization
- [ ] **"The" prefix**: "The Beatles" = "Beatles" matched
- [ ] **feat. notation**: "feat." = "ft." matched
- [ ] **Special characters**: "AC/DC" = "AC-DC" matched
- [ ] **Case insensitive**: "ARTIST" = "artist" matched

### ReplayGain
- [ ] **Preservation**: Existing ReplayGain values preserved
- [ ] **Skip upload**: Track with ReplayGain not re-uploaded
- [ ] **Log verification**: "skip - has ReplayGain metadata" shown

### Performance
- [ ] **10 tracks**: Duplicate check <2 seconds (cache hit)
- [ ] **100 tracks**: Duplicate check <5 seconds
- [ ] **Throughput**: >20 tracks/second

### Cleanup
- [ ] **AzuraCast**: All test data removed
- [ ] **Subsonic**: Test playlists deleted
- [ ] **Local**: Test artifacts cleaned

---

## 10. Troubleshooting Guide

### Issue: Upload Fails

**Symptoms**: Tracks not appearing in AzuraCast

**Checks**:
```bash
# Verify API key
curl -H "X-API-Key: ${AZURACAST_API_KEY}" \
  "${AZURACAST_HOST}/api/station/${AZURACAST_STATION_ID}"
# Should return station details, not 403 Forbidden

# Verify station ID
curl -H "X-API-Key: ${AZURACAST_API_KEY}" \
  "${AZURACAST_HOST}/api/stations" | jq '.[].id'
# Check your station ID is in the list

# Check disk space
curl -H "X-API-Key: ${AZURACAST_API_KEY}" \
  "${AZURACAST_HOST}/api/admin/storage" | jq '.storage_quota'
```

**Solution**: Update `.env` with correct credentials/station ID

---

### Issue: Duplicates Not Detected

**Symptoms**: Tracks re-uploaded on second run

**Checks**:
```bash
# Check log verbosity (must be INFO or DEBUG)
echo $LOG_LEVEL
# Should be: INFO or DEBUG, not WARNING/ERROR

# Verify cache is working
ls -la ~/.cache/emby-to-m3u/azuracast_*.json
# Should show recent cache files

# Check metadata matching logic
grep "Comparing metadata" duplicate_detection.log
# Should show normalized comparison
```

**Solution**:
- Set `LOG_LEVEL=DEBUG` in `.env`
- Clear cache: `rm -rf ~/.cache/emby-to-m3u/`
- Re-run test with verbose logging

---

### Issue: Performance Slow

**Symptoms**: Detection takes >10 seconds for 100 tracks

**Checks**:
```bash
# Verify cache hits
grep "cache hit" performance_benchmark.log
# Should show cache utilized

# Check API call count
grep -c "Fetching from AzuraCast API" performance_benchmark.log
# Should be 0 (cache hit) or 1 (single refresh)

# Monitor network latency
ping -c 5 ${AZURACAST_HOST}
# Check latency to AzuraCast server
```

**Solution**:
- Ensure cache directory writable: `chmod 755 ~/.cache/emby-to-m3u/`
- Check network connection to AzuraCast
- Consider increasing cache TTL in code

---

### Issue: Cleanup Fails

**Symptoms**: Files remain in AzuraCast after deletion

**Manual Deletion**:
```bash
# Via AzuraCast Web UI:
# 1. Login to AzuraCast
# 2. Navigate to: Stations > [Your Station] > Music Files
# 3. Select all test files
# 4. Click "Delete Selected"

# Via API (force delete):
curl -X DELETE \
  -H "X-API-Key: ${AZURACAST_API_KEY}" \
  "${AZURACAST_HOST}/api/station/${AZURACAST_STATION_ID}/files" \
  -d '{"files": ["*TestPlaylist*"]}'
```

---

### Issue: Metadata Normalization Not Working

**Symptoms**: Same track uploaded twice with minor metadata differences

**Checks**:
```bash
# Enable debug logging for normalization
export DEBUG_NORMALIZE=1

# Check normalization rules
grep "Normalization rule" normalization_test.log
# Should show each rule applied

# Verify metadata comparison
python -c "
from emby_to_m3u.utils.metadata import normalize_metadata

orig = {'artist': 'The Beatles', 'title': 'Hey Jude'}
modified = {'artist': 'Beatles', 'title': 'Hey Jude'}

print(f\"Original: {normalize_metadata(orig)}\")
print(f\"Modified: {normalize_metadata(modified)}\")
print(f\"Match: {normalize_metadata(orig) == normalize_metadata(modified)}\")
"
# Should output: Match: True
```

**Solution**: Check normalization rules in `emby_to_m3u/utils/metadata.py`

---

## Test Metrics Summary

After completing all tests, generate summary report:

```bash
# Generate final report
cat << EOF > test_summary_report.md
# AzuraCast Duplicate Detection Test Report

**Date**: $(date)
**Environment**: ${AZURACAST_HOST}

## Results

### Core Functionality
- Initial upload: $(grep "Upload complete" test_metrics.log | head -1)
- Duplicate detection: $(grep "already in AzuraCast" duplicate_detection.log | head -1)

### Performance
- 10-track detection: $(grep "10-track" test_metrics.log || echo "N/A")
- 100-track detection: $(grep "100-track" test_metrics.log || echo "N/A")
- Throughput: $(grep "Throughput" test_metrics.log || echo "N/A")

### Normalization
$(grep -c "Normalized" normalization_test.log || echo "0") normalization rules applied

### Status
✅ All tests passed
$(grep -c "\[ \]" quickstart.md) remaining checklist items

## Files Generated
- duplicate_detection.log
- normalization_test.log
- performance_benchmark.log
- test_metadata_expected.json
- test_metrics.log
EOF

cat test_summary_report.md
```

---

## Quick Reference

### Essential Commands

```bash
# Initial upload
python -m emby_to_m3u.services.azuracast sync --playlist "${SUBSONIC_PLAYLIST_NAME}" --station "${AZURACAST_STATION_ID}" --verbose

# Duplicate detection test
python -m emby_to_m3u.services.azuracast sync --playlist "${SUBSONIC_PLAYLIST_NAME}" --station "${AZURACAST_STATION_ID}" --verbose 2>&1 | tee duplicate_detection.log

# Verify zero uploads
grep "need upload" duplicate_detection.log

# Check AzuraCast files
curl -H "X-API-Key: ${AZURACAST_API_KEY}" "${AZURACAST_HOST}/api/station/${AZURACAST_STATION_ID}/files" | jq '.[].title'

# Delete all test files
curl -H "X-API-Key: ${AZURACAST_API_KEY}" "${AZURACAST_HOST}/api/station/${AZURACAST_STATION_ID}/files" | jq -r '.[].id' | xargs -I {} curl -X DELETE -H "X-API-Key: ${AZURACAST_API_KEY}" "${AZURACAST_HOST}/api/station/${AZURACAST_STATION_ID}/file/{}"
```

### Expected Timeline

- **Setup**: 5 minutes
- **Initial upload**: 2-3 minutes
- **Duplicate detection**: 1 minute
- **Normalization test**: 3 minutes
- **ReplayGain test**: 2 minutes
- **Performance benchmark**: 5 minutes
- **Cleanup**: 2 minutes

**Total**: ~15-20 minutes

---

## Notes

- **LIVE TESTING**: This workflow uses real servers. Expect actual file uploads/deletions.
- **API Rate Limits**: AzuraCast may have rate limits. Add delays if encountering 429 errors.
- **Cache Behavior**: Cache TTL is 1 hour by default. Clear cache to test cold-start performance.
- **Logging**: Keep `LOG_LEVEL=INFO` for normal tests, use `DEBUG` for troubleshooting.

**🎯 Success = 100% duplicate detection rate with 0 false negatives**
