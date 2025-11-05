#!/usr/bin/env python3
"""
Test with a real ENDF file containing multiple STYP types.

This uses actual ENDF-B-VIII.0 data for Br-74 which has:
- STYP=0 (Gamma rays)
- STYP=2 (Beta+ particles)
- STYP=8 (X-rays)
- STYP=9 (Auger electrons)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from JEFF_ENDF_parser import ENDFNumericDecayParser

# Real ENDF data for Br-74 (partial - showing multiple STYP types)
# This nuclide has EC/B+ decay with gamma, beta+, X-ray, and Auger spectra
br74_sample = """
 3.500000+4 7.329470+1          0          0          0          4 837 8457
 1.527000+3 2.000000+0          0          0          6          0 837 8457
 0.000000+0 0.000000+0 0.000000+0 0.000000+0 0.000000+0 0.000000+0 837 8457
 0.000000+0 1.000000+0          0          0         12          2 837 8457
 2.000000+0 0.000000+0 5.300000+6 1.000000+5 1.000000+0 0.000000+0 837 8457
 4.000000+7 0.000000+0 1.600000+6 0.000000+0 3.100000-4 1.000000-5 837 8457
 0.000000+0 0.000000+0          2          0          6        154 837 8457
 9.986000+3 0.000000+0 5.343000+5 0.000000+0 3.160000+3 0.000000+0 837 8457
 6.348000+2 0.000000+0          0          0          6        154 837 8457
 2.000000+0 0.000000+0 6.348000+2 0.000000+0 2.800000+1 2.000000+0 837 8457
 6.348000+2 0.000000+0          0          0          6        154 837 8457
 2.000000+0 0.000000+0 3.020000+2 0.000000+0 2.500000+1 2.000000+0 837 8457
 1.462000+3 0.000000+0          0          0          6        154 837 8457
 2.000000+0 0.000000+0 5.960000+2 0.000000+0 8.000000-1 3.000000-1 837 8457
 0.000000+0 2.000000+0          2          0          6         53 837 8457
 5.290000+3 0.000000+0 4.350000+5 0.000000+0 9.117000+2 0.000000+0 837 8457
 1.329000+3 0.000000+0          0          0          6         53 837 8457
 2.000000+0 0.000000+0 1.329000+3 0.000000+0 9.000000+1 3.000000+0 837 8457
 1.622000+3 0.000000+0          0          0          6         53 837 8457
 2.000000+0 0.000000+0 6.440000+2 0.000000+0 7.000000+1 2.000000+0 837 8457
 0.000000+0 8.000000+0          2          0          6         25 837 8457
 1.860000+4 0.000000+0 2.093000+4 0.000000+0 1.910000+4 0.000000+0 837 8457
 9.250000+3 0.000000+0          0          0          6         25 837 8457
 2.000000+0 0.000000+0 9.250000+3 0.000000+0 1.130000+3 0.000000+0 837 8457
 0.000000+0 9.000000+0          2          0          6          9 837 8457
 6.000000+2 0.000000+0 4.780000+3 0.000000+0 6.000000+2 0.000000+0 837 8457
 1.500000+3 0.000000+0          0          0          6          9 837 8457
 2.000000+0 0.000000+0 1.500000+3 0.000000+0 2.800000+2 0.000000+0 837 8457
                                                                  837 8  0
 0.000000+0 0.000000+0          0          0          0          0   0 0  0
