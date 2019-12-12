---
title: 'DAFSA: a Python library for Deterministic Acyclic Finite State Automata'
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
 - name: Department of Linguistic and Cultural Evolution, Max Planck Institute for the Science of Human History
   index: 1
date: 12 December 2019
bibliography: paper.bib
---

# Summary

Deterministic Acyclic Finite State Automata (DAFSA, also known as "directed acyclic word graphs", or DAWG) are data structures derived from tries that represent sequences by means of a directed acyclic graph with a single source vertex (the `start` symbol of all sequences) and at least one sink edge (`final` symbols, each pointed to by one or more sequences), with edge labels reporting the single characters that compose the strings [@Black:2008, @Blumer:1985, @Lucchesi:1993]. A compact variant [@Crochemore:1997] condenses the structure by merging every node which is an only child with its parent, concatenating the labels. The resulting graph can be used as special type of finite state recognizer acting as a deterministic finite state automaton, accepting all and only the sequences it was built upon. An illustration of a basic DAFSA is provided in Figure 1.

![Visual representation of a DAFSA for the list of sequences [`"dibs"`, `"tap"`, `"top"`, `"taps"`, `"tops"`]](https://raw.githubusercontent.com/tresoldi/dafsa/master/figures/example.png)

DAFSAs are commonly used for the space-efficient storage of sets of sequences, particularly in spell checking and in non-probabilistic set membership check [@Blumer:1985; @Ciura:2001; @Lucchesi:1993; @Havon:2011]. While they have already been proposed for treating and analyzing repetitions in texts and patterns of subsequences, especially in genomics [@Crochemore:1997], no general-purpose library is available for visualization and human exploration. One aspect not considered by the available implementations, a consequence of the design for set membership testing, is the potential of DAFSAs for investigating frequencies of subsequences, providing an alternative structural and graphical visualization for language models.

Here we describe [`dafsa`](https://pypi.org/project/dafsa/), a Python library for computing these automata and designed for exploring their potential usage in linguistic morphology and general investigation of lists of sequences with shared patterns. Structures can be condensed if desired and frequency weights are collected by default. While the data structure is designed for manipulation and investigation, it is computationally efficient for most purposes, typically processing a standard `/usr/share/dict/words` wordlist of about 100,000 sequences in under 10 minutes.

# Installation, Usage, & Examples

The library can be installed with the standard `pip` tool for
package management. Detailed instructions on how to use the library
can be found in the [official documentation](https://dafsa.readthedocs.io/en/latest/quickstart.html),
but for most purposes it is enough to create a new `DAFSA` object and
initialize it with the list of strings:

```python
>>> from dafsa import DAFSA
>>> d = DAFSA(["dib", "tap", "top", "taps", "tops"])
```

The library will by default collect frequency weights for each edge,
so that repeated observations are accounted for. The resulting structures
can be exported in either a custom textual format (using Python's standard
`.__str__()` and `.__repr__()` methods)
or in GML format (using the `.write_gml()` method),
as well as converted to equivalent `networkx` graphs (using the
`.to_graph()` method). Visualizations can
generated through DOT source code (using the `.to_dot()` method), and
manipulated according to the users' preferences and needs. An auxiliary
`.write_figure()` method allows to quickly generate figures in PNG, SVG,
or PDF format if `graphviz` is available, as in Figure 2.

![Non-condensed](https://raw.githubusercontent.com/tresoldi/dafsa/master/figures/phonemes.png)

The structures are not condensed by default, as in Figure 2, but condensation
can be performed by setting the `condense` flag when initializing the
object, as in the following snippet and Figure 3:

```python
>>>
"o kː j o"
"o r e kː j o"
"n a z o"
"s e"
"s e n t i r e"
"s e n s o"
"ɡ u a r d a r e"
"a m a r e"
"v o l a r e"
```

![condensed](https://raw.githubusercontent.com/tresoldi/dafsa/master/figures/reduced_phonemes.png)

A command-line `dafsa` tool is provided along with the library and allows
to perform all the actions. Assuming the data resides in a `phonemes.txt`
file, with one sequence per line, a PDF version of Figure 3 can be
generated with the following call, where `-c` instructs to condense the
graph, `-t` specifies the output format, and `-o` the output file:

```bash
$ dafsa -c -t pdf -o phonemes.pdf phonemes.txt
```

# Alternatives

The main alternatives to this library are based on `dwagdic` C++ library,
intended for production usage as memory-efficient data
structures, or on unsupported `adfa` and `minim` packages by
@Daciuk:2000.

# Acknowledgements

The author has received funding from the European Research Council (ERC)
under the European Union’s Horizon 2020 research and innovation
programme (grant agreement
No. [ERC Grant #715618](https://cordis.europa.eu/project/rcn/206320/factsheet/en)),
[Computer-Assisted Language Comparison](https://digling.org/calc/).

# References
