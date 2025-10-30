#!/bin/python
#
#
import os, math
from collections import defaultdict
# Conditional import to avoid dependency issues in JSON-only workflows
try:
    from PyClasses.Legacy import Legacy
except ImportError:
    Legacy = None  # Will be handled gracefully in methods that need it
from PyClasses.JSONParsing import NuclearDataModule
from PyClasses.DataModule import DataModule
import pandas as pd
import time
import copy
import numpy as np
import mmap
import struct
#from general.Unit import Unit

# pd.set_option("display.precision", 8)
pd.set_option('display.float_format', lambda x: "%1.4e" % x)
pd.set_option('display.expand_frame_repr', False )
pd.set_option('display.max_columns', None)
pd.set_option('styler.format.na_rep', '')
       

def retrieve_from_df(df, value, column_name=None, rel_tol=0.005, abs_tol=5e-6):
    '''
    Returns the first index (multiindex) for which df[column_name] equals value, or in case of a float
    is closer than the specified tolerance
    '''
    
    if column_name:
        data = df[column_name]
    else:
        data = df
    
    try:
        # Check if the column contains float values
        if pd.api.types.is_float_dtype(df[column_name]):
            # mask = []
            # for i, r in df.iterrows():
            #    mask.append(math.isclose(r[column_name], value, rel_tol=rel_tol, abs_tol=abs_tol))
            minabs = (df[column_name] - value).abs().min()
            index_minvalue = (df[column_name] - value).abs().idxmin()
            compared_value = df[column_name].loc[index_minvalue]
            if minabs < max(abs_tol,rel_tol * max(abs(value),abs(compared_value))):
                mask = (df[column_name] - value).abs() == minabs    
            else:
                mask = []
                
        else:
            # Exact match for other data types
            mask = data == value
            
        # Get the index of the first matching row
        index = data.index[mask].tolist()
        return index[0] if index else None
        
    except KeyError:
        print(f"Column '{column_name}' not found in the DataFrame.")
        return None
    

def pandas_to_numpy_dtype(pd_dtype):
    if pd.api.types.is_integer_dtype(pd_dtype):
        return np.int32
    elif pd.api.types.is_float_dtype(pd_dtype):
        return np.float64
    elif pd.api.types.is_bool_dtype(pd_dtype):
        return np.bool_
    elif pd.api.types.is_string_dtype(pd_dtype):
        return 'S50'  # Adjust string length as needed
    else:
        raise TypeError(f"Unsupported dtype: {pd_dtype}")
    
