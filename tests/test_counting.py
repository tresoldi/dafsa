"""Tests for the counting layer: sizes, ordering, ranking, totals, and paths.

Each obligation is checked against an independent reference rather than against
the implementation's own view:

* ``len()`` against a Python ``set`` of the inserted sequences.
* Iteration order against ``sorted()`` over the same set.
* ``rank``/``unrank`` against the enumerated list, and against each other as
  mutual inverses over the whole language.
* ``total_weight()`` against folding the inserted weights directly.
"""

from __future__ import annotations

import math
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from dafsa import Dafsa, Trie
from dafsa._algorithms import iterate, topological_order
from dafsa.automaton import ROOT, Match
from dafsa.semirings import BOOLEAN, COUNTING, PROBABILITY, TROPICAL, VITERBI
from helpers import accepted_sequences
from helpers import topological_order as reference_topological_order

WORDS = ["tap", "taps", "top", "tops", "dibs"]

STRUCTURES = pytest.mark.parametrize("structure", [Trie, Dafsa], ids=["trie", "dafsa"])

WORD_LISTS = st.lists(st.text(alphabet="abc", max_size=5), max_size=10)


# -- size ------------------------------------------------------------------


@STRUCTURES
def test_len_counts_distinct_sequences(structure: type[Any]) -> None:
    """The size of the language, not of the input.

    1.0's ``count_sequences()`` returned the length of the input list, duplicates
    included, while describing a structure that is a set.
    """
    automaton = structure.from_sequences(["ab", "ab", "cd"])

    assert len(automaton) == 2


@STRUCTURES
@settings(deadline=None, max_examples=200)
@given(words=WORD_LISTS)
def test_len_matches_a_reference_set(structure: type[Any], words: list[str]) -> None:
    assert len(structure.from_sequences(words)) == len(set(words))


@STRUCTURES
def test_an_empty_language_is_falsy(structure: type[Any]) -> None:
    """``__len__`` drives truthiness, and an automaton accepting nothing is empty."""
    empty = structure.from_sequences([])
    assert len(empty) == 0
    assert not empty

    assert structure.from_sequences([""])


def test_suffix_count_is_the_size_of_a_state_right_language() -> None:
    automaton = Dafsa.from_sequences(WORDS)

    assert automaton.suffix_count(ROOT) == len(automaton) == 5
    for state in automaton.states():
        enumerated = len(list(iterate(automaton, state)))
        assert automaton.suffix_count(state) == enumerated


def cached_counts(automaton: Any) -> Any:
    """Read the count cache without mypy narrowing it for the rest of the test."""
    return automaton._counts


def test_counts_are_computed_once_and_cached() -> None:
    automaton = Dafsa.from_sequences(WORDS)

    assert cached_counts(automaton) is None
    assert len(automaton) == 5

    first = cached_counts(automaton)
    assert first is not None
    assert len(automaton) == 5
    assert cached_counts(automaton) is first


# -- ordering --------------------------------------------------------------


@STRUCTURES
def test_iteration_is_in_order(structure: type[Any]) -> None:
    automaton = structure.from_sequences(WORDS)

    assert [tuple(word) for word in sorted(WORDS)] == list(automaton)


@STRUCTURES
@settings(deadline=None, max_examples=200)
@given(words=WORD_LISTS)
def test_iteration_matches_a_sorted_reference(
    structure: type[Any], words: list[str]
) -> None:
    automaton = structure.from_sequences(words)

    assert list(automaton) == sorted(tuple(word) for word in set(words))


@settings(deadline=None, max_examples=100)
@given(words=WORD_LISTS)
def test_iteration_agrees_with_brute_force_enumeration(words: list[str]) -> None:
    """``accepted_sequences`` walks with its own stack and returns an unordered set."""
    automaton = Dafsa.from_sequences(words)

    assert set(automaton) == accepted_sequences(automaton)


def test_iteration_is_lazy() -> None:
    """Taking one sequence must not enumerate the rest."""
    automaton = Dafsa.from_sequences(
        [f"{first}{second}" for first in "abc" for second in "abc"]
    )

    iterator = iter(automaton)
    assert next(iterator) == ("a", "a")


def test_iteration_orders_a_prefix_before_its_extensions() -> None:
    """The empty suffix sorts first, which is what makes ranking consistent."""
    automaton = Dafsa.from_sequences(["ab", "a", "abc"])

    assert list(automaton) == [("a",), ("a", "b"), ("a", "b", "c")]


def test_iteration_follows_the_alphabet_not_the_tokens() -> None:
    """With incomparable tokens the order is the alphabet's, and still total."""
    sequences: list[tuple[object, ...]] = [("b",), (1,), ("a",)]
    automaton = Dafsa.from_sequences(sequences)

    assert list(automaton) == sorted(sequences, key=automaton.alphabet.encode)


