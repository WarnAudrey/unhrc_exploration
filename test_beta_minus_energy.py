#!/usr/bin/env python3
"""
Test script to verify Beta- (STYP=1) energy extraction from ENDF files.
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

from JEFF_ENDF_parser import ENDFNumericDecayParser

# Sample ENDF data for H-3 (tritium) beta- decay
# This is extracted from the user's example
sample_endf_h3 = """
 $Rev:: 1450     $  $Date:: 2018-01-17#$                             1 0  0
 1.000000+0 1.000000+0         -1          0          0          0   1 1451
 0.000000+0 1.000000+0          0          0          0          6   1 1451
 0.000000+0 0.000000+0          0          0          4          8   1 1451
 0.000000+0 0.000000+0          0          0         32          2   1 1451
  0-Nn-  1  BNL        EVAL-NOV05 Conversion from ENSDF              1 1451
 /ENSDF/              DIST-FEB18                       20111222      1 1451
----ENDF/B-VIII.0     Material    1                                  1 1451
-----RADIOACTIVE DECAY DATA                                          1 1451
------ENDF-6 FORMAT                                                  1 1451
*********************** Begin Description ***********************    1 1451
**         ENDF/B-VII.1 RADIOACTIVE DECAY DATA FILE            **    1 1451
**         Produced at the NNDC from the ENSDF database        **    1 1451
**               Translated into ENDF format by:               **    1 1451
**    T.D. Johnson, E.A. McCutchan and A.A. Sonzogni, 2011     **    1 1451
*****************************************************************    1 1451
ENSDF evaluation authors: BALRAJ SINGH                               1 1451
Parent Excitation Energy: 0.0                                        1 1451
Parent Spin & Parity: 1/2+                                           1 1451
Parent half-life: 613.9 S 6                                          1 1451
Decay Mode: B-                                                       1 1451
************************ Energy  Balance ************************    1 1451
Mean Gamma Energy:      0.000E0 +- 0.000E0 keV                       1 1451
Mean X-Ray+511 Energy:  0.000E0 +- 0.000E0 keV                       1 1451
Mean CE+Auger Energy:   0.000E0 +- 0.000E0 keV                       1 1451
Mean B- Energy:         3.014E2 +- 0.000E0 keV                       1 1451
Mean B+ Energy:         0.000E0 +- 0.000E0 keV                       1 1451
Mean Neutrino Energy:   4.810E2 +- 1.000E-3 keV                      1 1451
Mean Neutron Energy:    0.000E0 +- 0.000E0 keV                       1 1451
Mean Proton Energy:     0.000E0 +- 0.000E0 keV                       1 1451
Mean Alpha Energy:      0.000E0 +- 0.000E0 keV                       1 1451
Mean Recoil Energy:     0.000E0 +- 0.000E0 keV                       1 1451
Sum Mean Energies:      7.823E2 +- 1.000E-3 keV                      1 1451
Q effective:            7.823E2 keV                                  1 1451
Missing Energy:         0.000E0 keV                                  1 1451
Deviation:              0.000E0 %                                    1 1451
************************ End Description ************************    1 1451
                                1        451         38          0   1 1451
                                8        457          9          0   1 1451
 0.000000+0 0.000000+0          0          0          0          0   1 1  0
                                                                     1 0  0
 1.000000+0 1.000000+0          0          0          0          1   1 8457
 6.139000+2 6.000000-1          0          0          6          0   1 8457
 3.013700+5 0.000000+0 0.000000+0 0.000000+0 0.000000+0 0.000000+0   1 8457
 5.000000-1 1.000000+0          0          0          6          1   1 8457
 1.000000+0 0.000000+0 7.823470+5 1.000000+0 1.000000+0 0.000000+0   1 8457
 0.000000+0 1.000000+0          0          0          6          1   1 8457
 1.000000+0 0.000000+0 3.013700+5 0.000000+0 0.000000+0 0.000000+0   1 8457
 7.823470+5 1.000000+0          0          0          6          0   1 8457
 1.000000+0 1.000000+0 1.000000+0 0.000000+0 0.000000+0 0.000000+0   1 8457
                                                                     1 8  0
                                                                     1 0  0
 0.000000+0 0.000000+0          0          0          0          0   0 0  0
                                                                    -1 0  0
