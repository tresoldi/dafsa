# DAFSA

[![PyPI](https://img.shields.io/pypi/v/dafsa.svg)](https://pypi.org/project/dafsa)
[![Build Status](https://travis-ci.org/tresoldi/dafsa.svg?branch=master)](https://travis-ci.org/tresoldi/dafsa)
[![codecov](https://codecov.io/gh/tresoldi/dafsa/branch/master/graph/badge.svg)](https://codecov.io/gh/tresoldi/dafsa)
[![Codacy
Badge](https://api.codacy.com/project/badge/Grade/a2b47483ff684590b1208dbb4bbfc3ee)](https://www.codacy.com/manual/tresoldi/dafsa?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=tresoldi/dafsa&amp;utm_campaign=Badge_Grade)

DAFSA is a library for computing [Deterministic Acyclic Finite State Automata](https://en.wikipedia.org/wiki/Deterministic_acyclic_finite_state_automaton) (also known as "directed acyclic word graphs", or DAWG). DAFSA are data structures derived from [tries](https://en.wikipedia.org/wiki/Trie) that allow to represent a set of sequences (typically character strings or *n*-grams) in the form of a directed acyclic graph with a single source vertex (the `start` symbol of all sequences) and at least one sink edge (`end` symbols, each pointed to by one or more sequences). In the current implementation, a trait of each node expresses whether it can be used a sink.

The primary difference between DAFSA and tries is that the latter eliminates suffix and infix redundancy, as in the example of Figure 1 (from the linked Wikipedia article) storing the set of strings `"tap"`, `"taps"`, `"top"`, and `"tops"`. Even though DAFSAs cannot be used to store precise frequency information, given that multiple paths can reach the same terminal node, they still allow to estimate the sampling frequency; being acyclic, they can also reject any sequence not included in the training. Fuzzy extensions will allow to estimate the sampling probability of unobserved sequences.

![Trie vs. DAFSA](https://raw.githubusercontent.com/tresoldi/dafsa/master/doc/trie-vs-dafsa.png)

This data structure is a special case of a finite state recognizer that acts as a deterministic finite state automaton, as it recognizes all and only the sequences it was built upon. Frequently used in computer science for the space-efficient storage of sets of sequences without common compression techniques, such as dictionary or entropy types, or without probabilistic data structures, such as Bloom filters, the automata generated by this library are intended for linguistic exploration, and extend published models by allowing to approximate probability of random observation by carrying information on the weight of each graph edge.

## Installation

In any standard Python environment, `dafsa` can be installed with:

```
pip install dafsa
```

## How to use

The library offers a `DAFSA` object to compute automata, along with methods for checking a sequence acceptance and for exporting the graph. A minimal usage is shown here:

```python
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
```

Note how the resulting graph includes the 5 training sequences, with one starting node (#0) that advances with either a `t` (observed four times) or a `d` symbol (observed a single time), a subsequent node to `t` that only advances with `a` and `o` symbols (#1), and so on.

The visualization is much clearer with a graphical representation:

```python
>>> d.graphviz_output("example.png")
```

![First example](https://raw.githubusercontent.com/tresoldi/dafsa/master/doc/example.png)

A DAFSA object allows to check for the presence or absence of a sequence in its structure, returning a terminal node if it can find a path:

```python
>>> d.lookup("tap")
F(#4:<s>/3)
>>> d.lookup("tops")
F()
>>> d.lookup("tapap") is None
True
>>> d.lookup("ta") is None
True
```

A command-line tool for reading files with lists of strings, with one string per line, is also available:

```
$ cat resources/dna.txt
CGCGAAA
CGCGATA
CGGAAA
CGGATA
GGATA
AATA

$ dafsa resources/dna.txt -t png -o dna.png
```

Which will produce the following graph:

![DNA example](https://raw.githubusercontent.com/tresoldi/dafsa/master/doc/dna.png)

Sequences are by default processed one character at time, with each character
assumed to be a single token. Pre-tokenized data can be provided to the
library in the format of a Python list or tuple, or specified in source by
using spaces as token delimiters:

```bash
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
```

![Phoneme example](https://raw.githubusercontent.com/tresoldi/dafsa/master/doc/phonemes.png)

## Changelog

Version 0.3:
  - Allow to join transitions in single sub-paths

Version 0.2.1:

  - Added support for segmented data

Version 0.2:

  - Added support for weighted edges and nodes
  - Added DOT export and Graphviz generation
  - Refined minimization method, which can be skipped if desired (resulting
    in a standard trie)
  - Added examples in the resources, also used for test data

Version 0.1:

  - First public release.

## Roadmap

Version 0.3:

  - Start integration with `networkx`, including:
    - Exporting DAFSA in standard network formats
    - Computation of shortest or *k*-shortest paths, along with
    cumulative edge and/or node weights

Version 0.4:

  - Profile code and make faster and less resource hungry, using
    multiple threads wherever possible, memoization, etc.
  - Work on options for nicer graphviz output (colors, widths, etc.)
  - Decide how (and if) to implement a `.__gt__()` method for
    the nodes, both before and after the final minimization
  - Allow to replace final nodes with edges to ``end-of-sequence``
      nodes (possibly as a default)

Version 1.0:

  - Full documentation
  - Add code from Daciuk's packages in an extra directory, along with
    notes on license

After 1.0:

  - Preliminary generation of minimal regular expressions matching the
    contents of a DAFSA
  - Consider the addition of empty transitions (or depend on the user
    aligning those)

Please note that this library is under development and still needs performance optimizations: common experiments such as building a DAFSA for the contents of `/usr/share/dict/words` will take many minutes in a common machine.

## Alternatives

The main alternative to this library is the `dawg` one, available at [https://github.com/pytries/DAWG](https://github.com/pytries/DAWG). `dawg` wraps the `dwagdic` C++ library, and is intended to production usage of DAFSAs as a space-efficient data structure. It does not support the computation of edge weights, nor it is intended for exporting the internal structure as a graph.

Other alternatives are the `adfa` and `minim` packages, written in C/C++, written by Jan Daciuk. The personal webpage hosting them has been offline for years, with a version at the [Wayback Machine](https://web.archive.org/web/20160531133017/http://galaxy.eti.pg.gda.pl/katedry/kiw/pracownicy/Jan.Daciuk/personal/minim.html) available. Note that the archived version does *not* include the packages.

## How to cite

If you use `dafsa`, please cite it as:

> Tresoldi, Tiago (2019). DAFSA, a a library for computing Deterministic Acyclic Finite State Automata. Version 0.2.1. Jena. Available at: <https://github.com/tresoldi/dafsa>

In BibTeX:

```bibtex
@misc{Tresoldi2019dafsa,
  author = {Tresoldi, Tiago},
  title = {DAFSA, a a library for computing Deterministic Acyclic Finite State Automata. Version 0.2.1},
  howpublished = {\url{https://github.com/tresoldi/dafsa}},
  address = {Jena},
  year = {2019},
}
```

## References

Black, Paul E. and Pieterse, Vreda (eds.). 1998. "Directed acyclic word graph", *Dictionary of Algorithms and Data Structures*. Gaithersburg: National Institute of Standards and Technology.

Blumer, Anselm C.; Blumer, Janet A.; Haussler, David; Ehrenfeucht, Andrzej; Chen, M.T.; Seiferas, Joel I. 1985. "The smallest automaton recognizing the subwords of a text", *Theoretical Computer Science*, 40: 31–55. [doi:10.1016/0304-3975(85)90157-4](https://doi.org/10.1016%2F0304-3975%2885%2990157-4).

Ciura, Marcin G. and Deorowicz, Sebastian. 2002. "How to sequeeze a lexicon", *Software-Practice and Experience* 31(11):1077-1090.

Daciuk, Jan; Mihov, Stoyan; Watson, Bruce and Watson, Richard. 2000. "Incremental construction of minimal acyclic finite state automata." *Computational Linguistics* 26(1):3-16.

Havon, Steve. 2011. "Compressing dictionaries with a DAWG". *Steve Hanov's Blog*. [url](http://stevehanov.ca/blog/?id=115)

Lucchesi, Cláudio L. and Kowaltowski, Tomasz. "Applications of finite automata representing large vocabularies". *Software-Practice and Experience*. 1993: 15–30. [CiteSeerX 10.1.1.56.5272](https://citeseerx.ist.psu.edu/viewdoc/summary?doi=10.1.1.56.5272).

## Author

Tiago Tresoldi (tresoldi@shh.mpg.de)

The author was supported during development by the
[ERC Grant #715618](https://cordis.europa.eu/project/rcn/206320/factsheet/en)
for the project [CALC](http://calc.digling.org)
(Computer-Assisted Language Comparison: Reconciling Computational and Classical
Approaches in Historical Linguistics), led by
[Johann-Mattis List](http://www.lingulist.de).
