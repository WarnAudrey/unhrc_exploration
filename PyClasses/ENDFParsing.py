#!/usr/bin/env python3
"""
ENDF Data Module - Wrapper for ENDF-6 format nuclear data parsing
Integrates JEFF_ENDF_parser.py for use with DataModule workflow
"""

import pandas as pd
import numpy as np
from pathlib import Path


class ENDFDataModule:
    """
    Wrapper for ENDF parsed data to match NuclearDataModule interface.
    Allows DataModule to populate from ENDF sources.
    """
    
    def __init__(self, endf_results):
        """
        Initialize ENDF Data Module from parsed ENDF results.
        
        Parameters:
        -----------
        endf_results : list
            List of dictionaries containing parsed ENDF data from JEFF_ENDF_parser
            Each dict has keys: 'ZA', 'Z', 'A', 'MAT', 'decays' (list of decay dicts)
        """
        self.endf_results = endf_results
        self.levels_df = pd.DataFrame()
        self.gamma_df = pd.DataFrame()
        self.decay_df = pd.DataFrame()
        self.nuclides_df = pd.DataFrame()
        
        # Parse the ENDF results into DataFrames
        self._parse_to_dataframes()
    
    def _parse_to_dataframes(self):
        """
        Convert ENDF results into DataFrames matching the NuclearDataModule format.
        
        ENDF data structure from JEFF_ENDF_parser:
        - Each result has modes[] with RTYP, BR, Q
        - EC/β+ splitting already done in the parser
        - spectra[] contains energy information
        """
        print("Converting ENDF data to DataFrames...")
        
        decay_rows = []
        nuclide_rows = []
        
        for result in self.endf_results:
            Z = result.get('Z')
            A = result.get('A')
            MAT = result.get('MAT')
            
            if Z is None or A is None:
                continue
            
            # Add nuclide entry
            nuclide_rows.append({
                'A': A,
                'Z': Z,
                'MAT': MAT
            })
            
            # Process decay modes (result["modes"] from ENDF parser)
            modes = result.get('modes', [])
            for mode in modes:
                # ENDF parser returns RTYP as float (1.0, 2.0, 1.5, 2.4, etc.)
                rtyp = mode.get('RTYP', 0.0)
                
                # Branching ratio (BR is a tuple: (value, uncertainty))
                br_tuple = mode.get('BR', (0.0, 0.0))
                branching = br_tuple[0] if isinstance(br_tuple, tuple) else br_tuple
                
                # Q-value (also a tuple)
                q_tuple = mode.get('Q', (0.0, 0.0))
                q_value = q_tuple[0] / 1000.0 if isinstance(q_tuple, tuple) else q_tuple / 1000.0  # Convert eV to keV
                
                # Daughter state
                rfs = mode.get('RFS', 0)
                
                # Map RTYP to decay mode label
                # The ENDF parser already handles EC/β+ splitting, so we'll see
                # separate entries with RTYP=2.0 for both components
                decay_mode_label = self._decode_endf_rtyp(rtyp)
                
                # Get energy information from spectra
                avg_energy = 0.0
                endpoint_energy = 0.0
                
                if "spectra" in result:
                    primary_decay = int(rtyp)
                    
                    # For beta decays, look for beta spectrum (STYP=2 for β+, could be other for β-)
                    for spec in result.get("spectra", []):
                        styp = spec.get("STYP", -1)
                        
                        # Beta+ spectrum (STYP=2)
                        if primary_decay == 2 and styp == 2:
                            # Mean energy from ER_AV
                            er_av = spec.get("ER_AV", (0.0, 0.0))
                            if isinstance(er_av, tuple) and er_av[0] > 0:
                                avg_energy = er_av[0] / 1000.0  # eV to keV
                            
                            # Try to get endpoint from discrete transitions
                            if "discrete" in spec and spec["discrete"]:
                                # Use first discrete transition's endpoint energy
                                first_disc = spec["discrete"][0]
                                er_tuple = first_disc.get("ER", (0.0, 0.0))
                                if isinstance(er_tuple, tuple):
                                    endpoint_energy = er_tuple[0] / 1000.0  # eV to keV
                        
                        # Beta- or other spectra - use ER_AV if available
                        elif styp in [0, 2, 4] and avg_energy == 0.0:
                            er_av = spec.get("ER_AV", (0.0, 0.0))
                            if isinstance(er_av, tuple) and er_av[0] > 0:
                                avg_energy = er_av[0] / 1000.0
                
                if decay_mode_label:
                    decay_rows.append({
                        'A': A,
                        'Z': Z,
                        'parentLevel': 0,  # ENDF MF=8 MT=457 is ground state
                        'decay_mode': decay_mode_label,
                        'final_level': int(rfs),  # Daughter state from RFS
                        'Intensity': f"{branching * 100:.6g}",  # Convert to percentage
                        'Average energy': f"{avg_energy:.6g} keV" if avg_energy > 0 else "",
                        'Endpoint energy': f"{endpoint_energy:.6g} keV" if endpoint_energy > 0 else "",
                    })
        
        # Create decay DataFrame
        if decay_rows:
            decay_df_temp = pd.DataFrame(decay_rows)
            decay_df_temp.sort_values(by=['A', 'Z', 'parentLevel', 'decay_mode', 'final_level'], inplace=True)
            self.decay_df = decay_df_temp.set_index(['A', 'Z', 'parentLevel', 'decay_mode', 'final_level'])
            print(f"Loaded {len(self.decay_df)} ENDF decay transitions")
            
            # Show decay mode breakdown
            decay_modes = self.decay_df.index.get_level_values('decay_mode').unique()
            print("ENDF decay modes loaded:")
            for mode in sorted(decay_modes):
                count = len(self.decay_df.xs(mode, level='decay_mode'))
                print(f"  {mode}: {count} transitions")
        
        # Create nuclides DataFrame
        if nuclide_rows:
            nuclides_df_temp = pd.DataFrame(nuclide_rows)
            nuclides_df_temp.sort_values(by=['A', 'Z'], inplace=True)
            # Remove duplicates (one entry per nuclide)
            nuclides_df_temp = nuclides_df_temp.drop_duplicates(subset=['A', 'Z'])
            self.nuclides_df = nuclides_df_temp.set_index(['A', 'Z'])
            print(f"Loaded {len(self.nuclides_df)} ENDF nuclide entries")
    
    def _decode_endf_rtyp(self, rtyp):
        """
        Decode ENDF RTYP to standard decay mode notation.
        
        NOTE: The ENDF parser (print_compact_summary_table) already handles
        EC/β+ splitting for all 2.x RTYP values, creating separate rows with
        labels "β+" and "EC" (with secondary particles preserved).
        
        Since we're reading from the parsed output (which already split),
        we should see RTYP=2.0 multiple times if there's EC/β+ splitting.
        
        This function maps the RTYP float values to our standard notation.
        """
        # For debugging, we'll use the decode_rtyp function from the ENDF parser
        # Import it if available
        try:
            from JEFF_ENDF_parser import decode_rtyp
            label = decode_rtyp(rtyp)
            
            # The parser returns labels like "β-", "β+", "EC", "α", "β-,n", etc.
            # Map these to our standard notation
            return self._map_endf_decay_mode(rtyp, label)
        except:
            # Fallback to simple mapping
            simple_map = {
                0.0: 'G', 1.0: 'B-', 2.0: 'B+', 3.0: 'IT',
                4.0: 'A', 5.0: 'n', 6.0: 'SF', 7.0: 'p'
            }
            return simple_map.get(float(rtyp), f'RTYP-{rtyp}')
    
    def _map_endf_decay_mode(self, rtyp, rtyp_label):
        """
        Map ENDF RTYP codes to standard decay mode notation.
        
        ENDF RTYP values (from ENDF-102 specification):
        - 0.0 = γ (gamma)
        - 1.0 = β⁻ (beta minus)
        - 2.0 = EC/β⁺ (electron capture / positron - ALREADY SPLIT by parser)
        - 4.0 = α (alpha)
        - 5.0 = n (neutron)
        - 6.0 = SF (spontaneous fission)
        - 7.0 = p (proton)
        - 1.5 = β⁻,n (beta-delayed neutron)
        - 1.4 = β⁻,α (beta-delayed alpha)
        - 2.4 = β⁺,α (positron-delayed alpha)
        - etc.
        
        The ENDF parser already splits EC/β⁺ into separate "β+" and "EC" rows.
        """
        # The parser provides RTYP_label which is already decoded
        # Map to our standard notation
        label_map = {
            'γ': 'G',           # Gamma
            'β-': 'B-',         # Beta minus
            'β+': 'B+',         # Beta plus (from EC/β+ split)
            'EC': 'EC',         # Electron capture (from EC/β+ split)
            'α': 'A',           # Alpha
            'IT': 'IT',         # Isomeric transition
            'n': 'n',           # Neutron
            'p': 'p',           # Proton
            'SF': 'SF',         # Spontaneous fission
            # Delayed particle emissions
            'β-,n': 'B-n',      # Beta-delayed neutron
            'β-,α': 'B-a',      # Beta-delayed alpha
            'β+,α': 'B+a',      # Positron-delayed alpha
            'β-,p': 'B-p',      # Beta-delayed proton
            'β+,p': 'B+p',      # Positron-delayed proton
            'EC,p': 'ECp',      # EC-delayed proton
            'EC,α': 'ECa',      # EC-delayed alpha
            'n,n': 'nn',        # Double neutron
            'p,p': 'pp',        # Double proton
        }
        
        return label_map.get(rtyp_label, rtyp_label)
    
    def get_levels_data(self):
        """Get levels DataFrame (may be empty for ENDF data)"""
        return self.levels_df
    
    def get_gamma_data(self):
        """Get gamma transitions DataFrame (may be empty for ENDF data)"""
        return self.gamma_df
    
    def get_decay_data(self):
        """Get decay transitions DataFrame"""
        return self.decay_df
    
    def get_nuclides_data(self):
        """Get nuclides DataFrame"""
        return self.nuclides_df
    
    def display_summary(self):
        """Display summary of loaded ENDF data"""
        print("=" * 60)
        print("ENDF DATA MODULE SUMMARY")
        print("=" * 60)
        
        if not self.decay_df.empty:
            print(f"\nDecay Transitions: {len(self.decay_df)} entries")
            print(f"Unique nuclei (decay): {len(self.decay_df.index.droplevel(['decay_mode', 'final_level']).unique())}")
            decay_modes = self.decay_df.index.get_level_values('decay_mode').unique()
            print(f"Decay modes: {', '.join(sorted(decay_modes))}")
        
        if not self.nuclides_df.empty:
            print(f"\nNuclides: {len(self.nuclides_df)} entries")


