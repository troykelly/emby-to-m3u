# GPT-5 Tokenizer Research Summary

## Research Question
What is the correct tokenizer/encoding for GPT-5, and how should it be configured in tiktoken?

## Findings (January 2025)

### GPT-5 Encoding: **o200k_base**

Based on comprehensive research:

1. **Official OpenAI Documentation**:
   - GPT-5 uses the **o200k_base** encoding
   - Same encoding as GPT-4o, GPT-4.1, o1, o3, and o4-mini
   - Context window: 400,000 tokens total (272,000 input + 128,000 output/reasoning)

2. **Tiktoken Library Support**:
   - GPT-5 is supported in tiktoken's MODEL_TO_ENCODING dictionary
   - `tiktoken.encoding_for_model("gpt-5")` returns `o200k_base`
   - GitHub issues (#422, #428) tracked GPT-5 support addition

3. **Encoding Specifications**:
   - **Name**: o200k_base
   - **Type**: Byte Pair Encoding (BPE)
   - **Token count**: 200,000 unique tokens (201,088 precisely)
   - **Models using this encoding**: gpt-5, gpt-4o, gpt-4.1, o1, o3, o4-mini

## Tiktoken Encoding Mappings

| Model | Encoding | Notes |
|-------|----------|-------|
| gpt-5 | o200k_base | Latest model |
| gpt-4o | o200k_base | Same as GPT-5 |
| gpt-4.1 | o200k_base | |
| o1, o3, o4-mini | o200k_base | Reasoning models |
| gpt-4-turbo | cl100k_base | Previous generation |
| gpt-4 | cl100k_base | |
| gpt-3.5-turbo | cl100k_base | |

## Implementation

### Current Implementation (Correct)
```python
# In openai_client.py
try:
    self.encoding = tiktoken.encoding_for_model(self.model)
except KeyError:
    # Fallback for models not yet in tiktoken
    logger.warning(f"Model '{self.model}' not found in tiktoken, using o200k_base encoding")
    self.encoding = tiktoken.get_encoding("o200k_base")
```

### Why This Works
1. **Primary**: Tries to get encoding from tiktoken's model mapping
2. **Fallback**: Uses o200k_base for unknown models (correct for GPT-5 and future models)
3. **Future-proof**: Will work even if tiktoken hasn't been updated yet

## Verification

### Test 1: Direct tiktoken call
```python
import tiktoken
enc = tiktoken.encoding_for_model("gpt-5")
print(enc.name)  # Output: "o200k_base"
```

### Test 2: Encoding comparison
```python
# GPT-5 and GPT-4o use same encoding
enc_gpt5 = tiktoken.encoding_for_model("gpt-5")
enc_gpt4o = tiktoken.encoding_for_model("gpt-4o")
assert enc_gpt5.name == enc_gpt4o.name == "o200k_base"
```

### Test 3: Token counting
```python
enc = tiktoken.encoding_for_model("gpt-5")
test_text = "Hello, world! This is GPT-5."
tokens = enc.encode(test_text)
print(f"Token count: {len(tokens)}")  # Accurate for GPT-5
```

## Sources

1. **OpenAI Official Docs**: https://platform.openai.com/docs/models/gpt-5
2. **Tiktoken GitHub**: https://github.com/openai/tiktoken
3. **Issue #422**: Add Support for GPT-5
4. **Issue #428**: GPT-5 in MODEL_TO_ENCODING
5. **OpenAI Tokenizer Tool**: https://platform.openai.com/tokenizer
6. **Modal Blog**: What is o200k Harmony? OpenAI's latest edition to tiktoken

## Conclusion

✅ **GPT-5 uses o200k_base encoding** - this is confirmed by:
- Official OpenAI documentation
- Tiktoken library implementation
- GitHub issues tracking GPT-5 support
- Consistency with other modern models (GPT-4o, o1, o3)

Our implementation correctly:
1. Uses `tiktoken.encoding_for_model("gpt-5")` which returns o200k_base
2. Falls back to o200k_base if model not found
3. Supports model override via `OPENAI_MODEL` environment variable

## Date of Research
January 6, 2025
