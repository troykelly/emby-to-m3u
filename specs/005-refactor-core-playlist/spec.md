# Feature Specification: AI/ML-Powered Playlist Generation with Station Identity Context

**Feature Branch**: `005-refactor-core-playlist`
**Created**: 2025-10-06
**Status**: Draft
**Input**: User description: "Refactor core playlist generation to use AI/ML playlist generator with station-identity.md context for Production City Radio programming"

## Execution Flow (main)
```
1. Parse user description from Input
   → Extract: AI/ML integration, station-identity.md context, Production City Radio programming
2. Extract key concepts from description
   → Actors: Radio programmers, AI/ML playlist generator, music library
   → Actions: Generate playlists, apply station programming rules, select tracks
   → Data: Station identity document, track metadata, daypart specifications
   → Constraints: Programming rules, BPM ranges, genre mix, Australian content requirements
3. For each unclear aspect:
   → [RESOLVED] Testing environment: Live against defined endpoints with environment keys
   → [RESOLVED] Station context: Use station-identity.md for programming rules
4. Fill User Scenarios & Testing section
   → Primary flow: Load station identity → Generate daypart playlists → Validate against rules
5. Generate Functional Requirements
   → Each requirement is testable against station-identity.md specifications
6. Identify Key Entities
   → Station Identity, Daypart, Playlist, Track Selection Criteria
7. Run Review Checklist
   → No implementation details included
   → All requirements testable
8. Return: SUCCESS (spec ready for planning)
```

---

## ⚡ Quick Guidelines
- ✅ Focus on WHAT the system needs to do for Production City Radio
- ❌ Avoid HOW to implement (no tech stack, APIs, code structure)
- 👥 Written for radio programming stakeholders, not developers

---

## Clarifications

### Session 2025-10-06
- Q: When the music library lacks sufficient tracks to meet daypart criteria (e.g., only 10 Australian electronic tracks exist but 30 are needed for a 2-hour specialty show), how should the system respond? → A: Relax constraints progressively (e.g., expand BPM range ±10) until sufficient tracks found
- Q: What is the acceptable variance percentage for genre distribution compliance (FR-022)? For example, if a daypart specifies "25% Contemporary Alternative," what deviation is acceptable before flagging non-compliance? → A: ±10% tolerance (15-35% acceptable for 25% target)
- Q: When track BPM or other critical metadata is missing from the music library, what should the system do? → A: Data should be retrieved (and cached permanently) from LastFM and if it still unavailable use aubio
- Q: When generating multiple playlists with a total cost budget (FR-009), how should the budget be distributed across playlists? → A: Total cost budget configurable as hard or suggested (with warnings). Hard limit uses dynamic allocation. Both configurable via environment variables, defaulting to suggested and dynamic
- Q: What happens if station-identity.md is updated with new programming rules while playlists are being generated? → A: Lock station-identity.md during generation to prevent concurrent updates

---

## User Scenarios & Testing *(mandatory)*

### Primary User Story
As a Production City Radio programming director, I need the playlist generator to automatically create hour-by-hour playlists that match our station identity programming document, so that our music selection maintains consistent quality, adheres to regulatory requirements (30% Australian content), and serves our target demographic of creative industry professionals with appropriate genre mixes, BPM ranges, and daypart-specific energy levels.

### Acceptance Scenarios

1. **Given** the station-identity.md document is loaded, **When** generating a "Morning Drive: Production Call (6:00 AM - 10:00 AM)" playlist, **Then** the system produces a playlist with:
   - 12-14 songs per hour with BPM progression 90-115 (6-7 AM) → 110-135 (7-9 AM) → 100-120 (9-10 AM)
   - Genre mix: 25% Contemporary Alternative, 20% Electronic/Downtempo, 20% Quality Pop/R&B, 15% Global Sounds, 10% Jazz/Neo-Soul
   - Minimum 30% Australian artists
   - Era mix: 40% current (0-2 years), 35% recent (2-5 years), 20% modern classics (5-10 years), 5% throwbacks (10-20 years)
   - Uplifting, positive mood with strong intros suitable for drive time

