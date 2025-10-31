import os
import json
import pandas as pd
import numpy as np

class NuclearDataModule:
    # Full periodic table mapping
    Z_TO_SYMBOL = {
        1:"H",2:"He",3:"Li",4:"Be",5:"B",6:"C",7:"N",8:"O",9:"F",10:"Ne",
        11:"Na",12:"Mg",13:"Al",14:"Si",15:"P",16:"S",17:"Cl",18:"Ar",19:"K",
        20:"Ca",21:"Sc",22:"Ti",23:"V",24:"Cr",25:"Mn",26:"Fe",27:"Co",28:"Ni",
        29:"Cu",30:"Zn",31:"Ga",32:"Ge",33:"As",34:"Se",35:"Br",36:"Kr",37:"Rb",
        38:"Sr",39:"Y",40:"Zr",41:"Nb",42:"Mo",43:"Tc",44:"Ru",45:"Rh",46:"Pd",
        47:"Ag",48:"Cd",49:"In",50:"Sn",51:"Sb",52:"Te",53:"I",54:"Xe",55:"Cs",
        56:"Ba",57:"La",58:"Ce",59:"Pr",60:"Nd",61:"Pm",62:"Sm",63:"Eu",64:"Gd",
        65:"Tb",66:"Dy",67:"Ho",68:"Er",69:"Tm",70:"Yb",71:"Lu",72:"Hf",73:"Ta",
        74:"W",75:"Re",76:"Os",77:"Ir",78:"Pt",79:"Au",80:"Hg",81:"Tl",82:"Pb",
        83:"Bi",84:"Po",85:"At",86:"Rn",87:"Fr",88:"Ra",89:"Ac",90:"Th",91:"Pa",
        92:"U",93:"Np",94:"Pu",95:"Am",96:"Cm",97:"Bk",98:"Cf",99:"Es",100:"Fm",
        101:"Md",102:"No",103:"Lr",104:"Rf",105:"Db",106:"Sg",107:"Bh",108:"Hs",
        109:"Mt",110:"Ds",111:"Rg",112:"Cn",113:"Nh",114:"Fl",115:"Mc",116:"Lv",
        117:"Ts",118:"Og"
    }
    
    def __init__(self, *json_dirs, auto_save_ascii=True, ascii_output_dir="nuclear_data_ascii"):
        """
        Initialize Nuclear Data Module
        
        Parameters:
        -----------
        *json_dirs : str
            Variable number of directory paths containing JSON nuclear data files
        auto_save_ascii : bool
            Whether to automatically save data to ASCII files after loading
        ascii_output_dir : str
            Directory name for ASCII output files
        """
        self.json_dirs = json_dirs
        self.levels_df = pd.DataFrame()
        self.gamma_df = pd.DataFrame()
        self.decay_df = pd.DataFrame()
        self.nuclides_df = pd.DataFrame()  # Store nuclides data
        self.auto_save_ascii = auto_save_ascii
        self.ascii_output_dir = ascii_output_dir
        self.normalization_lookup = {}  # Store normalization values
        
        # Load all data
        self.load_data()
        
        # Process delayed particle normalizations
        if not self.decay_df.empty:
            print("\nProcessing delayed particle normalizations...")
            self.add_delayed_particle_normalization()
        
        # Note: Auto-save functionality removed - use DataModule.print_to_ascii() instead

    def format_scientific_notation(self, value, unit="", significant_digits=4):
        """
        Format a numerical value in scientific notation with consistent significant digits
        
        Parameters:
        -----------
        value : float or None
            The numerical value to format
        unit : str
            The unit to append (e.g., "keV", "%")
        significant_digits : int
            Number of significant digits to display
        
        Returns:
        --------
        str : Formatted string in scientific notation or empty string if value is None
        """
        if value is None or pd.isna(value):
            return ""
        
        try:
            # Convert to float if it's a string
            if isinstance(value, str):
                # Remove existing unit and percentage symbols
                value_clean = value.replace('%', '').replace(unit, '').strip()
                value = float(value_clean)
            
            # Format in scientific notation with specified significant digits
            formatted_value = f"{value:.{significant_digits-1}e}"
            
            # Add unit if provided
            if unit:
                return f"{formatted_value} {unit}"
            else:
                return formatted_value
                
        except (ValueError, TypeError):
            return str(value) if value is not None else ""

    def determine_data_type(self, directory_path):
        """Determine the type of nuclear data based on directory path"""
        path_lower = directory_path.lower()
        if 'alpha' in path_lower:
            return 'alpha_decay'
        elif 'beta' in path_lower:
            return 'beta_decay'
        elif 'delayed-particle' in path_lower or 'delayed_particle' in path_lower:
            return 'delayed_particle_decay'
        elif 'adopted' in path_lower or 'level' in path_lower:
            return 'levels_gammas'
        else:
            # Default to levels_gammas for unknown directories
            return 'levels_gammas'

    def extract_levels_data(self, json_data, filename):
        """Extract nuclear level data from JSON"""
        # Extract nucleus information from the header
        header = json_data.get('header', {})
        element_name = header.get('elementName', 'N/A')
        parent_a = header.get('a')
        parent_z = header.get('z')

        # Skip if essential A or Z are missing
        if parent_a is None or parent_z is None:
            return []

        # Navigate to the list of levels
        levels_table = json_data.get("levelsTable", {}).get("levels", [])
        
        if not levels_table:
            return []

        rows = []
        # Process each level in the table
        for level_idx, level in enumerate(levels_table):
            # Extract energy information
            energy_info = level.get('energy', {})
            energy_value = energy_info.get('value')
            energy_unit = energy_info.get('unit', 'keV')

            # Extract spin-parity information
            spin_parity_info = level.get('spinParity', {})
            spin_parity_values = spin_parity_info.get('values', [])
            
            # Default values for spin-parity
            two_times_spin = None
            spin_parity = None
            
            if spin_parity_values:
                # Take the first spin-parity value if multiple exist
                first_sp = spin_parity_values[0]
                two_times_spin = first_sp.get('twoTimesSpin')
                parity_str = first_sp.get('parity', '+')
                spin_parity = 1 if parity_str == '+' else -1

            # Extract stability information
            is_stable = level.get('isStable', False)

            # Extract half-life information
            half_life_info = level.get('halfLife', {})
            half_life_value = half_life_info.get('value')
            half_life_unit = half_life_info.get('unit', 's')

            # Append the extracted data to our list
            rows.append({
                "A": parent_a,
                "Z": parent_z,
                "level": level_idx,  # Use index as level identifier
                "elementName": element_name,
                "energy": energy_value,
                "energyUnit": energy_unit,
                "twoTimesSpin": two_times_spin,
                "spinParity": spin_parity,
                "isStable": is_stable,
                "halfLife": half_life_value,
                "halfLifeUnit": half_life_unit
            })
        
        return rows

    def extract_gamma_data(self, json_data, filename):
        """
        Extract gamma transition data from ENSDF JSON files.
        
        Processes gamma-ray transitions between nuclear energy levels.
        Each transition represents a photon emission when a nucleus
        decays from a higher energy level to a lower one.
        
        Args:
            json_data: Parsed JSON containing nuclear structure data
            filename: Source file name for error reporting
            
        Returns:
            List of dictionaries, each representing one gamma transition
        """
        # Extract parent nucleus information from the header
        header = json_data.get('header', {})
        parent_symbol = header.get('elementSymbol', 'N/A')  # e.g., "Li" for Lithium
        element_name = header.get('elementName', 'N/A')     # e.g., "Lithium"
        parent_a = header.get('a')  # Mass number (A)
        parent_z = header.get('z')  # Atomic number (Z)
        parent_identifier = f"{parent_symbol}-{parent_a}"   # e.g., "Li-7"

        # Skip if essential nuclear identifiers are missing
        if parent_a is None or parent_z is None:
            return []

        # Navigate to gamma transition data in JSON structure
        gammas_table = json_data.get("gammasTable", {}).get("gammas", [])

        if not gammas_table:
            return []  # No gamma data in this nucleus

        rows = []
        # Process each gamma transition in the table
        for gamma_idx, gamma in enumerate(gammas_table):
            # Extract gamma-ray energy (photon energy emitted)
            energy_info = gamma.get('energy', {})
            energy_value = energy_info.get('value')      # Numerical value
            energy_unit = energy_info.get('unit', 'keV') # Usually keV

            # Extract gamma intensity (relative probability of this transition)
            intensity_info = gamma.get('gammaIntensity', {})
            intensity_value = intensity_info.get('value')  # Often as percentage
            
            # Extract nuclear level indices for the transition
            initial_level = gamma.get('initialLevel')  # Higher energy state (excited)
            final_level = gamma.get('finalLevel')      # Lower energy state (often ground)

            # Skip incomplete transition data
            # Both levels required to define a valid transition
            if initial_level is None or final_level is None:
                continue

            # For gamma transitions, the parent level equals the initial level
            # (the excited state that emits the gamma ray)
            parent_level = initial_level

            # Append the extracted data to our list
            rows.append({
                "A": parent_a,
                "Z": parent_z,
                "initialLevel": initial_level,
                "finalLevel": final_level,
                "elementName": element_name,
                "parentIdentifier": parent_identifier,
                "energy": energy_value,
                "energyUnit": energy_unit,
                "gammaIntensity": intensity_value
            })
        
        return rows
    
    def gamma_intensity_counter(self):
        """
        Fills missing gamma-ray intensity values using nuclear physics principles.
        
        Gamma intensities represent the relative probability that a nuclear level
        will emit a gamma ray via a specific transition. For any nuclear level,
        the sum of all transition probabilities should equal 100%.
        
        Algorithm:
        1. Unique transitions: If only one gamma comes from a level → 100% intensity
        2. Competing transitions: Distribute remaining intensity among missing values
        3. All missing: Assume equal probability (uniform distribution)
        
        This ensures conservation of probability and realistic branching ratios.
        """
        if self.gamma_df.empty:
            print("No gamma data available to process.")
            return 0  # No changes made
        
        # Reset index to work with the data more easily
        gamma_temp = self.gamma_df.reset_index()
        
        # Ensure gammaIntensity column can handle mixed data (strings, floats, NaN)
        gamma_temp['gammaIntensity'] = gamma_temp['gammaIntensity'].astype('object')
        
        # STEP 1: Identify unique transitions
        # Count how many gamma rays originate from each nuclear level
        initial_level_counts = gamma_temp.groupby(['parentIdentifier'])['initialLevel'].value_counts()
        
        # Find levels that emit only one gamma ray
        # These should get 100% intensity (no competing transitions)
        unique_initial_levels = set()
        for (parent_id, initial_level), count in initial_level_counts.items():
            if count == 1:  # Only one transition from this level
                unique_initial_levels.add((parent_id, initial_level))
        
        # Initialize counters for progress tracking
        changes_made = 0
        total_processed = 0
        nan_intensities_found = 0
        
        # STEP 2: Handle unique transitions (set to 100%)
        for idx, row in gamma_temp.iterrows():
            total_processed += 1
            parent_id = row['parentIdentifier']
            initial_level = row['initialLevel']
            current_intensity = row['gammaIntensity']
            
            # Track missing intensity values for statistics
            if pd.isna(current_intensity) or current_intensity == "" or current_intensity is None:
                nan_intensities_found += 1
            
            # If this level has only one gamma transition, it gets 100% intensity
            if (parent_id, initial_level) in unique_initial_levels:
                # Fix missing intensity for unique transitions
                if pd.isna(current_intensity) or current_intensity == "" or current_intensity is None:
                    gamma_temp.loc[idx, 'gammaIntensity'] = "100 %"
                    changes_made += 1
        
        # STEP 3: Handle competing transitions (multiple gammas from same level)
        # Group gamma rays by their originating nuclear level
        grouped = gamma_temp.groupby(['parentIdentifier', 'initialLevel'])
        
        for (parent_id, initial_level), group in grouped:
            # Skip unique transitions (already processed above)
            if (parent_id, initial_level) in unique_initial_levels:
                continue
                
            # Check how many transitions in this group have missing intensities
            missing_mask = group['gammaIntensity'].isna() | (group['gammaIntensity'] == "") | group['gammaIntensity'].isna()
            missing_count = missing_mask.sum()
            
            if missing_count > 0:
                # If all transitions in the group are missing intensities, distribute equally
                if missing_count == len(group):
                    equal_intensity = 100.0 / len(group)
                    for group_idx in group.index[missing_mask]:
                        gamma_temp.loc[group_idx, 'gammaIntensity'] = f"{equal_intensity:.1f} %"
                        changes_made += 1
                else:
                    # If some have intensities and some don't, assign remaining intensity
                    # Extract existing intensity values and calculate remaining
                    existing_intensities = []
                    for intensity in group['gammaIntensity']:
                        if not (pd.isna(intensity) or intensity == "" or intensity is None):
                            if isinstance(intensity, str) and '%' in intensity:
                                try:
                                    intensity_value = float(intensity.replace('%', '').strip())
                                    existing_intensities.append(intensity_value)
                                except ValueError:
                                    pass
                            elif isinstance(intensity, (int, float)):
                                existing_intensities.append(float(intensity))
                    
                    if existing_intensities:
                        total_existing = sum(existing_intensities)
                        remaining_intensity = max(0, 100.0 - total_existing)
                        
                        if remaining_intensity > 0 and missing_count > 0:
                            per_missing = remaining_intensity / missing_count
                            for group_idx in group.index[missing_mask]:
                                gamma_temp.loc[group_idx, 'gammaIntensity'] = f"{per_missing:.1f} %"
                                changes_made += 1
                        elif remaining_intensity <= 0:
                            # If existing intensities already sum to 100% or more, give small default values
                            default_small = 1.0
                            for group_idx in group.index[missing_mask]:
                                gamma_temp.loc[group_idx, 'gammaIntensity'] = f"{default_small:.1f} %"
                                changes_made += 1
                    else:
                        # No valid existing intensities found, distribute equally
                        equal_intensity = 100.0 / len(group)
                        for group_idx in group.index[missing_mask]:
                            gamma_temp.loc[group_idx, 'gammaIntensity'] = f"{equal_intensity:.1f} %"
                            changes_made += 1
        
        # Update the main gamma DataFrame with the modified data
        gamma_temp.sort_values(by=["A", "Z", "initialLevel", "finalLevel"], inplace=True)
        self.gamma_df = gamma_temp.set_index(['A', 'Z', 'initialLevel', 'finalLevel'])
        
        # Print summary of changes
        print(f"Gamma Intensity Counter: Updated {changes_made} transitions with missing intensities")
        print(f"Total NaN/missing intensities found: {nan_intensities_found}")
        
        return changes_made

    def extract_delayed_particle_normalization(self, json_data, filename):
        """
        Extract normalization data from delayed particle JSON files.
        
        Parameters:
        -----------
        json_data : dict
            JSON data for delayed particle decay
        filename : str
            Name of the JSON file being processed
            
        Returns:
        --------
        dict : Dictionary mapping nucleus identifiers to normalization values
        """
        normalizations = {}
        
        # Extract parent information
        parents = json_data.get('parents', [])
        if not parents:
            return normalizations
            
        parent = parents[0]
        parent_symbol = parent.get('elementSymbol', '')
        parent_a = parent.get('a', '')
        parent_z = parent.get('z', None)
        
        if parent_z is None:
            return normalizations
        
        nucleus_key = f"{parent_a}-{parent_z}"
        
        # Extract normalization from parent data
        normalization_data = parent.get('normalization', {})
        if normalization_data:
            # Get particle normalization value
            particle_norm = normalization_data.get('particle', {})
            if isinstance(particle_norm, dict) and 'value' in particle_norm:
                normalizations[nucleus_key] = particle_norm['value']
                print(f"Extracted normalization {particle_norm['value']} for {nucleus_key} from {filename}")
        
        return normalizations
    
    def split_ec_bplus_decays(self):
        """
        Split EC/β+ decays into separate β+ and EC components according to ENSDF specification.
        
        According to ENSDF manual (ensdfman.pdf, page 17):
        - IB = Intensity of β⁺-decay branch
        - IE = Intensity of electron capture branch  
        - TI = Total (ε + β⁺) decay intensity
        - Formula: TI = IB + IE
        
        In JSON files, the 'betaIntensity' field corresponds to IB (β+ component only).
        The EC component (IE) must be calculated as: IE = TI - IB
        
        For ground-state decays, TI = 100% (total branching)
        For decays from excited states, TI may be less than 100%
        
        This creates two rows for each EC/β+ decay:
        1. B+ row with measured β+ intensity (IB)
        2. EC row with calculated EC intensity (IE = TI - IB)
        
        Returns:
        --------
        int : Number of decays that were split
        """
        if self.decay_df.empty:
            print("No decay data available for EC/β+ splitting.")
            return 0
        
        # Reset index to work with the data
        decay_temp = self.decay_df.reset_index()
        
        # Find all β+ decays (B+ mode)
        bplus_mask = decay_temp['decay_mode'] == 'B+'
        bplus_decays = decay_temp[bplus_mask].copy()
        
        if bplus_decays.empty:
            print("No β+ decays found to split.")
            return 0
        
        print(f"\nSplitting {len(bplus_decays)} β+/EC decays according to ENSDF specification...")
        print("ENSDF formula: Total Intensity (TI) = β+ Intensity (IB) + EC Intensity (IE)")
        
        # Create EC companion rows
        ec_rows = []
        split_count = 0
        
        # Group by parent to determine total branching per level
        for (A, Z, parentLevel), group in bplus_decays.groupby(['A', 'Z', 'parentLevel']):
            # For ground state (parentLevel=0), total branching should be 100%
            # For excited states, sum all β+ branches from this level to get TI
            total_intensity = 0.0
            
            for idx, row in group.iterrows():
                # Extract β+ intensity (IB in ENSDF notation)
                bplus_intensity_str = row['Intensity']
                
                if pd.isna(bplus_intensity_str) or bplus_intensity_str == "":
                    bplus_intensity = 0.0
                else:
                    # Parse β+ intensity
                    try:
                        if isinstance(bplus_intensity_str, str):
                            intensity_clean = bplus_intensity_str.replace('%', '').strip()
                            bplus_intensity = float(intensity_clean)
                        else:
                            bplus_intensity = float(bplus_intensity_str)
                    except (ValueError, TypeError):
                        bplus_intensity = 0.0
                
                total_intensity += bplus_intensity
            
            # If we have any β+ intensity from this level, calculate EC
            if total_intensity > 0:
                # For each β+ transition, create corresponding EC transition
                for idx, row in group.iterrows():
                    bplus_intensity_str = row['Intensity']
                    
                    if pd.isna(bplus_intensity_str) or bplus_intensity_str == "":
                        bplus_intensity = 0.0
                    else:
                        try:
                            if isinstance(bplus_intensity_str, str):
                                intensity_clean = bplus_intensity_str.replace('%', '').strip()
                                bplus_intensity = float(intensity_clean)
                            else:
                                bplus_intensity = float(bplus_intensity_str)
                        except (ValueError, TypeError):
                            bplus_intensity = 0.0
                    
                    # ENSDF formula: TI = IB + IE
                    # For ground state: TI = 100%
                    # For excited state: TI = total β+ branching from this level
                    if parentLevel == 0:
                        TI = 100.0  # Ground state total branching
                    else:
                        TI = total_intensity  # Excited state total branching
                    
                    # Calculate EC intensity: IE = TI - IB
                    ec_intensity = max(0.0, TI - bplus_intensity)
                    
                    # Only create EC row if there's EC component
                    if ec_intensity > 0:
                        # Create EC row (copy of β+ row but with EC mode and different intensity)
                        ec_row = row.copy()
                        ec_row['decay_mode'] = 'EC'
                        ec_row['Intensity'] = self.format_scientific_notation(ec_intensity, "%")
                        # EC decays don't have β+ endpoint or average energy
                        ec_row['Endpoint energy'] = ""
                        ec_row['Average energy'] = ""
                        
                        ec_rows.append(ec_row)
                        split_count += 1
                        
                        if split_count <= 5:  # Show first few examples
                            print(f"  Example: {row['Parent']} level {parentLevel}")
                            print(f"    TI = {TI:.2f}%, IB (β+) = {bplus_intensity:.2f}%, IE (EC) = {ec_intensity:.2f}%")
        
        # Concatenate original data with new EC rows
        if ec_rows:
            ec_df = pd.DataFrame(ec_rows)
            decay_combined = pd.concat([decay_temp, ec_df], ignore_index=True)
            
            # Sort by the index columns
            decay_combined.sort_values(
                by=["A", "Z", "parentLevel", "decay_mode", "final_level"], 
                inplace=True
            )
            
            # Restore index
            self.decay_df = decay_combined.set_index(['A', 'Z', 'parentLevel', 'decay_mode', 'final_level'])
            
            print(f"\nSuccessfully split {split_count} β+/EC transitions into β+ and EC components")
            print(f"Total decay transitions after splitting: {len(self.decay_df)}")
            
            # Display breakdown by decay type after splitting
            decay_modes = self.decay_df.index.get_level_values('decay_mode').unique()
            print("\nDecay modes after EC/β+ splitting:")
            for mode in sorted(decay_modes):
                count = len(self.decay_df.xs(mode, level='decay_mode'))
                print(f"  - {mode}: {count} transitions")
        else:
            print("\nNo EC components found (all transitions are 100% β+)")
        
        return split_count

    def add_delayed_particle_normalization(self):
        """
        Add normalized intensity values for delayed particle decays as a key in the index.
        
        For delayed particle decays, multiplies normalization by intensity to create
        a normalized_intensity key. Sets to -1 for non-delayed particle decays.
        
        Returns:
        --------
        int : Number of delayed particle entries processed
        """
        if self.decay_df.empty:
            print("No decay data available to process normalization.")
            return 0
        
        # Reset index to work with the data
        decay_temp = self.decay_df.reset_index()
        
        # Counter for processed entries
        processed_count = 0
        
        # Process only delayed particle decays (decay modes with hyphen followed by particle symbol)
        # B-n, B-p, B-a, B-2n, etc. but NOT B-, B+, EC
        delayed_particle_mask = (
            decay_temp['decay_mode'].str.contains('-', na=False) & 
            ~decay_temp['decay_mode'].isin(['B-', 'B+', 'EC'])
        )
        delayed_entries = decay_temp[delayed_particle_mask]
        
        print(f"Processing normalization for {len(delayed_entries)} delayed particle decay entries...")
        
        for idx, row in delayed_entries.iterrows():
            try:
                # Extract intensity value from the formatted string
                intensity_str = row['Intensity']
                if pd.isna(intensity_str) or intensity_str == "":
                    continue
                    
                # Parse intensity value (remove % and convert to float)
                if isinstance(intensity_str, str):
                    # Handle scientific notation with %
                    intensity_clean = intensity_str.replace('%', '').strip()
                    if 'e' in intensity_clean.lower():
                        # Parse scientific notation
                        intensity_value = float(intensity_clean)
                    else:
                        intensity_value = float(intensity_clean)
                else:
                    intensity_value = float(intensity_str)
                
                # Get normalization for this nucleus
                nucleus_key = f"{row['A']}-{row['Z']}"
                normalization = self.normalization_lookup.get(nucleus_key)
                
                if normalization is not None:
                    # Normalization found (no longer storing in column)
                    processed_count += 1
                else:
                    print(f"Warning: No normalization found for {nucleus_key}")
                
            except (ValueError, TypeError) as e:
                print(f"Warning: Could not process normalization for entry {idx}: {e}")
                continue
        
        # Update the main decay DataFrame 
        decay_temp.sort_values(by=["A", "Z", "parentLevel", "decay_mode", "final_level"], inplace=True)
        self.decay_df = decay_temp.set_index(['A', 'Z', 'parentLevel', 'decay_mode', 'final_level'])
        
        print(f"Successfully processed normalizations for {processed_count} delayed particle decays")
        
        return processed_count

    def extract_decay_data(self, json_data, filename, is_alpha=False, is_delayed_particle=False):
        """Extract decay data from JSON with parent level - FIXED to include delayed particles from beta-decay files"""
        parent = json_data.get('parents', [{}])[0]
        parent_symbol = parent.get('elementSymbol', '')
        parent_a = parent.get('a', '')
        parent_z = parent.get('z', None)
        
        # Defensive check for parent_z
        if parent_z is None:
            return []
        
        # Initialize flag for delayed particles in beta-decay files
        is_delayed_in_beta = False
        
        # Determine decay mode from JSON
        decay_mode_from_file = json_data.get('decayMode', '')
        
        if is_alpha:
            decay_mode = 'A'
        elif is_delayed_particle:
            decay_mode = decay_mode_from_file
            # Handle all types of delayed particle decays: B-n, B-2n, B+p, B-p, B-A, etc.
            # Skip ECP delayed particle decays entirely
            if not decay_mode:
                print(f"Warning: No decay mode found in delayed particle file {filename}")
                return []
            if 'ECP' in decay_mode or 'EC' in decay_mode:
                print(f"Skipping ECP delayed particle decay file {filename} with mode: {decay_mode}")
                return []
                
            # Extract and store normalization data for delayed particle decays
            normalizations = self.extract_delayed_particle_normalization(json_data, filename)
            self.normalization_lookup.update(normalizations)
        else:
            # Processing beta-decay directory files
            decay_mode = decay_mode_from_file
            
            # Check if this beta-decay file actually contains delayed particles
            # Delayed particle modes contain a hyphen followed by a particle (B-n, B-2n, B+p, etc.)
            is_delayed_in_beta = False
            if decay_mode and '-' in decay_mode:
                # Check if it's a delayed particle mode (not just B- or B+)
                if decay_mode not in ['B-', 'B+'] and any(particle in decay_mode for particle in ['n', 'p', 'a', 'A', '2n', '2p', '3n', '4n']):
                    is_delayed_in_beta = True
                    print(f"Found delayed particle decay {decay_mode} in beta-decay file {filename}")
                    
                    # Extract and store normalization data for delayed particle decays
                    normalizations = self.extract_delayed_particle_normalization(json_data, filename)
                    self.normalization_lookup.update(normalizations)
            
            # If not delayed particle, must be B-, B+, or EC
            if not is_delayed_in_beta:
                if decay_mode not in ['B-', 'B+', 'EC']:
                    return []

        # Build level lookup by index, with safety (make int)
        levels = json_data.get("levelsTable", {}).get("levels", [])
        level_lookup = {}
        for idx, lvl in enumerate(levels):
            energy_info = lvl.get("energy", {})
            try:
                energy_value = energy_info.get("value")
                energy_unit = energy_info.get("unit", "")
                if energy_value is not None:
                    level_lookup[idx] = f"{energy_value} {energy_unit}".strip()
                else:
                    level_lookup[idx] = ""
            except:
                level_lookup[idx] = ""

        rows = []
        
        # Handle delayed particle decays (both from delayed-particle directory and beta-decay directory)
        if is_delayed_particle or is_delayed_in_beta:
            print(f"Processing delayed particle decay file {filename} with decay mode: {decay_mode}")
            
            # First, try to extract from delayedParticlesTable if it exists
            delayed_particles = json_data.get('delayedParticlesTable', {}).get('delayedParticles', [])
            
            if delayed_particles:
                print(f"Found {len(delayed_particles)} entries in delayedParticlesTable")
                
                for delayed_particle in delayed_particles:
                    # Convert final_level to integer
                    final_level = delayed_particle.get('finalLevel')
                    if final_level is not None:
                        try:
                            final_level = int(final_level)
                        except (ValueError, TypeError):
                            final_level = None
                    
                    # Extract parent level - for delayed particle decays, assume ground state unless specified
                    parent_level = 0  # Delayed particle decays typically originate from ground state
                    
                    # Extract intensity information
                    intensity_info = delayed_particle.get('intensity', {})
                    intensity_value = intensity_info.get('value')
                    
                    # Format intensity in scientific notation
                    if intensity_value is not None:
                        intensity_str = self.format_scientific_notation(intensity_value, "%")
                    else:
                        intensity_str = ""
                    
                    # For delayed particle decays, we don't have endpoint or average energy in the same way
                    # These are particle emission probabilities, not beta energies
                    endpoint_str = ""
                    avg_str = ""
                    
                    rows.append({
                        "A": parent_a,
                        "Z": parent_z,
                        "parentLevel": parent_level,
                        "decay_mode": decay_mode,
                        "final_level": final_level,
                        "Parent": f"{parent_symbol}-{parent_a}",
                        "Endpoint energy": endpoint_str,
                        "Average energy": avg_str,
                        "Intensity": intensity_str,
                    })
            
            # Also try to extract from other tables that might contain delayed particle data
            # Check for beta decays in delayed particle files (these are the underlying beta decays)
            beta_table = json_data.get('betasTable', {}).get('betas', [])
            if beta_table:
                print(f"Found {len(beta_table)} entries in betasTable for delayed decay")
                
                for beta in beta_table:
                    # Convert final_level to integer
                    final_level = beta.get('finalLevel')
                    if final_level is not None:
                        try:
                            final_level = int(final_level)
                        except (ValueError, TypeError):
                            final_level = None
                    
                    parent_level = beta.get('parentLevel', 0)

                    # Safely extract endpointEnergy
                    endpoint_e = beta.get('endpointEnergy', {})
                    energy_value, energy_unit = None, ''
                    if isinstance(endpoint_e, dict):
                        energy_value = endpoint_e.get('value')
                        energy_unit = endpoint_e.get('unit', '')
                    endpoint_str = self.format_scientific_notation(energy_value, energy_unit) if energy_value is not None else ""

                    # Safely extract averageEnergy
                    avg_e = beta.get('averageEnergy', {})
                    avg_value, avg_unit = None, ''
                    if isinstance(avg_e, dict):
                        avg_value = avg_e.get('value')
                        avg_unit = avg_e.get('unit', '')
                    avg_str = self.format_scientific_notation(avg_value, avg_unit) if avg_value is not None else ""

                    # Safely extract betaIntensity
                    beta_i = beta.get('betaIntensity', {})
                    beta_value = None
                    if isinstance(beta_i, dict):
                        beta_value = beta_i.get('value')
                    intensity_str = self.format_scientific_notation(beta_value, "%") if beta_value is not None else ""

                    rows.append({
                        "A": parent_a,
                        "Z": parent_z,
                        "parentLevel": parent_level,
                        "decay_mode": decay_mode,
                        "final_level": final_level,
                        "Parent": f"{parent_symbol}-{parent_a}",
                        "Endpoint energy": endpoint_str,
                        "Average energy": avg_str,
                        "Intensity": intensity_str,
                    })
            
            print(f"Extracted {len(rows)} total delayed particle decay entries from {filename}")
            return rows
        
        # Handle alpha decays
        elif is_alpha:
            for alpha in json_data.get('alphasTable', {}).get('alphas', []):
                # Convert final_level to integer
                final_level = alpha.get('finalLevel')
                if final_level is not None:
                    try:
                        final_level = int(final_level)
                    except (ValueError, TypeError):
                        final_level = None
                
                level_energy = level_lookup.get(final_level, "")

                # Extract parent level from alpha decay data
                parent_level = alpha.get('parentLevel')
                if parent_level is None:
                    # If parent level is not explicitly given, assume ground state (level 0)
                    parent_level = 0

                # Safely extract alpha energy
                alpha_e = alpha.get('energy', {})
                energy_value, energy_unit = None, ''
                if isinstance(alpha_e, dict):
                    energy_value = alpha_e.get('value')
                    energy_unit = alpha_e.get('unit', '')
                energy_str = self.format_scientific_notation(energy_value, energy_unit) if energy_value is not None else ""

                # Alpha decays don't have average energy
                avg_str = ""

                # Safely extract alpha intensity
                alpha_i = alpha.get('intensity', {})
                alpha_value = None
                if isinstance(alpha_i, dict):
                    alpha_value = alpha_i.get('value')
                # Format intensity in scientific notation
                intensity_str = self.format_scientific_notation(alpha_value, "%") if alpha_value is not None else ""

                rows.append({
                    "A": parent_a,
                    "Z": parent_z,
                    "parentLevel": parent_level,
                    "decay_mode": decay_mode,
                    "final_level": final_level,
                    "Parent": f"{parent_symbol}-{parent_a}",
                    "Endpoint energy": energy_str,
                    "Average energy": avg_str,
                    "Intensity": intensity_str,
                })
        
        # Handle beta decays (B+ and B-)
        elif decay_mode in ['B-', 'B+']:
            for beta in json_data.get('betasTable', {}).get('betas', []):
                # Convert final_level to integer
                final_level = beta.get('finalLevel')
                if final_level is not None:
                    try:
                        final_level = int(final_level)
                    except (ValueError, TypeError):
                        final_level = None
                
                level_energy = level_lookup.get(final_level, "")

                # Extract parent level from beta decay data
                parent_level = beta.get('parentLevel')
                if parent_level is None:
                    # If parent level is not explicitly given, assume ground state (level 0)
                    parent_level = 0

                # Safely extract endpointEnergy
                endpoint_e = beta.get('endpointEnergy', {})
                energy_value, energy_unit = None, ''
                if isinstance(endpoint_e, dict):
                    energy_value = endpoint_e.get('value')
                    energy_unit = endpoint_e.get('unit', '')
                endpoint_str = self.format_scientific_notation(energy_value, energy_unit) if energy_value is not None else ""

                # Safely extract averageEnergy
                avg_e = beta.get('averageEnergy', {})
                avg_value, avg_unit = None, ''
                if isinstance(avg_e, dict):
                    avg_value = avg_e.get('value')
                    avg_unit = avg_e.get('unit', '')
                avg_str = self.format_scientific_notation(avg_value, avg_unit) if avg_value is not None else ""

                # Safely extract betaIntensity
                beta_i = beta.get('betaIntensity', {})
                beta_value = None
                if isinstance(beta_i, dict):
                    beta_value = beta_i.get('value')
                intensity_str = self.format_scientific_notation(beta_value, "%") if beta_value is not None else ""

                rows.append({
                    "A": parent_a,
                    "Z": parent_z,
                    "parentLevel": parent_level,
                    "decay_mode": decay_mode,
                    "final_level": final_level,
                    "Parent": f"{parent_symbol}-{parent_a}",
                    "Endpoint energy": endpoint_str,
                    "Average energy": avg_str,
                    "Intensity": intensity_str,
                })
        
        # Handle electron capture decays (EC)
        # NOTE: EC decays use betasTable (same as B+), but with electronCaptureIntensity field
        elif decay_mode == 'EC':
            for beta in json_data.get('betasTable', {}).get('betas', []):
                # Convert final_level to integer
                final_level = beta.get('finalLevel')
                if final_level is not None:
                    try:
                        final_level = int(final_level)
                    except (ValueError, TypeError):
                        final_level = None
                
                level_energy = level_lookup.get(final_level, "")

                # Extract parent level from EC decay data
                parent_level = beta.get('parentLevel')
                if parent_level is None:
                    # If parent level is not explicitly given, assume ground state (level 0)
                    parent_level = 0

                # Safely extract endpointEnergy (Q-value for EC)
                endpoint_e = beta.get('endpointEnergy', {})
                energy_value, energy_unit = None, ''
                if isinstance(endpoint_e, dict):
                    energy_value = endpoint_e.get('value')
                    energy_unit = endpoint_e.get('unit', '')
                endpoint_str = self.format_scientific_notation(energy_value, energy_unit) if energy_value is not None else ""

                # For EC, average energy might not be available or be different
                avg_str = ""  # EC doesn't typically have average energy like beta decay

                # Safely extract electronCaptureIntensity (NOT betaIntensity for pure EC)
                ec_i = beta.get('electronCaptureIntensity', {})
                ec_value = None
                if isinstance(ec_i, dict):
                    ec_value = ec_i.get('value')
                intensity_str = self.format_scientific_notation(ec_value, "%") if ec_value is not None else ""

                rows.append({
                    "A": parent_a,
                    "Z": parent_z,
                    "parentLevel": parent_level,
                    "decay_mode": decay_mode,
                    "final_level": final_level,
                    "Parent": f"{parent_symbol}-{parent_a}",
                    "Endpoint energy": endpoint_str,
                    "Average energy": avg_str,
                    "Intensity": intensity_str,
                })
        
        return rows

    def extract_nuclides_data(self, json_data, filename):
        """
        Extract nuclide data from ENSDF JSON files.
        
        This method extracts nuclear data according to the NUCLIDE table structure
        defined in configuration_file.py, focusing on separation energies and basic
        nuclear properties, with more to be added later.
        
        Args:
            json_data: Parsed JSON containing nuclear structure data
            filename: Source file name for error reporting
            
        Returns:
            List of dictionaries, each representing one nuclide entry
        """
        # Extract nucleus information from the header
        header = json_data.get('header', {})
        element_name = header.get('elementName', 'N/A')
        element_symbol = header.get('elementSymbol', 'N/A')
        a_value = header.get('a')  # Mass number (A)
        z_value = header.get('z')  # Atomic number (Z)
        
        # Skip if essential nuclear identifiers are missing
        if a_value is None or z_value is None:
            return []
        
        # Navigate to separation energies in JSON structure
        q_values = json_data.get('qValues', {})
        separation_energies = q_values.get('separationEnergies', {})
        
        if not separation_energies:
            return []  # No separation energy data in this nucleus
        
        rows = []
        
        # Extract neutron separation energy
        neutron_sep_info = separation_energies.get('n', {})
        neutron_sep_value = neutron_sep_info.get('value') if isinstance(neutron_sep_info, dict) else None
        
        # Extract proton separation energy
        proton_sep_info = separation_energies.get('p', {})
        proton_sep_value = proton_sep_info.get('value') if isinstance(proton_sep_info, dict) else None
        
        # Create nuclide entry
        nuclide_entry = {
            "A": a_value,
            "Z": z_value,
            "Neutron_separation_energy": neutron_sep_value,
            "Proton_separation_energy": proton_sep_value,
        }
        
        rows.append(nuclide_entry)
        
        return rows

    def load_data(self):
        """
        Load data from all directories based on their type
        
        OPTIMIZATION NOTES:
        - Pre-allocates lists to reduce reallocation overhead for large datasets (193K+ records)
        - Processes files sequentially but with memory-efficient data structures
        - Uses extend() instead of append() for better bulk operations
        - Future optimization opportunity: chunked processing for very large datasets
        """
        all_level_rows = []
        all_gamma_rows = []
        all_decay_rows = []
        all_nuclides_rows = []
        
        # Pre-allocate lists with estimated sizes for better memory management
        # This reduces list reallocation overhead for large datasets
        
        for json_dir in self.json_dirs:
            if not os.path.exists(json_dir):
                print(f"Warning: Directory {json_dir} does not exist")
                continue
            
            # Determine data type based on directory path
            data_type = self.determine_data_type(json_dir)
            
            print(f"Processing {data_type} files from: {json_dir}")
            
            file_count = 0
            for filename in os.listdir(json_dir):
                if filename.lower().endswith('.json'):
                    file_count += 1
                    filepath = os.path.join(json_dir, filename)
                    try:
                        with open(filepath, 'r') as f:
                            data = json.load(f)
                            
                            if data_type == 'levels_gammas':
                                # Extract both levels and gamma data
                                levels_extracted = self.extract_levels_data(data, filename)
                                gamma_extracted = self.extract_gamma_data(data, filename)
                                nuclides_extracted = self.extract_nuclides_data(data, filename)
                                all_level_rows.extend(levels_extracted)
                                all_gamma_rows.extend(gamma_extracted)
                                all_nuclides_rows.extend(nuclides_extracted)
                            elif data_type in ['alpha_decay', 'beta_decay', 'delayed_particle_decay']:
                                # Extract decay data
                                is_alpha = (data_type == 'alpha_decay')
                                is_delayed_particle = (data_type == 'delayed_particle_decay')
                                decay_extracted = self.extract_decay_data(data, filename, is_alpha=is_alpha, is_delayed_particle=is_delayed_particle)
                                all_decay_rows.extend(decay_extracted)
                                
                    except Exception as e:
                        print(f"Error processing {data_type} file {filename}: {e}")
            
            print(f"Processed {file_count} {data_type} files")
        
        # Create levels DataFrame
        if all_level_rows:
            levels_df_temp = pd.DataFrame(all_level_rows)
            # Convert data types
            levels_df_temp['energy'] = pd.to_numeric(levels_df_temp['energy'], errors='coerce')
            levels_df_temp['twoTimesSpin'] = pd.to_numeric(levels_df_temp['twoTimesSpin'], errors='coerce').astype('Int32')
            levels_df_temp['spinParity'] = pd.to_numeric(levels_df_temp['spinParity'], errors='coerce').astype('Int32')
            levels_df_temp['halfLife'] = pd.to_numeric(levels_df_temp['halfLife'], errors='coerce')
            
            # Format float values in scientific notation
            levels_df_temp['energy'] = levels_df_temp.apply(lambda row: 
                self.format_scientific_notation(row['energy'], row['energyUnit']) if pd.notna(row['energy']) else row['energy'], axis=1)
            levels_df_temp['halfLife'] = levels_df_temp.apply(lambda row:
                self.format_scientific_notation(row['halfLife'], row['halfLifeUnit']) if pd.notna(row['halfLife']) else row['halfLife'], axis=1)
            
            # Sort and set index
            levels_df_temp.sort_values(by=["A", "Z", "level"], inplace=True)
            self.levels_df = levels_df_temp.set_index(['A', 'Z', 'level'])
            print(f"Loaded {len(self.levels_df)} nuclear levels")
        
        # Create gamma DataFrame with parent level in index
        if all_gamma_rows:
            gamma_df_temp = pd.DataFrame(all_gamma_rows)
            # Convert numeric columns
            gamma_df_temp['energy'] = pd.to_numeric(gamma_df_temp['energy'], errors='coerce')
            # Keep gammaIntensity as object type to preserve "%" symbols and handle mixed data types
            gamma_df_temp['initialLevel'] = pd.to_numeric(gamma_df_temp['initialLevel'], errors='coerce').astype('Int32')
            gamma_df_temp['finalLevel'] = pd.to_numeric(gamma_df_temp['finalLevel'], errors='coerce').astype('Int32')
            
            # Format float values in scientific notation
            gamma_df_temp['energy'] = gamma_df_temp.apply(lambda row:
                self.format_scientific_notation(row['energy'], row['energyUnit']) if pd.notna(row['energy']) else row['energy'], axis=1)
            
            # Sort and set index without parent level
            gamma_df_temp.sort_values(by=["A", "Z", "initialLevel", "finalLevel"], inplace=True)
            self.gamma_df = gamma_df_temp.set_index(['A', 'Z', 'initialLevel', 'finalLevel'])
            print(f"Loaded {len(self.gamma_df)} gamma transitions")
            
            # Automatically apply gamma intensity counter to fix NaN values
            print("\nApplying gamma intensity counter...")
            self.gamma_intensity_counter()
        
        # Create decay DataFrame with parent level
        if all_decay_rows:
            decay_df_temp = pd.DataFrame(all_decay_rows)
            decay_df_temp['parentLevel'] = pd.to_numeric(decay_df_temp['parentLevel'], errors='coerce').astype('Int32')
            # Convert final_level to integer
            decay_df_temp['final_level'] = pd.to_numeric(decay_df_temp['final_level'], errors='coerce').astype('Int32')
            
            # Fix NA values: replace any pandas <NA> or string 'NA' with np.nan in energy columns
            energy_columns = ['Endpoint energy', 'Average energy']
            for col in energy_columns:
                if col in decay_df_temp.columns:
                    # Replace empty strings and any 'NA' strings with np.nan
                    decay_df_temp[col] = decay_df_temp[col].replace(['', 'NA'], np.nan)
                    # Also handle pandas <NA> values
                    decay_df_temp[col] = decay_df_temp[col].where(pd.notna(decay_df_temp[col]), np.nan)
            
            self.decay_df = decay_df_temp.set_index(['A', 'Z', 'parentLevel', 'decay_mode', 'final_level'])
            print(f"Loaded {len(self.decay_df)} decay transitions")
            
            # Display breakdown by decay type
            decay_modes = self.decay_df.index.get_level_values('decay_mode').unique()
            print("Decay modes loaded:")
            for mode in decay_modes:
                count = len(self.decay_df.xs(mode, level='decay_mode'))
                print(f"  - {mode}: {count} transitions")
            
            # Apply EC/β+ splitting
            print("\nApplying EC/β+ decay splitting...")
            self.split_ec_bplus_decays()
            
            # NOTE: EC rows are now KEPT in the final dataset (not removed)
        
        # Create nuclides DataFrame
        if all_nuclides_rows:
            nuclides_df_temp = pd.DataFrame(all_nuclides_rows)
            # Convert data types
            nuclides_df_temp['Neutron_separation_energy'] = pd.to_numeric(nuclides_df_temp['Neutron_separation_energy'], errors='coerce')
            nuclides_df_temp['Proton_separation_energy'] = pd.to_numeric(nuclides_df_temp['Proton_separation_energy'], errors='coerce')
            
            # Format float values in scientific notation (assuming keV units for separation energies)
            nuclides_df_temp['Neutron_separation_energy'] = nuclides_df_temp['Neutron_separation_energy'].apply(
                lambda x: self.format_scientific_notation(x, "keV") if pd.notna(x) else x)
            nuclides_df_temp['Proton_separation_energy'] = nuclides_df_temp['Proton_separation_energy'].apply(
                lambda x: self.format_scientific_notation(x, "keV") if pd.notna(x) else x)
            
            # Sort and set index
            nuclides_df_temp.sort_values(by=["A", "Z"], inplace=True)
            self.nuclides_df = nuclides_df_temp.set_index(['A', 'Z'])
            print(f"Loaded {len(self.nuclides_df)} nuclide entries")


    def _apply_filters(self, df, **filters):
        """Apply filters to a dataframe"""
        if df.empty:
            return df
        
        filtered_df = df.copy()
        
        # Reset index to access A and Z as columns
        filtered_df = filtered_df.reset_index()
        
        # Apply A filters
        if 'A_min' in filters:
            filtered_df = filtered_df[filtered_df['A'] >= filters['A_min']]
        if 'A_max' in filters:
            filtered_df = filtered_df[filtered_df['A'] <= filters['A_max']]
        if 'A_list' in filters:
            filtered_df = filtered_df[filtered_df['A'].isin(filters['A_list'])]
        
        # Apply Z filters
        if 'Z_min' in filters:
            filtered_df = filtered_df[filtered_df['Z'] >= filters['Z_min']]
        if 'Z_max' in filters:
            filtered_df = filtered_df[filtered_df['Z'] <= filters['Z_max']]
        if 'Z_list' in filters:
            filtered_df = filtered_df[filtered_df['Z'].isin(filters['Z_list'])]
        
        # Apply element filters
        if 'elements' in filters and 'elementName' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['elementName'].isin(filters['elements'])]
        
        # Restore original index structure
        if 'level' in filtered_df.columns:
            # Levels dataframe
            filtered_df = filtered_df.set_index(['A', 'Z', 'level'])
        elif 'initialLevel' in filtered_df.columns and 'finalLevel' in filtered_df.columns and 'gammaIntensity' in filtered_df.columns:
            # Gamma dataframe
            filtered_df = filtered_df.set_index(['A', 'Z', 'initialLevel', 'finalLevel'])
        elif 'parentLevel' in filtered_df.columns and 'decay_mode' in filtered_df.columns:
            # Decay dataframe
            filtered_df = filtered_df.set_index(['A', 'Z', 'parentLevel', 'decay_mode', 'final_level'])
        
        return filtered_df

    def prioritize_decay(self, parent_filter="NN-1"):
        """Add priority column to decay data for sorting"""
        if self.decay_df.empty:
            return
            
        def assign_priority(row):
            if row['Parent'] == parent_filter:
                return 0
            return 1
        
        # Reset index temporarily to work with the Priority column
        temp_df = self.decay_df.reset_index()
        temp_df['Priority'] = temp_df.apply(assign_priority, axis=1)
        
        # Set the multi-index back with parent level
        self.decay_df = temp_df.set_index(['A', 'Z', 'parentLevel', 'decay_mode', 'final_level'])

    def sort_by_periodic_table(self):
        """Sort decay data by periodic table order"""
        if self.decay_df.empty:
            return pd.DataFrame()
            
        self.Z_TO_SYMBOL_INV = {v: k for k, v in self.Z_TO_SYMBOL.items()}

        # Work with a copy that has reset index
        temp_df = self.decay_df.reset_index()
        
        # Extract parent Z from Parent column for sorting (backup method if needed)
        temp_df['Parent Z for sorting'] = temp_df['Parent'].apply(
            lambda x: self.Z_TO_SYMBOL_INV.get(x.split('-')[0], None))
        temp_df['Parent Z for sorting'] = temp_df['Parent Z for sorting'].fillna(9999)

        # Sort by Priority (if exists), then by Z, then by A, then by parentLevel, then by decay_mode, then by final_level
        sort_columns = []
        if 'Priority' in temp_df.columns:
            sort_columns.append('Priority')
        sort_columns.extend(['Z', 'A', 'parentLevel', 'decay_mode', 'final_level'])
        
        sorted_df = temp_df.sort_values(by=sort_columns)
        
        # Drop temporary columns and reset multi-index
        columns_to_drop = ['Parent Z for sorting']
        if 'Priority' in sorted_df.columns:
            columns_to_drop.append('Priority')
        
        sorted_df = sorted_df.drop(columns=columns_to_drop)
        return sorted_df.set_index(['A', 'Z', 'parentLevel', 'decay_mode', 'final_level'])

    def get_sorted_decay(self, parent_filter="NN-1"):
        """Get sorted decay data with priority"""
        self.prioritize_decay(parent_filter)
        return self.sort_by_periodic_table()

    def get_levels_data(self):
        """Get nuclear levels DataFrame"""
        return self.levels_df

    def get_gamma_data(self):
        """Get gamma transitions DataFrame"""
        return self.gamma_df

    def get_decay_data(self):
        """Get decay transitions DataFrame"""
        return self.decay_df

    def get_nuclides_data(self):
        """Get nuclides DataFrame with separation energies"""
        return self.nuclides_df
    
    @staticmethod
    def json_ascii_formatter(module_name, df, float_format):
        """
        Custom formatter function for JSON-style ASCII output with consistent 3-line header format.
        This function can be passed to DataModule.print_to_ascii(custom_formatter=...).
        
        Args:
            module_name: Name of the module (LEVEL, TRANSITION, DECAY, NUCLIDE)
            df: DataFrame to format (already cleaned by DataModule)
            float_format: Float formatting function (from DataModule)
            
        Returns:
            str: Formatted string with proper JSON ASCII structure
        """
        import pandas as pd
        
        if df.empty:
            return ""
            
        na_patterns = ['', 'nan', 'NaN', 'NA', '<NA>', 'None', 'null']
        
        # Generate the consistent 3-line format for JSON modules
        lines = []
        
        # Line 1: Field names positioned where field values will appear
        header_parts = []
        for col in df.columns:
            header_parts.append(f"{col:>15}")
        
        # Calculate spacing for keys based on the index structure
        key_spacing_map = {
            'LEVEL': 13,      # "A   Z   level   "
            'TRANSITION': 28, # "A   Z   initialLevel finalLevel "
            'DECAY': 43,      # "A   Z   parentLevel decay_mode final_level "
            'NUCLIDE': 7      # "A   Z   "
        }
        key_spacing = key_spacing_map.get(module_name, 43)
        
        # Line 1: Field headers positioned where values appear
        field_line = " " * key_spacing + " ".join(header_parts)
        lines.append(field_line)
        
        # Line 2: Key names positioned where key values appear  
        key_line_map = {
            'LEVEL': "A   Z   level",
            'TRANSITION': "A   Z   initialLevel finalLevel",
            'DECAY': "A   Z   parentLevel decay_mode final_level",
            'NUCLIDE': "A   Z"
        }
        key_line = key_line_map.get(module_name, str(df.index.names))
        lines.append(key_line)
        
        # Line 3+: Data rows
        for idx, row in df.iterrows():
            # Format index parts based on module type
            if module_name == 'DECAY' and len(idx) == 5:
                A, Z, parentLevel, decay_mode, final_level = idx
                index_part = f"{A:<3} {Z:<3} {parentLevel:<11} {decay_mode:<10} {final_level:<11}"
            elif module_name == 'TRANSITION' and len(idx) == 4:
                A, Z, initialLevel, finalLevel = idx
                index_part = f"{A:<3} {Z:<3} {initialLevel:<12} {finalLevel:<12}"
            elif module_name == 'LEVEL' and len(idx) == 3:
                A, Z, level = idx
                index_part = f"{A:<3} {Z:<3} {level:<5}"
            elif module_name == 'NUCLIDE' and len(idx) == 2:
                A, Z = idx
                index_part = f"{A:<3} {Z:<3}"
            else:
                # Fallback for other modules or unexpected index structure
                if isinstance(idx, tuple):
                    index_part = " ".join([f"{str(i):<10}" for i in idx])
                else:
                    index_part = f"{str(idx):<10}"
            
            # Format data columns
            data_parts = []
            for col in df.columns:
                value = row[col]
                if pd.isna(value) or str(value).strip() in na_patterns or str(value).strip() == '':
                    formatted_value = ' ' * 15  # Blank spaces for NA values
                elif isinstance(value, (int, float)) and not pd.isna(value):
                    formatted_value = f"{float_format(value):>15}"
                else:
                    formatted_value = f"{str(value):>15}"
                data_parts.append(formatted_value)
            
            line = index_part + " " + " ".join(data_parts)
            lines.append(line)
        
        return "\n".join(lines)

    def display_summary(self):
        """Display summary of all loaded data"""
        print("=" * 60)
        print("NUCLEAR DATA MODULE SUMMARY")
        print("=" * 60)
        
        if not self.levels_df.empty:
            print(f"\nNuclear Levels: {len(self.levels_df)} entries")
            print(f"Unique nuclei (levels): {len(self.levels_df.index.droplevel('level').unique())}")
            if not self.levels_df['energy'].isna().all():
                print(f"Energy range: {self.levels_df['energy'].min():.2f} - {self.levels_df['energy'].max():.2f} keV")
        
        if not self.gamma_df.empty:
            print(f"\nGamma Transitions: {len(self.gamma_df)} entries")
            print(f"Unique nuclei (gamma): {len(self.gamma_df.index.droplevel(['initialLevel', 'finalLevel']).unique())}")
            if not self.gamma_df['energy'].isna().all():
                print(f"Gamma energy range: {self.gamma_df['energy'].min():.2f} - {self.gamma_df['energy'].max():.2f} keV")
        
        if not self.decay_df.empty:
            print(f"\nDecay Transitions: {len(self.decay_df)} entries")
            print(f"Unique nuclei (decay): {len(self.decay_df.index.droplevel(['decay_mode', 'final_level']).unique())}")
            decay_modes = self.decay_df.index.get_level_values('decay_mode').unique()
            print(f"Decay modes: {', '.join(decay_modes)}")
        
        if not self.nuclides_df.empty:
            print(f"\nNuclides Data (Separation Energies): {len(self.nuclides_df)} entries")
            print(f"Unique nuclei (nuclides): {len(self.nuclides_df)}")
            if not self.nuclides_df['Neutron_separation_energy'].isna().all():
                n_sep_min = self.nuclides_df['Neutron_separation_energy'].min()
                n_sep_max = self.nuclides_df['Neutron_separation_energy'].max()
                print(f"Neutron separation energy range: {n_sep_min:.2f} - {n_sep_max:.2f} keV")
            if not self.nuclides_df['Proton_separation_energy'].isna().all():
                p_sep_min = self.nuclides_df['Proton_separation_energy'].min()
                p_sep_max = self.nuclides_df['Proton_separation_energy'].max()
                print(f"Proton separation energy range: {p_sep_min:.2f} - {p_sep_max:.2f} keV")


