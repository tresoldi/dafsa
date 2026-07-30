"""Tests for transducers, composition, projection, and Revuz minimization.

The relation a transducer stands for is checked against the dictionary it was
built from: every input must map to exactly the outputs that were paired with it,
and nothing else.
"""

from __future__ import annotations

from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from dafsa import Dafsa, Trie, tokenize
from dafsa._algorithms import minimize
from dafsa.exceptions import DeterminismError
from dafsa.fst import EPSILON, Fst, align, compose
from dafsa.semirings import COUNTING, TROPICAL
from dafsa.structures import CompactDafsa
from helpers import accepted_sequences, assert_deterministic_and_dense, assert_minimal

WORD_LISTS = st.lists(st.text(alphabet="abc", max_size=4), max_size=8)


def joined(tokens: tuple[Any, ...]) -> str:
    """Render tokens as a string."""
    return "".join(str(token) for token in tokens)


# -- Revuz minimization ----------------------------------------------------


@settings(deadline=None, max_examples=300)
@given(words=WORD_LISTS)
def test_minimizing_a_trie_gives_the_incrementally_built_dafsa(
    words: list[str],
) -> None:
    """Two unrelated routes to the minimal automaton must arrive at the same one.

    The dictionary construction minimizes as it inserts, using a register keyed on
    states it has finished with. Revuz minimization instead takes a finished
    automaton and merges bottom-up. Agreement is a strong check on both.
    """
    minimized = minimize(Trie.from_sequences(words), Dafsa)
    incremental = Dafsa.from_sequences(words)

    assert minimized.num_states == incremental.num_states
    assert minimized.num_transitions == incremental.num_transitions
    assert accepted_sequences(minimized) == accepted_sequences(incremental)


@settings(deadline=None, max_examples=200)
@given(words=WORD_LISTS)
def test_minimization_preserves_the_language(words: list[str]) -> None:
    trie = Trie.from_sequences(words)

    assert accepted_sequences(minimize(trie, Dafsa)) == accepted_sequences(trie)


@settings(deadline=None, max_examples=200)
@given(words=WORD_LISTS)
def test_a_minimized_automaton_is_minimal(words: list[str]) -> None:
    assert_minimal(minimize(Trie.from_sequences(words), Dafsa))


@settings(deadline=None, max_examples=100)
@given(words=WORD_LISTS)
def test_minimizing_a_minimal_automaton_changes_nothing(words: list[str]) -> None:
    automaton = Dafsa.from_sequences(words)
    again = minimize(automaton, Dafsa)

    assert again.num_states == automaton.num_states
    assert accepted_sequences(again) == accepted_sequences(automaton)


@settings(deadline=None, max_examples=100)
@given(
    pairs=st.lists(
        st.tuples(st.text(alphabet="ab", min_size=1, max_size=3), st.integers(1, 9)),
        max_size=6,
    )
)
def test_minimization_preserves_weights(pairs: list[tuple[str, int]]) -> None:
    trie = Trie.from_weighted(pairs, semiring=COUNTING)
    minimized = minimize(trie, Dafsa)

    for sequence in trie:
        assert minimized.weight(sequence) == trie.weight(sequence)


def test_minimization_handles_compound_labels() -> None:
    compacted = Dafsa.from_sequences(["tapas", "topos"]).compact()
    minimized = minimize(compacted, CompactDafsa)

    assert accepted_sequences(minimized) == accepted_sequences(compacted)


def test_minimizing_an_empty_automaton() -> None:
    minimized = minimize(Trie.from_sequences([]), Dafsa)

    assert minimized.num_states == 1
    assert len(minimized) == 0


# -- the relation ----------------------------------------------------------


def test_apply_returns_the_paired_output() -> None:
    fst = Fst.from_pairs([("cat", "chat"), ("dog", "chien")])

    assert fst.apply("cat") == [tuple("chat")]
    assert fst.apply("dog") == [tuple("chien")]
    assert fst.apply("cow") == []


