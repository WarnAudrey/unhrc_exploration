#!/bin/bash
# Exact commands to run with your JEFF-4.0 file

JEFF_FILE="/Users/audreywarn/fluka-db-audrey/data_input/endf/Radioactive_Decay_Data_JEFF-40.endf"
SCRIPT_DIR="/Users/audreywarn/fluka-db-audrey/src/PyClasses"

echo "=========================================="
echo "JEFF-4.0 Q-value Analysis Commands"
echo "=========================================="
echo ""
echo "Your JEFF file:"
echo "  $JEFF_FILE"
echo ""

# Check file exists
if [ ! -f "$JEFF_FILE" ]; then
    echo "ERROR: File not found!"
    echo "Please verify the path is correct."
    exit 1
fi

echo "File found! Size: $(du -h "$JEFF_FILE" | cut -f1)"
echo ""

echo "=========================================="
echo "Command 1: Basic Comparison (30 seconds)"
echo "=========================================="
echo ""
echo "cd $SCRIPT_DIR"
echo "python3 compare_jeff_nudat_qvalues.py $JEFF_FILE"
echo ""

echo "=========================================="
echo "Command 2: Full Scan (3-5 minutes)"
echo "=========================================="
echo ""
echo "cd $SCRIPT_DIR"
echo "python3 compare_jeff_nudat_qvalues.py $JEFF_FILE --scan-all"
echo ""

echo "=========================================="
echo "Command 3: Save Full Results to File"
echo "=========================================="
echo ""
echo "cd $SCRIPT_DIR"
echo "python3 compare_jeff_nudat_qvalues.py $JEFF_FILE --scan-all > jeff_nudat_results.txt"
echo ""

echo "=========================================="
echo "Ready to run!"
echo "=========================================="
