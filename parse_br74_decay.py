#!/usr/bin/env python3
"""
Complete ENDF-6 Br-74 Decay Data Parser and Table Generator

This script parses the complete ENDF file (ignoring text sections)
and generates a formatted table with Z, A split and B+/EC separated.
"""

import re
from typing import Any, Dict, Iterable, List, Optional, Tuple
import numpy as np


# Decay mode mapping
DECAY_MODES = {
    0.0: "γ",      # Gamma/IT
    1.0: "β-",     # Beta minus
    2.0: "EC/β+",  # Electron capture and/or beta plus
    3.0: "IT",     # Isomeric transition  
    4.0: "α",      # Alpha
    5.0: "n",      # Neutron
    6.0: "SF",     # Spontaneous fission
    7.0: "p",      # Proton
}

# Radiation type mapping
RADIATION_TYPES = {
    0: "gamma",
    1: "beta-",
    2: "beta+/ec",
    4: "alpha",
    5: "neutron",
    6: "fission",
    7: "proton",
    8: "xray",
    9: "auger",
}


class Tabulated1D:
    """One-dimensional tabulated function with FIXED interpolation."""
    
    def __init__(self, x, y, breakpoints=None, interpolation=None):
        x_arr = np.asarray(list(x) if not isinstance(x, np.ndarray) else x, dtype=float)
        y_arr = np.asarray(list(y) if not isinstance(y, np.ndarray) else y, dtype=float)
        if x_arr.size != y_arr.size:
            raise ValueError("x and y must have the same length")
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
        self._x = np.asarray(list(x) if isinstance(x, list) else x, dtype=float)
    
    @property
    def y(self):
        return self._y
    
    @y.setter
    def y(self, y):
        self._y = np.asarray(list(y) if isinstance(y, list) else y, dtype=float)


class Tabulated2D:
    def __init__(self, breakpoints, interpolation):
        self.breakpoints = np.asarray(list(breakpoints), dtype=int)
        self.interpolation = np.asarray(list(interpolation), dtype=int)


class ENDFNumericDecayParser:
    """Parser for MF=8 MT=457 (ignores MF=1 MT=451 text)."""
    
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
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            self._lines = fh.read().splitlines()
        self._pos = 0
    
    def _readline(self) -> str:
        if self._pos >= len(self._lines):
            raise EOFError("Unexpected EOF")
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
                    items_d, values_d = self._get_list_record()
                    discrete = {}
                    discrete["ER"] = tuple(items_d[0:2])
                    discrete["RTYP"] = float(values_d[0])
                    discrete["TYPE"] = float(values_d[1])
                    if styp == 0:
                        discrete["RI"] = tuple(values_d[2:4].astype(float))
                        discrete["RIS"] = tuple(values_d[4:6].astype(float))
                        discrete["RICC"] = tuple(values_d[6:8].astype(float))
                        discrete["RICK"] = tuple(values_d[8:10].astype(float))
                        discrete["RICL"] = tuple(values_d[10:12].astype(float))
                    spectrum["discrete"].append(discrete)
            
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
    
    def parse_file(self, path: str):
        self.load_file(path)
        if not self._scan_to_mf_mt(8, 457):
            raise ValueError("No MF=8 MT=457 found")
        return self._parse_mf8_mt457()


def format_decay_table(parsed_data):
    """Generate formatted table matching the expected output."""
    
    # Extract basic info
    za = parsed_data["ZA"]
    z = za // 1000
    a = za % 1000
    halflife_s = parsed_data["T1/2"][0]
    
    # Get decay mode info
    mode = parsed_data["modes"][0]
    q_kev = mode["Q"][0] / 1000.0  # Convert eV to keV
    total_br_pct = mode["BR"][0]
    
    # Extract mean energies from spectra
    mean_alpha = 0.0
    mean_beta = 0.0
    mean_gamma = 0.0
    
    for spec in parsed_data["spectra"]:
        styp = spec["STYP"]
        er_av_kev = spec["ER_AV"][0] / 1000.0  # eV to keV
        
        if styp == 0:  # Gamma
            mean_gamma = er_av_kev
        elif styp == 2:  # Beta+
            mean_beta = er_av_kev
        elif styp == 4:  # Alpha
            mean_alpha = er_av_kev
    
    # For RTYP=2 (EC/B+), split into components
    # FD field in spectrum contains the B+ branching fraction
    bplus_br_pct = 0.0
    for spec in parsed_data["spectra"]:
        if spec["STYP"] == 2:  # Beta+ spectrum
            bplus_br_pct = spec["FD"][0]  # This is already in percent
            break
    
    ec_br_pct = total_br_pct - bplus_br_pct
    
    # Create output
    rows = []
    rows.append({
        "A": a,
        "Z": z,
        "parent_level": 0,
        "decay_mode": "B+",
        "daughter_level": 0,
        "Q": f"{q_kev:.4f} keV",
        "BR": f"{bplus_br_pct:.4f} %",
        "Half-life": f"{halflife_s:.4e} s",
        "Mean_alpha_E": f"{mean_alpha:.4f} keV",
        "Mean_beta_E": f"{mean_beta:.4f} keV",
        "Mean_gamma_E": f"{mean_gamma:.4f} keV",
    })
    
    rows.append({
        "A": a,
        "Z": z,
        "parent_level": 0,
        "decay_mode": "EC",
        "daughter_level": 0,
        "Q": f"{q_kev:.4f} keV",
        "BR": f"{ec_br_pct:.4f} %",
        "Half-life": f"{halflife_s:.4e} s",
        "Mean_alpha_E": f"{mean_alpha:.4f} keV",
        "Mean_beta_E": f"{mean_beta:.4f} keV",
        "Mean_gamma_E": f"{mean_gamma:.4f} keV",
    })
    
    return rows


def print_table(rows):
    """Print formatted table."""
    print("="*135)
    print("ENDF Radioactive Decay Data for Br-74 (DEBUG MODE)")
    print("="*135)
    print()
    print(f"{'':4s} {'':3s} {'':13s} {'':11s} {'':15s} {'Q (keV)':>15s} {'BR (%)':>12s} {'Half-life (s)':>15s} {'Mean_alpha_E (keV)':>20s} {'Mean_beta_E (keV)':>19s} {'Mean_gamma_E (keV)':>20s}")
    print(f"{'A':4s} {'Z':3s} {'parent_level':13s} {'decay_mode':11s} {'daughter_level':15s}")
    
    for row in rows:
        print(f"{row['A']:<4d} {row['Z']:<3d} {row['parent_level']:<13d} {row['decay_mode']:<11s} {row['daughter_level']:<15d} {row['Q']:>15s} {row['BR']:>12s} {row['Half-life']:>15s} {row['Mean_alpha_E']:>20s} {row['Mean_beta_E']:>19s} {row['Mean_gamma_E']:>20s}")


if __name__ == "__main__":
    # Put your complete ENDF file content here
    ENDF_FILE_PATH = "br74_endf.txt"  # Or load from string
    
    # Example: parse from file
    import sys
    if len(sys.argv) > 1:
        ENDF_FILE_PATH = sys.argv[1]
        parser = ENDFNumericDecayParser()
        parser.load_file(ENDF_FILE_PATH)
        if not parser._scan_to_mf_mt(8, 457):
            print("ERROR: No MF=8 MT=457 section found")
            sys.exit(1)
        result = parser._parse_mf8_mt457()
        rows = format_decay_table(result)
        print_table(rows)
    else:
        print("Usage: python parse_br74_decay.py <endf_file>")
        print("\nOr modify the script to include ENDF data as a string.")
