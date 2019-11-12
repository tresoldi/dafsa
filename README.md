# DAFSA


[![Build Status](https://travis-ci.org/tresoldi/dafsa.svg?branch=master)](https://travis-ci.org/tresoldi/dafsa)
[![codecov](https://codecov.io/gh/tresoldi/dafsa/branch/master/graph/badge.svg)](https://codecov.io/gh/tresoldi/dafsa)
[![PyPI](https://img.shields.io/pypi/v/dafsa.svg)](https://pypi.org/project/dafsa)

DAFSA is a library for computing [Deterministic Acyclic Finite State Automata](https://en.wikipedia.org/wiki/Deterministic_acyclic_finite_state_automaton), sometimes called "directed acyclic word graphs" (DAWG). DAFSA are data structures derived from [tries](https://en.wikipedia.org/wiki/Trie) that allow to represent a set of sequences (typically character strings or *n*-grams) in the form of a directed acyclic graph with a single source vertex (the `start` symbol of all sequences) and at least one sink edge (`end` symbols, potentially shared by one or more sequences). It is a special case of a finite state recognizer that acts as a deterministic finite state automaton, as it recognizes all and only the sequences it was built upon. Mostly used in computer science for the space-efficient storage of sets of sequences without common compression techniques, such as dictionary or entropy types, or without probabilistic data structures, such as Bloom filters, the automata generated by this library are intended for linguistic exploration, and extend published models by allowing to approximate probability of random observation by carrying information on the weight of each graph edge.

![Trie vs. DAFSA](https://raw.githubusercontent.com/tresoldi/dafsa/master/doc/trie-vs-dafsa.png)

The primary difference between DAFSA and tries is that suffix and infix redundancy is eliminated, as in the example of Figure 1 (from the linked Wikipedia article) storing the set of strings `"tap"`, `"taps"`, `"top"`, and `"tops"`. Even though DAFSAs cannot be used to store precise frequency information, given that terminal nodes can be reached by multiple paths, they allow to estimate the sampling frequency; being acyclic, they can also reject any sequence not included in the training. Fuzzy extensions will allow to estimate the sampling probability of unobserved sequences.

## Changelog

Version 0.2:
  - Added support for weighted edges
  - Added Graphviz export and generation
  - Added support for non-character tokens
  - Refined minimization method, which repeated until completion or can be
    skipped
  - Added some examples in the resources, also used for test data

Version 0.1:

  - First public release.

## Installation

In any standard Python environment, `dafsa` can be installed with:

```
pip install dafsa
```

## How to use

The library offers a `DAFSA` object that can be used to compute an automaton, with methods for checking a sequence acceptance and for exporting the graph. A minimal usage is shown here:

```python
>>> import dafsa
>>> d = dafsa.DAFSA()
>>> d.insert(["tap", "taps", "top"])
>>> print(d)
DAFSA with 5 nodes and 5 edges (0 seqs)
+-- ROOT [0] [('t', '1')]
    +-- F() [0] []
    +-- F(s|4) [0] [('s', '4')]
    +-- n(a|2;o|5) [0] [('o', '5'), ('a', '2')]
    +-- n(p|3) [0] [('p', '3')]
    +-- n(p|4) [0] [('p', '4')]
```

A command-line tool for reading files with lists of strings, with one string per line, is also available:

```
$ cat lexicon
defy
tried
defies
tries
defied
trying
denying
try
deny
defying

$ dafsa lexicon
DAFSA with 11 nodes and 13 edges (10 seqs)
+-- F() [0] []
+-- F(i|9) [0] [('i', '9')]
+-- n(d|6;s|6) [0] [('s', '6'), ('d', '6')]
+-- n(e|2) [0] [('e', '2')]
+-- n(e|5) [0] [('e', '5')]
+-- n(f|3;n|12) [0] [('f', '3'), ('n', '12')]
+-- n(g|6) [0] [('g', '6')]
+-- n(i|4;y|8) [0] [('i', '4'), ('y', '8')]
+-- n(n|10) [0] [('n', '10')]
+-- n(r|3) [0] [('r', '3')]
+-- n(y|8) [0] [('y', '8')]

`deny` in dafsa: F(i|9)
`dafsa` in dafsa: False
`dawg` in dafsa: False
```

## Alternatives

The main alternative to this library is the `dawg` one, available at [https://github.com/pytries/DAWG](https://github.com/pytries/DAWG). `dawg` is bundled with the `dwagdic` C++ library, and is intended to production usage of DAFSAs as a space-efficient data structure. It does not support the computation of edge weights, nor it is intended for exporting the internal structure as a graph.

Other alternatives are the `adfa` and `minim` packages, writting in C/C++, written by Jan Daciuk. The personal webpage hosting them has been offline for years, with a version at the [Wayback Machine](https://web.archive.org/web/20160531133017/http://galaxy.eti.pg.gda.pl/katedry/kiw/pracownicy/Jan.Daciuk/personal/minim.html) available. Note that the archived version does *not* include the packages.

## TODO

(...)

## How to cite

If you use `dafsa`, please cite it as:

> Tresoldi, Tiago (2019). DAFSA, a a library for computing Deterministic Acyclic Finite State Automata. Version 0.2. Jena. Available at: https://github.com/tresoldi/dafsa

In BibTeX:

```
@misc{Tresoldi2019dafsa,
  author = {Tresoldi, Tiago},
  title = {DAFSA, a a library for computing Deterministic Acyclic Finite State Automata. Version 0.2},
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
