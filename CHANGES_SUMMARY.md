# Level Matching Code Update Summary

## Changes Made to ENDFLevelMatcher_DECAY_v2_commented.py

### Key Architectural Change

The code now maintains **TWO separate data structures** to properly handle both level energies and transition information:

### 1. Daughter Level Energy Table: `self.daughter_levels`
```python
self.daughter_levels: Dict[(daughter_A, daughter_Z)] → {
    level_number: level_energy_eV,
    0: 0,           # Ground state always at 0 eV
    1: 2430000,     # First excited state
    2: 2780000,     # Second excited state
    ...
}
```

**Purpose:** Clean lookup table mapping daughter nucleus and level number to level energy.

**Calculation:** For each ENSDF transition, calculate once:
```
level_energy = Q_ground - particle_energy
```

**Deduplication:** If the same level appears in multiple transitions (from different parents), store the minimum energy value (most consistent with ground state = 0).

---

### 2. Transition Catalog: `self.transition_lookup`
```python
self.transition_lookup: Dict[(parent_A, parent_Z, decay_mode)] → [
    {'parent_level': 0, 'daughter_level': 0, 'particle_energy': 3508000},
    {'parent_level': 0, 'daughter_level': 1, 'particle_energy': 2500000},
    ...
]
```

**Purpose:** Catalog all available ENSDF transitions for each parent/decay_mode.

**Contents:** Each transition contains:
- `parent_level`: Parent nuclear level (usually 0 for ground state)
- `daughter_level`: Daughter level number
- `particle_energy`: Emitted particle energy (eV)

---

### 3. Matching Logic Update

The `_find_matching_transition` function now:

1. **Calculates ENDF daughter level energy:**
   ```python
   endf_daughter_level_energy = q_ground - endf_particle_energy
   ```

2. **Looks up available transitions** from `self.transition_lookup`

3. **For each transition**, retrieves ENSDF daughter level energy from the **daughter level table**:
   ```python
   daughter_key = (daughter_a, daughter_z)
   daughter_level_table = self.daughter_levels.get(daughter_key, {})
   ensdf_daughter_level_energy = daughter_level_table[daughter_level_num]
   ```

4. **Compares level energies** within configured tolerances

5. **Returns matched transition** with both `parent_level` and `final_level` from ENSDF

---

## Benefits of This Approach

1. **Clean Separation:** Level energies are stored once per unique level, not redundantly per transition
2. **Efficient Lookup:** Direct dictionary access to level energies
3. **Maintains Transitions:** Full transition catalog preserved for completeness
4. **Physically Correct:** Matches calculated ENDF level energies against stored ENSDF level energies
5. **No Redundant Calculations:** ENSDF level energies calculated once during lookup building

---

## Files Modified

- `/workspace/ENDFLevelMatcher_DECAY_v2_commented.py`
  - Updated `_build_ensdf_lookup()` function (lines 436-570)
  - Updated `_find_matching_transition()` function (lines 761-818)

---

## Testing Notes

The code structure is complete and ready for testing on your system with:
```bash
python ENDFLevelMatcher_DECAY_v2_commented.py \
  --endf /Users/audreywarn/fluka-db-audrey/outputs/endf/endf_data_modules/ascii/DECAY.ascii \
  --ensdf /Users/audreywarn/fluka-db-audrey/outputs/ensdf/json_data_modules/ascii/DECAY.ascii \
  --output DECAY_matched.ascii
```

Expected output will show:
- Step 1: Finding Q_ground values
- Step 2: Building daughter level tables and transition catalog
- Matching progress with statistics
- Final match rate and quality distribution
