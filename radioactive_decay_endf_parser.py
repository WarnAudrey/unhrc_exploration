import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np


class Tabulated1D:
    """A one-dimensional tabulated function supporting ENDF TAB1 interpolation."""

    def __init__(
        self,
        x: Iterable[float],
        y: Iterable[float],
        breakpoints: Optional[Iterable[int]] = None,
        interpolation: Optional[Iterable[int]] = None,
    ) -> None:
        # Materialize inputs once to avoid double-consuming iterables
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

    def __repr__(self) -> str:
        return f"<Tabulated1D: {self.x.size} points, {self.breakpoints.size} regions>"

    def __call__(self, x: Iterable[float] | float) -> np.ndarray | float:
        if isinstance(x, (int, float)):
            return self._interpolate_scalar(float(x))

        x_arr = np.asarray(list(x) if not isinstance(x, np.ndarray) else x, dtype=float)
        y = np.empty_like(x_arr)

        # Clamp out-of-range to boundary values
        below = x_arr <= self.x[0]
        above = x_arr >= self.x[-1]
        inside = ~(below | above)
        y[below] = self.y[0]
        y[above] = self.y[-1]

        if np.any(inside):
            xi_arr = x_arr[inside]
            idx = np.searchsorted(self.x, xi_arr, side="right") - 1
            idx = np.clip(idx, 0, self.x.size - 2)

            dest = np.flatnonzero(inside)

            # Evaluate by interpolation regions
            for k in range(len(self.breakpoints)):
                start_index = self.breakpoints[k - 1] - 1 if k > 0 else 0
                end_index = self.breakpoints[k] - 1
                mask = (idx >= start_index) & (idx < end_index)
                if not np.any(mask):
                    continue

                xk = xi_arr[mask]
                base_idx = idx[mask]
                xi = self.x[base_idx]
                xi1 = self.x[base_idx + 1]
                yi = self.y[base_idx]
                yi1 = self.y[base_idx + 1]

                itp = int(self.interpolation[k])
                target_idx = dest[mask]
                if itp == 1:
                    y[target_idx] = yi
                elif itp == 2:
                    y[target_idx] = yi + (xk - xi) / (xi1 - xi) * (yi1 - yi)
                elif itp == 3:
                    y[target_idx] = yi + np.log(xk / xi) / np.log(xi1 / xi) * (yi1 - yi)
                elif itp == 4:
                    y[target_idx] = yi * np.exp((xk - xi) / (xi1 - xi) * np.log(yi1 / yi))
                elif itp == 5:
                    y[target_idx] = yi * np.exp(
                        np.log(xk / xi) / np.log(xi1 / xi) * np.log(yi1 / yi)
                    )

        return y

    def _interpolate_scalar(self, x: float) -> float:
        if x <= self._x[0]:
            return float(self._y[0])
        if x >= self._x[-1]:
            return float(self._y[-1])

        idx = int(np.searchsorted(self._x, x, side="right") - 1)
        p = 2
        for b, p in zip(self.breakpoints, self.interpolation):
            if idx < b - 1:
                break

        xi = float(self._x[idx])
        xi1 = float(self._x[idx + 1])
        yi = float(self._y[idx])
        yi1 = float(self._y[idx + 1])

        if p == 1:
            return yi
        if p == 2:
            return yi + (x - xi) / (xi1 - xi) * (yi1 - yi)
        if p == 3:
            return yi + np.log(x / xi) / np.log(xi1 / xi) * (yi1 - yi)
        if p == 4:
            return yi * np.exp((x - xi) / (xi1 - xi) * np.log(yi1 / yi))
        if p == 5:
            return yi * np.exp(np.log(x / xi) / np.log(xi1 / xi) * np.log(yi1 / yi))
        return yi

    def integral(self) -> np.ndarray:
        partial_sum = np.zeros(len(self.x) - 1)
        i_low = 0
        for k in range(len(self.breakpoints)):
            i_high = int(self.breakpoints[k] - 1)
            x0 = self.x[i_low:i_high]
            x1 = self.x[i_low + 1 : i_high + 1]
            y0 = self.y[i_low:i_high]
            y1 = self.y[i_low + 1 : i_high + 1]

            itp = int(self.interpolation[k])
            if itp == 1:
                partial_sum[i_low:i_high] = y0 * (x1 - x0)
            elif itp == 2:
                m = (y1 - y0) / (x1 - x0)
                partial_sum[i_low:i_high] = (y0 - m * x0) * (x1 - x0) + m * (x1**2 - x0**2) / 2
            elif itp == 3:
                # Linear in log(x): y = y0 + m*ln(x/x0), m = (y1 - y0)/ln(x1/x0)
                logx = np.log(x1 / x0)
                m = (y1 - y0) / logx
                partial_sum[i_low:i_high] = y0 * (x1 - x0) + m * (x1 * logx - x1 + x0)
            elif itp == 4:
                m = np.log(y1 / y0) / (x1 - x0)
                partial_sum[i_low:i_high] = y0 / m * (np.exp(m * (x1 - x0)) - 1)
            elif itp == 5:
                m = np.log(y1 / y0) / np.log(x1 / x0)
                partial_sum[i_low:i_high] = y0 / ((m + 1) * x0**m) * (x1 ** (m + 1) - x0 ** (m + 1))

            i_low = i_high

        return np.concatenate(([0.0], np.cumsum(partial_sum)))

    @property
    def x(self) -> np.ndarray:
        return self._x

    @x.setter
    def x(self, x: Iterable[float]) -> None:
        self._x = np.asarray(list(x), dtype=float)

    @property
    def y(self) -> np.ndarray:
        return self._y

    @y.setter
    def y(self, y: Iterable[float]) -> None:
        self._y = np.asarray(list(y), dtype=float)

    @property
    def breakpoints(self) -> np.ndarray:
        return self._breakpoints

    @breakpoints.setter
    def breakpoints(self, breakpoints: Iterable[int]) -> None:
        self._breakpoints = np.asarray(list(breakpoints), dtype=int)

    @property
    def interpolation(self) -> np.ndarray:
        return self._interpolation

    @interpolation.setter
    def interpolation(self, interpolation: Iterable[int]) -> None:
        self._interpolation = np.asarray(list(interpolation), dtype=int)