2. **Given** multiple daypart specifications exist in station-identity.md, **When** generating playlists for a full broadcast day, **Then** the system creates distinct playlists for each daypart (Morning Drive, Midday Session, Afternoon Drive, Evening, Late Night) with appropriate:
   - BPM ranges specific to the time of day
   - Genre distributions matching daypart requirements
   - Talk/music ratios (e.g., minimal talk during Midday, more features during Drive times)
   - Rotation strategies (Power/Medium/Light rotation percentages)

3. **Given** the AI/ML playlist generator has access to the music library via existing endpoints, **When** selecting tracks for a playlist, **Then** the system:
   - Queries available tracks from Subsonic/Emby API
   - Applies selection criteria from the relevant daypart specification
   - Validates track metadata (BPM, genre, year, country) against requirements
   - Provides reasoning for each track selection aligned with station programming goals

4. **Given** a daypart specification includes specialty programming (e.g., "Wednesday: Australian Spotlight 7-9 PM - 100% Australian artists"), **When** generating that specialty playlist, **Then** the system:
   - Selects only tracks from Australian artists
   - Maintains appropriate BPM and genre diversity within the Australian catalog
   - Documents the specialty programming constraint in the playlist metadata

5. **Given** the Australian content requirement is 30% minimum, **When** validating any generated playlist, **Then** the system:
   - Calculates the percentage of Australian tracks
   - Flags playlists below 30% as non-compliant
   - Provides Australian artist alternatives when needed to meet quota

### Edge Cases
- When the music library doesn't have enough tracks matching a specific daypart's criteria (e.g., insufficient Australian electronic tracks with BPM 115-130), the system progressively relaxes constraints (e.g., expand BPM range ±10, then ±15) until sufficient tracks are found, logging each relaxation step
- How does the system handle conflicting requirements (e.g., a specialty show requiring 100% jazz when the library has limited jazz tracks meeting BPM requirements)?
- The system locks station-identity.md during playlist generation to prevent concurrent updates, ensuring consistency across all playlists in a batch; new programming rules apply only to subsequent generation runs after lock release
- How does the system ensure no song repeats within a 5-hour daypart (e.g., Midday requirement: "no-repeat workday" experience)?
- When BPM or other critical metadata is missing for tracks, the system retrieves data from Last.fm API and caches permanently; if still unavailable, analyzes audio using aubio-tools to extract BPM and caches the result

## Requirements *(mandatory)*

### Functional Requirements

#### Station Identity Integration
- **FR-001**: System MUST load and parse station-identity.md to extract all daypart specifications including name, time range, BPM progression, genre mix percentages, era distribution, mood/energy guidelines, and content focus
- **FR-002**: System MUST support multiple programming structures (Monday-Friday, Weekend Saturday/Sunday) with distinct daypart definitions for each schedule
- **FR-003**: System MUST extract and enforce rotation strategy categories (Power Rotation 60-70 spins/week, Medium Rotation 35 spins/week, Light Rotation 10-14 spins/week, Recurrent, Library/Gold)
- **FR-004**: System MUST recognize specialty programming constraints (e.g., 100% Australian, 100% Electronic, theme-based hours) and generate playlists accordingly
- **FR-031**: System MUST acquire an exclusive lock on station-identity.md at the start of playlist generation batch and release lock upon completion, preventing concurrent modifications during generation to ensure consistency across all playlists

