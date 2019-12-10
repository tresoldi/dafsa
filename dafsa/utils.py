"""
Module holding a number of utility functions.

The module also exports a `RESOURCE_DIR` object of type `pathlib.Path`,
pointing to the local `resources` directory.
"""

# Import Python libraries
import itertools
from pathlib import Path

# Set the resource directory; this is sage as we already added
# `zip_safe=False` to setup.py
RESOURCE_DIR = Path(__file__).parent.parent / "resources"


def common_prefix_length(seq_a, seq_b):
    """
    Return the length of the common prefix between two sequences.

    Parameters
    ----------
    seq_a : iter
        An iterable holding the first sequence.
    seq_b : iter
        An iterable holding the second sequence.

    Returns
    -------
    length: int
        The length of the common prefix between `seq_a` and `seq_b`.

    Examples
    --------

    >>> import dafsa
    >>> dafsa.utils.common_prefix_length("abcde", "abcDE")
    3
    >>> dafsa.utils.common_prefix_length("abcde", "ABCDE")
    0
    """

    common_prefix_len = 0
    for i in range(min(len(seq_a), len(seq_b))):
        if seq_a[i] != seq_b[i]:
            break
        common_prefix_len += 1

    return common_prefix_len


def pairwise(iterable):
    """
    Iterate pairwise over an iterable.

    The function follows the recipe offered on Python's `itertools`
    documentation.

    Parameters
    ----------
    iterable : iter
        The iterable to be iterate pairwise.

    Examples
    --------

    >>> import dafsa
    >>> list(dafsa.utils.pairwise([1,2,3,4,5]))
    [(1, 2), (2, 3), (3, 4), (4, 5)]
    """

    elem_a, elem_b = itertools.tee(iterable)
    next(elem_b, None)

    return zip(elem_a, elem_b)
