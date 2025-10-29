#!/usr/bin/env python3
"""
Nuclide Coverage Comparison Plot (with Debug Mode)

This script creates a scatter plot comparing which nuclides (N, Z pairs) are present
in ENDF vs ENSDF DECAY data files.

Handles both ENDF format (A Z ...) and ENSDF format (index Element-A ...).
"""

import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend for headless environments
import matplotlib.pyplot as plt
from pathlib import Path
import argparse


def read_nuclides_from_decay_ascii(filepath, debug=False):
    """
    Read unique (N, Z) pairs from a DECAY.ascii file with robust parsing.
    
    Handles two formats:
    1. ENDF format: A Z parentLevel decay_mode ...
    2. ENSDF format: index Element-A energy units ...
    
    Args:
        filepath: Path to DECAY.ascii file
        debug: If True, print diagnostic information
        
    Returns:
        set: Set of (N, Z) tuples representing unique nuclides
    """
    # Element symbol to Z mapping
    ELEMENT_TO_Z = {
        'H': 1, 'He': 2, 'Li': 3, 'Be': 4, 'B': 5, 'C': 6, 'N': 7, 'O': 8, 'F': 9, 'Ne': 10,
        'Na': 11, 'Mg': 12, 'Al': 13, 'Si': 14, 'P': 15, 'S': 16, 'Cl': 17, 'Ar': 18, 'K': 19, 'Ca': 20,
        'Sc': 21, 'Ti': 22, 'V': 23, 'Cr': 24, 'Mn': 25, 'Fe': 26, 'Co': 27, 'Ni': 28, 'Cu': 29, 'Zn': 30,
        'Ga': 31, 'Ge': 32, 'As': 33, 'Se': 34, 'Br': 35, 'Kr': 36, 'Rb': 37, 'Sr': 38, 'Y': 39, 'Zr': 40,
        'Nb': 41, 'Mo': 42, 'Tc': 43, 'Ru': 44, 'Rh': 45, 'Pd': 46, 'Ag': 47, 'Cd': 48, 'In': 49, 'Sn': 50,
        'Sb': 51, 'Te': 52, 'I': 53, 'Xe': 54, 'Cs': 55, 'Ba': 56, 'La': 57, 'Ce': 58, 'Pr': 59, 'Nd': 60,
        'Pm': 61, 'Sm': 62, 'Eu': 63, 'Gd': 64, 'Tb': 65, 'Dy': 66, 'Ho': 67, 'Er': 68, 'Tm': 69, 'Yb': 70,
        'Lu': 71, 'Hf': 72, 'Ta': 73, 'W': 74, 'Re': 75, 'Os': 76, 'Ir': 77, 'Pt': 78, 'Au': 79, 'Hg': 80,
        'Tl': 81, 'Pb': 82, 'Bi': 83, 'Po': 84, 'At': 85, 'Rn': 86, 'Fr': 87, 'Ra': 88, 'Ac': 89, 'Th': 90,
        'Pa': 91, 'U': 92, 'Np': 93, 'Pu': 94, 'Am': 95, 'Cm': 96, 'Bk': 97, 'Cf': 98, 'Es': 99, 'Fm': 100,
        'Md': 101, 'No': 102, 'Lr': 103, 'Rf': 104, 'Db': 105, 'Sg': 106, 'Bh': 107, 'Hs': 108, 'Mt': 109, 'Ds': 110,
        'Rg': 111, 'Cn': 112, 'Nh': 113, 'Fl': 114, 'Mc': 115, 'Lv': 116, 'Ts': 117, 'Og': 118
    }
    
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
        
        # Track last known A and Z for ENDF multi-index format
        last_A = None
        last_Z = None
        
        for line_num, line in enumerate(data_lines, start=3):
            # Skip empty lines
            if not line.strip():
                continue
            
            try:
                # Get original line with leading spaces to determine format
                original_line = lines[line_num - 1]
                
                # Find position of first non-space character
                first_char_pos = len(original_line) - len(original_line.lstrip())
                
                # Split by whitespace for processing
                parts = line.split()
                
                if len(parts) < 2:
                    if debug:
                        print(f"Line {line_num}: Too few columns ({len(parts)})")
                    skipped_lines.append((line_num, "too few columns", line[:80]))
                    continue
                
                A = None
                Z = None
                
                # Determine format based on indentation:
                # - Position 0-3: Normal line with A, Z, parentLevel, ...
                # - Position 4-10: Blank-A line with Z, parentLevel, ... (A is blank)
                # - Position >20: Continuation line with final_level, Parent, ... (A, Z, parentLevel, decay_mode blank)
                
                if first_char_pos > 20:
                    # Continuation line: use last A and Z
                    if last_A is not None and last_Z is not None:
                        A = last_A
                        Z = last_Z
                        if debug and line_num < 30:
                            print(f"Line {line_num}: Continuation (indent={first_char_pos}), using A={A}, Z={Z}")
                    else:
                        if debug:
                            print(f"Line {line_num}: Continuation but no previous A/Z")
                        skipped_lines.append((line_num, "continuation without parent", line[:80]))
                        continue
                        
                elif first_char_pos >= 4 and first_char_pos <= 20:
                    # Check if first field looks like a decay mode (delayed particle format)
                    first_field = parts[0]
                    is_decay_mode = (
                        first_field.startswith('B-') or 
                        first_field.startswith('B+') or 
                        first_field.startswith('EC') or
                        first_field == 'A'
                    )
                    
                    if is_decay_mode:
                        # Delayed particle format: decay_mode final_level Parent ...
                        # Use last A and Z
                        if last_A is not None and last_Z is not None:
                            A = last_A
                            Z = last_Z
                            if debug and line_num < 100:
                                print(f"Line {line_num}: Delayed particle (indent={first_char_pos}), decay={first_field}, using A={A}, Z={Z}")
                        else:
                            if debug:
                                print(f"Line {line_num}: Delayed particle but no previous A/Z")
                            skipped_lines.append((line_num, "delayed particle without parent", line[:80]))
                            continue
                    else:
                        # Blank-A line: parts[0]=Z, parts[1]=parentLevel, need to find A from Parent
                        try:
                            Z = int(parts[0])
                            # Find Parent (Element-A format) in parts
                            found_parent = False
                            for part in parts[3:7]:  # Parent should be around position 4-6
                                if '-' in part:
                                    try:
                                        element_mass = part.split('-')
                                        if len(element_mass) == 2:
                                            element_sym = element_mass[0]
                                            A = int(element_mass[1])
                                            Z_check = ELEMENT_TO_Z.get(element_sym)
                                            if Z_check == Z:  # Verify Z matches
                                                last_A = A
                                                last_Z = Z
                                                found_parent = True
                                                if debug and line_num < 20:
                                                    print(f"Line {line_num}: Blank-A format (indent={first_char_pos}), Z={Z}, Parent={part} -> A={A}")
                                                break
                                    except (ValueError, IndexError):
                                        continue
                            
                            if not found_parent:
                                if debug:
                                    print(f"Line {line_num}: Blank-A but no Parent found: {parts[:6]}")
                                skipped_lines.append((line_num, "blank-A no parent", line[:80]))
                                continue
                        except ValueError:
                            if debug:
                                print(f"Line {line_num}: Blank-A but can't parse Z: {parts[:3]}")
                            skipped_lines.append((line_num, "blank-A invalid Z", line[:80]))
                            continue
                        
                else:
                    # Normal line: parts[0]=A, parts[1]=Z
                    try:
                        A = int(parts[0])
                        Z = int(parts[1])
                        last_A = A
                        last_Z = Z
                        if debug and line_num < 15:
                            print(f"Line {line_num}: Normal format (indent={first_char_pos}), A={A}, Z={Z}")
                    except ValueError:
                        if debug:
                            print(f"Line {line_num}: Cannot parse A, Z from: {parts[:3]}")
                        skipped_lines.append((line_num, "invalid A or Z", line[:80]))
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
                    
            except Exception as e:
                if debug:
                    print(f"Line {line_num}: Unexpected error: {e}")
                skipped_lines.append((line_num, str(e), line[:80]))
                continue
        
        print(f"Successfully parsed {len(nuclides)} unique (N, Z) pairs")
        
        if skipped_lines:
            print(f"Skipped {len(skipped_lines)} lines due to parsing issues")
            if debug and len(skipped_lines) > 0:
                print(f"\nFirst 5 skipped lines:")
                for line_num, reason, content in skipped_lines[:5]:
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
    
    # Check light element region
    light_region = {(N, Z) for N, Z in common if Z <= 20 and abs(N - Z) <= 10}
    print(f"\nLight radioactive region (Z≤20, |N-Z|≤10): {len(light_region)} common nuclides")
    
    if light_region:
        examples = sorted(light_region)[:10]
        print(f"  Examples: {examples[:5]}")
    
    # Check proton-rich vs neutron-rich distribution
    print(f"\n" + "=" * 60)
    print("PROTON-RICH vs NEUTRON-RICH DISTRIBUTION")
    print("=" * 60)
    
    # ENDF distribution
    endf_proton_rich = {(N, Z) for N, Z in endf_nuclides if N < Z}
    endf_neutron_rich = {(N, Z) for N, Z in endf_nuclides if N > Z}
    endf_n_equals_z = {(N, Z) for N, Z in endf_nuclides if N == Z}
    
    print(f"ENDF dataset:")
    print(f"  Proton-rich (N<Z):   {len(endf_proton_rich):4d} ({100*len(endf_proton_rich)/len(endf_nuclides):.1f}%)")
    print(f"  N=Z line:            {len(endf_n_equals_z):4d} ({100*len(endf_n_equals_z)/len(endf_nuclides):.1f}%)")
    print(f"  Neutron-rich (N>Z):  {len(endf_neutron_rich):4d} ({100*len(endf_neutron_rich)/len(endf_nuclides):.1f}%)")
    
    # ENSDF distribution
    ensdf_proton_rich = {(N, Z) for N, Z in ensdf_nuclides if N < Z}
    ensdf_neutron_rich = {(N, Z) for N, Z in ensdf_nuclides if N > Z}
    ensdf_n_equals_z = {(N, Z) for N, Z in ensdf_nuclides if N == Z}
    
    print(f"\nENSDF dataset:")
    print(f"  Proton-rich (N<Z):   {len(ensdf_proton_rich):4d} ({100*len(ensdf_proton_rich)/len(ensdf_nuclides):.1f}%)")
    print(f"  N=Z line:            {len(ensdf_n_equals_z):4d} ({100*len(ensdf_n_equals_z)/len(ensdf_nuclides):.1f}%)")
    print(f"  Neutron-rich (N>Z):  {len(ensdf_neutron_rich):4d} ({100*len(ensdf_neutron_rich)/len(ensdf_nuclides):.1f}%)")
    
    # Check overlap in each region
    common_proton_rich = endf_proton_rich & ensdf_proton_rich
    common_neutron_rich = endf_neutron_rich & ensdf_neutron_rich
    
    print(f"\nOverlap by region:")
    print(f"  Proton-rich:   {len(common_proton_rich):4d}/{len(endf_proton_rich):4d} ENDF ({100*len(common_proton_rich)/len(endf_proton_rich):.1f}% coverage)")
    print(f"                 {len(common_proton_rich):4d}/{len(ensdf_proton_rich):4d} ENSDF ({100*len(common_proton_rich)/len(ensdf_proton_rich):.1f}% coverage)")
    print(f"  Neutron-rich:  {len(common_neutron_rich):4d}/{len(endf_neutron_rich):4d} ENDF ({100*len(common_neutron_rich)/len(endf_neutron_rich):.1f}% coverage)")
    print(f"                 {len(common_neutron_rich):4d}/{len(ensdf_neutron_rich):4d} ENSDF ({100*len(common_neutron_rich)/len(ensdf_neutron_rich):.1f}% coverage)")
    
    # Missing in ENSDF
    ensdf_missing_proton = endf_proton_rich - ensdf_proton_rich
    ensdf_missing_neutron = endf_neutron_rich - ensdf_neutron_rich
    
    print(f"\nMissing from ENSDF:")
    print(f"  Proton-rich:   {len(ensdf_missing_proton):4d} nuclides")
    print(f"  Neutron-rich:  {len(ensdf_missing_neutron):4d} nuclides")
    print("=" * 60)
    
    # Check known radioactive nuclides (common ones that should be in both datasets)
    known_radioactive = {
        (2, 1),    # H-3 (tritium)
        (8, 6),    # C-14
        (14, 11),  # Na-25
        (33, 27),  # Co-60
        (52, 38),  # Sr-90
        (89, 55),  # Cs-144
        (90, 62),  # Sm-152
        (146, 92), # U-238
    }
    
    radio_in_both = known_radioactive & common
    radio_in_endf_only = known_radioactive & endf_only
    radio_in_ensdf_only = known_radioactive & ensdf_only
    
    print(f"\nKnown radioactive nuclides (validation set):")
    print(f"  In both datasets: {len(radio_in_both)}/{len(known_radioactive)}")
    if radio_in_both:
        print(f"    {radio_in_both}")
    if radio_in_endf_only:
        print(f"  In ENDF only: {radio_in_endf_only}")
    if radio_in_ensdf_only:
        print(f"  In ENSDF only: {radio_in_ensdf_only}")
    
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
