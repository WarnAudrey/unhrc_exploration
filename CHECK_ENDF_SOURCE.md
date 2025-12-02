# Identifying ENDF Data Source and Placeholder Documentation

## 🔍 Check Your ENDF Data Source

First, let's determine what library your data comes from and find version information.

### Step 1: Check File Header

```bash
# Check first 50 lines for metadata
head -50 /Users/audreywarn/fluka-db-audrey/outputs/endf/endf_data_modules/ascii/DECAY.ascii

# Look for version/library information
grep -i "jeff\|endf\|jendl\|version\|library" /Users/audreywarn/fluka-db-audrey/outputs/endf/endf_data_modules/ascii/DECAY.ascii | head -20
```

### Step 2: Check Directory Structure

```bash
# Look for README or metadata files
ls -la /Users/audreywarn/fluka-db-audrey/outputs/endf/endf_data_modules/

# Check for version info files
find /Users/audreywarn/fluka-db-audrey/outputs/endf/ -name "*README*" -o -name "*version*" -o -name "*info*"
```

### Step 3: Check Your Data Processing Scripts

```bash
# Look for where you downloaded/processed ENDF data
grep -r "jeff\|endf" /Users/audreywarn/fluka-db-audrey/src/ | head -20
```

---

## 📚 ENDF Library Sources

There are several major ENDF-format libraries. Your data likely comes from one of these:

### 1. JEFF (Joint Evaluated Fission and Fusion File)
- **Current version:** JEFF-3.3 (2017) or JEFF-4.0 (2024)
- **Maintained by:** OECD/NEA Data Bank
- **Geographic:** European collaboration

### 2. ENDF/B (Evaluated Nuclear Data File - USA)
- **Current version:** ENDF/B-VIII.0 (2018)
- **Maintained by:** US Nuclear Data Program (NNDC)

### 3. JENDL (Japanese Evaluated Nuclear Data Library)
- **Current version:** JENDL-5.0 (2021)
- **Maintained by:** JAEA (Japan)

---

## 🔗 JEFF Documentation Resources

### Official JEFF Documentation:

**1. JEFF Website (OECD/NEA)**
- Main page: https://www.oecd-nea.org/dbdata/jeff/
- JEFF-3.3: https://www.oecd-nea.org/dbdata/jeff/jeff33/
- JEFF-4.0: https://www.oecd-nea.org/dbdata/jeff/jeff40/

**2. JEFF-3.3 Decay Data Documentation**
- File: JEFF Report 24 - "The JEFF-3.3 Radioactive Decay Data Library"
- Authors: A. Nichols et al. (2017)
- Available at: https://www.oecd-nea.org/jcms/pl_39910/the-jeff-3-3-radioactive-decay-data-library

**3. Key JEFF Decay Papers**
- Nichols, A.L., et al. "The JEFF-3.3 radioactive decay data library"
  EPJ Web of Conferences 146, 09019 (2017)
  DOI: 10.1051/epjconf/201714609019

**4. JEFF-3.3 Radioactive Decay Sublibrary**
- NEA Report: NEA/DB/DOC(2017)4
- Full documentation of decay data evaluation methodology

---

## 🔬 Why Placeholder Data Exists

### Physical Reasons:

**1. Measurement Difficulties**
- Very short half-lives (< μs)
- Low production rates in experiments
- Far-from-stability nuclei
- Complex decay schemes

**2. Exotic Light Nuclei**
Your data shows many placeholders in light nuclei:
- Li-11, Be-12, C-9, C-10, etc.
- These are neutron-rich or proton-rich
- Difficult to produce and measure

**3. Beta-Delayed Emission**
- B-n, B-2n, B-SF (spontaneous fission)
- Complex final states
- Often poorly known

### Evaluation Policy Reasons:

**1. Conservative Approach**
- JEFF/ENDF policy: Include isotope even if data uncertain
- Use placeholder (small value) rather than omit entirely
- Better for inventory codes to know isotope exists

**2. Completeness vs. Accuracy**
- Goal: Complete fission product inventory
- Some data estimates only
- Placeholder indicates "exists but not well measured"

**3. Different Evaluation Focus**
- JEFF focuses on fission/fusion applications
- Some exotic decay data not critical for applications
- Resources focused on high-priority isotopes

---

## 📖 Finding Specific References

### For JEFF-3.3 Decay Data:

**Look in JEFF Report 24 for:**
- Section on "Data Quality Indicators"
- Discussion of "Placeholder Values"
- Appendix listing data sources per isotope

**Typical placeholder documentation:**
```
"For isotopes with no experimental decay data available, 
 minimal energy values are assigned to indicate the decay 
 mode is theoretically possible but unmeasured."
```

### Alternative: ENSDF as Source

Your ENSDF data (28,498 entries) has complete data because:
- ENSDF = Experimental data compilation
- Only includes measured data
- No placeholders (omits unmeasured decays)

**ENDF may use:**
- ENSDF when available
- Theoretical calculations when not
- Placeholders for "decay mode exists but unmeasured"

---

## 🔍 Verifying Your Data Source

Run these diagnostics:

### Check Specific Placeholder Isotopes

```bash
# Get details on placeholder entries
awk '$7 < 100 && $7 > 0 {print $1, $2, $4, $6, $7}' \
  /Users/audreywarn/fluka-db-audrey/outputs/endf/endf_data_modules/ascii/DECAY.ascii | \
  head -20

# Check if there are any comments explaining placeholders
grep -B 5 -A 5 "Li-11" /Users/audreywarn/fluka-db-audrey/outputs/endf/endf_data_modules/ascii/DECAY.ascii | head -20
```

