#!/bin/bash
# Fix Python cache and run improved matcher

echo "=========================================="
echo "Clearing Python bytecode cache..."
echo "=========================================="

cd ~/fluka-db-audrey/src/PyClasses

# Remove all .pyc files and __pycache__ directories
find . -type f -name "*.pyc" -delete
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null

echo "✓ Cache cleared"
echo ""

echo "=========================================="
echo "Verifying file was updated..."
echo "=========================================="

# Check if improved code markers are present
if grep -q "dominant ENSDF transition" ENDFLevelMatching.py; then
    echo "✓ Improved version detected"
else
    echo "✗ Old version still in place"
    echo ""
    echo "Copying improved version..."
    cp /workspace/ENDFLevelMatching_IMPROVED.py ENDFLevelMatching.py
    echo "✓ Copied improved version"
fi

echo ""
echo "=========================================="
echo "Running improved matcher..."
echo "=========================================="
echo ""

python3 ENDFLevelMatching.py

echo ""
echo "=========================================="
echo "Checking for improvements..."
echo "=========================================="

# Count specific match types
echo "Placeholder replaced:"
grep -c "placeholder_replaced" DECAY_level_matched_diagnostics.ascii || echo "0"

echo "Assumed ground:"
grep -c "assumed_ground" DECAY_level_matched_diagnostics.ascii || echo "0"

echo ""
echo "Check Li-11 matches:"
grep "Li-11" DECAY_level_matched_diagnostics.ascii | head -5
