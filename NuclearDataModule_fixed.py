    def extract_decay_data(self, json_data, filename, is_alpha=False, is_delayed_particle=False):
        """Extract decay data from JSON with parent level"""
        parent = json_data.get('parents', [{}])[0]
        parent_symbol = parent.get('elementSymbol', '')
        parent_a = parent.get('a', '')
        parent_z = parent.get('z', None)
        
        # Defensive check for parent_z
        if parent_z is None:
            return []
        
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
        elif decay_mode == 'EC':
            for ec in json_data.get('electronCaptureTable', {}).get('electronCaptures', []):
                # Convert final_level to integer
                final_level = ec.get('finalLevel')
                if final_level is not None:
                    try:
                        final_level = int(final_level)
                    except (ValueError, TypeError):
                        final_level = None
                
                level_energy = level_lookup.get(final_level, "")

                # Extract parent level from EC decay data
                parent_level = ec.get('parentLevel')
                if parent_level is None:
                    # If parent level is not explicitly given, assume ground state (level 0)
                    parent_level = 0

                # For EC, we might have different energy fields
                # Safely extract capture energy or binding energy
                capture_e = ec.get('captureEnergy', {})
                energy_value, energy_unit = None, ''
                if isinstance(capture_e, dict):
                    energy_value = capture_e.get('value')
                    energy_unit = capture_e.get('unit', '')
                endpoint_str = self.format_scientific_notation(energy_value, energy_unit) if energy_value is not None else ""

                # For EC, average energy might not be available or be different
                avg_str = ""  # EC doesn't typically have average energy like beta decay

                # Safely extract EC intensity
                ec_i = ec.get('electronCaptureIntensity', {})
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
