# Changelog

## 2.0.0

A rewrite. 2.0 shares no implementation with 1.0 and its API is a deliberate break; `dafsa==1.0`
stays on PyPI, and the
[migration guide](https://dafsa.tresoldi.org/USER_GUIDE/#migrating-from-10) maps the old surface
onto the new one.

### Why

1.0 collected weights by re-walking sequences over the already-minimized graph. Because states
are shared after minimization, an edge counter held the total frequency of *every* sequence
crossing it, and `lookup()` returned the sum of those along the queried path:
`DAFSA(["dib", "tip", "tips", "top"]).lookup("tip")` gave `7` for a sequence inserted once. That
is not a patchable bug — weights need an algebra in which combining them along a path and across
paths is defined — and everything else followed from providing one.

### Added

- **A family of structures**, sharing one frozen core: `Trie`, `Dafsa`, `CompactDafsa`,
  `SuffixAutomaton`, `Cdawg` and `Fst`.
- **A semiring layer** (`dafsa.semirings`): a `Semiring` protocol plus boolean, counting,
  tropical, log, probability and Viterbi implementations, each checked against the semiring
  axioms property-based.
- **Weights that mean what they say.** `weight(seq)` returns what `seq` was inserted with,
  because minimization is weight-aware.
- **A counting layer.** `len()` in constant time, `rank`/`unrank` making the automaton a minimal
  perfect hash over its own language, ordered iteration, `starts_with`, `longest_prefix_of`,
  `total_weight` and `k_best`.
- **`match()`**, returning the states, transitions and weight of an accepted sequence
  ([#8](https://github.com/tresoldi/dafsa/issues/8)).
- **Path compaction** (`compact()`), collapsing forced chains into transitions labelled with
  several tokens.
- **Substring indexes.** `SuffixAutomaton` (online, linear-time) and `Cdawg`, with
  `contains_substring`, `num_substrings` and longest-common-substring.
- **Transducers.** `Fst` with `apply`, `project` and `compose`, over `(input, output)` pairs and
  `EPSILON`.
- **Weight pushing** (`push()`) for divisible semirings, and Revuz minimization.
- **An export layer** (`dafsa.export`): DOT, JSON, networkx, GML and GraphML.
- **Type annotations throughout**, checked with mypy in CI, with `py.typed` shipped.

### Changed

- Requires Python 3.10 or later.
- **Sequences are sorted as encoded symbols, never as tokens.** Mixed and mutually incomparable
  token types now work; 1.0 raised `TypeError`.
- **Tokenization is explicit.** `dafsa.tokenize`, and `--words`/`--sep` on the command line. The
  1.0 `delimiter` argument never split anything ([#17](https://github.com/tresoldi/dafsa/issues/17)).
- **State ids are dense and canonical**, renumbered at freeze time
  ([#7](https://github.com/tresoldi/dafsa/issues/7)).
- **`count_sequences()` split in two**: `len()` for distinct accepted sequences, `total_weight()`
  for how many were inserted.
- **The command-line interface** was rewritten; `--condense` is now `--compact`.
- **networkx is an optional dependency**, in the `graph` extra. It is needed only by the three
  graph exports.
- Documentation moved from Sphinx/ReadTheDocs to MkDocs Material, published to GitHub Pages: a
  landing page, one [User Guide](https://dafsa.tresoldi.org/USER_GUIDE/) covering concepts,
  worked examples, migration and references, and an API reference generated from the docstrings.
  Every `python` block in the README and the guide is executed by the test suite.
- `DESIGN.md` became [`ARCHITECTURE.md`](ARCHITECTURE.md), describing the delivered library rather
  than a plan, with the 1.0 audit as history and the decisions taken recorded as a log.

### Fixed

- `condense()` raising `IndexError` — the candidate filter excluded states with more than one
  incoming edge but not those with none, so the root qualified whenever it had a single outgoing
  edge ([#18](https://github.com/tresoldi/dafsa/issues/18),
  [#14](https://github.com/tresoldi/dafsa/issues/14)).
- `to_graph()` returning an undirected graph, and — unreported — writing every edge's label into
  one slot per pair of states, so parallel transitions lost all but one label
  ([#16](https://github.com/tresoldi/dafsa/issues/16)).
- Figures rendering accented and non-Latin tokens as boxes: the DOT output now declares a charset
  and a font with the coverage ([#15](https://github.com/tresoldi/dafsa/issues/15)).
- `RecursionError` on long sequences. Flat arrays and iterative traversal make it structurally
  unreachable, tested at 50,000 states through build, freeze, traverse, deep-copy and pickle
  ([#10](https://github.com/tresoldi/dafsa/issues/10)).
- `ZeroDivisionError` in `to_dot()` when built with `weight=False`, and `ValueError` on an empty
  automaton.
- A latent defect in the 1.0 minimizer, where `if child_idx:` treated state id `0` as "not
  found".

### Performance

Construction is roughly two orders of magnitude faster: the 0.5 changelog records 99,171
sequences taking "under 8 minutes", where a comparable corpus of 96,393 now builds in under four
seconds. Minimization also makes construction *cheaper* than building a trie, because fewer
states are ever allocated. `benchmarks/run.py` reproduces the numbers, and
`tests/test_performance.py` guards the scaling.

### Removed

- `DAFSANode` and `DAFSAEdge`. States are integers; there are no per-state objects.
- `d.nodes`, `d.lookup_nodes`, `dafsa.utils`.
- `lookup()`, whose cumulative weight was not a well-defined quantity.
- The vendored `daciuk/` archives — 896 KB of GPL-2 C source in an MIT repository. They remain in
  the git history, and the User Guide's references section cites the algorithms.
- `resources/template.dot`, superseded by the DOT emitter, which can set graph attributes.

---

## 1.0

- Minor code refactoring and linting
- Released and published version

## 0.6

- Documentation improvements following JOSS review
- Fixed bug where node finality was not considered in minimization

## 0.5.1

- Minor changes in preparation for submission (including tagged release)

## 0.5

- Improvements in speed, particularly in the `__eq__()` method of `DAFSANode` and the
  `_minimize()` method of `DAFSA`. The computation of a DAFSA for the contents of
  `/usr/share/dict/words` in the test machine (99,171 sequences) is now performed in under 8
  minutes.
- Added code from Daciuk's packages in an extra directory, along with notes on license

## 0.4

- Full documentation for existing code
- Added GML, PDF, and SVG export
- Allow to access all options from command-line

## 0.3

- Allow to join transitions in single sub-paths
- Allows to export a DAFSA as a `networkx` graph
- Preliminary documentation at ReadTheDocs

## 0.2.1

- Added support for segmented data

## 0.2

- Added support for weighted edges and nodes
- Added DOT export and Graphviz generation
- Refined minimization method, which can be skipped if desired (resulting in a standard trie)
- Added examples in the resources, also used for test data

## 0.1

- First public release.
