"""Finite-state structures for sequence data.

Sets of sequences are stored as automata in which every shared beginning and every
shared ending is held once. The package structure, the API contract, the audit of
1.0 that motivated the 2.0 rewrite, and the decisions taken along the way are in
``ARCHITECTURE.md`` at the root of the repository.

The pieces: the frozen core (``Alphabet``, ``Automaton``), the semiring layer
(``dafsa.semirings``), the dictionary structures ``Trie``, ``Dafsa`` and
``CompactDafsa``, the substring indexes ``SuffixAutomaton`` and ``Cdawg``, the
counting layer that makes an automaton an index rather than only a set, the
transducers ``Fst``, and ``dafsa.export``.

Examples:
    >>> import dafsa
    >>> automaton = dafsa.Dafsa.from_sequences(["tap", "taps", "top", "tops"])
    >>> "taps" in automaton
    True

    >>> counted = dafsa.Dafsa.from_sequences(
    ...     ["tip", "tip", "tap"], semiring=dafsa.semirings.COUNTING
    ... )
    >>> counted.weight("tip")
    2

    The automaton is also an index over its own language:

    >>> len(automaton), automaton.unrank(0), automaton.rank(("t", "o", "p", "s"))
    (4, ('t', 'a', 'p'), 3)
"""

from __future__ import annotations

from dafsa import export, semirings
from dafsa.alphabet import Alphabet, tokenize
from dafsa.automaton import ROOT, Automaton, Match, Transition
from dafsa.exceptions import (
    AcyclicityError,
    DafsaError,
    DeterminismError,
    ExportError,
    UnknownTokenError,
)
from dafsa.fst import EPSILON, Fst, compose
from dafsa.semirings import Semiring
from dafsa.structures import CompactDafsa, Dafsa, Trie
from dafsa.suffix import Cdawg, SuffixAutomaton

# The single source of the version: ``pyproject.toml`` declares it dynamic and
# reads it from here, so the two cannot drift. ``make bump-version`` edits this
# line and ``CITATION.cff``.
__version__ = "2.0.0"

__author__ = "Tiago Tresoldi"
__email__ = "dafsa@tresoldi.org"

__all__ = [
    "EPSILON",
    "ROOT",
    "AcyclicityError",
    "Alphabet",
    "Automaton",
    "Cdawg",
    "CompactDafsa",
    "Dafsa",
    "DafsaError",
    "DeterminismError",
    "ExportError",
    "Fst",
    "Match",
    "Semiring",
    "SuffixAutomaton",
    "Transition",
    "Trie",
    "UnknownTokenError",
    "__version__",
    "compose",
    "export",
    "semirings",
    "tokenize",
]
