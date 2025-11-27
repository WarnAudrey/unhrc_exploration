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
        self.absolute_tol = 1e3
        self.relative_tol = 1e-3
        self.strategy = MatchStrategy.HYBRID
        self.hybrid_threshold = 1e5
        self.relaxed_factor = 5.0
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
            comment='#'
        )
        if 'A' in self.endf_decay_df.columns:
            idx_cols = ['A', 'Z', 'parentLevel', 'decay_mode', 'final_level']
            self.endf_decay_df = self.endf_decay_df.set_index(idx_cols)
        print(f"  ENDF entries: {len(self.endf_decay_df)}")
        
        print(f"Loading ENSDF: {self.ensdf_decay_path}")
        self.ensdf_decay_df = pd.read_csv(
            self.ensdf_decay_path, 
            sep=r'\s+', 
            comment='#'
        )
        if 'A' in self.ensdf_decay_df.columns:
            idx_cols = ['A', 'Z', 'parentLevel', 'decay_mode', 'final_level']
            self.ensdf_decay_df = self.ensdf_decay_df.set_index(idx_cols)
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
        print("Building ENSDF level lookup...")
        self.level_lookup = {}
        
        ensdf_reset = self.ensdf_decay_df.reset_index()
        daughter_levels = {}
        
        for idx, row in ensdf_reset.iterrows():
            parent_a = int(row['A'])
            parent_z = int(row['Z'])
            decay_mode = row['decay_mode']
            final_level = row['final_level']
            
            energy = row.get('Average_energy', np.nan)
            if pd.isna(energy):
                energy = row.get('Endpoint_energy', np.nan)
            
            if pd.isna(energy):
                continue
            
            daughter_a, daughter_z = self._get_daughter_nucleus(
                parent_a, 
                parent_z, 
                decay_mode
            )
            key = (daughter_a, daughter_z)
            
            if key not in daughter_levels:
                daughter_levels[key] = {}
            
            if final_level not in daughter_levels[key]:
                daughter_levels[key][final_level] = energy
        
        for (a, z), levels in daughter_levels.items():
            level_data = []
            for level_num, energy in levels.items():
                level_data.append({
                    'level_number': level_num, 
                    'Energy': energy
                })
            
            if level_data:
                df = pd.DataFrame(level_data).sort_values('Energy')
                self.level_lookup[(a, z)] = df
        
        total_levels = sum(len(df) for df in self.level_lookup.values())
        print(f"  Built lookup for {len(self.level_lookup)} daughter nuclei")
        print(f"  Total levels catalogued: {total_levels}\n")
    
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
    
    def _find_matching_level(self, daughter_a, daughter_z, q_value, 
                            parent_name, decay_mode):
        daughter_elem = ATOMIC_SYMBOL.get(daughter_z, f'Z{daughter_z}')
        daughter_name = f"{daughter_elem}-{daughter_a}"
        
        if (daughter_a, daughter_z) not in self.level_lookup:
            return MatchResult(
                matched=False,
                final_level=np.nan,
                ensdf_energy=np.nan,
                endf_q_value=q_value,
                energy_diff=np.nan,
                rel_diff=np.nan,
                match_quality="failed",
                ambiguous=False,
                daughter_nuclide=daughter_name
            )
        
        daughter_levels = self.level_lookup[(daughter_a, daughter_z)]
        level_energies = daughter_levels['Energy'].values
        level_numbers = daughter_levels['level_number'].values
        
        abs_diffs = np.abs(level_energies - q_value)
        
        if self.strategy == MatchStrategy.ABSOLUTE:
            tolerances = np.full_like(level_energies, self.absolute_tol)
        elif self.strategy == MatchStrategy.RELATIVE:
            tolerances = np.maximum(
                level_energies * self.relative_tol, 
                1e-6
            )
        elif self.strategy == MatchStrategy.HYBRID:
            tolerances = np.where(
                level_energies < self.hybrid_threshold,
                self.absolute_tol,
                level_energies * self.relative_tol
            )
        
        within_tol = abs_diffs <= tolerances
        matches_idx = np.where(within_tol)[0]
        
        if len(matches_idx) == 0:
            relaxed_tols = tolerances * self.relaxed_factor
            within_relaxed = abs_diffs <= relaxed_tols
            matches_idx = np.where(within_relaxed)[0]
            
            if len(matches_idx) == 0:
                best_idx = np.argmin(abs_diffs)
                be = level_energies[best_idx]
                bd = abs_diffs[best_idx]
                rd = bd / max(be, 1e-6)
                return MatchResult(
                    matched=False,
                    final_level=np.nan,
                    ensdf_energy=be,
                    endf_q_value=q_value,
                    energy_diff=bd,
                    rel_diff=rd,
                    match_quality="failed",
                    ambiguous=False,
                    daughter_nuclide=daughter_name
                )
            else:
                best_idx = matches_idx[np.argmin(abs_diffs[matches_idx])]
                be = level_energies[best_idx]
                bl = float(level_numbers[best_idx])
                bd = abs_diffs[best_idx]
                rd = bd / max(be, 1e-6)
                amb = len(matches_idx) > 1
                return MatchResult(
                    matched=True,
                    final_level=bl,
                    ensdf_energy=be,
                    endf_q_value=q_value,
                    energy_diff=bd,
                    rel_diff=rd,
                    match_quality="marginal",
                    ambiguous=amb,
                    daughter_nuclide=daughter_name
                )
        
        best_idx = matches_idx[np.argmin(abs_diffs[matches_idx])]
        be = level_energies[best_idx]
        bl = float(level_numbers[best_idx])
        bd = abs_diffs[best_idx]
        rd = bd / max(be, 1e-6)
        amb = len(matches_idx) > 1
        
        qual = "exact" if bd < tolerances[best_idx] * 0.1 else "good"
        
        return MatchResult(
            matched=True,
            final_level=bl,
            ensdf_energy=be,
            endf_q_value=q_value,
            energy_diff=bd,
            rel_diff=rd,
            match_quality=qual,
            ambiguous=amb,
            daughter_nuclide=daughter_name
        )
    
    def match_levels(self, energy_column='Average_energy'):
        print("\n" + "="*70)
        print("ENDF-ENSDF LEVEL MATCHING")
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
        endf_reset['final_level_matched'] = np.nan
        endf_reset['match_quality'] = 'unknown'
        endf_reset['match_ambiguous'] = False
        endf_reset['energy_difference_keV'] = np.nan
        endf_reset['ensdf_level_energy_MeV'] = np.nan
        endf_reset['daughter_nuclide'] = ''
        
        matched_count = 0
        
        for idx, row in endf_reset.iterrows():
            parent_a = int(row['A'])
            parent_z = int(row['Z'])
            decay_mode = row['decay_mode']
            parent_name = row.get('Parent', f"{parent_a}-{parent_z}")
            
            q_value = row.get(energy_column, np.nan)
            if pd.isna(q_value):
                alt = 'Endpoint_energy' if energy_column == 'Average_energy' else 'Average_energy'
                q_value = row.get(alt, np.nan)
            
            if pd.isna(q_value) or q_value <= 0:
                self.unmatched_decays.append(row.to_dict())
                continue
            
            daughter_a, daughter_z = self._get_daughter_nucleus(
                parent_a, 
                parent_z, 
                decay_mode
            )
            
            match = self._find_matching_level(
                daughter_a, 
                daughter_z, 
                q_value, 
                parent_name, 
                decay_mode
            )
            self.match_results.append(match)
            
            if match.matched:
                endf_reset.at[idx, 'final_level_matched'] = match.final_level
                endf_reset.at[idx, 'match_quality'] = match.match_quality
                endf_reset.at[idx, 'match_ambiguous'] = match.ambiguous
                endf_reset.at[idx, 'energy_difference_keV'] = match.energy_diff / 1e3
                endf_reset.at[idx, 'ensdf_level_energy_MeV'] = match.ensdf_energy / 1e6
                endf_reset.at[idx, 'daughter_nuclide'] = match.daughter_nuclide
                matched_count += 1
            else:
                endf_reset.at[idx, 'match_quality'] = 'failed'
                endf_reset.at[idx, 'energy_difference_keV'] = match.energy_diff / 1e3
                endf_reset.at[idx, 'ensdf_level_energy_MeV'] = match.ensdf_energy / 1e6
                endf_reset.at[idx, 'daughter_nuclide'] = match.daughter_nuclide
                self.unmatched_decays.append(row.to_dict())
                
                msg = (f"MATCH FAILED: {parent_name} -> "
                       f"{match.daughter_nuclide} via {decay_mode}")
                warnings.warn(msg)
        
        print(f"Matching complete: {matched_count}/{len(endf_reset)} matched\n")
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
        df_out['final_level'] = df_out['final_level_matched'].fillna(
            df_out['final_level']
        )
        
        idx_cols = ['A', 'Z', 'parentLevel', 'decay_mode', 'final_level']
        df_out = df_out.set_index(idx_cols)
        
        keep_cols = ['Parent', 'Endpoint_energy', 'Average_energy', 'Intensity']
        keep_cols += ['match_quality', 'match_ambiguous', 'energy_difference_keV']
        keep_cols += ['ensdf_level_energy_MeV', 'daughter_nuclide']
        keep_cols = [c for c in keep_cols if c in df_out.columns]
        df_out = df_out[keep_cols]
        
        df_out.to_csv(output_path, sep=' ', float_format='%.6e')
        
        print(f"Saved matched DECAY data to: {output_path}")
        print(f"  Total entries: {len(df_out)}")
        matched_num = len(df_out[df_out['match_quality'] != 'failed'])
        print(f"  Matched: {matched_num}")
    
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
        default=1e3, 
        help="Absolute tolerance in eV"
    )
    parser.add_argument(
        "--rel-tol", 
        type=float, 
        default=1e-3, 
        help="Relative tolerance"
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
