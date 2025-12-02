# ENDF Placeholder Data: Complete Analysis & Solutions

## 🔍 The Problem

ENDF DECAY.ascii contains **placeholder values** for missing or uncertain data:
- Very small energies (< 100 eV) that are physically implausible
- Exactly zero energies
- Missing intensity values

**Example: Li-11 B- decay**
```
ENDF:  particle_energy = 9.1 eV     ← Placeholder! (should be ~20,000 keV)
ENSDF: particle_energy = 20,230 keV ← Real measurement
```

This causes massive matching failures even with correct Q_ground values.

---

## 📊 Identifying Placeholder Data

### Characteristics of Placeholder Entries

1. **Energy < 100 eV** (< 0.1 keV)
   - Most beta decays: > 10 keV
   - Most alpha decays: > 1000 keV
   - Values < 100 eV are almost certainly placeholders

2. **Exactly zero energy**
   - Physically impossible for actual decay
   - Clear indicator of missing data

3. **Very low intensity with low energy**
   - Real low-energy decays usually have some intensity
   - Placeholder combinations: E < 100 eV AND I < 1%

### Detection Strategy

```python
def is_placeholder(energy_eV, intensity=None):
    """
    Detect if ENDF entry contains placeholder data.
    
    Args:
        energy_eV: Particle energy in eV
        intensity: Branching ratio (0-100%)
    
    Returns:
        True if likely placeholder, False otherwise
    """
    # Exact zero is always placeholder
    if energy_eV == 0:
        return True
    
    # Very small energies (< 100 eV) are suspicious
    if energy_eV < 100:
        return True
    
    # Low energy + low intensity is suspicious
    if intensity is not None and energy_eV < 1e3 and intensity < 1.0:
        return True
    
    return False
```

---

## 🎯 Handling Strategies

### Strategy 1: Skip Placeholder Entries (Conservative)

**When to use:** You want only high-quality matches

**Implementation:**
```python
# In match_levels() method
for idx, row in endf_reset.iterrows():
    endf_energy = row.get('Endpoint_energy', np.nan)
    intensity = row.get('Intensity', np.nan)
    
    # Check for placeholder
    if not pd.isna(endf_energy) and is_placeholder(endf_energy, intensity):
        endf_reset.at[idx, 'match_quality'] = 'placeholder_data'
        continue  # Skip matching
    
    # ... rest of matching code
```

**Pros:**
- ✓ Avoids false matches
- ✓ Clean, high-quality output
- ✓ Clear reporting of data quality issues

**Cons:**
- ✗ Reduces coverage (lose ~5-10% of entries)
- ✗ Might skip some real low-energy transitions (rare)

---

### Strategy 2: Use ENSDF Energy (Fallback)

**When to use:** You want maximum coverage

**Implementation:**
```python
# In _find_matching_transition() method
if is_placeholder(endf_particle_energy):
    # Use ENSDF ground→ground Q-value instead
    key = (parent_a, parent_z, decay_mode)
    
    if key in self.q_ground_lookup:
        q_ground = self.q_ground_lookup[key]
        
        # Assume decay goes to ground state
        # (most common for missing ENDF data)
        return MatchResult(
            matched=True,
            parent_level=0.0,
            final_level=0.0,
            ensdf_energy=q_ground,
            endf_q_value=endf_particle_energy,
            energy_diff=0.0,  # No comparison possible
            rel_diff=0.0,
            match_quality="ensdf_fallback",
            ambiguous=False,
            daughter_nuclide=daughter_name
        )
```

**Pros:**
- ✓ Maximum coverage
- ✓ Uses known ENSDF data
- ✓ Good for simulation input (better than placeholder)

**Cons:**
- ✗ Assumes ground state population
- ✗ Might not match actual ENDF intent
- ✗ Creates "synthetic" matches

---

### Strategy 3: Hybrid Approach (Recommended)

**When to use:** Balance quality and coverage

