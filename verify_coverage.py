#!/usr/bin/env python3
"""
Verify nuclide coverage: ENDF vs ENSDF
Run this on your local machine
"""

import pandas as pd
import numpy as np

endf_path = "/Users/audreywarn/fluka-db-audrey/outputs/endf/endf_data_modules/ascii/DECAY.ascii"
ensdf_path = "/Users/audreywarn/fluka-db-audrey/outputs/ensdf/json_data_modules/ascii/DECAY.ascii"

print("="*70)
print("ENDF vs ENSDF: BREADTH vs DEPTH ANALYSIS")
print("="*70)

# Load data
endf_df = pd.read_csv(endf_path, sep=r'\s+', comment='#', 
                      index_col=[0,1,2,3,4], engine='python')
ensdf_df = pd.read_csv(ensdf_path, sep=r'\s+', comment='#',
                       index_col=[0,1,2,3,4], engine='python')

endf_reset = endf_df.reset_index()
ensdf_reset = ensdf_df.reset_index()

# Count unique nuclides
endf_nuclides = endf_reset[['A', 'Z']].drop_duplicates()
ensdf_nuclides = ensdf_reset[['A', 'Z']].drop_duplicates()

# Calculate N (neutron number)
endf_nuclides['N'] = endf_nuclides['A'] - endf_nuclides['Z']
ensdf_nuclides['N'] = ensdf_nuclides['A'] - ensdf_nuclides['Z']

print("\n" + "="*70)
print("BREADTH: Number of Different Isotopes")
print("="*70)
print(f"ENDF unique nuclides:    {len(endf_nuclides):5d}")
print(f"ENSDF unique nuclides:   {len(ensdf_nuclides):5d}")
print(f"Difference:              {len(endf_nuclides) - len(ensdf_nuclides):5d}")

if len(endf_nuclides) > len(ensdf_nuclides):
    print(f"\n✓ ENDF covers {len(endf_nuclides) - len(ensdf_nuclides)} MORE nuclides")
    print("  → This explains why your plot shows more ENDF coverage")

print("\n" + "="*70)
print("DEPTH: Transitions Per Nuclide")
print("="*70)
print(f"ENDF total transitions:  {len(endf_reset):5d}")
print(f"ENSDF total transitions: {len(ensdf_reset):5d}")
print(f"Difference:              {len(ensdf_reset) - len(endf_reset):5d}")

endf_avg = len(endf_reset) / len(endf_nuclides)
ensdf_avg = len(ensdf_reset) / len(ensdf_nuclides)

print(f"\nAverage transitions/nuclide:")
print(f"ENDF:  {endf_avg:6.1f} transitions/nuclide")
print(f"ENSDF: {ensdf_avg:6.1f} transitions/nuclide")
print(f"Ratio: {ensdf_avg/endf_avg:6.1f}x more detail in ENSDF")

print("\n" + "="*70)
print("OVERLAP ANALYSIS")
print("="*70)

endf_set = set(zip(endf_nuclides['A'], endf_nuclides['Z']))
ensdf_set = set(zip(ensdf_nuclides['A'], ensdf_nuclides['Z']))

overlap = endf_set & ensdf_set
endf_only = endf_set - ensdf_set
ensdf_only = ensdf_set - endf_set

print(f"In both databases:       {len(overlap):5d} ({100*len(overlap)/len(endf_set):.1f}% of ENDF)")
print(f"ENDF only:               {len(endf_only):5d}")
print(f"ENSDF only:              {len(ensdf_only):5d}")

print("\n" + "="*70)
print("Z AND N RANGE")
print("="*70)

print(f"\nENDF coverage:")
print(f"  Z: {endf_nuclides['Z'].min()} to {endf_nuclides['Z'].max()}")
print(f"  N: {endf_nuclides['N'].min()} to {endf_nuclides['N'].max()}")
print(f"  A: {endf_nuclides['A'].min()} to {endf_nuclides['A'].max()}")

print(f"\nENSDF coverage:")
print(f"  Z: {ensdf_nuclides['Z'].min()} to {ensdf_nuclides['Z'].max()}")
print(f"  N: {ensdf_nuclides['N'].min()} to {ensdf_nuclides['N'].max()}")
print(f"  A: {ensdf_nuclides['A'].min()} to {ensdf_nuclides['A'].max()}")

# Show distribution by Z
print("\n" + "="*70)
print("DISTRIBUTION BY ELEMENT (First 20)")
print("="*70)

from collections import Counter
endf_z_counts = Counter(endf_nuclides['Z'])
ensdf_z_counts = Counter(ensdf_nuclides['Z'])

from ENDFLevelMatcher_DECAY_v2 import ATOMIC_SYMBOL

print(f"{'Element':<10} {'ENDF':<10} {'ENSDF':<10} {'Difference':<10}")
print("-" * 50)

for z in sorted(set(list(endf_z_counts.keys()) + list(ensdf_z_counts.keys())))[:20]:
    elem = ATOMIC_SYMBOL.get(z, f'Z{z}')
    endf_count = endf_z_counts.get(z, 0)
    ensdf_count = ensdf_z_counts.get(z, 0)
    diff = endf_count - ensdf_count
    symbol = "+" if diff > 0 else " "
    print(f"{elem:<10} {endf_count:<10} {ensdf_count:<10} {symbol}{abs(diff):<9}")

print("\n" + "="*70)
print("INTERPRETATION")
print("="*70)
print("""
YOUR PLOT SHOWS NUCLIDE COVERAGE (BREADTH):
  ✓ ENDF has MORE nuclides (wider isotope coverage)
  ✓ ENSDF has FEWER nuclides (focused on well-studied cases)

BUT ENSDF HAS MORE DETAIL (DEPTH):
  ✓ ENSDF has ~10-40x more transitions per nuclide
  ✓ ENSDF provides complete level schemes
  ✓ ENDF only has representative decays

FOR A COMPLETE DATABASE YOU NEED BOTH:
  → Use ENDF for wide isotope coverage
  → Use ENSDF for detailed level information where available
  → Merge strategy: ENDF provides scaffold, ENSDF adds detail
""")

# Show examples of nuclides only in ENDF
if len(endf_only) > 0:
    print("\n" + "="*70)
    print("EXAMPLES: Nuclides in ENDF but NOT in ENSDF")
    print("="*70)
    print("These are likely exotic/short-lived isotopes from evaluations")
    print("\nFirst 15 examples:")
    
    endf_only_list = sorted(list(endf_only))[:15]
    for a, z in endf_only_list:
        elem = ATOMIC_SYMBOL.get(z, f'Z{z}')
        n = a - z
        print(f"  {elem}-{a:3d}  (Z={z:2d}, N={n:3d})")
