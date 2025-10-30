#!/usr/bin/env python3
"""
Nuclide Coverage Comparison Plot

This script creates a scatter plot comparing which nuclides (N, Z pairs) are present
in ENDF vs ENSDF DECAY data files.

Comparison is done by matching both N (neutron number) and Z (atomic number).
Nuclides near the valley of stability should appear in both datasets.

Plot shows:
- Blue circles: Nuclides in both ENDF and ENSDF
- Red triangles: Nuclides only in ENDF
- Green squares: Nuclides only in ENSDF

Only nuclides with Z <= 100 are shown (higher Z values are physically unrealistic
for most decay applications).

NOTE: EC (Electron Capture) decays are NOT included in the final datasets.
Both ENDF and ENSDF parsers exclude EC after using it for β+/EC splitting calculations.
Datasets include: α, β-, β+, and delayed particle decays (B-n, B+p, B-a, etc.).
"""

import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend for headless environments
import matplotlib.pyplot as plt
from pathlib import Path
import argparse


def read_nuclides_from_decay_ascii(filepath):
    """
    Read unique (N, Z) pairs from a DECAY.ascii file.
    
    The DECAY.ascii format has:
    - Line 1: Column headers (multi-level)
    - Line 2: Sub-headers
    - Line 3+: Data rows with format: A Z parentLevel decay_mode final_level ...
    
    We convert A, Z to N, Z for comparison where N = A - Z (neutron number).
    
    Args:
        filepath: Path to DECAY.ascii file
        
    Returns:
        set: Set of (N, Z) tuples representing unique nuclides
    """
    nuclides = set()
    
    try:
        with open(filepath, 'r') as f:
            lines = f.readlines()
        
        # Skip first two header lines
        for line_num, line in enumerate(lines[2:], start=3):
            line = line.strip()
            
            # Skip empty lines
            if not line:
                continue
            
            try:
                # Split by whitespace
                parts = line.split()
                
                # Extract A and Z (first two columns)
                if len(parts) >= 2:
                    A = int(parts[0])  # Mass number
                    Z = int(parts[1])  # Atomic number
                    N = A - Z           # Neutron number
                    
                    # Add (N, Z) tuple to set (automatically handles duplicates)
                    nuclides.add((N, Z))
                    
            except (ValueError, IndexError) as e:
                # Skip malformed lines
                print(f"Warning: Skipping malformed line {line_num}: {str(e)}")
                continue
        
        print(f"Read {len(nuclides)} unique (N, Z) pairs from {filepath}")
        return nuclides
        
    except FileNotFoundError:
        print(f"Error: File not found: {filepath}")
        return set()
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return set()


def filter_by_z_cutoff(nuclides, z_max=100):
    """
    Filter nuclides to only include Z <= z_max.
    
    Args:
        nuclides: Set of (N, Z) tuples
        z_max: Maximum Z value to include (default: 100)
        
    Returns:
        set: Filtered set of (N, Z) tuples
    """
    filtered = {(N, Z) for N, Z in nuclides if Z <= z_max}
    removed = len(nuclides) - len(filtered)
    
    if removed > 0:
        print(f"Filtered out {removed} nuclides with Z > {z_max}")
    
    return filtered


