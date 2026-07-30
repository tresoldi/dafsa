"""Finite-state structures for sequence data.

This is the 2.0 development line, a clean break from 1.0. The design, the audit
of 1.0 that motivated it, and the milestone plan are in ``DESIGN.md`` at the root
of the repository.

Available now: the frozen core (:class:`~dafsa.alphabet.Alphabet`,
:class:`~dafsa.automaton.Automaton`), the semiring layer
(:mod:`dafsa.semirings`), and the dictionary structures :class:`Trie` and
:class:`Dafsa`. The compacted, substring and transducer structures land in later
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
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from dafsa import semirings
from dafsa.alphabet import Alphabet, tokenize
from dafsa.automaton import ROOT, Automaton, Transition
from dafsa.exceptions import (
    AcyclicityError,
    DafsaError,
    DeterminismError,
    UnknownTokenError,
)
from dafsa.semirings import Semiring
from dafsa.structures import Dafsa, Trie

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
    "Dafsa",
    "DafsaError",
    "DeterminismError",
    "Semiring",
    "Transition",
    "Trie",
    "UnknownTokenError",
    "__version__",
    "semirings",
    "tokenize",
]
