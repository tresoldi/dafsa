---
title: 'DAFSA: A Python library for Deterministic Acyclic Finite State Automata'
tags:
  - Python
  - finite state automata
  - deterministic acyclic finite state automaton
  - directed acyclic word graph
  - sequence analysis
  - morphology
authors:
  - name: Tiago Tresoldi
    orcid: 0000-0002-2863-1467
    affiliation: 1 # (Multiple affiliations must be quoted)
affiliations:
 - name: post-doc, Max Planck Institute for the Science of Human History
   index: 1
date: 12 December 2019
bibliography: paper.bib
---

# Summary

``DAFSA`` is a Python library for computing [Deterministic Acyclic Finite State Automata](https://en.wikipedia.org/wiki/Deterministic_acyclic_finite_state_automaton) (also known as "directed acyclic word graphs", or DAWG). DAFSA are data structures derived from tries that allow to represent sequences by means of a directed acyclic graph with a single source vertex (the `start` symbol of all sequences) and at least one sink edge (`final` symbols, each pointed to by one or more sequences) [@Black:2008, @Blumer:1985, @Lucchesi:1993], with edge labels reporting the single characters that compose the strings. A compact variant [@Crochemore:1997] condenses the structure by merging every node which is an only child with its parent, concatenating the labels. The resulting structure is a finite state recognizer that acts as a deterministic finite state automaton,
as it recognizes all and only the sequences it was built upon. An illustration
is provided in Figure 1, with the DAFSA for the list of sequences
`dibs`, `tap`, `top`, `taps`, `tops`.

![Example](https://raw.githubusercontent.com/tresoldi/dafsa/master/figures/example.png)

The data structure is commonly used for the space-efficient storage of sets of sequences, particularly in spell checking and in non-probabilistic
set membership [@Blumer:1985; @Ciura:2001; @Lucchesi:1993; @Havon:2011].
While it has previously been explored for treating and analyzing
repetitions in texts and patterns of subsequences,
especially in genomics [@Crochemore:1997], no general-purpose software
package seems to be designed for this purpose, particularly for the
potential of using DAFSAs in linguistic morphology. The main alternatives
to this library are based on `dwagdic` C++
library, intended for production usage as memory-efficient data
structures, or on unsupported `adfa` and `minim` packages by
@Daciuk:2000.

The library here presented...

# Installation and usage

The library can be installed with the standard `pip` tool for
package management. Detailed instructions on how to use the library
can be found in the [official documentation](https://dafsa.readthedocs.io/en/latest/quickstart.html),
but for most purposes it is enough to create a new `DAFSA` object and
initialize it with the list of strings:

```python
>>> from dafsa import DAFSA
>>> d = DAFSA(["dib", "tip", "tips", "top"])
```

The library will by default collect frequency weights for each edge,
and allows to represent the resulting structure in either a custom textual
format (using Python standard `.__str__()` and `.__repr__()` methods)
or in standard GML format (HOW). Visualizations can be produced thorough
DOT source code (generated with the `.NAME()` method), with out-of-the-box
support for exporting as PNG, SVG, or PDF (NAME METHODS). Equivalent
`networkx` graphs can be generated with the NAME method.

Command-line

Condensed versions are not computed by default, but...

# Acknowledgements

The author has received funding from the European Research Council (ERC)
under the European Union’s Horizon 2020 research and innovation
programme (grant agreement
No. [ERC Grant #715618](https://cordis.europa.eu/project/rcn/206320/factsheet/en)),
[Computer-Assisted Language Comparison](https://digling.org/calc/).

# References
