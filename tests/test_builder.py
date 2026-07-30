"""Tests for the builder and, mostly, for what ``freeze()`` guarantees."""

from __future__ import annotations

import pytest

from dafsa._builder import Builder
from dafsa.alphabet import Alphabet
from dafsa.automaton import ROOT
from dafsa.exceptions import AcyclicityError, DeterminismError
from dafsa.semirings import COUNTING
from helpers import assert_csr_invariants, build_trie, csr


def test_root_exists_and_is_state_zero() -> None:
    builder = Builder(Alphabet("ab"))
    assert builder.num_states == 1
    assert not builder.is_final(ROOT)


def test_builder_exposes_its_alphabet() -> None:
    alphabet = Alphabet("ab")
    assert Builder(alphabet).alphabet is alphabet


def test_frozen_automaton_shares_the_alphabet() -> None:
    alphabet = Alphabet("ab")
    assert Builder(alphabet).freeze().alphabet is alphabet


def test_new_state_returns_dense_ids() -> None:
    builder = Builder(Alphabet("ab"))
    assert [builder.new_state() for _ in range(3)] == [1, 2, 3]


def test_add_transition_rejects_a_duplicate_symbol() -> None:
    builder = Builder(Alphabet("ab"))
    first = builder.new_state()
    second = builder.new_state()
    builder.add_transition(ROOT, 0, first)

    with pytest.raises(DeterminismError, match="already has a transition"):
        builder.add_transition(ROOT, 0, second)


def test_add_transition_rejects_unknown_states() -> None:
    builder = Builder(Alphabet("ab"))
    for source, target in ((5, ROOT), (ROOT, 5), (-1, ROOT)):
        with pytest.raises(IndexError):
            builder.add_transition(source, 0, target)


def test_add_transition_rejects_symbols_outside_the_alphabet() -> None:
    builder = Builder(Alphabet("ab"))
    state = builder.new_state()
    for symbol in (-1, 2):
        with pytest.raises(ValueError, match="symbol not in alphabet"):
            builder.add_transition(ROOT, symbol, state)


def test_set_final_round_trips() -> None:
    builder = Builder(Alphabet("ab"))
    builder.set_final(ROOT)
    assert builder.is_final(ROOT)
    builder.set_final(ROOT, final=False)
    assert not builder.is_final(ROOT)


def test_freeze_renumbers_breadth_first_in_symbol_order() -> None:
    """Numbering must depend on shape, not on the order states were allocated.

    Here the target of the root's *later* symbol is allocated *first*, so
    allocation order and canonical order disagree.
    """
    alphabet = Alphabet("ab")
    builder = Builder(alphabet)

    on_b = builder.new_state()  # allocated first, reached by the later symbol
    on_a = builder.new_state()
    builder.add_transition(ROOT, alphabet.id("b"), on_b)
    builder.add_transition(ROOT, alphabet.id("a"), on_a)
    builder.set_final(on_a)
    builder.set_final(on_b)

    automaton = builder.freeze()
    first, symbol, target, _ = csr(automaton)

    # The root's transitions are symbol-ascending, and their targets were
    # discovered in that order, so "a" leads to state 1 and "b" to state 2.
    assert symbol[first[ROOT] : first[ROOT + 1]] == [alphabet.id("a"), alphabet.id("b")]
    assert target[first[ROOT] : first[ROOT + 1]] == [1, 2]


def test_freeze_is_canonical_across_builders() -> None:
    """Two builders describing the same automaton must freeze identically."""
    alphabet = Alphabet("ab")

    forwards = Builder(alphabet)
    left = forwards.new_state()
    right = forwards.new_state()
    forwards.add_transition(ROOT, 0, left)
    forwards.add_transition(ROOT, 1, right)
    forwards.set_final(left)
    forwards.set_final(right)

    backwards = Builder(alphabet)
    other_right = backwards.new_state()
    other_left = backwards.new_state()
    backwards.add_transition(ROOT, 1, other_right)
    backwards.add_transition(ROOT, 0, other_left)
    backwards.set_final(other_right)
    backwards.set_final(other_left)

    assert csr(forwards.freeze()) == csr(backwards.freeze())


def test_freeze_drops_unreachable_states() -> None:
    builder = Builder(Alphabet("ab"))
    reachable = builder.new_state()
    orphan = builder.new_state()
    builder.add_transition(ROOT, 0, reachable)
    builder.add_transition(orphan, 1, reachable)
    builder.set_final(reachable)

    automaton = builder.freeze()

    assert builder.num_states == 3
    assert automaton.num_states == 2
    assert automaton.num_transitions == 1
    assert_csr_invariants(automaton)


