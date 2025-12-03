#!/bin/bash
# Helper script to find JEFF/ENDF files on your system

echo "=========================================="
echo "Searching for JEFF/ENDF files..."
echo "=========================================="
echo ""

echo "1. Looking for .endf files in fluka-db-audrey:"
find ~/fluka-db-audrey -name "*.endf" -type f 2>/dev/null | head -10

echo ""
echo "2. Looking for files with 'jeff' in name:"
find ~/fluka-db-audrey -iname "*jeff*" -type f 2>/dev/null | grep -E "\.(endf|dat)$" | head -10

echo ""
echo "3. Looking for files with 'decay' in name:"
find ~/fluka-db-audrey -iname "*decay*" -type f 2>/dev/null | grep -E "\.(endf|dat)$" | head -10

echo ""
echo "4. Checking common directories:"
for dir in \
    ~/fluka-db-audrey/data_input/endf \
    ~/fluka-db-audrey/data_input \
    ~/fluka-db-audrey/data \
    ~/fluka-db-audrey/src/data \
    ~/Downloads \
    ~/Desktop
do
    if [ -d "$dir" ]; then
        echo "   Checking: $dir"
        ls "$dir"/*.endf 2>/dev/null | head -3
    fi
done

echo ""
echo "=========================================="
echo "Once you find your file, run:"
echo "=========================================="
echo "python3 compare_jeff_nudat_qvalues.py /path/to/your/file.endf"
echo ""
