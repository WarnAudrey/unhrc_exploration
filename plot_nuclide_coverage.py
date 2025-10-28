#!/usr/bin/env python3
"""
Nuclide Coverage Comparison Plot

This script creates a scatter plot comparing which nuclides (A, Z pairs) are present
in ENDF vs ENSDF DECAY data files.

Plot shows:
- Blue: Nuclides in both ENDF and ENSDF
- Red: Nuclides only in ENDF
- Green: Nuclides only in ENSDF

Only nuclides with Z <= 100 are shown (higher Z values are physically unrealistic
for most decay applications).
"""

import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend for headless environments
import matplotlib.pyplot as plt
from pathlib import Path
import argparse


def read_nuclides_from_decay_ascii(filepath):
    """
    Read unique (A, Z) pairs from a DECAY.ascii file.
    
    The DECAY.ascii format has:
    - Line 1: Column headers (multi-level)
    - Line 2: Sub-headers
    - Line 3+: Data rows with format: A Z parentLevel decay_mode final_level ...
    
    Args:
        filepath: Path to DECAY.ascii file
        
    Returns:
        set: Set of (A, Z) tuples representing unique nuclides
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
                    
                    # Add to set (automatically handles duplicates)
                    nuclides.add((A, Z))
                    
            except (ValueError, IndexError) as e:
                # Skip malformed lines
                print(f"Warning: Skipping malformed line {line_num}: {str(e)}")
                continue
        
        print(f"Read {len(nuclides)} unique nuclides from {filepath}")
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
        nuclides: Set of (A, Z) tuples
        z_max: Maximum Z value to include (default: 100)
        
    Returns:
        set: Filtered set of (A, Z) tuples
    """
    filtered = {(A, Z) for A, Z in nuclides if Z <= z_max}
    removed = len(nuclides) - len(filtered)
    
    if removed > 0:
        print(f"Filtered out {removed} nuclides with Z > {z_max}")
    
    return filtered


def plot_nuclide_comparison(endf_nuclides, ensdf_nuclides, output_file="nuclide_coverage.png"):
    """
    Create a scatter plot comparing ENDF and ENSDF nuclide coverage.
    
    Args:
        endf_nuclides: Set of (A, Z) tuples from ENDF data
        ensdf_nuclides: Set of (A, Z) tuples from ENSDF data
        output_file: Path to save the plot image
    """
    # ========================================================================
    # CATEGORIZE NUCLIDES
    # ========================================================================
    # Use set operations to find differences and intersections
    common = endf_nuclides & ensdf_nuclides      # In both datasets
    endf_only = endf_nuclides - ensdf_nuclides   # Only in ENDF
    ensdf_only = ensdf_nuclides - endf_nuclides  # Only in ENSDF
    
    print("\n" + "=" * 60)
    print("NUCLIDE COVERAGE SUMMARY")
    print("=" * 60)
    print(f"Common to both:     {len(common):4d} nuclides")
    print(f"ENDF only:          {len(endf_only):4d} nuclides")
    print(f"ENSDF only:         {len(ensdf_only):4d} nuclides")
    print(f"Total ENDF:         {len(endf_nuclides):4d} nuclides")
    print(f"Total ENSDF:        {len(ensdf_nuclides):4d} nuclides")
    print("=" * 60)
    
    # ========================================================================
    # PREPARE DATA FOR PLOTTING
    # ========================================================================
    # Separate A and Z coordinates for each category
    
    # Common nuclides (blue)
    common_A = [A for A, Z in common]
    common_Z = [Z for A, Z in common]
    
    # ENDF-only nuclides (red)
    endf_A = [A for A, Z in endf_only]
    endf_Z = [Z for A, Z in endf_only]
    
    # ENSDF-only nuclides (green)
    ensdf_A = [A for A, Z in ensdf_only]
    ensdf_Z = [Z for A, Z in ensdf_only]
    
    # ========================================================================
    # CREATE PLOT
    # ========================================================================
    plt.figure(figsize=(14, 10))
    
    # Plot each category with different colors and markers
    # Plot in reverse order so most interesting data (differences) is on top
    
    if common:
        plt.scatter(common_A, common_Z, 
                   c='blue', marker='o', s=20, alpha=0.4, 
                   label=f'Both ENDF & ENSDF ({len(common)})')
    
    if ensdf_only:
        plt.scatter(ensdf_A, ensdf_Z, 
                   c='green', marker='s', s=30, alpha=0.7, 
                   label=f'ENSDF only ({len(ensdf_only)})')
    
    if endf_only:
        plt.scatter(endf_A, endf_Z, 
                   c='red', marker='^', s=30, alpha=0.7, 
                   label=f'ENDF only ({len(endf_only)})')
    
    # ========================================================================
    # FORMAT PLOT
    # ========================================================================
    plt.xlabel('Mass Number (A)', fontsize=12, fontweight='bold')
    plt.ylabel('Atomic Number (Z)', fontsize=12, fontweight='bold')
    plt.title('Nuclide Coverage Comparison: ENDF vs ENSDF Decay Data', 
              fontsize=14, fontweight='bold', pad=20)
    
    # Add grid for easier reading
    plt.grid(True, alpha=0.3, linestyle='--')
    
    # Add legend
    plt.legend(loc='upper left', fontsize=10, framealpha=0.9)
    
    # Set axis limits with some padding
    if endf_nuclides or ensdf_nuclides:
        all_Z = [Z for A, Z in (endf_nuclides | ensdf_nuclides)]
        all_A = [A for A, Z in (endf_nuclides | ensdf_nuclides)]
        
        plt.xlim(min(all_A) - 5, max(all_A) + 5)
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
        default="/Users/audreywarn/fluka-db-audrey/src/nuclear_data_output/json_data_modules/ascii/DECAY.ascii",
        help="Path to ENSDF DECAY.ascii file"
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