"""

def test_beta_minus_extraction():
    """Test that Beta- (STYP=1) energy extraction works correctly."""
    
    print("=" * 80)
    print("TESTING BETA- (STYP=1) ENERGY EXTRACTION")
    print("=" * 80)
    
    # Parse the sample data
    parser = ENDFNumericDecayParser()
    parser.load_text(sample_endf_h3)
    
    # Scan to MF=8 MT=457 section
    if not parser._scan_to_mf_mt(8, 457):
        print("ERROR: Could not find MF=8 MT=457 section!")
        return False
    
    # Parse the decay data
    try:
        data = parser._parse_mf8_mt457()
    except Exception as e:
        print(f"ERROR: Failed to parse decay data: {e}")
        return False
    
    print(f"\nParsed nuclide: ZA={data['ZA']}, LIS={data['LIS']}")
    print(f"Half-life: {data['T1/2'][0]:.1f} seconds")
    
    # Check for spectra
    if "spectra" not in data or len(data["spectra"]) == 0:
        print("\nERROR: No spectra found in parsed data!")
        return False
    
    print(f"\nNumber of spectra: {len(data['spectra'])}")
    
    # Look for Beta- spectrum (STYP=1)
    beta_minus_found = False
    for i, spec in enumerate(data["spectra"]):
        styp = spec.get("STYP", -1)
        print(f"\nSpectrum {i+1}:")
        print(f"  STYP: {styp}", end="")
        
        if styp == 0:
            print(" (Gamma)")
        elif styp == 1:
            print(" (Beta-) ✓")
            beta_minus_found = True
        elif styp == 2:
            print(" (Beta+)")
        elif styp == 4:
            print(" (Alpha)")
        else:
            print(f" (Unknown)")
        
        # Check for mean energy (ER_AV)
        if "ER_AV" in spec:
            er_av = spec["ER_AV"][0] if isinstance(spec["ER_AV"], tuple) else spec["ER_AV"]
            print(f"  Mean Energy (ER_AV): {er_av:.2f} eV = {er_av/1000:.2f} keV")
            
            if styp == 1:
                expected_keV = 301.37
                actual_keV = er_av / 1000
                if abs(actual_keV - expected_keV) < 1.0:
                    print(f"  ✓ CORRECT! Matches expected {expected_keV:.2f} keV")
                else:
                    print(f"  ✗ ERROR! Expected {expected_keV:.2f} keV, got {actual_keV:.2f} keV")
        
        # Check for discrete transitions
        if "discrete" in spec and spec["discrete"]:
            print(f"  Discrete transitions: {len(spec['discrete'])}")
            for j, disc in enumerate(spec["discrete"]):
                if "ER" in disc:
                    er = disc["ER"][0] if isinstance(disc["ER"], tuple) else disc["ER"]
                    print(f"    Transition {j+1}: ER = {er:.2f} eV")
                if "E_AVG" in disc:
                    e_avg = disc["E_AVG"][0] if isinstance(disc["E_AVG"], tuple) else disc["E_AVG"]
                    print(f"                      E_AVG = {e_avg:.2f} eV = {e_avg/1000:.2f} keV")
                if "IB" in disc:
                    ib = disc["IB"][0] if isinstance(disc["IB"], tuple) else disc["IB"]
                    print(f"                      IB = {ib:.2f}%")
    
    print("\n" + "=" * 80)
    if beta_minus_found:
        print("✓ SUCCESS: Beta- (STYP=1) spectrum found and energies extracted!")
    else:
        print("✗ FAILURE: Beta- (STYP=1) spectrum not found!")
    print("=" * 80)
    
    return beta_minus_found


if __name__ == "__main__":
    success = test_beta_minus_extraction()
    sys.exit(0 if success else 1)
