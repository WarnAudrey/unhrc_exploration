#!/usr/bin/env python3
"""
JEFF ENDF-6 Radioactive Decay Data Parser (MF=8, MT=457)

Universal parser for JEFF (Joint Evaluated Fission and Fusion) radioactive decay databases.
Parses ENDF-6 format radioactive decay data from the complete JEFF-4.0 dataset or any ENDF file.
Supports ALL material (MAT) numbers and automatically detects all nuclides and isomeric states.
Implements proper B+/EC splitting according to ENDF-102 specifications.

Features:
- Parses entire JEFF radioactive decay database (~3000 nuclides)
- Universal MAT support (works with ANY material number 1-9999)
- Automatic multi-level detection and verification
- Handles multiple isomeric states per nuclide
- Level completeness checking with gap detection
- Groups results by nuclide with combined tables
- Accurate B+/EC branching ratio calculations
- Fault-tolerant parsing (continues on errors)
- Works with incomplete/partial ENDF data

Usage:
    python3 JEFF_ENDF_parser.py <jeff_decay_file.endf>           # Summary view
    python3 JEFF_ENDF_parser.py --verbose <jeff_decay_file.endf> # Full details
    python3 JEFF_ENDF_parser.py -o output.txt <input.endf>       # Custom output

Examples:
    python3 JEFF_ENDF_parser.py jeff-40-radioactive.endf
    python3 JEFF_ENDF_parser.py uranium_decay.endf -o uranium_analysis.txt
"""

import re
from typing import Any, Dict, List, Optional, Tuple
import numpy as np


# Element symbols by atomic number
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
    91: 'Pa', 92: 'U', 93: 'Np', 94: 'Pu', 95: 'Am', 96: 'Cm', 97: 'Bk', 98: 'Cf', 99: 'Es', 100: 'Fm',
    101: 'Md', 102: 'No', 103: 'Lr', 104: 'Rf', 105: 'Db', 106: 'Sg', 107: 'Bh', 108: 'Hs', 109: 'Mt',
    110: 'Ds', 111: 'Rg', 112: 'Cn', 113: 'Nh', 114: 'Fl', 115: 'Mc', 116: 'Lv', 117: 'Ts', 118: 'Og'
}


class Tabulated1D:
    """
    Tabulated1D: One-dimensional tabulated function with ENDF-6 interpolation support.
    
    This class implements the TAB1 record type from ENDF-6 format, which represents
    a 1D function as a series of (x,y) points with interpolation rules between them.
    
    ENDF-6 supports multiple interpolation schemes:
        1 = Histogram (constant y in each interval)
        2 = Linear-linear (straight line between points)
        3 = Linear-log (y varies linearly with ln(x))
        4 = Log-linear (ln(y) varies linearly with x)
        5 = Log-log (ln(y) varies linearly with ln(x))
    
    The function domain can be divided into multiple regions, each with its own
    interpolation scheme, defined by breakpoints.
    """
    def __init__(self, x, y, breakpoints=None, interpolation=None):
        # Convert input arrays to numpy arrays for efficient computation
        # Handle both numpy arrays and iterables (lists, tuples, etc.)
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
    """
    Tabulated2D: Metadata for two-dimensional tabulated functions.
    
    This class stores interpolation information for 2D functions in ENDF-6 format (TAB2 records).
    It only stores the interpolation metadata; actual 2D data is stored separately.
    """
    def __init__(self, breakpoints, interpolation):
        # Store interpolation breakpoints (where interpolation scheme changes)
        self.breakpoints = np.asarray(list(breakpoints), dtype=int)
        # Store interpolation schemes for each region
        self.interpolation = np.asarray(list(interpolation), dtype=int)


