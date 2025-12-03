#!/usr/bin/env python3
"""
Analyze the 1,045 failures that remain even with 50 keV tolerance.

These represent cases where:
- Energy difference > 250 keV (minimum failure at 50 keV tolerance)
- Likely physics issues, not just tolerance problems
"""

import pandas as pd
import numpy as np

print("="*80)
print("ANALYSIS: Remaining Failures at 50 keV Tolerance")
print("="*80)

print("\nLoading matches_50keV.txt...")

# Read the detailed match file
try:
    df = pd.read_csv('/Users/audreywarn/fluka-db-audrey/src/PyClasses/matches_50keV.txt', 
                     sep=r'\s+', engine='python')
    print(f"Loaded {len(df)} total entries")
    
    # Filter for failures only
    failures = df[df['matched'] == 0].copy()
    print(f"Found {len(failures)} failures")
    
    # Add energy difference in keV (convert from whatever unit)
    # The diff_keV column should already exist
    
    print("\n" + "="*80)
    print("FAILURE BREAKDOWN BY ENERGY DIFFERENCE")
    print("="*80)
    
    # Categorize by energy difference
    categories = {
        "250-500 keV": (250, 500),
        "500-1000 keV": (500, 1000),
        "1-2 MeV": (1000, 2000),
        "2-5 MeV": (2000, 5000),
        "5-10 MeV": (5000, 10000),
        ">10 MeV": (10000, np.inf)
    }
    
    for cat_name, (min_kev, max_kev) in categories.items():
        count = len(failures[(failures['diff_keV'] >= min_kev) & 
                            (failures['diff_keV'] < max_kev)])
        pct = 100 * count / len(failures) if len(failures) > 0 else 0
        print(f"{cat_name:20s}: {count:4d} ({pct:5.1f}%)")
    
    print("\n" + "="*80)
    print("FAILURE BREAKDOWN BY DECAY MODE")
    print("="*80)
    
    if 'decay_mode' in failures.columns:
        mode_counts = failures['decay_mode'].value_counts()
        for mode, count in mode_counts.items():
            pct = 100 * count / len(failures)
            print(f"{mode:15s}: {count:4d} ({pct:5.1f}%)")
    
    print("\n" + "="*80)
    print("SPECIFIC PROBLEMATIC CASES (Top 20 by energy difference)")
    print("="*80)
    
    # Sort by energy difference and show top 20
    failures_sorted = failures.sort_values('diff_keV', ascending=False)
    
    display_cols = ['Parent', 'Daughter', 'decay_mode', 'diff_keV', 'quality']
    if all(col in failures_sorted.columns for col in display_cols):
        print(failures_sorted[display_cols].head(20).to_string())
    else:
        print("Available columns:", failures_sorted.columns.tolist())
        print(failures_sorted.head(20).to_string())
    
    print("\n" + "="*80)
    print("DELAYED PARTICLE DECAYS IN FAILURES")
    print("="*80)
    
    # Check for β-delayed particle modes
    if 'decay_mode' in failures.columns:
        delayed_modes = failures[failures['decay_mode'].str.contains('-', na=False) & 
                                ~failures['decay_mode'].isin(['B-', 'B+'])]
        
        if not delayed_modes.empty:
            print(f"Found {len(delayed_modes)} delayed particle failures")
            print("\nDelayed particle modes:")
            for mode in delayed_modes['decay_mode'].unique():
                count = len(delayed_modes[delayed_modes['decay_mode'] == mode])
                print(f"  {mode}: {count} failures")
            
            print("\nTop 10 delayed particle failures:")
            display_cols = ['Parent', 'Daughter', 'decay_mode', 'diff_keV']
            if all(col in delayed_modes.columns for col in display_cols):
                print(delayed_modes.sort_values('diff_keV', ascending=False)[display_cols].head(10).to_string())
        else:
            print("No delayed particle failures found")
    
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    print(f"\nTotal failures: {len(failures)}")
    print(f"Mean energy difference: {failures['diff_keV'].mean():.1f} keV")
    print(f"Median energy difference: {failures['diff_keV'].median():.1f} keV")
    print(f"Min energy difference: {failures['diff_keV'].min():.1f} keV")
    print(f"Max energy difference: {failures['diff_keV'].max():.1f} keV")
    
    # Recovery potential
    within_100 = len(failures[failures['diff_keV'] <= 100])
    within_500 = len(failures[failures['diff_keV'] <= 500])
    within_1000 = len(failures[failures['diff_keV'] <= 1000])
    
    print(f"\nRecovery potential with higher tolerance:")
    print(f"  100 keV: {within_100} failures ({100*within_100/len(failures):.1f}%)")
    print(f"  500 keV: {within_500} failures ({100*within_500/len(failures):.1f}%)")
    print(f"  1 MeV:   {within_1000} failures ({100*within_1000/len(failures):.1f}%)")
    
    print("\n" + "="*80)
    print("LIKELY ROOT CAUSES")
    print("="*80)
    
    print("""
Based on the failure patterns:

1. MODERATE FAILURES (250-500 keV):
   - Q-value evaluation differences between ENDF and ENSDF
   - Decay to excited states not well-matched
   - Could try 100-200 keV tolerance

2. LARGE FAILURES (>1 MeV):
   - β-delayed particle emission (β-n, β-2n, etc.)
   - Daughter nucleus calculation may be wrong
   - ENDF may combine multiple decay branches
   - Missing ENSDF transitions for exotic nuclei

3. EXTREME FAILURES (>10 MeV):
   - Likely systematic database issues
   - Wrong decay mode identification
   - Or very exotic nuclear structure
    """)

except FileNotFoundError:
    print("Error: matches_50keV.txt not found!")
    print("Make sure you ran: python ENDFLevelMatching.py --abs-tol 50000 --export-details matches_50keV.txt")
except Exception as e:
    print(f"Error analyzing file: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80 + "\n")
