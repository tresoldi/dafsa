"""Tests for the substring indexes.

Everything is checked against brute force over the source sequence: the set of
its suffixes, the set of its substrings, and the longest block shared with
another sequence are all cheap to compute directly for the small inputs used
here, and that is what the automaton is compared to.
"""

from __future__ import annotations

from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from dafsa import Cdawg, SuffixAutomaton, tokenize
from dafsa.semirings import COUNTING
from helpers import accepted_sequences, assert_deterministic_and_dense, assert_minimal

TEXTS = st.text(alphabet="abc", max_size=12)


def _plain(text: Any) -> SuffixAutomaton:
    return SuffixAutomaton.from_sequence(text)


def _compacted(text: Any) -> Cdawg:
    return SuffixAutomaton.from_sequence(text).compact()


INDEXES = pytest.mark.parametrize("build", [_plain, _compacted], ids=["suffix-automaton", "cdawg"])


def joined(tokens: tuple[Any, ...]) -> str:
    """Render tokens as a string, for comparison with the source text."""
    return "".join(str(token) for token in tokens)


def suffixes(text: str) -> set[tuple[str, ...]]:
    """Every suffix of ``text``, the empty one included."""
    return {tuple(text[start:]) for start in range(len(text) + 1)}


def substrings(text: str) -> set[str]:
    """Every distinct non-empty contiguous block of ``text``."""
    return {
        text[start:stop] for start in range(len(text)) for stop in range(start + 1, len(text) + 1)
    }


# -- the accepted language is the set of suffixes --------------------------


def test_accepts_the_suffixes() -> None:
    index = SuffixAutomaton.from_sequence("banana")

    assert accepted_sequences(index) == suffixes("banana")


@settings(deadline=None, max_examples=300)
@given(text=TEXTS)
def test_accepts_exactly_the_suffixes(text: str) -> None:
    assert accepted_sequences(SuffixAutomaton.from_sequence(text)) == suffixes(text)


@INDEXES
@settings(deadline=None, max_examples=200)
@given(text=TEXTS)
def test_compaction_preserves_the_accepted_suffixes(build: Any, text: str) -> None:
    assert accepted_sequences(build(text)) == suffixes(text)


def test_a_substring_is_not_the_same_as_a_suffix() -> None:
    """The distinction the whole structure turns on."""
    index = SuffixAutomaton.from_sequence("banana")

    # "nan" occurs inside "banana" but the string does not end with it.
    assert index.contains_substring("nan")
    assert "nan" not in index

    # "nana" does both.
    assert index.contains_substring("nana")
    assert "nana" in index


# -- substrings ------------------------------------------------------------


@INDEXES
@settings(deadline=None, max_examples=300)
@given(text=TEXTS)
def test_every_substring_is_found(build: Any, text: str) -> None:
    index = build(text)

    for block in substrings(text):
        assert index.contains_substring(block), block


@INDEXES
@settings(deadline=None, max_examples=300)
@given(text=TEXTS, probe=st.text(alphabet="abcd", max_size=5))
def test_substring_membership_matches_the_source(build: Any, text: str, probe: str) -> None:
    assert build(text).contains_substring(probe) == (probe in text)


@INDEXES
@settings(deadline=None, max_examples=300)
@given(text=TEXTS)
def test_num_substrings_matches_brute_force(build: Any, text: str) -> None:
    assert build(text).num_substrings() == len(substrings(text))


def test_num_substrings_of_a_known_case() -> None:
    assert SuffixAutomaton.from_sequence("banana").num_substrings() == 15
    assert SuffixAutomaton.from_sequence("aaaa").num_substrings() == 4
    assert SuffixAutomaton.from_sequence("abcd").num_substrings() == 10


@INDEXES
def test_the_empty_subsequence_is_always_present(build: Any) -> None:
    assert build("abc").contains_substring("")


@INDEXES
def test_unknown_tokens_are_not_substrings(build: Any) -> None:
    assert not build("abc").contains_substring("z")
    assert not build("abc").contains_substring("abz")


# -- structure -------------------------------------------------------------


@settings(deadline=None, max_examples=200)
@given(text=st.text(alphabet="abc", min_size=3, max_size=15))
def test_the_size_bounds_hold(text: str) -> None:
    """A suffix automaton has at most 2n-1 states and 3n-4 transitions."""
    index = SuffixAutomaton.from_sequence(text)
    length = len(text)

    assert index.num_states <= 2 * length - 1
    assert index.num_transitions <= 3 * length - 4


