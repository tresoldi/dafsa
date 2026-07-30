"""Tests for path compaction.

The obligation is narrow and strict: compaction must change the *size* of a
structure and nothing else. Language, weights, order, ranking and every query
answer must survive it unchanged, because a compacted automaton is meant to be a
smaller drawing of the same thing, not a different thing.

The regression tests for issues #18 and #14 are at the end, run from the inputs
their reporters supplied.
"""

from __future__ import annotations

import math
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from dafsa import CompactDafsa, Dafsa, Trie
from dafsa._algorithms import absorbable
from dafsa._algorithms import compact as compact_algorithm
from dafsa._builder import Builder
from dafsa.alphabet import Alphabet
from dafsa.automaton import ROOT
from dafsa.semirings import COUNTING, PROBABILITY, TROPICAL
from helpers import accepted_sequences, assert_deterministic_and_dense

WORDS = ["tap", "taps", "top", "tops", "dibs"]

STRUCTURES = pytest.mark.parametrize("structure", [Trie, Dafsa], ids=["trie", "dafsa"])

WORD_LISTS = st.lists(st.text(alphabet="abc", max_size=5), max_size=10)


# -- the language is preserved --------------------------------------------


@STRUCTURES
def test_compaction_preserves_the_language(structure: type[Any]) -> None:
    automaton = structure.from_sequences(WORDS)

    assert accepted_sequences(automaton.compact()) == accepted_sequences(automaton)


@STRUCTURES
@settings(deadline=None, max_examples=300)
@given(words=WORD_LISTS)
def test_compaction_preserves_the_language_generally(
    structure: type[Any], words: list[str]
) -> None:
    automaton = structure.from_sequences(words)

    assert accepted_sequences(automaton.compact()) == {tuple(w) for w in set(words)}


@STRUCTURES
@settings(deadline=None, max_examples=200)
@given(words=WORD_LISTS, probe=st.text(alphabet="abc", max_size=6))
def test_membership_survives_compaction(structure: type[Any], words: list[str], probe: str) -> None:
    """A compound label must match in full, not just on its first token."""
    compacted = structure.from_sequences(words).compact()

    assert compacted.accepts(probe) == (probe in set(words))


def test_a_partial_label_match_is_rejected() -> None:
    """The failure mode compaction invites: matching only a label's first token."""
    compacted = Dafsa.from_sequences(["tapas"]).compact()

    assert compacted.num_transitions == 1
    for prefix in ("t", "ta", "tap", "tapa"):
        assert prefix not in compacted
    for wrong in ("tapax", "tapos", "xapas"):
        assert wrong not in compacted
    assert "tapas" in compacted


# -- the structure shrinks -------------------------------------------------


def test_forced_chains_collapse() -> None:
    compacted = Dafsa.from_sequences(["tapas", "topos"]).compact()

    assert compacted.num_states == 4
    labels = {
        "".join(str(t) for t in compacted.transition_tokens(index))
        for state in compacted.states()
        for index in compacted.transition_indices(state)
    }
    assert labels == {"t", "apa", "opo", "s"}


def test_a_single_sequence_collapses_to_one_transition() -> None:
    compacted = Dafsa.from_sequences(["abcdefgh"]).compact()

    assert compacted.num_states == 2
    assert compacted.num_transitions == 1
    assert compacted.transition_tokens(0) == tuple("abcdefgh")


@STRUCTURES
@settings(deadline=None, max_examples=200)
@given(words=WORD_LISTS)
def test_compaction_never_grows_a_structure(structure: type[Any], words: list[str]) -> None:
    automaton = structure.from_sequences(words)
    compacted = automaton.compact()

    assert compacted.num_states <= automaton.num_states
    assert compacted.num_transitions <= automaton.num_transitions


@settings(deadline=None, max_examples=200)
@given(words=WORD_LISTS)
def test_compaction_reaches_a_fixed_point(words: list[str]) -> None:
    """One pass must be enough — 1.0 needed a round per join and still converged."""
    once = Dafsa.from_sequences(words).compact()
    twice = once.compact()

    assert (twice.num_states, twice.num_transitions) == (
        once.num_states,
        once.num_transitions,
    )


@STRUCTURES
@settings(deadline=None, max_examples=200)
@given(words=WORD_LISTS)
def test_structural_invariants_survive_compaction(structure: type[Any], words: list[str]) -> None:
    assert_deterministic_and_dense(structure.from_sequences(words).compact())


