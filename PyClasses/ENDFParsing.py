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
        - Each result has decays with RTYP (decay type), BR (branching ratio), energies
        - EC/β+ splitting already done in the parser
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
            
            # Process decays
            decays = result.get('decays', [])
            for decay in decays:
                rtyp = decay.get('RTYP')
                rtyp_label = decay.get('RTYP_label', str(rtyp))
                branching = decay.get('BR', 0.0)
                
                # Get average beta energy if available
                avg_energy = decay.get('Average_Beta_Energy', 0.0)
                endpoint_energy = decay.get('Endpoint_Energy', 0.0)
                
                # Map ENDF decay types to standard notation
                # RTYP values: 0=γ, 1=β⁻, 2=EC/β⁺, 4=α, 5=n, 6=SF, 7=p
                # With decimal extensions: 1.5=β⁻,n, 2.4=β⁺,α, etc.
                decay_mode = self._map_endf_decay_mode(rtyp, rtyp_label)
                
                if decay_mode:
                    decay_rows.append({
                        'A': A,
                        'Z': Z,
                        'parentLevel': 0,  # ENDF data is typically ground state
                        'decay_mode': decay_mode,
                        'final_level': 0,  # Can be refined if daughter level info available
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
    from PyClasses.JEFF_ENDF_parser import parse_endf_file
    
    endf_path = Path(endf_dir)
    if not endf_path.exists():
        raise FileNotFoundError(f"ENDF directory not found: {endf_dir}")
    
    # Find all ENDF files
    endf_files = list(endf_path.glob(file_pattern))
    if not endf_files:
        print(f"Warning: No files matching '{file_pattern}' found in {endf_dir}")
        return ENDFDataModule([])
    
    print(f"Found {len(endf_files)} ENDF file(s) in {endf_dir}")
    
    # Parse each ENDF file
    all_results = []
    for endf_file in endf_files:
        print(f"Parsing {endf_file.name}...")
        try:
            results = parse_endf_file(str(endf_file))
            all_results.extend(results)
        except Exception as e:
            print(f"Error parsing {endf_file}: {e}")
    
    print(f"Successfully parsed {len(all_results)} nuclides from ENDF files")
    
    # Create ENDFDataModule
    return ENDFDataModule(all_results)
