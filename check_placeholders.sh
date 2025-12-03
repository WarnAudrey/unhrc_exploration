#!/bin/bash

# Check for placeholder data in user's ENDF file
ENDF_FILE="/Users/audreywarn/fluka-db-audrey/outputs/endf/endf_data_modules/ascii/DECAY.ascii"

echo "==================================================================="
echo "ENDF Placeholder Data Analysis"
echo "==================================================================="
echo ""

# Count entries with energy < 100 eV (column 6 or 7, depending on format)
echo "Checking for placeholder energies (< 100 eV)..."
echo ""

# Method 1: Check endpoint energy column (usually column 7)
awk 'NR>2 {
    # Skip header lines
    if ($7 ~ /^[0-9]/ && $7 < 100) {
        count++
        if (count <= 10) {
            printf "  %3s %-5s %-10s %-10s Energy: %-15s\n", $1, $2, $4, $6, $7
        }
    }
} 
END {
    print ""
    print "Total entries with energy < 100 eV:", count
    print ""
}' "$ENDF_FILE"

# Count total entries
total=$(awk 'NR>2 {count++} END {print count}' "$ENDF_FILE")
placeholder=$(awk 'NR>2 && $7 < 100 {count++} END {print count}' "$ENDF_FILE")

echo "Total ENDF entries: $total"
echo "Placeholder entries: $placeholder"
if [ ! -z "$placeholder" ] && [ "$placeholder" -gt 0 ]; then
    pct=$(awk "BEGIN {printf \"%.1f\", 100*$placeholder/$total}")
    echo "Percentage: $pct%"
fi

echo ""
echo "==================================================================="
