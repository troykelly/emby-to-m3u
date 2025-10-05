# Feature Specification: Robust AzuraCast File Deduplication and Selective Upload

**Feature Branch**: `002-fix-azuracast-duplicate`
**Created**: 2025-10-05
**Status**: Draft
**Input**: User description: "Fix AzuraCast duplicate detection and selective upload logic"

## Execution Flow (main)
```
1. Parse user description from Input
   → Feature identified: Fix duplicate detection in AzuraCast upload process
2. Extract key concepts from description
   → Actors: System administrator, automated sync process
   → Actions: Upload tracks, detect duplicates, skip existing files
   → Data: Track metadata (artist, album, title, MusicBrainz ID, duration)
   → Constraints: Avoid re-uploading existing files, handle metadata variations
3. For each unclear aspect:
   → All aspects clearly specified in requirements
4. Fill User Scenarios & Testing section
   → Primary scenario: Sync library without duplicate uploads
5. Generate Functional Requirements
   → 21 testable requirements identified
6. Identify Key Entities
   → Track, Metadata, Cache, Upload Session
7. Run Review Checklist
   → No [NEEDS CLARIFICATION] markers
   → No implementation details in requirements
8. Return: SUCCESS (spec ready for planning)
```

---

## ⚡ Quick Guidelines
- ✅ Focus on WHAT users need and WHY
- ❌ Avoid HOW to implement (no tech stack, APIs, code structure)
- 👥 Written for business stakeholders, not developers

---

## Clarifications

### Session 2025-10-05
- Q: When a track exists in AzuraCast with ReplayGain metadata but the source system has DIFFERENT ReplayGain values, what should happen? → A: Skip upload - preserve existing AzuraCast ReplayGain values
- Q: If the sync process is interrupted mid-upload (network failure, crash), what should happen on the next run? → A: Restart fresh - re-evaluate all tracks from beginning
- Q: When multiple tracks in the source library are detected as duplicates of the SAME AzuraCast track, what should happen? → A: Upload none - log warning about source duplicates
- Q: When the AzuraCast API returns a rate limit error during upload, what should the system do? → A: Retry with exponential backoff - respect rate limits
- Q: What logging verbosity level should be used for duplicate detection decisions by default? → A: info

---

## User Scenarios & Testing *(mandatory)*

### Primary User Story
A system administrator configures the music library sync service to upload tracks from their media server (Emby/Subsonic) to AzuraCast. When running the sync process multiple times, the system should intelligently detect which files already exist in AzuraCast and skip them, uploading only new or changed files. This prevents wasting bandwidth, time, and potentially hitting API rate limits, while ensuring the AzuraCast library stays current.

### Acceptance Scenarios

1. **Given** a library with 100 tracks already uploaded to AzuraCast, **When** the sync process runs a second time with the same library, **Then** the system detects all 100 tracks as duplicates and uploads 0 files

2. **Given** a track exists in AzuraCast with metadata "The Beatles - Abbey Road - Come Together", **When** the sync process encounters the same track with metadata "Beatles - Abbey Road - Come Together" (missing "The" prefix), **Then** the system recognizes them as the same track and skips upload

3. **Given** a track exists in both systems with identical artist/album/title but different durations (180 seconds vs 186 seconds), **When** the sync process evaluates this track, **Then** the system logs a warning about duration mismatch but still recognizes it as a duplicate

4. **Given** two tracks with identical metadata but different MusicBrainz IDs, **When** the sync process evaluates them, **Then** the system treats them as different tracks and uploads both

5. **Given** a track with metadata "Artist feat. Guest" in one system and "Artist ft. Guest" in another, **When** the sync process compares them, **Then** the system normalizes both formats and recognizes them as the same track

6. **Given** a library of 1000 tracks being synced, **When** the process checks for duplicates, **Then** the entire duplicate detection completes in under 30 seconds

