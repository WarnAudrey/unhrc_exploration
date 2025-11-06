#!/usr/bin/env python3
"""
Comprehensive test to verify energy extraction for ALL STYP (spectrum types).

STYP values from ENDF-102:
  0 = Gamma rays
  1 = Beta- particles (electrons)
  2 = Beta+ particles (positrons)
  4 = Alpha particles
  8 = X-rays
  9 = Auger electrons
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from JEFF_ENDF_parser import ENDFNumericDecayParser

# Test data templates for each STYP type
def create_test_endf(za, styp, er_av, endpoint=None, intensity=100.0, half_life=3600.0):
    """
    Create a minimal ENDF MF=8 MT=457 section with one spectrum.
    
    Args:
        za: Nuclide identifier (Z*1000 + A)
        styp: Spectrum type (0=gamma, 1=beta-, 2=beta+, 4=alpha, 8=xray, 9=auger)
        er_av: Average/mean energy in eV
        endpoint: Endpoint energy in eV (for beta spectra)
        intensity: Intensity percentage
        half_life: Half-life in seconds
    """
    
    # MAT number (arbitrary for test)
    mat = 9999
    
    # Format floats in ENDF notation (E-less scientific)
    def fmt_endf(val):
        if val == 0.0:
            return " 0.000000+0"
        exp = 0
        mantissa = val
        if val != 0:
            while abs(mantissa) >= 10:
                mantissa /= 10
                exp += 1
            while abs(mantissa) < 1:
                mantissa *= 10
                exp -= 1
        sign = '+' if exp >= 0 else '-'
        return f" {mantissa:.6f}{sign}{abs(exp)}"
    
    z = za // 1000
    a = za % 1000
    awr = float(a)
    
    # Determine decay mode based on STYP
    if styp == 0:
        rtyp = 0.0  # Gamma
    elif styp == 1:
        rtyp = 1.0  # Beta-
    elif styp == 2:
        rtyp = 2.0  # EC/Beta+
    elif styp == 4:
        rtyp = 4.0  # Alpha
    elif styp == 8:
        rtyp = 0.0  # X-rays (usually from gamma/EC)
    elif styp == 9:
        rtyp = 0.0  # Auger (usually from gamma/EC)
    else:
        rtyp = 1.0  # Default to beta-
    
    if endpoint is None:
        endpoint = er_av * 1.5  # Approximate for beta
    
    endf_text = f"""
 1.000000+0 1.000000+0          0          0          0          1{mat:4d} 8457
{fmt_endf(half_life)}{fmt_endf(0.0)}          0          0          6          0{mat:4d} 8457
 0.000000+0 0.000000+0 0.000000+0 0.000000+0 0.000000+0 0.000000+0{mat:4d} 8457
 5.000000-1 1.000000+0          0          0          6          1{mat:4d} 8457
{fmt_endf(rtyp)}{fmt_endf(0.0)}{fmt_endf(endpoint)}{fmt_endf(0.0)} 1.000000+0 0.000000+0{mat:4d} 8457
 0.000000+0{fmt_endf(float(styp))}          2          0          6          1{mat:4d} 8457
 1.000000+0 0.000000+0{fmt_endf(er_av)}{fmt_endf(0.0)} 1.000000+0 0.000000+0{mat:4d} 8457
{fmt_endf(endpoint)}{fmt_endf(0.0)}          0          0          6          1{mat:4d} 8457
{fmt_endf(rtyp)}{fmt_endf(0.0)}{fmt_endf(er_av)}{fmt_endf(0.0)}{fmt_endf(intensity)} 0.000000+0{mat:4d} 8457
                                                                    {mat:4d} 8  0
 0.000000+0 0.000000+0          0          0          0          0   0 0  0