# -- ranking ---------------------------------------------------------------


@STRUCTURES
def test_rank_gives_the_position_in_iteration_order(structure: type[Any]) -> None:
    automaton = structure.from_sequences(WORDS)

    for position, sequence in enumerate(automaton):
        assert automaton.rank(sequence) == position


@STRUCTURES
def test_unrank_is_the_inverse_of_rank(structure: type[Any]) -> None:
    automaton = structure.from_sequences(WORDS)

    for sequence in automaton:
        assert automaton.unrank(automaton.rank(sequence)) == sequence


@STRUCTURES
@settings(deadline=None, max_examples=200)
@given(words=WORD_LISTS)
def test_ranking_is_a_bijection_onto_range(
    structure: type[Any], words: list[str]
) -> None:
    """The minimal-perfect-hash property, stated directly."""
    automaton = structure.from_sequences(words)

    positions = [automaton.rank(sequence) for sequence in automaton]

    assert sorted(positions) == list(range(len(automaton)))
    assert [automaton.unrank(i) for i in range(len(automaton))] == list(automaton)


def test_rank_rejects_sequences_that_are_not_accepted() -> None:
    automaton = Dafsa.from_sequences(["tap"])

    for absent in ("ta", "tapped", "zzz", ""):
        with pytest.raises(ValueError, match="not accepted"):
            automaton.rank(absent)


def test_unrank_rejects_positions_outside_the_language() -> None:
    automaton = Dafsa.from_sequences(WORDS)

    for position in (-1, len(automaton), 10_000):
        with pytest.raises(IndexError, match="out of range"):
            automaton.unrank(position)


def test_unrank_does_not_enumerate_to_reach_a_position() -> None:
    """A large language, indexed near its end, must still be cheap.

    Enumerating would visit every earlier sequence; descending by suffix counts
    visits one state per token.
    """
    automaton = Dafsa.from_sequences(
        [
            f"{a}{b}{c}{d}"
            for a in "abcde"
            for b in "abcde"
            for c in "abcde"
            for d in "abcde"
        ]
    )

    assert len(automaton) == 5**4
    assert automaton.unrank(5**4 - 1) == ("e", "e", "e", "e")
    assert automaton.rank(("e", "e", "e", "e")) == 5**4 - 1


# -- prefixes --------------------------------------------------------------


def test_starts_with_yields_only_extensions() -> None:
    automaton = Dafsa.from_sequences(WORDS)

    assert list(automaton.starts_with("ta")) == [
        ("t", "a", "p"),
        ("t", "a", "p", "s"),
    ]


def test_starts_with_an_empty_prefix_is_the_whole_language() -> None:
    automaton = Dafsa.from_sequences(WORDS)

    assert list(automaton.starts_with(())) == list(automaton)


def test_starts_with_an_absent_prefix_yields_nothing() -> None:
    automaton = Dafsa.from_sequences(WORDS)

    assert list(automaton.starts_with("zz")) == []
    assert list(automaton.starts_with("tz")) == []


def test_starts_with_includes_the_prefix_when_it_is_accepted() -> None:
    automaton = Dafsa.from_sequences(["a", "ab"])

    assert list(automaton.starts_with("a")) == [("a",), ("a", "b")]


@settings(deadline=None, max_examples=200)
@given(words=WORD_LISTS, prefix=st.text(alphabet="abc", max_size=3))
def test_starts_with_matches_filtering_the_whole_language(
    words: list[str], prefix: str
) -> None:
    automaton = Dafsa.from_sequences(words)
    head = tuple(prefix)

    expected = [s for s in automaton if s[: len(head)] == head]

    assert list(automaton.starts_with(prefix)) == expected


def test_longest_prefix_of() -> None:
    lexicon = Dafsa.from_sequences(["can", "candle"])

    assert lexicon.longest_prefix_of("candles") == tuple("candle")
    assert lexicon.longest_prefix_of("cane") == tuple("can")
    assert lexicon.longest_prefix_of("candle") == tuple("candle")
    assert lexicon.longest_prefix_of("ca") is None
    assert lexicon.longest_prefix_of("dog") is None


def test_longest_prefix_of_with_an_accepting_root() -> None:
    lexicon = Dafsa.from_sequences(["", "ab"])

    assert lexicon.longest_prefix_of("zzz") == ()
    assert lexicon.longest_prefix_of("ab") == ("a", "b")


def test_longest_prefix_of_stops_at_an_unknown_token() -> None:
    lexicon = Dafsa.from_sequences(["ab"])

    assert lexicon.longest_prefix_of("aQb") is None