def test_freeze_rejects_a_direct_cycle() -> None:
    builder = Builder(Alphabet("ab"))
    state = builder.new_state()
    builder.add_transition(ROOT, 0, state)
    builder.add_transition(state, 1, state)

    with pytest.raises(AcyclicityError, match="closes a cycle"):
        builder.freeze()


def test_freeze_rejects_a_longer_cycle() -> None:
    alphabet = Alphabet("abc")
    builder = Builder(alphabet)
    one = builder.new_state()
    two = builder.new_state()
    builder.add_transition(ROOT, 0, one)
    builder.add_transition(one, 1, two)
    builder.add_transition(two, 2, one)

    with pytest.raises(AcyclicityError):
        builder.freeze()


def test_freeze_accepts_a_diamond() -> None:
    """Converging paths are not cycles; a naive cycle check gets this wrong."""
    alphabet = Alphabet("abc")
    builder = Builder(alphabet)
    left = builder.new_state()
    right = builder.new_state()
    join = builder.new_state()
    builder.add_transition(ROOT, alphabet.id("a"), left)
    builder.add_transition(ROOT, alphabet.id("b"), right)
    builder.add_transition(left, alphabet.id("c"), join)
    builder.add_transition(right, alphabet.id("c"), join)
    builder.set_final(join)

    automaton = builder.freeze()

    assert automaton.num_states == 4
    assert automaton.num_transitions == 4
    assert_csr_invariants(automaton)


def test_freeze_leaves_the_builder_usable() -> None:
    alphabet = Alphabet("ab")
    builder = Builder(alphabet)
    first = builder.new_state()
    builder.add_transition(ROOT, alphabet.id("a"), first)
    builder.set_final(first)

    before = builder.freeze()
    second = builder.new_state()
    builder.add_transition(ROOT, alphabet.id("b"), second)
    builder.set_final(second)
    after = builder.freeze()

    assert before.num_states == 2
    assert after.num_states == 3


def test_freeze_of_an_empty_builder() -> None:
    automaton = Builder(Alphabet([])).freeze()

    assert automaton.num_states == 1
    assert automaton.num_transitions == 0
    assert not automaton.is_final(ROOT)
    assert_csr_invariants(automaton)


def test_builder_transitions_are_symbol_ordered() -> None:
    alphabet = Alphabet("abc")
    builder = Builder(alphabet)
    for token in "cab":
        state = builder.new_state()
        builder.add_transition(ROOT, alphabet.id(token), state)

    assert [t.symbol for t in builder.transitions(ROOT)] == [0, 1, 2]


def test_builder_repr_is_informative() -> None:
    builder = Builder(Alphabet("ab"))
    state = builder.new_state()
    builder.add_transition(ROOT, 0, state)

    assert repr(builder) == "<Builder states=2 transitions=1>"


def test_transition_weights_are_stored_and_surfaced() -> None:
    """The dictionary structures always weight transitions with ``one``.

    Non-unit transition weights come from the builder, which is the path weight
    pushing and transducers will use, so the storage has to work before they do.
    """
    alphabet = Alphabet("ab")
    builder = Builder(alphabet, COUNTING)
    middle = builder.new_state()
    end = builder.new_state()
    builder.add_transition(ROOT, alphabet.id("a"), middle, 3)
    builder.add_transition(middle, alphabet.id("b"), end, 5)
    builder.set_final(end, weight=7)

    automaton = builder.freeze()

    assert automaton.is_weighted
    assert [t.weight for t in automaton.all_transitions()] == [3, 5]
    assert automaton.weight("ab") == 3 * 5 * 7


def test_weights_equal_to_one_are_not_stored() -> None:
    alphabet = Alphabet("ab")
    builder = Builder(alphabet, COUNTING)
    end = builder.new_state()
    builder.add_transition(ROOT, alphabet.id("a"), end, COUNTING.one)
    builder.set_final(end, weight=COUNTING.one)

    automaton = builder.freeze()

    assert not automaton.is_weighted
    assert automaton.weight("a") == 1


def test_setting_a_state_non_final_clears_its_weight() -> None:
    builder = Builder(Alphabet("ab"), COUNTING)
    builder.set_final(ROOT, weight=9)
    assert builder.final_weight(ROOT) == 9

    builder.set_final(ROOT, final=False)
    assert builder.final_weight(ROOT) == COUNTING.zero


def test_builder_carries_its_semiring() -> None:
    builder = Builder(Alphabet("ab"), COUNTING)

    assert builder.semiring is COUNTING
    assert builder.freeze().semiring is COUNTING


def test_csr_invariants_hold_for_a_trie() -> None:
    assert_csr_invariants(build_trie(["tap", "taps", "top", "tops", "dibs"]))
