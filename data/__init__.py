# Marks data directory as a Python package
# Can contain data loading/processing utilities

import os
from pathlib import Path

DATA_DIR = Path(__file__).parent

def get_data_path(filename):
    """Helper to get absolute paths to data files"""
    return str(DATA_DIR / filename)