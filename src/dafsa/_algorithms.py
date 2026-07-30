"""Dynamic programming over the frozen automaton.

Everything here exploits the same fact: a frozen automaton is a directed acyclic
graph, so any quantity defined recursively over a state's successors can be
computed in one pass in reverse topological order. Three such quantities matter.

**Suffix counts.** How many sequences each state accepts. This is what turns the
automaton from a set into an index: with counts in hand, ``len()`` is a lookup,
and the *i*-th accepted sequence can be found without enumerating the first
*i* — the minimal-perfect-hash property that makes minimal acyclic automata
interesting beyond their size.

**Total weight.** The semiring sum over every accepted sequence, which is the
weighted generalisation of the count.

**Best sequences.** Selection under an idempotent semiring, where ``plus`` picks
a winner rather than accumulating.

Every function is iterative. The recursions are in the definitions, not in the
implementations.
"""

from __future__ import annotations

from array import array
from heapq import heappush, heappushpop
from typing import TYPE_CHECKING, Any, TypeVar

from dafsa._types import ROOT

if TYPE_CHECKING:
    from collections.abc import Iterator

    from dafsa._types import State, Symbol, Token
    from dafsa.automaton import Automaton
    from dafsa.semirings import Semiring

#: The concrete automaton class a compaction freezes into.
A = TypeVar("A", bound="Automaton")

_COUNT_TYPECODE = "q"

# Colours for the iterative post-order traversal.
_UNSEEN = 0
_OPEN = 1
_CLOSED = 2


def topological_order(automaton: Automaton) -> list[State]:
    """Return the states with every state preceding all of its successors.

    Iterative depth-first post-order, reversed. Note that the canonical
    breadth-first numbering ``freeze()`` assigns is *not* topological — a state
    can be discovered early through one predecessor while another predecessor is
    discovered later — so ``range(num_states)`` will not do.

    Parameters
    ----------
    automaton
        The automaton to order. Must be acyclic, which ``freeze()`` guarantees.

    Returns
    -------
    list of State
        The states, sources before targets.
    """
    colour = bytearray(automaton.num_states)
    post: list[State] = []

    for start in automaton.states():
        if colour[start] != _UNSEEN:
            continue

        colour[start] = _OPEN
        stack: list[tuple[State, int]] = [(start, 0)]
        while stack:
            state, index = stack.pop()
            outgoing = list(automaton.transitions(state))
            if index == len(outgoing):
                colour[state] = _CLOSED
                post.append(state)
                continue

            stack.append((state, index + 1))
            target = outgoing[index].target
            if colour[target] == _UNSEEN:
                colour[target] = _OPEN
                stack.append((target, 0))

    post.reverse()

    return post


def suffix_counts(automaton: Automaton) -> array[int]:
    """Return, for each state, how many sequences it accepts.

    A state accepts the empty suffix if it is final, plus everything its
    successors accept. Because the automaton is deterministic, no suffix is
    reachable by two paths from the same state, so the sum needs no
    deduplication.

    Parameters
    ----------
    automaton
        The automaton to count over.

    Returns
    -------
    array of int
        ``counts[q]`` is the number of sequences accepted from ``q``.
        ``counts[ROOT]`` is the size of the whole language.
    """
    counts = array(_COUNT_TYPECODE, bytes(8 * automaton.num_states))

    for state in reversed(topological_order(automaton)):
        total = 1 if automaton.is_final(state) else 0
        for transition in automaton.transitions(state):
            total += counts[transition.target]
        counts[state] = total

    return counts


def total_weight(automaton: Automaton) -> Any:
    """Return the semiring sum of the weights of every accepted sequence.

    The weighted generalisation of :func:`suffix_counts`: where counting adds
    one per accepted sequence, this combines each sequence's weight with the
    semiring's ``plus``.

    Parameters
    ----------
    automaton
        The automaton to total.

    Returns
    -------
    Any
        The total, or the semiring's ``zero`` for an empty language.
    """
    semiring = automaton.semiring
    totals: list[Any] = [semiring.zero] * automaton.num_states

    for state in reversed(topological_order(automaton)):
        total = automaton.final_weight(state)
        for transition in automaton.transitions(state):
            total = semiring.plus(
                total, semiring.times(transition.weight, totals[transition.target])
            )
        totals[state] = total

    return totals[ROOT]


