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
    """
    try:
        # Read the file with whitespace delimiter
        df = pd.read_csv(filepath, delim_whitespace=True)
        
        # If A and Z are in the index, reset it
        if df.index.nlevels > 1:
            df = df.reset_index()
        
        return df
    
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return None

def extract_nuclides_and_modes(df):
    """
    Extract unique nuclides and their decay modes from the dataframe.
    Returns:
        - nuclides: set of (Z, A) tuples
        - decay_data: dict mapping (Z, A) to list of decay modes
    """
    nuclides = set()
    decay_data = defaultdict(list)
    
    # Try to identify A and Z columns
    cols = df.columns.tolist()
    a_col = None
    z_col = None
    mode_col = None
    
    # Look for column names
    for col in cols:
        col_lower = str(col).lower()
        if 'a' == col_lower or col_lower == 'mass':
            a_col = col
        elif 'z' == col_lower or col_lower == 'atomic' or col_lower == 'proton':
            z_col = col
        elif 'mode' in col_lower or 'decay' in col_lower:
            mode_col = col
    
    # If not found by name, assume first two columns
    if a_col is None or z_col is None:
        if len(cols) >= 2:
            a_col = cols[0]  # Usually A comes first
            z_col = cols[1]  # Then Z
    
    # Look for mode column if not found
    if mode_col is None:
        for col in cols[2:]:  # Skip A and Z
            if df[col].dtype == 'object':  # Decay modes are usually strings
                mode_col = col
                break
    
    print(f"  Detected columns: A={a_col}, Z={z_col}, Mode={mode_col}")
    
    # Extract data
    for idx, row in df.iterrows():
        try:
            a = int(row[a_col])
            z = int(row[z_col])
            nuclide = (z, a)
            nuclides.add(nuclide)
            
            # Extract decay mode if available
            if mode_col is not None and pd.notna(row[mode_col]):
                mode = str(row[mode_col]).strip()
                if mode and mode.lower() not in ['nan', 'none', '']:
                    decay_data[nuclide].append(mode)
            
            # Also check for branching ratio columns and other decay-related columns
            for col in cols:
                col_str = str(col).lower()
                if any(x in col_str for x in ['br', 'branch', 'fraction', 'percent']):
                    # This might indicate additional decay channel info
                    pass
                    
        except (ValueError, KeyError, TypeError) as e:
            continue
    
    return nuclides, decay_data

def print_decay_mode_statistics(nuclides, decay_data, label, file_handle):
    """
    Write statistics about decay modes for a set of nuclides to file.
    """
    file_handle.write(f"\n{'='*70}\n")
    file_handle.write(f"DECAY MODE STATISTICS: {label}\n")
    file_handle.write(f"{'='*70}\n")
    file_handle.write(f"Total nuclides: {len(nuclides)}\n")
    
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
    if len(endf_nuclides) > 0:
        f.write(f"ENDF:  {endf_with_modes}/{len(endf_nuclides)} nuclides have decay mode data ({endf_with_modes/len(endf_nuclides)*100:.1f}%)\n")
    
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
