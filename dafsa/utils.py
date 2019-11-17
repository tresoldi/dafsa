# encoding: utf-8

# Import Python libraries
import itertools
from pathlib import Path

# Set the resource directory; this is sage as we already added
# `zip_safe=False` to setup.py
RESOURCE_DIR = Path(__file__).parent.parent / "resources"

# Define some auxiliary functions
def common_prefix_length(seq_a, seq_b):
    """
    Returns the length of the common prefix between two sequences.
    """

    common_prefix_len = 0
    for i in range(min(len(seq_a), len(seq_b))):
        if seq_a[i] != seq_b[i]:
            break
        common_prefix_len += 1

    return common_prefix_len


def pairwise(iterable):
    """
    Iterates pairwise over an iterable.

    s -> (s0,s1), (s1,s2), (s2, s3), ...
    """

    elem_a, elem_b = itertools.tee(iterable)
    next(elem_b, None)

    return zip(elem_a, elem_b)
