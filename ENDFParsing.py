#!/usr/bin/env python3
"""
ENDF Data Module for parsing ENDF-6 MF=8 MT=457 radioactive decay data.
FIXED VERSION: Properly splits EC/B+ decay + NO logft column.
UPDATED: Default pattern to parse .endf files.
UPDATED: Handles both 75-char and 80-char ENDF line formats.
"""

import numpy as np
import pandas as pd
from pathlib import Path
from typing import List, Dict, Optional
import sys
import os

# Add PyClasses to path if not already there
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

# Atomic symbols (from JEFF parser)
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


class DecayData:
    """Simple container for decay data from JEFF parser."""
    def __init__(self, jeff_dict):
        """Initialize from JEFF parser dictionary output."""
        # Store original parsed data for later use
        self.jeff_dict = jeff_dict
        
        self.parent_A = int(jeff_dict["ZA"] % 1000)
        self.parent_Z = int(jeff_dict["ZA"] // 1000)
        self.parent_level_energy = float(0.0)  # JEFF doesn't provide this directly
        self.element = ATOMIC_SYMBOL.get(self.parent_Z, f'Z{self.parent_Z}')
        
        # Half-life - ensure it's a float
        if "T1/2" in jeff_dict and jeff_dict["T1/2"]:
            hl_val = jeff_dict["T1/2"][0] if isinstance(jeff_dict["T1/2"], tuple) else jeff_dict["T1/2"]
            self.half_life = float(hl_val)
            self.hl_unit = 's'
        else:
            self.half_life = float(0.0)
            self.hl_unit = 's'
        
        # Decay modes with branching ratios
        self.decay_modes = {}
        if "modes" in jeff_dict:
            for mode in jeff_dict["modes"]:
                # Decode RTYP to mode string
                mode_str = self._decode_rtyp(mode["RTYP"])
                br = mode["BR"][0] if isinstance(mode["BR"], tuple) else mode["BR"]
                # Convert to percentage if needed
                br_pct = float(br * 100.0 if br <= 1.0 else br)
                self.decay_modes[mode_str] = br_pct
        
        # Energy information (from spectra)
        self.endpoint_energies = {}
        self.average_energies = {}
        
        if "spectra" in jeff_dict:
            for spec in jeff_dict["spectra"]:
                styp = spec.get("STYP", -1)
                
                # Get mean energy
                if "ER_AV" in spec and spec["ER_AV"]:
                    avg_e = spec["ER_AV"][0] if isinstance(spec["ER_AV"], tuple) else spec["ER_AV"]
                    avg_e = float(avg_e)
                    
                    # Map STYP to mode string
                    if styp == 1:  # Beta-
                        for mode_str in self.decay_modes:
                            if mode_str.startswith('B-') or mode_str.startswith('β-'):
                                self.average_energies[mode_str] = avg_e
                    elif styp == 2:  # Beta+
                        for mode_str in self.decay_modes:
                            if mode_str.startswith('B+') or mode_str.startswith('EC/B+'):
                                self.average_energies[mode_str] = avg_e
                    elif styp == 0:  # Gamma
                        self.average_energies['gamma'] = avg_e
                
                # Get endpoint energies from discrete transitions (for beta- and beta+)
                if styp == 1 and "discrete" in spec and spec["discrete"]:
                    for disc in spec["discrete"]:
                        if "ER" in disc:
                            endpoint = disc["ER"][0] if isinstance(disc["ER"], tuple) else disc["ER"]
                            endpoint = float(endpoint)
                            for mode_str in self.decay_modes:
                                if mode_str.startswith('B-') or mode_str.startswith('β-'):
                                    self.endpoint_energies[mode_str] = endpoint
                                    break
                elif styp == 2 and "discrete" in spec and spec["discrete"]:
                    for disc in spec["discrete"]:
                        if "ER" in disc:
                            endpoint = disc["ER"][0] if isinstance(disc["ER"], tuple) else disc["ER"]
                            endpoint = float(endpoint)
                            for mode_str in self.decay_modes:
                                if mode_str.startswith('B+') or mode_str.startswith('EC/B+'):
                                    self.endpoint_energies[mode_str] = endpoint
                                    break
    
    def _decode_rtyp(self, rtyp):
        """
        Decode RTYP to mode string in ENSDF notation.
        
        ENSDF notation: No commas, lowercase for particles (a, p, n)
        Examples: B-a, B+p, ECn, B-n
        """
        particle_map = {
            0: "γ", 1: "B-", 2: "EC/B+", 3: "IT",
            4: "a", 5: "n", 6: "SF", 7: "p"  # lowercase a, n, p for ENSDF
        }
        
        simple_modes = {
            0.0: "γ", 1.0: "B-", 2.0: "EC/B+", 3.0: "IT",
            4.0: "a", 5.0: "n", 6.0: "SF", 7.0: "p"  # lowercase a, n, p
        }
        
        rtyp_float = float(rtyp)
        
        if rtyp_float in simple_modes:
            return simple_modes[rtyp_float]
        
        # Decode combined mode - use ENSDF notation (no commas)
        primary = int(rtyp_float)
        secondary = int(round((rtyp_float - primary) * 10))
        
        primary_label = particle_map.get(primary, str(primary))
        secondary_label = particle_map.get(secondary, str(secondary))
        
        # Return without comma to match ENSDF notation
        return f"{primary_label}{secondary_label}"


class ENDFDataModule:
    """
    Wrapper for ENDF decay data that converts parsed ENDF files into DataFrames
    compatible with the Database/DataModule workflow.
    
    FIXED VERSION: Properly splits EC/B+ decay using extract_bplus_branching().
    UPDATED: Default pattern to parse .endf files.
    UPDATED: Handles both 75-char and 80-char ENDF line formats.
    """
    
    def __init__(self):
        self.decay_data = []
        self.nuclide_data = []
        self.source_files = []
    
    def load_from_endf_files(self, endf_dir: str, file_pattern: str = "*.endf"):
        """
        Load ENDF files from a directory or a single file.
        
        Args:
            endf_dir: Path to directory containing ENDF-6 files OR path to a single ENDF file
            file_pattern: Glob pattern for ENDF files (default: "*.endf") - ignored if endf_dir is a file
        """
        endf_path = Path(endf_dir)
        
        if not endf_path.exists():
            raise FileNotFoundError(f"ENDF path not found: {endf_dir}")
        
        # Check if path is a file or directory
        if endf_path.is_file():
            # Single file mode
            endf_files = [endf_path]
            print(f"\nProcessing single ENDF file: {endf_path.name}")
        else:
            # Directory mode - find all ENDF files matching the pattern
            endf_files = sorted(list(endf_path.glob(file_pattern)))
            endf_files = [f for f in endf_files if f.is_file()]
            
            if not endf_files:
                raise ValueError(f"No ENDF files found in {endf_dir} matching pattern '{file_pattern}'")
            
            print(f"\nFound {len(endf_files)} ENDF files in {endf_dir}")
        
        for file_path in endf_files:
            try:
                print(f"  Parsing: {file_path.name}")
                
                # Read file to find all MF=8 MT=457 sections
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                
                # Scan for all decay sections
                # Strategy: detect when MF/MT changes to 8/457 (works for both 75-char and 80-char formats)
                section_positions = []
                seen_sections = set()  # Track (MAT, MF, MT) to avoid duplicates
                prev_mf, prev_mt = None, None
                
                for i, line in enumerate(lines):
                    # Pad line to 80 characters if needed (ENDF standard)
                    line_padded = f"{line:<80}" if len(line) < 80 else line
                    
                    if len(line_padded) >= 75:
                        try:
                            # ENDF-6 format: columns are 1-based in documentation, 0-based in Python
                            # Columns 67-70: MAT (4 chars, right-justified)
                            # Columns 71-72: MF (2 chars, right-justified)  
                            # Columns 73-75: MT (3 chars, right-justified)
                            # Columns 76-80: Sequence (5 chars, right-justified) - may be missing in some files
                            mat = int(line_padded[66:70].strip() or 0)
                            mf = int(line_padded[70:72].strip() or 0)
                            mt = int(line_padded[72:75].strip() or 0)
                            
                            # Detect start of MF=8 MT=457 section (when MF/MT changes to 8/457)
                            # This works for both 75-char files (no seq) and 80-char files (with seq)
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
                
                # Parse each section
                for start_pos, mat_num in section_positions:
                    try:
                        parser = ENDFNumericDecayParser()
                        parser.load_file(str(file_path))
                        parser._pos = start_pos
                        
                        # Parse this section
                        result = parser._parse_mf8_mt457()
                        result["MAT"] = mat_num
                        
                        # Convert to DecayData object
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
        
        ENDF notation: B-,A, EC,p, B+,n (with commas, uppercase A)
        ENSDF notation: B-a, ECp, B+n (no commas, lowercase a)
        
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
        # Be careful to only replace standalone A, not A in other contexts
        ensdf_mode = ensdf_mode.replace('A', 'a')
        
        # Special case: restore uppercase for elements that should be uppercase
        # (Currently none, but keeping this for future-proofing)
        
        return ensdf_mode
    
    def _is_important_decay_mode(self, mode):
        """
        Check if a decay mode should be included in ENDF data.
        
        Includes in ENDF: A, B-, B+, EC, delayed particles (B-n, B+p, ECp, etc.)
        Excludes from ENDF: n, p, SF, IT, simple emissions
        """
        if not mode:
            return False
        
        # Include EC explicitly
        if mode.startswith('EC'):
            return True
        
        # Exclude simple modes
        excluded = {'n', 'p', 'nn', 'pp', 'SF', 'IT', 'G', 'γ'}
        if mode in excluded:
            return False
        
        # Include a (alpha), B-, B+
        if mode in {'a', 'A', 'B-', 'B+'}:
            return True
        
        # Include delayed particles from beta decay
        # Check if mode starts with beta/EC prefix and has additional particles
        for prefix in ['B-', 'B+', 'EC']:
            if mode.startswith(prefix) and len(mode) > len(prefix):
                return True
        
        return False
    
    def _parse_to_dataframes(self):
        """Convert parsed ENDF decay data into DECAY and NUCLIDE DataFrames."""
        decay_rows = []
        nuclide_rows = []
        
        for decay in self.decay_data:
            # NUCLIDE entry
            parent_name = f"{decay.element}-{decay.parent_A}"
            
            nuclide_rows.append({
                'A': decay.parent_A,
                'Z': decay.parent_Z,
                'level': decay.parent_level_energy,
                'Nuclide': parent_name,
                'Half_life': decay.half_life,
                'hl_unit': decay.hl_unit,
            })
            
            # DECAY entries
            for mode, total_branching_ratio in decay.decay_modes.items():
                if total_branching_ratio <= 0:
                    continue
                
                # =====================================================
                # FIX: Properly split EC/B+ using extract_bplus_branching()
                # Changed from: if mode == 'EC/B+' or mode.startswith('EC/B+,'):
                # To: if mode.startswith('EC/B+'):
                # This now catches EC/B+, EC/B+p, EC/B+a, EC/B+SF, etc.
                # =====================================================
                if mode.startswith('EC/B+'):
                    # Extract actual B+ branching from spectrum data
                    bplus_br_pct = extract_bplus_branching(decay.jeff_dict)
                    ec_br_pct = total_branching_ratio - bplus_br_pct
                    
                    # Get energies (only applicable to B+ component)
                    endpoint_energy = decay.endpoint_energies.get(mode, np.nan)
                    average_energy = decay.average_energies.get(mode, np.nan)
                    
                    # Determine secondary particle suffix (if any)
                    # In ENSDF notation: "EC/B+a" → suffix is "a"
                    # "EC/B+p" → suffix is "p"
                    suffix = ''
                    if mode.startswith('EC/B+') and len(mode) > 6:
                        suffix = mode[6:]  # Everything after "EC/B+"
                    
                    # Create B+ row (NO LOGFT!)
                    if bplus_br_pct > 0:
                        b_plus_mode = f"B+{suffix}"
                        # Convert to ENSDF notation (no commas, lowercase a)
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
                    
                    # Create EC row (NO LOGFT!)
                    if ec_br_pct > 0:
                        ec_mode = f"EC{suffix}"
                        # Convert to ENSDF notation (no commas, lowercase a)
                        ec_mode = self._convert_to_ensdf_notation(ec_mode)
                        
                        decay_row_ec = {
                            'A': decay.parent_A,
                            'Z': decay.parent_Z,
                            'parentLevel': decay.parent_level_energy,
                            'decay_mode': ec_mode,
                            'final_level': 0.0,
                            'Parent': parent_name,
                            'Endpoint_energy': np.nan,  # EC has no endpoint energy
                            'Average_energy': np.nan,   # EC has no average energy
                            'Intensity': ec_br_pct,
                        }
                        
                        if self._is_important_decay_mode(ec_mode):
                            decay_rows.append(decay_row_ec)
                    
                    continue
                
                # All other modes (not EC/B+) - NO LOGFT!
                endpoint_energy = decay.endpoint_energies.get(mode, np.nan)
                average_energy = decay.average_energies.get(mode, np.nan)
                
                # Convert mode to ENSDF notation (no commas, lowercase a)
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
        
        # Convert to DataFrames (NO multi-index - DataModule handles that)
        self.decay_df = pd.DataFrame(decay_rows) if decay_rows else pd.DataFrame()
        self.nuclide_df = pd.DataFrame(nuclide_rows) if nuclide_rows else pd.DataFrame()
        
        # Sort but DO NOT set index yet - DataModule.populate_DM_from_endf_data() expects regular columns
        if not self.decay_df.empty:
            self.decay_df = self.decay_df.sort_values(['A', 'Z', 'parentLevel', 'decay_mode', 'final_level'])
        
        if not self.nuclide_df.empty:
            self.nuclide_df = self.nuclide_df.sort_values(['A', 'Z', 'level'])
        
        self.nuclides_df = self.nuclide_df  # Alias
    
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


def parse_endf_files(endf_dir: str, file_pattern: str = "*.endf") -> ENDFDataModule:
    """
    Parse ENDF files and return an ENDFDataModule.
    
    Args:
        endf_dir: Path to directory containing ENDF-6 files OR path to a single ENDF file
        file_pattern: Glob pattern for ENDF files (default: "*.endf") - ignored if endf_dir is a file
        
    Returns:
        ENDFDataModule with loaded and parsed data
    """
    module = ENDFDataModule()
    module.load_from_endf_files(endf_dir, file_pattern=file_pattern)
    module._parse_to_dataframes()
    return module


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Parse ENDF-6 decay data files")
    parser.add_argument("endf_dir", 
                       nargs='?',
                       default="/Users/audreywarn/fluka-db-audrey/data_input/endf/ENDF-B-VIII.0_decay",
                       help="Directory containing ENDF files OR single ENDF file (default: ENDF-B-VIII.0_decay)")
    parser.add_argument("--output", "-o", help="Output directory for CSV files")
    parser.add_argument("--pattern", "-p", default="*.endf", help="File pattern (default: *.endf) - ignored if endf_dir is a file")
    
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
