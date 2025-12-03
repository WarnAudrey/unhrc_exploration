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
   - Absolute: Fixed tolerance (e.g., 1 keV for low-lying excited states)
   - Relative: Follows math.isclose() convention: rel_tol * max(|a|, |b|)
     (e.g., 0.1% for highly excited states, default: 0.1%)
   - Hybrid: Use absolute <500 keV, relative >500 keV (default strategy)
   
   Note: Relative tolerance implementation follows Python's math.isclose() logic,
   where tolerance = rel_tol * max(abs(ensdf_energy), abs(endf_energy))

OUTPUT:
-------
- Main file: DECAY_matched.ascii (ENDF format with updated levels)
- Diagnostics: DECAY_matched_diagnostics.ascii (match quality information)

AUTHOR: Generated via code review conversation
DATE: 2025-11-26
UPDATED: 2025-12-01 - Improved placeholder handling using ENSDF transition matching

IMPROVEMENTS IN THIS VERSION:
------------------------------
1. **Better Placeholder Replacement**:
   - When ENDF particle energy < 100 eV (placeholder), instead of assuming ground state,
     finds the dominant ENSDF transition (highest particle energy from ground state)
   - Uses that transition's actual daughter level number
   - More accurate level assignment for problematic isotopes (Li-11, Tc-99, etc.)

2. **ENSDF Q-values Always Used**:
   - Normal matching already uses ENSDF Q_ground (extracted from DECAY.ascii)
   - Calculation: E_daughter = Q_ground_ENSDF - E_particle_ENDF
   - This ensures correct energy scale even when JEFF particle energies are off

3. **Transparent Handling**:
   - "placeholder_replaced" match quality clearly identifies these cases
   - Diagnostic output shows which ENSDF transition was used
   - No silent assumptions
