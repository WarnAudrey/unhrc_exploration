#!/usr/bin/env python3
"""
Code snippet to add placeholder detection to ENDFLevelMatcher.

This adds the hybrid strategy for handling ENDF placeholder data:
1. Detect very small energies (< 100 eV)
2. Replace with ENSDF Q_ground when available
3. Label clearly as "placeholder_replaced"
"""

# =============================================================================
# ADD THIS METHOD TO ENDFLevelMatcher CLASS
# =============================================================================

def _is_placeholder(self, energy_eV, intensity=None):
    """
    Detect if ENDF energy value is a placeholder for missing data.
    
    Characteristics of placeholders:
    - Exactly zero energy (physically impossible for decay)
    - Very small energies (< 100 eV = 0.1 keV)
      Most beta decays: > 10 keV
      Most alpha decays: > 1000 keV
    - Low energy + low intensity combinations
    
    Args:
        energy_eV: Particle energy in eV
        intensity: Optional branching ratio (%)
    
    Returns:
        bool: True if likely placeholder, False otherwise
    
    Examples:
        Li-11 B-: 9.1 eV → True (placeholder)
        H-3 B-:   18,570 eV → False (real data)
    """
    # Exact zero is always placeholder
    if energy_eV == 0:
        return True
    
    # Very small values (< 100 eV = 0.1 keV)
    # Real decays are typically >> 1 keV
    if energy_eV < 100:
        return True
    
    # Suspicious combination: low energy + low intensity
    # Real weak transitions usually have either reasonable E or I
    if intensity is not None:
        if energy_eV < 1e3 and intensity < 1.0:
            return True
    
    return False


# =============================================================================
# MODIFY __init__ TO ADD PLACEHOLDER TRACKING
# =============================================================================
# Add these lines after self.matched_decay_df = None

# Track placeholder statistics
self.placeholder_count = 0
self.placeholder_replaced = 0


# =============================================================================
# MODIFY match_levels() METHOD
# =============================================================================
# Insert this code block RIGHT AFTER getting endf_energy but BEFORE
# the line: verbose = idx < 3

# ---------------------------------------------------------------------
# Check for placeholder data (ENDF missing/uncertain values)
# ---------------------------------------------------------------------
intensity = row.get('Intensity', np.nan)

if not pd.isna(endf_energy) and self._is_placeholder(endf_energy, intensity):
    self.placeholder_count += 1
    
    # Verbose output for first few placeholders
    if verbose:
        print(f"\n  ⚠ Placeholder detected: {parent_name}")
        print(f"    ENDF energy: {endf_energy:.2e} eV (< 100 eV threshold)")
    
    # Try to use ENSDF Q_ground as replacement
    key = (parent_a, parent_z, decay_mode)
    
    if key in self.q_ground_lookup:
        # ENSDF data available - replace placeholder
        q_ground = self.q_ground_lookup[key]
        daughter_a, daughter_z = self._get_daughter_nucleus(parent_a, parent_z, decay_mode)
        daughter_elem = ATOMIC_SYMBOL.get(daughter_z, f'Z{daughter_z}')
        daughter_name = f"{daughter_elem}-{daughter_a}"
        
        if verbose:
            print(f"    → Replacing with ENSDF Q_ground: {q_ground/1e3:.2f} keV")
            print(f"    → Assuming decay to ground state (level 0)")
        
        # Create "match" using ENSDF data
        match = MatchResult(
            matched=True,
            parent_level=0.0,
            final_level=0.0,  # Assume ground state
            ensdf_energy=q_ground,
            endf_q_value=endf_energy,
            energy_diff=np.nan,  # No meaningful comparison
            rel_diff=np.nan,
            match_quality="placeholder_replaced",
            ambiguous=False,
            daughter_nuclide=daughter_name
        )
        
        self.placeholder_replaced += 1
        
        # Store in DataFrame
        endf_reset.at[idx, 'parent_level_matched'] = 0.0
        endf_reset.at[idx, 'final_level_matched'] = 0.0
        endf_reset.at[idx, 'match_quality'] = "placeholder_replaced"
        endf_reset.at[idx, 'daughter_nuclide'] = daughter_name
        matched_count += 1
        
    else:
        # No ENSDF data - can't replace placeholder
        daughter_a, daughter_z = self._get_daughter_nucleus(parent_a, parent_z, decay_mode)
        daughter_elem = ATOMIC_SYMBOL.get(daughter_z, f'Z{daughter_z}')
        daughter_name = f"{daughter_elem}-{daughter_a}"
        
        if verbose:
            print(f"    → No ENSDF data available for replacement")
        
        match = MatchResult(
            matched=False,
            parent_level=np.nan,
            final_level=np.nan,
            ensdf_energy=np.nan,
            endf_q_value=endf_energy,
            energy_diff=np.nan,
            rel_diff=np.nan,
            match_quality="placeholder_data",
            ambiguous=False,
            daughter_nuclide=daughter_name
        )
        
        # Store in DataFrame
        endf_reset.at[idx, 'match_quality'] = "placeholder_data"
        endf_reset.at[idx, 'daughter_nuclide'] = daughter_name
        self.unmatched_decays.append(row.to_dict())
    
    # Add to results and continue to next entry
    self.match_results.append(match)
    continue  # Skip normal matching logic

