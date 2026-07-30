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

from dafsa import _algorithms
from dafsa._types import ROOT
from dafsa.semirings import BOOLEAN

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from dafsa._types import State, Symbol, Token
    from dafsa.alphabet import Alphabet
    from dafsa.semirings import Semiring

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


class Match(NamedTuple):
    """Everything known about one accepted sequence.

    Returned by :meth:`Automaton.match`. This is the resolution of issue #8: 1.0's
    ``lookup()`` returned only the final node and an uninterpretable cumulative
    weight, so the path a sequence took was not recoverable without dropping to a
    graph library.
    """

    sequence: tuple[Token, ...]
    states: tuple[State, ...]
    transitions: tuple[Transition, ...]
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
    labels
        One compound label per transition, or ``None`` when every transition
        consumes exactly one token. A label is a tuple of symbols whose first
        element equals the transition's entry in ``symbol``.

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
    the point of this representation. ``labels`` follows the same rule.

    Compound labels do not change the CSR layout. ``symbol`` continues to hold
    one symbol per transition — the *first* of its label — so determinism,
    ascending order within a state, and the binary search in :meth:`step` all
    work exactly as before. What changes is only how many tokens a transition
    consumes.
    """

    __slots__ = (
        "_alphabet",
        "_counts",
        "_final_weights",
        "_first",
        "_flags",
        "_labels",
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
        labels: list[tuple[Symbol, ...]] | None = None,
    ) -> None:
        self._alphabet = alphabet
        self._first = first
        self._symbol = symbol
        self._target = target
        self._flags = flags
        self._semiring = semiring
        self._transition_weights = transition_weights
        self._final_weights = final_weights
        self._labels = labels

        # Suffix counts are derived from the transitions, so they cannot be passed
        # in and be wrong. They are computed on first use rather than at
        # construction because membership testing does not need them, and an
        # O(transitions) pass is real work to charge a caller who never asks.
        self._counts: array[int] | None = None

    def _suffix_counts(self) -> array[int]:
        """Return suffix counts, computing them once on first use."""
        if self._counts is None:
            self._counts = _algorithms.suffix_counts(self)

        return self._counts

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
    def is_compact(self) -> bool:
        """Whether any transition consumes more than one token."""
        return self._labels is not None

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

    def transition_indices(self, state: State) -> range:
        """Return the indices of ``state``'s transitions, in symbol order.

        The index-based accessors below exist so that the dynamic programs can
        walk the arrays without allocating a :class:`Transition` per step.

        Parameters
        ----------
        state
            The state whose transitions to index.

        Returns
        -------
        range
            Indices into the transition arrays.
        """
        return range(self._first[state], self._first[state + 1])

    def transition_symbol(self, index: int) -> Symbol:
        """Return the first symbol consumed by the transition at ``index``."""
        return self._symbol[index]

    def transition_target(self, index: int) -> State:
        """Return the state entered by the transition at ``index``."""
        return self._target[index]

    def transition_label(self, index: int) -> tuple[Symbol, ...]:
        """Return every symbol consumed by the transition at ``index``.

        One symbol for an ordinary transition, several for a compacted one.

        Parameters
        ----------
        index
            A transition index.

        Returns
        -------
        tuple of Symbol
            The transition's label.
        """
        if self._labels is None:
            return (self._symbol[index],)

        return self._labels[index]

    def transition_tokens(self, index: int) -> tuple[Token, ...]:
        """Return the transition's label as caller-facing tokens.

        Parameters
        ----------
        index
            A transition index.

        Returns
        -------
        tuple of Token
            The tokens the transition consumes.
        """
        return self._alphabet.decode(self.transition_label(index))

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
        if self._labels is None:
            state = start
            for symbol in symbols:
                following = self.step(state, symbol)
                if following is None:
                    return None
                state = following

            return state

        # A compacted transition consumes several symbols at once, so the walk
        # advances by the label's length and must check that the label actually
        # matches what comes next rather than only its first symbol.
        pending = tuple(symbols)
        state = start
        position = 0
        while position < len(pending):
            index = self.transition_index(state, pending[position])
            if index is None:
                return None
            label = self._labels[index]
            if pending[position : position + len(label)] != label:
                return None
            position += len(label)
            state = self._target[index]

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
        position = 0
        while position < len(symbols):
            index = self.transition_index(state, symbols[position])
            if index is None:
                return semiring.zero
            label = self.transition_label(index)
            if symbols[position : position + len(label)] != label:
                return semiring.zero
            total = semiring.times(total, self.transition_weight(index))
            position += len(label)
            state = self._target[index]

        if not self.is_final(state):
            return semiring.zero

        return semiring.times(total, self.final_weight(state))

    def __contains__(self, sequence: object) -> bool:
        """Return whether ``sequence`` is accepted, for ``in`` syntax."""
        if not isinstance(sequence, Sequence):
            return False

        return self.accepts(sequence)

    def match(self, sequence: Sequence[Token]) -> Match | None:
        """Return the full path ``sequence`` takes, or ``None`` if it is rejected.

        Parameters
        ----------
        sequence
            The tokens to match.

        Returns
        -------
        Match or None
            The states visited, the transitions taken, and the weight.

        Examples
        --------
        >>> from dafsa import Dafsa
        >>> found = Dafsa.from_sequences(["tap"]).match("tap")
        >>> found.states
        (0, 1, 2, 3)
        >>> len(found.transitions)
        3
        """
        symbols = self._alphabet.try_encode(sequence)
        if symbols is None:
            return None

        semiring = self._semiring
        state = ROOT
        states = [state]
        transitions: list[Transition] = []
        weight = semiring.one
        position = 0

        while position < len(symbols):
            index = self.transition_index(state, symbols[position])
            if index is None:
                return None
            label = self.transition_label(index)
            if symbols[position : position + len(label)] != label:
                return None
            target = self._target[index]
            transitions.append(
                Transition(
                    state, symbols[position], target, self.transition_weight(index)
                )
            )
            weight = semiring.times(weight, self.transition_weight(index))
            position += len(label)
            state = target
            states.append(state)

        if not self.is_final(state):
            return None

        return Match(
            tuple(sequence),
            tuple(states),
            tuple(transitions),
            semiring.times(weight, self.final_weight(state)),
        )

    def paths(self, sequence: Sequence[Token]) -> Iterator[Match]:
        """Yield every accepting path for ``sequence``.

        A deterministic acceptor has at most one, so this yields nothing or one
        :class:`Match` and :meth:`match` is the direct way to ask. It exists so
        that code written against the transducers — where a single input can have
        several analyses — reads the same against an acceptor.

        Parameters
        ----------
        sequence
            The tokens to match.

        Yields
        ------
        Match
            Each accepting path.
        """
        found = self.match(sequence)
        if found is not None:
            yield found

    def longest_prefix_of(self, sequence: Sequence[Token]) -> tuple[Token, ...] | None:
        """Return the longest accepted prefix of ``sequence``.

        Useful for segmentation: repeatedly taking the longest accepted prefix of
        what remains is greedy longest-match tokenisation against a lexicon.

        Parameters
        ----------
        sequence
            The tokens to search within.

        Returns
        -------
        tuple of Token or None
            The longest prefix of ``sequence`` that the automaton accepts, or
            ``None`` if no prefix is accepted. The empty tuple is a valid answer
            when the root is accepting.

        Examples
        --------
        >>> from dafsa import Dafsa
        >>> lexicon = Dafsa.from_sequences(["can", "candle"])
        >>> lexicon.longest_prefix_of("candles")
        ('c', 'a', 'n', 'd', 'l', 'e')
        >>> lexicon.longest_prefix_of("cane")
        ('c', 'a', 'n')
        >>> lexicon.longest_prefix_of("dog") is None
        True
        """
        longest: tuple[Token, ...] | None = () if self.is_final(ROOT) else None
        symbols = self._alphabet.try_encode(sequence)
        if symbols is None:
            # Encode as far as the alphabet allows; an unknown token simply ends
            # the search rather than invalidating the prefixes before it.
            known = []
            for token in sequence:
                encoded = self._alphabet.try_encode((token,))
                if encoded is None:
                    break
                known.append(encoded[0])
            symbols = tuple(known)

        state = ROOT
        position = 0
        while position < len(symbols):
            index = self.transition_index(state, symbols[position])
            if index is None:
                break
            label = self.transition_label(index)
            if symbols[position : position + len(label)] != label:
                break
            position += len(label)
            state = self._target[index]
            if self.is_final(state):
                longest = tuple(sequence[:position])

        return longest

    def starts_with(self, prefix: Sequence[Token]) -> Iterator[tuple[Token, ...]]:
        """Yield the accepted sequences beginning with ``prefix``, in order.

        Costs the size of the answer, not the size of the language: the prefix is
        followed once to reach a state, and only that state's subtree is walked.
        This is the query an autocomplete is made of.

        Parameters
        ----------
        prefix
            The tokens every yielded sequence must start with.

        Yields
        ------
        tuple of Token
            Each accepted sequence extending ``prefix``, in the alphabet's order.

        Examples
        --------
        >>> from dafsa import Dafsa
        >>> automaton = Dafsa.from_sequences(["tap", "taps", "top"])
        >>> list(automaton.starts_with("ta"))
        [('t', 'a', 'p'), ('t', 'a', 'p', 's')]
        """
        symbols = self._alphabet.try_encode(prefix)
        if symbols is None:
            return

        state = ROOT
        emitted: list[Token] = []
        position = 0

        while position < len(symbols):
            index = self.transition_index(state, symbols[position])
            if index is None:
                return

            label = self.transition_label(index)
            remaining = symbols[position:]

            if len(remaining) < len(label):
                # The prefix stops in the middle of a compound label. Every
                # sequence through this transition consumes the whole label, so
                # the query is answered by descending anyway and reporting the
                # label in full — which is why this cannot be a plain `walk`,
                # since there is no state at the position the caller named.
                if label[: len(remaining)] != remaining:
                    return
                emitted.extend(self.transition_tokens(index))
                state = self._target[index]
                break

            if remaining[: len(label)] != label:
                return
            emitted.extend(self.transition_tokens(index))
            state = self._target[index]
            position += len(label)

        yield from _algorithms.iterate(self, state, tuple(emitted))

    # -- counting ----------------------------------------------------------

    def __len__(self) -> int:
        """Return how many distinct sequences are accepted.

        This is the size of the *language*, not of the input it was built from.
        1.0's ``count_sequences()`` returned the length of the input list,
        duplicates included, while describing a structure that is a set.

        Note that an automaton accepting nothing is therefore falsy.
        """
        return self._suffix_counts()[ROOT]

    def __iter__(self) -> Iterator[tuple[Token, ...]]:
        """Iterate over the accepted sequences in the alphabet's order.

        Lazy: memory is proportional to the longest sequence, not to the size of
        the language, so stopping early costs nothing for the rest.
        """
        return _algorithms.iterate(self)

    def rank(self, sequence: Sequence[Token]) -> int:
        """Return the position of ``sequence`` in iteration order.

        Together with :meth:`unrank` this makes the automaton a minimal perfect
        hash over its own language: every accepted sequence maps to a distinct
        integer in ``range(len(automaton))``, and back.

        Parameters
        ----------
        sequence
            An accepted sequence.

        Returns
        -------
        int
            Its zero-based position in :meth:`__iter__` order.

        Raises
        ------
        ValueError
            If the sequence is not accepted.

        Examples
        --------
        >>> from dafsa import Dafsa
        >>> automaton = Dafsa.from_sequences(["tap", "taps", "top"])
        >>> [automaton.rank(word) for word in ("tap", "taps", "top")]
        [0, 1, 2]
        """
        symbols = self._alphabet.try_encode(sequence)
        if symbols is None:
            message = "sequence is not accepted, so it has no rank"
            raise ValueError(message)

        return _algorithms.rank(self, symbols, self._suffix_counts())

    def unrank(self, position: int) -> tuple[Token, ...]:
        """Return the accepted sequence at ``position``.

        The inverse of :meth:`rank`, and cheaper than it looks: whole subtrees are
        skipped by their known sizes, so the cost tracks the sequence's length
        rather than its position.

        Parameters
        ----------
        position
            A zero-based position in :meth:`__iter__` order.

        Returns
        -------
        tuple of Token
            The sequence at that position.

        Raises
        ------
        IndexError
            If ``position`` is outside ``range(len(automaton))``.

        Examples
        --------
        >>> from dafsa import Dafsa
        >>> Dafsa.from_sequences(["tap", "taps", "top"]).unrank(2)
        ('t', 'o', 'p')
        """
        return _algorithms.unrank(self, position, self._suffix_counts())

    def suffix_count(self, state: State) -> int:
        """Return how many sequences are accepted from ``state``.

        Parameters
        ----------
        state
            The state to count from.

        Returns
        -------
        int
            The size of the state's right language.
        """
        return self._suffix_counts()[state]

    def topological_order(self) -> list[State]:
        """Return the states with every state before all of its successors.

        Exposed because it is the order any dynamic program over the structure
        needs, and because the canonical breadth-first numbering is *not*
        topological — a fact easy to assume otherwise and get wrong.

        Returns
        -------
        list of State
            The states, sources before targets.
        """
        return _algorithms.topological_order(self)

    def total_weight(self) -> Any:
        """Return the semiring sum of every accepted sequence's weight.

        For :data:`~dafsa.semirings.COUNTING` this is the total number of
        insertions, as distinct from ``len()``, which is the number of distinct
        sequences.

        Returns
        -------
        Any
            The total, or the semiring's ``zero`` for an empty language.

        Examples
        --------
        >>> from dafsa import Dafsa
        >>> from dafsa.semirings import COUNTING
        >>> automaton = Dafsa.from_sequences(["tip", "tip", "tap"], semiring=COUNTING)
        >>> len(automaton), automaton.total_weight()
        (2, 3)
        """
        return _algorithms.total_weight(self)

    def k_best(self, k: int) -> list[tuple[tuple[Token, ...], Any]]:
        """Return the ``k`` best accepted sequences with their weights.

        Only meaningful when the semiring is idempotent, so that ``plus`` selects
        a better weight instead of accumulating.

        Parameters
        ----------
        k
            How many to return.

        Returns
        -------
        list of tuple
            Up to ``k`` ``(sequence, weight)`` pairs, best first.

        Raises
        ------
        NotImplementedError
            If the semiring is not idempotent.

        Examples
        --------
        >>> from dafsa import Dafsa
        >>> from dafsa.semirings import TROPICAL
        >>> automaton = Dafsa.from_weighted(
        ...     [("tap", 2.0), ("taps", 0.5), ("top", 1.0)], semiring=TROPICAL
        ... )
        >>> automaton.k_best(2)
        [(('t', 'a', 'p', 's'), 0.5), (('t', 'o', 'p'), 1.0)]
        """
        return _algorithms.k_best(self, k)

    def __repr__(self) -> str:
        """Return a debugging representation."""
        weighted = f" {type(self._semiring).__name__}" if self.is_weighted else ""
        weighted += " compact" if self.is_compact else ""

        return (
            f"<{type(self).__name__} "
            f"states={self.num_states} "
            f"transitions={self.num_transitions} "
            f"alphabet={len(self._alphabet)}{weighted}>"
        )


__all__ = [
    "ROOT",
    "Automaton",
    "Match",
    "Transition",
    "flag_array",
    "index_array",
]
