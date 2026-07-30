"""Tests for weight pushing.

Pushing must not change what the automaton means. Every accepted sequence keeps
its weight to the last bit the semiring can represent; what moves is only where
along the path that weight sits. Those are the two things checked here, plus the
property the whole exercise is for — that afterwards each state's outgoing
weights come to ``one``.
"""

from __future__ import annotations

import math
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from dafsa import Dafsa, Trie
from dafsa._algorithms import minimize, potentials
from dafsa._builder import Builder
from dafsa.alphabet import Alphabet
from dafsa.automaton import ROOT
from dafsa.semirings import (
    BOOLEAN,
    COUNTING,
    LOG,
    PROBABILITY,
    TROPICAL,
    VITERBI,
    Semiring,
)
from helpers import accepted_sequences, assert_deterministic_and_dense, assert_minimal

DIVISIBLE = pytest.mark.parametrize(
    "semiring",
    [TROPICAL, LOG, PROBABILITY, VITERBI],
    ids=["tropical", "log", "probability", "viterbi"],
)

WEIGHTED_PAIRS = st.lists(
    st.tuples(
        st.text(alphabet="abc", min_size=1, max_size=4),
        st.floats(min_value=0.1, max_value=10.0, allow_nan=False),
    ),
    min_size=1,
    max_size=8,
    unique_by=lambda pair: pair[0],
)


def close(left: float, right: float) -> bool:
    """Compare weights, tolerating the rounding division introduces."""
    return math.isclose(left, right, rel_tol=1e-9, abs_tol=1e-12)


def local_total(automaton: Any, state: int, semiring: Semiring[Any]) -> Any:
    """Combine everything leaving ``state``, its final weight included."""
    total = automaton.final_weight(state)
    for index in automaton.transition_indices(state):
        total = semiring.plus(total, automaton.transition_weight(index))

    return total


# -- weights are preserved -------------------------------------------------


@DIVISIBLE
def test_pushing_preserves_every_weight(semiring: Semiring[Any]) -> None:
    words = ["tap", "taps", "top", "tops"]
    weights = [2.0, 0.5, 1.0, 3.0]
    automaton = Dafsa.from_weighted(zip(words, weights, strict=True), semiring=semiring)

    pushed = automaton.push()

    for word in words:
        assert close(pushed.weight(word), automaton.weight(word))


@DIVISIBLE
@settings(deadline=None, max_examples=200)
@given(pairs=WEIGHTED_PAIRS)
def test_pushing_preserves_weights_generally(
    semiring: Semiring[Any], pairs: list[tuple[str, float]]
) -> None:
    automaton = Dafsa.from_weighted(pairs, semiring=semiring)
    pushed = automaton.push()

    for sequence in automaton:
        assert close(pushed.weight(sequence), automaton.weight(sequence))


@DIVISIBLE
@settings(deadline=None, max_examples=200)
@given(pairs=WEIGHTED_PAIRS)
def test_pushing_preserves_the_language(
    semiring: Semiring[Any], pairs: list[tuple[str, float]]
) -> None:
    automaton = Dafsa.from_weighted(pairs, semiring=semiring)

    assert accepted_sequences(automaton.push()) == accepted_sequences(automaton)


@DIVISIBLE
@settings(deadline=None, max_examples=200)
@given(pairs=WEIGHTED_PAIRS)
def test_pushing_preserves_the_total_weight(
    semiring: Semiring[Any], pairs: list[tuple[str, float]]
) -> None:
    automaton = Dafsa.from_weighted(pairs, semiring=semiring)

    assert close(automaton.push().total_weight(), automaton.total_weight())


# -- the point of pushing --------------------------------------------------


@DIVISIBLE
@settings(deadline=None, max_examples=200)
@given(pairs=WEIGHTED_PAIRS)
def test_every_state_is_locally_normalised(
    semiring: Semiring[Any], pairs: list[tuple[str, float]]
) -> None:
    """The property pushing exists to establish."""
    pushed = Dafsa.from_weighted(pairs, semiring=semiring).push()

    for state in pushed.states():
        assert close(local_total(pushed, state, semiring), semiring.one)


def test_probabilities_become_a_local_distribution() -> None:
    """Under the probability semiring, normalisation is what it sounds like."""
    pushed = Dafsa.from_weighted(
        [("ax", 0.2), ("ay", 0.3), ("b", 0.5)], semiring=PROBABILITY
    ).push()

    for state in pushed.states():
        assert close(local_total(pushed, state, PROBABILITY), 1.0)


def test_the_initial_weight_carries_what_was_moved() -> None:
    """Weight has to end up somewhere; the front is where."""
    automaton = Dafsa.from_weighted([("a", 0.25), ("b", 0.75)], semiring=PROBABILITY)
    pushed = automaton.push()

    assert close(pushed.initial_weight, 1.0)
    assert close(automaton.initial_weight, 1.0)

    biased = Dafsa.from_weighted([("a", 2.0), ("b", 3.0)], semiring=PROBABILITY)

    assert close(biased.push().initial_weight, 5.0)


@DIVISIBLE
@settings(deadline=None, max_examples=100)
@given(pairs=WEIGHTED_PAIRS)
def test_pushing_twice_changes_nothing(
    semiring: Semiring[Any], pairs: list[tuple[str, float]]
) -> None:
    """An already-normalised automaton has nothing left to move."""
    once = Dafsa.from_weighted(pairs, semiring=semiring).push()
    twice = once.push()

    for sequence in once:
        assert close(twice.weight(sequence), once.weight(sequence))
    assert twice.num_states == once.num_states


