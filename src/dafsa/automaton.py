"""The frozen core every structure in this library is built on.

An :class:`Automaton` is immutable compressed-sparse-row adjacency over
:mod:`array`. There is no object per state and no object per transition: a state
is an integer, and its outgoing transitions occupy a contiguous slice of three
parallel arrays.

Three properties follow from that layout, and each of them answers a concrete
failure of the 1.0 implementation:

* Traversal is iterative over integer indices, so there is no object graph to
  copy recursively and no way to exhaust the interpreter's stack on a long
  sequence.
* State ids are dense and canonically ordered, so the gaps 1.0 left behind after
  minimization cannot occur.
* The arrays *are* the serialisation format, so exporting is a matter of writing
  them out rather than walking a graph.
"""

from __future__ import annotations

from array import array
from bisect import bisect_left
from collections.abc import Sequence
from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from dafsa._types import State, Symbol, Token
    from dafsa.alphabet import Alphabet

#: The state every traversal starts from. Canonical renumbering guarantees it.
ROOT: State = 0

#: Bit set in the state flags when a state is accepting.
_FINAL = 1

# ``array`` guarantees a minimum width per typecode rather than an exact one.
# "i" is 4 bytes everywhere that matters; the fallback keeps the module honest
# on a platform where it is not.
_MIN_INDEX_BYTES = 4
_INDEX_TYPECODE = "i" if array("i").itemsize >= _MIN_INDEX_BYTES else "l"
_FLAG_TYPECODE = "B"


def index_array(values: Iterable[int] = ()) -> array[int]:
    """Return an array suitable for holding state indices or symbols.

    Parameters
    ----------
    values
        Initial contents.

    Returns
    -------
    array of int
        An integer array of at least 32 bits per item.
    """
    return array(_INDEX_TYPECODE, values)


def flag_array(values: Iterable[int] = ()) -> array[int]:
    """Return an array suitable for holding per-state flag bits.

    Parameters
    ----------
    values
        Initial contents.

    Returns
    -------
    array of int
        An unsigned byte array.
    """
    return array(_FLAG_TYPECODE, values)


class Transition(NamedTuple):
    """One outgoing transition of a state."""

    source: State
    symbol: Symbol
    target: State


class Automaton:
    """An immutable, deterministic, acyclic automaton in CSR form.

    Instances are produced by a builder's ``freeze()`` and are not meant to be
    constructed directly: the constructor trusts its arguments, because the
    builder is what establishes the invariants they have to satisfy.

    Parameters
    ----------
    alphabet
        The alphabet the symbols refer to.
    first
        Offsets into the transition arrays, of length ``num_states + 1``. The
        transitions of state ``q`` are ``first[q]:first[q + 1]``.
    symbol
        Transition symbols, ascending within each state's slice.
    target
        Transition targets, parallel to ``symbol``.
    flags
        Per-state flag bits, one entry per state.

    Notes
    -----
    The invariants the constructor assumes, all established by ``freeze()``:
    ``first`` is non-decreasing and starts at zero; ``symbol`` is strictly
    ascending within each state's slice, which is what makes the binary search
    in :meth:`step` correct and encodes determinism; every state is reachable
    from :data:`ROOT`; and the transitions contain no cycle.
    """

    __slots__ = ("_alphabet", "_first", "_flags", "_symbol", "_target")

    def __init__(
        self,
        alphabet: Alphabet,
        first: array[int],
        symbol: array[int],
        target: array[int],
        flags: array[int],
    ) -> None:
        self._alphabet = alphabet
        self._first = first
        self._symbol = symbol
        self._target = target
        self._flags = flags

    # -- structure ---------------------------------------------------------

    @property
    def alphabet(self) -> Alphabet:
        """The alphabet this automaton's symbols refer to."""
        return self._alphabet

    @property
    def num_states(self) -> int:
        """The number of states."""
        return len(self._flags)

    @property
    def num_transitions(self) -> int:
        """The number of transitions."""
        return len(self._symbol)

    def states(self) -> range:
        """Return the states, as a range over their dense ids.

        Returns
        -------
        range
            ``range(num_states)``, in canonical order.
        """
        return range(len(self._flags))

    def is_final(self, state: State) -> bool:
        """Return whether ``state`` is accepting.

        Parameters
        ----------
        state
            The state to inspect.

        Returns
        -------
        bool
            Whether a sequence ending at ``state`` is accepted.
        """
        return bool(self._flags[state] & _FINAL)

    def out_degree(self, state: State) -> int:
        """Return the number of transitions leaving ``state``.

        Parameters
        ----------
        state
            The state to inspect.

        Returns
        -------
        int
            The number of outgoing transitions.
        """
        return self._first[state + 1] - self._first[state]

    def transitions(self, state: State) -> Iterator[Transition]:
        """Iterate over the transitions leaving ``state``, in symbol order.

        Parameters
        ----------
        state
            The state whose transitions to yield.

        Yields
        ------
        Transition
            Each outgoing transition.
        """
        symbols = self._symbol
        targets = self._target
        for index in range(self._first[state], self._first[state + 1]):
            yield Transition(state, symbols[index], targets[index])

    def all_transitions(self) -> Iterator[Transition]:
        """Iterate over every transition, ordered by source then symbol.

        Yields
        ------
        Transition
            Each transition in the automaton.
        """
        for state in self.states():
            yield from self.transitions(state)

    # -- traversal ---------------------------------------------------------

    def step(self, state: State, symbol: Symbol) -> State | None:
        """Follow one transition.

        Parameters
        ----------
        state
            The state to leave.
        symbol
            The symbol to consume.

        Returns
        -------
        State or None
            The state reached, or ``None`` if ``state`` has no transition on
            ``symbol``.
        """
        low = self._first[state]
        high = self._first[state + 1]
        index = bisect_left(self._symbol, symbol, low, high)
        if index < high and self._symbol[index] == symbol:
            return self._target[index]

        return None

    def walk(self, symbols: Iterable[Symbol], start: State = ROOT) -> State | None:
        """Follow a sequence of symbols.

        The traversal is a loop, not a recursion, so sequence length is bounded
        by memory rather than by the interpreter's stack.

        Parameters
        ----------
        symbols
            The symbols to consume in order.
        start
            The state to start from. Defaults to :data:`ROOT`.

        Returns
        -------
        State or None
            The state reached after consuming every symbol, or ``None`` if the
            path leaves the automaton partway through.
        """
        state = start
        for symbol in symbols:
            following = self.step(state, symbol)
            if following is None:
                return None
            state = following

        return state

    def accepts(self, sequence: Sequence[Token]) -> bool:
        """Return whether ``sequence`` is accepted.

        A sequence containing a token outside the alphabet is not accepted; that
        is an answer, not an error.

        Parameters
        ----------
        sequence
            The tokens to test.

        Returns
        -------
        bool
            Whether the automaton accepts ``sequence``.
        """
        symbols = self._alphabet.try_encode(sequence)
        if symbols is None:
            return False

        state = self.walk(symbols)

        return state is not None and self.is_final(state)

    def __contains__(self, sequence: object) -> bool:
        """Return whether ``sequence`` is accepted, for ``in`` syntax."""
        if not isinstance(sequence, Sequence):
            return False

        return self.accepts(sequence)

    def __repr__(self) -> str:
        """Return a debugging representation."""
        return (
            f"<{type(self).__name__} "
            f"states={self.num_states} "
            f"transitions={self.num_transitions} "
            f"alphabet={len(self._alphabet)}>"
        )


__all__ = ["ROOT", "Automaton", "Transition", "flag_array", "index_array"]
