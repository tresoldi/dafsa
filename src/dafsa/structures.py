"""Dictionary structures: tries and minimal acyclic automata.

Both structures are built by the same loop over sorted input. They differ in one
thing: whether a state, once it can no longer change, is looked up in a register
of states already seen. With the register, equivalent states are shared and the
result is the minimal automaton; without it, every path keeps its own states and
the result is a trie.

The construction is Daciuk, Mihov, Watson and Watson (2000). Input is processed in
sorted order, which means that once a sequence has been inserted, everything to
the right of its common prefix with the next sequence can never change again and
is therefore ready to be minimized. That is what makes the algorithm incremental
rather than build-a-trie-then-minimize.

Two details are worth stating, because 1.0 got both wrong:

**The register is a dictionary.** A state is minimized by looking up its
signature — its finality, its final weight, and its outgoing
``(symbol, target, weight)`` triples — in a hash map. 1.0 instead scanned every
state it had kept so far, comparing with ``__eq__``, and restarted the whole pass
whenever anything changed. Its own changelog records the result: 99,171 sequences
in "under 8 minutes".

**Edges are added only once the target is known to be canonical.** The classic
formulation wires a parent to its child immediately and rewires it during
minimization. Here the parent's edge is deferred until its child is popped from
the unchecked chain, by which point the child's own edges are complete and its
canonical representative is known. Nothing is ever rewired, so the builder needs
no mutation of existing transitions, and states that lost to a canonical
representative are simply never referenced — ``freeze()`` prunes them as
unreachable.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

from dafsa import _algorithms
from dafsa._builder import Builder

# State and Symbol are imported at runtime, not under TYPE_CHECKING, because the
# type aliases below are evaluated when this module is imported.
from dafsa._types import State, Symbol
from dafsa.alphabet import Alphabet
from dafsa.automaton import ROOT, Automaton
from dafsa.semirings import BOOLEAN

if TYPE_CHECKING:
    from collections.abc import Hashable, Iterable, Sequence

    from dafsa._types import Token
    from dafsa.semirings import Semiring

#: The concrete structure class a build freezes into.
A = TypeVar("A", bound=Automaton)

#: A state's minimization signature: what makes two states interchangeable.
_Signature = tuple[Any, ...]

#: One link of the chain of states that may still change: parent, symbol, child.
_Unchecked = tuple[State, Symbol, State]


class _Structure(Automaton):
    """Shared behaviour for the dictionary structures.

    Exists so that :meth:`compact` has one home. It lives here rather than on
    :class:`~dafsa.automaton.Automaton` because the result is a
    :class:`CompactDafsa`, and the core must not depend on the structures built
    on top of it.
    """

    __slots__ = ()

    def compact(self) -> CompactDafsa:
        """Return a path-compacted copy of this structure.

        Chains of states that every path is forced through collapse into single
        transitions labelled with several tokens. The language, the weights and
        the accepted order are all unchanged; only the number of states falls.

        Returns
        -------
        CompactDafsa
            A new frozen automaton. This one is untouched.

        Examples
        --------
        >>> automaton = Dafsa.from_sequences(["tapas", "topos"])
        >>> automaton.num_states, automaton.compact().num_states
        (8, 4)
        >>> "tapas" in automaton.compact()
        True
        """
        return _algorithms.compact(self, CompactDafsa)


class Trie(_Structure):
    """A prefix tree: shared prefixes, no shared suffixes.

    A trie is the honest baseline for the comparison this library was originally
    built to illustrate, and it remains useful whenever states need to be
    distinguishable by the prefix that reaches them — which minimization
    destroys, since a shared suffix state is reached by many prefixes.

    Construction costs the same as :class:`Dafsa` minus the register lookups, so
    a trie is never the cheaper choice; it is the choice that keeps prefixes
    distinct.

    Examples
    --------
    >>> trie = Trie.from_sequences(["tap", "taps", "top"])
    >>> "taps" in trie, "ta" in trie
    (True, False)

    One state per distinct prefix — ``t``, ``ta``, ``tap``, ``taps``, ``to``,
    ``top`` — plus the root:

    >>> trie.num_states
    7
    """

    __slots__ = ()

    @classmethod
    def from_sequences(
        cls,
        sequences: Iterable[Sequence[Token]],
        *,
        semiring: Semiring[Any] = BOOLEAN,
    ) -> Trie:
        """Build a trie accepting exactly ``sequences``.

        Parameters
        ----------
        sequences
            The sequences to accept. Each is a sequence of hashable tokens; a
            ``str`` is one token per character.
        semiring
            The semiring weights belong to. With the default, the result is a
            plain acceptor. With :data:`~dafsa.semirings.COUNTING`, each sequence
            contributes ``1``, so a repeated sequence gets its multiplicity.

        Returns
        -------
        Trie
            The frozen trie.
        """
        return _build(
            _unit_weighted(sequences, semiring),
            semiring,
            minimize=False,
            factory=cls,
        )

    @classmethod
    def from_weighted(
        cls,
        pairs: Iterable[tuple[Sequence[Token], Any]],
        *,
        semiring: Semiring[Any],
    ) -> Trie:
        """Build a trie from ``(sequence, weight)`` pairs.

        Parameters
        ----------
        pairs
            The sequences and their weights. Repeated sequences have their
            weights combined with the semiring's ``plus``.
        semiring
            The semiring the weights belong to.

        Returns
        -------
        Trie
            The frozen trie.
        """
        return _build(pairs, semiring, minimize=False, factory=cls)


class Dafsa(_Structure):
    """A minimal deterministic acyclic finite-state automaton.

    Equivalent states are shared, so the structure is as small as a deterministic
    automaton for this language can be. That sharing is what makes state ids
    meaningless as identifiers — a suffix state is reached by every prefix that
    leads to it — and it is why the counting layer, rather than the states
    themselves, is what answers questions about individual sequences.

    Examples
    --------
    >>> dafsa = Dafsa.from_sequences(["tap", "taps", "top", "tops"])
    >>> "tops" in dafsa, "to" in dafsa
    (True, False)

    The shared ``ps`` suffix is stored once, where a trie would store it twice:

    >>> words = ["tap", "taps", "top", "tops"]
    >>> dafsa.num_states < Trie.from_sequences(words).num_states
    True

    Weights mean what they say, which is the thing 1.0 could not do:

    >>> from dafsa.semirings import COUNTING
    >>> counted = Dafsa.from_sequences(["tip", "tip", "tap"], semiring=COUNTING)
    >>> counted.weight("tip"), counted.weight("tap"), counted.weight("nope")
    (2, 1, 0)
    """

    __slots__ = ()

    @classmethod
    def from_sequences(
        cls,
        sequences: Iterable[Sequence[Token]],
        *,
        semiring: Semiring[Any] = BOOLEAN,
    ) -> Dafsa:
        """Build the minimal automaton accepting exactly ``sequences``.

        Parameters
        ----------
        sequences
            The sequences to accept. Each is a sequence of hashable tokens; a
            ``str`` is one token per character. Order does not matter — the
            sorting the algorithm needs is done internally, over encoded symbols
            rather than over the caller's tokens.
        semiring
            The semiring weights belong to. With the default, the result is a
            plain acceptor. With :data:`~dafsa.semirings.COUNTING`, each sequence
            contributes ``1``, so a repeated sequence gets its multiplicity.

        Returns
        -------
        Dafsa
            The frozen, minimal automaton.
        """
        return _build(
            _unit_weighted(sequences, semiring),
            semiring,
            minimize=True,
            factory=cls,
        )

    @classmethod
    def from_weighted(
        cls,
        pairs: Iterable[tuple[Sequence[Token], Any]],
        *,
        semiring: Semiring[Any],
    ) -> Dafsa:
        """Build the minimal automaton from ``(sequence, weight)`` pairs.

        Parameters
        ----------
        pairs
            The sequences and their weights. Repeated sequences have their
            weights combined with the semiring's ``plus``.
        semiring
            The semiring the weights belong to.

        Returns
        -------
        Dafsa
            The frozen, minimal automaton. Minimization is weight-aware: two
            states are shared only if their weights agree as well as their
            transitions, so ``weight(seq)`` returns what ``seq`` was inserted
            with. That is stricter than unweighted minimization and yields more
            states — the price of weights that mean something.
        """
        return _build(pairs, semiring, minimize=True, factory=cls)


class CompactDafsa(_Structure):
    """A path-compacted automaton: transitions may consume several tokens.

    Produced by :meth:`_Structure.compact`. Where an ordinary automaton spends a
    state on each token of a forced chain, this spends one transition on the
    whole chain, which is what makes a drawn automaton readable at any size.

    The token contract is unchanged. Membership, weights, ranking and iteration
    all still take and return sequences of the original tokens; the compound
    labels are an internal matter, visible through
    :meth:`~dafsa.automaton.Automaton.transition_tokens` when a renderer needs
    them.

    Examples
    --------
    >>> compacted = Dafsa.from_sequences(["tapas", "topos"]).compact()
    >>> "tapas" in compacted, "tapa" in compacted
    (True, False)
    >>> sorted("".join(str(t) for t in s) for s in compacted)
    ['tapas', 'topos']

    The single ``t`` transition out of the root now carries the whole forced
    prefix, and 1.0 raised ``IndexError`` on exactly this input:

    >>> compacted.transition_tokens(0)
    ('t',)
    >>> compacted.num_states
    4
    """

    __slots__ = ()


def _unit_weighted(
    sequences: Iterable[Sequence[Token]],
    semiring: Semiring[Any],
) -> list[tuple[Sequence[Token], Any]]:
    """Pair each sequence with the semiring's ``one``.

    Parameters
    ----------
    sequences
        The sequences to weight.
    semiring
        The semiring supplying the unit weight.

    Returns
    -------
    list of tuple
        ``(sequence, one)`` pairs.
    """
    return [(sequence, semiring.one) for sequence in sequences]


def _build(
    pairs: Iterable[tuple[Sequence[Token], Any]],
    semiring: Semiring[Any],
    *,
    minimize: bool,
    factory: type[A],
) -> A:
    """Build a structure from weighted sequences.

    The single construction loop behind both :class:`Trie` and :class:`Dafsa`.

    Parameters
    ----------
    pairs
        ``(sequence, weight)`` pairs.
    semiring
        The semiring the weights belong to.
    minimize
        Whether to share equivalent states through a register.
    factory
        The class to freeze into.

    Returns
    -------
    Automaton
        The frozen structure.
    """
    materialised = [(tuple(sequence), weight) for sequence, weight in pairs]
    alphabet = Alphabet.from_sequences([sequence for sequence, _ in materialised])

    # Sorting encoded symbol tuples rather than the caller's sequences is what
    # makes the sorted-input requirement internal. Tuples of ints always compare;
    # tuples of arbitrary tokens may not, which is the crash 1.0 shipped with.
    encoded = sorted(
        (alphabet.encode(sequence), weight) for sequence, weight in materialised
    )

    builder = Builder(alphabet, semiring)
    register: dict[_Signature, State] | None = {} if minimize else None
    unchecked: list[_Unchecked] = []
    previous: tuple[Symbol, ...] = ()

    for symbols, weight in encoded:
        shared = _common_prefix_length(previous, symbols)
        _settle(builder, unchecked, register, down_to=shared)

        state = unchecked[-1][2] if unchecked else ROOT
        for symbol in symbols[shared:]:
            child = builder.new_state()
            unchecked.append((state, symbol, child))
            state = child

        # `final_weight` is `zero` until a sequence ends here, and `zero` is the
        # identity for `plus`, so first arrival and repeat arrival are one case.
        builder.set_final(
            state,
            weight=semiring.plus(builder.final_weight(state), weight),
        )
        previous = symbols

    _settle(builder, unchecked, register, down_to=0)

    return builder.freeze(factory)


def _common_prefix_length(left: tuple[Symbol, ...], right: tuple[Symbol, ...]) -> int:
    """Return how many leading symbols two encoded sequences share.

    Parameters
    ----------
    left, right
        The encoded sequences to compare.

    Returns
    -------
    int
        The length of the common prefix.
    """
    shared = 0
    for a, b in zip(left, right, strict=False):
        if a != b:
            break
        shared += 1

    return shared


def _settle(
    builder: Builder,
    unchecked: list[_Unchecked],
    register: dict[_Signature, State] | None,
    *,
    down_to: int,
) -> None:
    """Finalise the unchecked chain down to ``down_to``, wiring in each edge.

    Popping from the end means the deepest state settles first, so by the time a
    state is considered its own outgoing edges are all present and its signature
    is complete. That ordering is the whole correctness argument for using a
    register at all.

    Parameters
    ----------
    builder
        The builder being driven.
    unchecked
        The chain of ``(parent, symbol, child)`` links that may still change.
        Truncated in place.
    register
        Signature-to-state map, or ``None`` to skip sharing and build a trie.
    down_to
        How many links to leave in place.
    """
    while len(unchecked) > down_to:
        parent, symbol, child = unchecked.pop()

        target = child
        if register is not None:
            signature = _signature(builder, child)
            existing = register.get(signature)
            if existing is None:
                register[signature] = child
            else:
                # `child` is now referenced by nothing; freeze() prunes it.
                target = existing

        builder.add_transition(parent, symbol, target)


def _signature(builder: Builder, state: State) -> _Signature:
    """Return what makes ``state`` interchangeable with another state.

    Two states may be shared exactly when their signatures match: same finality,
    same final weight, and the same outgoing transitions to the same *canonical*
    targets with the same weights. Weights go through
    :meth:`~dafsa.semirings.Semiring.key` so that a semiring whose values are
    unhashable, or which spells one value several ways, still minimizes.

    Parameters
    ----------
    builder
        The builder holding the state.
    state
        The state to describe. Its children must already be canonical.

    Returns
    -------
    tuple
        A hashable signature.
    """
    semiring = builder.semiring
    final = builder.is_final(state)
    final_key: Hashable = semiring.key(builder.final_weight(state)) if final else None

    return (
        final,
        final_key,
        tuple(
            (transition.symbol, transition.target, semiring.key(transition.weight))
            for transition in builder.transitions(state)
        ),
    )


#: The construction loop, shared with the transducers, which are dictionaries
#: of ``(input, output)`` pairs and need exactly the same machinery.
build_from_weighted = _build

__all__ = ["CompactDafsa", "Dafsa", "Trie", "build_from_weighted"]
