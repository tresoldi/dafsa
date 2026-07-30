"""Finite-state structures for sequence data.

This is the 2.0 development line, a clean break from 1.0. The design, the audit
of 1.0 that motivated it, and the milestone plan are in ``DESIGN.md`` at the root
of the repository.

Currently available is the frozen core the structures are built on: an
:class:`~dafsa.alphabet.Alphabet` mapping tokens to dense symbols, and an
:class:`~dafsa.automaton.Automaton` holding deterministic acyclic transitions as
flat arrays. The user-facing structures (``Trie``, ``Dafsa``, and the rest) land
in later milestones.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from dafsa.alphabet import Alphabet
from dafsa.automaton import ROOT, Automaton, Transition
from dafsa.exceptions import (
    AcyclicityError,
    DafsaError,
    DeterminismError,
    UnknownTokenError,
)

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
    "DafsaError",
    "DeterminismError",
    "Transition",
    "UnknownTokenError",
    "__version__",
]
