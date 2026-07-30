"""Mapping between caller tokens and the dense symbols used internally.

An automaton never stores tokens. It stores the integers an :class:`Alphabet`
assigns to them, which is what makes the flat-array representation possible and
what lets construction sort sequences without ever comparing two tokens.

That last point matters more than it looks. Building a minimal acyclic automaton
incrementally requires the input in sorted order, and 1.0 got that order by
sorting the caller's sequences directly — which raises ``TypeError`` for mixed
input types and cannot handle tokens that are not mutually comparable at all.
Sorting tuples of integers instead is always well defined, so the requirement
becomes an internal invariant rather than something the caller has to satisfy.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from dafsa.exceptions import UnknownTokenError

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Sequence

    from dafsa._types import Symbol, Token


def _canonical_order(tokens: Iterable[Token]) -> list[Token]:
    """Order tokens for symbol assignment.

    Sorted order is preferred, because it makes the lexicographic order of
    encoded sequences agree with the lexicographic order of the sequences a
    caller would write down. When the tokens are not mutually comparable —
    mixed types, or feature bundles with no natural order — first-encountered
    order is used instead.

    Parameters
    ----------
    tokens
        The distinct tokens to order.

    Returns
    -------
    list of Token
        The tokens, sorted if that is possible and in the given order if not.
    """
    ordered = list(tokens)
    try:
        return sorted(ordered)  # type: ignore[type-var]
    except TypeError:
        return ordered


class Alphabet:
    """An ordered, immutable vocabulary of tokens.

    Symbols are assigned by position: the token at index ``i`` of
    :attr:`tokens` has symbol ``i``. The constructor preserves the order it is
    given; use :meth:`from_sequences` to derive a canonically ordered alphabet
    from data.

    Parameters
    ----------
    tokens
        The tokens, in the order symbols should be assigned. Repeats are
        ignored, keeping the first occurrence.

    Examples
    --------
    >>> alphabet = Alphabet("abc")
    >>> alphabet.id("b")
    1
    >>> alphabet.encode("cab")
    (2, 0, 1)
    >>> alphabet.decode((2, 0, 1))
    ('c', 'a', 'b')
    """

    __slots__ = ("_ids", "_tokens")

    def __init__(self, tokens: Iterable[Token]) -> None:
        ids: dict[Token, Symbol] = {}
        for token in tokens:
            if token not in ids:
                ids[token] = len(ids)

        self._ids = ids
        self._tokens: tuple[Token, ...] = tuple(ids)

    @classmethod
    def from_sequences(cls, sequences: Iterable[Sequence[Token]]) -> Alphabet:
        """Build an alphabet from the tokens appearing in ``sequences``.

        Parameters
        ----------
        sequences
            The sequences whose tokens make up the vocabulary.

        Returns
        -------
        Alphabet
            An alphabet over every distinct token seen, in sorted order where
            the tokens are mutually comparable and in first-encountered order
            otherwise.

        Examples
        --------
        >>> Alphabet.from_sequences(["tip", "tap"]).tokens
        ('a', 'i', 'p', 't')
        """
        seen: dict[Token, None] = {}
        for sequence in sequences:
            for token in sequence:
                seen.setdefault(token, None)

        return cls(_canonical_order(seen))

    @property
    def tokens(self) -> tuple[Token, ...]:
        """The tokens, indexed by symbol."""
        return self._tokens

    def id(self, token: Token) -> Symbol:
        """Return the symbol for ``token``.

        Parameters
        ----------
        token
            The token to look up.

        Returns
        -------
        Symbol
            The symbol assigned to ``token``.

        Raises
        ------
        UnknownTokenError
            If ``token`` is not in the alphabet.
        """
        try:
            return self._ids[token]
        except KeyError:
            message = f"token not in alphabet: {token!r}"
            raise UnknownTokenError(message) from None

    def token(self, symbol: Symbol) -> Token:
        """Return the token for ``symbol``.

        Parameters
        ----------
        symbol
            The symbol to look up.

        Returns
        -------
        Token
            The token assigned to ``symbol``.

        Raises
        ------
        IndexError
            If ``symbol`` is out of range.
        """
        if not 0 <= symbol < len(self._tokens):
            message = f"symbol out of range: {symbol}"
            raise IndexError(message)

        return self._tokens[symbol]

    def encode(self, sequence: Sequence[Token]) -> tuple[Symbol, ...]:
        """Encode a sequence of tokens as symbols.

        Parameters
        ----------
        sequence
            The tokens to encode.

        Returns
        -------
        tuple of Symbol
            The encoded sequence.

        Raises
        ------
        UnknownTokenError
            If any token is not in the alphabet. Use :meth:`try_encode` when an
            unknown token is an expected outcome rather than an error.
        """
        return tuple(self.id(token) for token in sequence)

    def try_encode(self, sequence: Sequence[Token]) -> tuple[Symbol, ...] | None:
        """Encode a sequence of tokens, or report that it cannot be encoded.

        This is what membership tests use: a sequence containing a token the
        automaton has never seen is simply not accepted, which is an answer
        rather than an error.

        Parameters
        ----------
        sequence
            The tokens to encode.

        Returns
        -------
        tuple of Symbol or None
            The encoded sequence, or ``None`` if any token is unknown.
        """
        ids = self._ids
        encoded = []
        for token in sequence:
            symbol = ids.get(token)
            if symbol is None:
                return None
            encoded.append(symbol)

        return tuple(encoded)

    def decode(self, symbols: Iterable[Symbol]) -> tuple[Token, ...]:
        """Decode symbols back into tokens.

        Parameters
        ----------
        symbols
            The symbols to decode.

        Returns
        -------
        tuple of Token
            The decoded tokens.

        Raises
        ------
        IndexError
            If any symbol is out of range.
        """
        return tuple(self.token(symbol) for symbol in symbols)

    def __len__(self) -> int:
        """Return the number of tokens in the alphabet."""
        return len(self._tokens)

    def __contains__(self, token: object) -> bool:
        """Return whether ``token`` is in the alphabet."""
        return token in self._ids

    def __iter__(self) -> Iterator[Token]:
        """Iterate over the tokens in symbol order."""
        return iter(self._tokens)

    def __eq__(self, other: object) -> bool:
        """Return whether two alphabets assign the same symbols to the same tokens."""
        if not isinstance(other, Alphabet):
            return NotImplemented

        return self._tokens == other._tokens

    def __hash__(self) -> int:
        """Return a hash consistent with :meth:`__eq__`."""
        return hash(self._tokens)

    def __repr__(self) -> str:
        """Return a debugging representation."""
        return f"Alphabet({self._tokens!r})"


__all__ = ["Alphabet"]
