# Migrating from 1.0

`dafsa` 2.0 is a rewrite. It shares no implementation with 1.0 and its API is a
deliberate break, so 1.0 code will not run unchanged. This document maps the old
surface onto the new one.

If you need the old behaviour rather than a port, `dafsa==1.0` stays on PyPI and is
the version the JOSS paper describes.

## Why the break

1.0 stored automata as a linked graph of Python objects and collected weights by
re-walking sequences over the already-minimized graph. That last detail is the one that
forced the rewrite: because states are shared after minimization, an edge counter ended
up holding the total frequency of *every* sequence crossing that edge, and `lookup()`
returned the sum of those along the queried path. In 1.0,
`DAFSA(["dib", "tip", "tips", "top"]).lookup("tip")[1]` returned `7` for a sequence
inserted once. In 2.0:

```python
from dafsa import Dafsa
from dafsa.semirings import COUNTING

automaton = Dafsa.from_sequences(["dib", "tip", "tips", "top"], semiring=COUNTING)
assert automaton.weight("tip") == 1
```

Fixing that is not a patch — it needs weights to live in an algebra where combining
them along a path and across paths is defined. That is the semiring layer, and
everything else followed from having one.

## What maps to what

| 1.0 | 2.0 |
|---|---|
| `DAFSA(seqs)` | `Dafsa.from_sequences(seqs)` |
| `DAFSA(seqs, minimize=False)` | `Trie.from_sequences(seqs)` |
| `DAFSA(seqs, weight=True)` | `Dafsa.from_sequences(seqs, semiring=COUNTING)` |
| `DAFSA(seqs, condense=True)` | `Dafsa.from_sequences(seqs).compact()` |
| `DAFSA(seqs, delimiter=" ")` | `Dafsa.from_sequences(tokenize(line) for line in lines)` |
| `d.lookup(seq)` | `seq in d`, `d.weight(seq)`, or `d.match(seq)` |
| `d.count_nodes()` | `d.num_states` |
| `d.count_edges()` | `d.num_transitions` |
| `d.count_sequences()` | `len(d)` for distinct sequences; `d.total_weight()` under `COUNTING` for insertions |
| `d.nodes`, `d.lookup_nodes` | removed — states are integers; use `d.transitions(q)` |
| `DAFSANode`, `DAFSAEdge` | removed — there are no per-state objects |
| `d.to_graph()` | `export.to_networkx(d)`, now a `MultiDiGraph` |
| `d.to_dot()` | `export.to_dot(d, ...)` |
| `d.write_figure(path, dpi)` | `export.write_figure(d, path, dpi=...)` |
| `d.write_gml(path)` | `export.write_gml(d, path)` |
| `d.condense()` (in place) | `d.compact()` (returns a new automaton) |
| `dafsa.utils.*` | internal, not public |
| `print(d)` node dump | not a stable format; use `export.to_json` or `export.to_dot` |

On the command line, `--condense` is now `--compact`, and tokenization is explicit:
`--words` or `--sep SEP`.

## Things that changed meaning

**`lookup()` has no direct replacement.** Its cumulative weight was not a well-defined
quantity. Choose what you actually wanted: membership → `seq in automaton`; the
sequence's weight → `automaton.weight(seq)`; the path it took → `automaton.match(seq)`,
which returns the states, the transitions and the weight, as asked for in
[issue #8](https://github.com/tresoldi/dafsa/issues/8).

**`count_sequences()` counted the input list, duplicates included**, while describing a
set. 2.0 separates the two: `len(automaton)` is how many distinct sequences are
accepted, and `total_weight()` under `COUNTING` is how many were put in.

**`delimiter` never split anything.** It only joined labels when condensing, so
`DAFSA(["a b c"], delimiter=" ")` treated the spaces as tokens — the subject of
[issue #17](https://github.com/tresoldi/dafsa/issues/17). Splitting is now explicit,
with `tokenize`.

**State ids have no gaps and no meaning.** 1.0 left holes where merged nodes had been
([issue #7](https://github.com/tresoldi/dafsa/issues/7)); 2.0 renumbers canonically at
freeze time. They are still meaningless as identifiers, because a shared suffix state
is reached by every prefix leading to it — use `rank`/`unrank` when you want a stable
number for a *sequence*.

## Things that no longer fail

| Was | Now |
|---|---|
| `condense()` raising `IndexError` ([#18](https://github.com/tresoldi/dafsa/issues/18), [#14](https://github.com/tresoldi/dafsa/issues/14)) | `compact()`, tested on both reporters' inputs |
| `to_graph()` undirected, parallel edge labels lost ([#16](https://github.com/tresoldi/dafsa/issues/16)) | `to_networkx()` returns a `MultiDiGraph`, one edge per transition |
| Accented characters drawn as boxes ([#15](https://github.com/tresoldi/dafsa/issues/15)) | the DOT emitter declares `charset` and a font with coverage |
| `RecursionError` on long sequences ([#10](https://github.com/tresoldi/dafsa/issues/10)) | flat arrays, iterative traversal; tested at 50,000 states |
| `TypeError` on mixed token types | sequences are sorted as encoded symbols, never as tokens |
| `ZeroDivisionError` in `to_dot()` with `weight=False` | scaling is opt-in and guarded |
