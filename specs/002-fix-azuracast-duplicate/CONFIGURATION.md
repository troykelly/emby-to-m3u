# AzuraCast Duplicate Detection - Configuration Guide

## Overview

This feature introduces robust duplicate detection for AzuraCast file uploads, preventing unnecessary re-uploads of tracks that already exist in your library.

## Environment Variables

### New Variables (Feature 002)

#### `AZURACAST_CACHE_TTL`
- **Type**: Integer (seconds)
- **Default**: `300` (5 minutes)
- **Description**: How long to cache the list of known tracks from AzuraCast
- **Impact**: Reduces API calls by >90% when set appropriately
- **Recommended Values**:
  - Small libraries (<500 tracks): `300` (5 minutes)
  - Medium libraries (500-2000 tracks): `600` (10 minutes)
  - Large libraries (>2000 tracks): `900` (15 minutes)

```bash
AZURACAST_CACHE_TTL=300
```

#### `AZURACAST_FORCE_REUPLOAD`
- **Type**: Boolean (`true`/`false`, `1`/`0`)
- **Default**: `false`
- **Description**: Bypass duplicate detection and force re-upload all tracks
- **Use Cases**:
  - Testing new upload logic
  - Forcing metadata updates
  - Recovering from corrupted uploads
- **Warning**: Will re-upload ALL tracks every run!

```bash
AZURACAST_FORCE_REUPLOAD=false
```

#### `AZURACAST_LEGACY_DETECTION`
- **Type**: Boolean
- **Default**: `false`
- **Description**: Use old exact string matching instead of new normalized detection
- **Use Cases**:
  - Rollback if new detection causes issues
  - Comparing old vs new behavior
  - Debugging detection mismatches
- **Note**: Legacy mode is less accurate and case-sensitive

```bash
AZURACAST_LEGACY_DETECTION=false
```

#### `AZURACAST_SKIP_REPLAYGAIN_CHECK`
- **Type**: Boolean
- **Default**: `false`
- **Description**: Skip checking for ReplayGain conflicts
- **Impact**:
  - When `true`: Always re-upload tracks even if AzuraCast has ReplayGain
  - When `false`: Preserve existing ReplayGain metadata in AzuraCast
- **Recommended**: Keep `false` to preserve existing ReplayGain analysis

```bash
AZURACAST_SKIP_REPLAYGAIN_CHECK=false
```

### Existing Variables (Unchanged)

These variables continue to work as before:

```bash
# Subsonic/Emby source server
SUBSONIC_URL=https://music.example.com
SUBSONIC_USER=your-username
SUBSONIC_PASSWORD=your-password

# AzuraCast destination server
AZURACAST_HOST=https://radio.example.com
AZURACAST_API_KEY=your-api-key-here
AZURACAST_STATIONID=1
```

## Configuration Examples

### Recommended Production Setup

```bash
# Source server (Subsonic/Emby)
SUBSONIC_URL=https://music.example.com
SUBSONIC_USER=sync-user
SUBSONIC_PASSWORD=secure-password

# Destination server (AzuraCast)
AZURACAST_HOST=https://radio.example.com
AZURACAST_API_KEY=abc123def456ghi789
AZURACAST_STATIONID=1

# New duplicate detection settings (recommended defaults)
AZURACAST_CACHE_TTL=300
AZURACAST_FORCE_REUPLOAD=false
AZURACAST_LEGACY_DETECTION=false
AZURACAST_SKIP_REPLAYGAIN_CHECK=false
```

### Large Library Optimization

For libraries with 5000+ tracks:

```bash
# Increase cache TTL to reduce API calls
AZURACAST_CACHE_TTL=900

# Keep other defaults
AZURACAST_FORCE_REUPLOAD=false
AZURACAST_LEGACY_DETECTION=false
AZURACAST_SKIP_REPLAYGAIN_CHECK=false
```

### Testing/Development Setup

For testing new features or debugging:

```bash
# Short cache for rapid testing
AZURACAST_CACHE_TTL=60

# Force reupload for testing (WARNING: uploads everything!)
AZURACAST_FORCE_REUPLOAD=true

# Use legacy detection for comparison
AZURACAST_LEGACY_DETECTION=false

# Allow ReplayGain re-analysis
AZURACAST_SKIP_REPLAYGAIN_CHECK=true
```

### Migration from Old System

If you're upgrading from the old duplicate detection:

```bash
# Phase 1: Run with legacy mode to verify no changes
AZURACAST_LEGACY_DETECTION=true
AZURACAST_FORCE_REUPLOAD=false

# Phase 2: Enable new detection (after testing)
AZURACAST_LEGACY_DETECTION=false
AZURACAST_CACHE_TTL=300

# Phase 3: Monitor logs for detection strategies
# (No config changes needed)
```

## Logging

The new detection system logs at INFO level:

```
INFO: AzuraCast initialized: cache_ttl=300s, force_reupload=False, legacy_detection=False
INFO: Uploading: No duplicate found [none]
INFO: Skipping: Duplicate found by MusicBrainz ID match [musicbrainz_id] (AzuraCast file: 12345)
INFO: Skipping: Duplicate found by normalized metadata [normalized_metadata] (AzuraCast file: 67890)
INFO: Upload complete: 5 uploaded, 95 skipped (duplicates), 0 failed out of 100 total tracks
```

## Troubleshooting

### Issue: Too many API calls (rate limiting)

**Solution**: Increase `AZURACAST_CACHE_TTL`:
```bash
AZURACAST_CACHE_TTL=600  # Increase to 10 minutes
```

### Issue: Tracks not being detected as duplicates

**Possible Causes**:
1. MusicBrainz IDs missing in source library
2. Metadata variations too extreme
3. Legacy mode enabled

**Solutions**:
```bash
# Ensure new detection is enabled
AZURACAST_LEGACY_DETECTION=false

# Check logs for detection strategies
# If seeing "No duplicate found" for known duplicates, investigate metadata
```

### Issue: Want to force re-upload specific tracks

**Solutions**:

Option 1: Delete from AzuraCast first
```bash
# Manually delete tracks in AzuraCast UI, then sync normally
AZURACAST_FORCE_REUPLOAD=false
```

Option 2: Force reupload (WARNING: reuploads ALL)
```bash
# This will reupload EVERYTHING
AZURACAST_FORCE_REUPLOAD=true
```

### Issue: ReplayGain values being overwritten

**Solution**: Ensure ReplayGain check is enabled:
```bash
AZURACAST_SKIP_REPLAYGAIN_CHECK=false
```

## Performance Tuning

### Cache TTL Guidelines

| Library Size | Recommended TTL | API Calls Saved |
|--------------|-----------------|-----------------|
| < 500 tracks | 300s (5 min) | ~95% |
| 500-2000 tracks | 600s (10 min) | ~97% |
| 2000-5000 tracks | 900s (15 min) | ~98% |
| > 5000 tracks | 1200s (20 min) | ~99% |

### Memory Usage

Cache memory scales with library size:
- ~300 bytes per track
- 1000 tracks ≈ 0.3 MB
- 10000 tracks ≈ 3 MB
- Well under 10MB for typical libraries

## Best Practices

1. **Start with defaults**: The default configuration works well for most users
2. **Monitor first run**: Watch logs to understand detection behavior
3. **Tune cache gradually**: Increase TTL if you see rate limiting
4. **Keep legacy mode off**: New detection is more accurate
5. **Preserve ReplayGain**: Keep `SKIP_REPLAYGAIN_CHECK=false`
6. **Test before production**: Use a test station first

## Support

For issues or questions:
- Check IMPLEMENTATION_STATUS.md for known limitations
- Review logs at INFO level for detection decisions
- Open an issue on GitHub with:
  - Environment configuration (redact credentials!)
  - Relevant log excerpts
  - Library size and metadata characteristics
