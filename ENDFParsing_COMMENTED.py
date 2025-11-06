#!/usr/bin/env python3
"""
================================================================================
ENDFParsing.py - HIGH-LEVEL DATABASE ADAPTER FOR ENDF DECAY DATA
================================================================================

PURPOSE:
--------
This module serves as a CRITICAL BRIDGE between raw ENDF-6 format data and the 
existing database/DataModule infrastructure. It transforms low-level ENDF data
into pandas DataFrames that match the database schema.

ARCHITECTURE OVERVIEW:
---------------------

┌─────────────────────────────────────────────────────────────────────────┐
│                      DATA FLOW ARCHITECTURE                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ENDF Files                                                              │
│  (Raw ENDF-6 format)                                                     │
│       │                                                                  │
│       ├─> 80-character fixed-width lines                                │
│       ├─> MF=8 MT=457 sections (decay data)                             │
│       └─> E-less notation (1.234+5)                                     │
│           │                                                              │
│           ↓                                                              │
│  ┌─────────────────────────────────────┐                               │
│  │   JEFF_ENDF_parser.py               │ ← LOW-LEVEL PARSER            │
│  │   (ENDFNumericDecayParser)          │                               │
│  └─────────────────────────────────────┘                               │
│           │                                                              │
│           ├─> Parses fixed-width lines                                  │
│           ├─> Extracts ALL ENDF fields                                  │
│           └─> Returns Python dictionaries                               │
│               {                                                          │
│                 "ZA": 95241,                                             │
│                 "T1/2": (1.36e10, 0),                                    │
│                 "modes": [{RTYP: 4.0, BR: (1.0, 0), ...}],              │
│                 "spectra": [{STYP: 4, ER_AV: (5.486e6, 0), ...}]        │
│               }                                                          │
│           │                                                              │
│           ↓                                                              │
│  ┌─────────────────────────────────────┐                               │
│  │   ENDFParsing.py (THIS FILE!)      │ ← HIGH-LEVEL ADAPTER           │
│  │   (ENDFDataModule + DecayData)     │                                │
│  └─────────────────────────────────────┘                               │
│           │                                                              │
│           ├─> Wraps raw ENDF dictionaries                               │
│           ├─> Maps STYP energies to decay modes                         │
│           ├─> Splits EC/B+ properly                                     │
│           ├─> Converts to ENSDF notation                                │
│           ├─> Filters important decay modes                             │
│           └─> Creates pandas DataFrames with proper schema              │
│               │                                                          │
│               ├─> DECAY DataFrame:                                       │
│               │   MultiIndex: [A, Z, parentLevel, decay_mode, final_level]│
│               │   Columns: [Parent, Endpoint_energy, Average_energy,    │
│               │             Intensity]                                   │
│               │                                                          │
│               └─> NUCLIDE DataFrame:                                     │
│                   MultiIndex: [A, Z, level]                              │
│                   Columns: [Nuclide, Half_life, hl_unit]                │
│           │                                                              │
│           ↓                                                              │
│  ┌─────────────────────────────────────┐                               │
│  │   Database.py                       │ ← DATABASE LAYER               │
│  │   (populate_DM_from_endf_data)     │                                │
│  └─────────────────────────────────────┘                               │
│           │                                                              │
│           ├─> Sets multi-index on DataFrames                            │
│           ├─> Validates schema                                          │
│           └─> Stores in DataModule objects                              │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘

WHY THIS MODULE IS NECESSARY:
-----------------------------

1. **FORMAT MISMATCH**: 
   - JEFF_ENDF_parser outputs raw ENDF data structure (nested dicts)
   - Database expects pandas DataFrames with specific columns/indices
   - This module TRANSFORMS one format to the other

2. **SCHEMA COMPATIBILITY**:
   - Database schema was designed for ENSDF data
   - ENDF has different field names, units, and structure
   - This module MAPS ENDF fields to database schema:
     * ENDF "RTYP=4.0" → Database "a" (alpha)
     * ENDF "STYP=1, ER_AV" → Database "Average_energy" for "B-"
     * ENDF "BR" (0-1) → Database "Intensity" (0-100%)

3. **DATA ENRICHMENT**:
   - Splits EC/B+ into separate database entries
   - Maps spectrum energies (STYP) to correct decay modes
   - Converts ENDF notation to ENSDF notation
   - Filters out unimportant decay modes

4. **MULTI-SOURCE SUPPORT**:
   - Database can handle both ENSDF and ENDF sources
   - Both produce the SAME DataFrame structure
   - Database code doesn't need to know the source

5. **BUSINESS LOGIC**:
   - Which decay modes are "important"?
   - How to handle EC/B+ splitting?
   - What notation to use?
   - These decisions are isolated HERE, not in low-level parser

WITHOUT THIS MODULE:
-------------------
You would need to either:
1. Rewrite the entire database to understand ENDF format (BAD!)
2. Put database logic in the low-level parser (VERY BAD!)
3. Write custom integration code everywhere (UNMAINTAINABLE!)

WITH THIS MODULE:
----------------
- Clean separation of concerns
- Low-level parser is format-focused
- High-level adapter is schema-focused
- Database remains source-agnostic
- Easy to add new data sources

FIXED VERSION: Properly splits EC/B+ decay + NO logft column.
UPDATED: Default pattern to parse .endf files.
UPDATED: Handles both 75-char and 80-char ENDF line formats.
UPDATED: Extracts energies for ALL STYP types (0,1,2,4,8,9)
"""