#### AI/ML Playlist Generation
- **FR-005**: System MUST use AI/ML capabilities to select tracks that match daypart criteria with explainable reasoning for each selection
- **FR-006**: System MUST generate playlists that satisfy multiple concurrent constraints (BPM range, genre mix, era distribution, Australian content, mood/energy, rotation category)
- **FR-007**: System MUST provide selection reasoning for each track that references station programming objectives (e.g., "Selected for Morning Drive energy level and positive lyrical content")
- **FR-008**: System MUST generate target track count based on daypart duration and tracks-per-hour specification (e.g., 12-14 songs/hour for Morning Drive = 48-56 tracks for 4-hour show)
- **FR-009**: System MUST implement cost controls for LLM API usage with configurable total budget mode (hard limit or suggested with warnings) and allocation strategy (dynamic based on complexity or equal distribution), both configurable via environment variables with defaults: suggested budget mode and dynamic allocation
- **FR-030**: System MUST dynamically allocate budget across playlists when hard limit mode is enabled, adjusting per-playlist cost based on playlist complexity and constraint satisfaction requirements; MUST warn operators when suggested budget mode is exceeded but continue generation

#### Track Selection & Validation
- **FR-010**: System MUST query music library (via existing Subsonic/Emby endpoints) to retrieve available tracks with metadata (title, artist, album, BPM, genre, year, country)
- **FR-011**: System MUST validate track metadata against daypart requirements before inclusion in playlist
- **FR-012**: System MUST enforce no-repeat rules within specified time windows (e.g., no song repeats in 5-hour Midday block)
- **FR-013**: System MUST calculate and enforce Australian content percentage (minimum 30%) across all playlists
- **FR-014**: System MUST support BPM progression requirements (e.g., Morning Drive: 90-115 → 110-135 → 100-120 over 4 hours)
- **FR-015**: System MUST apply mood/energy filters (e.g., exclude melancholy ballads from Morning Drive, avoid aggressive tracks during Midday)
- **FR-028**: System MUST implement progressive constraint relaxation when insufficient tracks are available (expand BPM range in ±10 BPM increments, then relax genre/era constraints), logging each relaxation step in decision log
- **FR-029**: System MUST retrieve missing track metadata (BPM, genre, etc.) from Last.fm API and cache permanently; if unavailable from Last.fm, MUST analyze audio files using aubio-tools to extract BPM and other audio features, caching results for future use

#### Playlist Output & Integration
- **FR-016**: System MUST generate playlists in M3U format compatible with existing AzuraCast sync workflow
- **FR-017**: System MUST generate playlist metadata files containing validation results (constraint satisfaction scores, BPM variance, energy progression, genre diversity)
- **FR-018**: System MUST create decision logs documenting AI selection reasoning, track criteria, validation results, and cost metrics for audit purposes
- **FR-019**: System MUST integrate with existing reporting system to generate Markdown and PDF reports of playlist generation

#### Regulatory & Programming Compliance
- **FR-020**: System MUST enforce 30-35% Australian content minimum as specified in station-identity.md
- **FR-021**: System MUST track and report compliance with rotation strategies (Power/Medium/Light spin frequencies)
- **FR-022**: System MUST validate genre distribution percentages match daypart specifications with ±10% tolerance (e.g., 25% target allows 15-35% range)
- **FR-023**: System MUST ensure era distribution compliance with specified targets (e.g., Current 40%, Recent 35%, Modern Classics 20%, Throwbacks 5%) with ±10% tolerance

#### Testing & Validation
- **FR-024**: System MUST support live testing against configured Subsonic/Emby endpoints using environment-provided credentials
- **FR-025**: System MUST validate generated playlists against station-identity.md criteria and produce compliance reports
- **FR-026**: System MUST calculate and report quality metrics: constraint satisfaction score, BPM variance, energy progression coherence, genre diversity index
- **FR-027**: System MUST log all AI decision-making with sufficient detail to reproduce or audit track selection

### Key Entities *(include if feature involves data)*

- **Station Identity Document**: Comprehensive programming guide containing daypart specifications, genre distributions, BPM ranges, rotation strategies, content focus, and brand positioning for Production City Radio. Serves as the authoritative source for all playlist generation rules.

- **Daypart Specification**: Time-bound programming segment (e.g., "Morning Drive 6-10 AM") with specific requirements including:
  - Time range and target demographic
  - BPM progression over the daypart duration
  - Genre mix percentages
  - Era distribution targets
  - Mood/energy guidelines
  - Content focus and features
  - Rotation strategy percentages
  - Tracks per hour target

