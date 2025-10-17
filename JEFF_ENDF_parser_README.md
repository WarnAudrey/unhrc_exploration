# JEFF ENDF Radioactive Decay Data Parser

A comprehensive Python parser for ENDF-6 format radioactive decay data files (MF=8, MT=457), fully compliant with ENDF-102 (2023 revision).

## Features

- **Complete Data Extraction**: Captures ALL fields from ENDF-102 Section 8.1
- **Multiple Output Modes**: Compact summary tables or detailed verbose output
- **All Energy Information**: Discrete transitions, continuous spectra, mean energies
- **Comprehensive Metadata**: Half-lives, Q-values, branching ratios, uncertainties
- **Radiation Spectra**: Gamma, beta+, alpha, X-ray, and Auger electron data
- **Field Verification**: 100% ENDF-102 compliant with explicit field names

## Requirements

- Python 3.6 or higher
- NumPy 1.20.0 or higher

## Installation

1. Clone this repository:
```bash
git clone <your-repo-url>
cd <your-repo-name>
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Basic Usage

Parse an ENDF file and generate output:
```bash
python JEFF_ENDF_parser.py <input_file>
```

### Output Options

**Compact Mode** (summary table only):
```bash
python JEFF_ENDF_parser.py --compact <input_file>
```

**Verbose Mode** (detailed data for all nuclides):
```bash
python JEFF_ENDF_parser.py --verbose <input_file>
```

**Custom Output File**:
```bash
python JEFF_ENDF_parser.py -o output.txt <input_file>
```

### Examples

```bash
# Parse JEFF-4.0 decay data with compact output
python JEFF_ENDF_parser.py --compact Radioactive_Decay_Data_JEFF-40.txt

# Generate detailed output to custom file
python JEFF_ENDF_parser.py --verbose -o detailed_output.txt decay_data.txt

# Default output (creates endf_decay_summary.txt)
python JEFF_ENDF_parser.py decay_data.endf
```

## Output Formats

### Compact Mode
Generates a summary table with essential columns:
- Z, A, Element, Isomeric Level, Nuclide Name
- Half-life, Q-value
- Beta+ Branch, EC Branch
- Mean alpha, beta, gamma energies
- MAT number

### Verbose Mode
Includes all compact information PLUS:
- Individual discrete transition energies (all types)
- Continuous spectrum distributions
- Internal conversion coefficients
- Sorted energy distribution summaries
- Complete uncertainties for all values
- Raw ENDF record metadata

## Data Files

This parser works with:
- **JEFF-4.0** radioactive decay data
- **ENDF/B-VIII.0** decay files
- Any ENDF-6 format file with MF=8, MT=457 sections

Download decay data files from:
- JEFF: https://www.oecd-nea.org/dbdata/jeff/
- ENDF: https://www.nndc.bnl.gov/endf/

## ENDF-102 Compliance

This parser extracts **100% of fields** specified in ENDF-102 Section 8.1:

| Field Category | Coverage |
|----------------|----------|
| Header (ZA, AWR, LIS, LISO, NST, NSP) | 6/6 |
| Half-life data | Complete |
| Decay modes | Complete |
| Gamma spectra | Complete (including M+ shell ICC) |
| Beta+ spectra | Complete (including average energy) |
| Alpha spectra | Complete (including hindrance factors) |
| X-ray spectra | Complete |
| Auger spectra | Complete |
| Continuous spectra | Complete |
| Covariance matrices | Complete |

## Documentation

For detailed information about the ENDF-6 format:
- **ENDF-102 Manual**: https://www.nndc.bnl.gov/endfdocs/ENDF-102-2023.pdf
- **Section 8.1**: Radioactive Decay Data (MF=8, MT=457)

## Code Structure

```
JEFF_ENDF_parser.py
├── Tabulated1D        - ENDF TAB1 record handler
├── Tabulated2D        - ENDF TAB2 record handler
├── ENDFNumericDecayParser
│   ├── Record parsers (_get_cont, _get_list, _get_tab1, etc.)
│   └── _parse_mf8_mt457 - Main decay data parser
├── Output functions
│   ├── format_and_print_combined_table
│   ├── print_compact_summary_table
│   ├── print_all_energies
│   └── print_detailed_data
└── Main execution block
```

## Troubleshooting

**Error: `ModuleNotFoundError: No module named 'numpy'`**
```bash
pip install numpy
```

**Error: `FileNotFoundError`**
- Check that the input file path is correct
- Use absolute paths if running from a different directory

**Error: `ValueError: min() iterable argument is empty`**
- This has been fixed in the latest version
- Ensure you're using the most recent code

## License

[Add your license here]

## Author

[Add your name/contact here]

## References

Based on ENDF-6 format specification:
- ENDF-102 Data Formats and Procedures for the Evaluated Nuclear Data Files ENDF/B-VI and ENDF/B-VII (2023 revision)
- NNDC: https://www.nndc.bnl.gov/
