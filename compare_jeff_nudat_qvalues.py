#!/usr/bin/env python3
"""
Compare JEFF-4.0 Q-values with NuDat experimental data.

This script uses your ENDF parser to extract Q-values directly from JEFF-4.0
and compares them with known experimental values from NuDat/ENSDF.

Purpose: Document and demonstrate the small Q-value issue in JEFF-4.0.
"""

import sys
from pathlib import Path

# Import your ENDF parser
try:
    from JEFF_ENDF_parser import ENDFNumericDecayParser, ATOMIC_SYMBOL
except ImportError:
    print("Error: JEFF_ENDF_parser.py not found in current directory")
    print("Please ensure JEFF_ENDF_parser.py is available")
    sys.exit(1)

# Known experimental Q-values from NuDat (https://www.nndc.bnl.gov/nudat3/)
# Format: (A, Z, mode): Q-value in keV
NUDAT_Q_VALUES = {
    # Li-11 β- decay
    (11, 3, 'B-'): 20230.0,  # NuDat: 20,230 keV
    
    # C-9 EC decay
    (9, 6, 'EC'): 16500.0,  # NuDat: ~16.5 MeV
    
    # C-10 EC decay
    (10, 6, 'EC'): 3648.0,  # NuDat: 3,648.12 keV
    
    # Be-7 EC decay
    (7, 4, 'EC'): 861.82,  # NuDat: 861.82 keV
    
    # N-12 EC decay
    (12, 7, 'EC'): 17338.0,  # NuDat: 17,338 keV
    
    # Be-12 β- decay
    (12, 4, 'B-'): 11710.0,  # NuDat: 11,710 keV (for comparison - should be OK)
    
    # He-6 β- decay
    (6, 2, 'B-'): 3508.0,  # NuDat: 3,508 keV (for comparison)
    
    # H-3 β- decay
    (3, 1, 'B-'): 18.59,  # NuDat: 18.59 keV (for comparison)
}

def decode_rtyp_simple(rtyp):
    """Decode RTYP to simple mode string."""
    rtyp_float = float(rtyp)
    
    if rtyp_float == 0.0:
        return "γ"
    elif rtyp_float == 1.0:
        return "B-"
    elif rtyp_float == 2.0:
        return "EC/B+"
    elif rtyp_float == 3.0:
        return "IT"
    elif rtyp_float == 4.0:
        return "α"
    elif rtyp_float == 5.0:
        return "n"
    elif rtyp_float == 6.0:
        return "SF"
    elif rtyp_float == 7.0:
        return "p"
    else:
        # Complex mode
        primary = int(rtyp_float)
        secondary = int(round((rtyp_float - primary) * 10))
        primary_map = {0: "γ", 1: "B-", 2: "EC/B+", 4: "α", 5: "n", 6: "SF", 7: "p"}
        secondary_map = {0: "", 1: "n", 2: "p", 4: "α", 5: "n", 7: "p"}
        return f"{primary_map.get(primary, str(primary))}{secondary_map.get(secondary, '')}"

def find_jeff_qvalues(jeff_file):
    """
    Parse JEFF file and extract all Q-values.
    
    Returns:
        dict: {(A, Z, mode): Q-value in eV}
    """
    parser = ENDFNumericDecayParser()
    parser.load_file(jeff_file)
    
    qvalues = {}
    sections_found = 0
    
    print(f"\n{'='*80}")
    print(f"Parsing JEFF file: {Path(jeff_file).name}")
    print(f"{'='*80}\n")
    
    # Scan through file for all MF=8 MT=457 sections
    parser._pos = 0
    while parser._pos < len(parser._lines):
        try:
            if parser._scan_to_mf_mt(8, 457):
                sections_found += 1
                
                # Parse this section
                data = parser._parse_mf8_mt457()
                
                # Extract identification
                za = data["ZA"]
                A = za % 1000
                Z = za // 1000
                element = ATOMIC_SYMBOL.get(Z, f'Z{Z}')
                nuclide = f"{element}-{A}"
                
                # Extract Q-values from decay modes
                if "modes" in data:
                    for mode in data["modes"]:
                        rtyp = mode["RTYP"]
                        mode_str = decode_rtyp_simple(rtyp)
                        
                        # Get Q-value (value, uncertainty) tuple
                        q_tuple = mode["Q"]
                        q_value = q_tuple[0] if isinstance(q_tuple, tuple) else q_tuple
                        
                        # Store in dictionary
                        key = (A, Z, mode_str)
                        qvalues[key] = float(q_value)
                
                # Move past this section
                parser._pos += 1
            else:
                break
                
        except EOFError:
            break
        except Exception as e:
            parser._pos += 1
            continue
    
    print(f"Processed {sections_found} decay sections")
    print(f"Extracted {len(qvalues)} Q-values\n")
    
    return qvalues

