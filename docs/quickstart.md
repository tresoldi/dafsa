# Quickstart

## Install

```bash
pip install dafsa
```

Writing image files also needs [Graphviz](https://graphviz.org/) and its `dot` executable on the
path. Everything else, including the DOT source itself, is pure Python.

## A set of sequences

```python
from dafsa import Dafsa

lexicon = Dafsa.from_sequences(["tap", "taps", "top", "tops"])

"taps" in lexicon        # True
"ta" in lexicon          # False — a prefix is not a member
len(lexicon)             # 4
```

The shared `ps` ending is stored once. A [`Trie`](api.md#dafsa.structures.Trie) keeps the two
copies apart, which is the comparison the structure exists to make:

```python
from dafsa import Trie

Dafsa.from_sequences(["tap", "taps", "top", "tops"]).num_states   # 5
Trie.from_sequences(["tap", "taps", "top", "tops"]).num_states    # 8
```

## Tokens are whatever you say they are

A `str` is a sequence of characters, so by default characters are the tokens. For anything
else, say so:

```python
from dafsa import Dafsa, tokenize

tokenize("the cat sat")            # ('the', 'cat', 'sat')

phrases = Dafsa.from_sequences([tokenize("the cat sat"), tokenize("the dog sat")])
("the", "cat", "sat") in phrases   # True
```

Tokens need only be hashable. They may be phonemes, part-of-speech tags, feature bundles,
integers, or a mix — including types that cannot be compared with each other:

```python
Dafsa.from_sequences([("a", 1), (2, "b")])   # fine
```

## Weights that mean something

Weights belong to a [semiring](api.md#dafsa.semirings), which is what makes them compose. The
default is boolean — plain membership, no weights stored. Counting gives you frequencies:

```python
from dafsa import Dafsa
from dafsa.semirings import COUNTING

counted = Dafsa.from_sequences(["tip", "tip", "tap"], semiring=COUNTING)

counted.weight("tip")        # 2
counted.weight("tap")        # 1
counted.weight("nope")       # 0 — the semiring's zero, not an error
len(counted)                 # 2 distinct sequences
counted.total_weight()       # 3 insertions
```

Or supply the weights yourself:

```python
from dafsa.semirings import TROPICAL

costs = Dafsa.from_weighted(
    [("tap", 2.0), ("taps", 0.5), ("top", 1.0)], semiring=TROPICAL
)

costs.weight("taps")   # 0.5
costs.k_best(2)        # [(('t','a','p','s'), 0.5), (('t','o','p'), 1.0)]
```

## An index, not just a set

Suffix counts make the automaton a minimal perfect hash over its own language: every accepted
sequence has a position, and every position has a sequence.

```python
lexicon = Dafsa.from_sequences(["tap", "taps", "top", "tops"])

list(lexicon)              # in order: tap, taps, top, tops
lexicon.rank("top")        # 2
lexicon.unrank(2)          # ('t', 'o', 'p')
```

`unrank` descends by subtree size rather than counting through, so reaching the millionth
sequence costs no more than reaching the first.

Prefix queries cost the size of their answer:

```python
list(lexicon.starts_with("ta"))   # [('t','a','p'), ('t','a','p','s')]
lexicon.longest_prefix_of("topsy")  # ('t','o','p','s')
```

## Searching inside one sequence

A [`SuffixAutomaton`](api.md#dafsa.suffix.SuffixAutomaton) indexes a single sequence and
answers questions about what occurs *within* it:

```python
from dafsa import SuffixAutomaton

index = SuffixAutomaton.from_sequence("banana")

index.contains_substring("nan")     # True
"nan" in index                      # False — it occurs, but is not a suffix
index.num_substrings()              # 15 distinct non-empty substrings
index.longest_common_subsequence_with("bananas")   # ('b','a','n','a','n','a')
```

## Relating one sequence to another

A [transducer](api.md#dafsa.fst.Fst) maps sequences to sequences:

```python
from dafsa import Fst, compose

translate = Fst.from_pairs([("cat", "chat"), ("dog", "chien")])
translate.apply("cat")     # [('c','h','a','t')]
translate.apply("cow")     # [] — not in the relation

analyse = Fst.from_pairs([("walked", "walk+PAST"), ("walks", "walk+PRES")])
tag = Fst.from_pairs([("walk+PAST", "V.PST"), ("walk+PRES", "V.PRS")])

compose(analyse, tag).apply("walked")   # [('V','.','P','S','T')]
```

A transducer may be ambiguous — one input, several analyses — which is why `apply` returns a
list.

## Making it smaller, and drawing it

Compaction collapses chains of states that every path is forced through:

```python
automaton = Dafsa.from_sequences(["tapas", "topos"])
automaton.num_states              # 8
automaton.compact().num_states    # 4
```

Everything answers the same afterwards; only the size changes. That is mostly what makes a
drawn automaton legible:

```python
from dafsa import export

export.write_figure(automaton.compact(), "words.png", scale_edges=True)
print(export.to_dot(automaton))
graph = export.to_networkx(automaton)   # a MultiDiGraph
```

## From the command line

```bash
dafsa words.txt                          # a summary
dafsa --words phrases.txt                # split lines on whitespace
dafsa -s counting words.txt              # with frequencies
dafsa --compact -t svg -o words.svg words.txt
dafsa -f suffix -t json -o index.json text.txt
```

`dafsa --help` lists everything.