class Database():
    '''
    Class describing the ensemble of data modules (Tables) making up
    the nuclear database exploited by FLUKA to perform its calculations
    The modules are contained in self.dm (dict) and callable by their
    name. Data modules are created based on the catalogue file, in DbParams.
    
    JSON Integration Usage Examples:
    ===============================
    
    # Example 1: Load JSON data and populate database
    db = Database(config, remove_dm=[])
    nuclear_data = db.populate_from_json_directories(
        "path/to/adopted/", 
        "path/to/beta-decay/", 
        "path/to/alpha-decay/",
        auto_save_ascii=False
    )
    
    # Example 2: Load JSON data separately, then populate
    nuclear_data = db.load_json_data("path/to/json/data/")
    db.populate_from_json(nuclear_data)
    
    # Example 3: Validate compatibility before population
    validation = db.validate_json_compatibility(nuclear_data)
    if validation['LEVEL']['compatible']:
        db.populate_from_json(nuclear_data)
    
    # Example 4: Access populated data
    level_table = db.get_table('LEVEL')
    print(f"Loaded {len(level_table.C)} nuclear levels")
    '''    
    
    def __init__(self, db_config, remove_dm=None):
        # Load parameters
        self.db_config = db_config
        self.dm_list = list(self.db_config.dm.index)
        # For debugging speedup purposes
        if remove_dm:
            for dm in remove_dm:
                if dm in self.dm_list:
                    self.dm_list.remove(dm)
        # Attributes
        self.dm = {}
        self.F5_dm = {}
        self.F5_dm_parquet = {}
        self._MEM_LVL_NB = 0
        
        # Track if this database was populated from JSON data
        self._json_source_module = None
        
        # keeping track of which reactions are done, to prevent 
        # parsing twice the same reactions (some blocks present
        # different results regarding the same readtion). For the moment
        # this means that when this happens, only the first block is taken
        # into account
        # Reactions types :
        #        'ngthermal'
        self.reactions = defaultdict(list)
        
        # Setup data modules according to descriptor
        for dm_name in self.dm_list:            
            self.dm[dm_name] = DataModule(dm_name, self.db_config)
        
    def get_table(self, name):
        return self.dm[name]
    
    def import_data(self):
        for table in self.dm:
            pass

    def populate_from_legacy(self, legacy):
        # self.parameters = legacy.dynp
        for dm_name in self.dm_list:
            print(f'------------------')
            print(f'Populating data module :  {dm_name}')

            start = time.time()
            self.dm[dm_name].populate_DM_from_legacy(legacy)
            end = time.time()
            print(f'Time spent in preparing {dm_name} : ', end-start)
    
    def populate_from_json(self, json_data_module):
        """
        Populate data modules from JSON-based nuclear data, similar to populate_from_legacy.
        
        Args:
            json_data_module: NuclearDataModule instance containing parsed JSON data
        """
        print('========')
        print('Populating database from JSON data')
        print('========')
        
        # Store reference to JSON source module for ASCII generation
        self._json_source_module = json_data_module
        
        start_total = time.time()
        
        # Populate each data module using the existing populate_DM_from_nuclear_data method
        # PROCESSING OPTIMIZATION: Process modules in order of dependency and data size
        # This ensures larger datasets (LEVEL: 193K+ records) are processed first
        # Benefits: better memory allocation patterns, early error detection on large datasets
        dm_priority = ['LEVEL', 'TRANSITION', 'DECAY']  # Process larger datasets first
        
        for dm_name in dm_priority:
            if dm_name in self.dm_list and dm_name in self.dm:
                print(f'Populating {dm_name} data module from JSON data...')
                start = time.time()
                
                # Validate compatibility first (cache results)
                validation = self.dm[dm_name].validate_nuclear_data_compatibility(json_data_module)
                if validation['compatible']:
                    self.dm[dm_name].populate_DM_from_nuclear_data(json_data_module)
                    print(f'Successfully populated {dm_name}: {len(self.dm[dm_name].C)} records')
                else:
                    print(f'Skipping {dm_name}: {", ".join(validation["warnings"])}')
                
                end = time.time()
                print(f'Time spent populating {dm_name}: {end-start:.2f}s')
        
        # Process remaining data modules
        remaining_dms = [dm for dm in self.dm_list if dm not in dm_priority]
        for dm_name in remaining_dms:
            if dm_name in self.dm:
                print(f'Populating {dm_name} data module from JSON data...')
                start = time.time()
                
                validation = self.dm[dm_name].validate_nuclear_data_compatibility(json_data_module)
                if validation['compatible']:
                    self.dm[dm_name].populate_DM_from_nuclear_data(json_data_module)
                    print(f'Successfully populated {dm_name}: {len(self.dm[dm_name].C)} records')
                else:
                    print(f'Skipping {dm_name}: {", ".join(validation["warnings"])}')
                
                end = time.time()
                print(f'Time spent populating {dm_name}: {end-start:.2f}s')
        
        # Update nuclear data statistics
        self._update_nuclear_statistics(json_data_module)
        
        end_total = time.time()
        print(f'Total time spent populating from JSON: {end_total-start_total:.2f}s')
        print('========')

    def populate_from_endf(self, endf_data_module):
        """
        Populate data modules from ENDF-based nuclear data.
        
        Args:
            endf_data_module: ENDFDataModule instance containing parsed ENDF data
        """
        print('========')
        print('Populating database from ENDF data')
        print('========')
        
        # Store reference to ENDF source module for ASCII generation
        self._endf_source_module = endf_data_module
        
        start_total = time.time()
        
        # ENDF only has DECAY and NUCLIDE data (no LEVEL or TRANSITION)
        # Use pre-indexed DataFrames to bypass populate_DM_from_endf_data() which expects tuples
        
        # DECAY module
        if 'DECAY' in self.dm_list and 'DECAY' in self.dm:
            print(f'Populating DECAY data module from ENDF data...')
            start = time.time()
            
            decay_dm = self.dm['DECAY']
            decay_df = endf_data_module.get_decay_dataframe(with_index=True)
            
            if not decay_df.empty:
                decay_dm.C = decay_df
                print(f'Successfully populated DECAY: {len(decay_df)} records')
            else:
                print(f'Warning: DECAY is empty')
            
            end = time.time()
            print(f'Time spent populating DECAY: {end-start:.2f}s')
        
        # NUCLIDE module  
        if 'NUCLIDE' in self.dm_list and 'NUCLIDE' in self.dm:
            print(f'Populating NUCLIDE data module from ENDF data...')
            start = time.time()
            
            nuclide_dm = self.dm['NUCLIDE']
            nuclide_df = endf_data_module.get_nuclide_dataframe(with_index=True)
            
            if not nuclide_df.empty:
                nuclide_dm.C = nuclide_df
                print(f'Successfully populated NUCLIDE: {len(nuclide_df)} records')
            else:
                print(f'Warning: NUCLIDE is empty')
            
            end = time.time()
            print(f'Time spent populating NUCLIDE: {end-start:.2f}s')
        
        # Update nuclear data statistics
        self._update_endf_statistics(endf_data_module)
        
        end_total = time.time()
        print(f'Total time spent populating from ENDF: {end_total-start_total:.2f}s')
        print('========')
    
    def _update_endf_statistics(self, endf_data_module):
        """
        Update nuclear data statistics after ENDF population
        
        Args:
            endf_data_module: ENDFDataModule instance containing parsed ENDF data
        """
        decay_data = endf_data_module.get_decay_data(with_index=True)
        nuclides_data = endf_data_module.get_nuclides_data(with_index=True)
        
        print('ENDF data statistics:')
        
        if not decay_data.empty:
            unique_nuclei_decay = len(decay_data.index.droplevel(['decay_mode', 'final_level']).unique())
            decay_modes = decay_data.index.get_level_values('decay_mode').unique()
            print(f'  - Decay transitions: {len(decay_data)} entries from {unique_nuclei_decay} nuclei')
            print(f'  - Decay modes: {", ".join(sorted(decay_modes))}')
            
            # Show EC/β+ splitting statistics
            bplus_count = len(decay_data.xs('B+', level='decay_mode')) if 'B+' in decay_modes else 0
            ec_count = len(decay_data.xs('EC', level='decay_mode')) if 'EC' in decay_modes else 0
            if bplus_count > 0 or ec_count > 0:
                print(f'  - EC/β+ splitting: {bplus_count} β+ transitions, {ec_count} EC transitions')
        
        if not nuclides_data.empty:
            print(f'  - Nuclides data: {len(nuclides_data)} entries')
    
    def _update_nuclear_statistics(self, json_data_module):
        """
        Update nuclear data statistics after JSON population
        
        Args:
            json_data_module: NuclearDataModule instance containing parsed JSON data
        """
        levels_data = json_data_module.get_levels_data()
        gamma_data = json_data_module.get_gamma_data()
        decay_data = json_data_module.get_decay_data()
        nuclides_data = json_data_module.get_nuclides_data()
        
        print('Nuclear data statistics:')
        if not levels_data.empty:
            unique_nuclei_levels = len(levels_data.index.droplevel('level').unique())
            print(f'  - Nuclear levels: {len(levels_data)} entries from {unique_nuclei_levels} nuclei')
        
        if not gamma_data.empty:
            unique_nuclei_gamma = len(gamma_data.index.droplevel(['initialLevel', 'finalLevel']).unique())
            print(f'  - Gamma transitions: {len(gamma_data)} entries from {unique_nuclei_gamma} nuclei')
        
        if not decay_data.empty:
            unique_nuclei_decay = len(decay_data.index.droplevel(['decay_mode', 'final_level']).unique())
            decay_modes = decay_data.index.get_level_values('decay_mode').unique()
            print(f'  - Decay transitions: {len(decay_data)} entries from {unique_nuclei_decay} nuclei')
            print(f'  - Decay modes: {", ".join(decay_modes)}')
        
        if not nuclides_data.empty:
            print(f'  - Nuclides data: {len(nuclides_data)} entries with separation energies')
            # Show separation energy statistics (temporarily disabled due to string format issue)
            # if not nuclides_data['Neutron_separation_energy'].isna().all():
            #     n_sep_count = nuclides_data['Neutron_separation_energy'].count()
            #     n_sep_range = (nuclides_data['Neutron_separation_energy'].min(), nuclides_data['Neutron_separation_energy'].max())
            #     print(f'    - Neutron separation energies: {n_sep_count} entries, range: {n_sep_range[0]:.2f} - {n_sep_range[1]:.2f} keV')
            # if not nuclides_data['Proton_separation_energy'].isna().all():
            #     p_sep_count = nuclides_data['Proton_separation_energy'].count()
            #     p_sep_range = (nuclides_data['Proton_separation_energy'].min(), nuclides_data['Proton_separation_energy'].max())
            #     print(f'    - Proton separation energies: {p_sep_count} entries, range: {p_sep_range[0]:.2f} - {p_sep_range[1]:.2f} keV')
            
    def retrieve_lvnb(self, A, Z, En):
        return self.dm['LEVEL'].retrieve_lvnb(A, Z, En)
    
    def load_json_data(self, *json_dirs, **kwargs):
        """
        Create a NuclearDataModule instance and load JSON data from specified directories.
        
        Args:
            *json_dirs: Variable number of directory paths containing JSON nuclear data files
            **kwargs: Additional arguments to pass to NuclearDataModule constructor
        
        Returns:
            NuclearDataModule: Loaded nuclear data module
        """
        print(f'Loading JSON nuclear data from {len(json_dirs)} directories:')
        for json_dir in json_dirs:
            print(f'  - {json_dir}')
        
        # Create and return NuclearDataModule instance
        nuclear_data = NuclearDataModule(*json_dirs, **kwargs)
        
        print('JSON data loading completed')
        nuclear_data.display_summary()
        
        return nuclear_data
    
    def populate_from_json_directories(self, *json_dirs, **kwargs):
        """
        Convenience method to load JSON data from directories and populate the database.
        
        Args:
            *json_dirs: Variable number of directory paths containing JSON nuclear data files
            **kwargs: Additional arguments to pass to NuclearDataModule constructor
        """
        # Load JSON data
        nuclear_data = self.load_json_data(*json_dirs, **kwargs)
        
        # Populate the database
        self.populate_from_json(nuclear_data)
        
        return nuclear_data
    
    def validate_json_compatibility(self, json_data_module):
        """
        Validate compatibility of JSON data with all data modules in the database.
        
        Args:
            json_data_module: NuclearDataModule instance containing parsed JSON data
            
        Returns:
            dict: Validation results for each data module
        """
        print('Validating JSON data compatibility with database modules...')
        
        validation_results = {}
        
        for dm_name in self.dm_list:
            if dm_name in self.dm:
                validation = self.dm[dm_name].validate_nuclear_data_compatibility(json_data_module)
                validation_results[dm_name] = validation
                
                if validation['compatible']:
                    print(f'  ✓ {dm_name}: Compatible')
                else:
                    print(f'  ✗ {dm_name}: {", ".join(validation["warnings"])}')
        
        compatible_modules = [dm for dm, val in validation_results.items() if val['compatible']]
        print(f'Compatible modules: {compatible_modules}')
        
        return validation_results
    
    
    def pointer_increment(self, key, var, Ascan, Zscan, amt):   
        refA = key[0]
        refZ = key[1]
        refK  = self.dm['NUCLIDE_POINTER'].C.loc[(refA,refZ), var]
        scanK = self.dm['NUCLIDE_POINTER'].C.loc[(Ascan, Zscan), var]
        if scanK > refK:
            self.dm['NUCLIDE_POINTER'].C.loc[(Ascan, Zscan),var] += amt
        elif scanK == refK:
            if Ascan > refA:
                self.dm['NUCLIDE_POINTER'].C.loc[(Ascan, Zscan),var] += amt
            elif Ascan == refA:
                if Zscan > refZ:
                    self.dm['NUCLIDE_POINTER'].C.loc[(Ascan, Zscan),var] += amt
        return None

    def import_additions(self, add):
        '''
        USED FOR RE-CREATION OF LEGACY DB ONLY:
        
        Function parsing the additions file and modyfing the data modules
        accordingly. 2 types of additions are possible : 
        - Direct addition to a non-existent key
            for dm : NUCLIDES, TRANSITION
            
        - Append to end of catalogue for an existing sub-key
            for dm: ISOMER*, DECAY, DECAY_ISOMER, LEVEL
                        GDR, 
            ISOMER: Always insert instead of adding at the end of list
                    Because A (and Z within A) must be monotonously increasing
        - The following dm are considered exhaustive and should not
          have any additions
            ADATA, ZDATA, NDATA, BEZIER, DECAY_TYPE
        '''
        nex = self.parameters['MEXMXB'][0]
        temp_trans = {}
        for table_name, key, vals in add:
            # case for which the key must be incomplete (last index missing
            # and automatically populated with n+1, where n is the current number
            # of elements related to that sub-key.)
            kl = list(key)
            table = self.dm[table_name]
            if table_name in ['DECAY', 'DECAY_ISOMER', 'LEVEL', 'GDR', 'ISOMER']:
                newid = table.find_max_index(tuple(kl)) + 1
                kl.append(newid)
                if table_name == 'LEVEL':
                    curr_lvl = newid
            
            #--------------------
            # Update the related parameters / pointers / sizes
            # Conditional formatting of some values is included here as well
            # (e.g. Average energy should be made negative for Beta minus decay)
            #--------------------
            if table_name == 'LEVEL':               
                self.dm['NUCLIDE'].C.loc[key,'Nb. Levels'] += 1
                nlev = self.dm['NUCLIDE'].C.loc[key,'Nb. Levels']
                
                # Shift all pointers behind the considered nuclide
                # by the amount of elements we add to it
                # To go from nlev levels to nlev+1, we need to add "shift"
                # values (1 for each level below; 1 energy; 1 hl).

                shift = Legacy.tri_block_address(nex, nlev+1) - Legacy.tri_block_address(nex, nlev) +1
                
                # IOFFST update: incremented by 2*shift as we add elements to both 
                #                SIGGTT and NSTOR
                self.parameters['IOFFST'][0] += 2 * shift
                
                # KDXNUC update: all nuclides whose level data is located after
                # the changed one in the blank common are incremented by 2*shift
                refL = self.dm['NUCLIDE'].C.loc[key,'KDXNUC']
                for AA in range(Legacy.NAMSMX):
                    for ZZww in range(min(Legacy.NZGVAX, AA)):
                        ZZ = ZZww + self.dm['ADATA'].C.loc[AA + 1,'INWAPS']
                        kch = (AA+1, ZZ)
                        #
                        # if the index exists (if it does not, skip)
                        if kch in self.dm['NUCLIDE'].C.index:
                            # if the value is NA, do nothing
                            if not pd.isna(self.dm['NUCLIDE'].C.loc[kch,'KDXNUC']):
                                if self.dm['NUCLIDE'].C.loc[kch,'KDXNUC']  > refL:
                                    self.dm['NUCLIDE'].C.loc[kch,'KDXNUC'] += 2 * shift

                table.add_record(tuple(kl),vals)
                        
                        
            elif table_name == 'TRANSITION':
            # Transition lines added to a fake level MUST follow
            # immediately after that level, as curr_lvl is used
                kk = (key[0], key[1], curr_lvl)
                self.import_transitions_DB(kk, vals)
            
            elif table_name == 'DECAY':
                # ALPHA LINES
                if vals['Decay'] == 'A':
                    # NALLNS update : one more line
                    if pd.isna(self.dm['NUCLIDE'].C.loc[key,'NALLNS']):
                        self.dm['NUCLIDE'].C.loc[key,'NALLNS'] = 1
                    else:
                        self.dm['NUCLIDE'].C.loc[key,'NALLNS'] += 1
                    
                    # KALLNS update : all nuclides whose decay data is located after
                    # the changed one in the blank common are incremented by 2
                    refA = self.dm['NUCLIDE_POINTER'].C.loc[key,'KALLNS']
                    for AA in range(Legacy.NAMSMX):
                        for ZZww in range(min(Legacy.NZGVAX, Legacy.NZGVAX)):
                            ZZ = ZZww + self.dm['ADATA'].C.loc[AA + 1,'INWAPS']
                            kch = (AA+1, ZZ)
                            self.pointer_increment(key, 'KALLNS', AA+1, ZZ, 2)
                    
                    # KALISM update : all isomers whose decay data is located after
                    # the changed one in the blank common are incremented by 2     
                    for NISM in range(Legacy.NUMISM):
                        self.dm['ISOMER'].C.loc[NISM+1,'KALISM'] += 2
                    
                    self.parameters['LOFFS1'][0] += 2
                    
                # GAMMA LINES
                if vals['Decay'] == 'G':
                    # NGMLNS update : one more line
                    if pd.isna(self.dm['NUCLIDE'].C.loc[key,'NGMLNS']):
                        self.dm['NUCLIDE'].C.loc[key,'NGMLNS'] = 1
                    else:
                        self.dm['NUCLIDE'].C.loc[key,'NGMLNS'] += 1
                    
                    # KGMLNS update : all nuclides whose decay data is located after
                    # the changed one in the blank common are incremented by 2
                    refG = self.dm['NUCLIDE_POINTER'].C.loc[key,'KGMLNS']
                    for AA in range(Legacy.NAMSMX):
                        for ZZww in range(min(Legacy.NZGVAX, Legacy.NZGVAX)):
                            ZZ = ZZww + self.dm['ADATA'].C.loc[AA + 1,'INWAPS']
                            kch = (AA+1, ZZ)
                            self.pointer_increment(key, 'KGMLNS', AA+1, ZZ, 2)
                    
                    # KGMISM update : all isomers whose decay data is located after
                    # the changed one in the blank common are incremented by 2     
                    for NISM in range(Legacy.NUMISM):
                        self.dm['ISOMER'].C.loc[NISM+1,'KGMISM'] += 2
                    
                    self.parameters['LOFFS2'][0] += 2
                    
                # ELECTRON LINES
                if vals['Decay'] == 'E':
                    # NCELNS update : one more line
                    if pd.isna(self.dm['NUCLIDE'].C.loc[key,'NCELNS']):
                        self.dm['NUCLIDE'].C.loc[key,'NCELNS'] = 1
                    else:
                        self.dm['NUCLIDE'].C.loc[key,'NCELNS'] += 1
                    
                    # KCELNS update : all nuclides whose decay data is located after
                    # the changed one in the blank common are incremented by 2
                    refE = self.dm['NUCLIDE_POINTER'].C.loc[key,'KCELNS']
                    for AA in range(Legacy.NAMSMX):
                        for ZZww in range(min(Legacy.NZGVAX, Legacy.NZGVAX)):
                            ZZ = ZZww + self.dm['ADATA'].C.loc[AA + 1,'INWAPS']
                            kch = (AA+1, ZZ)
                            self.pointer_increment(key, 'KCELNS', AA+1, ZZ, 2)
                    
                    # KCEISM update : all isomers whose decay data is located after
                    # the changed one in the blank common are incremented by 2     
                    for NISM in range(Legacy.NUMISM):
                        self.dm['ISOMER'].C.loc[NISM+1,'KCEISM'] += 2
                    
                    self.parameters['LOFFS0'][0] += 2
                    
                # BETA LINES
                if vals['Decay'] in ['B+','B-']:
                    # Average energy should never be negative because that
                    # would create an inversion of beta type down the line
                    vals['Average E.'] =  abs(vals['Average E.'])
                    # NBTSPC update : one more line
                    if pd.isna(self.dm['NUCLIDE'].C.loc[key,'NBTSPC']):
                        self.dm['NUCLIDE'].C.loc[key,'NBTSPC'] = 1
                    else:
                        self.dm['NUCLIDE'].C.loc[key,'NBTSPC'] += 1
                    
                    # KBTSPC update : all nuclides whose decay data is located after
                    # the changed one in the blank common are incremented by 3
                    refB = self.dm['NUCLIDE_POINTER'].C.loc[key,'KBTSPC']
                    for AA in range(Legacy.NAMSMX):
                        for ZZww in range(min(Legacy.NZGVAX, Legacy.NZGVAX)):
                            ZZ = ZZww + self.dm['ADATA'].C.loc[AA + 1,'INWAPS']
                            kch = (AA+1, ZZ)
                            self.pointer_increment(key, 'KBTSPC', AA+1, ZZ, 3)
                    
                    # KBTISM update : all isomers whose decay data is located after
                    # the changed one in the blank common are incremented by 3    
                    for NISM in range(Legacy.NUMISM):
                        self.dm['ISOMER'].C.loc[NISM+1,'KBTISM'] += 3
                    
                    self.parameters['MOFFST'][0] += 3
                    
                table.add_record(tuple(kl),vals)
                
            table.C = table.C.sort_index()
            
        print(self.parameters['MOFFST'][0])
                    
    def import_transitions_DB(self, lvl_key, transitions):
        # Add the contents of a transition dictionary
        # to the corresponding (key) level
        
        # - Transitions are added to a level that does not have any yet
        # - Additions are limited to self.parameters["MEXMXB"][0]  (50)
        
        # Establish ranking of transitions, by decreasing branching
        
        print('--------------------')
        print(' IMPORT TRANSITIONS ')
        print('--------------------')
        print(f'Legacy max transitions per level: {self.parameters["MEXMXB"][0]}')
        
        normalized_tr = copy.deepcopy(transitions)
        
        for transition in transitions:
            rank = 0
            for compared in transitions:
                if transitions[compared]['Branching'] >= transitions[transition]['Branching']:
                    rank += 1
            transitions[transition]['Rank'] = rank
            
        # Operations on the branchings
        #    - Calculate total branching of 50 most intense transitions
        
        total_branching = 0.0
        for transition in transitions:
            if transitions[transition]['Rank'] <= self.parameters['MEXMXB'][0]:
                total_branching += transitions[transition]['Branching']
            else:
                normalized_tr.pop(transition)
        
        # Import one by one the new transitions in TRANSITION data module
        counter = 0
        for transition in normalized_tr:
            transition_key = (lvl_key[0],lvl_key[1],lvl_key[2],transition)
            self.dm['TRANSITION'].add_record(transition_key,normalized_tr[transition])
            counter += 1

        print(f'Imported transitions for Nuclide A={lvl_key[0]}, Z={lvl_key[1]}')
        print(f'{counter} transitions imported')
        print('')
                    
    def import_changes(self, chg):
        '''
        Importing changes from the py/ascii file and changing the
        corresponding values in the database
        '''
        #
        for table_name, key, field, val in chg:
            if table_name == 'PARAMETER':
                self.parameters[key][0] = val
            else:
                table = self.dm[table_name]
                table.C.loc[key, field] = val
        pass

    def conduct_DQ_tests(self, testInfra):
        pass

    def print_setup(self, folder_path):
        if folder_path[-1] != '/':
            folder_path = folder_path + '/'
        
        # If data was populated from JSON, use custom JSON formatter with DataModule file I/O
        if self._json_source_module is not None:
            from PyClasses.JSONParsing import NuclearDataModule
            print("Using JSON-specific ASCII formatting with DataModule file I/O...")
            
            for table_name, table in self.dm.items():
                table_path = folder_path + table_name
                os.makedirs(os.path.dirname(folder_path), exist_ok=True)
                filenameA = table_path + '.ascii'
                print(f'Printing table {table_name} to text file...\n')
                # Use DataModule's print_to_ascii with JSON custom formatter
                table.print_to_ascii(filenameA, custom_formatter=NuclearDataModule.json_ascii_formatter)
        
        # If data was populated from ENDF, use scientific notation for all floats
        elif hasattr(self, '_endf_source_module') and self._endf_source_module is not None:
            print("Using ENDF-specific ASCII formatting with scientific notation...")
            
            for table_name, table in self.dm.items():
                table_path = folder_path + table_name
                os.makedirs(os.path.dirname(folder_path), exist_ok=True)
                filenameA = table_path + '.ascii'
                print(f'Printing table {table_name} to text file...\n')
                # Use scientific notation for all numerical values
                table.print_to_ascii(filenameA, float_format=lambda x: "%.8e" % x)
        
        else:
            # Use legacy DataModule ASCII formatting for non-JSON data
            for table_name, table in self.dm.items():
                table_path = folder_path + table_name
                os.makedirs(os.path.dirname(folder_path), exist_ok=True)
                filenameA = table_path + '.ascii'
                print(f'Printing table {table_name} to text file...\n')
                table.print_to_ascii(filenameA)

    def build_to_legacy_DB(self, old_lgcy_db, output_folder, chg):
        '''
        Function rebuilding the binary legacy data library from
        scratch, based on the contents of the datamodules
        '''
        
        # 1. Set up new Legacy instance, empty (i.e. no need to parse
        #  the binary db)
        if Legacy is None:
            raise ImportError("Legacy functionality requires numpy/scipy dependencies. Please install them or use JSON-only workflows.")
        LGCY = Legacy(self.db_config, 'from_datamodules', path_lgcy=output_folder)

        # 2. Update all sizes in legacy description

        #upd_lgcy.updateSizes() # TO DO !!!

        # 3. Recreate the contents in legacy form
        
        print('========')
        print('Rebuilding the legacy database')
        LGCY.build_legacy_DB(self)

        # 4. Write the binary file based on the legacy-form contents

        print('========')
        print('Rebuilding the binary file, and conducting sanity checks')
        LGCY.encode_legacy_data(old_lgcy_db, output_folder, sanity=not chg)
    
    def aposteriori_data_manip(self):
        # Skip if ISOMER data module doesn't exist (e.g., in JSON-only configurations)
        if 'ISOMER' not in self.dm:
            print("Skipping aposteriori_data_manip: No ISOMER data module available")
            return
            
        if 'NUCLIDE' not in self.dm:
            print("Skipping aposteriori_data_manip: No NUCLIDE data module available")
            return
            
        # 1. Add level number to all isomers in the ISOMER table
        isom_table = self.dm['ISOMER'].C
        nucl_table = self.dm['NUCLIDE'].C
        
        isom_table["Lvl. Nb."] = [
            # Note: you *could* do the calculations directly here instead of using a
            # function call, so long as you don't have indented code blocks such as
            # sub-routines or multi-line if statements.
            #
            # I'm using a function call.
            self.calculate_lvl_nb(
                A,
                Z,
                mass_exc_iso,
                nucl_table.xs((A,Z), level=['Mass Nb.','At. Nb.'])['Mass Ex.'].values[0]
            ) for A, Z, mass_exc_iso
            in zip(
                isom_table["Mass Nb. Ism."],
                isom_table["At. Nb. Ism."],
                isom_table["Mass Ex. Ism."]
            )
        ]
        
        self.dm['ISOMER'].C = isom_table
        return None
        
    def calculate_lvl_nb(self, A, Z, me_iso, me_gs):
        level_table = self.dm['LEVEL']
        subdf = level_table.C.xs((A, Z), level=['Mass Nb.','At. Nb.']).sort_values('Energy')
        level_nb_isomer = subdf['Energy'].sub((me_iso-me_gs)*0.001).abs().idxmin()
        # Add a test against spin and parity of the level
        return level_nb_isomer
    
    def level_matching(self, db_to_match):
        '''
        Function completing level matching. For each fake level in the 'LEVEL' ensdf dm
        we retrieve the related transitions, calculate the energy of the daughter level and
        retrieve its level number should the match be good enough.
        We finally update the TRANSITION ensdf dm to reflect this newly found daughter level
        index.
        '''
        print('test')
        for ind, row in self.dm['LEVEL'].C.iterrows():
            AA = ind[0]
            ZZ = ind[1]
            print(f'Starting matching levels for A = {AA}, Z = {ZZ}')
            EN = row['Energy']
            
            # If no transitions have been recorded for the level, delete it from the data module
            # as it does not need to be added to the database
            # Not true anymore as we are happy to include a fake level without any transition
            # which means that 100% of transitions will go to the continuum.
            
            # if (AA, ZZ, 'Sn') not in self.dm['TRANSITION'].C.index:
            #     self.dm['LEVEL'].C.drop((AA, ZZ, 'Sn'), inplace=True)
            #     continue
            
            if (AA, ZZ) not in self.dm['TRANSITION'].C.index:
                continue
            
            tot_br = 0.0
            for i, r in self.dm['TRANSITION'].C.loc[(AA,ZZ,'Sn',slice(None))].iterrows():
                tot_br += r['Branching']
            
            for i, r in self.dm['TRANSITION'].C.loc[(AA,ZZ,'Sn',slice(None))].iterrows():
                TE = r['Energy']
                dau_energy = EN - TE
                tolr = 0.02
                rel_tol = 2.5e-3
                abs_tol = 5.0e-6
                found_index = retrieve_from_df(db_to_match.dm['LEVEL'].C.loc[(AA,ZZ,slice(None))], dau_energy, column_name='Energy', rel_tol=rel_tol, abs_tol=abs_tol)
                # found_index = db_to_match.dm['LEVEL'].retrieve('Energy', dau_energy)
                
                if found_index:
                    print(f' --  Found matching index for nuclide {AA} / {ZZ} : Level energy {dau_energy:e} correponds to level nb. {found_index}')
                    self.dm['TRANSITION'].C.loc[(AA,ZZ,'Sn-Matched',found_index)] = self.dm['TRANSITION'].C.loc[(AA,ZZ,'Sn',i)]
                else:
                    # max level index in db is 540
                    # multiplication by 1e9 guarantees no confusion in the 
                    # case of lower energy levels
                    int_dau_energy = int(1e9 * dau_energy)
                    self.dm['TRANSITION'].C.loc[(AA,ZZ,'Sn-Unmatched',int_dau_energy)] = self.dm['TRANSITION'].C.loc[(AA,ZZ,'Sn',i)]
                    print(f'    --  Daughter level not found {AA}/{ZZ} : Level energy {dau_energy:e} ')
                    print(f'           Transition added with parent tag {found_index}')
             
            tot_br2 = 0.0
            for i, r in self.dm['TRANSITION'].C.loc[(AA,ZZ,'Sn-Matched',slice(None))].iterrows():
                tot_br2 += r['Branching']
            
            
            # The matching process should preserve the total branching. In case some levels
            # are unmatched that contributed to the total branching, we now renormalize to the
            # calculated tot_br above
            for i, r in self.dm['TRANSITION'].C.loc[(AA,ZZ,'Sn-Matched',slice(None))].iterrows():
                self.dm['TRANSITION'].C.at[(AA,ZZ,'Sn-Matched',i),'Branching'] = r['Branching'] / tot_br2 * tot_br
            # Attention: unmatched levels remain un-normalized, at that point

        print('\n Done with the matching')
                    
                    
    def fake_lvl_transitions_printing(self, path_output):
        # Print the Thermal neutron capture-specific table to ascii
                # Define the list of isotopes as tuples: (A-1, Element_upper, Original_Element)
        #isotope_tuples = [
        #    (1, 1, 'H', 'H'),
        #    (12, 6, 'C', 'C'),
        #    (14, 7, 'N', 'N'),
        #    (16, 8, 'O', 'O'),
        #    (17, 8, 'O', 'O'),
        #    (21, 10, 'NE', 'Ne'),
        #    (24, 12, 'MG', 'Mg'),
        #    (28, 14, 'SI', 'Si'),
        #    (29, 14, 'SI', 'Si'),
        #    (39, 19, 'K', 'K'),
        #    (41, 20, 'CA', 'Ca'),
        #    (42, 20, 'CA', 'Ca'),
        #    (43, 20, 'CA', 'Ca'),
        #    (46, 22, 'TI', 'Ti'),
        #    (48, 22, 'TI', 'Ti'),
        #    (49, 22, 'TI', 'Ti'),
        #    (52, 24, 'CR', 'Cr'),
        #    (53, 24, 'CR', 'Cr'),
        #    (57, 26, 'FE', 'Fe'),
        #    (60, 28, 'NI', 'Ni'),
        #    (61, 28, 'NI', 'Ni'),
        #    (67, 30, 'ZN', 'Zn'),
        #    (83, 36, 'KR', 'Kr'),
        #    (90, 40, 'ZR', 'Zr'),
        #    (91, 40, 'ZR', 'Zr'),
        #    (94, 42, 'MO', 'Mo'),
        #    (95, 42, 'MO', 'Mo')
        #]
        #
        ## decaying nuclide rather than capturing -> +1
        #january_nuclides = [(aa[0] + 1, aa[1]) for aa in isotope_tuples]
        
        #self.dm['THERMAL_N_CAPT'].C = self.dm['THERMAL_N_CAPT'].C.loc[january_nuclides]
        
        
        # self.dm['THERMAL_N_CAPT'].print_to_ascii('THERMAL_N_CAPT.ascii',float_format=lambda x: "%1.3e"%x)
        
        # Filter down the list of nuclides to be corrected for thermal neutron capture
        # According to the following logic
        # - Reject nuclides that don't have a Normalization record in ENSDF
        filter1 = self.dm['THERMAL_N_CAPT'].filter('ENSDF Norm.')
        # - Reject nuclides for which the sum of branchings multiplied by the Normalization figure
        #   is larger than ceiling_norm
        
        ceiling_norm = 110.0 # [%]
        filter2 = filter1.filter('Total Branching x Norm', lambda x: x < ceiling_norm and x >= 0.0)

        # filter3 = ....      # Placeholder
        
        # In addition, printout the required changes to the nuclear.bin to ascii
        with open(path_output, 'w+') as f:
            for ind, row in self.dm['LEVEL'].C.iterrows():
                AA = ind[0]
                ZZ = ind[1]
                
                # Apply the filters computed above
                if (AA, ZZ) not in filter2.C.index:
                    continue                
                
                print('', file=f)
                flev = '("LEVEL", '
                flev += f'({AA}, {ZZ}), '
                flev += f'{{"Energy": {row["Energy"]:e}, "Fakeness": {row["Fakeness"]} }}),'
                print(flev, file=f)
                
                # If no transitions, go to next level directly
                if (AA, ZZ) not in self.dm['TRANSITION'].C.index:
                    continue
                else:
                    ftra = f'("TRANSITION", ({AA}, {ZZ}, None),'+' {'
                    print(ftra, file=f)
                #
                # Successfully matched levels
                for i, r in self.dm['TRANSITION'].C.loc[(AA,ZZ,'Sn-Matched',slice(None))].iterrows():
                    norm_at_printout = 100.0 / max(100.0, filter2.C.loc[(AA,ZZ)]['Total Branching x Norm'])
                    bran = r["Branching"] * norm_at_printout
                    # Normalize to the value of ENSDF Norm., then divide by 100 to go from % to absolute
                    bran = bran * self.dm['THERMAL_N_CAPT'].C.loc[(AA,ZZ)]['ENSDF Norm.'] / 100.0
                    ftra = f'{i}: {{"Energy": {r["Energy"]:e}, "Branching": {bran:e} }},'
                
                    print(ftra, file=f)
                
                print('}),', file=f)

    
    def ready_dm_for_F5(self):
        """ Function that:
        - filters down each data module to keep only fields that are useful to FLUKA5
        - transforms the NULL values back in to F4 sentinel values
        - Convert data types to numpy for subsequent binary export
        """
        
        for name, dm in self.dm.items():
            # Define structured dtype based on DataFrame columns and their types
            F5_fields = [field['general']['name'] for field in dm.desc['fields'] if field['F5']['relevant_to_F5']]
            filtered_dm = dm.C[F5_fields]
            df_copy = filtered_dm.copy()
            for field in filtered_dm.columns:
                default = self.db_config.get_fld_attr(field, 'sentinel', 'F5')
                # sentinel values are tuples for compounded fields
                # For those, pick the corresponding one (identifiable through
                # the last character of the name which is a digit)
                if len(default) > 1:
                    default = default[int(field[-1])]
                    
                # TOREMOVE meta = dm.desc["flds"].get(field, {})
                # TOREMOVE default = get_field_default(meta)

                # Only fill if a default is found
                if default is not None:
                    df_copy[field] = df_copy[field].fillna(default)
                else:
                    # Fallback or warning
                    df_copy[field] = df_copy[field].fillna(-999999)
                    print(f"Warning: No default for field '{field}', using fallback.")
            
            # Converting index to regular columns, for export purposes
            self.F5_dm[name] = df_copy.reset_index()
