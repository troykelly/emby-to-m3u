#!/usr/bin/env python3
import re

# Test string with space
test = "*Genre Mix:*\n- Contemporary Alternative: 25%"

print("Test string:", repr(test))
print()

# Try different patterns
patterns = [
    r"\*Genre Mix\*:",
    r"\*Genre\sMix\*:",
    r"\*Genre\s+Mix\*:",
    r"\\*Genre Mix\\*:",
    r"\\\*Genre Mix\\\*:",
]

for i, pattern in enumerate(patterns, 1):
    print(f"Pattern {i}: {repr(pattern)}")
    try:
        match = re.search(pattern, test)
        if match:
            print(f"  ✓ MATCHED at position {match.start()}-{match.end()}")
            print(f"    Matched text: {repr(match.group(0))}")
        else:
            print(f"  ✗ NO MATCH")
    except Exception as e:
        print(f"  ✗ ERROR: {e}")
    print()
