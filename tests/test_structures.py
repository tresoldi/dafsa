"""Tests for the dictionary structures.

The obligations these check, in order of how much they matter:

1. The accepted language is exactly the inserted set.
2. A :class:`~dafsa.Dafsa` is genuinely minimal, checked against weighted right
   languages rather than against the register that built it.
3. ``weight(seq)`` returns what ``seq`` was inserted with — the property 1.0 could
   not satisfy, and the reason the semiring layer exists.
"""

from __future__ import annotations

import math
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from dafsa import Dafsa, Trie, tokenize
from dafsa.automaton import ROOT
from dafsa.semirings import (
    BOOLEAN,
    COUNTING,
    LOG,
    PROBABILITY,
    TROPICAL,
    Semiring,
)
from helpers import (
    accepted_sequences,
    assert_deterministic_and_dense,
    assert_minimal,
    build_trie,
    csr,
)

WORDS = ["tap", "taps", "top", "tops"]

STRUCTURES = pytest.mark.parametrize("structure", [Trie, Dafsa], ids=["trie", "dafsa"])

WORD_LISTS = st.lists(st.text(alphabet="abc", max_size=5), max_size=10)


# -- language --------------------------------------------------------------


@STRUCTURES
def test_accepts_exactly_the_inserted_sequences(structure: type[Any]) -> None:
    automaton = structure.from_sequences(WORDS)

    assert accepted_sequences(automaton) == {tuple(word) for word in WORDS}


@STRUCTURES
@settings(deadline=None, max_examples=200)
@given(words=WORD_LISTS)
def test_language_is_the_input_set(structure: type[Any], words: list[str]) -> None:
    automaton = structure.from_sequences(words)

    assert accepted_sequences(automaton) == {tuple(word) for word in words}


@settings(deadline=None, max_examples=200)
@given(words=WORD_LISTS)
def test_trie_and_dafsa_accept_the_same_language(words: list[str]) -> None:
    """Minimization must change the size and nothing else."""
    assert accepted_sequences(Trie.from_sequences(words)) == accepted_sequences(
        Dafsa.from_sequences(words)
    )


@settings(deadline=None, max_examples=100)
@given(words=WORD_LISTS)
def test_trie_agrees_with_the_naive_reference_trie(words: list[str]) -> None:
    """``build_trie`` scans linearly and shares nothing with the sorted-input loop."""
    assert accepted_sequences(Trie.from_sequences(words)) == accepted_sequences(
        build_trie(words)
    )


@STRUCTURES
@settings(deadline=None, max_examples=100)
@given(words=WORD_LISTS, probe=st.text(alphabet="abc", max_size=6))
def test_membership_agrees_with_a_reference_set(
    structure: type[Any], words: list[str], probe: str
) -> None:
    automaton = structure.from_sequences(words)

    assert automaton.accepts(probe) == (probe in set(words))


# -- minimality ------------------------------------------------------------


def test_the_canonical_example_matches_the_literature() -> None:
    """``{tap, taps, top, tops}`` minimizes to five states and five transitions.

    This is the figure the README and the JOSS paper are built around.
    """
    automaton = Dafsa.from_sequences(WORDS)

    assert (automaton.num_states, automaton.num_transitions) == (5, 5)
    assert_minimal(automaton)


def test_a_trie_is_larger_than_the_minimal_automaton() -> None:
    """The whole point: the shared ``ps`` suffix is stored once, not twice."""
    trie = Trie.from_sequences(WORDS)
    dafsa = Dafsa.from_sequences(WORDS)

    assert (trie.num_states, trie.num_transitions) == (8, 7)
    assert dafsa.num_states < trie.num_states


@settings(deadline=None, max_examples=300)
@given(words=WORD_LISTS)
def test_dafsa_is_minimal(words: list[str]) -> None:
    assert_minimal(Dafsa.from_sequences(words))


@settings(deadline=None, max_examples=100)
@given(
    words=st.lists(st.text(alphabet="ab", min_size=1, max_size=6), max_size=12),
)
def test_dafsa_is_minimal_on_longer_words(words: list[str]) -> None:
    assert_minimal(Dafsa.from_sequences(words))