class ENDFNumericDecayParser:
    """
    ENDFNumericDecayParser: Core parser for ENDF-6 radioactive decay data (MF=8, MT=457).
    
    This parser reads ENDF-6 format radioactive decay data files and extracts:
    - Half-lives and Q-values
    - Decay modes (β+, β-, EC, α, etc.) and branching ratios
    - Radiation spectra (gamma rays, beta particles, X-rays, Auger electrons)
    - Discrete transition energies and intensities
    - Mean radiation energies
    
    ENDF-6 Format Structure:
    - Each line is 80 characters fixed-width
    - Columns 1-66: Data fields
    - Columns 67-70: MAT (material identifier)
    - Columns 71-72: MF (file number, 8 for radioactive decay)
    - Columns 73-75: MT (section number, 457 for decay data)
    - Columns 76-80: Line sequence number
    
    MF=8 MT=457 Record Structure:
    1. HEAD record: ZA, AWR, LIS (isomeric state), LISO, NST (stability), NSP (# spectra)
    2. LIST record: Half-life with uncertainty
    3. LIST record: Decay modes with Q-values and branching ratios
    4. Multiple LIST/TAB1 records: Radiation spectra for each particle type
    """
    
    # Regular expression to parse ENDF's "E-less" floating point format
    # ENDF uses format like "1.23456+7" instead of "1.23456E+7"
    ENDF_FLOAT_RE = re.compile(r"([\s\-\+]?\d*\.\d+)([\+\-]) ?(\d+)")
    
    def __init__(self, text: Optional[str] = None):
        """
        Initialize the parser.
        
        Args:
            text: Optional ENDF text data to load immediately
        """
        self._lines: List[str] = []  # Storage for all lines from ENDF file
        self._pos: int = 0           # Current reading position (line number)
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
        """
        Parse an MF=8 MT=457 section (radioactive decay data for one level).
        
        ENDF-102 Manual Section 8.1: Radioactive Decay Data
        
        This function parses ONE complete MF=8 MT=457 section, which contains
        decay data for ONE isomeric state of ONE nuclide.
        
        Returns:
            Dictionary containing all decay data for this level
        """
        
        # ===================================================================
        # RECORD 1: HEAD RECORD - Identifies the nuclide and decay level
        # ===================================================================
        # ZA:   Nuclide identifier (Z*1000 + A, e.g., 35074 for Br-74)
        # AWR:  Atomic weight ratio
        # LIS:  Isomeric state level (0=ground, 1=1st excited, 2=2nd excited, etc.)
        #       **CRITICAL**: Different LIS values have separate MF=8 MT=457 sections!
        # LISO: Isomeric state flag (0=ground, 1=excited)
        # NST:  Stability flag (0=radioactive, 1=stable)
        # NSP:  Number of radiation spectra to follow (gamma, beta, X-ray, etc.)
        
        za, awr, lis, liso, nst, nsp = self._get_head_record()
        data = {"ZA": za, "AWR": awr, "LIS": lis, "LISO": liso, "NST": nst, "NSP": nsp}
        
        # ===================================================================
        # STABLE NUCLIDES (NST=1): Skip detailed decay data
        # ===================================================================
        if nst == 1:
            # For stable nuclides, only spin and parity are given
            self._get_list_record()  # Skip first LIST record
            (spi, par, *_), _ = self._get_list_record()
            data["SPI"] = spi   # Nuclear spin
            data["PAR"] = par   # Parity
            return data
        
        # ===================================================================
        # RECORD 2: HALF-LIFE AND EXCITATION ENERGIES
        # ===================================================================
        # For radioactive nuclides (NST=0), this LIST record contains:
        # C1: Half-life (seconds)
        # C2: Half-life uncertainty
        # N1: Number of excitation energy pairs (NC)
        # Values array: Pairs of (excitation energy, uncertainty) for daughter states
        
        items, values = self._get_list_record()
        data["T1/2"] = (items[0], items[1])  # (half-life, uncertainty) in seconds
        data["NC"] = items[4] // 2            # Number of daughter excitation states
        data["Ex"] = list(zip(values[::2], values[1::2]))  # (energy, uncertainty) pairs
        
        # ===================================================================
        # RECORD 3: SPIN/PARITY AND DECAY MODES
        # ===================================================================
        # This LIST record contains decay mode information
        # C1: SPI (nuclear spin)
        # C2: PAR (parity: +1.0 or -1.0)
        # N2: NDK (number of decay modes)
        # Values: 6 values per decay mode:
        #   [0] RTYP: Decay type (0.0=γ, 1.0=β-, 2.0=EC/β+, 4.0=α, etc.)
        #   [1] RFS: Isomeric state flag for daughter
        #   [2] Q: Q-value (decay energy in eV)
        #   [3] dQ: Q-value uncertainty
        #   [4] BR: Branching ratio (as fraction, e.g., 1.0 = 100%)
        #   [5] dBR: Branching ratio uncertainty
        
        items, values_modes = self._get_list_record()
        data["SPI"], data["PAR"], *_ = items
        data["NDK"] = int(items[5])  # Number of decay modes
        data["modes"] = []
        
        # Parse each decay mode
        if values_modes.size >= 6 * data["NDK"]:
            for i in range(data["NDK"]):
                rtyp = float(values_modes[6 * i])      # Decay type
                rfs = float(values_modes[6 * i + 1])   # Daughter isomeric state
                q = (float(values_modes[6 * i + 2]), float(values_modes[6 * i + 3]))  # (Q-value, uncertainty)
                br = (float(values_modes[6 * i + 4]), float(values_modes[6 * i + 5])) # (branching, uncertainty)
                data["modes"].append({"RTYP": rtyp, "RFS": rfs, "Q": q, "BR": br})
        
        # ===================================================================
        # RECORDS 4+: RADIATION SPECTRA (NSP spectra)
        # ===================================================================
        # Each spectrum describes one type of radiation emitted during decay
        # Common spectrum types (STYP):
        #   0 = Gamma rays
        #   2 = Beta+ particles  
        #   8 = X-rays
        #   9 = Auger electrons
        # 
        # For each spectrum, we read:
        # 1. Summary LIST record with mean energies
        # 2. Discrete transitions (if LCON != 1)
        # 3. Continuous spectrum (if LCON != 2)
        # 4. Covariance data (if LCOV != 0)
        
        data["spectra"] = []
        for spectrum_idx in range(nsp):
            try:
                # First LIST record for this spectrum: Summary information
                items, values = self._get_list_record()
                _, styp, lcon, lcov, _, ner = items
                # STYP: Radiation type (0=γ, 2=β+, 8=X-ray, 9=Auger)
                # LCON: Continuum flag (0=discrete+continuous, 1=continuous only, 2=discrete only)
                # LCOV: Covariance flag (0=none, 1=discrete only, 2=continuous only, 3=both)
                # NER:  Number of discrete energy records
                
                spectrum = {"STYP": styp, "LCON": lcon, "LCOV": lcov, "NER": ner}
                # FD: Discrete normalization (value, uncertainty) - often used for total branching
                spectrum["FD"] = tuple(values[0:2].astype(float))
                # ER_AV: Average radiation energy (value, uncertainty) in eV
                spectrum["ER_AV"] = tuple(values[2:4].astype(float))
                # FC: Continuum normalization (value, uncertainty)
                spectrum["FC"] = tuple(values[4:6].astype(float))
                
                # ============================================================
                # DISCRETE TRANSITIONS (if LCON != 1)
                # ============================================================
                # Read NER discrete transition records
                # Each transition describes a specific gamma ray, beta+ particle, etc.
                
                if lcon != 1:
                    spectrum["discrete"] = []
                    # Try to read NER discrete transition records
                    # Stop early if we hit EOF (handles incomplete files)
                    for record_idx in range(ner):
                        try:
                            # Each discrete transition is one LIST record
                            items_d, values_d = self._get_list_record()
                            discrete = {}
                            # ER: Transition energy (value, uncertainty) in eV
                            discrete["ER"] = tuple(items_d[0:2])
                            
                            # Handle incomplete data gracefully (for partial ENDF files)
                            if len(values_d) == 0:
                                continue
                            
                            # RTYP: Decay mode that produced this radiation
                            discrete["RTYP"] = float(values_d[0]) if len(values_d) > 0 else 0.0
                            # TYPE: Transition type (0=γ to ground, 1=γ to excited, etc.)
                            discrete["TYPE"] = float(values_d[1]) if len(values_d) > 1 else 0.0
                            
                            # ========================================
                            # GAMMA SPECTRUM (STYP=0): 
                            # ========================================
                            # For gamma rays, we get emission probabilities and conversion coefficients
                            if styp == 0:  
                                if len(values_d) >= 12:
                                    # RI:   Absolute gamma intensity (photons per 100 decays)
                                    discrete["RI"] = tuple(values_d[2:4].astype(float))
                                    # RIS:  Relative gamma intensity (normalized)
                                    discrete["RIS"] = tuple(values_d[4:6].astype(float))
                                    # RICC: Total internal conversion coefficient
                                    discrete["RICC"] = tuple(values_d[6:8].astype(float))
                                    # RICK: K-shell conversion coefficient
                                    discrete["RICK"] = tuple(values_d[8:10].astype(float))
                                    # RICL: L-shell conversion coefficient
                                    discrete["RICL"] = tuple(values_d[10:12].astype(float))
                            
                            # ========================================
                            # BETA+ SPECTRUM (STYP=2):
                            # ========================================
                            # For beta+ particles, we get emission intensity
                            elif styp == 2:  
                                if len(values_d) >= 6:
                                    # INTENSITY: Beta+ emission intensity (percent per decay)
                                    discrete["INTENSITY"] = tuple(values_d[4:6].astype(float))
                            
                            discrete["_raw_values"] = values_d
                            spectrum["discrete"].append(discrete)
                        except (IndexError, ValueError, EOFError) as e:
                            # EOF or error - stop trying to read more discrete records
                            # This handles truncated/incomplete ENDF files
                            break
                
                # ========================================
                # CONTINUOUS SPECTRUM (if LCON != 2)
                # ========================================
                # Some radiation has a continuous energy distribution
                # Stored as a TAB1 record (tabulated function)
                if lcon != 0:
                    try:
                        params, rp = self._get_tab1_record()
                        # RTYP: Decay mode producing this continuous spectrum
                        # RP: Probability function vs energy (Tabulated1D object)
                        spectrum["continuous"] = {"RTYP": params[0], "RP": rp}
                    except (EOFError, IndexError, ValueError):
                        pass  # Skip if not available (incomplete file)
                
                # ========================================
                # COVARIANCE DATA (if LCOV != 0)
                # ========================================
                # Uncertainty/correlation information for the spectra
                
                # Continuous spectrum covariance
                if lcov not in (0, 2) and lcon != 0:
                    try:
                        items_c, values_c = self._get_list_record()
                        covar_cont = {"LB": items_c[3]}
                        covar_cont["Ek"] = np.array(values_c[::2], dtype=float)  # Energy points
                        covar_cont["Fk"] = np.array(values_c[1::2], dtype=float) # Covariance values
                        spectrum["continuous_covariance"] = covar_cont
                    except (EOFError, IndexError, ValueError):
                        pass  # Skip if not available
                
                # Discrete spectrum covariance
                if lcov not in (0, 1):
                    try:
                        (__, ____, ls, lb, ne, nerp), values_dc = self._get_list_record()
                        covar_disc = {"LS": ls, "LB": lb, "NE": ne, "NERP": nerp}
                        covar_disc["Ek"] = np.array(values_dc[:nerp], dtype=float)  # Energy points
                        covar_disc["Fkk"] = np.array(values_dc[nerp:], dtype=float) # Covariance matrix
                        spectrum["discrete_covariance"] = covar_disc
                    except (EOFError, IndexError, ValueError):
                        pass  # Skip if not available
                
                # Add this spectrum to the list
                data["spectra"].append(spectrum)
                
            except (EOFError, IndexError, ValueError) as e:
                # If we can't even start reading this spectrum, we're done with spectra
                # This handles truncated ENDF files gracefully
                break
        
        return data