"""

# =============================================================================
# IMPORTS
# =============================================================================

import math  # For mathematical operations and isclose() reference logic
import numpy as np  # Numerical operations (NaN handling, statistics)
import pandas as pd  # DataFrame operations for tabular nuclear data
from typing import Dict, List, Tuple, Optional  # Type hints for code clarity
import warnings  # For warning about unknown decay modes
from pathlib import Path  # Cross-platform file path handling
from dataclasses import dataclass  # Clean data structure definitions
from enum import Enum  # For matching strategy enumeration

# =============================================================================
# DATA STRUCTURES
# =============================================================================

class MatchStrategy(Enum):
    """
    Energy matching tolerance strategies.
    
    Different nuclear energy regimes require different matching approaches:
    - Low-lying states: absolute tolerance (measurement precision similar)
    - Highly excited states: relative tolerance (uncertainty scales with energy)
    """
    ABSOLUTE = "absolute"  # Fixed keV tolerance (e.g., ±20 keV)
    RELATIVE = "relative"  # Percentage tolerance (e.g., ±0.1%)
    HYBRID = "hybrid"      # Absolute below threshold, relative above


@dataclass
class MatchResult:
    """
    Result of matching a single ENDF transition to ENSDF.
    
    Stores complete information about the match attempt, including:
    - Whether match succeeded
    - Which ENSDF levels were matched
    - Energy comparison metrics
    - Match quality assessment
    """
    matched: bool              # True if match found within tolerance
    parent_level: float        # ENSDF parent level number (or NaN if no match)
    final_level: float         # ENSDF daughter level number (THIS IS THE KEY OUTPUT!)
    ensdf_energy: float        # ENSDF particle energy for matched transition
    endf_q_value: float        # ENDF particle energy (input)
    energy_diff: float         # Absolute energy difference |ENSDF - ENDF|
    rel_diff: float            # Relative difference (energy_diff / energy)
    match_quality: str         # "exact", "good", "acceptable", "marginal", "failed"
    ambiguous: bool            # True if multiple transitions matched within tolerance
    daughter_nuclide: str      # Human-readable daughter name (e.g., "Be-9")


@dataclass
class MatchStatistics:
    """
    Aggregate statistics for entire matching run.
    
    Provides high-level overview of matching performance across all ENDF entries.
    """
    total_decays: int          # Total number of ENDF entries processed
    matched: int               # Number successfully matched
    unmatched: int             # Number that failed to match
    ambiguous: int             # Number with multiple possible matches
    exact_matches: int         # Matches with energy diff < 10% of tolerance
    good_matches: int          # Matches with energy diff < 50% of tolerance
    marginal_matches: int      # Matches requiring relaxed tolerance
    success_rate: float        # Percentage matched (matched/total * 100)


# Element symbols for atomic number Z
# Maps atomic number (proton count) to chemical element symbol
# Used for creating human-readable nuclide names (e.g., Z=4 → "Be", A=9 → "Be-9")
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
    
    CORE CONCEPT:
    ------------
    Uses TRUE ENSDF level energies from LEVEL.ascii (no calculations!).
    Compares calculated ENDF daughter level energies against experimental ENSDF values.
    
    WORKFLOW:
    --------
    1. __init__: Load all data files and build lookup tables
    2. set_tolerances: Configure matching criteria (optional)
    3. match_levels: Run matching algorithm on all ENDF entries
    4. save_matched_decay: Output enriched ENDF data
    """
    
    def __init__(self, endf_decay_path, ensdf_decay_path, ensdf_level_path):
        """
        Initialize matcher and load databases.
        
        This constructor performs ALL data loading and preprocessing:
        1. Stores file paths
        2. Sets default matching tolerances
        3. Loads ENDF decay data (~4,802 entries)
        4. Loads ENSDF decay data (~28,498 entries)
        5. Loads ENSDF level energies (~193,506 entries) ⭐ KEY DATA!
        6. Builds fast lookup dictionaries for O(1) matching
        
        Args:
            endf_decay_path: Path to ENDF DECAY.ascii file
            ensdf_decay_path: Path to ENSDF DECAY.ascii file
            ensdf_level_path: Path to ENSDF LEVEL.ascii file (experimental level energies!)
        """
        # Store file paths as Path objects for cross-platform compatibility
        self.endf_decay_path = Path(endf_decay_path)
        self.ensdf_decay_path = Path(ensdf_decay_path)
        self.ensdf_level_path = Path(ensdf_level_path)
        
        # Default tolerances (all energies in eV for consistency)
        self.absolute_tol = 1e3  # 1 keV = 1000 eV (good for low-lying excited states)
        self.relative_tol = 1e-3  # 0.1% = 0.001 (good for highly excited states)
        self.strategy = MatchStrategy.HYBRID  # Use absolute <500keV, relative >500keV
        self.hybrid_threshold = 5e5  # 500 keV = 500,000 eV (switch point)
        self.relaxed_factor = 5.0  # Allow 5x normal tolerance for marginal matches
        
        # Storage for results (populated by match_levels())
        self.match_results = []        # List of MatchResult objects (one per ENDF entry)
        self.unmatched_decays = []     # List of dictionaries for failed matches
        self.endf_decay_df = None      # DataFrame: ENDF decay data
        self.ensdf_decay_df = None     # DataFrame: ENSDF decay data
        self.ensdf_level_df = None     # DataFrame: ENSDF level energies (ground truth!)
        self.matched_decay_df = None   # DataFrame: ENDF data with matched levels (output)
        
        # Track placeholder data statistics
        self.placeholder_count = 0      # Total ENDF placeholders detected (< 100 eV)
        self.placeholder_replaced = 0   # Placeholders replaced with ENSDF Q_ground
        
        # Load data and build lookups (heavy lifting happens here!)
        self._load_decay_files()       # Step 1: Load ENDF and ENSDF decay data
        self._load_level_file()        # Step 2: Load ENSDF level energies
        self._build_ensdf_lookup()     # Step 3: Build fast lookup dictionaries
        
        # =====================================================================
        # DIAGNOSTIC: Check Q-values for specific cases
        # =====================================================================
        print("\n" + "="*70)
        print("Q-VALUE DIAGNOSTIC")
        print("="*70)
        print(f"Total Q-values in lookup: {len(self.q_ground_lookup)}")
        
        # Check Li-11 specifically (known problematic case)
        key = (11, 3, 'B-')
        if key in self.q_ground_lookup:
            q = self.q_ground_lookup[key]
            print(f"\nLi-11 B- decay:")
            print(f"  Q_ground used: {q/1e3:.2f} keV ({q:.2e} eV)")
            
            # Determine source
            if key in self.transition_lookup:
                print(f"  Source: ENSDF (has transitions in DECAY.ascii)")
                # Show some transitions
                transitions = self.transition_lookup[key]
                print(f"  Number of ENSDF transitions: {len(transitions)}")
                if transitions:
                    print(f"  First transition:")
                    print(f"    parent_level={transitions[0]['parent_level']}, "
                          f"daughter_level={transitions[0]['daughter_level']}")
                    print(f"    particle_energy={transitions[0]['particle_energy']/1e3:.2f} keV")
                    if len(transitions) > 1:
                        print(f"  Second transition:")
                        print(f"    parent_level={transitions[1]['parent_level']}, "
                              f"daughter_level={transitions[1]['daughter_level']}")
                        print(f"    particle_energy={transitions[1]['particle_energy']/1e3:.2f} keV")
            else:
                print(f"  Source: ENDF (no ENSDF transitions, used ENDF Q-value)")
        else:
            print(f"\nLi-11 B- decay: NOT FOUND in Q-value lookup!")
        
        # Check Be-12 for comparison (known successful case)
        key2 = (12, 4, 'B-')
        if key2 in self.q_ground_lookup:
            q2 = self.q_ground_lookup[key2]
            print(f"\nBe-12 B- decay (for comparison):")
            print(f"  Q_ground used: {q2/1e3:.2f} keV ({q2:.2e} eV)")
            source = 'ENSDF' if key2 in self.transition_lookup else 'ENDF'
            print(f"  Source: {source}")
            if key2 in self.transition_lookup:
                transitions2 = self.transition_lookup[key2]
                print(f"  Number of ENSDF transitions: {len(transitions2)}")
        
        # Check daughter nucleus level energies
        print(f"\nDaughter nucleus level energies:")
        
        # Be-11 levels (daughter of Li-11)
        daughter_key = (11, 4)
        if daughter_key in self.daughter_levels:
            be11_levels = self.daughter_levels[daughter_key]
            print(f"  Be-11 (daughter of Li-11):")
            for level_num in sorted(be11_levels.keys())[:5]:  # Show first 5 levels
                print(f"    Level {level_num}: {be11_levels[level_num]/1e3:.2f} keV")
        else:
            print(f"  Be-11: NOT FOUND in daughter levels!")
        
        # B-12 levels (daughter of Be-12)
        daughter_key2 = (12, 5)
        if daughter_key2 in self.daughter_levels:
            b12_levels = self.daughter_levels[daughter_key2]
            print(f"  B-12 (daughter of Be-12):")
            for level_num in sorted(b12_levels.keys())[:5]:  # Show first 5 levels
                print(f"    Level {level_num}: {b12_levels[level_num]/1e3:.2f} keV")
        
        print("="*70 + "\n")
    
    def _load_decay_files(self):
        """
        Load ENDF and ENSDF decay data files.
        
        ENDF FORMAT: Standard whitespace-separated with MultiIndex
        ENSDF FORMAT: Includes units (keV, %) requiring custom parsing
        
        Both files share similar structure:
        A  Z  parentLevel  decay_mode  final_level  Endpoint_energy  Average_energy  Intensity
        9  3  0.0          B-          0.0          13606000         5600000         100
        
        Key difference: ENSDF has complete decay schemes, ENDF has representative transitions
        """
        print("\n" + "="*70)
        print("LOADING DECAY FILES")
        print("="*70)
        
        # =====================================================================
        # LOAD ENDF DECAY DATA
        # =====================================================================
        print(f"Loading ENDF: {self.endf_decay_path}")
        
        # ENDF uses simple whitespace-separated format (no units in data)
        self.endf_decay_df = pd.read_csv(
            self.endf_decay_path, 
            sep=r'\s+',              # Any whitespace as separator
            comment='#',             # Skip comment lines
            index_col=[0, 1, 2, 3, 4],  # MultiIndex: (A, Z, parentLevel, decay_mode, final_level)
            engine='python'          # Required for regex separator
        )
        
        # Print diagnostics for verification
        print(f"  Index names: {self.endf_decay_df.index.names}")
        print(f"  Columns: {list(self.endf_decay_df.columns)}")
        print(f"  ENDF entries: {len(self.endf_decay_df)}")  # ~4,802 entries
        
        # =====================================================================
        # LOAD ENSDF DECAY DATA (WITH UNIT PARSING)
        # =====================================================================
        print(f"\nLoading ENSDF: {self.ensdf_decay_path}")
        
        # Read all non-comment lines
        lines = []
        with open(self.ensdf_decay_path, 'r') as f:
            for line in f:
                # Skip empty lines and comments
                if line.strip() and not line.strip().startswith('#'):
                    lines.append(line)
        
        # Parse each line manually (ENSDF includes units like "keV" and "%")
        processed_data = []
        for line in lines:
            parts = line.split()  # Split on whitespace
            
            # Verify minimum required fields
            if len(parts) < 5:
                continue
            
            # Parse required index fields (no units)
            try:
                a = int(parts[0])           # Mass number
                z = int(parts[1])           # Atomic number
                parent_level = float(parts[2])  # Parent level energy
                decay_mode = parts[3]       # Decay mode string (e.g., "B-", "A", "EC")
                final_level = float(parts[4])  # Daughter level number
            except ValueError:
                continue  # Skip malformed lines
            
            # Initialize data columns as NaN
            endpoint = np.nan    # Endpoint energy (max energy for decay)
            average = np.nan     # Average energy (mean for continuous spectra)
            intensity = np.nan   # Branching ratio (percentage)
            
            # Parse remaining fields with unit detection
            remaining = parts[5:]  # Everything after the 5 required fields
            col_idx = 0  # Track which data column we're filling
            
            i = 0
            while i < len(remaining):
                try:
                    val = float(remaining[i])  # Try to parse as number
                    
                    # Check if next token is a unit
                    if i + 1 < len(remaining):
                        unit = remaining[i + 1]
                        
                        if unit == 'keV':
                            # Convert keV to eV (standard unit)
                            val = val * 1e3
                            
                            # Assign to appropriate column based on order
                            if col_idx == 0:
                                endpoint = val
                                col_idx = 1
                            elif col_idx == 1:
                                average = val
                                col_idx = 2
                            
                            i += 2  # Skip value and unit
                        
                        elif unit == '%':
                            # Intensity is a percentage (dimensionless)
                            intensity = val
                            i += 2  # Skip value and unit
                        
                        else:
                            i += 1  # Not a recognized unit, move forward
                    else:
                        i += 1  # No more tokens
                        
                except ValueError:
                    i += 1  # Not a number, move forward
            
            # Store parsed data
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
        
        # Convert to DataFrame with MultiIndex (same structure as ENDF)
        self.ensdf_decay_df = pd.DataFrame(processed_data)
        self.ensdf_decay_df = self.ensdf_decay_df.set_index(
            ['A', 'Z', 'parentLevel', 'decay_mode', 'final_level']
        )
        
        # Print diagnostics
        print(f"  Index names: {self.ensdf_decay_df.index.names}")
        print(f"  Columns: {list(self.ensdf_decay_df.columns)}")
        print(f"  ENSDF entries: {len(self.ensdf_decay_df)}")  # ~28,498 entries
        print("="*70 + "\n")
    
    def _load_level_file(self):
        """
        Load ENSDF LEVEL.ascii file containing TRUE nuclear level energies.
        
        THIS IS THE GROUND TRUTH DATA!
        
        LEVEL.ascii contains experimentally measured energy levels for nuclear states.
        These are NOT calculated - they come from decades of spectroscopy experiments.
        
        Format example:
        A  Z  level  ...  energy  unit
        9  4  0      ...  0       keV      (Be-9 ground state)
        9  4  1      ...  2430    keV      (Be-9 first excited state)
        9  4  2      ...  2780    keV      (Be-9 second excited state)
        
        We will use these energies to match against calculated ENDF daughter levels.
        """
        print("\n" + "="*70)
        print("LOADING ENSDF LEVEL FILE")
        print("="*70)
        print(f"  Loading from: {self.ensdf_level_path}")
        
        # Parse file line by line (includes unit conversion)
        processed_data = []
        with open(self.ensdf_level_path, 'r') as f:
            for line_num, line in enumerate(f):
                # Skip header line
                if line_num == 0:
                    continue
                
                parts = line.strip().split()
                
                # Verify minimum required fields
                if len(parts) < 5:
                    continue
                
                try:
                    # Parse index fields
                    a = int(parts[0])        # Mass number
                    z = int(parts[1])        # Atomic number
                    level = int(parts[2])    # Level number (0=ground, 1=1st excited, etc.)
                    
                    # Parse energy and unit
                    energy_str = parts[4]    # Energy value
                    unit_str = parts[5] if len(parts) > 5 else 'keV'  # Default to keV
                    
                    energy_val = float(energy_str)
                    
                    # Convert to eV (standard unit)
                    if 'keV' in unit_str:
                        energy_eV = energy_val * 1e3   # keV → eV
                    elif 'MeV' in unit_str:
                        energy_eV = energy_val * 1e6   # MeV → eV
                    elif 'eV' in unit_str and 'keV' not in unit_str and 'MeV' not in unit_str:
                        energy_eV = energy_val         # Already in eV
                    else:
                        # Assume keV if unit unclear
                        energy_eV = energy_val * 1e3
                    
                    # Store parsed data
                    processed_data.append({
                        'A': a,
                        'Z': z,
                        'level': level,
                        'energy_eV': energy_eV  # This is the KEY data!
                    })
                    
                except (ValueError, IndexError):
                    continue  # Skip malformed lines
        
        # Convert to DataFrame with MultiIndex for fast lookups
        self.ensdf_level_df = pd.DataFrame(processed_data)
        self.ensdf_level_df = self.ensdf_level_df.set_index(['A', 'Z', 'level'])
        
        # Print diagnostics
        print(f"  Loaded {len(self.ensdf_level_df)} level entries")  # ~193,506 levels
        print(f"  Energy range: {self.ensdf_level_df['energy_eV'].min()/1e3:.1f} - "
              f"{self.ensdf_level_df['energy_eV'].max()/1e6:.1f} keV - MeV")
        print("="*70 + "\n")
    
    def _get_daughter_nucleus(self, parent_a, parent_z, decay_mode):
        """
        Calculate daughter nucleus (A, Z) from parent and decay mode.
        
        Uses nuclear physics conservation laws:
        - Mass number A: total nucleons (protons + neutrons)
        - Atomic number Z: number of protons
        
        DECAY MODES:
        -----------
        α decay:  Emit ²He⁴ nucleus → A-4, Z-2
        β⁻ decay: n → p + e⁻ + ν̄ → A same, Z+1
        β⁺ decay: p → n + e⁺ + ν → A same, Z-1
        EC decay: p + e⁻ → n + ν → A same, Z-1
        
        Can include particle emission (n, p, α) in addition to β decay.
        
        Args:
            parent_a: Parent mass number
            parent_z: Parent atomic number
            decay_mode: Decay mode string (e.g., "B-", "B-N", "A", "EC2P")
        
        Returns:
            Tuple (daughter_a, daughter_z)
        """
        # Convert to lowercase for case-insensitive matching
        mode = str(decay_mode).lower()
        
        # =====================================================================
        # ALPHA DECAY: Emit helium-4 nucleus
        # =====================================================================
        if mode.startswith('a'):
            # α particle = ²He⁴ → lose 4 nucleons and 2 protons
            return (parent_a - 4, parent_z - 2)
        
        # =====================================================================
        # BETA-MINUS DECAY: Neutron converts to proton
        # =====================================================================
        elif mode.startswith('b-'):
            # Count neutron emissions (e.g., "b-n" → 1 neutron, "b-2n" → 2 neutrons)
            n_count = mode.count('n')
            if '2n' in mode:
                n_count += 1  # "2n" counts as 2 total neutrons
            if '3n' in mode:
                n_count += 2  # "3n" counts as 3 total neutrons
            
            # Check for alpha emission in addition to beta
            if 'a' in mode:
                # β⁻ + α → lose 4 nucleons + n neutrons, Z increases by 1 but loses 2 from α
                return (parent_a - 4 - n_count, parent_z - 1)
            
            # Standard β⁻ decay: n → p → A decreases by neutron emissions, Z increases by 1
            return (parent_a - n_count, parent_z + 1)
        
        # =====================================================================
        # BETA-PLUS / ELECTRON CAPTURE: Proton converts to neutron
        # =====================================================================
        elif mode.startswith('b+') or mode.startswith('ec'):
            # Count proton emissions (e.g., "ec2p" → 2 protons)
            p_count = mode.count('p')
            if '2p' in mode:
                p_count += 1  # "2p" counts as 2 total protons
            
            # Check for alpha emission in addition to beta+/EC
            if 'a' in mode:
                # β⁺/EC + α → lose 4 nucleons + p protons, Z decreases by 1 + 2 (α) + p
                return (parent_a - 4 - p_count, parent_z - 2 - p_count)
            
            # Standard β⁺/EC decay: p → n → A decreases by proton emissions, Z decreases by 1
            return (parent_a - p_count, parent_z - 1)
        
        # =====================================================================
        # UNKNOWN DECAY MODE
        # =====================================================================
        else:
            # Warn user but don't crash (assume no change)
            warnings.warn(f"Unknown decay mode: {decay_mode}")
            return (parent_a, parent_z)
    
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
    
    def _build_ensdf_lookup(self):
        """
        Build ENSDF lookups using native level energies from LEVEL.ascii.
        
        Creates THREE critical lookup dictionaries for O(1) matching speed:
        
        1. daughter_levels: Dict[(A, Z)] → {level_num: level_energy_eV}
           - Direct from LEVEL.ascii (experimental values!)
           - Example: (9, 4) → {0: 0, 1: 2430000, 2: 2780000} for Be-9
        
        2. transition_lookup: Dict[(parent_A, parent_Z, decay_mode)] → [transitions]
           - From DECAY.ascii
           - Lists all observed transitions for each parent/mode combination
           - Example: (9, 3, "B-") → [{parent_level: 0, daughter_level: 0, ...}, ...]
        
        3. q_ground_lookup: Dict[(parent_A, parent_Z, decay_mode)] → Q_ground_eV
           - Maximum decay energy (ground state → ground state)
           - Used to calculate daughter level: E_daughter = Q_ground - E_particle
           - Example: (9, 3, "B-") → 13610000 eV
        
        These lookups convert linear O(n) searches into O(1) hash table lookups!
        """
        print("Building ENSDF lookups...")
        
        # =====================================================================
        # STEP 1: Build daughter level energy table from LEVEL.ascii
        # =====================================================================
        print("  Step 1: Building daughter level energy table from LEVEL.ascii...")
        
        # Initialize dictionary: (A, Z) → {level_num: energy_eV}
        self.daughter_levels = {}
        
        # Reset index to access columns
        ensdf_level_reset = self.ensdf_level_df.reset_index()
        
        # Build nested dictionary structure
        for idx, row in ensdf_level_reset.iterrows():
            a = int(row['A'])
            z = int(row['Z'])
            level = int(row['level'])
            energy = float(row['energy_eV'])  # Experimental value from LEVEL.ascii!
            
            # Create nested dictionary on first encounter
            key = (a, z)
            if key not in self.daughter_levels:
                self.daughter_levels[key] = {}
            
            # Store level energy (this is the GROUND TRUTH for matching!)
            self.daughter_levels[key][level] = energy
        
        # Print statistics
        total_nuclei = len(self.daughter_levels)
        total_levels = sum(len(levels) for levels in self.daughter_levels.values())
        print(f"    Built level tables for {total_nuclei} nuclei ({total_levels} total levels)")
        
        # =====================================================================
        # STEP 2: Build transition catalog and Q_ground from DECAY.ascii
        # =====================================================================
        print("  Step 2: Building transition catalog from DECAY.ascii...")
        
        # Reset index to access columns
        ensdf_decay_reset = self.ensdf_decay_df.reset_index()
        
        # Initialize dictionaries
        self.transition_lookup = {}  # (parent_A, parent_Z, mode) → [transitions]
        self.q_ground_lookup = {}    # (parent_A, parent_Z, mode) → Q_ground
        
        for idx, row in ensdf_decay_reset.iterrows():
            # Parse parent nucleus information
            parent_a = int(row['A'])
            parent_z = int(row['Z'])
            parent_level = float(row['parentLevel'])
            decay_mode = str(row['decay_mode'])
            
            # Skip if final_level is missing (incomplete data)
            if pd.isna(row['final_level']):
                continue
            
            daughter_level = int(row['final_level'])
            
            # Get particle energy (prefer endpoint, fall back to average)
            endpoint = row.get('Endpoint_energy', np.nan)
            average = row.get('Average_energy', np.nan)
            particle_energy = endpoint if not pd.isna(endpoint) else average
            
            # Skip if no energy data
            if pd.isna(particle_energy):
                continue
            
            # Create parent key for lookups
            parent_key = (parent_a, parent_z, decay_mode)
            
            # -------------------------------------------------------------
            # Track Q_ground (maximum particle energy from ground state)
            # -------------------------------------------------------------
            # Q_ground is the MAXIMUM particle energy from parent ground state
            # The daughter can be in ANY level (ground or excited)
            # Many nuclei (like Li-11) decay ONLY to excited states!
            # This is the reference energy for calculating daughter levels
            if parent_level == 0:  # FIXED: Only check parent is ground state
                if parent_key not in self.q_ground_lookup:
                    # First transition from parent ground state found
                    self.q_ground_lookup[parent_key] = particle_energy
                else:
                    # Take maximum particle energy from ground state
                    # This gives us the true Q-value for the decay
                    self.q_ground_lookup[parent_key] = max(
                        self.q_ground_lookup[parent_key], 
                        particle_energy
                    )
            
            # -------------------------------------------------------------
            # Store transition in catalog
            # -------------------------------------------------------------
            if parent_key not in self.transition_lookup:
                self.transition_lookup[parent_key] = []
            
            self.transition_lookup[parent_key].append({
                'parent_level': parent_level,
                'daughter_level': daughter_level,
                'particle_energy': particle_energy
            })
        
        # Print statistics
        total_parents = len(self.transition_lookup)
        total_transitions = sum(len(v) for v in self.transition_lookup.values())
        print(f"    Cataloged {total_transitions} transitions for {total_parents} parent nuclei")
        print(f"    Found Q_ground for {len(self.q_ground_lookup)} parent/decay_mode combinations")
        
        # =====================================================================
        # STEP 3: Add Q_ground from ENDF for missing parents
        # =====================================================================
        # ENSDF may be missing some ground→ground transitions that ENDF has
        # This extends our coverage
        print("  Step 3: Adding Q_ground from ENDF for missing parents...")
        
        # Reset ENDF index to access columns
        endf_reset = self.endf_decay_df.reset_index()
        
        added = 0
        for idx, row in endf_reset.iterrows():
            parent_a = int(row['A'])
            parent_z = int(row['Z'])
            parent_level = float(row['parentLevel'])
            decay_mode = str(row['decay_mode'])
            
            # Only use ground state ENDF entries
            if parent_level != 0:
                continue
            
            key = (parent_a, parent_z, decay_mode)
            
            # Skip if we already have Q_ground from ENSDF
            if key in self.q_ground_lookup:
                continue
            
            # Get energy from ENDF
            endpoint = row.get('Endpoint_energy', np.nan)
            average = row.get('Average_energy', np.nan)
            energy = endpoint if not pd.isna(endpoint) else average
            
            # Skip if no valid energy
            if pd.isna(energy) or energy <= 0:
                continue
            
            # Add to Q_ground lookup
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
        
        Allows customization of matching criteria based on physics requirements:
        - Tight tolerances: More accurate but fewer matches
        - Loose tolerances: More matches but potentially incorrect
        
        Relative tolerance follows math.isclose() convention:
            tolerance = rel_tol * max(abs(ensdf_energy), abs(endf_energy))
        This ensures symmetric comparison between the two energy values.
        
        Args:
            absolute_tol: Fixed energy tolerance in eV (e.g., 1000 for 1 keV)
            relative_tol: Fractional tolerance (e.g., 0.001 for 0.1%)
            strategy: "absolute", "relative", or "hybrid"
            hybrid_threshold: Energy (eV) where hybrid switches from absolute to relative
            relaxed_factor: Multiplier for marginal matches (e.g., 5.0 for 5x tolerance)
        """
        # Only update provided parameters (leave others at defaults)
        if absolute_tol is not None:
            self.absolute_tol = absolute_tol
        if relative_tol is not None:
            self.relative_tol = relative_tol
        if strategy is not None:
            # Convert string to enum
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
        
        THIS IS THE CORE MATCHING ALGORITHM!
        
        Algorithm:
        ---------
        1. Calculate daughter nucleus (A, Z) from decay mode
        2. Check if ENSDF transitions exist for this decay
        3. Get Q_ground (maximum decay energy)
        4. Calculate ENDF daughter level energy: E_daughter = Q_ground - E_particle
        5. Look up ENSDF level energies for daughter nucleus from LEVEL.ascii
        6. Compare calculated ENDF level against ENSDF levels
        7. Find best match within tolerance
        8. Return MatchResult with level assignment
        
        Args:
            parent_a: Parent mass number
            parent_z: Parent atomic number
            parent_level: Parent level number
            decay_mode: Decay mode (e.g., "B-")
            endf_particle_energy: ENDF particle energy (eV)
            parent_name: Human-readable parent name (for verbose output)
            verbose: If True, print detailed matching information
        
        Returns:
            MatchResult object with match status and level assignment
        """
        # =====================================================================
        # STEP 1: Identify daughter nucleus
        # =====================================================================
        daughter_a, daughter_z = self._get_daughter_nucleus(parent_a, parent_z, decay_mode)
        daughter_elem = ATOMIC_SYMBOL.get(daughter_z, f'Z{daughter_z}')
        daughter_name = f"{daughter_elem}-{daughter_a}"
        
        if verbose:
            print(f"\n  Matching: {parent_name} -> {daughter_name} via {decay_mode}")
            print(f"    ENDF particle energy: {endf_particle_energy/1e3:.2f} keV")
        
        # Create parent key for lookups
        key = (parent_a, parent_z, decay_mode)
        
        # =====================================================================
        # CASE 1: No ENSDF transitions available
        # =====================================================================
        if key not in self.transition_lookup:
            # No ENSDF decay scheme data for this parent
            # Try to match to ground state using Q_ground
            if key in self.q_ground_lookup:
                q_ground = self.q_ground_lookup[key]
                
                # Check if ENDF energy matches ground→ground Q-value
                if abs(endf_particle_energy - q_ground) <= self.absolute_tol:
                    if verbose:
                        print(f"    ✓ Matched to ground->ground (no ENSDF transitions)")
                    
                    # Assume decay to ground state
                    return MatchResult(
                        matched=True,
                        parent_level=0.0,
                        final_level=0.0,  # Ground state
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
            
            # Complete failure: no ENSDF data
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
        
        # =====================================================================
        # CASE 2: ENSDF transitions available
        # =====================================================================
        transitions = self.transition_lookup[key]
        
        if verbose:
            print(f"    Found {len(transitions)} ENSDF transitions")
        
        # Get Q_ground (required for calculating daughter level energy)
        q_ground = self.q_ground_lookup.get(key, None)
        
        if q_ground is None:
            if verbose:
                print(f"    ✗ No Q_ground available")
            
            # Cannot calculate daughter level without Q_ground
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
        
        # =====================================================================
        # STEP 2: Calculate ENDF daughter level energy
        # =====================================================================
        # KEY PHYSICS: E_daughter_level = Q_ground - E_particle
        # Energy conservation: total energy = particle energy + daughter excitation
        endf_daughter_level_energy = q_ground - endf_particle_energy
        
        if verbose:
            print(f"    Q_ground: {q_ground/1e3:.2f} keV")
            print(f"    ENDF calculated daughter level energy: {endf_daughter_level_energy/1e3:.2f} keV")
        
        # =====================================================================
        # STEP 3: Search for matching ENSDF level
        # =====================================================================
        best_match = None       # Best match found (even if outside tolerance)
        best_diff = np.inf      # Energy difference for best match
        matches_within_tol = [] # All matches within tolerance
        
        # Get ENSDF level energies for daughter nucleus (from LEVEL.ascii)
        daughter_key = (daughter_a, daughter_z)
        daughter_level_table = self.daughter_levels.get(daughter_key, {})
        
        if not daughter_level_table:
            if verbose:
                print(f"    ✗ No level energy data for daughter {daughter_name}")
            
            # Daughter nucleus not in LEVEL.ascii
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
        
        # Loop through all ENSDF transitions for this parent
        for trans in transitions:
            daughter_level_num = trans['daughter_level']
            
            # Look up ENSDF daughter level energy from LEVEL.ascii table
            if daughter_level_num not in daughter_level_table:
                continue  # This level not in LEVEL.ascii (skip)
            
            ensdf_daughter_level_energy = daughter_level_table[daughter_level_num]
            
            # -------------------------------------------------------------
            # Compare calculated ENDF level energy vs ENSDF level energy
            # -------------------------------------------------------------
            abs_diff = abs(ensdf_daughter_level_energy - endf_daughter_level_energy)
            
            # -------------------------------------------------------------
            # Calculate tolerance based on selected strategy
            # -------------------------------------------------------------
            if self.strategy == MatchStrategy.ABSOLUTE:
                # Pure absolute tolerance (fixed energy difference)
                # Good for low-lying states where measurement precision is similar
                tolerance = self.absolute_tol
                strategy_used = "absolute"
                
            elif self.strategy == MatchStrategy.RELATIVE:
                # Pure relative tolerance (percentage of level energy)
                # Good for highly excited states where uncertainty scales with energy
                # Following math.isclose() logic: rel_tol * max(|a|, |b|)
                max_energy = max(abs(ensdf_daughter_level_energy), abs(endf_daughter_level_energy))
                tolerance = max(self.relative_tol * max_energy, self.absolute_tol)
                strategy_used = "relative"
                
            elif self.strategy == MatchStrategy.HYBRID:
                # Hybrid: absolute for low-lying states, relative for highly excited states
                # Combines advantages of both approaches
                if ensdf_daughter_level_energy < self.hybrid_threshold:
                    tolerance = self.absolute_tol
                    strategy_used = "hybrid(abs)"
                else:
                    # Following math.isclose() logic: rel_tol * max(|a|, |b|)
                    max_energy = max(abs(ensdf_daughter_level_energy), abs(endf_daughter_level_energy))
                    tolerance = max(self.relative_tol * max_energy, self.absolute_tol)
                    strategy_used = "hybrid(rel)"
            else:
                # Fallback to absolute (should never happen)
                tolerance = self.absolute_tol
                strategy_used = "absolute"
            
            # Check if within tolerance
            if abs_diff <= tolerance:
                matches_within_tol.append((abs_diff, trans, tolerance, ensdf_daughter_level_energy, strategy_used))
            
            # Track best match regardless of tolerance
            if abs_diff < best_diff:
                best_diff = abs_diff
                best_match = (abs_diff, trans, tolerance, ensdf_daughter_level_energy, strategy_used)
        
        # =====================================================================
        # STEP 4: Return best match within tolerance
        # =====================================================================
        if matches_within_tol:
            # Sort by energy difference (ascending)
            matches_within_tol.sort(key=lambda x: x[0])
            abs_diff, trans, tol, ensdf_level_energy, strategy_used = matches_within_tol[0]
            
            # Calculate relative difference
            rel_diff = abs_diff / max(ensdf_level_energy, 1e-6)
            
            # Check for ambiguity (multiple matches)
            ambiguous = len(matches_within_tol) > 1
            
            # Assign quality based on how good the match is
            if abs_diff < tol * 0.1:
                quality = "exact"      # Excellent match (<10% of tolerance)
            elif abs_diff < tol * 0.5:
                quality = "good"       # Good match (<50% of tolerance)
            else:
                quality = "acceptable" # Acceptable match (within tolerance)
            
            if verbose:
                print(f"    ✓ Matched: parent_level={int(trans['parent_level'])}, "
                      f"daughter_level={int(trans['daughter_level'])}")
                print(f"      Level energy difference: {abs_diff/1e3:.2f} keV ({quality}, {strategy_used})")
                print(f"      Tolerance used: {tol/1e3:.2f} keV")
            
            # SUCCESS!
            return MatchResult(
                matched=True,
                parent_level=trans['parent_level'],
                final_level=trans['daughter_level'],  # THIS IS THE KEY OUTPUT!
                ensdf_energy=trans['particle_energy'],
                endf_q_value=endf_particle_energy,
                energy_diff=abs_diff,
                rel_diff=rel_diff,
                match_quality=quality,
                ambiguous=ambiguous,
                daughter_nuclide=daughter_name
            )
        
        # =====================================================================
        # STEP 5: Try relaxed tolerance (marginal matches)
        # =====================================================================
        if best_match:
            abs_diff, trans, tol, ensdf_level_energy, strategy_used = best_match
            
            # Check if within relaxed tolerance (default 5x normal tolerance)
            if abs_diff <= tol * self.relaxed_factor:
                rel_diff = abs_diff / max(ensdf_level_energy, 1e-6)
                
                if verbose:
                    print(f"    ~ Marginal match: {abs_diff/1e3:.2f} keV ({strategy_used}, relaxed)")
                    print(f"      Relaxed tolerance: {tol * self.relaxed_factor / 1e3:.2f} keV")
                
                # Marginal success (use with caution!)
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
        
        # =====================================================================
        # STEP 6: Return failure
        # =====================================================================
        if verbose and best_match:
            _, _, tol, _, strategy_used = best_match
            print(f"    ✗ No match (best: {best_diff/1e3:.2f} keV exceeds "
                  f"{strategy_used} tolerance {tol/1e3:.2f} keV)")
        
        # FAILURE: No match within (relaxed) tolerance
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
        """
        Match all ENDF transitions to ENSDF levels.
        
        This is the main entry point for batch matching!
        
        Process:
        -------
        1. Print matching configuration (tolerances, strategy)
        2. Loop through all ENDF entries
        3. For each entry, call _find_matching_transition()
        4. Store results in matched_decay_df
        5. Print comprehensive statistics
        
        Args:
            energy_column: Column to use for ENDF energy ("Endpoint_energy" or "Average_energy")
        
        Returns:
            DataFrame with matched ENDF data (stored in self.matched_decay_df)
        """
        # =====================================================================
        # Print configuration
        # =====================================================================
        print("\n" + "="*70)
        print("ENDF-ENSDF TRANSITION MATCHING")
        print("="*70)
        print(f"Strategy: {self.strategy.value}")
        print(f"  • Absolute tolerance: {self.absolute_tol/1e3:.3f} keV")
        print(f"  • Relative tolerance: {self.relative_tol*100:.4f}%")
        if self.strategy == MatchStrategy.HYBRID:
            print(f"  • Hybrid threshold: {self.hybrid_threshold/1e3:.1f} keV")
            print(f"    (use absolute below threshold, relative above)")
        print(f"  • Relaxed factor: {self.relaxed_factor}x (for marginal matches)")
        print(f"\nTotal ENDF decays: {len(self.endf_decay_df)}")
        print("="*70 + "\n")
        
        # Initialize result storage
        self.match_results = []      # List of MatchResult objects
        self.unmatched_decays = []   # List of failed matches
        
        # =====================================================================
        # Prepare DataFrame with result columns
        # =====================================================================
        endf_reset = self.endf_decay_df.reset_index()
        
        # Add columns for storing match results
        endf_reset['parent_level_matched'] = np.nan    # ENSDF parent level
        endf_reset['final_level_matched'] = np.nan     # ENSDF daughter level (KEY!)
        endf_reset['match_quality'] = 'unknown'        # Quality string
        endf_reset['match_ambiguous'] = False          # Ambiguity flag
        endf_reset['energy_difference_keV'] = np.nan   # Energy difference
        endf_reset['daughter_nuclide'] = ''            # Daughter name
        
        matched_count = 0
        
        # =====================================================================
        # Loop through all ENDF entries
        # =====================================================================
        for idx, row in endf_reset.iterrows():
            # Extract ENDF entry information
            parent_a = int(row['A'])
            parent_z = int(row['Z'])
            parent_level = float(row['parentLevel'])
            decay_mode = str(row['decay_mode'])
            parent_name = row.get('Parent', f"{parent_a}-{parent_z}")
            
            # Get ENDF energy (prefer endpoint, fall back to average)
            endf_energy = row.get(energy_column, np.nan)
            if pd.isna(endf_energy):
                alt_col = 'Average_energy' if energy_column == 'Endpoint_energy' else 'Endpoint_energy'
                endf_energy = row.get(alt_col, np.nan)
            
            # Skip if no energy data
            if pd.isna(endf_energy):
                self.unmatched_decays.append(row.to_dict())
                endf_reset.at[idx, 'match_quality'] = 'no_endf_energy'
                continue
            
            # Print verbose output for first 3 entries (for verification)
            verbose = idx < 3
            
            # -------------------------------------------------------------
            # Check for placeholder data (ENDF missing/uncertain values)
            # -------------------------------------------------------------
            intensity = row.get('Intensity', np.nan)
            
            if self._is_placeholder(endf_energy, intensity):
                self.placeholder_count += 1
                
                # Verbose output for first few placeholders
                if verbose:
                    print(f"\n  ⚠ Placeholder detected: {parent_name}")
                    print(f"    ENDF energy: {endf_energy:.2e} eV (< 100 eV threshold)")
                
                # Try to use ENSDF Q_ground as replacement
                key = (parent_a, parent_z, decay_mode)
                
                if key in self.transition_lookup and key in self.q_ground_lookup:
                    # ENSDF data available - find best transition match
                    q_ground = self.q_ground_lookup[key]
                    transitions = self.transition_lookup[key]
                    daughter_a, daughter_z = self._get_daughter_nucleus(parent_a, parent_z, decay_mode)
                    daughter_elem = ATOMIC_SYMBOL.get(daughter_z, f'Z{daughter_z}')
                    daughter_name = f"{daughter_elem}-{daughter_a}"
                    
                    # Strategy: Use dominant (highest particle energy) ground state transition
                    # This represents the most probable decay path when ENDF has no data
                    best_transition = None
                    best_energy = 0
                    
                    for trans in transitions:
                        if trans['parent_level'] == 0:  # From parent ground state
                            if trans['particle_energy'] > best_energy:
                                best_energy = trans['particle_energy']
                                best_transition = trans
                    
                    if best_transition:
                        # Use the dominant transition's daughter level
                        matched_level = best_transition['daughter_level']
                        particle_energy = best_transition['particle_energy']
                        
                        if verbose:
                            print(f"    → Matched to ENSDF dominant transition:")
                            print(f"       Daughter level: {matched_level}")
                            print(f"       Particle energy: {particle_energy/1e3:.2f} keV")
                        
                        match = MatchResult(
                            matched=True,
                            parent_level=0.0,
                            final_level=float(matched_level),
                            ensdf_energy=particle_energy,
                            endf_q_value=endf_energy,
                            energy_diff=np.nan,
                            rel_diff=np.nan,
                            match_quality="placeholder_replaced",
                            ambiguous=False,
                            daughter_nuclide=daughter_name
                        )
                        
                        self.placeholder_replaced += 1
                        
                        # Store in DataFrame
                        endf_reset.at[idx, 'parent_level_matched'] = 0.0
                        endf_reset.at[idx, 'final_level_matched'] = float(matched_level)
                        endf_reset.at[idx, 'match_quality'] = "placeholder_replaced"
                        endf_reset.at[idx, 'daughter_nuclide'] = daughter_name
                        matched_count += 1
                    else:
                        # No ground state transitions - use Q_ground to ground state
                        if verbose:
                            print(f"    → Using ENSDF Q_ground: {q_ground/1e3:.2f} keV")
                            print(f"    → Assuming decay to ground state (level 0)")
                        
                        match = MatchResult(
                            matched=True,
                            parent_level=0.0,
                            final_level=0.0,
                            ensdf_energy=q_ground,
                            endf_q_value=endf_energy,
                            energy_diff=np.nan,
                            rel_diff=np.nan,
                            match_quality="placeholder_replaced",
                            ambiguous=False,
                            daughter_nuclide=daughter_name
                        )
                        
                        self.placeholder_replaced += 1
                        
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
            
            # -------------------------------------------------------------
            # CALL MATCHING FUNCTION
            # -------------------------------------------------------------
            match = self._find_matching_transition(
                parent_a, parent_z, parent_level, decay_mode,
                endf_energy, parent_name, verbose=verbose
            )
            self.match_results.append(match)
            
            # -------------------------------------------------------------
            # Store results in DataFrame
            # -------------------------------------------------------------
            if match.matched:
                # SUCCESS: Store matched level information
                endf_reset.at[idx, 'parent_level_matched'] = match.parent_level
                endf_reset.at[idx, 'final_level_matched'] = match.final_level  # KEY OUTPUT!
                endf_reset.at[idx, 'match_quality'] = match.match_quality
                endf_reset.at[idx, 'match_ambiguous'] = match.ambiguous
                endf_reset.at[idx, 'energy_difference_keV'] = match.energy_diff / 1e3
                endf_reset.at[idx, 'daughter_nuclide'] = match.daughter_nuclide
                matched_count += 1
            else:
                # FAILURE: Store diagnostic information
                endf_reset.at[idx, 'match_quality'] = match.match_quality
                if not pd.isna(match.energy_diff):
                    endf_reset.at[idx, 'energy_difference_keV'] = match.energy_diff / 1e3
                endf_reset.at[idx, 'daughter_nuclide'] = match.daughter_nuclide
                
                # Track unmatched decays (except "no ENSDF data" cases)
                if match.match_quality not in ["no_ensdf_data"]:
                    self.unmatched_decays.append(row.to_dict())
        
        # =====================================================================
        # Calculate and print statistics
        # =====================================================================
        # Count matches by quality
        exact = sum(1 for m in self.match_results if m.match_quality == "exact")
        good = sum(1 for m in self.match_results if m.match_quality == "good")
        acceptable = sum(1 for m in self.match_results if m.match_quality == "acceptable")
        marginal = sum(1 for m in self.match_results if m.match_quality == "marginal")
        replaced = sum(1 for m in self.match_results if m.match_quality == "placeholder_replaced")
        assumed = sum(1 for m in self.match_results if m.match_quality == "assumed_ground")
        
        # Count failures by reason
        placeholder_only = sum(1 for m in self.match_results if m.match_quality == "placeholder_data")
        no_ensdf = sum(1 for m in self.match_results if m.match_quality == "no_ensdf_data")
        failed = sum(1 for m in self.match_results if m.match_quality == "failed")
        
        print(f"\nMatching complete!")
        print(f"  ✓ Total matched: {matched_count}/{len(endf_reset)} "
              f"({100*matched_count/len(endf_reset):.1f}%)")
        print(f"\nMatch quality:")
        print(f"  ✓ Exact: {exact}")
        print(f"  ✓ Good: {good}")
        print(f"  ✓ Acceptable: {acceptable}")
        print(f"  ✓ Marginal: {marginal}")
        print(f"  ✓ Placeholder replaced: {replaced}")
        print(f"  ~ Assumed ground: {assumed}")
        print(f"\nFailure breakdown:")
        print(f"  ⚠ Placeholder only: {placeholder_only}")
        print(f"  ✗ No ENSDF data: {no_ensdf}")
        print(f"  ✗ Energy mismatch: {failed}")
        print(f"  Total failed: {placeholder_only + no_ensdf + failed}")
        
        # Print placeholder statistics if any detected
        if self.placeholder_count > 0:
            print(f"\nPlaceholder data handling:")
            print(f"  ENDF placeholders detected:  {self.placeholder_count}")
            print(f"    Replaced with ENSDF:       {self.placeholder_replaced} "
                  f"({100*self.placeholder_replaced/self.placeholder_count:.1f}%)")
            print(f"    No ENSDF available:        {self.placeholder_count - self.placeholder_replaced}")
            print(f"  (Placeholders: ENDF energies < 100 eV, likely missing data)")
        
        # =====================================================================
        # Analyze failed matches
        # =====================================================================
        failed_matches = [m for m in self.match_results 
                         if m.match_quality == "failed" and not np.isnan(m.energy_diff)]
        
        if failed_matches:
            failed_diffs = [m.energy_diff for m in failed_matches]
            
            print(f"\nFailed match energy differences (keV):")
            print(f"  Min:      {np.min(failed_diffs)/1e3:8.3f}")
            print(f"  Median:   {np.median(failed_diffs)/1e3:8.3f}")
            print(f"  Mean:     {np.mean(failed_diffs)/1e3:8.3f}")
            print(f"  Max:      {np.max(failed_diffs)/1e3:8.3f}")
            
            # Count how many would match with relaxed tolerances
            # This helps determine if tolerances need adjustment
            within_10keV = sum(1 for d in failed_diffs if d <= 1e4)
            within_100keV = sum(1 for d in failed_diffs if d <= 1e5)
            within_1MeV = sum(1 for d in failed_diffs if d <= 1e6)
            
            print(f"\nFailed matches that would pass with higher tolerance:")
            print(f"  Within 10 keV:   {within_10keV:4d} "
                  f"({100*within_10keV/len(failed_diffs):.1f}%)")
            print(f"  Within 100 keV:  {within_100keV:4d} "
                  f"({100*within_100keV/len(failed_diffs):.1f}%)")
            print(f"  Within 1 MeV:    {within_1MeV:4d} "
                  f"({100*within_1MeV/len(failed_diffs):.1f}%)")
        print()
        
        # Store result DataFrame
        self.matched_decay_df = endf_reset
        return self.matched_decay_df
    
    def get_statistics(self):
        """
        Calculate aggregate matching statistics.
        
        Returns:
            MatchStatistics object with summary information
        """
        # Handle case where matching hasn't been run yet
        if not self.match_results:
            return MatchStatistics(
                total_decays=0, matched=0, unmatched=0, ambiguous=0,
                exact_matches=0, good_matches=0, marginal_matches=0, success_rate=0.0
            )
        
        # Count various match types
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
        """
        Print summary report of matching results.
        
        Human-readable summary including:
        - Total/matched/unmatched counts
        - Quality breakdown
        - Energy difference statistics
        """
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
        
        # Print energy difference statistics for matched entries
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
        
        This is the primary output of the tool!
        
        Process:
        -------
        1. Copy matched_decay_df
        2. Update parentLevel and final_level columns with ENSDF matches
        3. Recreate MultiIndex structure
        4. Keep only original ENDF columns
        5. Write to formatted ASCII file
        6. Save diagnostics to separate file
        
        Output format matches ENDF DECAY.ascii format but with enriched level data.
        
        Args:
            output_path: Path to output file (e.g., "DECAY_matched.ascii")
        """
        # Check that matching has been run
        if self.matched_decay_df is None:
            raise ValueError("No matched data. Run match_levels() first.")
        
        # =====================================================================
        # Update levels with matched values
        # =====================================================================
        df_out = self.matched_decay_df.copy()
        
        # Replace original levels with matched ENSDF levels (where available)
        df_out.loc[df_out['parent_level_matched'].notna(), 'parentLevel'] = \
            df_out['parent_level_matched']
        df_out.loc[df_out['final_level_matched'].notna(), 'final_level'] = \
            df_out['final_level_matched']  # THIS IS THE KEY UPDATE!
        
        # =====================================================================
        # Recreate MultiIndex (ENDF format)
        # =====================================================================
        idx_cols = ['A', 'Z', 'parentLevel', 'decay_mode', 'final_level']
        df_out = df_out.set_index(idx_cols)
        
        # =====================================================================
        # Keep only original ENDF columns
        # =====================================================================
        original_cols = []
        if 'Parent' in df_out.columns:
            original_cols.append('Parent')
        original_cols += ['Endpoint_energy', 'Average_energy', 'Intensity']
        
        keep_cols = [c for c in original_cols if c in df_out.columns]
        df_out = df_out[keep_cols]
        
        # =====================================================================
        # Write to formatted ASCII file
        # =====================================================================
        with open(output_path, 'w') as f:
            # Write header line (column names)
            index_names = ['A', 'Z', 'parentLevel', 'decay_mode', 'final_level']
            header_spacing = ' ' * 44  # Spacing for index columns
            data_cols = ' '.join([f'{col:>18}' for col in keep_cols])
            f.write(f"{header_spacing}{data_cols}\n")
            
            # Write index names (for reference)
            f.write(f"{' '.join([f'{name:<3}' if i < 2 else f'{name:<15}' for i, name in enumerate(index_names)])}\n")
            
            # Write data rows
            for idx, row in df_out.iterrows():
                # Format index values
                a_val = f"{idx[0]:<4d}"              # Mass number (integer)
                z_val = f"{idx[1]:<4d}"              # Atomic number (integer)
                pl_val = f"{idx[2]:<15.4e}"          # Parent level (scientific notation)
                dm_val = f"{idx[3]:<15}"             # Decay mode (string)
                fl_val = f"{idx[4]:<15.4e}"          # Final level (UPDATED! scientific notation)
                
                # Format data values
                data_vals = []
                for col in keep_cols:
                    val = row[col]
                    if pd.isna(val):
                        data_vals.append(' ' * 18)   # Empty for NaN
                    elif isinstance(val, str):
                        data_vals.append(f"{val:>18}")
                    else:
                        data_vals.append(f"{val:>18.6e}")  # Scientific notation
                
                # Write complete line
                line = f"{a_val}{z_val}{pl_val}{dm_val}{fl_val} {' '.join(data_vals)}\n"
                f.write(line)
        
        print(f"\nSaved matched DECAY data to: {output_path}")
        print(f"  Total entries: {len(df_out)}")
        
        # =====================================================================
        # Save diagnostics
        # =====================================================================
        diag_path = output_path.replace('.ascii', '_diagnostics.ascii')
        self._save_diagnostics(diag_path)
    
    def _save_diagnostics(self, output_path):
        """
        Save matching diagnostics to separate file.
        
        Diagnostics include:
        - Original and matched level numbers
        - Match quality
        - Energy differences
        - Parent and daughter nuclide names
        
        This file is useful for:
        - Validating matches
        - Identifying problematic transitions
        - Tuning tolerances
        
        Args:
            output_path: Path to diagnostics file (e.g., "DECAY_matched_diagnostics.ascii")
        """
        if self.matched_decay_df is None:
            return
        
        df_diag = self.matched_decay_df.copy()
        
        # Select diagnostic columns
        diag_cols = ['A', 'Z', 'parentLevel', 'parent_level_matched', 
                     'final_level', 'final_level_matched', 
                     'Parent', 'daughter_nuclide',
                     'match_quality', 'match_ambiguous', 'energy_difference_keV']
        
        # Keep only columns that exist
        diag_cols = [c for c in diag_cols if c in df_diag.columns]
        df_diag = df_diag[diag_cols]
        
        # Write as space-separated file
        df_diag.to_csv(output_path, sep=' ', float_format='%.4e', na_rep='', index=False)
        print(f"  Diagnostics saved to: {output_path}")
    
    def export_unmatched(self, filename):
        """
        Export list of unmatched decays for investigation.
        
        Useful for:
        - Identifying systematic problems
        - Finding missing ENSDF data
        - Debugging tolerance issues
        
        Args:
            filename: Output file path
        """
        if not self.unmatched_decays:
            print("No unmatched decays to export.")
            return
        
        df = pd.DataFrame(self.unmatched_decays)
        df.to_csv(filename, sep=' ', float_format='%.6e', index=False)
        print(f"Exported {len(self.unmatched_decays)} unmatched decays to {filename}")
    
    def export_match_details(self, filename):
        """
        Export detailed match information for all transitions.
        
        Includes:
        - Parent and daughter nuclides
        - Matched levels
        - ENDF and ENSDF energies
        - Energy differences (absolute and relative)
        - Match quality
        
        Useful for:
        - Statistical analysis
        - Publication-quality data
        - Detailed validation
        
        Args:
            filename: Output file path
        """
        if not self.match_results:
            print("No match results to export.")
            return
        
        # Build detailed data table
        data = []
        for i, result in enumerate(self.match_results):
            # Get corresponding ENDF entry information
            if self.matched_decay_df is not None:
                row_info = self.matched_decay_df.iloc[i]
            else:
                row_info = {}
            
            data.append({
                'Parent': row_info.get('Parent', ''),
                'Daughter': result.daughter_nuclide,
                'decay_mode': row_info.get('decay_mode', ''),
                'matched': int(result.matched),  # 1 or 0
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
    
    # =========================================================================
    # Set up argument parser
    # =========================================================================
    parser = argparse.ArgumentParser(
        description="Match ENDF decay transitions to ENSDF levels"
    )
    
    # Default file paths (update these for your system!)
    default_endf_path = "/Users/audreywarn/fluka-db-audrey/outputs/endf/endf_data_modules/ascii/DECAY.ascii"
    default_ensdf_decay_path = "/Users/audreywarn/fluka-db-audrey/outputs/ensdf/json_data_modules/ascii/DECAY.ascii"
    default_ensdf_level_path = "/Users/audreywarn/fluka-db-audrey/outputs/ensdf/json_data_modules/ascii/LEVEL.ascii"
    
    # Required input files
    parser.add_argument("--endf", default=default_endf_path, 
                       help="Path to ENDF DECAY.ascii")
    parser.add_argument("--ensdf", default=default_ensdf_decay_path, 
                       help="Path to ENSDF DECAY.ascii")
    parser.add_argument("--ensdf-level", default=default_ensdf_level_path, 
                       help="Path to ENSDF LEVEL.ascii")
    
    # Output file
    parser.add_argument("--output", default="DECAY_level_matched.ascii", 
                       help="Output ASCII file")
    
    # Tolerance parameters
    parser.add_argument("--abs-tol", type=float, default=1e3, 
                       help="Absolute tolerance in eV (default: 1 keV = 10^3 eV)")
    parser.add_argument("--rel-tol", type=float, default=1e-3, 
                       help="Relative tolerance (default: 0.1%% = 10^-3)")
    parser.add_argument("--strategy", choices=["absolute", "relative", "hybrid"], 
                       default="hybrid", help="Matching strategy")
    
    # Optional exports
    parser.add_argument("--export-unmatched", 
                       help="Export unmatched decays to ASCII file")
    parser.add_argument("--export-details", 
                       help="Export match details to ASCII file")
    
    args = parser.parse_args()
    
    # =========================================================================
    # Create matcher instance (loads all data)
    # =========================================================================
    matcher = ENDFLevelMatcher(
        endf_decay_path=args.endf, 
        ensdf_decay_path=args.ensdf,
        ensdf_level_path=args.ensdf_level
    )
    
    # =========================================================================
    # Set tolerances (optional customization)
    # =========================================================================
    matcher.set_tolerances(
        absolute_tol=args.abs_tol, 
        relative_tol=args.rel_tol, 
        strategy=args.strategy
    )
    
    # =========================================================================
    # Run matching algorithm
    # =========================================================================
    matched_df = matcher.match_levels()
    
    # =========================================================================
    # Print and save results
    # =========================================================================
    matcher.print_report()
    matcher.save_matched_decay(args.output)
    
    # =========================================================================
    # Optional exports
    # =========================================================================
    if args.export_unmatched:
        matcher.export_unmatched(args.export_unmatched)
    
    if args.export_details:
        matcher.export_match_details(args.export_details)
    
    print("\nLevel matching complete!")
