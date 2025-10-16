from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from endf_mf8_mt457_numeric_parser import ENDFNumericDecayParser, Tabulated1D


def sci(v: float) -> str:
    return f"{float(v):.6e}"


def fmt_pair(pair: Tuple[float, float], unit: str = "") -> str:
    val, unc = float(pair[0]), float(pair[1])
    if unit:
        return f"{sci(val)} {unit} ± {sci(unc)} {unit}"
    return f"{sci(val)} ± {sci(unc)}"


def draw_table(headers: Sequence[str], rows: Sequence[Sequence[str]], aligns: Sequence[str] | None = None) -> str:
    cols = len(headers)
    widths = [len(h) for h in headers]
    for r in rows:
        for i, cell in enumerate(r):
            widths[i] = max(widths[i], len(cell))
    if aligns is None:
        aligns = ["l"] * cols

    def fmt_row(cells: Sequence[str]) -> str:
        parts: List[str] = []
        for i, c in enumerate(cells):
            w = widths[i]
            if aligns[i] == "r":
                parts.append(c.rjust(w))
            elif aligns[i] == "c":
                pad = w - len(c)
                left = pad // 2
                right = pad - left
                parts.append(" " * left + c + " " * right)
            else:
                parts.append(c.ljust(w))
        return "  ".join(parts)

    sep = "  ".join("-" * w for w in widths)
    lines = [fmt_row(headers), sep]
    lines += [fmt_row(r) for r in rows]
    return "\n".join(lines)


def header_section(data: Dict[str, Any]) -> str:
    za = int(data.get("ZA", 0))
    z = za // 1000
    a = za % 1000
    awr = data.get("AWR")
    info_rows = [
        ("ZA", str(za)),
        ("Z", str(z)),
        ("A", str(a)),
        ("AWR (atomic weight ratio)", sci(awr) if awr is not None else ""),
        ("LIS", str(data.get("LIS", ""))),
        ("LISO", str(data.get("LISO", ""))),
        ("NST", str(data.get("NST", ""))),
        ("NSP", str(data.get("NSP", ""))),
    ]
    headers = ("Field", "Value")
    rows = [(k, v) for k, v in info_rows]
    return draw_table(headers, rows, aligns=["l", "r"])


def half_life_section(data: Dict[str, Any]) -> str:
    lines: List[str] = []
    if data.get("NST", 0) == 1:
        return draw_table(["Stable nuclide"], [[]])
    t12 = data.get("T1/2")
    rows: List[Sequence[str]] = []
    if isinstance(t12, tuple) and len(t12) == 2:
        rows.append(("Half-life", fmt_pair(t12, "s")))
    nc = data.get("NC")
    if nc is not None:
        rows.append(("NC (levels)", str(nc)))
    ex_list = data.get("Ex", [])
    for i, p in enumerate(ex_list, 1):
        rows.append((f"Ex[{i}]", fmt_pair(p, "eV")))
    if "SPI" in data:
        rows.append(("Spin (SPI)", sci(data["SPI"])))
    if "PAR" in data:
        rows.append(("Parity (PAR)", sci(data["PAR"])))
    return draw_table(["Parameter", "Value"], rows, aligns=["l", "r"])


def modes_section(data: Dict[str, Any]) -> str:
    modes = data.get("modes", [])
    if not modes:
        return ""
    headers = ("idx", "RTYP", "RFS", "Q [eV] (val ± unc)", "BR (val ± unc)")
    rows: List[Sequence[str]] = []
    for i, m in enumerate(modes, 1):
        q = m.get("Q", (0.0, 0.0))
        br = m.get("BR", (0.0, 0.0))
        rows.append(
            (
                f"{i}",
                sci(m.get("RTYP", 0.0)),
                sci(m.get("RFS", 0.0)),
                fmt_pair(q, "eV"),
                fmt_pair(br, ""),
            )
        )
    return draw_table(headers, rows, aligns=["r", "r", "r", "r", "r"])


def discrete_section(spec: Dict[str, Any]) -> str:
    if not spec.get("discrete"):
        return ""
    headers = (
        "idx",
        "ER [eV] (val ± unc)",
        "RTYP",
        "TYPE",
        "RI (val ± unc)",
        "RIS (val ± unc)",
        "RICC (val ± unc)",
        "RICK (val ± unc)",
        "RICL (val ± unc)",
    )
    rows: List[Sequence[str]] = []
    for i, d in enumerate(spec["discrete"], 1):
        er = d.get("ER", (0.0, 0.0))
        def maybe(p):
            return fmt_pair(p, "") if isinstance(p, tuple) and len(p) == 2 else ""
        rows.append(
            (
                f"{i}",
                fmt_pair(er, "eV"),
                sci(d.get("RTYP", 0.0)),
                sci(d.get("TYPE", 0.0)),
                maybe(d.get("RI")),
                maybe(d.get("RIS")),
                maybe(d.get("RICC")),
                maybe(d.get("RICK")),
                maybe(d.get("RICL")),
            )
        )
    return draw_table(headers, rows, aligns=["r"] + ["r"] * (len(headers) - 1))


def continuous_section(spec: Dict[str, Any]) -> str:
    if not spec.get("continuous"):
        return ""
    rp = spec["continuous"].get("RP")
    if not isinstance(rp, Tabulated1D):
        return ""
    headers = ("Energy [eV]", "Density")
    rows = [(sci(x), sci(y)) for x, y in zip(rp.x, rp.y)]
    return draw_table(headers, rows, aligns=["r", "r"])


def spectrum_sections(data: Dict[str, Any]) -> str:
    out_lines: List[str] = []
    for i, spec in enumerate(data.get("spectra", []), 1):
        out_lines.append(f"Spectrum {i}: STYP={spec.get('STYP')}, LCON={spec.get('LCON')}, LCOV={spec.get('LCOV')}, NER={spec.get('NER')}")
        # Header values
        fd = spec.get("FD")
        er_av = spec.get("ER_AV")
        fc = spec.get("FC")
        hdr_rows: List[Sequence[str]] = []
        if isinstance(fd, tuple):
            hdr_rows.append(("FD (fraction of decays)", fmt_pair(fd, "")))
        if isinstance(er_av, tuple):
            hdr_rows.append(("ER_AV (average energy)", fmt_pair(er_av, "eV")))
        if isinstance(fc, tuple):
            hdr_rows.append(("FC (average intensity)", fmt_pair(fc, "")))
        if hdr_rows:
            out_lines.append(draw_table(["Quantity", "Value"], hdr_rows, aligns=["l", "r"]))
        # Discrete
        dsec = discrete_section(spec)
        if dsec:
            out_lines.append(dsec)
        # Continuous
        csec = continuous_section(spec)
        if csec:
            out_lines.append(csec)
    return "\n\n".join(out_lines)


def main() -> None:
    text = Path("sample_endf_input.txt").read_text(encoding="utf-8")
    parser = ENDFNumericDecayParser(text)
    data = parser.parse_file("sample_endf_input.txt")

    print("=== MF=8 MT=457 Radioactive Decay Data (Numeric) ===")
    print()
    print(header_section(data))
    print()
    print(half_life_section(data))
    print()
    msec = modes_section(data)
    if msec:
        print("Decay Modes:")
        print(msec)
        print()
    ssec = spectrum_sections(data)
    if ssec:
        print(ssec)


if __name__ == "__main__":
    main()