7. **Given** a track exists in AzuraCast without ReplayGain metadata and the source has ReplayGain data, **When** the sync process evaluates this track, **Then** the system identifies it needs to be re-uploaded to add ReplayGain information

11. **Given** a track exists in AzuraCast with ReplayGain metadata and the source has different ReplayGain values, **When** the sync process evaluates this track, **Then** the system skips upload and preserves existing AzuraCast ReplayGain values

12. **Given** the source library contains three tracks that all match the same AzuraCast track as duplicates, **When** the sync process evaluates them, **Then** the system skips upload for all three source tracks and logs a warning identifying the source duplicates

13. **Given** the AzuraCast API returns a rate limit error during track upload, **When** the system encounters this error, **Then** the system retries the upload using exponential backoff and continues with remaining tracks once successful

8. **Given** the user enables force re-upload mode, **When** the sync process runs, **Then** all tracks upload regardless of existing duplicates

9. **Given** the sync process encounters 50 new tracks and 450 duplicates in a 500-track library, **When** processing begins, **Then** the system displays "50 of 500 tracks need upload" before starting and shows skip reasons for each duplicate

10. **Given** a sync session completes, **When** the process finishes, **Then** the system displays a summary report showing counts of uploaded, skipped, and errored tracks with reasons

### Edge Cases
- What happens when a track has no MusicBrainz ID in either system?
  - System falls back to metadata-based comparison
- What happens when track metadata contains special characters like "&", "/", or parentheses?
  - System normalizes these characters before comparison to ensure consistent matching
- What happens when the AzuraCast API is temporarily unavailable during the duplicate check?
  - System logs error and treats track as needing upload (fail-safe approach)
- What happens when two tracks have identical normalized metadata but one has additional featured artists?
  - System normalizes featuring artist notation ("feat.", "ft.", "featuring") to ensure proper matching
- What happens when cache expires mid-session?
  - System re-fetches known tracks list and continues processing
- What happens when comparing tracks where one has "Artist1 & Artist2" and the other has "Artist1, Artist2"?
  - System normalizes artist separator characters before comparison
- What happens when the sync process is interrupted mid-upload (network failure, process crash)?
  - On the next run, the system restarts fresh by re-evaluating all tracks from the beginning (no resume from interruption point)
- What happens when multiple tracks in the source library are detected as duplicates of the same AzuraCast track?
  - System skips upload for all source duplicates and logs a warning identifying the duplicate tracks in the source library
- What happens when the AzuraCast API returns a rate limit error during upload?
  - System retries the upload using exponential backoff strategy to respect API rate limits before continuing with remaining tracks

## Requirements *(mandatory)*

### Functional Requirements

**Duplicate Detection Strategy**
- **FR-001**: System MUST attempt duplicate detection using multiple strategies in order of reliability: MusicBrainz ID matching first, then normalized metadata matching, then file path matching if available
- **FR-002**: System MUST normalize all text metadata before comparison by removing leading/trailing whitespace and converting to lowercase
- **FR-003**: System MUST normalize special characters in metadata by standardizing punctuation and removing non-alphanumeric characters (except spaces)
- **FR-004**: System MUST handle "The" prefix variations by treating "The Beatles" and "Beatles" as equivalent when comparing artist names
- **FR-005**: System MUST normalize featuring artist notation by treating "feat.", "ft.", and "featuring" as equivalent
- **FR-006**: System MUST normalize artist separator characters by treating "&", "and", and "," as equivalent in multi-artist fields
- **FR-007**: System MUST consider tracks with identical MusicBrainz IDs as duplicates regardless of metadata differences
- **FR-008**: System MUST consider tracks with normalized matching metadata (artist + album + title) as potential duplicates
- **FR-009**: System MUST verify duration similarity for metadata-matched duplicates, logging a warning if duration differs by more than 5 seconds but not blocking the duplicate classification
- **FR-032**: System MUST detect when multiple source library tracks are duplicates of the same AzuraCast track, skip upload for all such source duplicates, and log a warning identifying the duplicate source tracks

