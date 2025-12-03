# Commands to Analyze Remaining Failures at 50 keV Tolerance

Run these commands on your system to understand the 1,045 remaining failures:

## 1. Check Specific Cases We Predicted

```bash
cd /Users/audreywarn/fluka-db-audrey/src/PyClasses

# Did Li-11 → Be-11 match?
grep "Li-11" matches_50keV.txt

# Did Be-12 → B-12 match?
grep "Be-12" matches_50keV.txt

# Did N-12 → C-12 match?
grep "N-12" matches_50keV.txt
```

## 2. Analyze Failure Patterns

```bash
# Look at all failures in diagnostics
grep "failed" DECAY_level_matched_diagnostics.ascii > failures_50keV.txt

# Count failures by energy range
echo "250-500 keV:"
awk '$9=="failed" && $11>=250 && $11<500 {count++} END {print count, "failures"}' DECAY_level_matched_diagnostics.ascii

echo "500-1000 keV:"
awk '$9=="failed" && $11>=500 && $11<1000 {count++} END {print count, "failures"}' DECAY_level_matched_diagnostics.ascii

echo "1-5 MeV:"
awk '$9=="failed" && $11>=1000 && $11<5000 {count++} END {print count, "failures"}' DECAY_level_matched_diagnostics.ascii

echo ">5 MeV:"
awk '$9=="failed" && $11>=5000 {count++} END {print count, "failures"}' DECAY_level_matched_diagnostics.ascii
```

## 3. Find Worst Cases

```bash
# Top 20 failures by energy difference
grep "failed" DECAY_level_matched_diagnostics.ascii | sort -k11 -nr | head -20

# Show parent and daughter with large differences
grep "failed" DECAY_level_matched_diagnostics.ascii | awk '$11>5000 {print $7, "->", $8, $11, "keV"}' | head -20
```

## 4. Check for β-Delayed Particle Modes

```bash
# Extract decay modes from ENDF file
awk '{print $4}' /Users/audreywarn/fluka-db-audrey/outputs/endf/endf_data_modules/ascii/DECAY.ascii | sort -u

# Count failures for each decay mode
echo "Failure counts by decay mode:"
awk 'NR>2 {mode=$4; if (!seen[mode]) {seen[mode]=1; modes[++n]=mode}} END {for(i=1;i<=n;i++) print modes[i]}' /Users/audreywarn/fluka-db-audrey/outputs/endf/endf_data_modules/ascii/DECAY.ascii | while read mode; do
    count=$(grep "$mode" DECAY_level_matched_diagnostics.ascii | grep "failed" | wc -l)
    echo "  $mode: $count"
done
```

## 5. Statistical Summary

```bash
# Get statistics on failed match energy differences
awk '$9=="failed" && $11!="" {sum+=$11; count++; if(min=="" || $11<min) min=$11; if($11>max) max=$11} END {print "Count:", count; print "Min:", min, "keV"; print "Max:", max, "keV"; print "Mean:", sum/count, "keV"}' DECAY_level_matched_diagnostics.ascii
```

## 6. Compare 1 keV vs 50 keV Results

```bash
# If you saved diagnostics from 1 keV run
# Count how many new matches were found
diff <(grep "matched" DECAY_level_matched_diagnostics_1keV.ascii | wc -l) <(grep "matched" DECAY_level_matched_diagnostics.ascii | wc -l)
```

## Expected Findings

Based on the results shown (76.5% match rate with 50 keV):

**Recovered with 50 keV tolerance:**
- ✅ 607 additional matches
- ✅ Most cases between 1-50 keV now match
- ✅ All failures now >250 keV

**Remaining 1,045 failures likely include:**

1. **Moderate (250-500 keV)**: ~200-300 cases
   - Q-value evaluation differences
   - Could try 100-200 keV tolerance

2. **Large (500-1000 keV)**: ~200-300 cases  
   - Excited state decays
   - Missing ENSDF transitions

3. **Very Large (1-10 MeV)**: ~300-500 cases
   - β-delayed particle emission
   - Daughter nucleus calculation issues

4. **Extreme (>10 MeV)**: ~100-200 cases
   - Systematic database issues
   - Wrong decay modes

## Questions to Answer

Run the commands above to determine:

1. **Did predicted cases match?**
   - Li-11 → Be-11 (320 keV calculated)
   - Be-12 → B-12 (14 keV)
   - N-12 → C-12 (29 keV)

2. **What's the distribution of failure energies?**
   - How many 250-500 keV?
   - How many >5 MeV?

3. **Are β-delayed particles the problem?**
   - How many B-n, B-2n failures?
   - Do they account for most large failures?

4. **Should tolerance be increased further?**
   - How many would match with 100 keV?
   - How many would match with 500 keV?

## Next Steps Based on Results

**If most failures are 250-1000 keV:**
→ Try 100-200 keV tolerance for better coverage

**If most failures are >5 MeV and β-delayed:**
→ Need special handling for delayed particle modes

**If failures are evenly distributed:**
→ 50 keV is optimal, remaining failures are data quality issues

---

Run these commands and share the output - I can help interpret the results!
