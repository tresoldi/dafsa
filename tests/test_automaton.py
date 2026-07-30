"""Tests for the frozen automaton: traversal, membership, and depth."""

from __future__ import annotations

import copy
import pickle
import sys

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from dafsa.alphabet import Alphabet
from dafsa.automaton import ROOT, Automaton, Transition
from helpers import accepted_sequences, build_trie

WORDS = ["tap", "taps", "top", "tops", "dibs"]


def test_accepts_every_inserted_sequence() -> None:
    automaton = build_trie(WORDS)
    for word in WORDS:
        assert automaton.accepts(word)


def test_rejects_non_members() -> None:
    automaton = build_trie(WORDS)
    for word in ["ta", "tapped", "dib", "", "zzz"]:
        assert not automaton.accepts(word)


def test_rejects_a_proper_prefix_that_is_not_final() -> None:
    """The failure mode is accepting every prefix; ``is_final`` is what stops it."""
    automaton = build_trie(["tips"])
    assert automaton.accepts("tips")
    for prefix in ["t", "ti", "tip"]:
        assert not automaton.accepts(prefix)


def test_rejects_sequences_with_unknown_tokens_without_raising() -> None:
    automaton = build_trie(["ab"])
    assert not automaton.accepts("aQ")
    assert not automaton.accepts("QQQQ")


def test_in_operator() -> None:
    automaton = build_trie(WORDS)
    assert "tap" in automaton
    assert "ta" not in automaton


def test_in_operator_rejects_non_sequences() -> None:
    automaton = build_trie(WORDS)
    assert 42 not in automaton
    assert None not in automaton


def test_the_empty_sequence_is_accepted_only_when_the_root_is_final() -> None:
    assert "" not in build_trie(["a"])
    assert "" in build_trie(["", "a"])


def test_tokens_need_not_be_characters() -> None:
    automaton = build_trie([("the", "cat"), ("the", "dog")])
    assert ("the", "cat") in automaton
    assert ("the",) not in automaton
    assert ("the", "bird") not in automaton


def test_structure_of_a_known_trie() -> None:
    automaton = build_trie(["ab", "ac"])

    assert automaton.num_states == 4
    assert automaton.num_transitions == 3
    assert automaton.out_degree(ROOT) == 1
    assert not automaton.is_final(ROOT)
    assert list(automaton.states()) == [0, 1, 2, 3]


def test_step_follows_and_reports_missing_transitions() -> None:
    alphabet = Alphabet.from_sequences(["ab"])
    automaton = build_trie(["ab"])

    after_a = automaton.step(ROOT, alphabet.id("a"))
    assert after_a is not None
    assert automaton.step(ROOT, alphabet.id("b")) is None
    assert automaton.step(after_a, alphabet.id("a")) is None


def test_walk_returns_none_when_the_path_breaks() -> None:
    automaton = build_trie(["abc"])
    alphabet = automaton.alphabet

    assert automaton.walk(alphabet.encode("abc")) is not None
    assert automaton.walk(alphabet.encode("abcabc")) is None


def test_walk_accepts_a_start_state() -> None:
    automaton = build_trie(["ab"])
    alphabet = automaton.alphabet

    after_a = automaton.step(ROOT, alphabet.id("a"))
    assert after_a is not None
    assert automaton.walk(alphabet.encode("b"), start=after_a) is not None


def test_walk_of_no_symbols_stays_put() -> None:
    automaton = build_trie(["ab"])
    assert automaton.walk([]) == ROOT
    assert automaton.walk([], start=1) == 1


def test_transitions_are_yielded_in_symbol_order() -> None:
    automaton = build_trie(["c", "a", "b"])
    symbols = [transition.symbol for transition in automaton.transitions(ROOT)]

    assert symbols == sorted(symbols)
    assert symbols == [0, 1, 2]


def test_transitions_report_their_source() -> None:
    automaton = build_trie(["ab"])
    (transition,) = automaton.transitions(ROOT)

    assert isinstance(transition, Transition)
    assert transition.source == ROOT


def test_all_transitions_covers_everything_once() -> None:
    automaton = build_trie(WORDS)
    everything = list(automaton.all_transitions())

    assert len(everything) == automaton.num_transitions
    assert [t.source for t in everything] == sorted(t.source for t in everything)


def test_repr_is_informative() -> None:
    automaton = build_trie(["ab"])
    assert repr(automaton).startswith("<Automaton states=3 transitions=2")


def test_language_matches_an_independent_enumeration() -> None:
    expected = {tuple(word) for word in WORDS}
    assert accepted_sequences(build_trie(WORDS)) == expected


@settings(deadline=None, max_examples=200)
@given(st.lists(st.text(alphabet="abc", max_size=5), max_size=8))
def test_language_matches_the_input_set(words: list[str]) -> None:
    """The accepted language must be exactly the set of inserted sequences."""
    automaton = build_trie(words)
    expected = {tuple(word) for word in words}

    assert accepted_sequences(automaton) == expected
    for word in words:
        assert automaton.accepts(word)


@settings(deadline=None, max_examples=100)
@given(
    words=st.lists(st.text(alphabet="ab", min_size=1, max_size=4), max_size=6),
    probe=st.text(alphabet="ab", max_size=5),
)
def test_membership_agrees_with_a_reference_set(words: list[str], probe: str) -> None:
    automaton = build_trie(words)
    assert automaton.accepts(probe) == (probe in set(words))


# -- depth -----------------------------------------------------------------
#
# Issue #10. In 1.0 the states were linked Python objects, so a deep automaton
# could not be deep-copied, pickled, or traversed without recursing once per
# state. The flat arrays remove the possibility rather than raise the limit, and
# these tests run well past the default recursion limit of 1000.

DEEP = 50_000


def test_issue_10_deep_automaton_builds_and_freezes() -> None:
    automaton = build_trie(["a" * DEEP])

    assert automaton.num_states == DEEP + 1
    assert automaton.num_transitions == DEEP


def test_issue_10_deep_automaton_is_traversable() -> None:
    automaton = build_trie(["a" * DEEP])

    assert automaton.accepts("a" * DEEP)
    assert not automaton.accepts("a" * (DEEP - 1))


def test_issue_10_deep_automaton_survives_deepcopy() -> None:
    """``copy.deepcopy`` on the 1.0 node graph was the direct cause of #10."""
    automaton = build_trie(["a" * DEEP])
    duplicate = copy.deepcopy(automaton)

    assert duplicate.num_states == automaton.num_states
    assert duplicate.accepts("a" * DEEP)


def test_issue_10_deep_automaton_survives_pickling() -> None:
    automaton = build_trie(["a" * DEEP])
    restored: Automaton = pickle.loads(pickle.dumps(automaton))

    assert restored.num_states == automaton.num_states
    assert restored.accepts("a" * DEEP)


def test_recursion_limit_is_not_being_quietly_raised() -> None:
    """Guards the tests above: they must pass at the default limit, not a raised one."""
    assert sys.getrecursionlimit() < DEEP

    with pytest.raises(RecursionError):
        _overflow()


def _overflow() -> int:
    return _overflow()
