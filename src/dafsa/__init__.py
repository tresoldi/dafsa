# __init__.py

# Version of the dafsa package
__version__ = "2.0"  # remember to sync with setup.py
__author__ = "Tiago Tresoldi"
__email__ = "tiago.tresoldi@lingfil.uu.se"

# Import from local modules
from .common import build_dafsa, read_words, extract_sequences, graphviz_output
from .minimize import (
    build_minim_array,
    merge_child_list,
    merge_redundant_nodes,
    minimize_trie,
)
from .node import Node

# Build namespace
__all__ = [
    "build_dafsa",
    "extract_sequences",
    "graphviz_output",
    "read_words",
]
