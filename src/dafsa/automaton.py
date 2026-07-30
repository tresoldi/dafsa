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
from typing import TYPE_CHECKING, Any, NamedTuple

from dafsa.semirings import BOOLEAN

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from dafsa._types import State, Symbol, Token
    from dafsa.alphabet import Alphabet
    from dafsa.semirings import Semiring

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
    """One outgoing transition of a state.

    ``weight`` is typed :obj:`~typing.Any` because it belongs to whichever
    semiring the automaton was built over, and the automaton does not carry that
    type as a parameter. For an unweighted automaton it is the semiring's
    :attr:`~dafsa.semirings.Semiring.one`.
    """

    source: State
    symbol: Symbol
    target: State
    weight: Any


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
    semiring
        The semiring the weights belong to.
    transition_weights
        One weight per transition, or ``None`` when every transition weight is
        the semiring's ``one``.
    final_weights
        One weight per state, or ``None`` when every accepting state's weight is
        the semiring's ``one``.

    Notes
    -----
    The invariants the constructor assumes, all established by ``freeze()``:
    ``first`` is non-decreasing and starts at zero; ``symbol`` is strictly
    ascending within each state's slice, which is what makes the binary search
    in :meth:`step` correct and encodes determinism; every state is reachable
    from :data:`ROOT`; and the transitions contain no cycle.

    The two weight arrays are ``None`` in the common unweighted case rather than
    filled with copies of ``one``. A plain acceptor therefore costs nothing for
    weights it does not use, which matters because memory frugality is much of
    the point of this representation.
    """

    __slots__ = (
        "_alphabet",
        "_final_weights",
        "_first",
        "_flags",
        "_semiring",
        "_symbol",
        "_target",
        "_transition_weights",
    )

    def __init__(  # noqa: PLR0913 - the CSR arrays are irreducibly separate
        self,
        alphabet: Alphabet,
        first: array[int],
        symbol: array[int],
        target: array[int],
        flags: array[int],
        semiring: Semiring[Any] = BOOLEAN,
        transition_weights: list[Any] | None = None,
        final_weights: list[Any] | None = None,
    ) -> None:
        self._alphabet = alphabet
        self._first = first
        self._symbol = symbol
        self._target = target
        self._flags = flags
        self._semiring = semiring
        self._transition_weights = transition_weights
        self._final_weights = final_weights

    # -- structure ---------------------------------------------------------

    @property
    def alphabet(self) -> Alphabet:
        """The alphabet this automaton's symbols refer to."""
        return self._alphabet

    @property
    def semiring(self) -> Semiring[Any]:
        """The semiring this automaton's weights belong to."""
        return self._semiring

    @property
    def is_weighted(self) -> bool:
        """Whether any weight differs from the semiring's ``one``.

        ``False`` means the automaton is a plain acceptor and stores no weight
        arrays; :meth:`weight` still answers, with ``one`` for accepted
        sequences.
        """
        return self._transition_weights is not None or self._final_weights is not None

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

    def final_weight(self, state: State) -> Any:
        """Return the weight contributed by accepting at ``state``.

        Parameters
        ----------
        state
            The state to inspect.

        Returns
        -------
        Any
            The state's final weight, or the semiring's ``zero`` if the state is
            not accepting.
        """
        if not self.is_final(state):
            return self._semiring.zero
        if self._final_weights is None:
            return self._semiring.one

        return self._final_weights[state]

    def transition_weight(self, index: int) -> Any:
        """Return the weight of the transition at ``index``.

        Parameters
        ----------
        index
            A transition index, as produced by :meth:`transition_index`.

        Returns
        -------
        Any
            The transition's weight, or the semiring's ``one`` if the automaton
            stores no transition weights.
        """
        if self._transition_weights is None:
            return self._semiring.one

        return self._transition_weights[index]

    def transitions(self, state: State) -> Iterator[Transition]:
        """Iterate over the transitions leaving ``state``, in symbol order.

        Parameters
        ----------
        state
            The state whose transitions to yield.

        Yields
        ------
        Transition
            Each outgoing transition, carrying its weight.
        """
        symbols = self._symbol
        targets = self._target
        for index in range(self._first[state], self._first[state + 1]):
            yield Transition(
                state, symbols[index], targets[index], self.transition_weight(index)
            )

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

    def transition_index(self, state: State, symbol: Symbol) -> int | None:
        """Return the index of ``state``'s transition on ``symbol``.

        The binary search is over one state's slice of the symbol array, which is
        ascending — the invariant that makes this correct is established by
        ``freeze()``.

        Parameters
        ----------
        state
            The state to leave.
        symbol
            The symbol to consume.

        Returns
        -------
        int or None
            The transition's index into the transition arrays, or ``None`` if
            there is no such transition.
        """
        high = self._first[state + 1]
        index = bisect_left(self._symbol, symbol, self._first[state], high)
        if index < high and self._symbol[index] == symbol:
            return index

        return None

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
        index = self.transition_index(state, symbol)

        return None if index is None else self._target[index]

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

    def weight(self, sequence: Sequence[Token]) -> Any:
        """Return the weight ``sequence`` is accepted with.

        The weight is the semiring product of the transition weights along the
        path and the final weight of the state it ends at — which, for an
        automaton built from weighted sequences, is exactly the weight that
        sequence was inserted with.

        This is the query 1.0's ``lookup()`` was reaching for and got wrong:
        there, weights were counters over a minimized graph, so the returned
        "cumulative weight" summed the frequencies of every sequence sharing an
        edge. ``DAFSA(["dib", "tip", "tips", "top"]).lookup("tip")`` gave ``7``
        for a sequence inserted once.

        Parameters
        ----------
        sequence
            The tokens to weigh.

        Returns
        -------
        Any
            The sequence's weight, or the semiring's ``zero`` if it is not
            accepted. ``zero`` is the weight of a path that does not exist, so a
            rejection needs no special case at the call site.
        """
        symbols = self._alphabet.try_encode(sequence)
        if symbols is None:
            return self._semiring.zero

        semiring = self._semiring
        total = semiring.one
        state = ROOT
        for symbol in symbols:
            index = self.transition_index(state, symbol)
            if index is None:
                return semiring.zero
            total = semiring.times(total, self.transition_weight(index))
            state = self._target[index]

        if not self.is_final(state):
            return semiring.zero

        return semiring.times(total, self.final_weight(state))

    def __contains__(self, sequence: object) -> bool:
        """Return whether ``sequence`` is accepted, for ``in`` syntax."""
        if not isinstance(sequence, Sequence):
            return False

        return self.accepts(sequence)

    def __repr__(self) -> str:
        """Return a debugging representation."""
        weighted = f" {type(self._semiring).__name__}" if self.is_weighted else ""

        return (
            f"<{type(self).__name__} "
            f"states={self.num_states} "
            f"transitions={self.num_transitions} "
            f"alphabet={len(self._alphabet)}{weighted}>"
        )


__all__ = ["ROOT", "Automaton", "Transition", "flag_array", "index_array"]
