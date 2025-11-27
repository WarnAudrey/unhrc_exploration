# Parent Level Matching - What's Expected?

## Key Question: Why are all `parentLevel` values still 0?

### Short Answer: **This is likely CORRECT!**

## The Physics:

Most radioactive decays occur from **ground states** (parentLevel=0):

- Excited nuclear states typically decay via **gamma emission** (picoseconds)
- **Beta/alpha decay** is much slower (seconds to years)
- Only **long-lived isomeric states** undergo beta/alpha decay from excited levels

### Examples of Isomers (that decay from excited states):
- Tc-99m (metastable technetium)
- Co-60m 
- Am-242m

## What Your Data Shows:

Looking at your output:
```
8   2   0.0000e+00     B-             1.0000e+00      He-8
10  6   0.0000e+00     B+             1.0000e+00      C-10
19  8   0.0000e+00     B-             2.0000e+00      O-19
20  8   0.0000e+00     B-             3.0000e+00      O-20
```

✅ **`final_level` IS being updated** (0 → 1, 2, 3)
❓ **`parentLevel` stays 0** - but is this wrong?

## Why parentLevel=0 is Expected:

1. **ENDF structure**: Each ENDF entry describes decay of a SPECIFIC nuclear state:
   - A=8, Z=2, LISO=0 → He-8 **ground state** decay
   - A=8, Z=2, LISO=1 → He-8 **isomeric state** decay (if it existed)

2. **ENSDF structure**: Same - most entries are ground state decays (parentLevel=0)

3. **Matching logic**: When ENDF He-8 ground state (parentLevel=0) matches an ENSDF transition, it should match to ENSDF He-8 ground state decay (parentLevel=0)

## What to Check:

### 1. Does ENSDF have non-zero parent levels?

Run on your machine:
```python
import pandas as pd

# Load ENSDF (custom parser needed)
# ... after loading into DataFrame ...

print("Parent level distribution:")
print(df['parentLevel'].value_counts())
```

**Expected result**: 
- 95-99% of entries will have parentLevel=0
- Only a few isomeric states will have parentLevel>0

### 2. Check the diagnostics file:

```bash
head -50 DECAY_matched_diagnostics.ascii
```

Look for columns:
- `parent_level_matched` - what the matcher found
- `final_level_matched` - what the matcher found

### 3. Look for ENDF isomeric entries:

ENDF isomers would have non-standard naming like:
- "Tc-99m" (m = metastable)
- Or LISO > 0 in the original ENDF format

These SHOULD potentially get parentLevel > 0 after matching.

## The Real Question:

**Should we UPDATE parentLevel, or should it remain as-is?**

### Interpretation 1: parentLevel is FIXED (describes which nuclide state we're evaluating)
- He-8 ground state decay should keep parentLevel=0
- He-8m isomer decay should keep parentLevel=1
- **Only update `final_level`**

### Interpretation 2: parentLevel is a PLACEHOLDER (ENDF doesn't know, we infer from ENSDF)
- ENDF gives aggregated data without knowing true parent level
- Match energy to ENSDF to find BOTH parent and daughter levels
- **Update BOTH `parentLevel` and `final_level`**

## My Recommendation:

**Check your diagnostics file first!**

If `parent_level_matched` column shows all zeros → ENSDF also has mostly ground state decays (normal)

If `parent_level_matched` has non-zero values → Check if they're being copied to output correctly

## To Generate Diagnostics:

The script should have created `DECAY_matched_diagnostics.ascii` - please share first 50 lines so we can see what `parent_level_matched` and `final_level_matched` contain.
