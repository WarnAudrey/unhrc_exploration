# How to Find Your JEFF File and Run the Script

## The Error You Got

```
compare_jeff_nudat_qvalues.py: error: the following arguments are required: jeff_file
```

**This means:** You need to tell the script WHERE your JEFF ENDF file is located!

---

## Step 1: Find Your JEFF File

Run this command to search for it:

```bash
find ~/fluka-db-audrey -name "*.endf" 2>/dev/null
```

**Or search more broadly:**

```bash
find ~ -name "*jeff*" -name "*.endf" 2>/dev/null
```

**Or check common locations:**

```bash
ls ~/fluka-db-audrey/data_input/endf/
ls ~/fluka-db-audrey/data/
ls ~/fluka-db-audrey/src/
```

---

## Step 2: Run the Script with the File Path

Once you find it, use the FULL path:

### Example 1: If file is at `/Users/audreywarn/fluka-db-audrey/data_input/endf/jeff-40-radioactive.endf`

```bash
python3 compare_jeff_nudat_qvalues.py /Users/audreywarn/fluka-db-audrey/data_input/endf/jeff-40-radioactive.endf
```

### Example 2: If file is at `/Users/audreywarn/fluka-db-audrey/data_input/endf/JEFF-4.0/jeff40.endf`

```bash
python3 compare_jeff_nudat_qvalues.py /Users/audreywarn/fluka-db-audrey/data_input/endf/JEFF-4.0/jeff40.endf
```

### Example 3: Using relative path (if you're in the right directory)

```bash
cd ~/fluka-db-audrey/data_input/endf/
python3 ~/fluka-db-audrey/src/PyClasses/compare_jeff_nudat_qvalues.py ./jeff-40-radioactive.endf
```

---

## Step 3: Full Scan (After Basic Works)

Once the basic comparison works, run the full scan:

```bash
python3 compare_jeff_nudat_qvalues.py /full/path/to/jeff-40.endf --scan-all > results.txt
```

---

## Common File Locations

Check these directories:

```bash
# Common location 1: data_input
ls ~/fluka-db-audrey/data_input/endf/

# Common location 2: data directory
ls ~/fluka-db-audrey/data/

# Common location 3: Downloads
ls ~/Downloads/*jeff*.endf

# Common location 4: Desktop
ls ~/Desktop/*jeff*.endf
```

---

## If You Can't Find the File

### Option 1: Download JEFF-4.0

Visit: https://www.oecd-nea.org/dbdata/jeff/jeff40/

Download the radioactive decay file (usually named something like `jeff-40-radioactive_decay.endf`)

### Option 2: Check What Files You Have

```bash
# Find ANY .endf files
find ~/fluka-db-audrey -name "*.endf" 2>/dev/null

# Find files with "jeff" in the name
find ~/fluka-db-audrey -iname "*jeff*" 2>/dev/null

# Find files with "decay" in the name
find ~/fluka-db-audrey -iname "*decay*" 2>/dev/null
```

### Option 3: Use ENDF-B-VIII.0 Instead

If you have ENDF-B-VIII.0 decay files instead:

```bash
python3 compare_jeff_nudat_qvalues.py /path/to/ENDF-B-VIII.0/decay/file.endf
```

---

## Quick Troubleshooting

### Error: "File not found"

```bash
# Check the file exists
ls -l /path/you/provided/file.endf

# If it doesn't exist, search again
find ~ -name "*.endf" -type f 2>/dev/null | head -20
```

### Error: "JEFF_ENDF_parser module not found"

```bash
# Make sure you're in the same directory as the parser
cd ~/fluka-db-audrey/src/PyClasses/
ls -l JEFF_ENDF_parser.py compare_jeff_nudat_qvalues.py

# Then run
python3 compare_jeff_nudat_qvalues.py /full/path/to/jeff-40.endf
```

---

## Example Session (Copy-Paste)

```bash
# 1. Go to your PyClasses directory
cd ~/fluka-db-audrey/src/PyClasses/

# 2. Find your JEFF file
find ~/fluka-db-audrey -name "*.endf" 2>/dev/null

# 3. Run script with the path you found
python3 compare_jeff_nudat_qvalues.py /the/path/you/found/jeff-40.endf

# 4. If basic works, run full scan
python3 compare_jeff_nudat_qvalues.py /the/path/you/found/jeff-40.endf --scan-all > results.txt

# 5. Check results
less results.txt
grep "Li-11" results.txt
```

---

## What File You Need

**File requirements:**
- Format: ENDF-6
- Content: Radioactive decay data (MF=8 MT=457 sections)
- Library: JEFF-4.0, ENDF-B-VIII.0, or similar
- Extension: Usually `.endf` or `.dat`
- Size: Typically 10-100 MB for full decay library

**File name examples:**
- `jeff-40-radioactive.endf`
- `jeff-40-radioactive_decay.endf`
- `JEFF_4.0_decay.endf`
- `decay.endf` (in ENDF-B-VIII.0 directory)

---

## Still Stuck?

Share the output of:

```bash
cd ~/fluka-db-audrey
find . -name "*.endf" -o -name "*decay*" 2>/dev/null | head -20
```

This will show what ENDF/decay files you have available!
