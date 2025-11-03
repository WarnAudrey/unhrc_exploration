import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from collections import Counter, defaultdict

# File paths
ensdf_path = '/Users/audreywarn/fluka-db-audrey/outputs/ensdf/json_data_modules/ascii/DECAY.ascii'
endf_path = '/Users/audreywarn/fluka-db-audrey/outputs/endf/endf_data_modules/ascii/DECAY.ascii'

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

def print_decay_mode_statistics(nuclides, decay_data, label):
    """
    Print statistics about decay modes for a set of nuclides.
    """
    print(f"\n{'='*70}")
    print(f"DECAY MODE STATISTICS: {label}")
    print(f"{'='*70}")
    print(f"Total nuclides: {len(nuclides)}")
    
    # Count nuclides with decay mode information
    nuclides_with_modes = [n for n in nuclides if n in decay_data and decay_data[n]]
    print(f"Nuclides with decay mode data: {len(nuclides_with_modes)} ({len(nuclides_with_modes)/len(nuclides)*100:.1f}%)")
    
    if not nuclides_with_modes:
        print("No decay mode information available for these nuclides.")
        return
    
    # Collect all decay modes
    all_modes = []
    for nuclide in nuclides_with_modes:
        all_modes.extend(decay_data[nuclide])
    
    # Count decay modes
    mode_counts = Counter(all_modes)
    
    print(f"\nTotal decay mode entries: {len(all_modes)}")
    print(f"Unique decay modes: {len(mode_counts)}")
    
    # Print top decay modes
    print(f"\nTop 20 decay modes:")
    print(f"{'Decay Mode':<30} {'Count':>10} {'Percentage':>12}")
    print("-" * 55)
    for mode, count in mode_counts.most_common(20):
        percentage = count / len(all_modes) * 100
        print(f"{mode:<30} {count:>10} {percentage:>11.2f}%")
    
    # Statistics by decay type categories
    print(f"\nDecay type categories:")
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
    
    print(f"{'Category':<25} {'Count':>10} {'Percentage':>12}")
    print("-" * 50)
    for category in sorted(category_counts.keys()):
        count = category_counts[category]
        percentage = count / len(all_modes) * 100
        print(f"{category:<25} {count:>10} {percentage:>11.2f}%")
    
    # Multi-mode decay statistics
    multi_mode_nuclides = [n for n in nuclides_with_modes if len(decay_data[n]) > 1]
    print(f"\nNuclides with multiple decay modes: {len(multi_mode_nuclides)} ({len(multi_mode_nuclides)/len(nuclides_with_modes)*100:.1f}%)")
    
    # Distribution of number of decay modes per nuclide
    modes_per_nuclide = [len(decay_data[n]) for n in nuclides_with_modes]
    print(f"\nDecay modes per nuclide:")
    print(f"  Mean: {np.mean(modes_per_nuclide):.2f}")
    print(f"  Median: {np.median(modes_per_nuclide):.2f}")
    print(f"  Max: {np.max(modes_per_nuclide)}")
    
    modes_dist = Counter(modes_per_nuclide)
    print(f"\nDistribution:")
    print(f"{'# Modes':>10} {'# Nuclides':>12} {'Percentage':>12}")
    print("-" * 36)
    for n_modes in sorted(modes_dist.keys())[:10]:  # Show up to 10 different values
        count = modes_dist[n_modes]
        percentage = count / len(nuclides_with_modes) * 100
        print(f"{n_modes:>10} {count:>12} {percentage:>11.2f}%")


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

# Print decay mode statistics for each category
print("\n[4/4] Analyzing decay modes...\n")

if ensdf_only:
    print_decay_mode_statistics(ensdf_only, ensdf_decay_data, "ENSDF-ONLY NUCLIDES")

if endf_only:
    print_decay_mode_statistics(endf_only, endf_decay_data, "ENDF-ONLY NUCLIDES")

if common_nuclides:
    print_decay_mode_statistics(common_nuclides, ensdf_decay_data, "COMMON NUCLIDES (ENSDF data)")
    print_decay_mode_statistics(common_nuclides, endf_decay_data, "COMMON NUCLIDES (ENDF data)")

# Overall statistics
print_decay_mode_statistics(ensdf_nuclides, ensdf_decay_data, "ALL ENSDF NUCLIDES")
print_decay_mode_statistics(endf_nuclides, endf_decay_data, "ALL ENDF NUCLIDES")

# Comparison of decay mode coverage
print(f"\n{'='*70}")
print(f"DECAY MODE COVERAGE COMPARISON")
print(f"{'='*70}")

ensdf_with_modes = sum(1 for n in ensdf_nuclides if n in ensdf_decay_data and ensdf_decay_data[n])
endf_with_modes = sum(1 for n in endf_nuclides if n in endf_decay_data and endf_decay_data[n])