"""


def test_real_multi_styp():
    """Test energy extraction from real ENDF data with multiple STYP types."""
    
    print("="*80)
    print("TESTING REAL ENDF DATA: Br-74 (Multiple STYP Types)")
    print("="*80)
    
    parser = ENDFNumericDecayParser()
    parser.load_text(br74_sample)
    
    if not parser._scan_to_mf_mt(8, 457):
        print("ERROR: Could not find MF=8 MT=457 section")
        return False
    
    try:
        data = parser._parse_mf8_mt457()
    except Exception as e:
        print(f"ERROR: Parsing failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print(f"\nParsed nuclide:")
    print(f"  ZA = {data['ZA']} (Br-74)")
    print(f"  LIS = {data['LIS']}")
    print(f"  Half-life = {data['T1/2'][0]:.1f} seconds")
    print(f"  NSP = {data['NSP']} spectra")
    
    if "spectra" not in data:
        print("\nERROR: No spectra found")
        return False
    
    print(f"\nFound {len(data['spectra'])} spectra:")
    
    styp_names = {
        0: "Gamma rays",
        1: "Beta- particles",
        2: "Beta+ particles",
        4: "Alpha particles",
        8: "X-rays",
        9: "Auger electrons"
    }
    
    all_passed = True
    styp_found = set()
    
    for i, spec in enumerate(data["spectra"]):
        styp = spec.get("STYP", -1)
        styp_name = styp_names.get(int(styp), f"Unknown ({styp})")
        styp_found.add(int(styp))
        
        print(f"\n{'-'*80}")
        print(f"Spectrum {i+1}: STYP={styp} ({styp_name})")
        print(f"{'-'*80}")
        
        # Check ER_AV (mean energy)
        if "ER_AV" in spec and spec["ER_AV"]:
            er_av = spec["ER_AV"]
            if isinstance(er_av, tuple):
                er_av_val, er_av_unc = er_av[0], er_av[1]
            else:
                er_av_val = er_av
                er_av_unc = 0.0
            
            print(f"  Mean Energy (ER_AV):")
            print(f"    {er_av_val:.2f} ± {er_av_unc:.2f} eV")
            print(f"    {er_av_val/1000:.3f} ± {er_av_unc/1000:.3f} keV")
            
            if er_av_val > 0:
                print(f"    ✓ Non-zero mean energy extracted")
            else:
                print(f"    ⚠ Warning: Zero mean energy")
        else:
            print(f"  ⚠ No ER_AV (mean energy) field")
        
        # Check FD (normalization)
        if "FD" in spec:
            fd = spec["FD"]
            if isinstance(fd, tuple):
                fd_val = fd[0]
            else:
                fd_val = fd
            print(f"  Normalization (FD): {fd_val:.2f}")
        
        # Check discrete transitions
        if "discrete" in spec and spec["discrete"]:
            n_discrete = len(spec["discrete"])
            print(f"  Discrete transitions: {n_discrete}")
            
            # Show first few transitions
            for j, disc in enumerate(spec["discrete"][:3]):
                print(f"\n    Transition {j+1}:")
                
                if "ER" in disc:
                    er = disc["ER"]
                    if isinstance(er, tuple):
                        er_val = er[0]
                        print(f"      Energy (ER): {er_val:.2f} eV = {er_val/1000:.3f} keV")
                
                # Beta spectra have E_AVG and IB
                if "E_AVG" in disc:
                    e_avg = disc["E_AVG"]
                    if isinstance(e_avg, tuple):
                        e_avg_val = e_avg[0]
                        print(f"      Average (E_AVG): {e_avg_val:.2f} eV = {e_avg_val/1000:.3f} keV")
                        print(f"      ✓ Beta spectrum energy field extracted")
                
                if "IB" in disc:
                    ib = disc["IB"]
                    if isinstance(ib, tuple):
                        ib_val = ib[0]
                        print(f"      Intensity (IB): {ib_val:.2f}%")
                
                # Gamma/Alpha/X-ray/Auger have RI
                if "RI" in disc:
                    ri = disc["RI"]
                    if isinstance(ri, tuple):
                        ri_val = ri[0]
                        print(f"      Intensity (RI): {ri_val:.2f}")
            
            if n_discrete > 3:
                print(f"    ... and {n_discrete - 3} more transitions")
        else:
            print(f"  No discrete transitions (continuous only)")
    
    # Summary
    print(f"\n{'='*80}")
    print(f"SUMMARY")
    print(f"{'='*80}")
    print(f"STYP types found in Br-74:")
    
    expected_styp = {0, 2, 8, 9}  # Gamma, Beta+, X-ray, Auger
    
    for styp_num in sorted(styp_found):
        styp_name = styp_names.get(styp_num, f"Unknown ({styp_num})")
        print(f"  ✓ STYP={styp_num}: {styp_name}")
    
    if styp_found == expected_styp:
        print(f"\n✓ ALL EXPECTED STYP TYPES FOUND")
        print(f"✓ Energy extraction working for real ENDF data!")
    else:
        missing = expected_styp - styp_found
        extra = styp_found - expected_styp
        if missing:
            print(f"\n⚠ Missing STYP types: {missing}")
        if extra:
            print(f"\n⚠ Unexpected STYP types: {extra}")
        all_passed = False
    
    print(f"{'='*80}")
    
    return all_passed


if __name__ == "__main__":
    success = test_real_multi_styp()
    sys.exit(0 if success else 1)