def extract_bplus_branching(parsed_data):
    """
    Extract β+ branching ratio by summing individual β+ transition intensities.
    
    ENDF-102 Manual Note:
    For EC/β+ decay (RTYP=2.0), the total branching ratio includes BOTH:
    - β+ emission (positron emission)
    - Electron capture (EC)
    
    To separate them:
    1. β+ branching = sum of all individual β+ transition intensities
    2. EC branching = Total branching - β+ branching
    
    Args:
        parsed_data: Parsed decay data dictionary
    
    Returns:
        β+ branching ratio as a percentage (0-100)
    """
    # Handle stable nuclides (no decay data)
    if "spectra" not in parsed_data:
        return 0.0
    
    # Look for the beta+ spectrum (STYP=2)
    for spec in parsed_data["spectra"]:
        if spec["STYP"] == 2 and "discrete" in spec:  # Beta+ spectrum
            total_intensity = 0.0
            
            # Sum all individual β+ transition intensities
            # Each discrete transition contributes to the total β+ emission
            for discrete in spec["discrete"]:
                if "INTENSITY" in discrete:
                    intensity = discrete["INTENSITY"][0]  # Intensity in percent
                    total_intensity += intensity
            
            # Return the calculated total, or fall back to FD normalization
            if total_intensity > 0:
                return total_intensity
            else:
                # If no discrete transitions, use FD (discrete normalization)
                # FD is typically a fraction (0-1) or percentage (0-100)
                return spec["FD"][0] * 100.0 if spec["FD"][0] > 1.0 else spec["FD"][0]
    
    # No beta+ spectrum found
    return 0.0


