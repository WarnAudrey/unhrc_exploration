# ENDF-6 Radioactive Decay Data Parser

A Python parser for ENDF-6 format radioactive decay data (MF=8, MT=457) with proper B+/EC splitting according to ENDF-102 specifications.

## Features

- ✅ **ENDF-102 Compliant** - Follows official ENDF-102-2023 specifications
- ✅ **Ignores Text Sections** - Only parses numeric data (MF=8, MT=457)
- ✅ **Proper B+/EC Split** - Correctly separates β+ and EC branching ratios
- ✅ **511 keV Detection** - Checks for annihilation photon peaks (with ±1 keV tolerance)
- ✅ **Clean Output** - Readable formatted tables with comprehensive information
- ✅ **Bug Fixed** - Includes corrected `Tabulated1D` interpolation (double-indexing fix)

## Requirements

```bash
pip install numpy
```

## Usage

### From File

```bash
python3 run_br74_parser.py your_endf_file.txt
```

### Using Embedded Example

```bash
python3 run_br74_parser.py
```

This will run the parser with embedded Br-74 example data.

## Example Output

```
==================================================================================================================================
ENDF-6 Radioactive Decay Data Parser (ENDF-102 Compliant)
==================================================================================================================================

Nuclide: Br-74 (Z=35, A=74)
Half-life: 1.5240e+03 seconds (25.40 minutes)
Q-value: 6907.0000 keV

Decay Mode Analysis:
  RTYP: 2.0 → EC/β+ decay
  Total Branching Ratio: 100.0000%
  β+ Branching: 91.1700%
  EC Branching: 8.8300%
  511 keV annihilation peak: Not detected in discrete list

Mean Radiation Energies:
  Alpha particles: 0.0000 keV
  Beta particles:  1052.5700 keV
  Gamma rays:      3423.3900 keV

==================================================================================================================================
DECAY MODES TABLE
==================================================================================================================================

A    Z     Parent    Decay Daughter         Q-value       Branching       Half-life        α Energy        β Energy        γ Energy
            Level     Mode    Level           (keV)       Ratio (%)       (seconds)           (keV)           (keV)           (keV)
----------------------------------------------------------------------------------------------------------------------------------
74   35         0       B+        0       6907.0000         91.1700      1.5240e+03          0.0000       1052.5700       3423.3900
74   35         0       EC        0       6907.0000          8.8300      1.5240e+03          0.0000       1052.5700       3423.3900
----------------------------------------------------------------------------------------------------------------------------------

Summary:
  • Br-74 undergoes EC/β+ decay with T½ = 25.40 minutes
  • β+ emission accounts for 91.17% of decays
  • Electron capture accounts for 8.83% of decays
==================================================================================================================================
```

## ENDF Data Format

The parser expects ENDF-6 format files containing:
- **MF=1, MT=451**: Text/descriptive section (automatically ignored)
- **MF=8, MT=457**: Radioactive decay numeric data (parsed)

## Key Features Explained

### B+/EC Splitting

For EC/β+ decay (RTYP=2.0), the parser:
1. Sums individual β+ transition intensities from discrete entries
2. Calculates EC branching as: `EC% = Total% - β+%`
3. Verifies with 511 keV annihilation photon detection (±1 keV tolerance)

### Bug Fix: Tabulated1D Interpolation

The original code had a double-indexing bug:
```python
# BUGGY (doesn't work):
y[inside][mask] = yi

# FIXED:
dest = np.flatnonzero(inside)
target_idx = dest[mask]
y[target_idx] = yi
```

## Files

- **`run_br74_parser.py`** - Main parser script
- **`br74_endf_test.txt`** - Example ENDF data file for Br-74
- **`ENDF_PARSER_README.md`** - This documentation

## References

- ENDF-102-2023: ENDF-6 Formats Manual - https://www.nndc.bnl.gov/endfdocs/ENDF-102-2023.pdf
- NuDat Database: https://www.nndc.bnl.gov/nudat3/
- JEFF-4.0 Radioactive Decay Data File

## Technical Details

### Supported Decay Modes (RTYP values)

- **0.0**: Gamma/IT (Isomeric Transition)
- **1.0**: β⁻ (Beta minus)
- **2.0**: EC/β+ (Electron Capture and/or Beta plus) ← **Currently implemented**
- **3.0**: IT (Isomeric Transition)
- **4.0**: α (Alpha)
- **5.0**: n (Neutron)
- **6.0**: SF (Spontaneous Fission)
- **7.0**: p (Proton)

### Radiation Types (STYP values)

- **0**: Gamma rays
- **1**: β⁻
- **2**: β+ / EC electrons
- **4**: α particles
- **5**: Neutrons
- **6**: Spontaneous fission fragments
- **7**: Protons
- **8**: X-rays
- **9**: Auger electrons

## License

This parser is provided as-is for scientific and educational purposes.

## Author

Created for ENDF-6 radioactive decay data analysis with ENDF-102 compliance.
