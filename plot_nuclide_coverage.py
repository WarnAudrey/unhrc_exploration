#!/usr/bin/env python3
"""
Nuclide Coverage Comparison Plot

This script creates a scatter plot comparing which nuclides (A, Z pairs) are present
in ENDF vs JSON DECAY data files.

Plot shows:
- Blue: Nuclides in both ENDF and JSON
- Red: Nuclides only in ENDF
- Green: Nuclides only in JSON

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


def plot_nuclide_comparison(endf_nuclides, json_nuclides, output_file="nuclide_coverage.png"):
    """
    Create a scatter plot comparing ENDF and JSON nuclide coverage.
    
    Args:
        endf_nuclides: Set of (A, Z) tuples from ENDF data
        json_nuclides: Set of (A, Z) tuples from JSON data
        output_file: Path to save the plot image
    """
    # ========================================================================
    # CATEGORIZE NUCLIDES
    # ========================================================================
    # Use set operations to find differences and intersections
    common = endf_nuclides & json_nuclides      # In both datasets
    endf_only = endf_nuclides - json_nuclides   # Only in ENDF
    json_only = json_nuclides - endf_nuclides   # Only in JSON
    
    print("\n" + "=" * 60)
    print("NUCLIDE COVERAGE SUMMARY")
    print("=" * 60)
    print(f"Common to both:     {len(common):4d} nuclides")
    print(f"ENDF only:          {len(endf_only):4d} nuclides")
    print(f"JSON only:          {len(json_only):4d} nuclides")
    print(f"Total ENDF:         {len(endf_nuclides):4d} nuclides")
    print(f"Total JSON:         {len(json_nuclides):4d} nuclides")
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
    
    # JSON-only nuclides (green)
    json_A = [A for A, Z in json_only]
    json_Z = [Z for A, Z in json_only]
    
    # ========================================================================
    # CREATE PLOT
    # ========================================================================
    plt.figure(figsize=(14, 10))
    
    # Plot each category with different colors and markers
    # Plot in reverse order so most interesting data (differences) is on top
    
    if common:
        plt.scatter(common_Z, common_A, 
                   c='blue', marker='o', s=20, alpha=0.4, 
                   label=f'Both ENDF & JSON ({len(common)})')
    
    if json_only:
        plt.scatter(json_Z, json_A, 
                   c='green', marker='s', s=30, alpha=0.7, 
                   label=f'JSON only ({len(json_only)})')
    
    if endf_only:
        plt.scatter(endf_Z, endf_A, 
                   c='red', marker='^', s=30, alpha=0.7, 
                   label=f'ENDF only ({len(endf_only)})')
    
    # ========================================================================
    # FORMAT PLOT
    # ========================================================================
    plt.xlabel('Atomic Number (Z)', fontsize=12, fontweight='bold')
    plt.ylabel('Mass Number (A)', fontsize=12, fontweight='bold')
    plt.title('Nuclide Coverage Comparison: ENDF vs JSON Decay Data', 
              fontsize=14, fontweight='bold', pad=20)
    
    # Add grid for easier reading
    plt.grid(True, alpha=0.3, linestyle='--')
    
    # Add legend
    plt.legend(loc='upper left', fontsize=10, framealpha=0.9)
    
    # Set axis limits with some padding
    if endf_nuclides or json_nuclides:
        all_Z = [Z for A, Z in (endf_nuclides | json_nuclides)]
        all_A = [A for A, Z in (endf_nuclides | json_nuclides)]
        
        plt.xlim(min(all_Z) - 2, max(all_Z) + 2)
        plt.ylim(min(all_A) - 5, max(all_A) + 5)
    
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
        description="Compare nuclide coverage between ENDF and JSON DECAY data"
    )
    parser.add_argument(
        '--endf',
        type=str,
        default="/Users/audreywarn/fluka-db-audrey/outputs/endf/endf_data_modules/ascii/DECAY.ascii",
        help="Path to ENDF DECAY.ascii file"
    )
    parser.add_argument(
        '--json',
        type=str,
        default="/Users/audreywarn/fluka-db-audrey/src/nuclear_data_output/json_data_modules/ascii/DECAY.ascii",
        help="Path to JSON DECAY.ascii file"
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
    json_file = args.json
    output_file = args.output
    z_max = args.zmax
    
    print("=" * 60)
    print("NUCLIDE COVERAGE COMPARISON")
    print("=" * 60)
    print(f"ENDF file: {endf_file}")
    print(f"JSON file: {json_file}")
    print(f"Output:    {output_file}")
    print(f"Z cutoff:  {z_max}")
    print("=" * 60)
    
    # ========================================================================
    # READ DATA
    # ========================================================================
    print("\nReading ENDF decay data...")
    endf_nuclides = read_nuclides_from_decay_ascii(endf_file)
    
    print("\nReading JSON decay data...")
    json_nuclides = read_nuclides_from_decay_ascii(json_file)
    
    # Check if data was loaded
    if not endf_nuclides and not json_nuclides:
        print("\nError: No data loaded from either file. Exiting.")
        return
    
    # ========================================================================
    # APPLY Z CUTOFF
    # ========================================================================
    print(f"\nApplying Z <= {z_max} filter...")
    endf_nuclides = filter_by_z_cutoff(endf_nuclides, z_max=z_max)
    json_nuclides = filter_by_z_cutoff(json_nuclides, z_max=z_max)
    
    # ========================================================================
    # CREATE PLOT
    # ========================================================================
    print("\nGenerating plot...")
    plot_nuclide_comparison(endf_nuclides, json_nuclides, 
                           output_file=output_file)
    
    print("\nDone!")


if __name__ == "__main__":
    main()