@settings(deadline=None, max_examples=100)
@given(words=WORD_LISTS)
def test_dafsa_never_has_more_states_than_the_trie(words: list[str]) -> None:
    assert (
        Dafsa.from_sequences(words).num_states <= Trie.from_sequences(words).num_states
    )


def test_suffix_sharing_is_what_shrinks_the_automaton() -> None:
    """Distinct prefixes, one shared suffix: the trie grows, the DAFSA does not."""
    words = [f"{prefix}ing" for prefix in ("walk", "talk", "jump", "sing")]
    trie = Trie.from_sequences(words)
    dafsa = Dafsa.from_sequences(words)

    assert trie.num_states == 4 * len("walking") + 1
    assert dafsa.num_states < trie.num_states
    assert_minimal(dafsa)


# -- structure -------------------------------------------------------------


@STRUCTURES
@settings(deadline=None, max_examples=100)
@given(words=WORD_LISTS)
def test_structural_invariants_hold(structure: type[Any], words: list[str]) -> None:
    assert_deterministic_and_dense(structure.from_sequences(words))


@STRUCTURES
@settings(deadline=None, max_examples=100)
@given(words=WORD_LISTS, seed=st.integers())
def test_input_order_does_not_affect_the_result(
    structure: type[Any], words: list[str], seed: int
) -> None:
    """Sorting happens internally, so the caller's order cannot matter."""
    shuffled = sorted(words, key=lambda word: hash((word, seed)))

    assert csr(structure.from_sequences(words)) == csr(
        structure.from_sequences(shuffled)
    )


@STRUCTURES
def test_empty_input_gives_a_single_rejecting_state(structure: type[Any]) -> None:
    automaton = structure.from_sequences([])

    assert automaton.num_states == 1
    assert automaton.num_transitions == 0
    assert not automaton.is_final(ROOT)
    assert "" not in automaton


@STRUCTURES
def test_the_empty_sequence_makes_the_root_accepting(structure: type[Any]) -> None:
    automaton = structure.from_sequences(["", "a"])

    assert automaton.is_final(ROOT)
    assert "" in automaton
    assert "a" in automaton


@STRUCTURES
def test_duplicate_sequences_are_accepted_once(structure: type[Any]) -> None:
    automaton = structure.from_sequences(["ab", "ab", "ab"])

    assert accepted_sequences(automaton) == {("a", "b")}


@STRUCTURES
def test_multi_character_tokens(structure: type[Any]) -> None:
    """Issue #17: tokens are whatever the caller says they are."""
    sequences = [tokenize("the cat sat"), tokenize("the dog sat")]
    automaton = structure.from_sequences(sequences)

    assert ("the", "cat", "sat") in automaton
    assert ("the", "cat") not in automaton
    assert set(automaton.alphabet.tokens) == {"cat", "dog", "sat", "the"}


@STRUCTURES
def test_mutually_incomparable_tokens(structure: type[Any]) -> None:
    """1.0 sorted the caller's sequences, so this raised ``TypeError``."""
    sequences: list[tuple[object, ...]] = [("a", 1), (2, "b"), ("a", 2)]
    automaton = structure.from_sequences(sequences)

    assert accepted_sequences(automaton) == {("a", 1), (2, "b"), ("a", 2)}


@STRUCTURES
def test_a_deep_sequence_builds_and_is_queried(structure: type[Any]) -> None:
    """Issue #10, through the public construction path."""
    depth = 20_000
    automaton = structure.from_sequences(["a" * depth])

    assert automaton.num_states == depth + 1
    assert automaton.accepts("a" * depth)


def test_a_deep_dafsa_shares_its_whole_tail() -> None:
    """Every state of ``a**n`` has a distinct right language, so nothing merges."""
    automaton = Dafsa.from_sequences(["a" * 500])

    assert automaton.num_states == 501
    assert_minimal(automaton)


def test_repr_names_the_structure() -> None:
    assert repr(Dafsa.from_sequences(WORDS)).startswith("<Dafsa states=5")
    assert repr(Trie.from_sequences(WORDS)).startswith("<Trie states=8")


# -- weights ---------------------------------------------------------------


