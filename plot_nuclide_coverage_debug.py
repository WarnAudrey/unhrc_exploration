#!/usr/bin/env python3
"""
Nuclide Coverage Comparison Plot (with Debug Mode)

This script creates a scatter plot comparing which nuclides (N, Z pairs) are present
in ENDF vs ENSDF DECAY data files.

Includes robust parsing and debug mode to diagnose data format issues.
"""

import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend for headless environments
import matplotlib.pyplot as plt
from pathlib import Path
import argparse


def read_nuclides_from_decay_ascii(filepath, debug=False):
    """
    Read unique (N, Z) pairs from a DECAY.ascii file with robust parsing.
    
    Args:
        filepath: Path to DECAY.ascii file
        debug: If True, print diagnostic information
        
    Returns:
        set: Set of (N, Z) tuples representing unique nuclides
    """
    nuclides = set()
    skipped_lines = []
    
    try:
        with open(filepath, 'r') as f:
            lines = f.readlines()
        
        print(f"\nFile: {filepath}")
        print(f"Total lines in file: {len(lines)}")
        
        # Skip first two header lines
        data_lines = lines[2:]
        print(f"Data lines (after skipping 2 header lines): {len(data_lines)}")
        
        for line_num, line in enumerate(data_lines, start=3):
            line = line.strip()
            
            # Skip empty lines
            if not line:
                continue
            
            try:
                # Split by whitespace
                parts = line.split()
                
                if len(parts) < 2:
                    if debug:
                        print(f"Line {line_num}: Too few columns ({len(parts)})")
                    skipped_lines.append((line_num, "too few columns", line[:80]))
                    continue
                
                # Try to parse A and Z from first two columns
                try:
                    A = int(parts[0])  # Mass number
                    Z = int(parts[1])  # Atomic number
                except ValueError:
                    # First column might be empty due to multi-index formatting
                    # Try to find the first two integer values
                    integers = []
                    for i, part in enumerate(parts):
                        try:
                            integers.append((i, int(part)))
                            if len(integers) == 2:
                                break
                        except ValueError:
                            continue
                    
                    if len(integers) >= 2:
                        A = integers[0][1]
                        Z = integers[1][1]
                    else:
                        if debug:
                            print(f"Line {line_num}: Cannot parse A and Z: {parts[:5]}")
                        skipped_lines.append((line_num, "cannot parse A,Z", line[:80]))
                        continue
                
                # Sanity checks
                if A < 0 or A > 300:
                    if debug:
                        print(f"Line {line_num}: Invalid A={A}")
                    skipped_lines.append((line_num, f"invalid A={A}", line[:80]))
                    continue
                    
                if Z < 0 or Z > 120:
                    if debug:
                        print(f"Line {line_num}: Invalid Z={Z}")
                    skipped_lines.append((line_num, f"invalid Z={Z}", line[:80]))
                    continue
                
                N = A - Z  # Neutron number
                
                if N < 0 or N > 200:
                    if debug:
                        print(f"Line {line_num}: Invalid N={N} (A={A}, Z={Z})")
                    skipped_lines.append((line_num, f"invalid N={N}", line[:80]))
                    continue
                
                # Add (N, Z) tuple to set
                nuclides.add((N, Z))
                
                if debug and line_num < 10:
                    print(f"Line {line_num}: A={A}, Z={Z}, N={N} ✓")
                    
            except Exception as e:
                if debug:
                    print(f"Line {line_num}: Unexpected error: {e}")
                skipped_lines.append((line_num, str(e), line[:80]))
                continue
        
        print(f"Successfully parsed {len(nuclides)} unique (N, Z) pairs")
        
        if skipped_lines:
            print(f"Skipped {len(skipped_lines)} lines due to parsing issues")
            if debug or len(skipped_lines) > 100:
                print("\nFirst 10 skipped lines:")
                for line_num, reason, content in skipped_lines[:10]:
                    print(f"  Line {line_num} ({reason}): {content}")
        
        return nuclides
        
    except FileNotFoundError:
        print(f"Error: File not found: {filepath}")
        return set()
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return set()


def filter_by_z_cutoff(nuclides, z_max=100):
    """Filter nuclides to only include Z <= z_max."""
    filtered = {(N, Z) for N, Z in nuclides if Z <= z_max}
    removed = len(nuclides) - len(filtered)
    
    if removed > 0:
        print(f"Filtered out {removed} nuclides with Z > {z_max}")
    
    return filtered


