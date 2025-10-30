#!/usr/bin/env python3
"""
Nuclide Coverage Overlay on Karlsruhe Chart

This script overlays ENDF and ENSDF nuclide coverage comparison on top of
the Karlsruhe Nuclide Chart (Chart of Nuclides).

You need to:
1. Download the Karlsruhe chart image (PNG/JPG)
2. Provide the path to the image
3. Optionally specify the N and Z ranges of the chart

Plot shows:
- Background: Karlsruhe Nuclide Chart
- Blue circles: Nuclides in both ENDF and ENSDF
- Red triangles: Nuclides only in ENDF
- Green squares: Nuclides only in ENSDF

NOTE: EC (Electron Capture) decays are NOT included in the final datasets.
Both ENDF and ENSDF parsers exclude EC after using it for β+/EC splitting calculations.
Datasets include: α, β-, β+, and delayed particle decays (B-n, B+p, B-a, etc.).
"""

import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend for headless environments
import matplotlib.pyplot as plt
from matplotlib import image as mpimg
from pathlib import Path
import argparse
import numpy as np


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


def plot_nuclide_overlay(endf_nuclides, ensdf_nuclides, 
                         chart_image_path=None,
                         n_min=0, n_max=180, z_min=0, z_max=120,
                         output_file="nuclide_overlay.png"):
    """
    Create a scatter plot overlaid on the Karlsruhe Nuclide Chart.
    
    Args:
        endf_nuclides: Set of (A, Z) tuples from ENDF data
        ensdf_nuclides: Set of (A, Z) tuples from ENSDF data
        chart_image_path: Path to Karlsruhe chart background image
        n_min, n_max: Neutron number range of the background chart
        z_min, z_max: Atomic number range of the background chart
        output_file: Path to save the plot image
    """
    # ========================================================================
    # CATEGORIZE NUCLIDES
    # ========================================================================
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
    # Calculate N (neutron number = A - Z) and Z for each category
    
    # Common nuclides (blue)
    common_N = [A - Z for A, Z in common]
    common_Z = [Z for A, Z in common]
    
    # ENDF-only nuclides (red)
    endf_N = [A - Z for A, Z in endf_only]
    endf_Z = [Z for A, Z in endf_only]
    
    # ENSDF-only nuclides (green)
    ensdf_N = [A - Z for A, Z in ensdf_only]
    ensdf_Z = [Z for A, Z in ensdf_only]
    
    # ========================================================================
    # CREATE FIGURE
    # ========================================================================
    fig, ax = plt.subplots(figsize=(16, 12))
    
    # ========================================================================
    # LOAD AND DISPLAY BACKGROUND CHART
    # ========================================================================
    if chart_image_path and Path(chart_image_path).exists():
        print(f"\nLoading background image: {chart_image_path}")
        try:
            img = mpimg.imread(chart_image_path)
            
            # Display image with proper extent (coordinates)
            # extent = [left, right, bottom, top] in data coordinates
            ax.imshow(img, aspect='auto', 
                     extent=[n_min, n_max, z_min, z_max],
                     zorder=0, alpha=0.7)
            print(f"Chart range: N=[{n_min}, {n_max}], Z=[{z_min}, {z_max}]")
        except Exception as e:
            print(f"Warning: Could not load background image: {e}")
            print("Proceeding with plain background...")
    else:
        if chart_image_path:
            print(f"Warning: Chart image not found at {chart_image_path}")
        print("Creating plot without background chart")
    
    # ========================================================================
    # OVERLAY SCATTER PLOT
    # ========================================================================
    # Plot with higher zorder to appear on top of background
    # Use edge colors for better visibility on background
    
    if common:
        ax.scatter(common_N, common_Z, 
                  c='blue', marker='o', s=25, alpha=0.6,
                  edgecolors='darkblue', linewidths=0.5,
                  label=f'Both ENDF & ENSDF ({len(common)})',
                  zorder=3)
    
    if ensdf_only:
        ax.scatter(ensdf_N, ensdf_Z, 
                  c='limegreen', marker='s', s=35, alpha=0.8,
                  edgecolors='darkgreen', linewidths=0.8,
                  label=f'ENSDF only ({len(ensdf_only)})',
                  zorder=4)
    
    if endf_only:
        ax.scatter(endf_N, endf_Z, 
                  c='red', marker='^', s=35, alpha=0.8,
                  edgecolors='darkred', linewidths=0.8,
                  label=f'ENDF only ({len(endf_only)})',
                  zorder=5)
    
    # ========================================================================
    # FORMAT PLOT
    # ========================================================================
    ax.set_xlabel('Neutron Number (N)', fontsize=14, fontweight='bold')
    ax.set_ylabel('Atomic Number (Z)', fontsize=14, fontweight='bold')
    ax.set_title('Nuclide Coverage: ENDF vs ENSDF (Overlay on Karlsruhe Chart)', 
                fontsize=15, fontweight='bold', pad=20)
    
    # Add grid (subtle, so it doesn't interfere with background)
    ax.grid(True, alpha=0.2, linestyle='--', zorder=1)
    
    # Add legend with semi-transparent background
    ax.legend(loc='upper left', fontsize=11, framealpha=0.95, 
             edgecolor='black', fancybox=True)
    
    # Set axis limits
    if chart_image_path and Path(chart_image_path).exists():
        # Use chart's coordinate system
        ax.set_xlim(n_min, n_max)
        ax.set_ylim(z_min, z_max)
    else:
        # Auto-scale to data
        if endf_nuclides or ensdf_nuclides:
            all_Z = [Z for A, Z in (endf_nuclides | ensdf_nuclides)]
            all_N = [A - Z for A, Z in (endf_nuclides | ensdf_nuclides)]
            ax.set_xlim(min(all_N) - 5, max(all_N) + 5)
            ax.set_ylim(min(all_Z) - 2, max(all_Z) + 2)
    
    # Tight layout
    plt.tight_layout()
    
    # ========================================================================
    # SAVE PLOT
    # ========================================================================
    plt.savefig(output_file, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"\nOverlay plot saved to: {output_file}")
    
    # plt.show()  # Disabled for headless mode


