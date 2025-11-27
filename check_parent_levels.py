#!/usr/bin/env python3
"""
Quick diagnostic to check parent level distribution in ENSDF
"""

import pandas as pd
import numpy as np

# This would need the actual ENSDF file path
# For now, let's analyze the logic

print("="*70)
print("ANALYZING PARENT LEVEL MATCHING")
print("="*70)

print("\nKey Question: Why are all parentLevel values still 0?")
print("\nPossible reasons:")
print("1. Most ENSDF decays ARE from ground states (parentLevel=0)")
print("   - Excited parent states decay via gamma (picoseconds), not beta/alpha")
print("   - Only long-lived isomers undergo beta/alpha decay from excited states")
print("\n2. ENSDF might have limited data for excited parent state decays")
print("\n3. The matching might not be finding ENSDF transitions with parentLevel>0")

print("\n" + "="*70)
print("WHAT TO CHECK IN YOUR ENSDF FILE:")
print("="*70)

print("\nRun this to see parent level distribution in ENSDF:")
print("""
import pandas as pd
import numpy as np

# Load ENSDF (adjust path)
ensdf_path = "/Users/audreywarn/fluka-db-audrey/outputs/ensdf/json_data_modules/ascii/DECAY.ascii"

# Read with your custom parser or pandas
ensdf = pd.read_csv(ensdf_path, sep=r'\\s+', comment='#', engine='python')

# Check parent level distribution
print("\\nParent Level Distribution in ENSDF:")
print(ensdf['parentLevel'].value_counts().head(20))

print("\\nNumber of transitions with parentLevel > 0:")
print((ensdf['parentLevel'] > 0).sum())

print("\\nExamples of non-zero parent levels:")
print(ensdf[ensdf['parentLevel'] > 0].head(10))
""")

print("\n" + "="*70)
print("EXPECTED BEHAVIOR:")
print("="*70)
print("""
For radioactive decay:
- ~99% of decays occur from GROUND states (parentLevel=0)
- Only ISOMERIC states (long-lived excited states) decay via beta/alpha
- Examples of isomers: Tc-99m, Co-60m, Am-242m

Your output showing all parentLevel=0 is likely CORRECT because:
- ENDF entries are for nuclides in specific states (ground or isomeric)
- ENSDF mostly contains decays from ground states
- Matching ground→ground transitions will preserve parentLevel=0

To verify: Look for isomeric entries in ENDF (LISO > 0)
These should potentially match to ENSDF parentLevel > 0
""")

print("\n" + "="*70)
print("WHAT SHOULD BE CHECKED:")
print("="*70)
print("""
1. Check ENDF for isomeric states (LISO > 0):
   - These represent decays from excited parent states
   
2. Check if ENSDF has matching transitions from excited parents

3. Verify diagnostics file shows parent_level_matched values

Example ENDF entry that SHOULD get non-zero parentLevel:
  A=99, Z=43, parentLevel=0, LISO=1  (Tc-99m isomer)
  This should match to ENSDF parentLevel=1 transition
""")
