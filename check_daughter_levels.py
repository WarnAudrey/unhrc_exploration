#!/usr/bin/env python3
"""
Check if ENSDF LEVEL.ascii has the daughter levels that ENDF predicts.

This investigates whether failed matches are due to:
1. Missing ENSDF levels (incomplete database)
2. Energy mismatches (evaluation differences)
"""

import sys

# Specific failed beta decays to investigate
cases = [
    {
        "name": "Be-7 → Li-7 (β+ or EC)",
        "parent_A": 7, "parent_Z": 4,
        "daughter_A": 7, "daughter_Z": 3,
        "diff_keV": 384.10,
        "expected_level_keV": "~384 keV in Li-7",
        "check": "Does Li-7 have a level near 384 keV or 478 keV (known first excited)?"
    },
    {
        "name": "Li-11 → Be-11 (β-)",
        "parent_A": 11, "parent_Z": 3,
        "daughter_A": 11, "daughter_Z": 4,
        "diff_keV": 320.00,
        "expected_level_keV": "~320 keV in Be-11",
        "check": "Does Be-11 have a level near 320 keV?"
    },
    {
        "name": "N-13 → C-13 (β+)",
        "parent_A": 13, "parent_Z": 7,
        "daughter_A": 13, "daughter_Z": 6,
        "diff_keV": 2220.00,
        "expected_level_keV": "~2220 keV in C-13",
        "check": "Does C-13 have a level near 2.22 MeV? (known excited state at 3.09 MeV)"
    },
    {
        "name": "Be-12 → B-12 (β-)",
        "parent_A": 12, "parent_Z": 4,
        "daughter_A": 12, "daughter_Z": 5,
        "diff_keV": 14.00,
        "expected_level_keV": "~14 keV in B-12 OR near ground state",
        "check": "Is this essentially ground state with small energy difference?"
    }
]

print("="*80)
print("INVESTIGATING: Do ENSDF Daughter Levels Exist?")
print("="*80)
print("""
For beta decays, energy conservation requires:
    E_daughter_level = Q_ground - E_particle

If matching fails, either:
1. ENSDF LEVEL.ascii doesn't have this excited state (incomplete)
2. ENSDF has it but at different energy (evaluation difference)
3. Q_ground value is wrong
""")

for case in cases:
    print("\n" + "="*80)
    print(f"CASE: {case['name']}")
    print("="*80)
    print(f"Parent:  A={case['parent_A']}, Z={case['parent_Z']}")
    print(f"Daughter: A={case['daughter_A']}, Z={case['daughter_Z']}")
    print(f"Energy difference: {case['diff_keV']:.2f} keV")
    print(f"\nExpected: {case['expected_level_keV']}")
    print(f"Question: {case['check']}")
    print("\nTO INVESTIGATE:")
    print(f"  grep '^{case['daughter_A']:3d} {case['daughter_Z']:2d}' LEVEL.ascii")
    print(f"  # Look for levels near {case['diff_keV']:.0f} keV")

print("\n" + "="*80)
print("DIAGNOSTIC COMMANDS")
print("="*80)

print("""
# Check Li-7 levels (for Be-7 → Li-7 case)
grep '^  7  3' /path/to/ENSDF/LEVEL.ascii | head -20

# Check Be-11 levels (for Li-11 → Be-11 case)
grep '^ 11  4' /path/to/ENSDF/LEVEL.ascii | head -20

# Check C-13 levels (for N-13 → C-13 case)
grep '^ 13  6' /path/to/ENSDF/LEVEL.ascii | head -20

# Check B-12 levels (for Be-12 → B-12 case)
grep '^ 12  5' /path/to/ENSDF/LEVEL.ascii | head -20
""")

print("="*80)
print("KEY QUESTIONS TO ANSWER")
print("="*80)

print("""
For EACH failed match:

1. Does ENSDF LEVEL.ascii have the daughter nucleus at all?
   → If NO: ENSDF is incomplete (expected for exotic nuclei)
   → If YES: Continue to #2

2. Does ENSDF have a level NEAR the calculated energy?
   → Check within ±100 keV of calculated value
   → If NO: ENSDF level structure incomplete
   → If YES: Continue to #3

3. What is the EXACT energy difference?
   → If <50 keV: Evaluation difference (increase tolerance)
   → If 50-500 keV: Possible systematic offset
   → If >500 keV: Wrong level OR wrong Q_ground

4. Is the Q_ground value correct?
   → Compare ENDF vs ENSDF Q-values for same decay
   → Check if they agree within ~10 keV
   → If they differ significantly: Database inconsistency

5. For very close matches (<20 keV):
   → Almost certainly the right level
   → Just need higher tolerance
   → Example: Be-12 → B-12 (14 keV) is likely ground state

6. For large mismatches (>1 MeV):
   → Check if decay mode is actually β-n (beta-delayed neutron)
   → Check if ENDF entry combines multiple branches
   → May be systematic database issue
""")

print("="*80)
print("EXPECTED FINDINGS")
print("="*80)

print("""
Based on nuclear physics knowledge:

Li-7 levels:
  - Ground state: 0 keV
  - First excited: 478 keV (1/2-)
  
  Prediction: Be-7 → Li-7 with 384 keV diff might be:
    a) Aiming for 478 keV level (94 keV off)
    b) Different Q_ground evaluation
    c) Missing intermediate level

Be-11 levels:
  - Ground state: 0 keV
  - First excited: 320 keV (1/2+)
  
  Prediction: Li-11 → Be-11 with 320 keV diff is probably:
    ✓ Exactly the first excited state!
    → Should match with higher tolerance

C-13 levels:
  - Ground state: 0 keV
  - First excited: 3089 keV (1/2+)
  
  Prediction: N-13 → C-13 with 2220 keV diff:
    - Not close to 3089 keV
    - Might be missing level in ENSDF
    - Or wrong Q_ground

B-12 levels:
  - Ground state: 0 keV
  - Highly excited states
  
  Prediction: Be-12 → B-12 with 14 keV diff:
    ✓ Essentially ground state
    → Should match with 20 keV tolerance
""")

print("="*80)
print("ACTION ITEMS")
print("="*80)

print("""
1. IMMEDIATE: Run these commands to check ENSDF levels:
   
   # Export detailed match info
   python ENDFLevelMatching.py --export-details all_matches.txt
   
   # Look at specific cases
   grep "Be-7" all_matches.txt
   grep "Li-11" all_matches.txt
   grep "N-13" all_matches.txt

2. CHECK ENSDF: Look at actual LEVEL.ascii entries:
   
   # This will show you if the levels exist
   grep "^  7  3" LEVEL.ascii  # Li-7
   grep "^ 11  4" LEVEL.ascii  # Be-11
   grep "^ 13  6" LEVEL.ascii  # C-13

3. COMPARE Q_ground: Check if ENDF and ENSDF agree:
   
   # From the code's q_ground_lookup
   # Should be in diagnostic output

4. HYPOTHESIS TEST:
   
   If Be-11 has a level at exactly 320 keV:
   → Tolerance issue (increase to 20-50 keV)
   
   If Be-11 doesn't have 320 keV level:
   → ENSDF incomplete (expected for exotic nucleus)
   
   If Be-11 has level at ~330 keV (10 keV off):
   → Evaluation difference (reasonable)
""")

print("="*80 + "\n")
