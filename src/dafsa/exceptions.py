"""Exceptions raised by the library.

Every exception derives from ``DafsaError``, so callers can catch the whole
family, and additionally from the built-in exception a caller would reasonably
expect, so ``except KeyError`` and ``except ValueError`` keep working.
"""

from __future__ import annotations


class DafsaError(Exception):
    """Base class for every error raised by this library."""


class UnknownTokenError(DafsaError, KeyError):
    """A token is not present in the alphabet.

    Raised when encoding a sequence that contains a token the alphabet was not
    built from. Membership tests do not raise this: an unknown token simply
    means the sequence cannot be accepted.
    """


class DeterminismError(DafsaError, ValueError):
    """A state was given two outgoing transitions on the same symbol.

    The structures in this library are deterministic by construction, so this
    signals a defect in whatever drove the builder.
    """


class AcyclicityError(DafsaError, ValueError):
    """The transitions being frozen contain a cycle.

    Every structure in this library is acyclic; the algorithms that traverse a
    frozen automaton rely on it, so the cycle is rejected at ``freeze()`` rather
    than allowed to cause a non-terminating traversal later.
    """


class ExportError(DafsaError, RuntimeError):
    """An export could not be produced.

    Raised when an external tool an export depends on is missing or fails —
    Graphviz, in practice. The automaton itself is fine; only the rendering of it
    could not be made.
    """


__all__ = [
    "AcyclicityError",
    "DafsaError",
    "DeterminismError",
    "ExportError",
    "UnknownTokenError",
]
