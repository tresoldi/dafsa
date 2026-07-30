# User Guide

`dafsa` stores **sets of sequences as automata**. You give it sequences; it gives you
back a graph in which every shared beginning and every shared ending is stored once,
and which answers membership, counting, ranking, prefix and weight queries by walking.

That problem shows up wherever data is discrete and sequential: word lists,
transcriptions, tag sequences, nucleotides. This guide teaches the concepts, helps you
pick a structure, and works through examples in several domains. Every code block on
this page is executed in the test suite, so the examples stay correct against the
installed version.

> New here? Read **Core concepts** and **Choosing a structure**, then jump to the
> worked example closest to your problem.

---

## Installation

```bash
pip install dafsa
```

There are no required dependencies. Two things are optional:

- `pip install "dafsa[graph]"` adds [networkx](https://networkx.org/), needed only by
  the three graph exports (`to_networkx`, `write_gml`, `write_graphml`).
- Writing image files needs [Graphviz](https://graphviz.org/) installed and its `dot`
  executable on the path. The DOT *source* is pure Python and always available.

Requires Python 3.10 or later.

---

## Core concepts

### A sequence is any `Sequence[Hashable]`

Tokens need only be hashable. A `str` is a sequence of characters, so by default
characters are the tokens — not because the library is about text, but because that is
what a `str` *is*.

```python
from dafsa import Dafsa

lexicon = Dafsa.from_sequences(["tap", "taps", "top", "tops"])

assert "taps" in lexicon
assert "ta" not in lexicon  # a prefix is not a member
assert len(lexicon) == 4
```

For anything else, say what the tokens are:

```python
from dafsa import Dafsa, tokenize

assert tokenize("the cat sat") == ("the", "cat", "sat")

phrases = Dafsa.from_sequences([tokenize("the cat sat"), tokenize("the dog sat")])
assert ("the", "cat", "sat") in phrases
```

Tokens may be phonemes, part-of-speech tags, feature bundles, integers, or a mix —
including types that cannot be compared with each other, which 1.0 rejected:

```python
from dafsa import Dafsa

mixed = Dafsa.from_sequences([("a", 1), (2, "b")])
assert len(mixed) == 2
```

Sequences are ordered by their *encoded symbols*, never by their tokens, which is why
incomparable types work. The order is stable for a given automaton and is what `rank`,
`unrank` and iteration report.

### Build, then freeze

Construction happens in a mutable builder; the result is an immutable `Automaton`.
Freezing is where the invariants are established: states are renumbered canonically in
breadth-first order, unreachable states are pruned, and determinism and acyclicity are
checked. Consequently state ids are dense, small, and reproducible.

```python
from dafsa import Dafsa

automaton = Dafsa.from_sequences(["tap", "taps", "top", "tops"])
assert list(automaton.states()) == list(range(automaton.num_states))
```

Underneath, an automaton is compressed sparse row adjacency over `array.array`: one
offset array, one symbol array, one target array, one flag byte per state. There is no
object per state and no object per transition, traversal is iterative, and deep
recursion is structurally impossible.

### Minimisation is what makes it small

A trie shares prefixes. Minimisation additionally merges states with the same right
language, so shared *endings* are stored once too.

```python
from dafsa import Dafsa, Trie

words = ["tap", "taps", "top", "tops"]

assert Trie.from_sequences(words).num_states == 8
assert Dafsa.from_sequences(words).num_states == 5
```

Minimising is not an extra pass tacked onto a trie: sequences are inserted in sorted
order and the suffix behind the insertion point is minimised as construction proceeds,
against a register of already-minimal states. Fewer states are ever allocated, so
building the minimal automaton is *cheaper* than building the trie.

### Weights live in a semiring

A weight is only useful if you can say what happens when weights are combined *along* a
path and *across* paths. That is exactly a semiring: a zero, a one, an addition and a
multiplication. `dafsa` makes the semiring explicit, and minimisation is aware of it —
so two states are merged only if they agree on weights as well as on structure.

```python
from dafsa import Dafsa
from dafsa.semirings import COUNTING

counted = Dafsa.from_sequences(["tip", "tip", "tap"], semiring=COUNTING)

assert counted.weight("tip") == 2
assert counted.weight("tap") == 1
assert counted.weight("nope") == 0  # the semiring's zero, not an error
assert len(counted) == 2  # distinct sequences
assert counted.total_weight() == 3  # insertions
```

The default semiring is boolean: plain membership, with no weights stored.

---

## Choosing a structure

Start from the question you are asking:

| Your situation | Structure | Note |
|----------------|-----------|------|
| Store a set of sequences and query it | `Dafsa` | the usual choice |
| The structure must remain a tree (one state per prefix) | `Trie` | states grow with total input length |
| The automaton is to be drawn, exported, or made smaller still | `CompactDafsa` | via `.compact()` |
| Ask what occurs *inside* one long sequence | `SuffixAutomaton` | linear time and space |
| The same, with forced chains collapsed | `Cdawg` | via `.compact()` |
| Map sequences to sequences, not merely accept them | `Fst` | may be ambiguous |

And from what you want the weights to mean:

| You want | Semiring | Weight of a path / of alternatives |
|----------|----------|-------------------------------------|
| Membership only | `BOOLEAN` (default) | and / or |
| Frequencies | `COUNTING` | × / + |
| Costs, shortest path | `TROPICAL` | + / min |
| Negative log probabilities | `LOG` | + / log-sum-exp |
| Probabilities | `PROBABILITY` | × / + |
| The single best derivation | `VITERBI` | × / max |

Any type satisfying the `Semiring` protocol works; the six above are built in and are
each checked against the semiring axioms by property-based tests.

---

## The structures

### `Trie` and `Dafsa`

Both take an iterable of sequences and freeze it. They differ only in whether
equivalent states are merged, and they answer every query identically.

```python
from dafsa import Dafsa, Trie

words = ["tapas", "tapes", "topos"]

trie = Trie.from_sequences(words)
dafsa = Dafsa.from_sequences(words)

assert all(w in trie and w in dafsa for w in words)
assert list(trie) == list(dafsa)
assert dafsa.num_states < trie.num_states
```

Supply weights with `from_weighted`, which takes `(sequence, weight)` pairs:

```python
from dafsa import Dafsa
from dafsa.semirings import TROPICAL

costs = Dafsa.from_weighted(
    [("tap", 2.0), ("taps", 0.5), ("top", 1.0)], semiring=TROPICAL
)

assert costs.weight("taps") == 0.5
assert costs.k_best(2) == [
    (("t", "a", "p", "s"), 0.5),
    (("t", "o", "p"), 1.0),
]
```

### `CompactDafsa`

Compaction collapses chains of states that every path is forced through — a state with
exactly one transition in, one out, and no acceptance of its own. The transition that
replaces the chain is labelled with several tokens at once.

```python
from dafsa import Dafsa

automaton = Dafsa.from_sequences(["tapas", "topos"])

assert automaton.num_states == 8
assert automaton.compact().num_states == 4
assert "tapas" in automaton.compact()
```

Nothing about the answers changes; only the size does. That is mostly what makes a
drawn automaton legible, and on a real lexicon it removes roughly two thirds of the
states.

### `SuffixAutomaton` and `Cdawg`

A suffix automaton indexes a *single* sequence and answers questions about what occurs
within it. It is built online in linear time and has at most 2*n*−1 states.

```python
from dafsa import SuffixAutomaton

index = SuffixAutomaton.from_sequence("banana")

assert index.contains_substring("nan")
assert "nan" not in index  # it occurs, but it is not a suffix
assert index.num_substrings() == 15
assert index.longest_common_subsequence_with("bananas") == tuple("banana")
```

The distinction in the second and third lines is deliberate: the automaton *accepts*
the suffixes of the sequence, while `contains_substring` asks only whether a walk
exists, ignoring acceptance. `Cdawg` is the same index with forced chains collapsed,
obtained with `.compact()`.

### `Fst`

A transducer relates sequences to sequences. Internally it is an ordinary automaton
over an alphabet of `(input, output)` pairs — pairs are hashable, so nothing special is
needed — with an `EPSILON` sentinel for "nothing on this side".

```python
from dafsa import Fst

translate = Fst.from_pairs([("cat", "chat"), ("dog", "chien")])

assert translate.apply("cat") == [tuple("chat")]
assert translate.apply("cow") == []  # not in the relation
```

`apply` returns a list because a transducer may be ambiguous — one input, several
analyses. Composition chains two relations into one:

```python
from dafsa import Fst, compose

analyse = Fst.from_pairs([("walked", "walk+PAST"), ("walks", "walk+PRES")])
tag = Fst.from_pairs([("walk+PAST", "V.PST"), ("walk+PRES", "V.PRS")])

assert compose(analyse, tag).apply("walked") == [tuple("V.PST")]
```

`project("input")` and `project("output")` return either side as a `Dafsa`.

---

## Querying

### Membership, weight, and the path taken

```python
from dafsa import Dafsa
from dafsa.semirings import COUNTING

lexicon = Dafsa.from_sequences(["tap", "tap", "taps", "top"], semiring=COUNTING)

assert "tap" in lexicon
assert lexicon.weight("tap") == 2

found = lexicon.match("taps")
assert found is not None
assert found.weight == 1
assert len(found.states) == 5  # the root, plus one per token
assert lexicon.match("nope") is None
```

`match` returns the states visited, the transitions taken and the accumulated weight —
which is what 1.0's `lookup()` was reached for, and did not correctly provide.

### Counting, ranking, ordered iteration

Suffix counts — how many accepted sequences leave each state — turn the automaton into
a minimal perfect hash over its own language. Every accepted sequence has a position,
and every position has a sequence.

```python
from dafsa import Dafsa

lexicon = Dafsa.from_sequences(["tap", "taps", "top", "tops"])

assert len(lexicon) == 4  # counted, not enumerated
assert list(lexicon) == [
    ("t", "a", "p"),
    ("t", "a", "p", "s"),
    ("t", "o", "p"),
    ("t", "o", "p", "s"),
]
assert lexicon.rank("top") == 2
assert lexicon.unrank(2) == ("t", "o", "p")
```

`unrank` descends by subtree size rather than counting through, so reaching the
millionth sequence costs no more than reaching the first. `len()` is likewise a lookup,
not a traversal, once the counts are computed.

### Prefix queries

Prefix queries cost the size of their answer, not the size of the automaton.

```python
from dafsa import Dafsa

lexicon = Dafsa.from_sequences(["tap", "taps", "top", "tops"])

assert list(lexicon.starts_with("ta")) == [
    ("t", "a", "p"),
    ("t", "a", "p", "s"),
]
assert lexicon.longest_prefix_of("topsy") == ("t", "o", "p", "s")
```

Both work on a compacted automaton too, including when the prefix ends part-way through
a multi-token label.

### Totals and best paths

```python
from dafsa import Dafsa
from dafsa.semirings import COUNTING, TROPICAL

counted = Dafsa.from_sequences(["a", "a", "b"], semiring=COUNTING)
assert counted.total_weight() == 3

costs = Dafsa.from_weighted([("a", 3.0), ("b", 1.0), ("c", 2.0)], semiring=TROPICAL)
assert [seq for seq, _ in costs.k_best(2)] == [("b",), ("c",)]
assert costs.total_weight() == 1.0  # min, in the tropical semiring
```

Weight pushing moves weight towards the initial state without changing what any
sequence weighs, which makes prefixes informative earlier:

```python
from dafsa import Dafsa
from dafsa.semirings import TROPICAL

costs = Dafsa.from_weighted([("ab", 3.0), ("ac", 5.0)], semiring=TROPICAL)
pushed = costs.push()

assert pushed.weight("ab") == costs.weight("ab")
assert pushed.weight("ac") == costs.weight("ac")
```

Pushing requires a divisible semiring; `BOOLEAN` and `COUNTING` are not, and say so.

---

## Exporting and drawing

```python
from dafsa import Dafsa, export

automaton = Dafsa.from_sequences(["tap", "taps", "top"]).compact()

dot = export.to_dot(automaton, scale_edges=False)
assert dot.startswith("digraph")

payload = export.to_json(automaton)
assert '"states"' in payload
```

`export.write_figure(automaton, "words.png")` renders through Graphviz — it needs `dot`
on the path — and accepts `dpi` and a format inferred from the suffix. The DOT emitter
declares a charset and a font with the coverage to draw accented and non-Latin tokens,
which 1.0 rendered as boxes.

With the `graph` extra installed, `export.to_networkx(automaton)` returns a
`MultiDiGraph` with one edge per transition, and `export.write_gml` /
`export.write_graphml` write those formats. There are no loaders: an export is for
inspection and interchange, not a persistence format.

---

## From the command line

```bash
dafsa words.txt                          # a summary
dafsa --words phrases.txt                # split lines on whitespace
dafsa --sep , codes.txt                  # split lines on a separator
dafsa -s counting words.txt              # with frequencies
dafsa --compact -t svg -o words.svg words.txt
dafsa -f suffix -t json -o index.json text.txt
```

`-f` selects the structure (`dafsa`, `trie`, `suffix`, `cdawg`), `-s` the semiring, `-t`
the output type. Tokenization is explicit and the two forms are mutually exclusive:
`--words` splits on whitespace, `--sep SEP` on a given separator, and neither means one
token per character. `dafsa --help` lists everything.

---

## Worked examples by domain

### Lexicography

A word list, stored once and indexed in place. The automaton is the dictionary *and*
its numbering: `rank` gives each word a stable integer, `unrank` inverts it, and no
side table is needed.

```python
from dafsa import Dafsa

words = ["ban", "band", "bandana", "bank", "banks", "bat", "bats"]
lexicon = Dafsa.from_sequences(words)

assert len(lexicon) == len(words)
assert [lexicon.unrank(lexicon.rank(w)) == tuple(w) for w in words] == [True] * 7
assert list(lexicon.starts_with("bank")) == [tuple("bank"), tuple("banks")]
assert lexicon.longest_prefix_of("bandanas") == tuple("bandana")
```

### Phonology

Multi-character segments must stay whole: `tʃ` is one phoneme, not two tokens. Pass
sequences of tokens rather than strings and the alphabet takes care of itself.

```python
from dafsa import Dafsa

forms = [
    ("tʃ", "a"),
    ("tʃ", "i"),
    ("k", "a"),
]
inventory = Dafsa.from_sequences(forms)

assert ("tʃ", "a") in inventory
assert "tʃa" not in inventory  # three characters is not two phonemes
assert sorted(inventory.alphabet) == ["a", "i", "k", "tʃ"]
```

Feature bundles work the same way, as long as they are hashable — use a `frozenset` or
a tuple rather than a `dict`.

### Historical linguistics

A sound change is a relation between forms, and relations compose. Two changes applied
in sequence are one transducer.

```python
from dafsa import Fst, compose

lenition = Fst.from_pairs([("apa", "aba"), ("ata", "ada")])
voicing = Fst.from_pairs([("aba", "ava"), ("ada", "aza")])

chain = compose(lenition, voicing)
assert chain.apply("apa") == [tuple("ava")]
assert chain.apply("ata") == [tuple("aza")]
```

`project("output")` on the composed transducer gives the set of resulting forms as a
plain `Dafsa`.

### Genomics

A substring index over a single sequence, in linear time and space. The question is not
"is this in my dictionary" but "does this occur anywhere in my text".

```python
from dafsa import SuffixAutomaton

genome = "ACGTACGTGACGT"
index = SuffixAutomaton.from_sequence(genome)

assert index.contains_substring("GTGA")
assert not index.contains_substring("GGGG")
assert index.longest_common_subsequence_with("TTACGTGA") == tuple("TACGTGA")
```

`num_substrings()` counts the distinct non-empty substrings without enumerating them.

### Anything discrete

Tags, integers, tuples, mixed types — a sequence is a `Sequence[Hashable]` and nothing
in the library assumes text.

```python
from dafsa import Dafsa

paths = [(1, 2, 3), (1, 2, 4), (1, 5)]
graph = Dafsa.from_sequences(paths)

assert (1, 2, 4) in graph
assert list(graph.starts_with((1, 2))) == [(1, 2, 3), (1, 2, 4)]
```

---

## Scaling and performance

Construction is register-based: an already-minimal state is found by dictionary lookup,
not by scanning every state seen so far. The 0.5 changelog records 99,171 sequences
taking "under 8 minutes"; a comparable corpus of 96,393 sequences now builds in under
four seconds, and the minimal automaton builds *faster* than the trie.

| Structure | States, at 96,393 sequences |
|-----------|-----------------------------|
| `Trie` | 360,103 |
| `Dafsa` | 109,160 |
| `CompactDafsa` | 39,864 |

`benchmarks/run.py` reproduces these numbers and `tests/test_performance.py` guards the
scaling. Two properties are worth stating plainly:

- **No recursion limit.** Flat arrays and iterative traversal make `RecursionError`
  structurally unreachable; the test suite exercises 50,000 states through build,
  freeze, traverse, deep-copy and pickle.
- **Position-independent access.** `unrank` costs the same at the end of the language
  as at the beginning, because it descends by subtree size.

---

## Migrating from 1.0

2.0 is a clean break. There is no compatibility shim, and 1.0 code will not run
unchanged. If you need the old behaviour, `dafsa==1.0` stays on PyPI and is the version
the JOSS paper describes.

### Why the break

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

### What maps to what

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

### Things that changed meaning

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

### Things that no longer fail

| Was | Now |
|---|---|
| `condense()` raising `IndexError` ([#18](https://github.com/tresoldi/dafsa/issues/18), [#14](https://github.com/tresoldi/dafsa/issues/14)) | `compact()`, tested on both reporters' inputs |
| `to_graph()` undirected, parallel edge labels lost ([#16](https://github.com/tresoldi/dafsa/issues/16)) | `to_networkx()` returns a `MultiDiGraph`, one edge per transition |
| Accented characters drawn as boxes ([#15](https://github.com/tresoldi/dafsa/issues/15)) | the DOT emitter declares `charset` and a font with coverage |
| `RecursionError` on long sequences ([#10](https://github.com/tresoldi/dafsa/issues/10)) | flat arrays, iterative traversal; tested at 50,000 states |
| `TypeError` on mixed token types | sequences are sorted as encoded symbols, never as tokens |
| `ZeroDivisionError` in `to_dot()` with `weight=False` | scaling is opt-in and guarded |

---

## References

The algorithms `dafsa` implements, and where to read about them.

### Minimal acyclic DFA construction

The incremental construction used by `Trie` and `Dafsa` — insert sorted sequences,
minimize the suffix behind you, keep a register of already-minimized states — is
Daciuk's:

- Daciuk, Jan; Mihov, Stoyan; Watson, Bruce W.; Watson, Richard E. (2000).
  "Incremental Construction of Minimal Acyclic Finite-State Automata."
  *Computational Linguistics* 26(1): 3–16.
- Daciuk, Jan (1998). *Incremental Construction of Finite-State Automata and
  Transducers, and their Use in the Natural Language Processing.* PhD thesis, Technical
  University of Gdańsk.
- Ciura, Marcin G.; Deorowicz, Sebastian (2001). "How to squeeze a lexicon."
  *Software: Practice and Experience* 31(11): 1077–1090.

`dafsa` 1.0 was based on Steve Hanov's public-domain Python sketch of the same
algorithm:

- Hanov, Steve (2011). "Succinct Data Structures: Cramming 80,000 words into a
  Javascript file." <http://stevehanov.ca/blog/?id=115>

Jan Daciuk published C and C++ reference implementations (`fsa`, `adfa`, `fadd`,
`ccip`, `utr`, `minim`), originally at a Gdańsk University of Technology address that
is no longer reachable; the [archive.org
snapshot](https://web.archive.org/web/20160531133017/http://galaxy.eti.pg.gda.pl/katedry/kiw/pracownicy/Jan.Daciuk/personal/minim.html)
preserves the page but not the archives, and Daciuk's personal page is at
<http://www.jandaciuk.pl/>. Copies of those tarballs were vendored under `daciuk/` from
version 0.5 until the 2.0 rewrite, when they were removed: they are GPL-2 licensed
while this project is MIT, and 896 KB of third-party C source is not something a Python
library should carry. They remain in the git history:

```bash
git log --all --oneline -- daciuk/            # find a revision that still has them
git show <revision>:daciuk/fsa_0.51.tar.gz > fsa_0.51.tar.gz
```

### Suffix automata and CDAWGs

`SuffixAutomaton` and `Cdawg` index every substring of a sequence, which is a different
problem from storing a dictionary of whole sequences:

- Blumer, Anselm; Blumer, Janet; Haussler, David; Ehrenfeucht, Andrzej; Chen, M. T.;
  Seiferas, Joel (1985). "The smallest automaton recognizing the subwords of a text."
  *Theoretical Computer Science* 40: 31–55.
- Blumer, Anselm; Blumer, Janet; Haussler, David; McConnell, Ross; Ehrenfeucht, Andrzej
  (1987). "Complete inverted files for efficient text retrieval and analysis."
  *Journal of the ACM* 34(3): 578–595.
- Inenaga, Shunsuke; Hoshino, Hiromasa; Shinohara, Ayumi; Takeda, Masayuki; Arikawa,
  Setsuo; Mauri, Giancarlo; Pavesi, Giulio (2005). "On-line construction of compact
  directed acyclic word graphs." *Discrete Applied Mathematics* 146(2): 156–179.

### Weighted automata and semirings

The semiring layer, weight-aware minimization, weight pushing, and transducer
composition follow the weighted finite-state transducer literature:

- Mohri, Mehryar (1997). "Finite-State Transducers in Language and Speech Processing."
  *Computational Linguistics* 23(2): 269–311.
- Mohri, Mehryar (2009). "Weighted Automata Algorithms." In *Handbook of Weighted
  Automata*, edited by Manfred Droste, Werner Kuich, and Heiko Vogler, 213–254.
  Springer.
- Mohri, Mehryar; Pereira, Fernando; Riley, Michael (2002). "Weighted finite-state
  transducers in speech recognition." *Computer Speech & Language* 16(1): 69–88.
- Allauzen, Cyril; Riley, Michael; Schalkwyk, Johan; Skut, Wojciech; Mohri, Mehryar
  (2007). "OpenFst: A General and Efficient Weighted Finite-State Transducer Library."
  In *Implementation and Application of Automata (CIAA 2007)*, 11–23. Springer.

### This library

- Tresoldi, Tiago (2020). *DAFSA, a library for computing Deterministic Acyclic Finite
  State Automata.* Version 1.0. Jena.
  DOI: [10.5281/zenodo.3668870](https://doi.org/10.5281/zenodo.3668870)
- Tresoldi, Tiago (2020). "DAFSA: a Python library for Deterministic Acyclic Finite
  State Automata." Submitted to the *Journal of Open Source Software*;
  [review thread](https://joss.theoj.org/papers/10d826c5b26e5222beb1b3780d606725). The
  manuscript source is kept in `manuscript/` in this repository.

---

## Next steps

- The [API Reference](reference.md) is generated from the docstrings and always matches
  the installed code.
- [`ARCHITECTURE.md`](https://github.com/tresoldi/dafsa/blob/master/ARCHITECTURE.md)
  explains how the library is put together and why, and records the decisions taken.
- [`CHANGELOG.md`](https://github.com/tresoldi/dafsa/blob/master/CHANGELOG.md) records
  what changed between versions.
