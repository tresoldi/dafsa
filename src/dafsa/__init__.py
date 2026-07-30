"""Finite-state structures for sequence data.

This is the 2.0 development line, a clean break from 1.0. The design, the audit
of 1.0 that motivated it, and the milestone plan are in ``DESIGN.md`` at the root
of the repository.

Available now: the frozen core (:class:`~dafsa.alphabet.Alphabet`,
:class:`~dafsa.automaton.Automaton`), the semiring layer
(:mod:`dafsa.semirings`), the dictionary structures :class:`Trie`, :class:`Dafsa` and
:class:`CompactDafsa`, and the counting layer that makes an automaton an index
rather than only a set. The substring and transducer structures land in later
milestones.

Examples
--------
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

from importlib.metadata import PackageNotFoundError, version

from dafsa import semirings
from dafsa.alphabet import Alphabet, tokenize
from dafsa.automaton import ROOT, Automaton, Match, Transition
from dafsa.exceptions import (
    AcyclicityError,
    DafsaError,
    DeterminismError,
    UnknownTokenError,
)
from dafsa.semirings import Semiring
from dafsa.structures import CompactDafsa, Dafsa, Trie

try:
    __version__ = version("dafsa")
except PackageNotFoundError:  # pragma: no cover - source tree without install
    __version__ = "0.0.0.dev0"

__author__ = "Tiago Tresoldi"
__email__ = "tiago.tresoldi@lingfil.uu.se"

__all__ = [
    "ROOT",
    "AcyclicityError",
    "Alphabet",
    "Automaton",
    "CompactDafsa",
    "Dafsa",
    "DafsaError",
    "DeterminismError",
    "Match",
    "Semiring",
    "Transition",
    "Trie",
    "UnknownTokenError",
    "__version__",
    "semirings",
    "tokenize",
]
