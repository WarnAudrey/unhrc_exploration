#!/usr/bin/env python3
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
import warnings
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

class MatchStrategy(Enum):
    ABSOLUTE = "absolute"
    RELATIVE = "relative"
    HYBRID = "hybrid"

@dataclass
class MatchResult:
    matched: bool
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
    total_decays: int
    matched: int
    unmatched: int
    ambiguous: int
    exact_matches: int
    good_matches: int
    marginal_matches: int
    success_rate: float

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

class ENDFLevelMatcherDECAY:
    
    def __init__(self, endf_decay_path, ensdf_decay_path):
        self.endf_decay_path = Path(endf_decay_path)
        self.ensdf_decay_path = Path(ensdf_decay_path)
        # Default tolerances (energies in eV)
        self.absolute_tol = 2e4  # 20 keV for low energies
        self.relative_tol = 1e-2  # 1% for high energies
        self.strategy = MatchStrategy.HYBRID
        self.hybrid_threshold = 5e5  # 500 keV threshold
        self.relaxed_factor = 5.0  # More relaxed for edge cases
        self.match_results = []
        self.unmatched_decays = []
        self.endf_decay_df = None
        self.ensdf_decay_df = None
        self.matched_decay_df = None
        self._load_decay_files()
        self._build_ensdf_level_lookup()
    
    def _load_decay_files(self):
        print("\n" + "="*70)
        print("LOADING DECAY FILES")
        print("="*70)
        
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
        
        print(f"\nLoading ENSDF: {self.ensdf_decay_path}")
        
        # Read ENSDF file line by line to handle units
        lines = []
        with open(self.ensdf_decay_path, 'r') as f:
            for line in f:
                if line.strip() and not line.strip().startswith('#'):
                    lines.append(line)
        
        # Process data to remove units
        # Only process lines that start with a digit (actual data, not headers)
        processed_data = []
        for line in lines:
            parts = line.split()
            if len(parts) >= 5:
                # Check if first part is a digit (data line) vs letter (header line)
                try:
                    # First 5 are index: A, Z, parentLevel, decay_mode, final_level
                    a = int(parts[0])
                    z = int(parts[1])
                    parent_level = float(parts[2])
                    decay_mode = parts[3]
                    final_level = float(parts[4])
                except ValueError:
                    # This is a header line, skip it
                    continue
                
                # Remaining parts are data columns with units
                # Format: value unit value unit value unit
                # Columns in order: Endpoint_energy, Average_energy, Intensity
                endpoint = np.nan
                average = np.nan
                intensity = np.nan
                
                remaining = parts[5:]
                col_idx = 0  # Track which column we're on (0=Endpoint, 1=Average, 2=Intensity)
                
                i = 0
                while i < len(remaining):
                    # Try to parse as a number
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
        
        self.ensdf_decay_df = pd.DataFrame(processed_data)
        self.ensdf_decay_df = self.ensdf_decay_df.set_index(
            ['A', 'Z', 'parentLevel', 'decay_mode', 'final_level']
        )
        
        print(f"  Index names: {self.ensdf_decay_df.index.names}")
        print(f"  Columns: {list(self.ensdf_decay_df.columns)}")
        print(f"  ENSDF entries: {len(self.ensdf_decay_df)}")
        print("="*70 + "\n")
    
    def _get_daughter_nucleus(self, parent_a, parent_z, decay_mode):
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
    
    def _build_ensdf_level_lookup(self):
        """
        Build lookup table of daughter level energies from ENSDF.
        
        Logic:
        1. For each parent/decay_mode, find Q_max (ground→ground transition)
        2. Calculate daughter level energy = Q_max - Particle_Energy
        3. Store: Daughter(A,Z) → {level_number: level_energy}
        """
        print("Building ENSDF daughter level lookup...")
        print("  Step 1: Finding Q_max for each parent/decay_mode...")
        
        ensdf_reset = self.ensdf_decay_df.reset_index()
        
        # Step 1: Find Q_max (maximum particle energy = ground to ground)
        q_max_lookup = {}  # (parent_a, parent_z, decay_mode) -> Q_max
        
        for idx, row in ensdf_reset.iterrows():
            parent_a = int(row['A'])
            parent_z = int(row['Z'])
            parent_level = float(row['parentLevel'])
            decay_mode = str(row['decay_mode'])
            
            # Only use ground state parent for Q_max
            if parent_level != 0:
                continue
            
            # Get maximum particle energy (should be for ground→ground)
            endpoint = row.get('Endpoint_energy', np.nan)
            average = row.get('Average_energy', np.nan)
            energy = endpoint if not pd.isna(endpoint) else average
            
            if pd.isna(energy) or energy <= 0:
                continue
            
            key = (parent_a, parent_z, decay_mode)
            if key not in q_max_lookup:
                q_max_lookup[key] = energy
            else:
                q_max_lookup[key] = max(q_max_lookup[key], energy)
        
        print(f"    Found Q_max for {len(q_max_lookup)} parent/decay combinations")
        
        # Step 2: Calculate daughter level energies
        print("  Step 2: Calculating daughter level energies...")
        self.daughter_level_lookup = {}  # (daughter_a, daughter_z) -> {level_num: energy}
        
        for idx, row in ensdf_reset.iterrows():
            parent_a = int(row['A'])
            parent_z = int(row['Z'])
            parent_level = float(row['parentLevel'])
            decay_mode = str(row['decay_mode'])
            final_level = float(row['final_level'])
            
            # Only use ground state parent
            if parent_level != 0:
                continue
            
            # Get particle energy
            endpoint = row.get('Endpoint_energy', np.nan)
            average = row.get('Average_energy', np.nan)
            particle_energy = endpoint if not pd.isna(endpoint) else average
            
            if pd.isna(particle_energy):
                continue
            
            # Get Q_max
            q_key = (parent_a, parent_z, decay_mode)
            if q_key not in q_max_lookup:
                continue
            q_max = q_max_lookup[q_key]
            
            # Calculate daughter level energy
            # E_level = Q_max - E_particle (ignoring recoil)
            level_energy = q_max - particle_energy
            
            # Get daughter nucleus
            daughter_a, daughter_z = self._get_daughter_nucleus(parent_a, parent_z, decay_mode)
            d_key = (daughter_a, daughter_z)
            
            if d_key not in self.daughter_level_lookup:
                self.daughter_level_lookup[d_key] = {}
            
            # Store level energy (use minimum if multiple entries)
            if final_level not in self.daughter_level_lookup[d_key]:
                self.daughter_level_lookup[d_key][final_level] = level_energy
            else:
                # Keep the most consistent value (closest to expected)
                self.daughter_level_lookup[d_key][final_level] = min(
                    self.daughter_level_lookup[d_key][final_level],
                    level_energy
                )
        
        # Also store Q_max for ENDF matching
        self.q_max_lookup = q_max_lookup
        
        total_daughters = len(self.daughter_level_lookup)
        total_levels = sum(len(levels) for levels in self.daughter_level_lookup.values())
        print(f"    Built level lookup for {total_daughters} daughter nuclei")
        print(f"    Total daughter levels: {total_levels}")
        
        # Step 3: Build Q_max from ENDF for parents not in ENSDF
        print("  Step 3: Building Q_max from ENDF for missing parents...")
        endf_reset = self.endf_decay_df.reset_index()
        
        for idx, row in endf_reset.iterrows():
            parent_a = int(row['A'])
            parent_z = int(row['Z'])
            parent_level = float(row['parentLevel'])
            decay_mode = str(row['decay_mode'])
            
            # Only use ground state
            if parent_level != 0:
                continue
            
            q_key = (parent_a, parent_z, decay_mode)
            
            # Skip if we already have it from ENSDF
            if q_key in self.q_max_lookup:
                continue
            
            # Get max particle energy from ENDF
            endpoint = row.get('Endpoint_energy', np.nan)
            average = row.get('Average_energy', np.nan)
            energy = endpoint if not pd.isna(endpoint) else average
            
            if pd.isna(energy) or energy <= 0:
                continue
            
            if q_key not in self.q_max_lookup:
                self.q_max_lookup[q_key] = energy
            else:
                self.q_max_lookup[q_key] = max(self.q_max_lookup[q_key], energy)
        
        print(f"    Added Q_max from ENDF: {len(self.q_max_lookup) - len(q_max_lookup)} parents")
        print(f"    Total Q_max available: {len(self.q_max_lookup)}")
        print(f"  Step 4: Lookup ready for matching!\n")
    
    def set_tolerances(self, absolute_tol=None, relative_tol=None, 
                      strategy=None, hybrid_threshold=None, 
                      relaxed_factor=None):
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
        Match ENDF decay to ENSDF daughter levels.
        
        Logic:
        1. Get Q_max for this parent/decay_mode
        2. Calculate ENDF daughter level energy = Q_max - ENDF_particle_energy
        3. Match to ENSDF known daughter level energies
        4. Return the matching level number
        """
        daughter_a, daughter_z = self._get_daughter_nucleus(parent_a, parent_z, decay_mode)
        daughter_elem = ATOMIC_SYMBOL.get(daughter_z, f'Z{daughter_z}')
        daughter_name = f"{daughter_elem}-{daughter_a}"
        
        if verbose:
            print(f"\n  Matching: {parent_name} -> {daughter_name} via {decay_mode}")
            print(f"    ENDF particle energy: {endf_particle_energy/1e3:.2f} keV")
        
        # Step 1: Get Q_max
        q_key = (parent_a, parent_z, decay_mode)
        if q_key not in self.q_max_lookup:
            if verbose:
                print(f"    ✗ No Q_max data for this parent/decay combination")
            return MatchResult(
                matched=False,
                final_level=np.nan,
                ensdf_energy=np.nan,
                endf_q_value=endf_particle_energy,
                energy_diff=np.nan,
                rel_diff=np.nan,
                match_quality="no_q_max",
                ambiguous=False,
                daughter_nuclide=daughter_name
            )
        
        q_max = self.q_max_lookup[q_key]
        if verbose:
            print(f"    Q_max: {q_max/1e3:.2f} keV")
        
        # Step 2: Calculate ENDF daughter level energy
        endf_level_energy = q_max - endf_particle_energy
        if verbose:
            print(f"    Calculated ENDF level energy: {endf_level_energy/1e3:.2f} keV")
        
        # Step 3: Look up daughter levels
        d_key = (daughter_a, daughter_z)
        if d_key not in self.daughter_level_lookup:
            # If no ENSDF data, but level energy is close to 0, assign ground state
            if abs(endf_level_energy) <= self.absolute_tol:
                if verbose:
                    print(f"    ~ No ENSDF data, but level ~0, assigning ground state")
                return MatchResult(
                    matched=True,
                    final_level=0.0,
                    ensdf_energy=0.0,
                    endf_q_value=endf_particle_energy,
                    energy_diff=abs(endf_level_energy),
                    rel_diff=0.0,
                    match_quality="assumed_ground",
                    ambiguous=False,
                    daughter_nuclide=daughter_name
                )
            else:
                if verbose:
                    print(f"    ✗ No ENSDF level data for daughter {daughter_name}")
                return MatchResult(
                    matched=False,
                    final_level=np.nan,
                    ensdf_energy=np.nan,
                    endf_q_value=endf_particle_energy,
                    energy_diff=np.nan,
                    rel_diff=np.nan,
                    match_quality="no_daughter_levels",
                    ambiguous=False,
                    daughter_nuclide=daughter_name
                )
        
        daughter_levels = self.daughter_level_lookup[d_key]
        if verbose:
            print(f"    Found {len(daughter_levels)} ENSDF levels for {daughter_name}")
        
        # Step 4: Match to closest level
        best_match = None
        best_diff = np.inf
        matches_within_tol = []
        
        for level_num, ensdf_level_energy in daughter_levels.items():
            abs_diff = abs(ensdf_level_energy - endf_level_energy)
            
            # Calculate tolerance
            if self.strategy == MatchStrategy.ABSOLUTE:
                tolerance = self.absolute_tol
            elif self.strategy == MatchStrategy.RELATIVE:
                tolerance = max(abs(ensdf_level_energy) * self.relative_tol, 1e3)
            elif self.strategy == MatchStrategy.HYBRID:
                if abs(ensdf_level_energy) < self.hybrid_threshold:
                    tolerance = self.absolute_tol
                else:
                    tolerance = abs(ensdf_level_energy) * self.relative_tol
            
            if abs_diff <= tolerance:
                matches_within_tol.append((abs_diff, level_num, ensdf_level_energy, tolerance))
            
            if abs_diff < best_diff:
                best_diff = abs_diff
                best_match = (abs_diff, level_num, ensdf_level_energy, tolerance)
        
        # Return best match
        if matches_within_tol:
            matches_within_tol.sort(key=lambda x: x[0])
            abs_diff, level_num, ensdf_e, tol = matches_within_tol[0]
            
            rel_diff = abs_diff / max(abs(ensdf_e), 1e-6)
            ambiguous = len(matches_within_tol) > 1
            
            if abs_diff < tol * 0.1:
                quality = "exact"
            elif abs_diff < tol * 0.5:
                quality = "good"
            else:
                quality = "acceptable"
            
            if verbose:
                print(f"    ✓ Matched to level {int(level_num)}")
                print(f"      ENSDF level energy: {ensdf_e/1e3:.2f} keV")
                print(f"      Difference: {abs_diff/1e3:.2f} keV ({quality})")
            
            return MatchResult(
                matched=True,
                final_level=level_num,
                ensdf_energy=ensdf_e,
                endf_q_value=endf_particle_energy,
                energy_diff=abs_diff,
                rel_diff=rel_diff,
                match_quality=quality,
                ambiguous=ambiguous,
                daughter_nuclide=daughter_name
            )
        
        # Try relaxed
        if best_match:
            abs_diff, level_num, ensdf_e, tol = best_match
            if abs_diff <= tol * self.relaxed_factor:
                rel_diff = abs_diff / max(abs(ensdf_e), 1e-6)
                if verbose:
                    print(f"    ~ Marginal match to level {int(level_num)}")
                    print(f"      ENSDF level energy: {ensdf_e/1e3:.2f} keV")
                    print(f"      Difference: {abs_diff/1e3:.2f} keV (marginal)")
                
                return MatchResult(
                    matched=True,
                    final_level=level_num,
                    ensdf_energy=ensdf_e,
                    endf_q_value=endf_particle_energy,
                    energy_diff=abs_diff,
                    rel_diff=rel_diff,
                    match_quality="marginal",
                    ambiguous=False,
                    daughter_nuclide=daughter_name
                )
        
        # No match
        if verbose:
            if best_match:
                _, _, ensdf_e, _ = best_match
                print(f"    ✗ No match (closest: {ensdf_e/1e3:.2f} keV, diff: {best_diff/1e3:.2f} keV)")
            else:
                print(f"    ✗ No match found")
        
        return MatchResult(
            matched=False,
            final_level=np.nan,
            ensdf_energy=best_match[2] if best_match else np.nan,
            endf_q_value=endf_particle_energy,
            energy_diff=best_diff,
            rel_diff=best_diff / max(abs(best_match[2]), 1e-6) if best_match else np.nan,
            match_quality="failed",
            ambiguous=False,
            daughter_nuclide=daughter_name
        )
    
    def match_levels(self, energy_column='Endpoint_energy'):
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
        
        endf_reset = self.endf_decay_df.reset_index()
        endf_reset['final_level_matched'] = np.nan
        endf_reset['match_quality'] = 'unknown'
        endf_reset['match_ambiguous'] = False
        endf_reset['energy_difference_keV'] = np.nan
        endf_reset['ensdf_particle_energy_MeV'] = np.nan
        endf_reset['daughter_nuclide'] = ''
        
        matched_count = 0
        no_ensdf_count = 0
        
        for idx, row in endf_reset.iterrows():
            parent_a = int(row['A'])
            parent_z = int(row['Z'])
            parent_level = float(row['parentLevel'])
            decay_mode = str(row['decay_mode'])
            parent_name = row.get('Parent', f"{parent_a}-{parent_z}")
            
            # Get ENDF particle energy
            endf_energy = row.get(energy_column, np.nan)
            if pd.isna(endf_energy):
                alt_col = 'Average_energy' if energy_column == 'Endpoint_energy' else 'Endpoint_energy'
                endf_energy = row.get(alt_col, np.nan)
            
            if pd.isna(endf_energy):
                self.unmatched_decays.append(row.to_dict())
                endf_reset.at[idx, 'match_quality'] = 'no_endf_energy'
                continue
            
            # Verbose for first 3 matches
            verbose = idx < 3
            
            # Find matching transition
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
            
            if match.matched:
                endf_reset.at[idx, 'final_level_matched'] = match.final_level
                endf_reset.at[idx, 'match_quality'] = match.match_quality
                endf_reset.at[idx, 'match_ambiguous'] = match.ambiguous
                endf_reset.at[idx, 'energy_difference_keV'] = match.energy_diff / 1e3
                endf_reset.at[idx, 'ensdf_particle_energy_MeV'] = match.ensdf_energy / 1e6
                endf_reset.at[idx, 'daughter_nuclide'] = match.daughter_nuclide
                matched_count += 1
            else:
                endf_reset.at[idx, 'match_quality'] = match.match_quality
                if match.match_quality == "no_ensdf_data":
                    no_ensdf_count += 1
                else:
                    self.unmatched_decays.append(row.to_dict())
                    
                if not pd.isna(match.energy_diff):
                    endf_reset.at[idx, 'energy_difference_keV'] = match.energy_diff / 1e3
                if not pd.isna(match.ensdf_energy):
                    endf_reset.at[idx, 'ensdf_particle_energy_MeV'] = match.ensdf_energy / 1e6
                endf_reset.at[idx, 'daughter_nuclide'] = match.daughter_nuclide
        
        # Count match types
        exact = sum(1 for m in self.match_results if m.match_quality == "exact")
        good = sum(1 for m in self.match_results if m.match_quality == "good")
        acceptable = sum(1 for m in self.match_results if m.match_quality == "acceptable")
        marginal = sum(1 for m in self.match_results if m.match_quality == "marginal")
        assumed = sum(1 for m in self.match_results if m.match_quality == "assumed_ground")
        
        # Count failure reasons
        no_q_max = sum(1 for m in self.match_results if m.match_quality == "no_q_max")
        no_daughter = sum(1 for m in self.match_results if m.match_quality == "no_daughter_levels")
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
        print(f"  ✗ No Q_max for parent: {no_q_max}")
        print(f"  ✗ No daughter level data: {no_daughter}")
        print(f"  ✗ Energy mismatch: {failed}")
        print(f"  Total failed: {no_q_max + no_daughter + failed}\n")
        
        self.matched_decay_df = endf_reset
        return self.matched_decay_df
    
    def get_statistics(self):
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
        if self.matched_decay_df is None:
            raise ValueError("No matched data. Run match_levels() first.")
        
        df_out = self.matched_decay_df.copy()
        
        # Update final_level with matched values
        df_out.loc[df_out['final_level_matched'].notna(), 'final_level'] = df_out['final_level_matched']
        
        idx_cols = ['A', 'Z', 'parentLevel', 'decay_mode', 'final_level']
        df_out = df_out.set_index(idx_cols)
        
        # Keep relevant columns (match ENDF format plus diagnostics)
        keep_cols = []
        if 'Parent' in df_out.columns:
            keep_cols.append('Parent')
        keep_cols += ['Endpoint_energy', 'Average_energy', 'Intensity']
        keep_cols += ['match_quality', 'match_ambiguous', 'energy_difference_keV']
        keep_cols += ['ensdf_particle_energy_MeV', 'daughter_nuclide']
        keep_cols = [c for c in keep_cols if c in df_out.columns]
        df_out = df_out[keep_cols]
        
        # Save with proper MultiIndex formatting
        with open(output_path, 'w') as f:
            # Write header with proper spacing
            # Index column names
            index_names = ['A', 'Z', 'parentLevel', 'decay_mode', 'final_level']
            header_spacing = ' ' * 44  # Space for index columns
            data_cols = ' '.join([f'{col:>18}' for col in keep_cols])
            f.write(f"{header_spacing}{data_cols}\n")
            f.write(f"{' '.join([f'{name:<3}' if i < 2 else f'{name:<15}' for i, name in enumerate(index_names)])}\n")
            
            # Write data rows
            for idx, row in df_out.iterrows():
                # Format index values
                a_val = f"{idx[0]:<4d}"
                z_val = f"{idx[1]:<4d}"
                pl_val = f"{idx[2]:<15.4e}"
                dm_val = f"{idx[3]:<15}"
                fl_val = f"{idx[4]:<15.4e}"
                
                # Format data values
                data_vals = []
                for col in keep_cols:
                    val = row[col]
                    if pd.isna(val):
                        data_vals.append(' ' * 18)
                    elif isinstance(val, str):
                        data_vals.append(f"{val:>18}")
                    elif isinstance(val, bool):
                        data_vals.append(f"{str(val):>18}")
                    else:
                        data_vals.append(f"{val:>18.6e}")
                
                line = f"{a_val}{z_val}{pl_val}{dm_val}{fl_val} {' '.join(data_vals)}\n"
                f.write(line)
        
        print(f"\nSaved matched DECAY data to: {output_path}")
        print(f"  Total entries: {len(df_out)}")
        matched_num = len(df_out[df_out['match_quality'] != 'failed'])
        print(f"  Matched: {matched_num}")
        print(f"  Failed: {len(df_out) - matched_num}")
    
    def export_unmatched(self, filename):
        if not self.unmatched_decays:
            print("No unmatched decays to export.")
            return
        
        df = pd.DataFrame(self.unmatched_decays)
        df.to_csv(filename, sep=' ', float_format='%.6e', index=False)
        print(f"Exported {len(self.unmatched_decays)} unmatched decays to {filename}")
    
    def export_match_details(self, filename):
        if not self.match_results:
            print("No match results to export.")
            return
        
        data = []
        for i, result in enumerate(self.match_results):
            if self.matched_decay_df is not None:
                row_info = self.matched_decay_df.iloc[i]
            else:
                row_info = {}
            
            entry = {}
            entry['Parent'] = row_info.get('Parent', '')
            entry['decay_mode'] = row_info.get('decay_mode', '')
            entry['Daughter'] = result.daughter_nuclide
            entry['matched'] = int(result.matched)
            entry['final_level'] = result.final_level
            entry['ensdf_energy_MeV'] = result.ensdf_energy / 1e6
            entry['endf_q_MeV'] = result.endf_q_value / 1e6
            entry['diff_keV'] = result.energy_diff / 1e3
            entry['rel_diff_pct'] = result.rel_diff * 100
            entry['quality'] = result.match_quality
            entry['ambiguous'] = int(result.ambiguous)
            
            data.append(entry)
        
        df = pd.DataFrame(data)
        df.to_csv(filename, sep=' ', float_format='%.6e', index=False)
        print(f"Exported {len(data)} match details to {filename}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Match ENDF decay final levels to ENSDF levels"
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
        default="hybrid"
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
    
    matcher = ENDFLevelMatcherDECAY(
        endf_decay_path=args.endf, 
        ensdf_decay_path=args.ensdf
    )
    
    matcher.set_tolerances(
        absolute_tol=args.abs_tol, 
        relative_tol=args.rel_tol, 
        strategy=args.strategy
    )
    
    matched_df = matcher.match_levels()
    matcher.print_report()
    matcher.save_matched_decay(args.output)
    
    if args.export_unmatched:
        matcher.export_unmatched(args.export_unmatched)
    
    if args.export_details:
        matcher.export_match_details(args.export_details)
    
    print("\nLevel matching complete!")
