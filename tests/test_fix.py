#!/usr/bin/env python3
import re

test = "*Genre Mix:*"

patterns = [
    (r"\*Genre\s+Mix\*", "Original (won't work - no space before *)"),
    (r"\*Genre\s+Mix\s*\*", "With optional space before *"),
    (r"\*+Genre\s+Mix\*+", "Multiple asterisks"),
    (r"\*+Genre\s+Mix\*+:", "Full pattern"),
]

print("Test string:", repr(test))
print()

for pattern, desc in patterns:
    match = re.search(pattern, test)
    if match:
        print(f"✓ {desc:50} matched: {repr(match.group(0))}")
    else:
        print(f"✗ {desc:50} NO MATCH")