def plot_nuclide_comparison(endf_nuclides, ensdf_nuclides, output_file="nuclide_coverage.png"):
    """
    Create a scatter plot comparing ENDF and ENSDF nuclide coverage.
    
    Compares nuclides based on both N (neutron number) and Z (atomic number).
    
    Args:
        endf_nuclides: Set of (N, Z) tuples from ENDF data
        ensdf_nuclides: Set of (N, Z) tuples from ENSDF data
        output_file: Path to save the plot image
    """
    # ========================================================================
    # CATEGORIZE NUCLIDES (comparing both N and Z)
    # ========================================================================
    # Use set operations to find differences and intersections
    # Two nuclides are the same if they have identical (N, Z) pairs
    common = endf_nuclides & ensdf_nuclides      # In both datasets
    endf_only = endf_nuclides - ensdf_nuclides   # Only in ENDF
    ensdf_only = ensdf_nuclides - endf_nuclides  # Only in ENSDF
    
    print("\n" + "=" * 60)
    print("NUCLIDE COVERAGE COMPARISON (by N and Z)")
    print("=" * 60)
    print(f"Common to both:     {len(common):4d} nuclides")
    print(f"ENDF only:          {len(endf_only):4d} nuclides")
    print(f"ENSDF only:         {len(ensdf_only):4d} nuclides")
    print(f"Total ENDF:         {len(endf_nuclides):4d} nuclides")
    print(f"Total ENSDF:        {len(ensdf_nuclides):4d} nuclides")
    print("=" * 60)
    
    # ========================================================================
    # DIAGNOSE STABLE NUCLIDES (near valley of stability)
    # ========================================================================
    # Check for common stable nuclides (Z <= 20, |N-Z| <= 10)
    # These should ideally be in both datasets
    stable_region = {(N, Z) for N, Z in common 
                     if Z <= 20 and abs(N - Z) <= 10}
    
    print(f"\nStable region check (Z≤20, |N-Z|≤10):")
    print(f"  Found {len(stable_region)} common nuclides near stability")
    
    # Show some examples
    if stable_region:
        examples = sorted(stable_region)[:10]  # First 10
        print(f"  Examples (N, Z): {examples[:5]}")
    
    # Check if any stable nuclides are missing from either dataset
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
    
    print(f"\nKnown stable nuclides check:")
    print(f"  In both datasets: {len(stable_in_both)}/{len(known_stable)}")
    if stable_in_endf_only:
        print(f"  In ENDF only: {stable_in_endf_only}")
    if stable_in_ensdf_only:
        print(f"  In ENSDF only: {stable_in_ensdf_only}")
    
    # ========================================================================
    # PREPARE DATA FOR PLOTTING
    # ========================================================================
    # Data is already in (N, Z) format
    
    # Common nuclides (blue)
    common_N = [N for N, Z in common]
    common_Z = [Z for N, Z in common]
    
    # ENDF-only nuclides (red)
    endf_N = [N for N, Z in endf_only]
    endf_Z = [Z for N, Z in endf_only]
    
    # ENSDF-only nuclides (green)
    ensdf_N = [N for N, Z in ensdf_only]
    ensdf_Z = [Z for N, Z in ensdf_only]
    
    # ========================================================================
    # CREATE PLOT
    # ========================================================================
    plt.figure(figsize=(14, 10))
    
    # Plot each category with different colors and markers
    # Plot in reverse order so most interesting data (differences) is on top
    
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
    
    # ========================================================================
    # FORMAT PLOT
    # ========================================================================
    plt.xlabel('Neutron Number (N)', fontsize=12, fontweight='bold')
    plt.ylabel('Atomic Number (Z)', fontsize=12, fontweight='bold')
    plt.title('Nuclide Coverage Comparison: ENDF vs ENSDF Decay Data', 
              fontsize=14, fontweight='bold', pad=20)
    
    # Add grid for easier reading
    plt.grid(True, alpha=0.3, linestyle='--')
    
    # Add legend
    plt.legend(loc='upper left', fontsize=10, framealpha=0.9)
    
    # Set axis limits with some padding
    if endf_nuclides or ensdf_nuclides:
        all_N = [N for N, Z in (endf_nuclides | ensdf_nuclides)]
        all_Z = [Z for N, Z in (endf_nuclides | ensdf_nuclides)]
        
        plt.xlim(min(all_N) - 5, max(all_N) + 5)
        plt.ylim(min(all_Z) - 2, max(all_Z) + 2)
    
    # Tight layout to prevent label cutoff
    plt.tight_layout()
    
    # ========================================================================
    # SAVE PLOT
    # ========================================================================
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"\nPlot saved to: {output_file}")
    
    # Show plot (disabled for headless/batch mode)
    # plt.show()


def main():
    """
    Main function to orchestrate the nuclide coverage comparison.
    """
    # ========================================================================
    # PARSE COMMAND-LINE ARGUMENTS
    # ========================================================================
    parser = argparse.ArgumentParser(
        description="Compare nuclide coverage between ENDF and ENSDF DECAY data"
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
        help="Output plot filename (default: nuclide_coverage_comparison.png)"
    )
    parser.add_argument(
        '--zmax',
        type=int,
        default=100,
        help="Maximum Z value to plot (default: 100)"
    )
    
    args = parser.parse_args()
    
    # ========================================================================
    # FILE PATHS
    # ========================================================================
    endf_file = args.endf
    ensdf_file = args.ensdf
    output_file = args.output
    z_max = args.zmax
    
    print("=" * 60)
    print("NUCLIDE COVERAGE COMPARISON")
    print("=" * 60)
    print(f"ENDF file:  {endf_file}")
    print(f"ENSDF file: {ensdf_file}")
    print(f"Output:     {output_file}")
    print(f"Z cutoff:   {z_max}")
    print("=" * 60)
    
    # ========================================================================
    # READ DATA
    # ========================================================================
    print("\nReading ENDF decay data...")
    endf_nuclides = read_nuclides_from_decay_ascii(endf_file)
    
    print("\nReading ENSDF decay data...")
    ensdf_nuclides = read_nuclides_from_decay_ascii(ensdf_file)
    
    # Check if data was loaded
    if not endf_nuclides and not ensdf_nuclides:
        print("\nError: No data loaded from either file. Exiting.")
        return
    
    # ========================================================================
    # APPLY Z CUTOFF
    # ========================================================================
    print(f"\nApplying Z <= {z_max} filter...")
    endf_nuclides = filter_by_z_cutoff(endf_nuclides, z_max=z_max)
    ensdf_nuclides = filter_by_z_cutoff(ensdf_nuclides, z_max=z_max)
    
    # ========================================================================
    # CREATE PLOT
    # ========================================================================
    print("\nGenerating plot...")
    plot_nuclide_comparison(endf_nuclides, ensdf_nuclides, 
                           output_file=output_file)
    
    print("\nDone!")


if __name__ == "__main__":
    main()
