"""Substring indexes: suffix automata and their compacted form.

These answer a different question from the dictionary structures, and the
distinction is worth stating plainly because the two are easy to conflate — this
project's own design document did so at first.

A ``Dafsa`` stores a *set of sequences* and answers "is
this one of them". A ``SuffixAutomaton`` is built from a *single* sequence
and answers "does this occur anywhere inside it". The first is a dictionary; the
second is an index, and it is what makes substring search, repeat detection and
longest-common-substring possible at all.

Likewise ``CompactDafsa`` and ``Cdawg`` are not the
same thing under two names. The first is a path-compacted dictionary; the second
is a path-compacted *suffix* automaton, and the acronym in the literature —
compact directed acyclic word graph — refers only to the latter.

Construction is the online algorithm of Blumer et al., which extends the
automaton one token at a time and occasionally clones a state whose incoming
paths have come to disagree about length. It runs in linear time and produces at
most ``2n - 1`` states and ``3n - 4`` transitions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from dafsa._builder import Builder
from dafsa._types import ROOT
from dafsa.alphabet import Alphabet
from dafsa.automaton import Automaton
from dafsa.semirings import BOOLEAN

if TYPE_CHECKING:
    from collections.abc import Sequence

    from dafsa._types import State, Symbol, Token
    from dafsa.semirings import Semiring

_NO_LINK = -1


class _Cursor:
    """A position inside an automaton, which may be part-way along a label.

    An ordinary automaton has a state for every position a walk can reach. A
    compacted one does not — a transition may consume several tokens, and the
    positions between them are real but nameless. Substring queries have to visit
    those positions, so this tracks one explicitly: a state, and how far into one
    of its outgoing labels the walk has gone.
    """

    __slots__ = ("_automaton", "index", "offset", "state")

    def __init__(self, automaton: Automaton, state: State = ROOT) -> None:
        self._automaton = automaton
        self.state = state
        self.index: int | None = None
        self.offset = 0

    def advance(self, symbol: Symbol) -> bool:
        """Consume one symbol, reporting whether it could be.

        Args:
            symbol: The symbol to consume.

        Returns:
            Whether the walk continued. On ``False`` the cursor is left where it
            was and must be discarded.
        """
        automaton = self._automaton

        if self.index is None:
            index = automaton.transition_index(self.state, symbol)
            if index is None:
                return False
            self.index = index
            self.offset = 1
        else:
            label = automaton.transition_label(self.index)
            if label[self.offset] != symbol:
                return False
            self.offset += 1

        label = automaton.transition_label(self.index)
        if self.offset == len(label):
            self.state = automaton.transition_target(self.index)
            self.index = None
            self.offset = 0

        return True


class _SubstringIndex(Automaton):
    """Queries shared by the suffix automaton and its compacted form."""

    __slots__ = ()

    def contains_substring(self, subsequence: Sequence[Token]) -> bool:
        """Return whether ``subsequence`` occurs anywhere in the indexed sequence.

        Note that this does *not* consult accepting states. A substring is
        present exactly when it can be walked from the root; acceptance is what
        distinguishes a *suffix*, which is a stricter question.

        Args:
            subsequence: The tokens to look for.

        Returns:
            Whether they occur contiguously somewhere in the source.
        """
        symbols = self._alphabet.try_encode(subsequence)
        if symbols is None:
            return False

        cursor = _Cursor(self)

        return all(cursor.advance(symbol) for symbol in symbols)

    def num_substrings(self) -> int:
        """Return how many distinct non-empty subsequences occur in the source.

        Counted structurally rather than by enumeration, so a sequence with
        quadratically many distinct substrings still costs one pass.

        Returns:
            The number of distinct non-empty substrings.

        Examples:
            >>> SuffixAutomaton.from_sequence("banana").num_substrings()
            15
        """
        # walks[q] counts the distinct strings spellable from q, the empty one
        # included. A compacted transition also passes through its label's proper
        # prefixes, which end nowhere in particular but are substrings all the
        # same, so each contributes len(label) - 1 beyond its target's count.
        walks = [0] * self.num_states
        for state in reversed(self.topological_order()):
            total = 1
            for index in self.transition_indices(state):
                label = self.transition_label(index)
                total += len(label) - 1 + walks[self.transition_target(index)]
            walks[state] = total

        return walks[ROOT] - 1

    def longest_common_subsequence_with(self, other: Sequence[Token]) -> tuple[Token, ...]:
        """Return the longest contiguous block ``other`` shares with the source.

        Contiguous, so this is longest *common substring*, not the edit-distance
        sense of the phrase.

        Args:
            other: The sequence to compare against.

        Returns:
            The longest block occurring in both, or ``()`` if they share nothing.
            The first such block is returned when several tie.

        Notes:
            Restarts the walk at each position of ``other``, so the cost is
            O(len(other) x longest match). Linear time needs the suffix links the
            construction builds, and those are discarded when the automaton is
            frozen: they are scaffolding for building, not part of the structure.

        Examples:
            >>> index = SuffixAutomaton.from_sequence("banana")
            >>> "".join(index.longest_common_subsequence_with("bananas"))
            'banana'
            >>> "".join(index.longest_common_subsequence_with("ananas"))
            'anana'
        """
        tokens = tuple(other)
        best_start = 0
        best_length = 0

        for start in range(len(tokens)):
            if len(tokens) - start <= best_length:
                break

            cursor = _Cursor(self)
            length = 0
            for position in range(start, len(tokens)):
                encoded = self._alphabet.try_encode((tokens[position],))
                if encoded is None or not cursor.advance(encoded[0]):
                    break
                length += 1

            if length > best_length:
                best_start, best_length = start, length

        return tokens[best_start : best_start + best_length]


class SuffixAutomaton(_SubstringIndex):
    """The minimal automaton accepting every suffix of one sequence.

    Accepting states mark the suffixes. Every *substring* is walkable from the
    root whether or not it ends at an accepting state, which is why
    ``contains_substring`` ignores acceptance and ``in`` does not.

    Examples:
        >>> index = SuffixAutomaton.from_sequence("banana")
        >>> sorted("".join(s) for s in index)
        ['', 'a', 'ana', 'anana', 'banana', 'na', 'nana']

        Every suffix is accepted; a substring merely occurs. ``nan`` occurs inside
        ``banana`` but is not a suffix of it, and the two queries differ:

        >>> "nan" in index, index.contains_substring("nan")
        (False, True)
        >>> "nana" in index, index.contains_substring("nana")
        (True, True)
        >>> index.contains_substring("bana"), index.contains_substring("nab")
        (True, False)
    """

    __slots__ = ()

    @classmethod
    def from_sequence(
        cls,
        sequence: Sequence[Token],
        *,
        semiring: Semiring[Any] = BOOLEAN,
    ) -> SuffixAutomaton:
        """Build the suffix automaton of ``sequence``.

        Args:
            sequence: The sequence to index. A ``str`` is one token per character.
            semiring: The semiring weights belong to. Every weight is ``one``; the
                parameter exists so an index composes with the rest of the library.

        Returns:
            The frozen index.
        """
        return _build_suffix_automaton(sequence, semiring, cls)

    def compact(self) -> Cdawg:
        """Return the compacted form of this index.

        Returns:
            The compact directed acyclic word graph for the same sequence.
        """
        # Imported here rather than at module scope: it would be a cycle.
        from dafsa import _algorithms

        return _algorithms.compact(self, Cdawg)


class Cdawg(_SubstringIndex):
    """A compact directed acyclic word graph: a path-compacted suffix automaton.

    Produced by ``SuffixAutomaton.compact``. Chains of states that every
    occurrence is forced through collapse into single transitions labelled with
    several tokens, which is what makes the structure small enough to draw and
    cheap enough to store for a long text.

    Every query still takes and returns ordinary token sequences. A substring may
    now end part-way along a label, at a position with no state of its own; the
    queries account for that.

    Examples:
        >>> index = SuffixAutomaton.from_sequence("banana")
        >>> compacted = index.compact()
        >>> compacted.num_states < index.num_states
        True
        >>> compacted.contains_substring("nan"), compacted.contains_substring("nab")
        (True, False)
        >>> compacted.num_substrings() == index.num_substrings()
        True
    """

    __slots__ = ()


def _build_suffix_automaton(
    sequence: Sequence[Token],
    semiring: Semiring[Any],
    factory: type[SuffixAutomaton],
) -> SuffixAutomaton:
    """Construct a suffix automaton by online extension.

    The algorithm of Blumer et al.: each token extends the automaton, and where
    an existing state turns out to represent paths of two different lengths it is
    cloned so that the shorter one can be redirected. That clone is the whole
    subtlety of the construction, and the reason a suffix automaton has at most
    ``2n - 1`` states rather than the ``n + 1`` a naive reading suggests.

    Args:
        sequence: The sequence to index.
        semiring: The semiring for the frozen result.
        factory: The class to freeze into.

    Returns:
        The frozen index.
    """
    tokens = tuple(sequence)
    alphabet = Alphabet.from_sequences([tokens])
    symbols = alphabet.encode(tokens)

    # Construction needs to redirect transitions that already exist, which the
    # builder deliberately does not allow, so it runs on its own scratch
    # structures and the result is handed over afterwards.
    transitions: list[dict[Symbol, int]] = [{}]
    lengths: list[int] = [0]
    links: list[int] = [_NO_LINK]
    last = 0

    def add_state(length: int, link: int, edges: dict[Symbol, int]) -> int:
        transitions.append(edges)
        lengths.append(length)
        links.append(link)

        return len(lengths) - 1

    for symbol in symbols:
        current = add_state(lengths[last] + 1, _NO_LINK, {})

        walker = last
        while walker != _NO_LINK and symbol not in transitions[walker]:
            transitions[walker][symbol] = current
            walker = links[walker]

        if walker == _NO_LINK:
            links[current] = 0
        else:
            existing = transitions[walker][symbol]
            if lengths[walker] + 1 == lengths[existing]:
                links[current] = existing
            else:
                clone = add_state(
                    lengths[walker] + 1,
                    links[existing],
                    dict(transitions[existing]),
                )
                while walker != _NO_LINK and transitions[walker].get(symbol) == existing:
                    transitions[walker][symbol] = clone
                    walker = links[walker]
                links[existing] = clone
                links[current] = clone

        last = current

    # The suffixes are exactly the states on the link chain from the last one.
    accepting = set()
    walker = last
    while walker != _NO_LINK:
        accepting.add(walker)
        walker = links[walker]

    builder = Builder(alphabet, semiring)
    for _ in range(len(lengths) - 1):
        builder.new_state()

    for state, edges in enumerate(transitions):
        for symbol, target in sorted(edges.items()):
            builder.add_transition(state, symbol, target)
        if state in accepting:
            builder.set_final(state)

    return builder.freeze(factory)


__all__ = ["Cdawg", "SuffixAutomaton"]
