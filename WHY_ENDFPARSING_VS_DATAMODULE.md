# Why ENDFParsing When DataModule Exists?

## The Critical Distinction

**ENDFParsing** and **DataModule** serve **completely different roles** in the architecture:

| Aspect | ENDFParsing | DataModule |
|--------|-------------|------------|
| **Role** | Format-specific parser | Generic data container |
| **Input** | Raw ENDF files | pandas DataFrames |
| **Output** | pandas DataFrames | Structured storage |
| **Knowledge** | ENDF-6 format details | Database schema |
| **Responsibility** | Parse & transform ENDF | Store & manage data |
| **Reusability** | ENDF files only | ANY data source |

## The Complete Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                    MULTI-SOURCE DATABASE ARCHITECTURE                   │
├────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  DATA SOURCES (Different Formats)                                      │
│  ├─ ENDF-6 files (80-char fixed-width)                                │
│  ├─ JSON files (structured JSON)                                       │
│  ├─ ENSDF files (ENSDF format)                                         │
│  └─ Legacy Fortran binary (nuclear.bin)                                │
│           │                                                             │
│           ↓                                                             │
│  ┌──────────────────────────────────────────────────┐                 │
│  │   FORMAT-SPECIFIC PARSERS (Layer 1)              │                 │
│  ├──────────────────────────────────────────────────┤                 │
│  │ • ENDFParsing.py          (ENDF files)          │                 │
│  │ • JSONParsing.py          (JSON files)          │                 │
│  │ • ENSDFParsing.py         (ENSDF files)         │                 │
│  │ • Legacy.py               (Fortran binary)       │                 │
│  └──────────────────────────────────────────────────┘                 │
│           │                                                             │
│           │ All output: pandas DataFrames                              │
│           │             with consistent schema                         │
│           ↓                                                             │
│  ┌──────────────────────────────────────────────────┐                 │
│  │   DATAMODULE (Layer 2)                           │                 │
│  ├──────────────────────────────────────────────────┤                 │
│  │ • Generic data container                         │                 │
│  │ • Schema validation                              │                 │
│  │ • Data storage & retrieval                       │                 │
│  │ • Export (ASCII, binary, etc.)                   │                 │
│  └──────────────────────────────────────────────────┘                 │
│           │                                                             │
│           ↓                                                             │
│  ┌──────────────────────────────────────────────────┐                 │
│  │   DATABASE (Layer 3)                             │                 │
│  ├──────────────────────────────────────────────────┤                 │
│  │ • Collection of DataModules                      │                 │
│  │ • Cross-module queries                           │                 │
│  │ • Database-level operations                      │                 │
│  └──────────────────────────────────────────────────┘                 │
│                                                                         │
└────────────────────────────────────────────────────────────────────────┘
```

## Why ENDFParsing is Necessary

### 1. **DataModule is Format-Agnostic**

DataModule has **NO KNOWLEDGE** of ENDF file format:

```python
# What DataModule CANNOT do:
❌ Read 80-character fixed-width lines
❌ Parse ENDF-6 HEAD/LIST/TAB1 records
❌ Decode E-less notation (1.234+5)
❌ Map STYP spectrum types to decay modes
❌ Split EC/B+ based on β+ intensities
❌ Convert RTYP codes to ENSDF notation

# What DataModule CAN do:
✅ Store DataFrames with specific schema
✅ Validate column types and indices
✅ Export to various formats
✅ Query and retrieve data
```

### 2. **DataModule is a Container, Not a Parser**

Look at DataModule's population methods:

```python
class DataModule:
    
    def populate_DM_from_endf_data(self, endf_data):
        """
        INPUT: endf_data = ENDFDataModule instance
               Already has .decay_df and .nuclides_df DataFrames!
        
        This method just:
        1. Extracts rows from pre-built DataFrames
        2. Maps columns to schema
        3. Stores in self.C
        
        It does NOT parse ENDF files!
        """
        for idx, row in endf_data.decay_df.iterrows():
            # Copy fields from DataFrame
            temp['Endpoint_energy'] = row['Endpoint_energy']
            temp['Average_energy'] = row['Average_energy']
            # ... etc
    
    def populate_DM_from_nuclear_data(self, nuclear_data):
        """
        INPUT: nuclear_data = NuclearDataModule instance
               Already has .levels_df, .gamma_df, .decay_df DataFrames!
        
        Same pattern: expects DataFrames as input
        """
    
    def populate_DM_from_legacy(self, lgcy):
        """
        INPUT: lgcy = Legacy instance
               Already parsed Fortran binary!
        
        Same pattern: expects parsed data structure
        """
