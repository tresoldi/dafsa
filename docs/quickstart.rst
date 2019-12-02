How to use
==========

The library offers a ``DAFSA`` object to compute automata, along with
methods for checking a sequence acceptance and for exporting the graph.
A minimal usage is shown here:

.. code:: python

   >>> import dafsa
   >>> d = dafsa.DAFSA(["tap", "taps", "top", "tops", "dibs"])
   >>> print(d)
   DAFSA with 7 nodes and 8 edges (5 sequences)
     +-- #0: 0(#1:<d>/1|#5:<t>/4) [('t', 5), ('d', 1)]
     +-- #1: n(#2:<i>/1) [('i', 2)]
     +-- #2: n(#3:<b>/1) [('b', 3)]
     +-- #3: n(#4:<s>/3) [('s', 4)]
     +-- #4: F() []
     +-- #5: n(#6:<a>/2|#6:<o>/2) [('o', 6), ('a', 6)]
     +-- #6: n(#3:<p>/4) [('p', 3)]

Note how the resulting graph includes the 5 training sequences, with one
starting node (#0) that advances with either a ``t`` (observed four
times) or a ``d`` symbol (observed a single time), a subsequent node to
``t`` that only advances with ``a`` and ``o`` symbols (#1), and so on.

The visualization is much clearer with a graphical representation:

.. code:: python

   >>> d.graphviz_output("example.png")

.. figure:: https://raw.githubusercontent.com/tresoldi/dafsa/master/figures/example.png
   :alt: First example

   First example

A DAFSA object allows to check for the presence or absence of a sequence
in its structure, returning a terminal node if it can find a path:

.. code:: python

   >>> d.lookup("tap")
   F(#4:<s>/3)
   >>> d.lookup("tops")
   F()
   >>> d.lookup("tapap") is None
   True
   >>> d.lookup("ta") is None
   True

A command-line tool for reading files with lists of strings, with one
string per line, is also available:

::

   $ cat resources/dna.txt
   CGCGAAA
   CGCGATA
   CGGAAA
   CGGATA
   GGATA
   AATA

   $ dafsa resources/dna.txt -t png -o dna.png

Which will produce the following graph:

.. figure:: https://raw.githubusercontent.com/tresoldi/dafsa/master/figures/dna.png
   :alt: DNA example

   DNA example

Sequences are by default processed one character at time, with each
character assumed to be a single token. Pre-tokenized data can be
provided to the library in the format of a Python list or tuple, or
specified in source by using spaces as token delimiters:

.. code:: bash

   $ cat resources/phonemes.txt
   o kː j o
   o r e kː j o
   n a z o
   s e n t i r e
   s e n s o
   ɡ u a r d a r e
   a m a r e
   v o l a r e

   $ dafsa resources/phonemes.txt -t png -o phonemes.png

.. figure:: https://raw.githubusercontent.com/tresoldi/dafsa/master/figures/phonemes.png
   :alt: Phoneme example

   Phoneme example