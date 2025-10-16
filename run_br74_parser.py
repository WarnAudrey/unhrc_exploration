#!/usr/bin/env python3
"""
ENDF-6 Radioactive Decay Data Parser (MF=8, MT=457) - Universal MAT Support

Parses ENDF-6 format radioactive decay data from external files.
Supports ALL material (MAT) numbers and automatically detects all nuclides.
Implements proper B+/EC splitting according to ENDF-102 specifications.

Features:
- Parses ALL MF=8 MT=457 sections in a single file
- Works with ANY nuclide (any MAT number)
- Handles multiple isomeric states
- Groups results by nuclide and displays combined tables
- Accurate B+/EC branching ratio calculations

Usage:
    python3 run_br74_parser.py <endf_file.txt>              # Summary view
    python3 run_br74_parser.py --verbose <endf_file.txt>    # Full details
"""

import re
from typing import Any, Dict, List, Optional, Tuple
import numpy as np


class Tabulated1D:
    """Tabulated function with FIXED interpolation."""
    def __init__(self, x, y, breakpoints=None, interpolation=None):
        x_arr = np.asarray(list(x) if not isinstance(x, np.ndarray) else x, dtype=float)
        y_arr = np.asarray(list(y) if not isinstance(y, np.ndarray) else y, dtype=float)
        if breakpoints is None or interpolation is None:
            self.breakpoints = np.array([x_arr.size], dtype=int)
            self.interpolation = np.array([2], dtype=int)
        else:
            self.breakpoints = np.asarray(list(breakpoints), dtype=int)
            self.interpolation = np.asarray(list(interpolation), dtype=int)
        self.x = x_arr
        self.y = y_arr
    
    @property
    def x(self):
        return self._x
    
    @x.setter
    def x(self, x):
        self._x = np.asarray(x, dtype=float)
    
    @property
    def y(self):
        return self._y
    
    @y.setter
    def y(self, y):
        self._y = np.asarray(y, dtype=float)


class Tabulated2D:
    def __init__(self, breakpoints, interpolation):
        self.breakpoints = np.asarray(list(breakpoints), dtype=int)
        self.interpolation = np.asarray(list(interpolation), dtype=int)