import numpy as np
import pandas as pd
from pathlib import Path
from typing import List, Dict, Optional
import sys
import os

# ============================================================================
# STEP 1: IMPORT THE LOW-LEVEL ENDF PARSER
# ============================================================================
# We depend on JEFF_ENDF_parser.py for the actual ENDF-6 format parsing.
# That module handles the fixed-width line reading, E-less notation, etc.
# We just CONSUME its output and transform it for the database.

current_dir = os.path.dirname(os.path.abspath(__file__))
pyclasses_dir = os.path.join(current_dir, 'PyClasses')
if os.path.exists(pyclasses_dir) and pyclasses_dir not in sys.path:
    sys.path.insert(0, pyclasses_dir)

# Import the low-level ENDF parser
try:
    from JEFF_ENDF_parser import ENDFNumericDecayParser, extract_bplus_branching
except ImportError:
    try:
        from PyClasses.JEFF_ENDF_parser import ENDFNumericDecayParser, extract_bplus_branching
    except ImportError:
        print("Error: JEFF_ENDF_parser module not found.")
        print(f"Searched in: {current_dir} and {pyclasses_dir}")
        print("Please ensure JEFF_ENDF_parser.py is in the same directory or in PyClasses/")
        sys.exit(1)

# Atomic symbols (shared with JEFF parser)
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


# ============================================================================
# STEP 2: DecayData CLASS - ENDF DICTIONARY → DATABASE-READY OBJECT
# ============================================================================