"""
    
    # Add HEAD record at the beginning
    head = f" {fmt_endf(float(za))}{fmt_endf(awr)}          0          0          0          1{mat:4d} 8457\n"
    
    return head + endf_text


def test_styp_extraction(styp, styp_name, er_av_eV, za=92235):
    """Test energy extraction for a specific STYP type."""
    
    print(f"\n{'='*80}")
    print(f"Testing STYP={styp} ({styp_name})")
    print(f"{'='*80}")
    
    # Create test ENDF data
    endpoint_eV = er_av_eV * 1.5 if styp in [1, 2] else er_av_eV
    test_data = create_test_endf(za, styp, er_av_eV, endpoint=endpoint_eV)
    
    # Parse the data
    parser = ENDFNumericDecayParser()
    parser.load_text(test_data)
    
    if not parser._scan_to_mf_mt(8, 457):
        print(f"  ✗ ERROR: Could not find MF=8 MT=457 section")
        return False
    
    try:
        data = parser._parse_mf8_mt457()
    except Exception as e:
        print(f"  ✗ ERROR: Parsing failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Check results
    print(f"  Parsed ZA: {data['ZA']}")
    
    if "spectra" not in data or len(data["spectra"]) == 0:
        print(f"  ✗ ERROR: No spectra found")
        return False
    
    print(f"  Number of spectra: {len(data['spectra'])}")
    
    success = False
    for i, spec in enumerate(data["spectra"]):
        spec_styp = spec.get("STYP", -1)
        print(f"\n  Spectrum {i+1}: STYP={spec_styp}")
        
        if spec_styp != styp:
            print(f"    ✗ ERROR: Expected STYP={styp}, got STYP={spec_styp}")
            continue
        
        # Check ER_AV (mean energy)
        if "ER_AV" in spec:
            er_av = spec["ER_AV"]
            if isinstance(er_av, tuple):
                er_av_val = er_av[0]
                er_av_unc = er_av[1]
                print(f"    ER_AV: {er_av_val:.2f} ± {er_av_unc:.2f} eV")
            else:
                er_av_val = er_av
                print(f"    ER_AV: {er_av_val:.2f} eV")
            
            if abs(er_av_val - er_av_eV) < 1.0:
                print(f"    ✓ Mean energy CORRECT: {er_av_val:.2f} eV = {er_av_val/1000:.2f} keV")
                success = True
            else:
                print(f"    ✗ Mean energy WRONG: Expected {er_av_eV:.2f}, got {er_av_val:.2f}")
        else:
            print(f"    ✗ ERROR: No ER_AV field found")
        
        # Check FD (normalization)
        if "FD" in spec:
            fd = spec["FD"]
            if isinstance(fd, tuple):
                fd_val = fd[0]
                print(f"    FD (normalization): {fd_val:.2f}")
        
        # Check discrete transitions
        if "discrete" in spec and spec["discrete"]:
            print(f"    Discrete transitions: {len(spec['discrete'])}")
            
            for j, disc in enumerate(spec["discrete"][:3]):  # Show first 3
                print(f"      Transition {j+1}:")
                
                if "ER" in disc:
                    er = disc["ER"]
                    if isinstance(er, tuple):
                        er_val = er[0]
                        print(f"        ER (endpoint): {er_val:.2f} eV = {er_val/1000:.2f} keV")
                
                if "E_AVG" in disc:
                    e_avg = disc["E_AVG"]
                    if isinstance(e_avg, tuple):
                        e_avg_val = e_avg[0]
                        print(f"        E_AVG (average): {e_avg_val:.2f} eV = {e_avg_val/1000:.2f} keV")
                        
                        # Verify E_AVG matches input for beta spectra
                        if styp in [1, 2] and abs(e_avg_val - er_av_eV) < 1.0:
                            print(f"        ✓ Average energy in discrete matches ER_AV")
                
                if "IB" in disc:
                    ib = disc["IB"]
                    if isinstance(ib, tuple):
                        ib_val = ib[0]
                        print(f"        IB (intensity): {ib_val:.2f}%")
                
                if "RI" in disc:
                    ri = disc["RI"]
                    if isinstance(ri, tuple):
                        ri_val = ri[0]
                        print(f"        RI (intensity): {ri_val:.2f}%")
        else:
            print(f"    No discrete transitions")
    
    print(f"\n  {'✓ PASS' if success else '✗ FAIL'}: {styp_name}")
    return success


def main():
    """Test all STYP types."""
    
    print("="*80)
    print("COMPREHENSIVE STYP ENERGY EXTRACTION TEST")
    print("="*80)
    print("\nTesting energy extraction for all spectrum types (STYP)...")
    
    # Define test cases: (STYP, name, test_energy_eV)
    test_cases = [
        (0, "Gamma rays", 661657.0),           # 661.657 keV (Cs-137)
        (1, "Beta- particles", 301370.0),      # 301.37 keV (H-3)
        (2, "Beta+ particles", 633000.0),      # 633 keV (F-18)
        (4, "Alpha particles", 5486000.0),     # 5.486 MeV (Am-241)
        (8, "X-rays", 59541.0),                # 59.541 keV (Am-241 Np L X-ray)
        (9, "Auger electrons", 17750.0),       # 17.75 keV (typical Auger)
    ]
    
    results = {}
    
    for styp, name, energy in test_cases:
        success = test_styp_extraction(styp, name, energy)
        results[styp] = success
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    all_passed = True
    for styp, name, energy in test_cases:
        status = "✓ PASS" if results[styp] else "✗ FAIL"
        print(f"  STYP={styp} ({name:20s}): {status}")
        if not results[styp]:
            all_passed = False
    
    print("="*80)
    
    if all_passed:
        print("✓ ALL TESTS PASSED: Energy extraction works for all STYP types!")
    else:
        print("✗ SOME TESTS FAILED: Check output above for details")
    
    print("="*80)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
