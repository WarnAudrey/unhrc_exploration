    def _find_matching_transition(self, parent_a, parent_z, parent_level, 
                                  decay_mode, endf_particle_energy, parent_name, verbose=False):
        """
        Match ENDF particle energy to ENSDF transitions.
        
        Returns BOTH parent_level and daughter_level from the best matching transition.
        
        Logic:
        1. Look up all ENSDF transitions for this parent/decay_mode  
        2. Find transition with closest particle energy match
        3. Return (parent_level, daughter_level) from that transition
        """
        daughter_a, daughter_z = self._get_daughter_nucleus(parent_a, parent_z, decay_mode)
        daughter_elem = ATOMIC_SYMBOL.get(daughter_z, f'Z{daughter_z}')
        daughter_name = f"{daughter_elem}-{daughter_a}"
        
        if verbose:
            print(f"\n  Matching: {parent_name} -> {daughter_name} via {decay_mode}")
            print(f"    ENDF particle energy: {endf_particle_energy/1e3:.2f} keV")
        
        # Look up ENSDF transitions for this parent
        key = (parent_a, parent_z, decay_mode)
        if key not in self.transition_lookup:
            # Try to assign ground->ground if energy matches Q_ground
            if key in self.q_ground_lookup:
                q_ground = self.q_ground_lookup[key]
                if abs(endf_particle_energy - q_ground) <= self.absolute_tol:
                    if verbose:
                        print(f"    ✓ Matched to ground->ground transition")
                    return MatchResult(
                        matched=True,
                        parent_level=0.0,
                        final_level=0.0,
                        ensdf_energy=q_ground,
                        endf_q_value=endf_particle_energy,
                        energy_diff=abs(endf_particle_energy - q_ground),
                        rel_diff=abs(endf_particle_energy - q_ground) / max(q_ground, 1e-6),
                        match_quality="assumed_ground",
                        ambiguous=False,
                        daughter_nuclide=daughter_name
                    )
            
            if verbose:
                print(f"    ✗ No ENSDF transitions for this parent")
            return MatchResult(
                matched=False,
                parent_level=np.nan,
                final_level=np.nan,
                ensdf_energy=np.nan,
                endf_q_value=endf_particle_energy,
                energy_diff=np.nan,
                rel_diff=np.nan,
                match_quality="no_ensdf_data",
                ambiguous=False,
                daughter_nuclide=daughter_name
            )
        
        # Get all transitions for this parent
        transitions = self.transition_lookup[key]
        
        if verbose:
            print(f"    Found {len(transitions)} ENSDF transitions")
        
        # Find best matching transition by particle energy
        best_match = None
        best_diff = np.inf
        matches_within_tol = []
        
        for trans in transitions:
            ensdf_particle_energy = trans['particle_energy']
            abs_diff = abs(ensdf_particle_energy - endf_particle_energy)
            
            # Calculate tolerance
            if self.strategy == MatchStrategy.ABSOLUTE:
                tolerance = self.absolute_tol
            elif self.strategy == MatchStrategy.RELATIVE:
                tolerance = max(ensdf_particle_energy * self.relative_tol, 1e3)
            elif self.strategy == MatchStrategy.HYBRID:
                if ensdf_particle_energy < self.hybrid_threshold:
                    tolerance = self.absolute_tol
                else:
                    tolerance = ensdf_particle_energy * self.relative_tol
            
            # Check if within tolerance
            if abs_diff <= tolerance:
                matches_within_tol.append((abs_diff, trans, tolerance))
            
            # Track best match overall
            if abs_diff < best_diff:
                best_diff = abs_diff
                best_match = (abs_diff, trans, tolerance)
        
        # Return best match
        if matches_within_tol:
            matches_within_tol.sort(key=lambda x: x[0])
            abs_diff, trans, tol = matches_within_tol[0]
            
            rel_diff = abs_diff / max(trans['particle_energy'], 1e-6)
            ambiguous = len(matches_within_tol) > 1
            
            if abs_diff < tol * 0.1:
                quality = "exact"
            elif abs_diff < tol * 0.5:
                quality = "good"
            else:
                quality = "acceptable"
            
            if verbose:
                print(f"    ✓ Matched to parent_level={int(trans['parent_level'])}, daughter_level={int(trans['daughter_level'])}")
                print(f"      ENSDF particle energy: {trans['particle_energy']/1e3:.2f} keV")
                print(f"      Difference: {abs_diff/1e3:.2f} keV ({quality})")
            
            return MatchResult(
                matched=True,
                parent_level=trans['parent_level'],
                final_level=trans['daughter_level'],
                ensdf_energy=trans['particle_energy'],
                endf_q_value=endf_particle_energy,
                energy_diff=abs_diff,
                rel_diff=rel_diff,
                match_quality=quality,
                ambiguous=ambiguous,
                daughter_nuclide=daughter_name
            )
        
        # Try relaxed tolerance
        if best_match:
            abs_diff, trans, tol = best_match
            if abs_diff <= tol * self.relaxed_factor:
                rel_diff = abs_diff / max(trans['particle_energy'], 1e-6)
                if verbose:
                    print(f"    ~ Marginal match to parent_level={int(trans['parent_level'])}, daughter_level={int(trans['daughter_level'])}")
                    print(f"      Difference: {abs_diff/1e3:.2f} keV (marginal)")
                
                return MatchResult(
                    matched=True,
                    parent_level=trans['parent_level'],
                    final_level=trans['daughter_level'],
                    ensdf_energy=trans['particle_energy'],
                    endf_q_value=endf_particle_energy,
                    energy_diff=abs_diff,
                    rel_diff=rel_diff,
                    match_quality="marginal",
                    ambiguous=False,
                    daughter_nuclide=daughter_name
                )
        
        # No match
        if verbose:
            if best_match:
                _, trans, _ = best_match
                print(f"    ✗ No match (closest: {trans['particle_energy']/1e3:.2f} keV, diff: {best_diff/1e3:.2f} keV)")
            else:
                print(f"    ✗ No match found")
        
        return MatchResult(
            matched=False,
            parent_level=np.nan,
            final_level=np.nan,
            ensdf_energy=best_match[1]['particle_energy'] if best_match else np.nan,
            endf_q_value=endf_particle_energy,
            energy_diff=best_diff,
            rel_diff=best_diff / max(best_match[1]['particle_energy'], 1e-6) if best_match else np.nan,
            match_quality="failed",
            ambiguous=False,
            daughter_nuclide=daughter_name
        )
