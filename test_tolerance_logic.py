#!/usr/bin/env python3
"""
Test script to demonstrate the difference between old and new tolerance logic.

This script compares:
1. OLD: tolerance = energy_a * rel_tol
2. NEW: tolerance = rel_tol * max(abs(energy_a), abs(energy_b))  [math.isclose convention]
"""

import math

def old_tolerance_check(energy_a, energy_b, rel_tol, abs_tol):
    """Old implementation - only uses energy_a for relative tolerance."""
    abs_diff = abs(energy_a - energy_b)
    tolerance = max(energy_a * rel_tol, abs_tol)
    return abs_diff <= tolerance, abs_diff, tolerance

def new_tolerance_check(energy_a, energy_b, rel_tol, abs_tol):
    """New implementation - uses max(|a|, |b|) following math.isclose()."""
    abs_diff = abs(energy_a - energy_b)
    max_energy = max(abs(energy_a), abs(energy_b))
    tolerance = max(rel_tol * max_energy, abs_tol)
    return abs_diff <= tolerance, abs_diff, tolerance

def test_cases():
    """Test various energy comparison scenarios."""
    
    # Default parameters (matching the code)
    rel_tol = 1e-3  # 0.1%
    abs_tol = 1e3   # 1 keV
    
    test_scenarios = [
        # (ensdf_energy, endf_energy, description)
        (2430000, 2425000, "Similar high energies (2.43 MeV vs 2.425 MeV)"),
        (100000, 99500, "Similar medium energies (100 keV vs 99.5 keV)"),
        (1000, 900, "Low energies (1 keV vs 0.9 keV)"),
        (500, 600, "Very low energies (0.5 keV vs 0.6 keV)"),
        (1000000, 999000, "1% difference (1 MeV vs 999 keV)"),
        (10000, 5000, "Large relative difference (10 keV vs 5 keV)"),
        (0, 500, "Zero vs non-zero (0 vs 0.5 keV)"),
        (100, 0, "Non-zero vs zero (0.1 keV vs 0)"),
    ]
    
    print("="*100)
    print("TOLERANCE LOGIC COMPARISON")
    print("="*100)
    print(f"Configuration: rel_tol = {rel_tol*100:.3f}%, abs_tol = {abs_tol/1e3:.1f} keV\n")
    
    for ensdf_energy, endf_energy, description in test_scenarios:
        print(f"\n{description}")
        print(f"  ENSDF energy: {ensdf_energy/1e3:10.3f} keV")
        print(f"  ENDF energy:  {endf_energy/1e3:10.3f} keV")
        print(f"  Difference:   {abs(ensdf_energy - endf_energy)/1e3:10.3f} keV")
        
        # Old logic
        old_match, old_diff, old_tol = old_tolerance_check(ensdf_energy, endf_energy, rel_tol, abs_tol)
        print(f"\n  OLD Logic (only uses ENSDF energy):")
        print(f"    Tolerance:  {old_tol/1e3:10.3f} keV")
        print(f"    Match:      {'✓ YES' if old_match else '✗ NO'}")
        
        # New logic
        new_match, new_diff, new_tol = new_tolerance_check(ensdf_energy, endf_energy, rel_tol, abs_tol)
        print(f"\n  NEW Logic (uses max of both energies - math.isclose):")
        print(f"    Tolerance:  {new_tol/1e3:10.3f} keV")
        print(f"    Match:      {'✓ YES' if new_match else '✗ NO'}")
        
        # Compare with math.isclose
        math_match = math.isclose(ensdf_energy, endf_energy, rel_tol=rel_tol, abs_tol=abs_tol)
        print(f"\n  Python math.isclose():")
        print(f"    Match:      {'✓ YES' if math_match else '✗ NO'}")
        
        # Verify consistency
        if new_match != math_match:
            print(f"\n  ⚠️  WARNING: New logic doesn't match math.isclose()!")
        
        # Highlight differences
        if old_match != new_match:
            print(f"\n  📌 DIFFERENT RESULTS: Old={old_match}, New={new_match}")
        
        print("-"*100)
    
    print("\n" + "="*100)
    print("SUMMARY")
    print("="*100)
    print("The NEW logic correctly follows Python's math.isclose() convention.")
    print("Key advantages:")
    print("  1. Symmetric: isclose(a, b) == isclose(b, a)")
    print("  2. Robust: Handles edge cases (near-zero, large differences)")
    print("  3. Standard: Matches Python conventions")
    print("="*100 + "\n")

if __name__ == "__main__":
    test_cases()
