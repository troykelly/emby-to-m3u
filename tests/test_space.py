#!/usr/bin/env python3
import re

test = "*Genre Mix:*"

# Check what's between Genre and Mix
idx_genre = test.find("Genre")
idx_mix = test.find("Mix")
between = test[idx_genre+5:idx_mix]

print(f"Test string: {repr(test)}")
print(f"Between 'Genre' and 'Mix': {repr(between)}")
print(f"Is it a space? {between == ' '}")
print()

# Try pattern without \s+
pattern1 = r"\*Genre Mix\*:"
match1 = re.search(pattern1, test)
print(f"Pattern with literal space: {repr(pattern1)}")
print(f"Result: {match1}")
if match1:
    print(f"  Matched: {repr(match1.group(0))}")