def compare_qvalues(jeff_file):
    """
    Compare JEFF Q-values with NuDat experimental values.
    """
    # Extract Q-values from JEFF
    jeff_qvalues = find_jeff_qvalues(jeff_file)
    
    # Prepare comparison data
    comparisons = []
    
    for (A, Z, mode), nudat_q_kev in NUDAT_Q_VALUES.items():
        element = ATOMIC_SYMBOL.get(Z, f'Z{Z}')
        nuclide = f"{element}-{A}"
        
        # Look up JEFF Q-value
        jeff_q_ev = jeff_qvalues.get((A, Z, mode), None)
        
        if jeff_q_ev is not None:
            jeff_q_kev = jeff_q_ev / 1000.0  # Convert eV to keV
            ratio = jeff_q_kev / nudat_q_kev if nudat_q_kev > 0 else 0
            diff = abs(jeff_q_kev - nudat_q_kev)
            
            comparisons.append({
                'nuclide': nuclide,
                'mode': mode,
                'jeff_kev': jeff_q_kev,
                'nudat_kev': nudat_q_kev,
                'diff_kev': diff,
                'ratio': ratio
            })
    
    # Display results
    print(f"\n{'='*80}")
    print(f"JEFF-4.0 Q-VALUES vs NuDat EXPERIMENTAL DATA")
    print(f"{'='*80}\n")
    
    print(f"{'Nuclide':<12} {'Mode':<8} {'JEFF (keV)':<15} {'NuDat (keV)':<15} {'Ratio':<12} {'Status'}")
    print(f"{'-'*80}")
    
    small_qvalues = []
    normal_qvalues = []
    
    for comp in comparisons:
        nuclide = comp['nuclide']
        mode = comp['mode']
        jeff = comp['jeff_kev']
        nudat = comp['nudat_kev']
        ratio = comp['ratio']
        
        # Determine status
        if jeff < 0.1:  # Less than 100 eV
            status = "⚠️  MINIMAL VALUE"
            small_qvalues.append(comp)
        elif ratio > 0.9 and ratio < 1.1:
            status = "✓  Good match"
            normal_qvalues.append(comp)
        else:
            status = "~  Differs"
            normal_qvalues.append(comp)
        
        print(f"{nuclide:<12} {mode:<8} {jeff:<15.2e} {nudat:<15.2f} {ratio:<12.6f} {status}")
    
    # Summary statistics
    print(f"\n{'='*80}")
    print(f"SUMMARY")
    print(f"{'='*80}\n")
    
    print(f"Total comparisons:        {len(comparisons)}")
    print(f"Minimal values (< 100 eV): {len(small_qvalues)}")
    print(f"Normal values:            {len(normal_qvalues)}")
    
    if small_qvalues:
        print(f"\n{'='*80}")
        print(f"DETAILED ANALYSIS: Minimal Q-values")
        print(f"{'='*80}\n")
        
        for comp in small_qvalues:
            nuclide = comp['nuclide']
            mode = comp['mode']
            jeff = comp['jeff_kev']
            nudat = comp['nudat_kev']
            diff = comp['diff_kev']
            
            print(f"{nuclide} {mode} decay:")
            print(f"  JEFF-4.0:     {jeff:.6e} keV  ({jeff*1000:.3f} eV)")
            print(f"  NuDat/ENSDF:  {nudat:.2f} keV")
            print(f"  Difference:   {diff:.2f} keV")
            print(f"  Orders of magnitude off: {abs(int(round(np.log10(nudat/jeff))))}")
            print()
    
    return comparisons, small_qvalues

def scan_for_all_small_qvalues(jeff_file, threshold_ev=100):
    """
    Scan JEFF file for ALL Q-values below threshold.
    
    Args:
        jeff_file: Path to JEFF ENDF file
        threshold_ev: Threshold in eV (default: 100 eV)
    """
    jeff_qvalues = find_jeff_qvalues(jeff_file)
    
    small_qvalues = []
    
    for (A, Z, mode), q_ev in jeff_qvalues.items():
        if q_ev < threshold_ev:
            element = ATOMIC_SYMBOL.get(Z, f'Z{Z}')
            nuclide = f"{element}-{A}"
            small_qvalues.append({
                'nuclide': nuclide,
                'A': A,
                'Z': Z,
                'mode': mode,
                'q_ev': q_ev,
                'q_kev': q_ev / 1000.0
            })
    
    # Sort by Q-value
    small_qvalues.sort(key=lambda x: x['q_ev'])
    
    print(f"\n{'='*80}")
    print(f"ALL Q-VALUES < {threshold_ev} eV IN JEFF-4.0")
    print(f"{'='*80}\n")
    
    print(f"Found {len(small_qvalues)} entries with Q < {threshold_ev} eV\n")
    
    print(f"{'Nuclide':<12} {'Mode':<10} {'Q (eV)':<15} {'Q (keV)':<15}")
    print(f"{'-'*80}")
    
    for entry in small_qvalues[:50]:  # Show first 50
        print(f"{entry['nuclide']:<12} {entry['mode']:<10} {entry['q_ev']:<15.6e} {entry['q_kev']:<15.6e}")
    
    if len(small_qvalues) > 50:
        print(f"\n... and {len(small_qvalues) - 50} more entries")
    
    return small_qvalues

if __name__ == "__main__":
    import argparse
    import numpy as np
    
    parser = argparse.ArgumentParser(
        description="Compare JEFF-4.0 Q-values with NuDat experimental data"
    )
    parser.add_argument(
        "jeff_file",
        help="Path to JEFF ENDF file (e.g., jeff-40-radioactive.endf)"
    )
    parser.add_argument(
        "--scan-all",
        action="store_true",
        help="Scan for ALL small Q-values (< 100 eV)"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=100.0,
        help="Threshold in eV for small Q-values (default: 100)"
    )
    
    args = parser.parse_args()
    
    # Check file exists
    if not Path(args.jeff_file).exists():
        print(f"Error: File not found: {args.jeff_file}")
        sys.exit(1)
    
    # Run comparison
    comparisons, small_qvalues = compare_qvalues(args.jeff_file)
    
    # Optionally scan for all small Q-values
    if args.scan_all:
        all_small = scan_for_all_small_qvalues(args.jeff_file, threshold_ev=args.threshold)
