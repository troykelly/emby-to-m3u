# Environment Variables Reference

## OpenAI Configuration

### OPENAI_API_KEY (Required)
- **Description**: OpenAI API key for authentication
- **Format**: `sk-proj-...` or `sk-...`
- **Example**: `OPENAI_API_KEY=sk-proj-abc123...`
- **Notes**: Primary API key variable

### OPENAI_KEY (Alternative)
- **Description**: Alternative API key variable name
- **Format**: Same as OPENAI_API_KEY
- **Example**: `OPENAI_KEY=sk-svcacct-xyz789...`
- **Notes**: Supported for backward compatibility. `OPENAI_API_KEY` takes precedence if both are set.

### OPENAI_MODEL (Optional)
- **Description**: Override the default GPT-5 model
- **Format**: Model identifier string
- **Default**: `gpt-5`
- **Examples**:
  ```bash
  OPENAI_MODEL=gpt-5          # Default (latest)
  OPENAI_MODEL=gpt-4o         # GPT-4 Optimized
  OPENAI_MODEL=gpt-4-turbo    # GPT-4 Turbo
  OPENAI_MODEL=gpt-4          # GPT-4
  OPENAI_MODEL=gpt-3.5-turbo  # GPT-3.5 Turbo (cost-effective)
  ```
- **Notes**: Use for development/testing with cheaper models or production with specific models

## Subsonic MCP Configuration

### SUBSONIC_MCP_URL (Required for MCP integration)
- **Description**: URL for Subsonic MCP server
- **Format**: HTTP/HTTPS URL
- **Example**: `SUBSONIC_MCP_URL=http://localhost:3000`
- **Notes**: Required for music library integration via MCP tools

## Priority Order

### API Key
1. Constructor parameter: `OpenAIClient(api_key="sk-...")`
2. `OPENAI_API_KEY` environment variable
3. `OPENAI_KEY` environment variable
4. Error raised if none found

### Model Selection
1. Constructor parameter: `OpenAIClient(model="gpt-4o")`
2. `OPENAI_MODEL` environment variable
3. Default: `gpt-5`

## Example .env File

```bash
# OpenAI Configuration
OPENAI_API_KEY=sk-proj-your_api_key_here
OPENAI_MODEL=gpt-5

# OR use alternative variable names
# OPENAI_KEY=sk-svcacct-your_api_key_here
# OPENAI_MODEL=gpt-4o

# Subsonic MCP (required for music library integration)
SUBSONIC_MCP_URL=http://localhost:3000

# AzuraCast (required for playlist sync)
AZURACAST_API_URL=https://radio.example.com
AZURACAST_API_KEY=your_azuracast_api_key
AZURACAST_STATION_ID=1
```

## Usage Examples

### Development (Cost-Effective)
```bash
# Use GPT-3.5 Turbo for development
export OPENAI_API_KEY=sk-proj-...
export OPENAI_MODEL=gpt-3.5-turbo
python -m ai_playlist.main
```

### Production (Best Performance)
```bash
# Use GPT-5 for production
export OPENAI_API_KEY=sk-proj-...
export OPENAI_MODEL=gpt-5
python -m ai_playlist.main
```

### Testing (Balanced)
```bash
# Use GPT-4o for testing
OPENAI_MODEL=gpt-4o pytest tests/
```

## Validation

Verify your environment variables:
```bash
python -c "
import os
from src.ai_playlist.openai_client import OpenAIClient

# Check API key
api_key = os.getenv('OPENAI_API_KEY') or os.getenv('OPENAI_KEY')
if api_key:
    print(f'✅ API Key: {api_key[:20]}...')
else:
    print('❌ No API key found')

# Check model
client = OpenAIClient()
print(f'✅ Model: {client.model}')
print(f'✅ Encoding: {client.encoding.name}')
"
```

## Security Best Practices

1. **Never commit `.env` files** to version control
   - Add `.env` to `.gitignore`

2. **Use different keys for different environments**
   - Development: Limited quota key
   - Production: Full access key

3. **Rotate API keys regularly**
   - Update keys every 90 days

4. **Use service accounts for production**
   - Prefer `sk-svcacct-...` keys for production
   - Use project-specific keys: `sk-proj-...`

5. **Monitor API usage**
   - Set up usage alerts in OpenAI dashboard
   - Track costs with the built-in cost tracking
