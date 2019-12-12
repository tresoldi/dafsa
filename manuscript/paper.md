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

Deterministic Acyclic Finite State Automata (DAFSA, also known as "directed acyclic word graphs", or DAWG) are data structures derived from tries used to represent collections of strings by means of directed acyclic graphs with a single source vertex (the `start` of all sequences), at least one sink node (each pointed to by one or more edges), and edge labels carrying information on the sequence of characters that compose the strings [@Black:2008; @Blumer:1985; @Lucchesi:1993]. A compact variant [@Crochemore:1997] condenses the structure by merging every node which is an only child with its parent, concatenating the labels. The resulting graph can be used as special type of finite state recognizer, accepting all and only the strings it was built upon. An illustration of a basic DAFSA is provided in Figure 1.

![Visual representation of a DAFSA for the list of strings `"dibs"`, `"tap"`, `"top"`, `"taps"`, and `"tops"`.](https://raw.githubusercontent.com/tresoldi/dafsa/master/figures/example.png)

DAFSAs are commonly used for the memory-efficient storage of sets of strings, particularly in spell checking and in non-probabilistic set membership check [@Blumer:1985; @Ciura:2001; @Lucchesi:1993; @Havon:2011]. While there have been proposals for using them in treating and analyzing pattern repetitions, especially in genomics [@Crochemore:1997], no general-purpose library designed for such exploration and visualization is available. In particular, as a consequence of the available implementations being designed for efficient set membership testing, no library exploring the potential of DAFSAs for investigating frequency of substring patterns, providing an alternative to structural and graphical visualization of language models or grammars, is available.

This work describes [`dafsa`](https://pypi.org/project/dafsa/), a Python library for computing these automata and designed for usage in linguistic morphology and formal grammars in general. Structures can be condensed if desired, frequency weights are collected by default, and a number of export options are offered.

# Installation, Usage, & Examples

The library can be installed with the standard `pip` tool for
package management.

```bash
$ pip install dafsa
```

Detailed instructions on how to use the library
are given in the [documentation](https://dafsa.readthedocs.io/en/latest/quickstart.html),
but for most purposes it is enough to create a new `DAFSA` object and
initialize it with the list of strings:

```python
>>> from dafsa import DAFSA
>>> d = DAFSA(["dib", "tap", "top", "taps", "tops"])
```

The library will by default collect frequency weights for each edge and node.
The resulting structures
can be exported in either a custom textual format (using the standard
`repr()` command)
or in GML format (using the `.write_gml()` method),
as well as converted to equivalent `networkx` graphs (using the
`.to_graph()` method). Visualizations can
generated through DOT source code (using the `.to_dot()` method), and
manipulated according to the users' preferences and needs. An auxiliary
`.write_figure()` method allows to quickly generate figures in PNG, SVG,
or PDF format if `graphviz` is available, as in Figure 2.

![A non-condensed DAFSA for a list of 9 Italian words phonetically
transcribed.](https://raw.githubusercontent.com/tresoldi/dafsa/master/figures/phonemes.png)

The structures are not condensed by default, as in Figure 2, but condensation
can be performed by setting the `condense` flag when initializing the
object, as done in the following snippet and illustrated in Figure 3:

```python
>>> words = [
    "o kː j o", "o r e kː j o", "n a z o",
    "s e", "s e n t i r e", "s e n s o",
    "g u a r d a r e", "a m a r e", "v o l a r e"]
>>> d = DAFSA(words, condense=True) # SEPARATOR
```

![A condensed DAFSA for the same list of 9 Italian words phonetically
transcribed used in Figure 2.](https://raw.githubusercontent.com/tresoldi/dafsa/master/figures/reduced_phonemes.png)

A command-line `dafsa` tool is provided along with the library.
Assuming the data reside in a `phonemes.txt`
file, with one sequence per line, a PDF version of Figure 3 can be
generated with the following call, where `-c` instructs to condense the
graph, `-t` specifies the output format, and `-o` the output file:

```bash
$ dafsa -c -t pdf -o phonemes.pdf phonemes.txt
```

# Alternatives

The main alternatives to `dafsa`,
such as the Python [`DAWG` library](https://github.com/pytries/DAWG),
are based on `dwagdic` C++ library,
designed for production usage as memory-efficient data
structures. The unsupported `adfa` and `minim` packages by
@Daciuk:2000 are closer in intention, as well as the Python
prototype by @Havon:2011. Similar functionalities are offered by a number
of tools for analysis of genetic data, usually as a visualization of
sequence alignments, but none as an independent tool that can be used
with generic lists of strings.

# Code Availability

The `dafsa` source code is on GitHub at
[https://github.com/tresoldi/dafsa](https://github.com/tresoldi/dafsa)
and the documentation is at
[https://dafsa.readthedocs.io/](https://dafsa.readthedocs.io/).

# Acknowledgements

The author has received funding from the European Research Council (ERC)
under the European Union’s Horizon 2020 research and innovation
programme (grant agreement
No. [ERC Grant #715618](https://cordis.europa.eu/project/rcn/206320/factsheet/en)),
[Computer-Assisted Language Comparison](https://digling.org/calc/).

# References