def iterate(
    automaton: Automaton,
    start: State = ROOT,
    prefix: tuple[Token, ...] = (),
) -> Iterator[tuple[Token, ...]]:
    """Yield accepted sequences in the alphabet's order.

    Depth-first with an explicit stack and a shared buffer, so memory is
    proportional to the longest sequence rather than to the size of the language,
    and a caller can stop early without having paid for the rest.

    Parameters
    ----------
    automaton
        The automaton to enumerate.
    start
        The state to enumerate from. Defaults to the root, giving the whole
        language.
    prefix
        Tokens to prepend to each result — the path already taken to reach
        ``start``. Enumerating a subtree and prepending its prefix is what makes
        a prefix query cost the size of its answer rather than the size of the
        language.

    Yields
    ------
    tuple of Token
        Each accepted sequence, in ascending order.
    """
    buffer: list[Token] = list(prefix)

    if automaton.is_final(start):
        yield tuple(buffer)

    # Each frame is a state, how far through its transitions we are, and how many
    # tokens entering it appended that leaving it must remove. A compacted
    # transition appends several at once, so a boolean will not do.
    stack: list[tuple[State, int, int]] = [(start, 0, 0)]
    while stack:
        state, offset, consumed = stack.pop()
        indices = automaton.transition_indices(state)
        if offset == len(indices):
            if consumed:
                del buffer[len(buffer) - consumed :]
            continue

        stack.append((state, offset + 1, consumed))
        index = indices[offset]
        tokens = automaton.transition_tokens(index)
        buffer.extend(tokens)
        target = automaton.transition_target(index)
        if automaton.is_final(target):
            yield tuple(buffer)
        stack.append((target, 0, len(tokens)))


def rank(automaton: Automaton, symbols: tuple[Symbol, ...], counts: array[int]) -> int:
    """Return how many accepted sequences sort before ``symbols``.

    Walks the sequence, and at each step adds everything that branches off
    earlier: the prefix itself if it is accepted (a prefix sorts before anything
    extending it), and the whole subtree under every smaller symbol.

    Parameters
    ----------
    automaton
        The automaton to rank within.
    symbols
        The encoded sequence, which must be accepted.
    counts
        Suffix counts, as returned by :func:`suffix_counts`.

    Returns
    -------
    int
        The sequence's zero-based position in :func:`iterate` order.

    Raises
    ------
    ValueError
        If the sequence is not accepted, and therefore has no position.
    """
    position = 0
    state = ROOT
    consumed = 0

    while consumed < len(symbols):
        if automaton.is_final(state):
            position += 1

        found = None
        for index in automaton.transition_indices(state):
            if automaton.transition_symbol(index) == symbols[consumed]:
                label = automaton.transition_label(index)
                if symbols[consumed : consumed + len(label)] != label:
                    break
                found = automaton.transition_target(index)
                consumed += len(label)
                break
            position += counts[automaton.transition_target(index)]

        if found is None:
            message = "sequence is not accepted, so it has no rank"
            raise ValueError(message)
        state = found

    if not automaton.is_final(state):
        message = "sequence is not accepted, so it has no rank"
        raise ValueError(message)

    return position


def unrank(
    automaton: Automaton, position: int, counts: array[int]
) -> tuple[Token, ...]:
    """Return the accepted sequence at ``position``, without enumerating.

    The inverse of :func:`rank`. Descends the automaton, at each state skipping
    whole subtrees whose sizes are already known, so the cost depends on the
    sequence's length rather than on its position.

    Parameters
    ----------
    automaton
        The automaton to index into.
    position
        A zero-based position in :func:`iterate` order.
    counts
        Suffix counts, as returned by :func:`suffix_counts`.

    Returns
    -------
    tuple of Token
        The sequence at that position.

    Raises
    ------
    IndexError
        If ``position`` is outside the language.
    """
    if not 0 <= position < counts[ROOT]:
        message = f"position out of range: {position}"
        raise IndexError(message)

    remaining = position
    state = ROOT
    tokens: list[Token] = []

    while True:
        if automaton.is_final(state):
            if remaining == 0:
                return tuple(tokens)
            remaining -= 1

        for index in automaton.transition_indices(state):
            target = automaton.transition_target(index)
            size = counts[target]
            if remaining < size:
                tokens.extend(automaton.transition_tokens(index))
                state = target
                break
            remaining -= size
        else:  # pragma: no cover - counts guarantee a branch is always found
            message = "suffix counts are inconsistent with the transitions"
            raise AssertionError(message)


