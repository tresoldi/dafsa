"""The mutable side of build-then-freeze.

A :class:`Builder` accumulates states and transitions in growable parallel lists
— still no object per state — and ``freeze()`` turns them into the flat arrays of
:class:`~dafsa.automaton.Automaton`.

``freeze()`` is where the invariants the frozen core relies on are established
rather than assumed:

* **Canonical renumbering.** States are renumbered by breadth-first traversal
  from the root, following each state's transitions in ascending symbol order.
  Numbering therefore depends only on the automaton's shape, so two builders
  that describe the same automaton freeze to identical arrays, and there are no
  gaps in the ids.
* **Reachability.** States not reachable from the root are dropped. A builder
  that allocated a state and then abandoned it costs nothing in the result.
* **Determinism.** Two transitions on the same symbol from the same state are
  rejected when added.
* **Acyclicity.** A cycle is rejected at freeze time rather than left to hang a
  later traversal.

Every pass here is iterative. Nothing in this module recurses on the structure
of the automaton being built.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar, overload

from dafsa.automaton import ROOT, Automaton, Transition, flag_array, index_array
from dafsa.exceptions import AcyclicityError, DeterminismError
from dafsa.semirings import BOOLEAN

if TYPE_CHECKING:
    from collections.abc import Iterator

    from dafsa._types import State, Symbol
    from dafsa.alphabet import Alphabet
    from dafsa.semirings import Semiring

#: The concrete automaton class a builder freezes into.
A = TypeVar("A", bound=Automaton)

_FINAL = 1

# Colours for the iterative cycle check.
_WHITE = 0
_GREY = 1
_BLACK = 2


class Builder:
    """Accumulates states and transitions, then freezes them.

    The root state is created automatically and is always state
    :data:`~dafsa.automaton.ROOT`.

    Parameters
    ----------
    alphabet
        The alphabet whose symbols the transitions will use.
    semiring
        The semiring weights belong to. Defaults to
        :data:`~dafsa.semirings.BOOLEAN`, which is the unweighted case.

    Examples
    --------
    >>> from dafsa.alphabet import Alphabet
    >>> alphabet = Alphabet("ab")
    >>> builder = Builder(alphabet)
    >>> state = builder.new_state()
    >>> builder.add_transition(0, alphabet.id("a"), state)
    >>> builder.set_final(state)
    >>> automaton = builder.freeze()
    >>> "a" in automaton, "b" in automaton
    (True, False)
    """

    __slots__ = (
        "_alphabet",
        "_final",
        "_final_weights",
        "_labels",
        "_semiring",
        "_symbols",
        "_targets",
        "_weights",
    )

    def __init__(self, alphabet: Alphabet, semiring: Semiring[Any] = BOOLEAN) -> None:
        self._alphabet = alphabet
        self._semiring = semiring
        self._symbols: list[list[Symbol]] = [[]]
        self._targets: list[list[State]] = [[]]
        self._weights: list[list[Any]] = [[]]
        self._labels: list[list[tuple[Symbol, ...]]] = [[]]
        self._final: list[bool] = [False]
        self._final_weights: list[Any] = [semiring.zero]

    @property
    def alphabet(self) -> Alphabet:
        """The alphabet this builder's symbols refer to."""
        return self._alphabet

    @property
    def semiring(self) -> Semiring[Any]:
        """The semiring this builder's weights belong to."""
        return self._semiring

    @property
    def num_states(self) -> int:
        """The number of states allocated so far, reachable or not."""
        return len(self._final)

    def new_state(self) -> State:
        """Allocate a state with no transitions.

        Returns
        -------
        State
            The new state's id, valid only within this builder: ``freeze()``
            renumbers.
        """
        self._symbols.append([])
        self._targets.append([])
        self._weights.append([])
        self._labels.append([])
        self._final.append(False)
        self._final_weights.append(self._semiring.zero)

        return len(self._final) - 1

    def add_transition(
        self,
        source: State,
        symbol: Symbol,
        target: State,
        weight: Any = None,
        label: tuple[Symbol, ...] | None = None,
    ) -> None:
        """Add a transition.

        Parameters
        ----------
        source
            The state the transition leaves.
        symbol
            The symbol consumed.
        target
            The state the transition enters.
        weight
            The transition's weight. ``None`` means the semiring's ``one``, which
            is the identity for combining along a path and so contributes
            nothing.
        label
            Every symbol the transition consumes, for a compacted transition.
            ``None`` means the transition consumes ``symbol`` alone. The first
            element must be ``symbol``, because determinism and ordering are keyed
            on it.

        Raises
        ------
        IndexError
            If ``source`` or ``target`` is not an allocated state.
        ValueError
            If ``symbol`` is not a symbol of the alphabet, or if ``label`` does
            not begin with it.
        DeterminismError
            If ``source`` already has a transition on ``symbol``.
        """
        self._check_state(source)
        self._check_state(target)

        if not 0 <= symbol < len(self._alphabet):
            message = f"symbol not in alphabet: {symbol}"
            raise ValueError(message)

        symbols = self._symbols[source]
        if symbol in symbols:
            token = self._alphabet.token(symbol)
            message = (
                f"state {source} already has a transition on {token!r} "
                f"(symbol {symbol})"
            )
            raise DeterminismError(message)

        if label is None:
            label = (symbol,)
        elif not label or label[0] != symbol:
            message = f"label {label!r} does not begin with symbol {symbol}"
            raise ValueError(message)

        symbols.append(symbol)
        self._targets[source].append(target)
        self._weights[source].append(self._semiring.one if weight is None else weight)
        self._labels[source].append(label)

    def set_final(
        self,
        state: State,
        *,
        final: bool = True,
        weight: Any = None,
    ) -> None:
        """Mark ``state`` as accepting, or not.

        Parameters
        ----------
        state
            The state to mark.
        final
            Whether the state accepts. Keyword-only, so call sites read as
            ``set_final(q)`` or ``set_final(q, final=False)``.
        weight
            The state's final weight. ``None`` means the semiring's ``one``.
            Ignored when ``final`` is false, which resets the weight to ``zero``.

        Raises
        ------
        IndexError
            If ``state`` is not an allocated state.
        """
        self._check_state(state)
        self._final[state] = final
        if final:
            self._final_weights[state] = (
                self._semiring.one if weight is None else weight
            )
        else:
            self._final_weights[state] = self._semiring.zero

    def final_weight(self, state: State) -> Any:
        """Return ``state``'s final weight.

        Parameters
        ----------
        state
            The state to inspect.

        Returns
        -------
        Any
            The final weight, or the semiring's ``zero`` if the state does not
            accept. Returning ``zero`` rather than raising is what lets a caller
            accumulate with ``plus`` without a special case for the first time a
            sequence reaches a state.
        """
        self._check_state(state)

        return self._final_weights[state]

    def is_final(self, state: State) -> bool:
        """Return whether ``state`` is currently marked accepting.

        Parameters
        ----------
        state
            The state to inspect.

        Returns
        -------
        bool
            Whether the state accepts.
        """
        self._check_state(state)

        return self._final[state]

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
        self._check_state(state)
        for symbol, target, weight, _label in self._ordered(state):
            yield Transition(state, symbol, target, weight)

    @overload
    def freeze(self) -> Automaton: ...

    @overload
    def freeze(self, factory: type[A]) -> A: ...

    def freeze(self, factory: type[Automaton] = Automaton) -> Automaton:
        """Validate, renumber, and flatten into a frozen automaton.

        Parameters
        ----------
        factory
            The class to instantiate. Defaults to :class:`~dafsa.automaton.Automaton`;
            the structures pass themselves so that a frozen ``Dafsa`` is a
            ``Dafsa`` and not merely an automaton that happens to be minimal.

        Returns
        -------
        Automaton
            The frozen automaton. The builder is left usable, so it can be
            frozen again after further additions.

        Raises
        ------
        AcyclicityError
            If the reachable transitions contain a cycle.
        """
        # Sorted once and reused by all three passes below; sorting per pass
        # would triple the cost of the hot path for no benefit.
        outgoing = [self._ordered(state) for state in range(len(self._final))]

        order = self._canonical_order(outgoing)
        self._check_acyclic(order, outgoing)
        renumbered = {old: new for new, old in enumerate(order)}

        first = index_array()
        symbol = index_array()
        target = index_array()
        flags = flag_array()
        transition_weights: list[Any] = []
        final_weights: list[Any] = []
        labels: list[tuple[Symbol, ...]] = []

        first.append(0)
        for old in order:
            for out_symbol, out_target, out_weight, out_label in outgoing[old]:
                symbol.append(out_symbol)
                target.append(renumbered[out_target])
                transition_weights.append(out_weight)
                labels.append(out_label)
            first.append(len(symbol))
            flags.append(_FINAL if self._final[old] else 0)
            final_weights.append(self._final_weights[old])

        return factory(
            self._alphabet,
            first,
            symbol,
            target,
            flags,
            self._semiring,
            self._trivial_or(transition_weights),
            self._trivial_or(final_weights, skip=self._semiring.zero),
            labels if any(len(entry) > 1 for entry in labels) else None,
        )

    def _trivial_or(self, weights: list[Any], skip: Any = None) -> list[Any] | None:
        """Return ``weights``, or ``None`` when every entry is trivial.

        A list of nothing but ``one`` carries no information, and storing it would
        cost memory on every plain acceptor. ``skip`` names an additional value to
        treat as trivial — ``zero`` for final weights, since a non-accepting state
        holds ``zero`` and says nothing about weighting.

        Parameters
        ----------
        weights
            The weights to inspect.
        skip
            An extra value to treat as carrying no information, or ``None``.

        Returns
        -------
        list or None
            ``None`` if every weight is trivial, otherwise the list unchanged.
        """
        semiring = self._semiring
        trivial = {semiring.key(semiring.one)}
        if skip is not None:
            trivial.add(semiring.key(skip))

        if all(semiring.key(weight) in trivial for weight in weights):
            return None

        return weights

    # -- internals ---------------------------------------------------------

    def _check_state(self, state: State) -> None:
        """Raise if ``state`` was never allocated.

        Parameters
        ----------
        state
            The state to validate.

        Raises
        ------
        IndexError
            If ``state`` is out of range. Negative indices are rejected too,
            since they would silently address a state from the other end.
        """
        if not 0 <= state < len(self._final):
            message = f"no such state: {state}"
            raise IndexError(message)

    def _ordered(self, state: State) -> list[tuple[Symbol, State, Any, Any]]:
        """Return ``state``'s transitions as tuples, symbol-ascending.

        Parameters
        ----------
        state
            The state whose transitions to order.

        Returns
        -------
        list of tuple
            ``(symbol, target, weight, label)`` tuples, sorted by symbol. Symbols
            are unique per state, so sorting on the first element alone is a total
            order and never has to compare weights — which may not be orderable.
        """
        entries = zip(
            self._symbols[state],
            self._targets[state],
            self._weights[state],
            self._labels[state],
            strict=True,
        )

        return sorted(entries, key=lambda entry: entry[0])

    @staticmethod
    def _canonical_order(
        outgoing: list[list[tuple[Symbol, State, Any, Any]]],
    ) -> list[State]:
        """Return the reachable states in canonical (breadth-first) order.

        Discovery follows each state's transitions in ascending symbol order, so
        the result depends only on the shape of the automaton and not on the
        order in which the builder happened to be driven.

        Parameters
        ----------
        outgoing
            Per-state transitions as ``(symbol, target)``, symbol-ascending.

        Returns
        -------
        list of State
            The reachable states, root first.
        """
        order: list[State] = [ROOT]
        seen = {ROOT}

        # An index into `order` used as a queue head, so nothing is popped from
        # the front of a list.
        head = 0
        while head < len(order):
            state = order[head]
            head += 1
            for _, target, _weight, _label in outgoing[state]:
                if target not in seen:
                    seen.add(target)
                    order.append(target)

        return order

    def _check_acyclic(
        self,
        order: list[State],
        outgoing: list[list[tuple[Symbol, State, Any, Any]]],
    ) -> None:
        """Raise if the states in ``order`` contain a cycle.

        Iterative depth-first search with the usual three colours: a transition
        into a grey state is a back edge, and a back edge is a cycle. A
        transition into a black state is not — converging paths are ordinary in
        a minimized automaton, and a check that flagged them would reject every
        interesting structure this library builds.

        Parameters
        ----------
        order
            The states to check, which must be closed under transitions.
        outgoing
            Per-state transitions as ``(symbol, target)``, symbol-ascending.

        Raises
        ------
        AcyclicityError
            If a cycle is reachable from any state in ``order``.
        """
        colour = dict.fromkeys(order, _WHITE)

        for start in order:
            if colour[start] != _WHITE:
                continue

            colour[start] = _GREY
            # Each frame is a state and how far through its transitions we are.
            stack: list[tuple[State, int]] = [(start, 0)]

            while stack:
                state, index = stack.pop()
                transitions = outgoing[state]
                if index == len(transitions):
                    colour[state] = _BLACK
                    continue

                stack.append((state, index + 1))
                symbol, target, _weight, _label = transitions[index]

                if colour[target] == _GREY:
                    token = self._alphabet.token(symbol)
                    message = (
                        f"transition on {token!r} closes a cycle "
                        f"back into state {target}"
                    )
                    raise AcyclicityError(message)

                if colour[target] == _WHITE:
                    colour[target] = _GREY
                    stack.append((target, 0))

    def __repr__(self) -> str:
        """Return a debugging representation."""
        transitions = sum(len(symbols) for symbols in self._symbols)

        return (
            f"<{type(self).__name__} "
            f"states={self.num_states} "
            f"transitions={transitions}>"
        )


__all__ = ["Builder"]
