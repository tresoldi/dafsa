# __init__.py

# Version of the ngesh package
__version__ = "0.2"
__author__ = "Tiago Tresoldi"
__email__ = "tresoldi@shh.mpg.de"

# Import Python libraries
from pathlib import Path

# Set the resource directory; this is sage as we already added
# `zip_safe=False` to setup.py
RESOURCE_DIR = Path(__file__).parent.parent / "resources"

# Build the namespace
from dafsa.dafsa import DAFSA