```

**Key insight**: DataModule's `populate_DM_from_*` methods all expect **already-parsed data structures**. They don't parse raw files!

### 3. **The Parser → DataModule Flow**

For **ENDF files**:

```python
# Step 1: Parse ENDF files (ENDFParsing does this)
from PyClasses.ENDFParsing import parse_endf_files

endf_module = parse_endf_files("/path/to/endf/files")
# Now endf_module has:
#   .decay_df (DataFrame with ENDF decay data)
#   .nuclides_df (DataFrame with ENDF nuclide data)

# Step 2: Load into DataModule (DataModule does this)
decay_dm = DataModule('DECAY', db_config)
decay_dm.populate_DM_from_endf_data(endf_module)
# Now decay_dm.C has the data in database schema
```

For **JSON files**:

```python
# Step 1: Parse JSON files (JSONParsing does this)
from PyClasses.JSONParsing import NuclearDataModule

json_module = NuclearDataModule()
json_module.load_from_json_dir("/path/to/json/files")
# Now json_module has:
#   .levels_df, .gamma_df, .decay_df, .nuclides_df

# Step 2: Load into DataModule (DataModule does this)
decay_dm = DataModule('DECAY', db_config)
decay_dm.populate_DM_from_nuclear_data(json_module)
# Now decay_dm.C has the data in database schema
```

**Pattern**: Parser → intermediate DataFrames → DataModule

## What Each Layer Does

### Layer 1: Format-Specific Parsers

**ENDFParsing.py** (for ENDF files):
```python
Responsibilities:
├─ Read ENDF-6 fixed-width files
├─ Use JEFF_ENDF_parser for low-level parsing
├─ Map STYP energies to decay modes
├─ Split EC/B+ using β+ intensities
├─ Convert RTYP codes to ENSDF notation
├─ Filter important decay modes
└─ Output: pandas DataFrames matching database schema

Output DataFrames:
├─ decay_df: (A, Z, parentLevel, decay_mode, final_level) → 
│            [Endpoint_energy, Average_energy, Intensity]
└─ nuclides_df: (A, Z, level) → 
                [Half_life, hl_unit, ...]
```

**JSONParsing.py** (for JSON files):
```python
Responsibilities:
├─ Read JSON files
├─ Parse JSON structure
├─ Extract level, transition, decay data
├─ Convert units (keV, s, etc.)
├─ Handle fake levels (negative energies)
└─ Output: pandas DataFrames matching database schema

Output DataFrames:
├─ levels_df: (A, Z, level) → [energy, spin, parity, halfLife, ...]
├─ gamma_df: (A, Z, initialLevel, finalLevel) → [energy, intensity, ...]
├─ decay_df: (A, Z, parentLevel, decay_mode, final_level) → [...]
└─ nuclides_df: (A, Z) → [neutron_sep, proton_sep, ...]
```

**Legacy.py** (for Fortran binary):
```python
Responsibilities:
├─ Read Fortran unformatted binary (nuclear.bin)
├─ Parse fixed-length records
├─ Decode compact storage formats
├─ Handle triangular arrays
└─ Output: Python dicts/arrays for DataModule

Output: Direct access to binary data via lgcy.contents
```

### Layer 2: DataModule (Generic Container)

```python
Responsibilities:
├─ Define database schema (via db_config)
├─ Receive DataFrames from parsers
├─ Validate schema compliance
├─ Store data in self.C (pandas DataFrame)
├─ Provide query methods
├─ Export to ASCII/binary formats
└─ Source-agnostic (works with ANY parser)

Key Methods:
├─ populate_DM_from_endf_data(endf_module)
├─ populate_DM_from_nuclear_data(json_module)
├─ populate_DM_from_legacy(legacy_module)
├─ print_to_ascii(filename)
├─ filter(field, function)
└─ retrieve(column, value)
```

## Why Not Merge Them?

### ❌ Bad Idea: Put ENDF Parsing in DataModule

```python
class DataModule:
    def populate_DM_from_endf_files(self, endf_dir):
        # Now DataModule needs to know:
        # - ENDF-6 fixed-width format
        # - E-less notation
        # - STYP codes
        # - EC/B+ splitting logic
        # - ENSDF notation rules
        # ... BAD! Mixed concerns!
