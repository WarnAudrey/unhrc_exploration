#!/usr/bin/env python3
"""
Test script to verify EC and EC delayed particle parsing.
"""

import sys
import os

# Add path if needed
if len(sys.argv) > 1:
    json_parser_path = sys.argv[1]
    sys.path.insert(0, os.path.dirname(json_parser_path))

try:
    from JSONParsing_FIXED import NuclearDataModule
except ImportError:
    print("Error: Could not import JSONParsing_FIXED")
    print("Usage: python3 test_ec_parsing.py /path/to/JSONParsing_FIXED.py")
    sys.exit(1)

def test_ec_parsing(json_dir):
    """Test EC parsing with a specific directory."""
    
    print("=" * 80)
    print("TESTING EC PARSING")
    print("=" * 80)
    print(f"Input directory: {json_dir}\n")
    
    # Initialize with the directory
    nuclear_module = NuclearDataModule(json_dir)
    
    # Get decay data
    decay_df = nuclear_module.get_decay_data()
    
    if decay_df.empty:
        print("⚠️  WARNING: No decay data loaded!")
        return
    
    # Check decay modes
    decay_modes = decay_df.index.get_level_values('decay_mode').unique()
    
    print("\n" + "=" * 80)
    print("DECAY MODES FOUND:")
    print("=" * 80)
    for mode in sorted(decay_modes):
        count = len(decay_df.xs(mode, level='decay_mode'))
        print(f"  {mode:10s}: {count:4d} transitions")
    
    # Check specifically for EC
    ec_modes = [m for m in decay_modes if 'EC' in m]
    
    print("\n" + "=" * 80)
    print("EC-RELATED MODES:")
    print("=" * 80)
    if ec_modes:
        print(f"Found {len(ec_modes)} EC-related modes:")
        for mode in sorted(ec_modes):
            count = len(decay_df.xs(mode, level='decay_mode'))
            print(f"  ✅ {mode:10s}: {count:4d} transitions")
            
            # Show sample
            sample = decay_df.xs(mode, level='decay_mode').head(3)
            print(f"     Sample entries:")
            for idx, row in sample.iterrows():
                A, Z, parentLevel, _, final_level = idx
                parent = row['Parent']
                intensity = row['Intensity']
                print(f"       {parent} (A={A}, Z={Z}) -> level {final_level}, intensity={intensity}")
    else:
        print("❌ NO EC-RELATED MODES FOUND!")
        print("\nThis suggests EC decays are not being parsed.")
        print("Possible issues:")
        print("  1. No EC decay files in the directory")
        print("  2. EC files exist but have empty betasTable")
        print("  3. Parser is filtering them out")
    
    print("\n" + "=" * 80)
    print("SUMMARY:")
    print("=" * 80)
    print(f"Total decay transitions: {len(decay_df)}")
    print(f"Total decay modes: {len(decay_modes)}")
    print(f"EC-related modes: {len(ec_modes)}")
    
    if not ec_modes:
        print("\n⚠️  ACTION NEEDED: Run the diagnostic script on your beta-decay directory:")
        print("    python3 diagnose_ensdf_coverage.py --type beta-decay")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test EC parsing in ENSDF JSON data")
    parser.add_argument(
        'json_dir',
        type=str,
        help="Path to ENSDF JSON directory (beta-decay or full directory)"
    )
    
    args = parser.parse_args()
    
    if not os.path.exists(args.json_dir):
        print(f"Error: Directory not found: {args.json_dir}")
        sys.exit(1)
    
    test_ec_parsing(args.json_dir)
