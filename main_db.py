#!/usr/bin/env python3
"""
Main execution script for nuclear database processing.
Handles both JSON (ENSDF) and legacy database workflows.
"""

import os
import sys
import argparse
from pathlib import Path

# Add project root to path if needed
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from PyClasses.JSONParsing import NuclearDataModule
from PyClasses.DataModule import DataModule
from PyClasses.DBConfig import DBConfig
import PyClasses.configuration_file as config_file


def process_json(json_dirs, output_dir, config_type='dmf5'):
    """
    Process JSON nuclear data files and populate data modules.
    
    Parameters:
    -----------
    json_dirs : list of str
        Paths to JSON data directories (adopted, beta-decay, alpha-decay, delayed-particle-decay)
    output_dir : str
        Output directory for ASCII files
    config_type : str
        Configuration type to use ('dmf5' for JSON, 'dm' for legacy)
    """
    print("=" * 80)
    print("NUCLEAR DATABASE JSON PROCESSING")
    print("=" * 80)
    
    # Validate input directories
    for json_dir in json_dirs:
        if not os.path.exists(json_dir):
            print(f"ERROR: Directory not found: {json_dir}")
            return False
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    print(f"\nOutput directory: {output_dir}")
    
    # Step 1: Load JSON data using NuclearDataModule
    print("\n" + "=" * 80)
    print("STEP 1: Loading JSON data from ENSDF files")
    print("=" * 80)
    
    # Pass all directories to NuclearDataModule (it auto-loads and splits EC/β+)
    nuclear_data = NuclearDataModule(*json_dirs, auto_save_ascii=False)
    
    # The EC/β+ splitting has already happened automatically in load_data()
    # Display what was loaded
    nuclear_data.display_summary()
    
    # Step 2: Initialize database configuration
    print("\n" + "=" * 80)
    print("STEP 2: Initializing database configuration")
    print("=" * 80)
    
    # Load the configuration (dmf5 for JSON, dm for legacy)
    if config_type == 'dmf5':
        print("Using JSON configuration (dmf5)...")
        db_config = DBConfig(
            db=config_file.dbf5,
            dm=config_file.dmf5,
            lgcy={'parameters': {}, 'F4_only_variables': {}, 'records_list': []}
        )
    else:
        print("Using legacy configuration (dm)...")
        db_config = DBConfig(
            db=config_file.db,
            dm=config_file.dm,
            lgcy=config_file.lgcy
        )
    
    # Step 3: Populate data modules from nuclear data
    print("\n" + "=" * 80)
    print("STEP 3: Populating data modules")
    print("=" * 80)
    
    data_modules = {}
    module_names = ['LEVEL', 'TRANSITION', 'DECAY', 'NUCLIDE']
    
    for dm_name in module_names:
        print(f"\nProcessing {dm_name} module...")
        try:
            # Create data module instance
            dm = DataModule(dm_name, db_config)
            
            # Populate from nuclear data (EC/β+ already split)
            dm.populate_DM_from_nuclear_data(nuclear_data)
            
            # Store for later use
            data_modules[dm_name] = dm
            
            print(f"  ✓ {dm_name}: {len(dm.C)} records")
            
        except Exception as e:
            print(f"  ✗ Error processing {dm_name}: {e}")
            import traceback
            traceback.print_exc()
    
    # Step 4: Save to ASCII files
    print("\n" + "=" * 80)
    print("STEP 4: Saving to ASCII files")
    print("=" * 80)
    
    for dm_name, dm in data_modules.items():
        if not dm.C.empty:
            output_file = os.path.join(output_dir, f"{dm_name.lower()}.txt")
            print(f"\nWriting {dm_name} to {output_file}...")
            
            try:
                # Use custom JSON formatter for clean output
                dm.print_to_ascii(
                    filename=output_file,
                    float_format=lambda x: "%1.4e" % x,
                    custom_formatter=NuclearDataModule.json_ascii_formatter
                )
                print(f"  ✓ Saved {len(dm.C)} records")
                
            except Exception as e:
                print(f"  ✗ Error saving {dm_name}: {e}")
                import traceback
                traceback.print_exc()
    
    print("\n" + "=" * 80)
    print("PROCESSING COMPLETE")
    print("=" * 80)
    print(f"\nOutput files written to: {output_dir}")
    
    # Display EC/β+ split statistics
    if 'DECAY' in data_modules:
        decay_dm = data_modules['DECAY']
        if not decay_dm.C.empty:
            print("\nDecay mode statistics:")
            # For dmf5, decay_mode is in the index
            if hasattr(decay_dm.C.index, 'get_level_values'):
                try:
                    decay_modes = decay_dm.C.index.get_level_values('decay_mode').unique()
                    for mode in sorted(decay_modes):
                        count = len(decay_dm.C.xs(mode, level='decay_mode'))
                        print(f"  {mode}: {count} transitions")
                except:
                    # For legacy format, decay mode is a column
                    if 'Decay' in decay_dm.C.columns:
                        for mode in sorted(decay_dm.C['Decay'].unique()):
                            count = len(decay_dm.C[decay_dm.C['Decay'] == mode])
                            print(f"  {mode}: {count} transitions")
    
    return True