def format_halflife(halflife_seconds):
    """
    Format half-life in human-readable units.
    
    Converts half-life from seconds (ENDF standard) to appropriate units:
    - Seconds (< 1 minute)
    - Minutes (< 1 hour)
    - Hours (< 1 day)
    - Days (< 1 year)
    - Years (>= 1 year)
    
    Args:
        halflife_seconds: Half-life in seconds
    
    Returns:
        Formatted string with appropriate units
    """
    if halflife_seconds < 60:
        return f"{halflife_seconds:.2f} seconds"
    elif halflife_seconds < 3600:
        return f"{halflife_seconds/60:.2f} minutes"
    elif halflife_seconds < 86400:
        return f"{halflife_seconds/3600:.2f} hours"
    elif halflife_seconds < 31536000:
        return f"{halflife_seconds/86400:.2f} days"
    else:
        return f"{halflife_seconds/31536000:.2f} years"


def verify_all_levels(all_results):
    """
    Verify and report on all decay levels found for each nuclide.
    
    This function provides quality assurance by:
    1. Grouping all parsed sections by nuclide (ZA)
    2. Identifying all LIS (isomeric state) levels found
    3. Checking for gaps in the LIS sequence (0, 1, 2, ...)
    4. Warning about potentially missing levels
    5. Showing half-life for each level to help identify them
    
    IMPORTANT: In ENDF-6 format, different isomeric states of the same nuclide
    are stored as SEPARATE sections (often with different MAT numbers).
    For example:
    - Br-74 ground state (LIS=0) → MAT=837
    - Br-74 excited state (LIS=1) → MAT=838
    
    This function ensures we've captured ALL levels from the file.
    
    Args:
        all_results: List of parsed decay data dictionaries
    """
    print("\n" + "="*140)
    print("LEVEL COMPLETENESS CHECK - Verifying ALL Isomeric States Captured")
    print("="*140)
    
    # ===================================================================
    # GROUP ALL RESULTS BY NUCLIDE (ZA)
    # ===================================================================
    # Multiple results may have same ZA but different LIS (isomeric levels)
    nuclides = {}
    for result in all_results:
        za = result["ZA"]
        if za not in nuclides:
            nuclides[za] = []
        nuclides[za].append(result)
    
    # ===================================================================
    # CHECK EACH NUCLIDE FOR LEVEL COMPLETENESS
    # ===================================================================
    for za, states in sorted(nuclides.items()):
        # Extract Z (atomic number) and A (mass number) from ZA
        Z = za // 1000   # Integer division gives atomic number
        A = za % 1000    # Remainder gives mass number
        element = ATOMIC_SYMBOL.get(Z, f"Z{Z}")  # Get element symbol (e.g., "Br")
        
        # ===================================================================
        # SORT LEVELS BY LIS (isomeric state number)
        # ===================================================================
        # LIS=0: Ground state
        # LIS=1: First excited state (often labeled as 'm' or 'm1')
        # LIS=2: Second excited state (labeled as 'm2')
        # etc.
        states_sorted = sorted(states, key=lambda x: x["LIS"])
        lis_values = [s["LIS"] for s in states_sorted]
        mat_values = [s.get("MAT", "?") for s in states_sorted]
        
        print(f"\n{element}-{A} (ZA={za}):")
        print(f"  Found {len(states)} decay level(s): LIS = {lis_values}")
        print(f"  Corresponding MAT numbers: {mat_values}")
        
        # ===================================================================
        # GAP DETECTION: Check for missing LIS levels
        # ===================================================================
        # Expected: LIS should be sequential starting from 0
        # E.g., if we have 3 levels, expect LIS = [0, 1, 2]
        # If we find [0, 2], then LIS=1 is missing!
        expected_lis = list(range(len(states)))
        
        if lis_values != expected_lis:
            # Found a gap or non-sequential LIS values
            missing = set(expected_lis) - set(lis_values)
            if missing:
                print(f"  ⚠ WARNING: Possible missing levels - expected LIS values {expected_lis}, found {lis_values}")
                print(f"            Missing LIS: {sorted(missing)}")
                print(f"            → Check if JEFF database has incomplete data for this nuclide")
        else:
            # All good - sequential LIS from 0 to N-1
            print(f"  ✓ Level sequence is complete (LIS 0 through {len(states)-1})")
        
        # Show details for each level
        for state in states_sorted:
            lis = state["LIS"]
            mat = state.get("MAT", "?")
            
            # Handle half-life (may be missing for stable nuclides or parsing errors)
            if "T1/2" in state and state["T1/2"]:
                halflife_s = state["T1/2"][0]
                halflife_str = format_halflife(halflife_s)
            else:
                halflife_str = "STABLE or unknown"
            
            # Determine state name
            if lis == 0:
                state_name = f"{element}-{A}"
            else:
                state_name = f"{element}-{A}m{lis if lis > 1 else ''}"
            
            print(f"    Level {lis} (MAT={mat}): {state_name}, T½ = {halflife_str}")
    
    print("\n" + "="*140)
    print()


