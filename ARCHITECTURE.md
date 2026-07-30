# dafsa Architecture

> Status: **describes the delivered architecture as of 2.0.0.**
> This document was originally `DESIGN.md`, the anchor for a thirteen-milestone
> rewrite of the library. That rewrite is complete, and the file now reflects how
> `dafsa` is actually built. The history is in §8 and the decisions taken along the
> way are recorded in §9.

This document defines the structure, boundaries, and design principles of `dafsa`. New
modules should fit within it; changes that move away from it should update it in the
same pull request.

---

## 1. Purpose and scope

`dafsa` stores **sets of sequences as finite-state automata**. Given sequences, it
produces a graph in which every shared beginning and every shared ending is stored
once, and answers membership, counting, ranking, prefix and weight queries by walking
it.

1.0 did one part of this: it computed a minimal deterministic acyclic finite-state
automaton from a list of sequences and drew it. It is cited (JOSS 2020, Zenodo DOI
10.5281/zenodo.3668870) and is, as one bug reporter put it, "the one people will most
likely find when looking for a DAFSA implementation in Python." 2.0 keeps that role — a
readable reference implementation — and widens it in three directions: a **family** of
structures rather than one class, weights that live in an explicit **semiring**, and a
flat-array **representation that scales**.

The library is written for linguists and researchers working with morphology, phonology
and sequence data, but the core assumes nothing about text. A token is a `Hashable` and
a sequence is a `Sequence[Hashable]`. Representative domains:

| Domain | Tokens | Sequences |
|--------|--------|-----------|
| Lexicography | characters | words in a lexicon |
| Phonology | phonemes, feature bundles | transcribed forms |
| Historical linguistics | segments | forms related by sound change |
| Morphology | morphs, tags | analyses, as transducer pairs |
| Genomics | nucleotides | reads, indexed by substring |
| Anything discrete | integers, tuples, mixed types | paths, event traces |

**Design consequence:** the core vocabulary is *token*, *sequence*, *symbol*, *state*,
*transition* — never *character* or *word*. Text-specific convenience is confined to
`tokenize` and the command-line interface.

**Non-goals.** Incremental insertion or deletion after construction; cyclic automata and
general regular-expression compilation; a C or Rust extension; *loading* automata from
disk (export only, §4); any change to `manuscript/`, which remains the record of the 1.0
JOSS paper.

---

## 2. Design principles

1. **Readable first.** This is a reference implementation. Where a clear algorithm and a
   clever one differ measurably, take the clear one and record the benchmark.
2. **Build, then freeze.** Construction happens in a builder; the result is an
   immutable, canonically numbered, flat-array automaton. There is no post-construction
   mutation and no per-state object a caller can hold.
3. **No recursion on data-dependent depth.** Every traversal is iterative, with an
   explicit stack or a topological order. This is what makes a `RecursionError`
   structurally unreachable rather than merely unlikely.
4. **Tokens are opaque.** The core never assumes a token is a string, is comparable, or
   is a single character. Sorting happens over encoded integer symbols, never over the
   caller's sequences.
5. **Separate structure from rendering.** Nothing in the core knows about Graphviz, DOT,
   fonts, or networkx.
6. **Correctness is checked independently.** Minimality, determinism and weight
   preservation are verified by code that shares no implementation with the builder
   (§6).
7. **No required dependencies.** Every structure, algorithm and the DOT output are plain
   Python. networkx is needed by three graph exports and lives in an extra.
8. **Typed throughout.** Full annotations, `py.typed` shipped, and mypy in CI over
   `src/`, `tests/`, `benchmarks/` and `figures/`.

---

## 3. Package structure

`src/` layout; the public API is re-exported from `__init__.py`, so file layout is
transparent to users.

