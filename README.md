# dafsa

[![PyPI](https://img.shields.io/pypi/v/dafsa.svg)](https://pypi.org/project/dafsa)
[![CI](https://github.com/tresoldi/dafsa/actions/workflows/CI.yml/badge.svg)](https://github.com/tresoldi/dafsa/actions/workflows/CI.yml)
[![Docs](https://github.com/tresoldi/dafsa/actions/workflows/docs.yml/badge.svg)](https://tresoldi.github.io/dafsa)
[![Zenodo](https://zenodo.org/badge/DOI/10.5281/zenodo.3668870.svg)](https://doi.org/10.5281/zenodo.3668870)
[![Joss](https://joss.theoj.org/papers/10d826c5b26e5222beb1b3780d606725/status.svg)](https://joss.theoj.org/papers/10d826c5b26e5222beb1b3780d606725)

Finite-state structures for sequence data: tries, DAFSAs, path-compacted DAFSAs, suffix
automata, and acyclic weighted transducers — with weights that mean something, and small enough
drawings to look at.

Written for linguists and researchers working with morphology, phonology and sequence data, and
readable enough to be used as a reference implementation of the algorithms it contains.

```python
from dafsa import Dafsa

lexicon = Dafsa.from_sequences(["tap", "taps", "top", "tops"])

assert "taps" in lexicon
assert "ta" not in lexicon  # a prefix is not a member
assert len(lexicon) == 4
assert lexicon.num_states == 5  # where a trie would need 8
```

![Trie vs. DAFSA](https://raw.githubusercontent.com/tresoldi/dafsa/master/figures/trie-vs-dafsa.png)

A DAFSA eliminates the suffix and infix redundancy a [trie](https://en.wikipedia.org/wiki/Trie)
leaves behind, storing a set of sequences in a directed acyclic graph with a single source. Being
acyclic, it accepts all and only the sequences it was built from.

## Install

```bash
pip install dafsa
```

Python 3.10 or later. Writing image files also needs [Graphviz](https://graphviz.org/) on the
path; every other export, including the DOT source itself, is pure Python.

## What it does

**A family of structures**, sharing one frozen core:

| | |
|---|---|
| `Trie` | prefix tree — keeps every prefix distinct |
| `Dafsa` | the minimal automaton for a set of sequences |
| `CompactDafsa` | chains of forced states collapsed into compound transitions |
| `SuffixAutomaton` | index every substring of a single sequence |
| `Cdawg` | the compacted form of that index |
| `Fst` | relate one sequence to another |

**Tokens are whatever you say they are** — characters, phonemes, words, tags, feature bundles,
even types that cannot be compared with each other:

```python
from dafsa import Dafsa, tokenize

phrases = Dafsa.from_sequences([tokenize("the cat sat"), tokenize("the dog sat")])
assert ("the", "cat", "sat") in phrases
```

**Weights belong to a semiring**, so combining them along a path and across paths is defined:

```python
from dafsa import Dafsa
from dafsa.semirings import COUNTING

counted = Dafsa.from_sequences(["tip", "tip", "tap"], semiring=COUNTING)
assert counted.weight("tip") == 2
assert counted.total_weight() == 3  # insertions, over 2 distinct sequences
```

**The automaton is an index, not only a set.** Suffix counts make it a minimal perfect hash over
its own language:

```python
from dafsa import Dafsa

lexicon = Dafsa.from_sequences(["tap", "taps", "top", "tops"])

assert lexicon.rank("top") == 2
assert lexicon.unrank(2) == ("t", "o", "p")
assert list(lexicon.starts_with("ta")) == [("t", "a", "p"), ("t", "a", "p", "s")]
```

**Drawings you can read**, with compaction and correct fonts:

```python
# docs-test: skip — writing a figure needs Graphviz on the path
from dafsa import export

export.write_figure(lexicon.compact(), "words.png", scale_edges=True)
```

## From the command line

```bash
dafsa words.txt                    # a summary
dafsa --words phrases.txt          # split lines on whitespace
dafsa -s counting words.txt        # with frequencies
dafsa --compact -t svg -o words.svg words.txt
```

## Documentation

- [User Guide](https://tresoldi.github.io/dafsa/USER_GUIDE/) — the library in one page,
  including migration from 1.0 and the references
- [API Reference](https://tresoldi.github.io/dafsa/reference/)
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — how the library is put together, and why

## Upgrading from 1.0

2.0 is a deliberate break; 1.0 code will not run unchanged, and `dafsa==1.0` stays on PyPI. The
[migration section of the User Guide](https://tresoldi.github.io/dafsa/USER_GUIDE/#migrating-from-10)
maps the old API onto the new one.

The reason for breaking is worth stating plainly. 1.0 collected weights by re-walking sequences
over the already-minimized graph, so an edge counter held the total frequency of *every* sequence
crossing it, and `lookup()` summed those along the queried path:

```python
# docs-test: skip — this is 1.0, kept here to show what it did
>>> DAFSA(["dib", "tip", "tips", "top"]).lookup("tip")[1]
7
```

`"tip"` was inserted once. That is not a patchable bug — it is the absence of an algebra, and
fixing it is what the rest of 2.0 was built around.

2.0 also closes the open issues 1.0 accumulated: the `condense()` crashes ([#18], [#14]), the
undirected graph export and its lost parallel-edge labels ([#16]), missing glyphs in figures
([#15]), the recursion limit ([#10]), gaps in state ids ([#7]), `lookup()` not returning a path
([#8]), and the `delimiter` that never split anything ([#17]).

Construction is also about two orders of magnitude faster: the 0.5 changelog records 99,171
sequences taking "under 8 minutes", where a comparable corpus of 96,393 now builds in under four
seconds.

[#7]: https://github.com/tresoldi/dafsa/issues/7
[#8]: https://github.com/tresoldi/dafsa/issues/8
[#10]: https://github.com/tresoldi/dafsa/issues/10
[#14]: https://github.com/tresoldi/dafsa/issues/14
[#15]: https://github.com/tresoldi/dafsa/issues/15
[#16]: https://github.com/tresoldi/dafsa/issues/16
[#17]: https://github.com/tresoldi/dafsa/issues/17
[#18]: https://github.com/tresoldi/dafsa/issues/18

## Contributing

Contributing guidelines, including a code of conduct, are in
[CONTRIBUTING.md](CONTRIBUTING.md). Bug reports and questions are welcome as GitHub issues.

## Author and citation

The library is developed by Tiago Tresoldi (tiago.tresoldi@lingfil.uu.se).

The author has received funding from the European Research Council (ERC) under the European
Union's Horizon 2020 research and innovation programme (grant agreement
[ERC Grant #715618](https://cordis.europa.eu/project/rcn/206320/factsheet/en),
[Computer-Assisted Language Comparison](https://digling.org/calc/)).

If you use `dafsa`, please cite it as:

> Tresoldi, Tiago (2020). *DAFSA, a library for computing Deterministic Acyclic Finite State
> Automata.* Version 1.0. Jena. DOI: [10.5281/zenodo.3668870](https://doi.org/10.5281/zenodo.3668870)

```bibtex
@misc{Tresoldi2020dafsa,
  author = {Tresoldi, Tiago},
  title = {DAFSA, a library for computing Deterministic Acyclic Finite State Automata},
  howpublished = {\url{https://github.com/tresoldi/dafsa}},
  address = {Jena},
  doi = {10.5281/zenodo.3668870}
}
```

The full changelog is in [CHANGELOG.md](CHANGELOG.md).
