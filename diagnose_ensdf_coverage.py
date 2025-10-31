#!/usr/bin/env python3
"""
Diagnostic script to analyze ENSDF JSON coverage issues.

This script examines why neutron-rich nuclides might be missing from ENSDF decay data.
"""

import os
import json
import sys
from collections import defaultdict

def analyze_json_files(json_dir):
    """Analyze JSON files to understand coverage patterns."""
    
    print(f"Analyzing JSON files in: {json_dir}")
    print("=" * 80)
    
    # Statistics
    total_files = 0
    beta_minus_files = 0
    beta_plus_files = 0
    alpha_files = 0
    delayed_files = 0
    
    # Files with/without betasTable
    files_with_betas = 0
    files_without_betas = 0
    
    # Files with/without alphasTable
    files_with_alphas = 0
    files_without_alphas = 0
    
    # Nuclide coverage by N/Z ratio
    proton_rich = []  # N < Z
    neutron_rich = []  # N > Z
    n_equals_z = []   # N == Z
    
    # Problem files
    empty_betas_table = []
    empty_alphas_table = []
    missing_decay_mode = []
    
    for filename in os.listdir(json_dir):
        if not filename.lower().endswith('.json'):
            continue
            
        total_files += 1
        filepath = os.path.join(json_dir, filename)
        
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            # Extract parent info
            parent = data.get('parents', [{}])[0]
            parent_a = parent.get('a')
            parent_z = parent.get('z')
            
            if parent_a is None or parent_z is None:
                continue
            
            parent_n = parent_a - parent_z
            
            # Get decay mode
            decay_mode = data.get('decayMode', '')
            
            if not decay_mode:
                missing_decay_mode.append((filename, parent_a, parent_z, parent_n))
                continue
            
            # Classify by decay mode
            if decay_mode == 'B-':
                beta_minus_files += 1
            elif decay_mode == 'B+' or decay_mode == 'EC':
                beta_plus_files += 1
            elif decay_mode == 'A':
                alpha_files += 1
            elif '-' in decay_mode and any(p in decay_mode for p in ['n', 'p', 'a', '2n', '2p']):
                delayed_files += 1
            
            # Check for betasTable
            betas_table = data.get('betasTable', {}).get('betas', [])
            
            if decay_mode in ['B-', 'B+']:
                if betas_table:
                    files_with_betas += 1
                else:
                    files_without_betas += 1
                    empty_betas_table.append((filename, decay_mode, parent_a, parent_z, parent_n))
            
            # Check for alphasTable
            alphas_table = data.get('alphasTable', {}).get('alphas', [])
            
            if decay_mode == 'A':
                if alphas_table:
                    files_with_alphas += 1
                else:
                    files_without_alphas += 1
                    empty_alphas_table.append((filename, decay_mode, parent_a, parent_z, parent_n))
            
            # Classify by N/Z ratio
            if parent_n < parent_z:
                proton_rich.append((parent_n, parent_z, decay_mode, filename))
            elif parent_n > parent_z:
                neutron_rich.append((parent_n, parent_z, decay_mode, filename))
            else:
                n_equals_z.append((parent_n, parent_z, decay_mode, filename))
                
        except Exception as e:
            print(f"Error processing {filename}: {e}")
            continue
    
    # Print results
    print(f"\nTOTAL FILES: {total_files}")
    print("\nDECAY MODE DISTRIBUTION:")
    print(f"  B- (beta-minus):     {beta_minus_files:4d} files")
    print(f"  B+/EC (beta-plus):   {beta_plus_files:4d} files")
    print(f"  Alpha:               {alpha_files:4d} files")
    print(f"  Delayed particles:   {delayed_files:4d} files")
    
    print("\nBETAS TABLE ANALYSIS (B-/B+ decays only):")
    print(f"  Files WITH betasTable:    {files_with_betas:4d}")
    print(f"  Files WITHOUT betasTable: {files_without_betas:4d}")
    
    print("\nALPHAS TABLE ANALYSIS (Alpha decays only):")
    print(f"  Files WITH alphasTable:    {files_with_alphas:4d}")
    print(f"  Files WITHOUT alphasTable: {files_without_alphas:4d}")
    
    print("\nN/Z DISTRIBUTION:")
    print(f"  Proton-rich (N<Z):   {len(proton_rich):4d} files")
    print(f"  N=Z line:            {len(n_equals_z):4d} files")
    print(f"  Neutron-rich (N>Z):  {len(neutron_rich):4d} files")
    
    print("\n" + "=" * 80)
    print("PROBLEM FILES - BETA DECAYS WITH EMPTY betasTable")
    print("=" * 80)
    print(f"Total: {len(empty_betas_table)} files\n")
    if empty_betas_table:
        # Sort by N/Z ratio (descending) to show most neutron-rich first
        empty_betas_sorted = sorted(empty_betas_table, key=lambda x: x[4]/x[3] if x[3] > 0 else 0, reverse=True)
        for filename, mode, A, Z, N in empty_betas_sorted:
            ratio = N/Z if Z > 0 else 0
            print(f"  {filename[:60]:60s} | {mode:4s} | A={A:3d} Z={Z:3d} N={N:3d} | N/Z={ratio:.3f}")
    
    print("\n" + "=" * 80)
    print("PROBLEM FILES - ALPHA DECAYS WITH EMPTY alphasTable")
    print("=" * 80)
    print(f"Total: {len(empty_alphas_table)} files\n")
    if empty_alphas_table:
        # Sort by N/Z ratio (ascending) to show most proton-rich first
        empty_alphas_sorted = sorted(empty_alphas_table, key=lambda x: x[4]/x[3] if x[3] > 0 else 0)
        for filename, mode, A, Z, N in empty_alphas_sorted:
            ratio = N/Z if Z > 0 else 0
            print(f"  {filename[:60]:60s} | {mode:4s} | A={A:3d} Z={Z:3d} N={N:3d} | N/Z={ratio:.3f}")
    
    print(f"\n  Missing decay mode: {len(missing_decay_mode)}")
    
    # Analyze neutron-rich B- decays specifically
    neutron_rich_bminus = [item for item in neutron_rich if item[2] == 'B-']
    neutron_rich_empty = [item for item in empty_betas_table if item[4] > item[3] and item[1] == 'B-']
    
    # Analyze proton-rich alpha decays specifically
    proton_rich_alpha = [item for item in proton_rich if item[2] == 'A']
    proton_rich_alpha_empty = [item for item in empty_alphas_table if item[4] < item[3]]
    
    print("\n" + "=" * 80)
    print("DIAGNOSIS SUMMARY:")
    print("=" * 80)
    
    print(f"\nNeutron-rich B- decays:      {len(neutron_rich_bminus):4d} total files")
    print(f"  With EMPTY betasTable:     {len(neutron_rich_empty):4d} files ({100*len(neutron_rich_empty)/len(neutron_rich_bminus):.1f}%)")
    
    print(f"\nProton-rich alpha decays:    {len(proton_rich_alpha):4d} total files")
    print(f"  With EMPTY alphasTable:    {len(proton_rich_alpha_empty):4d} files ({100*len(proton_rich_alpha_empty)/len(proton_rich_alpha):.1f}%)" if proton_rich_alpha else "  (No proton-rich alpha files found)")
    
    print("\n" + "-" * 80)
    
    if len(neutron_rich_empty) > 50:
        print("⚠️  BETA DECAY ISSUE FOUND:")
        print(f"    {len(neutron_rich_empty)} neutron-rich B- decay files have empty betasTable!")
        print("    These nuclides are missing from your ENSDF decay dataset.")
        print("    The JSON files exist, but contain no detailed transition data.")
        print("\n    SOLUTION: Parser should create at least ONE entry per decay file,")
        print("              even if betasTable is empty (use ground-state to ground-state).")
    else:
        print("✓ No major issues with beta decay coverage.")
    
    if len(empty_alphas_table) > 50:
        print("\n⚠️  ALPHA DECAY ISSUE FOUND:")
        print(f"    {len(empty_alphas_table)} alpha decay files have empty alphasTable!")
        print("    These nuclides are missing from your ENSDF decay dataset.")
        print("\n    SOLUTION: Parser should create at least ONE entry per decay file,")
        print("              even if alphasTable is empty (use ground-state to ground-state).")
    else:
        print("\n✓ No major issues with alpha decay coverage.")
    
    return {
        'total': total_files,
        'empty_betas': len(empty_betas_table),
        'empty_alphas': len(empty_alphas_table),
        'neutron_rich': len(neutron_rich),
        'neutron_rich_bminus': len(neutron_rich_bminus),
        'neutron_rich_empty': len(neutron_rich_empty),
        'proton_rich_alpha': len(proton_rich_alpha),
        'proton_rich_alpha_empty': len(proton_rich_alpha_empty) if proton_rich_alpha else 0
    }


if __name__ == "__main__":
    if len(sys.argv) > 1:
        json_dir = sys.argv[1]
    else:
        # Default path (user should modify)
        json_dir = "/Users/audreywarn/fluka-db-audrey/data_input/ensdf/json_070125/beta-decay/"
    
    if not os.path.exists(json_dir):
        print(f"Error: Directory not found: {json_dir}")
        print(f"\nUsage: python3 {sys.argv[0]} <path-to-json-directory>")
        sys.exit(1)
    
    analyze_json_files(json_dir)