def test_apply_reports_every_analysis() -> None:
    """A transducer may be ambiguous; that is the point of returning a list."""
    fst = Fst.from_alignments([[("a", "x")], [("a", "y")], [("a", "z")]])

    assert fst.apply("a") == [("x",), ("y",), ("z",)]


@settings(deadline=None, max_examples=200)
@given(
    pairs=st.lists(
        st.tuples(
            st.text(alphabet="ab", min_size=1, max_size=4),
            st.text(alphabet="xy", min_size=1, max_size=4),
        ),
        max_size=6,
        unique_by=lambda pair: pair[0],
    )
)
def test_apply_matches_the_dictionary_it_was_built_from(
    pairs: list[tuple[str, str]],
) -> None:
    fst = Fst.from_pairs(pairs)

    for source, target in pairs:
        assert tuple(target) in fst.apply(source)


def test_epsilon_lets_the_sides_differ_in_length() -> None:
    fst = Fst.from_alignments([[("a", "x"), (EPSILON, "y"), (EPSILON, "z")]])

    assert fst.apply("a") == [("x", "y", "z")]


def test_epsilon_on_the_output_side_deletes() -> None:
    fst = Fst.from_alignments([[("a", "x"), ("b", EPSILON), ("c", "z")]])

    assert fst.apply("abc") == [("x", "z")]


def test_align_pads_the_shorter_side() -> None:
    assert align("ab", "xyz") == [("a", "x"), ("b", "y"), (EPSILON, "z")]
    assert align("abc", "x") == [("a", "x"), ("b", EPSILON), ("c", EPSILON)]
    assert align("", "") == []


def test_a_transducer_is_minimal() -> None:
    fst = Fst.from_pairs([("cat", "chat"), ("cot", "chot")])

    assert_minimal(fst)
    assert_deterministic_and_dense(fst)


def test_word_tokens() -> None:
    fst = Fst.from_pairs([(tokenize("the cat"), tokenize("le chat"))])

    assert fst.apply(tokenize("the cat")) == [("le", "chat")]


def test_weighted_alignments() -> None:
    fst = Fst.from_weighted_alignments(
        [([("a", "x")], 2.0), ([("b", "y")], 5.0)], semiring=TROPICAL
    )

    assert fst.semiring is TROPICAL
    assert fst.weight([("a", "x")]) == 2.0
    assert fst.weight([("b", "y")]) == 5.0


# -- projection ------------------------------------------------------------


def test_project_gives_each_side() -> None:
    fst = Fst.from_pairs([("cat", "chat"), ("dog", "chien")])

    assert sorted(joined(s) for s in fst.project("input")) == ["cat", "dog"]
    assert sorted(joined(s) for s in fst.project("output")) == ["chat", "chien"]


def test_project_removes_epsilons() -> None:
    fst = Fst.from_alignments([[("a", "x"), (EPSILON, "y"), ("b", EPSILON)]])

    assert list(fst.project("input")) == [("a", "b")]
    assert list(fst.project("output")) == [("x", "y")]


def test_project_determinizes_an_ambiguous_side() -> None:
    """Two pairs sharing an input make the projection nondeterministic."""
    fst = Fst.from_alignments([[("a", "x")], [("a", "y")]])
    projected = fst.project("input")

    assert list(projected) == [("a",)]
    assert projected.num_states == 2


def test_project_returns_a_minimal_acceptor() -> None:
    fst = Fst.from_pairs([("tap", "1"), ("taps", "2"), ("top", "3"), ("tops", "4")])
    projected = fst.project("input")

    assert_minimal(projected)
    assert (
        projected.num_states
        == Dafsa.from_sequences(["tap", "taps", "top", "tops"]).num_states
    )


@settings(deadline=None, max_examples=200)
@given(
    pairs=st.lists(
        st.tuples(
            st.text(alphabet="ab", min_size=1, max_size=4),
            st.text(alphabet="xy", min_size=1, max_size=4),
        ),
        max_size=6,
    )
)
def test_project_input_matches_the_source_sequences(
    pairs: list[tuple[str, str]],
) -> None:
    projected = Fst.from_pairs(pairs).project("input")

    assert {joined(s) for s in projected} == {source for source, _ in pairs}


