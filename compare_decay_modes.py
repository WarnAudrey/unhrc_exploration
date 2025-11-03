import pandas as pd
import numpy as np
from collections import Counter, defaultdict

# File paths
ensdf_path = '/Users/audreywarn/fluka-db-audrey/outputs/ensdf/json_data_modules/ascii/DECAY.ascii'
endf_path = '/Users/audreywarn/fluka-db-audrey/outputs/endf/endf_data_modules/ascii/DECAY.ascii'
output_path = '/Users/audreywarn/fluka-db-audrey/outputs/decay_mode_statistics.txt'

def read_decay_data_with_modes(filepath):
    """
    Read decay data from ASCII file and return DataFrame with decay modes.
    The data typically has a MultiIndex with (A, Z, parentLevel, decay_mode, final_level).
    """
    try:
        # Try reading with pandas directly - it might handle the MultiIndex
        df = pd.read_csv(filepath, sep=r'\s+', header=0)
        
        # Check if we need to reset the index to access A, Z, decay_mode
        if df.index.nlevels > 1:
            # MultiIndex case - reset to get all index levels as columns
            df = df.reset_index()
        
        return df
    
    except Exception as e:
        print(f"Error with pandas read: {e}")
        print("Trying alternative parsing...")
        
        # Alternative: read line by line and parse the MultiIndex structure
        try:
            lines = []
            
            with open(filepath, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    parts = line.split()
                    lines.append(parts)
            
            if not lines:
                print(f"No data found in {filepath}")
                return None
            
            # First line should be the header
            # It looks like: "Parent Endpoint_energy Average_energy Intensity" (or similar)
            # But we need to extract the MultiIndex columns from the data
            
            # Check if first line is a header (contains non-numeric values)
            first_line = lines[0]
            is_header = False
            try:
                float(first_line[0])
            except (ValueError, TypeError):
                is_header = True
            
            # Skip header if present
            data_start = 1 if is_header else 0
            
            # Parse data rows
            # Expected format: A Z parentLevel decay_mode final_level [data columns...]
            # The first 5 columns form the MultiIndex
            data_rows = []
            for line in lines[data_start:]:
                if len(line) >= 5:
                    # Extract A, Z, parentLevel, decay_mode, final_level
                    a = line[0]
                    z = line[1]
                    parent_level = line[2]
                    decay_mode = line[3]
                    final_level = line[4]
                    # Rest are data columns
                    data_cols = line[5:] if len(line) > 5 else []
                    
                    data_rows.append({
                        'A': a,
                        'Z': z,
                        'parentLevel': parent_level,
                        'decay_mode': decay_mode,
                        'final_level': final_level,
                        'data': data_cols
                    })
            
            # Create DataFrame
            df = pd.DataFrame(data_rows)
            
            return df
        
        except Exception as e2:
            print(f"Error reading {filepath}: {e2}")
            import traceback
            traceback.print_exc()
            return None

def extract_nuclides_and_modes(df):
    """
    Extract unique nuclides and their decay modes from the dataframe.
    The dataframe should have columns like A, Z, parentLevel, decay_mode, final_level
    (from the MultiIndex that was reset).
    Returns:
        - nuclides: set of (Z, A) tuples
        - decay_data: dict mapping (Z, A) to list of decay modes
    """
    nuclides = set()
    decay_data = defaultdict(list)
    
    # Try to identify A, Z, and decay_mode columns
    cols = df.columns.tolist()
    print(f"  Available columns: {cols[:10]}...")  # Print first 10 columns
    
    a_col = None
    z_col = None
    mode_col = None
    
    # Look for column names (case-insensitive)
    for col in cols:
        col_str = str(col)
        col_lower = col_str.lower()
        
        if col_lower == 'a' or col_lower == 'mass':
            a_col = col
        elif col_lower == 'z' or col_lower == 'atomic' or col_lower == 'proton':
            z_col = col
        elif 'decay_mode' in col_lower or col_lower == 'decay' or col_lower == 'mode':
            mode_col = col
    
    # If not found by name, try positional (A is typically first, Z is second)
    if a_col is None and len(cols) > 0:
        a_col = cols[0]
    if z_col is None and len(cols) > 1:
        z_col = cols[1]
    
    print(f"  Detected columns: A={a_col}, Z={z_col}, Mode={mode_col}")
    print(f"  Total rows: {len(df)}")
    
    if mode_col is None:
        print("  WARNING: No decay_mode column found!")
        print(f"  All columns: {cols}")
    
    # Extract data - aggregate by nuclide (Z, A)
    parsed_count = 0
    nuclide_modes_sets = defaultdict(set)  # Use set to avoid duplicate modes per nuclide
    
    for idx, row in df.iterrows():
        try:
            a_val = str(row[a_col]).strip()
            z_val = str(row[z_col]).strip()
            
            if not a_val or not z_val or a_val == 'nan' or z_val == 'nan':
                continue
                
            a = int(float(a_val))
            z = int(float(z_val))
            nuclide = (z, a)
            nuclides.add(nuclide)
            parsed_count += 1
            
            # Extract decay mode
            if mode_col is not None:
                mode_val = str(row[mode_col]).strip()
                if mode_val and mode_val.lower() not in ['nan', 'none', '', 'n/a']:
                    # Clean the mode value
                    nuclide_modes_sets[nuclide].add(mode_val)
                    
        except (ValueError, KeyError, TypeError) as e:
            continue
    
    # Convert sets to lists for decay_data
    for nuclide, modes_set in nuclide_modes_sets.items():
        decay_data[nuclide] = list(modes_set)
    
    print(f"  Total rows processed: {parsed_count}")
    print(f"  Unique nuclides: {len(nuclides)}")
    print(f"  Nuclides with decay modes: {sum(1 for n in nuclides if n in decay_data and decay_data[n])}")
    
    return nuclides, decay_data

def print_decay_mode_statistics(nuclides, decay_data, label, file_handle):
    """
    Write statistics about decay modes for a set of nuclides to file.
    """
    file_handle.write(f"\n{'='*70}\n")
    file_handle.write(f"DECAY MODE STATISTICS: {label}\n")
    file_handle.write(f"{'='*70}\n")
    file_handle.write(f"Total nuclides: {len(nuclides)}\n")
    
    if len(nuclides) == 0:
        file_handle.write("No nuclides in this category.\n")
        return
    
    # Count nuclides with decay mode information
    nuclides_with_modes = [n for n in nuclides if n in decay_data and decay_data[n]]
    file_handle.write(f"Nuclides with decay mode data: {len(nuclides_with_modes)} ({len(nuclides_with_modes)/len(nuclides)*100:.1f}%)\n")
    
    if not nuclides_with_modes:
        file_handle.write("No decay mode information available for these nuclides.\n")
        return
    
    # Collect all decay modes
    all_modes = []
    for nuclide in nuclides_with_modes:
        all_modes.extend(decay_data[nuclide])
    
    # Count decay modes
    mode_counts = Counter(all_modes)
    
    file_handle.write(f"\nTotal decay mode entries: {len(all_modes)}\n")
    file_handle.write(f"Unique decay modes: {len(mode_counts)}\n")
    
    # Print top decay modes
    file_handle.write(f"\nTop 20 decay modes:\n")
    file_handle.write(f"{'Decay Mode':<30} {'Count':>10} {'Percentage':>12}\n")
    file_handle.write("-" * 55 + "\n")
    for mode, count in mode_counts.most_common(20):
        percentage = count / len(all_modes) * 100
        file_handle.write(f"{mode:<30} {count:>10} {percentage:>11.2f}%\n")
    
    # Statistics by decay type categories
    file_handle.write(f"\nDecay type categories:\n")
    categories = {
        'Beta Decay': ['B-', 'B+', 'EC', 'BETA', 'beta'],
        'Alpha Decay': ['A', 'ALPHA', 'alpha'],
        'Spontaneous Fission': ['SF', 'FISSION', 'fission'],
        'Proton Emission': ['P', 'PROTON', 'proton'],
        'Neutron Emission': ['N', 'NEUTRON', 'neutron'],
        'Stable': ['STABLE', 'stable', 'IS']
    }
    
    category_counts = defaultdict(int)
    for mode in all_modes:
        mode_upper = mode.upper()
        categorized = False
        for category, keywords in categories.items():
            if any(kw.upper() in mode_upper for kw in keywords):
                category_counts[category] += 1
                categorized = True
                break
        if not categorized:
            category_counts['Other'] += 1
    
    file_handle.write(f"{'Category':<25} {'Count':>10} {'Percentage':>12}\n")
    file_handle.write("-" * 50 + "\n")
    for category in sorted(category_counts.keys()):
        count = category_counts[category]
        percentage = count / len(all_modes) * 100
        file_handle.write(f"{category:<25} {count:>10} {percentage:>11.2f}%\n")
    
    # Multi-mode decay statistics
    multi_mode_nuclides = [n for n in nuclides_with_modes if len(decay_data[n]) > 1]
    file_handle.write(f"\nNuclides with multiple decay modes: {len(multi_mode_nuclides)} ({len(multi_mode_nuclides)/len(nuclides_with_modes)*100:.1f}%)\n")
    
    # Distribution of number of decay modes per nuclide
    modes_per_nuclide = [len(decay_data[n]) for n in nuclides_with_modes]
    file_handle.write(f"\nDecay modes per nuclide:\n")
    file_handle.write(f"  Mean: {np.mean(modes_per_nuclide):.2f}\n")
    file_handle.write(f"  Median: {np.median(modes_per_nuclide):.2f}\n")
    file_handle.write(f"  Max: {np.max(modes_per_nuclide)}\n")
    
    modes_dist = Counter(modes_per_nuclide)
    file_handle.write(f"\nDistribution:\n")
    file_handle.write(f"{'# Modes':>10} {'# Nuclides':>12} {'Percentage':>12}\n")
    file_handle.write("-" * 36 + "\n")
    for n_modes in sorted(modes_dist.keys())[:10]:  # Show up to 10 different values
        count = modes_dist[n_modes]
        percentage = count / len(nuclides_with_modes) * 100
        file_handle.write(f"{n_modes:>10} {count:>12} {percentage:>11.2f}%\n")


# Main execution
print("="*70)
print("NUCLEAR DECAY DATA COMPARISON AND ANALYSIS")
print("="*70)

print("\n[1/4] Reading ENSDF data...")
ensdf_df = read_decay_data_with_modes(ensdf_path)
if ensdf_df is not None:
    ensdf_nuclides, ensdf_decay_data = extract_nuclides_and_modes(ensdf_df)
    print(f"Found {len(ensdf_nuclides)} unique nuclides in ENSDF")
else:
    ensdf_nuclides, ensdf_decay_data = set(), {}
    print("Failed to read ENSDF data")

print("\n[2/4] Reading ENDF data...")
endf_df = read_decay_data_with_modes(endf_path)
if endf_df is not None:
    endf_nuclides, endf_decay_data = extract_nuclides_and_modes(endf_df)
    print(f"Found {len(endf_nuclides)} unique nuclides in ENDF")
else:
    endf_nuclides, endf_decay_data = set(), {}
    print("Failed to read ENDF data")

# Find common and unique nuclides
common_nuclides = ensdf_nuclides & endf_nuclides
ensdf_only = ensdf_nuclides - endf_nuclides
endf_only = endf_nuclides - ensdf_nuclides

print(f"\n[3/4] Nuclide overlap analysis:")
print(f"  Common nuclides: {len(common_nuclides)}")
print(f"  ENSDF only: {len(ensdf_only)}")
print(f"  ENDF only: {len(endf_only)}")
print(f"  Total unique: {len(ensdf_nuclides | endf_nuclides)}")

# Write all statistics to file
print(f"\n[4/4] Writing statistics to {output_path}...")

with open(output_path, 'w') as f:
    f.write("="*70 + "\n")
    f.write("NUCLEAR DECAY DATA COMPARISON AND ANALYSIS\n")
    f.write("="*70 + "\n")
    
    f.write(f"\nDATA SOURCES:\n")
    f.write(f"  ENSDF: {ensdf_path}\n")
    f.write(f"  ENDF:  {endf_path}\n")
    
    f.write(f"\nNUCLIDE OVERLAP ANALYSIS:\n")
    f.write(f"  ENSDF nuclides: {len(ensdf_nuclides)}\n")
    f.write(f"  ENDF nuclides:  {len(endf_nuclides)}\n")
    f.write(f"  Common nuclides: {len(common_nuclides)}\n")
    f.write(f"  ENSDF only: {len(ensdf_only)}\n")
    f.write(f"  ENDF only: {len(endf_only)}\n")
    f.write(f"  Total unique: {len(ensdf_nuclides | endf_nuclides)}\n")
    
    # Print decay mode statistics for each category
    if ensdf_only:
        print_decay_mode_statistics(ensdf_only, ensdf_decay_data, "ENSDF-ONLY NUCLIDES", f)
    
    if endf_only:
        print_decay_mode_statistics(endf_only, endf_decay_data, "ENDF-ONLY NUCLIDES", f)
    
    if common_nuclides:
        print_decay_mode_statistics(common_nuclides, ensdf_decay_data, "COMMON NUCLIDES (ENSDF data)", f)
        print_decay_mode_statistics(common_nuclides, endf_decay_data, "COMMON NUCLIDES (ENDF data)", f)
    
    # Overall statistics
    print_decay_mode_statistics(ensdf_nuclides, ensdf_decay_data, "ALL ENSDF NUCLIDES", f)
    print_decay_mode_statistics(endf_nuclides, endf_decay_data, "ALL ENDF NUCLIDES", f)
    
    # Comparison of decay mode coverage
    f.write(f"\n{'='*70}\n")
    f.write(f"DECAY MODE COVERAGE COMPARISON\n")
    f.write(f"{'='*70}\n")
    
    ensdf_with_modes = sum(1 for n in ensdf_nuclides if n in ensdf_decay_data and ensdf_decay_data[n])
    endf_with_modes = sum(1 for n in endf_nuclides if n in endf_decay_data and endf_decay_data[n])
    
    if len(ensdf_nuclides) > 0:
        f.write(f"\nENSDF: {ensdf_with_modes}/{len(ensdf_nuclides)} nuclides have decay mode data ({ensdf_with_modes/len(ensdf_nuclides)*100:.1f}%)\n")
    else:
        f.write(f"\nENSDF: No nuclides found\n")
    
    if len(endf_nuclides) > 0:
        f.write(f"ENDF:  {endf_with_modes}/{len(endf_nuclides)} nuclides have decay mode data ({endf_with_modes/len(endf_nuclides)*100:.1f}%)\n")
    else:
        f.write(f"ENDF:  No nuclides found\n")
    
    # For common nuclides, compare decay mode agreement
    if common_nuclides:
        f.write(f"\nFor {len(common_nuclides)} common nuclides:\n")
        both_have_modes = sum(1 for n in common_nuclides 
                              if n in ensdf_decay_data and ensdf_decay_data[n] 
                              and n in endf_decay_data and endf_decay_data[n])
        only_ensdf_has_modes = sum(1 for n in common_nuclides 
                                   if n in ensdf_decay_data and ensdf_decay_data[n] 
                                   and (n not in endf_decay_data or not endf_decay_data[n]))
        only_endf_has_modes = sum(1 for n in common_nuclides 
                                  if n in endf_decay_data and endf_decay_data[n] 
                                  and (n not in ensdf_decay_data or not ensdf_decay_data[n]))
        neither_has_modes = len(common_nuclides) - both_have_modes - only_ensdf_has_modes - only_endf_has_modes
        
        f.write(f"  Both sources have mode data: {both_have_modes} ({both_have_modes/len(common_nuclides)*100:.1f}%)\n")
        f.write(f"  Only ENSDF has mode data: {only_ensdf_has_modes} ({only_ensdf_has_modes/len(common_nuclides)*100:.1f}%)\n")
        f.write(f"  Only ENDF has mode data: {only_endf_has_modes} ({only_endf_has_modes/len(common_nuclides)*100:.1f}%)\n")
        f.write(f"  Neither has mode data: {neither_has_modes} ({neither_has_modes/len(common_nuclides)*100:.1f}%)\n")
    
    f.write(f"\n{'='*70}\n")
    f.write("ANALYSIS COMPLETE\n")
    f.write(f"{'='*70}\n")

print(f"\nStatistics written to: {output_path}")
print("\nScript completed successfully!")
