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

This work describes [`dafsa`](https://pypi.org/project/dafsa/), a Python library for computing graphs from lists of strings for identifying, visualizing, and inspecting patterns of substrings. The library is designed for usage by linguists in studies on morphology and formal grammars, and is intended for faster, easier, and simpler generation of visualizations.
It collects frequency weights by default, it can condense structures, and it provides several export options.
Figure 1 depicts a basic DAFSA, based upon five English words and generated with default settings.

![Visual representation of a DAFSA for the list of strings `"dibs"`, `"tap"`, `"top"`, `"taps"`, and `"tops"`.](https://raw.githubusercontent.com/tresoldi/dafsa/master/figures/example.png)

# Background

Deterministic Acyclic Finite State Automata (DAFSA, also known as "Directed Acyclic Word Graphs", or DAWG) are data structures extended from tries and used to describe collections of strings through directed acyclic graphs with a sole source vertex (the `start` of all sequences), at least one sink node (each pointed to by one or more edges), and edge labels carrying information on the sequence of characters that form the strings [@Black:2008; @Blumer:1985; @Lucchesi:1993]. A compact variant [@Crochemore:1997] condenses the structure by merging every node which is an only child with its parent, concatenating their labels. The resulting graph is a particular finite state recognizer, accepting all and only the strings from the original list.

DAFSAs are mostly used for the memory-efficient storage of sets of strings, such as in spelling correction and in non-probabilistic set membership check [@Blumer:1985; @Ciura:2001; @Lucchesi:1993; @Havon:2011]. While there have been proposals for applying them to the treatment and analysis of pattern repetitions, especially in genomics [@Crochemore:1997], no general-purpose library designed for such exploration and visualization is available. In specific, as a consequence of most implementations being designed for an efficient set membership testing, no available library builds DAFSAs that collect node and edge frequency.

# Installation, Usage, & Examples

The library can be installed with the standard `pip` tool for
package management:

```bash
$ pip install dafsa
```

The [documentation](https://dafsa.readthedocs.io/en/latest/quickstart.html)
offers detailed instructions on how to use the library.
For most purposes it is sufficient to create a new `DAFSA` object and
initialize it with the list of strings, as in the generation of the graph
for Figure 1:

```python
>>> from dafsa import DAFSA
>>> d = DAFSA(["dib", "tap", "top", "taps", "tops"])
```

The library will by default collect frequency weights for each edge and node.
We can export the resulting structures in either a custom textual format (using the standard
`repr()` command)
or in GML format (using the `.write_gml()` method),
or convert them to equivalent graphs in the `networkx` library (using the
`.to_graph()` method). Visualizations can be
generated through DOT source code (using the `.to_dot()` method), and
manipulated according to the users' preferences and needs. An auxiliary
`.write_figure()` method allows to generate figures in PNG, SVG,
or PDF format if `graphviz` is available, as in Figure 2.

![A non-condensed DAFSA for a list of 9 Italian words phonetically
transcribed.](https://raw.githubusercontent.com/tresoldi/dafsa/master/figures/phonemes.png)

Graphs are not condensed by default, as in Figure 2, but condensation
can be performed by setting the `condense` flag when initializing the
object, as done in the following code snippet and illustrated in Figure 3:

```python
>>> words = [
    "o k: j o", "o r e k: j o", "n a z o",
    "s e", "s e n t i r e", "s e n s o",
    "g u a r d a r e", "a m a r e", "v o l a r e"]
>>> words = [word.split() for word in words]
>>> d = DAFSA(words, condense=True)
```

![A condensed DAFSA for the same list of 9 Italian words phonetically
transcribed used in Figure 2.](https://raw.githubusercontent.com/tresoldi/dafsa/master/figures/reduced_phonemes.png)

A command-line `dafsa` tool is provided along with the library.
Assuming the data is found in a `phonemes.txt`
file, with one sequence per line, a PDF version of Figure 3 can be
generated with the following call, where `-c` instructs to condense the
graph, `-t` specifies the output format, and `-o` the output file:

```bash
$ dafsa -c -t pdf -o phonemes.pdf phonemes.txt
```

# Alternatives

The main alternatives to this library,
such as the Python [`DAWG` package](https://github.com/pytries/DAWG),
are based on `dwagdic` C++ library,
designed for production usage of memory- and speed-efficient data
structures. The unsupported `adfa` and `minim` packages by
@Daciuk:2000 are closer in intention, as well as the Python
prototype by @Havon:2011. Similar functionalities are offered by several
tools for analysis of genetic data, usually as an extension of
sequence alignments, but none as an autonomous tool that can be employed
with generic lists of strings.

# Code and Documentation Availability

The `dafsa` source code is available on GitHub at
[https://github.com/tresoldi/dafsa](https://github.com/tresoldi/dafsa).

The documentation is available at
[https://dafsa.readthedocs.io/](https://dafsa.readthedocs.io/).

# Acknowledgements

The author has received funding from the European Research Council (ERC)
under the European Union’s Horizon 2020 research and innovation
programme (grant agreement
No. [ERC Grant #715618](https://cordis.europa.eu/project/rcn/206320/factsheet/en),
[Computer-Assisted Language Comparison](https://digling.org/calc/)).

# References
