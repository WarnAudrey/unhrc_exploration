#!/usr/bin/env python3
"""
Analyze failed matches from ENDF-ENSDF level matching.

This script helps understand why matches failed and suggests improvements.
"""

# Sample failed matches from the user's output
failed_matches = [
    ("Be-7", "Li-7", 384.10),
    ("He-8", "Li-8", 980.80),
    ("C-10", "B-10", 718.40),
    ("Li-11", "Be-11", 320.00),
    ("Be-12", "B-12", 14.00),
    ("N-12", "C-12", 29.00),
    ("N-13", "C-13", 2220.00),
    ("O-13", "N-13", 7509.90),
    ("Be-14", "B-14", 14910.00),
    ("B-14", "C-14", 29.00),
    ("C-16", "N-16", 120.40),
    ("B-17", "C-17", 18690.00),
    ("C-17", "N-17", 1374.00),
    ("C-18", "N-18", 742.00),
    ("N-18", "O-18", 1982.00),
    ("C-19", "N-19", 8484.00),
    ("N-19", "O-19", 8421.00),
    ("C-20", "N-20", 14897.00),
    ("N-20", "O-20", 10216.00),
]

print("="*80)
print("FAILED MATCH ANALYSIS")
print("="*80)
print(f"Analyzing {len(failed_matches)} sample failed matches\n")

# Current tolerance settings
abs_tol_keV = 1.0      # Current absolute tolerance
hybrid_threshold_keV = 500.0  # Switch point

# Categorize failures
categories = {
    "Very Close (<20 keV)": [],
    "Close (20-100 keV)": [],
    "Moderate (100-500 keV)": [],
    "Large (500-1000 keV)": [],
    "Very Large (1-5 MeV)": [],
    "Extreme (>5 MeV)": []
}

for parent, daughter, diff_keV in failed_matches:
    if diff_keV < 20:
        categories["Very Close (<20 keV)"].append((parent, daughter, diff_keV))
    elif diff_keV < 100:
        categories["Close (20-100 keV)"].append((parent, daughter, diff_keV))
    elif diff_keV < 500:
        categories["Moderate (100-500 keV)"].append((parent, daughter, diff_keV))
    elif diff_keV < 1000:
        categories["Large (500-1000 keV)"].append((parent, daughter, diff_keV))
    elif diff_keV < 5000:
        categories["Very Large (1-5 MeV)"].append((parent, daughter, diff_keV))
    else:
        categories["Extreme (>5 MeV)"].append((parent, daughter, diff_keV))

# Print analysis
for category, matches in categories.items():
    if matches:
        print(f"\n{category}: {len(matches)} cases")
        print("-" * 80)
        for parent, daughter, diff in matches:
            print(f"  {parent:8s} → {daughter:8s}  Δ = {diff:8.2f} keV")

print("\n" + "="*80)
print("RECOMMENDATIONS")
print("="*80)

# Count how many would be recovered with different tolerances
tolerances = [5, 10, 20, 50, 100, 200, 500, 1000]
print("\nMatch recovery with different absolute tolerances:")
print("-" * 80)
for tol in tolerances:
    recovered = sum(1 for _, _, diff in failed_matches if diff <= tol)
    pct = 100 * recovered / len(failed_matches)
    print(f"  {tol:5d} keV: would recover {recovered:2d}/{len(failed_matches)} ({pct:5.1f}%) of these failures")

print("\n" + "="*80)
print("LIKELY CAUSES OF FAILURES")
print("="*80)

print("\n1. VERY CLOSE FAILURES (<20 keV):")
print("   - Likely measurement uncertainties")
print("   - Different evaluation rounds")
print("   - Recommendation: Increase absolute tolerance to 10-20 keV")

print("\n2. MODERATE FAILURES (100-500 keV):")
print("   - Possible decay to excited states not properly identified")
print("   - Q-value differences between databases")
print("   - May need manual investigation")

print("\n3. LARGE FAILURES (>500 keV):")
print("   - Likely decaying to excited states")
print("   - ENDF may have grouped multiple transitions")
print("   - ENSDF level data may be incomplete")

print("\n4. EXTREME FAILURES (>5 MeV):")
print("   - Possible systematic issues:")
print("     * Wrong decay mode identification")
print("     * Different Q-value conventions")
print("     * Missing nuclear structure data")

print("\n" + "="*80)
print("SUGGESTED NEXT STEPS")
print("="*80)

print("\n1. Quick Win: Increase absolute tolerance to 10-20 keV")
print("   → Would recover 'Very Close' failures")
print("   Command: python ENDFLevelMatching.py --abs-tol 20000")

print("\n2. Investigate Specific Cases:")
print("   → Manually check Be-12, N-12 (14-29 keV differences)")
print("   → Are these known evaluation differences?")

print("\n3. Check if Large Failures are Excited State Decays:")
print("   → Compare ENDF particle energies to ENSDF excited state levels")
print("   → May need multi-level matching capability")

print("\n4. Verify Q-values Match Between Databases:")
print("   → Extract Q_ground from both ENDF and ENSDF")
print("   → Look for systematic offsets")

print("\n5. Use Relative Tolerance for High-Energy States:")
print("   → Current hybrid threshold: 500 keV")
print("   → Above this, 0.1% relative tolerance applies")
print("   → For 10 MeV states: tolerance = 10 keV")

print("\n" + "="*80 + "\n")