def test_greedy_segmentation_against_a_lexicon() -> None:
    """What ``longest_prefix_of`` is for."""
    lexicon = Dafsa.from_sequences(["the", "cat", "sat", "a", "at"])
    text = "thecatsat"

    segments = []
    while text:
        token = lexicon.longest_prefix_of(text)
        assert token is not None
        segments.append("".join(str(part) for part in token))
        text = text[len(token) :]

    assert segments == ["the", "cat", "sat"]


# -- match -----------------------------------------------------------------


def test_match_returns_the_whole_path() -> None:
    """Issue #8: 1.0 returned only a final node and an uninterpretable weight."""
    automaton = Dafsa.from_sequences(["tap"])
    found = automaton.match("tap")

    assert isinstance(found, Match)
    assert found.sequence == ("t", "a", "p")
    assert len(found.states) == 4
    assert len(found.transitions) == 3
    assert found.states[0] == ROOT
    assert automaton.is_final(found.states[-1])


def test_match_transitions_chain_correctly() -> None:
    automaton = Dafsa.from_sequences(WORDS)
    found = automaton.match("tops")
    assert found is not None

    for index, transition in enumerate(found.transitions):
        assert transition.source == found.states[index]
        assert transition.target == found.states[index + 1]
        assert automaton.alphabet.token(transition.symbol) == found.sequence[index]


def test_match_returns_none_for_rejected_sequences() -> None:
    automaton = Dafsa.from_sequences(["tap"])

    # Three different exits, all None: "ta" walks a real path that does not end
    # accepting; "at" and "tt" use known tokens but have no transition to follow;
    # "tapped" and "zzz" contain tokens the alphabet has never seen.
    for absent in ("ta", "at", "tt", "tapped", "zzz", ""):
        assert automaton.match(absent) is None


def test_match_carries_the_weight() -> None:
    automaton = Dafsa.from_weighted([("tap", 7)], semiring=COUNTING)
    found = automaton.match("tap")

    assert found is not None
    assert found.weight == 7


def test_paths_yields_the_single_accepting_path() -> None:
    """A deterministic acceptor has at most one; the plural is for the transducers."""
    automaton = Dafsa.from_sequences(["tap"])

    assert len(list(automaton.paths("tap"))) == 1
    assert list(automaton.paths("nope")) == []
    assert next(iter(automaton.paths("tap"))) == automaton.match("tap")


# -- totals ----------------------------------------------------------------


def test_total_weight_counts_every_insertion() -> None:
    """``len`` is distinct sequences; ``total_weight`` is what was put in."""
    automaton = Dafsa.from_sequences(["tip", "tip", "tap"], semiring=COUNTING)

    assert len(automaton) == 2
    assert automaton.total_weight() == 3


def test_total_weight_of_an_empty_language_is_zero() -> None:
    for semiring in (BOOLEAN, COUNTING, TROPICAL, PROBABILITY, VITERBI):
        automaton = Dafsa.from_sequences([], semiring=semiring)
        assert automaton.total_weight() == semiring.zero


def test_total_weight_of_an_acceptor_is_one() -> None:
    assert Dafsa.from_sequences(WORDS).total_weight() is True


@settings(deadline=None, max_examples=200)
@given(
    pairs=st.lists(
        st.tuples(st.text(alphabet="abc", min_size=1, max_size=4), st.integers(1, 20)),
        max_size=10,
    )
)
def test_total_weight_matches_folding_the_input(pairs: list[tuple[str, int]]) -> None:
    automaton = Dafsa.from_weighted(pairs, semiring=COUNTING)

    assert automaton.total_weight() == sum(weight for _, weight in pairs)


def test_total_weight_is_a_minimum_under_the_tropical_semiring() -> None:
    automaton = Dafsa.from_weighted(
        [("tap", 2.0), ("taps", 0.5), ("top", 1.0)], semiring=TROPICAL
    )

    assert automaton.total_weight() == 0.5


def test_total_weight_sums_probabilities() -> None:
    automaton = Dafsa.from_weighted(
        [("a", 0.5), ("b", 0.25), ("c", 0.125)], semiring=PROBABILITY
    )

    assert math.isclose(automaton.total_weight(), 0.875)


@settings(deadline=None, max_examples=100)
@given(words=WORD_LISTS)
def test_total_weight_agrees_with_summing_each_weight(words: list[str]) -> None:
    """The dynamic program must agree with asking each sequence individually."""
    automaton = Dafsa.from_sequences(words, semiring=COUNTING)

    expected = sum(automaton.weight(sequence) for sequence in automaton)

    assert automaton.total_weight() == expected


