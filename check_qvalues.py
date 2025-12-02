#!/usr/bin/env python3
"""
Quick diagnostic script to check Q-values for Li-11 and Be-12 cases.
Run this AFTER loading your matcher to see what Q-values are being used.
"""

import sys
sys.path.append('/Users/audreywarn/fluka-db-audrey/src/PyClasses')

# Import your matcher
from ENDFLevelMatching import ENDFLevelMatcher

print("="*70)
print("Q-VALUE DIAGNOSTIC SCRIPT")
print("="*70)

# Initialize matcher
print("\nInitializing matcher...")
matcher = ENDFLevelMatcher(
    endf_decay_path="/Users/audreywarn/fluka-db-audrey/outputs/endf/endf_data_modules/ascii/DECAY.ascii",
    ensdf_decay_path="/Users/audreywarn/fluka-db-audrey/outputs/ensdf/json_data_modules/ascii/DECAY.ascii",
    ensdf_level_path="/Users/audreywarn/fluka-db-audrey/outputs/ensdf/json_data_modules/ascii/LEVEL.ascii"
)

print("\n" + "="*70)
print("Q-VALUE ANALYSIS")
print("="*70)
print(f"Total Q-values in lookup: {len(matcher.q_ground_lookup)}")

# Check Li-11 specifically
print("\n" + "-"*70)
print("CASE 1: Li-11 B- decay (FAILS at 50 keV with 320 keV difference)")
print("-"*70)
key = (11, 3, 'B-')
if key in matcher.q_ground_lookup:
    q = matcher.q_ground_lookup[key]
    print(f"Q_ground used: {q/1e3:.2f} keV")
    
    if key in matcher.transition_lookup:
        print(f"Source: ENSDF (has transitions)")
        transitions = matcher.transition_lookup[key]
        print(f"Number of ENSDF transitions: {len(transitions)}")
        print("\nENSDF transitions:")
        for i, trans in enumerate(transitions[:3]):
            print(f"  {i+1}. parent_level={trans['parent_level']}, "
                  f"daughter_level={trans['daughter_level']}, "
                  f"particle_energy={trans['particle_energy']/1e3:.2f} keV")
    else:
        print(f"Source: ENDF (no ENSDF transitions)")
else:
    print("NOT FOUND in Q-value lookup!")

# Check daughter levels
daughter_key = (11, 4)
if daughter_key in matcher.daughter_levels:
    be11_levels = matcher.daughter_levels[daughter_key]
    print(f"\nBe-11 daughter levels (from ENSDF LEVEL.ascii):")
    for level_num in sorted(be11_levels.keys())[:5]:
        print(f"  Level {level_num}: {be11_levels[level_num]/1e3:.2f} keV")
    
    # Calculate what ENDF thinks
    if key in matcher.q_ground_lookup:
        q = matcher.q_ground_lookup[key]
        # ENDF entry
        print(f"\nENDF Li-11 decay:")
        print(f"  Particle energy: 20,230 keV (from your ENDF file)")
        print(f"  Q_ground used: {q/1e3:.2f} keV")
        endf_calculated = q - 20230e3
        print(f"  Calculated daughter level: {endf_calculated/1e3:.2f} keV")
        
        # Compare to ENSDF levels
        print(f"\nComparison:")
        print(f"  ENDF calculates: {endf_calculated/1e3:.2f} keV")
        print(f"  ENSDF level 0: {be11_levels[0]/1e3:.2f} keV")
        if 1 in be11_levels:
            print(f"  ENSDF level 1: {be11_levels[1]/1e3:.2f} keV")
            diff_level0 = abs(endf_calculated - be11_levels[0])
            diff_level1 = abs(endf_calculated - be11_levels[1])
            print(f"\n  Difference to level 0: {diff_level0/1e3:.2f} keV")
            print(f"  Difference to level 1: {diff_level1/1e3:.2f} keV")
            print(f"\n  → Algorithm picks closest: level {0 if diff_level0 < diff_level1 else 1}")
            print(f"  → Difference: {min(diff_level0, diff_level1)/1e3:.2f} keV")

# Check Be-12 for comparison
print("\n" + "-"*70)
print("CASE 2: Be-12 B- decay (MATCHES at 50 keV with 14 keV difference)")
print("-"*70)
key2 = (12, 4, 'B-')
if key2 in matcher.q_ground_lookup:
    q2 = matcher.q_ground_lookup[key2]
    print(f"Q_ground used: {q2/1e3:.2f} keV")
    source = 'ENSDF' if key2 in matcher.transition_lookup else 'ENDF'
    print(f"Source: {source}")
    
    if key2 in matcher.transition_lookup:
        transitions2 = matcher.transition_lookup[key2]
        print(f"Number of ENSDF transitions: {len(transitions2)}")

# Check B-12 daughter levels
daughter_key2 = (12, 5)
if daughter_key2 in matcher.daughter_levels:
    b12_levels = matcher.daughter_levels[daughter_key2]
    print(f"\nB-12 daughter levels (from ENSDF LEVEL.ascii):")
    for level_num in sorted(b12_levels.keys())[:5]:
        print(f"  Level {level_num}: {b12_levels[level_num]/1e3:.2f} keV")
    
    if key2 in matcher.q_ground_lookup:
        q2 = matcher.q_ground_lookup[key2]
        print(f"\nENDF Be-12 decay:")
        print(f"  Particle energy: 11,710 keV (from your ENDF file)")
        print(f"  Q_ground used: {q2/1e3:.2f} keV")
        endf_calculated2 = q2 - 11710e3
        print(f"  Calculated daughter level: {endf_calculated2/1e3:.2f} keV")
        
        print(f"\nComparison:")
        print(f"  ENDF calculates: {endf_calculated2/1e3:.2f} keV")
        print(f"  ENSDF level 0: {b12_levels[0]/1e3:.2f} keV")
        diff = abs(endf_calculated2 - b12_levels[0])
        print(f"  Difference: {diff/1e3:.2f} keV")

print("\n" + "="*70)
print("SUMMARY")
print("="*70)
print("""
If Li-11 shows 320 keV difference to closest ENSDF level:
→ Q-value mismatch between ENDF and ENSDF databases

If Be-12 shows 14 keV difference:
→ Normal evaluation uncertainty (matches with 50 keV tolerance)

Both ENDF and ENSDF are from 2025, so Q-values SHOULD agree.
If they don't, this suggests:
1. Different evaluation methods
2. Different reference data
3. Possible data extraction error
""")
print("="*70 + "\n")
