#!/usr/bin/env python3
"""
Investigate specific failed matches to understand root causes.

This script shows what ENSDF knows about the daughter nucleus and why matching failed.
"""

# Specific cases to investigate
cases = {
    "Be-12 → B-12 (14 keV difference)": {
        "parent_A": 12, "parent_Z": 4,
        "daughter_A": 12, "daughter_Z": 5,
        "endf_energy_keV": None,  # Would need to read from file
        "q_ground_keV": None,
        "calculated_daughter_level_keV": None,
        "tolerance_keV": 1.0,
        "analysis": """
        POSSIBLE CAUSES:
        1. Q-value uncertainty between ENDF and ENSDF evaluations
        2. Different rounding conventions
        3. Excited state decay that looks like ground state
        
        SOLUTION:
        - Increase absolute tolerance to 20 keV
        - This is within typical nuclear data uncertainties
        """
    },
    
    "N-13 → C-13 (2.2 MeV difference)": {
        "parent_A": 13, "parent_Z": 7,
        "daughter_A": 13, "daughter_Z": 6,
        "analysis": """
        POSSIBLE CAUSES:
        1. ENDF entry represents decay to excited C-13 state (~2.2 MeV)
        2. ENSDF may not have this transition cataloged
        3. Different branching ratio conventions
        
        QUESTIONS TO ASK:
        - Does C-13 have an excited state at ~2.2 MeV?
        - Is this a β+ decay that ENDF treats differently?
        - Check ENSDF for C-13 level structure
        """
    },
    
    "Be-14 → B-14 (14.9 MeV difference)": {
        "parent_A": 14, "parent_Z": 4,
        "daughter_A": 14, "daughter_Z": 5,
        "analysis": """
        POSSIBLE CAUSES:
        1. Be-14 is very neutron-rich (Q_beta ~ 12-15 MeV)
        2. May be β-delayed neutron emission (β-n mode)
        3. Multiple decay branches not properly separated
        4. Q-value for different decay channel
        
        INVESTIGATION NEEDED:
        - Check if ENDF decay_mode is "B-N" (beta-delayed neutron)
        - This would change daughter nucleus calculation
        - May need special handling for exotic decays
        """
    },
    
    "O-13 → N-13 (7.5 MeV difference)": {
        "parent_A": 13, "parent_Z": 8,
        "daughter_A": 13, "daughter_Z": 7,
        "analysis": """
        POSSIBLE CAUSES:
        1. O-13 β+ decay or EC (electron capture)
        2. High Q-value for proton-rich nucleus
        3. Decay to highly excited N-13 state
        4. Two identical entries (7509.9 and 7510.0 keV) suggest data issue
        
        DATA QUALITY CHECK:
        - Why are there two O-13 entries with identical energy?
        - May be duplicate records in ENDF
        - Check ENDF file for O-13
        """
    }
}

print("="*80)
print("SPECIFIC FAILURE INVESTIGATION")
print("="*80)

for case_name, details in cases.items():
    print(f"\n{'='*80}")
    print(f"CASE: {case_name}")
    print(f"{'='*80}")
    
    if "parent_A" in details:
        print(f"\nParent:   A={details['parent_A']}, Z={details['parent_Z']}")
        print(f"Daughter: A={details['daughter_A']}, Z={details['daughter_Z']}")
    
    print(f"\n{details['analysis']}")

print("\n" + "="*80)
print("GENERAL DIAGNOSTIC QUESTIONS")
print("="*80)

print("""
To diagnose failures, ask these questions:

1. TOLERANCE ISSUES (small differences <100 keV):
   Q: Is the difference within expected nuclear data uncertainties?
   → If YES: Increase absolute tolerance
   → If NO: Investigate Q-value differences

2. EXCITED STATE DECAYS (100-500 keV differences):
   Q: Does the daughter have an excited state at calculated energy?
   → Check ENSDF LEVEL.ascii for daughter nucleus
   → Look for levels near Q_ground - E_particle
   → May indicate transition catalog is incomplete

3. LARGE DIFFERENCES (>500 keV):
   Q: Is this a complex decay mode (β-delayed particles)?
   → Check ENDF decay_mode field
   → β-n, β-2n, β-α modes have different kinematics
   → May need special daughter nucleus calculation

4. DUPLICATE ENERGIES:
   Q: Are there multiple ENDF entries with same/similar energies?
   → May indicate different final states
   → Check if ENDF lists multiple branches
   → Possible data quality issue

5. Q-VALUE MISMATCHES:
   Q: Do ENDF and ENSDF agree on ground→ground Q-value?
   → Compare q_ground_lookup values
   → Check if evaluations are from different years
   → Systematic offset indicates database incompatibility
""")

print("="*80)
print("RECOMMENDED DIAGNOSTIC COMMANDS")
print("="*80)

print("""
# Export detailed match information
python ENDFLevelMatching.py --export-details all_matches.txt

# Look at Q-values for specific nucleus
grep "Be-12" all_matches.txt
grep "N-13" all_matches.txt

# Check ENSDF level structure
grep "^12  5" LEVEL.ascii  # B-12 levels
grep "^13  6" LEVEL.ascii  # C-13 levels

# Check ENDF decay modes
grep "^12  4" DECAY.ascii  # Be-12 decays
grep "^14  4" DECAY.ascii  # Be-14 decays

# Count failures by magnitude
awk '$9=="failed" && $11<50 {count++} END {print count, "failures <50 keV"}' DECAY_level_matched_diagnostics.ascii
awk '$9=="failed" && $11>5000 {count++} END {print count, "failures >5 MeV"}' DECAY_level_matched_diagnostics.ascii
""")

print("="*80 + "\n")