def k_best(automaton: Automaton, k: int) -> list[tuple[tuple[Token, ...], Any]]:
    """Return the ``k`` best accepted sequences, best first.

    "Best" is defined by the semiring: for an idempotent semiring, ``plus``
    selects a winner rather than accumulating, and the winner is the better
    weight. Non-idempotent semirings have no such notion — under
    :data:`~dafsa.semirings.COUNTING`, ``plus(2, 3)`` is ``5``, not a preference —
    so they are refused rather than given an arbitrary ordering.

    Parameters
    ----------
    automaton
        The automaton to search.
    k
        How many sequences to return. Non-positive values return nothing.

    Returns
    -------
    list of tuple
        Up to ``k`` ``(sequence, weight)`` pairs, best first.

    Raises
    ------
    NotImplementedError
        If the semiring is not idempotent.

    Notes
    -----
    This examines every accepted sequence, keeping only ``k`` at a time, so it is
    O(*n* log *k*) in time and O(*k*) in memory. It does not prune, and with the
    weight placement the dictionary structures use it *cannot*: every transition
    weight is the semiring's ``one`` and a sequence's whole weight sits on its
    final state, so no prefix carries information about how good its extensions
    might be. Weight pushing redistributes weight towards the front and is what
    would make a genuinely pruning best-first search possible.
    """
    semiring = automaton.semiring
    if not semiring.idempotent:
        message = (
            f"{type(semiring).__name__} is not idempotent, so its `plus` does not "
            f"select a best weight; k_best is undefined for it"
        )
        raise NotImplementedError(message)

    if k <= 0:
        return []

    # A min-heap ordered worst-first, so the worst candidate is what gets evicted.
    heap: list[_Worst] = []
    for sequence in iterate(automaton):
        candidate = _Worst(automaton.weight(sequence), sequence, semiring)
        if len(heap) < k:
            heappush(heap, candidate)
        else:
            heappushpop(heap, candidate)

    return [(entry.sequence, entry.weight) for entry in sorted(heap, reverse=True)]


def absorbable(automaton: Automaton) -> list[bool]:
    """Return which states can be folded into the transition that reaches them.

    A state disappears into its incoming edge when every path through it is
    forced: it has exactly one way in, exactly one way out, and does not accept.
    Then ``p -a-> q -b-> r`` carries the same language as ``p -ab-> r``, and ``q``
    holds no information.

    The predicate that matters is ``in_degree == 1``, **not** ``<= 1``. A state
    with no incoming edge — the root — has nothing to be folded into, and it is
    precisely that case which 1.0 failed to exclude: its ``_joining_round``
    skipped candidates with ``targets[node_id] > 1`` and then indexed
    ``[edge for edge in edges if edge["target"] == node_id][0]``, so the root
    raised ``IndexError`` the moment it had a single outgoing edge. That is
    issues #18 and #14, and the fix is this one comparison.

    Parameters
    ----------
    automaton
        The automaton to analyse.

    Returns
    -------
    list of bool
        Indexed by state.

    Notes
    -----
    1.0 also required the *predecessor* to have exactly one outgoing edge, and
    this does not. The condition is unnecessary: a compacted label keeps the
    first symbol of the edge it replaces, so the predecessor's other transitions
    remain distinguishable and determinism is preserved. Dropping it compacts
    strictly more.
    """
    in_degree = [0] * automaton.num_states
    for state in automaton.states():
        for index in automaton.transition_indices(state):
            in_degree[automaton.transition_target(index)] += 1

    return [
        in_degree[state] == 1
        and automaton.out_degree(state) == 1
        and not automaton.is_final(state)
        for state in automaton.states()
    ]


def compact(automaton: Automaton, factory: type[A]) -> A:
    """Collapse forced chains of states into single compound transitions.

    Every chain is collapsed in one pass. 1.0 needed repeated rounds because its
    de-duplication guard iterated a dict and compared the literal keys
    ``"source"`` and ``"target"``, which meant at most one join happened per
    round; the whole thing converged only through O(n) rounds of O(n²) work.

    Parameters
    ----------
    automaton
        The automaton to compact.
    factory
        The class to freeze the result into.

    Returns
    -------
    Automaton
        A new frozen automaton. The input is untouched, so there is no way for
        reported counts to describe a different graph from the one being
        queried — which is what 1.0's in-place ``condense()`` plus its
        ``lookup_nodes`` deep copy allowed.
    """
    # Imported here rather than at module scope: the builder imports the
    # automaton, which imports this module.
    from dafsa._builder import Builder  # noqa: PLC0415

    folds = absorbable(automaton)
    semiring = automaton.semiring
    survivors = [state for state in automaton.states() if not folds[state]]
    renumbered = {old: new for new, old in enumerate(survivors)}

    builder = Builder(automaton.alphabet, semiring)
    for _ in range(len(survivors) - 1):
        builder.new_state()

    for state in survivors:
        for index in automaton.transition_indices(state):
            label = list(automaton.transition_label(index))
            weight = automaton.transition_weight(index)
            target = automaton.transition_target(index)

            while folds[target]:
                (following,) = automaton.transition_indices(target)
                label.extend(automaton.transition_label(following))
                weight = semiring.times(weight, automaton.transition_weight(following))
                target = automaton.transition_target(following)

            builder.add_transition(
                renumbered[state],
                label[0],
                renumbered[target],
                weight,
                tuple(label),
            )
        if automaton.is_final(state):
            builder.set_final(renumbered[state], weight=automaton.final_weight(state))

    return builder.freeze(factory)


