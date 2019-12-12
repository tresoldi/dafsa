# __init__.py

"""
__init__ file for the DAFSA library.

This single file allows to load the library and the main object easily,
as in:

.. code:: python

   >>> from dafsa import DAFSA
   >>> d = DAFSA(["tap", "taps", "top", "tops", "dibs"])
   >>> print(d)
   DAFSA with 7 nodes and 8 edges (5 sequences)
     +-- #0: 0(#1:<d>/1|#5:<t>/4) [('t', 5), ('d', 1)]
     +-- #1: n(#2:<i>/1) [('i', 2)]
     +-- #2: n(#3:<b>/1) [('b', 3)]
     +-- #3: n(#4:<s>/3) [('s', 4)]
     +-- #4: F() []
     +-- #5: n(#6:<a>/2|#6:<o>/2) [('o', 6), ('a', 6)]
     +-- #6: n(#3:<p>/4) [('p', 3)]
"""

# Version of the dafsa package
__version__ = "0.5.1"
__author__ = "Tiago Tresoldi"
__email__ = "tresoldi@shh.mpg.de"

# Build the namespace
from dafsa.dafsa import DAFSANode, DAFSAEdge, DAFSA