class ENDFNumericDecayParser:
    """Parser for MF=8 MT=457."""
    
    ENDF_FLOAT_RE = re.compile(r"([\s\-\+]?\d*\.\d+)([\+\-]) ?(\d+)")
    
    def __init__(self, text: Optional[str] = None):
        self._lines: List[str] = []
        self._pos: int = 0
        if text is not None:
            self.load_text(text)
    
    def load_text(self, text: str):
        self._lines = text.splitlines()
        self._pos = 0
    
    def load_file(self, path: str):
        """Load ENDF data from file."""
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            self._lines = fh.read().splitlines()
        self._pos = 0
    
    def _readline(self) -> str:
        if self._pos >= len(self._lines):
            raise EOFError("EOF")
        line = self._lines[self._pos]
        self._pos += 1
        return f"{line:<80}" if len(line) < 80 else line
    
    def _scan_to_mf_mt(self, mf: int, mt: int) -> bool:
        for i in range(self._pos, len(self._lines)):
            ln = f"{self._lines[i]:<80}" if len(self._lines[i]) < 80 else self._lines[i]
            try:
                mf_val = self._int_endf(ln[70:72])
                mt_val = self._int_endf(ln[72:75])
                if mf_val == mf and mt_val == mt:
                    self._pos = i
                    return True
            except:
                continue
        return False
    
    @classmethod
    def _py_float_endf(cls, s: str) -> float:
        return float(cls.ENDF_FLOAT_RE.sub(r"\1e\2\3", s))
    
    @staticmethod
    def _int_endf(s: str) -> int:
        return 0 if s.strip() == "" else int(s)
    
    def _get_cont_record(self, skip_c=False):
        line = self._readline()
        c1 = None if skip_c else self._py_float_endf(line[:11])
        c2 = None if skip_c else self._py_float_endf(line[11:22])
        l1 = self._int_endf(line[22:33])
        l2 = self._int_endf(line[33:44])
        n1 = self._int_endf(line[44:55])
        n2 = self._int_endf(line[55:66])
        return c1, c2, l1, l2, n1, n2
    
    def _get_head_record(self):
        line = self._readline()
        za = int(self._py_float_endf(line[:11]))
        awr = self._py_float_endf(line[11:22])
        l1 = self._int_endf(line[22:33])
        l2 = self._int_endf(line[33:44])
        n1 = self._int_endf(line[44:55])
        n2 = self._int_endf(line[55:66])
        return za, awr, l1, l2, n1, n2
    
    def _get_list_record(self):
        items = list(self._get_cont_record())
        npl = int(items[4])
        b = np.empty(npl)
        for i in range((npl - 1) // 6 + 1):
            line = self._readline()
            n = min(6, npl - 6 * i)
            for j in range(n):
                b[6 * i + j] = self._py_float_endf(line[11 * j : 11 * (j + 1)])
        return items, b
    
    def _get_tab1_record(self):
        line = self._readline()
        c1 = self._py_float_endf(line[:11])
        c2 = self._py_float_endf(line[11:22])
        l1 = self._int_endf(line[22:33])
        l2 = self._int_endf(line[33:44])
        n_regions = self._int_endf(line[44:55])
        n_pairs = self._int_endf(line[55:66])
        params = [c1, c2, l1, l2]
        
        breakpoints = np.zeros(n_regions, dtype=int)
        interpolation = np.zeros(n_regions, dtype=int)
        m = 0
        for _ in range((n_regions - 1) // 3 + 1):
            line = self._readline()
            to_read = min(3, n_regions - m)
            for _ in range(to_read):
                breakpoints[m] = self._int_endf(line[0:11])
                interpolation[m] = self._int_endf(line[11:22])
                line = line[22:]
                m += 1
        
        x = np.zeros(n_pairs)
        y = np.zeros(n_pairs)
        m = 0
        for _ in range((n_pairs - 1) // 3 + 1):
            line = self._readline()
            to_read = min(3, n_pairs - m)
            for _ in range(to_read):
                x[m] = self._py_float_endf(line[:11])
                y[m] = self._py_float_endf(line[11:22])
                line = line[22:]
                m += 1
        
        return params, Tabulated1D(x, y, breakpoints, interpolation)
    
    def _get_tab2_record(self):
        params = self._get_cont_record()
        n_regions = params[4]
        breakpoints = np.zeros(n_regions, dtype=int)
        interpolation = np.zeros(n_regions, dtype=int)
        m = 0
        for _ in range((n_regions - 1) // 3 + 1):
            line = self._readline()
            to_read = min(3, n_regions - m)
            for _ in range(to_read):
                breakpoints[m] = self._int_endf(line[0:11])
                interpolation[m] = self._int_endf(line[11:22])
                line = line[22:]
                m += 1
        return params, Tabulated2D(breakpoints, interpolation)
    
    def _get_intg_record(self):
        items = self._get_cont_record()
        ndigit = items[2]
        npar = items[3]
        nlines = items[4]
        nrow_rules = {2: 18, 3: 12, 4: 11, 5: 9, 6: 8}
        nrow = nrow_rules[ndigit]
        corr = np.identity(npar)
        for _ in range(nlines):
            line = self._readline()
            ii = self._int_endf(line[:5]) - 1
            jj = self._int_endf(line[5:10]) - 1
            factor = 10 ** ndigit
            for j in range(nrow):
                if jj + j >= ii:
                    break
                element = self._int_endf(line[11 + (ndigit + 1) * j : 11 + (ndigit + 1) * (j + 1)])
                if element > 0:
                    corr[ii, jj] = (element + 0.5) / factor
                elif element < 0:
                    corr[ii, jj] = (element - 0.5) / factor
        corr = corr + corr.T - np.diag(corr.diagonal())
        return corr
    
    def _parse_mf8_mt457(self) -> Dict[str, Any]:
        za, awr, lis, liso, nst, nsp = self._get_head_record()
        data = {"ZA": za, "AWR": awr, "LIS": lis, "LISO": liso, "NST": nst, "NSP": nsp}
        
        if nst == 1:
            self._get_list_record()
            (spi, par, *_), _ = self._get_list_record()
            data["SPI"] = spi
            data["PAR"] = par
            return data
        
        items, values = self._get_list_record()
        data["T1/2"] = (items[0], items[1])
        data["NC"] = items[4] // 2
        data["Ex"] = list(zip(values[::2], values[1::2]))
        
        items, values_modes = self._get_list_record()
        data["SPI"], data["PAR"], *_ = items
        data["NDK"] = int(items[5])
        data["modes"] = []
        
        if values_modes.size >= 6 * data["NDK"]:
            for i in range(data["NDK"]):
                rtyp = float(values_modes[6 * i])
                rfs = float(values_modes[6 * i + 1])
                q = (float(values_modes[6 * i + 2]), float(values_modes[6 * i + 3]))
                br = (float(values_modes[6 * i + 4]), float(values_modes[6 * i + 5]))
                data["modes"].append({"RTYP": rtyp, "RFS": rfs, "Q": q, "BR": br})
        
        data["spectra"] = []
        for _ in range(nsp):
            items, values = self._get_list_record()
            _, styp, lcon, lcov, _, ner = items
            spectrum = {"STYP": styp, "LCON": lcon, "LCOV": lcov, "NER": ner}
            spectrum["FD"] = tuple(values[0:2].astype(float))
            spectrum["ER_AV"] = tuple(values[2:4].astype(float))
            spectrum["FC"] = tuple(values[4:6].astype(float))
            
            if lcon != 1:
                spectrum["discrete"] = []
                for _ in range(ner):
                    try:
                        items_d, values_d = self._get_list_record()
                        discrete = {}
                        discrete["ER"] = tuple(items_d[0:2])
                        
                        # Handle incomplete data gracefully
                        if len(values_d) == 0:
                            continue
                        
                        discrete["RTYP"] = float(values_d[0]) if len(values_d) > 0 else 0.0
                        discrete["TYPE"] = float(values_d[1]) if len(values_d) > 1 else 0.0
                        
                        if styp == 0:  # Gamma spectrum
                            if len(values_d) >= 12:
                                discrete["RI"] = tuple(values_d[2:4].astype(float))
                                discrete["RIS"] = tuple(values_d[4:6].astype(float))
                                discrete["RICC"] = tuple(values_d[6:8].astype(float))
                                discrete["RICK"] = tuple(values_d[8:10].astype(float))
                                discrete["RICL"] = tuple(values_d[10:12].astype(float))
                        elif styp == 2:  # Beta+ spectrum
                            if len(values_d) >= 6:
                                discrete["INTENSITY"] = tuple(values_d[4:6].astype(float))
                        
                        discrete["_raw_values"] = values_d
                        spectrum["discrete"].append(discrete)
                    except (IndexError, ValueError, EOFError) as e:
                        # Skip incomplete or malformed records
                        continue
            
            if lcon != 0:
                params, rp = self._get_tab1_record()
                spectrum["continuous"] = {"RTYP": params[0], "RP": rp}
            
            if lcov not in (0, 2) and lcon != 0:
                items_c, values_c = self._get_list_record()
                covar_cont = {"LB": items_c[3]}
                covar_cont["Ek"] = np.array(values_c[::2], dtype=float)
                covar_cont["Fk"] = np.array(values_c[1::2], dtype=float)
                spectrum["continuous_covariance"] = covar_cont
            
            if lcov not in (0, 1):
                (__, ____, ls, lb, ne, nerp), values_dc = self._get_list_record()
                covar_disc = {"LS": ls, "LB": lb, "NE": ne, "NERP": nerp}
                covar_disc["Ek"] = np.array(values_dc[:nerp], dtype=float)
                covar_disc["Fkk"] = np.array(values_dc[nerp:], dtype=float)
                spectrum["discrete_covariance"] = covar_disc
            
            data["spectra"].append(spectrum)
        
        return data


def extract_bplus_branching(parsed_data):
    """Extract B+ branching ratio by summing individual β+ transition intensities."""
    for spec in parsed_data["spectra"]:
        if spec["STYP"] == 2 and "discrete" in spec:  # Beta+ spectrum
            total_intensity = 0.0
            
            for discrete in spec["discrete"]:
                if "INTENSITY" in discrete:
                    intensity = discrete["INTENSITY"][0]
                    total_intensity += intensity
            
            if total_intensity > 0:
                return total_intensity
            else:
                return spec["FD"][0] * 100.0 if spec["FD"][0] > 1.0 else spec["FD"][0]
    
    return 0.0


def format_and_print_combined_table(all_results):
    """Generate and print combined formatted table for all decay levels and nuclides."""
    
    if not all_results:
        print("No data to display")
        return
    
    # Group results by nuclide (ZA)
    nuclides = {}
    for result in all_results:
        za = result["ZA"]
        if za not in nuclides:
            nuclides[za] = []
        nuclides[za].append(result)
    
    # Element symbol lookup (expanded)
    ELEMENT_SYMBOLS = {
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
    
    # Print header
    print()
    print("="*140)
    print(f"ENDF-6 Radioactive Decay Data Parser (ENDF-102 Compliant) - Universal MAT Support")
    print("="*140)
    print()
    print(f"Number of nuclides: {len(nuclides)}")
    print(f"Total decay sections: {len(all_results)}")
    print()
    
    # Show info for each nuclide and its states
    state_counter = 0
    for za in sorted(nuclides.keys()):
        z = za // 1000
        a = za % 1000
        element = ELEMENT_SYMBOLS.get(z, f'Z{z}')
        
        print(f"Nuclide: {element}-{a} (Z={z}, A={a}, ZA={za})")
        print(f"  Number of decay states: {len(nuclides[za])}")
        print()
        
        for result in nuclides[za]:
            lis = result.get("LIS", 0)
            liso = result.get("LISO", 0)
            mat = result.get("MAT", 0)
            halflife_s = result["T1/2"][0]
            
            level_name = f"{element}-{a}" if lis == 0 else f"{element}-{a}m{lis}" if lis > 0 else f"{element}-{a}"
            
            print(f"  State {state_counter} (MAT={mat}, LIS={lis}, LISO={liso}):")
            print(f"    Name: {level_name}")
            print(f"    Half-life: {halflife_s:.4e} seconds ({halflife_s/60.0:.2f} minutes)")
            
            if result.get("modes"):
                mode = result["modes"][0]
                q_kev = mode["Q"][0] / 1000.0
                rtyp = mode["RTYP"]
                total_br_pct = mode["BR"][0] * 100.0 if mode["BR"][0] <= 1.0 else mode["BR"][0]
                
                print(f"    Q-value: {q_kev:.4f} keV")
                print(f"    RTYP: {rtyp} → {'EC/β+ decay' if rtyp == 2.0 else f'Decay type {rtyp}'}")
                
                # Calculate B+/EC split
                bplus_br_pct = extract_bplus_branching(result)
                ec_br_pct = total_br_pct - bplus_br_pct
                
                print(f"    Total Branching Ratio: {total_br_pct:.4f}%")
                print(f"    β+ Branching: {bplus_br_pct:.4f}%")
                print(f"    EC Branching: {ec_br_pct:.4f}%")
                
                # Mean energies
                mean_alpha = 0.0
                mean_beta = 0.0
                mean_gamma = 0.0
                
                for spec in result["spectra"]:
                    styp = spec["STYP"]
                    er_av_kev = spec["ER_AV"][0] / 1000.0
                    
                    if styp == 0:  # Gamma
                        mean_gamma = er_av_kev
                    elif styp == 2:  # Beta+
                        mean_beta = er_av_kev
                    elif styp == 4:  # Alpha
                        mean_alpha = er_av_kev
                
                print(f"    Mean energies: α={mean_alpha:.4f} keV, β={mean_beta:.4f} keV, γ={mean_gamma:.4f} keV")
            print()
            state_counter += 1
    
    # Print combined table
    print("="*140)
    print("DECAY MODES TABLE (ALL NUCLIDES AND LEVELS)")
    print("="*140)
    print()
    print(f"{'MAT':5s} {'A':4s} {'Z':3s} {'Parent':>8s} {'Decay':>8s} {'Daughter':>8s} {'Q-value':>15s} {'Branching':>15s} {'Half-life':>15s} {'α Energy':>15s} {'β Energy':>15s} {'γ Energy':>15s}")
    print(f"{'':5s} {'':4s} {'':3s} {'Level':>8s} {'Mode':>8s} {'Level':>8s} {'(keV)':>15s} {'Ratio (%)':>15s} {'(seconds)':>15s} {'(keV)':>15s} {'(keV)':>15s} {'(keV)':>15s}")
    print("-"*140)
    
    # Print rows for each nuclide, state, and decay mode
    for za in sorted(nuclides.keys()):
        z = za // 1000
        a = za % 1000
        
        for result in nuclides[za]:
            lis = result.get("LIS", 0)
            mat = result.get("MAT", 0)
            halflife_s = result["T1/2"][0]
            
            if not result.get("modes"):
                continue
            
            mode = result["modes"][0]
            q_kev = mode["Q"][0] / 1000.0
            rtyp = mode["RTYP"]
            total_br_pct = mode["BR"][0] * 100.0 if mode["BR"][0] <= 1.0 else mode["BR"][0]
            
            # Mean energies
            mean_alpha = 0.0
            mean_beta = 0.0
            mean_gamma = 0.0
            
            for spec in result["spectra"]:
                styp = spec["STYP"]
                er_av_kev = spec["ER_AV"][0] / 1000.0
                
                if styp == 0:
                    mean_gamma = er_av_kev
                elif styp == 2:
                    mean_beta = er_av_kev
                elif styp == 4:
                    mean_alpha = er_av_kev
            
            # Calculate B+/EC split
            bplus_br_pct = extract_bplus_branching(result)
            ec_br_pct = total_br_pct - bplus_br_pct
            
            # Print B+ row
            print(f"{mat:<5d} {a:<4d} {z:<3d} {lis:>8d} {'B+':>8s} {0:>8d} {q_kev:>15.4f} {bplus_br_pct:>15.4f} {halflife_s:>15.4e} {mean_alpha:>15.4f} {mean_beta:>15.4f} {mean_gamma:>15.4f}")
            
            # Print EC row
            print(f"{mat:<5d} {a:<4d} {z:<3d} {lis:>8d} {'EC':>8s} {0:>8d} {q_kev:>15.4f} {ec_br_pct:>15.4f} {halflife_s:>15.4e} {mean_alpha:>15.4f} {mean_beta:>15.4f} {mean_gamma:>15.4f}")
    
    print("-"*140)
    print()
    print("Summary:")
    for za in sorted(nuclides.keys()):
        z = za // 1000
        a = za % 1000
        element = ELEMENT_SYMBOLS.get(z, f'Z{z}')
        
        for result in nuclides[za]:
            lis = result.get("LIS", 0)
            mat = result.get("MAT", 0)
            halflife_s = result["T1/2"][0]
            
            if result.get("modes"):
                bplus_br_pct = extract_bplus_branching(result)
                mode = result["modes"][0]
                total_br_pct = mode["BR"][0] * 100.0 if mode["BR"][0] <= 1.0 else mode["BR"][0]
                ec_br_pct = total_br_pct - bplus_br_pct
                
                level_name = f"{element}-{a}" if lis == 0 else f"{element}-{a}m{lis}" if lis > 0 else f"{element}-{a}"
                print(f"  • {level_name} (MAT={mat}, level {lis}) undergoes EC/β+ decay with T½ = {halflife_s/60.0:.2f} minutes")
                print(f"    - β+ emission: {bplus_br_pct:.2f}% | EC: {ec_br_pct:.2f}%")
    print("="*140)
    print()


def format_and_print_table(parsed_data):
    """Generate and print formatted table according to ENDF-102 specifications."""
    
    # Extract Z and A
    za = parsed_data["ZA"]
    z = za // 1000
    a = za % 1000
    halflife_s = parsed_data["T1/2"][0]
    
    # Decay mode info
    mode = parsed_data["modes"][0]
    rtyp = mode["RTYP"]
    q_kev = mode["Q"][0] / 1000.0  # eV to keV
    total_br_pct = mode["BR"][0] * 100.0 if mode["BR"][0] <= 1.0 else mode["BR"][0]
    
    # Mean energies from spectra
    mean_alpha = 0.0
    mean_beta = 0.0
    mean_gamma = 0.0
    
    for spec in parsed_data["spectra"]:
        styp = spec["STYP"]
        er_av_kev = spec["ER_AV"][0] / 1000.0
        
        if styp == 0:  # Gamma
            mean_gamma = er_av_kev
        elif styp == 2:  # Beta+
            mean_beta = er_av_kev
        elif styp == 4:  # Alpha
            mean_alpha = er_av_kev
    
    # B+/EC split according to ENDF-102
    bplus_br_pct = 0.0
    ec_br_pct = 0.0
    has_511_peak = False
    
    if rtyp == 2.0:  # EC/β+ decay
        bplus_br_pct = extract_bplus_branching(parsed_data)
        
        if bplus_br_pct is None or bplus_br_pct == 0.0:
            for spec in parsed_data["spectra"]:
                if spec["STYP"] == 2:
                    bplus_br_pct = spec["FD"][0] * 100.0 if spec["FD"][0] < 1.0 else spec["FD"][0]
                    break
        
        # Check for 511 keV annihilation photons
        ANNIHILATION_ENERGY_KEV = 511.0
        ENERGY_TOLERANCE_KEV = 1.0
        
        for spec in parsed_data["spectra"]:
            if spec["STYP"] == 0 and "discrete" in spec:
                for discrete in spec["discrete"]:
                    gamma_energy_kev = discrete["ER"][0] / 1000.0
                    if abs(gamma_energy_kev - ANNIHILATION_ENERGY_KEV) < ENERGY_TOLERANCE_KEV:
                        has_511_peak = True
                        break
                if has_511_peak:
                    break
        
        ec_br_pct = total_br_pct - bplus_br_pct
        
        if bplus_br_pct < 0 or ec_br_pct < 0:
            print(f"WARNING: Negative branching ratio detected!")
            print(f"  Total BR: {total_br_pct:.4f}%")
            print(f"  B+ BR: {bplus_br_pct:.4f}%")
            print(f"  EC BR: {ec_br_pct:.4f}%")
    else:
        print(f"Note: RTYP={rtyp} is not EC/β+ decay")
    
    # Extract element symbol
    ELEMENT_SYMBOLS = {35: 'Br', 74: 'W'}
    element = ELEMENT_SYMBOLS.get(z, f'Z{z}')
    
    # Print header
    print()
    print("="*130)
    print(f"ENDF-6 Radioactive Decay Data Parser (ENDF-102 Compliant)")
    print("="*130)
    print()
    print(f"Nuclide: {element}-{a} (Z={z}, A={a})")
    print(f"Half-life: {halflife_s:.4e} seconds ({halflife_s/60.0:.2f} minutes)")
    print(f"Q-value: {q_kev:.4f} keV")
    print()
    
    print("Decay Mode Analysis:")
    print(f"  RTYP: {rtyp} → {'EC/β+ decay' if rtyp == 2.0 else f'Decay type {rtyp}'}")
    print(f"  Total Branching Ratio: {total_br_pct:.4f}%")
    print(f"  β+ Branching: {bplus_br_pct:.4f}%")
    print(f"  EC Branching: {ec_br_pct:.4f}%")
    print(f"  511 keV annihilation peak: {'FOUND ✓' if has_511_peak else 'Not detected in discrete list'}")
    print()
    
    print("Mean Radiation Energies:")
    print(f"  Alpha particles: {mean_alpha:.4f} keV")
    print(f"  Beta particles:  {mean_beta:.4f} keV")
    print(f"  Gamma rays:      {mean_gamma:.4f} keV")
    print()
    
    print("="*130)
    print("DECAY MODES TABLE")
    print("="*130)
    print()
    print(f"{'A':4s} {'Z':3s} {'Parent':>8s} {'Decay':>8s} {'Daughter':>8s} {'Q-value':>15s} {'Branching':>15s} {'Half-life':>15s} {'α Energy':>15s} {'β Energy':>15s} {'γ Energy':>15s}")
    print(f"{'':4s} {'':3s} {'Level':>8s} {'Mode':>8s} {'Level':>8s} {'(keV)':>15s} {'Ratio (%)':>15s} {'(seconds)':>15s} {'(keV)':>15s} {'(keV)':>15s} {'(keV)':>15s}")
    print("-"*130)
    
    print(f"{a:<4d} {z:<3d} {0:>8d} {'B+':>8s} {0:>8d} {q_kev:>15.4f} {bplus_br_pct:>15.4f} {halflife_s:>15.4e} {mean_alpha:>15.4f} {mean_beta:>15.4f} {mean_gamma:>15.4f}")
    print(f"{a:<4d} {z:<3d} {0:>8d} {'EC':>8s} {0:>8d} {q_kev:>15.4f} {ec_br_pct:>15.4f} {halflife_s:>15.4e} {mean_alpha:>15.4f} {mean_beta:>15.4f} {mean_gamma:>15.4f}")
    
    print("-"*130)
    print()
    print("Summary:")
    print(f"  • {element}-{a} undergoes EC/β+ decay with T½ = {halflife_s/60.0:.2f} minutes")
    print(f"  • β+ emission accounts for {bplus_br_pct:.2f}% of decays")
    print(f"  • Electron capture accounts for {ec_br_pct:.2f}% of decays")
    print("="*130)
    print()


def print_detailed_data(parsed_data):
    """Print all detailed transition data."""
    print()
    print("="*130)
    print("DETAILED TRANSITION DATA")
    print("="*130)
    print()
    
    # Gamma rays
    for spec in parsed_data["spectra"]:
        if spec["STYP"] == 0 and "discrete" in spec:
            print(f"GAMMA RAY TRANSITIONS (Total: {len(spec['discrete'])})")
            print("-"*130)
            print(f"{'#':>4s} {'Energy (keV)':>15s} {'Uncertainty':>15s} {'Intensity':>15s} {'Int. Unc.':>15s} {'ICC Total':>15s} {'ICC K':>15s} {'ICC L':>15s}")
            print("-"*130)
            for i, disc in enumerate(spec["discrete"], 1):
                energy_kev = disc["ER"][0] / 1000.0
                energy_unc = disc["ER"][1] / 1000.0
                if "RI" in disc:
                    intensity = disc["RI"][0]
                    int_unc = disc["RI"][1]
                    icc = disc.get("RICC", (0, 0))[0]
                    ick = disc.get("RICK", (0, 0))[0]
                    icl = disc.get("RICL", (0, 0))[0]
                    print(f"{i:>4d} {energy_kev:>15.4f} {energy_unc:>15.4f} {intensity:>15.6f} {int_unc:>15.6f} {icc:>15.6f} {ick:>15.6f} {icl:>15.6f}")
            print()
    
    # Beta+ transitions
    for spec in parsed_data["spectra"]:
        if spec["STYP"] == 2 and "discrete" in spec:
            print(f"BETA+ TRANSITIONS (Total: {len(spec['discrete'])})")
            print("-"*130)
            print(f"{'#':>4s} {'Endpoint (keV)':>18s} {'Uncertainty':>15s} {'Intensity (%)':>18s} {'Int. Unc.':>15s} {'TYPE':>10s}")
            print("-"*130)
            for i, disc in enumerate(spec["discrete"], 1):
                energy_kev = disc["ER"][0] / 1000.0
                energy_unc = disc["ER"][1] / 1000.0
                trans_type = disc.get("TYPE", 0)
                if "INTENSITY" in disc:
                    intensity = disc["INTENSITY"][0]
                    int_unc = disc["INTENSITY"][1]
                    print(f"{i:>4d} {energy_kev:>18.4f} {energy_unc:>15.4f} {intensity:>18.4f} {int_unc:>15.4f} {trans_type:>10.1f}")
            print()
    
    # X-rays
    for spec in parsed_data["spectra"]:
        if spec["STYP"] == 8 and "discrete" in spec:
            print(f"X-RAY TRANSITIONS (Total: {len(spec['discrete'])})")
            print("-"*130)
            print(f"{'#':>4s} {'Energy (keV)':>15s} {'Uncertainty':>15s} {'RTYP':>10s} {'TYPE':>10s}")
            print("-"*130)
            for i, disc in enumerate(spec["discrete"], 1):
                energy_kev = disc["ER"][0] / 1000.0
                energy_unc = disc["ER"][1] / 1000.0
                rtyp = disc.get("RTYP", 0)
                trans_type = disc.get("TYPE", 0)
                print(f"{i:>4d} {energy_kev:>15.4f} {energy_unc:>15.4f} {rtyp:>10.1f} {trans_type:>10.1f}")
            print()
    
    # Auger electrons
    for spec in parsed_data["spectra"]:
        if spec["STYP"] == 9 and "discrete" in spec:
            print(f"AUGER ELECTRON TRANSITIONS (Total: {len(spec['discrete'])})")
            print("-"*130)
            print(f"{'#':>4s} {'Energy (keV)':>15s} {'Uncertainty':>15s} {'RTYP':>10s} {'TYPE':>10s}")
            print("-"*130)
            for i, disc in enumerate(spec["discrete"], 1):
                energy_kev = disc["ER"][0] / 1000.0
                energy_unc = disc["ER"][1] / 1000.0
                rtyp = disc.get("RTYP", 0)
                trans_type = disc.get("TYPE", 0)
                print(f"{i:>4d} {energy_kev:>15.4f} {energy_unc:>15.4f} {rtyp:>10.1f} {trans_type:>10.1f}")
            print()
    
    # Additional metadata
    print("="*130)
    print("ADDITIONAL METADATA")
    print("="*130)
    print(f"Spin (SPI): {parsed_data.get('SPI', 'N/A')}")
    print(f"Parity (PAR): {parsed_data.get('PAR', 'N/A')}")
    print(f"Isomeric state (LIS): {parsed_data.get('LIS', 0)}")
    print(f"Number of excited states (NC): {parsed_data.get('NC', 0)}")
    if parsed_data.get('Ex'):
        print(f"Excited state energies:")
        for i, (ex_val, ex_unc) in enumerate(parsed_data['Ex'], 1):
            print(f"  Ex[{i}]: {ex_val/1000.0:.4f} ± {ex_unc/1000.0:.4f} keV")
    print("="*130)
    print()


if __name__ == "__main__":
    import sys
    import os
    
    # Check for verbose/full flag and output file
    verbose = False
    file_arg = None
    output_file = None
    
    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg in ['--verbose', '--full', '-v', '--all']:
            verbose = True
        elif arg in ['--output', '-o']:
            if i + 1 < len(sys.argv):
                output_file = sys.argv[i + 1]
                i += 1
            else:
                print("ERROR: --output requires a filename argument")
                exit(1)
        elif not arg.startswith('-'):
            file_arg = arg
        i += 1
    
    # File argument is REQUIRED
    if not file_arg:
        print()
        print("="*80)
        print("ENDF-6 Radioactive Decay Data Parser")
        print("="*80)
        print()
        print("Usage:")
        print("  python3 run_br74_parser.py <endf_file.txt>                    # Summary view")
        print("  python3 run_br74_parser.py --verbose <endf_file.txt>          # Full details")
        print("  python3 run_br74_parser.py -o output.txt <endf_file.txt>      # Save to file")
        print("  python3 run_br74_parser.py --verbose -o out.txt <file.txt>    # Full details to file")
        print()
        print("Options:")
        print("  --verbose, -v, --full, --all    Show all transitions and detailed data")
        print("  --output, -o <filename>         Save output to specified file")
        print()
        print("Example:")
        print("  python3 run_br74_parser.py br74_endf_test.txt")
        print("  python3 run_br74_parser.py --verbose br74_endf_test.txt")
        print("  python3 run_br74_parser.py --verbose -o br74_output.txt br74_endf_test.txt")
        print()
        print("="*80)
        exit(1)
    
    # Auto-generate output filename if not specified
    if output_file is None:
        base_name = os.path.splitext(os.path.basename(file_arg))[0]
        output_file = f"{base_name}_parsed_output.txt"
    
    # Read from file
    input_file = file_arg
    
    try:
        # Parse ALL MF=8 MT=457 sections in the file (all MAT types)
        all_results = []
        
        with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        # Find all MF=8 MT=457 sections with their MAT numbers
        section_info = []  # List of (line_num, mat_num) tuples
        for i, line in enumerate(lines):
            if len(line) >= 75:
                try:
                    mat = int(line[66:70].strip() or 0)
                    mf = int(line[70:72].strip() or 0)
                    mt = int(line[72:75].strip() or 0)
                    seq = int(line[75:80].strip() or 0)
                    if mf == 8 and mt == 457 and seq == 1:  # HEAD record
                        section_info.append((i, mat))
                except:
                    continue
        
        if not section_info:
            print("ERROR: No MF=8 MT=457 section found in file")
            print("This file may not contain radioactive decay data.")
            exit(1)
        
        # Extract unique MAT numbers
        unique_mats = sorted(set([mat for _, mat in section_info]))
        
        print(f"Found {len(section_info)} decay section(s) across {len(unique_mats)} material(s): MAT={', '.join(map(str, unique_mats))}")
        
        # Parse each section
        for start_pos, mat_num in section_info:
            parser = ENDFNumericDecayParser()
            parser.load_file(input_file)
            parser._pos = start_pos
            result = parser._parse_mf8_mt457()
            result["MAT"] = mat_num  # Store MAT number with result
            all_results.append(result)
        
        # Redirect output to file
        original_stdout = sys.stdout
        
        with open(output_file, 'w', encoding='utf-8') as f:
            sys.stdout = f
            
            print(f"Reading ENDF data from: {input_file}")
            if verbose:
                print("(Verbose mode: showing all detailed transitions)")
            print(f"Found {len(all_results)} decay state(s)")
            print()
            
            # Format and print all results
            format_and_print_combined_table(all_results)
            
            if verbose:
                for i, result in enumerate(all_results):
                    print()
                    print("="*130)
                    print(f"DETAILED DATA FOR STATE {i} (LIS={result.get('LIS', 0)})")
                    print("="*130)
                    print_detailed_data(result)
        
        # Restore stdout
        sys.stdout = original_stdout
        
        # Print confirmation to console
        print(f"✓ Successfully parsed: {input_file}")
        print(f"✓ Output saved to: {output_file}")
        print(f"✓ Found {len(all_results)} decay state(s)")
        if verbose:
            print(f"✓ Mode: Full details (all transitions)")
        else:
            print(f"✓ Mode: Summary view")
        
        # Show brief summary to console
        ELEMENT_SYMBOLS = {
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
        
        for result in all_results:
            za = result["ZA"]
            z = za // 1000
            a = za % 1000
            lis = result.get("LIS", 0)
            mat = result.get("MAT", 0)
            halflife_s = result["T1/2"][0]
            element = ELEMENT_SYMBOLS.get(z, f'Z{z}')
            
            level_name = f"{element}-{a}" if lis == 0 else f"{element}-{a}m{lis}" if lis > 0 else f"{element}-{a}"
            
            print()
            print(f"MAT={mat}, Level {lis}: {level_name}, T½ = {halflife_s/60.0:.2f} min")
            
            # Show B+/EC split
            bplus_br_pct = extract_bplus_branching(result)
            if result.get("modes"):
                mode = result["modes"][0]
                total_br_pct = mode["BR"][0] * 100.0 if mode["BR"][0] <= 1.0 else mode["BR"][0]
                ec_br_pct = total_br_pct - bplus_br_pct
                
                print(f"  β+ Branching: {bplus_br_pct:.2f}%")
                print(f"  EC Branching: {ec_br_pct:.2f}%")
        
    except FileNotFoundError:
        print(f"ERROR: File not found: {input_file}")
        print()
        print("Please check the file path and try again.")
        exit(1)
    except Exception as e:
        print(f"ERROR: Failed to parse file: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