def parse_endf_files(endf_dir, file_pattern="*.endf"):
    """
    Parse ENDF files from a directory using JEFF_ENDF_parser.
    
    Parameters:
    -----------
    endf_dir : str or Path
        Directory containing ENDF files
    file_pattern : str
        Glob pattern for ENDF files (default: "*.endf")
    
    Returns:
    --------
    ENDFDataModule : Parsed ENDF data in DataModule-compatible format
    """
    # Import the parser class from your ENDF parser
    import sys
    from pathlib import Path as PathlibPath
    
    # Add PyClasses to path if needed
    pyclass_path = PathlibPath(__file__).parent
    if str(pyclass_path) not in sys.path:
        sys.path.insert(0, str(pyclass_path))
    
    from JEFF_ENDF_parser import ENDFNumericDecayParser, ATOMIC_SYMBOL
    
    endf_path = Path(endf_dir)
    if not endf_path.exists():
        raise FileNotFoundError(f"ENDF directory not found: {endf_dir}")
    
    # Find all ENDF files
    endf_files = list(endf_path.glob(file_pattern))
    if not endf_files:
        print(f"Warning: No files matching '{file_pattern}' found in {endf_dir}")
        return ENDFDataModule([])
    
    print(f"Found {len(endf_files)} ENDF file(s) in {endf_dir}")
    
    # Parse each ENDF file (following the pattern from JEFF_ENDF_parser __main__)
    all_results = []
    
    for endf_file in endf_files:
        print(f"Parsing {endf_file.name}...")
        try:
            # Read file and scan for MF=8 MT=457 sections
            with open(endf_file, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            # Find all decay sections
            section_info = []
            for i, line in enumerate(lines):
                if len(line) >= 75:
                    try:
                        mat = int(line[66:70].strip() or 0)
                        mf = int(line[70:72].strip() or 0)
                        mt = int(line[72:75].strip() or 0)
                        seq = int(line[75:80].strip() or 0)
                        
                        if mf == 8 and mt == 457 and seq == 1:
                            section_info.append((i, mat))
                    except:
                        continue
            
            if not section_info:
                print(f"  Warning: No MF=8 MT=457 sections found in {endf_file.name}")
                continue
            
            print(f"  Found {len(section_info)} decay section(s)")
            
            # Parse each section
            for start_pos, mat_num in section_info:
                try:
                    parser = ENDFNumericDecayParser()
                    parser.load_file(str(endf_file))
                    parser._pos = start_pos
                    
                    result = parser._parse_mf8_mt457()
                    result["MAT"] = mat_num
                    
                    # Add Z and A for convenience
                    za = result["ZA"]
                    result["Z"] = za // 1000
                    result["A"] = za % 1000
                    
                    all_results.append(result)
                    
                except Exception as e:
                    print(f"  Warning: Skipped MAT={mat_num}: {str(e)[:60]}")
                    continue
        
        except Exception as e:
            print(f"  Error reading {endf_file.name}: {e}")
            continue
    
    print(f"Successfully parsed {len(all_results)} decay sections from ENDF files")
    
    # Create ENDFDataModule
    return ENDFDataModule(all_results)
