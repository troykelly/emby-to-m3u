# Phase 0: Research & Technical Decisions

## OpenAI Responses API + HostedMCPTool Integration

**Decision**: Use OpenAI GPT-4o-mini via Responses API with HostedMCPTool for track selection

**Rationale**:
- Responses API supports MCP tool integration via `HostedMCPTool` for Subsonic access
- GPT-4o-mini provides cost-effective inference (<$0.50 target per execution)
- Supports structured outputs for playlist specifications
- Native retry/error handling for reliability
- Streaming support for progress reporting

**Implementation Pattern**:
```python
from openai import OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Configure Subsonic MCP as hosted tool
subsonic_mcp_tool = {
    "type": "hosted_mcp",
    "hosted_mcp": {
        "server_url": os.getenv("SUBSONIC_MCP_URL"),
        "tools": ["search_tracks", "get_genres", "search_similar", "analyze_library"]
    }
}

# LLM track selection with MCP tools
response = client.chat.completions.create(
    model="gpt-5",
    messages=[{
        "role": "user",
        "content": f"Select tracks for {daypart} matching BPM {bpm_range}, genres {genre_mix}, era {distribution}, 30-35% Australian, ordered for energy flow"
    }],
    tools=[subsonic_mcp_tool],
    tool_choice="auto"
)
```

**Alternatives Considered**:
- Anthropic Claude MCP (more complex setup, higher cost)
- Local LLM (insufficient quality for constraint satisfaction)
- Direct Subsonic API (lacks intelligent track selection logic)

**Cost Analysis**:
- GPT-4o-mini: ~$0.15 per 1M input tokens, ~$0.60 per 1M output tokens
- Estimated per-playlist: ~2K input + 1K output = ~$0.001 per playlist
- 47 playlists = ~$0.047, well under $0.50 budget

## Plain-Language Document Parsing Strategy

**Decision**: Use structured prompt parsing with regex + LLM validation

**Rationale**:
- Programming documents (station-identity.md) contain semi-structured text
- Regex extracts quantitative data (BPM ranges, percentages, time slots)
- LLM validates extracted data and fills gaps (ambiguous mood descriptions)
- Hybrid approach balances accuracy with cost

**Implementation Pattern**:
```python
import re
from dataclasses import dataclass

@dataclass
class DaypartSpec:
    name: str
    day: str
    time_range: tuple[str, str]
    bpm_progression: dict[str, tuple[int, int]]
    genre_mix: dict[str, float]
    era_distribution: dict[str, float]
    australian_min: float
    mood: str

def parse_programming_document(content: str) -> list[DaypartSpec]:
    # Regex extract structured data
    dayparts = []

    # Extract time blocks: "Morning Drive: (6:00 AM - 10:00 AM)"
    time_pattern = r"([A-Z][^:]+):\s*\((\d+:\d+ [AP]M)\s*-\s*(\d+:\d+ [AP]M)\)"

    # Extract BPM: "90-115 BPM", "110-135 BPM"
    bpm_pattern = r"(\d+)-(\d+) BPM"

    # Extract genre percentages: "Alternative: 25%"
    genre_pattern = r"([A-Za-z\s/]+):\s*(\d+)%"

    # Extract era distributions: "Current (last 2 years): 40%"
    era_pattern = r"([A-Z][^:]+)\s*\([^)]+\):\s*(\d+)%"

    # Extract Australian content: "30% minimum", "30-35%"
    aus_pattern = r"Australian[^:]*:\s*(\d+)(?:-(\d+))?%"

    # LLM validation for ambiguous sections
    # ...

    return dayparts
```

**Alternatives Considered**:
- Pure LLM parsing (too expensive, ~$0.10 per document)
- Manual JSON conversion (defeats automation purpose)
- NLP libraries (overkill for semi-structured data)

## Constraint Relaxation Algorithm

**Decision**: Implement hierarchical constraint relaxation with priority queue

**Rationale**:
- Clarified priority: BPM→Genre→Era, maintain Australian 30% minimum
- Incremental relaxation (±10 BPM, ±5% genre/era per step)
- Prevents over-relaxation while meeting 80%+ satisfaction target

