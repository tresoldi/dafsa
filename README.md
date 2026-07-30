# dafsa

[![CI](https://github.com/tresoldi/dafsa/actions/workflows/quality.yml/badge.svg)](https://github.com/tresoldi/dafsa/actions/workflows/quality.yml)
[![Docs](https://img.shields.io/badge/docs-mkdocs-blue.svg)](https://dafsa.tresoldi.org/)
[![PyPI version](https://badge.fury.io/py/dafsa.svg)](https://badge.fury.io/py/dafsa)
[![Python versions](https://img.shields.io/pypi/pyversions/dafsa.svg)](https://pypi.org/project/dafsa/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Zenodo](https://zenodo.org/badge/DOI/10.5281/zenodo.3668870.svg)](https://doi.org/10.5281/zenodo.3668870)
[![JOSS](https://joss.theoj.org/papers/10d826c5b26e5222beb1b3780d606725/status.svg)](https://joss.theoj.org/papers/10d826c5b26e5222beb1b3780d606725)

**Store sets of sequences as finite-state automata.**

`dafsa` turns a collection of sequences into a graph in which every shared beginning
and every shared ending is stored once, then answers membership, counting, ranking,
prefix and weight queries by walking it. Tokens are anything hashable — characters,
phonemes, tags, integers, tuples — so it is as much at home in phonology or genomics as
in a spell checker.

```python
from dafsa import Dafsa

lexicon = Dafsa.from_sequences(["tap", "taps", "top", "tops"])

lexicon.num_states  # 5   — a trie would need 8
len(lexicon)  # 4   — counted, not enumerated
lexicon.unrank(2)  # ('t', 'o', 'p')
```

![Trie vs. DAFSA](https://raw.githubusercontent.com/tresoldi/dafsa/master/figures/trie-vs-dafsa.png)

That third line is the point beyond compression: because a minimal acyclic automaton
knows how many sequences leave each state, it is also a **minimal perfect hash over its
own language**. Every accepted sequence has a position, every position has a sequence,
and reaching the millionth costs no more than reaching the first.

## Install

```bash
pip install dafsa
```

No required dependencies. `pip install "dafsa[graph]"` adds networkx for the three graph
exports; writing image files additionally needs [Graphviz](https://graphviz.org/) on the
path.

## The interface

Six structures share one frozen core, so they all answer the same queries.

```python
from dafsa import Dafsa, SuffixAutomaton, Fst
from dafsa.semirings import COUNTING

counted = Dafsa.from_sequences(["tip", "tip", "tap"], semiring=COUNTING)
counted.weight("tip")  # 2 — what it was inserted with, not a path sum

index = SuffixAutomaton.from_sequence("banana")
index.contains_substring("nan")  # True

translate = Fst.from_pairs([("cat", "chat")])
translate.apply("cat")  # [('c', 'h', 'a', 't')]
```

Weights belong to an explicit **semiring** — boolean, counting, tropical, log,
probability and Viterbi are built in, and any type satisfying the protocol works.
Because minimization is weight-aware, the weight of a path is the weight the sequence
was inserted with. There is also a command line: `dafsa --help`.

## Choosing a structure

| Structure | Use it for | Note |
|-----------|------------|------|
| `Dafsa` | storing and querying a set of sequences | the usual choice |
| `Trie` | when the structure must stay a tree | states grow with total input length |
| `CompactDafsa` | drawing, exporting, or shrinking further | via `.compact()` |
| `SuffixAutomaton` | what occurs *inside* one long sequence | online, linear time and space |
| `Cdawg` | the same, with forced chains collapsed | via `.compact()` |
| `Fst` | mapping sequences to sequences | may be ambiguous, so `apply` returns a list |

## Why dafsa

- **Weights that mean what they say.** Minimization is weight-aware, so `weight(seq)`
  returns what `seq` was inserted with. 1.0's `lookup()` returned the sum of shared edge
  counters along the path — `7` for a sequence inserted once.
- **An index, not only a set.** Constant-time `len()`, `rank`/`unrank`, ordered
  iteration, prefix queries, `total_weight` and `k_best`.
- **Flat arrays, no object graph.** Compressed sparse row adjacency over `array.array`,
  so 96,393 sequences build in under four seconds where 1.0's changelog records "under 8
  minutes" for a comparable corpus — and `RecursionError` is structurally unreachable.
- **Typed and tested.** Full type hints (`py.typed`), strict linting and type-checking,
  100% branch coverage, and property-based tests checking the automata against
  independent references rather than against themselves.

## Documentation

- **[Documentation site](https://dafsa.tresoldi.org/)** — user guide and full API
  reference.
- **[User Guide](docs/USER_GUIDE.md)** — concepts, choosing a structure, and worked
  examples across lexicography, phonology, historical linguistics and genomics.
- **[API Reference](https://dafsa.tresoldi.org/reference/)** — every public class and
  function, generated from the source.
- **[MIGRATION.md](MIGRATION.md)** — 2.0 is a deliberate break from 1.0; this maps the
  old API onto the new one.
- **[ARCHITECTURE.md](ARCHITECTURE.md)** — how the library is put together, and why.

## Citation

If you use `dafsa` in academic research, please cite:

```bibtex
@software{tresoldi_dafsa,
  author  = {Tresoldi, Tiago},
  title   = {DAFSA: Finite-state structures for sequence data},
  url     = {https://github.com/tresoldi/dafsa},
  doi     = {10.5281/zenodo.3668870},
  version = {2.0.0},
  year    = {2026}
}
```

## License

MIT — see [LICENSE](LICENSE).
