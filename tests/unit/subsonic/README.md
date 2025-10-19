# Subsonic Models Comprehensive Test Suite

## Quick Start

Run the comprehensive model tests:

```bash
# Run all tests with coverage
python -m pytest tests/unit/subsonic/test_models_comprehensive.py --cov=src/subsonic/models --cov-report=term-missing

# Run all tests verbosely
python -m pytest tests/unit/subsonic/test_models_comprehensive.py -v

# Run specific test class
python -m pytest tests/unit/subsonic/test_models_comprehensive.py::TestSubsonicConfigEdgeCases -v

# Run specific test
python -m pytest tests/unit/subsonic/test_models_comprehensive.py::TestSubsonicConfigEdgeCases::test_url_validation_empty_string -v
```

## Test Coverage Results

```
Name                    Stmts   Miss   Cover
--------------------------------------------
src/subsonic/models.py     81      0   100%
--------------------------------------------
```

## Test Suite Structure

### 63 Tests Across 6 Categories

1. **TestSubsonicConfigEdgeCases** (25 tests)
   - URL validation edge cases
   - Username and password validation
   - HTTP warning tests
   - Validation order tests

2. **TestSubsonicAuthTokenEdgeCases** (15 tests)
   - Token expiry logic
   - Auth params generation
   - Unicode and special character handling

3. **TestSubsonicTrackEdgeCases** (7 tests)
   - Field validation
   - Edge values (negative, zero, extreme)
   - Optional field handling

4. **TestSubsonicArtistEdgeCases** (5 tests)
   - Minimal and complete data
   - Edge value handling

5. **TestSubsonicAlbumEdgeCases** (5 tests)
   - Minimal and complete data
   - Edge value handling

6. **TestModelIntegration** (3 tests)
   - Cross-model workflows
   - Integration scenarios

7. **TestBoundaryValues** (3 tests)
   - Maximum values
   - Extreme inputs

## What's Tested

### Previously Uncovered Lines

✅ **Lines 30-43**: SubsonicConfig validation
- URL protocol checking
- Username requirements
- Password/API key validation
- HTTP warning generation

✅ **Lines 75-77**: SubsonicAuthToken.is_expired()
- None check for non-expiring tokens
- Expiry time comparison

✅ **Line 85**: SubsonicAuthToken.to_auth_params()
- Dictionary creation and values

### Edge Cases

- Empty strings and None values
- Invalid protocols (ftp://, ws://, etc.)
- Negative values (duration, year, bitrate)
- Zero values (duration, file size, album count)
- Maximum integer values (2^31-1)
- Very long strings (10,000+ characters)
- Unicode characters (Chinese, Russian, emoji)
- Special characters in usernames
- Timezone-aware datetime handling

## Files

- **Test File**: `test_models_comprehensive.py`
- **Source File**: `src/subsonic/models.py`
- **Coverage Summary**: `TEST_COVERAGE_SUMMARY.md`

## Test Examples

### Testing URL Validation
```python
def test_url_validation_empty_string(self):
    """Test line 30: Empty URL raises ValueError."""
    with pytest.raises(ValueError, match="url must be a valid HTTP/HTTPS URL"):
        SubsonicConfig(url="", username="user", password="pass")
```

### Testing Token Expiry
```python
def test_is_expired_none_never_expires(self):
    """Test line 75-76: Token with expires_at=None never expires."""
    token = SubsonicAuthToken(
        token="test_token",
        salt="test_salt",
        username="user",
        created_at=datetime.now(timezone.utc),
        expires_at=None,
    )
    assert token.is_expired() is False
```

### Testing Auth Parameters
```python
def test_to_auth_params_structure(self):
    """Test line 85: to_auth_params() returns correct dict structure."""
    token = SubsonicAuthToken(
        token="abc123",
        salt="xyz789",
        username="testuser",
        created_at=datetime.now(timezone.utc),
    )
    params = token.to_auth_params()
    assert isinstance(params, dict)
    assert set(params.keys()) == {"u", "t", "s"}
```

## Benefits

1. **100% Coverage**: All code paths tested
2. **Regression Prevention**: Comprehensive edge case coverage
3. **Documentation**: Tests serve as usage examples
4. **Confidence**: Safe refactoring with full test coverage
5. **Validation**: All input validation thoroughly tested

## Running with Coverage Report

Generate an HTML coverage report:

```bash
python -m pytest tests/unit/subsonic/test_models_comprehensive.py \
    --cov=src/subsonic/models \
    --cov-report=html \
    --cov-report=term-missing

# View the HTML report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

## Continuous Integration

Add to your CI pipeline:

```yaml
- name: Run Subsonic Model Tests
  run: |
    python -m pytest tests/unit/subsonic/test_models_comprehensive.py \
      --cov=src/subsonic/models \
      --cov-fail-under=90 \
      -v
```

## Contributing

When adding new features to `src/subsonic/models.py`:

1. Add corresponding tests to `test_models_comprehensive.py`
2. Ensure coverage remains at 100%
3. Test edge cases and validation logic
4. Update this README if needed

## Support

For questions or issues:
- Review the test code for usage examples
- Check the coverage report for untested areas
- Refer to `TEST_COVERAGE_SUMMARY.md` for details
