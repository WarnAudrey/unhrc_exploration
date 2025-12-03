# Tolerance Logic Update - Following math.isclose() Convention

## Summary

The code has been updated to follow the same relative tolerance logic as the reference ENSDF parser code, which uses Python's `math.isclose()` convention.

## Key Change

### Previous Implementation (INCORRECT)
```python
# Only used one energy value for relative tolerance
tolerance = ensdf_daughter_level_energy * self.relative_tol
```

### New Implementation (CORRECT - Following math.isclose())
```python
# Uses maximum of both energy values (symmetric comparison)
max_energy = max(abs(ensdf_daughter_level_energy), abs(endf_daughter_level_energy))
tolerance = max(self.relative_tol * max_energy, self.absolute_tol)
```

## Rationale

Python's `math.isclose(a, b, rel_tol=r)` uses the formula:
```
abs(a - b) <= rel_tol * max(abs(a), abs(b))
```

This ensures:
1. **Symmetry**: `isclose(a, b) == isclose(b, a)`
2. **Robustness**: Works correctly when one value is near zero
3. **Consistency**: Matches standard Python conventions

## Reference Code

The ENSDF parser uses this exact logic:
```python
if not math.isclose(self.lvl_energy, self.sn, rel_tol=1.0e-3):
    return
```

## Implementation Details

The update affects two strategies in `_find_matching_transition()`:

### 1. RELATIVE Strategy
```python
elif self.strategy == MatchStrategy.RELATIVE:
    # Pure relative tolerance (percentage of level energy)
    # Following math.isclose() logic: rel_tol * max(|a|, |b|)
    max_energy = max(abs(ensdf_daughter_level_energy), abs(endf_daughter_level_energy))
    tolerance = max(self.relative_tol * max_energy, self.absolute_tol)
    strategy_used = "relative"
```

### 2. HYBRID Strategy (Relative Mode)
```python
elif self.strategy == MatchStrategy.HYBRID:
    if ensdf_daughter_level_energy < self.hybrid_threshold:
        tolerance = self.absolute_tol
        strategy_used = "hybrid(abs)"
    else:
        # Following math.isclose() logic: rel_tol * max(|a|, |b|)
        max_energy = max(abs(ensdf_daughter_level_energy), abs(endf_daughter_level_energy))
        tolerance = max(self.relative_tol * max_energy, self.absolute_tol)
        strategy_used = "hybrid(rel)"
```

## Default Parameters

- **absolute_tol**: 1 keV (1000 eV)
- **relative_tol**: 0.1% (0.001)
- **strategy**: HYBRID
- **hybrid_threshold**: 500 keV (500,000 eV)

## Example

For matching energies:
- ENSDF level energy: 2,430,000 eV (2.43 MeV)
- ENDF calculated energy: 2,425,000 eV (2.425 MeV)
- Difference: 5,000 eV (5 keV)

**With relative tolerance = 0.001 (0.1%):**

Old formula (incorrect):
```
tolerance = 2,430,000 * 0.001 = 2,430 eV
5,000 eV > 2,430 eV → NO MATCH ✗
```

New formula (correct - math.isclose):
```
max_energy = max(2,430,000, 2,425,000) = 2,430,000 eV
tolerance = 0.001 * 2,430,000 = 2,430 eV
tolerance = max(2,430 eV, 1,000 eV) = 2,430 eV
5,000 eV > 2,430 eV → NO MATCH ✗
```

In this case, both give the same result because both energies are similar. However, the new formula is more robust for edge cases where energies differ significantly or when one is near zero.

## Benefits

1. **Consistency**: Matches Python standard library conventions
2. **Symmetry**: Same result regardless of which value is "reference"
3. **Robustness**: Handles edge cases better (near-zero energies, large differences)
4. **Maintainability**: Easier to understand for Python developers familiar with `math.isclose()`

## Files Modified

- `/workspace/endf_ensdf_matcher_commented.py`
  - Added `import math` 
  - Updated relative tolerance calculation in `RELATIVE` strategy
  - Updated relative tolerance calculation in `HYBRID` strategy (high-energy mode)
  - Updated docstrings to document math.isclose() convention
  - Added comments explaining the logic inline

## Testing Recommendation

Run matching with default parameters and compare results to ensure:
1. Match rates are similar or improved
2. Energy differences for matched transitions are within expected ranges
3. No regressions in quality metrics (exact/good/acceptable/marginal counts)
