"""Utility for comparing ENSDF and ENDF decay datasets.

Loads ASCII decay data, identifies nuclides unique to each source,
and prints statistics about their decay modes.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Sequence, Set, Tuple

import numpy as np
import pandas as pd


DEFAULT_ENSDF_PATH = (
    "/Users/audreywarn/fluka-db-audrey/outputs/ensdf/json_data_modules/ascii/DECAY.ascii"
)
DEFAULT_ENDF_PATH = (
    "/Users/audreywarn/fluka-db-audrey/outputs/endf/endf_data_modules/ascii/DECAY.ascii"
)


NUCLIDE = Tuple[int, int]  # (Z, A)


@dataclass
class DecayDataset:
    name: str
    path: Path
    frame: pd.DataFrame
    z_col: str
    a_col: str
    mode_col: str

    @property
    def nuclides(self) -> Set[NUCLIDE]:
        data = self.frame[[self.z_col, self.a_col]].dropna()
        return set(map(tuple, data.astype(int).itertuples(index=False, name=None)))


def _normalise_column_names(columns: Sequence[str]) -> Sequence[str]:
    return [col.strip() if isinstance(col, str) else col for col in columns]


def _guess_column(columns: Iterable[str], *candidates: str) -> Optional[str]:
    normalised = {col.upper().replace(" ", "").replace("-", "").replace("_", ""): col for col in columns}
    for candidate in candidates:
        key = candidate.upper().replace(" ", "").replace("-", "").replace("_", "")
        if key in normalised:
            return normalised[key]
    return None


def _detect_mode_column(columns: Sequence[str]) -> Optional[str]:
    # Prioritise explicit mode-like names
    priority = [
        "DECAY_MODE",
        "RADTYPE",
        "MODE",
        "DECAYMODE",
        "DECMODE",
        "DECAYTYPE",
        "TYPE",
    ]

    for name in priority:
        match = _guess_column(columns, name)
        if match:
            return match

    # Fall back to any column containing these substrings (case insensitive)
    substrings = ("MODE", "DECAY", "RAD")
    for column in columns:
        if not isinstance(column, str):
            continue
        upper = column.upper()
        if any(sub in upper for sub in substrings):
            return column

    return None


def read_decay_dataset(
    name: str,
    path: Path,
    *,
    mode_column: Optional[str] = None,
    z_column: Optional[str] = None,
    a_column: Optional[str] = None,
) -> DecayDataset:
    if not path.exists():
        raise FileNotFoundError(f"{name} file not found: {path}")

    try:
        frame = pd.read_csv(
            path,
            delim_whitespace=True,
            comment="#",
            dtype=str,
            engine="python",
        )
    except Exception as exc:
        raise RuntimeError(f"Failed to read {name} dataset at {path}") from exc

    if frame.empty:
        raise ValueError(f"{name} dataset is empty: {path}")

    frame.columns = _normalise_column_names(frame.columns)

    all_columns = list(frame.columns)

    z_col = z_column or _guess_column(all_columns, "Z", "PROTON", "ZNUM")
    a_col = a_column or _guess_column(all_columns, "A", "MASS", "ANUM")

    if z_col is None or a_col is None:
        raise ValueError(
            f"Unable to identify Z/A columns in {name} dataset. "
            f"Detected columns: {all_columns}. Provide --{name.lower()}-z-col and --{name.lower()}-a-col."
        )

    mode_col: Optional[str] = mode_column or _detect_mode_column(all_columns)
    if mode_col is None:
        raise ValueError(
            f"Unable to detect decay mode column for {name}. "
            f"Detected columns: {all_columns}. Provide --{name.lower()}-mode-col."
        )

    # Convert Z and A to integers, dropping rows where conversion fails
    frame[z_col] = pd.to_numeric(frame[z_col], errors="coerce")
    frame[a_col] = pd.to_numeric(frame[a_col], errors="coerce")
    frame = frame.dropna(subset=[z_col, a_col])
    frame[z_col] = frame[z_col].astype(int)
    frame[a_col] = frame[a_col].astype(int)

    # Normalise decay mode entries as strings and strip whitespace
    frame[mode_col] = frame[mode_col].astype(str).str.strip().replace({"": "UNKNOWN", "nan": "UNKNOWN"})

    return DecayDataset(name=name, path=path, frame=frame, z_col=z_col, a_col=a_col, mode_col=mode_col)


def merge_decay_data(frame: pd.DataFrame, nuclides: Set[NUCLIDE], z_col: str, a_col: str) -> pd.DataFrame:
    if not nuclides:
        return frame.iloc[0:0]

    nuclide_df = pd.DataFrame(sorted(nuclides), columns=[z_col, a_col])
    merged = frame.merge(nuclide_df, on=[z_col, a_col], how="inner")
    return merged


def describe_decay_modes(dataset: DecayDataset, nuclides: Set[NUCLIDE], label: str, top_n: int = 10) -> None:
    print(f"\nDecay mode statistics for {dataset.name} ? {label}")
    if not nuclides:
        print("  No nuclides in this category.")
        return

    subset = merge_decay_data(dataset.frame, nuclides, dataset.z_col, dataset.a_col)
    if subset.empty:
        print("  No decay entries found for the specified nuclides.")
        return

    total_nuclides = len(nuclides)
    total_rows = len(subset)

    per_nuclide_counts = subset.groupby([dataset.z_col, dataset.a_col])[dataset.mode_col].count()
    per_nuclide_unique_modes = subset.groupby([dataset.z_col, dataset.a_col])[dataset.mode_col].nunique()

    avg_decays_per_nuclide = per_nuclide_counts.mean()
    median_decays_per_nuclide = per_nuclide_counts.median()
    avg_unique_modes = per_nuclide_unique_modes.mean()

    mode_counts = subset[dataset.mode_col].value_counts(dropna=False)

    print(f"  Nuclide count: {total_nuclides}")
    print(f"  Decay entry count: {total_rows}")
    print(f"  Avg decays per nuclide: {avg_decays_per_nuclide:.2f}")
    print(f"  Median decays per nuclide: {median_decays_per_nuclide:.2f}")
    print(f"  Avg unique decay modes per nuclide: {avg_unique_modes:.2f}")
    print(f"  Unique decay modes: {mode_counts.size}")
    print("  Top decay modes:")

    for mode, count in mode_counts.head(top_n).items():
        fraction = count / total_rows
        print(f"    {mode:>15}: {count:>6} ({fraction:>6.2%})")


def parse_arguments(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare ENDF and ENSDF decay mode coverage.")

    parser.add_argument("--ensdf", type=Path, default=Path(DEFAULT_ENSDF_PATH), help="Path to ENSDF DECAY.ascii file")
    parser.add_argument("--endf", type=Path, default=Path(DEFAULT_ENDF_PATH), help="Path to ENDF DECAY.ascii file")

    parser.add_argument("--ensdf-mode-col", dest="ensdf_mode_col", help="Explicit decay mode column for ENSDF")
    parser.add_argument("--endf-mode-col", dest="endf_mode_col", help="Explicit decay mode column for ENDF")

    parser.add_argument("--z-col", dest="z_col", help="Override proton number column (applies to both datasets)")
    parser.add_argument("--a-col", dest="a_col", help="Override mass number column (applies to both datasets)")

    parser.add_argument(
        "--top-n",
        type=int,
        default=10,
        help="Number of top decay modes to display for each category",
    )

    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_arguments(argv)

    try:
        ensdf_dataset = read_decay_dataset(
            "ENSDF",
            args.ensdf,
            mode_column=args.ensdf_mode_col,
            z_column=args.z_col,
            a_column=args.a_col,
        )
        endf_dataset = read_decay_dataset(
            "ENDF",
            args.endf,
            mode_column=args.endf_mode_col,
            z_column=args.z_col,
            a_column=args.a_col,
        )
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    ensdf_nuclides = ensdf_dataset.nuclides
    endf_nuclides = endf_dataset.nuclides

    combined = ensdf_nuclides | endf_nuclides
    common = ensdf_nuclides & endf_nuclides
    ensdf_only = ensdf_nuclides - endf_nuclides
    endf_only = endf_nuclides - ensdf_nuclides

    print("Summary of nuclide coverage")
    print("---------------------------")
    print(f"ENSDF nuclides: {len(ensdf_nuclides):>6}")
    print(f"ENDF nuclides : {len(endf_nuclides):>6}")
    print(f"Common        : {len(common):>6}")
    print(f"ENSDF only    : {len(ensdf_only):>6}")
    print(f"ENDF only     : {len(endf_only):>6}")
    coverage = (len(common) / len(combined) * 100.0) if combined else np.nan
    print(f"Coverage overlap: {coverage:.2f}%" if not np.isnan(coverage) else "Coverage overlap: N/A")

    describe_decay_modes(ensdf_dataset, ensdf_only, "nuclides unique to ENSDF", top_n=args.top_n)
    describe_decay_modes(endf_dataset, endf_only, "nuclides unique to ENDF", top_n=args.top_n)
    describe_decay_modes(ensdf_dataset, common, "common nuclides (ENSDF view)", top_n=args.top_n)


if __name__ == "__main__":
    main()

