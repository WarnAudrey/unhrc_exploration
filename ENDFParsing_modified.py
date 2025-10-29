#!/usr/bin/env python3
"""
ENDF Data Module - Wrapper for ENDF-6 format nuclear data parsing
Integrates JEFF_ENDF_parser.py for use with DataModule workflow

MODIFIED VERSION: Filters to match JSON/ENSDF parser scope
Only includes: Alpha, Beta-, Beta+, EC, and delayed particle decays
Excludes: Simple emissions (n, p), SF, IT, and exotic combined modes
"""

import pandas as pd
import numpy as np
from pathlib import Path


class ENDFDataModule:
    """
    Wrapper for ENDF parsed data to match NuclearDataModule interface.
    Allows DataModule to populate from ENDF sources.
    
    MODIFICATION: Added decay mode filtering to match JSON/ENSDF parser
    """
    
    def __init__(self, endf_results):
        """Initialize ENDF Data Module from parsed ENDF results."""
        self.endf_results = endf_results
        self.levels_df = pd.DataFrame()
        self.gamma_df = pd.DataFrame()
        self.decay_df = pd.DataFrame()
        self.nuclides_df = pd.DataFrame()
        self._parse_to_dataframes()

        print(f"DEBUG: ENDFDataModule received {len(endf_results)} results")
        if endf_results:
            print(f"DEBUG: First result type: {type(endf_results[0])}")
            print(f"DEBUG: First result keys: {endf_results[0].keys() if isinstance(endf_results[0], dict) else 'NOT A DICT'}")
    
    def _is_important_decay_mode(self, mode):
        """
        Check if decay mode should be included (matches JSON/ENSDF parser scope).
        
        IMPORTANT DECAY MODES (to keep):
        - A: Alpha decay
        - B-: Beta minus
        - B+: Beta plus (created by EC/β+ splitting)
        - EC: Electron capture (created by EC/β+ splitting)
        - B-n, B-p, B-a, B-2n, etc.: Delayed particle decays
        
        EXCLUDED MODES:
        - n, p, nn, pp: Simple particle emissions
        - SF: Spontaneous fission
        - IT: Isomeric transition
        - G: Gamma emission (already covered by gamma tables)
        - Any combined mode with SF or IT
        - Exotic combined modes (B+,8, EC,8, etc.)
        
        Args:
            mode: Decay mode string (e.g., "A", "B-", "B-n", "SF")
            
        Returns:
            bool: True if mode should be included, False otherwise
        """
        if not mode:
            return False
        
        # ====================================================================
        # EXCLUDE: Unwanted simple decay modes
        # ====================================================================
        excluded_simple_modes = {
            'n',   # Neutron emission
            'p',   # Proton emission
            'nn',  # Double neutron
            'pp',  # Double proton
            'SF',  # Spontaneous fission
            'IT',  # Isomeric transition
            'G'    # Gamma (handled separately)
        }
        
        if mode in excluded_simple_modes:
            return False
        
        # ====================================================================
        # EXCLUDE: Combined modes with SF or IT
        # ====================================================================
        # Examples: "B-,SF", "B+,SF", "EC,SF", "β-,SF", "B-,IT"
        if ',SF' in mode or 'SF,' in mode:
            return False
        
        if ',IT' in mode or 'IT,' in mode:
            return False
        
        # ====================================================================
        # EXCLUDE: Exotic numeric combined modes
        # ====================================================================
        # Examples: "B+,8", "EC,8", "B-,9", etc.
        # These are rare exotic decay modes not in standard databases
        if ',' in mode:
            parts = mode.split(',')
            for part in parts:
                # Check if any part is a pure number (e.g., "8", "9")
                if part.strip().isdigit():
                    return False
        
        # ====================================================================
        # INCLUDE: Standard important modes
        # ====================================================================
        important_standard_modes = {
            'A',   # Alpha
            'B-',  # Beta minus
            'B+',  # Beta plus (from EC/β+ splitting)
            'EC'   # Electron capture (from EC/β+ splitting)
        }
        
        if mode in important_standard_modes:
            return True
        
        # ====================================================================
        # INCLUDE: Delayed particle decays
        # ====================================================================
        # Identified by: B-n, B-p, B-a, B-2n, B+,p, EC,p, EC,α, etc.
        # Must have B-, B+, or EC followed by particle symbol
        delayed_particle_prefixes = ['B-', 'B+', 'EC']
        
        for prefix in delayed_particle_prefixes:
            if mode.startswith(prefix) and len(mode) > len(prefix):
                # Check for valid delayed particle suffix
                suffix = mode[len(prefix):]
                
                # Remove comma if present (e.g., "B+,p" → "p")
                if suffix.startswith(','):
                    suffix = suffix[1:]
                
                # Valid particle suffixes: n, p, a, α, 2n, 3n, 2p, 3p, etc.
                valid_particles = {'n', 'p', 'a', 'α', '2n', '3n', '4n', 
                                 '2p', '3p', '4p', '2a', '3a'}
                
                if suffix in valid_particles:
                    return True
        
        # ====================================================================
        # DEFAULT: Exclude unknown modes
        # ====================================================================
        # If we don't recognize it, don't include it
        print(f"  Filtering out unknown decay mode: {mode}")
        return False
    
    def _parse_to_dataframes(self):
        """Convert ENDF results into DataFrames with decay mode filtering."""
        print("Converting ENDF data to DataFrames...")
        
        import sys
        from pathlib import Path as PathlibPath
        
        workspace_root = PathlibPath(__file__).parent.parent
        if str(workspace_root) not in sys.path:
            sys.path.insert(0, str(workspace_root))
        
        from JEFF_ENDF_parser import ATOMIC_SYMBOL, extract_bplus_branching, decode_rtyp
        
        decay_rows = []
        nuclide_rows = []
        
        print(f"DEBUG: Processing {len(self.endf_results)} ENDF results")
        
        for idx, result in enumerate(self.endf_results):
            if idx == 0:
                print(f"DEBUG: First result keys: {result.keys()}")
                print(f"DEBUG: ZA = {result.get('ZA')}, Z = {result.get('Z')}, A = {result.get('A')}")
                print(f"DEBUG: Has modes? {('modes' in result)}, count = {len(result.get('modes', []))}")
            
            Z = result.get('Z')
            A = result.get('A')
            MAT = result.get('MAT')
            
            if Z is None or A is None:
                print(f"DEBUG: Skipping result {idx} - missing Z or A")
                continue
            
            element_name = ATOMIC_SYMBOL.get(Z, f'Z{Z}')
            element_symbol = element_name
            
            # Extract nuclide properties
            lis = result.get('LIS', 0)
            liso = result.get('LISO', 0)
            nst = result.get('NST', 0)
            awr = result.get('AWR', 0.0)
            spi = result.get('SPI', 0.0)
            par = result.get('PAR', 0.0)
            
            t_half = result.get('T1/2', (0.0, 0.0))
            halflife = t_half[0] if isinstance(t_half, tuple) else t_half
            halflife_unc = t_half[1] if isinstance(t_half, tuple) else 0.0
            
            ndk = result.get('NDK', 0)
            nsp = result.get('NSP', 0)
            nc = result.get('NC', 0)
            
            nuclide_rows.append({
                'A': A,
                'Z': Z,
                'elementName': element_name,
                'elementSymbol': element_symbol,
                'MAT': MAT,
                'LIS': lis,
                'LISO': liso,
                'NST': nst,
                'AWR': awr,
                'Spin': spi,
                'Parity': par,
                'HalfLife': halflife,
                'HalfLife_uncertainty': halflife_unc,
                'NDK': ndk,
                'NSP': nsp,
                'NC': nc
            })
            
            modes = result.get('modes', [])
            
            if idx == 0 and modes:
                print(f"DEBUG: First mode: {modes[0]}")
            
            for mode_idx, mode in enumerate(modes):
                rtyp = mode.get('RTYP', 0.0)
                
                br_tuple = mode.get('BR', (0.0, 0.0))
                total_branching = br_tuple[0] if isinstance(br_tuple, tuple) else br_tuple
                branching_unc = br_tuple[1] if isinstance(br_tuple, tuple) else 0.0
                
                q_tuple = mode.get('Q', (0.0, 0.0))
                q_value = (q_tuple[0] if isinstance(q_tuple, tuple) else q_tuple) / 1000.0
                q_unc = (q_tuple[1] if isinstance(q_tuple, tuple) else 0.0) / 1000.0
                
                rfs = mode.get('RFS', 0)
                
                # Extract beta spectrum energy
                avg_energy = 0.0
                endpoint_energy = 0.0
                
                if "spectra" in result:
                    primary_decay = int(rtyp)
                    
                    for spec in result.get("spectra", []):
                        styp = spec.get("STYP", -1)
                        
                        if primary_decay == 2 and styp == 2:
                            er_av = spec.get("ER_AV", (0.0, 0.0))
                            if isinstance(er_av, tuple) and er_av[0] > 0:
                                avg_energy = er_av[0] / 1000.0
                            
                            if "discrete" in spec and spec["discrete"]:
                                first_disc = spec["discrete"][0]
                                er_tuple = first_disc.get("ER", (0.0, 0.0))
                                if isinstance(er_tuple, tuple):
                                    endpoint_energy = er_tuple[0] / 1000.0
                        
                        elif styp in [0, 2, 4] and avg_energy == 0.0:
                            er_av = spec.get("ER_AV", (0.0, 0.0))
                            if isinstance(er_av, tuple) and er_av[0] > 0:
                                avg_energy = er_av[0] / 1000.0
                
                # EC/β+ splitting
                primary_mode = int(rtyp)
                
                if primary_mode == 2:
                    bplus_br_pct = extract_bplus_branching(result)
                    bplus_br = bplus_br_pct / 100.0
                    
                    total_br = total_branching * 100.0 if total_branching <= 1.0 else total_branching
                    ec_br = (total_br - bplus_br_pct) / 100.0
                    
                    secondary = int(round((rtyp - primary_mode) * 10))
                    particle_map = {
                        0: "",
                        1: ",β-",
                        2: ",β+",
                        3: ",IT",
                        4: ",α",
                        5: ",n",
                        6: ",SF",
                        7: ",p"
                    }
                    suffix = particle_map.get(secondary, f",{secondary}" if secondary > 0 else "")
                    
                    bplus_label = f"B+{suffix}"
                    ec_label = f"EC{suffix}"
                    
                    # FILTER: Check if B+ mode is important
                    if self._is_important_decay_mode(bplus_label):
                        decay_rows.append({
                            'A': A,
                            'Z': Z,
                            'parentLevel': lis,
                            'decay_mode': bplus_label,
                            'final_level': int(rfs),
                            'RTYP': rtyp,
                            'RFS': rfs,
                            'Q_value': q_value,
                            'Q_uncertainty': q_unc,
                            'Branching_ratio': bplus_br,
                            'Branching_uncertainty': branching_unc,
                            'Intensity': float(bplus_br * 100),
                            'Average_energy': float(avg_energy) if avg_energy > 0 else np.nan,
                            'Endpoint_energy': float(endpoint_energy) if endpoint_energy > 0 else np.nan,
                            'MAT': MAT
                        })
                    
                    # FILTER: Check if EC mode is important
                    if self._is_important_decay_mode(ec_label):
                        decay_rows.append({
                            'A': A,
                            'Z': Z,
                            'parentLevel': lis,
                            'decay_mode': ec_label,
                            'final_level': int(rfs),
                            'RTYP': rtyp,
                            'RFS': rfs,
                            'Q_value': q_value,
                            'Q_uncertainty': q_unc,
                            'Branching_ratio': ec_br,
                            'Branching_uncertainty': branching_unc,
                            'Intensity': float(ec_br * 100),
                            'Average_energy': float(avg_energy) if avg_energy > 0 else np.nan,
                            'Endpoint_energy': float(endpoint_energy) if endpoint_energy > 0 else np.nan,
                            'MAT': MAT
                        })
                
                else:
                    decay_mode_label = self._decode_endf_rtyp(rtyp)
                    
                    # FILTER: Check if this is an important decay mode
                    if decay_mode_label and self._is_important_decay_mode(decay_mode_label):
                        decay_rows.append({
                            'A': A,
                            'Z': Z,
                            'parentLevel': lis,
                            'decay_mode': decay_mode_label,
                            'final_level': int(rfs),
                            'RTYP': rtyp,
                            'RFS': rfs,
                            'Q_value': q_value,
                            'Q_uncertainty': q_unc,
                            'Branching_ratio': total_branching,
                            'Branching_uncertainty': branching_unc,
                            'Intensity': float(total_branching * 100),
                            'Average_energy': float(avg_energy) if avg_energy > 0 else np.nan,
                            'Endpoint_energy': float(endpoint_energy) if endpoint_energy > 0 else np.nan,
                            'MAT': MAT
                        })
        
        print(f"DEBUG: Collected {len(decay_rows)} decay rows")
        print(f"DEBUG: Collected {len(nuclide_rows)} nuclide rows")
        
        if decay_rows and len(decay_rows) > 0:
            print(f"DEBUG: First decay row: {decay_rows[0]}")
        
        if decay_rows:
            decay_df_temp = pd.DataFrame(decay_rows)
            
            numeric_columns = ['Intensity', 'Average_energy', 'Endpoint_energy', 
                             'RTYP', 'RFS', 'Q_value', 'Q_uncertainty', 
                             'Branching_ratio', 'Branching_uncertainty']
            for col in numeric_columns:
                if col in decay_df_temp.columns:
                    decay_df_temp[col] = pd.to_numeric(decay_df_temp[col], errors='coerce')
            
            decay_df_temp.sort_values(by=['A', 'Z', 'parentLevel', 'decay_mode', 'final_level'], inplace=True)
            self.decay_df = decay_df_temp.set_index(['A', 'Z', 'parentLevel', 'decay_mode', 'final_level'])
            
            print(f"Loaded {len(self.decay_df)} ENDF decay transitions (after filtering)")
            
            # Display breakdown by decay type
            decay_modes = self.decay_df.index.get_level_values('decay_mode').unique()
            print("ENDF decay modes loaded (filtered to match ENSDF scope):")
            for mode in sorted(decay_modes):
                count = len(self.decay_df.xs(mode, level='decay_mode'))
                print(f"  - {mode}: {count} transitions")
        
        if nuclide_rows:
            nuclides_df_temp = pd.DataFrame(nuclide_rows)
            nuclides_df_temp.sort_values(by=['A', 'Z'], inplace=True)
            nuclides_df_temp = nuclides_df_temp.drop_duplicates(subset=['A', 'Z'])
            self.nuclides_df = nuclides_df_temp.set_index(['A', 'Z'])
            
            print(f"Loaded {len(self.nuclides_df)} ENDF nuclide entries")
        else:
            print("WARNING: No nuclide rows created!")
    
    def _decode_endf_rtyp(self, rtyp):
        """Decode ENDF RTYP to standard decay mode notation."""
        try:
            from JEFF_ENDF_parser import decode_rtyp
            label = decode_rtyp(rtyp)
            return self._map_endf_decay_mode(rtyp, label)
        except:
            simple_map = {
                0.0: 'G',
                1.0: 'B-',
                2.0: 'B+',
                3.0: 'IT',
                4.0: 'A',
                5.0: 'n',
                6.0: 'SF',
                7.0: 'p'
            }
            return simple_map.get(float(rtyp), f'RTYP-{rtyp}')
    
    def _map_endf_decay_mode(self, rtyp, rtyp_label):
        """Map ENDF RTYP codes to standard decay mode notation."""
        label_map = {
            'γ': 'G',
            'β-': 'B-',
            'β+': 'B+',
            'EC': 'EC',
            'α': 'A',
            'IT': 'IT',
            'n': 'n',
            'p': 'p',
            'SF': 'SF',
            'β-,n': 'B-n',
            'β-,α': 'B-a',
            'β+,α': 'B+,α',
            'β-,p': 'B-p',
            'β+,p': 'B+,p',
            'EC,p': 'EC,p',
            'EC,α': 'EC,α',
            'n,n': 'nn',
            'p,p': 'pp',
        }
        
        return label_map.get(rtyp_label, rtyp_label)
    
    def get_levels_data(self):
        """Get levels DataFrame (empty for ENDF data)."""
        return self.levels_df
    
    def get_gamma_data(self):
        """Get gamma transitions DataFrame (empty for ENDF data)."""
        return self.gamma_df
    
    def get_decay_data(self):
        """Get decay transitions DataFrame."""
        return self.decay_df
    
    def get_nuclides_data(self):
        """Get nuclides DataFrame."""
        return self.nuclides_df
    
    def display_summary(self):
        """Display summary of loaded ENDF data."""
        print("=" * 60)
        print("ENDF DATA MODULE SUMMARY (FILTERED)")
        print("=" * 60)
        
        if not self.decay_df.empty:
            print(f"\nDecay Transitions: {len(self.decay_df)} entries")
            print(f"Unique nuclei (decay): {len(self.decay_df.index.droplevel(['decay_mode', 'final_level']).unique())}")
            decay_modes = self.decay_df.index.get_level_values('decay_mode').unique()
            print(f"Decay modes: {', '.join(sorted(decay_modes))}")
        
        if not self.nuclides_df.empty:
            print(f"\nNuclides: {len(self.nuclides_df)} entries")


