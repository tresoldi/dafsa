"""Acyclic weighted finite-state transducers.

An acceptor answers whether a sequence is in a set. A transducer relates one
sequence to another — surface form to lemma, orthography to phonemes, one
notation to another — which is most of what finite-state machinery is used for in
linguistics.

The representation needs no new core. A transducer transition carries an input
symbol and an output symbol, and a *pair of tokens is itself a token*: hashable,
and therefore something an ``Alphabet`` can number. So an
``Fst`` is an ordinary ``Automaton`` whose alphabet is
an alphabet of pairs, and it inherits minimization, counting, compaction and
export unchanged.

One consequence is worth stating. Determinism in the core means one transition
per *pair* per state, not one per input symbol, so a state may well have both
``a:x`` and ``a:y``. That is exactly the ambiguity a transducer is allowed to
have — one input, several analyses — and it is why ``Fst.apply`` returns a
list.

``EPSILON`` marks a side that consumes or emits nothing, so that a transducer
can relate sequences of different lengths.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from dafsa import _algorithms
from dafsa._builder import Builder
from dafsa._types import ROOT
from dafsa.alphabet import Alphabet
from dafsa.automaton import Automaton
from dafsa.exceptions import DeterminismError
from dafsa.semirings import BOOLEAN
from dafsa.structures import Dafsa

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from dafsa._types import State, Token
    from dafsa.semirings import Semiring


class _Epsilon:
    """The empty side of a transducer transition."""

    __slots__ = ()

    def __repr__(self) -> str:
        """Return a readable marker."""
        return "EPSILON"


#: Marks a transition side that consumes or emits nothing. Using it on the input
#: side inserts, on the output side deletes; a transducer needs both to relate
#: sequences whose lengths differ.
EPSILON = _Epsilon()

#: One aligned step: what is read, and what is written.
Pair = tuple[Any, Any]

# Composition filter. When one side deletes and the other inserts, the two moves
# are independent and either order produces the same composed path, so exactly one
# order must be allowed or the result is counted twice. The rule adopted is that
# within a run between matches, right-alone moves come before left-alone ones:
# from `_FREE` either kind may be taken, and once a left-alone move has been taken
# no right-alone move may follow until the next match. Two states suffice; a
# three-state filter that forbade both orders would lose the path altogether.
_FREE = 0
_LEFT_ONLY = 1


class Fst(Automaton):
    """An acyclic weighted transducer over ``(input, output)`` pairs.

    Examples:
        >>> fst = Fst.from_pairs([("cat", "chat"), ("dog", "chien")])
        >>> fst.apply("cat")
        [('c', 'h', 'a', 't')]
        >>> fst.apply("cow")
        []

        Ambiguity is allowed, and reported as several results:

        >>> ambiguous = Fst.from_alignments(
        ...     [[("a", "x")], [("a", "y")]]
        ... )
        >>> sorted(ambiguous.apply("a"))
        [('x',), ('y',)]
    """

    __slots__ = ()

    @classmethod
    def from_alignments(
        cls,
        alignments: Iterable[Sequence[Pair]],
        *,
        semiring: Semiring[Any] = BOOLEAN,
    ) -> Fst:
        """Build a transducer from aligned pairs.

        Args:
            alignments: Each alignment is a sequence of ``(input, output)`` pairs, read in
                order. Either side of a pair may be ``EPSILON``.
            semiring: The semiring weights belong to.

        Returns:
            The frozen, minimal transducer.
        """
        return _build([(tuple(a), semiring.one) for a in alignments], semiring, cls)

    @classmethod
    def from_weighted_alignments(
        cls,
        pairs: Iterable[tuple[Sequence[Pair], Any]],
        *,
        semiring: Semiring[Any],
    ) -> Fst:
        """Build a transducer from weighted aligned pairs.

        Args:
            pairs: ``(alignment, weight)`` pairs. Repeated alignments have their weights
                combined with the semiring's ``plus``.
            semiring: The semiring the weights belong to.

        Returns:
            The frozen, minimal transducer.
        """
        return _build([(tuple(a), w) for a, w in pairs], semiring, cls)

    @classmethod
    def from_pairs(
        cls,
        pairs: Iterable[tuple[Sequence[Token], Sequence[Token]]],
        *,
        semiring: Semiring[Any] = BOOLEAN,
    ) -> Fst:
        """Build a transducer from unaligned sequence pairs.

        Convenience only. The two sides are zipped position by position and the
        shorter one padded with ``EPSILON`` at the end. That is *an*
        alignment, not the right one for any particular linguistic purpose — for
        that, align deliberately and use ``from_alignments``.

        Args:
            pairs: ``(input, output)`` sequence pairs.
            semiring: The semiring weights belong to.

        Returns:
            The frozen, minimal transducer.
        """
        return cls.from_alignments(
            (align(source, target) for source, target in pairs), semiring=semiring
        )

    def apply(self, sequence: Sequence[Token]) -> list[tuple[Token, ...]]:
        """Return every output the transducer relates to ``sequence``.

        Args:
            sequence: The input tokens.

        Returns:
            Each output, in the alphabet's order. Empty when the input is not
            related to anything, several when the transducer is ambiguous.
        """
        tokens = tuple(sequence)
        results: list[tuple[Token, ...]] = []

        # Each item is a state, how much input is consumed, and what has been
        # emitted. An epsilon input side advances the automaton without advancing
        # the input, which is what lets outputs be longer than inputs.
        stack: list[tuple[State, int, tuple[Token, ...]]] = [(ROOT, 0, ())]
        while stack:
            state, consumed, emitted = stack.pop()
            if consumed == len(tokens) and self.is_final(state):
                results.append(emitted)

            for index in self.transition_indices(state):
                source, target = self._pair(index)
                if source is EPSILON:
                    following = consumed
                elif consumed < len(tokens) and source == tokens[consumed]:
                    following = consumed + 1
                else:
                    continue

                extended = emitted if target is EPSILON else (*emitted, target)
                stack.append((self.transition_target(index), following, extended))

        return sorted(results, key=self._sort_key)

    def project(self, side: str = "input") -> Dafsa:
        """Return the acceptor for one side of the relation.

        Args:
            side: ``"input"`` or ``"output"``.

        Returns:
            The minimal acceptor for the projected sequences, with epsilons
            removed.

        Raises:
            ValueError: If ``side`` is neither ``"input"`` nor ``"output"``.

        Notes:
            The projection is **unweighted**. Projecting collapses the distinction
            between paths that shared a side, and reconciling their weights is
            weighted determinization — a genuinely different algorithm, and out of
            scope here. Dropping the weights is the honest option; carrying one
            arbitrary path's weight would not be.
        """
        if side not in {"input", "output"}:
            message = f"side must be 'input' or 'output', not {side!r}"
            raise ValueError(message)

        position = 0 if side == "input" else 1
        projected: dict[State, list[tuple[Token, State]]] = {}
        empty: dict[State, list[State]] = {}

        for state in self.states():
            projected[state] = []
            empty[state] = []
            for index in self.transition_indices(state):
                token = self._pair(index)[position]
                target = self.transition_target(index)
                if token is EPSILON:
                    empty[state].append(target)
                else:
                    projected[state].append((token, target))

        return _determinize(self, projected, empty)

    def _pair(self, index: int) -> Pair:
        """Return the ``(input, output)`` pair a transition carries."""
        return cast("Pair", self._alphabet.token(self.transition_symbol(index)))

    def _sort_key(self, tokens: tuple[Token, ...]) -> tuple[str, ...]:
        """Return an orderable form of an output, for deterministic results."""
        return tuple(f"{token!r}" for token in tokens)


def align(source: Sequence[Token], target: Sequence[Token]) -> list[Pair]:
    """Zip two sequences position by position, padding with ``EPSILON``.

    Args:
        source: The sequence supplying the input side.
        target: The sequence supplying the output side.

    Returns:
        The aligned pairs.

    Examples:
        >>> align("ab", "xyz")
        [('a', 'x'), ('b', 'y'), (EPSILON, 'z')]
    """
    length = max(len(source), len(target))

    return [
        (
            source[position] if position < len(source) else EPSILON,
            target[position] if position < len(target) else EPSILON,
        )
        for position in range(length)
    ]


def compose(left: Fst, right: Fst, *, semiring: Semiring[Any] | None = None) -> Fst:
    """Return the transducer relating ``left``'s input to ``right``'s output.

    The standard product construction: a state of the result is a state of each
    input plus a filter marker, and a transition matches ``left``'s output
    against ``right``'s input.

    Args:
        left: The transducer applied first. Its output alphabet is matched against
            ``right``'s input alphabet by token equality.
        right: The transducer applied second.
        semiring: The semiring of the result. Defaults to ``left``'s.

    Returns:
        The composed transducer.

    Raises:
        DeterminismError: If the composition is ambiguous — if two composed paths carry the same
            ``(input, output)`` pair out of the same state. Resolving that needs
            weighted determinization, which is out of scope; the error names the pair
            so the ambiguity can be found in the inputs.

    Notes:
        Epsilons are filtered after Mohri, Pereira and Riley: without a filter, a
        composition where ``left`` deletes and ``right`` inserts produces the same
        path by several interleavings.

    Examples:
        >>> upper = Fst.from_pairs([("cat", "CAT")])
        >>> reverse = Fst.from_pairs([("CAT", "gato")])
        >>> compose(upper, reverse).apply("cat")
        [('g', 'a', 't', 'o')]
    """
    algebra = semiring if semiring is not None else left.semiring

    pairs: dict[tuple[State, State, int], list[tuple[Pair, Any, Any]]] = {}
    start = (ROOT, ROOT, _FREE)
    seen = {start}
    frontier = [start]

    while frontier:
        node = frontier.pop()
        here, there, filtered = node
        outgoing: list[tuple[Pair, Any, Any]] = []

        for index in left.transition_indices(here):
            source, middle = left._pair(index)
            weight = left.transition_weight(index)
            target = left.transition_target(index)

            if middle is EPSILON:
                # A left-alone move is always available, and closes the door on
                # right-alone moves until the next match.
                outgoing.append(((source, EPSILON), weight, (target, there, _LEFT_ONLY)))
                continue

            for other in right.transition_indices(there):
                pivot, sink = right._pair(other)
                if pivot != middle:
                    continue
                combined = algebra.times(weight, right.transition_weight(other))
                outgoing.append(
                    (
                        (source, sink),
                        combined,
                        (target, right.transition_target(other), _FREE),
                    )
                )

        if filtered == _FREE:
            for other in right.transition_indices(there):
                pivot, sink = right._pair(other)
                if pivot is EPSILON:
                    outgoing.append(
                        (
                            (EPSILON, sink),
                            right.transition_weight(other),
                            (here, right.transition_target(other), _FREE),
                        )
                    )

        pairs[node] = outgoing
        for _, _, successor in outgoing:
            if successor not in seen:
                seen.add(successor)
                frontier.append(successor)

    return _assemble(left, right, pairs, algebra, start)


def _assemble(
    left: Fst,
    right: Fst,
    pairs: dict[tuple[State, State, int], list[tuple[Pair, Any, Any]]],
    semiring: Semiring[Any],
    start: tuple[State, State, int],
) -> Fst:
    """Turn a composed transition map into a frozen transducer."""
    alphabet = Alphabet.from_sequences(
        [[pair for outgoing in pairs.values() for pair, _, _ in outgoing]]
    )
    order = [start, *(node for node in pairs if node != start)]
    numbering = {node: index for index, node in enumerate(order)}

    builder = Builder(alphabet, semiring)
    for _ in range(len(order) - 1):
        builder.new_state()

    for node in order:
        state = numbering[node]
        for pair, weight, successor in pairs[node]:
            symbol = alphabet.id(pair)
            try:
                builder.add_transition(state, symbol, numbering[successor], weight)
            except DeterminismError as error:
                message = (
                    f"composition is ambiguous on {pair!r}: two paths carry the "
                    f"same input and output out of one state, which needs "
                    f"weighted determinization to resolve"
                )
                raise DeterminismError(message) from error
        here, there, _ = node
        if left.is_final(here) and right.is_final(there):
            builder.set_final(
                state,
                weight=semiring.times(left.final_weight(here), right.final_weight(there)),
            )

    return _algorithms.minimize(builder.freeze(Fst), Fst)


def _determinize(
    automaton: Automaton,
    projected: dict[State, list[tuple[Token, State]]],
    empty: dict[State, list[State]],
) -> Dafsa:
    """Subset-construct and minimize an acceptor from a projected transducer.

    Projection turns a deterministic transducer into a nondeterministic acceptor,
    twice over: two pairs may share a side, and an epsilon on the projected side
    consumes nothing. Subset construction resolves both.
    """

    def closure(states: frozenset[State]) -> frozenset[State]:
        reached = set(states)
        frontier = list(states)
        while frontier:
            for target in empty[frontier.pop()]:
                if target not in reached:
                    reached.add(target)
                    frontier.append(target)

        return frozenset(reached)

    start = closure(frozenset({ROOT}))
    subsets = {start: 0}
    order = [start]
    edges: dict[int, list[tuple[Token, int]]] = {}

    head = 0
    while head < len(order):
        subset = order[head]
        head += 1
        grouped: dict[Token, set[State]] = {}
        for state in subset:
            for token, target in projected[state]:
                grouped.setdefault(token, set()).add(target)

        outgoing = []
        for token, targets in grouped.items():
            reached = closure(frozenset(targets))
            if reached not in subsets:
                subsets[reached] = len(order)
                order.append(reached)
            outgoing.append((token, subsets[reached]))
        edges[subsets[subset]] = outgoing

    alphabet = Alphabet.from_sequences(
        [[token for outgoing in edges.values() for token, _ in outgoing]]
    )
    builder = Builder(alphabet)
    for _ in range(len(order) - 1):
        builder.new_state()

    for index, subset in enumerate(order):
        for token, target in edges[index]:
            builder.add_transition(index, alphabet.id(token), target)
        if any(automaton.is_final(state) for state in subset):
            builder.set_final(index)

    return _algorithms.minimize(builder.freeze(), Dafsa)


def _build(
    alignments: list[tuple[tuple[Pair, ...], Any]],
    semiring: Semiring[Any],
    factory: type[Fst],
) -> Fst:
    """Build a transducer from weighted alignments.

    A transducer over pair-tokens is a dictionary of pair-sequences, so this is
    the ordinary construction with the ordinary register — the pairs simply carry
    two things where a token usually carries one.
    """
    # Imported here rather than at module scope: `structures` imports this module.
    from dafsa.structures import build_from_weighted

    return build_from_weighted(alignments, semiring, minimize=True, factory=factory)


__all__ = ["EPSILON", "Fst", "align", "compose"]
