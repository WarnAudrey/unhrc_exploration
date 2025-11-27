#!/usr/bin/env python3
"""
Quick check of ENSDF parent level distribution
"""

import pandas as pd
import numpy as np

ensdf_path = "/Users/audreywarn/fluka-db-audrey/outputs/ensdf/json_data_modules/ascii/DECAY.ascii"

print("="*70)
print("ENSDF PARENT LEVEL ANALYSIS")
print("="*70)

# Read ENSDF file
lines = []
with open(ensdf_path, 'r') as f:
    for line in f:
        if line.strip() and not line.strip().startswith('#'):
            lines.append(line)

# Process data
data = []
for line in lines:
    parts = line.split()
    if len(parts) >= 5:
        try:
            a = int(parts[0])
            z = int(parts[1])
            parent_level = float(parts[2])
            decay_mode = parts[3]
            final_level = float(parts[4])
            data.append({
                'A': a,
                'Z': z,
                'parentLevel': parent_level,
                'decay_mode': decay_mode,
                'final_level': final_level
            })
        except ValueError:
            continue

df = pd.DataFrame(data)

print(f"\nTotal ENSDF transitions: {len(df)}")

print("\n" + "="*70)
print("PARENT LEVEL DISTRIBUTION:")
print("="*70)

parent_counts = df['parentLevel'].value_counts().sort_index().head(15)
for level, count in parent_counts.items():
    pct = 100 * count / len(df)
    print(f"  parentLevel = {int(level):3d}: {count:6d} transitions ({pct:5.1f}%)")

non_zero_parents = (df['parentLevel'] > 0).sum()
zero_parents = (df['parentLevel'] == 0).sum()
print(f"\n  Ground state (0): {zero_parents:6d} ({100*zero_parents/len(df):.1f}%)")
print(f"  Excited (>0):     {non_zero_parents:6d} ({100*non_zero_parents/len(df):.1f}%)")

if non_zero_parents > 0:
    print("\n" + "="*70)
    print("EXAMPLES OF EXCITED PARENT STATE DECAYS:")
    print("="*70)
    excited = df[df['parentLevel'] > 0].head(20)
    print(excited[['A', 'Z', 'parentLevel', 'decay_mode', 'final_level']].to_string(index=False))

print("\n" + "="*70)
print("INTERPRETATION:")
print("="*70)
print("""
If ~99% of transitions have parentLevel=0:
  → Your output showing all parentLevel=0 is CORRECT
  → Most radioactive decays occur from ground states
  → Only isomers (long-lived excited states) decay from excited levels

If many transitions have parentLevel>0:
  → Check DECAY_matched_diagnostics.ascii
  → Look for parent_level_matched column
  → Verify those values are being written to output
""")