def main():
    """Main entry point with command-line argument parsing."""
    parser = argparse.ArgumentParser(
        description='Nuclear Database Processing Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process all JSON data from parent directory (EASIEST)
  python main_db.py process_json \\
    --json-dir /Users/audreywarn/fluka-db-audrey/data_input/ensdf/json_070125 \\
    --output ./output_data/
  
  # Or specify individual directories
  python main_db.py process_json \\
    --adopted /path/to/adopted/ \\
    --beta /path/to/beta-decay/ \\
    --alpha /path/to/alpha-decay/ \\
    --delayed /path/to/delayed-particle-decay/ \\
    --output ./output_data/
  
  # Use specific configuration
  python main_db.py process_json --json-dir /path/to/json/ --config dmf5
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # JSON processing command
    json_parser = subparsers.add_parser('process_json', help='Process JSON nuclear data files')
    
    # Option 1: Single parent directory (auto-discovers subdirectories)
    json_parser.add_argument('--json-dir', help='Path to parent JSON directory (auto-discovers subdirectories)')
    
    # Option 2: Individual directories
    json_parser.add_argument('--adopted', help='Path to adopted levels JSON directory')
    json_parser.add_argument('--beta', help='Path to beta-decay JSON directory')
    json_parser.add_argument('--alpha', help='Path to alpha-decay JSON directory')
    json_parser.add_argument('--delayed', help='Path to delayed-particle-decay JSON directory')
    
    json_parser.add_argument('--output', default='./nuclear_data_output', help='Output directory for ASCII files')
    json_parser.add_argument('--config', choices=['dmf5', 'dm'], default='dmf5', 
                           help='Configuration type (dmf5=JSON, dm=legacy)')
    
    args = parser.parse_args()
    
    if args.command == 'process_json':
        json_dirs = []
        
        # Option 1: Auto-discover from parent directory
        if args.json_dir:
            parent_dir = Path(args.json_dir)
            if not parent_dir.exists():
                print(f"ERROR: Directory not found: {args.json_dir}")
                sys.exit(1)
            
            print(f"Auto-discovering JSON subdirectories in: {args.json_dir}")
            
            # Look for standard ENSDF subdirectories
            subdirs = {
                'adopted': ['adopted', 'adopted-levels'],
                'beta': ['beta-decay', 'beta_decay'],
                'alpha': ['alpha-decay', 'alpha_decay'],
                'delayed': ['delayed-particle-decay', 'delayed_particle_decay', 'delayed-particle']
            }
            
            for data_type, possible_names in subdirs.items():
                for name in possible_names:
                    subdir = parent_dir / name
                    if subdir.exists() and subdir.is_dir():
                        json_dirs.append(str(subdir))
                        print(f"  Found {data_type}: {subdir}")
                        break
            
            if not json_dirs:
                print(f"ERROR: No recognized subdirectories found in {args.json_dir}")
                print("Expected subdirectories: adopted/, beta-decay/, alpha-decay/, delayed-particle-decay/")
                sys.exit(1)
        
        # Option 2: Use individually specified directories
        else:
            if not args.adopted:
                print("ERROR: Must specify either --json-dir or --adopted")
                json_parser.print_help()
                sys.exit(1)
            
            json_dirs = [args.adopted]
            if args.beta:
                json_dirs.append(args.beta)
            if args.alpha:
                json_dirs.append(args.alpha)
            if args.delayed:
                json_dirs.append(args.delayed)
        
        # Run processing
        success = process_json(json_dirs, args.output, args.config)
        sys.exit(0 if success else 1)
    
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
