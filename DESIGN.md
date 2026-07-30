# `dafsa` 2.0 — Design Document and Migration Plan

Status: accepted; milestones 0–11 implemented (see §12)
Target: a single `2.0.0` release (clean break from `1.0`)
Scope of this document: what 2.0 is, why the 1.0 internals are being replaced rather than
patched, the concrete API, and the ordered plan to get there.

---

## 1. Purpose

`dafsa` 1.0 computes a minimal deterministic acyclic finite-state automaton from a list of
sequences, and draws it. It is cited (JOSS 2020, Zenodo DOI 10.5281/zenodo.3668870) and is,
as one bug reporter put it, "the one people will most likely find when looking for a DAFSA
implementation in Python."

2.0 keeps that role — a readable reference implementation for linguists and researchers —
and widens it in three directions:

1. **A family of structures**, not one class: trie, DAFSA, path-compacted DAFSA, suffix
   automaton / CDAWG, and acyclic weighted transducers.
2. **Weights that mean something**: a proper weighted automaton over an explicit semiring,
   instead of 1.0's frequency counters, whose composition is not well defined (§2.3).
3. **A representation that scales**: flat arrays instead of a linked graph of Python
   objects, so the library is fast, memory-frugal, serialisable, and structurally immune to
   recursion limits.

**Non-goals for 2.0.** Incremental insertion or deletion after construction (structures are
built then frozen); cyclic automata and general regular-expression compilation; a C or Rust
extension; loading automata from disk (export only, §8); any change to `manuscript/`.

---

## 2. Audit of 1.0

The 1.0 implementation lives in git history at `a78c94e~1` (`dafsa/dafsa.py`, 983 lines);
`master` currently holds only a stub under `src/dafsa/`. The findings below are what 2.0 has
to answer for. Line numbers refer to `dafsa/dafsa.py` at that commit, and every symptom was
reproduced by running that code, except where noted as latent.

### 2.1 Open issues and their root causes

