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
        
        parser = ENDFNumericDecayParser()
        
        for file_path in endf_files:
            try:
                print(f"  Parsing: {file_path.name}")
                
                # Debug: show what methods the parser has
                parser_methods = [m for m in dir(parser) if not m.startswith('_')]
                print(f"    Available parser methods: {parser_methods[:10]}...")
                
                # Try different method names that the parser might have
                if hasattr(parser, 'parse_file'):
                    print(f"    Using parser.parse_file()")
                    decay_list = parser.parse_file(str(file_path))
                elif hasattr(parser, 'parse'):
                    print(f"    Using parser.parse()")
                    decay_list = parser.parse(str(file_path))
                elif hasattr(parser, 'read_file'):
                    print(f"    Using parser.read_file()")
                    decay_list = parser.read_file(str(file_path))
                elif hasattr(parser, 'load_file'):
                    print(f"    Using parser.load_file()")
                    decay_list = parser.load_file(str(file_path))
                else:
                    # Try calling the parser directly with the file path
                    print(f"    Using parser() directly")
                    decay_list = parser(str(file_path))
                
                print(f"    Result: {type(decay_list)}, length: {len(decay_list) if decay_list else 0}")
                
                if decay_list:
                    self.decay_data.extend(decay_list)
                    self.source_files.append(str(file_path))
                else:
                    print(f"    WARNING: Parser returned empty or None!")
                    
            except Exception as e:
                print(f"    ERROR parsing {file_path.name}: {e}")
                import traceback
                print("Full traceback:")
                traceback.print_exc()
                # Don't continue - we need to see what's failing
                raise
        
        print(f"\nLoaded {len(self.decay_data)} decay entries from {len(self.source_files)} files")
    
    def _is_important_decay_mode(self, mode):
        """
        Check if a decay mode should be included in the filtered output.
        
        Includes:
        - A (alpha)
        - B- (beta minus)
        - B+ (beta plus)
        - Delayed particle decays: B-n, B-p, B+p, B+a, etc.
        
        Excludes:
        - EC (electron capture) and EC-delayed particles
        - Simple particle emissions: n, p, nn, pp
        - SF (spontaneous fission)
        - IT (isomeric transition)
        - Exotic combined modes
        """
        if not mode:
            return False
        
        # Exclude simple particle emissions, fission, isomeric transitions
        excluded_simple_modes = {'n', 'p', 'nn', 'pp', 'SF', 'IT', 'G'}
        if mode in excluded_simple_modes:
            return False
        
        # Exclude modes containing SF or IT
        if ',SF' in mode or 'SF,' in mode or ',IT' in mode or 'IT,' in mode:
            return False
        
        # Exclude exotic combined modes (e.g., "14C", "24Ne")
        if ',' in mode:
            parts = mode.split(',')
            for part in parts:
                if part.strip().isdigit():
                    return False
        
        # Include basic alpha and beta decay modes (NO EC)
        if mode in {'A', 'B-', 'B+'}:
            return True
        
        # Include delayed particle emissions from beta decays ONLY (NO EC)
        for prefix in ['B-', 'B+']:
            if mode.startswith(prefix) and len(mode) > len(prefix):
                suffix = mode[len(prefix):]
                if suffix.startswith(','):
                    suffix = suffix[1:]
                # Valid delayed particles
                valid_particles = {'n', 'p', 'a', 'α', '2n', '3n', '4n', '2p', '3p', '4p', '2a', '3a'}
                if suffix in valid_particles:
                    return True
        
        # Filter out everything else (including EC, ECn, ECp, etc.)
        # Uncomment the line below to see what's being filtered
        # print(f"  Filtering out decay mode: {mode}")
        return False
    
    def _parse_to_dataframes(self):
        """
        Convert parsed ENDF decay data into DECAY and NUCLIDE DataFrames.
        Applies filtering to include only important decay modes.
        """
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
                'hl_unit': decay.hl_unit if hasattr(decay, 'hl_unit') else 's',
            })
            
            # DECAY entries
            for mode, branching_ratio in decay.decay_modes.items():
                if branching_ratio <= 0:
                    continue
                
                # Get final level (if available)
                final_level = 0.0
                if hasattr(decay, 'final_levels') and mode in decay.final_levels:
                    final_level = decay.final_levels[mode]
                
                # Handle EC/β+ splitting - ONLY keep β+, discard EC
                if mode == 'EC/B+':
                    # Get EC/β+ ratio (default to 50/50 if not specified)
                    ec_fraction = 0.5
                    if hasattr(decay, 'ec_beta_plus_ratio'):
                        ec_fraction = decay.ec_beta_plus_ratio
                    
                    # Calculate branching ratios
                    beta_plus_br = branching_ratio * (1 - ec_fraction)
                    # ec_br = branching_ratio * ec_fraction  # NOT USED - EC excluded
                    
                    # Get energies (for β+ only)
                    endpoint_energy = np.nan
                    average_energy = np.nan
                    
                    if hasattr(decay, 'endpoint_energies') and 'EC/B+' in decay.endpoint_energies:
                        endpoint_energy = float(decay.endpoint_energies['EC/B+'])
                    if hasattr(decay, 'average_energies') and 'EC/B+' in decay.average_energies:
                        average_energy = float(decay.average_energies['EC/B+'])
                    
                    # Create β+ row ONLY
                    if beta_plus_br > 0:
                        beta_plus_row = {
                            'A': decay.parent_A,
                            'Z': decay.parent_Z,
                            'parentLevel': decay.parent_level_energy,
                            'decay_mode': 'B+',
                            'final_level': final_level,
                            'Parent': parent_name,
                            'Endpoint_energy': endpoint_energy,
                            'Average_energy': average_energy,
                            'Intensity': beta_plus_br,
                            'logft': decay.logft if hasattr(decay, 'logft') else np.nan,
                        }
                        if self._is_important_decay_mode('B+'):
                            decay_rows.append(beta_plus_row)
                    
                    # EC row is NOT created - EC is excluded
                    
                    continue
                
                # All other decay modes
                endpoint_energy = np.nan
                average_energy = np.nan
                
                if hasattr(decay, 'endpoint_energies') and mode in decay.endpoint_energies:
                    endpoint_energy = float(decay.endpoint_energies[mode])
                if hasattr(decay, 'average_energies') and mode in decay.average_energies:
                    average_energy = float(decay.average_energies[mode])
                
                decay_row = {
                    'A': decay.parent_A,
                    'Z': decay.parent_Z,
                    'parentLevel': decay.parent_level_energy,
                    'decay_mode': mode,
                    'final_level': final_level,
                    'Parent': parent_name,
                    'Endpoint_energy': endpoint_energy,
                    'Average_energy': average_energy,
                    'Intensity': branching_ratio,
                    'logft': decay.logft if hasattr(decay, 'logft') else np.nan,
                }
                
                # Apply filter - will exclude EC and EC-delayed particle modes
                if self._is_important_decay_mode(mode):
                    decay_rows.append(decay_row)
        
        # Convert to DataFrames
        self.decay_df = pd.DataFrame(decay_rows) if decay_rows else pd.DataFrame()
        self.nuclide_df = pd.DataFrame(nuclide_rows) if nuclide_rows else pd.DataFrame()
        
        # Also create alias for compatibility
        self.nuclides_df = self.nuclide_df
        
        # Sort by A, Z, parentLevel
        if not self.decay_df.empty:
            self.decay_df = self.decay_df.sort_values(['A', 'Z', 'parentLevel']).reset_index(drop=True)
        if not self.nuclide_df.empty:
            self.nuclide_df = self.nuclide_df.sort_values(['A', 'Z', 'level']).reset_index(drop=True)
            self.nuclides_df = self.nuclide_df
    
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
    
    # Compatibility methods for Database.py
    def get_decay_data(self):
        """Alias for get_decay_dataframe() for compatibility."""
        return self.get_decay_dataframe()
    
    def get_nuclide_data(self):
        """Alias for get_nuclide_dataframe() for compatibility."""
        return self.get_nuclide_dataframe()
    
    def get_nuclides_data(self):
        """Alias for get_nuclide_dataframe() for compatibility (plural form)."""
        return self.get_nuclide_dataframe()
    
    def display_summary(self):
        """Display summary statistics of loaded data."""
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
    Convenience function to parse ENDF files and return an ENDFDataModule.
    
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