def minimize(automaton: Automaton, factory: type[A]) -> A:
    """Return the minimal automaton accepting the same weighted language.

    Revuz's algorithm: because the automaton is acyclic, states can be settled in
    reverse topological order, and by the time a state is reached every successor
    already stands for its equivalence class. Two states then merge exactly when
    their signatures agree.

    The dictionary structures do not need this — their construction minimizes as
    it goes. It exists for automata that arrive already built, which is what
    subset construction produces when a transducer is projected onto one side.

    Parameters
    ----------
    automaton
        The automaton to minimize. Must be deterministic and acyclic.
    factory
        The class to freeze the result into.

    Returns
    -------
    Automaton
        The minimal equivalent automaton.
    """
    # Imported here rather than at module scope: the builder imports the
    # automaton, which imports this module.
    from dafsa._builder import Builder  # noqa: PLC0415

    semiring = automaton.semiring
    register: dict[tuple[Any, ...], State] = {}
    canonical: dict[State, State] = {}

    for state in reversed(topological_order(automaton)):
        final = automaton.is_final(state)
        signature = (
            final,
            semiring.key(automaton.final_weight(state)) if final else None,
            tuple(
                (
                    automaton.transition_label(index),
                    canonical[automaton.transition_target(index)],
                    semiring.key(automaton.transition_weight(index)),
                )
                for index in automaton.transition_indices(state)
            ),
        )
        canonical[state] = register.setdefault(signature, state)

    survivors = sorted(set(canonical.values()))
    renumbered = {old: new for new, old in enumerate(survivors)}

    builder = Builder(automaton.alphabet, semiring)
    for _ in range(len(survivors) - 1):
        builder.new_state()

    # The root must stay the root; freeze() prunes whatever the swap orphans.
    swap = dict(renumbered)
    root = canonical[ROOT]
    swap[root], swap[survivors[0]] = renumbered[survivors[0]], renumbered[root]

    for old in survivors:
        for index in automaton.transition_indices(old):
            label = automaton.transition_label(index)
            builder.add_transition(
                swap[old],
                label[0],
                swap[canonical[automaton.transition_target(index)]],
                automaton.transition_weight(index),
                label,
            )
        if automaton.is_final(old):
            builder.set_final(swap[old], weight=automaton.final_weight(old))

    return builder.freeze(factory)


class _Worst:
    """Orders weighted sequences worst-first, for eviction from a bounded heap.

    Comparison goes through the semiring's ``plus`` rather than ``<``, because a
    caller's weights need not be numbers or even orderable. Ties break on the
    sequence so the result is deterministic; the comparison is on tokens where
    they are orderable and on repr otherwise, since a tie-break only has to be
    consistent.
    """

    __slots__ = ("_semiring", "sequence", "weight")

    def __init__(
        self,
        weight: Any,
        sequence: tuple[Token, ...],
        semiring: Semiring[Any],
    ) -> None:
        self.weight = weight
        self.sequence = sequence
        self._semiring = semiring

    def __lt__(self, other: _Worst) -> bool:
        """Return whether this entry is the worse of the two."""
        mine, theirs = self.weight, other.weight
        if self._semiring.key(mine) != self._semiring.key(theirs):
            # Under an idempotent semiring, `plus` returns the better weight.
            return self._semiring.key(self._semiring.plus(mine, theirs)) == (
                self._semiring.key(theirs)
            )

        return _tie_break(self.sequence) > _tie_break(other.sequence)


def _tie_break(sequence: tuple[Token, ...]) -> tuple[str, ...]:
    """Return a consistently orderable form of ``sequence`` for tie-breaking."""
    return tuple(f"{token!r}" for token in sequence)


__all__ = [
    "absorbable",
    "compact",
    "iterate",
    "k_best",
    "minimize",
    "rank",
    "suffix_counts",
    "topological_order",
    "total_weight",
    "unrank",
]
