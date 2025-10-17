import re

test = """*Genre Mix:*
- Contemporary Alternative: 25%
- Electronic/Downtempo: 20%

*Era Mix:*
- Current: 40%"""

print("Test content:")
print(repr(test))
print("\n" + "="*80)

# Find the literal string first
if '*Genre Mix:*' in test:
    print("Found literal '*Genre Mix:*'")

# Test simplest pattern
pattern = r'\*Genre Mix\*:'
match = re.search(pattern, test)
if match:
    print(f"Simple pattern matched at position {match.start()}")
else:
    print("Simple pattern: NO MATCH")

# Test with space
pattern2 = r'\*Genre\s+Mix\*:'
match2 = re.search(pattern2, test)
if match2:
    print(f"Pattern with \\s+ matched at position {match2.start()}")
    # Now try to capture until next section
    pattern3 = r'\*Genre\s+Mix\*:(.*?)(?=\*Era)'
    match3 = re.search(pattern3, test, re.DOTALL)
    if match3:
        print("Captured content:", repr(match3.group(1)))
else:
    print("Pattern with \\s+: NO MATCH")

# Check what the actual characters are
idx = test.find('Genre Mix')
if idx >= 0:
    print(f"\nActual characters around 'Genre Mix' (index {idx}):")
    print(repr(test[max(0,idx-5):idx+20]))