**Implementation Pattern**:
```python
from dataclasses import dataclass
from typing import List, Dict

@dataclass
class ConstraintSet:
    bpm_range: tuple[int, int]
    genre_mix: Dict[str, float]
    era_distribution: Dict[str, float]
    australian_min: float  # NON-NEGOTIABLE

    def relax_bpm(self, increment: int = 10):
        """Relax BPM range by ±increment"""
        return ConstraintSet(
            bpm_range=(self.bpm_range[0] - increment, self.bpm_range[1] + increment),
            genre_mix=self.genre_mix,
            era_distribution=self.era_distribution,
            australian_min=self.australian_min
        )

    def relax_genre(self, tolerance: float = 0.05):
        """Allow ±tolerance variance in genre percentages"""
        # Implementation: adjust genre_mix ranges
        pass

    def relax_era(self, tolerance: float = 0.05):
        """Allow ±tolerance variance in era percentages"""
        # Implementation: adjust era_distribution ranges
        pass

def select_tracks_with_relaxation(criteria: ConstraintSet, max_iterations: int = 3) -> List[Track]:
    for iteration in range(max_iterations):
        tracks = search_with_constraints(criteria)
        satisfaction = validate_constraints(tracks, criteria)

        if satisfaction >= 0.80:  # 80% threshold
            return tracks

        # Relax in priority order
        if iteration == 0:
            criteria = criteria.relax_bpm()
        elif iteration == 1:
            criteria = criteria.relax_genre()
        elif iteration == 2:
            criteria = criteria.relax_era()

    return tracks  # Return best effort
```

**Alternatives Considered**:
- Simultaneous relaxation (too aggressive, poor quality)
- User-defined priority (conflicts with automation requirement)
- Machine learning optimization (overkill, training data unavailable)

## Quality Validation Metrics

**Decision**: Combined constraint satisfaction + flow quality scoring

**Rationale**:
- Clarified: ≥80% constraint satisfaction AND verified flow quality
- Quantifiable metrics for automated validation
- Supports indefinite logging requirement (FR-014)

**Implementation Pattern**:
```python
from dataclasses import dataclass

@dataclass
class ValidationResult:
    constraint_satisfaction: float  # 0.0-1.0
    flow_quality_score: float       # 0.0-1.0
    bpm_variance: float             # Tempo transition smoothness
    energy_progression: str         # "smooth" | "choppy" | "monotone"
    genre_diversity: float          # 0.0-1.0
    gap_analysis: Dict[str, str]    # Constraint → reason if unmet

    def is_valid(self) -> bool:
        return (
            self.constraint_satisfaction >= 0.80 and
            self.flow_quality_score >= 0.70  # Smooth transitions
        )

def validate_playlist(tracks: List[Track], criteria: ConstraintSet) -> ValidationResult:
    # Constraint satisfaction
    bpm_match = calculate_bpm_satisfaction(tracks, criteria.bpm_range)
    genre_match = calculate_genre_satisfaction(tracks, criteria.genre_mix)
    era_match = calculate_era_satisfaction(tracks, criteria.era_distribution)
    aus_match = calculate_australian_content(tracks, criteria.australian_min)

    constraint_sat = (bpm_match + genre_match + era_match + aus_match) / 4

    # Flow quality
    bpm_variance = calculate_bpm_transitions(tracks)
    energy_prog = analyze_energy_progression(tracks)

    flow_score = 1.0 - (bpm_variance / 100.0)  # Lower variance = better flow

    return ValidationResult(
        constraint_satisfaction=constraint_sat,
        flow_quality_score=flow_score,
        bpm_variance=bpm_variance,
        energy_progression=energy_prog,
        genre_diversity=calculate_genre_diversity(tracks),
        gap_analysis=identify_gaps(tracks, criteria)
    )
```

**Alternatives Considered**:
- Pure constraint matching (ignores listening experience)
- User satisfaction metrics (requires historical data, unavailable)
- Machine learning quality model (training data unavailable)

## Error Handling & Retry Strategy

**Decision**: Exponential backoff with circuit breaker pattern

**Rationale**:
- Clarified: 3 retry attempts with exponential backoff, skip on fail
- Circuit breaker prevents cascade failures
- Preserves cost/time budget (<10 min, <$0.50)

**Implementation Pattern**:
```python
import asyncio
from typing import Callable, TypeVar, Optional

T = TypeVar('T')

async def retry_with_backoff(
    func: Callable[..., T],
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0
) -> Optional[T]:
    """Retry with exponential backoff"""
    for attempt in range(max_attempts):
        try:
            return await func()
        except Exception as e:
            if attempt == max_attempts - 1:
                logger.error(f"Failed after {max_attempts} attempts: {e}")
                return None

            delay = min(base_delay * (2 ** attempt), max_delay)
            logger.warning(f"Attempt {attempt + 1} failed, retrying in {delay}s: {e}")
            await asyncio.sleep(delay)

    return None

# Usage in playlist generation
async def generate_playlist(spec: PlaylistSpec) -> Optional[Playlist]:
    result = await retry_with_backoff(
        lambda: llm_select_tracks(spec),
        max_attempts=3
    )

    if result is None:
        logger.error(f"Skipping playlist {spec.name} after retries")
        # Continue with next playlist (FR-013)

    return result
```