def test_the_input_is_not_mutated() -> None:
    """1.0 compacted in place and read queries from a stale deep copy."""
    automaton = Dafsa.from_sequences(["tapas", "topos"])
    before = (automaton.num_states, automaton.num_transitions)

    automaton.compact()

    assert (automaton.num_states, automaton.num_transitions) == before
    assert "tapas" in automaton


def test_a_compacted_automaton_reports_itself_as_compact() -> None:
    plain = Dafsa.from_sequences(WORDS)
    compacted = plain.compact()

    assert not plain.is_compact
    assert compacted.is_compact
    assert isinstance(compacted, CompactDafsa)
    assert "compact" in repr(compacted)


def test_nothing_to_compact_leaves_labels_unstored() -> None:
    """A structure with no forced chain must not pay for a label array."""
    automaton = Dafsa.from_sequences(["a", "b", "c"])
    compacted = automaton.compact()

    assert not compacted.is_compact
    assert compacted.num_states == automaton.num_states


# -- what may and may not be absorbed --------------------------------------


def test_the_root_is_never_absorbed() -> None:
    """The one-line fix for #18 and #14, stated directly.

    The root has no incoming edge. 1.0 tested ``in_degree > 1`` and so treated it
    as a candidate whenever it had a single outgoing edge, then indexed an empty
    list of incoming edges.
    """
    automaton = Dafsa.from_sequences(["tapas", "topos"])

    assert not absorbable(automaton)[ROOT]
    assert all(not absorbable(automaton)[ROOT] for _ in range(2))


def test_an_accepting_state_is_never_absorbed() -> None:
    """Absorbing it would lose the shorter sequence."""
    automaton = Dafsa.from_sequences(["ab", "abc"])
    compacted = automaton.compact()

    assert accepted_sequences(compacted) == {("a", "b"), ("a", "b", "c")}
    assert ("a", "b") in compacted


def test_a_state_with_two_ways_in_is_never_absorbed() -> None:
    """Absorbing it would need the label duplicated onto both predecessors."""
    automaton = Dafsa.from_sequences(["ax", "bx"])
    folds = absorbable(automaton)

    shared = automaton.step(ROOT, automaton.alphabet.id("a"))
    assert shared is not None
    assert not folds[shared]


def test_a_state_with_two_ways_out_is_never_absorbed() -> None:
    automaton = Dafsa.from_sequences(["ab", "ac"])
    folds = absorbable(automaton)

    branching = automaton.step(ROOT, automaton.alphabet.id("a"))
    assert branching is not None
    assert not folds[branching]


def test_a_branching_predecessor_does_not_block_absorption() -> None:
    """A deliberate departure from 1.0, which also required this and compacted less.

    ``p`` branches two ways; the chain under one of them is still forced, and a
    compound label keeps its first token, so determinism at ``p`` is unaffected.
    """
    automaton = Dafsa.from_sequences(["axyz", "b"])
    compacted = automaton.compact()

    assert compacted.out_degree(ROOT) == 2
    labels = {
        "".join(str(t) for t in compacted.transition_tokens(index))
        for index in compacted.transition_indices(ROOT)
    }
    assert labels == {"axyz", "b"}


# -- every query still answers the same ------------------------------------


@settings(deadline=None, max_examples=200)
@given(words=WORD_LISTS)
def test_counting_survives_compaction(words: list[str]) -> None:
    automaton = Dafsa.from_sequences(words)
    compacted = automaton.compact()

    assert len(compacted) == len(automaton)
    assert compacted.total_weight() == automaton.total_weight()


@settings(deadline=None, max_examples=200)
@given(words=WORD_LISTS)
def test_iteration_order_survives_compaction(words: list[str]) -> None:
    automaton = Dafsa.from_sequences(words)

    assert list(automaton.compact()) == list(automaton)


@settings(deadline=None, max_examples=200)
@given(words=WORD_LISTS)
def test_ranking_survives_compaction(words: list[str]) -> None:
    """Suffix counts are per state, and compaction removes states."""
    automaton = Dafsa.from_sequences(words)
    compacted = automaton.compact()

    for sequence in automaton:
        assert compacted.rank(sequence) == automaton.rank(sequence)
    for position in range(len(automaton)):
        assert compacted.unrank(position) == automaton.unrank(position)


