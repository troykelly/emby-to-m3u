# Model Override Configuration Guide

## Overview
The AI Playlist system supports flexible model selection through environment variables and initialization parameters.

## Environment Variable: `OPENAI_MODEL`

Set the `OPENAI_MODEL` environment variable to override the default GPT-5 model:

```bash
# Use GPT-4o instead of GPT-5
export OPENAI_MODEL="gpt-4o"

# Use GPT-4 Turbo
export OPENAI_MODEL="gpt-4-turbo"

# Use GPT-4
export OPENAI_MODEL="gpt-4"
```

### In .env file:
```bash
# OpenAI Configuration
OPENAI_API_KEY=sk-proj-...
OPENAI_MODEL=gpt-4o  # Override default gpt-5
```

## Programmatic Override

You can also override the model when initializing the `OpenAIClient`:

```python
from src.ai_playlist.openai_client import OpenAIClient

# Use specific model
client = OpenAIClient(model="gpt-4o")

# Model parameter takes precedence over OPENAI_MODEL env var
client = OpenAIClient(
    api_key="sk-...",
    model="gpt-4-turbo"
)
```

## Model Selection Priority

The system uses the following priority order:

1. **Explicit parameter**: `OpenAIClient(model="gpt-4o")`
2. **Environment variable**: `OPENAI_MODEL=gpt-4o`
3. **Default**: `gpt-5`

## Supported Models

All OpenAI models are supported, including:
- **gpt-5** (default) - Uses o200k_base encoding
- **gpt-4o** - Uses o200k_base encoding
- **gpt-4-turbo** - Uses cl100k_base encoding
- **gpt-4** - Uses cl100k_base encoding
- **gpt-3.5-turbo** - Uses cl100k_base encoding

## Tokenizer Encoding

The system automatically selects the correct tiktoken encoding for each model:

| Model | Encoding |
|-------|----------|
| gpt-5 | o200k_base |
| gpt-4o | o200k_base |
| gpt-4.1 | o200k_base |
| gpt-4-turbo | cl100k_base |
| gpt-4 | cl100k_base |
| gpt-3.5-turbo | cl100k_base |

### Fallback Behavior

If a model is not recognized by tiktoken (e.g., `gpt-5` until tiktoken is updated), the system:
1. Logs a warning
2. Falls back to `o200k_base` encoding (the latest encoding for modern models)

```python
# Example warning:
# WARNING: Model 'gpt-5' not found in tiktoken, using o200k_base encoding
```

## Cost Considerations

Different models have different pricing. Update the cost variables if using a different model:

```python
# Default pricing (GPT-5/GPT-4o pricing)
cost_per_input_token = 0.00000015   # $0.15 per 1M tokens
cost_per_output_token = 0.00000060  # $0.60 per 1M tokens
```

Refer to [OpenAI Pricing](https://openai.com/api/pricing/) for current rates.

## Testing Model Override

```bash
# Test with different models
OPENAI_MODEL=gpt-4o python -m pytest tests/unit/ai_playlist/test_openai_client.py

# Verify encoding detection
python -c "
from src.ai_playlist.openai_client import OpenAIClient
import os

os.environ['OPENAI_MODEL'] = 'gpt-4o'
client = OpenAIClient()
print(f'Model: {client.model}')
print(f'Encoding: {client.encoding.name}')
"
```

## Example Usage

### Development (using cheaper model):
```bash
export OPENAI_MODEL="gpt-3.5-turbo"
python -m ai_playlist.main
```

### Production (using GPT-5):
```bash
export OPENAI_MODEL="gpt-5"
python -m ai_playlist.main
```

### Testing (using GPT-4o):
```bash
OPENAI_MODEL="gpt-4o" pytest tests/
```

## Research Findings

Based on research (January 2025):
- **GPT-5 uses o200k_base encoding** (same as GPT-4o, GPT-4.1, o1, o3, o4-mini)
- **tiktoken support**: `tiktoken.encoding_for_model("gpt-5")` returns o200k_base
- **Context length**: GPT-5 supports up to 400,000 tokens (272,000 input + 128,000 output)

## Troubleshooting

### Issue: Model not found in tiktoken
**Solution**: The system will automatically use `o200k_base` encoding with a warning. This is expected for newly released models.

### Issue: Wrong encoding being used
**Solution**: Verify the model name matches OpenAI's exact model identifier. Check tiktoken documentation for supported models.

### Issue: Cost estimates incorrect
**Solution**: Update `cost_per_input_token` and `cost_per_output_token` in `openai_client.py` to match your model's pricing.
