#!/usr/bin/env python3
"""
Diagnose parent level matching
"""

import sys
sys.path.insert(0, '/workspace')

# Import the matcher
from ENDFLevelMatcher_DECAY_v2 import ENDFLevelMatcherDECAY

# Create matcher with default paths
endf_path = "/Users/audreywarn/fluka-db-audrey/outputs/endf/endf_data_modules/ascii/DECAY.ascii"
ensdf_path = "/Users/audreywarn/fluka-db-audrey/outputs/ensdf/json_data_modules/ascii/DECAY.ascii"

print("="*70)
print("DIAGNOSTIC: Parent Level Matching")
print("="*70)

# Check ENSDF parent level distribution
print("\nAnalyzing ENSDF parent level distribution...")
try:
    import pandas as pd
    import numpy as np
    
    # Read ENSDF with simple parser
    ensdf_df = pd.read_csv(ensdf_path, sep=r'\s+', comment='#', engine='python')
    
    if 'parentLevel' in ensdf_df.columns:
        print("\nENSDF Parent Level Distribution:")
        parent_counts = ensdf_df['parentLevel'].value_counts().sort_index().head(10)
        for level, count in parent_counts.items():
            print(f"  parentLevel = {level}: {count} transitions")
        
        non_zero_parents = (ensdf_df['parentLevel'] > 0).sum()
        total = len(ensdf_df)
        print(f"\nTotal transitions with parentLevel > 0: {non_zero_parents}/{total} ({100*non_zero_parents/total:.1f}%)")
        
        if non_zero_parents > 0:
            print("\nExample transitions from excited parent states:")
            excited_parents = ensdf_df[ensdf_df['parentLevel'] > 0].head(10)
            print(excited_parents[['A', 'Z', 'parentLevel', 'decay_mode', 'final_level']].to_string())
    else:
        print("Note: parentLevel column not found in ENSDF DataFrame")
        print(f"Columns: {ensdf_df.columns.tolist()}")
    
    # Check if ENSDF is MultiIndex
    if isinstance(ensdf_df.index, pd.MultiIndex):
        print("\nENSDF has MultiIndex, checking index names...")
        print(f"Index names: {ensdf_df.index.names}")
        
        # Reset index to access parentLevel
        ensdf_reset = ensdf_df.reset_index()
        if 'parentLevel' in ensdf_reset.columns:
            parent_counts = ensdf_reset['parentLevel'].value_counts().sort_index().head(10)
            print("\nParent Level Distribution (from index):")
            for level, count in parent_counts.items():
                print(f"  parentLevel = {level}: {count} transitions")
            
            non_zero = (ensdf_reset['parentLevel'] > 0).sum()
            total = len(ensdf_reset)
            print(f"\nTransitions with parentLevel > 0: {non_zero}/{total} ({100*non_zero/total:.1f}%)")
            
            if non_zero > 0:
                print("\nExamples with excited parent states:")
                examples = ensdf_reset[ensdf_reset['parentLevel'] > 0][['A', 'Z', 'parentLevel', 'decay_mode', 'final_level']].head(10)
                print(examples.to_string(index=False))

except Exception as e:
    print(f"Error analyzing ENSDF: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*70)
print("CONCLUSION:")
print("="*70)
print("""
If ENSDF shows mostly parentLevel=0:
  → This is NORMAL - most radioactive decays occur from ground states
  → Only isomeric states (long-lived excited states) decay from parentLevel>0
  → Your matching results showing parentLevel=0 are CORRECT

If ENSDF has many parentLevel>0 entries:
  → Check diagnostics file to see if parent_level_matched has non-zero values
  → The save function should copy parent_level_matched → parentLevel
""")
