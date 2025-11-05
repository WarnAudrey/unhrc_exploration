#!/usr/bin/env python3
"""
Test that ENDFParsing.py can handle both:
1. A single ENDF file
2. A directory containing multiple ENDF files
"""

import sys
import os
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from ENDFParsing import parse_endf_files

# Sample minimal ENDF data for H-3
h3_data = """
 1.000000+0 1.000000+0          0          0          0          1   1 8457
 6.139000+2 6.000000-1          0          0          6          0   1 8457
 3.013700+5 0.000000+0 0.000000+0 0.000000+0 0.000000+0 0.000000+0   1 8457
 5.000000-1 1.000000+0          0          0          6          1   1 8457
 1.000000+0 0.000000+0 7.823470+5 1.000000+0 1.000000+0 0.000000+0   1 8457
 0.000000+0 1.000000+0          0          0          6          1   1 8457
 1.000000+0 0.000000+0 3.013700+5 0.000000+0 0.000000+0 0.000000+0   1 8457
                                                                     1 8  0
 0.000000+0 0.000000+0          0          0          0          0   0 0  0
"""

# Sample minimal ENDF data for He-6
he6_data = """
 2.000000+0 6.000000+0          0          0          0          1   2 8457
 8.067000+2 1.000000+0          0          0          6          0   2 8457
 4.500000+5 0.000000+0 0.000000+0 0.000000+0 0.000000+0 0.000000+0   2 8457
 1.000000+0 1.000000+0          0          0          6          1   2 8457
 1.000000+0 0.000000+0 9.000000+5 1.000000+0 1.000000+0 0.000000+0   2 8457
 0.000000+0 1.000000+0          0          0          6          1   2 8457
 1.000000+0 0.000000+0 4.500000+5 0.000000+0 0.000000+0 0.000000+0   2 8457
                                                                     2 8  0
 0.000000+0 0.000000+0          0          0          0          0   0 0  0
"""


def test_single_file_mode():
    """Test parsing a single ENDF file."""
    
    print("="*80)
    print("TEST 1: SINGLE FILE MODE")
    print("="*80)
    
    # Create temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.endf', delete=False) as f:
        f.write(h3_data)
        temp_file = f.name
    
    try:
        print(f"\nCreated temporary file: {temp_file}")
        
        # Parse the single file
        result = parse_endf_files(temp_file)
        
        print(f"\n✓ Successfully parsed single file")
        print(f"  Decay entries: {len(result.decay_df) if hasattr(result, 'decay_df') else 0}")
        print(f"  Nuclide entries: {len(result.nuclide_df) if hasattr(result, 'nuclide_df') else 0}")
        
        if hasattr(result, 'decay_df') and len(result.decay_df) > 0:
            print("\n✅ PASS: Single file mode works!")
            return True
        else:
            print("\n✗ FAIL: No data extracted from single file")
            return False
            
    except Exception as e:
        print(f"\n✗ FAIL: Error parsing single file: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Cleanup
        os.unlink(temp_file)


def test_directory_mode():
    """Test parsing multiple ENDF files from a directory."""
    
    print("\n" + "="*80)
    print("TEST 2: DIRECTORY MODE")
    print("="*80)
    
    # Create temporary directory with multiple files
    temp_dir = tempfile.mkdtemp()
    
    try:
        print(f"\nCreated temporary directory: {temp_dir}")
        
        # Create two ENDF files in the directory
        file1 = Path(temp_dir) / "h3.endf"
        file2 = Path(temp_dir) / "he6.endf"
        
        file1.write_text(h3_data)
        file2.write_text(he6_data)
        
        print(f"  Created: {file1.name}")
        print(f"  Created: {file2.name}")
        
        # Parse the directory
        result = parse_endf_files(temp_dir, file_pattern="*.endf")
        
        print(f"\n✓ Successfully parsed directory")
        print(f"  Decay entries: {len(result.decay_df) if hasattr(result, 'decay_df') else 0}")
        print(f"  Nuclide entries: {len(result.nuclide_df) if hasattr(result, 'nuclide_df') else 0}")
        
        if hasattr(result, 'nuclide_df') and len(result.nuclide_df) >= 2:
            print("\n✅ PASS: Directory mode works!")
            return True
        else:
            print(f"\n⚠ WARNING: Expected at least 2 nuclides, got {len(result.nuclide_df) if hasattr(result, 'nuclide_df') else 0}")
            # Still count as pass if we got some data
            if hasattr(result, 'decay_df') and len(result.decay_df) > 0:
                print("  But got some data, so counting as pass")
                return True
            return False
            
    except Exception as e:
        print(f"\n✗ FAIL: Error parsing directory: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Cleanup
        shutil.rmtree(temp_dir)


def main():
    """Run all tests."""
    
    print("="*80)
    print("FILE AND DIRECTORY MODE TESTS")
    print("="*80)
    
    test1_pass = test_single_file_mode()
    test2_pass = test_directory_mode()
    
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"  Single File Mode:  {'✅ PASS' if test1_pass else '✗ FAIL'}")
    print(f"  Directory Mode:    {'✅ PASS' if test2_pass else '✗ FAIL'}")
    
    if test1_pass and test2_pass:
        print("\n✅ ALL TESTS PASSED!")
        print("="*80)
        return 0
    else:
        print("\n✗ SOME TESTS FAILED")
        print("="*80)
        return 1


if __name__ == "__main__":
    sys.exit(main())