print(f"\nENSDF: {ensdf_with_modes}/{len(ensdf_nuclides)} nuclides have decay mode data ({ensdf_with_modes/len(ensdf_nuclides)*100:.1f}%)")
print(f"ENDF:  {endf_with_modes}/{len(endf_nuclides)} nuclides have decay mode data ({endf_with_modes/len(endf_nuclides)*100:.1f}%)")

# For common nuclides, compare decay mode agreement
if common_nuclides:
    print(f"\nFor {len(common_nuclides)} common nuclides:")
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
    
    print(f"  Both sources have mode data: {both_have_modes} ({both_have_modes/len(common_nuclides)*100:.1f}%)")
    print(f"  Only ENSDF has mode data: {only_ensdf_has_modes} ({only_ensdf_has_modes/len(common_nuclides)*100:.1f}%)")
    print(f"  Only ENDF has mode data: {only_endf_has_modes} ({only_endf_has_modes/len(common_nuclides)*100:.1f}%)")
    print(f"  Neither has mode data: {neither_has_modes} ({neither_has_modes/len(common_nuclides)*100:.1f}%)")

print(f"\n{'='*70}")
print("ANALYSIS COMPLETE")
print(f"{'='*70}")

# Now create the visualization
print("\n\nCreating visualization...")

# Convert to arrays for plotting
def nuclides_to_arrays(nuclides):
    """Convert set of (Z, A) tuples to Z, N, A arrays"""
    if not nuclides:
        return np.array([]), np.array([]), np.array([])
    z_vals = np.array([z for z, a in nuclides])
    a_vals = np.array([a for z, a in nuclides])
    n_vals = a_vals - z_vals
    return z_vals, n_vals, a_vals

z_common, n_common, a_common = nuclides_to_arrays(common_nuclides)
z_ensdf, n_ensdf, a_ensdf = nuclides_to_arrays(ensdf_only)
z_endf, n_endf, a_endf = nuclides_to_arrays(endf_only)

# Create the plot
fig, ax = plt.subplots(figsize=(14, 10))

# Plot nuclides with different colors and markers
if len(endf_only) > 0:
    ax.scatter(n_endf, z_endf, c='#FF6B6B', marker='s', s=30, 
               label=f'ENDF only (n={len(endf_only)})', alpha=0.8, edgecolors='darkred', linewidths=0.3)

if len(ensdf_only) > 0:
    ax.scatter(n_ensdf, z_ensdf, c='#4ECDC4', marker='^', s=30, 
               label=f'ENSDF only (n={len(ensdf_only)})', alpha=0.8, edgecolors='darkblue', linewidths=0.3)

if len(common_nuclides) > 0:
    ax.scatter(n_common, z_common, c='#95E1D3', marker='o', s=30, 
               label=f'Common (n={len(common_nuclides)})', alpha=0.9, edgecolors='darkgreen', linewidths=0.3)

# Add labels and title
ax.set_xlabel('Neutron Number (N = A - Z)', fontsize=14, fontweight='bold')
ax.set_ylabel('Proton Number (Z)', fontsize=14, fontweight='bold')
ax.set_title('Comparison of ENDF and ENSDF Nuclear Data Sources', fontsize=16, fontweight='bold', pad=20)

# Grid for better readability
ax.grid(True, alpha=0.3, linestyle='--', linewidth=0.5)

# Legend
ax.legend(loc='upper left', fontsize=11, framealpha=0.9)

# Set axis limits with some padding
if len(ensdf_nuclides) + len(endf_nuclides) > 0:
    all_n = np.concatenate([n_common, n_ensdf, n_endf])
    all_z = np.concatenate([z_common, z_ensdf, z_endf])
    
    if len(all_n) > 0 and len(all_z) > 0:
        n_range = all_n.max() - all_n.min()
        z_range = all_z.max() - all_z.min()
        
        ax.set_xlim(all_n.min() - 0.05*n_range, all_n.max() + 0.05*n_range)
        ax.set_ylim(all_z.min() - 0.05*z_range, all_z.max() + 0.05*z_range)

# Add some statistics as text
stats_text = f"Total unique nuclides: {len(ensdf_nuclides | endf_nuclides)}\n"
if len(ensdf_nuclides | endf_nuclides) > 0:
    stats_text += f"Coverage overlap: {len(common_nuclides)/(len(ensdf_nuclides | endf_nuclides))*100:.1f}%"
ax.text(0.98, 0.98, stats_text, transform=ax.transAxes, 
        fontsize=10, verticalalignment='top', horizontalalignment='right',
        bbox=dict(boxstyle='round', facecolor='white', alpha=0.8, edgecolor='gray', linewidth=1))

plt.tight_layout()

# Save the figure
output_path = '/Users/audreywarn/fluka-db-audrey/outputs/nuclear_data_comparison.png'
plt.savefig(output_path, dpi=300, bbox_inches='tight')
print(f"\nPlot saved to: {output_path}")

plt.show()

print("\nScript completed successfully!")
