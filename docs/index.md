# dafsa

Finite-state structures for sequence data: tries, DAFSAs, path-compacted DAFSAs, suffix
automata, and acyclic weighted transducers.

!!! warning "2.0 is under development"

    This documentation tracks the 2.0 development line, which is a **clean break** from 1.0.
    Nothing here is stable yet. Currently available: the frozen core
    ([`Alphabet`](api.md#dafsa.alphabet.Alphabet),
    [`Automaton`](api.md#dafsa.automaton.Automaton)), the
    [semiring layer](api.md#dafsa.semirings), and the structures
    [`Trie`](api.md#dafsa.structures.Trie), [`Dafsa`](api.md#dafsa.structures.Dafsa) and
    [`CompactDafsa`](api.md#dafsa.structures.CompactDafsa). The substring and transducer
    structures are still being built.

    For the released library — the one described by the JOSS paper and the Zenodo DOI — use
    `pip install dafsa==1.0` and read
    [the 1.0 documentation](https://dafsa.readthedocs.io/en/latest/).

## What 2.0 changes

1.0 offered a single `DAFSA` class over a linked graph of Python objects, with frequency
counters whose composition was not well defined. 2.0 replaces the internals entirely:

- **A family of structures.** `Trie`, `Dafsa`, `CompactDafsa`, `SuffixAutomaton`, `Cdawg`,
  and `Fst`, all sharing one frozen core.
- **Weights over an explicit semiring.** Boolean, counting, tropical, log, probability, and
  Viterbi are built in, and any type satisfying the `Semiring` protocol works. The weight of
  a path is, by construction, the weight that was assigned to that sequence.
- **Flat-array representation.** Compressed sparse row adjacency over `array.array`, so the
  library is fast, memory-frugal, trivially exportable, and structurally incapable of hitting
  a recursion limit.
- **Build, then freeze.** Construction happens in a builder; the result is immutable and
  canonically numbered, which also means state ids have no gaps.

The full rationale, the audit of 1.0 that motivated the rewrite, the API, the milestone plan,
and the 1.0 → 2.0 migration table are in
[`DESIGN.md`](https://github.com/tresoldi/dafsa/blob/master/DESIGN.md).

## Installation

2.0 is not released. To work against the development line:

```bash
git clone https://github.com/tresoldi/dafsa.git
cd dafsa
pip install -e ".[dev]"
```

Requires Python 3.10 or later.

## Citation

If you use `dafsa`, please cite it as:

> Tresoldi, Tiago (2020). *DAFSA, a library for computing Deterministic Acyclic Finite State
> Automata.* Version 1.0. Jena. DOI: [10.5281/zenodo.3668870](https://doi.org/10.5281/zenodo.3668870)