def format_and_print_combined_table(all_results):
    """Generate and print combined formatted table for all decay levels and nuclides."""
    
    if not all_results:
        print("No data to display")
        return
    
    # First verify all levels
    verify_all_levels(all_results)
    
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
    
    # ================================================================
    # CLEAN TABLE FORMAT - All Data in Easy-to-Read Columns
    # ================================================================
    
    print()
    print("="*200)
    print("RADIOACTIVE DECAY DATA TABLE - Clean Format")
    print("="*200)
    print()
    print(f"Total nuclides: {len(nuclides)}")
    print(f"Total decay levels: {len(all_results)}")
    print()
    
    # Print table header
    print(f"{'Z':>3s}  {'A':>4s}  {'Element':>4s}  {'LIS':>3s}  {'Nuclide':>8s}  {'Half-life':>18s}  {'Q-value':>12s}  {'B+ Branch':>10s}  {'EC Branch':>10s}  {'Mean α':>10s}  {'Mean β':>10s}  {'Mean γ':>10s}  {'MAT':>5s}")
    print(f"{'':>3s}  {'':>4s}  {'':>4s}  {'':>3s}  {'Name':>8s}  {'':>18s}  {'(keV)':>12s}  {'(%)':>10s}  {'(%)':>10s}  {'(keV)':>10s}  {'(keV)':>10s}  {'(keV)':>10s}  {'':>5s}")
    print("-"*200)
    
    # Print table rows - one row per decay level
    for za in sorted(nuclides.keys()):
        z = za // 1000
        a = za % 1000
        element = ELEMENT_SYMBOLS.get(z, f'Z{z}')
        
        for result in nuclides[za]:
            lis = result.get("LIS", 0)
            mat = result.get("MAT", 0)
            
            # Handle half-life (may be missing for stable nuclides)
            halflife_s = result.get("T1/2", [0, 0])[0] if "T1/2" in result else 0
            halflife_str = format_halflife(halflife_s) if halflife_s > 0 else "STABLE"
            
            # Nuclide name (e.g., Br-74, Br-74m, Br-74m2)
            if lis == 0:
                nuclide_name = f"{element}-{a}"
            elif lis == 1:
                nuclide_name = f"{element}-{a}m"
            else:
                nuclide_name = f"{element}-{a}m{lis}"
            
            # Get decay data
            if result.get("modes"):
                mode = result["modes"][0]
                q_kev = mode["Q"][0] / 1000.0
                rtyp = mode["RTYP"]
                total_br_pct = mode["BR"][0] * 100.0 if mode["BR"][0] <= 1.0 else mode["BR"][0]
                
                # Calculate B+/EC split
                bplus_br_pct = extract_bplus_branching(result)
                ec_br_pct = total_br_pct - bplus_br_pct
                
                # Mean energies (only if spectra data exists)
                mean_alpha = 0.0
                mean_beta = 0.0
                mean_gamma = 0.0
                
                if "spectra" in result:
                    for spec in result["spectra"]:
                        styp = spec["STYP"]
                        er_av_kev = spec["ER_AV"][0] / 1000.0
                        
                        if styp == 0:  # Gamma
                            mean_gamma = er_av_kev
                        elif styp == 2:  # Beta+
                            mean_beta = er_av_kev
                        elif styp == 4:  # Alpha
                            mean_alpha = er_av_kev
            else:
                # Stable nuclide or no decay modes
                q_kev = 0.0
                bplus_br_pct = 0.0
                ec_br_pct = 0.0
                mean_alpha = 0.0
                mean_beta = 0.0
                mean_gamma = 0.0
            
            # Print single row for this decay level
            print(f"{z:>3d}  {a:>4d}  {element:>4s}  {lis:>3d}  {nuclide_name:>8s}  {halflife_str:>18s}  {q_kev:>12.2f}  {bplus_br_pct:>10.2f}  {ec_br_pct:>10.2f}  {mean_alpha:>10.2f}  {mean_beta:>10.2f}  {mean_gamma:>10.2f}  {mat:>5d}")
    
    print("-"*200)
    print()
    print("Summary:")
    for za in sorted(nuclides.keys()):
        z = za // 1000
        a = za % 1000
        element = ELEMENT_SYMBOLS.get(z, f'Z{z}')
        
        for result in nuclides[za]:
            lis = result.get("LIS", 0)
            mat = result.get("MAT", 0)
            # Handle half-life (may be missing for stable nuclides)
            halflife_s = result.get("T1/2", [0, 0])[0] if "T1/2" in result else 0
            
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
    
    # Handle stable nuclides or missing data
    if "modes" not in parsed_data or "spectra" not in parsed_data:
        print("(Stable nuclide or incomplete decay data)")
        return
    
    # Extract Z and A
    za = parsed_data["ZA"]
    z = za // 1000
    a = za % 1000
    # Handle half-life (may be missing for stable nuclides)
    halflife_s = parsed_data.get("T1/2", [0, 0])[0] if "T1/2" in parsed_data else 0
    
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
    
    # Check if this is a stable nuclide (no decay data)
    if "spectra" not in parsed_data:
        print("(Stable nuclide - no decay transitions)")
        print()
        if "SPI" in parsed_data and "PAR" in parsed_data:
            print(f"Nuclear spin: {parsed_data['SPI']}")
            print(f"Parity: {parsed_data['PAR']}")
        return
    
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
    """
    ═══════════════════════════════════════════════════════════════════════════
    MAIN EXECUTION BLOCK
    ═══════════════════════════════════════════════════════════════════════════
    
    This is the entry point when running: python3 JEFF_ENDF_parser.py <file>
    
    Overall Workflow:
    -----------------
    1. Parse command-line arguments (--verbose, --output, filename)
    2. Validate input file exists
    3. Scan entire ENDF file for ALL MF=8 MT=457 sections (all MAT, all LIS)
    4. Parse each section independently (fault-tolerant)
    5. Group results by nuclide (ZA) and verify ALL levels captured
    6. Generate formatted output with level completeness check
    7. Save to file and display console summary
    
    Design Philosophy:
    ------------------
    - Universal: Works with any ENDF file, any MAT numbers, any nuclides
    - Fault-tolerant: Continues parsing even if some sections fail
    - Complete: Captures ALL isomeric states (LIS) for each nuclide
    - Verifiable: Reports what was found and warns about missing data
    """
    import sys
    import os
    
    # ═══════════════════════════════════════════════════════════════════════════
    # STEP 1: COMMAND-LINE ARGUMENT PARSING
    # ═══════════════════════════════════════════════════════════════════════════
    # Parse command-line arguments to determine mode and file paths
    
    verbose = False       # --verbose flag: Show ALL transition details
    file_arg = None       # Input ENDF file path (required)
    output_file = None    # Output file path (optional, auto-generated if not provided)
    
    # Manual argument parsing (more flexible than argparse for simple cases)
    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg in ['--verbose', '--full', '-v', '--all']:
            verbose = True  # Enable verbose output mode
        elif arg in ['--output', '-o']:
            # Next argument should be the output filename
            if i + 1 < len(sys.argv):
                output_file = sys.argv[i + 1]
                i += 1  # Skip next arg since we consumed it
            else:
                print("ERROR: --output requires a filename argument")
                exit(1)
        elif not arg.startswith('-'):
            # Non-flag argument is the input file
            file_arg = arg
        i += 1
    
    # File argument is REQUIRED
    if not file_arg:
        print()
        print("="*80)
        print("JEFF ENDF-6 Radioactive Decay Data Parser")
        print("="*80)
        print()
        print("Usage:")
        print("  python3 JEFF_ENDF_parser.py <endf_file.endf>                    # Summary view")
        print("  python3 JEFF_ENDF_parser.py --verbose <endf_file.endf>          # Full details")
        print("  python3 JEFF_ENDF_parser.py -o output.txt <endf_file.endf>      # Save to file")
        print("  python3 JEFF_ENDF_parser.py --verbose -o out.txt <file.endf>    # Full details to file")
        print()
        print("Options:")
        print("  --verbose, -v, --full, --all    Show all transitions and detailed data")
        print("  --output, -o <filename>         Save output to specified file")
        print()
        print("Examples:")
        print("  python3 JEFF_ENDF_parser.py jeff-40-radioactive.endf")
        print("  python3 JEFF_ENDF_parser.py --verbose uranium_decay.endf")
        print("  python3 JEFF_ENDF_parser.py -o analysis.txt jeff-40-radioactive.endf")
        print("  python3 JEFF_ENDF_parser.py --verbose -o full_data.txt jeff-40-radioactive.endf")
        print()
        print("="*80)
        exit(1)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # STEP 2: FILE VALIDATION AND OUTPUT FILE SETUP
    # ═══════════════════════════════════════════════════════════════════════════
    
    # Auto-generate output filename if user didn't specify one
    # Example: "jeff-40-radioactive.endf" → "jeff-40-radioactive_parsed_output.txt"
    if output_file is None:
        base_name = os.path.splitext(os.path.basename(file_arg))[0]
        output_file = f"{base_name}_parsed_output.txt"
    
    # Set input file path
    input_file = file_arg
    
    try:
        # ═══════════════════════════════════════════════════════════════════════════
        # STEP 3: READ ENTIRE FILE INTO MEMORY
        # ═══════════════════════════════════════════════════════════════════════════
        # For large JEFF files (~100-200 MB), this is still efficient
        # Modern systems can easily handle this in RAM
        # Alternative would be streaming, but we need multiple passes for section detection
        
        all_results = []  # Will store parsed data for ALL decay sections
        
        with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()  # Read all lines at once
        
        # STEP 1: COMPREHENSIVE SECTION SCANNING
        # ======================================
        # Scan entire file line-by-line to find ALL MF=8 MT=457 sections
        # Each section represents one decay level of one nuclide
        # Different isomeric states (LIS) of the same nuclide have separate sections
        
        section_info = []  # List of (line_num, mat_num) tuples
        for i, line in enumerate(lines):
            # ENDF lines must be at least 75 characters to contain MF/MT info
            if len(line) >= 75:
                try:
                    # Extract ENDF line metadata from fixed-width columns:
                    mat = int(line[66:70].strip() or 0)   # Material number (cols 67-70)
                    mf = int(line[70:72].strip() or 0)    # File number (cols 71-72)
                    mt = int(line[72:75].strip() or 0)    # Section number (cols 73-75)
                    seq = int(line[75:80].strip() or 0)   # Sequence number (cols 76-80)
                    
                    # Look for HEAD records (seq=1) of radioactive decay sections (MF=8, MT=457)
                    # Each HEAD record marks the start of a new decay section
                    # CRITICAL: Different LIS levels of same nuclide have separate HEAD records
                    # CRITICAL: Different MAT numbers may represent different LIS of same nuclide
                    # We MUST capture ALL HEAD records to get ALL levels
                    if mf == 8 and mt == 457 and seq == 1:
                        section_info.append((i, mat))
                        # Note: At this point we don't know the LIS value yet - 
                        # that's in the HEAD record data itself, which we'll parse later
                except:
                    # Skip lines with malformed or missing metadata
                    continue
        
        # Verify we found at least one decay section
        if not section_info:
            print("ERROR: No MF=8 MT=457 section found in file")
            print("This file may not contain radioactive decay data.")
            exit(1)
        
        # Extract unique MAT numbers for reporting
        unique_mats = sorted(set([mat for _, mat in section_info]))
        
        # Report what we found
        print(f"Found {len(section_info)} decay section(s) across {len(unique_mats)} material(s): MAT={', '.join(map(str, unique_mats[:20]))}")
        if len(unique_mats) > 20:
            print(f"  ... and {len(unique_mats) - 20} more materials")
        
        # STEP 2: PARSE EACH DECAY SECTION
        # =================================
        # Process each MF=8 MT=457 section independently
        # Each section may have different LIS (isomeric state level)
        # Track which ZA+LIS combinations we successfully parse
        
        parsed_sections = {}  # Track (ZA, LIS) combinations
        
        for start_pos, mat_num in section_info:
            try:
                # Create a fresh parser for each section
                parser = ENDFNumericDecayParser()
                parser.load_file(input_file)
                parser._pos = start_pos  # Position at this section's HEAD record
                
                # Parse this decay section
                result = parser._parse_mf8_mt457()
                result["MAT"] = mat_num  # Store MAT number with result
                
                # Track what we parsed
                za = result["ZA"]
                lis = result["LIS"]
                parsed_sections[(za, lis)] = mat_num
                
                all_results.append(result)
                print(f"✓ Successfully parsed MAT={mat_num}, ZA={za}, LIS={lis}")
                
            except (EOFError, IndexError, ValueError) as e:
                print(f"⚠ WARNING: Skipped MAT={mat_num} (incomplete data): {str(e)[:60]}")
                continue
            except Exception as e:
                print(f"✗ ERROR: Failed to parse MAT={mat_num}: {str(e)[:60]}")
                continue
        
        # STEP 3: VERIFY ALL LEVELS WERE CAPTURED
        # ========================================
        # Check that we didn't miss any LIS levels
        print(f"\n📊 Parsing Summary:")
        print(f"   Total sections found: {len(section_info)}")
        print(f"   Successfully parsed: {len(all_results)}")
        print(f"   Failed/skipped: {len(section_info) - len(all_results)}")
        
        # Group by nuclide to show LIS distribution
        by_nuclide = {}
        for (za, lis), mat in parsed_sections.items():
            if za not in by_nuclide:
                by_nuclide[za] = []
            by_nuclide[za].append((lis, mat))
        
        print(f"   Unique nuclides: {len(by_nuclide)}")
        
        # Show examples of multi-level nuclides
        multi_level = {za: levels for za, levels in by_nuclide.items() if len(levels) > 1}
        if multi_level:
            print(f"   Multi-level nuclides: {len(multi_level)}")
            print(f"   Examples:")
            for za, levels in sorted(multi_level.items())[:5]:
                Z = za // 1000
                A = za % 1000
                element = ATOMIC_SYMBOL.get(Z, f'Z{Z}')
                lis_values = sorted([lis for lis, _ in levels])
                print(f"     {element}-{A}: LIS = {lis_values}")
        
        # Check if we have any results
        if not all_results:
            print("ERROR: No decay data could be parsed from the file.")
            print("The file may contain incomplete or corrupted ENDF records.")
            exit(1)
        
        # Redirect output to file
        original_stdout = sys.stdout
        
        try:
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
        except Exception as e:
            # Make sure to restore stdout before printing error
            sys.stdout = original_stdout
            raise
        
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
            # Handle half-life (may be missing for stable nuclides)
            halflife_s = result.get("T1/2", [0, 0])[0] if "T1/2" in result else 0
            element = ATOMIC_SYMBOL.get(z, f'Z{z}')
            
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
        # Make sure stdout is restored before printing error
        if 'original_stdout' in locals():
            sys.stdout = original_stdout
        
        print()
        print("="*80)
        print(f"ERROR: Failed during output generation")
        print("="*80)
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {e}")
        print()
        print(f"Parsing completed successfully for {len(all_results)} decay states")
        print(f"Error occurred while generating output file: {output_file}")
        print()
        print("This may indicate:")
        print("  • A stable nuclide (NST=1) was encountered")
        print("  • Missing data in one of the parsed sections")
        print("  • A structure we haven't seen before")
        print()
        print("Partial data may have been written to output file.")
        print()
        import traceback
        print("Full traceback:")
        traceback.print_exc()
        exit(1)