def test_unweighted_structures_store_no_weight_arrays() -> None:
    """A plain acceptor must not pay for weights it does not use."""
    automaton = Dafsa.from_sequences(WORDS)

    assert not automaton.is_weighted
    assert automaton._transition_weights is None
    assert automaton._final_weights is None
    assert automaton.weight("tap") is True
    assert automaton.weight("nope") is False


def test_counting_all_ones_still_stores_nothing() -> None:
    """Every count is ``one``, so the arrays would carry no information."""
    automaton = Dafsa.from_sequences(["ab", "cd"], semiring=COUNTING)

    assert not automaton.is_weighted
    assert automaton.weight("ab") == 1


def test_counting_records_multiplicity() -> None:
    automaton = Dafsa.from_sequences(["tip", "tip", "tap"], semiring=COUNTING)

    assert automaton.is_weighted
    assert automaton.weight("tip") == 2
    assert automaton.weight("tap") == 1
    assert automaton.weight("nope") == COUNTING.zero


def test_the_one_point_zero_weight_bug_is_gone() -> None:
    """The regression that motivated the semiring layer.

    1.0 collected counters by re-walking sequences over the minimized graph, so an
    edge weight was the total frequency of everything crossing it and
    ``lookup("tip")`` returned the path-sum ``3 + 2 + 2 == 7`` for a sequence
    inserted exactly once.
    """
    automaton = Dafsa.from_sequences(["dib", "tip", "tips", "top"], semiring=COUNTING)

    assert automaton.weight("tip") == 1
    assert automaton.weight("tip") != 7
    for word in ("dib", "tips", "top"):
        assert automaton.weight(word) == 1


@pytest.mark.parametrize(
    ("semiring", "weights"),
    [
        (COUNTING, [3, 1, 4]),
        (TROPICAL, [1.5, 0.25, 2.0]),
        (PROBABILITY, [0.5, 0.25, 0.125]),
        (LOG, [0.5, 1.5, 2.5]),
    ],
    ids=["counting", "tropical", "probability", "log"],
)
def test_weights_survive_construction(
    semiring: Semiring[Any], weights: list[Any]
) -> None:
    """The core promise: what goes in comes back out."""
    words = ["tap", "taps", "top"]
    automaton = Dafsa.from_weighted(zip(words, weights, strict=True), semiring=semiring)

    for word, weight in zip(words, weights, strict=True):
        assert math.isclose(automaton.weight(word), weight, rel_tol=1e-12)


@STRUCTURES
@settings(deadline=None, max_examples=200)
@given(
    pairs=st.lists(
        st.tuples(st.text(alphabet="abc", min_size=1, max_size=4), st.integers(1, 50)),
        max_size=10,
    )
)
def test_weight_equals_the_accumulated_input(
    structure: type[Any], pairs: list[tuple[str, int]]
) -> None:
    """Repeated sequences accumulate with ``plus``; everything else is untouched."""
    automaton = structure.from_weighted(pairs, semiring=COUNTING)

    expected: dict[str, int] = {}
    for word, weight in pairs:
        expected[word] = expected.get(word, 0) + weight

    for word, weight in expected.items():
        assert automaton.weight(word) == weight


@settings(deadline=None, max_examples=200)
@given(
    pairs=st.lists(
        st.tuples(st.text(alphabet="ab", min_size=1, max_size=4), st.integers(1, 20)),
        max_size=8,
    )
)
def test_weighted_dafsa_is_still_minimal(pairs: list[tuple[str, int]]) -> None:
    """Weight-aware minimization must be minimal *for the weighted language*."""
    assert_minimal(Dafsa.from_weighted(pairs, semiring=COUNTING))


def test_weights_prevent_sharing_that_would_lose_them() -> None:
    """Two sequences with the same suffix but different weights cannot merge.

    Unweighted, ``ax`` and ``bx`` share everything after the first token. Give
    them different weights and the accepting states must stay distinct, or one of
    the weights would be lost.
    """
    unweighted = Dafsa.from_sequences(["ax", "bx"])
    weighted = Dafsa.from_weighted([("ax", 1), ("bx", 2)], semiring=COUNTING)

    assert weighted.num_states > unweighted.num_states
    assert weighted.weight("ax") == 1
    assert weighted.weight("bx") == 2
    assert_minimal(weighted)