**Implementation:**
```python
# Add placeholder detection to ENDFLevelMatcher class

def _is_placeholder(self, energy_eV, intensity=None):
    """Detect placeholder data."""
    if energy_eV == 0 or energy_eV < 100:
        return True
    if intensity is not None and energy_eV < 1e3 and intensity < 1.0:
        return True
    return False

def _find_matching_transition(self, parent_a, parent_z, parent_level, 
                              decay_mode, endf_particle_energy, 
                              parent_name, verbose=False):
    """Enhanced with placeholder handling."""
    
    # Check for placeholder early
    if self._is_placeholder(endf_particle_energy):
        if verbose:
            print(f"    ⚠ ENDF energy is placeholder ({endf_particle_energy:.2f} eV)")
        
        # Try to use ENSDF data instead
        daughter_a, daughter_z = self._get_daughter_nucleus(parent_a, parent_z, decay_mode)
        daughter_elem = ATOMIC_SYMBOL.get(daughter_z, f'Z{daughter_z}')
        daughter_name = f"{daughter_elem}-{daughter_a}"
        
        key = (parent_a, parent_z, decay_mode)
        
        # Option A: Use ENSDF Q_ground (assume ground state)
        if key in self.q_ground_lookup:
            q_ground = self.q_ground_lookup[key]
            
            if verbose:
                print(f"    → Using ENSDF Q_ground: {q_ground/1e3:.2f} keV")
            
            return MatchResult(
                matched=True,
                parent_level=0.0,
                final_level=0.0,
                ensdf_energy=q_ground,
                endf_q_value=endf_particle_energy,
                energy_diff=np.nan,  # No meaningful comparison
                rel_diff=np.nan,
                match_quality="placeholder_replaced",
                ambiguous=False,
                daughter_nuclide=daughter_name
            )
        
        # Option B: Mark as placeholder and skip
        else:
            return MatchResult(
                matched=False,
                parent_level=np.nan,
                final_level=np.nan,
                ensdf_energy=np.nan,
                endf_q_value=endf_particle_energy,
                energy_diff=np.nan,
                rel_diff=np.nan,
                match_quality="placeholder_data",
                ambiguous=False,
                daughter_nuclide=daughter_name
            )
    
    # ... continue with normal matching logic
```

**Pros:**
- ✓ Good coverage
- ✓ Clear labeling of data quality
- ✓ Uses best available data
- ✓ Maintains traceability

**Cons:**
- ✗ More complex code
- ✗ Needs careful documentation

---

## 📈 Expected Impact

### Current Results (72.4% match rate)
```
Total matched: 3,478/4,802
  Real matches: 701
  Assumed ground: 2,777
Failed: 1,324
```

### With Placeholder Detection
```
Estimated breakdown:
  Placeholder data: ~300-500 entries (~6-10% of ENDF)
  
With Strategy 1 (Skip):
  Match rate: ~67-69% (lose placeholder entries)
  Higher quality matches

With Strategy 2 (Replace):
  Match rate: ~77-80% (replace with ENSDF)
  Lower quality but more coverage

With Strategy 3 (Hybrid):
  Match rate: ~74-77%
  Clearly labeled: "placeholder_replaced" vs real matches
```

---

## 🔧 Implementation Code

### Add to ENDFLevelMatcher.__init__():

```python
# Track placeholder statistics
self.placeholder_count = 0
self.placeholder_replaced = 0
```

### Add helper method:

```python
def _is_placeholder(self, energy_eV, intensity=None):
    """
    Detect if energy value is a placeholder.
    
    Placeholders are characterized by:
    - Exactly zero energy
    - Very small energies (< 100 eV)
    - Low energy + low intensity combinations
    
    Args:
        energy_eV: Particle energy in eV
        intensity: Optional branching ratio (%)
    
    Returns:
        bool: True if likely placeholder
    """
    # Exact zero
    if energy_eV == 0:
        return True
    
    # Very small values (< 100 eV = 0.1 keV)
    # Most real decays are >> 1 keV
    if energy_eV < 100:
        return True
    
    # Suspicious combinations: low E + low I
    if intensity is not None:
        if energy_eV < 1e3 and intensity < 1.0:
            return True
    
    return False
```

### Modify match_levels():

```python
# In the loop where you process each ENDF entry
for idx, row in endf_reset.iterrows():
    # ... get endf_energy ...
    
    # NEW: Check for placeholder
    intensity = row.get('Intensity', np.nan)
    if not pd.isna(endf_energy) and self._is_placeholder(endf_energy, intensity):
        self.placeholder_count += 1
        
        # Try to replace with ENSDF data
        key = (parent_a, parent_z, decay_mode)
        if key in self.q_ground_lookup:
            # Use ENSDF Q_ground
            q_ground = self.q_ground_lookup[key]
            daughter_a, daughter_z = self._get_daughter_nucleus(parent_a, parent_z, decay_mode)
            daughter_elem = ATOMIC_SYMBOL.get(daughter_z, f'Z{daughter_z}')
            daughter_name = f"{daughter_elem}-{daughter_a}"
            
            match = MatchResult(
                matched=True,
                parent_level=0.0,
                final_level=0.0,
                ensdf_energy=q_ground,
                endf_q_value=endf_energy,
                energy_diff=np.nan,
                rel_diff=np.nan,
                match_quality="placeholder_replaced",
                ambiguous=False,
                daughter_nuclide=daughter_name
            )
            self.placeholder_replaced += 1
        else:
            # No ENSDF data available
            match = MatchResult(
                matched=False,
                parent_level=np.nan,
                final_level=np.nan,
                ensdf_energy=np.nan,
                endf_q_value=endf_energy,
                energy_diff=np.nan,
                rel_diff=np.nan,
                match_quality="placeholder_data",
                ambiguous=False,
                daughter_nuclide=daughter_name
            )
        
        self.match_results.append(match)
        
        # Store result
        if match.matched:
            endf_reset.at[idx, 'final_level_matched'] = match.final_level
            endf_reset.at[idx, 'match_quality'] = match.match_quality
            endf_reset.at[idx, 'daughter_nuclide'] = match.daughter_nuclide
        else:
            endf_reset.at[idx, 'match_quality'] = match.match_quality
            endf_reset.at[idx, 'daughter_nuclide'] = match.daughter_nuclide
        
        continue  # Skip normal matching
    
    # ... rest of normal matching code ...
```

