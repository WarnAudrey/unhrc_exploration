from pathlib import Path
from typing import Any, Dict, Tuple

from endf_mf8_mt457_numeric_parser import ENDFNumericDecayParser, Tabulated1D


def sci(x: float) -> str:
    return f"{x:.6e}"


def fmt_pair(p: Tuple[float, float], unit: str) -> str:
    return f"{sci(float(p[0]))} {unit} ± {sci(float(p[1]))} {unit}"


def print_head(data: Dict[str, Any]) -> None:
    za = int(data.get("ZA", 0))
    z = za // 1000
    a = za % 1000
    awr = data.get("AWR", None)
    print("=== HEAD (MF=8, MT=457) ===")
    print(f"ZA: {za} (Z={z}, A={a})")
    if awr is not None:
        print(f"AWR: {sci(float(awr))} (atomic weight ratio, dimensionless)")
    print(f"LIS: {data.get('LIS', 0)}  LISO: {data.get('LISO', 0)}  NST: {data.get('NST', 0)}  NSP: {data.get('NSP', 0)}")
    print()


def print_decay_summary(data: Dict[str, Any]) -> None:
    if data.get("NST", 0) == 1:
        print("Nuclide is stable (NST=1)")
        if "SPI" in data:
            print(f"Spin (SPI): {sci(float(data['SPI']))}")
        if "PAR" in data:
            print(f"Parity (PAR): {sci(float(data['PAR']))}")
        print()
        return

    # Half-life and excited states
    t12 = data.get("T1/2")
    if isinstance(t12, tuple) and len(t12) == 2:
        print("Half-life (seconds):", fmt_pair(t12, "s"))
    nc = data.get("NC")
    if nc is not None:
        print(f"Number of level energies (NC): {nc}")
    ex_list = data.get("Ex", [])
    if ex_list:
        print("Excited level energies (Ex): value ± unc [eV]")
        for i, p in enumerate(ex_list, 1):
            print(f"  Ex[{i:02d}]: {fmt_pair(p, 'eV')}")
    # Decay parameters
    if "SPI" in data:
        print(f"Spin (SPI): {sci(float(data['SPI']))}")
    if "PAR" in data:
        print(f"Parity (PAR): {sci(float(data['PAR']))}")

    # Decay modes
    modes = data.get("modes", [])
    if modes:
        print("\nDecay modes (RTYP, RFS, Q, BR):")
        print("  idx  RTYP        RFS         Q [eV] (val ± unc)            BR (val ± unc)")
        for i, m in enumerate(modes, 1):
            q = m.get("Q", (0.0, 0.0))
            br = m.get("BR", (0.0, 0.0))
            print(
                f"  {i:3d}  {sci(float(m.get('RTYP', 0.0))):>10}  {sci(float(m.get('RFS', 0.0))):>10}  "
                f"{sci(float(q[0]))} eV ± {sci(float(q[1]))} eV   "
                f"{sci(float(br[0]))} ± {sci(float(br[1]))}"
            )
    print()


def print_spectrum(idx: int, spec: Dict[str, Any]) -> None:
    print(f"--- Spectrum {idx} ---")
    styp = spec.get("STYP")
    lcon = spec.get("LCON")
    lcov = spec.get("LCOV")
    ner = spec.get("NER")
    print(f"STYP: {styp}  LCON: {lcon}  LCOV: {lcov}  NER: {ner}")

    fd = spec.get("FD")
    er_av = spec.get("ER_AV")
    fc = spec.get("FC")
    if isinstance(fd, tuple):
        print("FD (fraction of decays):", fmt_pair(fd, ""))
    if isinstance(er_av, tuple):
        print("ER_AV (average energy):", fmt_pair(er_av, "eV"))
    if isinstance(fc, tuple):
        print("FC (average intensity):", fmt_pair(fc, ""))

    if lcon != 1 and spec.get("discrete"):
        print("Discrete lines:")
        print("  idx    ER [eV] (val ± unc)          RTYP         TYPE         RI (val ± unc)        RIS (val ± unc)        RICC (val ± unc)        RICK (val ± unc)        RICL (val ± unc)")
        for j, d in enumerate(spec["discrete"], 1):
            er = d.get("ER", (0.0, 0.0))
            rtyp = sci(float(d.get("RTYP", 0.0)))
            dtype = sci(float(d.get("TYPE", 0.0)))
            def fmt_opt(pair):
                return fmt_pair(pair, "") if isinstance(pair, tuple) and len(pair) == 2 else ""
            ri = fmt_opt(d.get("RI"))
            ris = fmt_opt(d.get("RIS"))
            ricc = fmt_opt(d.get("RICC"))
            rick = fmt_opt(d.get("RICK"))
            ricl = fmt_opt(d.get("RICL"))
            print(
                f"  {j:3d}  {sci(float(er[0]))} eV ± {sci(float(er[1]))} eV  {rtyp:>12}  {dtype:>12}  "
                f"{ri:>22}  {ris:>22}  {ricc:>22}  {rick:>22}  {ricl:>22}"
            )

    if lcon != 0 and spec.get("continuous"):
        cont = spec["continuous"]
        rp = cont.get("RP")
        if isinstance(rp, Tabulated1D):
            print("Continuous spectrum RP (energy vs density):")
            print("  Energy [eV]           Density")
            for xv, yv in zip(rp.x, rp.y):
                print(f"  {sci(float(xv))}    {sci(float(yv))}")

    if lcov not in (0, 2) and spec.get("continuous_covariance"):
        cc = spec["continuous_covariance"]
        print("Continuous covariance (Ek, Fk):")
        Ek = cc.get("Ek") or []
        Fk = cc.get("Fk") or []
        print("  Ek [eV]               Fk")
        for ek, fk in zip(Ek, Fk):
            print(f"  {sci(float(ek))}    {sci(float(fk))}")

    if lcov not in (0, 1) and spec.get("discrete_covariance"):
        dc = spec["discrete_covariance"]
        Ek = dc.get("Ek") or []
        Fkk = dc.get("Fkk") or []
        print("Discrete covariance:")
        print(f"  LS={dc.get('LS')}, LB={dc.get('LB')}, NE={dc.get('NE')}, NERP={dc.get('NERP')}")
        print("  Ek [eV]           Fkk (packed)")
        for ek, fk in zip(Ek, Fkk):
            print(f"  {sci(float(ek))}    {sci(float(fk))}")
    print()


def main() -> None:
    text = Path("sample_endf_input.txt").read_text(encoding="utf-8")
    parser = ENDFNumericDecayParser(text)
    data = parser.parse_file("sample_endf_input.txt")

    print_head(data)
    print_decay_summary(data)

    spectra = data.get("spectra", [])
    for i, spec in enumerate(spectra, 1):
        print_spectrum(i, spec)


if __name__ == "__main__":
    main()
