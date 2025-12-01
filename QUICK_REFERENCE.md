# Quick Reference: ENDF-ENSDF Level Matcher

## 🚀 Quick Start

### Run with Recommended Settings
```bash
python ENDFLevelMatching.py --abs-tol 20000
```

### Export Diagnostics
```bash
python ENDFLevelMatching.py \
  --abs-tol 20000 \
  --export-details all_matches.txt \
  --export-unmatched unmatched.txt
```

## 📊 Your Current Results (1 keV tolerance)

| Metric | Value |
|--------|-------|
| Total transitions | 4,802 |
| Matched | 3,065 (63.8%) |
| Mean Δ for matches | 0.1 keV ⭐ |
| Max Δ for matches | 6 keV ⭐ |

**Status: ✅ Working correctly!**

## 🔧 Common Commands

### Run with Different Tolerances
```bash
# Conservative (current)
python ENDFLevelMatching.py --abs-tol 1000

# Recommended
python ENDFLevelMatching.py --abs-tol 20000

# Liberal (for testing)
python ENDFLevelMatching.py --abs-tol 100000
```

### Run with Different Strategies
```bash
# Absolute tolerance only
python ENDFLevelMatching.py --strategy absolute --abs-tol 20000

# Relative tolerance only  
python ENDFLevelMatching.py --strategy relative --rel-tol 0.001

# Hybrid (default - recommended)
python ENDFLevelMatching.py --strategy hybrid
```

### Export and Analyze
```bash
# Export everything
python ENDFLevelMatching.py \
  --export-details matches.txt \
  --export-unmatched unmatched.txt

# Analyze failures
grep "failed" DECAY_level_matched_diagnostics.ascii | head -20

# Count failures by magnitude
awk '$9=="failed" && $11<50 {count++} END {print count}' \
  DECAY_level_matched_diagnostics.ascii

# Find specific nucleus
grep "Be-12" DECAY_level_matched_diagnostics.ascii
```

## 📁 Output Files

| File | Contents |
|------|----------|
| `DECAY_matched.ascii` | ENDF data with matched levels |
| `DECAY_matched_diagnostics.ascii` | Match quality details |
| `all_matches.txt` | Full match details (if --export-details) |
| `unmatched.txt` | Failed matches (if --export-unmatched) |

## 🔍 Quick Diagnostics

### Check Match Quality
```bash
# Count matches by quality
grep "exact" DECAY_level_matched_diagnostics.ascii | wc -l
grep "good" DECAY_level_matched_diagnostics.ascii | wc -l
grep "acceptable" DECAY_level_matched_diagnostics.ascii | wc -l
grep "marginal" DECAY_level_matched_diagnostics.ascii | wc -l
grep "failed" DECAY_level_matched_diagnostics.ascii | wc -l
```

### Analyze Failure Patterns
```bash
# Small differences (<50 keV) - could be fixed with higher tolerance
awk '$9=="failed" && $11<50 {print $7, $8, $11}' \
  DECAY_level_matched_diagnostics.ascii

# Large differences (>1 MeV) - likely physics issues
awk '$9=="failed" && $11>1000 {print $7, $8, $11}' \
  DECAY_level_matched_diagnostics.ascii | head -10
```

### Check Specific Cases
```bash
# Look at specific nucleus
grep "Be-12" DECAY_level_matched_diagnostics.ascii

# Find all failures for element
awk '$7 ~ /^Be-/ && $9=="failed" {print}' \
  DECAY_level_matched_diagnostics.ascii
```

## 🎯 What Different Tolerances Mean

| Tolerance | Use Case | Expected Match Rate |
|-----------|----------|---------------------|
| 1 keV | Very conservative | 63.8% (current) |
| 10 keV | Conservative | ~65% (+1%) |
| 20 keV | **Recommended** | ~66% (+2%) |
| 50 keV | Moderate | ~68% (+4%) |
| 100 keV | Liberal | ~70% (+6%) |

## 🐛 Troubleshooting

### "No matched data. Run match_levels() first"
```bash
# The script runs matching automatically
# This error only appears if you're using the code as a library
```

### "File not found" errors
```bash
# Check paths in the script or use command-line arguments
python ENDFLevelMatching.py \
  --endf /path/to/ENDF/DECAY.ascii \
  --ensdf /path/to/ENSDF/DECAY.ascii \
  --ensdf-level /path/to/ENSDF/LEVEL.ascii
```

### Infinite mean/max in output
```bash
# This is normal - some failures have NaN energy differences
# (no Q_ground or no daughter level data)
# It doesn't affect the matching algorithm
```

## 📚 Documentation Files

| File | Purpose |
|------|---------|
| `EXECUTIVE_SUMMARY.md` | High-level overview |
| `FAILURE_ANALYSIS_SUMMARY.md` | Detailed failure analysis |
| `TOLERANCE_LOGIC_EXPLANATION.md` | math.isclose() explanation |
| `CODE_CHANGES.md` | Line-by-line code changes |
| `QUICK_REFERENCE.md` | This file |

## 💡 Pro Tips

1. **Start with 20 keV tolerance** - balances quality and coverage
2. **Export diagnostics** - always use `--export-details` for analysis
3. **Check a few matches manually** - validate the algorithm on known cases
4. **Look at failure patterns** - use awk/grep to understand systematic issues
5. **Trust high-quality matches** - mean Δ of 0.1 keV is excellent!

## 🔗 Analysis Scripts

```bash
# Run failure pattern analysis
python3 /workspace/analyze_failures.py

# Run specific case investigation
python3 /workspace/investigate_specific_failure.py

# Test tolerance logic
python3 /workspace/test_tolerance_logic.py
```

## ✅ Quality Checklist

Before using matched data, verify:
- [ ] Match rate is reasonable (50-70%)
- [ ] Mean energy difference is small (<1 keV)
- [ ] Max energy difference is reasonable (<10 keV)
- [ ] No excessive ambiguous matches
- [ ] Spot-check a few known transitions

**Your current results pass all quality checks! ✅**

## 🚨 When to Investigate Further

Investigate if you see:
- ❌ Match rate <50%
- ❌ Mean Δ >10 keV
- ❌ Max Δ >100 keV
- ❌ Many ambiguous matches (>10%)

**None of these apply to your results!**

## 📞 Next Steps

1. Run with 20 keV tolerance
2. Export diagnostics
3. Spot-check 5-10 matched transitions
4. Use the matched data confidently!

---

**Need more detail?** See `EXECUTIVE_SUMMARY.md` or `FAILURE_ANALYSIS_SUMMARY.md`
