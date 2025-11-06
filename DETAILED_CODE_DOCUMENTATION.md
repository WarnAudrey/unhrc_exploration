# ENDF Parser - Detailed Code Documentation

## Overview

This document provides a comprehensive explanation of the ENDF parsing architecture, focusing on why **ENDFParsing.py** is a critical bridge between the low-level format parser and the database.

## New Documentation Files Created

### 1. **ENDFParsing_COMMENTED.py**
   - **850+ lines of detailed inline comments**
   - Explains EVERY section of the code
   - Documents the transformation pipeline
   - Shows why each transformation is necessary
   - **Location**: `/workspace/ENDFParsing_COMMENTED.py`

### 2. **JEFF_ENDF_parser_ARCHITECTURE.md**
   - **Comprehensive architecture guide**
   - Explains the separation of concerns
   - Documents ENDF-6 format challenges
   - Shows data flow with examples
   - Explains why the layered architecture is essential
   - **Location**: `/workspace/JEFF_ENDF_parser_ARCHITECTURE.md`

## Quick Summary

### The Two-Layer Architecture

```
┌──────────────────────────────────────────────────────────┐
│                     DATA PIPELINE                         │
├──────────────────────────────────────────────────────────┤
│                                                           │
│  ENDF Files (80-char fixed-width)                        │
│       │                                                   │
│       ▼                                                   │
│  ┌────────────────────────────┐                          │
│  │  JEFF_ENDF_parser.py       │ ◄── LOW-LEVEL           │
│  │  (Format Parser)           │                          │
│  └────────────────────────────┘                          │
│       │                                                   │
│       │ Output: Python dicts (raw ENDF structure)        │
│       ▼                                                   │
│  ┌────────────────────────────┐                          │
│  │  ENDFParsing.py            │ ◄── HIGH-LEVEL          │
│  │  (Database Adapter)        │                          │
│  └────────────────────────────┘                          │
│       │                                                   │
│       │ Output: pandas DataFrames (database schema)      │
│       ▼                                                   │
│  ┌────────────────────────────┐                          │
│  │  Database.py               │ ◄── STORAGE LAYER       │
│  │  (DataModule Storage)      │                          │
│  └────────────────────────────┘                          │
│                                                           │
└──────────────────────────────────────────────────────────┘
```

## Why ENDFParsing is Necessary

### The Core Problem: Impedance Mismatch

**ENDF data structure ≠ Database schema**

| What | ENDF Has | Database Needs | ENDFParsing Does |
|------|----------|----------------|------------------|
| **Decay Modes** | Numeric codes (RTYP=4.0) | ENSDF strings ("a") | Converts notation |
| **Energies** | Separate by spectrum type (STYP) | Attached to decay modes | Maps STYP → modes |
| **EC/B+ Data** | Single total branching | Separate EC and B+ entries | Splits using intensities |
| **Branching** | 0-1 range | 0-100% range | Converts units |
| **All Modes** | Everything (including trivial) | Only important modes | Filters modes |
| **Structure** | Nested dictionaries | Flat DataFrames | Flattens structure |

### Example: Alpha Decay of Am-241

#### ENDF File (Raw):
```
 9.524100+4 2.409852+2          0          0          6          395425 8457    1
 1.360360+10 0.000000+0          0          0          6          095425 8457    2
 5.000000-1 1.000000+0          1          0         18          395425 8457    3
 4.000000+0 0.000000+0 5.637000+6 3.000000+3 1.000000+0 0.000000+095425 8457    4
```

#### After JEFF_ENDF_parser (Low-Level):
```python
{
    "ZA": 95241,              # Am-241
    "T1/2": (1.36e10, 0),     # Half-life in seconds
    "modes": [
        {
            "RTYP": 4.0,      # Numeric code for alpha
            "BR": (1.0, 0)    # 100% branching (0-1 scale)
        }
    ],
    "spectra": [
        {
            "STYP": 4,        # Alpha particle spectrum
            "ER_AV": (5.486e6, 0)  # Mean energy separate from mode
        }
    ]
}
```
**Problem**: This doesn't match database schema!