### Update statistics printing:

```python
# At end of match_levels()
print(f"\nPlaceholder data detected:")
print(f"  Total placeholders: {self.placeholder_count}")
print(f"  Replaced with ENSDF: {self.placeholder_replaced}")
print(f"  Skipped (no ENSDF): {self.placeholder_count - self.placeholder_replaced}")
```

---

## 📋 Diagnostic Commands

### Find all placeholder entries in ENDF:

```bash
# Find entries with energy < 100 eV
awk '$6 != "" && $6 < 100 {print $0}' \
  /Users/audreywarn/fluka-db-audrey/outputs/endf/endf_data_modules/ascii/DECAY.ascii

# Count them
awk '$6 != "" && $6 < 100 {count++} END {print "Placeholders:", count}' \
  /Users/audreywarn/fluka-db-audrey/outputs/endf/endf_data_modules/ascii/DECAY.ascii
```

### Check specific nuclei:

```bash
# Check all Li isotopes
grep "^1[0-9] *3 " /Users/audreywarn/fluka-db-audrey/outputs/endf/endf_data_modules/ascii/DECAY.ascii

# Check He-6 (known to be tricky)
grep "^6 *2 " /Users/audreywarn/fluka-db-audrey/outputs/endf/endf_data_modules/ascii/DECAY.ascii
```

### Analyze your current matches:

```bash
# Count placeholder failures
awk '$9 == "failed" && $5 != "" && $5 < 0.1 {count++} END {print "Failed due to placeholders:", count}' \
  matches_50keV.txt
```

---

## 🎓 Physics Context

### Why Do Placeholders Exist?

1. **Measurement difficulties**
   - Very short-lived nuclei
   - Low production rates
   - Complex decay schemes

2. **Data evaluation timing**
   - Some ENDF evaluations older than latest measurements
   - Conservative approach: use placeholder if uncertain

3. **Systematic vs. statistical uncertainties**
   - Better to mark as uncertain than give wrong value

### Common Cases

**Exotic light nuclei:**
- Li-11, Be-12, Be-14, B-15, etc.
- Far from stability
- Hard to measure

**Beta-delayed particle emission:**
- B-n, B-2n, B-alpha, etc.
- Complex final states
- Difficult spectroscopy

**High-lying states:**
- Weak branches
- Low statistics
- Large uncertainties

---

## ✅ Recommended Approach

### For Your Use Case:

**Implement Strategy 3 (Hybrid):**

1. **Detect placeholders** (< 100 eV threshold)
2. **Replace with ENSDF Q_ground** (assume ground state)
3. **Label clearly** as "placeholder_replaced"
4. **Report statistics** (how many, which nuclei)

This gives you:
- ✓ Maximum coverage (~75-80% match rate)
- ✓ Better data quality than placeholders
- ✓ Clear traceability
- ✓ Easy to filter out if needed

### Output Format:

```
Match quality categories:
  exact              - Perfect match (< 10% of tolerance)
  good               - Good match (< 50% of tolerance)
  acceptable         - Within tolerance
  marginal           - Within relaxed tolerance
  assumed_ground     - No ENSDF transitions (assumed ground)
  placeholder_replaced - ENDF placeholder, used ENSDF instead ← NEW
  placeholder_data   - ENDF placeholder, no ENSDF available ← NEW
  failed             - Outside tolerance
  no_ensdf_data      - No ENSDF data at all
```

---

## 📊 Quick Reference

| Energy Range | Interpretation | Action |
|--------------|----------------|--------|
| 0 eV | Exact zero | Placeholder - replace |
| < 100 eV | ~Suspicious | Likely placeholder - replace |
| 100 eV - 1 keV | Rare but possible | Check intensity; if low, replace |
| > 1 keV | Normal | Use as-is |

| Match Quality | Meaning | Confidence |
|---------------|---------|------------|
| exact/good/acceptable | Real match | High ✓✓✓ |
| marginal | Loose match | Medium ✓✓ |
| placeholder_replaced | ENSDF used | Medium ✓✓ |
| assumed_ground | Guessed ground | Low ✓ |
| failed | No match | N/A ✗ |

---

## 🚀 Next Steps

1. **Run diagnostics** to count placeholders in your ENDF file
2. **Implement Strategy 3** (hybrid approach)
3. **Re-run matching** and compare statistics
4. **Document** which entries were replaced
5. **Validate** a sample of replaced entries manually

Expected outcome:
- Match rate: **75-80%**
- Clear quality labels
- Better simulation input than placeholders