# Example usage and main execution
if __name__ == "__main__":
    # Define data directories - update these paths to match your system
    adopted_dir = "/Users/audreywarn/fluka-db-audrey/data_input/ensdf/json_070125/adopted/"
    beta_dir = "/Users/audreywarn/fluka-db-audrey/data_input/ensdf/json_070125/beta-decay/"
    alpha_dir = "/Users/audreywarn/fluka-db-audrey/data_input/ensdf/json_070125/alpha-decay/"
    delayed_particle_dir = "/Users/audreywarn/fluka-db-audrey/data_input/ensdf/json_070125/delayed-particle-decay/"
    
    print("Initializing Nuclear Data Module...")
    print(f"Loading data from {len([adopted_dir, beta_dir, alpha_dir, delayed_particle_dir])} directories")
    
    # Initialize module with all directories - ASCII files will be generated automatically
    nuclear_module = NuclearDataModule(adopted_dir, beta_dir, alpha_dir, delayed_particle_dir)
    
    # Display comprehensive summary
    nuclear_module.display_summary()
    
    print("\n" + "=" * 60)
    print("DATA ACCESS EXAMPLES")
    print("=" * 60)
    
    # Get data handles
    levels_data = nuclear_module.get_levels_data()
    gamma_data = nuclear_module.get_gamma_data()
    decay_data = nuclear_module.get_decay_data()
    nuclides_data = nuclear_module.get_nuclides_data()
    
    # Display sample data if available
    if not levels_data.empty:
        print(f"\nNuclear Levels Sample (first 3 entries):")
        print(levels_data.head(3).to_string())
    
    if not gamma_data.empty:
        print(f"\nGamma Transitions Sample (first 3 entries):")
        print(gamma_data.head(3).to_string())
    
    if not decay_data.empty:
        print(f"\nDecay Transitions Sample (first 3 entries):")
        print(decay_data.head(3).to_string())
        
        # Show delayed particle decays if they exist
        delayed_modes = [mode for mode in decay_data.index.get_level_values('decay_mode').unique() if '-' in mode and mode not in ['B-', 'B+']]
        if delayed_modes:
            print(f"\nDelayed particle decay modes found: {', '.join(delayed_modes)}")
            for mode in delayed_modes[:2]:  # Show first 2 delayed modes
                mode_data = decay_data.xs(mode, level='decay_mode')
                print(f"\nSample {mode} decays (first 2):")
                display_cols = ['Parent', 'Intensity']
                print(mode_data[display_cols].head(2).to_string())
    
    if not nuclides_data.empty:
        print(f"\nNuclides Data Sample (first 3 entries):")
        print(nuclides_data.head(3).to_string())
    
    print("\n" + "=" * 60)
    print("NUCLEAR DATA MODULE COMPLETE")
    print("=" * 60)
    print("✅ Now includes delayed particles from beta-decay files!")
    print("✅ B-n, B-2n, B+p, B-a and other delayed modes will be captured")
    print("✅ Use with Database.py to generate complete DECAY.ascii files")
