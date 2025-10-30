#!/usr/bin/env python3
"""
ENDF Data Module for parsing ENDF-6 MF=8 MT=457 radioactive decay data.
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
    from JEFF_ENDF_parser import ENDFNumericDecayParser
except ImportError:
    try:
        from PyClasses.JEFF_ENDF_parser import ENDFNumericDecayParser
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
        self.parent_A = jeff_dict["ZA"] % 1000
        self.parent_Z = jeff_dict["ZA"] // 1000
        self.parent_level_energy = 0.0  # JEFF doesn't provide this directly
        self.element = ATOMIC_SYMBOL.get(self.parent_Z, f'Z{self.parent_Z}')
        
        # Half-life
        if "T1/2" in jeff_dict and jeff_dict["T1/2"]:
            self.half_life = jeff_dict["T1/2"][0]
            self.hl_unit = 's'
        else:
            self.half_life = 0.0
            self.hl_unit = 's'
        
        # Decay modes with branching ratios
        self.decay_modes = {}
        if "modes" in jeff_dict:
            for mode in jeff_dict["modes"]:
                # Decode RTYP to mode string
                mode_str = self._decode_rtyp(mode["RTYP"])
                br = mode["BR"][0] if isinstance(mode["BR"], tuple) else mode["BR"]
                # Convert to percentage if needed
                br_pct = br * 100.0 if br <= 1.0 else br
                self.decay_modes[mode_str] = br_pct
        
        # Energy information (from spectra)
        self.endpoint_energies = {}
        self.average_energies = {}
        
        if "spectra" in jeff_dict:
            for spec in jeff_dict["spectra"]:
                styp = spec.get("STYP", -1)
                
                # Get mean energy
                if "ER_AV" in spec and spec["ER_AV"]:
                    avg_e = spec["ER_AV"][0]
                    
                    # Map STYP to mode string
                    if styp == 2:  # Beta+
                        for mode_str in self.decay_modes:
                            if mode_str.startswith('B+') or mode_str.startswith('EC/B+'):
                                self.average_energies[mode_str] = avg_e
                    elif styp == 0:  # Gamma
                        self.average_energies['gamma'] = avg_e
                
                # Get endpoint energies from discrete transitions (for beta+)
                if styp == 2 and "discrete" in spec and spec["discrete"]:
                    for disc in spec["discrete"]:
                        if "ER" in disc:
                            endpoint = disc["ER"][0]
                            for mode_str in self.decay_modes:
                                if mode_str.startswith('B+') or mode_str.startswith('EC/B+'):
                                    self.endpoint_energies[mode_str] = endpoint
                                    break
    
    def _decode_rtyp(self, rtyp):
        """Decode RTYP to mode string."""
        particle_map = {
            0: "γ", 1: "B-", 2: "EC/B+", 3: "IT",
            4: "A", 5: "n", 6: "SF", 7: "p"
        }
        
        simple_modes = {
            0.0: "γ", 1.0: "B-", 2.0: "EC/B+", 3.0: "IT",
            4.0: "A", 5.0: "n", 6.0: "SF", 7.0: "p"
        }
        
        rtyp_float = float(rtyp)
        
        if rtyp_float in simple_modes:
            return simple_modes[rtyp_float]
        
        # Decode combined mode
        primary = int(rtyp_float)
        secondary = int(round((rtyp_float - primary) * 10))
        
        primary_label = particle_map.get(primary, str(primary))
        secondary_label = particle_map.get(secondary, str(secondary))
        
        return f"{primary_label},{secondary_label}"


class ENDFDataModule:
    """
    Wrapper for ENDF decay data that converts parsed ENDF files into DataFrames
    compatible with the Database/DataModule workflow.
    """
    
    def __init__(self):
        self.decay_data = []
        self.nuclide_data = []
        self.source_files = []
    
    def load_from_endf_files(self, endf_dir: str, file_pattern: str = "*"):
        """
        Load all ENDF files from a directory using ENDFNumericDecayParser.
        
        Args:
            endf_dir: Path to directory containing ENDF-6 files
            file_pattern: Glob pattern for ENDF files (default: "*")
        """
        endf_path = Path(endf_dir)
        
        if not endf_path.exists():
            raise FileNotFoundError(f"ENDF directory not found: {endf_dir}")
        
        # Find all ENDF files matching the pattern
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
                section_positions = []
                for i, line in enumerate(lines):
                    if len(line) >= 75:
                        try:
                            mat = int(line[66:70].strip() or 0)
                            mf = int(line[70:72].strip() or 0)
                            mt = int(line[72:75].strip() or 0)
                            seq = int(line[75:80].strip() or 0)
                            
                            if mf == 8 and mt == 457 and seq == 1:
                                section_positions.append((i, mat))
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
    
    def _is_important_decay_mode(self, mode):
        """
        Check if a decay mode should be included (NO EC).
        
        Includes: A, B-, B+, delayed particles (B-n, B+p, etc.)
        Excludes: EC, n, p, SF, IT, etc.
        """
        if not mode:
            return False
        
        # Exclude EC explicitly
        if mode.startswith('EC'):
            return False
        
        # Exclude simple modes
        excluded = {'n', 'p', 'nn', 'pp', 'SF', 'IT', 'G', 'γ'}
        if mode in excluded:
            return False
        
        # Include A, B-, B+
        if mode in {'A', 'B-', 'B+'}:
            return True
        
        # Include delayed particles from beta
        for prefix in ['B-', 'B+']:
            if mode.startswith(prefix + ','):
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
            for mode, branching_ratio in decay.decay_modes.items():
                if branching_ratio <= 0:
                    continue
                
                # Split EC/B+ mode
                if mode == 'EC/B+' or mode.startswith('EC/B+,'):
                    # Extract B+ component only (EC excluded)
                    # JEFF parser should have calculated this already
                    # If not, we'll use the full branching for B+
                    endpoint_energy = decay.endpoint_energies.get(mode, np.nan)
                    average_energy = decay.average_energies.get(mode, np.nan)
                    
                    # Create B+ row only
                    b_plus_mode = mode.replace('EC/B+', 'B+')
                    decay_row = {
                        'A': decay.parent_A,
                        'Z': decay.parent_Z,
                        'parentLevel': decay.parent_level_energy,
                        'decay_mode': b_plus_mode,
                        'final_level': 0.0,
                        'Parent': parent_name,
                        'Endpoint_energy': endpoint_energy,
                        'Average_energy': average_energy,
                        'Intensity': branching_ratio,
                        'logft': np.nan,
                    }
                    
                    if self._is_important_decay_mode(b_plus_mode):
                        decay_rows.append(decay_row)
                    
                    # EC is NOT created
                    continue
                
                # All other modes
                endpoint_energy = decay.endpoint_energies.get(mode, np.nan)
                average_energy = decay.average_energies.get(mode, np.nan)
                
                decay_row = {
                    'A': decay.parent_A,
                    'Z': decay.parent_Z,
                    'parentLevel': decay.parent_level_energy,
                    'decay_mode': mode,
                    'final_level': 0.0,
                    'Parent': parent_name,
                    'Endpoint_energy': endpoint_energy,
                    'Average_energy': average_energy,
                    'Intensity': branching_ratio,
                    'logft': np.nan,
                }
                
                # Apply filter
                if self._is_important_decay_mode(mode):
                    decay_rows.append(decay_row)
        
        # Convert to DataFrames
        self.decay_df = pd.DataFrame(decay_rows) if decay_rows else pd.DataFrame()
        self.nuclide_df = pd.DataFrame(nuclide_rows) if nuclide_rows else pd.DataFrame()
        
        # Set multi-index for DECAY DataFrame (expected by Database.py)
        if not self.decay_df.empty:
            self.decay_df = self.decay_df.sort_values(['A', 'Z', 'parentLevel', 'decay_mode', 'final_level'])
            self.decay_df = self.decay_df.set_index(['A', 'Z', 'parentLevel', 'decay_mode', 'final_level'])
        
        # Set multi-index for NUCLIDE DataFrame (expected by Database.py)
        if not self.nuclide_df.empty:
            self.nuclide_df = self.nuclide_df.sort_values(['A', 'Z', 'level'])
            self.nuclide_df = self.nuclide_df.set_index(['A', 'Z', 'level'])
        
        self.nuclides_df = self.nuclide_df  # Alias
    
    def get_decay_dataframe(self) -> pd.DataFrame:
        """Return the DECAY DataFrame."""
        if not hasattr(self, 'decay_df'):
            self._parse_to_dataframes()
        return self.decay_df
    
    def get_nuclide_dataframe(self) -> pd.DataFrame:
        """Return the NUCLIDE DataFrame."""
        if not hasattr(self, 'nuclide_df'):
            self._parse_to_dataframes()
        return self.nuclide_df
    
    # Compatibility methods
    def get_decay_data(self):
        return self.get_decay_dataframe()
    
    def get_nuclide_data(self):
        return self.get_nuclide_dataframe()
    
    def get_nuclides_data(self):
        return self.get_nuclide_dataframe()
    
    def display_summary(self):
        """Display summary statistics."""
        if not hasattr(self, 'decay_df'):
            self._parse_to_dataframes()
        
        print("\n" + "=" * 60)
        print("ENDF DATA MODULE SUMMARY (FILTERED - NO EC)")
        print("=" * 60)
        print(f"Source files:         {len(self.source_files)}")
        print(f"Total decay entries:  {len(self.decay_df)}")
        print(f"Total nuclides:       {len(self.nuclide_df)}")
        
        if not self.decay_df.empty:
            print(f"\nDecay modes present:")
            mode_counts = self.decay_df['decay_mode'].value_counts()
            for mode, count in mode_counts.items():
                print(f"  {mode:10s}: {count:5d}")
        
        print("=" * 60)


def parse_endf_files(endf_dir: str, file_pattern: str = "*") -> ENDFDataModule:
    """
    Parse ENDF files and return an ENDFDataModule.
    
    Args:
        endf_dir: Path to directory containing ENDF-6 files
        file_pattern: Glob pattern for ENDF files (default: "*")
        
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
    parser.add_argument("endf_dir", help="Directory containing ENDF files")
    parser.add_argument("--output", "-o", help="Output directory for CSV files")
    parser.add_argument("--pattern", "-p", default="*", help="File pattern (default: *)")
    
    args = parser.parse_args()
    
    # Parse ENDF files
    endf_module = parse_endf_files(args.endf_dir, file_pattern=args.pattern)
    endf_module.display_summary()
    
    # Optionally save to CSV
    if args.output:
        output_path = Path(args.output)
        output_path.mkdir(parents=True, exist_ok=True)
        
        decay_df = endf_module.get_decay_dataframe()
        nuclide_df = endf_module.get_nuclide_dataframe()
        
        decay_file = output_path / "DECAY.csv"
        nuclide_file = output_path / "NUCLIDE.csv"
        
        decay_df.to_csv(decay_file, index=False)
        nuclide_df.to_csv(nuclide_file, index=False)
        
        print(f"\nSaved to:")
        print(f"  {decay_file}")
        print(f"  {nuclide_file}")