# -- k best ----------------------------------------------------------------


def test_k_best_under_the_tropical_semiring() -> None:
    automaton = Dafsa.from_weighted(
        [("tap", 2.0), ("taps", 0.5), ("top", 1.0)], semiring=TROPICAL
    )

    assert automaton.k_best(2) == [(("t", "a", "p", "s"), 0.5), (("t", "o", "p"), 1.0)]
    assert automaton.k_best(1) == [(("t", "a", "p", "s"), 0.5)]


def test_k_best_under_the_viterbi_semiring_prefers_the_largest() -> None:
    automaton = Dafsa.from_weighted(
        [("tap", 0.2), ("taps", 0.5), ("top", 0.1)], semiring=VITERBI
    )

    assert [weight for _, weight in automaton.k_best(3)] == [0.5, 0.2, 0.1]


def test_k_best_returns_everything_when_k_exceeds_the_language() -> None:
    automaton = Dafsa.from_weighted([("a", 1.0), ("b", 2.0)], semiring=TROPICAL)

    assert len(automaton.k_best(10)) == 2


@pytest.mark.parametrize("k", [0, -1])
def test_k_best_of_nothing_is_nothing(k: int) -> None:
    automaton = Dafsa.from_weighted([("a", 1.0)], semiring=TROPICAL)

    assert automaton.k_best(k) == []


def test_k_best_is_refused_for_non_idempotent_semirings() -> None:
    """Under counting, ``plus(2, 3)`` is ``5`` — an accumulation, not a preference."""
    automaton = Dafsa.from_sequences(["ab"], semiring=COUNTING)

    with pytest.raises(NotImplementedError, match="not idempotent"):
        automaton.k_best(1)


@settings(deadline=None, max_examples=100)
@given(
    pairs=st.lists(
        st.tuples(
            st.text(alphabet="ab", min_size=1, max_size=3),
            st.integers(0, 100).map(float),
        ),
        max_size=8,
    ),
    k=st.integers(1, 5),
)
def test_k_best_matches_sorting_everything(
    pairs: list[tuple[str, float]], k: int
) -> None:
    """The heap must agree with the obvious O(n log n) answer."""
    automaton = Dafsa.from_weighted(pairs, semiring=TROPICAL)

    everything = sorted(
        ((sequence, automaton.weight(sequence)) for sequence in automaton),
        key=lambda entry: entry[1],
    )

    assert [weight for _, weight in automaton.k_best(k)] == [
        weight for _, weight in everything[:k]
    ]


def test_k_best_breaks_ties_deterministically() -> None:
    automaton = Dafsa.from_weighted(
        [("a", 1.0), ("b", 1.0), ("c", 1.0)], semiring=TROPICAL
    )

    assert automaton.k_best(2) == automaton.k_best(2)
    assert len(automaton.k_best(2)) == 2


# -- topological order -----------------------------------------------------


@settings(deadline=None, max_examples=100)
@given(words=WORD_LISTS)
def test_topological_order_is_valid(words: list[str]) -> None:
    """Every source must precede every target."""
    automaton = Dafsa.from_sequences(words)
    order = automaton.topological_order()
    position = {state: index for index, state in enumerate(order)}

    assert sorted(order) == list(automaton.states())
    for transition in automaton.all_transitions():
        assert position[transition.source] < position[transition.target]


@settings(deadline=None, max_examples=100)
@given(words=WORD_LISTS)
def test_topological_order_agrees_with_an_independent_algorithm(
    words: list[str],
) -> None:
    """The library uses depth-first post-order; the reference uses Kahn's."""
    automaton = Dafsa.from_sequences(words)
    theirs = {state: index for index, state in enumerate(automaton.topological_order())}
    reference = reference_topological_order(automaton)

    assert sorted(reference) == sorted(theirs)
    for transition in automaton.all_transitions():
        assert theirs[transition.source] < theirs[transition.target]


def test_canonical_numbering_is_not_topological() -> None:
    """Guards the reason ``topological_order`` exists at all.

    If breadth-first numbering happened to be topological, every dynamic program
    here could just iterate ``reversed(range(num_states))``. It is not: a state
    can be discovered early through one predecessor and have another predecessor
    discovered later.
    """
    # "a" reaches the accepting state directly, so it is numbered 1; "bc" reaches
    # the same state through an intermediate numbered 2, giving a 2 -> 1 edge.
    automaton = Dafsa.from_sequences(["a", "bc"])
    naive_is_topological = all(
        transition.source < transition.target
        for transition in automaton.all_transitions()
    )

    assert not naive_is_topological
    assert topological_order(automaton) != list(automaton.states())
