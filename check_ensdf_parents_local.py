#!/usr/bin/env python3
"""
Check ENSDF parent level distribution
Run this on your local machine
"""
import pandas as pd
import numpy as np

ensdf_path = "/Users/audreywarn/fluka-db-audrey/outputs/ensdf/json_data_modules/ascii/DECAY.ascii"

print("="*70)
print("ENSDF PARENT LEVEL ANALYSIS")
print("="*70)

# Read ENSDF - try MultiIndex first
try:
    df = pd.read_csv(ensdf_path, sep=r'\s+', comment='#', 
                     index_col=[0,1,2,3,4], engine='python')
    print(f"\nTotal ENSDF transitions: {len(df)}")
    
    # Reset index to access parentLevel
    df_reset = df.reset_index()
    
    if 'parentLevel' in df_reset.columns:
        parent_counts = df_reset['parentLevel'].value_counts().sort_index().head(15)
        print("\nParent Level Distribution:")
        for level, count in parent_counts.items():
            pct = 100 * count / len(df_reset)
            print(f"  parentLevel = {int(level):3d}: {count:6d} ({pct:5.1f}%)")
        
        non_zero = (df_reset['parentLevel'] > 0).sum()
        zero = (df_reset['parentLevel'] == 0).sum()
        print(f"\n  Ground state (0): {zero:6d} ({100*zero/len(df_reset):.1f}%)")
        print(f"  Excited (>0):     {non_zero:6d} ({100*non_zero/len(df_reset):.1f}%)")
        
        if non_zero > 0:
            print("\n" + "="*70)
            print("EXAMPLES OF EXCITED PARENT STATE DECAYS (first 20):")
            print("="*70)
            excited = df_reset[df_reset['parentLevel'] > 0].head(20)
            cols = ['A', 'Z', 'parentLevel', 'decay_mode', 'final_level']
            if 'Endpoint_energy' in excited.columns:
                cols.append('Endpoint_energy')
            print(excited[cols].to_string(index=False))
            
            # Also show how many unique parents have excited states
            unique_excited_parents = excited.groupby(['A', 'Z', 'parentLevel']).size()
            print(f"\nUnique parent nuclei with excited state decays: {len(unique_excited_parents)}")
        
        print("\n" + "="*70)
        print("CONCLUSION:")
        print("="*70)
        if non_zero == 0:
            print("✓ ALL ENSDF transitions have parentLevel=0 (ground states)")
            print("✓ Your output showing parentLevel=0 everywhere is CORRECT")
            print("✓ This is normal - most radioactive decays occur from ground states")
            print("\nExplanation:")
            print("  - Excited states decay via gamma emission (picoseconds)")
            print("  - Only long-lived isomers undergo beta/alpha decay from excited levels")
            print("  - Examples: Tc-99m, Co-60m, Am-242m")
        else:
            print(f"⚠ ENSDF has {non_zero} transitions from excited parent states")
            print("⚠ But diagnostics show parent_level_matched is all zeros")
            print("\nPossible reasons:")
            print("  1. ENDF doesn't have entries for these excited parents (most likely)")
            print("  2. Energy matching fails for excited state transitions")
            print("  3. These are rare isomers not in ENDF database")
            
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