def plot_nuclide_comparison(endf_nuclides, ensdf_nuclides, output_file="nuclide_coverage.png"):
    """Create a scatter plot comparing ENDF and ENSDF nuclide coverage."""
    
    # Categorize nuclides
    common = endf_nuclides & ensdf_nuclides
    endf_only = endf_nuclides - ensdf_nuclides
    ensdf_only = ensdf_nuclides - endf_nuclides
    
    print("\n" + "=" * 60)
    print("NUCLIDE COVERAGE COMPARISON (by N and Z)")
    print("=" * 60)
    print(f"Common to both:     {len(common):4d} nuclides")
    print(f"ENDF only:          {len(endf_only):4d} nuclides")
    print(f"ENSDF only:         {len(ensdf_only):4d} nuclides")
    print(f"Total ENDF:         {len(endf_nuclides):4d} nuclides")
    print(f"Total ENSDF:        {len(ensdf_nuclides):4d} nuclides")
    print("=" * 60)
    
    # Check stable region
    stable_region = {(N, Z) for N, Z in common if Z <= 20 and abs(N - Z) <= 10}
    print(f"\nStable region (Z≤20, |N-Z|≤10): {len(stable_region)} common nuclides")
    
    # Check known stable nuclides
    known_stable = {
        (6, 6),   # C-12
        (7, 6),   # C-13
        (7, 7),   # N-14
        (8, 8),   # O-16
        (10, 8),  # O-18
        (20, 20), # Ca-40
        (26, 26), # Fe-52
    }
    
    stable_in_both = known_stable & common
    stable_in_endf_only = known_stable & endf_only
    stable_in_ensdf_only = known_stable & ensdf_only
    
    print(f"\nKnown stable nuclides:")
    print(f"  In both datasets: {len(stable_in_both)}/{len(known_stable)}")
    if stable_in_endf_only:
        print(f"  In ENDF only: {stable_in_endf_only}")
    if stable_in_ensdf_only:
        print(f"  In ENSDF only: {stable_in_ensdf_only}")
    
    # Prepare data for plotting
    common_N = [N for N, Z in common]
    common_Z = [Z for N, Z in common]
    
    endf_N = [N for N, Z in endf_only]
    endf_Z = [Z for N, Z in endf_only]
    
    ensdf_N = [N for N, Z in ensdf_only]
    ensdf_Z = [Z for N, Z in ensdf_only]
    
    # Create plot
    plt.figure(figsize=(14, 10))
    
    if common:
        plt.scatter(common_N, common_Z, 
                   c='blue', marker='o', s=20, alpha=0.4, 
                   label=f'Both ENDF & ENSDF ({len(common)})')
    
    if ensdf_only:
        plt.scatter(ensdf_N, ensdf_Z, 
                   c='green', marker='s', s=30, alpha=0.7, 
                   label=f'ENSDF only ({len(ensdf_only)})')
    
    if endf_only:
        plt.scatter(endf_N, endf_Z, 
                   c='red', marker='^', s=30, alpha=0.7, 
                   label=f'ENDF only ({len(endf_only)})')
    
    plt.xlabel('Neutron Number (N)', fontsize=12, fontweight='bold')
    plt.ylabel('Atomic Number (Z)', fontsize=12, fontweight='bold')
    plt.title('Nuclide Coverage Comparison: ENDF vs ENSDF Decay Data', 
              fontsize=14, fontweight='bold', pad=20)
    
    plt.grid(True, alpha=0.3, linestyle='--')
    plt.legend(loc='upper left', fontsize=10, framealpha=0.9)
    
    if endf_nuclides or ensdf_nuclides:
        all_N = [N for N, Z in (endf_nuclides | ensdf_nuclides)]
        all_Z = [Z for N, Z in (endf_nuclides | ensdf_nuclides)]
        
        plt.xlim(min(all_N) - 5, max(all_N) + 5)
        plt.ylim(min(all_Z) - 2, max(all_Z) + 2)
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"\nPlot saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Compare nuclide coverage between ENDF and ENSDF DECAY data (with debug mode)"
    )
    parser.add_argument(
        '--endf',
        type=str,
        default="/Users/audreywarn/fluka-db-audrey/outputs/endf/endf_data_modules/ascii/DECAY.ascii",
        help="Path to ENDF DECAY.ascii file"
    )
    parser.add_argument(
        '--ensdf',
        type=str,
        default="/Users/audreywarn/fluka-db-audrey/src/nuclear_data_ascii/decay_transitions.txt",
        help="Path to ENSDF decay data file"
    )
    parser.add_argument(
        '--output',
        type=str,
        default="nuclide_coverage_comparison.png",
        help="Output plot filename"
    )
    parser.add_argument(
        '--zmax',
        type=int,
        default=100,
        help="Maximum Z value to plot (default: 100)"
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help="Enable debug mode with verbose output"
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("NUCLIDE COVERAGE COMPARISON (DEBUG MODE)")
    print("=" * 60)
    print(f"ENDF file:  {args.endf}")
    print(f"ENSDF file: {args.ensdf}")
    print(f"Output:     {args.output}")
    print(f"Z cutoff:   {args.zmax}")
    print(f"Debug mode: {args.debug}")
    print("=" * 60)
    
    # Read data with debug info
    print("\n" + "=" * 60)
    print("READING ENDF DATA")
    print("=" * 60)
    endf_nuclides = read_nuclides_from_decay_ascii(args.endf, debug=args.debug)
    
    print("\n" + "=" * 60)
    print("READING ENSDF DATA")
    print("=" * 60)
    ensdf_nuclides = read_nuclides_from_decay_ascii(args.ensdf, debug=args.debug)
    
    if not endf_nuclides and not ensdf_nuclides:
        print("\nError: No data loaded from either file. Exiting.")
        return
    
    # Apply Z cutoff
    print(f"\nApplying Z <= {args.zmax} filter...")
    endf_nuclides = filter_by_z_cutoff(endf_nuclides, z_max=args.zmax)
    ensdf_nuclides = filter_by_z_cutoff(ensdf_nuclides, z_max=args.zmax)
    
    # Create plot
    print("\nGenerating plot...")
    plot_nuclide_comparison(endf_nuclides, ensdf_nuclides, 
                           output_file=args.output)
    
    print("\nDone!")


if __name__ == "__main__":
    main()