#### After ENDFParsing (High-Level):
```python
DECAY DataFrame:
┌─────┬────┬─────────────┬────────────┬─────────────┬─────────┬─────────────────┬────────────────┬───────────┐
│  A  │ Z  │ parentLevel │ decay_mode │ final_level │ Parent  │ Endpoint_energy │ Average_energy │ Intensity │
├─────┼────┼─────────────┼────────────┼─────────────┼─────────┼─────────────────┼────────────────┼───────────┤
│ 241 │ 95 │    0.0      │     a      │     0.0     │ Am-241  │    5486000      │    5486000     │   100.0   │
└─────┴────┴─────────────┴────────────┴─────────────┴─────────┴─────────────────┴────────────────┴───────────┘

NUCLIDE DataFrame:
┌─────┬────┬───────┬─────────┬────────────┬─────────┐
│  A  │ Z  │ level │ Nuclide │ Half_life  │ hl_unit │
├─────┼────┼───────┼─────────┼────────────┼─────────┤
│ 241 │ 95 │  0.0  │ Am-241  │ 1.36036e10 │    s    │
└─────┴────┴───────┴─────────┴────────────┴─────────┘
```
**Success**: Matches database schema perfectly!

## Key Transformations in ENDFParsing

### 1. Energy Mapping (STYP → Decay Mode)

**Why needed**: ENDF stores energies in spectrum records (STYP), but database needs them attached to decay modes.

```python
# ENDF has:
"spectra": [{"STYP": 4, "ER_AV": 5486000}]  # STYP=4 is alpha
"modes": [{"RTYP": 4.0}]                     # RTYP=4 is alpha

# ENDFParsing maps them:
if styp == 4:  # Alpha spectrum
    for mode_str in self.decay_modes:
        if mode_str.startswith('a'):  # Alpha mode
            self.average_energies[mode_str] = 5486000
```

### 2. EC/B+ Splitting

**Why needed**: ENDF gives total EC/B+ branching, but database needs separate entries.

```python
# ENDF has:
mode = "EC/B+", total_branching = 100%
beta_plus_intensity = 91.17%  # From spectrum

# ENDFParsing splits:
bplus_br = 91.17
ec_br = 100.0 - 91.17 = 8.83

# Creates two database rows:
Row 1: decay_mode="B+", Intensity=91.17
Row 2: decay_mode="EC", Intensity=8.83
```

### 3. Notation Conversion

**Why needed**: ENDF uses numeric codes, database uses ENSDF strings.

```python
# ENDF has:
RTYP = 4.0      # Alpha
RTYP = 1.0      # Beta-
RTYP = 1.5      # Beta- + neutron

# ENDFParsing converts:
4.0  → "a"      # Lowercase per ENSDF
1.0  → "B-"
1.5  → "B-n"    # No comma per ENSDF
```

### 4. Mode Filtering

**Why needed**: ENDF includes all modes, database wants only "important" ones.

```python
# ENDF has:
modes = ["B-", "n", "p", "SF", "IT"]

# ENDFParsing filters:
important_modes = ["B-"]  # Only decay modes, not reactions
```

## Handling All Spectrum Types (STYP)

ENDFParsing correctly handles **ALL 6 spectrum types**:

| STYP | Type | Fields Extracted | Mapped To |
|------|------|------------------|-----------|
| **0** | Gamma rays | ER (energy), RI (intensity), ICC (conversion) | `gamma` key |
| **1** | Beta- | E_AVG (mean), IB (intensity), ER (endpoint) | `B-` mode |
| **2** | Beta+ | ER (endpoint), IB (intensity) | `B+` or `EC/B+` mode |
| **4** | Alpha | ER (energy), RP (intensity), ER_AV (mean) | `a` mode |
| **8** | X-rays | ER (energy), RI (intensity) | `x-ray` key |
| **9** | Auger e- | ER (energy), RI (intensity) | `auger` key |

**Critical**: Each STYP has different ENDF fields, and ENDFParsing maps them correctly to the appropriate decay modes.

## Code Documentation Features

### In ENDFParsing_COMMENTED.py

1. **Module-Level Documentation** (200+ lines)
   - Complete architecture diagram
   - Data flow explanation
   - Why the module exists
   - What it does vs. doesn't do

2. **Class-Level Documentation**
   - `DecayData`: ENDF dict → Python object
   - `ENDFDataModule`: Main database adapter

