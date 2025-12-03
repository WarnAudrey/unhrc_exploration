# Code Update Summary: math.isclose() Convention

## Overview

The ENDF-ENSDF level matcher code has been updated to follow the same relative tolerance logic as the reference ENSDF parser code, which uses Python's `math.isclose()` convention.

## Changes Made

### 1. Updated Tolerance Calculation

**File**: `/workspace/endf_ensdf_matcher_commented.py`

**Location**: `_find_matching_transition()` method, lines ~920-940

**RELATIVE Strategy** - Changed from:
```python
# OLD (incorrect - only uses one energy)
tolerance = max(ensdf_daughter_level_energy * self.relative_tol, 1e3)
```

To:
```python
# NEW (correct - follows math.isclose convention)
max_energy = max(abs(ensdf_daughter_level_energy), abs(endf_daughter_level_energy))
tolerance = max(self.relative_tol * max_energy, self.absolute_tol)
```

**HYBRID Strategy** (high-energy mode) - Changed from:
```python
# OLD (incorrect - only uses one energy)
tolerance = ensdf_daughter_level_energy * self.relative_tol
```

To:
```python
# NEW (correct - follows math.isclose convention)
max_energy = max(abs(ensdf_daughter_level_energy), abs(endf_daughter_level_energy))
tolerance = max(self.relative_tol * max_energy, self.absolute_tol)
```

### 2. Added Import

Added `import math` to imports section (line 91) for reference and potential future use.

### 3. Updated Documentation

**Main docstring** (lines 73-80):
- Clarified that relative tolerance follows math.isclose() convention
- Added mathematical formula
- Updated examples

**set_tolerances() docstring** (lines 717-719):
- Added explanation of math.isclose() convention
- Clarified that comparison is symmetric

**Inline comments** (lines 922-924, 934-936):
- Added comments explaining the math.isclose() logic
- Documented the formula being used

## Why This Matters

### Reference Code Pattern

The ENSDF parser code uses:
```python
if not math.isclose(self.lvl_energy, self.sn, rel_tol=1.0e-3):
    return
```

This uses Python's standard `math.isclose()` which implements:
```
abs(a - b) <= rel_tol * max(abs(a), abs(b)) + abs_tol
```

### Advantages of math.isclose() Convention

1. **Symmetry**: `isclose(a, b) == isclose(b, a)` always
2. **Robustness**: Handles edge cases correctly:
   - Near-zero values
   - Large magnitude differences
   - One value being zero
3. **Standard Practice**: Follows Python conventions
4. **Maintainability**: Familiar to Python developers

### Example Comparison

For two energies at 2.43 MeV and 2.425 MeV (5 keV difference) with rel_tol=0.001:

**OLD approach (asymmetric)**:
- If comparing A to B: tolerance = 2.43 MeV × 0.001 = 2.43 keV
- If comparing B to A: tolerance = 2.425 MeV × 0.001 = 2.425 keV
- **Different results depending on order!**

**NEW approach (symmetric - math.isclose)**:
- Either direction: tolerance = max(2.43, 2.425) MeV × 0.001 = 2.43 keV
- **Same result regardless of order** ✓

## Testing

### Verification Script

A test script (`test_tolerance_logic.py`) was created to verify:
1. NEW logic matches `math.isclose()` exactly
2. Behavior is correct for edge cases
3. Comparison is symmetric

Run with:
```bash
python3 /workspace/test_tolerance_logic.py
```

### Test Results

✅ All test cases confirm: **NEW logic === math.isclose()**

Test scenarios verified:
- Similar high energies (2+ MeV)
- Medium energies (~100 keV)
- Low energies (~1 keV)
- Very low energies (<1 keV)
- Large relative differences
- Zero vs non-zero comparisons

## Impact on Matching Results

### Expected Changes

With the updated logic:
- **Match rate**: Should remain similar or slightly improve
- **Symmetry**: Matching is now order-independent
- **Edge cases**: Better handling of near-zero energies
- **Consistency**: Aligns with reference ENSDF parser

### Practical Impact

For most cases (similar energy values), the difference is minimal. The update is most important for:
1. **Consistency** with reference code
2. **Correctness** in edge cases
3. **Code maintainability** (standard conventions)

## Files Modified

1. **Main code**: `/workspace/endf_ensdf_matcher_commented.py`
   - Updated tolerance calculation (2 locations)
   - Added import statement
   - Updated docstrings and comments

2. **Documentation**: 
   - `/workspace/TOLERANCE_LOGIC_EXPLANATION.md` - Detailed explanation
   - `/workspace/UPDATE_SUMMARY.md` - This file
   
3. **Testing**:
   - `/workspace/test_tolerance_logic.py` - Verification script

## Compatibility

- **Backward compatible**: Default parameters unchanged
- **API unchanged**: No changes to function signatures
- **Output format**: Identical file formats
- **Configuration**: All existing configuration options still work

## Recommendations

1. **Re-run matching** with default parameters to verify results
2. **Compare statistics** (match rates, quality distribution)
3. **Spot-check** a few transitions to ensure sensible matches
4. **Use test script** to understand behavior for specific cases

## Default Configuration

The code still uses the same defaults:
- **absolute_tol**: 1 keV (1000 eV)
- **relative_tol**: 0.1% (0.001)
- **strategy**: HYBRID
- **hybrid_threshold**: 500 keV

These values now work correctly following math.isclose() convention.

## Questions?

The update ensures your code follows the same tolerance logic as the reference ENSDF parser. The key change is using `max(|a|, |b|)` instead of just `|a|` for relative tolerance calculations, making the comparison symmetric and more robust.