```

**Problems**:
1. **Violates Single Responsibility Principle**
2. **Makes DataModule format-specific** (can't easily add new sources)
3. **Hard to test** (parsing logic mixed with storage logic)
4. **Hard to maintain** (ENDF changes affect DataModule)
5. **Can't reuse ENDF parser** for other applications

### ✅ Good Design: Separate Layers

```python
# Layer 1: Format expert
class ENDFDataModule:
    """Knows: ENDF format
       Doesn't know: Database schema details"""
    def load_from_endf_files(self, dir):
        # Parse ENDF files
        # Return DataFrames
    
# Layer 2: Storage expert  
class DataModule:
    """Knows: Database schema
       Doesn't know: File formats"""
    def populate_DM_from_endf_data(self, endf_module):
        # Take DataFrames
        # Store with validation
```

**Benefits**:
1. **Clear separation of concerns**
2. **Easy to add new data sources** (just write new parser)
3. **Easy to test** (test parser separately from storage)
4. **Easy to maintain** (format changes isolated)
5. **Parsers are reusable** (use ENDFParsing elsewhere)

## Real-World Analogy

Think of a **multi-language document database**:

```
Documents (Raw Files)
├─ English documents (.txt)
├─ French documents (.txt)
├─ Japanese documents (.txt)
└─ Binary documents (.bin)
        ↓
Translators (Format Parsers)
├─ English translator → Universal format
├─ French translator → Universal format
├─ Japanese translator → Universal format
└─ Binary decoder → Universal format
        ↓
Filing Cabinet (DataModule)
└─ Stores all documents in universal format
   (doesn't know original languages)
```

- **ENDFParsing** = English translator (ENDF-specific)
- **JSONParsing** = French translator (JSON-specific)
- **Legacy** = Binary decoder (Fortran-specific)
- **DataModule** = Filing cabinet (universal storage)

You need translators BEFORE you can file documents!

## Code Example: The Full Flow

```python
# ============================================================
# SCENARIO: Load ENDF-B-VIII.0 data into database
# ============================================================

# Step 1: Parse ENDF files (ENDFParsing)
# -----------------------------------------------
from PyClasses.ENDFParsing import parse_endf_files

endf_path = "/data/ENDF-B-VIII.0_decay/"
endf_module = parse_endf_files(endf_path, file_pattern="*.endf")

# What happened:
# - JEFF_ENDF_parser read 80-char lines
# - Parsed MF=8 MT=457 sections
# - Extracted RTYP, STYP, energies, branchings
# - Mapped STYP → decay modes
# - Split EC/B+
# - Converted to ENSDF notation
# - Built DataFrames

print(type(endf_module.decay_df))  # pandas.DataFrame
print(endf_module.decay_df.columns)
# ['Parent', 'Endpoint_energy', 'Average_energy', 'Intensity']

# Step 2: Create DataModule (Generic Container)
# -----------------------------------------------
from PyClasses.DataModule import DataModule
from PyClasses.DBConfig import DBConfig

db_config = DBConfig("config_dmf5.json")
decay_dm = DataModule('DECAY', db_config)

# What happened:
# - Read schema from config
# - Created empty DataFrame with proper columns/types
# - Ready to receive data

# Step 3: Populate DataModule (Storage)
# -----------------------------------------------
decay_dm.populate_DM_from_endf_data(endf_module)

# What happened:
# - Iterated over endf_module.decay_df rows
# - Mapped columns to schema
# - Validated types
# - Stored in decay_dm.C

print(type(decay_dm.C))  # pandas.DataFrame
print(len(decay_dm.C))   # Number of decay channels

# Step 4: Use DataModule (Query/Export)
# -----------------------------------------------
# Query
am241_decays = decay_dm.C.loc[(241, 95)]  # All Am-241 decays

# Export
decay_dm.print_to_ascii("DECAY.ascii")

# ============================================================
# KEY INSIGHT: DataModule never saw ENDF files!
# It only saw pre-built DataFrames from ENDFParsing.
# ============================================================
```

## Summary

**ENDFParsing is necessary because**:

1. **DataModule is format-agnostic** - it doesn't know how to parse ENDF files
2. **DataModule expects DataFrames** - not raw files
3. **ENDFParsing is the translator** - from ENDF format to database schema
4. **Separation of concerns** - parsing vs. storage are different responsibilities
5. **Extensibility** - easy to add new data sources without modifying DataModule
6. **Reusability** - ENDFParsing can be used for non-database applications
7. **Testability** - can test parsing logic separately from storage logic

**The architecture is**:

```
Raw Files → Format Parser → DataFrames → DataModule → Database
```

**Not**:

```
Raw Files → DataModule (doing everything) → Database  ❌
```

This is a **textbook example** of the **Adapter Pattern** and **Separation of Concerns** in software design!
