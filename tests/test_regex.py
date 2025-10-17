import re

test = """*Genre Mix:*
- Contemporary Alternative: 25%
- Electronic/Downtempo: 20%

*Era Mix:*
- Current: 40%"""

print("Test content:")
print(test)
print("\n" + "="*80)

# Test pattern 1: Original attempt
pattern1 = r'\*+Genre\s+Mix\*+:(.*?)(?=\n\s*\*+[A-Z]|\n\s*###|$)'
match = re.search(pattern1, test, re.IGNORECASE | re.DOTALL)
if match:
    print('Pattern 1 MATCHED!')
    print('Content:', repr(match.group(1)))
else:
    print('Pattern 1: NO MATCH')

# Test pattern 2: Simpler
pattern2 = r'\*Genre\s+Mix\*:(.*?)(?=\n\s*\*Era)'
match2 = re.search(pattern2, test, re.IGNORECASE | re.DOTALL)
if match2:
    print('\nPattern 2 MATCHED!')
    print('Content:', repr(match2.group(1)))
else:
    print('\nPattern 2: NO MATCH')

# Test pattern 3: Even simpler - just match until next * section
pattern3 = r'\*Genre\s+Mix\*:(.*?)(?=\n\s*\*\w+)'
match3 = re.search(pattern3, test, re.IGNORECASE | re.DOTALL)
if match3:
    print('\nPattern 3 MATCHED!')
    print('Content:', repr(match3.group(1)))
else:
    print('\nPattern 3: NO MATCH')

# Test pattern 4: Match until double newline or next section
pattern4 = r'\*Genre\s+Mix\*:(.*?)(?=\n\n\*|\n###|$)'
match4 = re.search(pattern4, test, re.IGNORECASE | re.DOTALL)
if match4:
    print('\nPattern 4 MATCHED!')
    print('Content:', repr(match4.group(1)))
else:
    print('\nPattern 4: NO MATCH')