# ... rest of normal matching code continues here ...


# =============================================================================
# ADD PLACEHOLDER STATISTICS TO OUTPUT
# =============================================================================
# Add this section in match_levels() AFTER the existing statistics printing
# (after the "Failed matches that would pass..." section)

if self.placeholder_count > 0:
    print(f"\nPlaceholder data handling:")
    print(f"  ENDF placeholders detected:  {self.placeholder_count}")
    print(f"    Replaced with ENSDF:       {self.placeholder_replaced} "
          f"({100*self.placeholder_replaced/self.placeholder_count:.1f}%)")
    print(f"    No ENSDF available:        {self.placeholder_count - self.placeholder_replaced}")
    print(f"  (Placeholders: ENDF energies < 100 eV, likely missing data)")


# =============================================================================
# UPDATE THE QUALITY CATEGORIES IN STATISTICS
# =============================================================================
# Add these lines to the statistics section (after marginal, before no_ensdf)

replaced = sum(1 for m in self.match_results if m.match_quality == "placeholder_replaced")
placeholder_only = sum(1 for m in self.match_results if m.match_quality == "placeholder_data")

# Update the print statements:
print(f"  ✓ Marginal: {marginal}")
print(f"  ✓ Placeholder replaced: {replaced}")  # NEW
print(f"  ~ Assumed ground: {assumed}")
print(f"\nFailure breakdown:")
print(f"  ⚠ Placeholder only: {placeholder_only}")  # NEW
print(f"  ✗ No ENSDF data: {no_ensdf}")
print(f"  ✗ Energy mismatch: {failed}")


# =============================================================================
# SUMMARY: WHAT THIS ADDS
# =============================================================================
"""
NEW FEATURES:
1. Detects ENDF placeholder data (< 100 eV)
2. Replaces with ENSDF Q_ground when available
3. Labels as "placeholder_replaced" or "placeholder_data"
4. Reports statistics on placeholder handling

EXAMPLE OUTPUT:
  Placeholder data handling:
    ENDF placeholders detected:  482
      Replaced with ENSDF:       456 (94.6%)
      No ENSDF available:        26

NEW MATCH QUALITY CATEGORIES:
  - placeholder_replaced: ENDF was placeholder, used ENSDF Q_ground (assume level 0)
  - placeholder_data: ENDF was placeholder, no ENSDF available (failed)

EXPECTED IMPACT:
  - Match rate: +3-5% (capture placeholders with ENSDF data)
  - Data quality: Better than using placeholders
  - Traceability: Clear labeling of replaced values
"""
