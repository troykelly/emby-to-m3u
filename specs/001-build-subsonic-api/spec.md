# Feature Specification: Subsonic API Integration for Music Library Access

**Feature Branch**: `001-build-subsonic-api`
**Created**: 2025-10-05
**Status**: Draft
**Input**: User description: "Build Subsonic API client to replace Emby integration"

## Execution Flow (main)
```
1. Parse user description from Input
   → Feature: Replace Emby integration with Subsonic API support
2. Extract key concepts from description
   → Actors: Music library users, system administrators
   → Actions: Authenticate, fetch music library, stream tracks, generate playlists
   → Data: Track metadata, authentication credentials, streaming URLs
   → Constraints: Support multiple Subsonic implementations, 1000+ tracks, 90% test coverage
3. For each unclear aspect:
   → No critical clarifications needed - requirements are comprehensive
4. Fill User Scenarios & Testing section
   → User flows: Authentication, library browsing, track streaming, playlist generation
5. Generate Functional Requirements
   → All requirements are testable and concrete
6. Identify Key Entities
   → Music tracks, authentication tokens, server configuration
7. Run Review Checklist
   → Spec contains some implementation details that need abstraction
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
- Q: When authentication credentials are invalid or a token expires during operation, how should the system respond to ongoing user requests? → A: Queue pending requests and retry authentication up to 3 times before failing
- Q: When the Subsonic server is temporarily unreachable during a library fetch operation, what should happen to already-retrieved tracks? → A: Discard all partial data and fail the entire operation
- Q: For observability and troubleshooting, what diagnostic information must the system log during Subsonic server interactions? → A: The system should honour M3U_LOG_LEVEL defaulting to B (errors plus key milestones)
- Q: When a Subsonic server connection is configured but the application also has existing Emby configuration, which music source should take precedence? → A: Subsonic always takes precedence if configured, ignoring Emby completely
- Q: When multiple tracks have identical metadata (same title, artist, album) but different unique IDs, how should the system handle this during playlist generation? → A: Keep only first occurrence; silently discard duplicates

---

## User Scenarios & Testing

### Primary User Story
As a music library administrator, I need to connect the playlist generation system to a Subsonic-compatible music server (Navidrome, Airsonic, or Gonic) so that users can automatically generate playlists from their complete music collection. When configured, Subsonic replaces Emby as the music source, allowing migration away from Emby while maintaining all existing playlist functionality.

### Acceptance Scenarios

1. **Given** a Subsonic server URL and valid credentials, **When** the system attempts authentication, **Then** the system successfully connects and retrieves an authentication token without exposing the password in requests.

2. **Given** an authenticated connection to a music server, **When** requesting the complete music library, **Then** the system retrieves all tracks with complete metadata (title, artist, album, genre, year, duration, track numbers).

3. **Given** a music library with 5000+ tracks, **When** fetching all songs, **Then** the system handles pagination automatically and retrieves the complete library within 60 seconds.

4. **Given** a valid track identifier, **When** requesting to stream or download a track, **Then** the system provides access to the audio file through the appropriate streaming endpoint.

5. **Given** track metadata from the Subsonic server, **When** generating M3U playlists, **Then** all existing playlist generation features continue to work without modification.

6. **Given** a network failure or API error, **When** making requests to the Subsonic server, **Then** the system retries with exponential backoff and provides clear error messages.

7. **Given** different Subsonic implementations (Navidrome, Airsonic, Gonic), **When** connecting to any compatible server, **Then** the system successfully retrieves and processes music data consistently.

### Edge Cases

- What happens when the music library contains 10,000+ tracks? System must handle pagination efficiently without timeouts.
- What happens when authentication fails (wrong credentials, expired token)? System must queue pending requests and retry authentication up to 3 times with existing credentials before failing with clear error messages.
- What happens when a track lacks certain metadata fields (genre, year, MusicBrainz ID)? System must gracefully handle missing optional fields.
- What happens when multiple tracks have identical metadata but different IDs? System must keep only the first occurrence and silently discard subsequent duplicates to prevent duplicate playlist entries.
- What happens when network connectivity is intermittent during library fetch? System must retry with exponential backoff, but if server remains unreachable, discard all partial data and fail the operation to ensure data consistency.
- What happens when track metadata uses different character encodings? System must handle UTF-8 and other encodings correctly.
- What happens when the server implementation returns non-standard API responses? System must validate responses and fail gracefully.

## Requirements

### Functional Requirements

- **FR-001**: System MUST authenticate with Subsonic-compatible servers using token-based authentication (salted password hash) to avoid transmitting passwords in clear text.

- **FR-002**: System MUST support configuration through environment variables for server URL, username, password, client identifier, and API version. System MUST respect existing M3U_LOG_LEVEL environment variable for controlling diagnostic logging verbosity, defaulting to errors plus key operational milestones (connection events, library fetch completion, track streaming initiation).

- **FR-003**: System MUST retrieve the complete music library from connected Subsonic servers, including all track metadata.

- **FR-016**: System MUST log diagnostic information according to configured M3U_LOG_LEVEL, including at minimum: fatal errors (authentication failures, connection refused), connection lifecycle events (start, success, failure), library fetch operations (start, progress, completion), and track streaming requests (initiation, success, failure).

- **FR-004**: System MUST transform Subsonic API metadata to the existing internal track format without data loss for essential fields (title, artist, album, genre, duration, track numbers, year, premiere date). When multiple tracks have identical metadata (title, artist, album) but different unique IDs, system MUST keep only the first occurrence and silently discard duplicates to prevent duplicate entries in playlists.

- **FR-005**: System MUST handle music libraries containing 1000+ tracks through automatic pagination without manual intervention.

- **FR-006**: System MUST provide streaming and download capabilities for individual tracks using their unique identifiers.

- **FR-007**: System MUST implement retry logic with exponential backoff for network failures and transient API errors to ensure reliability. If server becomes unreachable during library fetch, system MUST discard partial data and fail the entire operation to maintain data consistency.

- **FR-008**: System MUST support multiple Subsonic implementations (Navidrome, Airsonic, Gonic) through standard API compliance.

- **FR-009**: System MUST maintain backward compatibility with existing track model structure so that Last.fm, AzuraCast, ReplayGain, and playlist generation modules continue working without changes.

- **FR-017**: When Subsonic server configuration is present (SUBSONIC_URL environment variable set), system MUST use Subsonic as the exclusive music source, completely ignoring any existing Emby configuration. When Subsonic configuration is absent, system MUST fall back to existing Emby integration behavior.

- **FR-010**: System MUST handle error conditions gracefully, including authentication failures (401), resource not found (404), and network timeouts, providing clear error messages. When authentication expires during operation, system MUST queue pending requests and retry authentication up to 3 times before failing.

- **FR-011**: System MUST convert Subsonic-specific genre strings to array format as expected by the existing track model.

- **FR-012**: System MUST convert Subsonic duration values (seconds) to internal tick format (multiply by 10,000,000) for time calculations.

- **FR-013**: System MUST preserve MusicBrainz identifiers from Subsonic metadata for music metadata enrichment.

- **FR-014**: System MUST achieve 90% or higher code coverage through automated testing to ensure reliability.

- **FR-015**: System MUST complete fetching 5000 tracks within 60 seconds to ensure acceptable performance for large libraries.

### Key Entities

- **Music Track**: Represents a single audio file with metadata including unique identifier, title, artist name, album name, genre classification, track and disc numbers, production year, premiere date, runtime duration, and external provider identifiers (MusicBrainz).

- **Authentication Token**: Represents a secure authentication credential generated from username and salted password hash, used for API requests without exposing the original password.

- **Server Configuration**: Represents connection details for a Subsonic-compatible music server, including base URL, username, password, client name, and API version number.

- **Music Library**: Represents the complete collection of tracks available from the connected music server, potentially containing thousands of tracks with full metadata.

---

## Review & Acceptance Checklist

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

- [x] User description parsed
- [x] Key concepts extracted
- [x] Ambiguities marked
- [x] User scenarios defined
- [x] Requirements generated
- [x] Entities identified
- [x] Review checklist passed

---
