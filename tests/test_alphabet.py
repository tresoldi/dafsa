"""Tests for the token/symbol mapping."""

from __future__ import annotations

import pytest

from dafsa.alphabet import Alphabet
from dafsa.exceptions import UnknownTokenError


def test_constructor_preserves_the_given_order() -> None:
    alphabet = Alphabet("cab")
    assert alphabet.tokens == ("c", "a", "b")
    assert alphabet.id("c") == 0


def test_constructor_ignores_repeats() -> None:
    alphabet = Alphabet("abab")
    assert alphabet.tokens == ("a", "b")
    assert len(alphabet) == 2


def test_from_sequences_sorts_comparable_tokens() -> None:
    """Sorted symbols make encoded order agree with the order a caller expects."""
    alphabet = Alphabet.from_sequences(["tip", "tap", "top"])
    assert alphabet.tokens == ("a", "i", "o", "p", "t")


def test_from_sequences_accepts_non_string_tokens() -> None:
    alphabet = Alphabet.from_sequences([("the", "cat"), ("the", "dog")])
    assert alphabet.tokens == ("cat", "dog", "the")


def test_from_sequences_survives_mutually_incomparable_tokens() -> None:
    """1.0 sorted the caller's sequences, so this input raised ``TypeError``.

    Ordering falls back to first-encountered, which is still a total order — it
    just is not the tokens' natural one, because they have none.
    """
    sequences: list[tuple[object, ...]] = [("a", 1), (2, "b")]
    alphabet = Alphabet.from_sequences(sequences)

    assert alphabet.tokens == ("a", 1, 2, "b")
    assert len(alphabet) == 4


def test_encode_decode_round_trip() -> None:
    alphabet = Alphabet.from_sequences(["tips"])
    assert alphabet.decode(alphabet.encode("tips")) == ("t", "i", "p", "s")


def test_encode_rejects_unknown_tokens() -> None:
    alphabet = Alphabet("ab")
    with pytest.raises(UnknownTokenError):
        alphabet.encode("axb")


def test_unknown_token_error_is_a_key_error() -> None:
    """Callers should be able to catch the built-in they would expect."""
    assert issubclass(UnknownTokenError, KeyError)


def test_try_encode_reports_unknown_tokens_without_raising() -> None:
    alphabet = Alphabet("ab")
    assert alphabet.try_encode("ab") == (0, 1)
    assert alphabet.try_encode("axb") is None


def test_try_encode_handles_the_empty_sequence() -> None:
    assert Alphabet("ab").try_encode("") == ()


def test_token_rejects_out_of_range_symbols() -> None:
    alphabet = Alphabet("ab")
    assert alphabet.token(1) == "b"
    for symbol in (-1, 2):
        with pytest.raises(IndexError):
            alphabet.token(symbol)


def test_membership_and_iteration() -> None:
    alphabet = Alphabet("ab")
    assert "a" in alphabet
    assert "z" not in alphabet
    assert list(alphabet) == ["a", "b"]


def test_equality_depends_on_order_not_just_content() -> None:
    assert Alphabet("ab") == Alphabet("ab")
    assert Alphabet("ab") != Alphabet("ba")
    assert Alphabet("ab") != "ab"


def test_hash_is_consistent_with_equality() -> None:
    assert hash(Alphabet("ab")) == hash(Alphabet("ab"))
    assert len({Alphabet("ab"), Alphabet("ab"), Alphabet("ba")}) == 2


def test_repr_is_informative() -> None:
    assert repr(Alphabet("ab")) == "Alphabet(('a', 'b'))"


def test_empty_alphabet() -> None:
    alphabet = Alphabet([])
    assert len(alphabet) == 0
    assert alphabet.tokens == ()