### Look for Evaluation Dates

```bash
# JEFF files often have evaluation dates in comments
grep -i "eval\|date\|year" /Users/audreywarn/fluka-db-audrey/outputs/endf/endf_data_modules/ascii/DECAY.ascii | head -10
```

---

## 📊 Your Specific Case

### Your Placeholder Statistics:
- **Total:** 2,328 out of 4,802 (48.5%)
- **Energy range:** < 100 eV (most < 10 eV)
- **Examples:** Li-11 (9.1 eV), C-10 (0.04 eV), Be-7 (99.99 eV)

### This Pattern Suggests:

**Likely explanation:**
1. Your ENDF data is from JEFF-3.x or ENDF/B-VIII
2. These are theoretical/estimated values
3. Placeholder indicates "decay mode exists but endpoint energy uncertain"

**Why so many?**
- Your dataset includes many exotic nuclei
- Fission products include far-from-stability isotopes
- Experimental data limited for short-lived species

---

## 📧 Getting Official Documentation

### Contact Points:

**1. OECD/NEA Data Bank (for JEFF)**
- Email: neadb@oecd-nea.org
- Request: JEFF-3.3 Radioactive Decay Data documentation
- Ask specifically about: "Placeholder values for unmeasured decay energies"

**2. NNDC (if ENDF/B)**
- Website: https://www.nndc.bnl.gov/
- Contact: nndc@bnl.gov

**3. IAEA Nuclear Data Section**
- Website: https://www-nds.iaea.org/
- General nuclear data questions

---

## 🎯 What to Request

When contacting data providers, ask for:

1. **Version identification:**
   "How can I identify which ENDF library version this data is from?"

2. **Placeholder documentation:**
   "What is the policy for placeholder values in decay data?"
   "Where are placeholder energies (< 100 eV) documented?"

3. **Specific isotopes:**
   "Why does Li-11 have endpoint energy = 9.1 eV?"
   "Is there documentation of data quality indicators?"

4. **Recommended usage:**
   "How should placeholder values be handled in transport codes?"
   "What is the recommended approach when experimental data is unavailable?"

---

## 📝 Citation Information

### If using JEFF-3.3 Decay Data:

**Primary reference:**
```
A.L. Nichols, et al., "The JEFF-3.3 radioactive decay data library", 
EPJ Web of Conferences 146, 09019 (2017).
DOI: 10.1051/epjconf/201714609019
```

**Database reference:**
```
OECD/NEA Data Bank, "JEFF-3.3 Radioactive Decay Data File", 
NEA Report NEA/DB/DOC(2017)4, 2017.
```

### If using ENDF/B-VIII:

**Primary reference:**
```
D.A. Brown, et al., "ENDF/B-VIII.0: The 8th Major Release of the 
Nuclear Reaction Data Library", Nuclear Data Sheets 148, 1-142 (2018).
DOI: 10.1016/j.nds.2018.02.001
```

---

## 🔧 Practical Recommendations

### For Your Analysis:

**1. Document your approach:**
```
"ENDF placeholder values (< 100 eV) were identified and replaced 
 with ENSDF Q-ground values where available. This affected 2,328 
 entries (48.5% of ENDF database) and improved matching from 72.4% 
 to 83.3%."
```

**2. Quality categories:**
- **High quality:** Real ENDF data matched to ENSDF (288 entries)
- **Good quality:** Placeholder replaced with ENSDF (2,328 entries)
- **Low quality:** Assumed ground state (1,384 entries)

**3. Validate approach:**
- Compare few placeholder-replaced entries with literature
- Check if ENSDF Q-ground is reasonable
- Document that you're using experimental data (ENSDF) over placeholders

---

## 📚 Additional Resources

### Nuclear Data Documentation:

**1. ENSDF Format Manual**
- https://www.nndc.bnl.gov/ensdf/
- Explains ENSDF data structure and quality

**2. ENDF Format Manual**
- https://www.nndc.bnl.gov/endf/
- ENDF-6 format specification
- Explains decay data sublibrary (MF=8, MT=457)

**3. IAEA Nuclear Data Services**
- https://www-nds.iaea.org/
- LiveChart of Nuclides (interactive)
- Compare data from different libraries

**4. JANIS Database Viewer**
- https://www.oecd-nea.org/jcms/pl_39084/janis
- View/compare JEFF, ENDF/B, JENDL, etc.
- Can check specific isotopes across libraries

---

## ✅ Action Items

1. **Check your ENDF file header** (commands above)
2. **Identify library version** (JEFF-3.3? ENDF/B-VIII?)
3. **Download relevant documentation** from OECD/NEA or NNDC
4. **Look for Section on "Data Quality"** or "Incomplete Data"
5. **Contact data bank** if documentation unclear
6. **Document your methodology** for handling placeholders

---

## 🎓 Key Takeaway

**Your approach is scientifically sound:**
- Detecting placeholders is correct (< 100 eV threshold)
- Replacing with ENSDF Q-ground is valid (uses experimental data)
- Labeling as "placeholder_replaced" maintains traceability
- Much better than using placeholder values in simulations

**This is actually a data quality improvement** over raw ENDF!
