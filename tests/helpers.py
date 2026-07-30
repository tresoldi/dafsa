"""Shared test helpers.

The point of :func:`build_trie` is to exercise the core without depending on the
structures that build on it. It is a deliberately naive prefix-tree insertion —
linear scan for an existing transition, no minimization, no register — so that
when a core test fails, the core is what failed.
"""

from __future__ import annotations

from itertools import pairwise
from typing import TYPE_CHECKING

from dafsa._builder import Builder
from dafsa.alphabet import Alphabet
from dafsa.automaton import ROOT

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from dafsa._types import State, Symbol, Token
    from dafsa.automaton import Automaton


def build_trie(sequences: Iterable[Sequence[Token]]) -> Automaton:
    """Build a trie over ``sequences`` using only the core."""
    materialised = [tuple(sequence) for sequence in sequences]
    alphabet = Alphabet.from_sequences(materialised)
    builder = Builder(alphabet)

    for sequence in materialised:
        state = ROOT
        for token in sequence:
            state = _descend(builder, state, alphabet.id(token))
        builder.set_final(state)

    return builder.freeze()


def _descend(builder: Builder, state: State, symbol: Symbol) -> State:
    """Return the target of ``symbol`` from ``state``, creating it if absent."""
    for transition in builder.transitions(state):
        if transition.symbol == symbol:
            return transition.target

    target = builder.new_state()
    builder.add_transition(state, symbol, target)

    return target


def csr(automaton: Automaton) -> tuple[list[int], list[int], list[int], list[int]]:
    """Return an automaton's raw CSR arrays, for invariant checks."""
    return (
        list(automaton._first),
        list(automaton._symbol),
        list(automaton._target),
        list(automaton._flags),
    )


def assert_csr_invariants(automaton: Automaton) -> None:
    """Assert the structural invariants the frozen core promises."""
    first, symbol, target, flags = csr(automaton)

    assert len(first) == automaton.num_states + 1
    assert len(flags) == automaton.num_states
    assert len(symbol) == len(target) == automaton.num_transitions

    assert first[0] == 0
    assert first[-1] == automaton.num_transitions
    assert all(a <= b for a, b in pairwise(first))

    for state in automaton.states():
        window = symbol[first[state] : first[state + 1]]
        # Strictly ascending: sorted for the binary search, unique for determinism.
        assert all(a < b for a, b in pairwise(window))

    assert all(0 <= item < automaton.num_states for item in target)
    assert all(0 <= item < len(automaton.alphabet) for item in symbol)


def accepted_sequences(automaton: Automaton) -> set[tuple[Token, ...]]:
    """Enumerate everything ``automaton`` accepts, by brute-force traversal.

    This is the independent reference the core is checked against. It walks every
    path with an explicit stack, so it shares no code with the library beyond the
    transition accessors.
    """
    found: set[tuple[Token, ...]] = set()
    stack: list[tuple[State, tuple[Token, ...]]] = [(ROOT, ())]

    while stack:
        state, prefix = stack.pop()
        if automaton.is_final(state):
            found.add(prefix)
        for transition in automaton.transitions(state):
            token = automaton.alphabet.token(transition.symbol)
            stack.append((transition.target, (*prefix, token)))

    return found
