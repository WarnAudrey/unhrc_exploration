#!/usr/bin/env python3
"""
Test alpha energy extraction with actual ENDF decay data structure.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from ENDFParsing import ENDFDataModule

# Simulate parsed JEFF data for Am-241 (alpha decay)
# This mimics what JEFF_ENDF_parser returns
am241_jeff_data = {
    "ZA": 95241,
    "LIS": 0,
    "T1/2": (1.3626e10, 0),  # ~432 years in seconds
    "modes": [
        {
            "RTYP": 4.0,  # Alpha decay
            "RFS": 0,
            "Q": (5637000, 0),  # 5.637 MeV Q-value
            "BR": (1.0, 0)  # 100% branching
        }
    ],
    "spectra": [
        {
            "STYP": 4,  # Alpha spectrum
            "ER_AV": (5486000, 0),  # 5.486 MeV average
            "FD": (1.0, 0),
            "discrete": [
                {
                    "ER": (5486000, 0),  # 5.486 MeV alpha group (84.8%)
                    "RTYP": 4.0,
                    "RI": (84.8, 0)
                },
                {
                    "ER": (5443000, 0),  # 5.443 MeV alpha group (13.1%)
                    "RTYP": 4.0,
                    "RI": (13.1, 0)
                }
            ]
        }
    ]
}

def test_alpha_energy_extraction():
    """Test that alpha energies are extracted and mapped correctly."""
    
    print("="*80)
    print("TESTING ALPHA ENERGY EXTRACTION")
    print("="*80)
    
    # Create DecayData object (internal class in ENDFParsing.py)
    from ENDFParsing import DecayData
    
    decay = DecayData(am241_jeff_data)
    
    print(f"\nNuclide: {decay.element}-{decay.parent_A}")
    print(f"Half-life: {decay.half_life:.2e} seconds (~432 years)")
    
    print(f"\nDecay modes:")
    for mode, br in decay.decay_modes.items():
        print(f"  {mode}: {br:.1f}%")
    
    print(f"\nAverage energies:")
    if decay.average_energies:
        for mode, energy in decay.average_energies.items():
            print(f"  {mode}: {energy:.0f} eV = {energy/1e6:.3f} MeV")
    else:
        print("  ⚠ WARNING: No average energies found!")
    
    print(f"\nEndpoint energies:")
    if decay.endpoint_energies:
        for mode, energy in decay.endpoint_energies.items():
            print(f"  {mode}: {energy:.0f} eV = {energy/1e6:.3f} MeV")
    else:
        print("  ⚠ WARNING: No endpoint energies found!")
    
    # Check results
    success = True
    
    if 'a' not in decay.decay_modes and 'α' not in decay.decay_modes:
        print("\n✗ FAIL: Alpha decay mode not found!")
        success = False
    else:
        print("\n✓ Alpha decay mode found")
    
    if not decay.average_energies:
        print("✗ FAIL: No average energies extracted!")
        success = False
    elif 'a' in decay.average_energies or 'α' in decay.average_energies:
        alpha_key = 'a' if 'a' in decay.average_energies else 'α'
        expected_energy = 5486000  # eV
        actual_energy = decay.average_energies[alpha_key]
        
        if abs(actual_energy - expected_energy) < 1000:
            print(f"✓ Alpha average energy correct: {actual_energy/1e6:.3f} MeV")
        else:
            print(f"✗ FAIL: Expected {expected_energy/1e6:.3f} MeV, got {actual_energy/1e6:.3f} MeV")
            success = False
    else:
        print("✗ FAIL: Alpha energy not mapped to decay mode!")
        success = False
    
    print("\n" + "="*80)
    if success:
        print("✅ SUCCESS: Alpha energies are being extracted!")
    else:
        print("✗ FAILURE: Alpha energy extraction has issues")
    print("="*80)
    
    return success


if __name__ == "__main__":
    success = test_alpha_energy_extraction()
    sys.exit(0 if success else 1)
