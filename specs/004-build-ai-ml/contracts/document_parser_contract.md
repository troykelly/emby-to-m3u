# Document Parser Contract

## parse_programming_document()

**Purpose**: Parse plain-language programming document into structured daypart specifications

### Input
```python
def parse_programming_document(content: str) -> List[DaypartSpec]
```

**Parameters**:
- `content`: str - Raw markdown content from station-identity.md

**Preconditions**:
- content is not empty
- content contains valid markdown structure

### Output

**Return Type**: `List[DaypartSpec]`

**Success Response**:
```python
[
    DaypartSpec(
        name="Production Call",
        day="Monday",
        time_range=("06:00", "10:00"),
        bpm_progression={
            "06:00-07:00": (90, 115),
            "07:00-09:00": (110, 135),
            "09:00-10:00": (100, 120)
        },
        genre_mix={
            "Alternative": 0.25,
            "Electronic": 0.20,
            "Quality Pop": 0.20,
            "Global Sounds": 0.15,
            "Contemporary Jazz": 0.10
        },
        era_distribution={
            "Current (0-2 years)": 0.40,
            "Recent (2-5 years)": 0.35,
            "Modern Classics (5-10 years)": 0.20,
            "Throwbacks (10-20 years)": 0.05
        },
        australian_min=0.30,
        mood="energetic morning drive",
        tracks_per_hour=12
    ),
    # ... more dayparts
]
```

**Error Cases**:
- `ValueError`: If content is empty or invalid
- `ParseError`: If markdown structure cannot be parsed
- `ValidationError`: If extracted data fails validation

### Contract Tests

**Test 1: Valid Complete Document**
```python
def test_parse_complete_document():
    content = """
    ## Monday Programming

    ### Morning Drive: "Production Call" (6:00 AM - 10:00 AM)

    BPM Progression:
    - 6:00-7:00 AM: 90-115 BPM
    - 7:00-9:00 AM: 110-135 BPM
    - 9:00-10:00 AM: 100-120 BPM

    Genre Mix:
    - Alternative: 25%
    - Electronic: 20%
    - Quality Pop: 20%
    - Global Sounds: 15%
    - Contemporary Jazz: 10%

    Era Mix:
    - Current (last 2 years): 40%
    - Recent (2-5 years): 35%
    - Modern Classics (5-10 years): 20%
    - Strategic Throwbacks (10-20 years): 5%

    Australian Content: 30% minimum
    """

    result = parse_programming_document(content)

    assert len(result) == 1
    assert result[0].name == "Production Call"
    assert result[0].day == "Monday"
    assert result[0].time_range == ("06:00", "10:00")
    assert result[0].bpm_progression["06:00-07:00"] == (90, 115)
    assert result[0].genre_mix["Alternative"] == 0.25
    assert result[0].era_distribution["Current (0-2 years)"] == 0.40
    assert result[0].australian_min == 0.30
```

**Test 2: Empty Document**
```python
def test_parse_empty_document():
    with pytest.raises(ValueError, match="Content cannot be empty"):
        parse_programming_document("")
```

**Test 3: Invalid BPM Range**
```python
def test_parse_invalid_bpm():
    content = "BPM: 500-600 BPM"  # Invalid range

    with pytest.raises(ValidationError, match="BPM values must be ≤ 300"):
        parse_programming_document(content)
```

**Test 4: Genre Percentages Exceed 100%**
```python
def test_parse_genre_overflow():
    content = """
    Genre Mix:
    - Alternative: 60%
    - Electronic: 50%
    """

    with pytest.raises(ValidationError, match="Genre percentages sum to >100%"):
        parse_programming_document(content)
```

### Implementation Notes

- Use regex for quantitative extraction (BPM, percentages, times)
- Use LLM for ambiguous mood descriptions only
- Validate all extracted data before returning
- Log parsing decisions to DecisionLog