def parse_endf_files(endf_dir, file_pattern="*.endf"):
    """Parse ENDF files from a directory using JEFF_ENDF_parser."""
    import sys
    from pathlib import Path as PathlibPath
    
    pyclass_path = PathlibPath(__file__).parent
    if str(pyclass_path) not in sys.path:
        sys.path.insert(0, str(pyclass_path))
    
    from JEFF_ENDF_parser import ENDFNumericDecayParser, ATOMIC_SYMBOL
    
    endf_path = Path(endf_dir)
    if not endf_path.exists():
        raise FileNotFoundError(f"ENDF directory not found: {endf_dir}")
    
    endf_files = list(endf_path.glob(file_pattern))
    if not endf_files:
        print(f"Warning: No files matching '{file_pattern}' found in {endf_dir}")
        return ENDFDataModule([])
    
    print(f"Found {len(endf_files)} ENDF file(s) in {endf_dir}")
    
    all_results = []
    
    for endf_file in endf_files:
        print(f"Parsing {endf_file.name}...")
        try:
            with open(endf_file, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
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
            
            for start_pos, mat_num in section_info:
                try:
                    parser = ENDFNumericDecayParser()
                    parser.load_file(str(endf_file))
                    parser._pos = start_pos
                    result = parser._parse_mf8_mt457()
                    result["MAT"] = mat_num
                    
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
    
    return ENDFDataModule(all_results)