3. **Method-Level Documentation**
   - Every method has purpose explanation
   - Input/output documented
   - Transformation logic explained

4. **Inline Comments**
   - Every significant block explained
   - Edge cases documented
   - Business logic justified

5. **Examples Throughout**
   - Real data examples (Am-241, H-3, etc.)
   - Before/after transformations
   - Expected outputs

### In JEFF_ENDF_parser_ARCHITECTURE.md

1. **Format Background**
   - ENDF-6 fixed-width format
   - E-less notation
   - Multi-record structure

2. **Parsing Methods**
   - Complete method hierarchy
   - What each method does
   - Why it's structured that way

3. **STYP-Specific Parsing**
   - All 6 spectrum types documented
   - Field differences explained
   - Code examples for each

4. **Data Flow Examples**
   - Complete pipeline walkthrough
   - Real file → dict → DataFrame → database
   - Transformations at each step

5. **Architecture Justification**
   - Why two layers?
   - Benefits of separation
   - Alternative approaches (and why they're worse)

## Using the Documentation

### For Understanding the Code

1. **Start with**: `JEFF_ENDF_parser_ARCHITECTURE.md`
   - Read "Purpose and Role"
   - Read "Why Keep This Separate"
   - Understand the pipeline

2. **Then read**: `ENDFParsing_COMMENTED.py`
   - Read module docstring (architecture diagram)
   - Read `DecayData.__init__` (energy mapping)
   - Read `_parse_to_dataframes` (DataFrame creation)

3. **For specific questions**:
   - "How is beta- energy extracted?" → Search "STYP=1" in both files
   - "How is EC/B+ split?" → Search "EC/B+ SPLITTING"
   - "Why this architecture?" → Read ARCHITECTURE.md conclusion

### For Debugging

1. **Format parsing issues** → Check `JEFF_ENDF_parser.py`
   - Fixed-width parsing
   - E-less notation
   - Record structure

2. **Energy not appearing** → Check `ENDFParsing.py`
   - STYP mapping (lines ~89-143 in COMMENTED version)
   - Mode string matching
   - Energy field extraction

3. **Wrong database values** → Check `ENDFParsing.py`
   - `_parse_to_dataframes` method
   - Unit conversions
   - Notation conversions

### For Extending the Code

1. **Adding new spectrum type**:
   - Add STYP case in `JEFF_ENDF_parser._parse_discrete_transitions`
   - Add STYP case in `ENDFParsing.DecayData.__init__`
   - Update documentation

2. **Adding new decay mode**:
   - Update `_decode_rtyp` in `ENDFParsing.py`
   - Update `_is_important_decay_mode` if needed
   - No changes to JEFF_ENDF_parser needed!

3. **Changing database schema**:
   - Update `_parse_to_dataframes` in `ENDFParsing.py`
   - No changes to JEFF_ENDF_parser needed!

## Summary Table

| File | Purpose | Lines | Key Content |
|------|---------|-------|-------------|
| `ENDFParsing_COMMENTED.py` | Heavily commented source | ~850 | Complete inline documentation |
| `JEFF_ENDF_parser_ARCHITECTURE.md` | Architecture guide | ~700 | Design rationale, examples |
| `ENDFParsing.py` (original) | Production code | ~596 | Clean implementation |
| `JEFF_ENDF_parser.py` (original) | Low-level parser | ~1758 | Format parsing |

## Key Takeaways

1. **Two-layer architecture is essential**
   - Low-level: Format parsing (JEFF_ENDF_parser)
   - High-level: Business logic (ENDFParsing)

2. **ENDFParsing is the critical bridge**
   - Without it, database can't understand ENDF data
   - Handles ALL schema transformations
   - Enables source-agnostic database

3. **Clean separation of concerns**
   - Format changes → update JEFF_ENDF_parser
   - Schema changes → update ENDFParsing
   - Never mix the two

4. **Complete energy extraction**
   - All 6 STYP types handled
   - Average and endpoint energies
   - Correct mapping to decay modes

5. **Proper EC/B+ handling**
   - Splits based on β+ intensities
   - Creates separate database entries
   - Preserves total branching ratio

---

**For questions or clarifications, refer to the specific sections in the commented files!**