@settings(deadline=None, max_examples=200)
@given(words=WORD_LISTS, prefix=st.text(alphabet="abc", max_size=3))
def test_prefix_queries_survive_compaction(words: list[str], prefix: str) -> None:
    """A prefix may now end in the middle of a compound label."""
    automaton = Dafsa.from_sequences(words)

    assert list(automaton.compact().starts_with(prefix)) == list(automaton.starts_with(prefix))


def test_starts_with_a_prefix_inside_a_label() -> None:
    compacted = Dafsa.from_sequences(["tapas", "topos"]).compact()

    assert list(compacted.starts_with("ta")) == [tuple("tapas")]
    assert list(compacted.starts_with("t")) == [tuple("tapas"), tuple("topos")]
    assert list(compacted.starts_with("tap")) == [tuple("tapas")]
    assert list(compacted.starts_with("tax")) == []


@settings(deadline=None, max_examples=200)
@given(words=WORD_LISTS, probe=st.text(alphabet="abc", max_size=6))
def test_longest_prefix_survives_compaction(words: list[str], probe: str) -> None:
    automaton = Dafsa.from_sequences(words)

    assert automaton.compact().longest_prefix_of(probe) == automaton.longest_prefix_of(probe)


def test_longest_prefix_stops_inside_a_label() -> None:
    lexicon = Dafsa.from_sequences(["candle"]).compact()

    assert lexicon.longest_prefix_of("candles") == tuple("candle")
    assert lexicon.longest_prefix_of("candid") is None


@settings(deadline=None, max_examples=200)
@given(words=WORD_LISTS)
def test_match_survives_compaction(words: list[str]) -> None:
    """The state path is shorter after compaction, but the weight is the same."""
    automaton = Dafsa.from_sequences(words)
    compacted = automaton.compact()

    for sequence in automaton:
        found = compacted.match(sequence)
        assert found is not None
        assert found.sequence == sequence
        assert found.weight == automaton.weight(sequence)
        assert len(found.states) == len(found.transitions) + 1


def test_match_rejects_a_partially_matching_label() -> None:
    """All tokens known, first token of the label right, rest wrong."""
    compacted = Dafsa.from_sequences(["tapas"]).compact()

    for wrong in ("tapa", "tapap", "tapass"):
        assert compacted.match(wrong) is None
    assert compacted.match("tapas") is not None


def test_match_states_are_fewer_after_compaction() -> None:
    automaton = Dafsa.from_sequences(["tapas"])
    plain = automaton.match("tapas")
    compacted = automaton.compact().match("tapas")

    assert plain is not None
    assert compacted is not None
    assert len(plain.states) == 6
    assert len(compacted.states) == 2


# -- weights ---------------------------------------------------------------


def test_weights_survive_compaction() -> None:
    automaton = Dafsa.from_weighted([("tapas", 3), ("topos", 5)], semiring=COUNTING)
    compacted = automaton.compact()

    assert compacted.weight("tapas") == 3
    assert compacted.weight("topos") == 5
    assert compacted.weight("tapa") == COUNTING.zero


@settings(deadline=None, max_examples=200)
@given(
    pairs=st.lists(
        st.tuples(st.text(alphabet="abc", min_size=1, max_size=4), st.integers(1, 20)),
        max_size=8,
    )
)
def test_every_weight_survives_compaction(pairs: list[tuple[str, int]]) -> None:
    automaton = Dafsa.from_weighted(pairs, semiring=COUNTING)
    compacted = automaton.compact()

    for sequence in automaton:
        assert compacted.weight(sequence) == automaton.weight(sequence)


def test_absorbed_transition_weights_multiply() -> None:
    """A compound label carries the product of the weights it replaced."""
    alphabet = Alphabet("abc")
    builder = Builder(alphabet, COUNTING)
    middle = builder.new_state()
    end = builder.new_state()
    builder.add_transition(ROOT, alphabet.id("a"), middle, 3)
    builder.add_transition(middle, alphabet.id("b"), end, 5)
    builder.set_final(end)

    compacted = compact_algorithm(builder.freeze(), CompactDafsa)

    assert compacted.num_transitions == 1
    assert compacted.transition_weight(0) == 15
    assert compacted.weight("ab") == 15


def test_probability_weights_survive_compaction() -> None:
    automaton = Dafsa.from_weighted([("walking", 0.5), ("talking", 0.25)], semiring=PROBABILITY)
    compacted = automaton.compact()

    assert math.isclose(compacted.weight("walking"), 0.5)
    assert math.isclose(compacted.weight("talking"), 0.25)