# -- pushing recovers state sharing ---------------------------------------


def test_pushing_lets_minimization_share_what_weights_had_blocked() -> None:
    """The claim in the design document, checked.

    Weight-aware minimization cannot merge two accepting states with different
    weights, even when everything downstream of them is identical. Pushing moves
    the difference to the transitions that lead in, where it belongs, and the
    tails become interchangeable again.
    """
    unweighted = Dafsa.from_sequences(["ax", "bx"])
    weighted = Dafsa.from_weighted([("ax", 0.3), ("bx", 0.7)], semiring=PROBABILITY)
    recovered = minimize(weighted.push(), Dafsa)

    assert weighted.num_states > unweighted.num_states
    assert recovered.num_states == unweighted.num_states

    for sequence, weight in (("ax", 0.3), ("bx", 0.7)):
        assert close(recovered.weight(sequence), weight)


@settings(deadline=None, max_examples=200)
@given(pairs=WEIGHTED_PAIRS)
def test_pushing_then_minimizing_never_grows_an_automaton(
    pairs: list[tuple[str, float]],
) -> None:
    automaton = Dafsa.from_weighted(pairs, semiring=PROBABILITY)
    recovered = minimize(automaton.push(), Dafsa)

    assert recovered.num_states <= automaton.num_states
    for sequence in automaton:
        assert close(recovered.weight(sequence), automaton.weight(sequence))


@settings(deadline=None, max_examples=100)
@given(pairs=WEIGHTED_PAIRS)
def test_the_recovered_automaton_is_still_minimal(
    pairs: list[tuple[str, float]],
) -> None:
    assert_minimal(
        minimize(Dafsa.from_weighted(pairs, semiring=PROBABILITY).push(), Dafsa)
    )


@settings(deadline=None, max_examples=100)
@given(pairs=WEIGHTED_PAIRS)
def test_structural_invariants_survive_pushing(pairs: list[tuple[str, float]]) -> None:
    assert_deterministic_and_dense(Dafsa.from_weighted(pairs, semiring=TROPICAL).push())


# -- what pushing refuses --------------------------------------------------


@pytest.mark.parametrize("semiring", [BOOLEAN, COUNTING], ids=["boolean", "counting"])
def test_pushing_is_refused_for_indivisible_semirings(
    semiring: Semiring[Any],
) -> None:
    """Nothing can be moved without a way to divide it."""
    automaton = Dafsa.from_sequences(["ab"], semiring=semiring)

    with pytest.raises(NotImplementedError, match="not divisible"):
        automaton.push()


class ConcatenationSemiring:
    """A non-commutative semiring, to exercise the guard the built-ins cannot.

    Weights are strings and ``times`` concatenates, so ``times(a, b)`` and
    ``times(b, a)`` differ. Division strips a suffix. Every built-in commutes, so
    without something like this the check in ``push`` could never be reached.
    """

    zero = ""
    one = ""
    idempotent = False
    commutative = False
    divisible = True

    def plus(self, left: str, right: str) -> str:
        return min(left, right)

    def times(self, left: str, right: str) -> str:
        return left + right

    def divide(self, left: str, right: str) -> str:
        return left[: len(left) - len(right)]

    def key(self, weight: str) -> str:
        return weight


def test_pushing_is_refused_for_non_commutative_semirings() -> None:
    """The potentials would not cancel along a path if the order mattered."""
    automaton = Dafsa.from_weighted([("ab", "x")], semiring=ConcatenationSemiring())

    with pytest.raises(NotImplementedError, match="does not commute"):
        automaton.push()


def test_pushing_is_refused_when_a_state_cannot_accept() -> None:
    """No potential means nothing to divide by."""
    alphabet = Alphabet("ab")
    builder = Builder(alphabet, TROPICAL)
    dead = builder.new_state()
    builder.add_transition(ROOT, alphabet.id("a"), dead)

    with pytest.raises(ZeroDivisionError, match="cannot reach an accepting state"):
        builder.freeze().push()


# -- potentials ------------------------------------------------------------


def test_potentials_measure_what_remains() -> None:
    automaton = Dafsa.from_weighted([("ab", 2.0), ("ac", 5.0)], semiring=TROPICAL)
    values = potentials(automaton)

    # Tropical `plus` is `min`, so the root's potential is the cheapest sequence.
    assert values[ROOT] == 2.0


def test_potentials_of_an_unweighted_automaton_are_one() -> None:
    automaton = Dafsa.from_sequences(["ab", "cd"], semiring=VITERBI)

    assert all(value == VITERBI.one for value in potentials(automaton))


def test_pushing_an_unweighted_automaton_changes_nothing() -> None:
    automaton = Dafsa.from_sequences(["tap", "taps"], semiring=PROBABILITY)
    pushed = automaton.push()

    assert pushed.num_states == automaton.num_states
    assert accepted_sequences(pushed) == accepted_sequences(automaton)


def test_pushing_a_trie() -> None:
    """Pushing is a property of the weights, not of how the states are arranged."""
    trie = Trie.from_weighted([("ab", 2.0), ("ac", 3.0)], semiring=PROBABILITY)
    pushed = trie.push()

    assert isinstance(pushed, Trie)
    for sequence in trie:
        assert close(pushed.weight(sequence), trie.weight(sequence))


def test_pushing_keeps_the_class() -> None:
    compacted = Dafsa.from_weighted(
        [("tapas", 2.0), ("topos", 3.0)], semiring=TROPICAL
    ).compact()
    pushed = compacted.push()

    assert type(pushed) is type(compacted)
    assert close(pushed.weight("tapas"), 2.0)