class Tabulated2D:
    """Metadata holder for a two-dimensional function's interpolation info."""

    def __init__(self, breakpoints: Iterable[int], interpolation: Iterable[int]) -> None:
        self.breakpoints = np.asarray(list(breakpoints), dtype=int)
        self.interpolation = np.asarray(list(interpolation), dtype=int)


class ENDFRadioactiveDecayParser:
    """Parser for ENDF-6 radioactive decay data (MF=8, MT=457).

    Example:
        parser = ENDFRadioactiveDecayParser()
        data = parser.parse_file("/Users/audreywarn/fluka-db-audrey/src/PyClasses/74Br.txt")
    """

    ENDF_FLOAT_RE = re.compile(r"([\s\-\+]?\d*\.\d+)([\+\-]) ?(\d+)")

    def __init__(self, text: Optional[str] = None) -> None:
        self._lines: List[str] = []
        self._pos: int = 0
        if text is not None:
            self.load_text(text)

    # ---------- Public API ----------
    def load_text(self, text: str) -> None:
        self._lines = text.splitlines()
        self._pos = 0

    def load_file(self, path: str) -> None:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            self._lines = fh.read().splitlines()
        self._pos = 0

    def parse_file(self, path: str) -> Dict[str, Any]:
        self.load_file(path)
        if not self._scan_to_mf_mt(8, 457):
            raise ValueError("No MF=8 MT=457 section found in file")
        return self._parse_mf8_mt457()

    # ---------- Low-level line handling ----------
    def _readline(self) -> str:
        if self._pos >= len(self._lines):
            raise EOFError("Unexpected end of file while parsing ENDF data")
        line = self._lines[self._pos]
        self._pos += 1
        if len(line) < 80:
            # Pad to 80 chars to ensure fixed-width slices are safe
            line = f"{line:<80}"
        return line

    def _peekline(self) -> str:
        if self._pos >= len(self._lines):
            raise EOFError("Unexpected end of file while parsing ENDF data")
        line = self._lines[self._pos]
        if len(line) < 80:
            line = f"{line:<80}"
        return line

    def _scan_to_mf_mt(self, mf: int, mt: int) -> bool:
        for i in range(self._pos, len(self._lines)):
            ln = self._lines[i]
            if len(ln) < 80:
                ln = f"{ln:<80}"
            try:
                mf_val = self._int_endf(ln[70:72])
                mt_val = self._int_endf(ln[72:75])
            except Exception:
                continue
            if mf_val == mf and mt_val == mt:
                self._pos = i
                return True
        return False

    # ---------- ENDF field parsers ----------
    @classmethod
    def _py_float_endf(cls, s: str) -> float:
        return float(cls.ENDF_FLOAT_RE.sub(r"\1e\2\3", s))

    @staticmethod
    def _int_endf(s: str) -> int:
        return 0 if s.strip() == "" else int(s)

    # ---------- ENDF record readers ----------
    def _get_text_record(self) -> str:
        return self._readline()[:66]

    def _get_cont_record(self, skip_c: bool = False) -> Tuple[Optional[float], Optional[float], int, int, int, int]:
        line = self._readline()
        if skip_c:
            c1 = None
            c2 = None
        else:
            c1 = self._py_float_endf(line[:11])
            c2 = self._py_float_endf(line[11:22])
        l1 = self._int_endf(line[22:33])
        l2 = self._int_endf(line[33:44])
        n1 = self._int_endf(line[44:55])
        n2 = self._int_endf(line[55:66])
        return c1, c2, l1, l2, n1, n2

    def _get_head_record(self) -> Tuple[int, float, int, int, int, int]:
        line = self._readline()
        za = int(self._py_float_endf(line[:11]))
        awr = self._py_float_endf(line[11:22])
        l1 = self._int_endf(line[22:33])
        l2 = self._int_endf(line[33:44])
        n1 = self._int_endf(line[44:55])
        n2 = self._int_endf(line[55:66])
        return za, awr, l1, l2, n1, n2

    def _get_list_record(self) -> Tuple[List[Any], np.ndarray]:
        items = list(self._get_cont_record())
        npl = int(items[4])
        b = np.empty(npl)
        for i in range((npl - 1) // 6 + 1):
            line = self._readline()
            n = min(6, npl - 6 * i)
            for j in range(n):
                b[6 * i + j] = self._py_float_endf(line[11 * j : 11 * (j + 1)])
        return items, b

    def _get_tab1_record(self) -> Tuple[List[Any], Tabulated1D]:
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

    def _get_tab2_record(self) -> Tuple[Tuple[Optional[float], Optional[float], int, int, int, int], Tabulated2D]:
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

    def _get_intg_record(self) -> np.ndarray:
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

    # ---------- MF=8, MT=457 parser ----------
    def _parse_mf8_mt457(self) -> Dict[str, Any]:
        za, awr, lis, liso, nst, nsp = self._get_head_record()
        data: Dict[str, Any] = {"ZA": za, "AWR": awr, "LIS": lis, "LISO": liso, "NST": nst, "NSP": nsp}

        if nst == 1:
            self._get_list_record()  # NG (not used here)
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
            spectrum: Dict[str, Any] = {"STYP": styp, "LCON": lcon, "LCOV": lcov, "NER": ner}

            spectrum["FD"] = tuple(values[0:2].astype(float))
            spectrum["ER_AV"] = tuple(values[2:4].astype(float))
            spectrum["FC"] = tuple(values[4:6].astype(float))

            if lcon != 1:
                spectrum["discrete"] = []
                for _ in range(ner):
                    items_d, values_d = self._get_list_record()
                    discrete: Dict[str, Any] = {}
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