class DecayData:
    """
    CRITICAL ADAPTER CLASS: Wraps raw ENDF dictionary and extracts database fields.
    
    ROLE IN PIPELINE:
    -----------------
    1. INPUT: Raw dictionary from JEFF_ENDF_parser (ENDF-6 structure)
    2. PROCESS: 
       - Extracts nuclide identification (Z, A, element)
       - Decodes decay modes from RTYP values
       - Maps spectrum energies (STYP) to decay modes
       - Handles ALL spectrum types: Beta-, Beta+, Alpha, Gamma, X-ray, Auger
    3. OUTPUT: Object with database-compatible attributes
    
    KEY TRANSFORMATIONS:
    -------------------
    - ENDF RTYP (4.0) → ENSDF notation ('a' for alpha)
    - ENDF STYP energies → Mapped to correct decay modes
    - ENDF branching ratios (0-1) → Percentages (0-100)
    - Spectrum data → average_energies and endpoint_energies dicts
    
    WHY THIS IS NEEDED:
    ------------------
    The raw ENDF dictionary structure is:
      {"ZA": 95241, "modes": [...], "spectra": [...]}
    
    But the database needs:
      - parent_A, parent_Z, element (separate fields)
      - decay_modes dict: {"a": 100.0}  (ENSDF notation, percentages)
      - average_energies dict: {"a": 5486000}  (mapped by mode)
      - endpoint_energies dict: {"a": 5486000}  (mapped by mode)
    
    This class performs that transformation.
    """
    
    def __init__(self, jeff_dict):
        """
        Initialize from JEFF parser dictionary output.
        
        TRANSFORMATION PIPELINE:
        -----------------------
        1. Extract basic nuclide info (Z, A, element)
        2. Extract half-life
        3. Decode decay modes from RTYP → ENSDF notation
        4. Map spectrum energies (STYP) to decay modes
        5. Handle all 6 spectrum types (STYP 0,1,2,4,8,9)
        """
        # Store original parsed data for later use
        self.jeff_dict = jeff_dict
        
        # ====================================================================
        # NUCLIDE IDENTIFICATION
        # ====================================================================
        # ENDF stores: ZA = Z*1000 + A (e.g., 95241 for Am-241)
        # Database needs: separate A, Z, and element symbol
        
        self.parent_A = int(jeff_dict["ZA"] % 1000)  # Mass number
        self.parent_Z = int(jeff_dict["ZA"] // 1000)  # Atomic number
        self.parent_level_energy = float(0.0)  # JEFF doesn't provide this
        self.element = ATOMIC_SYMBOL.get(self.parent_Z, f'Z{self.parent_Z}')
        
        # ====================================================================
        # HALF-LIFE EXTRACTION
        # ====================================================================
        # ENDF stores: T1/2 in seconds (may be tuple with uncertainty)
        # Database needs: float value in seconds + unit string
        
        if "T1/2" in jeff_dict and jeff_dict["T1/2"]:
            hl_val = jeff_dict["T1/2"][0] if isinstance(jeff_dict["T1/2"], tuple) else jeff_dict["T1/2"]
            self.half_life = float(hl_val)
            self.hl_unit = 's'
        else:
            self.half_life = float(0.0)
            self.hl_unit = 's'
        
        # ====================================================================
        # DECAY MODE DECODING (RTYP → ENSDF NOTATION)
        # ====================================================================
        # ENDF stores: RTYP codes (0=gamma, 1=beta-, 2=EC/B+, 4=alpha, etc.)
        # Database needs: ENSDF strings ("B-", "EC/B+", "a", etc.)
        #
        # Example transformations:
        #   RTYP=1.0 → "B-" (beta minus)
        #   RTYP=2.0 → "EC/B+" (electron capture / positron emission)
        #   RTYP=4.0 → "a" (alpha, lowercase per ENSDF convention)
        #   RTYP=1.5 → "B-n" (delayed neutron emission)
        
        self.decay_modes = {}
        if "modes" in jeff_dict:
            for mode in jeff_dict["modes"]:
                # Decode RTYP to mode string using our decoder
                mode_str = self._decode_rtyp(mode["RTYP"])
                
                # Extract branching ratio
                br = mode["BR"][0] if isinstance(mode["BR"], tuple) else mode["BR"]
                
                # Convert to percentage if needed (ENDF uses 0-1, database uses 0-100)
                br_pct = float(br * 100.0 if br <= 1.0 else br)
                
                self.decay_modes[mode_str] = br_pct
        
        # ====================================================================
        # ENERGY EXTRACTION (SPECTRUM DATA → DECAY MODE MAPPING)
        # ====================================================================
        # CRITICAL SECTION: This is where energies get mapped to decay modes!
        #
        # ENDF structure:
        #   "spectra": [
        #     {
        #       "STYP": 4,  ← Spectrum type (4 = alpha particles)
        #       "ER_AV": (5486000, 0),  ← Mean energy in eV
        #       "discrete": [...]  ← Individual transitions
        #     }
        #   ]
        #
        # Database needs:
        #   average_energies = {"a": 5486000}  ← Energy mapped to mode "a"
        #   endpoint_energies = {"a": 5486000}  ← Endpoint mapped to mode "a"
        #
        # The STYP → Mode mapping:
        #   STYP=0 → gamma (but stored separately, not in decay_modes)
        #   STYP=1 → B- (beta minus)
        #   STYP=2 → B+ or EC/B+ (beta plus)
        #   STYP=4 → a (alpha)
        #   STYP=8 → X-rays (not a decay mode, characteristic radiation)
        #   STYP=9 → Auger electrons (not a decay mode, atomic process)
        
        self.endpoint_energies = {}
        self.average_energies = {}
        
        if "spectra" in jeff_dict:
            for spec in jeff_dict["spectra"]:
                styp = spec.get("STYP", -1)
                
                # ============================================================
                # MEAN ENERGY EXTRACTION (ER_AV field)
                # ============================================================
                # ER_AV is the average/mean energy for this spectrum type
                # We map it to the corresponding decay mode(s)
                
                if "ER_AV" in spec and spec["ER_AV"]:
                    avg_e = spec["ER_AV"][0] if isinstance(spec["ER_AV"], tuple) else spec["ER_AV"]
                    avg_e = float(avg_e)
                    
                    # Map STYP to mode string and store energy
                    if styp == 1:  # Beta- particles
                        for mode_str in self.decay_modes:
                            if mode_str.startswith('B-') or mode_str.startswith('β-'):
                                self.average_energies[mode_str] = avg_e
                    
                    elif styp == 2:  # Beta+ particles
                        for mode_str in self.decay_modes:
                            if mode_str.startswith('B+') or mode_str.startswith('EC/B+'):
                                self.average_energies[mode_str] = avg_e
                    
                    elif styp == 4:  # Alpha particles
                        for mode_str in self.decay_modes:
                            if mode_str.startswith('a') or mode_str.startswith('α'):
                                self.average_energies[mode_str] = avg_e
                    
                    elif styp == 0:  # Gamma rays
                        # Gamma is not a decay mode, but we store it separately
                        self.average_energies['gamma'] = avg_e
                
                # ============================================================
                # ENDPOINT/DISCRETE ENERGY EXTRACTION
                # ============================================================
                # For beta spectra, ER is the endpoint (maximum) energy
                # For alpha, ER is the discrete alpha group energy
                # We extract these from the first discrete transition
                
                # Beta- discrete transitions
                if styp == 1 and "discrete" in spec and spec["discrete"]:
                    for disc in spec["discrete"]:
                        if "ER" in disc:
                            endpoint = disc["ER"][0] if isinstance(disc["ER"], tuple) else disc["ER"]
                            endpoint = float(endpoint)
                            for mode_str in self.decay_modes:
                                if mode_str.startswith('B-') or mode_str.startswith('β-'):
                                    self.endpoint_energies[mode_str] = endpoint
                                    break
                
                # Beta+ discrete transitions
                elif styp == 2 and "discrete" in spec and spec["discrete"]:
                    for disc in spec["discrete"]:
                        if "ER" in disc:
                            endpoint = disc["ER"][0] if isinstance(disc["ER"], tuple) else disc["ER"]
                            endpoint = float(endpoint)
                            for mode_str in self.decay_modes:
                                if mode_str.startswith('B+') or mode_str.startswith('EC/B+'):
                                    self.endpoint_energies[mode_str] = endpoint
                                    break
                
                # Alpha discrete transitions
                elif styp == 4 and "discrete" in spec and spec["discrete"]:
                    # For alpha, only set if not already set by ER_AV
                    # (ER_AV is preferred as it's the mean of all alpha groups)
                    for disc in spec["discrete"]:
                        if "ER" in disc:
                            alpha_energy = disc["ER"][0] if isinstance(disc["ER"], tuple) else disc["ER"]
                            alpha_energy = float(alpha_energy)
                            for mode_str in self.decay_modes:
                                if mode_str.startswith('a') or mode_str.startswith('α'):
                                    # Only set if not already set by ER_AV
                                    if mode_str not in self.average_energies:
                                        self.average_energies[mode_str] = alpha_energy
                                    if mode_str not in self.endpoint_energies:
                                        self.endpoint_energies[mode_str] = alpha_energy
                                    break
    
    def _decode_rtyp(self, rtyp):
        """
        Decode ENDF RTYP decay mode codes to ENSDF notation.
        
        CRITICAL TRANSFORMATION: ENDF codes → Database strings
        
        ENDF RTYP format:
        ----------------
        Integer part = primary decay mode
        Decimal part = secondary particle emission
        
        Particle codes:
          0 = γ (gamma)
          1 = β- (beta minus)
          2 = EC/β+ (electron capture / positron)
          3 = IT (isomeric transition)
          4 = α (alpha)
          5 = n (neutron)
          6 = SF (spontaneous fission)
          7 = p (proton)
        
        Examples:
          RTYP=1.0 → "B-" (beta minus)
          RTYP=2.0 → "EC/B+" (EC/positron, will be split later)
          RTYP=4.0 → "a" (alpha, lowercase per ENSDF)
          RTYP=1.5 → "B-n" (beta minus + neutron = delayed neutron)
          RTYP=2.7 → "B+p" (positron + proton)
        
        ENSDF notation rules:
        --------------------
        - No commas between particles
        - Lowercase for particles: a, p, n (NOT A, P, N)
        - Examples: B-a, B+p, ECn, B-n
        
        WHY THIS MATTERS:
        ----------------
        The database schema expects ENSDF notation strings.
        ENDF uses numeric codes.
        This function bridges that gap.
        """
        particle_map = {
            0: "γ", 1: "B-", 2: "EC/B+", 3: "IT",
            4: "a", 5: "n", 6: "SF", 7: "p"  # lowercase a, n, p per ENSDF
        }
        
        # Handle simple integer modes
        simple_modes = {
            0.0: "γ", 1.0: "B-", 2.0: "EC/B+", 3.0: "IT",
            4.0: "a", 5.0: "n", 6.0: "SF", 7.0: "p"
        }
        
        rtyp_float = float(rtyp)
        
        if rtyp_float in simple_modes:
            return simple_modes[rtyp_float]
        
        # Decode combined mode (e.g., 1.5 = beta- + neutron)
        primary = int(rtyp_float)
        secondary = int(round((rtyp_float - primary) * 10))
        
        primary_label = particle_map.get(primary, str(primary))
        secondary_label = particle_map.get(secondary, str(secondary))
        
        # Return without comma (ENSDF notation: "B-n" not "B-,n")
        return f"{primary_label}{secondary_label}"


# ============================================================================
# STEP 3: ENDFDataModule CLASS - MAIN DATABASE ADAPTER
# ============================================================================

class ENDFDataModule:
    """
    PRIMARY DATABASE ADAPTER: Converts ENDF files to database-ready DataFrames.
    
    *** THIS IS THE KEY CLASS THAT MAKES ENDF DATA WORK WITH THE DATABASE ***
    
    ROLE IN PIPELINE:
    ----------------
    1. INPUT: ENDF files (via JEFF_ENDF_parser)
    2. PROCESS:
       a) Parse ENDF → raw dictionaries (via DecayData wrapper)
       b) Apply business logic (EC/B+ splitting, mode filtering, notation conversion)
       c) Build pandas DataFrames with database schema
    3. OUTPUT: DataFrames ready for Database.populate_DM_from_endf_data()
    
    KEY OUTPUT DATAFRAMES:
    ---------------------
    
    1. DECAY DataFrame:
       Purpose: Store individual decay channels (mode + energy + intensity)
       Schema:
         - MultiIndex: [A, Z, parentLevel, decay_mode, final_level]
         - Columns: [Parent, Endpoint_energy, Average_energy, Intensity]
       Example row:
         (241, 95, 0.0, 'a', 0.0) → ['Am-241', 5486000, 5486000, 100.0]
    
    2. NUCLIDE DataFrame:
       Purpose: Store nuclide properties (half-life, etc.)
       Schema:
         - MultiIndex: [A, Z, level]
         - Columns: [Nuclide, Half_life, hl_unit]
       Example row:
         (241, 95, 0.0) → ['Am-241', 1.36e10, 's']
    
    WHY THIS SCHEMA?
    ---------------
    The database was originally designed for ENSDF data, which uses this exact
    structure. By transforming ENDF data to match, we ensure:
    1. Database code doesn't need modification
    2. Both ENSDF and ENDF sources work identically
    3. Downstream code is source-agnostic
    
    CRITICAL TRANSFORMATIONS PERFORMED:
    ----------------------------------
    1. EC/B+ SPLITTING:
       - ENDF stores total EC/B+ branching ratio
       - Database needs separate EC and B+ entries
       - We split using extract_bplus_branching()
    
    2. MODE FILTERING:
       - ENDF includes all modes (including trivial ones)
       - Database wants only "important" decay modes
       - We filter using _is_important_decay_mode()
    
    3. NOTATION CONVERSION:
       - ENDF: "EC/B+,A" (uppercase, commas)
       - ENSDF: "EC/B+a" (lowercase, no commas)
       - We convert using _convert_to_ensdf_notation()
    
    4. ENERGY MAPPING:
       - ENDF: Energies in spectrum records (STYP-based)
       - Database: Energies attached to decay modes
       - We map using DecayData class
    
    5. UNIT CONVERSION:
       - ENDF: Energies in eV, branching as 0-1
       - Database: Energies in eV, branching as 0-100%
       - We handle in DecayData and _parse_to_dataframes()
    """
    
    def __init__(self):
        """Initialize empty data structures."""
        self.decay_data = []  # List of DecayData objects (one per nuclide/level)
        self.nuclide_data = []  # Same as decay_data (for compatibility)
        self.source_files = []  # List of source file paths
    
    def load_from_endf_files(self, endf_dir: str, file_pattern: str = "*.endf"):
        """
        Load ENDF files from a directory or single file.
        
        FLEXIBLE INPUT HANDLING:
        -----------------------
        - Accepts single large file (JEFF-4.0 format)
        - Accepts directory of individual files (ENDF-B-VIII.0 format)
        - Auto-detects which mode based on path
        
        FILE FORMAT COMPATIBILITY:
        -------------------------
        - Handles 75-character lines (no sequence numbers)
        - Handles 80-character lines (with sequence numbers)
        - Auto-pads short lines to 80 characters
        
        SECTION DETECTION:
        -----------------
        - Scans for MF=8 MT=457 sections (radioactive decay data)
        - Uses MF/MT transition tracking (robust!)
        - Doesn't rely on sequence numbers (which may be missing)
        
        PARSING WORKFLOW:
        ----------------
        1. Find all ENDF files
        2. For each file:
           a) Read all lines
           b) Scan for MF=8 MT=457 section starts
           c) For each section:
              - Use JEFF_ENDF_parser to parse
              - Wrap result in DecayData object
              - Store in self.decay_data list
        
        Args:
            endf_dir: Path to directory OR single ENDF file
            file_pattern: Glob pattern for directory mode (default: "*.endf")
        """
        endf_path = Path(endf_dir)
        
        if not endf_path.exists():
            raise FileNotFoundError(f"ENDF path not found: {endf_dir}")
        
        # Check if path is a file or directory
        if endf_path.is_file():
            # Single file mode (JEFF-4.0 format)
            endf_files = [endf_path]
            print(f"\nProcessing single ENDF file: {endf_path.name}")
        else:
            # Directory mode (ENDF-B-VIII.0 format)
            endf_files = sorted(list(endf_path.glob(file_pattern)))
            endf_files = [f for f in endf_files if f.is_file()]
            
            if not endf_files:
                raise ValueError(f"No ENDF files found in {endf_dir} matching pattern '{file_pattern}'")
            
            print(f"\nFound {len(endf_files)} ENDF files in {endf_dir}")
        
        # Process each file
        for file_path in endf_files:
            try:
                print(f"  Parsing: {file_path.name}")
                
                # Read entire file
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                
                # ============================================================
                # SECTION DETECTION: Find all MF=8 MT=457 sections
                # ============================================================
                # ENDF line structure (80 characters):
                #   Columns 67-70: MAT (material number)
                #   Columns 71-72: MF (file type, 8=decay)
                #   Columns 73-75: MT (section type, 457=decay)
                #   Columns 76-80: Sequence number (may be missing!)
                #
                # ROBUST STRATEGY:
                # We track when (MF, MT) transitions to (8, 457).
                # This works regardless of sequence numbers!
                
                section_positions = []
                seen_sections = set()  # Avoid duplicates: (MAT, MF, MT)
                prev_mf, prev_mt = None, None
                
                for i, line in enumerate(lines):
                    # Pad line to 80 characters if needed (ENDF standard)
                    # This handles both 75-char and 80-char files!
                    line_padded = f"{line:<80}" if len(line) < 80 else line
                    
                    if len(line_padded) >= 75:
                        try:
                            # Extract MAT, MF, MT from fixed columns
                            mat = int(line_padded[66:70].strip() or 0)
                            mf = int(line_padded[70:72].strip() or 0)
                            mt = int(line_padded[72:75].strip() or 0)
                            
                            # Detect section start: MF/MT just changed to 8/457
                            if mf == 8 and mt == 457 and (prev_mf != 8 or prev_mt != 457):
                                section_key = (mat, mf, mt)
                                if section_key not in seen_sections:
                                    section_positions.append((i, mat))
                                    seen_sections.add(section_key)
                            
                            prev_mf, prev_mt = mf, mt
                        except:
                            continue
                
                if not section_positions:
                    print(f"    No decay data found in {file_path.name}")
                    continue
                
                print(f"    Found {len(section_positions)} decay section(s)")
                
                # ============================================================
                # PARSE EACH SECTION
                # ============================================================
                for start_pos, mat_num in section_positions:
                    try:
                        # Use JEFF_ENDF_parser to parse this section
                        parser = ENDFNumericDecayParser()
                        parser.load_file(str(file_path))
                        parser._pos = start_pos  # Jump to section start
                        
                        # Parse this section → raw dictionary
                        result = parser._parse_mf8_mt457()
                        result["MAT"] = mat_num
                        
                        # Wrap in DecayData object → database-compatible
                        decay_obj = DecayData(result)
                        self.decay_data.append(decay_obj)
                        
                        za = result["ZA"]
                        lis = result["LIS"]
                        print(f"      Parsed MAT={mat_num}, ZA={za}, LIS={lis}")
                        
                    except Exception as e:
                        print(f"      Warning: Failed to parse MAT={mat_num}: {e}")
                        continue
                
                self.source_files.append(str(file_path))
                    
            except Exception as e:
                print(f"    Warning: Failed to process {file_path.name}: {e}")
                continue
        
        print(f"\nLoaded {len(self.decay_data)} decay entries from {len(self.source_files)} files")
    
    def _convert_to_ensdf_notation(self, mode):
        """
        Convert ENDF decay mode notation to ENSDF notation.
        
        NOTATION DIFFERENCES:
        --------------------
        ENDF: "B-,A", "EC,p", "B+,n" (commas, uppercase A)
        ENSDF: "B-a", "ECp", "B+n" (no commas, lowercase a)
        
        WHY THIS MATTERS:
        ----------------
        The database expects ENSDF notation (legacy from ENSDF data source).
        ENDF files use slightly different notation.
        We must convert to maintain consistency.
        
        Args:
            mode: Decay mode string in ENDF notation
            
        Returns:
            Decay mode string in ENSDF notation
        """
        if not mode:
            return mode
        
        # Remove commas
        ensdf_mode = mode.replace(',', '')
        
        # Convert uppercase A (alpha) to lowercase a
        ensdf_mode = ensdf_mode.replace('A', 'a')
        
        return ensdf_mode
    
    def _is_important_decay_mode(self, mode):
        """
        Filter decay modes: Which ones should be included in the database?
        
        BUSINESS LOGIC DECISION:
        -----------------------
        ENDF includes ALL possible decay modes, even trivial ones.
        The database only wants "important" decay modes.
        
        INCLUSION CRITERIA:
        ------------------
        Include:
          - Alpha (a, A)
          - Beta- (B-)
          - Beta+ (B+)
          - Electron Capture (EC)
          - Delayed particle emission (B-n, B+p, ECp, etc.)
        
        Exclude:
          - Simple particle emission (n, p, SF, IT)
          - These are not decay modes, but nuclear reactions
        
        WHY THIS FILTERING?
        ------------------
        1. Reduces database size (removes noise)
        2. Focuses on physically significant decay channels
        3. Matches behavior of ENSDF data module
        4. Makes comparisons easier
        
        Args:
            mode: Decay mode string (ENSDF notation)
            
        Returns:
            bool: True if mode should be included
        """
        if not mode:
            return False
        
        # Include EC explicitly
        if mode.startswith('EC'):
            return True
        
        # Exclude simple modes (not decay modes)
        excluded = {'n', 'p', 'nn', 'pp', 'SF', 'IT', 'G', 'γ'}
        if mode in excluded:
            return False
        
        # Include a (alpha), B-, B+
        if mode in {'a', 'A', 'B-', 'B+'}:
            return True
        
        # Include delayed particles from beta decay
        for prefix in ['B-', 'B+', 'EC']:
            if mode.startswith(prefix) and len(mode) > len(prefix):
                return True
        
        return False
    
    def _parse_to_dataframes(self):
        """
        Convert parsed ENDF decay data into DECAY and NUCLIDE DataFrames.
        
        *** THIS IS WHERE THE MAGIC HAPPENS! ***
        
        TRANSFORMATION PIPELINE:
        -----------------------
        DecayData objects → pandas DataFrames with database schema
        
        INPUT: self.decay_data = [DecayData, DecayData, ...]
        OUTPUT: self.decay_df, self.nuclide_df (pandas DataFrames)
        
        KEY OPERATIONS:
        --------------
        
        1. EC/B+ SPLITTING:
           Input: One mode with total branching
             {"EC/B+": 100.0}
           Output: Two separate database entries
             {"EC": 8.83, "B+": 91.17}
           Why: EC and B+ are physically distinct processes
        
        2. MODE FILTERING:
           Input: All modes from ENDF
             ["B-", "n", "p", "SF", "IT"]
           Output: Only important modes
             ["B-"]
           Why: Database focuses on decay modes, not reactions
        
        3. NOTATION CONVERSION:
           Input: ENDF notation
             "B-,A" (uppercase, comma)
           Output: ENSDF notation
             "B-a" (lowercase, no comma)
           Why: Database standard is ENSDF notation
        
        4. SCHEMA CONSTRUCTION:
           Input: Python objects/dicts
           Output: pandas DataFrame with:
             - Proper column names
             - Proper data types
             - Sorted by (A, Z, parentLevel, decay_mode, final_level)
           Why: Database expects this exact structure
        
        DATAFRAME SCHEMAS:
        -----------------
        
        DECAY DataFrame columns:
          - A (int): Mass number
          - Z (int): Atomic number
          - parentLevel (float): Parent excitation energy
          - decay_mode (str): Decay mode (ENSDF notation)
          - final_level (float): Daughter excitation energy
          - Parent (str): Nuclide name (e.g., "Am-241")
          - Endpoint_energy (float): Maximum energy (eV)
          - Average_energy (float): Mean energy (eV)
          - Intensity (float): Branching ratio (%)
        
        NUCLIDE DataFrame columns:
          - A (int): Mass number
          - Z (int): Atomic number
          - level (float): Excitation energy
          - Nuclide (str): Nuclide name
          - Half_life (float): Half-life (seconds)
          - hl_unit (str): Unit ('s')
        
        NOTE: MultiIndex is NOT set here!
        Database.populate_DM_from_endf_data() sets it later.
        """
        decay_rows = []
        nuclide_rows = []
        
        for decay in self.decay_data:
            # ================================================================
            # NUCLIDE ENTRY (one per nuclide/level)
            # ================================================================
            parent_name = f"{decay.element}-{decay.parent_A}"
            
            nuclide_rows.append({
                'A': decay.parent_A,
                'Z': decay.parent_Z,
                'level': decay.parent_level_energy,
                'Nuclide': parent_name,
                'Half_life': decay.half_life,
                'hl_unit': decay.hl_unit,
            })
            
            # ================================================================
            # DECAY ENTRIES (one per decay channel)
            # ================================================================
            for mode, total_branching_ratio in decay.decay_modes.items():
                if total_branching_ratio <= 0:
                    continue
                
                # ============================================================
                # SPECIAL CASE: EC/B+ SPLITTING
                # ============================================================
                # CRITICAL BUSINESS LOGIC!
                #
                # Physical background:
                # -------------------
                # Proton-rich nuclei can decay by two competing modes:
                # 1. β+ emission: p → n + e+ + ν (requires Q > 1.022 MeV)
                # 2. Electron Capture: p + e- → n + ν (no threshold)
                #
                # ENDF stores TOTAL branching ratio for both.
                # Database needs SEPARATE entries for EC and B+.
                #
                # How we split:
                # ------------
                # 1. Sum all β+ transition intensities from spectrum
                # 2. β+ branching = sum of intensities
                # 3. EC branching = Total - β+
                #
                # This uses extract_bplus_branching() from JEFF_ENDF_parser.
                
                if mode.startswith('EC/B+'):
                    # Extract actual B+ branching from spectrum data
                    bplus_br_pct = extract_bplus_branching(decay.jeff_dict)
                    ec_br_pct = total_branching_ratio - bplus_br_pct
                    
                    # Get energies (only applicable to B+ component)
                    endpoint_energy = decay.endpoint_energies.get(mode, np.nan)
                    average_energy = decay.average_energies.get(mode, np.nan)
                    
                    # Determine secondary particle suffix (if any)
                    # "EC/B+a" → suffix is "a"
                    suffix = ''
                    if mode.startswith('EC/B+') and len(mode) > 6:
                        suffix = mode[6:]
                    
                    # Create B+ database entry
                    if bplus_br_pct > 0:
                        b_plus_mode = f"B+{suffix}"
                        b_plus_mode = self._convert_to_ensdf_notation(b_plus_mode)
                        
                        decay_row_bplus = {
                            'A': decay.parent_A,
                            'Z': decay.parent_Z,
                            'parentLevel': decay.parent_level_energy,
                            'decay_mode': b_plus_mode,
                            'final_level': 0.0,
                            'Parent': parent_name,
                            'Endpoint_energy': endpoint_energy,
                            'Average_energy': average_energy,
                            'Intensity': bplus_br_pct,
                        }
                        
                        if self._is_important_decay_mode(b_plus_mode):
                            decay_rows.append(decay_row_bplus)
                    
                    # Create EC database entry
                    if ec_br_pct > 0:
                        ec_mode = f"EC{suffix}"
                        ec_mode = self._convert_to_ensdf_notation(ec_mode)
                        
                        decay_row_ec = {
                            'A': decay.parent_A,
                            'Z': decay.parent_Z,
                            'parentLevel': decay.parent_level_energy,
                            'decay_mode': ec_mode,
                            'final_level': 0.0,
                            'Parent': parent_name,
                            'Endpoint_energy': np.nan,  # EC has no endpoint
                            'Average_energy': np.nan,   # EC has no particle energy
                            'Intensity': ec_br_pct,
                        }
                        
                        if self._is_important_decay_mode(ec_mode):
                            decay_rows.append(decay_row_ec)
                    
                    continue
                
                # ============================================================
                # ALL OTHER MODES (not EC/B+)
                # ============================================================
                endpoint_energy = decay.endpoint_energies.get(mode, np.nan)
                average_energy = decay.average_energies.get(mode, np.nan)
                
                # Convert mode to ENSDF notation
                ensdf_mode = self._convert_to_ensdf_notation(mode)
                
                decay_row = {
                    'A': decay.parent_A,
                    'Z': decay.parent_Z,
                    'parentLevel': decay.parent_level_energy,
                    'decay_mode': ensdf_mode,
                    'final_level': 0.0,
                    'Parent': parent_name,
                    'Endpoint_energy': endpoint_energy,
                    'Average_energy': average_energy,
                    'Intensity': total_branching_ratio,
                }
                
                # Apply filter
                if self._is_important_decay_mode(ensdf_mode):
                    decay_rows.append(decay_row)
        
        # ====================================================================
        # CREATE DATAFRAMES
        # ====================================================================
        # Convert row lists to pandas DataFrames
        # NO multi-index set yet - Database.populate_DM_from_endf_data() does that
        
        self.decay_df = pd.DataFrame(decay_rows) if decay_rows else pd.DataFrame()
        self.nuclide_df = pd.DataFrame(nuclide_rows) if nuclide_rows else pd.DataFrame()
        
        # Sort by index columns (but don't set as index yet!)
        if not self.decay_df.empty:
            self.decay_df = self.decay_df.sort_values(
                ['A', 'Z', 'parentLevel', 'decay_mode', 'final_level']
            )
        
        if not self.nuclide_df.empty:
            self.nuclide_df = self.nuclide_df.sort_values(['A', 'Z', 'level'])
        
        self.nuclides_df = self.nuclide_df  # Alias for compatibility
    
    def get_decay_dataframe(self, with_index: bool = False) -> pd.DataFrame:
        """
        Return the DECAY DataFrame.
        
        Args:
            with_index: If True, return with multi-index already set
        """
        if not hasattr(self, 'decay_df'):
            self._parse_to_dataframes()
        
        if with_index and not self.decay_df.empty:
            if not isinstance(self.decay_df.index, pd.MultiIndex):
                df = self.decay_df.copy()
                df = df.set_index(['A', 'Z', 'parentLevel', 'decay_mode', 'final_level'])
                return df
        
        return self.decay_df
    
    def get_nuclide_dataframe(self, with_index: bool = False) -> pd.DataFrame:
        """
        Return the NUCLIDE DataFrame.
        
        Args:
            with_index: If True, return with multi-index already set
        """
        if not hasattr(self, 'nuclide_df'):
            self._parse_to_dataframes()
        
        if with_index and not self.nuclide_df.empty:
            if not isinstance(self.nuclide_df.index, pd.MultiIndex):
                df = self.nuclide_df.copy()
                df = df.set_index(['A', 'Z', 'level'])
                return df
        
        return self.nuclide_df
    
    # Compatibility methods
    def get_decay_data(self, with_index: bool = False):
        return self.get_decay_dataframe(with_index=with_index)
    
    def get_nuclide_data(self, with_index: bool = False):
        return self.get_nuclide_dataframe(with_index=with_index)
    
    def get_nuclides_data(self, with_index: bool = False):
        return self.get_nuclide_dataframe(with_index=with_index)
    
    def display_summary(self):
        """Display summary statistics."""
        if not hasattr(self, 'decay_df'):
            self._parse_to_dataframes()
        
        print("\n" + "=" * 60)
        print("ENDF DATA MODULE SUMMARY (WITH EC/B+ SPLIT)")
        print("=" * 60)
        print(f"Source files:         {len(self.source_files)}")
        print(f"Total decay entries:  {len(self.decay_df)}")
        print(f"Total nuclides:       {len(self.nuclide_df)}")
        
        if not self.decay_df.empty:
            print(f"\nDecay modes present:")
            mode_counts = self.decay_df['decay_mode'].value_counts()
            for mode, count in mode_counts.items():
                print(f"  {mode:10s}: {count:5d}")
            
            # Show EC vs B+ statistics
            ec_count = sum(count for mode, count in mode_counts.items() if mode.startswith('EC'))
            bplus_count = sum(count for mode, count in mode_counts.items() if mode.startswith('B+'))
            print(f"\n  Total EC entries:  {ec_count}")
            print(f"  Total B+ entries:  {bplus_count}")
        
        print("=" * 60)


# ============================================================================
# STEP 4: CONVENIENCE FUNCTION - MAIN ENTRY POINT
# ============================================================================

def parse_endf_files(endf_dir: str, file_pattern: str = "*.endf") -> ENDFDataModule:
    """
    Parse ENDF files and return an ENDFDataModule.
    
    CONVENIENCE WRAPPER FOR: load_from_endf_files() + _parse_to_dataframes()
    
    This is the function called by main_db.py:
      from PyClasses.ENDFParsing import parse_endf_files
      ENDF = parse_endf_files(path_input_endf_dir, file_pattern="*.endf")
    
    Args:
        endf_dir: Path to directory containing ENDF-6 files OR path to single file
        file_pattern: Glob pattern for ENDF files (default: "*.endf")
        
    Returns:
        ENDFDataModule with loaded and parsed data ready for database
    """
    module = ENDFDataModule()
    module.load_from_endf_files(endf_dir, file_pattern=file_pattern)
    module._parse_to_dataframes()
    return module


# ============================================================================
# COMMAND-LINE INTERFACE (for testing)
# ============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Parse ENDF-6 decay data files")
    parser.add_argument("endf_dir", 
                       nargs='?',
                       default="/Users/audreywarn/fluka-db-audrey/data_input/endf/ENDF-B-VIII.0_decay",
                       help="Directory containing ENDF files OR single ENDF file")
    parser.add_argument("--output", "-o", help="Output directory for CSV files")
    parser.add_argument("--pattern", "-p", default="*.endf", 
                       help="File pattern (default: *.endf) - ignored if endf_dir is a file")
    
    args = parser.parse_args()
    
    # Parse ENDF files
    endf_path = Path(args.endf_dir)
    if endf_path.is_file():
        print(f"Parsing single ENDF file: {args.endf_dir}")
    else:
        print(f"Parsing ENDF files from directory: {args.endf_dir}")
        print(f"File pattern: {args.pattern}")
    
    endf_module = parse_endf_files(args.endf_dir, file_pattern=args.pattern)
    endf_module.display_summary()
