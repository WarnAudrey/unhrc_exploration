#!/bin/bash
# Parse JEFF-4.0 radioactive decay database with VERBOSE output
# 
# This will parse the full JEFF-4.0 database and output ALL detailed transition data
# WARNING: Output file will be very large (200-500 MB for full database)
#
python3 JEFF_ENDF_parser.py --verbose /Users/audreywarn/fluka-db-audrey/data_input/endf/Radioactive_Decay_Data_JEFF-40.txt -o JEFF40_VERBOSE_analysis.txt
