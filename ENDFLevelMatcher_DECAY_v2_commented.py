#!/usr/bin/env python3
"""
ENDF-ENSDF Level Matching Tool

PURPOSE:
--------
Matches ENDF decay transitions to ENSDF by comparing particle energies.
Enriches ENDF data with detailed level information from ENSDF.

DATABASES:
----------
- ENDF (Evaluated Nuclear Data File): Decay data library
  - Coverage: 4,802 decay transitions
  - Strategy: Representative transition per decay mode (one entry per parent/mode)
  - Contains: Particle energies (endpoint/average), branching ratios, half-lives
  - Missing: Daughter level information (final_level mostly 0)

- ENSDF (Evaluated Nuclear Structure Data File): Nuclear structure + decay database
  - Coverage: 28,498 decay transitions
  - Strategy: Complete decay schemes (all branches to all daughter levels)
  - Contains: Complete level schemes with all decay branches
  - **Key Finding**: ALL entries have parentLevel=0 (only ground state parent decays)
    → This is NORMAL - excited states decay via gamma (fast), not beta/alpha (slow)
    → Only rare long-lived isomers would have parentLevel>0

WHAT THIS TOOL DOES:
--------------------
**Problem**: ENDF entries mostly have final_level=0 (missing daughter level detail)
**Solution**: Match ENDF particle energies to ENSDF to find which daughter level is populated

Simple Approach - Direct Energy Matching:
  ENDF:  Li-9 B- decay, Particle Energy = 13,606 keV, final_level = 0 (unknown)
  ENSDF: Li-9 B- decay options:
         → Be-9 level 0, Particle Energy = 13,610 keV
         → Be-9 level 1, Particle Energy = 11,180 keV
         → Be-9 level 2, Particle Energy = 10,830 keV
  Match:  13,606 keV ≈ 13,610 keV (difference = 4 keV < 20 keV tolerance)
  Result: final_level = 0 (decay populates Be-9 ground state)

The key insight: ENSDF already provides particle energies for each transition.
We don't need to calculate anything - just compare ENDF energy to ENSDF energies!

MATCHING ALGORITHM:
-------------------
1. Load both databases
   - ENDF: 4,802 transitions with particle energies
   - ENSDF: 28,498 transitions with particle energies + level information

2. Build lookup table from ENSDF:
   - Group by (A, Z, decay_mode)
   - Store all transitions with their energies and levels
   
3. For each ENDF entry:
   - Look up all ENSDF transitions for same (A, Z, decay_mode)
   - Compare ENDF particle energy to each ENSDF particle energy
   - Find closest match within tolerance
   - Copy the final_level from that ENSDF transition
   
4. Save enriched ENDF with updated level assignments

Tolerances (configurable):
   - Absolute: 20 keV (for low energies)
   - Relative: 1% (for high energies)
   - Hybrid: Use absolute <500 keV, relative >500 keV (default)

IMPORTANT NOTES:
----------------
- **parentLevel stays 0**: ENSDF only contains ground state decays (parentLevel=0)
  → Physical: Excited states decay via gamma before beta/alpha decay occurs
  → If you see parentLevel=0 everywhere in output, this is CORRECT
  
- **final_level DOES update**: This is the key enrichment (e.g., 0 → 1, 2, 3)
  → Shows which daughter level is populated by the decay
  → Enables gamma cascade reconstruction
  
- **Not all transitions match**: 
  → 73.6% match rate achieved (3,533 / 4,802)
  → Failures due to: no ENSDF data, energy mismatch, or assumed ground states

OUTPUT:
-------
- Main file: DECAY_matched.ascii (ENDF format with updated levels)
- Diagnostics: DECAY_matched_diagnostics.ascii (match quality information)

AUTHOR: [Generated via conversation with user]
DATE: 2025-11-26
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
import warnings
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

# =============================================================================
# DATA STRUCTURES
# =============================================================================

class MatchStrategy(Enum):
    """
    Energy matching tolerance strategies.
    
    ABSOLUTE: Use fixed energy difference (e.g., 20 keV)
    RELATIVE: Use percentage of energy (e.g., 1%)
    HYBRID: Use absolute below threshold, relative above
    """
    ABSOLUTE = "absolute"
    RELATIVE = "relative"
    HYBRID = "hybrid"


@dataclass
class MatchResult:
    """
    Result of matching a single ENDF transition to ENSDF.
    
    Attributes:
        matched: bool - Was a match found?
        parent_level: float - Matched parent level number from ENSDF
        final_level: float - Matched daughter level number from ENSDF
        ensdf_energy: float - Particle energy from ENSDF (eV)
        endf_q_value: float - Particle energy from ENDF (eV)
        energy_diff: float - Absolute energy difference (eV)
        rel_diff: float - Relative energy difference (fraction)
        match_quality: str - Quality descriptor (exact/good/acceptable/marginal/failed)
        ambiguous: bool - Multiple matches within tolerance?
        daughter_nuclide: str - Daughter nucleus name (e.g., "Li-8")
    """
    matched: bool
    parent_level: float  # Matched parent level
    final_level: float   # Matched daughter level
    ensdf_energy: float
    endf_q_value: float
    energy_diff: float
    rel_diff: float
    match_quality: str
    ambiguous: bool
    daughter_nuclide: str


@dataclass
class MatchStatistics:
    """
    Aggregate statistics for entire matching run.
    """
    total_decays: int
    matched: int
    unmatched: int
    ambiguous: int
    exact_matches: int
    good_matches: int
    marginal_matches: int
    success_rate: float


# Element symbols for atomic number Z
ATOMIC_SYMBOL = {
    0: 'n', 1: 'H', 2: 'He', 3: 'Li', 4: 'Be', 5: 'B', 6: 'C', 7: 'N', 8: 'O', 9: 'F', 10: 'Ne',
    11: 'Na', 12: 'Mg', 13: 'Al', 14: 'Si', 15: 'P', 16: 'S', 17: 'Cl', 18: 'Ar', 19: 'K', 20: 'Ca',
    21: 'Sc', 22: 'Ti', 23: 'V', 24: 'Cr', 25: 'Mn', 26: 'Fe', 27: 'Co', 28: 'Ni', 29: 'Cu', 30: 'Zn',
    31: 'Ga', 32: 'Ge', 33: 'As', 34: 'Se', 35: 'Br', 36: 'Kr', 37: 'Rb', 38: 'Sr', 39: 'Y', 40: 'Zr',
    41: 'Nb', 42: 'Mo', 43: 'Tc', 44: 'Ru', 45: 'Rh', 46: 'Pd', 47: 'Ag', 48: 'Cd', 49: 'In', 50: 'Sn',
    51: 'Sb', 52: 'Te', 53: 'I', 54: 'Xe', 55: 'Cs', 56: 'Ba', 57: 'La', 58: 'Ce', 59: 'Pr', 60: 'Nd',
    61: 'Pm', 62: 'Sm', 63: 'Eu', 64: 'Gd', 65: 'Tb', 66: 'Dy', 67: 'Ho', 68: 'Er', 69: 'Tm', 70: 'Yb',
    71: 'Lu', 72: 'Hf', 73: 'Ta', 74: 'W', 75: 'Re', 76: 'Os', 77: 'Ir', 78: 'Pt', 79: 'Au', 80: 'Hg',
    81: 'Tl', 82: 'Pb', 83: 'Bi', 84: 'Po', 85: 'At', 86: 'Rn', 87: 'Fr', 88: 'Ra', 89: 'Ac', 90: 'Th',
    91: 'Pa', 92: 'U', 93: 'Np', 94: 'Pu', 95: 'Am', 96: 'Cm', 97: 'Bk', 98: 'Cf', 99: 'Es', 100: 'Fm'
}


# =============================================================================
# MAIN MATCHER CLASS
# =============================================================================

class ENDFLevelMatcherDECAY:
    """
    Main class for matching ENDF decay data to ENSDF level information.
    
    Workflow:
    ---------
    1. Initialize: Load both databases
    2. Build lookup: Index all ENSDF transitions by (A, Z, decay_mode)
    3. Match: For each ENDF entry, find best matching ENSDF transition
    4. Save: Write enriched ENDF data with updated level information
    
    Key Attributes:
    ---------------
    endf_decay_df: DataFrame with ENDF decay transitions
    ensdf_decay_df: DataFrame with ENSDF transitions (includes level info)
    transition_lookup: Dict mapping (A,Z,mode) → list of transitions
    q_ground_lookup: Dict mapping (A,Z,mode) → maximum particle energy
    match_results: List of MatchResult objects for all transitions
    """
    
    def __init__(self, endf_decay_path, ensdf_decay_path):
        """
        Initialize matcher and load databases.
        
        Args:
            endf_decay_path: Path to ENDF DECAY.ascii file
            ensdf_decay_path: Path to ENSDF DECAY.ascii file
        """
        self.endf_decay_path = Path(endf_decay_path)
        self.ensdf_decay_path = Path(ensdf_decay_path)
        
        # Default tolerances (energies in eV)
        self.absolute_tol = 2e4  # 20 keV
        self.relative_tol = 1e-2  # 1%
        self.strategy = MatchStrategy.HYBRID
        self.hybrid_threshold = 5e5  # 500 keV - use absolute below, relative above
        self.relaxed_factor = 5.0  # Allow 5x tolerance for "marginal" matches
        
        # Storage for results
        self.match_results = []
        self.unmatched_decays = []
        self.endf_decay_df = None
        self.ensdf_decay_df = None
        self.matched_decay_df = None
        
        # Load data and build lookups
        self._load_decay_files()
        self._build_ensdf_lookup()
    
    def _load_decay_files(self):
        """
        Load ENDF and ENSDF decay data files.
        
        ENDF Format:
        -----------
        Space-separated ASCII with MultiIndex:
        A Z parentLevel decay_mode final_level  Parent Endpoint_energy Average_energy Intensity
        1 0 0.0000e+00  B-         0.0000e+00   n-1    7.817000e+05   3.013700e+05   1.000000e+02
        
        ENSDF Format:
        ------------
        Similar to ENDF but with units:
        A Z parentLevel decay_mode final_level  Endpoint_energy Average_energy   Intensity
        1 0 0           B-         0.0          7.823e+02 keV   3.014e+02 keV   1.000e+02 %
        
        Note: ENSDF energies have units (keV, %) that must be parsed and converted
        """
        print("\n" + "="*70)
        print("LOADING DECAY FILES")
        print("="*70)
        
        # -------------------------
        # Load ENDF (straightforward - no units)
        # -------------------------
        print(f"Loading ENDF: {self.endf_decay_path}")
        self.endf_decay_df = pd.read_csv(
            self.endf_decay_path, 
            sep=r'\s+',  # Whitespace-separated
            comment='#',  # Skip comment lines
            index_col=[0, 1, 2, 3, 4],  # MultiIndex: A, Z, parentLevel, decay_mode, final_level
            engine='python'
        )
        print(f"  Index names: {self.endf_decay_df.index.names}")
        print(f"  Columns: {list(self.endf_decay_df.columns)}")
        print(f"  ENDF entries: {len(self.endf_decay_df)}")
        
        # -------------------------
        # Load ENSDF (complex - has units that must be stripped)
        # -------------------------
        print(f"\nLoading ENSDF: {self.ensdf_decay_path}")
        
        # Read file line by line
        lines = []
        with open(self.ensdf_decay_path, 'r') as f:
            for line in f:
                if line.strip() and not line.strip().startswith('#'):
                    lines.append(line)
        
        # Parse each line, handling units
        processed_data = []
        for line in lines:
            parts = line.split()
            if len(parts) >= 5:
                # Try to parse index columns (A, Z, parentLevel, decay_mode, final_level)
                try:
                    a = int(parts[0])
                    z = int(parts[1])
                    parent_level = float(parts[2])
                    decay_mode = parts[3]
                    final_level = float(parts[4])
                except ValueError:
                    # Header line (starts with letters) - skip it
                    continue
                
                # Parse data columns with units
                # Format: value unit value unit value unit
                # Columns: Endpoint_energy, Average_energy, Intensity
                endpoint = np.nan
                average = np.nan
                intensity = np.nan
                
                remaining = parts[5:]  # Data after index
                col_idx = 0  # Track which column (0=Endpoint, 1=Average, 2=Intensity)
                
                i = 0
                while i < len(remaining):
                    try:
                        val = float(remaining[i])
                        # Next item should be the unit
                        if i + 1 < len(remaining):
                            unit = remaining[i + 1]
                            if unit == 'keV':
                                # Convert keV to eV for consistency with ENDF
                                val = val * 1e3
                                if col_idx == 0:
                                    endpoint = val
                                    col_idx = 1
                                elif col_idx == 1:
                                    average = val
                                    col_idx = 2
                                i += 2
                            elif unit == '%':
                                intensity = val
                                i += 2
                            else:
                                i += 1
                        else:
                            i += 1
                    except ValueError:
                        i += 1
                
                processed_data.append({
                    'A': a,
                    'Z': z,
                    'parentLevel': parent_level,
                    'decay_mode': decay_mode,
                    'final_level': final_level,
                    'Endpoint_energy': endpoint,
                    'Average_energy': average,
                    'Intensity': intensity
                })
        
        # Convert to DataFrame with same structure as ENDF
        self.ensdf_decay_df = pd.DataFrame(processed_data)
        self.ensdf_decay_df = self.ensdf_decay_df.set_index(
            ['A', 'Z', 'parentLevel', 'decay_mode', 'final_level']
        )
        
        print(f"  Index names: {self.ensdf_decay_df.index.names}")
        print(f"  Columns: {list(self.ensdf_decay_df.columns)}")
        print(f"  ENSDF entries: {len(self.ensdf_decay_df)}")
        print("="*70 + "\n")
    
    def _get_daughter_nucleus(self, parent_a, parent_z, decay_mode):
        """
        Calculate daughter nucleus (A, Z) from parent and decay mode.
        
        Decay mode nomenclature:
        ------------------------
        B- : Beta minus (n → p + e- + ν̄)  → Z+1, A same
        B+ : Beta plus / positron (p → n + e+ + ν) → Z-1, A same
        EC : Electron capture (p + e- → n + ν) → Z-1, A same
        a  : Alpha (lose He-4) → Z-2, A-4
        n  : Neutron emission → Z same, A-1
        p  : Proton emission → Z-1, A-1
        
        Complex modes:
        B-n : Beta then neutron → Z+1, A-1
        B-a : Beta then alpha → Z-1, A-4
        etc.
        
        Args:
            parent_a: Mass number of parent
            parent_z: Atomic number of parent
            decay_mode: Decay mode string (e.g., "B-", "EC", "B-n")
        
        Returns:
            Tuple[int, int]: (daughter_a, daughter_z)
        """
        mode = str(decay_mode).lower()
        
        # Alpha decay
        if mode.startswith('a'):
            return (parent_a - 4, parent_z - 2)
        
        # Beta minus (and variants)
        elif mode.startswith('b-'):
            n_count = mode.count('n')
            if '2n' in mode:
                n_count += 1
            if '3n' in mode:
                n_count += 2
            # B-a: beta then alpha
            if 'a' in mode:
                return (parent_a - 4 - n_count, parent_z - 1)
            # B-n: beta then neutron(s)
            return (parent_a - n_count, parent_z + 1)
        
        # Beta plus / Electron capture
        elif mode.startswith('b+') or mode.startswith('ec'):
            p_count = mode.count('p')
            if '2p' in mode:
                p_count += 1
            # B+a or ECa: then alpha
            if 'a' in mode:
                return (parent_a - 4 - p_count, parent_z - 2 - p_count)
            return (parent_a - p_count, parent_z - 1)
        
        else:
            warnings.warn(f"Unknown decay mode: {decay_mode}")
            return (parent_a, parent_z)
    
    def _build_ensdf_lookup(self):
        """
        Build lookup table of all ENSDF transitions.
        
        Purpose:
        --------
        Create fast lookup structure: (parent_A, Z, decay_mode) → list of transitions
        Each transition contains: parent_level, daughter_level, particle_energy
        
        Also builds Q_ground lookup: (parent_A, Z, decay_mode) → maximum particle energy
        Q_ground is the ground-to-ground transition energy (parent_level=0, daughter_level=0)
        
        Lookups Created:
        ----------------
        self.transition_lookup: Dict[(A,Z,mode)] → [
            {'parent_level': 0, 'daughter_level': 0, 'particle_energy': 3508000},
            {'parent_level': 0, 'daughter_level': 1, 'particle_energy': 2500000},
            ...
        ]
        
        self.q_ground_lookup: Dict[(A,Z,mode)] → max_particle_energy (eV)
        
        Fallback:
        ---------
        If Q_ground not in ENSDF, use ENDF's maximum energy as estimate
        """
        print("Building ENSDF transition lookup...")
        print("  Cataloging all transitions with (parent_level, daughter_level, energy)...")
        
        ensdf_reset = self.ensdf_decay_df.reset_index()
        
        self.transition_lookup = {}
        self.q_ground_lookup = {}
        
        # -------------------------
        # Step 1: Catalog all ENSDF transitions
        # -------------------------
        for idx, row in ensdf_reset.iterrows():
            parent_a = int(row['A'])
            parent_z = int(row['Z'])
            parent_level = float(row['parentLevel'])
            decay_mode = str(row['decay_mode'])
            daughter_level = float(row['final_level'])
            
            # Get particle energy (prefer endpoint, fallback to average)
            endpoint = row.get('Endpoint_energy', np.nan)
            average = row.get('Average_energy', np.nan)
            particle_energy = endpoint if not pd.isna(endpoint) else average
            
            if pd.isna(particle_energy):
                continue  # Skip entries without energy data
            
            # Key: unique parent + decay mode
            key = (parent_a, parent_z, decay_mode)
            
            # Add to transition list
            if key not in self.transition_lookup:
                self.transition_lookup[key] = []
            
            self.transition_lookup[key].append({
                'parent_level': parent_level,
                'daughter_level': daughter_level,
                'particle_energy': particle_energy
            })
            
            # Track Q_ground (ground to ground transition energy)
            if parent_level == 0 and daughter_level == 0:
                if key not in self.q_ground_lookup:
                    self.q_ground_lookup[key] = particle_energy
                else:
                    # Take maximum (most energetic ground-to-ground transition)
                    self.q_ground_lookup[key] = max(self.q_ground_lookup[key], particle_energy)
        
        total_parents = len(self.transition_lookup)
        total_transitions = sum(len(v) for v in self.transition_lookup.values())
        print(f"    Found {total_transitions} transitions for {total_parents} parent nuclei")
        print(f"    Q_ground available for {len(self.q_ground_lookup)} parents")
        
        # -------------------------
        # Step 2: Add Q_ground from ENDF for missing parents
        # -------------------------
        # Some parents exist in ENDF but not in ENSDF
        # Use ENDF's maximum energy as estimated Q_ground
        print("  Adding Q_ground from ENDF for missing parents...")
        endf_reset = self.endf_decay_df.reset_index()
        
        added = 0
        for idx, row in endf_reset.iterrows():
            parent_a = int(row['A'])
            parent_z = int(row['Z'])
            parent_level = float(row['parentLevel'])
            decay_mode = str(row['decay_mode'])
            
            # Only use ground state entries
            if parent_level != 0:
                continue
            
            key = (parent_a, parent_z, decay_mode)
            
            # Skip if already have Q_ground from ENSDF
            if key in self.q_ground_lookup:
                continue
            
            # Get ENDF energy
            endpoint = row.get('Endpoint_energy', np.nan)
            average = row.get('Average_energy', np.nan)
            energy = endpoint if not pd.isna(endpoint) else average
            
            if pd.isna(energy) or energy <= 0:
                continue
            
            # Use as estimated Q_ground
            self.q_ground_lookup[key] = energy
            added += 1
        
        print(f"    Added {added} Q_ground values from ENDF")
        print(f"    Total Q_ground available: {len(self.q_ground_lookup)}")
        print("  Lookup complete!\n")
    
    def set_tolerances(self, absolute_tol=None, relative_tol=None, 
                      strategy=None, hybrid_threshold=None, 
                      relaxed_factor=None):
        """
        Configure energy matching tolerances.
        
        Args:
            absolute_tol: Absolute energy difference tolerance (eV)
            relative_tol: Relative energy difference tolerance (fraction)
            strategy: "absolute", "relative", or "hybrid"
            hybrid_threshold: Energy threshold for hybrid strategy (eV)
            relaxed_factor: Factor for "marginal" matches (multiplies tolerance)
        """
        if absolute_tol is not None:
            self.absolute_tol = absolute_tol
        if relative_tol is not None:
            self.relative_tol = relative_tol
        if strategy is not None:
            strategy_map = {
                "absolute": MatchStrategy.ABSOLUTE,
                "relative": MatchStrategy.RELATIVE,
                "hybrid": MatchStrategy.HYBRID
            }
            self.strategy = strategy_map[strategy.lower()]
        if hybrid_threshold is not None:
            self.hybrid_threshold = hybrid_threshold
        if relaxed_factor is not None:
            self.relaxed_factor = relaxed_factor
    
    def _find_matching_transition(self, parent_a, parent_z, parent_level, 
                                  decay_mode, endf_particle_energy, parent_name, verbose=False):
        """
        Find best matching ENSDF transition for an ENDF entry.
        
        Matching Strategy:
        ------------------
        1. Look up all ENSDF transitions for this (A, Z, decay_mode)
        2. Compare ENDF particle energy to each ENSDF particle energy
        3. Find transition(s) within tolerance
        4. Return best match (smallest energy difference)
        5. If no match, try relaxed tolerance (5x normal)
        6. If still no match, return failure
        
        Returns BOTH parent_level and daughter_level from matched transition.
        
        Special Cases:
        --------------
        - No ENSDF transitions: Try to match to Q_ground (ground→ground)
        - Multiple matches: Flag as "ambiguous" and return best
        - No match: Return "failed" with closest transition info
        
        Args:
            parent_a: Parent mass number
            parent_z: Parent atomic number
            parent_level: Parent level (usually 0)
            decay_mode: Decay mode string
            endf_particle_energy: Particle energy from ENDF (eV)
            parent_name: Parent nuclide name (for logging)
            verbose: Print detailed matching info?
        
        Returns:
            MatchResult object with match status and level information
        """
        # Calculate daughter nucleus
        daughter_a, daughter_z = self._get_daughter_nucleus(parent_a, parent_z, decay_mode)
        daughter_elem = ATOMIC_SYMBOL.get(daughter_z, f'Z{daughter_z}')
        daughter_name = f"{daughter_elem}-{daughter_a}"
        
        if verbose:
            print(f"\n  Matching: {parent_name} -> {daughter_name} via {decay_mode}")
            print(f"    ENDF particle energy: {endf_particle_energy/1e3:.2f} keV")
        
        key = (parent_a, parent_z, decay_mode)
        
        # -------------------------
        # Case 1: No ENSDF transitions available
        # -------------------------
        if key not in self.transition_lookup:
            # Try to assume ground->ground if energy matches Q_ground
            if key in self.q_ground_lookup:
                q_ground = self.q_ground_lookup[key]
                if abs(endf_particle_energy - q_ground) <= self.absolute_tol:
                    if verbose:
                        print(f"    ✓ Matched to ground->ground (no ENSDF transitions)")
                    return MatchResult(
                        matched=True,
                        parent_level=0.0,
                        final_level=0.0,
                        ensdf_energy=q_ground,
                        endf_q_value=endf_particle_energy,
                        energy_diff=abs(endf_particle_energy - q_ground),
                        rel_diff=abs(endf_particle_energy - q_ground) / max(q_ground, 1e-6),
                        match_quality="assumed_ground",
                        ambiguous=False,
                        daughter_nuclide=daughter_name
                    )
            
            # No ENSDF data and can't assume ground
            if verbose:
                print(f"    ✗ No ENSDF transitions available")
            return MatchResult(
                matched=False,
                parent_level=np.nan,
                final_level=np.nan,
                ensdf_energy=np.nan,
                endf_q_value=endf_particle_energy,
                energy_diff=np.nan,
                rel_diff=np.nan,
                match_quality="no_ensdf_data",
                ambiguous=False,
                daughter_nuclide=daughter_name
            )
        
        # -------------------------
        # Case 2: ENSDF transitions available - find best match
        # -------------------------
        transitions = self.transition_lookup[key]
        
        if verbose:
            print(f"    Found {len(transitions)} ENSDF transitions")
        
        # Search for matching transition
        best_match = None
        best_diff = np.inf
        matches_within_tol = []
        
        for trans in transitions:
            ensdf_energy = trans['particle_energy']
            abs_diff = abs(ensdf_energy - endf_particle_energy)
            
            # Calculate tolerance based on strategy
            if self.strategy == MatchStrategy.ABSOLUTE:
                tolerance = self.absolute_tol
            elif self.strategy == MatchStrategy.RELATIVE:
                tolerance = max(ensdf_energy * self.relative_tol, 1e3)  # Minimum 1 keV
            elif self.strategy == MatchStrategy.HYBRID:
                # Use absolute for low energies, relative for high energies
                if ensdf_energy < self.hybrid_threshold:
                    tolerance = self.absolute_tol
                else:
                    tolerance = ensdf_energy * self.relative_tol
            
            # Check if within tolerance
            if abs_diff <= tolerance:
                matches_within_tol.append((abs_diff, trans, tolerance))
            
            # Track best overall match (even if outside tolerance)
            if abs_diff < best_diff:
                best_diff = abs_diff
                best_match = (abs_diff, trans, tolerance)
        
        # -------------------------
        # Return best match within tolerance
        # -------------------------
        if matches_within_tol:
            # Sort by energy difference, take best
            matches_within_tol.sort(key=lambda x: x[0])
            abs_diff, trans, tol = matches_within_tol[0]
            
            rel_diff = abs_diff / max(trans['particle_energy'], 1e-6)
            ambiguous = len(matches_within_tol) > 1  # Multiple matches?
            
            # Classify match quality
            if abs_diff < tol * 0.1:
                quality = "exact"     # Within 10% of tolerance
            elif abs_diff < tol * 0.5:
                quality = "good"      # Within 50% of tolerance
            else:
                quality = "acceptable"  # Within 100% of tolerance
            
            if verbose:
                p_lvl = int(trans['parent_level'])
                d_lvl = int(trans['daughter_level'])
                print(f"    ✓ Matched: parent_level={p_lvl}, daughter_level={d_lvl}")
                print(f"      ENSDF energy: {trans['particle_energy']/1e3:.2f} keV")
                print(f"      Difference: {abs_diff/1e3:.2f} keV ({quality})")
            
            return MatchResult(
                matched=True,
                parent_level=trans['parent_level'],
                final_level=trans['daughter_level'],
                ensdf_energy=trans['particle_energy'],
                endf_q_value=endf_particle_energy,
                energy_diff=abs_diff,
                rel_diff=rel_diff,
                match_quality=quality,
                ambiguous=ambiguous,
                daughter_nuclide=daughter_name
            )
        
        # -------------------------
        # Try relaxed tolerance (5x normal)
        # -------------------------
        if best_match:
            abs_diff, trans, tol = best_match
            if abs_diff <= tol * self.relaxed_factor:
                rel_diff = abs_diff / max(trans['particle_energy'], 1e-6)
                if verbose:
                    p_lvl = int(trans['parent_level'])
                    d_lvl = int(trans['daughter_level'])
                    print(f"    ~ Marginal: parent_level={p_lvl}, daughter_level={d_lvl}")
                    print(f"      Difference: {abs_diff/1e3:.2f} keV")
                
                return MatchResult(
                    matched=True,
                    parent_level=trans['parent_level'],
                    final_level=trans['daughter_level'],
                    ensdf_energy=trans['particle_energy'],
                    endf_q_value=endf_particle_energy,
                    energy_diff=abs_diff,
                    rel_diff=rel_diff,
                    match_quality="marginal",
                    ambiguous=False,
                    daughter_nuclide=daughter_name
                )
        
        # -------------------------
        # No match found
        # -------------------------
        if verbose:
            if best_match:
                _, trans, _ = best_match
                print(f"    ✗ No match (closest: {trans['particle_energy']/1e3:.2f} keV, diff: {best_diff/1e3:.2f} keV)")
        
        return MatchResult(
            matched=False,
            parent_level=np.nan,
            final_level=np.nan,
            ensdf_energy=best_match[1]['particle_energy'] if best_match else np.nan,
            endf_q_value=endf_particle_energy,
            energy_diff=best_diff,
            rel_diff=best_diff / max(best_match[1]['particle_energy'], 1e-6) if best_match else np.nan,
            match_quality="failed",
            ambiguous=False,
            daughter_nuclide=daughter_name
        )
    
    def match_levels(self, energy_column='Endpoint_energy'):
        """
        Match all ENDF transitions to ENSDF levels.
        
        Main matching loop:
        -------------------
        1. Iterate through all ENDF decay entries
        2. Extract particle energy (endpoint or average)
        3. Call _find_matching_transition() for each entry
        4. Store matched parent_level and final_level
        5. Aggregate statistics and report results
        
        Args:
            energy_column: Which energy column to use for matching
                          ('Endpoint_energy' or 'Average_energy')
        
        Returns:
            DataFrame with matched results including diagnostic columns
        
        Side Effects:
        -------------
        - Populates self.match_results with MatchResult objects
        - Creates self.matched_decay_df with enriched data
        - Adds diagnostic columns: parent_level_matched, final_level_matched,
          match_quality, energy_difference_keV, etc.
        """
        print("\n" + "="*70)
        print("ENDF-ENSDF TRANSITION MATCHING")
        print("="*70)
        print(f"Strategy: {self.strategy.value}")
        print(f"Absolute tolerance: {self.absolute_tol/1e3:.3f} keV")
        print(f"Relative tolerance: {self.relative_tol*100:.4f}%")
        if self.strategy == MatchStrategy.HYBRID:
            print(f"Hybrid threshold: {self.hybrid_threshold/1e3:.1f} keV")
        print(f"Matching on: {energy_column}")
        print(f"Total ENDF decays: {len(self.endf_decay_df)}")
        print("="*70 + "\n")
        
        self.match_results = []
        self.unmatched_decays = []
        
        # Reset index to work with DataFrame rows
        endf_reset = self.endf_decay_df.reset_index()
        
        # Add diagnostic columns
        endf_reset['parent_level_matched'] = np.nan
        endf_reset['final_level_matched'] = np.nan
        endf_reset['match_quality'] = 'unknown'
        endf_reset['match_ambiguous'] = False
        endf_reset['energy_difference_keV'] = np.nan
        endf_reset['daughter_nuclide'] = ''
        
        matched_count = 0
        
        # -------------------------
        # Main matching loop
        # -------------------------
        for idx, row in endf_reset.iterrows():
            parent_a = int(row['A'])
            parent_z = int(row['Z'])
            parent_level = float(row['parentLevel'])
            decay_mode = str(row['decay_mode'])
            parent_name = row.get('Parent', f"{parent_a}-{parent_z}")
            
            # Get ENDF particle energy (try primary column, fallback to alternate)
            endf_energy = row.get(energy_column, np.nan)
            if pd.isna(endf_energy):
                alt_col = 'Average_energy' if energy_column == 'Endpoint_energy' else 'Endpoint_energy'
                endf_energy = row.get(alt_col, np.nan)
            
            # Skip if no energy data
            if pd.isna(endf_energy):
                self.unmatched_decays.append(row.to_dict())
                endf_reset.at[idx, 'match_quality'] = 'no_endf_energy'
                continue
            
            # Verbose output for first 3 matches (for debugging)
            verbose = idx < 3
            
            # Find matching ENSDF transition
            match = self._find_matching_transition(
                parent_a, 
                parent_z,
                parent_level,
                decay_mode,
                endf_energy,
                parent_name,
                verbose=verbose
            )
            self.match_results.append(match)
            
            # Store match results
            if match.matched:
                endf_reset.at[idx, 'parent_level_matched'] = match.parent_level
                endf_reset.at[idx, 'final_level_matched'] = match.final_level
                endf_reset.at[idx, 'match_quality'] = match.match_quality
                endf_reset.at[idx, 'match_ambiguous'] = match.ambiguous
                endf_reset.at[idx, 'energy_difference_keV'] = match.energy_diff / 1e3
                endf_reset.at[idx, 'daughter_nuclide'] = match.daughter_nuclide
                matched_count += 1
            else:
                endf_reset.at[idx, 'match_quality'] = match.match_quality
                if not pd.isna(match.energy_diff):
                    endf_reset.at[idx, 'energy_difference_keV'] = match.energy_diff / 1e3
                endf_reset.at[idx, 'daughter_nuclide'] = match.daughter_nuclide
                if match.match_quality not in ["no_ensdf_data"]:
                    self.unmatched_decays.append(row.to_dict())
        
        # -------------------------
        # Count and report match statistics
        # -------------------------
        exact = sum(1 for m in self.match_results if m.match_quality == "exact")
        good = sum(1 for m in self.match_results if m.match_quality == "good")
        acceptable = sum(1 for m in self.match_results if m.match_quality == "acceptable")
        marginal = sum(1 for m in self.match_results if m.match_quality == "marginal")
        assumed = sum(1 for m in self.match_results if m.match_quality == "assumed_ground")
        
        no_ensdf = sum(1 for m in self.match_results if m.match_quality == "no_ensdf_data")
        failed = sum(1 for m in self.match_results if m.match_quality == "failed")
        
        print(f"\nMatching complete!")
        print(f"  ✓ Total matched: {matched_count}/{len(endf_reset)} ({100*matched_count/len(endf_reset):.1f}%)")
        print(f"\nMatch quality:")
        print(f"  ✓ Exact: {exact}")
        print(f"  ✓ Good: {good}")
        print(f"  ✓ Acceptable: {acceptable}")
        print(f"  ✓ Marginal: {marginal}")
        print(f"  ~ Assumed ground: {assumed}")
        print(f"\nFailure breakdown:")
        print(f"  ✗ No ENSDF data: {no_ensdf}")
        print(f"  ✗ Energy mismatch: {failed}")
        print(f"  Total failed: {no_ensdf + failed}\n")
        
        self.matched_decay_df = endf_reset
        return self.matched_decay_df
    
    def get_statistics(self):
        """Calculate aggregate matching statistics."""
        if not self.match_results:
            return MatchStatistics(
                total_decays=0,
                matched=0,
                unmatched=0,
                ambiguous=0,
                exact_matches=0,
                good_matches=0,
                marginal_matches=0,
                success_rate=0.0
            )
        
        total = len(self.match_results)
        matched = sum(1 for m in self.match_results if m.matched)
        unmatched = total - matched
        ambiguous = sum(1 for m in self.match_results if m.ambiguous)
        exact = sum(1 for m in self.match_results if m.match_quality == "exact")
        good = sum(1 for m in self.match_results if m.match_quality == "good")
        marginal = sum(1 for m in self.match_results if m.match_quality == "marginal")
        srate = 100 * matched / total if total > 0 else 0.0
        
        return MatchStatistics(
            total_decays=total,
            matched=matched,
            unmatched=unmatched,
            ambiguous=ambiguous,
            exact_matches=exact,
            good_matches=good,
            marginal_matches=marginal,
            success_rate=srate
        )
    
    def print_report(self):
        """Print summary report of matching results."""
        stats = self.get_statistics()
        
        print("\n" + "="*70)
        print("LEVEL MATCHING REPORT")
        print("="*70)
        print(f"Total decays:        {stats.total_decays:6d}")
        print(f"Matched:             {stats.matched:6d} ({stats.success_rate:.1f}%)")
        print(f"Unmatched:           {stats.unmatched:6d} ({100-stats.success_rate:.1f}%)")
        print("\nMatch Quality Breakdown:")
        print(f"  Exact matches:     {stats.exact_matches:6d}")
        print(f"  Good matches:      {stats.good_matches:6d}")
        print(f"  Marginal matches:  {stats.marginal_matches:6d}")
        print(f"\nAmbiguous matches:   {stats.ambiguous:6d}")
        
        if self.match_results:
            matched_results = [m for m in self.match_results if m.matched]
            if matched_results:
                diffs = [m.energy_diff for m in matched_results]
                print("\nEnergy Difference Statistics (keV):")
                print(f"  Min:    {np.min(diffs)/1e3:8.3f}")
                print(f"  Median: {np.median(diffs)/1e3:8.3f}")
                print(f"  Mean:   {np.mean(diffs)/1e3:8.3f}")
                print(f"  Max:    {np.max(diffs)/1e3:8.3f}")
                print(f"  Std:    {np.std(diffs)/1e3:8.3f}")
        
        print("="*70 + "\n")
    
    def save_matched_decay(self, output_path):
        """
        Save matched ENDF data with updated level information.
        
        Output Format:
        --------------
        - Main file: ENDF format with updated parentLevel and final_level
        - Only includes original ENDF columns (no diagnostic info)
        - Diagnostics saved separately to *_diagnostics.ascii
        
        Key Operation:
        --------------
        Updates the MultiIndex columns parentLevel and final_level with matched values:
            df['parentLevel'] = df['parent_level_matched']  (where matched)
            df['final_level'] = df['final_level_matched']  (where matched)
        
        Args:
            output_path: Path for output file (e.g., "DECAY_matched.ascii")
        """
        if self.matched_decay_df is None:
            raise ValueError("No matched data. Run match_levels() first.")
        
        df_out = self.matched_decay_df.copy()
        
        # -------------------------
        # Update BOTH parentLevel and final_level with matched values
        # -------------------------
        # Note: In current ENSDF, all parent_level_matched = 0 (ground states only)
        # But final_level_matched DOES update (0 → 1, 2, 3, etc.)
        df_out.loc[df_out['parent_level_matched'].notna(), 'parentLevel'] = df_out['parent_level_matched']
        df_out.loc[df_out['final_level_matched'].notna(), 'final_level'] = df_out['final_level_matched']
        
        # Recreate MultiIndex with updated values
        idx_cols = ['A', 'Z', 'parentLevel', 'decay_mode', 'final_level']
        df_out = df_out.set_index(idx_cols)
        
        # -------------------------
        # Keep ONLY original ENDF columns (remove diagnostic columns)
        # -------------------------
        original_cols = []
        if 'Parent' in df_out.columns:
            original_cols.append('Parent')
        original_cols += ['Endpoint_energy', 'Average_energy', 'Intensity']
        
        keep_cols = [c for c in original_cols if c in df_out.columns]
        df_out = df_out[keep_cols]
        
        # -------------------------
        # Write to file with proper formatting
        # -------------------------
        with open(output_path, 'w') as f:
            # Header line 1: Column names
            index_names = ['A', 'Z', 'parentLevel', 'decay_mode', 'final_level']
            header_spacing = ' ' * 44  # Space for index columns
            data_cols = ' '.join([f'{col:>18}' for col in keep_cols])
            f.write(f"{header_spacing}{data_cols}\n")
            
            # Header line 2: Index names
            f.write(f"{' '.join([f'{name:<3}' if i < 2 else f'{name:<15}' for i, name in enumerate(index_names)])}\n")
            
            # Data rows
            for idx, row in df_out.iterrows():
                # Format index values
                a_val = f"{idx[0]:<4d}"
                z_val = f"{idx[1]:<4d}"
                pl_val = f"{idx[2]:<15.4e}"  # parentLevel in scientific notation
                dm_val = f"{idx[3]:<15}"     # decay_mode as string
                fl_val = f"{idx[4]:<15.4e}"  # final_level in scientific notation
                
                # Format data values
                data_vals = []
                for col in keep_cols:
                    val = row[col]
                    if pd.isna(val):
                        data_vals.append(' ' * 18)
                    elif isinstance(val, str):
                        data_vals.append(f"{val:>18}")
                    else:
                        data_vals.append(f"{val:>18.6e}")
                
                line = f"{a_val}{z_val}{pl_val}{dm_val}{fl_val} {' '.join(data_vals)}\n"
                f.write(line)
        
        print(f"\nSaved matched DECAY data to: {output_path}")
        print(f"  Format: Same as input, with updated parentLevel and final_level")
        print(f"  Total entries: {len(df_out)}")
        
        # Save diagnostics to separate file
        diag_path = output_path.replace('.ascii', '_diagnostics.ascii')
        self._save_diagnostics(diag_path)
    
    def _save_diagnostics(self, output_path):
        """
        Save matching diagnostics to separate file.
        
        Diagnostic Columns:
        -------------------
        - A, Z: Parent nucleus
        - parentLevel, parent_level_matched: Original and matched parent levels
        - final_level, final_level_matched: Original and matched daughter levels
        - Parent, daughter_nuclide: Nucleus names
        - match_quality: exact/good/acceptable/marginal/failed/assumed_ground
        - match_ambiguous: Multiple matches within tolerance?
        - energy_difference_keV: Absolute energy difference
        """
        if self.matched_decay_df is None:
            return
        
        df_diag = self.matched_decay_df.copy()
        
        # Select diagnostic columns
        diag_cols = ['A', 'Z', 'parentLevel', 'parent_level_matched', 
                     'final_level', 'final_level_matched', 
                     'Parent', 'daughter_nuclide',
                     'match_quality', 'match_ambiguous', 'energy_difference_keV']
        
        diag_cols = [c for c in diag_cols if c in df_diag.columns]
        df_diag = df_diag[diag_cols]
        
        # Save as space-separated ASCII
        df_diag.to_csv(output_path, sep=' ', float_format='%.4e', na_rep='', index=False)
        print(f"  Diagnostics saved to: {output_path}")
    
    def export_unmatched(self, filename):
        """Export list of unmatched decays for investigation."""
        if not self.unmatched_decays:
            print("No unmatched decays to export.")
            return
        
        df = pd.DataFrame(self.unmatched_decays)
        df.to_csv(filename, sep=' ', float_format='%.6e', index=False)
        print(f"Exported {len(self.unmatched_decays)} unmatched decays to {filename}")
    
    def export_match_details(self, filename):
        """Export detailed match information for all transitions."""
        if not self.match_results:
            print("No match results to export.")
            return
        
        data = []
        for i, result in enumerate(self.match_results):
            if self.matched_decay_df is not None:
                row_info = self.matched_decay_df.iloc[i]
            else:
                row_info = {}
            
            entry = {
                'Parent': row_info.get('Parent', ''),
                'Daughter': result.daughter_nuclide,
                'decay_mode': row_info.get('decay_mode', ''),
                'matched': int(result.matched),
                'parent_level_matched': result.parent_level,
                'daughter_level_matched': result.final_level,
                'ensdf_energy_MeV': result.ensdf_energy / 1e6,
                'endf_energy_MeV': result.endf_q_value / 1e6,
                'diff_keV': result.energy_diff / 1e3,
                'rel_diff_pct': result.rel_diff * 100,
                'quality': result.match_quality,
                'ambiguous': int(result.ambiguous)
            }
            
            data.append(entry)
        
        df = pd.DataFrame(data)
        df.to_csv(filename, sep=' ', float_format='%.6e', index=False)
        print(f"Exported {len(data)} match details to {filename}")


# =============================================================================
# COMMAND-LINE INTERFACE
# =============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Match ENDF decay transitions to ENSDF levels"
    )
    
    default_endf_path = "/Users/audreywarn/fluka-db-audrey/outputs/endf/endf_data_modules/ascii/DECAY.ascii"
    default_ensdf_path = "/Users/audreywarn/fluka-db-audrey/outputs/ensdf/json_data_modules/ascii/DECAY.ascii"
    
    parser.add_argument(
        "--endf", 
        default=default_endf_path, 
        help="Path to ENDF DECAY.ascii"
    )
    parser.add_argument(
        "--ensdf", 
        default=default_ensdf_path, 
        help="Path to ENSDF DECAY.ascii"
    )
    parser.add_argument(
        "--output", 
        default="DECAY_matched.ascii", 
        help="Output ASCII file"
    )
    parser.add_argument(
        "--abs-tol", 
        type=float, 
        default=2e4, 
        help="Absolute tolerance in eV (default: 20 keV)"
    )
    parser.add_argument(
        "--rel-tol", 
        type=float, 
        default=1e-2, 
        help="Relative tolerance (default: 1%%)"
    )
    parser.add_argument(
        "--strategy", 
        choices=["absolute", "relative", "hybrid"], 
        default="hybrid",
        help="Matching strategy"
    )
    parser.add_argument(
        "--export-unmatched", 
        help="Export unmatched decays to ASCII file"
    )
    parser.add_argument(
        "--export-details", 
        help="Export match details to ASCII file"
    )
    
    args = parser.parse_args()
    
    # Create matcher
    matcher = ENDFLevelMatcherDECAY(
        endf_decay_path=args.endf, 
        ensdf_decay_path=args.ensdf
    )
    
    # Set tolerances
    matcher.set_tolerances(
        absolute_tol=args.abs_tol, 
        relative_tol=args.rel_tol, 
        strategy=args.strategy
    )
    
    # Run matching
    matched_df = matcher.match_levels()
    matcher.print_report()
    matcher.save_matched_decay(args.output)
    
    # Optional exports
    if args.export_unmatched:
        matcher.export_unmatched(args.export_unmatched)
    
    if args.export_details:
        matcher.export_match_details(args.export_details)
    
    print("\nLevel matching complete!")