def test_k_best_survives_compaction() -> None:
    automaton = Dafsa.from_weighted([("tapas", 2.0), ("topos", 0.5)], semiring=TROPICAL)

    assert automaton.compact().k_best(2) == automaton.k_best(2)


# -- tokens ----------------------------------------------------------------


def test_compaction_works_with_non_string_tokens() -> None:
    """1.0 joined labels with ``str.join`` and raised ``TypeError`` for these."""
    sequences = [("the", "big", "cat"), ("the", "big", "dog")]
    compacted = Dafsa.from_sequences(sequences).compact()

    assert accepted_sequences(compacted) == set(sequences)
    assert compacted.transition_tokens(0) == ("the", "big")


def test_compaction_works_with_mutually_incomparable_tokens() -> None:
    sequences: list[tuple[object, ...]] = [("a", 1, "z"), ("a", 2, "z")]
    compacted = Dafsa.from_sequences(sequences).compact()

    assert accepted_sequences(compacted) == set(sequences)


def test_transition_tokens_decode_the_label() -> None:
    compacted = Dafsa.from_sequences(["abc"]).compact()

    assert compacted.transition_label(0) == compacted.alphabet.encode("abc")
    assert compacted.transition_tokens(0) == ("a", "b", "c")


def test_transition_symbol_is_the_first_of_the_label() -> None:
    """Determinism and the binary search are keyed on it, so it must stay exact."""
    compacted = Dafsa.from_sequences(["tapas", "topos"]).compact()

    for state in compacted.states():
        for index in compacted.transition_indices(state):
            label = compacted.transition_label(index)
            assert compacted.transition_symbol(index) == label[0]


# -- edge cases ------------------------------------------------------------


def test_compacting_an_empty_structure() -> None:
    compacted = Dafsa.from_sequences([]).compact()

    assert compacted.num_states == 1
    assert compacted.num_transitions == 0
    assert len(compacted) == 0


def test_compacting_a_structure_accepting_only_the_empty_sequence() -> None:
    compacted = Dafsa.from_sequences([""]).compact()

    assert compacted.num_states == 1
    assert compacted.is_final(ROOT)
    assert "" in compacted


def test_compacting_a_deep_chain() -> None:
    """The whole point, at a size where it matters."""
    automaton = Dafsa.from_sequences(["a" * 10_000])
    compacted = automaton.compact()

    assert automaton.num_states == 10_001
    assert compacted.num_states == 2
    assert compacted.accepts("a" * 10_000)
    assert not compacted.accepts("a" * 9_999)


# -- regressions -----------------------------------------------------------


def test_issue_18() -> None:
    """``DAFSA(["tapas", "topos"]).condense()`` raised ``IndexError`` in 1.0.

    The reporter expected either one shared ``p`` edge or "two new collapsed
    edges, 'apa' and 'opo'". The second is what compaction produces.
    """
    compacted = Dafsa.from_sequences(["tapas", "topos"]).compact()

    labels = sorted(
        "".join(str(t) for t in compacted.transition_tokens(index))
        for state in compacted.states()
        for index in compacted.transition_indices(state)
    )

    assert labels == ["apa", "opo", "s", "t"]
    assert "tapas" in compacted
    assert "topos" in compacted


def test_issue_14() -> None:
    """The reporter fed 1.0's own text output back in and ``condense()`` crashed.

    The input is unusual — long strings sharing a ``+-- #`` prefix — which is
    precisely what makes the root a single-out-edge state and triggered the bug.
    """
    lines = [
        "+-- #5: n(#6/2:<p>/2) [('p', 6)]",
        "+-- #6: F(#3/2:<s>/1) [('s', 3)]",
        "+-- #8: n(#3/1:<p>/1) [('p', 3)]",
    ]
    compacted = Dafsa.from_sequences(lines).compact()

    assert accepted_sequences(compacted) == {tuple(line) for line in lines}
    assert compacted.num_states < Dafsa.from_sequences(lines).num_states


@settings(deadline=None, max_examples=300)
@given(words=st.lists(st.text(alphabet="ab", max_size=6), max_size=8))
def test_compaction_never_raises(words: list[str]) -> None:
    """Neither issue was a wrong answer — both were a crash."""
    Dafsa.from_sequences(words).compact()
    Trie.from_sequences(words).compact()
