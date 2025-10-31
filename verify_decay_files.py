#!/usr/bin/env python3
"""
Verification script to check what's actually in your DECAY.ascii files.
This will tell us exactly why nuclides are missing.
"""

import sys

def count_unique_nuclides(filepath):
    """Count unique (A, Z) pairs in a DECAY.ascii file."""
    
    print("=" * 80)
    print(f"ANALYZING: {filepath}")
    print("=" * 80)
    
    try:
        with open(filepath, 'r') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"❌ ERROR: File not found!")
        return
    
    print(f"\nTotal lines in file: {len(lines)}")
    
    # Skip headers
    data_lines = lines[2:]
    print(f"Data lines (after 2 headers): {len(data_lines)}")
    
    # Track unique (A, Z) pairs
    nuclides = set()
    
    # Track last A, Z for multi-index parsing
    last_A = None
    last_Z = None
    
    # Statistics
    lines_parsed = 0
    lines_skipped = 0
    
    for line_num, line in enumerate(data_lines, start=3):
        if not line.strip():
            continue
        
        parts = line.split()
        if len(parts) < 2:
            lines_skipped += 1
            continue
        
        try:
            # Try to parse A and Z from first two columns
            try:
                A = int(parts[0])
                Z = int(parts[1])
                last_A = A
                last_Z = Z
                nuclides.add((A, Z))
                lines_parsed += 1
            except ValueError:
                # First column is not an integer - might be multi-index continuation
                # Use last known A, Z
                if last_A is not None and last_Z is not None:
                    nuclides.add((last_A, last_Z))
                    lines_parsed += 1
                else:
                    lines_skipped += 1
                    
        except Exception as e:
            lines_skipped += 1
            continue
    
    print(f"\nParsing results:")
    print(f"  Lines successfully parsed: {lines_parsed}")
    print(f"  Lines skipped: {lines_skipped}")
    print(f"  Unique (A, Z) pairs found: {len(nuclides)}")
    
    # Convert to (N, Z) and analyze
    nz_pairs = {(A - Z, Z) for A, Z in nuclides}
    
    print(f"  Unique (N, Z) pairs: {len(nz_pairs)}")
    
    # N/Z distribution
    proton_rich = {(N, Z) for N, Z in nz_pairs if N < Z}
    neutron_rich = {(N, Z) for N, Z in nz_pairs if N > Z}
    n_equals_z = {(N, Z) for N, Z in nz_pairs if N == Z}
    
    print(f"\nN/Z Distribution:")
    print(f"  Proton-rich (N<Z):   {len(proton_rich):4d} ({100*len(proton_rich)/len(nz_pairs):.1f}%)")
    print(f"  N=Z line:            {len(n_equals_z):4d} ({100*len(n_equals_z)/len(nz_pairs):.1f}%)")
    print(f"  Neutron-rich (N>Z):  {len(neutron_rich):4d} ({100*len(neutron_rich)/len(nz_pairs):.1f}%)")
    
    # Show sample nuclides
    print(f"\nSample nuclides (first 10):")
    for A, Z in sorted(nuclides)[:10]:
        N = A - Z
        ratio = N/Z if Z > 0 else 0
        print(f"  A={A:3d} Z={Z:3d} N={N:3d} | N/Z={ratio:.3f}")
    
    # Show first 10 lines of actual data
    print(f"\nFirst 10 data lines from file:")
    for i, line in enumerate(data_lines[:10]):
        print(f"  {i+3:3d}: {line.rstrip()[:100]}")
    
    return len(nz_pairs)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Verify DECAY.ascii file contents")
    parser.add_argument(
        '--endf',
        type=str,
        default="/Users/audreywarn/fluka-db-audrey/outputs/endf/endf_data_modules/ascii/DECAY.ascii",
        help="Path to ENDF DECAY.ascii file"
    )
    parser.add_argument(
        '--ensdf',
        type=str,
        default="/Users/audreywarn/fluka-db-audrey/src/nuclear_data_output/json_data_modules/ascii/DECAY.ascii",
        help="Path to ENSDF decay data file"
    )
    
    args = parser.parse_args()
    
    print("\n" + "=" * 80)
    print("VERIFYING DECAY.ASCII FILES")
    print("=" * 80)
    
    print("\n\n" + "=" * 80)
    print("ENDF FILE")
    print("=" * 80)
    endf_count = count_unique_nuclides(args.endf)
    
    print("\n\n" + "=" * 80)
    print("ENSDF FILE")
    print("=" * 80)
    ensdf_count = count_unique_nuclides(args.ensdf)
    
    print("\n\n" + "=" * 80)
    print("COMPARISON")
    print("=" * 80)
    if endf_count and ensdf_count:
        print(f"ENDF unique nuclides:  {endf_count}")
        print(f"ENSDF unique nuclides: {ensdf_count}")
        print(f"Difference: {abs(endf_count - ensdf_count)}")
        
        if ensdf_count < endf_count * 0.5:
            print(f"\n⚠️  WARNING: ENSDF has less than 50% of ENDF nuclides!")
            print(f"   This suggests ENSDF data is incomplete.")
            print(f"\n   ACTIONS:")
            print(f"   1. Verify you regenerated ENSDF with updated JSON parser")
            print(f"   2. Check that EC decays are being parsed")
            print(f"   3. Run: python3 diagnose_ensdf_coverage.py --type both")
