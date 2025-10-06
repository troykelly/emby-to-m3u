# Playlist Validator Contract

## validate_playlist()

**Purpose**: Validate generated playlist meets quality standards (≥80% constraint satisfaction + flow quality)

### Input
```python
def validate_playlist(
    tracks: List[SelectedTrack],
    criteria: TrackSelectionCriteria
) -> ValidationResult
```

**Parameters**:
- `tracks`: List[SelectedTrack] - Ordered list of selected tracks
- `criteria`: TrackSelectionCriteria - Original selection criteria

**Preconditions**:
- tracks is not empty
- criteria is valid
- All tracks have required metadata

### Output

**Return Type**: `ValidationResult`

**Success Response** (passing validation):
```python
ValidationResult(
    constraint_satisfaction=0.85,  # ≥ 0.80 threshold
    bpm_satisfaction=0.90,
    genre_satisfaction=0.82,
    era_satisfaction=0.83,
    australian_content=0.33,  # 33% actual vs 30% minimum
    flow_quality_score=0.78,  # ≥ 0.70 threshold
    bpm_variance=8.5,  # Average BPM change between tracks
    energy_progression="smooth",
    genre_diversity=0.75,
    gap_analysis={},  # Empty = all criteria met
    passes_validation=True  # constraint_satisfaction ≥ 0.80 AND flow_quality ≥ 0.70
)
```

**Failure Response** (insufficient constraints):
```python
ValidationResult(
    constraint_satisfaction=0.72,  # < 0.80 threshold
    bpm_satisfaction=0.85,
    genre_satisfaction=0.65,  # Genre mix not satisfied
    era_satisfaction=0.70,
    australian_content=0.30,  # Exactly at minimum
    flow_quality_score=0.82,  # Flow is good
    bpm_variance=12.3,
    energy_progression="smooth",
    genre_diversity=0.60,
    gap_analysis={
        "genre_mix": "Alternative 18% (target: 20-30%), Electronic 12% (target: 15-25%)",
        "era_distribution": "Current era 32% (target: 35-45%)"
    },
    passes_validation=False  # constraint_satisfaction < 0.80
)
```

### Contract Tests

**Test 1: Valid Playlist Passes**
```python
def test_validate_passing_playlist():
    tracks = [
        SelectedTrack(
            track_id="1", title="Track 1", artist="Artist AU", bpm=100,
            genre="Alternative", year=2023, country="AU", duration_seconds=240,
            position=1, selection_reason="reason"
        ),
        SelectedTrack(
            track_id="2", title="Track 2", artist="Artist AU", bpm=108,
            genre="Electronic", year=2022, country="AU", duration_seconds=250,
            position=2, selection_reason="reason"
        ),
        SelectedTrack(
            track_id="3", title="Track 3", artist="Artist UK", bpm=115,
            genre="Alternative", year=2023, country="GB", duration_seconds=235,
            position=3, selection_reason="reason"
        )
    ]

    criteria = TrackSelectionCriteria(
        bpm_range=(90, 120),
        genre_mix={"Alternative": (0.20, 0.50), "Electronic": (0.20, 0.50)},
        era_distribution={"Current": (0.30, 0.70)},
        australian_min=0.30,
        energy_flow="moderate build"
    )

    result = validate_playlist(tracks, criteria)

    assert result.passes_validation is True
    assert result.constraint_satisfaction >= 0.80
    assert result.flow_quality_score >= 0.70
    assert result.australian_content >= 0.30
    assert len(result.gap_analysis) == 0
```

**Test 2: Insufficient Australian Content Fails**
```python
def test_validate_insufficient_australian():
    tracks = [
        SelectedTrack(..., country="US"),  # 0%
        SelectedTrack(..., country="GB"),  # 0%
        SelectedTrack(..., country="AU"),  # 33%
    ]

    criteria = TrackSelectionCriteria(
        bpm_range=(90, 120),
        genre_mix={"Alternative": (0.30, 0.70)},
        era_distribution={"Current": (0.30, 0.70)},
        australian_min=0.50,  # 50% required
        energy_flow="moderate"
    )

    result = validate_playlist(tracks, criteria)

    assert result.passes_validation is False
    assert result.australian_content == 0.33  # Actual
    assert "australian_content" in result.gap_analysis
```

**Test 3: Poor Flow Quality Fails**
```python
def test_validate_choppy_flow():
    tracks = [
        SelectedTrack(..., bpm=80),
        SelectedTrack(..., bpm=140),  # +60 BPM jump
        SelectedTrack(..., bpm=90),   # -50 BPM drop
        SelectedTrack(..., bpm=130),  # +40 BPM jump
    ]

    criteria = valid_criteria

    result = validate_playlist(tracks, criteria)

    assert result.flow_quality_score < 0.70  # Poor flow
    assert result.energy_progression == "choppy"
    assert result.passes_validation is False
```

**Test 4: BPM Out of Range**
```python
def test_validate_bpm_out_of_range():
    tracks = [
        SelectedTrack(..., bpm=100),  # OK
        SelectedTrack(..., bpm=150),  # OUT OF RANGE
        SelectedTrack(..., bpm=105),  # OK
    ]

    criteria = TrackSelectionCriteria(
        bpm_range=(90, 120),
        ...
    )

    result = validate_playlist(tracks, criteria)

    assert result.bpm_satisfaction < 1.0
    assert "bpm_range" in result.gap_analysis
```

### Validation Calculations

**Constraint Satisfaction**:
```python
constraint_satisfaction = (
    bpm_satisfaction +
    genre_satisfaction +
    era_satisfaction +
    australian_satisfaction
) / 4
```

**BPM Satisfaction**:
```python
in_range_count = sum(1 for t in tracks if bpm_min <= t.bpm <= bpm_max)
bpm_satisfaction = in_range_count / len(tracks)
```

**Genre Satisfaction**:
```python
for genre, (min_pct, max_pct) in criteria.genre_mix.items():
    actual_pct = count_genre(tracks, genre) / len(tracks)
    if min_pct <= actual_pct <= max_pct:
        genre_matches += 1

genre_satisfaction = genre_matches / len(criteria.genre_mix)
```

**Flow Quality Score**:
```python
bpm_changes = [abs(tracks[i+1].bpm - tracks[i].bpm) for i in range(len(tracks)-1)]
avg_bpm_variance = sum(bpm_changes) / len(bpm_changes)

# Smooth: avg variance < 10, Choppy: > 20
flow_quality_score = max(0, 1.0 - (avg_bpm_variance / 50.0))
```

**Energy Progression**:
```python
if avg_bpm_variance < 10:
    energy_progression = "smooth"
elif avg_bpm_variance > 20:
    energy_progression = "choppy"
else:
    energy_progression = "moderate"
```

### Implementation Notes

- Calculate all metrics independently
- Generate gap_analysis for any unmet criteria
- passes_validation requires BOTH thresholds met
- Log validation results to DecisionLog