```
src/dafsa/
├── __init__.py       # public API surface (stable import path)
├── _types.py         # Token, Symbol, State, ROOT — the vocabulary, no logic
├── exceptions.py     # DafsaError and the four errors deriving from it
├── alphabet.py       # Alphabet (token <-> symbol id), tokenize
├── semirings.py      # the Semiring protocol and six built-ins
├── automaton.py      # Transition, Match, Automaton — the frozen CSR core
├── _builder.py       # Builder and freeze()
├── _algorithms.py    # traversal, counting, ranking, compaction, pushing, minimization
├── structures.py     # Trie, Dafsa, CompactDafsa
├── suffix.py         # SuffixAutomaton, Cdawg — substring indexes
├── fst.py            # EPSILON, Fst, align, compose — transducers
├── export.py         # DOT, JSON, networkx, GML, GraphML
├── __main__.py       # the command-line interface
└── py.typed
```

### The frozen core

An `Automaton` is compressed-sparse-row adjacency over `array.array`. There is no object
per state and no object per transition:

```
_alphabet             Alphabet
_first                array[int32], length num_states + 1    # q's transitions are [_first[q]:_first[q+1]]
_symbol               array[int32], length num_transitions   # sorted by (source, symbol)
_target               array[int32], length num_transitions
_flags                array[uint8]                           # bit 0: final
_labels               list[tuple[Symbol, ...]] | None        # compound labels, when compacted
_transition_weights   list[W] | None                         # semiring elements
_final_weights        list[W] | None
_initial_weight       W                                      # where weight pushing puts the remainder
_counts               array[int64] | None                    # accepted suffixes from q, lazy
_semiring             Semiring[W]
```

The optional fields are `None` rather than filled with defaults, and that is load-
bearing: a plain acceptor pays nothing for the weight machinery, and `weight()` returns
the semiring's `one` for an accepted sequence without consulting an array. Memory
frugality is much of the argument for this representation.

Consequences: transition lookup is a `bisect` over one state's sorted symbol slice,
O(log k); memory is roughly 12 bytes per transition against several hundred for a linked
node/edge pair; state ids are dense with `0` the root; there is no object graph to
deep-copy; and the arrays are the serialisation format.

`freeze()` is where the core's invariants are *established* rather than assumed, which
is the point of having a build/freeze split at all. It renumbers breadth-first from the
root following transitions in ascending symbol order — so two builders describing the
same automaton freeze to byte-identical arrays — prunes unreachable states, and checks
determinism and acyclicity. The acyclicity check is an iterative three-colour search,
and the distinction that matters is that an edge into a *grey* state is a cycle while an
edge into a *black* state is not: converging paths are exactly the state sharing that
makes a DAFSA a DAFSA.

### Dependency rule

Dependencies point **inward**. `_types`, `exceptions` and `semirings` import nothing
else in the package; `alphabet` imports `exceptions`; `automaton` imports `_types`,
`semirings` and `_algorithms`; `_builder` imports `automaton`; the structures, the
substring indexes, the transducers, the export layer and the CLI sit on top and are
imported by nothing below them.

`ROOT` lives in `_types` rather than in `automaton` for exactly this reason: `automaton`
and `_algorithms` would otherwise import each other. Where a genuine cycle remains — a
structure that must build a new automaton — the import is function-local and carries a
comment saying so.

---

## 4. Public API contract

The lifecycle is *construct, then query*. Construction is a classmethod on a structure;
the result is immutable.

```python
from dafsa import Dafsa
from dafsa.semirings import COUNTING

automaton = Dafsa.from_sequences(sequences, semiring=COUNTING)
automaton = Dafsa.from_weighted(pairs, semiring=COUNTING)
```

`Sequence[Hashable]` is the input contract. A `str` is accepted and documented as one
token per character; `dafsa.tokenize` is the explicit way to get multi-character tokens.
There is no `delimiter` parameter to be misunderstood.

Every structure — `Trie`, `Dafsa`, `CompactDafsa`, `SuffixAutomaton`, `Cdawg`, `Fst` —
is an `Automaton`, and so answers the same queries:

```python
seq in automaton                  -> bool
automaton.weight(seq)             -> W               # semiring.zero if rejected
automaton.match(seq)              -> Match | None    # states, transitions, weight
automaton.paths(seq)              -> Iterator[Match] # all paths, for ambiguous transducers
automaton.longest_prefix_of(seq)  -> tuple | None
automaton.starts_with(prefix)     -> Iterator[tuple]
len(automaton)                    -> int             # distinct accepted sequences
iter(automaton)                   -> Iterator[tuple] # in the alphabet's order
automaton.rank(seq) / .unrank(i)
automaton.k_best(k)               -> list[tuple[tuple, W]]
automaton.total_weight()          -> W
automaton.compact()               -> CompactDafsa
automaton.push()                  -> Self            # divisible semirings only
```