**Upload Decision Logic**
- **FR-010**: System MUST skip upload when a file exists in AzuraCast and has identical normalized metadata
- **FR-011**: System MUST skip upload when a file exists in AzuraCast and already has ReplayGain metadata, regardless of whether source ReplayGain values differ (existing AzuraCast values are preserved)
- **FR-012**: System MUST upload a file when it does not exist in AzuraCast based on all detection strategies
- **FR-013**: System MUST upload a file when it exists but lacks ReplayGain metadata and the source provides ReplayGain data
- **FR-014**: System MUST allow force re-upload mode that bypasses duplicate detection and uploads all files
- **FR-015**: System MUST allow legacy detection mode that uses the original comparison logic for backward compatibility

**Performance and Caching**
- **FR-016**: System MUST fetch the list of known tracks from AzuraCast only once per sync session
- **FR-017**: System MUST cache the known tracks list in memory with a timestamp for the session duration
- **FR-018**: System MUST invalidate cached track list after a configurable time period (default 5 minutes)
- **FR-019**: System MUST complete duplicate detection for a 100-track library in under 5 seconds
- **FR-020**: System MUST complete duplicate detection for a 1000-track library in under 30 seconds

**Progress Reporting**
- **FR-021**: System MUST display the count of tracks needing upload before starting the upload process (e.g., "X of Y tracks need upload")
- **FR-022**: System MUST display the skip reason for each track that is not uploaded (duplicate, has ReplayGain, etc.)
- **FR-023**: System MUST display a summary report at the end of the sync session showing counts of uploaded tracks, skipped tracks, and errors with their reasons

**Configuration and Control**
- **FR-024**: System MUST support a force re-upload configuration option that overrides duplicate detection
- **FR-025**: System MUST support a legacy detection mode configuration option that uses the original detection logic
- **FR-026**: System MUST support a configurable cache time-to-live setting
- **FR-027**: System MUST support a configuration option to skip ReplayGain verification during duplicate detection

**Accuracy and Reliability**
- **FR-028**: System MUST achieve at least 95% accuracy in detecting duplicate files with metadata variations
- **FR-029**: System MUST ensure a second sync run with an unchanged library results in zero file uploads (100% duplicate detection)
- **FR-030**: System MUST provide clear logging for each upload decision showing which detection strategy was used and why the file was uploaded or skipped, using INFO level verbosity by default
- **FR-031**: System MUST NOT persist partial upload state across sessions; interrupted sync processes restart fresh on next run by re-evaluating all tracks from the beginning
- **FR-033**: System MUST handle AzuraCast API rate limit errors by retrying uploads using exponential backoff strategy to respect rate limits before continuing with remaining tracks

### Key Entities

- **Track**: Represents a music track with metadata including artist, album, title, duration, file path, MusicBrainz ID, and ReplayGain information
- **Normalized Metadata**: A processed version of track metadata with standardized formatting used for comparison, including lowercase text, normalized special characters, and standardized artist notation
- **Known Tracks Cache**: A temporary in-memory store of tracks already present in AzuraCast, including their metadata and timestamps, used to avoid repeated API calls during a sync session
- **Upload Session**: A single execution of the sync process that encompasses fetching known tracks, evaluating all source tracks, making upload decisions, and generating summary reports
- **Upload Decision**: The outcome of duplicate detection for a single track, indicating whether to upload, skip, or flag for review, along with the reason and detection strategy used

---

## Review & Acceptance Checklist
*GATE: Automated checks run during main() execution*

### Content Quality
- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

### Requirement Completeness
- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

---

## Execution Status
*Updated by main() during processing*

- [x] User description parsed
- [x] Key concepts extracted
- [x] Ambiguities marked (none found)
- [x] User scenarios defined
- [x] Requirements generated
- [x] Entities identified
- [x] Review checklist passed

---
