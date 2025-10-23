# ENDF-specific configuration (dmf_endf)
# Add this to configuration_file.py after the dmf5 definition

dmf_endf = {
    'LEVEL': {
        'description': 'Nuclear energy levels from ENDF decay data (limited - ENDF focuses on ground states)',
        'keys': ['A', 'Z', 'level'],
        'data_source': 'endf',
        'fields': {
            'elementName': {
                'description': 'Element name',
                'type': 'string',
            },
            'LIS': {
                'description': 'Isomeric state level (0=ground, 1=1st excited, etc.)',
                'type': 'int32',
            },
            'energy': {
                'description': 'Level energy (typically 0 for ENDF ground state data)',
                'type': 'float64',
            },
            'twoTimesSpin': {
                'description': 'Two times nuclear spin (2J)',
                'type': 'float64',
            },
            'spinParity': {
                'description': 'Spin parity (+1 or -1)',
                'type': 'float64',
            },
            'halfLife': {
                'description': 'Nuclear half-life (seconds)',
                'type': 'float64',
            },
            'MAT': {
                'description': 'ENDF material number',
                'type': 'int32',
            }
        }
    },
    
    'TRANSITION': {
        'description': 'Gamma-ray transitions from ENDF spectra (STYP=0)',
        'keys': ['A', 'Z', 'initialLevel', 'finalLevel'],
        'data_source': 'endf',
        'fields': {
            'elementName': {
                'description': 'Element name',
                'type': 'string',
            },
            'energy': {
                'description': 'Gamma-ray energy (keV)',
                'type': 'float64',
            },
            'energyUncertainty': {
                'description': 'Energy uncertainty (keV)',
                'type': 'float64',
            },
            'absoluteIntensity': {
                'description': 'Absolute gamma intensity (gammas per 100 decays)',
                'type': 'float64',
            },
            'relativeIntensity': {
                'description': 'Relative gamma intensity (normalized)',
                'type': 'float64',
            },
            'totalICC': {
                'description': 'Total internal conversion coefficient',
                'type': 'float64',
            },
            'MAT': {
                'description': 'ENDF material number',
                'type': 'int32',
            }
        }
    },
    
    'DECAY': {
        'description': 'Nuclear decay transitions from ENDF decay data (MF=8 MT=457)',
        'keys': ['A', 'Z', 'parentLevel', 'decay_mode', 'final_level'],
        'data_source': 'endf',
        'fields': {
            'RTYP': {
                'description': 'ENDF decay type code (1.0=β-, 2.0=EC/β+, 4.0=α, etc.)',
                'type': 'float64',
            },
            'RFS': {
                'description': 'Daughter nucleus isomeric state',
                'type': 'float64',
            },
            'Q_value': {
                'description': 'Decay Q-value (energy release in keV)',
                'type': 'float64',
            },
            'Q_uncertainty': {
                'description': 'Q-value uncertainty (keV)',
                'type': 'float64',
            },
            'Branching_ratio': {
                'description': 'Branching ratio (fraction, 0-1)',
                'type': 'float64',
            },
            'Branching_uncertainty': {
                'description': 'Branching ratio uncertainty',
                'type': 'float64',
            },
            'Endpoint_energy': {
                'description': 'Beta endpoint energy (keV) - maximum beta particle energy',
                'type': 'string',
            },
            'Average_energy': {
                'description': 'Average decay energy (keV) - mean particle energy',
                'type': 'string',
            },
            'Intensity': {
                'description': 'Decay intensity (percentage)',
                'type': 'string',
            },
            'MAT': {
                'description': 'ENDF material number',
                'type': 'int32',
            }
        }
    },

    'NUCLIDE': {
        'description': 'Nuclide properties from ENDF decay data',
        'keys': ['A', 'Z'],
        'data_source': 'endf',
        'fields': {
            'elementName': {
                'description': 'Element name',
                'type': 'string',
            },
            'elementSymbol': {
                'description': 'Element symbol',
                'type': 'string',
            },
            'MAT': {
                'description': 'ENDF material number',
                'type': 'int32',
            },
            'LIS': {
                'description': 'Isomeric state level',
                'type': 'int32',
            },
            'LISO': {
                'description': 'Isomeric state flag (0=ground, 1=excited)',
                'type': 'int32',
            },
            'NST': {
                'description': 'Stability flag (0=radioactive, 1=stable)',
                'type': 'int32',
            },
            'AWR': {
                'description': 'Atomic weight ratio (mass relative to neutron)',
                'type': 'float64',
            },
            'Spin': {
                'description': 'Nuclear spin',
                'type': 'float64',
            },
            'Parity': {
                'description': 'Nuclear parity (+1 or -1)',
                'type': 'float64',
            },
            'HalfLife': {
                'description': 'Half-life (seconds)',
                'type': 'float64',
            },
            'HalfLife_uncertainty': {
                'description': 'Half-life uncertainty (seconds)',
                'type': 'float64',
            },
            'NDK': {
                'description': 'Number of decay modes',
                'type': 'int32',
            },
            'NSP': {
                'description': 'Number of radiation spectra',
                'type': 'int32',
            },
            'NC': {
                'description': 'Number of daughter excitation states',
                'type': 'int32',
            }
        }
    }
}
