import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# File paths
endfb8_path = '/Users/audreywarn/fluka-db-audrey/outputs/endfb8/endf_data_modules/ascii/DECAY.ascii'
endf_path = '/Users/audreywarn/fluka-db-audrey/outputs/endf/endf_data_modules/ascii/DECAY.ascii'

def read_decay_data(filepath):
    """
    Read decay data from ASCII file with MultiIndex (A, Z, ...) and extract unique nuclides.
    """
    try:
        # Read the file with whitespace delimiter
        df = pd.read_csv(filepath, delim_whitespace=True)
        
        # The first two columns should be A and Z (based on the MultiIndex structure)
        # Check if they're in the columns (when MultiIndex is flattened) or if we need to reset index
        if 'A' in df.columns and 'Z' in df.columns:
            # A and Z are regular columns
            nuclides = set(zip(df['Z'].astype(int), df['A'].astype(int)))
        elif df.index.nlevels >= 2:
            # MultiIndex case - A and Z are in the index
            # Reset index to access A and Z
            df_reset = df.reset_index()
            # Get the first two index level names (should be A and Z)
            a_col = df_reset.columns[0]  # First index level (A)
            z_col = df_reset.columns[1]  # Second index level (Z)
            nuclides = set(zip(df_reset[z_col].astype(int), df_reset[a_col].astype(int)))
        else:
            # Fallback: assume first two columns are A and Z
            cols = df.columns.tolist()
            a_col, z_col = cols[0], cols[1]
            nuclides = set(zip(df[z_col].astype(int), df[a_col].astype(int)))
        
        return nuclides
    
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        print("Attempting line-by-line parsing...")
        
        # Alternative: read line by line, skip header, extract first two numeric values
        nuclides = set()
        with open(filepath, 'r') as f:
            lines = f.readlines()
            # Skip header lines (they typically don't start with a digit)
            for line in lines:
                line = line.strip()
                if not line or not line[0].isdigit():
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        a = int(parts[0])  # First column is A
                        z = int(parts[1])  # Second column is Z
                        nuclides.add((z, a))
                    except ValueError:
                        continue
        return nuclides

# Read data from both sources
print("Reading ENDF-B-VIII.0 data...")
endfb8_nuclides = read_decay_data(endfb8_path)
print(f"Found {len(endfb8_nuclides)} nuclides in ENDF-B-VIII.0")

print("Reading ENDF (JEFF-4.0) data...")
endf_nuclides = read_decay_data(endf_path)
print(f"Found {len(endf_nuclides)} nuclides in ENDF (JEFF-4.0)")

# Find common and unique nuclides
common_nuclides = endfb8_nuclides & endf_nuclides
endfb8_only = endfb8_nuclides - endf_nuclides
endf_only = endf_nuclides - endfb8_nuclides

print(f"\nCommon nuclides: {len(common_nuclides)}")
print(f"ENDF-B-VIII.0 only: {len(endfb8_only)}")
print(f"ENDF (JEFF-4.0) only: {len(endf_only)}")

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
z_endfb8, n_endfb8, a_endfb8 = nuclides_to_arrays(endfb8_only)
z_endf, n_endf, a_endf = nuclides_to_arrays(endf_only)

# Create the plot
fig, ax = plt.subplots(figsize=(14, 10))

# Plot nuclides with different colors and markers
if len(endf_only) > 0:
    ax.scatter(n_endf, z_endf, c='#FF6B6B', marker='s', s=30, 
               label=f'ENDF (JEFF-4.0) only (n={len(endf_only)})', alpha=0.8, edgecolors='darkred', linewidths=0.3)

if len(endfb8_only) > 0:
    ax.scatter(n_endfb8, z_endfb8, c='#4ECDC4', marker='^', s=30, 
               label=f'ENDF-B-VIII.0 only (n={len(endfb8_only)})', alpha=0.8, edgecolors='darkblue', linewidths=0.3)

if len(common_nuclides) > 0:
    ax.scatter(n_common, z_common, c='#95E1D3', marker='o', s=30, 
               label=f'Common (n={len(common_nuclides)})', alpha=0.9, edgecolors='darkgreen', linewidths=0.3)

# Add labels and title
ax.set_xlabel('Neutron Number (N = A - Z)', fontsize=14, fontweight='bold')
ax.set_ylabel('Proton Number (Z)', fontsize=14, fontweight='bold')
ax.set_title('Comparison of ENDF-B-VIII.0 and ENDF (JEFF-4.0) Nuclear Data Sources', fontsize=16, fontweight='bold', pad=20)

# Grid for better readability
ax.grid(True, alpha=0.3, linestyle='--', linewidth=0.5)

# Legend
ax.legend(loc='upper left', fontsize=11, framealpha=0.9)

# Set axis limits with some padding
if len(endfb8_nuclides) + len(endf_nuclides) > 0:
    all_n = np.concatenate([n_common, n_endfb8, n_endf])
    all_z = np.concatenate([z_common, z_endfb8, z_endf])
    
    n_range = all_n.max() - all_n.min()
    z_range = all_z.max() - all_z.min()
    
    ax.set_xlim(all_n.min() - 0.05*n_range, all_n.max() + 0.05*n_range)
    ax.set_ylim(all_z.min() - 0.05*z_range, all_z.max() + 0.05*z_range)

# Add some statistics as text
stats_text = f"Total unique nuclides: {len(endfb8_nuclides | endf_nuclides)}\n"
stats_text += f"Coverage overlap: {len(common_nuclides)/(len(endfb8_nuclides | endf_nuclides))*100:.1f}%"
ax.text(0.98, 0.98, stats_text, transform=ax.transAxes, 
        fontsize=10, verticalalignment='top', horizontalalignment='right',
        bbox=dict(boxstyle='round', facecolor='white', alpha=0.8, edgecolor='gray', linewidth=1))

plt.tight_layout()

# Save the figure
output_path = '/Users/audreywarn/fluka-db-audrey/outputs/endf_endfb8_comparison.png'
plt.savefig(output_path, dpi=300, bbox_inches='tight')
print(f"\nPlot saved to: {output_path}")

plt.show()

print("\nScript completed successfully!")