**Alternatives Considered**:
- Immediate failure (violates automation requirement)
- Unlimited retries (exceeds time budget)
- Manual intervention (conflicts with FR-011)

## Decision Log Storage

**Decision**: Structured JSON logging with indefinite retention

**Rationale**:
- Clarified: Indefinite retention for audit/replay (FR-014)
- JSON format for queryability and analysis
- Separate log stream for decision events

**Implementation Pattern**:
```python
import json
import logging
from datetime import datetime
from pathlib import Path

class DecisionLogger:
    def __init__(self, log_dir: Path = Path("logs/decisions")):
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Separate decision log file per execution
        self.log_file = self.log_dir / f"decisions_{datetime.now().isoformat()}.jsonl"

    def log_decision(
        self,
        decision_type: str,
        playlist_name: str,
        criteria: dict,
        selected_tracks: list,
        validation_result: dict,
        metadata: dict = None
    ):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "decision_type": decision_type,
            "playlist_name": playlist_name,
            "criteria": criteria,
            "selected_tracks": selected_tracks,
            "validation": validation_result,
            "metadata": metadata or {}
        }

        with open(self.log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")

# Usage
decision_logger = DecisionLogger()
decision_logger.log_decision(
    decision_type="track_selection",
    playlist_name="Monday_ProductionCall_0600_1000",
    criteria={"bpm": "90-115", "genre": {"Alternative": 0.25, "Electronic": 0.20}},
    selected_tracks=[{"id": "123", "title": "Track 1"}, ...],
    validation_result={"constraint_satisfaction": 0.85, "flow_quality": 0.78},
    metadata={"llm_cost": 0.002, "execution_time": 3.5}
)
```

**Alternatives Considered**:
- Database storage (adds complexity, overkill for append-only logs)
- Cloud logging service (adds cost, external dependency)
- In-memory only (violates indefinite retention requirement)

## Claude Flow Hive Memory Integration

**Decision**: Store reference data in Claude Flow memory under `ai-playlist/` namespace

**Rationale**:
- User requirement: "keep memory MCP updated and refer to it while working"
- Constitution requirement: Store specifications in Claude Flow memory
- Enables agent coordination and context sharing

**Memory Namespace Structure**:
```
ai-playlist/
├── station-identity-analysis     # Parsed programming document structure
├── playlist-naming-schema         # Naming convention rules
├── llm-workflow-requirements      # LLM integration patterns
├── constraint-relaxation-rules    # Priority and tolerance settings
├── validation-thresholds          # Quality metrics and thresholds
├── reference-implementations      # Code patterns and examples
└── execution-history              # Previous runs for learning
```

**Implementation Pattern**:
```bash
# Store parsed programming analysis
npx claude-flow@alpha memory store "ai-playlist/station-identity-analysis" \
  --content "Daypart structure: Morning Drive 6-10 AM, Midday 10 AM-3 PM..."

# Store LLM workflow requirements
npx claude-flow@alpha memory store "ai-playlist/llm-workflow-requirements" \
  --content "Use GPT-4o-mini with HostedMCPTool for Subsonic access..."

# Retrieve during execution
npx claude-flow@alpha memory retrieve "ai-playlist/constraint-relaxation-rules"
```

**Alternatives Considered**:
- Local file storage (no multi-agent sharing)
- Database (adds complexity)
- Git repository (versioning overkill for runtime data)

## Research Summary

All technical decisions documented with rationale and alternatives. No NEEDS CLARIFICATION items remain. Ready for Phase 1: Design & Contracts.

**Key Technologies**:
- OpenAI GPT-4o-mini + Responses API + HostedMCPTool
- Subsonic MCP server for track metadata
- Python 3.13+ with async/await
- Structured JSON logging
- Claude Flow hive memory for coordination

**Architecture Pattern**: Hybrid regex+LLM parsing → Constraint-based track selection with relaxation → Quality validation → AzuraCast sync

**Constitutional Compliance**: All requirements satisfied (hive-mind, TDD, code quality, security, deployment)