@settings(deadline=None, max_examples=200)
@given(text=TEXTS)
def test_the_suffix_automaton_is_minimal(text: str) -> None:
    """It is the minimal automaton for the suffix language, not merely a small one."""
    assert_minimal(SuffixAutomaton.from_sequence(text))


@INDEXES
@settings(deadline=None, max_examples=200)
@given(text=TEXTS)
def test_structural_invariants_hold(build: Any, text: str) -> None:
    assert_deterministic_and_dense(build(text))


@settings(deadline=None, max_examples=200)
@given(text=TEXTS)
def test_compaction_never_grows_the_index(text: str) -> None:
    index = SuffixAutomaton.from_sequence(text)
    compacted = index.compact()

    assert isinstance(compacted, Cdawg)
    assert compacted.num_states <= index.num_states


def test_compaction_shrinks_a_repetitive_sequence() -> None:
    """Where compaction earns its place: long forced runs."""
    index = SuffixAutomaton.from_sequence("abcdefghij")
    compacted = index.compact()

    assert compacted.num_states < index.num_states
    assert compacted.num_substrings() == index.num_substrings()


def test_a_cloned_state_is_produced_when_needed() -> None:
    """``abcbc`` forces the clone branch of the construction.

    The state reached by ``bc`` is arrived at by paths of two different lengths,
    so it has to be split; without the clone the automaton would accept ``abc``
    as a suffix, which it is not.
    """
    index = SuffixAutomaton.from_sequence("abcbc")

    assert accepted_sequences(index) == suffixes("abcbc")
    assert "abc" not in index
    assert index.contains_substring("abc")


# -- edge cases ------------------------------------------------------------


def test_an_empty_sequence() -> None:
    index = SuffixAutomaton.from_sequence("")

    assert index.num_states == 1
    assert index.num_transitions == 0
    assert index.num_substrings() == 0
    assert "" in index
    assert index.contains_substring("")


def test_a_single_token() -> None:
    index = SuffixAutomaton.from_sequence("a")

    assert accepted_sequences(index) == {(), ("a",)}
    assert index.num_substrings() == 1


def test_a_repeated_token() -> None:
    index = SuffixAutomaton.from_sequence("aaaa")

    assert accepted_sequences(index) == {(), ("a",), ("a", "a"), ("a",) * 3, ("a",) * 4}
    assert index.num_substrings() == 4


def test_non_string_tokens() -> None:
    sentence = tokenize("the cat sat on the mat")
    index = SuffixAutomaton.from_sequence(sentence)

    assert index.contains_substring(("cat", "sat"))
    assert index.contains_substring(("the", "mat"))
    assert not index.contains_substring(("mat", "the"))
    assert ("the", "mat") in index


def test_the_semiring_is_carried() -> None:
    index = SuffixAutomaton.from_sequence("ab", semiring=COUNTING)

    assert index.semiring is COUNTING
    assert index.weight("ab") == 1


def test_a_long_sequence_builds() -> None:
    """Linear-time construction, at a size where a quadratic one would show."""
    index = SuffixAutomaton.from_sequence("ab" * 5_000)

    assert index.contains_substring("abab")
    assert index.num_states <= 2 * 10_000 - 1


# -- longest common substring ---------------------------------------------


def longest_shared(left: str, right: str) -> str:
    """The longest block the two share, by brute force."""
    best = ""
    for start in range(len(right)):
        for stop in range(start + 1, len(right) + 1):
            block = right[start:stop]
            if len(block) > len(best) and block in left:
                best = block

    return best


def test_longest_common_substring() -> None:
    index = SuffixAutomaton.from_sequence("banana")

    assert joined(index.longest_common_subsequence_with("bananas")) == "banana"
    assert joined(index.longest_common_subsequence_with("ananas")) == "anana"
    assert joined(index.longest_common_subsequence_with("xyz")) == ""


@INDEXES
@settings(deadline=None, max_examples=300)
@given(left=TEXTS, right=st.text(alphabet="abcd", max_size=8))
def test_longest_common_substring_matches_brute_force(build: Any, left: str, right: str) -> None:
    found = joined(build(left).longest_common_subsequence_with(right))

    assert len(found) == len(longest_shared(left, right))
    assert found in left
    assert found in right


def test_longest_common_substring_with_word_tokens() -> None:
    index = SuffixAutomaton.from_sequence(tokenize("the cat sat on the mat"))
    shared = index.longest_common_subsequence_with(tokenize("a cat sat on a mat"))

    assert shared == ("cat", "sat", "on")