def test_project_rejects_an_unknown_side() -> None:
    fst = Fst.from_pairs([("a", "x")])

    with pytest.raises(ValueError, match="must be 'input' or 'output'"):
        fst.project("sideways")


def test_project_of_an_empty_transducer() -> None:
    projected = Fst.from_pairs([]).project("input")

    assert len(projected) == 0


# -- composition -----------------------------------------------------------


def test_compose_chains_two_relations() -> None:
    upper = Fst.from_pairs([("cat", "CAT")])
    translate = Fst.from_pairs([("CAT", "gato")])

    assert compose(upper, translate).apply("cat") == [tuple("gato")]


def test_compose_drops_what_does_not_meet_in_the_middle() -> None:
    left = Fst.from_pairs([("a", "m"), ("b", "n")])
    right = Fst.from_pairs([("m", "x")])
    composed = compose(left, right)

    assert composed.apply("a") == [("x",)]
    assert composed.apply("b") == []


def test_compose_is_associative_on_a_simple_chain() -> None:
    first = Fst.from_pairs([("a", "b")])
    second = Fst.from_pairs([("b", "c")])
    third = Fst.from_pairs([("c", "d")])

    left = compose(compose(first, second), third)
    right = compose(first, compose(second, third))

    assert left.apply("a") == right.apply("a") == [("d",)]


def test_compose_handles_epsilon_on_both_sides() -> None:
    """Without a filter, the interleavings would produce the same path twice."""
    left = Fst.from_alignments([[("a", "m"), ("b", EPSILON)]])
    right = Fst.from_alignments([[("m", "x"), (EPSILON, "y")]])

    composed = compose(left, right)

    assert composed.apply("ab") == [("x", "y")]


def test_compose_multiplies_weights() -> None:
    left = Fst.from_weighted_alignments([([("a", "m")], 2.0)], semiring=TROPICAL)
    right = Fst.from_weighted_alignments([([("m", "x")], 3.0)], semiring=TROPICAL)

    composed = compose(left, right)

    assert composed.weight([("a", "x")]) == 5.0


def test_compose_reports_an_ambiguous_result() -> None:
    """Two routes to the same input and output need weighted determinization."""
    left = Fst.from_alignments([[("a", "m")], [("a", "n")]])
    right = Fst.from_alignments([[("m", "x")], [("n", "x")]])

    with pytest.raises(DeterminismError, match="composition is ambiguous"):
        compose(left, right)


def test_compose_with_an_empty_transducer() -> None:
    composed = compose(Fst.from_pairs([]), Fst.from_pairs([("a", "x")]))

    assert composed.apply("a") == []


def test_composing_a_relation_with_its_inverse_direction() -> None:
    surface = Fst.from_pairs([("walked", "walk+PAST"), ("walks", "walk+PRES")])
    tagger = Fst.from_pairs([("walk+PAST", "V.PST"), ("walk+PRES", "V.PRS")])

    analysed = compose(surface, tagger)

    assert analysed.apply("walked") == [tuple("V.PST")]
    assert analysed.apply("walks") == [tuple("V.PRS")]


@settings(deadline=None, max_examples=100)
@given(
    first=st.lists(
        st.tuples(
            st.text(alphabet="ab", min_size=1, max_size=3),
            st.text(alphabet="mn", min_size=1, max_size=3),
        ),
        max_size=4,
        unique_by=lambda pair: pair[0],
    )
)
def test_composing_with_the_identity_changes_nothing(
    first: list[tuple[str, str]],
) -> None:
    middles = {target for _, target in first}
    identity = Fst.from_pairs([(m, m) for m in middles])

    left = Fst.from_pairs(first)
    composed = compose(left, identity)

    for source, target in first:
        assert tuple(target) in composed.apply(source)
