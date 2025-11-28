#!/usr/bin/env python3
"""
ENDF-ENSDF Level Matching Tool

PURPOSE:
--------
Matches ENDF decay transitions to ENSDF by comparing calculated daughter level energies.
Enriches ENDF data with detailed level information from ENSDF.

DATABASES:
----------
- ENDF (Evaluated Nuclear Data File): Decay data library
  - Coverage: 4,802 decay transitions
  - Strategy: Representative transition per decay mode (one entry per parent/mode)
  - Contains: Particle energies (endpoint/average), branching ratios, half-lives
  - Missing: Daughter level information (final_level mostly 0)

- ENSDF (Evaluated Nuclear Structure Data File): Nuclear structure + decay database
  - DECAY.ascii: 28,498 decay transitions with level information
  - LEVEL.ascii: 193,506 nuclear level energies (TRUE level energies!)
  - Strategy: Complete decay schemes (all branches to all daughter levels)

WHAT THIS TOOL DOES:
--------------------
**Problem**: ENDF entries mostly have final_level=0 (missing daughter level detail)
**Solution**: 
1. Calculate ENDF daughter level energies: E_daughter = Q_ground - E_particle
2. Look up ENSDF daughter level energies from LEVEL.ascii (native level energies!)
3. Match within tolerance
4. Update ENDF with matched level numbers

Physics-Based Approach:
----------------------
The daughter level energy is determined by energy conservation:
    E_daughter_level = Q_ground - E_particle

Where Q_ground is the ground-to-ground decay energy (maximum particle energy).

Example:
  Li-9 B- decay, Q_ground = 13,610 keV (from ENSDF ground→ground)
  
  ENDF:  Li-9 decay, E_particle = 13,606 keV, final_level = ? (unknown)
         → Calculate: E_daughter = 13,610 - 13,606 = 4 keV
  
  ENSDF LEVEL.ascii:
         → Be-9 level 0: E_level = 0 keV (from LEVEL.ascii)
         → Be-9 level 1: E_level = 2,430 keV (from LEVEL.ascii)
         → Be-9 level 2: E_level = 2,780 keV (from LEVEL.ascii)
  
  Match:  E_daughter(ENDF) = 4 keV ≈ E_level_0(ENSDF) = 0 keV
          Difference = 4 keV < 20 keV tolerance ✓
  
  Result: final_level = 0 (decay populates Be-9 ground state)

MATCHING ALGORITHM:
-------------------
1. Load databases:
   - ENDF DECAY.ascii: 4,802 transitions
   - ENSDF DECAY.ascii: 28,498 transitions
   - ENSDF LEVEL.ascii: 193,506 level energies ⭐

2. Build lookups:
   a) daughter_levels: Dict[(A, Z)] → {level_num: level_energy} from LEVEL.ascii
   b) transition_lookup: Dict[(A, Z, mode)] → [transitions] from DECAY.ascii
   c) q_ground_lookup: Dict[(A, Z, mode)] → Q_ground from ground→ground transitions
   
3. Match each ENDF entry:
   a) Calculate ENDF daughter level energy: E_level_ENDF = Q_ground - E_particle_ENDF
   b) Look up ENSDF level energies from LEVEL.ascii table
   c) Compare within tolerance
   d) Return matched level number

Tolerances (applied to LEVEL ENERGIES):
   - Absolute: 20 keV (for low-lying excited states)
   - Relative: 1% (for highly excited states)
   - Hybrid: Use absolute <500 keV, relative >500 keV (default)

OUTPUT:
-------
- Main file: DECAY_matched.ascii (ENDF format with updated levels)
- Diagnostics: DECAY_matched_diagnostics.ascii (match quality information)

AUTHOR: Generated via code review conversation
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
    """Energy matching tolerance strategies."""
    ABSOLUTE = "absolute"
    RELATIVE = "relative"
    HYBRID = "hybrid"


@dataclass
class MatchResult:
    """Result of matching a single ENDF transition to ENSDF."""
    matched: bool
    parent_level: float
    final_level: float
    ensdf_energy: float
    endf_q_value: float
    energy_diff: float
    rel_diff: float
    match_quality: str
    ambiguous: bool
    daughter_nuclide: str


@dataclass
class MatchStatistics:
    """Aggregate statistics for entire matching run."""
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

class ENDFLevelMatcher:
    """
    Main class for matching ENDF decay data to ENSDF level information.
    
    Uses TRUE ENSDF level energies from LEVEL.ascii (no calculations!).
    """
    
    def __init__(self, endf_decay_path, ensdf_decay_path, ensdf_level_path):
        """
        Initialize matcher and load databases.
        
        Args:
            endf_decay_path: Path to ENDF DECAY.ascii file
            ensdf_decay_path: Path to ENSDF DECAY.ascii file
            ensdf_level_path: Path to ENSDF LEVEL.ascii file
        """
        self.endf_decay_path = Path(endf_decay_path)
        self.ensdf_decay_path = Path(ensdf_decay_path)
        self.ensdf_level_path = Path(ensdf_level_path)
        
        # Default tolerances (energies in eV)
        self.absolute_tol = 2e4  # 20 keV
        self.relative_tol = 1e-2  # 1%
        self.strategy = MatchStrategy.HYBRID
        self.hybrid_threshold = 5e5  # 500 keV
        self.relaxed_factor = 5.0
        
        # Storage for results
        self.match_results = []
        self.unmatched_decays = []
        self.endf_decay_df = None
        self.ensdf_decay_df = None
        self.ensdf_level_df = None
        self.matched_decay_df = None
        
        # Load data and build lookups
        self._load_decay_files()
        self._load_level_file()
        self._build_ensdf_lookup()
    
    def _load_decay_files(self):
        """Load ENDF and ENSDF decay data files."""
        print("\n" + "="*70)
        print("LOADING DECAY FILES")
        print("="*70)
        
        # Load ENDF
        print(f"Loading ENDF: {self.endf_decay_path}")
        self.endf_decay_df = pd.read_csv(
            self.endf_decay_path, 
            sep=r'\s+',
            comment='#',
            index_col=[0, 1, 2, 3, 4],
            engine='python'
        )
        print(f"  Index names: {self.endf_decay_df.index.names}")
        print(f"  Columns: {list(self.endf_decay_df.columns)}")
        print(f"  ENDF entries: {len(self.endf_decay_df)}")
        
        # Load ENSDF (with unit parsing)
        print(f"\nLoading ENSDF: {self.ensdf_decay_path}")
        
        lines = []
        with open(self.ensdf_decay_path, 'r') as f:
            for line in f:
                if line.strip() and not line.strip().startswith('#'):
                    lines.append(line)
        
        processed_data = []
        for line in lines:
            parts = line.split()
            if len(parts) >= 5:
                try:
                    a = int(parts[0])
                    z = int(parts[1])
                    parent_level = float(parts[2])
                    decay_mode = parts[3]
                    final_level = float(parts[4])
                except ValueError:
                    continue
                
                endpoint = np.nan
                average = np.nan
                intensity = np.nan
                
                remaining = parts[5:]
                col_idx = 0
                
                i = 0
                while i < len(remaining):
                    try:
                        val = float(remaining[i])
                        if i + 1 < len(remaining):
                            unit = remaining[i + 1]
                            if unit == 'keV':
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
        
        self.ensdf_decay_df = pd.DataFrame(processed_data)
        self.ensdf_decay_df = self.ensdf_decay_df.set_index(
            ['A', 'Z', 'parentLevel', 'decay_mode', 'final_level']
        )
        
        print(f"  Index names: {self.ensdf_decay_df.index.names}")
        print(f"  Columns: {list(self.ensdf_decay_df.columns)}")
        print(f"  ENSDF entries: {len(self.ensdf_decay_df)}")
        print("="*70 + "\n")
    
    def _load_level_file(self):
        """
        Load ENSDF LEVEL.ascii file containing TRUE nuclear level energies.
        """
        print("\n" + "="*70)
        print("LOADING ENSDF LEVEL FILE")
        print("="*70)
        print(f"  Loading from: {self.ensdf_level_path}")
        
        processed_data = []
        with open(self.ensdf_level_path, 'r') as f:
            for line_num, line in enumerate(f):
                if line_num == 0:
                    continue
                
                parts = line.strip().split()
                if len(parts) < 5:
                    continue
                
                try:
                    a = int(parts[0])
                    z = int(parts[1])
                    level = int(parts[2])
                    
                    energy_str = parts[4]
                    unit_str = parts[5] if len(parts) > 5 else 'keV'
                    
                    energy_val = float(energy_str)
                    
                    if 'keV' in unit_str:
                        energy_eV = energy_val * 1e3
                    elif 'MeV' in unit_str:
                        energy_eV = energy_val * 1e6
                    elif 'eV' in unit_str and 'keV' not in unit_str and 'MeV' not in unit_str:
                        energy_eV = energy_val
                    else:
                        energy_eV = energy_val * 1e3
                    
                    processed_data.append({
                        'A': a,
                        'Z': z,
                        'level': level,
                        'energy_eV': energy_eV
                    })
                except (ValueError, IndexError):
                    continue
        
        self.ensdf_level_df = pd.DataFrame(processed_data)
        self.ensdf_level_df = self.ensdf_level_df.set_index(['A', 'Z', 'level'])
        
        print(f"  Loaded {len(self.ensdf_level_df)} level entries")
        print(f"  Energy range: {self.ensdf_level_df['energy_eV'].min()/1e3:.1f} - {self.ensdf_level_df['energy_eV'].max()/1e6:.1f} keV - MeV")
        print("="*70 + "\n")
    
    def _get_daughter_nucleus(self, parent_a, parent_z, decay_mode):
        """Calculate daughter nucleus (A, Z) from parent and decay mode."""
        mode = str(decay_mode).lower()
        
        if mode.startswith('a'):
            return (parent_a - 4, parent_z - 2)
        
        elif mode.startswith('b-'):
            n_count = mode.count('n')
            if '2n' in mode:
                n_count += 1
            if '3n' in mode:
                n_count += 2
            if 'a' in mode:
                return (parent_a - 4 - n_count, parent_z - 1)
            return (parent_a - n_count, parent_z + 1)
        
        elif mode.startswith('b+') or mode.startswith('ec'):
            p_count = mode.count('p')
            if '2p' in mode:
                p_count += 1
            if 'a' in mode:
                return (parent_a - 4 - p_count, parent_z - 2 - p_count)
            return (parent_a - p_count, parent_z - 1)
        
        else:
            warnings.warn(f"Unknown decay mode: {decay_mode}")
            return (parent_a, parent_z)
    
    def _build_ensdf_lookup(self):
        """
        Build ENSDF lookups using native level energies from LEVEL.ascii.
        
        Creates:
        --------
        self.daughter_levels: Dict[(A, Z)] → {level_num: level_energy_eV}
            Direct from LEVEL.ascii - NO calculations!
        
        self.transition_lookup: Dict[(parent_A, parent_Z, decay_mode)] → [transitions]
            From DECAY.ascii
        
        self.q_ground_lookup: Dict[(parent_A, parent_Z, decay_mode)] → Q_ground_eV
        """
        print("Building ENSDF lookups...")
        print("  Step 1: Building daughter level energy table from LEVEL.ascii...")
        
        # Step 1: Build daughter level energy table directly from LEVEL data
        self.daughter_levels = {}
        
        ensdf_level_reset = self.ensdf_level_df.reset_index()
        for idx, row in ensdf_level_reset.iterrows():
            a = int(row['A'])
            z = int(row['Z'])
            level = int(row['level'])
            energy = float(row['energy_eV'])
            
            key = (a, z)
            if key not in self.daughter_levels:
                self.daughter_levels[key] = {}
            
            self.daughter_levels[key][level] = energy
        
        total_nuclei = len(self.daughter_levels)
        total_levels = sum(len(levels) for levels in self.daughter_levels.values())
        print(f"    Built level tables for {total_nuclei} nuclei ({total_levels} total levels)")
        
        # Step 2: Build transition catalog and Q_ground from DECAY data
        print("  Step 2: Building transition catalog from DECAY.ascii...")
        
        ensdf_decay_reset = self.ensdf_decay_df.reset_index()
        
        self.transition_lookup = {}
        self.q_ground_lookup = {}
        
        for idx, row in ensdf_decay_reset.iterrows():
            parent_a = int(row['A'])
            parent_z = int(row['Z'])
            parent_level = float(row['parentLevel'])
            decay_mode = str(row['decay_mode'])
            
            # Skip if final_level is NaN
            if pd.isna(row['final_level']):
                continue
            
            daughter_level = int(row['final_level'])
            
            # Get particle energy
            endpoint = row.get('Endpoint_energy', np.nan)
            average = row.get('Average_energy', np.nan)
            particle_energy = endpoint if not pd.isna(endpoint) else average
            
            if pd.isna(particle_energy):
                continue
            
            parent_key = (parent_a, parent_z, decay_mode)
            
            # Track Q_ground (ground to ground transition energy)
            if parent_level == 0 and daughter_level == 0:
                if parent_key not in self.q_ground_lookup:
                    self.q_ground_lookup[parent_key] = particle_energy
                else:
                    self.q_ground_lookup[parent_key] = max(self.q_ground_lookup[parent_key], particle_energy)
            
            # Store transition in catalog
            if parent_key not in self.transition_lookup:
                self.transition_lookup[parent_key] = []
            
            self.transition_lookup[parent_key].append({
                'parent_level': parent_level,
                'daughter_level': daughter_level,
                'particle_energy': particle_energy
            })
        
        total_parents = len(self.transition_lookup)
        total_transitions = sum(len(v) for v in self.transition_lookup.values())
        print(f"    Cataloged {total_transitions} transitions for {total_parents} parent nuclei")
        print(f"    Found Q_ground for {len(self.q_ground_lookup)} parent/decay_mode combinations")
        
        # Step 3: Add Q_ground from ENDF for missing parents
        print("  Step 3: Adding Q_ground from ENDF for missing parents...")
        endf_reset = self.endf_decay_df.reset_index()
        
        added = 0
        for idx, row in endf_reset.iterrows():
            parent_a = int(row['A'])
            parent_z = int(row['Z'])
            parent_level = float(row['parentLevel'])
            decay_mode = str(row['decay_mode'])
            
            if parent_level != 0:
                continue
            
            key = (parent_a, parent_z, decay_mode)
            
            if key in self.q_ground_lookup:
                continue
            
            endpoint = row.get('Endpoint_energy', np.nan)
            average = row.get('Average_energy', np.nan)
            energy = endpoint if not pd.isna(endpoint) else average
            
            if pd.isna(energy) or energy <= 0:
                continue
            
            self.q_ground_lookup[key] = energy
            added += 1
        
        print(f"    Added {added} Q_ground values from ENDF")
        print(f"    Total Q_ground available: {len(self.q_ground_lookup)}")
        print("  Lookup complete!\n")
    
    def set_tolerances(self, absolute_tol=None, relative_tol=None, 
                      strategy=None, hybrid_threshold=None, 
                      relaxed_factor=None):
        """Configure energy matching tolerances."""
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
        """Find best matching ENSDF transition for an ENDF entry."""
        daughter_a, daughter_z = self._get_daughter_nucleus(parent_a, parent_z, decay_mode)
        daughter_elem = ATOMIC_SYMBOL.get(daughter_z, f'Z{daughter_z}')
        daughter_name = f"{daughter_elem}-{daughter_a}"
        
        if verbose:
            print(f"\n  Matching: {parent_name} -> {daughter_name} via {decay_mode}")
            print(f"    ENDF particle energy: {endf_particle_energy/1e3:.2f} keV")
        
        key = (parent_a, parent_z, decay_mode)
        
        # Case 1: No ENSDF transitions available
        if key not in self.transition_lookup:
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
        
        # Case 2: ENSDF transitions available
        transitions = self.transition_lookup[key]
        
        if verbose:
            print(f"    Found {len(transitions)} ENSDF transitions")
        
        q_ground = self.q_ground_lookup.get(key, None)
        
        if q_ground is None:
            if verbose:
                print(f"    ✗ No Q_ground available")
            return MatchResult(
                matched=False,
                parent_level=np.nan,
                final_level=np.nan,
                ensdf_energy=np.nan,
                endf_q_value=endf_particle_energy,
                energy_diff=np.nan,
                rel_diff=np.nan,
                match_quality="no_q_ground",
                ambiguous=False,
                daughter_nuclide=daughter_name
            )
        
        # Calculate ENDF daughter level energy
        endf_daughter_level_energy = q_ground - endf_particle_energy
        
        if verbose:
            print(f"    Q_ground: {q_ground/1e3:.2f} keV")
            print(f"    ENDF calculated daughter level energy: {endf_daughter_level_energy/1e3:.2f} keV")
        
        # Search for matching transition
        best_match = None
        best_diff = np.inf
        matches_within_tol = []
        
        daughter_key = (daughter_a, daughter_z)
        daughter_level_table = self.daughter_levels.get(daughter_key, {})
        
        if not daughter_level_table:
            if verbose:
                print(f"    ✗ No level energy data for daughter {daughter_name}")
            return MatchResult(
                matched=False,
                parent_level=np.nan,
                final_level=np.nan,
                ensdf_energy=np.nan,
                endf_q_value=endf_particle_energy,
                energy_diff=np.nan,
                rel_diff=np.nan,
                match_quality="no_daughter_levels",
                ambiguous=False,
                daughter_nuclide=daughter_name
            )
        
        for trans in transitions:
            daughter_level_num = trans['daughter_level']
            
            # Look up ENSDF daughter level energy from LEVEL.ascii table
            if daughter_level_num not in daughter_level_table:
                continue
            
            ensdf_daughter_level_energy = daughter_level_table[daughter_level_num]
            
            # Compare level energies
            abs_diff = abs(ensdf_daughter_level_energy - endf_daughter_level_energy)
            
            # Calculate tolerance
            if self.strategy == MatchStrategy.ABSOLUTE:
                tolerance = self.absolute_tol
            elif self.strategy == MatchStrategy.RELATIVE:
                tolerance = max(ensdf_daughter_level_energy * self.relative_tol, 1e3)
            elif self.strategy == MatchStrategy.HYBRID:
                if ensdf_daughter_level_energy < self.hybrid_threshold:
                    tolerance = self.absolute_tol
                else:
                    tolerance = ensdf_daughter_level_energy * self.relative_tol
            
            if abs_diff <= tolerance:
                matches_within_tol.append((abs_diff, trans, tolerance, ensdf_daughter_level_energy))
            
            if abs_diff < best_diff:
                best_diff = abs_diff
                best_match = (abs_diff, trans, tolerance, ensdf_daughter_level_energy)
        
        # Return best match within tolerance
        if matches_within_tol:
            matches_within_tol.sort(key=lambda x: x[0])
            abs_diff, trans, tol, ensdf_level_energy = matches_within_tol[0]
            
            rel_diff = abs_diff / max(ensdf_level_energy, 1e-6)
            ambiguous = len(matches_within_tol) > 1
            
            if abs_diff < tol * 0.1:
                quality = "exact"
            elif abs_diff < tol * 0.5:
                quality = "good"
            else:
                quality = "acceptable"
            
            if verbose:
                print(f"    ✓ Matched: parent_level={int(trans['parent_level'])}, daughter_level={int(trans['daughter_level'])}")
                print(f"      Level energy difference: {abs_diff/1e3:.2f} keV ({quality})")
            
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
        
        # Try relaxed tolerance
        if best_match:
            abs_diff, trans, tol, ensdf_level_energy = best_match
            if abs_diff <= tol * self.relaxed_factor:
                rel_diff = abs_diff / max(ensdf_level_energy, 1e-6)
                if verbose:
                    print(f"    ~ Marginal match: {abs_diff/1e3:.2f} keV")
                
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
        
        # No match found
        if verbose and best_match:
            print(f"    ✗ No match (best: {best_diff/1e3:.2f} keV)")
        
        return MatchResult(
            matched=False,
            parent_level=np.nan,
            final_level=np.nan,
            ensdf_energy=best_match[1]['particle_energy'] if best_match else np.nan,
            endf_q_value=endf_particle_energy,
            energy_diff=best_diff,
            rel_diff=best_diff / max(best_match[3], 1e-6) if best_match else np.nan,
            match_quality="failed",
            ambiguous=False,
            daughter_nuclide=daughter_name
        )
    
    def match_levels(self, energy_column='Endpoint_energy'):
        """Match all ENDF transitions to ENSDF levels."""
        print("\n" + "="*70)
        print("ENDF-ENSDF TRANSITION MATCHING")
        print("="*70)
        print(f"Strategy: {self.strategy.value}")
        print(f"Absolute tolerance: {self.absolute_tol/1e3:.3f} keV")
        print(f"Relative tolerance: {self.relative_tol*100:.4f}%")
        if self.strategy == MatchStrategy.HYBRID:
            print(f"Hybrid threshold: {self.hybrid_threshold/1e3:.1f} keV")
        print(f"Total ENDF decays: {len(self.endf_decay_df)}")
        print("="*70 + "\n")
        
        self.match_results = []
        self.unmatched_decays = []
        
        endf_reset = self.endf_decay_df.reset_index()
        
        endf_reset['parent_level_matched'] = np.nan
        endf_reset['final_level_matched'] = np.nan
        endf_reset['match_quality'] = 'unknown'
        endf_reset['match_ambiguous'] = False
        endf_reset['energy_difference_keV'] = np.nan
        endf_reset['daughter_nuclide'] = ''
        
        matched_count = 0
        
        for idx, row in endf_reset.iterrows():
            parent_a = int(row['A'])
            parent_z = int(row['Z'])
            parent_level = float(row['parentLevel'])
            decay_mode = str(row['decay_mode'])
            parent_name = row.get('Parent', f"{parent_a}-{parent_z}")
            
            endf_energy = row.get(energy_column, np.nan)
            if pd.isna(endf_energy):
                alt_col = 'Average_energy' if energy_column == 'Endpoint_energy' else 'Endpoint_energy'
                endf_energy = row.get(alt_col, np.nan)
            
            if pd.isna(endf_energy):
                self.unmatched_decays.append(row.to_dict())
                endf_reset.at[idx, 'match_quality'] = 'no_endf_energy'
                continue
            
            verbose = idx < 3
            
            match = self._find_matching_transition(
                parent_a, parent_z, parent_level, decay_mode,
                endf_energy, parent_name, verbose=verbose
            )
            self.match_results.append(match)
            
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
                total_decays=0, matched=0, unmatched=0, ambiguous=0,
                exact_matches=0, good_matches=0, marginal_matches=0, success_rate=0.0
            )
        
        total = len(self.match_results)
        matched = sum(1 for m in self.match_results if m.matched)
        return MatchStatistics(
            total_decays=total,
            matched=matched,
            unmatched=total - matched,
            ambiguous=sum(1 for m in self.match_results if m.ambiguous),
            exact_matches=sum(1 for m in self.match_results if m.match_quality == "exact"),
            good_matches=sum(1 for m in self.match_results if m.match_quality == "good"),
            marginal_matches=sum(1 for m in self.match_results if m.match_quality == "marginal"),
            success_rate=100 * matched / total if total > 0 else 0.0
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
        """Save matched ENDF data with updated level information."""
        if self.matched_decay_df is None:
            raise ValueError("No matched data. Run match_levels() first.")
        
        df_out = self.matched_decay_df.copy()
        
        # Update levels with matched values
        df_out.loc[df_out['parent_level_matched'].notna(), 'parentLevel'] = df_out['parent_level_matched']
        df_out.loc[df_out['final_level_matched'].notna(), 'final_level'] = df_out['final_level_matched']
        
        # Recreate MultiIndex
        idx_cols = ['A', 'Z', 'parentLevel', 'decay_mode', 'final_level']
        df_out = df_out.set_index(idx_cols)
        
        # Keep only original ENDF columns
        original_cols = []
        if 'Parent' in df_out.columns:
            original_cols.append('Parent')
        original_cols += ['Endpoint_energy', 'Average_energy', 'Intensity']
        
        keep_cols = [c for c in original_cols if c in df_out.columns]
        df_out = df_out[keep_cols]
        
        # Write to file
        with open(output_path, 'w') as f:
            index_names = ['A', 'Z', 'parentLevel', 'decay_mode', 'final_level']
            header_spacing = ' ' * 44
            data_cols = ' '.join([f'{col:>18}' for col in keep_cols])
            f.write(f"{header_spacing}{data_cols}\n")
            
            f.write(f"{' '.join([f'{name:<3}' if i < 2 else f'{name:<15}' for i, name in enumerate(index_names)])}\n")
            
            for idx, row in df_out.iterrows():
                a_val = f"{idx[0]:<4d}"
                z_val = f"{idx[1]:<4d}"
                pl_val = f"{idx[2]:<15.4e}"
                dm_val = f"{idx[3]:<15}"
                fl_val = f"{idx[4]:<15.4e}"
                
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
        print(f"  Total entries: {len(df_out)}")
        
        diag_path = output_path.replace('.ascii', '_diagnostics.ascii')
        self._save_diagnostics(diag_path)
    
    def _save_diagnostics(self, output_path):
        """Save matching diagnostics to separate file."""
        if self.matched_decay_df is None:
            return
        
        df_diag = self.matched_decay_df.copy()
        
        diag_cols = ['A', 'Z', 'parentLevel', 'parent_level_matched', 
                     'final_level', 'final_level_matched', 
                     'Parent', 'daughter_nuclide',
                     'match_quality', 'match_ambiguous', 'energy_difference_keV']
        
        diag_cols = [c for c in diag_cols if c in df_diag.columns]
        df_diag = df_diag[diag_cols]
        
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
            
            data.append({
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
            })
        
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
    default_ensdf_decay_path = "/Users/audreywarn/fluka-db-audrey/outputs/ensdf/json_data_modules/ascii/DECAY.ascii"
    default_ensdf_level_path = "/Users/audreywarn/fluka-db-audrey/outputs/ensdf/json_data_modules/ascii/LEVEL.ascii"
    
    parser.add_argument("--endf", default=default_endf_path, help="Path to ENDF DECAY.ascii")
    parser.add_argument("--ensdf", default=default_ensdf_decay_path, help="Path to ENSDF DECAY.ascii")
    parser.add_argument("--ensdf-level", default=default_ensdf_level_path, help="Path to ENSDF LEVEL.ascii")
    parser.add_argument("--output", default="DECAY_level_matched.ascii", help="Output ASCII file")
    parser.add_argument("--abs-tol", type=float, default=2e4, help="Absolute tolerance in eV (default: 20 keV)")
    parser.add_argument("--rel-tol", type=float, default=1e-2, help="Relative tolerance (default: 1%%)")
    parser.add_argument("--strategy", choices=["absolute", "relative", "hybrid"], default="hybrid", help="Matching strategy")
    parser.add_argument("--export-unmatched", help="Export unmatched decays to ASCII file")
    parser.add_argument("--export-details", help="Export match details to ASCII file")
    
    args = parser.parse_args()
    
    # Create matcher
    matcher = ENDFLevelMatcher(
        endf_decay_path=args.endf, 
        ensdf_decay_path=args.ensdf,
        ensdf_level_path=args.ensdf_level
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