| Issue | Symptom | Root cause |
|---|---|---|
| [#18](https://github.com/tresoldi/dafsa/issues/18), [#14](https://github.com/tresoldi/dafsa/issues/14) | `condense()` raises `IndexError: list index out of range` | `_joining_round` (L645–655) skips candidates with `targets[node_id] > 1` but never excludes nodes with **zero** in-edges. The root node qualifies whenever it emits a single edge, and `[edge for edge in edges if edge["target"] == node_id][0]` then indexes an empty list. `DAFSA(["tapas", "topos"])` hits it on the root's single `t` edge. |
| [#17](https://github.com/tresoldi/dafsa/issues/17) | `delimiter=" "` ignored; spaces become tokens | `delimiter` is never used to split input. It is only used to *join* labels when compacting (L679). A `str` input is iterated character by character, spaces included. `__main__.py` splits on whitespace before calling the library, so the CLI appears to work while the API does not. |
| [#16](https://github.com/tresoldi/dafsa/issues/16) | `to_graph()` returns an undirected graph, contradicting its docstring | `nx.Graph()` at L927. Two further defects in the same method: a nested loop over all nodes re-adds every edge once per node (O(n²) work), and `graph[l_id][r_id]["label"] = label` overwrites the label whenever two transitions connect the same pair of states. |
| [#15](https://github.com/tresoldi/dafsa/issues/15) | PDF/PNG show tofu boxes with Unicode codepoints instead of glyphs | `resources/template.dot` declares neither `charset` nor `fontname`, so Graphviz renders with a default font that has no coverage for the requested glyphs — the box-with-codepoint output is that font's missing-glyph fallback. |
| [#10](https://github.com/tresoldi/dafsa/issues/10) | Recursion limit | `copy.deepcopy(self.nodes)` (L459) walks the linked `DAFSANode` graph recursively, one frame per state along a path; the same applies to pickling or any recursive traversal of the object graph. Depth is proportional to sequence length. |
| [#8](https://github.com/tresoldi/dafsa/issues/8) | `.lookup()` cannot return a path | It returns `(final_node, cum_weight)` only, and the weight is not interpretable (§2.3). |
| [#7](https://github.com/tresoldi/dafsa/issues/7) | Gaps in node ids after minimization | Ids come from a global `itertools.count()`; merged nodes are abandoned and their ids are never reused. |

### 2.2 Additional defects found in the audit (no issue filed)

- **Latent falsy-id defect in the minimizer.** `if child_idx:` (L575) treats the node id `0` as
  "not found", because `0` is falsy, so a child found equivalent to the root would be discarded
  instead of merged. The test should be `if child_idx is not None`. Searching 20,000 random
  corpora produced no input that reaches the branch — the root's out-edge set is the set of all
  distinct initial tokens, which is hard for an interior state to match — so this is recorded as
  a latent defect rather than an observable bug. 2.0 removes the possibility by keying the
  register on state signatures instead of scanning for an index.
- **Minimization is quadratic.** `_minimize` finds an equivalent state by scanning every node
  in `self.nodes` (L570), and the whole pass is wrapped in a `while True` that restarts on any
  change (L543). `DAFSANode.__hash__` exists but no register/dictionary is used, discarding
  the whole point of Daciuk's algorithm. The 0.5 changelog records the consequence: 99,171
  sequences in "under 8 minutes".
- **`to_dot()` divides by zero.** `max_weight = max(node.weight ...)` (L861) is `0` when the
  object was built with `weight=False`, and `node.weight / max_weight` then raises
  `ZeroDivisionError`. `max()` on an empty node set raises `ValueError`.
- **The compaction de-duplication guard does not work.** `edge_info` is a dict, so
  `for node_id in edge_info` (L666) iterates the literal keys `"source"` and `"target"`, and
  `transitions_nodes += edge_info` (L667) appends those same strings. After the first accepted
  candidate the guard rejects everything, so `_joining_round` performs at most one join per
  call — measured on `DAFSA(["abcde", "xbcde"])`, the successive rounds return `1, 1, 1, 0`.
  `condense()` still converges, via O(n) rounds of O(n²) work each.
- **Compaction assumes string tokens.** `self._delimiter.join([label_from, label_to])` (L679)
  raises `TypeError` for tuple or integer tokens.
- **Compaction desynchronises the object.** It mutates `self.nodes` while `lookup()` reads the
  `copy.deepcopy` kept in `self.lookup_nodes` (L459). After `condense()`, `count_nodes()` and
  `count_edges()` describe a different graph from the one `lookup()` queries, and peak memory
  is doubled.
- **`__eq__`, `__hash__`, and `__gt__` disagree.** `__eq__` compares `final` (L184) while
  `__hash__` and `__gt__` delegate to `__str__`, which omits it (L92–97). The ordering is not
  consistent with equality.
- **`sorted(sequences)` (L432) is a type trap.** Daciuk's construction needs the input sorted
  in the same order the algorithm compares tokens, so 1.0 sorts the caller's sequences
  directly. Mixed input types raise `TypeError`, and tuples of mutually incomparable tokens —
  the normal case for linguistic feature bundles — cannot be used at all.
- **`count_sequences()` counts duplicates** in the input list, while the automaton represents
  a set.
- **`DAFSAEdge` subclasses `dict`** and stores nothing in it.

### 2.3 The weight semantics are the deepest problem

1.0 minimizes first and *then* re-walks every sequence over the minimized graph
(`_collect_weights`, L702–723), incrementing a counter on each edge traversed. Because states
are shared after minimization, an edge counter ends up being the total frequency of *all*
sequences that traverse that edge, and `lookup()` returns the sum of those counters along the
queried path. That number does not answer any question the user asked. Concretely:

```python
>>> DAFSA(["dib", "tip", "tips", "top"]).lookup("tip")[1]
7          # 3 (root—t, shared by tip/tips/top) + 2 (t—i) + 2 (i—p)
```

`"tip"` was inserted once. There is no reading of `7` as a weight of `"tip"`.

This is not a bug to patch; it is the absence of an algebra. A weighted automaton needs one
operation to combine weights *along* a path and another to combine weights *across*
alternative paths, with the identities and distributivity that make the combination
associative and order-independent. That is a semiring, and it is the reason §5 exists. Once
weights live in a semiring and minimization is weight-aware, the weight of a path is by
construction the weight that was assigned to that sequence.

---

## 3. Design principles

1. **Readable first.** This is a reference implementation. Where a clear algorithm and a
   clever one differ measurably, take the clear one and record the benchmark.
2. **Build, then freeze.** Construction happens in a builder; the result is an immutable,
   canonically numbered, flat-array automaton. No post-construction mutation.
3. **No recursion, ever, on data-dependent depth.** Every traversal is iterative with an
   explicit stack or a topological order.
4. **Tokens are opaque.** The core never assumes tokens are strings, comparable, or
   single-character.
5. **Separate structure from rendering.** Nothing in the core knows about Graphviz, DOT,
   fonts, or networkx.
6. **Correctness is checked independently.** Minimality, determinism, and weight preservation
   are verified by code that does not share an implementation with the builder (§11).

---

## 4. Core representation

### 4.1 Alphabet

Tokens are mapped to dense integer symbol ids by an `Alphabet`:

```python
class Alphabet:
    tokens: tuple[Hashable, ...]        # symbol id -> token
    def id(self, token: Hashable) -> int
    def __len__(self) -> int
```

Ids are assigned in sorted token order when the tokens are mutually comparable, and in
first-encountered order otherwise. Either way, **the automaton is built by sorting tuples of
integer ids, never the caller's sequences** — which removes the entire `TypeError` class of
§2.2 and makes "sorted input" an internal invariant rather than a caller obligation. Iteration
order is documented as the alphabet's order, which coincides with lexicographic order in the
comparable case.

### 4.2 Frozen automaton (CSR arrays)

A frozen automaton is compressed-sparse-row adjacency over `array.array` — no per-state or
per-transition Python objects:

```
alphabet      Alphabet
s_first       array[int32], length num_states + 1     # transitions of q are [s_first[q] : s_first[q+1]]
t_symbol      array[int32], length num_transitions    # sorted by (source, symbol)
t_target      array[int32], length num_transitions
s_flags       array[uint8]                            # bit 0: final
t_weight      list[W] | None                          # semiring elements, weighted case only   [M3]
s_final       list[W] | None                          # final weights, weighted case only       [M3]
s_count       array[int64] | None                     # accepted suffixes from q (§6.3), lazy   [M4]
```

The fields marked `[M3]` and `[M4]` are added by the milestone noted, not carried as `None`
placeholders beforehand: a weight field means nothing until the semiring that interprets it
exists, and a field whose only possible value is `None` is worse documentation than its
absence. The first four fields plus `s_flags` are what milestone 1 built.

The weight fields stay `None` even *after* milestone 3 whenever every weight equals the
semiring's `one`, which is the case for any plain acceptor and for a counting automaton whose
every count is 1. `weight()` then returns `one` for an accepted sequence without consulting an
array. A weightless structure therefore pays nothing for the weight machinery, which matters
because memory frugality is much of the argument for this representation.

Consequences, each of which answers something in §2:

- Transition lookup is a `bisect` over one state's sorted symbol slice: O(log k).
- Memory is ~12 bytes per transition plus the weight list, against several hundred bytes for a
  `DAFSANode` + `DAFSAEdge` pair.
- State ids are dense, `0` is the root, and numbering is canonical (BFS from the root,
  transitions in symbol order) — **issue #7 disappears by construction**, no flag needed.
- There is no object graph to deep-copy and no recursive structure to traverse — **issue #10
  becomes structurally unreachable**.
- The arrays are the serialisation format (§8).

### 4.3 Builder

During construction only the states on the path just inserted are mutable. The builder holds
growable parallel lists (`list[list[int]]` for symbols and targets per state) rather than node
objects, and `freeze()` flattens them into the CSR arrays with canonical renumbering. This is
the "array-based from the start" decision: at no point does a node become a first-class
object that user code can hold a reference to.

`freeze()` is where the frozen core's invariants are *established* rather than assumed, which
is the point of having a build/freeze split at all. It performs four jobs:

1. **Canonical renumbering.** Breadth-first from the root, following each state's transitions
   in ascending symbol order. Numbering therefore depends only on the automaton's shape, so
   two builders describing the same automaton freeze to byte-identical arrays. That is a
   stronger property than "no gaps" and is what makes the arrays comparable and diffable.
2. **Reachability pruning.** States allocated and then abandoned cost nothing in the result.
3. **Determinism.** Enforced when a transition is added, so a duplicate symbol is reported at
   the call site that caused it rather than discovered at freeze time.
4. **Acyclicity.** Iterative three-colour depth-first search. The distinction that matters:
   an edge into a *grey* state is a cycle, an edge into a *black* state is not. Converging
   paths are exactly the state sharing that makes a DAFSA a DAFSA, so a check that rejected
   them would reject every structure this library exists to build.

Every pass is iterative. Nothing in the builder recurses on the structure being built, which
is what makes §2.1's issue #10 unreachable rather than merely unlikely.

Errors are raised as a small family in `dafsa.exceptions`, each deriving from `DafsaError`
*and* from the built-in a caller would reasonably catch: `UnknownTokenError` (a `KeyError`),
`DeterminismError` and `AcyclicityError` (both `ValueError`).

---

## 5. Semiring layer

```python
class Semiring(Protocol[W]):
    zero: W                                  # additive identity, multiplicative annihilator
    one: W                                   # multiplicative identity
    def plus(self, a: W, b: W) -> W: ...     # combine across alternative paths
    def times(self, a: W, b: W) -> W: ...    # combine along a path
    def key(self, a: W) -> Hashable: ...     # canonical form, for the minimization register

    idempotent: bool
    commutative: bool
    divisible: bool                          # supports divide(), enabling weight pushing
    def divide(self, a: W, b: W) -> W: ...   # optional
```

Built-ins, as module-level singletons:

| Semiring | ⊕ | ⊗ | 0̄ | 1̄ | Use |
|---|---|---|---|---|---|
| `BOOLEAN` | ∨ | ∧ | `False` | `True` | plain acceptors (**default**) |
| `COUNTING` | `+` | `×` | `0` | `1` | frequencies, integer-exact |
| `TROPICAL` | `min` | `+` | `inf` | `0` | costs, shortest path |
| `LOG` | `-log(e⁻ᵃ+e⁻ᵇ)` | `+` | `inf` | `0` | probabilities in negative-log space |
| `PROBABILITY` | `+` | `×` | `0.0` | `1.0` | direct probabilities |
| `VITERBI` | `max` | `×` | `0.0` | `1.0` | best-path probability |

`star` is deliberately absent: every structure in 2.0 is acyclic, so no closure is needed. It
can be added to the protocol as optional if cyclic support ever lands.

Users supply their own by satisfying the protocol; nothing in the algorithms inspects the
concrete type.

**Weight-aware minimization.** Two states are equivalent only if their final weights and their
outgoing `(symbol, target, weight)` triples agree, compared through `Semiring.key`. This is
what makes `weight(seq)` equal to the weight assigned to `seq` (§2.3), at the cost of less
state sharing than an unweighted DAFSA. Weight pushing (Mohri) recovers some of that sharing
for divisible semirings and is offered as an explicit optional pass, not a default.

Two decisions taken while implementing this layer:

- **`LOG.plus` is computed stably, not literally.** The spelling in the table above is what the
  operation *means*; evaluating it directly is unusable, because `exp(-1000)` flushes to zero
  and the log of zero follows. The implementation factors out the smaller weight so the
  exponential is always of a non-positive number: `m - log1p(exp(m - M))`. That form is correct
  at magnitudes where the direct one underflows in one direction and raises `OverflowError` in
  the other, and both failures are pinned by tests.
- **Dividing by `zero` raises `ZeroDivisionError` in every divisible semiring.** For the
  log-space semirings the tempting alternative is to return `-inf`, but no weight `w` satisfies
  `times(w, inf) == left` for finite `left`, so there is nothing honest to return. This makes
  the tropical and log semirings behave like the probability ones, which raise for the same
  reason.

`COUNTING` is deliberately **not** divisible: integer division is not exact, and a semiring
that silently truncated would corrupt weight pushing in a way that is hard to attribute later.

---

## 6. Structures

All structures share the frozen core of §4.2 and differ only in construction and label type.

### 6.1 `Trie`

Prefix tree, no suffix sharing. Same incremental insertion, no register. Kept because it is
the honest baseline for the trie-vs-DAFSA comparison the README is built around, and because
1.0's `minimize=False` produced a trie by disabling the minimizer's effect while still paying
its cost.

### 6.2 `Dafsa`

Daciuk's incremental construction from sorted symbol-id tuples, with a **register**:
`dict[StateKey, int]`, where `StateKey` is `(is_final, final_weight_key, symbol₀, target₀,
weight₀_key, …)`. Children are registered before their parents, so the key is well defined and
equivalence testing is a single dict lookup on a hash of the state's out-degree — replacing
1.0's linear scan and its restart loop.

One departure from the classic formulation, which is what lets the builder stay append-only.
The textbook version wires a parent to its child immediately and *rewires* that edge when the
child turns out to be equivalent to a registered state. Here the parent's edge is instead
deferred until the child is popped from the unchecked chain — at which point the child's own
edges are all present and its canonical representative is known — so each edge is added exactly
once and nothing is ever rewired. The builder therefore needs no operation for mutating an
existing transition, and a state that lost to a canonical representative is simply never
referenced: `freeze()` prunes it as unreachable, using machinery that already had to exist.

### 6.3 Counting, ranking, and enumeration

At freeze time, one reverse-topological pass fills `s_count[q]` = number of accepted sequences
reachable from `q`. In O(|transitions|) this buys:

- `len(automaton)` in O(1) — the number of *distinct* accepted sequences, fixing §2.2's
  duplicate-counting confusion.
- `rank(seq) -> int` and `unrank(i) -> tuple` — the automaton as a minimal perfect hash over
  its language, in lexicographic order. This is a standard and genuinely useful property of
  minimal acyclic DFAs that 1.0 did not expose.
- `total_weight()` — ⊕ over all accepted paths, by the same topological pass.
- Lazy lexicographic iteration and k-best extraction.

### 6.4 `CompactDafsa`

Path compression of a frozen `Dafsa`: a maximal chain of states each having exactly one
in-edge and one out-edge, non-final, whose predecessor has exactly one out-edge, collapses
into a single transition labelled with a **tuple of tokens**. Differences from 1.0's
`condense()`:

- Candidate selection uses in-degrees computed once over the CSR arrays. The predicate is
  `indeg(q) == 1`, not `indeg(q) <= 1`, so the root — and every other source — is excluded.
  **This is the fix for #18 and #14.**
- All candidate chains are collapsed in one pass, not one per round.
- Labels are token tuples, so nothing is `str.join`-ed and non-string tokens work.
- It returns a **new frozen automaton** rather than mutating in place, so there is no
  `lookup_nodes` shadow copy and no way for the reported counts to describe a different graph
  from the one being queried.
- Joining tokens into a display string is a rendering concern, handled by the DOT emitter's
  `label_sep` parameter.

**One deliberate departure from the condition stated above.** 1.0 also required the *predecessor*
to have exactly one outgoing edge, and this document originally repeated that. The condition is
unnecessary: a compound label keeps the first token of the edge it replaces, so a branching
predecessor's transitions stay distinguishable and determinism is untouched. Dropping it
compacts strictly more — `["axyz", "b"]` collapses to two transitions out of the root rather
than leaving the `xyz` chain expanded.

**Compound labels do not change the CSR layout.** `t_symbol` keeps holding one symbol per
transition — the *first* of its label — so ascending order within a state, determinism, and the
binary search in `step` all work unchanged. A parallel `labels` list holds the full tuple, and
is `None` when every label has length one, exactly as the weight arrays are. What changes is
only how many tokens a transition consumes, which the traversal, ranking and enumeration code
now accounts for.

Measured on the 96,393-sequence corpus: 109,160 states fall to 39,864 (63% fewer) and 194,703
transitions to 125,407, in 0.64s. The language, `len()`, iteration order and every weight are
unchanged, which is the whole contract.

### 6.5 `SuffixAutomaton` and `Cdawg`

Worth stating plainly, because the two were run together in earlier scoping: a *compact
DAFSA* (§6.4) and a *CDAWG* in the literature are different structures. §6.4 is a
path-compressed dictionary automaton. A suffix automaton (DAWG) is the minimal DFA accepting
every **substring** of a single sequence; the CDAWG is its path-compressed form. 2.0 provides
both, because the substring index is what makes longest-common-substring, substring search,
and repeat detection possible — capabilities the dictionary structures cannot offer.

- `SuffixAutomaton.from_sequence(seq)` — online construction (Blumer et al.), linear time.
- `Cdawg` — path-compressed suffix automaton.

**A correction to the sentence above.** This section originally said the suffix automaton is
"the minimal DFA accepting every **substring**". That is a real structure, but it is the wrong
one to compact: if every state accepts, no state is ever absorbable and `compact()` does
nothing, so the CDAWG could not exist. The automaton built is therefore the classical one,
accepting the **suffixes**, with acceptance marking the states on the suffix-link chain. Every
*substring* is still indexed — it is exactly what can be walked from the root — so
`contains_substring()` deliberately ignores acceptance, while `in` does not. Compaction then has
non-accepting interior states to absorb and the CDAWG is a real structure.

Labels are the compound token tuples milestone 5 introduced, not `(start, length)` spans into
the source. Spans would be more compact for a single long text, but they would make the
structure a second representation with its own traversal, and they cannot express a label whose
tokens are not contiguous in any one source — which is what a compacted *dictionary* has.
Sharing one representation is worth more than the bytes.

Suffix links are scaffolding for construction and are not kept after freezing, which costs
`longest_common_subsequence_with` its linear-time algorithm: it restarts at each position, so it
is O(len(other) × longest match). Storing the links would be an array in the core for one
structure's benefit; revisit if the quadratic worst case ever bites.

### 6.6 `Fst`

**The representation needed no new core, which is the finding of this milestone.** A transition
carries an input and an output symbol, and a *pair of tokens is itself a token*: hashable, and
so something an `Alphabet` can number. An `Fst` is therefore an ordinary `Automaton` over an
alphabet of pairs, and inherits minimization, counting, compaction and export unchanged. It also
means core determinism is one transition per *pair*, not per input — which is exactly the
ambiguity a transducer is allowed to have, and why `apply()` returns a list.

Three decisions worth recording, each a limit rather than a feature:

- **The composition filter has two states, not three.** The textbook filter is usually given as
  three, forbidding a right-alone move after a left-alone one *and* the reverse. Implemented
  literally that loses the path entirely when one side deletes while the other inserts — a test
  caught it on `("ab" -> "m") o ("m" -> "xy")`, which composed to nothing. Exactly one of the two
  orders must be allowed, not neither: right-alone moves come before left-alone ones within a
  run, and the two filter states are "may still move right alone" and "may not".
- **`compose` refuses an ambiguous result** rather than determinizing it. If two composed paths
  carry the same input and output out of one state, resolving them means weighted
  determinization, which is a different algorithm and out of scope. The error names the pair.
- **`project` is unweighted.** Projection collapses paths that shared a side, and reconciling
  their weights is the same weighted determinization. Dropping the weights is honest; carrying
  one arbitrary path's is not.

Projection needed subset construction, and subset construction produces a DFA that is not
minimal, so milestone 7 also added **Revuz minimization** (`_algorithms.minimize`) — settle
states in reverse topological order, merge on signature. The dictionary structures do not need
it, since they minimize as they insert, but it now provides a strong independent check on them:
minimizing a `Trie` must produce exactly the `Dafsa` that the incremental construction builds,
by an entirely different route, and a property test asserts it does.

Acyclic weighted transducer. Transitions carry `(input_symbol, output_symbol, weight)` with
`EPSILON = -1` permitted on either side. Built from aligned sequence pairs; minimized by the
same register discipline over `(final, final_weight, sorted (in, out, target, weight))`.
`compose(f, g)` is the standard product construction with epsilon filtering; `project(side)`
yields an acceptor. This is the piece the morphology use case needs, and it is why the
semiring layer is generic rather than hard-coded to counts.

---

## 7. Public API

```python
import dafsa
from dafsa import Trie, Dafsa, CompactDafsa, SuffixAutomaton, Cdawg, Fst
from dafsa.semirings import BOOLEAN, COUNTING, TROPICAL, LOG, PROBABILITY, VITERBI
```

### Construction

```python
Dafsa.from_sequences(seqs: Iterable[Sequence[Hashable]], *, semiring=BOOLEAN) -> Dafsa
Dafsa.from_weighted(pairs: Iterable[tuple[Sequence[Hashable], W]], *, semiring) -> Dafsa
Dafsa.from_sorted_symbols(...)          # low-level, streaming, pre-sorted ids
dafsa.tokenize(text: str, sep: str | None = None) -> tuple[str, ...]
```

`Sequence[Hashable]` is the input contract. A `str` is accepted and documented as one token
per character; `dafsa.tokenize` is the explicit way to get multi-character tokens. **This is
the resolution of #17**: the constructor has no `delimiter` parameter to be misunderstood.

### Query

```python
seq in automaton                        -> bool
automaton.weight(seq)                   -> W                    # semiring.zero if rejected
automaton.match(seq)                    -> Match | None         # states, transitions, weight
automaton.paths(seq)                    -> Iterator[Path]       # all paths (ambiguous FSTs)
automaton.longest_prefix_of(seq)        -> tuple[Hashable, ...]
automaton.starts_with(prefix)           -> Iterator[tuple]
len(automaton)                          -> int                  # distinct accepted sequences
iter(automaton)                         -> Iterator[tuple]      # lexicographic
automaton.rank(seq) / automaton.unrank(i)
automaton.k_best(k)                     -> list[tuple[tuple, W]]
automaton.total_weight()                -> W
```

`Match` carries the state path, the transition path, and the semiring weight — **the
resolution of #8**, without needing networkx for the common case.

### What exists after milestone 1

The core is public and stable enough to build on; everything above that is not listed here is
still to come. `Alphabet` and `Automaton` are importable from `dafsa` directly, `Builder` is
`dafsa._builder.Builder` and stays private — callers reach it through the structures.

```python
Alphabet(tokens) / Alphabet.from_sequences(seqs)
alphabet.tokens / .id(token) / .token(symbol)
alphabet.encode(seq) / .try_encode(seq) -> tuple | None / .decode(symbols)
len(alphabet) / token in alphabet / iter(alphabet) / == / hash()

automaton.accepts(seq) -> bool          # seq in automaton
automaton.step(state, symbol)           -> State | None
automaton.walk(symbols, start=ROOT)     -> State | None
automaton.transitions(state) / .all_transitions() -> Iterator[Transition]
automaton.is_final(state) / .out_degree(state) / .states()
automaton.num_states / .num_transitions / .alphabet
```

`try_encode` returning `None` rather than raising is the deliberate half of the token
contract: a sequence containing a token the automaton has never seen is *not accepted*, which
is an answer, not an error. Only `encode` raises, for callers who mean it.

### Transform and inspect

```python
automaton.compact()                     -> CompactDafsa
automaton.push()                        -> Self                 # weight pushing, divisible semirings
dafsa.intersect(a, b) / union / concat
dafsa.compose(f: Fst, g: Fst)           -> Fst
automaton.num_states / num_transitions / input_count / semiring / alphabet
automaton.transitions(q)                -> Iterator[Transition]  # read-only view
```

---

## 8. Export

Export only, by decision: sequences are the source of truth and construction is fast enough to
rebuild. The CSR arrays make a compact binary format straightforward if loading is ever wanted,
so nothing here forecloses it.

```python
dafsa.export.to_dict(a) / to_json(a, path=None)
dafsa.export.to_dot(a, *, label_nodes=False, fontname="DejaVu Sans", charset="UTF-8",
                    weight_scale=1.5, label_sep=" ") -> str
dafsa.export.write_figure(a, path, *, dpi=300, **dot_kwargs)
dafsa.export.to_networkx(a) -> nx.MultiDiGraph
dafsa.export.write_gml(a, path) / write_graphml(a, path)
```

- The DOT emitter declares `charset="UTF-8"` and a configurable `fontname` defaulting to a
  wide-coverage font, and escapes labels properly — **the fix for #15**, together with a
  documented note that Graphviz must be able to find a font covering the tokens in use.
  Escaping is not cosmetic: a token containing a quote or a backslash would otherwise end the
  DOT attribute early and produce a file Graphviz rejects. The tests render every generated
  source through `dot` rather than pattern-matching the text, because source Graphviz will not
  parse is not an export.
- `resources/template.dot` is deleted. Emitting the source directly is what makes it possible
  to set graph-level attributes at all — the template had placeholders for nodes and edges and
  no way to express `charset` or `fontname`, which is the immediate cause of #15.
- Node sizing guards against `max_weight == 0` and against an empty automaton, fixing the
  `ZeroDivisionError` and `ValueError` of §2.2.
- `to_networkx` returns a **`MultiDiGraph`**, built in a single pass over the CSR arrays, one
  edge per transition, each carrying its own `label` and `weight` — **the fix for #16**,
  including the parallel-edge label loss and the O(n²) nested loop that the issue did not
  mention.

**On networkx.** It stays a core dependency, used for the graph exports, GML/GraphML writing,
and networkx-backed extras such as full path enumeration. Construction, minimization, lookup,
counting, and k-best are implemented directly on the CSR arrays: they are the algorithms this
library exists to show, and delegating them would defeat the point as well as being slower.

That revisit is now due, and the answer is clear: **networkx earns only the export surface.**
Nothing in milestones 0–5 needed it, `match()` closed #8 without it — the 1.0 issue explicitly
suggested reaching for networkx to return paths — and here it is used for `to_networkx`,
`write_gml` and `write_graphml`, all of which are optional to any actual use of the library. It
should move to an optional `graph` extra before release, with the three functions raising a
clear error when it is absent. That is a packaging change, not a design change, and it belongs
with milestone 12.

**Graphviz** is not a Python dependency at all — `write_figure` shells out to `dot`, and its
absence raises `ExportError` with a message saying so. `to_dot` returns source regardless, so a
caller without Graphviz can still render elsewhere.

---

## 9. Command-line interface

```
dafsa [-f trie|dafsa|compact|suffix|cdawg] [-s boolean|counting|tropical|log|probability|viterbi]
      [-o OUTPUT] [-t stdout|json|dot|png|pdf|svg|gml|graphml] [--dpi N]
      [--sep SEP] [--label-nodes] [--font NAME] SOURCE
```

`--condense` becomes `--compact`; `--sep` makes the tokenization that 1.0 did implicitly (and
undocumentedly, in `__main__.py`) explicit and optional.

**Tokenization needed two flags, not one.** `--sep` was specified with an optional value so that
bare `--sep` could mean whitespace. In `argparse` that is a trap: `dafsa --sep words.txt` assigns
the *filename* to `--sep` and then reports the positional as missing, because nothing
distinguishes an omitted optional value from the argument that follows it. So `--sep SEP` takes a
required value and `--words` splits on whitespace, the two being mutually exclusive, and omitting
both leaves every character a token. `--sep ""` is rejected with a message pointing at `--words`,
since `str.split("")` raises.

This is the half of **#17** the API could not fix. 1.0's `__main__.py` called `line.split()`
whenever it saw a space, so the command line appeared to handle word tokens while the API did
not — and neither side made the difference visible. The split is now one flag that does nothing
unless asked, calling the same `tokenize` the API exposes.

---

## 10. Repository and infrastructure changes

| Area | Change |
|---|---|
| Python | `requires-python = ">=3.10"`; CI matrix 3.10–3.13 |
| Packaging | Delete `setup.py`; single version source via `importlib.metadata` (today `pyproject.toml` and `src/dafsa/__init__.py` both hard-code `"2.0"`); ship `py.typed` |
| Typing | `mypy --strict` on `src/`, enforced in CI |
| Lint | `ruff` replaces `flake8`; drop `.codacy.yml` |
| Docs | **MkDocs Material + mkdocstrings**. Delete `.readthedocs.yml` (it pins Python 3.5 and cannot build), `docs/conf.py`, `docs/Makefile`, and the `.rst` sources; author Markdown; publish to GitHub Pages from CI |
| `daciuk/` | **Removed** (896 KB of GPL-2 tarballs inside an MIT repository — an inconsistency, even though `MANIFEST.in` keeps them out of the sdist). Replaced by `docs/references.md` citing Daciuk's algorithms, his personal page, and the archive.org snapshot. Git history retains the files |
| CI | Upgrade `actions/checkout` and `actions/setup-python` v2 → v4; add coverage; add the benchmark job below; update branch triggers |
| Benchmarks | `benchmarks/run.py` produces the numbers quoted in this document, and `tests/test_performance.py` guards them in CI |
| README | Rewritten for the structure family; dead Travis badge removed; Zenodo DOI and citation kept; explicit 1.0 → 2.0 note |
| `manuscript/`, `paper.json` | **Untouched.** They remain the record of the 1.0 JOSS paper. 2.0 is documented in the changelog and docs, and gets a new Zenodo version DOI on release |

Decisions taken while implementing the above, recorded because they are worth reversing
deliberately rather than by accident:

- **`requirements.txt` deleted.** PEP 621 `dependencies` is now the single source, and a
  duplicate list drifts. Note that closed issue #4 explicitly asked for that file; the request
  it was serving — an explicit, discoverable dependency list — is met by `pyproject.toml` and
  `pip install -e ".[dev]"`.
- **`mkdocs` pinned to `<2`, `mkdocs-material` to `<10`.** MkDocs 2.0 removes the plugin
  system outright, which breaks both `mkdocs-material` and `mkdocstrings` with no migration
  path. Defensive, not permanent — revisit once that settles.
- **Doctests run in CI.** `--doctest-modules` over `src/`, so the examples in the docstrings
  are executed rather than merely plausible.
- **Tests ship in the sdist** (`recursive-include tests *.py`), so downstream packagers can
  run them at build time.

**One operational constraint worth knowing.** The credentials available to automated sessions
in this repository lack GitHub's `workflow` scope, so `.github/workflows/*` cannot be created,
modified, or deleted by a pushed commit — the push is rejected outright, and the GitHub
contents API returns 404 for the same reason. Workflow changes have to be made by a human, or
by a token that carries the scope. A corollary that has already bitten once: a workflow file
whose name is not exactly `*.yml` or `*.yaml` is silently ignored by Actions rather than
reported as an error, so a typo in the filename disables the workflow with no signal.

---

## 11. Testing strategy

Tests that check the implementation against something *other than itself*:

- **Language equivalence.** For random and corpus-derived inputs, the automaton's accepted set
  equals a reference Python `set`, checked in both directions (membership of every inserted
  sequence, rejection of sampled non-members).
- **Independent minimality verifier.** After `freeze()`, no two states share a signature —
  computed by a checker that does not use the builder's register.
- **Determinism and canonical form.** Per state, symbols are unique and sorted; state ids are
  dense; numbering is BFS-canonical.
- **Semiring laws.** Property-based (`hypothesis`) checks of associativity, commutativity where
  claimed, distributivity, and the identity/annihilator axioms for every built-in.
- **Weight preservation.** For every inserted `(sequence, weight)`, `weight(seq)` equals the
  assigned weight, and `total_weight()` equals the ⊕-fold of all assigned weights. This is the
  test 1.0 could not have passed (§2.3).
- **Rank round-trip.** `unrank(rank(seq)) == seq` for all accepted sequences; `len()` matches
  the reference set.
- **FST composition.** `compose(f, g)` agrees with brute-force relation composition on small
  random transducers.
- **Regression tests** reproducing #14, #15, #16, #17, and #18 from their reported inputs.
- **Depth test.** A single sequence of 50,000 tokens builds, freezes, exports, and is queried
  with no `RecursionError` (#10).

---

## 12. Work plan

One release. Ordered so that each milestone is independently testable and nothing is built on
an unverified layer.

| # | Milestone | Contents | Status |
|---|---|---|---|
| 0 | Infrastructure | `pyproject.toml` (3.10+, ruff, mypy, `py.typed`), CI refresh, MkDocs skeleton, remove `daciuk/` and the Sphinx/RTD files | **done** |
| 1 | Core | `Alphabet`, CSR `Automaton`, builder, `freeze()` with canonical renumbering, iterative traversal, `contains` | **done** |
| 2 | Semiring layer | protocol, six built-ins, law tests | **done** |
| 3 | Dictionary structures | `Trie`, `Dafsa` (register-based, weight-aware), minimality verifier | **done** |
| 4 | Counting layer | `s_count`, `len`, `rank`/`unrank`, lexicographic iteration, `total_weight`, `k_best`, plus the §7 query methods `match`/`paths`/`longest_prefix_of`/`starts_with` — closes #8 | **done** |
| 5 | Compaction | `CompactDafsa` — closes #18, #14 | **done** |
| 6 | Substring index | `SuffixAutomaton`, `Cdawg` | **done** |
| 7 | Transducers | `Fst`, `compose`, `project` | **done** |
| 8 | Export | DOT with UTF-8 and fonts, `MultiDiGraph`, JSON, GML/GraphML — closes #15, #16 | **done** |
| 9 | Weight pushing | `push()` for divisible semirings | **done** |
| 10 | CLI | rewrite against the new API — closes the remainder of #17 | **done** |
| 11 | Docs and benchmarks | MkDocs site, migration guide, quickstart, benchmark suite in CI | **done** |
| 12 | Release | `2.0.0`, Zenodo version DOI, close #7, #8, #10, #14, #15, #16, #17, #18 with pointers to the relevant sections here | |

Milestone 1 delivered the core at 100% branch coverage, checked against independent references
rather than against itself: a brute-force stack-based enumeration of the accepted language, and
`hypothesis` properties asserting that the accepted language equals the inserted set and that
membership agrees with a plain Python `set`. Issue #10's depth tests build a 50,000-state
automaton and then freeze, traverse, `deepcopy`, and `pickle` it, with a guard test asserting
the recursion limit has *not* been raised so the other four cannot pass vacuously.

Milestone 3 answers the benchmark §2.2 quotes. On a 96,393-sequence corpus (639,088 tokens):

| | time | states | transitions |
|---|---|---|---|
| `Trie` | 6.7s | 360,103 | 360,102 |
| `Dafsa` | 3.8s | 109,160 | 194,703 |

Against 1.0's "under 8 minutes" for 99,171 sequences, that is roughly two orders of magnitude,
and the register is where nearly all of it comes from. Note that the DAFSA builds *faster* than
the trie: minimization means fewer states are ever allocated, so sharing pays for itself during
construction rather than costing extra. Lookups run at ~290,000/s. Minimality at that scale was
confirmed by checking that all 109,160 state signatures are distinct, computed from the frozen
arrays with no involvement from the register that built them.

Milestone 4 folded in the four §7 query methods that no milestone had owned — `match`,
`paths`, `longest_prefix_of` and `starts_with`. That gap mattered: milestone 12 listed **#8**
as closed on release, but #8 asks `lookup()` to return a path and nothing in the plan built
`match()`. It is built now.

Three notes from that milestone:

- **`s_count` is computed lazily, not at freeze.** It is derived from the transitions, so it
  can never be passed in and be wrong, and a caller who only tests membership should not pay an
  O(transitions) pass. Measured on the 96k corpus: 0.57s on first use, then free.
- **Canonical breadth-first numbering is *not* a topological order.** A state can be discovered
  early through one predecessor and have another predecessor discovered later, so the dynamic
  programs cannot simply walk `reversed(range(num_states))`. `Dafsa.from_sequences(["a", "bc"])`
  is a two-transition counterexample, and a test pins it so the shortcut is never taken by
  someone who assumes otherwise.
- **`k_best` cannot prune yet, and says so.** With every transition weight `one` and the whole
  weight on the final state, no prefix carries information about how good its extensions might
  be, so the implementation examines every accepted sequence while holding only *k* — O(*n*
  log *k*) time, O(*k*) memory. Weight pushing (milestone 9) is what moves weight towards the
  front and makes a genuinely pruning best-first search possible. It is also refused outright
  for non-idempotent semirings, where `plus` accumulates rather than selects and "best" has no
  meaning.

Measured on the same 96k corpus: full ordered iteration in 0.82s; `rank`/`unrank` round-trip
over all 96,393 sequences in 3.9s; a prefix query returning 4 results in 0.11ms. `unrank` is
position-independent as intended — 26.0ms per thousand calls at position ~48,000 against
29.3ms at ~96,000, where enumeration would have made the latter tens of thousands of times
slower.

Milestone 8 was taken out of order, ahead of 6 and 7, because it depends on nothing they
produce and closes two more reported issues — the tracker goes from eight open to four with the
work already done.

It closed **#16** twice over. The reported half is that `to_graph()` returned an `nx.Graph`
while documenting a directed one. The unreported half is worse: 1.0 wrote every edge's label
into `graph[l][r]["label"]`, a single slot per *pair of states*, so two transitions joining the
same pair silently lost one. Measured on `DAFSA(["am", "an"])`, 1.0 produces an undirected graph
with **two** edges labelled `a` and `n` for an automaton with **three** transitions — the `m` is
simply gone. A `MultiDiGraph` built in one pass gives three edges labelled `a`, `m`, `n`.

**#15** — accented characters rendering as boxes — is a font-resolution failure, and the fix is
to stop leaving the choice to Graphviz: the emitter declares `charset="UTF-8"` and a
`fontname` defaulting to a face with coverage well past Latin-1. Verified by rendering the
reporter's own input to PDF and confirming the named font is the one embedded. One honest
limit: the original tofu could not be reproduced on the development machine, because fontconfig
there substitutes a covering font (DejaVu Serif) for Graphviz's unresolvable default, so the
symptom never appears. What is verified is that naming a font changes which font is embedded,
which is the mechanism the fix relies on.

Milestone 5 closed **#18** and **#14**, both of which were the same one-character defect:
1.0 tested `in_degree > 1` when selecting compaction candidates and so failed to exclude states
with *no* incoming edge. The root qualifies whenever it emits a single edge, and the next line
indexed `[0]` into its empty list of incoming edges. The predicate is `in_degree == 1`. Both
reporters' inputs are now regression tests, and `DAFSA(["tapas", "topos"]).condense()` — which
raised `IndexError` — produces exactly the `apa` and `opo` edges the reporter of #18 guessed at.

One bug of our own surfaced while testing it, worth recording because it is the failure mode
compaction invites: a prefix query whose prefix ends *inside* a compound label cannot be
answered by walking to a state, because there is no state at that position. `starts_with` now
descends the transition when the query is a proper prefix of its label and reports the label in
full, which is correct — every sequence through that transition consumes all of it.

Two implementation decisions in milestone 3 worth recording:

- **A sequence's weight sits on its final state; every transition weight is `one`.** There is
  no canonical way to distribute a weight along a path — deciding that is exactly what weight
  pushing does (milestone 9) — so construction does not invent one. `weight(seq)` is then the
  product of a chain of `one`s and the final weight, which is the weight that was inserted.
**The benchmark guard is a ratio, not a stopwatch.** A wall-clock threshold on shared CI
hardware either trips on a loaded runner or is set so loose it catches nothing. What is asserted
instead is that quadrupling the input does not multiply the work by more than ten: linear growth
is about four, and the quadratic scan 1.0 shipped would be about sixteen. Loose absolute budgets
sit alongside to catch a catastrophe. It also lives in `tests/`, not in a separate CI job, so it
runs under the existing `pytest` step — which incidentally avoids needing a workflow change,
since the credentials available to automated sessions here cannot touch `.github/workflows`
(§10).

Milestone 9 needed one addition to the core: **an initial weight**. Pushing moves weight
towards the front of a path, and the front of the *first* transition has nowhere further to go,
so without somewhere to put it the total weight of the language would change and `weight(seq)`
would stop meaning what it says. A single scalar on the automaton solves it, and the property
test is exact: every accepted sequence keeps the weight it had, to within the rounding division
introduces.

The claim §5 makes about pushing recovering state sharing is now checked rather than asserted.
`{"ax": 0.3, "bx": 0.7}` minimizes to five states weighted against three unweighted, because two
accepting states with different weights cannot merge however identical everything downstream is.
Pushing moves the difference onto the transitions leading in, and `minimize(push(a))` returns to
three with every weight intact.

Pushing also establishes what milestone 4 said `k_best` was missing: after it, the weights
leaving any state combine with its final weight to `one`, so a prefix's weight is informative
about its extensions. `k_best` still enumerates — making it prune is a separate change, and it is
not pretended otherwise.

- **`Automaton` is not generic over the weight type.** Weights are typed `Any`. Making the
  class `Automaton[W]` would thread a type parameter through every structure, the builder, and
  `freeze()`'s overloads for a gain confined to callers who mix semirings in one program. It is
  the clearest remaining typing wart and worth revisiting once the transducers exist, since
  composition is where mixing actually arises.

---

## 13. Migration: 1.0 → 2.0

A clean break. There is no compatibility shim; 1.0 code will not run unchanged.

| 1.0 | 2.0 |
|---|---|
| `DAFSA(seqs)` | `Dafsa.from_sequences(seqs)` |
| `DAFSA(seqs, minimize=False)` | `Trie.from_sequences(seqs)` |
| `DAFSA(seqs, weight=True)` | `Dafsa.from_sequences(seqs, semiring=COUNTING)`, or `from_weighted` for explicit weights |
| `DAFSA(seqs, condense=True)` | `Dafsa.from_sequences(seqs).compact()` |
| `DAFSA(seqs, delimiter=" ")` | `Dafsa.from_sequences(dafsa.tokenize(line, " ") for line in lines)` |
| `d.lookup(seq)` → `(node, cum_weight) \| None` | `seq in d` / `d.weight(seq)` / `d.match(seq)`. Note that 1.0's `cum_weight` has no 2.0 equivalent, because it was not a well-defined quantity (§2.3) |
| `d.count_nodes()` / `count_edges()` | `d.num_states` / `d.num_transitions` |
| `d.count_sequences()` | `len(d)` for distinct accepted sequences, `d.input_count` for the 1.0 behaviour (input length, duplicates included) |
| `d.nodes`, `d.lookup_nodes` | removed. Use `d.transitions(q)` read-only views |
| `DAFSANode`, `DAFSAEdge` | removed. States are integers; there are no per-state objects to hold |
| `d.to_graph()` (undirected) | `dafsa.export.to_networkx(d)` → `MultiDiGraph` |
| `d.to_dot()` | `dafsa.export.to_dot(d, ...)` |
| `d.write_figure(path, dpi)` | `dafsa.export.write_figure(d, path, dpi=...)` |
| `d.write_gml(path)` | `dafsa.export.write_gml(d, path)` |
| `d.condense()` (in place) | `d.compact()` (returns a new automaton) |
| `dafsa.utils.common_prefix_length`, `pairwise` | internal, not public |
| `print(d)` node dump format | changed; not a stable interface. Use `to_json` or `to_dot` for machine-readable output |

Users who need the old `print()` dump or `cum_weight` should pin `dafsa==1.0`, which remains
on PyPI and is the version the JOSS paper describes.

---

## 14. Risks and things to watch

1. **Weight-aware minimization shares fewer states** than 1.0's minimize-then-count approach,
   so weighted automata will be larger. This is the price of correct weights; `push()` and the
   benchmark suite should quantify it before release.
2. **Export-only persistence** will generate requests for loading, from anyone building a
   large dictionary once and querying it repeatedly. The CSR layout is deliberately chosen so
   that a binary format is additive when that day comes.
3. **networkx as a core dependency** may end up earning its place only in the export layer
   (§8). Decide at milestone 8 whether it moves to an optional extra.
4. **Suffix automata and transducers widen the maintenance surface** considerably relative to
   1.0's single class. Each needs its own independent verifier (§11), not just round-trip tests.
5. **Scale target.** The design aims at ~10⁶ sequences in pure Python with the CSR core. If
   real corpora push past that, the escape hatch is `from_sorted_symbols` streaming plus,
   eventually, an optional native backend — not a change to the public API.