def main():
    """
    Main function to create nuclide coverage overlay.
    """
    # ========================================================================
    # PARSE COMMAND-LINE ARGUMENTS
    # ========================================================================
    parser = argparse.ArgumentParser(
        description="Overlay ENDF/ENSDF coverage on Karlsruhe Nuclide Chart",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usage:
  # With downloaded Karlsruhe chart:
  python3 plot_nuclide_overlay.py --chart karlsruhe_chart.png
  
  # With custom coordinate ranges:
  python3 plot_nuclide_overlay.py --chart chart.png --n-range 0 200 --z-range 0 110
  
  # Without background (plain plot):
  python3 plot_nuclide_overlay.py
        """
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
        '--chart',
        type=str,
        default=None,
        help="Path to Karlsruhe Nuclide Chart background image (PNG/JPG)"
    )
    parser.add_argument(
        '--n-range',
        type=int,
        nargs=2,
        default=[0, 180],
        metavar=('N_MIN', 'N_MAX'),
        help="Neutron number range of background chart (default: 0 180)"
    )
    parser.add_argument(
        '--z-range',
        type=int,
        nargs=2,
        default=[0, 120],
        metavar=('Z_MIN', 'Z_MAX'),
        help="Atomic number range of background chart (default: 0 120)"
    )
    parser.add_argument(
        '--output',
        type=str,
        default="nuclide_overlay_karlsruhe.png",
        help="Output plot filename (default: nuclide_overlay_karlsruhe.png)"
    )
    parser.add_argument(
        '--zmax',
        type=int,
        default=100,
        help="Maximum Z value to include in data (default: 100)"
    )
    
    args = parser.parse_args()
    
    # ========================================================================
    # DISPLAY CONFIGURATION
    # ========================================================================
    print("=" * 70)
    print("NUCLIDE COVERAGE OVERLAY ON KARLSRUHE CHART")
    print("=" * 70)
    print(f"ENDF file:        {args.endf}")
    print(f"ENSDF file:       {args.ensdf}")
    print(f"Background chart: {args.chart if args.chart else 'None (plain background)'}")
    print(f"Chart N range:    {args.n_range[0]} - {args.n_range[1]}")
    print(f"Chart Z range:    {args.z_range[0]} - {args.z_range[1]}")
    print(f"Data Z cutoff:    {args.zmax}")
    print(f"Output file:      {args.output}")
    print("=" * 70)
    
    # ========================================================================
    # READ DATA
    # ========================================================================
    print("\nReading ENDF decay data...")
    endf_nuclides = read_nuclides_from_decay_ascii(args.endf)
    
    print("\nReading ENSDF decay data...")
    ensdf_nuclides = read_nuclides_from_decay_ascii(args.ensdf)
    
    # Check if data was loaded
    if not endf_nuclides and not ensdf_nuclides:
        print("\nError: No data loaded from either file. Exiting.")
        return
    
    # ========================================================================
    # APPLY Z CUTOFF
    # ========================================================================
    print(f"\nApplying Z <= {args.zmax} filter...")
    endf_nuclides = filter_by_z_cutoff(endf_nuclides, z_max=args.zmax)
    ensdf_nuclides = filter_by_z_cutoff(ensdf_nuclides, z_max=args.zmax)
    
    # ========================================================================
    # CREATE OVERLAY PLOT
    # ========================================================================
    print("\nGenerating overlay plot...")
    plot_nuclide_overlay(
        endf_nuclides, 
        ensdf_nuclides,
        chart_image_path=args.chart,
        n_min=args.n_range[0],
        n_max=args.n_range[1],
        z_min=args.z_range[0],
        z_max=args.z_range[1],
        output_file=args.output
    )
    
    print("\n" + "=" * 70)
    print("INSTRUCTIONS FOR DOWNLOADING KARLSRUHE CHART:")
    print("=" * 70)
    print("1. Visit: https://www.nndc.bnl.gov/nudat3/")
    print("   OR: https://www-nds.iaea.org/relnsd/vcharthtml/VChartHTML.html")
    print("   OR: Search 'Karlsruhe Nuclide Chart' and download high-res image")
    print("")
    print("2. Download a high-resolution PNG or JPG of the chart")
    print("")
    print("3. Run this script again with:")
    print(f"   python3 {Path(__file__).name} --chart /path/to/chart.png")
    print("=" * 70)
    
    print("\nDone!")


if __name__ == "__main__":
    main()
