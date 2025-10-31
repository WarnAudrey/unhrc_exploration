#!/usr/bin/env python3
"""
Test script to diagnose a specific JSON file parsing issue.
"""

import json
import sys

def diagnose_json_file(filepath):
    """Diagnose why a specific JSON file isn't being parsed."""
    
    print("=" * 80)
    print(f"DIAGNOSING: {filepath}")
    print("=" * 80)
    
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
    except Exception as e:
        print(f"❌ ERROR: Could not load JSON file: {e}")
        return
    
    # Extract key information
    decay_mode = data.get('decayMode', '')
    parents = data.get('parents', [])
    
    print(f"\nDecay Mode: {decay_mode}")
    
    if parents:
        parent = parents[0]
        parent_a = parent.get('a')
        parent_z = parent.get('z')
        parent_symbol = parent.get('elementSymbol', '')
        print(f"Parent: {parent_symbol}-{parent_a} (A={parent_a}, Z={parent_z})")
    else:
        print("⚠️  No parent information found!")
    
    # Check for various tables
    print("\n" + "-" * 80)
    print("TABLE CONTENTS:")
    print("-" * 80)
    
    # Check betasTable
    betas_table = data.get('betasTable', {}).get('betas', [])
    print(f"\nbetasTable: {len(betas_table)} entries")
    if betas_table:
        print("  ✅ betasTable exists with data")
        print(f"  First entry fields: {list(betas_table[0].keys())}")
        
        # For EC, check for electronCaptureIntensity
        first_beta = betas_table[0]
        if 'electronCaptureIntensity' in first_beta:
            ec_intensity = first_beta.get('electronCaptureIntensity', {})
            print(f"  ✅ electronCaptureIntensity found: {ec_intensity.get('value')}")
        else:
            print("  ⚠️  No electronCaptureIntensity field")
        
        if 'betaIntensity' in first_beta:
            beta_intensity = first_beta.get('betaIntensity', {})
            print(f"  ℹ️  betaIntensity found: {beta_intensity.get('value')}")
        
        # Show first few entries
        print(f"\n  Sample entries (first {min(3, len(betas_table))}):")
        for i, beta in enumerate(betas_table[:3]):
            final_level = beta.get('finalLevel')
            ec_int = beta.get('electronCaptureIntensity', {}).get('value', 'N/A')
            endpoint = beta.get('endpointEnergy', {}).get('value', 'N/A')
            print(f"    [{i}] finalLevel={final_level}, EC_intensity={ec_int}, endpoint={endpoint} keV")
    else:
        print("  ❌ betasTable is EMPTY or missing!")
    
    # Check electronCaptureTable
    ec_table = data.get('electronCaptureTable', {}).get('electronCaptures', [])
    print(f"\nelectronCaptureTable: {len(ec_table)} entries")
    if ec_table:
        print("  ℹ️  electronCaptureTable exists (old format)")
    
    # Check alphasTable
    alphas_table = data.get('alphasTable', {}).get('alphas', [])
    print(f"\nalphasTable: {len(alphas_table)} entries")
    
    # Check delayedParticlesTable
    delayed_table = data.get('delayedParticlesTable', {}).get('delayedParticles', [])
    print(f"\ndelayedParticlesTable: {len(delayed_table)} entries")
    
    # Check levelsTable
    levels_table = data.get('levelsTable', {}).get('levels', [])
    print(f"\nlevelsTable: {len(levels_table)} entries")
    
    print("\n" + "=" * 80)
    print("DIAGNOSIS:")
    print("=" * 80)
    
    # Determine what should happen
    if decay_mode == 'EC':
        print(f"✅ Decay mode is 'EC' - should be parsed as electron capture")
        
        if not betas_table:
            print(f"❌ ISSUE FOUND: betasTable is empty!")
            print(f"   The parser expects EC decays to have entries in betasTable")
            print(f"   with electronCaptureIntensity field.")
            print(f"\n   SOLUTION: Parser should create at least one ground-state")
            print(f"   entry even when betasTable is empty, using parent info.")
        else:
            print(f"✅ betasTable has {len(betas_table)} entries - should parse OK")
            
            # Check if electronCaptureIntensity exists
            has_ec_intensity = any('electronCaptureIntensity' in beta for beta in betas_table)
            if has_ec_intensity:
                print(f"✅ electronCaptureIntensity field found - parser should work")
            else:
                print(f"⚠️  WARNING: No electronCaptureIntensity field found")
                print(f"   Parser may not extract intensity correctly")
    else:
        print(f"ℹ️  Decay mode is '{decay_mode}' (not pure EC)")
        if 'EC' in decay_mode:
            print(f"   This is an EC-related mode (delayed particle?)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 test_single_file.py <path-to-json-file>")
        print("\nExample:")
        print("  python3 test_single_file.py /path/to/141PR_141ND-EC-DECAY-2.49-H-.json")
        sys.exit(1)
    
    filepath = sys.argv[1]
    
    import os
    if not os.path.exists(filepath):
        print(f"Error: File not found: {filepath}")
        sys.exit(1)
    
    diagnose_json_file(filepath)
