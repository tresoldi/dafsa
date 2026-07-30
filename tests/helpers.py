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
    from collections.abc import Hashable, Iterable, Sequence
    from typing import Any

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


def topological_order(automaton: Automaton) -> list[State]:
    """Return the states with every state before all of its successors.

    Kahn's algorithm. Note that the canonical breadth-first numbering ``freeze()``
    assigns is *not* topological — a state can be discovered early via one
    predecessor while another predecessor is discovered later — so this cannot be
    replaced by ``range(num_states)``.
    """
    indegree = dict.fromkeys(automaton.states(), 0)
    for transition in automaton.all_transitions():
        indegree[transition.target] += 1

    queue = [state for state, count in indegree.items() if count == 0]
    order: list[State] = []
    while queue:
        state = queue.pop()
        order.append(state)
        for transition in automaton.transitions(state):
            indegree[transition.target] -= 1
            if indegree[transition.target] == 0:
                queue.append(transition.target)

    assert len(order) == automaton.num_states, "graph is not acyclic"

    return order


def weighted_right_languages(
    automaton: Automaton,
) -> dict[State, frozenset[tuple[tuple[Token, ...], Hashable]]]:
    """Return each state's weighted right language, computed by brute force.

    A state's weighted right language is the map from every suffix it accepts to
    the weight it accepts that suffix with. It is the definition of what a state
    *is*, behaviourally: two states are equivalent precisely when theirs agree.

    This shares no logic with the construction's register — it works from the
    frozen arrays, bottom up — which is what makes it usable as an independent
    check of minimality rather than a restatement of the builder's own belief.
    """
    semiring = automaton.semiring
    tables: dict[State, dict[tuple[Token, ...], Any]] = {}

    for state in reversed(topological_order(automaton)):
        table: dict[tuple[Token, ...], Any] = {}
        if automaton.is_final(state):
            table[()] = automaton.final_weight(state)
        for index in automaton.transition_indices(state):
            tokens = automaton.transition_tokens(index)
            target = automaton.transition_target(index)
            weight_of = automaton.transition_weight(index)
            for suffix, weight in tables[target].items():
                table[(*tokens, *suffix)] = semiring.times(weight_of, weight)
        tables[state] = table

    return {
        state: frozenset((suffix, semiring.key(weight)) for suffix, weight in table.items())
        for state, table in tables.items()
    }


def assert_minimal(automaton: Automaton) -> None:
    """Assert no two states are behaviourally equivalent, and none is dead.

    Checked against weighted right languages rather than against state
    signatures, so a bug shared between the builder's register and a
    signature-based checker cannot hide here.
    """
    languages = weighted_right_languages(automaton)

    # Every state must be able to reach acceptance, or it is dead weight — except
    # the root, which exists whether or not the language is empty. The minimal
    # automaton for the empty language is exactly one non-accepting state.
    for state, language in languages.items():
        if state == ROOT:
            continue
        assert language, f"state {state} accepts nothing and should not exist"

    seen: dict[frozenset[tuple[tuple[Token, ...], Hashable]], State] = {}
    for state, language in languages.items():
        duplicate = seen.get(language)
        assert duplicate is None, (
            f"states {duplicate} and {state} have the same weighted right "
            f"language, so the automaton is not minimal"
        )
        seen[language] = state


def assert_deterministic_and_dense(automaton: Automaton) -> None:
    """Assert determinism, canonical numbering, and full reachability."""
    assert_csr_invariants(automaton)

    reached = {ROOT}
    frontier = [ROOT]
    while frontier:
        for transition in automaton.transitions(frontier.pop()):
            if transition.target not in reached:
                reached.add(transition.target)
                frontier.append(transition.target)

    assert reached == set(automaton.states()), "unreachable states survived freeze()"


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
        for index in automaton.transition_indices(state):
            # Every token the transition consumes, which is several once the
            # automaton has been compacted.
            tokens = automaton.transition_tokens(index)
            target = automaton.transition_target(index)
            stack.append((target, (*prefix, *tokens)))

    return found
