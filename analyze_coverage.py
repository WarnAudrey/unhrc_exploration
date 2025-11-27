#!/usr/bin/env python3
"""
Analyze nuclide coverage: ENDF vs ENSDF
"""

import pandas as pd
import numpy as np

endf_path = "/Users/audreywarn/fluka-db-audrey/outputs/endf/endf_data_modules/ascii/DECAY.ascii"
ensdf_path = "/Users/audreywarn/fluka-db-audrey/outputs/ensdf/json_data_modules/ascii/DECAY.ascii"

print("="*70)
print("ENDF vs ENSDF: COVERAGE ANALYSIS")
print("="*70)

# Load ENDF
endf_df = pd.read_csv(endf_path, sep=r'\s+', comment='#', 
                      index_col=[0,1,2,3,4], engine='python')
endf_reset = endf_df.reset_index()

# Load ENSDF  
ensdf_df = pd.read_csv(ensdf_path, sep=r'\s+', comment='#',
                       index_col=[0,1,2,3,4], engine='python')
ensdf_reset = ensdf_df.reset_index()

print("\n" + "="*70)
print("TRANSITION COUNT (Depth)")
print("="*70)
print(f"ENDF total transitions:  {len(endf_reset):6d}")
print(f"ENSDF total transitions: {len(ensdf_reset):6d}")
print(f"Ratio (ENSDF/ENDF):      {len(ensdf_reset)/len(endf_reset):6.1f}x")

print("\n" + "="*70)
print("NUCLIDE COUNT (Breadth)")
print("="*70)

# Count unique nuclides (A, Z combinations)
endf_nuclides = endf_reset[['A', 'Z']].drop_duplicates()
ensdf_nuclides = ensdf_reset[['A', 'Z']].drop_duplicates()

print(f"ENDF unique nuclides:    {len(endf_nuclides):6d}")
print(f"ENSDF unique nuclides:   {len(ensdf_nuclides):6d}")

if len(endf_nuclides) > len(ensdf_nuclides):
    print(f"✓ ENDF covers MORE nuclides ({len(endf_nuclides) - len(ensdf_nuclides)} more)")
else:
    print(f"✓ ENSDF covers MORE nuclides ({len(ensdf_nuclides) - len(endf_nuclides)} more)")

print("\n" + "="*70)
print("OVERLAP ANALYSIS")
print("="*70)

# Find overlap
endf_set = set(zip(endf_nuclides['A'], endf_nuclides['Z']))
ensdf_set = set(zip(ensdf_nuclides['A'], ensdf_nuclides['Z']))

overlap = endf_set & ensdf_set
endf_only = endf_set - ensdf_set
ensdf_only = ensdf_set - endf_set

print(f"In both databases:       {len(overlap):6d}")
print(f"ENDF only:               {len(endf_only):6d}")
print(f"ENSDF only:              {len(ensdf_only):6d}")

print("\n" + "="*70)
print("AVERAGE TRANSITIONS PER NUCLIDE")
print("="*70)

endf_avg = len(endf_reset) / len(endf_nuclides)
ensdf_avg = len(ensdf_reset) / len(ensdf_nuclides)

print(f"ENDF:  {endf_avg:6.1f} transitions/nuclide")
print(f"ENSDF: {ensdf_avg:6.1f} transitions/nuclide")

print("\n" + "="*70)
print("INTERPRETATION")
print("="*70)

if len(endf_nuclides) > len(ensdf_nuclides):
    print("""
ENDF has WIDER coverage (more isotopes)
ENSDF has DEEPER coverage (more transitions per isotope)

This means:
  - ENDF: Broad but shallow (one entry per decay mode)
  - ENSDF: Narrow but deep (complete level schemes)
  
Your plot likely shows NUCLIDE coverage → ENDF wins
But for COMPLETE decay schemes → ENSDF wins
""")
else:
    print("""
ENSDF has both wider AND deeper coverage
ENDF is a subset
""")

# Show some examples of ENDF-only nuclides
if len(endf_only) > 0:
    print("\n" + "="*70)
    print("EXAMPLES: NUCLIDES IN ENDF BUT NOT ENSDF")
    print("="*70)
    endf_only_list = sorted(list(endf_only))[:20]
    for a, z in endf_only_list:
        # Get element symbol
        from ENDFLevelMatcher_DECAY_v2 import ATOMIC_SYMBOL
        elem = ATOMIC_SYMBOL.get(z, f'Z{z}')
        print(f"  {elem}-{a} (A={a}, Z={z})")
    
    if len(endf_only) > 20:
        print(f"  ... and {len(endf_only)-20} more")

if len(ensdf_only) > 0:
    print("\n" + "="*70)
    print("EXAMPLES: NUCLIDES IN ENSDF BUT NOT ENDF")
    print("="*70)
    ensdf_only_list = sorted(list(ensdf_only))[:20]
    for a, z in ensdf_only_list:
        from ENDFLevelMatcher_DECAY_v2 import ATOMIC_SYMBOL
        elem = ATOMIC_SYMBOL.get(z, f'Z{z}')
        print(f"  {elem}-{a} (A={a}, Z={z})")
    
    if len(ensdf_only) > 20:
        print(f"  ... and {len(ensdf_only)-20} more")
