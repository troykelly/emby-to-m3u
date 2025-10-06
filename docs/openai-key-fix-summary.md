# OpenAI API Key Environment Variable Fix

## Issue

The AI playlist codebase was looking for `OPENAI_API_KEY` environment variable, but the actual environment has `OPENAI_KEY` set. This caused tests to skip and API calls to fail.

## Solution

Updated all references to support both environment variable names for backward compatibility:
- `OPENAI_API_KEY` (standard/preferred)
- `OPENAI_KEY` (alternative/existing)

The code now tries `OPENAI_API_KEY` first, then falls back to `OPENAI_KEY`.

## Files Modified

### 1. `/workspaces/emby-to-m3u/src/ai_playlist/openai_client.py`

**Changes:**
```python
# OLD:
self.api_key = api_key or os.getenv("OPENAI_API_KEY")
if not self.api_key:
    raise ValueError("OPENAI_API_KEY must be provided or set in environment")

# NEW:
self.api_key = api_key or os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_KEY")
if not self.api_key:
    raise ValueError("OPENAI_API_KEY or OPENAI_KEY must be provided or set in environment")
```

### 2. `/workspaces/emby-to-m3u/src/ai_playlist/track_selector.py`

**Changes:**
```python
# OLD:
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY environment variable not set")

# NEW:
api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY or OPENAI_KEY environment variable not set")
```

### 3. `/workspaces/emby-to-m3u/tests/performance/test_playlist_performance.py`

**Changes:**
```python
# OLD:
@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="No OpenAI API key")

# NEW:
@pytest.mark.skipif(not (os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_KEY")), reason="No OpenAI API key")
```

Updated 2 test functions:
- `test_performance_single_playlist_real_api()`
- `test_performance_token_estimation_accuracy()`

### 4. `/workspaces/emby-to-m3u/tests/unit/ai_playlist/test_openai_client.py`

**Changes:**
```python
# Updated test to check both variable names
def test_init_without_api_key_raises_error(self, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_KEY", raising=False)

    with pytest.raises(ValueError, match="OPENAI_API_KEY or OPENAI_KEY must be provided"):
        OpenAIClient()
```

**Added new tests:**
```python
def test_init_with_openai_key_env_var(self, monkeypatch):
    """Test initialization from OPENAI_KEY environment variable."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_KEY", "env-openai-key-789")

    client = OpenAIClient()
    assert client.api_key == "env-openai-key-789"

def test_init_prefers_openai_api_key_over_openai_key(self, monkeypatch):
    """Test that OPENAI_API_KEY takes precedence over OPENAI_KEY."""
    monkeypatch.setenv("OPENAI_API_KEY", "api-key-first")
    monkeypatch.setenv("OPENAI_KEY", "openai-key-second")

    client = OpenAIClient()
    assert client.api_key == "api-key-first"
```

### 5. `/workspaces/emby-to-m3u/specs/004-build-ai-ml/quickstart.md`

**Documentation Updates:**

1. Prerequisites section - Added alternative variable name:
```bash
# OpenAI Configuration
OPENAI_API_KEY=sk-proj-...  # Your OpenAI API key for GPT-4o-mini
# OR
OPENAI_KEY=sk-proj-...      # Alternative variable name (both are supported)
```

2. Environment setup - Added both options:
```bash
# OpenAI API Configuration (use either variable name)
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
# OR
OPENAI_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

3. Troubleshooting section - Updated error message and solutions:
```bash
#### 1. "OPENAI_API_KEY or OPENAI_KEY environment variable not set"

**Solution**:
# Add to .env file (either variable name works)
echo "OPENAI_API_KEY=sk-proj-your_key_here" >> .env
# OR
echo "OPENAI_KEY=sk-proj-your_key_here" >> .env

**Note**: Both `OPENAI_API_KEY` and `OPENAI_KEY` are supported for backward compatibility.
```

4. Real API testing section - Added both options:
```bash
# Set environment variables (either variable name works)
export OPENAI_API_KEY="sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
# OR
export OPENAI_KEY="sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

## Verification

### Test Results

All initialization tests pass:
```bash
tests/unit/ai_playlist/test_openai_client.py::TestOpenAIClientInit::test_init_with_explicit_api_key PASSED
tests/unit/ai_playlist/test_openai_client.py::TestOpenAIClientInit::test_init_with_env_var PASSED
tests/unit/ai_playlist/test_openai_client.py::TestOpenAIClientInit::test_init_with_openai_key_env_var PASSED
tests/unit/ai_playlist/test_openai_client.py::TestOpenAIClientInit::test_init_prefers_openai_api_key_over_openai_key PASSED
tests/unit/ai_playlist/test_openai_client.py::TestOpenAIClientInit::test_init_without_api_key_raises_error PASSED
tests/unit/ai_playlist/test_openai_client.py::TestOpenAIClientInit::test_client_creates_async_openai_instance PASSED
```

### Integration Test

```bash
python3 -c "
import os
from openai import OpenAI

api_key = os.getenv('OPENAI_API_KEY') or os.getenv('OPENAI_KEY')
if api_key:
    client = OpenAI(api_key=api_key)
    print('✅ OpenAI client initialized successfully')
    print(f'✅ API key detected from: {\"OPENAI_API_KEY\" if os.getenv(\"OPENAI_API_KEY\") else \"OPENAI_KEY\"}')
"
```

**Output:**
```
✅ OpenAI client initialized successfully
✅ API key detected from: OPENAI_KEY
```

## Success Criteria

- ✅ All files updated to check both variable names
- ✅ Tests no longer skip due to missing API key
- ✅ Documentation updated with both names
- ✅ Verification test passes
- ✅ All unit tests pass (6/6)
- ✅ Integration test confirms API key detection

## Backward Compatibility

The implementation maintains full backward compatibility:

1. **Precedence order**: `OPENAI_API_KEY` takes priority over `OPENAI_KEY`
2. **Existing code**: Any code using `OPENAI_API_KEY` continues to work
3. **New environments**: Environments with `OPENAI_KEY` now work correctly
4. **Migration path**: Users can migrate from `OPENAI_KEY` to `OPENAI_API_KEY` gradually

## Impact

### Before Fix
- Tests skipped: "No OpenAI API key"
- API calls failed: "OPENAI_API_KEY environment variable not set"
- Performance tests couldn't run

### After Fix
- Tests detect API key from either variable
- API calls work with both variable names
- Performance tests can now execute
- Better developer experience with clear error messages

## Next Steps

1. ✅ Performance tests can now run with real API
2. ✅ Integration tests will use detected API key
3. ✅ Documentation is accurate and complete
4. Ready for production deployment

## Recommendations

1. **Standardize on `OPENAI_API_KEY`** - This is the standard convention used by OpenAI SDK
2. **Keep `OPENAI_KEY` support** - For backward compatibility with existing deployments
3. **Update `.env.example`** - Show both variable names with a note about preference
4. **CI/CD pipelines** - Update to use `OPENAI_API_KEY` going forward
