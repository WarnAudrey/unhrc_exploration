# Level Matching Code Update - Final Version

## Key Improvement: Using Native ENSDF Level Energies

### Previous Approach (WRONG)
- **Calculated** level energies from decay transitions: `E_level = Q_ground - E_particle`
- This was indirect and potentially inconsistent

### Current Approach (CORRECT)
- **Directly uses** ENSDF LEVEL.ascii which contains the true nuclear level energies
- NO calculations for ENSDF level energies
- Much cleaner, more accurate, and physically correct

---

## Updated Architecture

### 1. Data Sources

**Input Files:**
- `ENDF DECAY.ascii`: ENDF decay transitions (needs level matching)
- `ENSDF DECAY.ascii`: ENSDF decay transitions catalog
- `ENSDF LEVEL.ascii`: **TRUE nuclear level energies** ⭐ NEW

**Example ENSDF LEVEL.ascii:**
```
                 elementName          energy      energyUnit
A   Z   level
4   2   0              Helium   0.000e+00 keV             keV
4   2   1              Helium   2.021e+04 keV             keV
4   2   2              Helium   2.101e+04 keV             keV
```

---

### 2. Data Structures

#### A. Daughter Level Energy Table: `self.daughter_levels`
```python
Dict[(A, Z)] → {level_number: level_energy_eV}

Example:
{
  (4, 2): {  # Helium-4
    0: 0,           # Ground state
    1: 20210000,    # First excited state (from LEVEL.ascii)
    2: 21010000,    # Second excited state (from LEVEL.ascii)
    ...
  }
}
```

**Source:** Direct from `ENSDF LEVEL.ascii` - NO calculations!

**Purpose:** Fast lookup of true ENSDF level energies for matching

---

#### B. Transition Catalog: `self.transition_lookup`
```python
Dict[(parent_A, parent_Z, decay_mode)] → [
  {'parent_level': 0, 'daughter_level': 0, 'particle_energy': 3508000},
  {'parent_level': 0, 'daughter_level': 1, 'particle_energy': 2500000},
  ...
]
```

**Source:** From `ENSDF DECAY.ascii`

**Purpose:** Catalog all available ENSDF transitions

---

#### C. Q_ground Lookup: `self.q_ground_lookup`
```python
Dict[(parent_A, parent_Z, decay_mode)] → Q_ground_energy_eV
```

**Source:** Maximum particle energy from ground→ground transitions in `ENSDF DECAY.ascii`

**Purpose:** Calculate ENDF daughter level energies

---

### 3. Matching Algorithm

**Step 1:** Calculate ENDF daughter level energy
```python
endf_daughter_level_energy = Q_ground - endf_particle_energy
```

**Step 2:** Look up ENSDF daughter level energies from LEVEL.ascii table
```python
daughter_key = (daughter_A, daughter_Z)
daughter_level_table = self.daughter_levels[daughter_key]
ensdf_daughter_level_energy = daughter_level_table[level_num]
```

**Step 3:** Compare level energies within tolerance
```python
abs_diff = abs(ensdf_daughter_level_energy - endf_daughter_level_energy)
if abs_diff <= tolerance:
    # Match found!
```

**Step 4:** Return matched transition with `parent_level` and `final_level`

---

## Code Changes

### Updated Methods

1. **`__init__()`**
   - Added `ensdf_level_path` parameter
   - Calls `_load_level_file()` before `_build_ensdf_lookup()`

2. **`_load_level_file()` NEW**
   - Loads ENSDF LEVEL.ascii
   - Parses line-by-line to handle units (keV → eV)
   - Stores in `self.ensdf_level_df`

3. **`_build_ensdf_lookup()` REWRITTEN**
   - **Step 1:** Build `self.daughter_levels` directly from LEVEL.ascii (no calculations!)
   - **Step 2:** Build `self.transition_lookup` and `self.q_ground_lookup` from DECAY.ascii

4. **`_find_matching_transition()`**
   - Looks up ENSDF level energies from `self.daughter_levels` table
   - No changes to matching logic itself

5. **Command-line interface**
   - Added `--ensdf-level` argument with default path

---

## Usage

```bash
python ENDFLevelMatcher_DECAY_v2_commented.py \
  --endf /path/to/ENDF/DECAY.ascii \
  --ensdf /path/to/ENSDF/DECAY.ascii \
  --ensdf-level /path/to/ENSDF/LEVEL.ascii \
  --output DECAY_matched.ascii
```

**Default paths:**
- ENDF: `/Users/audreywarn/fluka-db-audrey/outputs/endf/endf_data_modules/ascii/DECAY.ascii`
- ENSDF DECAY: `/Users/audreywarn/fluka-db-audrey/outputs/ensdf/json_data_modules/ascii/DECAY.ascii`
- ENSDF LEVEL: `/Users/audreywarn/fluka-db-audrey/outputs/ensdf/json_data_modules/ascii/LEVEL.ascii` ⭐ NEW

---

## Benefits

1. ✅ **Physically Correct**: Uses true ENSDF level energies, not derived values
2. ✅ **No Redundant Calculations**: ENSDF data used as-is
3. ✅ **Clean Separation**: Structure (LEVEL) vs. Decay (DECAY) data properly separated
4. ✅ **More Accurate**: Avoids potential rounding errors from calculations
5. ✅ **Comprehensive**: LEVEL.ascii contains full level schemes, not just decay endpoints
6. ✅ **Maintains Transitions**: Full transition catalog preserved for traceability

---

## Files Modified

- `/workspace/ENDFLevelMatcher_DECAY_v2_commented.py`
  - Line 224-255: Updated `__init__()` method
  - Line 381-450: Added `_load_level_file()` method
  - Line 511-616: Rewritten `_build_ensdf_lookup()` method
  - Line 1338-1355: Updated command-line arguments
  - Line 1391-1395: Updated matcher instantiation

---

## Next Steps

Test on your system with all three files:
```bash
python ENDFLevelMatcher_DECAY_v2_commented.py
```

Expected improvements:
- Higher match rates (LEVEL.ascii has more comprehensive level data)
- More accurate matching (using true level energies)
- Better coverage (ENSDF structure database is more complete than decay-only data)