def test_equal_weights_are_shared_again() -> None:
    """The converse: identical weights must not block sharing."""
    same = Dafsa.from_weighted([("ax", 7), ("bx", 7)], semiring=COUNTING)

    assert same.num_states == Dafsa.from_sequences(["ax", "bx"]).num_states
    assert same.weight("ax") == same.weight("bx") == 7


def test_boolean_weights_collapse_duplicates() -> None:
    automaton = Dafsa.from_sequences(["ab", "ab"], semiring=BOOLEAN)

    assert automaton.weight("ab") is True
    assert not automaton.is_weighted


def test_probability_weights_of_a_shared_suffix() -> None:
    automaton = Dafsa.from_weighted(
        [("walk", 0.5), ("talk", 0.25)], semiring=PROBABILITY
    )

    assert math.isclose(automaton.weight("walk"), 0.5)
    assert math.isclose(automaton.weight("talk"), 0.25)
    assert automaton.weight("balk") == PROBABILITY.zero


def test_transitions_carry_their_weight() -> None:
    """Construction puts the sequence's weight on the final state, not the path.

    There is no canonical way to spread a weight along a path — that is what
    weight pushing is for — so every transition weight is ``one`` and the whole
    weight sits where the sequence ends.
    """
    automaton = Dafsa.from_weighted([("ab", 5)], semiring=COUNTING)

    for state in automaton.states():
        for transition in automaton.transitions(state):
            assert transition.weight == COUNTING.one

    ending = automaton.walk(automaton.alphabet.encode("ab"))
    assert ending is not None
    assert automaton.final_weight(ending) == 5


def test_weight_of_a_sequence_whose_path_breaks_is_zero() -> None:
    """All tokens known, but no path: distinct from the unknown-token case."""
    automaton = Dafsa.from_weighted([("ab", 5)], semiring=COUNTING)

    assert automaton.weight("aa") == COUNTING.zero
    assert automaton.weight("ba") == COUNTING.zero


def test_weight_of_a_proper_prefix_is_zero() -> None:
    """The path exists but does not end at an accepting state."""
    automaton = Dafsa.from_weighted([("abc", 5)], semiring=COUNTING)

    assert automaton.weight("ab") == COUNTING.zero
    assert automaton.weight("abc") == 5


def test_final_weight_of_a_non_accepting_state_is_zero() -> None:
    automaton = Dafsa.from_weighted([("ab", 5)], semiring=COUNTING)

    assert automaton.final_weight(ROOT) == COUNTING.zero


def test_semiring_is_carried_on_the_automaton() -> None:
    assert Dafsa.from_sequences(WORDS).semiring is BOOLEAN
    assert Dafsa.from_sequences(WORDS, semiring=TROPICAL).semiring is TROPICAL


def test_tropical_weights_pick_the_cheapest_analysis() -> None:
    automaton = Dafsa.from_weighted(
        [("ab", 2.0), ("ab", 5.0), ("cd", 1.0)], semiring=TROPICAL
    )

    # `plus` is `min`, so the repeated sequence keeps its cheaper weight.
    assert automaton.weight("ab") == 2.0
    assert automaton.weight("cd") == 1.0
    assert automaton.weight("zz") == math.inf


# -- tokenize --------------------------------------------------------------


def test_tokenize_splits_on_whitespace_by_default() -> None:
    assert tokenize("the cat sat") == ("the", "cat", "sat")
    assert tokenize("  spaced   out  ") == ("spaced", "out")


def test_tokenize_accepts_an_explicit_separator() -> None:
    assert tokenize("a-b-c", "-") == ("a", "b", "c")
    assert tokenize("a__b", "_") == ("a", "", "b")


def test_issue_17_scenario() -> None:
    """The reporter's input, now doing what they expected.

    ``DAFSA(["a b c", "a ab ac", "a ab ab c"], delimiter=" ")`` in 1.0 treated the
    spaces as tokens and produced a ten-state automaton over a six-token alphabet.
    """
    lines = ["a b c", "a ab ac", "a ab ab c"]
    automaton = Dafsa.from_sequences([tokenize(line) for line in lines])

    assert set(automaton.alphabet.tokens) == {"a", "ab", "ac", "b", "c"}
    assert " " not in automaton.alphabet
    for line in lines:
        assert tokenize(line) in automaton
    assert ("a", "b") not in automaton