- **Playlist Specification**: Generated from daypart specification, containing:
  - Unique identifier and name
  - Target track count based on duration
  - Track selection criteria (BPM range, genre mix, era distribution, Australian content minimum, energy flow)
  - Reference to source daypart
  - Cost budget allocation

- **Track Selection Criteria**: Constraints derived from daypart specification used by AI/ML to select tracks:
  - BPM range with tolerance
  - Genre mix percentages with tolerance
  - Era distribution targets with tolerance
  - Australian content minimum percentage
  - Energy flow requirements (uplifting, contemplative, varied, etc.)
  - Mood filters (exclude types: melancholy, aggressive, etc.)

- **Selected Track**: Individual track chosen by AI/ML for inclusion in playlist, containing:
  - Track metadata (ID, title, artist, album, BPM, genre, year, country, duration)
  - Position in playlist
  - Selection reasoning provided by AI/ML
  - Validation status against criteria

- **Playlist**: Complete generated playlist with:
  - Unique identifier and name
  - List of selected tracks in playback order
  - Reference to source playlist specification
  - Validation results (constraint scores, flow metrics, gap analysis)
  - Creation timestamp and cost metrics

- **Validation Result**: Assessment of playlist compliance with station identity requirements:
  - Constraint satisfaction scores (BPM, genre, era, Australian content)
  - Flow quality metrics (BPM variance, energy progression, genre diversity)
  - Gap analysis identifying deficiencies
  - Pass/fail status

- **Decision Log**: Audit trail of AI/ML selection process including:
  - Decision type (track selection, validation, error)
  - Playlist name and criteria
  - Selected tracks with reasoning
  - Validation results
  - Cost and execution time metadata
  - Error details if applicable

---

## Review & Acceptance Checklist
*GATE: Automated checks run during main() execution*

### Content Quality
- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs (Production City Radio programming compliance)
- [x] Written for non-technical stakeholders (radio programming directors)
- [x] All mandatory sections completed

### Requirement Completeness
- [x] No [NEEDS CLARIFICATION] markers remain (all clarified in Session 2025-10-06)
- [x] Requirements are testable and unambiguous (can validate against station-identity.md)
- [x] Success criteria are measurable (BPM ranges, genre percentages, Australian content %)
- [x] Scope is clearly bounded (refactor playlist generation to use AI/ML with station identity)
- [x] Dependencies and assumptions identified (existing Subsonic/Emby endpoints, station-identity.md format)

---

## Execution Status
*Updated by main() during processing*

- [x] User description parsed
- [x] Key concepts extracted (AI/ML integration, station identity context, daypart programming)
- [x] Ambiguities marked (all clarified in Session 2025-10-06)
- [x] User scenarios defined (5 scenarios with Production City Radio examples)
- [x] Requirements generated (31 functional requirements including clarifications)
- [x] Entities identified (8 key entities)
- [x] Review checklist passed (all clarifications resolved)

---

## Notes for Planning Phase

1. **Integration with Existing System**: This refactor should preserve existing M3U generation, AzuraCast sync, and reporting capabilities while replacing manual playlist logic with AI/ML-driven track selection using station-identity.md context.

2. **Live Testing Environment**: Testing will be conducted against actual Subsonic/Emby endpoints using credentials from environment variables (SUBSONIC_URL, SUBSONIC_USER, SUBSONIC_PASSWORD). Ensure test suite can validate against real music library data.

3. **Station Identity as Programming Source**: The station-identity.md file becomes the single source of truth for programming rules. File locking must be implemented to prevent concurrent modifications during generation (FR-031).

4. **Cost Management**: AI/ML usage requires configurable cost controls via environment variables - budget mode (hard/suggested, default: suggested) and allocation strategy (dynamic/equal, default: dynamic). See FR-009 and FR-030.

5. **Metadata Enhancement**: System must retrieve missing track metadata from Last.fm API with permanent caching, falling back to aubio-tools audio analysis when Last.fm data unavailable (FR-029). Ensure aubio-tools is available in deployment environment.
