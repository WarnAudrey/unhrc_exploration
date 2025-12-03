#!/bin/bash

echo "=================================================================="
echo "ENDF Data Source Identification"
echo "=================================================================="
echo ""

ENDF_FILE="/Users/audreywarn/fluka-db-audrey/outputs/endf/endf_data_modules/ascii/DECAY.ascii"

echo "1. Checking file header for metadata..."
echo "=================================================================="
head -100 "$ENDF_FILE" | grep -i "jeff\|endf\|jendl\|version\|library\|eval\|date"
echo ""

echo "2. Checking for comment lines..."
echo "=================================================================="
grep "^#" "$ENDF_FILE" | head -20
echo ""

echo "3. Looking for evaluation information in parent directory..."
echo "=================================================================="
ls -la /Users/audreywarn/fluka-db-audrey/outputs/endf/endf_data_modules/
echo ""

echo "4. Searching for README or version files..."
echo "=================================================================="
find /Users/audreywarn/fluka-db-audrey/outputs/endf/ -maxdepth 3 -type f \( -iname "*readme*" -o -iname "*version*" -o -iname "*info*" \) 2>/dev/null
echo ""

echo "5. Checking specific placeholder isotopes..."
echo "=================================================================="
echo "Examples of placeholder data:"
grep "^11 *3 .*B-" "$ENDF_FILE" | head -5
grep "^10 *6 .*EC" "$ENDF_FILE" | head -5
echo ""

echo "6. First 5 lines of file..."
echo "=================================================================="
head -5 "$ENDF_FILE"
echo ""

echo "=================================================================="
echo "Analysis complete. Look for:"
echo "  - 'JEFF' or 'ENDF/B' or 'JENDL' in output above"
echo "  - Version numbers (e.g., 3.3, VIII.0, 5.0)"
echo "  - Evaluation dates"
echo "=================================================================="
