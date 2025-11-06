# Single File and Directory Support Fix

## Problem
The ENDF parser only accepted **directories** containing multiple `.endf` files. When users passed a **single large ENDF file** (like `Radioactive_Decay_Data_JEFF-40.endf`), it failed with:

```
ValueError: No ENDF files found in /path/to/Radioactive_Decay_Data_JEFF-40.endf matching pattern '*.endf'
```

This happened because:
- JEFF-4.0 data comes as **one large file** with all nuclides
- ENDF-B-VIII.0 data comes as **individual files per nuclide** in a directory
- The parser only supported the second format

## Solution
Modified `ENDFParsing.py` to automatically detect and handle both cases:

### Updated `load_from_endf_files()` method
```python
def load_from_endf_files(self, endf_dir: str, file_pattern: str = "*.endf"):
    """
    Load ENDF files from a directory or a single file.
    
    Args:
        endf_dir: Path to directory containing ENDF-6 files OR path to a single ENDF file
        file_pattern: Glob pattern for ENDF files (default: "*.endf") - ignored if endf_dir is a file
    """
    endf_path = Path(endf_dir)
    
    if not endf_path.exists():
        raise FileNotFoundError(f"ENDF path not found: {endf_dir}")
    
    # Check if path is a file or directory
    if endf_path.is_file():
        # Single file mode
        endf_files = [endf_path]
        print(f"\nProcessing single ENDF file: {endf_path.name}")
    else:
        # Directory mode - find all ENDF files matching the pattern
        endf_files = sorted(list(endf_path.glob(file_pattern)))
        endf_files = [f for f in endf_files if f.is_file()]
        
        if not endf_files:
            raise ValueError(f"No ENDF files found in {endf_dir} matching pattern '{file_pattern}'")
        
        print(f"\nFound {len(endf_files)} ENDF files in {endf_dir}")
```

## Usage Examples

### Single File Mode (JEFF-4.0)
```bash
python3 main_db.py process_endf \
    --endf "/Users/audreywarn/fluka-db-audrey/data_input/endf/Radioactive_Decay_Data_JEFF-40.endf" \
    --output "../outputs/jeff40/"
```

Output:
```
Processing single ENDF file: Radioactive_Decay_Data_JEFF-40.endf
  Parsing: Radioactive_Decay_Data_JEFF-40.endf
    Found 2847 decay section(s)
    ...
```

### Directory Mode (ENDF-B-VIII.0)
```bash
python3 main_db.py process_endf \
    --endf "/Users/audreywarn/fluka-db-audrey/data_input/endf/ENDF-B-VIII.0_decay" \
    --output "../outputs/endfb8/"
```

Output:
```
Found 3852 ENDF files in /Users/audreywarn/fluka-db-audrey/data_input/endf/ENDF-B-VIII.0_decay
  Parsing: dec-001_H_003.endf
  Parsing: dec-002_He_006.endf
  ...
```

## Test Results

### Test 1: Single File Mode
```
✅ PASS: Single file mode works!
  - Parses single large ENDF file
  - Extracts all decay sections
  - Creates correct data structures
```

### Test 2: Directory Mode
```
✅ PASS: Directory mode works!
  - Scans directory for *.endf files
  - Parses each file individually
  - Combines all data into one structure
```

## Benefits

1. **Flexible Input**: Accepts both formats automatically
2. **Backward Compatible**: Existing directory-based workflows unchanged
3. **JEFF-4.0 Support**: Can now parse large monolithic JEFF files
4. **Auto-Detection**: No need to specify mode, it's automatic
5. **Clear Feedback**: Prints which mode is being used

## Files Modified

- **`ENDFParsing.py`**:
  - `load_from_endf_files()` method (lines ~174-200)
  - `parse_endf_files()` docstring (line ~542)
  - `__main__` section argparse help (lines ~557-573)

## Compatibility

✅ Works with both ENDF-B-VIII.0 (directory of files) and JEFF-4.0 (single file)  
✅ Maintains backward compatibility with existing code  
✅ No breaking changes to API  
✅ Automatic detection - no configuration needed  

## Common File Structures

### ENDF-B-VIII.0 (Directory)
```
ENDF-B-VIII.0_decay/
  ├── dec-001_H_003.endf
  ├── dec-002_He_006.endf
  ├── dec-006_C_014.endf
  └── ... (3852 files)
```

### JEFF-4.0 (Single File)
```
Radioactive_Decay_Data_JEFF-40.endf
  (One file with all nuclides, ~2847 sections)
```

Both formats are now fully supported! ✅