`Alphabet` and `Automaton` are importable from `dafsa` directly; `Builder` is
`dafsa._builder.Builder` and stays private — callers reach it through the structures.

`try_encode` returning `None` rather than raising is the deliberate half of the token
contract: a sequence containing a token the automaton has never seen is *not accepted*,
which is an answer, not an error. Only `encode` raises, for callers who mean it.

### Weights

A weight is only useful if combining it *along* a path and *across* paths is defined,
which is exactly a semiring. `Semiring` is a `Protocol` with `zero`, `one`, `plus`,
`times`, `key`, an optional `divide`, and the flags `idempotent`, `commutative` and
`divisible`. Six are built in (`BOOLEAN`, `COUNTING`, `TROPICAL`, `LOG`, `PROBABILITY`,
`VITERBI`); any type satisfying the protocol works, and nothing in the algorithms
inspects the concrete type. `star` is deliberately absent, since every structure here is
acyclic.

Minimization is weight-aware: two states merge only if their final weights and their
outgoing `(symbol, target, weight)` triples agree, compared through `Semiring.key`. That
is what makes `weight(seq)` the weight assigned to `seq`, at the cost of less sharing
than an unweighted DAFSA. `push()` recovers some of it for divisible semirings, as an
explicit optional pass rather than a default.

### Export

Export only, by decision: sequences are the source of truth and construction is fast
enough to rebuild. The CSR arrays make a compact binary format straightforward if
loading is ever wanted, so nothing here forecloses it.

```python
dafsa.export.to_dict(a) / to_json(a, path=None)
dafsa.export.to_dot(a, *, label_nodes=False, fontname=..., charset="UTF-8", ...)
dafsa.export.write_figure(a, path, *, dpi=300, **dot_kwargs)
dafsa.export.to_networkx(a) -> nx.MultiDiGraph
dafsa.export.write_gml(a, path) / write_graphml(a, path)
```

Graphviz is not a Python dependency: `write_figure` shells out to `dot` and raises
`ExportError` when it is absent, while `to_dot` returns source regardless. The three
networkx-backed functions raise `ExportError` naming `pip install dafsa[graph]`, and a
test asserts that importing `dafsa` does not import networkx at all.

### Command line

```
dafsa [-f dafsa|trie|suffix] [-s boolean|counting|tropical|log|probability|viterbi]
      [--sep SEP | --words] [--compact] [--push]
      [-t text|json|dot|gml|graphml|png|pdf|svg] [-o PATH] [--dpi N]
      [--label-nodes] [--font NAME] [--label-sep SEP] [--scale-edges] SOURCE
```

Tokenization is explicit and needs two flags rather than one: `--words` splits on
whitespace, `--sep SEP` on a given separator, and omitting both leaves every character a
token.

There is no `-f cdawg`, because a CDAWG is not a separate construction: it is a suffix
automaton with `compact()` applied, so `-f suffix --compact` builds one and the summary
names it `Cdawg`. The same holds for `CompactDafsa` and `-f dafsa --compact`.

---

## 5. Terminology

To keep the library legible across domains, docs, examples and docstrings use neutral
terms:

| Prefer | Avoid |
|--------|-------|
| token | character, letter |
| sequence | word, string |
| symbol | token id, code |
| state, transition | node, edge (except in export formats, where they are the format's terms) |
| accepted | recognised, matched |
| compaction | condensation |

Two distinctions are worth stating because they were run together in earlier scoping:

- A **compact DAFSA** (`CompactDafsa`) is a path-compressed *dictionary* automaton. A
  **CDAWG** (`Cdawg`) is the path-compressed form of a *suffix* automaton. They are
  different structures over different inputs.
- A **suffix automaton** accepts the suffixes of one sequence, and indexes every
  substring as what can be walked from the root. `contains_substring` therefore ignores
  acceptance while `in` does not.

---

## 6. Testing and documentation architecture

**Tests check the implementation against something other than itself.** The suite covers
100% of branches; the gate in `pyproject.toml` is set below that, at 88%, so an unrelated
line-count change does not fail a pull request. The parts that matter are:

- **Language equivalence.** The accepted set equals a reference Python `set`, in both
  directions, for random and corpus-derived inputs.
- **Independent minimality verifier.** After `freeze()`, no two states share a
  signature — computed by a checker that does not use the builder's register. At the
  96k-sequence scale, all 109,160 signatures are distinct.
- **Cross-checking two constructions.** Revuz minimization applied to a `Trie` must
  produce exactly the `Dafsa` the incremental construction builds, by an entirely
  different route.
- **Semiring laws**, property-based with `hypothesis`: associativity, commutativity
  where claimed, distributivity, identities and annihilators for every built-in.
- **Weight preservation.** For every inserted `(sequence, weight)`, `weight(seq)` equals
  the assigned weight and `total_weight()` equals the ⊕-fold of all of them. This is the
  test 1.0 could not have passed (§8).
- **Regression tests** reproducing every closed issue from its reported input. They live
  beside the unit tests for the code they exercise rather than in one file, because they
  need the same fixtures — but each is named `test_issue_NN_…`, so `pytest -k issue`
  collects the whole set at once. That includes a depth test which builds, freezes,
  exports and queries a 50,000-token sequence with a guard asserting the recursion limit
  was not raised.
- **Doctests** over `src/` and **executed documentation**: every `python` block in
  `README.md`, `MIGRATION.md` and the User Guide is run by `tests/test_docs_examples.py`,
  so an example naming a renamed API fails the suite instead of shipping.
- **A benchmark guard that is a ratio, not a stopwatch.** Quadrupling the input must not
  multiply the work by more than ten — linear growth is about four, and the quadratic
  scan 1.0 shipped would be about sixteen. Loose absolute budgets sit alongside to catch
  a catastrophe.

Test files are named for the module they cover (`test_alphabet.py`, `test_automaton.py`,
…) with three exceptions named for a concern that crosses modules: `test_efficiency.py`,
`test_docs_examples.py` and `test_packaging.py`. Property-based tests are not gathered
into one file either — they belong next to the behaviour they generalise.

**Documentation is three pages**, and no more, because a page nobody maintains is worse
than a page that does not exist:

- **`docs/index.md`** — front-matter only; the landing page is `overrides/home.html`, a
  standalone template with its own typography.
- **`docs/USER_GUIDE.md`** — the narrative: concepts, choosing a structure, worked
  examples by domain, and the references. Migration has its own root-level
  `MIGRATION.md`, which the guide and the README both point at.
- **`docs/reference.md`** — `::: dafsa`, generated from the docstrings by mkdocstrings,
  so there is no hand-maintained reference to drift.

Docstrings are **Google style**, which is what mkdocstrings parses and what ruff's
pydocstyle rules enforce; types come from the annotations rather than from the docstring,
so the two cannot disagree. Tooling is MkDocs Material + mkdocstrings, published to GitHub
Pages from CI at `dafsa.tresoldi.org` (`docs/CNAME`); build with `make site`.

**Nothing committed is unreproducible.** `benchmarks/run.py` produces the numbers quoted
here and `figures/trie-vs-dafsa.py` redraws the figure the README opens with, from the
library's own DOT emitter — so a claim in this document, and a picture in the README, can
be re-checked rather than taken on trust. The three remaining files under `figures/` belong
to `manuscript/`, and `resources/` is the sample data the User Guide's command-line
examples run against, exercised by `tests/test_cli.py` so that it cannot quietly rot.

Linting is **ruff** with a rule set matching the sibling `freqprob` project, formatting
is `ruff format`, typing is **mypy**, and static security analysis is **bandit** — the
same four checks `make quality` runs and CI enforces. `filterwarnings = ["error"]` is
kept stricter than `freqprob`'s deliberately: a warning escaping a test is how several
real defects surfaced during this rewrite, and swallowing `DeprecationWarning` would have
hidden them.

**`ruff` and `mypy` are pinned to exact versions** in the `dev` extra, and the pre-commit
hooks use the same ones. This is not fussiness: ruff 0.15 and 0.16 disagree about whether
`PLR0917` exists, so the `noqa` comment one of them demands the other reports as unused,
and no source file can satisfy both. A range would make `make quality` pass or fail
depending on what a contributor happened to have installed.

---

## 7. Versioning and compatibility

2.0.0 is a **clean break**. It shares no implementation with 1.0 and there is no
compatibility shim, because the thing that had to change — what a weight *means* — is
not expressible in the old API. `dafsa==1.0` stays on PyPI and is the version the JOSS
paper describes; the User Guide maps the old surface onto the new one.

The public API is the top-level `dafsa` namespace. After 2.0.0, breaking changes to it
are expected to be rare and clearly flagged; the project follows semantic versioning.
Python 3.10 or later; the CI matrix is 3.10–3.13.

The version has a single source: `dafsa.__version__`, which `pyproject.toml` declares
`dynamic` and reads from. `make bump-version TYPE=patch|minor|major` edits it and
`CITATION.cff` together, and a test asserts the installed metadata agrees.

`manuscript/` and `paper.json` are untouched. 2.0 is documented in the changelog and the
docs site, and gets a new Zenodo version DOI on release.

---

## 8. How it was built (history)

### Why 1.0 was replaced rather than patched

The 1.0 implementation lives in git history at `a78c94e~1` (`dafsa/dafsa.py`, 983
lines). Every symptom below was reproduced by running that code, except where noted.

**The weight semantics were the deepest problem.** 1.0 minimized first and *then*
re-walked every sequence over the minimized graph, incrementing a counter on each edge.
Because states are shared after minimization, an edge counter ends up being the total
frequency of *all* sequences traversing that edge, and `lookup()` returned the sum of
those along the queried path:

```
>>> DAFSA(["dib", "tip", "tips", "top"]).lookup("tip")[1]
7          # 3 (root-t, shared by tip/tips/top) + 2 (t-i) + 2 (i-p)
```

`"tip"` was inserted once, and there is no reading of `7` as its weight. That is not a
bug to patch; it is the absence of an algebra, and it is why the semiring layer exists.

**The reported issues and their root causes:**

| Issue | Symptom | Root cause |
|---|---|---|
| [#18](https://github.com/tresoldi/dafsa/issues/18), [#14](https://github.com/tresoldi/dafsa/issues/14) | `condense()` raises `IndexError` | `_joining_round` skipped candidates with more than one in-edge but never excluded those with **zero**. The root qualifies whenever it emits a single edge, and the next line indexes `[0]` into its empty list of in-edges. |
| [#17](https://github.com/tresoldi/dafsa/issues/17) | `delimiter=" "` ignored; spaces become tokens | `delimiter` never split input. It only *joined* labels when compacting. `__main__.py` split on whitespace before calling the library, so the CLI appeared to work while the API did not. |
| [#16](https://github.com/tresoldi/dafsa/issues/16) | `to_graph()` returns an undirected graph | `nx.Graph()`. Two further defects in the same method: a nested loop re-added every edge once per node, and a single `label` slot per *pair of states* silently dropped parallel transitions. |
| [#15](https://github.com/tresoldi/dafsa/issues/15) | Figures show tofu boxes instead of glyphs | `resources/template.dot` declared neither `charset` nor `fontname`, leaving font resolution to Graphviz's default. |
| [#10](https://github.com/tresoldi/dafsa/issues/10) | `RecursionError` | `copy.deepcopy` over a linked node graph, one frame per state along a path. |
| [#8](https://github.com/tresoldi/dafsa/issues/8) | `lookup()` cannot return a path | It returned `(final_node, cum_weight)` only — and the weight was not interpretable. |
| [#7](https://github.com/tresoldi/dafsa/issues/7) | Gaps in node ids after minimization | Ids came from a global counter; merged nodes were abandoned and their ids never reused. |

**Defects found in the audit, with no issue filed:** minimization was quadratic and
wrapped in a restart loop, with `DAFSANode.__hash__` defined but no register used —
discarding the whole point of Daciuk's algorithm, and the reason the 0.5 changelog
records 99,171 sequences taking "under 8 minutes"; `to_dot()` divided by zero when built
with `weight=False`; the compaction de-duplication guard iterated a dict's literal keys
and so rejected everything after the first join; compaction assumed string tokens, and
mutated `self.nodes` while `lookup()` read a `deepcopy`, so the reported counts described
a different graph from the one being queried; `__eq__`, `__hash__` and `__gt__`
disagreed about whether finality counts; `sorted(sequences)` on the caller's own input
made mixed and incomparable token types a `TypeError`; and `count_sequences()` counted
duplicates while describing a set.

One further finding is recorded as **latent rather than observable**: `if child_idx:`
treated the state id `0` as "not found", so a child equivalent to the root would be
discarded instead of merged. Searching 20,000 random corpora produced no input that
reaches the branch — the root's out-edge set is the set of all distinct initial tokens,
which is hard for an interior state to match. 2.0 removes the possibility by keying a
register on state signatures instead of scanning for an index.

### The milestones

The rewrite shipped as thirteen milestones, ordered so that each was independently
testable and nothing was built on an unverified layer.

| # | Milestone | Contents |
|---|---|---|
| 0 | Infrastructure | `pyproject.toml` (3.10+, ruff, mypy, `py.typed`), CI refresh, MkDocs skeleton, `daciuk/` and the Sphinx/RTD files removed |
| 1 | Core | `Alphabet`, CSR `Automaton`, builder, `freeze()` with canonical renumbering, iterative traversal |
| 2 | Semiring layer | the protocol, six built-ins, law tests |
| 3 | Dictionary structures | `Trie`, `Dafsa` (register-based, weight-aware), minimality verifier |
| 4 | Counting layer | suffix counts, `len`, `rank`/`unrank`, ordered iteration, `total_weight`, `k_best`, `match`/`paths`/`longest_prefix_of`/`starts_with` — closes #8 |
| 5 | Compaction | `CompactDafsa` — closes #18, #14 |
| 6 | Substring index | `SuffixAutomaton`, `Cdawg` |
| 7 | Transducers | `Fst`, `compose`, `project`, Revuz minimization |
| 8 | Export | DOT with UTF-8 and fonts, `MultiDiGraph`, JSON, GML/GraphML — closes #15, #16 |
| 9 | Weight pushing | `push()` for divisible semirings |
| 10 | CLI | rewritten against the new API — closes the remainder of #17 |
| 11 | Docs and benchmarks | MkDocs site, migration guide, benchmark suite |
| 12 | Release | `2.0.0`, Zenodo version DOI, close the eight issues |

Milestone 8 was taken out of order, ahead of 6 and 7, because it depended on nothing
they produced and closed two more reported issues.

### Measured results

On a 96,393-sequence corpus (639,088 tokens), reproducible with `benchmarks/run.py`:

| | time | states | transitions |
|---|---|---|---|
| `Trie` | 6.7s | 360,103 | 360,102 |
| `Dafsa` | 3.8s | 109,160 | 194,703 |
| `CompactDafsa` | +0.64s | 39,864 | 125,407 |

Against 1.0's "under 8 minutes" for 99,171 sequences that is roughly two orders of
magnitude, and the register is where nearly all of it comes from. Note that the DAFSA
builds *faster* than the trie: minimization means fewer states are ever allocated, so
sharing pays for itself during construction rather than costing extra. Lookups run at
about 290,000/s; full ordered iteration takes 0.82s; `rank`/`unrank` round-trip over all
96,393 sequences takes 3.9s. `unrank` is position-independent as intended — 26.0ms per
thousand calls at position ~48,000 against 29.3ms at ~96,000, where enumeration would
have made the latter tens of thousands of times slower.

---

## 9. Decisions (resolved)

Recorded because they are worth reversing deliberately rather than by accident.

### Representation and construction

1. **Array-based from the start**, not a linked graph refactored later. At no point does
   a state become a first-class object user code can hold a reference to (§3).
2. **Edges are deferred, not rewired.** The textbook Daciuk construction wires a parent
   to its child immediately and rewires when the child turns out to be equivalent to a
   registered state. Here the parent's edge is deferred until the child is popped from
   the unchecked chain, so each edge is added exactly once. The builder needs no
   operation for mutating a transition, and a state that lost to a canonical
   representative is simply never referenced — `freeze()` prunes it with machinery that
   already had to exist.
3. **Suffix counts are computed lazily, not at freeze.** They are derived from the
   transitions, so they can never be passed in and be wrong, and a caller who only tests
   membership should not pay an O(transitions) pass. Measured at 0.57s on first use for
   the 96k corpus, then free.
4. **Canonical breadth-first numbering is *not* a topological order.** A state can be
   discovered early through one predecessor and have another discovered later, so the
   dynamic programs cannot walk `reversed(range(num_states))`.
   `Dafsa.from_sequences(["a", "bc"])` is a two-transition counterexample, and a test
   pins it.
5. **`Automaton` is not generic over the weight type.** Weights are typed `Any`. Making
   the class `Automaton[W]` would thread a type parameter through every structure, the
   builder and `freeze()`'s overloads, for a gain confined to callers who mix semirings
   in one program. It is the clearest remaining typing wart.

### Weights

6. **A sequence's weight sits on its final state; every transition weight is `one`.**
   There is no canonical way to distribute a weight along a path — deciding that is
   exactly what weight pushing does — so construction does not invent one.
7. **`LOG.plus` is computed stably, not literally.** `-log(e⁻ᵃ + e⁻ᵇ)` is what the
   operation *means*; evaluating it directly is unusable, because `exp(-1000)` flushes to
   zero and the log of zero follows. The implementation factors out the smaller weight so
   the exponential is always of a non-positive number: `m - log1p(exp(m - M))`. Both
   failures of the direct form are pinned by tests.
8. **Dividing by `zero` raises `ZeroDivisionError` in every divisible semiring.** For the
   log-space semirings the tempting alternative is `-inf`, but no weight `w` satisfies
   `times(w, inf) == left` for finite `left`, so there is nothing honest to return.
9. **`COUNTING` is deliberately not divisible.** Integer division is not exact, and a
   semiring that silently truncated would corrupt weight pushing in a way that is hard to
   attribute later.
10. **Weight pushing needed an initial weight on the core.** The front of the first
    transition has nowhere further to push to, so without somewhere to put the remainder
    the total weight of the language would change. A single scalar solves it, and a
    property test asserts every accepted sequence keeps its weight to within the rounding
    that division introduces.
11. **`k_best` enumerates rather than prunes, and says so.** Before pushing, no prefix
    carries information about how good its extensions might be, so the implementation
    examines every accepted sequence while holding only *k* — O(*n* log *k*) time, O(*k*)
    memory. It is refused outright for non-idempotent semirings, where `plus` accumulates
    rather than selects and "best" has no meaning.

### Structures

12. **Compaction does not require the predecessor to have one out-edge.** 1.0 did, and
    the condition is unnecessary: a compound label keeps the first token of the edge it
    replaces, so a branching predecessor's transitions stay distinguishable and
    determinism is untouched. Dropping it compacts strictly more — `["axyz", "b"]`
    collapses to two transitions out of the root rather than leaving `xyz` expanded.
13. **Compound labels do not change the CSR layout.** `_symbol` keeps one symbol per
    transition — the *first* of its label — so ordering, determinism and the binary
    search in `step` work unchanged. A parallel `_labels` list holds the full tuple and is
    `None` when every label has length one.
14. **Compacted labels are token tuples, not `(start, length)` spans.** Spans would be
    more compact for a single long text, but they would make the substring index a second
    representation with its own traversal, and they cannot express a label whose tokens
    are not contiguous in any one source — which is what a compacted *dictionary* has.
15. **Suffix links are not kept after freezing.** That costs
    `longest_common_subsequence_with` its linear-time algorithm — it restarts at each
    position, so it is O(len(other) × longest match). Storing them would be an array in
    the core for one structure's benefit; revisit if the quadratic worst case ever bites.
16. **An `Fst` needed no new core.** A *pair of tokens is itself a token* — hashable, and
    so something an `Alphabet` can number — so an `Fst` is an ordinary `Automaton` over an
    alphabet of pairs and inherits minimization, counting, compaction and export
    unchanged. It also means core determinism is one transition per *pair*, not per input,
    which is exactly the ambiguity a transducer is allowed to have.
17. **The composition epsilon filter has two states, not three.** The textbook filter is
    usually given as three, forbidding a right-alone move after a left-alone one *and* the
    reverse. Implemented literally that loses the path entirely when one side deletes
    while the other inserts; a test caught it on `("ab" → "m") ∘ ("m" → "xy")`, which
    composed to nothing. Exactly one of the two orders must be allowed.
18. **`compose` refuses an ambiguous result** rather than determinizing it, and
    **`project` is unweighted.** Both would need weighted determinization, which is a
    different algorithm and out of scope. Dropping the weights is honest; carrying one
    arbitrary path's is not.

### Packaging and infrastructure

19. **networkx moved to an optional `graph` extra.** Nothing outside the export layer
    needs it — `match()` closed #8 without it, even though that issue suggested reaching
    for networkx. The library has no required dependencies.
20. **Export only, no loaders.** Sequences are the source of truth and construction is
    fast enough to rebuild. The CSR layout is chosen so a binary format is additive if
    that day comes.
21. **`resources/template.dot` deleted.** Emitting DOT directly is what makes it possible
    to set graph-level attributes at all — the template had placeholders for nodes and
    edges and no way to express `charset` or `fontname`, which is the immediate cause of
    #15.
22. **`daciuk/` removed** — 896 KB of GPL-2 C source in an MIT repository. The tarballs
    remain in git history and the User Guide's references section cites the algorithms,
    Daciuk's personal page, and the archive.org snapshot.
23. **`requirements.txt` deleted.** PEP 621 `dependencies` is the single source, and a
    duplicate list drifts. Closed issue #4 asked for that file; the request it was serving
    — an explicit, discoverable dependency list — is met by `pyproject.toml`.
24. **`mkdocs` pinned to `<2` and `mkdocs-material` to `<10`.** MkDocs 2.0 removes the
    plugin system outright, breaking both `mkdocs-material` and `mkdocstrings` with no
    migration path. Defensive, not permanent.
25. **Tests ship in the sdist**, so downstream packagers can run them at build time.

### Known limits

26. **#15's original tofu could not be reproduced** on the development machine, because
    fontconfig there substitutes a covering font for Graphviz's unresolvable default. What
    *is* verified is that naming a font changes which font is embedded, which is the
    mechanism the fix relies on.

    That verification is inherently machine-dependent, and the CI matrix proved it: the
    GitHub Linux images ship DejaVu, the macOS and Windows ones do not, and there Graphviz
    silently substitutes another face, so a PDF asserted to name `DejaVuSans` names
    something else. Naming a font is all the library can do; honouring the name is the
    system's business. The test therefore splits in two — that the DOT and the rendered
    output carry the font the caller asked for is asserted everywhere, while the assertion
    about which face is *embedded* is skipped where a probe render shows Graphviz cannot
    resolve it.
27. **Weight-aware minimization shares fewer states** than 1.0's minimize-then-count
    approach, so weighted automata are larger. `push()` recovers some of it:
    `{"ax": 0.3, "bx": 0.7}` minimizes to five states against three unweighted, and
    `minimize(push(a))` returns to three with every weight intact.
28. **Scale target is around 10⁶ sequences** in pure Python. If real corpora push past
    that, the escape hatch is streaming construction from pre-sorted symbols plus,
    eventually, an optional native backend — not a change to the public API.
29. **Automated sessions in this repository cannot touch `.github/workflows`.** The
    available credentials lack GitHub's `workflow` scope, so such a push is rejected
    outright and the contents API returns 404 for the same reason. A corollary that has
    already bitten once: a workflow file whose name is not exactly `*.yml` or `*.yaml` is
    silently ignored by Actions rather than reported as an error.
